#!/usr/bin/env python3
"""rippenbreite_pruefen.py - Misst die SICHTBARE Breite jeder Modell-Rippe im Render quer zur Rippe und meldet zu dicke ('Platten').

Aufruf: rippenbreite_pruefen.py OBJ.json --kam K-6171 [--soll 0.07] [--faktor 1.6] [--aus DIR]
Je Pfad aus erker_polygon.unterbau.rippen_pfade (pfade, Spiegel, pfade_ohne_spiegel) wird die Mittellinie in die Kamera projiziert; quer dazu (je 12. Punkt) laeuft ein Profil
ueber das Render-Tiefenbild: Breite = zusammenhaengender Bereich um die Mitte, dessen Tiefe <= Mittentiefe + 0,06 m liegt (Rippenfront + Flanke bis 6 cm), in Metern
(Pixel x Tiefe / f). Ausgabe je Pfad Median und Max; > soll*faktor = ZU DICK. Nutzer 12.11.: 'zu dick/zu fett' muss das Werkzeug selbst erkennen."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2, trimesh
_d = os.path.dirname(os.path.abspath(__file__))
def lade(n):
    s = importlib.util.spec_from_file_location(n, os.path.join(_d, n + ".py")); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
EPI, RK = lade("epilinie"), lade("render_kern")
a = sys.argv[1:]
if len(a) < 3: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
kam = opt("--kam", "K-6171"); soll = float(opt("--soll", 0.07)); fak = float(opt("--faktor", 1.6)); aus = opt("--aus", ".")
K = EPI.kam(od, kam); kk = json.load(open(os.path.join(od, "messprotokoll", kam + ".json")))["kamera"]
im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kam[2:] + "_*"))[0]); H, W = im.shape[:2]
m = trimesh.load(os.path.join(root, obj["stl"])); m.apply_scale(obj.get("stl_massstab", 87) / 1000.0); m.apply_translation(np.asarray(kk.get("rahmen_verschiebung", [0, 0, 0]), float))
R, _ = cv2.Rodrigues(np.array(kk["rvec"], float)); t = np.array(kk["t"], float)
depth = np.asarray(RK.dreiecke_rastern(m, R, t, kk["f_px"], kk["cx"], kk["cy"], W, H)[0], np.float32)
def f(x):
    if isinstance(x, dict):
        if "rippen_pfade" in x: yield x["rippen_pfade"]
        for v in x.values(): yield from f(v)
    elif isinstance(x, list):
        for v in x: yield from f(v)
r = next(f(obj)); uc = r.get("spiegel_u"); n_ = np.array([0.3338, 0.9426]); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
P = [("pfad%d" % i, np.array(p)) for i, p in enumerate(r["pfade"])]
if uc is not None: P += [("spiegel_" + nm_, np.c_[2 * uc - p[:, 0], p[:, 1], p[:, 2]]) for nm_, p in list(P)]
P += [("ohne%d" % i, np.array(e["pfad"] if isinstance(e, dict) else e)) for i, e in enumerate(r.get("pfade_ohne_spiegel", []))]
out = []
for name, p in P:
    Wd = np.array([np.r_[u_ * a_ + n_ * b_, z_] for a_, b_, z_ in p]); tt = np.linspace(0, len(Wd) - 1, 120); Wd = np.array([np.interp(tt, range(len(Wd)), Wd[:, i]) for i in range(3)]).T
    q = np.array([EPI.projekt(K, w) for w in Wd]); ws = []
    for j in range(6, len(q) - 6, 6):
        tg = q[j + 3] - q[j - 3]; tg /= np.linalg.norm(tg) + 1e-9; nm = np.array([-tg[1], tg[0]]); c = q[j]
        def d_(s): 
            x, y = int(c[0] + nm[0] * s), int(c[1] + nm[1] * s); return depth[y, x] if 0 <= x < W and 0 <= y < H else np.nan
        d0 = d_(0)
        if not np.isfinite(d0) or d0 <= 0: continue
        lo = hi = 0
        while lo > -150 and np.isfinite(d_(lo - 1)) and 0 < d_(lo - 1) <= d0 + 0.06: lo -= 1
        while hi < 150 and np.isfinite(d_(hi + 1)) and 0 < d_(hi + 1) <= d0 + 0.06: hi += 1
        ws.append((hi - lo) * d0 / K["f"])
    if ws: out.append((name, float(np.median(ws)), float(np.max(ws)), len(ws)))
print("Rippe       Median(m)  Max(m)   Soll %.2f, Grenze %.2f" % (soll, soll * fak))
for n, md, mx, k in out: print("%-10s  %.3f     %.3f   %s" % (n, md, mx, "ZU DICK" if md > soll * fak else ""))
json.dump([dict(rippe=n, median_m=md, max_m=mx) for n, md, mx, k in out], open(os.path.join(aus, "rippenbreite.json"), "w"))
