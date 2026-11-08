#!/usr/bin/env python3
"""oeffnungen_vergleich.py - Segmentbogen-Oeffnungen einer Fassade aus VERSCHIEDENEN Quellen (Wolken, Modell-STL) mit mehreren Methoden messen und gegeneinander legen.
Widerspruch zwischen Quellen wird gezeigt, nicht gemittelt (Regel 5). venv-seg/bin/python -I tools/oeffnungen_vergleich.py --fassaden F.json --id f02 --quelle name:wolke:pfad.npy --quelle name:stl:pfad.stl [--massstab 87]"""
import argparse, json, numpy as np, sys, os, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import quader_relief as Q, bauteil_erkennen as B
ap = argparse.ArgumentParser(); ap.add_argument("--fassaden", required=True); ap.add_argument("--id", required=True); ap.add_argument("--quelle", action="append", required=True)
ap.add_argument("--massstab", type=float, default=87); ap.add_argument("--g", type=float, default=0.05); ap.add_argument("--tol", type=float, default=0.10); a = ap.parse_args()
F = [f for f in json.load(open(a.fassaden))["fassaden"] if f["id"] == a.id][0]; n, d, o = (np.array(F[k][:2]) for k in ("n", "d", "o")); U0, U1, Z0, Z1 = -13.0, 13.0, -0.5, 8.0
res = {}
for spec in a.quelle:
    name, art, pfad = spec.split(":", 2)
    if art == "stl": m = trimesh.load(pfad); m.apply_scale(a.massstab / 1000.0); X = m.sample(1500000)
    else: X = np.load(pfad)
    q = X[:, :2] - o; P = np.c_[q @ d, q @ n, X[:, 2]]; P = P[(P[:, 0] > U0) & (P[:, 0] < U1) & (P[:, 1] > -6) & (P[:, 1] < 3) & (P[:, 2] > Z0) & (P[:, 2] < Z1)]
    D = Q.raster(P, Z0, Z1, U0, U1, a.g, perz=50, mind=3); M = Q.luecken_fuellen(Q.modell_raster(Q.baum(D, tol=a.tol, minz=1), D.shape), a.tol, max_breite=int(1.0 / a.g))
    for var in ("median", "fit"):
        res[(name, var)] = B.oeffnungen(M, U0, Z0, a.g, variante=var)
        res[(name, var + "+loch")] = B.oeffnungen(M, U0, Z0, a.g, variante=var, leer_ist_offen=True)
for (name, var), O in res.items():
    print(f"== {name} / {var}: {len([x for x in O if x["zeilen"] >= 8])} Oeffnungen (mind. 8 Zeilen)")
    for o_ in [x for x in O if x["zeilen"] >= 8]: print("   u %.2f..%.2f (B %.2f)  zk %.2f  zs %.2f  tiefe %.2f  Zeilen %d" % (o_["u0"], o_["u1"], o_["u1"] - o_["u0"], o_["zk"], o_["zs"], o_["tiefe"], o_["zeilen"]) + ("  sigma_zk %.1f cm %s" % (o_["sigma_zk_cm"], "bestimmt" if o_["zk_bestimmt"] else "UNBESTIMMT") if "sigma_zk_cm" in o_ else ""))
