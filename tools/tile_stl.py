#!/usr/bin/env python3
"""tile_stl.py — zerlegt ein großes STL in bett-taugliche Druckkacheln (Gitter).

Schneidet per manifold-Intersection in nx×ny Kacheln, legt jede flach mit
Min-Ecke auf den Ursprung, dreht bei Bedarf 90° damit sie aufs Bett passt,
und exportiert prefix_r{r}c{c}.stl. Alle Kacheln teilen z=0 (Tischebene) →
stehen nebeneinander und ergeben wieder das Gesamtgelände.
"""
import argparse, numpy as np, trimesh

def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--nx", type=int, default=3)
    p.add_argument("--ny", type=int, default=2)
    p.add_argument("--bed-x", type=float, default=250)
    p.add_argument("--bed-y", type=float, default=210)
    p.add_argument("--prefix", default="modelle/3d_druck/hoellental_tile")
    a = p.parse_args()

    m = trimesh.load(a.input, force="mesh")
    b = m.bounds
    (x0, y0, z0), (x1, y1, z1) = b[0], b[1]
    xs = np.linspace(x0, x1, a.nx + 1)
    ys = np.linspace(y0, y1, a.ny + 1)
    print(f"Modell {x1-x0:.0f}×{y1-y0:.0f}×{z1-z0:.0f} mm → {a.nx}×{a.ny} Kacheln")
    made = []
    for r in range(a.ny):
        for c in range(a.nx):
            cx = (xs[c] + xs[c+1]) / 2; cy = (ys[r] + ys[r+1]) / 2
            cz = (z0 + z1) / 2
            cutter = trimesh.creation.box(
                extents=[xs[c+1]-xs[c], ys[r+1]-ys[r], (z1-z0)+10])
            cutter.apply_translation([cx, cy, cz])
            try:
                tile = m.intersection(cutter)
            except Exception as e:
                print(f"  r{r}c{c}: Fehler {e}"); continue
            if tile.is_empty or len(tile.faces) == 0:
                print(f"  r{r}c{c}: leer"); continue
            tb = tile.bounds
            tile.apply_translation(-tb[0])            # Min-Ecke auf Ursprung
            ext = tile.extents
            if ext[0] > a.bed_x or ext[1] > a.bed_y:  # 90° drehen falls nötig
                tile.apply_transform(trimesh.transformations.rotation_matrix(
                    np.pi/2, [0, 0, 1]))
                tile.apply_translation(-tile.bounds[0]); ext = tile.extents
            fit = "OK" if (ext[0] <= a.bed_x and ext[1] <= a.bed_y) else "PASST NICHT!"
            fn = f"{a.prefix}_r{r}c{c}.stl"
            tile.export(fn)
            made.append(fn)
            print(f"  r{r}c{c}: {ext[0]:.0f}×{ext[1]:.0f}×{ext[2]:.0f} mm  "
                  f"wt={tile.is_watertight}  {fit}  -> {fn}")
    print(f"\n{len(made)} Kacheln exportiert.")

if __name__ == "__main__":
    main()
