#!/usr/bin/env python3
"""terrain_stack_tiles.py — zerlegt ein hohes Gelände-STL in STECKBARE Kacheln.

Teilt in nx×ny (XY, Bettgröße) UND in Z-Etagen (≤ max-z = Drucker-Bauhöhe), so dass
die echten Höhen erhalten bleiben (KEINE Abflachung) und das Modell auf einem kleinen
Drucker (z.B. MK4S, 220 mm Z) entsteht. An den Z-Fugen werden Zapfen (Pins) auf die
Oberseite der unteren Etage gesetzt und passende Löcher in die Unterseite der oberen —
so STECKEN die Etagen zusammen. Die Schnittebenen sind innen/versteckt; die sichtbare
Geländeoberfläche bleibt echt.

Beispiel:
  python3 tools/terrain_stack_tiles.py modelle/3d_druck/hirschsprung_osm.stl \
      --bed-x 250 --bed-y 210 --max-z 205 --prefix /tmp/st
"""
import argparse, numpy as np, trimesh
import trimesh.transformations as T


def terrain_top(m, x, y, zhi, zlo):
    """Höhe der Geländeoberfläche an (x,y) per Ray von oben."""
    try:
        locs, _, _ = m.ray.intersects_location([[x, y, zhi + 20]], [[0, 0, -1]])
        if len(locs):
            return float(locs[:, 2].max())
    except Exception:
        pass
    return zlo


def peg(r, h, cx, cy, cz):
    c = trimesh.creation.cylinder(radius=r, height=h, sections=16)
    c.apply_translation([cx, cy, cz])
    return c


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--bed-x", type=float, default=250)
    p.add_argument("--bed-y", type=float, default=210)
    p.add_argument("--max-z", type=float, default=205)   # sichere Bauhöhe (< 220)
    p.add_argument("--prefix", default="modelle/3d_druck/stack")
    p.add_argument("--pin-r", type=float, default=6.0)
    p.add_argument("--pin-h", type=float, default=14.0)  # halb oben / halb im Loch
    a = p.parse_args()

    m = trimesh.load(a.input, force="mesh")
    (x0, y0, z0), (x1, y1, z1) = m.bounds
    W, D, H = x1 - x0, y1 - y0, z1 - z0
    nx = int(np.ceil(W / a.bed_x)); ny = int(np.ceil(D / a.bed_y))
    nz = int(np.ceil(H / a.max_z))
    xs = np.linspace(x0, x1, nx + 1); ys = np.linspace(y0, y1, ny + 1)
    zs = np.linspace(z0, z1, nz + 1)
    print(f"Modell {W:.0f}×{D:.0f}×{H:.0f} mm → {nx}×{ny} XY × {nz} Z-Etagen "
          f"(Etage {H/nz:.0f} mm ≤ {a.max_z:.0f})")

    # Zapfen-XY je XY-Zelle (Zellmitte; Fallback-Offsets wenn dort kein Material)
    pin_xy = {}
    for xi in range(nx):
        for yi in range(ny):
            cx = (xs[xi] + xs[xi+1]) / 2; cy = (ys[yi] + ys[yi+1]) / 2
            pin_xy[(xi, yi)] = (cx, cy)

    made = []
    ph = a.pin_h
    for zi in range(nz):
        for yi in range(ny):
            for xi in range(nx):
                zlo, zhi = zs[zi], zs[zi+1]
                cutter = trimesh.creation.box(
                    extents=[xs[xi+1]-xs[xi], ys[yi+1]-ys[yi], (zhi-zlo)])
                cutter.apply_translation([(xs[xi]+xs[xi+1])/2,
                                          (ys[yi]+ys[yi+1])/2, (zlo+zhi)/2])
                try:
                    tile = m.intersection(cutter)
                except Exception as e:
                    print(f"  z{zi}y{yi}x{xi}: Fehler {e}"); continue
                if tile.is_empty or len(tile.faces) == 0:
                    continue
                cx, cy = pin_xy[(xi, yi)]
                tt = terrain_top(m, cx, cy, z1, z0)
                # Zapfen oben (wenn nicht oberste Etage und Gelände reicht drüber)
                if zi < nz - 1 and tt > zhi + ph * 0.5:
                    tile = tile.union(peg(a.pin_r, ph, cx, cy, zhi))
                # Loch unten (wenn nicht unterste Etage und Material drunter)
                if zi > 0 and tt > zlo + 2:
                    tile = tile.difference(peg(a.pin_r + 0.4, ph + 2, cx, cy, zlo))
                # flach auf Ursprung legen, drehen falls nötig
                tile.apply_translation(-tile.bounds[0])
                ext = tile.extents
                if ext[0] > a.bed_x or ext[1] > a.bed_y:
                    tile.apply_transform(T.rotation_matrix(np.pi/2, [0, 0, 1]))
                    tile.apply_translation(-tile.bounds[0]); ext = tile.extents
                fit = "OK" if (ext[0] <= a.bed_x and ext[1] <= a.bed_y
                               and ext[2] <= 220) else "PASST NICHT!"
                fn = f"{a.prefix}_z{zi}y{yi}x{xi}.stl"
                tile.export(fn); made.append(fn)
                print(f"  z{zi}y{yi}x{xi}: {ext[0]:.0f}×{ext[1]:.0f}×{ext[2]:.0f} mm "
                      f"wt={tile.is_watertight} {fit} -> {fn}")
    print(f"\n{len(made)} Steckkacheln exportiert.")


if __name__ == "__main__":
    main()
