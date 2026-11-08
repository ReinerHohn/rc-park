#!/usr/bin/env python3
"""wolke_ebenen_ransac.py - BS48 Schritt 1 des Eigenbau-Min-Cut: Ebenen aus der (bereinigten) Wolke per iterativem RANSAC (Open3D).
Wolke im Netzrahmen (npy) auf Basis-bbox zuschneiden, Ebenen (Schwelle --th m) bis --min Punkte; Ausgabe json (Normale, d, Punktzahl, Ausdehnung) + Abdeckung.
  venv-o3d/bin/python -I tools/wolke_ebenen_ransac.py wolke.npy aus.json [--th 0.04 --min 3000 --max 80]"""
import sys, json, argparse, numpy as np, open3d as o3d
ap = argparse.ArgumentParser(); ap.add_argument("wolke"); ap.add_argument("aus"); ap.add_argument("--th", type=float, default=0.04); ap.add_argument("--min", type=int, default=3000); ap.add_argument("--max", type=int, default=80)
ap.add_argument("--box", default="-14.6,2.7,0.6,15.7,17.0,19.9")
a = ap.parse_args(); X = np.load(a.wolke).astype(np.float64); b = np.array(a.box.split(","), float); lo, hi = b[:3] - 0.5, b[3:] + 0.5
X = X[np.all((X >= lo) & (X <= hi), 1)]; n0 = len(X); print("Punkte im Gebaeude-Kasten", n0, flush=True)
pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(X)); res = []
for k in range(a.max):
    if len(pc.points) < a.min: break
    pl, idx = pc.segment_plane(a.th, 3, 2000)
    if len(idx) < a.min: break
    P = np.asarray(pc.points)[idx]; n = np.array(pl[:3]); ev = np.linalg.eigh(np.cov((P - P.mean(0)).T))[1]; ext = np.ptp(P @ ev[:, 1:], 0)
    res.append(dict(n=n.tolist(), d=float(pl[3]), punkte=int(len(idx)), schwerpunkt=P.mean(0).tolist(), ausdehnung_m=ext.round(2).tolist(), vertikal=bool(abs(n[2]) < 0.2)))
    print(k, "n=%s punkte=%d ausdehnung=%s" % (np.round(n, 2), len(idx), ext.round(1)), flush=True); pc = pc.select_by_index(idx, invert=True)
dec = sum(r["punkte"] for r in res); print(f"{len(res)} Ebenen, Abdeckung {100*dec/n0:.1f} % der Punkte"); json.dump(res, open(a.aus, "w"), indent=1)
