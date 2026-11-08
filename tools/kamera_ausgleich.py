#!/usr/bin/env python3
"""kamera_ausgleich.py - BS3d: GEMEINSAMER Kamera-Ausgleich ueber viele Fotos gegen foto_diff (kosten_lr, kleiner = besser). Generisch.

Aufruf: kamera_ausgleich.py modelle/<obj>/objekt.json --stl NETZ --aus ARBEITSORDNER (--fotos 000,004,.. | --auswahl wichtigkeit.json)
        [--holdout 001,024,..] [--masken ORDNER] [--k-ordner ORDNER] [--kerne 6] [--max-fotos N]

Verfahren (Original-K-Dateien werden NIE geschrieben; Ergebnis = Vorschlag-JSON je Foto + Gesamtbericht):
 1. Fotogruppen (gleiche Bildgroesse +-1 px, f_px innerhalb 5 %, >= 3 Mitglieder = ein Kameratyp/Zoom): GEMEINSAME Parameter lf (ln f-Faktor)
    und dk1 (k1-Zuschlag), angepasst nur auf Nicht-Holdout-Fotos der Gruppe; uebernommen nur, wenn die Mehrzahl der Holdout-Fotos der Gruppe
    UND das Gruppenmittel der Trainingsfotos besser wird (Holdout-Fotos der Gruppe vorhanden; sonst Gruppe verworfen).
 2. Pose je Foto: Drehung um das Kamerazentrum (rx,ry,rz Grad) + kleine Verschiebung in Kamerakoordinaten (tx,ty,tz m), Grenzen +-ROT_MAX/+-T_MAX,
    Regularisierung (quadratisch, gegen die gegebene Buendel-/Ankerlage). Mustersuche (Kompass, erste Verbesserung).
 3. Holdout je Foto in der Pruefhaelfte: Maske am Median-x in A/B teilen; Fit auf A -> Test auf B und umgekehrt. Pose wird nur uebernommen, wenn
    BEIDE Pruefhaelften um mehr als die Rauschgrenze besser werden UND der Fit auf der vollen Maske besser ist. Sonst: Original beibehalten.
 4. Plausibilitaet: modellkanten_px >= MIN_KANTEN_PX (Register BS3e: Punktfassung bei Tele degeneriert), sonst Probe ungueltig.
Messziel ist das GPU-RASTER (foto_diff Standard, FD_RASTER=1).
"""
import os, sys, json, glob, shutil, subprocess, argparse, threading, queue, math, time
import numpy as np
from concurrent.futures import ThreadPoolExecutor

TOOLS = os.path.dirname(os.path.abspath(__file__)); PY = os.environ.get("AUSGLEICH_PY", "/media/oem/scan/venv-seg/bin/python")
POSE = ["rx", "ry", "rz", "tx", "ty", "tz"]
SCHRITT0 = {"rx": 0.3, "ry": 0.3, "rz": 0.2, "tx": 0.06, "ty": 0.06, "tz": 0.06}          # ANNAHME: Startschritte (Grad / m)
SCHRITT_MIN = {"rx": 0.02, "ry": 0.02, "rz": 0.02, "tx": 0.005, "ty": 0.005, "tz": 0.005}
ROT_MAX, T_MAX = 1.5, 0.30                                                                # ANNAHME (Auftrag: Rotation +-1,5 Grad, Translation klein)
SIG_ROT, SIG_T, LAMBDA = 1.0, 0.15, 0.004                                                 # ANNAHME: Regularisierung lambda*sum((p/sigma)^2)
MIN_KANTEN_PX = 20000                                                                     # ANNAHME: darunter degeneriert (BS3e: 70 px bei Tele)
RAUSCH = 0.008     # GEMESSEN (Nullproben syn_null, 0,02 Grad / 5 mm, 8 Richtungen x 3 Fotos): lr-Streuung 0,0026-0,0056 -> 2 sigma; Gewinne darunter = Rauschen
EPS_SUCHE = 0.003   # Mindestverbesserung je Suchschritt (ANNAHME ~ 1 sigma)


def rod(v):
    th = np.linalg.norm(v)
    if th < 1e-12: return np.eye(3)
    k = v / th; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]); return np.eye(3) + math.sin(th) * Kx + (1 - math.cos(th)) * Kx @ Kx


