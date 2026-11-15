#!/usr/bin/env python3
"""modell_ansicht.py AUS.jpg --stl a.stl[,b.stl] --von x y z --nach x y z [--f 900] [--groesse 1000 1300] [--wolke punkte.npy] - schattiertes Modell aus einer FREIEN Kamera (Modellrahmen, Meter).

Fuer Rueckfragen des Nutzers aus der 3D-Seite ("warum fehlt hier das Dach?"): dieselbe Stelle aus aehnlichem Blickwinkel rendern, optional die dichte Wolke
als rote Punkte darueber (nur Punkte VOR der Modellflaeche oder ohne Modell dahinter = dort fehlt Modell). Dreiecks-Raster (GPU) wie modell_neben_foto.py.
"""
import sys, os, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_kern as rk
a = sys.argv; g = lambda k, n: [float(v) for v in a[a.index(k) + 1:a.index(k) + 1 + n]]
C = np.array(g("--von", 3)); Zp = np.array(g("--nach", 3)); f = g("--f", 1)[0] if "--f" in a else 900.0; W, H = [int(v) for v in g("--groesse", 2)] if "--groesse" in a else (1000, 1300)
z = Zp - C; z /= np.linalg.norm(z); x = np.cross(z, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(z, x); R = np.stack([x, y, z]); t = -R @ C
ms = [trimesh.load(s) for s in a[a.index("--stl") + 1].split(",")]; mm = trimesh.util.concatenate(ms) if len(ms) > 1 else ms[0]; mm.apply_scale(87.0 / 1000.0)
res = rk.dreiecke_rastern(mm, R, t, f, W / 2, H / 2, W, H); tiefe = np.asarray(res[0]); fid = np.asarray(res[1]); tr = fid >= 0
li = R.T @ np.array([-0.45, -0.75, -1.0]); li /= np.linalg.norm(li); im = np.full((H, W), 235, np.uint8); im[tr] = (60 + 190 * np.clip(mm.face_normals[fid[tr]] @ li, 0, 1)).astype(np.uint8); im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
if "--wolke" in a:
    P = np.load(a[a.index("--wolke") + 1]).astype(np.float64); p = P @ R.T + t; ok = p[:, 2] > 1; u = (f * p[ok, 0] / p[ok, 2] + W / 2).astype(int); v = (f * p[ok, 1] / p[ok, 2] + H / 2).astype(int); d = p[ok, 2]; inb = (u >= 0) & (u < W) & (v >= 0) & (v < H); u, v, d = u[inb], v[inb], d[inb]
    mt = np.where(tr, tiefe, np.inf)[v, u]; frei = d < mt - 0.4; im[v[frei], u[frei]] = (0, 0, 255); print(f"Wolke: {int(frei.sum())} von {len(d)} Punkten liegen > 0,4 m vor dem Modell oder ohne Modell dahinter")
cv2.imwrite(a[1], im); print("->", a[1])
