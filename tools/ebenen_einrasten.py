#!/usr/bin/env python3
"""ebenen_einrasten.py - Familie 'Ebenen': RANSAC-Ebenen aus der Wolke (Modellrahmen, m), dann Netzknoten nahe einer Ebene (Abstand < --tol, Normale < --winkel) auf die Ebene projizieren.
Netz-STL in mm (1:87). Aufruf: venv-o3d/bin/python tools/ebenen_einrasten.py --wolke X.npy --stl in.stl --aus out.stl [--tol 0.15] [--winkel 25] [--n 40] [--min 4000]"""
import argparse, numpy as np, trimesh, open3d as o3d
ap = argparse.ArgumentParser(); ap.add_argument("--wolke", required=True); ap.add_argument("--stl", required=True); ap.add_argument("--aus", required=True)
ap.add_argument("--tol", type=float, default=0.15); ap.add_argument("--winkel", type=float, default=25); ap.add_argument("--n", type=int, default=40); ap.add_argument("--min", type=int, default=4000)
a = ap.parse_args(); X = np.load(a.wolke)[:, :3].astype(float); m = trimesh.load(a.stl); k = 87 / 1000.0
V = np.asarray(m.vertices) * k; N = np.asarray(m.vertex_normals)
pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(X)); pc = pc.voxel_down_sample(0.05); ebenen = []
for i in range(a.n):
    if len(pc.points) < a.min: break
    pl, idx = pc.segment_plane(0.06, 3, 2000)
    if len(idx) < a.min: break
    ebenen.append(np.array(pl)); pc = pc.select_by_index(idx, invert=True)
print("Ebenen:", len(ebenen)); cw = np.cos(np.radians(a.winkel)); bewegt = np.zeros(len(V), bool)
best = np.full(len(V), a.tol)
for pl in ebenen:
    n = pl[:3] / np.linalg.norm(pl[:3]); d = (V @ n + pl[3] / np.linalg.norm(pl[:3])); ok = (np.abs(d) < best) & (np.abs(N @ n) > cw)
    V[ok] -= d[ok, None] * n; best[ok] = np.abs(d[ok]); bewegt[ok] = True
print("Knoten bewegt: %.1f %%" % (100 * bewegt.mean()))
r = trimesh.Trimesh(V / k, m.faces, process=False); r.export(a.aus)
