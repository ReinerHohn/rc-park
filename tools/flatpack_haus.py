#!/usr/bin/env python3
"""flatpack_haus.py — Gebäude als FLAT-PACK-Bausatz für schnellen Druck.

Erzeugt flach liegende Teile (schnell + scharfe Details + kein Support):
  - 4 Wände (Fenster/Tür-Öffnungen, Steck-Tabs unten, erhabene Nummer)
  - Boden mit passenden Schlitzen (Wände stecken rein → ausgerichtet)
  - Giebeldach (2 Dachplatten)
Zusammenbau: Wände in Bodenschlitze stecken, Ecken kleben, Dach drauf.
Maßstab 1:160 (N) default. Haus hohl + Fenster offen → mit LED beleuchtbar.

Beispiel:
  python3 tools/flatpack_haus.py --w 8 --d 6 --h 6 --cols 3 --rows 2 \
      --name H1 --out modelle/flatpack
"""
import argparse, os, numpy as np, trimesh
import sys; sys.path.insert(0, os.path.dirname(__file__))
from light_prep import window as _win
from terrain_spanten import text_mesh

def U(p): return trimesh.util.concatenate([x for x in p if x is not None])

def wall_panel(w, h, t, wins, tabs, label):
    """Flache Wand (liegt in XY, Dicke Z=t). wins=[(cx,cz,ww,wh)], tabs=[x-Positionen]."""
    p = trimesh.creation.box(extents=[w, h, t]); p.apply_translation([w/2, h/2, t/2])
    cuts = []
    for (cx, cz, ww, wh) in wins:
        c = trimesh.creation.box(extents=[ww, wh, t+2]); c.apply_translation([cx, cz, t/2]); cuts.append(c)
    if cuts: p = p.difference(U(cuts))
    # Steck-Tabs unten (ragen in -Y)
    tb = []
    for tx in tabs:
        b = trimesh.creation.box(extents=[6, 4, t]); b.apply_translation([tx, -2, t/2]); tb.append(b)
    panel = U([p]+tb)
    # Nummer erhaben oben auf die Platte
    lbl = text_mesh(label, size=5, depth=0.5)
    if lbl is not None:
        lbl.apply_translation([w/2-6, h-6, t]); panel = U([panel, lbl])
    return panel

def floor_with_slots(w, d, ft, tol, wall_t, tabsets):
    """Boden w x d, Schlitze für die Wand-Tabs (tabsets = {'front':[x..],'back':[x..],'left':[y..],'right':[y..]})."""
    fl = trimesh.creation.box(extents=[w, d, ft]); fl.apply_translation([w/2, d/2, ft/2])
    cuts = []
    inset = wall_t/2 + 0.5
    for tx in tabsets['front']:
        c = trimesh.creation.box(extents=[6+2*tol, wall_t+2*tol, ft+2]); c.apply_translation([tx, inset, ft/2]); cuts.append(c)
    for tx in tabsets['back']:
        c = trimesh.creation.box(extents=[6+2*tol, wall_t+2*tol, ft+2]); c.apply_translation([tx, d-inset, ft/2]); cuts.append(c)
    for ty in tabsets['left']:
        c = trimesh.creation.box(extents=[wall_t+2*tol, 6+2*tol, ft+2]); c.apply_translation([inset, ty, ft/2]); cuts.append(c)
    for ty in tabsets['right']:
        c = trimesh.creation.box(extents=[wall_t+2*tol, 6+2*tol, ft+2]); c.apply_translation([w-inset, ty, ft/2]); cuts.append(c)
    if cuts: fl = fl.difference(U(cuts))
    return fl