def kamera_neu(K0, p, lf=0.0, dk1=0.0):
    """K0 (dict) + Pose p (rx..tz) + Gruppenparameter -> neue K (Kopie)."""
    import cv2
    K = json.loads(json.dumps(K0)); k = K["kamera"]; R = cv2.Rodrigues(np.array(k["rvec"]))[0]; t = np.array(k["t"])
    Rd = rod(np.radians(np.array([p.get("rx", 0.0), p.get("ry", 0.0), p.get("rz", 0.0)])))
    R2 = Rd @ R; t2 = Rd @ t + np.array([p.get("tx", 0.0), p.get("ty", 0.0), p.get("tz", 0.0)])
    k["rvec"] = cv2.Rodrigues(R2)[0].ravel().tolist(); k["t"] = t2.tolist(); k["f_px"] = k["f_px"] * math.exp(lf); k["k1"] = k.get("k1", 0.0) + dk1
    return K


def regul(p):
    return LAMBDA * sum((p[n] / (SIG_ROT if n[0] == "r" else SIG_T)) ** 2 for n in POSE)


def gruppen(K, minimum=3):
    """K: {foto: K-dict}. Gruppen nach Bildgroesse (+-1 px) und f_px (5 %); Mitglieder >= minimum. Rueckgabe: Liste von Fotolisten."""
    fl = sorted(K, key=lambda n: K[n]["kamera"]["f_px"]); gr = []
    for n in fl:
        k = K[n]["kamera"]; b = k["bild"]
        for g in gr:
            k0 = K[g[0]]["kamera"]
            if abs(k0["bild"][0] - b[0]) <= 1 and abs(k0["bild"][1] - b[1]) <= 1 and abs(math.log(k["f_px"] / K[g[-1]]["kamera"]["f_px"])) < 0.05 and abs(math.log(k["f_px"] / k0["f_px"])) < 0.08: g.append(n); break
        else: gr.append([n])
    return [sorted(g) for g in gr if len(g) >= minimum]


