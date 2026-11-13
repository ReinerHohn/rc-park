#!/usr/bin/env python3
"""rippen_aeste_bild.py - Rippenaeste im BILD des Referenzfotos bilden (Skelett zerlegt an Kreuzungen), Tiefe je Ast aus den guten Punkten robust interpoliert (13.11.2026).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/rippen_aeste_bild.py DIR/alle_punkte.npz --aus DIR [--min_px 25] [--gut_anteil 0.3] [--junction_r 4]
Ablauf: Punkte (Skelett jedes 3. Pixel) -> Pixelgraph (Abstand <= 5 px) -> Knoten mit Grad >= 3 samt Umkreis entfernen -> Zusammenhaenge = Aeste; je Ast Reihenfolge ueber laengsten Weg;
Tiefe (u,n,z) nur aus Punkten mit Score >= Schwelle (Median 9 Punkte), Luecken linear interpoliert, dann Gauss; Ast verworfen, wenn < gut_anteil gute Punkte. Ausgabe DIR/aeste.json + aeste_uz.png.
Reine Geometrie."""
import sys, os, json, numpy as np, cv2
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.ndimage import gaussian_filter1d, median_filter
a = sys.argv[1:]
if not a: sys.exit(__doc__)
opt = lambda n, d: float(a[a.index(n) + 1]) if n in a else d
aus = a[a.index("--aus") + 1] if "--aus" in a else os.path.dirname(a[0]); minpx, ganteil, jr = opt("--min_px", 25), opt("--gut_anteil", 0.3), opt("--junction_r", 4)
D = np.load(a[0]); px, py, U, N, Z, S, thr = D["px"].astype(float), D["py"].astype(float), D["u"], D["n"], D["z"], D["score"], float(D["thr"])
XY = np.column_stack([px, py]); T = cKDTree(XY); pr = np.array(sorted(T.query_pairs(5.0))); deg = np.bincount(pr.ravel(), minlength=len(XY))
# Kreuzungen: Knoten mit >= 3 Nachbarn in 8 px mit stark unterschiedlicher Richtung -> grob: Grad >= 5 bei Radius 5
junc = np.where(deg >= 5)[0]; rem = np.zeros(len(XY), bool)
if len(junc): Tj = cKDTree(XY[junc]); rem = Tj.query(XY)[0] < jr
alive = np.where(~rem)[0]; Ta = cKDTree(XY[alive]); pa = np.array(sorted(Ta.query_pairs(5.0))); d = np.linalg.norm(XY[alive][pa[:, 0]] - XY[alive][pa[:, 1]], axis=1)
G = coo_matrix((np.r_[d, d], (np.r_[pa[:, 0], pa[:, 1]], np.r_[pa[:, 1], pa[:, 0]])), shape=(len(alive),) * 2).tocsr(); nc, lab = connected_components(G, directed=False); aeste = []
for c in range(nc):
    m = np.where(lab == c)[0]
    if len(m) < minpx / 3: continue
    d0 = dijkstra(G, indices=m[0], directed=False); a_ = m[int(np.argmax(d0[m]))]; d1, pre = dijkstra(G, indices=a_, directed=False, return_predecessors=True); b_ = m[int(np.argmax(d1[m]))]
    if d1[b_] < minpx: continue
    p = [b_]
    while p[-1] != a_ and pre[p[-1]] >= 0: p.append(pre[p[-1]])
    idx = alive[np.array(p[::-1])]; good = S[idx] >= thr
    if good.mean() < ganteil or good.sum() < 5: continue
    s = np.arange(len(idx), dtype=float); P = []
    for V in (U, N, Z):
        v = V[idx].copy(); gi = np.where(good)[0]; vm = v.copy(); vm[gi] = median_filter(v[gi], size=min(9, max(1, len(gi) // 2 * 2 - 1)), mode="nearest"); P.append(gaussian_filter1d(np.interp(s, gi, vm[gi]), 3, mode="nearest"))
    P = np.column_stack(P); L = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
    if L < 0.2: continue
    k = np.linspace(0, len(P) - 1, max(4, int(L / 0.05))).astype(int); aeste.append(dict(laenge_m=round(L, 3), gut=round(float(good.mean()), 2), score=round(float(S[idx].mean()), 2), pfad=np.round(P[k], 3).tolist()))
aeste.sort(key=lambda r: -r["laenge_m"]); json.dump(aeste, open(os.path.join(aus, "aeste.json"), "w")); print(len(aeste), "Aeste, Gesamtlaenge %.1f m; Laengen:" % sum(r["laenge_m"] for r in aeste), [r["laenge_m"] for r in aeste][:25])
img = np.zeros((int(2.0 * 250) + 10, int(3.5 * 250) + 10, 3), np.uint8); rng = np.random.default_rng(5)
for r in aeste:
    col = tuple(int(v) for v in rng.integers(90, 255, 3)); P = np.array(r["pfad"])
    for p, q in zip(P[:-1], P[1:]): cv2.line(img, (int((p[0] + 10.2) * 250) + 5, int((8.3 - p[2]) * 250) + 5), (int((q[0] + 10.2) * 250) + 5, int((8.3 - q[2]) * 250) + 5), col, 2)
cv2.imwrite(os.path.join(aus, "aeste_uz.png"), img)
