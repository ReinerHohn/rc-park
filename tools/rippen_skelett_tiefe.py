#!/usr/bin/env python3
"""rippen_skelett_tiefe.py - Rippenbahnen in 3D: Gold-Skelett im besten Nahfoto + Tiefe per Gold-Konsens in den anderen Nahkameras (13.11.2026).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/rippen_skelett_tiefe.py modelle/<objekt>/objekt.json --ref K-6130 --kams K-n11_06,K-e04,K-6124,K-i08
        --box u0 u1 n0 n1 z0 z1 [--aus DIR] [--min_kams 2] [--schritt 3]
Ablauf: Gold = G-B (rote Wand ~0), lokal normiert; Skelett (skeletonize) der Ref-Kamera; je Skelettpunkt Strahl, Tiefe t in 1-cm-Schritten innerhalb --box (u n z, Fassadenrahmen);
Score(t) = Mittel des Goldwerts (Max im 2-px-Umkreis) in den Gegenkameras, in denen der Punkt im Bild liegt (>= min_kams); bester t je Punkt, Median ueber 5 Nachbarn.
Ausgabe: DIR/rippen3d.json (Punkte u n z Score), DIR/ueberlagerung_<kam>.jpg (Punkte in jede Kamera zurueckprojiziert) und DIR/ansicht_uz.png. Reine Geometrie + Bildverarbeitung.
Grenze: Verdeckung (Rippe nur in 1 Kamera sichtbar) -> min_kams; parallele Rippen im Tiefenband -> Konsens in >= 3 Kameras bevorzugen."""
import sys, os, json, glob, numpy as np, cv2
from skimage.morphology import skeletonize
a = sys.argv[1:]
if len(a) < 5: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
od = os.path.dirname(os.path.abspath(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); obj = json.load(open(a[0]))
ref = opt("--ref", None); kams = opt("--kams", "").split(","); aus = opt("--aus", "."); os.makedirs(aus, exist_ok=True); mink = int(opt("--min_kams", 2)); step = int(opt("--schritt", 3))
i = a.index("--box"); u0, u1, n0, n1, z0, z1 = (float(v) for v in a[i + 1:i + 7]); ax = np.array([0.3338, 0.9426])
def cam(kid):
    k = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float))
    return dict(R=R, t=np.array(k["t"], float), sh=np.asarray(k.get("rahmen_verschiebung", [0, 0, 0]), float), f=k["f_px"], cx=k["cx"], cy=k["cy"], k1=float(k.get("k1") or 0))
def foto(kid): return cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0])
def goldkarte(im, scale):
    g = np.clip(im[..., 1].astype(np.float32) - im[..., 0].astype(np.float32), 0, None); g = cv2.GaussianBlur(g, (0, 0), max(1.0, 0.008 * scale))
    lm = cv2.dilate(g, np.ones((max(5, int(0.25 * scale)) | 1,) * 2)); return np.clip(g / (lm + 3.0), 0, 1)
def proj(K, P):
    x = (P + K["sh"]) @ K["R"].T + K["t"]; xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; r2 = xn * xn + yn * yn
    return K["f"] * xn * (1 + K["k1"] * r2) + K["cx"], K["f"] * yn * (1 + K["k1"] * r2) + K["cy"], x[:, 2]
def strahl(K, px, py):
    x, y = (px - K["cx"]) / K["f"], (py - K["cy"]) / K["f"]; xu, yu = x, y
    for _ in range(10): r2 = xu * xu + yu * yu; xu, yu = x / (1 + K["k1"] * r2), y / (1 + K["k1"] * r2)
    d = np.stack([xu, yu, np.ones_like(xu)], 1) @ K["R"]; d /= np.linalg.norm(d, axis=1, keepdims=True); c = -K["R"].T @ K["t"] - K["sh"]; return c, d
