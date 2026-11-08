#!/usr/bin/env python3
"""modell_foto_overlay.py --stl x.stl [--stl_mm_massstab 87] --fotos kameras_netz.json --bilder dir --foto name.jpg [--wolke w.npy] --out jpg
Ganzes Modell (rot) + optional Wolke (gelb) in ein kalibriertes Foto projiziert - zum ANSEHEN (Regel 3/9d, Nutzer 8.11.: 'Bildfeedback ist richtig geil')."""
import os, json, argparse, numpy as np, cv2, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("--stl", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--foto", required=True)
ap.add_argument("--wolke"); ap.add_argument("--out", required=True); ap.add_argument("--winkel", type=float, default=0.6); a = ap.parse_args()
k = json.load(open(a.fotos))[a.foto]; R = np.array(k["Rn"]); t = np.array(k["tn"]); im = cv2.imread(os.path.join(a.bilder, a.foto) if False else a.bilder + "/" + a.foto, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
def pr(P): X = P @ R.T + t; z = np.maximum(X[:, 2], 1e-3); return k["f"] * X[:, :2] / z[:, None] + [k["cx"], k["cy"]], X[:, 2]
if a.wolke:
    P = np.load(a.wolke)[:, :3][::3]; uv, z = pr(P)
    for (u, v), zz in zip(uv, z):
        if zz > 1 and 0 <= u < im.shape[1] and 0 <= v < im.shape[0]: cv2.circle(im, (int(u), int(v)), 3, (0, 255, 255), -1)
m = trimesh.load(a.stl, process=False); m.apply_scale(87 / 1000); mm = m.copy(); mm.merge_vertices(); V = np.asarray(mm.vertices); ed = mm.face_adjacency_edges[mm.face_adjacency_angles > a.winkel]
p0, z0 = pr(V[ed[:, 0]]); p1, z1 = pr(V[ed[:, 1]])
for q0, q1, a0, a1 in zip(p0, p1, z0, z1):
    if a0 > 1 and a1 > 1: cv2.line(im, (int(q0[0]), int(q0[1])), (int(q1[0]), int(q1[1])), (0, 0, 255), 3)
cv2.imwrite(a.out, cv2.resize(im, None, fx=0.4, fy=0.4)); print("geschrieben", a.out)