class Bank:
    def __init__(s, objpfad, stl, aus, n_slots, k_ordner=None):
        s.stl, s.aus = stl, aus; s.root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objpfad)))); s.src = os.path.dirname(os.path.abspath(objpfad))
        s.obj = json.load(open(objpfad)); s.kdir = k_ordner or os.path.join(s.src, "messprotokoll")
        s.slots = queue.Queue(); s.lock = threading.Lock(); s.cache = {}; s.log = []; s.n = 0
        s.vram_limit = float(os.environ.get('AUSGLEICH_VRAM_MB', 6000)); s.vram_used = 0.0; s.cv = threading.Condition(); s.ausfall = {}   # foto -> [endgueltig gescheitert, Proben]
        for i in range(n_slots):
            d = os.path.join(aus, f"slot{i}", "modelle", os.path.basename(s.src)); os.makedirs(os.path.join(d, "messprotokoll"), exist_ok=True)
            o = dict(s.obj)
            for k in ("stl", "masstabelle", "elemente", "audit", "fotos_dir"):
                if k in o: o[k] = os.path.join(s.root, o[k])
            json.dump(o, open(os.path.join(d, "objekt.json"), "w"))
            for n in os.listdir(s.src):
                if n not in ("messprotokoll", "objekt.json") and not os.path.lexists(os.path.join(d, n)): os.symlink(os.path.join(s.src, n), os.path.join(d, n))
            s.slots.put(d)

    def gewicht(s, foto):
        """VRAM-Gewicht (MiB) eines Raster-Laufs: ANNAHME 3.0e-4 MiB je Bildpixel, bewusst konservativ (Messung: 073 mit 20 Mpx = 3,55 GiB, 4 Laeufe a 10 Mpx ~ 4,9 GiB; Lauf mit 1.8e-4 hatte noch OOM), mind. 800."""
        try: w, h = s.K(foto)["kamera"]["bild"]; return max(800.0, w * h * 3.0e-4)
        except Exception: return 2000.0

    def _smi_frei(s):
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.split(",")
            return float(r[0]) - float(r[1])
        except Exception: return 1e9      # keine GPU-Abfrage moeglich -> nur eigene Summe zaehlt

    def vram_hol(s, g):
        with s.cv:
            while (s.vram_used > 0 and s.vram_used + g > s.vram_limit) or s._smi_frei() < 600: s.cv.wait(timeout=2)   # eigene Summe + Fremdbelegung (nvidia-smi) beachten
            s.vram_used += g; s.vram_spitze = max(getattr(s, "vram_spitze", 0.0), s.vram_used)

    def vram_gib(s, g):
        with s.cv: s.vram_used -= g; s.cv.notify_all()

    def K(s, foto): return json.load(open(os.path.join(s.kdir, f"K-{foto}.json")))

    def _fd(s, d, foto, extra, o):
        env = dict(os.environ, FD_RASTER="1"); env.pop("CUDA_VISIBLE_DEVICES", None)
        return subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "foto_diff.py"), os.path.join(d, "objekt.json"), foto, "--stl", s.stl, "--aus", o] + extra, capture_output=True, text=True, env=env)

    def maske_erzeugen(s, foto, ziel):
        d = s.slots.get()
        try:
            json.dump(s.K(foto), open(os.path.join(d, "messprotokoll", f"K-{foto}.json"), "w")); o = os.path.join(d, "aus"); shutil.rmtree(o, ignore_errors=True)
            s._fd(d, foto, ["--maske-aus", ziel], o); shutil.rmtree(o, ignore_errors=True)
        finally: s.slots.put(d)
        return os.path.exists(ziel)

    def eval(s, foto, K, maske, tag=""):
        """-> dict(lr, kanten, versatz) oder None (ungueltig). K = vollstaendige K-Datei (dict)."""
        key = (foto, maske, json.dumps(K["kamera"], sort_keys=True))
        with s.lock:
            if key in s.cache: return s.cache[key]
        g = s.gewicht(foto); s.vram_hol(g); d = s.slots.get(); r = None; verloren = False
        try:
            json.dump(K, open(os.path.join(d, "messprotokoll", f"K-{foto}.json"), "w")); o = os.path.join(d, "aus"); shutil.rmtree(o, ignore_errors=True)
            for versuch in range(4):       # voruebergehende GPU-Fehler (VRAM-Konkurrenz) wiederholen; Fehlschlag + stderr im Protokoll fehler.log
                shutil.rmtree(o, ignore_errors=True); pr = s._fd(d, foto, ["--bewertung-maske", maske, "--glaettung", "0.18"], o); j = glob.glob(os.path.join(o, "foto_diff_*.json"))
                if j: break
                with s.lock: open(os.path.join(s.aus, "fehler.log"), "a").write(f"{foto} {os.path.basename(maske)} versuch {versuch} rc={pr.returncode}: {pr.stderr[-400:]}\n")
                time.sleep(3 * (versuch + 1))
            if j:
                e = json.load(open(j[0])); kp = e.get("modellkanten_px") or 0
                if e.get("kosten_lr") is not None and kp >= MIN_KANTEN_PX: r = dict(lr=e["kosten_lr"], kanten=kp, versatz=(e.get("versatz") or {}).get("versatz_m"))
                else: r = dict(lr=None, kanten=kp, versatz=None)
            else: verloren = True      # nach allen Wiederholungen kein Ergebnis (OOM/Absturz) = verlorene Probe
            shutil.rmtree(o, ignore_errors=True)
        finally: s.slots.put(d); s.vram_gib(g)
        with s.lock:
            a_ = s.ausfall.setdefault(foto, [0, 0]); a_[1] += 1; a_[0] += int(verloren)
            s.cache[key] = r; s.n += 1; s.log.append(dict(foto=foto, tag=tag, maske=os.path.basename(maske), lr=None if r is None else r["lr"]))
            print(f"[{tag}] {foto} {os.path.basename(maske)} -> {None if r is None else (r['lr'], r['kanten'])}", flush=True)
        return r


def lr_von(r): return None if r is None or r.get("lr") is None else r["lr"]