def win_grid(span, h, cols, rows, door=False):
    """Fenster-Raster auf einer Wand der Breite 'span', Höhe 'h'."""
    wins = []
    xs = np.linspace(span*0.18, span*0.82, cols)
    zs = np.linspace(h*0.35, h*0.78, rows)
    for x in xs:
        for z in zs: wins.append((x, z, 5, 7))
    if door: wins.append((span/2, h*0.22, 7, 13))
    return wins, list(np.round(xs,1))

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--w', type=float, default=8, help='Breite real [m]')
    p.add_argument('--d', type=float, default=6, help='Tiefe real [m]')
    p.add_argument('--h', type=float, default=6, help='Wandhöhe real [m]')
    p.add_argument('--scale', type=float, default=160)
    p.add_argument('--cols', type=int, default=3); p.add_argument('--rows', type=int, default=2)
    p.add_argument('--t', type=float, default=1.6, help='Wandstärke mm')
    p.add_argument('--tol', type=float, default=0.2)
    p.add_argument('--name', default='H1'); p.add_argument('--out', default='modelle/flatpack')
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    k = 1000/a.scale
    W, D, H, t = a.w*k, a.d*k, a.h*k, a.t
    print(f"Haus 1:{a.scale:.0f}: {W:.0f} x {D:.0f} x {H:.0f} mm")
    # Tabs: 2-3 je Wand
    ftab = list(np.linspace(W*0.25, W*0.75, 2)); stab = list(np.linspace(D*0.25, D*0.75, 2))
    fw, _ = win_grid(W, H, a.cols, a.rows, door=True)
    bw, _ = win_grid(W, H, a.cols, a.rows)
    lw, _ = win_grid(D, H, max(1,a.cols-1), a.rows)
    rw, _ = win_grid(D, H, max(1,a.cols-1), a.rows)
    panels = {
        'front': wall_panel(W, H, t, fw, ftab, f"{a.name}-F"),
        'back':  wall_panel(W, H, t, bw, ftab, f"{a.name}-B"),
        'left':  wall_panel(D, H, t, lw, stab, f"{a.name}-L"),
        'right': wall_panel(D, H, t, rw, stab, f"{a.name}-R"),
    }
    floor = floor_with_slots(W, D, t, a.tol, t, {'front':ftab,'back':ftab,'left':stab,'right':stab})
    # Giebeldach: 2 Platten (Schräge), flach
    ov = 5; rlen = W+2*ov; rslope = (D/2+ov)  # grob
    roof1 = trimesh.creation.box(extents=[rlen, rslope, t]); roof1.apply_translation([rlen/2, rslope/2, t/2])
    roof2 = trimesh.creation.box(extents=[rlen, rslope, t]); roof2.apply_translation([rlen/2, rslope/2, t/2])
    lbl = text_mesh(f"{a.name}-D", size=5, depth=0.5)
    if lbl is not None: lbl.apply_translation([rlen/2-6, rslope-6, t]); roof1 = U([roof1,lbl])

    # alles flach auf Platte: Shelf-Packing ins Bett (max 240 breit, 200 tief)
    items = [panels['front'],panels['back'],panels['left'],panels['right'],floor,roof1,roof2]
    gap = 5; BEDW = 240
    layout = []; cx = 0; cy = 0; rowh = 0
    for m in items:
        m = m.copy(); m.apply_translation([-m.bounds[0][0], -m.bounds[0][1], 0])  # nach 0,0
        w_, d_ = m.extents[0], m.extents[1]
        if cx + w_ > BEDW:          # neue Reihe
            cx = 0; cy += rowh + gap; rowh = 0
        m.apply_translation([cx, cy, 0]); layout.append(m)
        cx += w_ + gap; rowh = max(rowh, d_)
    plate = U(layout); fn = f"{a.out}/{a.name}_flatpack.stl"; plate.export(fn)
    e = plate.extents
    print(f"Flat-Pack-Platte: {e[0]:.0f} x {e[1]:.0f} x {e[2]:.1f} mm -> {fn}")
    print(f"Teile: {a.name}-F/B/L/R (Wände) + Boden + {a.name}-D (2 Dach). Wände in Bodenschlitze, Ecken kleben, Dach drauf.")

if __name__ == '__main__':
    main()
