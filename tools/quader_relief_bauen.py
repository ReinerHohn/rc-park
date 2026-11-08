#!/usr/bin/env python3
"""quader_relief_bauen.py - Quaderbaum-Relief einer Fassade aus der Wolke -> STL (Modellrahmen, mm im Massstab) + Kennzahlen. Nichts objektbezogen.
  venv-seg/bin/python -I tools/quader_relief_bauen.py --wolke W.npy --fassaden F.json --id f02 --aus relief.stl [--massstab 87] [--g 0.05] [--tol 0.10] [--dicke 0.3] [--zmax 21] [--urange -13,13]
Je Quader: Flaeche s_vorn (Median der Zelle), Platte 'dicke' m nach hinten (Relief, kein Volumen bis zur Rueckwand). Verschmolzen: waagerecht und dann senkrecht gleich tiefe Nachbarn."""
import argparse, json, numpy as np, trimesh, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import quader_relief as Q
ap = argparse.ArgumentParser(); ap.add_argument("--wolke", required=True); ap.add_argument("--fassaden", required=True); ap.add_argument("--id", required=True); ap.add_argument("--aus", required=True)
ap.add_argument("--massstab", type=float, default=87); ap.add_argument("--g", type=float, default=0.05); ap.add_argument("--tol", type=float, default=0.10); ap.add_argument("--dicke", type=float, default=0.3)
ap.add_argument("--zmax", type=float, default=21.0); ap.add_argument("--urange", default="-13,13"); ap.add_argument("--srange", default="-6,3"); a = ap.parse_args()
F = [f for f in json.load(open(a.fassaden))["fassaden"] if f["id"] == a.id][0]; n, d, o = (np.array(F[k][:2]) for k in ("n", "d", "o"))
X = np.load(a.wolke); q = X[:, :2] - o; P = np.c_[q @ d, q @ n, X[:, 2]]; u0, u1 = (float(x) for x in a.urange.split(",")); s0, s1 = (float(x) for x in a.srange.split(","))
P = P[(P[:, 0] > u0) & (P[:, 0] < u1) & (P[:, 1] > s0) & (P[:, 1] < s1) & (P[:, 2] > -0.5) & (P[:, 2] < a.zmax)]
D = Q.raster(P, -0.5, a.zmax, u0, u1, a.g, perz=50, mind=3); B = Q.baum(D, tol=a.tol, minz=1)
M = Q.luecken_fuellen(Q.modell_raster(B, D.shape), a.tol, max_breite=int(1.0 / a.g)); B2 = [(z0, z1, u0_, u1_, float(np.nanmedian(M[z0:z1, u0_:u1_]))) for z0, z1, u0_, u1_, s in B if np.isfinite(np.nanmedian(M[z0:z1, u0_:u1_]))] if False else B
# Verschmelzen waagerecht, dann senkrecht
Z = [b for b in B if np.isfinite(b[4])]; Z.sort(key=lambda b: (b[0], b[1], b[2])); H = []
for b in Z:
    if H and H[-1][0] == b[0] and H[-1][1] == b[1] and H[-1][3] == b[2] and abs(H[-1][4] - b[4]) <= a.tol / 2: H[-1] = (b[0], b[1], H[-1][2], b[3], H[-1][4])
    else: H.append(b)
H.sort(key=lambda b: (b[2], b[3], b[0])); V = []
for b in H:
    if V and V[-1][2] == b[2] and V[-1][3] == b[3] and V[-1][1] == b[0] and abs(V[-1][4] - b[4]) <= a.tol / 2: V[-1] = (V[-1][0], b[1], b[2], b[3], V[-1][4])
    else: V.append(b)
print(f"Zellen {D.shape}, Blaetter {len(B)}, nach Verschmelzen {len(V)} Quader; Wolkenpunkte {len(P)}")
meshes = []; sc = a.massstab and 1000.0 / a.massstab
for z0, z1, uu0, uu1, s in V:
    U0_, U1_ = -0.5 * 0 + u0 + uu0 * a.g, u0 + uu1 * a.g; Z0_, Z1_ = -0.5 + z0 * a.g, -0.5 + z1 * a.g
    box = trimesh.creation.box(extents=(U1_ - U0_, a.dicke, Z1_ - Z0_)); box.apply_translation(((U0_ + U1_) / 2, s - a.dicke / 2, (Z0_ + Z1_) / 2))   # lokal (u, s, z)
    meshes.append(box)
m = trimesh.util.concatenate(meshes); v = m.vertices.copy(); uu_, ss_, zz_ = v[:, 0], v[:, 1], v[:, 2]
xy = o[None] + uu_[:, None] * d[None] + ss_[:, None] * n[None]; m.vertices = np.c_[xy, zz_]
m.apply_scale(sc); m.export(a.aus); print(a.aus, "Dreiecke", len(m.faces), "Groesse MB", round(os.path.getsize(a.aus) / 1e6, 1))
