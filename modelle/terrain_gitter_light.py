#!/usr/bin/env python3
"""terrain_gitter_light.py - wie terrain_gitter, aber Rippen als FACHWERK (Löcher)
→ deutlich weniger Filament. Jede Rippe = durchgehende Bodenschiene + Oberband (folgt
Topografie) + senkrechte Posten; dazwischen Lücher. Reine Polygon-Extrusion (robust).

  python3 terrain_gitter_light.py --stl belchen_skigebiet.stl --foot 220 --exagg 1.6 \
      --ribs 10 --t 0.9 --out belchen_gitter_light.stl
"""
import argparse, numpy as np, trimesh
from shapely.geometry import Polygon
from terrain_gitter import hf_from_stl, hf_synth, sample

def rib_mesh(coords, hs, t, base, band, post_w, pitch, axis, pos):
    L = coords[-1]
    # Außenkontur: Unterkante (links->rechts) + Oberkante (rechts->links, folgt Gelände)
    outer = [(c, 0.0) for c in coords] + [(c, h) for c, h in zip(coords[::-1], hs[::-1])]
    holes = []
    c = post_w
    while c + post_w < L:
        ca, cb = c, min(c + (pitch - post_w), L - post_w)
        if cb - ca < 4:
            break
        # min. Geländehöhe über dem Lochbereich -> Oberband bleibt stehen
        mask = (coords >= ca) & (coords <= cb)
        hmin = hs[mask].min() if mask.any() else hs.min()
        top = hmin - band
        bot = base
        if top - bot > 4:
            holes.append([(ca, bot), (cb, bot), (cb, top), (ca, top)])
        c += pitch
    poly = Polygon(outer, holes)
    if not poly.is_valid:
        poly = poly.buffer(0)
    m = trimesh.creation.extrude_polygon(poly, height=t)  # Polygon in XY, extrudiert in Z
    V = m.vertices.copy()
    px, py, pz = V[:, 0], V[:, 1], V[:, 2]
    if axis == 'y':   # Rippe läuft entlang world-Y bei world-x=pos
        out = np.column_stack([pos + pz - t / 2, px, py])
    else:             # entlang world-X bei world-y=pos
        out = np.column_stack([px, pos + pz - t / 2, py])
    return trimesh.Trimesh(out, m.faces, process=False)

def build(H, fx, fy, hscale, nribs, t, base, band, post_w, pitch, msamp=200):
    meshes = []
    for u in np.linspace(0, 1, nribs):      # Y-Rippen (x=pos)
        cs = np.linspace(0, 1, msamp)
        hs = np.maximum(sample(H, u * np.ones_like(cs), cs) * hscale, base + band + 2)
        meshes.append(rib_mesh(cs * fy, hs, t, base, band, post_w, pitch, 'y', u * fx))
    for v in np.linspace(0, 1, nribs):      # X-Rippen (y=pos)
        cs = np.linspace(0, 1, msamp)
        hs = np.maximum(sample(H, cs, v * np.ones_like(cs)) * hscale, base + band + 2)
        meshes.append(rib_mesh(cs * fx, hs, t, base, band, post_w, pitch, 'x', v * fy))
    m = trimesh.util.concatenate(meshes)
    trimesh.repair.fix_normals(m)
    return m

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--stl'); p.add_argument('--out', default='/tmp/gitter_light.stl')
    p.add_argument('--foot', type=float, default=220); p.add_argument('--exagg', type=float, default=1.6)
    p.add_argument('--ribs', type=int, default=10); p.add_argument('--t', type=float, default=0.9)
    p.add_argument('--base', type=float, default=3.5); p.add_argument('--band', type=float, default=5.0)
    p.add_argument('--post', type=float, default=3.0); p.add_argument('--pitch', type=float, default=22.0)
    p.add_argument('--grid', type=int, default=200)
    a = p.parse_args()
    if a.stl:
        H, ar = hf_from_stl(a.stl, a.grid); hscale = a.exagg
    else:
        H, ar = hf_synth(a.grid); hscale = 60 * a.exagg
    fx = a.foot if ar >= 1 else a.foot * ar
    fy = a.foot if ar < 1 else a.foot / ar
    m = build(H, fx, fy, hscale, a.ribs, a.t, a.base, a.band, a.post, a.pitch)
    e = m.extents
    print(f'FACHWERK {a.ribs}x{a.ribs}  t={a.t}mm  Band={a.band} Posten={a.post}@{a.pitch}mm')
    print(f'Masse: {e[0]:.0f} x {e[1]:.0f} x {e[2]:.0f} mm   Dreiecke: {len(m.faces):,}')
    m.export(a.out); print(f'-> {a.out}')
