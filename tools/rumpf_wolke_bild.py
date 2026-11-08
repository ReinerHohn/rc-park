#!/usr/bin/env python3
"""rumpf_wolke_bild.py <stl> <aus.jpg> - STL-Kanten (rot) ueber Wolke (grau): Vorder-(x-z), Seiten-(y-z), Draufsicht (x-y). venv-seg."""
import sys, glob, numpy as np, trimesh, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
m = trimesh.load(sys.argv[1]); V = m.vertices * 87 / 1000; P = np.vstack([np.load(f)[:, :3] for f in sorted(glob.glob("/media/oem/scan/rc-park_null/kaufhaus_handy3/dicht_neu/stapel/sicher_*_modell.npy"))])
P = P[::6]; fig, ax = plt.subplots(1, 3, figsize=(24, 8)); E = m.edges_unique
for a, (i, j, t) in zip(ax, ((0, 2, "Vorderansicht x-z"), (1, 2, "Seite y-z"), (0, 1, "Draufsicht x-y"))):
    a.scatter(P[:, i], P[:, j], s=0.2, c="0.6", alpha=0.5)
    for e in E: a.plot(V[e, i], V[e, j], "r-", lw=0.8)
    a.set_aspect("equal"); a.set_title(t); a.set_xlim(-14, 16) if i == 0 else None
plt.tight_layout(); plt.savefig(sys.argv[2], dpi=55)
