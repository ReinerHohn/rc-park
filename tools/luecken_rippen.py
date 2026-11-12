#!/usr/bin/env python3
"""luecken_rippen.py - Rippen, die im Foto da sind (Rippenmaske-Skelett, siehe kanten_ketten --farbe band), aber von keinem Modellpfad gedeckt sind, als neue Pfade vorschlagen.
Aufruf: luecken_rippen.py OBJ.json --kam K-6171 --fenster x0 y0 x1 y1 --pfad bauteile/10/unterbau/rippen_pfade --achse_n nx ny [--roi x0 y0 x1 y1]... [--abstand_px 30] [--min_px 70] [--aus DIR] [--schreiben]
Ablauf: Maske (schwarz neutral + Gold, Putz faellt weg) -> Skelett -> Pixel > abstand_px von jedem projizierten Modellpfad -> Komponenten >= min_px -> laengster Weg -> auf die Flaeche gesetzt, die aus den vorhandenen Pfaden (Ebene) gefittet wird (Tiefe ist egal, Lage im Foto zaehlt) -> Pfade (u,n,z). Ohne --schreiben nur Bild (aus/luecken_neu.jpg) + JSON.
Grenzen: Maske ist auf schwarz+Gold gegen hellen Putz abgestimmt (andere Ornamente: Maske anpassen); Fussbuendel mit 4-6 uebereinanderliegenden Rippen bleiben Naeherung."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2
from skimage.morphology import skeletonize, remove_small_objects
from scipy.spatial import cKDTree
from scipy.ndimage import label, convolve
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.interpolate import splprep, splev
_d = os.path.dirname(os.path.abspath(__file__)); sp = importlib.util.spec_from_file_location("e", os.path.join(_d, "epilinie.py")); E = importlib.util.module_from_spec(sp); sp.loader.exec_module(E)
a = sys.argv[1:]
if len(a) < 6: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
kam = opt("--kam", None); fw = [int(v) for v in a[a.index("--fenster") + 1:a.index("--fenster") + 5]]; x0, y0, x1, y1 = fw
rois = [[int(v) for v in a[i + 1:i + 5]] for i, t in enumerate(a) if t == "--roi"]
nx, ny = [float(v) for v in a[a.index("--achse_n") + 1:a.index("--achse_n") + 3]]; nn = np.array([nx, ny]); nn /= np.linalg.norm(nn); uu = np.array([nn[1], -nn[0]])
W = lambda q: np.array([*(q[0] * uu + q[1] * nn), q[2]]); UVZ = lambda P: np.array([P[0] @ uu[0] + P[1] * 0, 0, 0])
pt = opt("--pfad", "").split("/"); r = obj
for k in pt: r = r[int(k)] if isinstance(r, list) else r[k]
K = E.kam(od, kam); im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kam[2:] + "_*"))[0])[y0:y1, x0:x1]
def px(q, welt=False):
    P = [E.projekt(K, np.array(p) if welt else W(p)) for p in q]; return np.array([x for x in P if x]) - [x0, y0]
vor, pts3 = [], []
for nm, sp_ in (("pfade", True), ("pfade_ohne_spiegel", False)):
    for p in r.get(nm, []):
        q = np.array(p["pfad"] if isinstance(p, dict) else p, float); L = [q]
        if (nm == "pfade") or (isinstance(p, dict) and p.get("spiegeln")): B = q.copy(); B[:, 0] = 2 * r["spiegel_u"] - B[:, 0]; L.append(B)
        for A in L: vor.append(px(A)); pts3 += [W(v) for v in A]
dense = [a_ * (1 - t) + b_ * t for P in vor for a_, b_ in zip(P[:-1], P[1:]) for t in np.linspace(0, 1, 12)]; T = cKDTree(np.array(dense))
pts3 = np.array(pts3); c3 = pts3.mean(0); U_, S_, Vt = np.linalg.svd(pts3 - c3); nrm = Vt[2]; nrm = nrm if nrm @ (E.kam(od, kam)["c"] - c3) > 0 else -nrm   # Flaeche = Ausgleichsebene der vorhandenen Pfade
f = im.astype(int); b, g, rr = f[..., 0], f[..., 1], f[..., 2]; gold = (g > 0.62 * rr) & (rr > 140) & ((rr - b) > 70); dk = (f.max(2) < 80) & ((rr - b) < 30)
gl = cv2.dilate(gold.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))); m = ((dk | gold).astype(np.uint8) * gl); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
m = remove_small_objects(m.astype(bool), 800).astype(np.uint8); m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8)); sk = skeletonize(m > 0)
ys, xs = np.nonzero(sk); d = T.query(np.c_[xs, ys])[0]; unc = np.zeros_like(sk); sel = d > float(opt("--abstand_px", 30)); unc[ys[sel], xs[sel]] = True
if rois: keep = np.zeros_like(unc); [keep.__setitem__((slice(ry0 - y0, ry1 - y0), slice(rx0 - x0, rx1 - x0)), True) for rx0, ry0, rx1, ry1 in rois]; unc &= keep
unc = cv2.dilate(unc.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & sk; lab, nl = label(unc, structure=np.ones((3, 3))); out = []; vis = im.copy()
vis[m > 0] = (0.7 * vis[m > 0] + 0.3 * np.array([255, 0, 255])).astype(np.uint8)
for l in range(1, nl + 1):
    Y, X = np.nonzero(lab == l)
    if len(X) < int(opt("--min_px", 70)): continue
    idx = -np.ones(lab.shape, int); idx[Y, X] = np.arange(len(X)); I, J = [], []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0: continue
            yy, xx = Y + dy, X + dx; ok = (yy >= 0) & (yy < lab.shape[0]) & (xx >= 0) & (xx < lab.shape[1]); ok[ok] = idx[yy[ok], xx[ok]] >= 0
            I += list(np.arange(len(X))[ok]); J += list(idx[(Y + dy)[ok], (X + dx)[ok]])
    G = coo_matrix((np.ones(len(I)), (I, J)), shape=(len(X), len(X))); d0 = dijkstra(G, indices=0, unweighted=True); s = int(np.argmax(np.where(np.isfinite(d0), d0, -1)))
    dd, pr = dijkstra(G, indices=s, unweighted=True, return_predecessors=True); e = int(np.argmax(np.where(np.isfinite(dd), dd, -1))); path = [e]
    while path[-1] != s: path.append(int(pr[path[-1]]))
    P0 = np.c_[X[path], Y[path]].astype(float); teile = [P0]; ang_max = float(opt("--knick_grad", 60)); k = 20
    ii = 0
    while ii < len(teile):                                                              # an Knicken > --knick_grad teilen (Verbindungspunkt zweier Rippen im Skelett)
        P_ = teile[ii]; best = None
        for j in range(k, len(P_) - k):
            v1, v2 = P_[j] - P_[j - k], P_[j + k] - P_[j]; c_ = float(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)); ang = float(np.degrees(np.arccos(np.clip(c_, -1, 1))))
            if ang > ang_max and (best is None or ang > best[0]): best = (ang, j)
        if best: teile[ii:ii + 1] = [P_[:best[1] + 1], P_[best[1]:]]
        else: ii += 1
    for P in teile:
        if len(P) < int(opt("--min_px", 70)): continue
        try: tck, _ = splprep(P.T, s=len(P) * 4.0); Q = np.array(splev(np.linspace(0, 1, 24), tck)).T
        except Exception: continue
        W3 = []
        for q in Q:
            c, dv = E.strahl(K, q + [x0, y0]); den = dv @ nrm
            if abs(den) < 1e-3: W3 = None; break
            W3.append(c + dv * (((c3 - c) @ nrm) / den))
        if W3 is None: continue
        W3 = np.array(W3); uvz = np.c_[W3[:, :2] @ uu, W3[:, :2] @ nn, W3[:, 2]]; ln = float(np.linalg.norm(np.diff(W3, axis=0), axis=1).sum())
        out.append(dict(pfad=uvz.round(3).tolist(), laenge_m=round(ln, 2), px=len(P))); cv2.polylines(vis, [Q.astype(np.int32)], False, (0, 0, 255), 5); cv2.putText(vis, str(len(out) - 1), tuple(Q[len(Q) // 2].astype(int) + [8, 0]), 0, 1.4, (0, 255, 255), 4)
aus = opt("--aus", "."); os.makedirs(aus, exist_ok=True); cv2.imwrite(os.path.join(aus, "luecken_neu.jpg"), vis); json.dump(out, open(os.path.join(aus, "luecken_neu.json"), "w"))
print(len(out), "neue Pfade:", [(i, o["laenge_m"], o["px"]) for i, o in enumerate(out)])
