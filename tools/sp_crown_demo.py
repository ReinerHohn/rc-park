#!/usr/bin/env python3
"""sp_crown_demo.py — DEMO-Kranz zum 3-mm-LED-Fit-Test: sauberer Ring (wasserdicht),
groß genug, Wand dick genug, mit N senkrechten (radialen) selbst-zentrierenden
Ø-Löchern. Runde 3-mm-LED klemmt gerade in der Lochwand → nur reinkleben.
"""
import sys, numpy as np, trimesh
sys.path.insert(0, "tools")
import light_prep as L

OUT = "modelle/3d_druck/sp-crown-demo.stl"

R_OUT   = 20.0        # Außenradius (Ø40 mm) — reichlich Platz für 3-mm
WALL    = 4.0         # Wanddicke → 3-mm-LED (Körper ~3 mm) sitzt im Barrel
HEIGHT  = 25.0        # Ringhöhe
LED_HOLE = 3.3        # Ø für 3-mm-LED (3,0 + 0,3 Klebespiel)
N_HOLES = 8           # Löcher rundum


def main():
    r_in = R_OUT - WALL
    # sauberer, wasserdichter Ring (Annulus mit Deckeln)
    ring = trimesh.creation.annulus(r_min=r_in, r_max=R_OUT, height=HEIGHT, sections=96)
    ring.apply_translation([0, 0, HEIGHT / 2.0])   # auf z=0 absetzen
    zmid = HEIGHT / 2.0

    holes = []
    for i in range(N_HOLES):
        a = 2 * np.pi * i / N_HOLES
        p = [R_OUT * np.cos(a), R_OUT * np.sin(a), zmid]   # Mund außen
        d = [np.cos(a), np.sin(a), 0.0]                    # senkrecht/radial
        holes.append({"type": "bore", "pos": p, "dir": d,
                      "d": LED_HOLE, "through": WALL + 4.0, "overshoot": 1.5})

    out = L.prep(ring, holes)
    out.export(OUT)
    gap = 2 * np.pi * R_OUT / N_HOLES - LED_HOLE
    print(f"Ring Ø{2*R_OUT:.0f} mm, Wand {WALL:.0f} mm, h {HEIGHT:.0f} mm, "
          f"{N_HOLES}×Ø{LED_HOLE} Löcher, Lücke zw. Löchern ≈{gap:.0f} mm")
    print(f"watertight={out.is_watertight} faces={len(out.faces):,} -> {OUT}")


if __name__ == "__main__":
    main()
