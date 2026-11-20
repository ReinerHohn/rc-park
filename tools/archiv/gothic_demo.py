#!/usr/bin/env python3
"""gothic_demo.py — Demonstrator fürs Skelett-+-Maßwerk-System:
  (1) GERÜST (gothic-frame.stl): Wand mit Spitzbogen-Öffnung + umlaufendem Absatz
      (Rebate), in den die flache Platte bündig einsetzt. Schnell druckbar (0,8).
  (2) MASSWERK (gothic-tracery.stl): flache, durchbrochene Spitzbogen-Platte
      (Rahmen + Pfosten + Maßwerk/Rose). LIEGEND drucken (0,4), von hinten
      beleuchtbar → Licht durch die Öffnungen.
Beweist, dass sich ein Fenster sauber splitten lässt (Münster-Prinzip im Kleinen).
"""
import numpy as np, trimesh
from shapely.geometry import Polygon, box as sbox, Point
from shapely.ops import unary_union

# Maße (mm)
W, SPRING = 26.0, 28.0        # Fenster: Breite, gerade Wand bis Kämpfer
SLAB_W, SLAB_H, SLAB_T = 46.0, 70.0, 6.0
X0, Y0 = (SLAB_W-W)/2, 8.0     # Fenster-Ursprung in der Wand
REBATE, PANEL_T = 3.0, 2.4     # Absatz-Breite, Plattendicke
BORDER, BAR = 2.2, 1.8         # Rahmenbreite, Pfosten-/Stegbreite (0,8-düsen-tauglich)


def lancet(w, spring, x0=0, y0=0, n=28):
    """Spitzbogen (gleichseitig): gerade Wände bis spring, zwei Bögen zur Spitze."""
    R = w; apex = spring + np.sqrt(R**2 - (w/2)**2)
    P = [(0, 0), (w, 0), (w, spring)]
    cx, cy = 0, spring                                   # rechter Bogen, Zentrum links
    for t in np.linspace(0, np.radians(60), n):
        P.append((cx+R*np.cos(t), cy+R*np.sin(t)))
    cx, cy = w, spring                                   # linker Bogen, Zentrum rechts
    for t in np.linspace(np.radians(120), np.radians(180), n):
        P.append((cx+R*np.cos(t), cy+R*np.sin(t)))
    P.append((0, spring))
    poly = Polygon(P)
    return trimesh.path.polygons.transform_polygon(poly, None) if False else \
           Polygon([(x+x0, y+y0) for x, y in poly.exterior.coords])


def ext(poly, h, z=0.0):
    poly = poly.buffer(0.02).buffer(-0.02)      # Kontur sauber re-meshen (killt degen. Dreiecke)
    geoms = list(poly.geoms) if poly.geom_type == "MultiPolygon" else [poly]
    parts = [trimesh.creation.extrude_polygon(g, height=h) for g in geoms if g.area > 1e-3]
    m = trimesh.util.concatenate(parts) if len(parts) > 1 else parts[0]
    m.apply_translation([0, 0, z]); return m


def main():
    inner = lancet(W, SPRING, X0, Y0)          # Öffnung
    outer = inner.buffer(REBATE)               # Platte/Rebate (größer)
    apex = Y0 + SPRING + np.sqrt(W**2-(W/2)**2)
    cx = X0 + W/2

    # ---- (1) GERÜST ----
    slab = ext(Polygon([(0,0),(SLAB_W,0),(SLAB_W,SLAB_H),(0,SLAB_H)]), SLAB_T)
    thru = ext(inner, SLAB_T+2, -1)                         # Durchbruch
    reb  = ext(outer, PANEL_T+0.3, SLAB_T-PANEL_T)          # Absatz vorne (Platte sitzt rein)
    frame = slab.difference(reb).difference(thru)           # sequenziell
    frame.export("modelle/3d_druck/gothic-frame.stl")
    print(f"GERÜST: {SLAB_W:.0f}x{SLAB_H:.0f}x{SLAB_T:.0f}mm, Absatz {REBATE}mm/{PANEL_T}mm  "
          f"watertight={frame.is_watertight}")

    # ---- (2) MASSWERK (flach, garantiert zusammenhängend) ----
    glaz = inner.buffer(-BORDER)                            # verglaste Innenfläche
    border = outer.difference(glaz)                         # Rahmen-Ring (ein Stück)
    bars = []
    for gx in (cx - W/6, cx + W/6):                         # 2 Pfosten → 3 Bahnen
        bars.append(sbox(gx-BAR/2, Y0, gx+BAR/2, Y0+SPRING+8))
    bars.append(sbox(X0, Y0+SPRING*0.55-BAR/2, X0+W, Y0+SPRING*0.55+BAR/2))  # Kämpferriegel
    rose_c = (cx, Y0+SPRING + (apex-(Y0+SPRING))*0.45)      # Rose im Bogenfeld
    rose = Point(*rose_c).buffer(5.2).difference(Point(*rose_c).buffer(5.2-BAR))
    bars = [b.intersection(outer) for b in bars]
    filigree = unary_union([border] + bars + [rose]).intersection(outer)
    if filigree.geom_type == "MultiPolygon":
        filigree = max(filigree.geoms, key=lambda g: g.area)
    panel = ext(filigree, PANEL_T)
    panel.export("modelle/3d_druck/gothic-tracery.stl")
    print(f"MASSWERK: flach {PANEL_T}mm, {len(filigree.interiors)} Licht-Öffnungen  "
          f"watertight={panel.is_watertight} zusammenhängend=1Stück  (liegend, hinterleuchtbar)")


if __name__ == "__main__":
    main()
