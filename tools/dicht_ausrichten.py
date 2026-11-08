#!/usr/bin/env python3
"""dicht_ausrichten.py <fused.ply> <T.npz> <aus_prefix> [--max N]
Dichte COLMAP-Wolke mit der Aehnlichkeitstransformation (R,s,t aus iphone_ausrichten.py) in den Netzrahmen legen: p' = s*R@p + t.
Schreibt <aus_prefix>_pts.npy (float32 Nx3) und <aus_prefix>_rgb.npy (uint8 Nx3)."""
import sys, numpy as np, trimesh
ply, tz, pre = sys.argv[1:4]; mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 0
T = np.load(tz); R, s, t = T["R"], float(T["s"]), T["t"]
pc = trimesh.load(ply); P = np.asarray(pc.vertices, float); C = np.asarray(pc.colors)[:, :3].astype(np.uint8)
if mx and len(P) > mx:
    i = np.random.default_rng(0).choice(len(P), mx, replace=False); P, C = P[i], C[i]
Q = (s * (R @ P.T)).T + t
np.save(pre + "_pts.npy", Q.astype(np.float32)); np.save(pre + "_rgb.npy", C)
print(len(Q), "Punkte; Box min", Q.min(0).round(1), "max", Q.max(0).round(1))
