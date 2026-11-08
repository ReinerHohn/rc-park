#!/usr/bin/env python3
"""lot_aus_fotos.py --fotos k.json --bilder dir [--n 40] [--aus lot.json]
Lotrichtung im Wolkenrahmen AUS DEN FOTOS (Manhattan-Welt): je Foto Linienstuecke (LSD), nahezu senkrechte Linien -> Fluchtpunkt der Vertikalen (RANSAC + SVD-Verfeinerung),
Richtung in Kamerakoordinaten -> Weltrichtung R^T d. Mittel ueber Fotos = wahre Lotrichtung im Rahmen; Abweichung von (0,0,1) = Kipp-Winkel des Rahmens. Unabhaengig von Boden/Wand der Wolke
(Boden kann geneigt sein, Wand ueberhaengen)."""
import json, argparse, os, numpy as np, cv2
ap = argparse.ArgumentParser(); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--n", type=int, default=40); ap.add_argument("--aus"); a = ap.parse_args()
K = json.load(open(a.fotos)); names = sorted(K); rng = np.random.default_rng(0); pick = [names[i] for i in rng.choice(len(names), min(a.n, len(names)), replace=False)]
lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD); ups = []; rows = []
for nm in pick:
    k = K[nm]; g = cv2.imread(os.path.join(a.bilder, nm), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
    if g is None: continue
    sc = 0.5; g = cv2.resize(g, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA); L = lsd.detect(g)[0]
    if L is None: continue
    L = (L.reshape(-1, 4)) / sc; d = L[:, 2:] - L[:, :2]; ln = np.linalg.norm(d, axis=1); ang = np.degrees(np.arctan2(np.abs(d[:, 0]), np.abs(d[:, 1])))   # Abweichung von Bildvertikale
    s = (ln > 120) & (ang < 25); L = L[s]
    if len(L) < 15: continue
    h0 = np.c_[L[:, :2], np.ones(len(L))]; h1 = np.c_[L[:, 2:], np.ones(len(L))]; ln_h = np.cross(h0, h1); ln_h /= np.linalg.norm(ln_h[:, :2], axis=1, keepdims=True)   # Linien (a,b,c) normiert
    best = (0, None)
    for _ in range(800):
        i, j = rng.choice(len(L), 2, replace=False); vp = np.cross(ln_h[i], ln_h[j])
        if abs(vp[2]) < 1e-9: vp = vp / (np.linalg.norm(vp)); 
        # Konsistenz: Abstand Linienmitte -> Gerade durch Mitte und VP (Winkelfehler)
        mid = 0.5 * (L[:, :2] + L[:, 2:]); vpx = vp[:2] / vp[2] if abs(vp[2]) > 1e-9 else vp[:2] * 1e9
        dv = vpx - mid; dl = L[:, 2:] - L[:, :2]; cosang = np.abs((dv * dl).sum(1)) / (np.linalg.norm(dv, axis=1) * np.linalg.norm(dl, axis=1) + 1e-9); inl = cosang > np.cos(np.radians(1.0))
        if inl.sum() > best[0]: best = (int(inl.sum()), inl)
    if best[1] is None or best[0] < 10: continue
    M = ln_h[best[1]]; _, _, Vt = np.linalg.svd(M); vp = Vt[-1]; Ki = np.array([[1 / k["f"], 0, -k["cx"] / k["f"]], [0, 1 / k["f"], -k["cy"] / k["f"]], [0, 0, 1]]); dcam = Ki @ vp; dcam /= np.linalg.norm(dcam)
    R = np.array(k["Rn"]); dw = R.T @ dcam
    if dw[2] < 0: dw = -dw     # nach oben
    ups.append(dw); err = np.degrees(np.arccos(np.clip(dw @ np.array([0, 0, 1.0]), -1, 1))); rows.append((nm, best[0], len(L), err, dw))
    print("%-34s Inlier %3d/%3d  Lotabweichung %.2f Grad  up_welt %s" % (nm[-34:], best[0], len(L), err, np.round(dw, 4)), flush=True)
U = np.array(ups); med = np.median(U, axis=0); med /= np.linalg.norm(med); mean = U.mean(0); mean /= np.linalg.norm(mean)
ang = np.degrees(np.arccos(np.clip(U @ med, -1, 1))); print("n=%d Fotos; Median up_welt %s (Abweichung von z: %.2f Grad); Streuung um Median: Median %.2f Grad, 90%% %.2f Grad" % (len(U), np.round(med, 4), np.degrees(np.arccos(med[2])), np.median(ang), np.percentile(ang, 90)))
if a.aus: json.dump(dict(up_welt=med.tolist(), n=len(U), abw_von_z_grad=float(np.degrees(np.arccos(med[2]))), streuung_median_grad=float(np.median(ang))), open(a.aus, "w"), indent=1)