def pose_suche(bank, foto, K0, maske, start, max_proben, lf=0.0, dk1=0.0, tag="pose"):
    """Kompasssuche ueber POSE, Ziel kosten_lr + Regularisierung. -> (best p, lr_best, lr_start, proben)."""
    def f(p):
        r = bank.eval(foto, kamera_neu(K0, p, lf, dk1), maske, tag); v = lr_von(r)
        return None if v is None else v + regul(p)
    best = dict(start); fb = f(best); n = 1
    if fb is None: return best, None, None, n
    lr0 = fb - regul(best); sch = dict(SCHRITT0)
    while n < max_proben and any(sch[k] >= SCHRITT_MIN[k] for k in POSE):
        verb = False
        for k in POSE:
            if sch[k] < SCHRITT_MIN[k]: continue
            for sg in (+1, -1):
                c = dict(best); c[k] = best[k] + sg * sch[k]; lim = ROT_MAX if k[0] == "r" else T_MAX
                if abs(c[k]) > lim: continue
                v = f(c); n += 1
                if v is not None and v < fb - EPS_SUCHE: fb, best, verb = v, c, True; break
            if n >= max_proben: break
        if not verb:
            for k in POSE: sch[k] /= 2
    return best, fb - regul(best), lr0, n


def haelften(maske, aus):
    import cv2
    m = cv2.imread(maske, cv2.IMREAD_GRAYSCALE) > 0; xs = np.where(m)[1]; xm = int(np.median(xs)); A = m.copy(); B = m.copy(); A[:, xm:] = False; B[:, :xm] = False
    os.makedirs(aus, exist_ok=True); b = os.path.basename(maske)[:-4]; pa = os.path.join(aus, b + "_A.png"); pb = os.path.join(aus, b + "_B.png")
    cv2.imwrite(pa, A.astype(np.uint8) * 255); cv2.imwrite(pb, B.astype(np.uint8) * 255); return pa, pb, xm


NULL = {n: 0.0 for n in POSE}


def foto_ausgleich(bank, foto, K0, maske, aus_m, proben, proben_h, lf=0.0, dk1=0.0, holdout=True):
    """Pose eines Fotos mit A/B-Pruefung. -> Ergebnis-dict."""
    out = dict(foto=foto, maske=maske)
    r0 = bank.eval(foto, kamera_neu(K0, NULL, lf, dk1), maske, "basis"); out["lr_start"] = lr_von(r0); out["kanten_px"] = None if r0 is None else r0["kanten"]
    if out["lr_start"] is None: out["status"] = "ungueltig (Modellkanten < %d px)" % MIN_KANTEN_PX; out["p"] = dict(NULL); return out
    best, lrb, lr0, n = pose_suche(bank, foto, K0, maske, NULL, proben, lf, dk1, "voll"); out["p_voll"] = best; out["lr_voll_fit"] = lrb; out["proben"] = n
    out["p"] = dict(NULL); out["lr_nachher"] = out["lr_start"]; out["uebernommen"] = False
    if not holdout: out["uebernommen"] = lrb < lr0 - 1e-4; out["p"] = best if out["uebernommen"] else dict(NULL); out["lr_nachher"] = lrb if out["uebernommen"] else lr0; return out
    pa, pb, xm = haelften(maske, aus_m); h = {}
    for fit, pr, nm in ((pa, pb, "A->B"), (pb, pa, "B->A")):
        b2, f2, s2, n2 = pose_suche(bank, foto, K0, fit, NULL, proben_h, lf, dk1, "hold-" + nm)
        if f2 is None: h[nm] = None; continue
        pr0 = lr_von(bank.eval(foto, kamera_neu(K0, NULL, lf, dk1), pr, "hold-pr0")); pr1 = lr_von(bank.eval(foto, kamera_neu(K0, b2, lf, dk1), pr, "hold-pr1"))
        h[nm] = dict(p=b2, fit_vorher=s2, fit_nachher=f2, pruef_vorher=pr0, pruef_nachher=pr1, gewinn=None if pr0 is None or pr1 is None else pr0 - pr1)
    out["holdout"] = h
    ok = all(v is not None and v["gewinn"] is not None and v["gewinn"] > RAUSCH for v in h.values()) and (lr0 - lrb) > RAUSCH
    out["uebernommen"] = bool(ok)
    if ok:
        out["p"] = best; r1 = bank.eval(foto, kamera_neu(K0, best, lf, dk1), maske, "nachher"); out["lr_nachher"] = lr_von(r1)
    return out


