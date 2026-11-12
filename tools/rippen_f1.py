#!/usr/bin/env python3
"""rippen_f1.py - FEINES Foto-Mass fuer Rippen/Leisten (Wolke und foto_diff sind dafuer blind): Modellkanten (Tiefenkanten des exakten Renders) gegen Fotokanten (Stabilitaetskarte) in vielen Nahfotos, nur im Erkerbereich, Toleranz in cm (Welt) statt Kappe 0,35 m.
Aufruf: rippen_f1.py STL --box "x0,y0,z0,x1,y1,z1" [--fotos a.jpg,b.jpg | --n 44 --ziel 17.5,7.7,7.3 --radius 16] [--tol_cm 3] [--stabil 0.4] [--stl_massstab 87] [--aus JSON]
Je Foto: ROI = Bildkasten der Boxecken; Modellkante = Tiefensprung (> 0,04) im sichtbaren Teil; Fotokante = Stabilitaetskarte >= --stabil; Toleranz in Pixeln = tol_cm / (Tiefe/f). Praezision = Modellkantenpixel mit Fotokante in Toleranz, Recall = Fotokantenpixel mit Modellkante in Toleranz, F1. Ausgabe: Mittel ueber Fotos (Median der F1), je Foto.
Hinweis: Fotokanten-Karten sind dicht (Wandkanten, Schatten) -> Recall misst nur, ob Modellkanten dort liegen, wo Fotokanten sind; vorher/nachher gleiche Fotos, gleiche Parameter vergleichen."""
import sys, os, json
import numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import render_kern as RK
a = sys.argv[1:]
if len(a) < 3: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; KAM = json.load(open(D + "/sfm/kam_lot2.json")); bx = np.array([float(v) for v in opt("--box", "").split(",")]); tol = float(opt("--tol_cm", 3)) / 100.0; st = float(opt("--stabil", 0.4))
m = trimesh.load(a[0]); m.apply_scale(float(opt("--stl_massstab", 87)) / 1000.0)
if "--fotos" in a: fl = opt("--fotos", "").split(",")
else:
    Z = np.array([float(v) for v in opt("--ziel", "17.5,7.7,7.3").split(",")]); R_ = float(opt("--radius", 16)); L = []
    for f, c in KAM.items():
        if not os.path.exists(f"{D}/stabil/{f[:-4]}.png") or "6171" in f: continue
        C = np.array(c["C"]); d = np.linalg.norm(C - Z); ax = np.array(c["Rn"])[2]
        if d < R_ and ax @ ((Z - C) / d) > 0.85: L.append((d, f))
    L.sort(); fl = ["ip_IMG_6171.jpg"] + [f for _, f in L][:int(opt("--n", 44))]
SCH = None
if "--pfade_json" in a: SCH = [np.array(q) for q in json.load(open(opt("--pfade_json", "")))]   # Liste von xyz-Pfaden: Messung nur im Schlauch (--schlauch_cm 6) um diese Pfade
SC = float(opt("--schlauch_cm", 6)) / 100.0
corn = np.array([[x, y, z] for x in (bx[0], bx[3]) for y in (bx[1], bx[4]) for z in (bx[2], bx[5])]); res = []
for f in fl:
    c = KAM[f]; R = np.array(c["Rn"]); t = np.array(c["tn"]); W = int(c["W"]); H = int(c["H"]); q = corn @ R.T + t
    if (q[:, 2] < 0.5).any(): continue
    x = q[:, 0] / q[:, 2]; y = q[:, 1] / q[:, 2]; s = 1 + c["params"][3] * (x * x + y * y); u = c["f"] * x * s + c["cx"]; v = c["f"] * y * s + c["cy"]
    x0, x1, y0, y1 = int(max(u.min(), 0)), int(min(u.max(), W)), int(max(v.min(), 0)), int(min(v.max(), H))
    if x1 - x0 < 80 or y1 - y0 < 80: continue
    r = RK.dreiecke_rastern(m, R, t, c["f"], c["cx"], c["cy"], W, H); depth = np.asarray(r[0], np.float32); fid = np.asarray(r[1]); vis = fid >= 0; dp = depth.copy(); dp[~vis] = 0
    dd = np.abs(cv2.Sobel(dp, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(dp, cv2.CV_32F, 0, 1)); me = ((dd > 0.04) & vis)[y0:y1, x0:x1]
    sm = cv2.imread(f"{D}/stabil/{f[:-4]}.png", 0); sm = cv2.resize(sm, (W, H), interpolation=cv2.INTER_LINEAR); fe = (sm >= 255 * st)[y0:y1, x0:x1]
    dz = float(np.median(depth[y0:y1, x0:x1][vis[y0:y1, x0:x1]])) if vis[y0:y1, x0:x1].any() else 0
    if dz <= 0 or me.sum() < 50: continue
    rp = max(2, int(round(tol / (dz / c["f"])))); k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rp + 1, 2 * rp + 1))
    fe_d = cv2.dilate(fe.astype(np.uint8), k) > 0; me_d = cv2.dilate(me.astype(np.uint8), k) > 0
    if SCH is not None:
        mk = np.zeros((H, W), np.uint8); rs = max(3, int(round(SC / (dz / c["f"]))))
        for Pp in SCH:
            q2 = Pp @ R.T + t
            if (q2[:, 2] < 0.5).any(): continue
            x2 = q2[:, 0] / q2[:, 2]; y2 = q2[:, 1] / q2[:, 2]; s2 = 1 + c["params"][3] * (x2 * x2 + y2 * y2); cv2.polylines(mk, [np.c_[c["f"] * x2 * s2 + c["cx"], c["f"] * y2 * s2 + c["cy"]].astype(np.int32)], False, 255, 2 * rs)
        mk = mk[y0:y1, x0:x1] > 0; me = me & mk; fe = fe & mk
        if me.sum() < 50: continue
    P = float((me & fe_d).sum() / me.sum()); Rc = float((fe & me_d).sum() / max(fe.sum(), 1)); F = 2 * P * Rc / (P + Rc + 1e-9)
    res.append(dict(foto=f, praez=round(P, 3), recall=round(Rc, 3), f1=round(F, 3), tol_px=rp, tiefe_m=round(dz, 2)))
fs = np.array([r_["f1"] for r_ in res]); print(f"{len(res)} Fotos, Rippen-F1 Mittel {fs.mean():.3f} Median {np.median(fs):.3f} | Praezision Mittel {np.mean([r_['praez'] for r_ in res]):.3f} Recall Mittel {np.mean([r_['recall'] for r_ in res]):.3f}")
if "--aus" in a: json.dump(res, open(opt("--aus", "rippen_f1.json"), "w"), indent=1)
