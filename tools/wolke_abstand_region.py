#!/usr/bin/env python3
"""wolke_abstand_region.py - Abstand Wolkenpunkte -> Netz in einer Quaderregion (K-Rahmen m), fuer Details, die der Foto-Diff nicht sieht (Fenster-Nischen/Sprossen).
  venv-seg/bin/python -I tools/wolke_abstand_region.py objekt.json --dicht sfm/dicht_alle --box x0,y0,z0,x1,y1,z1 --netz A.stl --netz B.stl ... [--tiefe 0.6]
Netz: STL mm -> K-Rahmen m wie foto_diff._netz (mm*massstab/1000 + (0,0,rv_z)). Wolke: fused.ply -> K-Rahmen (Umeyama, wolke_front.rahmen_umeyama). Beleg: Abstaende in cm je Netz (Median, P90, Anteil < 2 cm), nur Wolkenpunkte im Quader."""
import os, sys, json, argparse, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import wolke_front as WF
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--dicht", required=True); ap.add_argument("--box", required=True); ap.add_argument("--netz", action="append", required=True)
ap.add_argument("--normale", default="0.344,0.939"); ap.add_argument("--rv-z", type=float, default=0.431); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--n", type=int, default=150000); a = ap.parse_args()
od = os.path.dirname(os.path.abspath(a.objekt)); s, Rm, t0, CM, rest = WF.rahmen_umeyama(a.dicht, od); X, _ = WF.ply_farbe(os.path.join(a.dicht, "fused.ply")); X = s * (Rm @ X.T).T + t0
x0, y0, z0, x1, y1, z1 = [float(v) for v in a.box.split(",")]; ok = (X[:, 0] >= x0) & (X[:, 0] <= x1) & (X[:, 1] >= y0) & (X[:, 1] <= y1) & (X[:, 2] >= z0) & (X[:, 2] <= z1); Xr = X[ok]
if len(Xr) > a.n: Xr = Xr[np.random.default_rng(0).choice(len(Xr), a.n, replace=False)]
print("Wolkenpunkte im Quader:", len(Xr))
for p in a.netz:
    m = trimesh.load(p, force="mesh"); m.vertices = m.vertices * (a.massstab / 1000.0) + np.array([0, 0, a.rv_z])
    _, d, _ = trimesh.proximity.closest_point(m, Xr); d = d * 100
    print(f"{os.path.basename(p):28s} Median {np.median(d):5.2f} cm  P90 {np.percentile(d, 90):5.2f} cm  <2cm {np.mean(d < 2) * 100:5.1f} %  <5cm {np.mean(d < 5) * 100:5.1f} %")