Kr = cam(ref); Ir = foto(ref); allk = [cam(k) for k in kams]; Is = [foto(k) for k in kams]
# Bildbereich der Box in der Ref-Kamera
ec = np.array([[u * ax[1] + n * ax[0], -u * ax[0] + n * ax[1], z] for u in (u0, u1) for n in (n0, n1) for z in (z0, z1)]); px, py, _ = proj(Kr, ec)
bx0, bx1, by0, by1 = int(max(px.min() - 20, 0)), int(min(px.max() + 20, Ir.shape[1])), int(max(py.min() - 20, 0)), int(min(py.max() + 20, Ir.shape[0]))
scale_r = float(Kr["f"] / np.median(proj(Kr, ec)[2])); G = goldkarte(Ir, scale_r)[by0:by1, bx0:bx1]; m = G > 0.55; ck = int(float(opt("--close_m", 0.0)) * scale_r) | 1 if float(opt("--close_m", 0.0)) > 0 else 5; m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ck, ck))); sk = skeletonize(m > 0)   # --close_m: Goldlinien einer Rippe (2-3 parallel) zum Band schliessen; sk = skeletonize(m > 0)
ys, xs = np.nonzero(sk); sel = np.arange(0, len(xs), step); xs, ys = xs[sel] + bx0, ys[sel] + by0; print("Skelettpunkte", len(xs), "Ref-Massstab %.0f px/m" % scale_r)
c, d = strahl(Kr, xs.astype(float), ys.astype(float)); ts = np.arange(1.5, 45, 0.01); best = np.zeros(len(xs)); bt = np.zeros(len(xs)); nk = np.zeros(len(xs), int)
Gs = [goldkarte(im, float(K["f"] / 5.0)) for im, K in zip(Is, allk)]
for j in range(len(xs)):
    P = c + d[j][None, :] * ts[:, None]; u = P[:, 0] * ax[1] - P[:, 1] * ax[0]; n = P[:, 0] * ax[0] + P[:, 1] * ax[1]; ok = (u > u0) & (u < u1) & (n > n0) & (n < n1) & (P[:, 2] > z0) & (P[:, 2] < z1)
    if not ok.any(): continue
    P = P[ok]; tt = ts[ok]; S = np.zeros(len(P)); N = np.zeros(len(P))
    for K, g in zip(allk, Gs):
        qx, qy, qz = proj(K, P); inb = (qz > 0) & (qx >= 2) & (qx < g.shape[1] - 3) & (qy >= 2) & (qy < g.shape[0] - 3)
        v = np.zeros(len(P)); xi, yi = qx[inb].astype(int), qy[inb].astype(int); v[inb] = np.maximum.reduce([g[yi + dy, xi + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]); S += v; N += inb
    sc = np.where(N >= mink, S / np.maximum(N, 1), 0); k = int(np.argmax(sc)); best[j], bt[j], nk[j] = sc[k], tt[k], N[k]
P3 = c + d * bt[:, None]; thr = float(opt("--schwelle", 0)) or max(0.25, float(np.percentile(best[best > 0], 60))); good = best > thr; print("Score-Perzentile 10/50/90/99:", [round(float(np.percentile(best[best > 0], q)), 2) for q in (10, 50, 90, 99)], "Schwelle", round(thr, 2), "gute Punkte:", int(good.sum()), "von", len(xs))
res = [dict(u=round(float(p[0] * ax[1] - p[1] * ax[0]), 3), n=round(float(p[0] * ax[0] + p[1] * ax[1]), 3), z=round(float(p[2]), 3), score=round(float(s), 2), kams=int(k_), px=int(x_), py=int(y_)) for p, s, k_, x_, y_ in zip(P3[good], best[good], nk[good], xs[good], ys[good])]
np.savez(os.path.join(aus, "alle_punkte.npz"), px=xs, py=ys, u=P3[:, 0] * ax[1] - P3[:, 1] * ax[0], n=P3[:, 0] * ax[0] + P3[:, 1] * ax[1], z=P3[:, 2], score=best, nk=nk, thr=thr)   # ALLE Skelettpunkte (auch schwache) fuer Kettenbildung im Bild
json.dump(dict(ref=ref, kams=kams, box=[u0, u1, n0, n1, z0, z1], punkte=res), open(os.path.join(aus, "rippen3d.json"), "w"))
for kid, K, im in [(ref, Kr, Ir)] + list(zip(kams, allk, Is)):
    qx, qy, qz = proj(K, P3[good]); o = im.copy()
    for x_, y_ in zip(qx, qy):
        if 0 <= x_ < o.shape[1] and 0 <= y_ < o.shape[0]: cv2.circle(o, (int(x_), int(y_)), 3, (255, 0, 255), -1)
    qa, qb, _ = proj(K, ec); x0, y0, x1, y1 = int(max(qa.min() - 30, 0)), int(max(qb.min() - 30, 0)), int(min(qa.max() + 30, o.shape[1])), int(min(qb.max() + 30, o.shape[0])); o = o[y0:y1, x0:x1]; h = 900
    cv2.imwrite(os.path.join(aus, "ueberlagerung_%s.jpg" % kid), cv2.resize(o, (int(o.shape[1] * h / o.shape[0]), h)), [cv2.IMWRITE_JPEG_QUALITY, 85])
U = np.array([[r["u"], r["z"], r["score"]] for r in res]); img = np.zeros((int((z1 - z0) * 200) + 10, int((u1 - u0) * 200) + 10, 3), np.uint8)
for u_, z_, s_ in U: cv2.circle(img, (int((u_ - u0) * 200) + 5, int((z1 - z_) * 200) + 5), 2, (int(255 * s_),) * 3, -1)
cv2.imwrite(os.path.join(aus, "ansicht_uz.png"), img)