def gruppen_suche(bank, mitglieder, K, masken, train, hold, proben, ex):
    """Gemeinsame lf, dk1 auf train; Pruefung auf hold. -> dict."""
    def summe(lf, dk1, liste):
        rs = list(ex.map(lambda n: lr_von(bank.eval(n, kamera_neu(K[n], NULL, lf, dk1), masken[n], "gruppe")), liste))
        return None if any(r is None for r in rs) else float(np.mean(rs)), rs
    st = {"lf": 0.01, "dk1": 0.02}; mn = {"lf": 0.001, "dk1": 0.002}; p = {"lf": 0.0, "dk1": 0.0}
    fb, r_start = summe(0, 0, train); n = 1
    if fb is None: return dict(status="ungueltig")
    while n < proben and any(st[k] >= mn[k] for k in st):
        verb = False
        for k in ("lf", "dk1"):
            if st[k] < mn[k]: continue
            for sg in (1, -1):
                c = dict(p); c[k] += sg * st[k]; v, _ = summe(c["lf"], c["dk1"], train); n += 1
                if v is not None and v < fb - EPS_SUCHE: fb, p, verb = v, c, True; break
        if not verb: st = {k: v / 2 for k, v in st.items()}
    res = dict(mitglieder=mitglieder, train=train, hold=hold, lf=p["lf"], dk1=p["dk1"], train_vorher=float(np.mean(r_start)), train_nachher=fb, proben=n)
    if hold:
        v0, h0 = summe(0, 0, hold); v1, h1 = summe(p["lf"], p["dk1"], hold)
        res.update(hold_vorher=h0, hold_nachher=h1, hold_besser=int(sum(1 for a, b in zip(h0, h1) if a is not None and b is not None and b < a - RAUSCH)))
        res["uebernommen"] = bool(v0 is not None and v1 is not None and v1 < v0 - RAUSCH and res["hold_besser"] > len(hold) / 2 and fb < float(np.mean(r_start)) - RAUSCH)
    else: res["uebernommen"] = False; res["grund"] = "kein Holdout-Foto in der Gruppe"
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--fotos"); ap.add_argument("--auswahl", help="JSON mit Liste 'auswahl' (Dateinamen) - nur Fotos mit K-Datei und Maske"); ap.add_argument("--holdout", default="")
    ap.add_argument("--masken", help="Ordner mit C_<nr>.png / <nr>.png; fehlende werden mit foto_diff --maske-aus erzeugt"); ap.add_argument("--k-ordner"); ap.add_argument("--kerne", type=int, default=6)
    ap.add_argument("--max-fotos", type=int, default=0); ap.add_argument("--proben", type=int, default=70); ap.add_argument("--proben-hold", type=int, default=45)
    ap.add_argument("--ohne-gruppen", action="store_true"); a = ap.parse_args(argv)
    os.makedirs(a.aus, exist_ok=True); bank = Bank(a.objekt, a.stl, a.aus, a.kerne, a.k_ordner); ex = ThreadPoolExecutor(a.kerne)
    if a.fotos: fotos = a.fotos.split(",")
    else:
        fotos = [os.path.splitext(x)[0] for x in json.load(open(a.auswahl))["auswahl"]]
    hold = [x for x in a.holdout.split(",") if x]
    fotos = [f for f in dict.fromkeys(fotos + hold) if os.path.exists(os.path.join(bank.kdir, f"K-{f}.json"))]
    if a.max_fotos: fotos = fotos[:a.max_fotos]
    md = os.path.join(a.aus, "masken"); os.makedirs(md, exist_ok=True); masken = {}
    def mask_hol(f):
        for q in ([os.path.join(a.masken, f"C_{f}.png"), os.path.join(a.masken, f"{f}.png")] if a.masken else []):
            if os.path.exists(q): return q
        z = os.path.join(md, f"{f}.png")
        if not os.path.exists(z) and not bank.maske_erzeugen(f, z): return None
        return z
    for f, m in zip(fotos, ex.map(mask_hol, fotos)):
        if m: masken[f] = m
    fotos = [f for f in fotos if f in masken]; K = {f: bank.K(f) for f in fotos}
    out = dict(stl=a.stl, objekt=a.objekt, fotos=fotos, holdout=[h for h in hold if h in fotos], konstanten=dict(ROT_MAX=ROT_MAX, T_MAX=T_MAX, SIG_ROT=SIG_ROT, SIG_T=SIG_T, LAMBDA=LAMBDA, MIN_KANTEN_PX=MIN_KANTEN_PX, RAUSCH=RAUSCH), gruppen=[], fotos_ergebnis={})
    t0 = time.time(); gp = {f: (0.0, 0.0) for f in fotos}
    if not a.ohne_gruppen:
        for g in gruppen({f: K[f] for f in fotos}):
            tr = [f for f in g if f not in hold]; ho = [f for f in g if f in hold]
            if len(tr) < 2: continue
            r = gruppen_suche(bank, g, K, masken, tr, ho, 40, ex); out["gruppen"].append(r)
            if r.get("uebernommen"):
                for f in g: gp[f] = (r["lf"], r["dk1"])
    def job(f):
        lf, dk1 = gp[f]
        return foto_ausgleich(bank, f, K[f], masken[f], os.path.join(md, "h"), a.proben, a.proben_hold, lf, dk1)
    for f, r in zip(fotos, ex.map(job, fotos)):
        r["gruppe_lf_dk1"] = gp[f]; r["holdout_foto"] = f in hold
        if r.get("lr_start") is not None and r.get("uebernommen") is not None:
            pass
        # Gruppeneffekt allein (ohne Pose)
        r["lr_original"] = lr_von(bank.eval(f, K[f], masken[f], "orig")); r["lr_gruppe_allein"] = lr_von(bank.eval(f, kamera_neu(K[f], NULL, *gp[f]), masken[f], "grp")) if gp[f] != (0.0, 0.0) else r["lr_original"]
        Kn = kamera_neu(K[f], r["p"], *gp[f]); r["lr_endgueltig"] = lr_von(bank.eval(f, Kn, masken[f], "end"))
        r["vorschlag"] = dict(rvec=Kn["kamera"]["rvec"], t=Kn["kamera"]["t"], f_px=Kn["kamera"]["f_px"], k1=Kn["kamera"]["k1"], K_original=os.path.join(bank.kdir, f"K-{f}.json"))
        out["fotos_ergebnis"][f] = r; json.dump(r, open(os.path.join(a.aus, f"vorschlag_{f}.json"), "w"), indent=1)
    # Gueltigkeit: Fotos mit > 2 % endgueltig verlorenen Proben (OOM/Absturz) gelten NICHT als bewertet
    out["vram_spitze_mib"] = getattr(bank, "vram_spitze", None); out["ausfall"] = {f: dict(verloren=v[0], proben=v[1], anteil=round(v[0] / max(v[1], 1), 4)) for f, v in bank.ausfall.items()}
    fl = os.path.join(a.aus, "fehler.log"); out["fehler_log_zeilen"] = sum(1 for _ in open(fl)) if os.path.exists(fl) else 0; out["gueltig_gesamt"] = out["fehler_log_zeilen"] == 0   # Auftrag: nur gueltig wenn fehler.log leer
    ungueltig = [f for f, v in out["ausfall"].items() if v["anteil"] > 0.02]; out["ungueltig_oom"] = ungueltig
    for f in ungueltig:
        if f in out["fotos_ergebnis"]: out["fotos_ergebnis"][f]["status"] = "UNGUELTIG (OOM-Ausfall %.1f %%) - nachrechnen mit --kerne 1" % (100 * out["ausfall"][f]["anteil"]); out["fotos_ergebnis"][f]["uebernommen"] = False
    # Gesamtbericht
    def stat(liste):
        v = [(out["fotos_ergebnis"][f]["lr_original"], out["fotos_ergebnis"][f]["lr_endgueltig"]) for f in liste if f in out["fotos_ergebnis"] and f not in ungueltig and out["fotos_ergebnis"][f]["lr_original"] is not None and out["fotos_ergebnis"][f]["lr_endgueltig"] is not None]
        if not v: return None
        return dict(n=len(v), mittel_vorher=float(np.mean([x[0] for x in v])), mittel_nachher=float(np.mean([x[1] for x in v])), besser=sum(1 for x in v if x[1] < x[0] - 1e-4), schlechter=sum(1 for x in v if x[1] > x[0] + 1e-4), unveraendert=sum(1 for x in v if abs(x[1] - x[0]) <= 1e-4))
    out["bericht"] = dict(training=stat([f for f in fotos if f not in hold]), holdout=stat([f for f in fotos if f in hold]), uebernommen=[f for f in fotos if out["fotos_ergebnis"][f].get("uebernommen")], proben_gesamt=bank.n, sekunden=round(time.time() - t0))
    json.dump(out, open(os.path.join(a.aus, "ausgleich_bericht.json"), "w"), indent=1)
    print("FERTIG", json.dumps(out["bericht"]), flush=True)


if __name__ == "__main__": main()
