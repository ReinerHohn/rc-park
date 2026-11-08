#!/usr/bin/env python3
"""kamera_feinlage.py - BS3b/BS3c: Kamera-Feinlage je Foto ueber foto_diff (kosten_lr, kleiner = besser).

Sucht kleine Aenderungen von Rotation (3 Achsen um das Kamerazentrum, Grad), Brennweite (Faktor) und k1, die kosten_lr minimieren.
Mustersuche (Koordinatenabstieg, alle +/- Proben eines Schritts parallel, Schrittweite halbieren wenn nichts besser).
Die Original-K-Dateien werden NIE geschrieben: je Probe wird eine Kopie in einem Arbeitsordner (Objektordner-Kopie mit absoluten Pfaden) abgelegt;
foto_diff.k_datei findet sie dort zuerst (Objektordner/messprotokoll). Ergebnis = Vorschlag-JSON, nicht K-*.json.
Holdout (--holdout): Maske in linke/rechte Haelfte (am Median-x der Maskenpixel) teilen, auf einer Haelfte optimieren, auf der anderen pruefen.

Aufruf: kamera_feinlage.py modelle/<obj>/objekt.json FOTO --stl NETZ --maske MASKE.png --aus ARBEITSORDNER [--varianten voll,k1fest,nurrot] [--holdout]
"""
import os, sys, json, glob, shutil, subprocess, argparse, threading, queue, math, time
import numpy as np
from concurrent.futures import ThreadPoolExecutor

TOOLS = os.path.dirname(os.path.abspath(__file__)); PY = os.environ.get("FEINLAGE_PY", "/media/oem/scan/venv-seg/bin/python")
NAMEN = ["rx", "ry", "rz", "lf", "k1"]       # rx..rz Grad (Kamera-Achsen), lf = ln(f-Faktor), k1 absolut
SCHRITT0 = {"rx": 0.4, "ry": 0.4, "rz": 0.3, "lf": 0.01, "k1": 0.03}     # ANNAHME: Startschritte; Halbierung bis SCHRITT_MIN
SCHRITT_MIN = {"rx": 0.03, "ry": 0.03, "rz": 0.03, "lf": 0.001, "k1": 0.003}


def rod(v):
    th = np.linalg.norm(v)
    if th < 1e-12: return np.eye(3)
    k = v / th; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]); return np.eye(3) + math.sin(th) * Kx + (1 - math.cos(th)) * Kx @ Kx


def rvec_of(R):
    import cv2
    return cv2.Rodrigues(R)[0].ravel()


class Werkbank:
    def __init__(s, objpfad, foto, stl, aus, n_slots):
        s.foto, s.stl, s.aus = foto, stl, aus; s.root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(objpfad))))
        s.src = os.path.dirname(os.path.abspath(objpfad)); s.obj = json.load(open(objpfad)); s.K0 = None
        kp = None
        sys.path.insert(0, TOOLS); import fehlteile_finden as FF
        kp = FF.k_datei(objpfad, s.obj, s.root, foto); s.K0 = json.load(open(kp)); s.kpfad = kp
        s.slots = queue.Queue(); s.log = []; s.lock = threading.Lock(); s.cache = {}
        for i in range(n_slots):
            d = os.path.join(aus, f"slot{i}", "modelle", os.path.basename(s.src)); os.makedirs(os.path.join(d, "messprotokoll"), exist_ok=True)
            o = dict(s.obj)
            for k in ("stl", "masstabelle", "elemente", "audit", "fotos_dir"):
                if k in o: o[k] = os.path.join(s.root, o[k])
            json.dump(o, open(os.path.join(d, "objekt.json"), "w"))
            for n in os.listdir(s.src):
                if n not in ("messprotokoll", "objekt.json") and not os.path.lexists(os.path.join(d, n)): os.symlink(os.path.join(s.src, n), os.path.join(d, n))
            s.slots.put(d)

    def kamera(s, p):
        K = json.loads(json.dumps(s.K0)); k = K["kamera"]; R = np.array(__import__("cv2").Rodrigues(np.array(k["rvec"]))[0]); t = np.array(k["t"])
        Rd = rod(np.radians(np.array([p["rx"], p["ry"], p["rz"]])))          # Drehung um das Kamerazentrum: R' = Rd R, t' = Rd t
        k["rvec"] = rvec_of(Rd @ R).tolist(); k["t"] = (Rd @ t).tolist(); k["f_px"] = k["f_px"] * math.exp(p["lf"]); k["k1"] = k.get("k1", 0.0) if p.get("k1") is None else p["k1"]
        return K

    def eval(s, p, maske, tag=""):
        key = (tuple(round(p[n], 6) for n in NAMEN), maske)
        with s.lock:
            if key in s.cache: return s.cache[key]
        d = s.slots.get()
        try:
            K = s.kamera(dict(p, k1=p["k1"])); json.dump(K, open(os.path.join(d, "messprotokoll", f"K-{s.foto}.json"), "w"))
            o = os.path.join(d, "aus"); shutil.rmtree(o, ignore_errors=True)
            env = dict(os.environ, CUDA_VISIBLE_DEVICES="", FD_RASTER="0")
            r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "foto_diff.py"), os.path.join(d, "objekt.json"), s.foto, "--stl", s.stl, "--aus", o, "--bewertung-maske", maske, "--glaettung", "0.18"], capture_output=True, text=True, env=env)
            j = glob.glob(os.path.join(o, "foto_diff_*.json")); v = None; vm = None
            if j:
                e = json.load(open(j[0])); v = e.get("kosten_lr"); vm = (e.get("versatz") or {}).get("versatz_m")
            shutil.rmtree(o, ignore_errors=True)
        finally: s.slots.put(d)
        with s.lock:
            s.cache[key] = (v, vm); s.log.append(dict(tag=tag, maske=os.path.basename(maske), **{n: p[n] for n in NAMEN}, kosten_lr=v, versatz_m=vm))
            print(f"[{tag}] {os.path.basename(maske)} " + " ".join(f"{n}={p[n]:+.4f}" for n in NAMEN) + f" -> lr={v} versatz={vm}", flush=True)
        return s.cache[key]


