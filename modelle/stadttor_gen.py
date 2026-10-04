#!/usr/bin/env python3
"""
stadttor_gen.py — generiert ein stilisiertes Freiburger Stadttor (Martinstor/
Schwabentor-Typ) als wasserdichte STL: quadratischer Turm mit Rundbogen-Durchfahrt,
Gesims und steilem Spitzdach.

Erzeugt (in modelle/stl/):
  freiburger_stadttor.stl        komplettes Modell
  stadttor_turm.stl              Teil 1 (Turm + Gesims)   — Bausatz
  stadttor_dach.stl              Teil 2 (Spitzdach)        — Bausatz

Rein numpy/stdlib, keine externen Mesh-Libs. Geometrie ist bewusst supportfrei:
Rundbogen ist selbsttragend, Dachflächen sind mit ~67° steiler als 45°.

Masse in mm. Standard: ~40 mm Grundflaeche, ~139 mm hoch. Zum Verkleinern im
Slicer skalieren.
"""

import math
import struct

# ---------------------------------------------------------------- Parameter
TX = 40.0          # Turm-Tiefe  (Extrusionsrichtung X, = Durchfahrt)
TY = 40.0          # Turm-Breite (Y, Fassadenbreite)
TH = 80.0          # Turmkoerper-Hoehe
AW = 20.0          # Breite der Torbogen-Durchfahrt
R = AW / 2.0       # Bogenradius
ASPRING = 30.0     # Hoehe, auf der der Rundbogen ansetzt
ARCTOP = ASPRING + R
CY = TY / 2.0      # Mitte der Durchfahrt (Y)
ARC_SEG = 16       # Segmente je Bogen-Viertel (Glattheit)

OVER = 3.0         # Gesims-Ueberstand
CZ0, CZ1 = TH, TH + 6.0          # Gesims unten/oben
ROOF_BASE_Z = CZ1 - 2.0          # Dachbasis ragt 2 mm ins Gesims (saubere Union)
ROOF_H = 55.0                    # Dachhoehe


# ---------------------------------------------------------------- Helfer
def norm(p1, p2, p3):
    ux, uy, uz = p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]
    vx, vy, vz = p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / ln, ny / ln, nz / ln)


def box(x0, x1, y0, y1, z0, z1):
    """12 Dreiecke, Normalen nach aussen."""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    q = [(0, 3, 2, 1),   # unten (-Z)
         (4, 5, 6, 7),   # oben  (+Z)
         (0, 1, 5, 4),   # -Y
         (2, 3, 7, 6),   # +Y
         (1, 2, 6, 5),   # +X
         (3, 0, 4, 7)]   # -X
    tris = []
    for a, b, c, d in q:
        tris.append((v[a], v[b], v[c]))
        tris.append((v[a], v[c], v[d]))
    return tris


def tower_profile():
    """2D-Dreiecke (y,z) des Turm-Querschnitts: Rechteck mit Rundbogen-Nische
    unten. CCW-orientiert (von +X gesehen)."""
    t = []
    L = CY - R           # linke Pfeilerkante (y)
    Rr = CY + R          # rechte Pfeilerkante (y)

    # A: linker Pfeiler, Fan von (0,0)
    la = [(L, 0.0), (L, ASPRING), (L, ARCTOP), (L, TH), (0.0, TH)]
    prev = (0.0, 0.0)
    ring = [(0.0, 0.0)] + la
    for i in range(1, len(ring) - 1):
        t.append(((0.0, 0.0), ring[i], ring[i + 1]))

    # B: rechter Pfeiler, Fan von (TY,0)
    ring = [(TY, 0.0), (TY, TH), (Rr, TH), (Rr, ARCTOP), (Rr, ASPRING), (Rr, 0.0)]
    for i in range(1, len(ring) - 1):
        t.append(((TY, 0.0), ring[i], ring[i + 1]))

    # C: Sturz ueber dem Bogen, Fan von (L,TH)
    ring = [(L, TH), (L, ARCTOP), (CY, ARCTOP), (Rr, ARCTOP), (Rr, TH)]
    for i in range(1, len(ring) - 1):
        t.append(((L, TH), ring[i], ring[i + 1]))

    # D: linker Bogenzwickel (Fan von Ecke (L,ARCTOP)), Bogen 180deg->90deg
    corner = (L, ARCTOP)
    pts = []
    for s in range(ARC_SEG + 1):
        ang = math.radians(180 - 90 * s / ARC_SEG)
        pts.append((CY + R * math.cos(ang), ASPRING + R * math.sin(ang)))
    for i in range(len(pts) - 1):
        t.append((corner, pts[i], pts[i + 1]))

    # E: rechter Bogenzwickel (Fan von Ecke (Rr,ARCTOP)), Bogen 90deg->0deg
    corner = (Rr, ARCTOP)
    pts = []
    for s in range(ARC_SEG + 1):
        ang = math.radians(90 - 90 * s / ARC_SEG)
        pts.append((CY + R * math.cos(ang), ASPRING + R * math.sin(ang)))
    for i in range(len(pts) - 1):
        t.append((corner, pts[i], pts[i + 1]))

    return t


