#!/usr/bin/env python3
"""test_kamera_ausgleich.py - BS3d synthetischer Beweis: Kameras absichtlich verschieben (Kamerazentrum 3/5/10 cm, Rotation 0,3/0,5/1 Grad),
pruefen ob der Ausgleich (kamera_ausgleich.foto_ausgleich, ohne Holdout) die Lage zurueckholt. Mass = RMS-Pixelabstand der projizierten Netzpunkte
zwischen wiedergewonnener und ORIGINAL-Kamera (Original = Messziel; das Optimum der Originalkamera kann selbst leicht daneben liegen).
Aufruf: test_kamera_ausgleich.py modelle/<obj>/objekt.json --stl NETZ --masken ORDNER --aus ARBEITSORDNER --fotos 000,004,209 [--kerne 6] [--nullproben]
"""
import os, sys, json, argparse, math
import numpy as np
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
import kamera_ausgleich as KA


def punkte(stl, obj, K, n=3000, seed=1):
    """Netzpunkte im Kamerarahmen wie foto_diff._netz_raster: Massstab stl_massstab/1000, dann Verschiebung rahmen_verschiebung der Kamera."""
    import trimesh
    m = trimesh.load(stl, force="mesh"); v = np.asarray(m.vertices) * (obj.get("stl_massstab", 87) / 1000.0); rng = np.random.default_rng(seed)
    return v[rng.choice(len(v), min(n, len(v)), replace=False)] + np.asarray(K["kamera"].get("rahmen_verschiebung", [0, 0, 0]), float)


def proj(K, X):
    import cv2
    k = K["kamera"]; R = cv2.Rodrigues(np.array(k["rvec"]))[0]; c = X @ R.T + np.array(k["t"]); z = c[:, 2]
    return np.stack([k["f_px"] * c[:, 0] / z + k["cx"], k["f_px"] * c[:, 1] / z + k["cy"]], 1), z


def px_abstand(Ka, Kb, X):
    pa, za = proj(Ka, X); pb, zb = proj(Kb, X); w, h = Ka["kamera"]["bild"]
    ok = (za > 0) & (zb > 0) & (pa[:, 0] > 0) & (pa[:, 0] < w) & (pa[:, 1] > 0) & (pa[:, 1] < h)
    return float(np.sqrt(np.mean(np.sum((pa[ok] - pb[ok]) ** 2, 1)))) if ok.sum() > 50 else None


def storung(K0, art, groesse, seed):
    """art 'zentrum' (m) oder 'rot' (Grad): zufaellige Richtung. Zentrum verschieben: t' = t - R d (d Weltvektor) = in Kamerakoordinaten tx..tz = -R d."""
    rng = np.random.default_rng(seed); v = rng.normal(size=3); v /= np.linalg.norm(v)
    p = {n: 0.0 for n in KA.POSE}
    if art == "rot": p.update(rx=v[0] * groesse, ry=v[1] * groesse, rz=v[2] * groesse)
    else: p.update(tx=v[0] * groesse, ty=v[1] * groesse, tz=v[2] * groesse)
    return KA.kamera_neu(K0, p), p


