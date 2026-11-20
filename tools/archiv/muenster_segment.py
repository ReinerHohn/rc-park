#!/usr/bin/env python3
"""muenster_segment.py — EIN Münsterturm-Segment als GERÜST zum Stapeln:
  - 4 Gotik-Wände (Spitzbogen-Fenster + Absatz für einsteckbares Maßwerk)
  - 4 Eckpfeiler (Strebe/Buttress-Look, verbinden die Wände)
  - Stapel-Kragen oben (zentriert das nächste Segment)
+ das flache Maßwerk-Panel (1 Design, 4× drucken).
Baut die Wände flach (2D, bewährt) und dreht sie in Position → kein 3D-Fenster-Boolean.
"""
import sys, numpy as np, trimesh
sys.path.insert(0, "tools")
from gothic_demo import lancet, ext
from shapely.geometry import Polygon, box as sbox, Point
from shapely.ops import unary_union
import trimesh.transformations as T

SIDE, HGT, WALL = 56.0, 90.0, 4.0     # Turm-Außenkante, Segmenthöhe, Wanddicke
WIN_W, WIN_SPR = 26.0, 56.0           # Fenster: Breite, gerade Wand bis Kämpfer
REBATE, PANEL_T = 3.0, 2.4
BORDER, BAR = 2.2, 1.8                # 0,8-tauglich
POST = 7.0                            # Eckpfeiler-Kantenlänge


def wall_slab():
    """Flache Gotik-Wand in XY: X∈[-SIDE/2,SIDE/2], Y∈[0,HGT], Z∈[0,WALL]."""
    x0 = -WIN_W/2
    inner = lancet(WIN_W, WIN_SPR, x0, 14.0)
    outer = inner.buffer(REBATE)
    slab = ext(Polygon([(-SIDE/2,0),(SIDE/2,0),(SIDE/2,HGT),(-SIDE/2,HGT)]), WALL)
    thru = ext(inner, WALL+2, -1)
    reb  = ext(outer, PANEL_T+0.3, WALL-PANEL_T)
    return slab.difference(reb).difference(thru), inner, outer


def place_wall(wall, angle_deg):
    """XY-Wand aufrichten (+90° um X) und an die +Y-Seite drehen/schieben."""
    m = wall.copy()
    m.apply_transform(T.rotation_matrix(np.pi/2, [1,0,0]))   # Höhe→Z, Dicke→-Y
    m.apply_translation([0, 0, 0])
    m.apply_translation([0, SIDE/2, 0])                       # an die Außenkante +Y
    m.apply_transform(T.rotation_matrix(np.radians(angle_deg), [0,0,1]))
    return m


def tracery_panel():
    """Flaches Maßwerk (zusammenhängend), passend zum Fenster."""
    x0 = -WIN_W/2
    inner = lancet(WIN_W, WIN_SPR, x0, 14.0); outer = inner.buffer(REBATE)
    cx = 0.0; apex = 14.0 + WIN_SPR + np.sqrt(WIN_W**2-(WIN_W/2)**2)
    glaz = inner.buffer(-BORDER); border = outer.difference(glaz)
    bars = []
    for gx in (cx-WIN_W/6, cx+WIN_W/6):
        bars.append(sbox(gx-BAR/2, 14.0, gx+BAR/2, 14.0+WIN_SPR+8))
    bars.append(sbox(x0, 14.0+WIN_SPR*0.5-BAR/2, x0+WIN_W, 14.0+WIN_SPR*0.5+BAR/2))
    rc = (cx, 14.0+WIN_SPR + (apex-(14.0+WIN_SPR))*0.45)
    rose = Point(*rc).buffer(5.2).difference(Point(*rc).buffer(5.2-BAR))
    bars = [b.intersection(outer) for b in bars]
    fil = unary_union([border]+bars+[rose]).intersection(outer)
    if fil.geom_type == "MultiPolygon":
        fil = max(fil.geoms, key=lambda g: g.area)
    return ext(fil, PANEL_T)


def base_plate():
    """Boden-Lehre: Platte mit umlaufender NUT, in die die 4 Wände selbst-ausrichtend
    einrasten (Wand-Fußabdruck = Quadrat-Ring außen SIDE / innen SIDE-2*WALL)."""
    clr = 0.4
    base = trimesh.creation.box(extents=[SIDE+6, SIDE+6, 3.0])
    base.apply_translation([0, 0, 1.5])
    ring_o = trimesh.creation.box(extents=[SIDE+clr, SIDE+clr, 2.4])
    ring_i = trimesh.creation.box(extents=[SIDE-2*WALL-clr, SIDE-2*WALL-clr, 3.0])
    groove = ring_o.difference(ring_i); groove.apply_translation([0, 0, 3.0-1.0])  # Nut 2mm tief von oben
    return base.difference(groove)


def main():
    wall, inner, outer = wall_slab()        # FLACH in XY (Fassaden-Zier liegt in XY = scharf)
    wall.export("modelle/3d_druck/muenster-wall.stl")
    print(f"WAND (4× flach drucken): {SIDE:.0f}x{HGT:.0f}x{WALL:.0f}mm  watertight={wall.is_watertight}")

    pan = tracery_panel()
    pan.export("modelle/3d_druck/muenster-tracery.stl")
    print(f"MASSWERK (4× flach): watertight={pan.is_watertight}")

    base = base_plate()
    base.export("modelle/3d_druck/muenster-base.stl")
    print(f"BODEN-LEHRE (Nut, selbst-ausrichtend, stapelbar): watertight={base.is_watertight}")
    print("Bausatz: 4× Wand + 4× Maßwerk + 1× Boden-Lehre → alles FLACH gedruckt, zusammenkleben.")


if __name__ == "__main__":
    main()