def extrude(profile, x0, x1):
    """Extrudiere 2D-(y,z)-Profil entlang X zu wasserdichtem Volumen."""
    tris = []
    # Deckel vorne (-X) und hinten (+X)
    for (a, b, c) in profile:
        pa0, pb0, pc0 = (x0, a[0], a[1]), (x0, b[0], b[1]), (x0, c[0], c[1])
        pa1, pb1, pc1 = (x1, a[0], a[1]), (x1, b[0], b[1]), (x1, c[0], c[1])
        tris.append((pa0, pc0, pb0))   # vorne, Normale -X
        tris.append((pa1, pb1, pc1))   # hinten, Normale +X

    # Randkanten finden (gerichtet, Reverse fehlt => Rand)
    from collections import defaultdict
    cnt = defaultdict(int)
    for (a, b, c) in profile:
        for u, w in ((a, b), (b, c), (c, a)):
            cnt[(u, w)] += 1
    walls = [(u, w) for (u, w) in cnt if cnt.get((w, u), 0) == 0]

    for (u, w) in walls:
        u0, w0 = (x0, u[0], u[1]), (x0, w[0], w[1])
        u1, w1 = (x1, u[0], u[1]), (x1, w[0], w[1])
        tris.append((u0, w0, w1))
        tris.append((u0, w1, u1))
    return tris


def pyramid(x0, x1, y0, y1, z0, h):
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    apex = (cx, cy, z0 + h)
    b = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]
    tris = [(b[0], b[2], b[1]), (b[0], b[3], b[2])]        # Boden (-Z)
    for i in range(4):
        tris.append((b[i], b[(i + 1) % 4], apex))          # Seitenflaechen
    return tris


def manifold_ok(tris):
    """Jede ungerichtete Kante muss genau 2x vorkommen."""
    from collections import defaultdict
    e = defaultdict(int)
    for (a, b, c) in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            e[frozenset((u, w))] += 1
    bad = sum(1 for v in e.values() if v != 2)
    return bad, len(e)


def write_stl(path, tris, name="model"):
    with open(path, "wb") as f:
        f.write(b" " * 80)
        f.write(struct.pack("<I", len(tris)))
        for (a, b, c) in tris:
            n = norm(a, b, c)
            f.write(struct.pack("<3f", *n))
            for p in (a, b, c):
                f.write(struct.pack("<3f", *p))
            f.write(struct.pack("<H", 0))


# ---------------------------------------------------------------- Bauen
prof = tower_profile()
turm = extrude(prof, 0.0, TX)
gesims = box(-OVER, TX + OVER, -OVER, TY + OVER, CZ0, CZ1)   # ueber Turm zentriert
dach = pyramid(-OVER, TX + OVER, -OVER, TY + OVER, ROOF_BASE_Z, ROOF_H)

teil_turm = turm + gesims
teil_dach = dach
komplett = turm + gesims + dach

import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")
os.makedirs(OUT, exist_ok=True)

for fname, tris, label in (
    ("freiburger_stadttor.stl", komplett, "Komplett"),
    ("stadttor_turm.stl", teil_turm, "Turm+Gesims"),
    ("stadttor_dach.stl", teil_dach, "Dach"),
):
    bad, ne = manifold_ok(tris)
    write_stl(os.path.join(OUT, fname), tris)
    status = "OK wasserdicht" if bad == 0 else f"WARN {bad} offene Kanten"
    print(f"{label:14s} {len(tris):4d} Dreiecke  {status}  -> {fname}")

print(f"\nMasse: {TX:.0f} x {TY:.0f} mm Grundflaeche, "
      f"Hoehe {ROOF_BASE_Z + ROOF_H:.0f} mm (Turm {TH:.0f} + Dach {ROOF_H:.0f}).")
