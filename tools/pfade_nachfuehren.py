#!/usr/bin/env python3
"""pfade_nachfuehren.py - vorhandene Rippenpfade (rippen_pfade.pfade_ohne_spiegel) im Foto auf die gemessene Rippenmitte nachfuehren.
Aufruf: pfade_nachfuehren.py OBJ.json --kam K-6171 --fenster x0 y0 x1 y1 --pfad bauteile/10/unterbau/rippen_pfade --achse_n nx ny [--max_px 40] [--glatt 5] [--nur i,j,k] [--schreiben] [--aus DIR]
Ablauf: Rippenmaske (schwarz neutral + Gold, Putz faellt weg) -> Skelett; jeder Pfadpunkt wird ins Foto projiziert, zum naechsten Skelettpixel (<= --max_px) verschoben, die Verschiebung entlang des Pfades mit Median/Glaettung beruhigt (Ausreisser = anderes Rippe/Querstueck faellt weg), Strahl durch den neuen Pixel mit der Ebene durch den alten Punkt (senkrecht zur Pfadnormale) geschnitten -> Tiefe bleibt, nur die Lage im Foto wird korrigiert.
Ohne --schreiben nur Bericht + Bild (aus/nachgefuehrt.jpg: weiss = alt, gruen = neu, Skelett magenta). Mit --schreiben ueberschreibt es die Pfade in OBJ.json (vorher Kopie sichern; danach bauen_abnehmen + Render)."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2
from skimage.morphology import skeletonize, remove_small_objects
from scipy.spatial import cKDTree
from scipy.ndimage import median_filter, gaussian_filter1d
_d = os.path.dirname(os.path.abspath(__file__)); sp = importlib.util.spec_from_file_location("e", os.path.join(_d, "epilinie.py")); E = importlib.util.module_from_spec(sp); sp.loader.exec_module(E)
a = sys.argv[1:]
if len(a) < 6: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
kam = opt("--kam", None); x0, y0, x1, y1 = [int(v) for v in a[a.index("--fenster") + 1:a.index("--fenster") + 5]]
nx, ny = [float(v) for v in a[a.index("--achse_n") + 1:a.index("--achse_n") + 3]]; nn = np.array([nx, ny]); nn /= np.linalg.norm(nn); uu = np.array([nn[1], -nn[0]])
W = lambda q: np.array([*(q[0] * uu + q[1] * nn), q[2]]); UVZ = lambda P: [float(P[:2] @ uu), float(P[:2] @ nn), float(P[2])]
r = obj
for k in opt("--pfad", "").split("/"): r = r[int(k)] if isinstance(r, list) else r[k]
K = E.kam(od, kam); big = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kam[2:] + "_*"))[0]); im = big[y0:y1, x0:x1]
f = im.astype(int); b, g, rr = f[..., 0], f[..., 1], f[..., 2]; gold = (g > 0.62 * rr) & (rr > 140) & ((rr - b) > 70); dk = (f.max(2) < 80) & ((rr - b) < 30)
gl = cv2.dilate(gold.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))); m = ((dk | gold).astype(np.uint8) * gl); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
m = remove_small_objects(m.astype(bool), 800).astype(np.uint8); m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)); sk = skeletonize(m > 0); ys, xs = np.nonzero(sk); T = cKDTree(np.c_[xs, ys])
maxpx, gl_ = float(opt("--max_px", 40)), float(opt("--glatt", 5)); nur = [int(v) for v in opt("--nur", "").split(",") if v != ""]; vis = im.copy(); vis[m > 0] = (0.75 * vis[m > 0] + 0.25 * np.array([255, 0, 255])).astype(np.uint8); rep = []
for i, e in enumerate(r.get("pfade_ohne_spiegel", [])):
    if nur and i not in nur: continue
    dct = isinstance(e, dict); Q = np.array(e["pfad"] if dct else e, float); nrm = np.array(e["normale"] if dct and e.get("normale") else r["normale"], float); nrm /= np.linalg.norm(nrm)
    P3 = np.array([W(q) for q in Q]); n3 = np.array([nrm[0] * uu[0] + nrm[1] * nn[0], nrm[0] * uu[1] + nrm[1] * nn[1], nrm[2]]); n3 /= np.linalg.norm(n3)
    pxs = np.array([E.projekt(K, p) if E.projekt(K, p) else (np.nan, np.nan) for p in P3]) - [x0, y0]
    if np.isnan(pxs).any(): rep.append((i, "ausserhalb")); continue
    # Verschiebung nur senkrecht zum Pfad (laengs ist egal)
    tg = np.gradient(pxs, axis=0); tg /= (np.linalg.norm(tg, axis=1, keepdims=True) + 1e-9); nl = np.c_[-tg[:, 1], tg[:, 0]]
    dd, ii = T.query(pxs); disp = np.zeros(len(pxs)); ok = dd <= maxpx
    for j in range(len(pxs)):
        if ok[j]: disp[j] = float((np.c_[xs[ii[j]], ys[ii[j]]][0] - pxs[j]) @ nl[j])
    if ok.sum() < 0.5 * len(ok): rep.append((i, f"zu wenig Skelett ({int(ok.sum())}/{len(ok)})")); continue
    disp[~ok] = np.interp(np.flatnonzero(~ok), np.flatnonzero(ok), disp[ok]); disp = gaussian_filter1d(median_filter(disp, size=5, mode="nearest"), gl_, mode="nearest")
    new = pxs + nl * disp[:, None]; Pn = []
    for p0, q in zip(P3, new):
        c, dv = E.strahl(K, q + [x0, y0]); den = dv @ n3; Pn.append(c + dv * (((p0 - c) @ n3) / den) if abs(den) > 1e-3 else p0)
    Pn = np.array(Pn); rep.append((i, f"mittl. Verschiebung {np.abs(disp).mean():.1f} px, max {np.abs(disp).max():.1f} px, 3D max {np.linalg.norm(Pn - P3, axis=1).max() * 100:.1f} cm"))
    cv2.polylines(vis, [pxs.astype(np.int32)], False, (255, 255, 255), 3); cv2.polylines(vis, [new.astype(np.int32)], False, (0, 255, 0), 3); cv2.putText(vis, str(i), tuple(new[len(new) // 2].astype(int) + [8, 0]), 0, 1.3, (0, 255, 255), 3)
    if "--breite" in a:                                   # Rippenbreite aus der Maske: Breite des Maskenbands senkrecht zur Mittellinie (px) -> m ueber Abstand/Brennweite
        wm = []
        for q, nl_, p3 in zip(new, nl, Pn):
            dq, iq = T.query(q)
            if dq > 12: continue                                  # Mittelpunkt nicht an der Maske: keine Messung
            q = np.array([xs[iq], ys[iq]], float); lim = []
            for sg in (1, -1):
                t_ = 0
                while t_ < 90:
                    x_, y_ = (q + sg * nl_ * (t_ + 1)).astype(int)
                    if not (0 <= x_ < m.shape[1] and 0 <= y_ < m.shape[0]) or not m[y_, x_]: break
                    t_ += 1
                lim.append(t_)
            dist = float(np.linalg.norm(p3 - K["c"])); wm.append((lim[0] + lim[1]) * dist / K["f"])
        wmed = 0.72 * float(np.median([w_ for w_ in wm if w_ > 0.02])) if any(w_ > 0.02 for w_ in wm) else None   # 0,72: Gold-zu-Gold-Frontbreite / Maske inkl. dunkler Flanken (Messung 6171: 0,07 / 0,098)
        if wmed is None: continue
        rep.append((i, f"Maskenbreite Median {wmed * 100:.1f} cm (Min {min(wm) * 100:.1f}, Max {max(wm) * 100:.1f})"))
        if not dct: e = dict(pfad=r["pfade_ohne_spiegel"][i], spiegeln=False); r["pfade_ohne_spiegel"][i] = e; dct = True
        e["b"] = round(float(np.clip(wmed, float(opt("--b_min", 0.03)), float(opt("--b_max", 0.09)))), 3)
    newq = [UVZ(p) for p in Pn]; 
    if dct: e["pfad"] = [[round(v, 3) for v in q] for q in newq]
    else: r["pfade_ohne_spiegel"][i] = [[round(v, 3) for v in q] for q in newq]
aus = opt("--aus", "."); os.makedirs(aus, exist_ok=True); cv2.imwrite(os.path.join(aus, "nachgefuehrt.jpg"), vis)
for t in rep: print(*t)
if "--schreiben" in a: json.dump(obj, open(a[0], "w"), indent=1, ensure_ascii=False); print("geschrieben:", a[0])
