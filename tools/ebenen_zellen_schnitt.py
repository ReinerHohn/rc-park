#!/usr/bin/env python3
"""ebenen_zellen_schnitt.py - Familie 'Ebenenanordnung + Graph-Cut' (eigene Nachbildung des PolyFit/Kinetic-Gedankens, KEIN CGAL-Code, daher lizenzfrei):
 1 RANSAC-Ebenen aus der Wolke (Modellrahmen, m)   2 Voxelraum (Raster --voxel) wird durch alle Ebenen in Zellen zerlegt (Vorzeichenvektor)
 3 je Zelle Daten aus dem Carving (leer/Material, aus carving_cache.npz + material.npz): Kosten 'innen' = leere Voxel, Kosten 'aussen' = Materialvoxel
 4 Min-Cut (scipy maximum_flow): Summe Datenkosten + --lambda * Grenzflaeche zwischen Zellen (je Voxelflaeche)   5 Innen/Aussen je Zelle -> Netz (Marching Cubes, leicht geglaettet)
Aufruf: venv-seg/bin/python -I tools/ebenen_zellen_schnitt.py --wolke X.npy --carving DIR --box x0 x1 y0 y1 z0 z1 --aus out.stl [--lambda 2] [--ebenen 40] [--min 3000]
Ausgabe STL mm 1:87. Prueffrage: Diff (modell_wettbewerb) besser als OpenMVS? Annahme/Parameter siehe Register BR."""
import argparse, numpy as np, json, os, trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import maximum_flow
ap = argparse.ArgumentParser(); ap.add_argument("--wolke", required=True); ap.add_argument("--carving", required=True); ap.add_argument("--box", nargs=6, type=float, required=True)
ap.add_argument("--aus", required=True); ap.add_argument("--lambda", dest="lam", type=float, default=2.0); ap.add_argument("--ebenen", type=int, default=40); ap.add_argument("--min", type=int, default=3000)
ap.add_argument("--massstab", type=float, default=87.0); a = ap.parse_args()
import open3d as o3d
X = np.load(a.wolke)[:, :3].astype(float); pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(X)).voxel_down_sample(0.05); planes = []
for i in range(a.ebenen):
    if len(pc.points) < a.min: break
    pl, idx = pc.segment_plane(0.06, 3, 2000)
    if len(idx) < a.min: break
    n = np.array(pl[:3]); s = np.linalg.norm(n); planes.append(np.r_[n / s, pl[3] / s]); pc = pc.select_by_index(idx, invert=True)
P = np.array(planes); print("Ebenen:", len(P))
c = np.load(os.path.join(a.carving, "carving_cache.npz")); mm = np.load(os.path.join(a.carving, "material.npz")); lo = c["lo"]; vox = float(c["vox"])
x0, x1, y0, y1, z0, z1 = a.box; i0 = np.floor((np.array([x0, y0, z0]) - lo) / vox).astype(int); i1 = np.ceil((np.array([x1, y1, z1]) - lo) / vox).astype(int)
sl = tuple(slice(max(0, i0[k]), min(c["leer"].shape[k], i1[k])) for k in range(3)); leer = c["leer"][sl]; mat = mm["material"][sl]; sh = leer.shape; off = np.array([s.start for s in sl])
print("Raster", sh)
gx, gy, gz = np.meshgrid(*[(np.arange(sh[k]) + off[k] + 0.5) * vox + lo[k] for k in range(3)], indexing="ij")
code = np.zeros(sh, np.uint64)
for k, p in enumerate(P):
    code |= ((gx * p[0] + gy * p[1] + gz * p[2] + p[3] > 0).astype(np.uint64) << np.uint64(k))
del gx, gy, gz
u, inv = np.unique(code.ravel(), return_inverse=True); inv = inv.reshape(sh); n = len(u); print("Zellen:", n)
cl = np.bincount(inv.ravel(), weights=leer.ravel(), minlength=n); cm = np.bincount(inv.ravel(), weights=mat.ravel(), minlength=n)
# Grenzflaechen zwischen Zellen
pairs = []
for ax in range(3):
    s1 = [slice(None)] * 3; s2 = [slice(None)] * 3; s1[ax] = slice(0, -1); s2[ax] = slice(1, None)
    A = inv[tuple(s1)].ravel(); B = inv[tuple(s2)].ravel(); k = A != B; pairs.append(np.stack([A[k], B[k]], 1))
pairs = np.concatenate(pairs); lo_p = np.minimum(pairs[:, 0], pairs[:, 1]); hi_p = np.maximum(pairs[:, 0], pairs[:, 1])
key = lo_p.astype(np.int64) * n + hi_p; uk, cnt = np.unique(key, return_counts=True); ea = (uk // n).astype(int); eb = (uk % n).astype(int)
# Min-Cut: S = innen-Quelle, T = aussen-Senke; Kosten 'innen' (Zelle bleibt in S-Seite) = leere Voxel, 'aussen' = Materialvoxel
SC = 1000.0 / max(1.0, max(cl.max(), cm.max())); S, T = n, n + 1
rows = [np.full(n, S), np.arange(n), ea, eb]; cols = [np.arange(n), np.full(n, T), eb, ea]
w_in = np.round(cm * SC).astype(np.int64) + 1; w_out = np.round(cl * SC).astype(np.int64) + 1; w_e = np.maximum(1, np.round(a.lam * cnt * SC).astype(np.int64))
caps = [w_in, w_out, w_e, w_e]   # Kante S->v kostet, wenn v AUSSEN (Material wird aussen gelegt); v->T kostet, wenn v INNEN (leere Voxel innen)
G = coo_matrix((np.concatenate(caps), (np.concatenate(rows), np.concatenate(cols))), shape=(n + 2, n + 2)).tocsr().astype(np.int32)
fl = maximum_flow(G, S, T)
res = G - fl.flow; res.data = np.where(res.data > 0, 1, 0); res.eliminate_zeros()
from scipy.sparse.csgraph import breadth_first_order
reach = np.zeros(n + 2, bool); reach[breadth_first_order(res, S, directed=True, return_predecessors=False)] = True
innen = reach[:n]; print("Zellen innen:", int(innen.sum()), "von", n)
vol = innen[inv].astype(np.float32); from scipy.ndimage import gaussian_filter; vol = gaussian_filter(vol, 0.7)
from skimage.measure import marching_cubes
v, f, _, _ = marching_cubes(np.pad(vol, 1), 0.5); v = (v - 1 + off + 0.5) * vox + lo
m = trimesh.Trimesh(v, f); parts = m.split(only_watertight=False); m = max(parts, key=lambda q: len(q.faces)); print("Dreiecke", len(m.faces), "wasserdicht", m.is_watertight)
m.apply_scale(1000.0 / a.massstab); m.export(a.aus)
