#!/usr/bin/env python3
"""rippen_ketten3d.py - aus den 3D-Punkten von rippen_skelett_tiefe.py durchgehende Rippenketten bilden (13.11.2026).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/rippen_ketten3d.py DIR/rippen3d.json --aus DIR [--min_laenge 0.3] [--radius 0.03] [--luecke 0.25]
Ablauf: Nachbarschaftsgraph (3D-Radius), je Zusammenhang laengster geodaetischer Weg (wie kanten_features: iterativ, Umgebung 3,5 cm entfernt), Glaetten (Gauss) und Resampling 5 cm,
danach Ketten mit Luecke <= --luecke und Richtungs-cos >= 0,85 verbinden. Ausgabe DIR/ketten.json (je Kette Punkte u n z, Laenge m, mittlerer Score) + DIR/ketten_uz.png.
Reine Geometrie."""
import sys, os, json, numpy as np, cv2
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.ndimage import gaussian_filter1d
a = sys.argv[1:]
if not a: sys.exit(__doc__)
opt = lambda n, d: float(a[a.index(n) + 1]) if n in a else d
aus = a[a.index("--aus") + 1] if "--aus" in a else os.path.dirname(a[0]); minl, rad, gap = opt("--min_laenge", 0.3), opt("--radius", 0.03), opt("--luecke", 0.25)
D = json.load(open(a[0])); pts = D["punkte"]; X = np.array([[p["u"], p["n"], p["z"]] for p in pts]); sc = np.array([p["score"] for p in pts])
alive = np.ones(len(X), bool); chains = []
def weg(idx):
    T = cKDTree(X[idx]); pr = np.array(sorted(T.query_pairs(rad)))
    if len(pr) == 0: return None
    d = np.linalg.norm(X[idx][pr[:, 0]] - X[idx][pr[:, 1]], axis=1); G = coo_matrix((np.r_[d, d], (np.r_[pr[:, 0], pr[:, 1]], np.r_[pr[:, 1], pr[:, 0]])), shape=(len(idx),) * 2).tocsr()
    nc, lab = connected_components(G, directed=False); best = None
    for c in range(nc):
        m = np.where(lab == c)[0]
        if len(m) < 8: continue
        d0 = dijkstra(G, indices=m[0], directed=False); d0[~np.isfinite(d0)] = -1; a_ = int(np.argmax(np.where(np.isin(np.arange(len(idx)), m), d0, -1)))
        d1, pre = dijkstra(G, indices=a_, directed=False, return_predecessors=True); d1[~np.isfinite(d1)] = -1; b_ = int(np.argmax(np.where(np.isin(np.arange(len(idx)), m), d1, -1)))
        L = d1[b_]
        if best is None or L > best[0]:
            p = [b_]
            while p[-1] != a_ and pre[p[-1]] >= 0: p.append(pre[p[-1]])
            best = (L, [int(idx[q]) for q in p[::-1]])
    return best
for _ in range(400):
    idx = np.where(alive)[0]
    if len(idx) < 8: break
    b = weg(idx)
    if b is None or b[0] < minl * 0.6: break
    L, path = b
    if L >= minl: chains.append(path)
    T = cKDTree(X[alive]); ai = np.where(alive)[0]; near = set(); Tp = cKDTree(X[path])
    dd, _ = Tp.query(X[ai]); alive[ai[dd < 0.035]] = False
def glatt(P, h=0.05):
    P = np.array(P); s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    if s[-1] < h: return P
    k = np.arange(0, s[-1], h); Q = np.column_stack([np.interp(k, s, P[:, i]) for i in range(3)]); Q = np.column_stack([gaussian_filter1d(Q[:, i], 2, mode="nearest") for i in range(3)]); return np.vstack([Q, P[-1:]])
ch = [glatt(X[p]) for p in chains]; sco = [float(sc[p].mean()) for p in chains]
# Ketten verbinden
changed = True
while changed:
    changed = False
    for i in range(len(ch)):
        for j in range(len(ch)):
            if i == j or ch[i] is None or ch[j] is None: continue
            for ei in (0, -1):
                for ej in (0, -1):
                    pi, pj = ch[i][ei], ch[j][ej]
                    if np.linalg.norm(pi - pj) > gap: continue
                    di = ch[i][ei] - ch[i][ei + (4 if ei == 0 else -4)]; dj = ch[j][ej + (4 if ej == 0 else -4)] - ch[j][ej]
                    di /= np.linalg.norm(di) + 1e-9; dj /= np.linalg.norm(dj) + 1e-9
                    if float(di @ dj) < 0.85: continue
                    A = ch[i] if ei == -1 else ch[i][::-1]; B = ch[j] if ej == 0 else ch[j][::-1]; ch[i] = np.vstack([A, B]); ch[j] = None; sco[i] = (sco[i] + sco[j]) / 2; changed = True; break
                if changed: break
            if changed: break
        if changed: break
res = []
for c, s in zip(ch, sco):
    if c is None: continue
    L = float(np.linalg.norm(np.diff(c, axis=0), axis=1).sum())
    if L >= minl: res.append(dict(laenge_m=round(L, 3), score=round(s, 2), pfad=np.round(c, 3).tolist()))
res.sort(key=lambda r: -r["laenge_m"]); json.dump(res, open(os.path.join(aus, "ketten.json"), "w")); print(len(res), "Ketten, Gesamtlaenge %.1f m; Laengen:" % sum(r["laenge_m"] for r in res), [r["laenge_m"] for r in res][:20])
U = np.array(D["box"]); img = np.zeros((int((U[5] - U[4]) * 250) + 10, int((U[1] - U[0]) * 250) + 10, 3), np.uint8); rng = np.random.default_rng(3)
for r in res:
    col = tuple(int(v) for v in rng.integers(90, 255, 3)); P = np.array(r["pfad"])
    for p, q in zip(P[:-1], P[1:]): cv2.line(img, (int((p[0] - U[0]) * 250) + 5, int((U[5] - p[2]) * 250) + 5), (int((q[0] - U[0]) * 250) + 5, int((U[5] - q[2]) * 250) + 5), col, 2)
cv2.imwrite(os.path.join(aus, "ketten_uz.png"), img)
