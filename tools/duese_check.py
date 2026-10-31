#!/usr/bin/env python3
"""duese_check.py - Welche Teile sind mit Duese X druckbar? Dicke (Strahl nach innen) und Spalt (Strahl nach aussen).
  python tools/duese_check.py ORDNER_MIT_STL [--duese 0.2] [--proben 6000]
Regel: Wand >= 2 Linien (2 x 1,1 x Duese), Spalt >= 1 Linie (1,1 x Duese)."""
import argparse, glob, os, numpy as np, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("dir"); ap.add_argument("--duese", type=float, default=0.2)
ap.add_argument("--proben", type=int, default=6000); a = ap.parse_args()
wmin = 2 * 1.1 * a.duese; gmin = 1.1 * a.duese
rows = []
for f in sorted(glob.glob(os.path.join(a.dir, "*.stl"))):
    m = trimesh.load(f); P, fi = trimesh.sample.sample_surface(m, a.proben, seed=1); N = m.face_normals[fi]
    o_in = P - N * 1e-3
    loc, ir, _ = m.ray.intersects_location(o_in, -N, multiple_hits=False)
    th = np.full(len(P), np.inf); th[ir] = np.linalg.norm(loc - o_in[ir], axis=1)
    o_out = P + N * 1e-3
    loc, ir, _ = m.ray.intersects_location(o_out, N, multiple_hits=False)
    gp = np.full(len(P), np.inf); gp[ir] = np.linalg.norm(loc - o_out[ir], axis=1)
    rows.append((os.path.basename(f), m.volume / 1000, (th < wmin).mean(), (gp < gmin).mean(), np.percentile(th[np.isfinite(th)], 5) if np.isfinite(th).any() else 0))
print(f"Duese {a.duese} mm: Wand >= {wmin:.2f} mm, Spalt >= {gmin:.2f} mm")
bad = [r for r in rows if r[2] > 0.02 or r[3] > 0.02]
print(f"{len(rows)} Teile, davon {len(bad)} mit >2 % zu duenner Wand oder zu engem Spalt")
for n, v, t, g, p5 in sorted(rows, key=lambda r: -(r[2] + r[3]))[:15]:
    print(f"  {n:28s} {v:6.2f} cm3  zu duenn {t*100:5.1f} %  zu eng {g*100:5.1f} %  Dicke p5 {p5:.2f} mm")