def semaphor_test(a):
    """Simuliertes foto_diff (kein GPU): 12 Laeufe gemischter Groesse, 6 Threads; Spitze der gleichzeitig angemeldeten MiB muss <= Limit sein;
    ein Foto liefert immer Fehler -> Ausfallanteil 100 % und Gueltigkeit false."""
    import threading, time, tempfile, shutil as sh
    from concurrent.futures import ThreadPoolExecutor as TP
    d = temp_ordner(); obj = json.load(open(a.objekt)); b = KA.Bank(a.objekt, a.stl, d, 6); b.vram_limit = 7000.0; b._smi_frei = lambda: 1e9
    gross = b.gewicht("073"); klein = b.gewicht("000"); live = [0.0]; spitze = [0.0]; lk = threading.Lock(); orig = b._fd
    def fake(dd, foto, extra, o):
        g = b.gewicht(foto)
        with lk: live[0] += g; spitze[0] = max(spitze[0], live[0])
        time.sleep(0.3)
        with lk: live[0] -= g
        class R: returncode = 1; stderr = "simulierter OOM"; stdout = ""
        if foto != "000":
            os.makedirs(o, exist_ok=True); json.dump(dict(kosten_lr=-0.1, modellkanten_px=10 ** 6), open(os.path.join(o, "foto_diff_x.json"), "w"))
        return R()
    b._fd = fake; K0 = b.K("000"); time.sleep(0)
    import types; KA.time.sleep = lambda x: None
    def lauf(i):
        foto = "073" if i % 4 == 0 else "000" if i % 4 == 1 else "114"; K = json.loads(json.dumps(b.K(foto))); K["kamera"]["f_px"] += i
        return b.eval(foto, K, os.path.join(d, "m.png"), "t")
    with TP(6) as ex: list(ex.map(lauf, range(24)))
    ok_sem = spitze[0] <= b.vram_limit + 1e-6; au = {f: v for f, v in b.ausfall.items()}
    anteil = {f: v[0] / max(v[1], 1) for f, v in au.items()}
    print(json.dumps(dict(gewicht_073=gross, gewicht_klein=klein, spitze_mib=spitze[0], limit=b.vram_limit, semaphor_ok=ok_sem, ausfall=au, anteil=anteil, gueltig={f: x <= 0.02 for f, x in anteil.items()}, ohne_semaphor_spitze_waere=6 * gross)))
    sh.rmtree(d, ignore_errors=True); sys.exit(0 if ok_sem and anteil.get("000", 0) == 1.0 and anteil.get("073", 1) == 0.0 else 1)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--masken", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--fotos", default="000,004,209"); ap.add_argument("--kerne", type=int, default=6); ap.add_argument("--proben", type=int, default=70)
    ap.add_argument("--groessen-zentrum", default="0.03,0.05,0.10"); ap.add_argument("--groessen-rot", default="0.3,0.5,1.0"); ap.add_argument("--nullproben", action="store_true"); ap.add_argument("--semaphor-test", action="store_true", help="ohne GPU: Semaphor (nie > Limit) und Ausfallzaehler/Gueltigkeit mit simuliertem foto_diff belegen"); ap.add_argument("--nachrechnen", help="synthetisch.json: Pixelabstaende mit richtigem Netzrahmen neu rechnen (keine Foto-Diff-Laeufe)")
    a = ap.parse_args()
    if a.semaphor_test: return semaphor_test(a)
    os.makedirs(a.aus, exist_ok=True); bank = KA.Bank(a.objekt, a.stl, a.aus, a.kerne); ex = ThreadPoolExecutor(a.kerne); obj = json.load(open(a.objekt))
    fotos = a.fotos.split(","); mk = {f: (os.path.join(a.masken, f"C_{f}.png") if os.path.exists(os.path.join(a.masken, f"C_{f}.png")) else os.path.join(a.masken, f"{f}.png")) for f in fotos}
    if a.nachrechnen:
        res = json.load(open(a.nachrechnen)); K = {}; Xs = {}
        for e in res:
            f = e["foto"]
            if f not in K: K[f] = bank.K(f); Xs[f] = punkte(a.stl, obj, K[f])
            Kp = KA.kamera_neu(K[f], e["gestoert"]); Kr = KA.kamera_neu(Kp, e["pose"]); e["px_gestoert"] = px_abstand(K[f], Kp, Xs[f]); e["px_nach_ausgleich"] = px_abstand(K[f], Kr, Xs[f])
        json.dump(res, open(a.nachrechnen[:-5] + "_px.json", "w"), indent=1)
        for e in res: print(e["foto"], e["art"], e["groesse"], "px gest", round(e["px_gestoert"], 2), "nach", round(e["px_nach_ausgleich"], 2), "lr orig/gest/nach", e["lr_original"], e["lr_gestoert"], e["lr_nach"], "proben", e["proben"])
        return
    K = {f: bank.K(f) for f in fotos}; X = {f: punkte(a.stl, obj, K[f]) for f in fotos}; res = []
    if a.nullproben:   # Rauschen: lr-Streuung bei winzigen Verschiebungen (0,02 Grad / 5 mm), 8 Richtungen je Foto
        for f in fotos:
            r0 = KA.lr_von(bank.eval(f, K[f], mk[f], "null0"))
            xs = list(ex.map(lambda s: KA.lr_von(bank.eval(f, storung(K[f], "rot", 0.02, s)[0], mk[f], "null")), range(8)))
            xt = list(ex.map(lambda s: KA.lr_von(bank.eval(f, storung(K[f], "zentrum", 0.005, 100 + s)[0], mk[f], "null")), range(8)))
            res.append(dict(foto=f, null=r0, rot002=xs, zentrum5mm=xt, std_rot=float(np.std(xs)), std_zentrum=float(np.std(xt))))
        json.dump(res, open(os.path.join(a.aus, "nullproben.json"), "w"), indent=1); print(json.dumps(res)); return
    fälle = [(f, "zentrum", float(g)) for f in fotos for g in a.groessen_zentrum.split(",")] + [(f, "rot", float(g)) for f in fotos for g in a.groessen_rot.split(",")]
    def fall(c):
        f, art, g = c; Kp, pst = storung(K[f], art, g, 7 + int(g * 1000))
        r = KA.foto_ausgleich(bank, f, Kp, mk[f], os.path.join(a.aus, "h"), a.proben, 0, holdout=False)
        Kr = KA.kamera_neu(Kp, r["p"]); lr_o = KA.lr_von(bank.eval(f, K[f], mk[f], "orig"))
        d0 = px_abstand(K[f], Kp, X[f]); d1 = px_abstand(K[f], Kr, X[f])
        e = dict(foto=f, art=art, groesse=g, px_gestoert=d0, px_nach_ausgleich=d1, lr_original=lr_o, lr_gestoert=r["lr_start"], lr_nach=r["lr_nachher"], proben=r["proben"], pose=r["p"], gestoert=pst)
        print("FALL", json.dumps(e), flush=True); return e
    res = list(ex.map(fall, fälle))
    json.dump(res, open(os.path.join(a.aus, "synthetisch.json"), "w"), indent=1)
    print("TABELLE foto art groesse px_gestoert px_nach lr_orig lr_gest lr_nach")
    for e in res: print(e["foto"], e["art"], e["groesse"], e["px_gestoert"] and round(e["px_gestoert"], 2), e["px_nach_ausgleich"] and round(e["px_nach_ausgleich"], 2), e["lr_original"], e["lr_gestoert"], e["lr_nach"])


if __name__ == "__main__": main()
