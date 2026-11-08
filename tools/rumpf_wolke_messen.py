#!/usr/bin/env python3
"""rumpf_wolke_messen.py - Abstand Wolkenpunkte -> STL nach Hoehenband (Messung wie 6.11.): Median, Anteil < 0,3 m, Perzentil 90.
  rumpf_wolke_messen.py <stl> [--masstab 87] [--kasten x0 x1 y0 y1] [--wolke GLOB]   (STL mm im Massstab 1:M, Meter = mm*M/1000)"""
import sys, glob, argparse, numpy as np, trimesh
import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__))); from gpu_knn import min_abstand, naechster, ball_anzahl   # GPU (Nutzerregel)
ap = argparse.ArgumentParser(); ap.add_argument("stl", nargs="+"); ap.add_argument("--masstab", type=float, default=87)
ap.add_argument("--kasten", type=float, nargs=4, default=[-7, 14, 3, 17]); ap.add_argument("--wolke", default="/media/oem/scan/rc-park_null/kaufhaus_handy3/dicht_neu/stapel/sicher_*_modell.npy")
ap.add_argument("--baender", default="0,3,5,11,20"); a = ap.parse_args()
P = np.vstack([np.load(f)[:, :3] for f in sorted(glob.glob(a.wolke))]).astype(float); x0, x1, y0, y1 = a.kasten
P = P[(P[:, 0] >= x0) & (P[:, 0] <= x1) & (P[:, 1] >= y0) & (P[:, 1] <= y1)]; B = [float(b) for b in a.baender.split(",")]
print(f"Wolke im Kasten {len(P)} Pkt")
for f in a.stl:
    m = trimesh.load(f); m.vertices = m.vertices * a.masstab / 1000; S, _ = trimesh.sample.sample_surface_even(m, 2500000, seed=1)
    d = min_abstand(P, S); print(f"{f}  (wasserdicht {m.is_watertight}, Volumen {m.volume:.0f} m3)")
    for lo, hi in zip(B[:-1], B[1:]):
        k = (P[:, 2] >= lo) & (P[:, 2] < hi)
        if k.sum(): print(f"  z {lo:g}-{hi:g} m: n={k.sum():7d}  Median {np.median(d[k]):.3f} m  P90 {np.percentile(d[k], 90):.3f}  Anteil<0,3 m {100 * (d[k] < 0.3).mean():.1f} %")
    print(f"  alle: Median {np.median(d):.3f} m  Anteil<0,3 m {100 * (d < 0.3).mean():.1f} %")