def suche(wb, maske, frei, start, tag, max_proben, ex):
    best = dict(start); fb, vm = wb.eval(best, maske, tag); n = 1
    if fb is None: raise SystemExit("Startprobe ohne Ergebnis")
    sch = {k: SCHRITT0[k] for k in frei}
    while n < max_proben and any(sch[k] >= SCHRITT_MIN[k] for k in frei):
        cand = []
        for k in frei:
            if sch[k] < SCHRITT_MIN[k]: continue
            for sg in (+1, -1): c = dict(best); c[k] += sg * sch[k]; cand.append(c)
        res = list(ex.map(lambda c: wb.eval(c, maske, tag)[0], cand)); n += len(cand)
        ok = [(r, c) for r, c in zip(res, cand) if r is not None]
        if ok and min(ok, key=lambda x: x[0])[0] < fb - 1e-4:
            fb, best = min(ok, key=lambda x: x[0])[0], min(ok, key=lambda x: x[0])[1]
            # Schritt je Achse beibehalten (Mustersuche: nur bei Misserfolg halbieren)
        else:
            for k in frei: sch[k] /= 2
    return best, fb, n


def haelften(maske, aus):
    import cv2
    m = cv2.imread(maske, cv2.IMREAD_GRAYSCALE) > 0; xs = np.where(m)[1]; xm = int(np.median(xs)); A = m.copy(); B = m.copy(); A[:, xm:] = False; B[:, :xm] = False
    os.makedirs(aus, exist_ok=True); pa = os.path.join(aus, os.path.basename(maske)[:-4] + "_A.png"); pb = os.path.join(aus, os.path.basename(maske)[:-4] + "_B.png")
    cv2.imwrite(pa, A.astype(np.uint8) * 255); cv2.imwrite(pb, B.astype(np.uint8) * 255); return pa, pb, xm


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--stl", required=True); ap.add_argument("--maske", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--varianten", default="voll,k1fest,nurrot"); ap.add_argument("--proben", type=int, default=90, help="Obergrenze Proben je Variante und Suche"); ap.add_argument("--kerne", type=int, default=6)
    ap.add_argument("--holdout", action="store_true"); ap.add_argument("--holdout-varianten", default="voll"); ap.add_argument("--holdout-proben", type=int, default=0); a = ap.parse_args(argv)
    os.makedirs(a.aus, exist_ok=True); wb = Werkbank(a.objekt, a.foto, a.stl, a.aus, a.kerne); ex = ThreadPoolExecutor(a.kerne)
    k1_0 = wb.K0["kamera"].get("k1", 0.0); start = dict(rx=0.0, ry=0.0, rz=0.0, lf=0.0, k1=k1_0)
    FREI = {"voll": ["rx", "ry", "rz", "lf", "k1"], "k1fest": ["rx", "ry", "rz", "lf"], "nurrot": ["rx", "ry", "rz"]}
    out = dict(foto=a.foto, stl=a.stl, maske=a.maske, K_original=wb.kpfad, k0=dict(f_px=wb.K0["kamera"]["f_px"], k1=k1_0), varianten={}, holdout={})
    kopf = wb.eval(start, a.maske, "basis")[0]; out["kosten_lr_basis"] = kopf
    ms = {"voll": a.maske}
    if a.holdout: pa, pb, xm = haelften(a.maske, os.path.join(a.aus, "masken")); out["holdout_xsplit"] = xm
    for v in a.varianten.split(","):
        st = dict(start)
        if v == "k1fest": st["k1"] = 0.0       # Variante: k1 fest 0 (statt gebuendelter Wert)
        if v == "nurrot": pass
        b, fb, n = suche(wb, a.maske, FREI[v], st, v, a.proben, ex)
        fk = wb.eval(st, a.maske, v + "-start")[0]
        out["varianten"][v] = dict(start=st, start_lr=fk, best=b, kosten_lr=fb, proben=n, f_px=wb.K0["kamera"]["f_px"] * math.exp(b["lf"]), k1=b["k1"])
    if a.holdout:
        for fit, pr, nm in ((pa, pb, "A->B"), (pb, pa, "B->A")):
            for v in a.holdout_varianten.split(","):
                st = dict(start)
                if v == "k1fest": st["k1"] = 0.0
                b, fb, n = suche(wb, fit, FREI[v], st, f"hold-{nm}-{v}", a.holdout_proben or a.proben, ex)
                base_fit = wb.eval(st, fit, "hold")[0]; base_pr = wb.eval(st, pr, "hold")[0]; pr_best = wb.eval(b, pr, "hold")[0]; pr_orig = wb.eval(start, pr, "hold")[0]
                out["holdout"][f"{nm}:{v}"] = dict(fit_start=base_fit, fit_best=fb, pruef_original=pr_orig, pruef_start=base_pr, pruef_best=pr_best, best=b, proben=n)
    out["alle_proben"] = wb.log
    json.dump(out, open(os.path.join(a.aus, f"feinlage_{a.foto}.json"), "w"), indent=1)
    print("FERTIG", a.foto, "basis", kopf, {v: (r["start_lr"], r["kosten_lr"]) for v, r in out["varianten"].items()})


if __name__ == "__main__": main()
