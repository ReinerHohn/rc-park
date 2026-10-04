#!/usr/bin/env python3
"""
fensterrosette_gen.py — generiert eine gotische Fensterrosette als flaches
Relief-Panel (zum flach Drucken + Aufkleben/Hinterleuchten).

Ausgabe:
  modelle/stl/rosette.stl   3D: dünne Platte + erhabenes Maßwerk (Speichen, Ringe, Foils)
  modelle/svg/rosette.svg   2D: dasselbe Muster als Vektor (ansehen/Papier/Laser)

Idee: durchscheinende Grundplatte (Glas) + erhabenes „Stein"-Maßwerk obendrauf.
Flach gedruckt → scharfes Detail in der XY-Ebene, in Minuten fertig. Hinterleuchtet
leuchtet das Glas, das Maßwerk bleibt dunkel. Alles aus einfachen Volumenkörpern
(Zylinder/Ringe/Balken), die im Slicer zu einem Teil verschmelzen.

Rein math/stdlib (+ struct). Masse in mm.
"""

import math
import struct
import os

# -------------------------------------------------------------- Parameter
R = 45.0            # Aussenradius der Rosette (=> 90 mm Durchmesser)
BASE_TH = 2.0       # Dicke der Grundplatte (Glas)
RELIEF = 1.6        # Hoehe des erhabenen Maszwerks
Z0 = 0.0
Z1 = BASE_TH                 # Oberkante Platte
Z2 = BASE_TH + RELIEF        # Oberkante Maszwerk
SEG = 64            # Segmente fuer grosse Kreise
SEGS = 20           # Segmente fuer kleine Kreise
BARS = 6            # Durchmesser-Balken (=> 12 Speichen)
BARW = 2.4          # Balkenbreite
FRAME = 4.0         # Breite des aeusseren Steinrahmens
INNER_R = R * 0.52  # Radius des inneren Rings
INNER_W = 2.4
FOIL_R = R * 0.78   # Radius, auf dem die Foils (Kreischen) sitzen
N_FOIL = 12
FOIL_OUT = 4.2
FOIL_IN = 2.6
HUB_R = 6.0         # zentrale Nabe


# -------------------------------------------------------------- Mesh-Helfer
def _ring(cx, cy, r, seg):
    return [(cx + r * math.cos(2 * math.pi * i / seg),
             cy + r * math.sin(2 * math.pi * i / seg)) for i in range(seg)]


def cylinder(z0, z1, r, seg, cx=0.0, cy=0.0):
    p = _ring(cx, cy, r, seg)
    t = []
    cb, ct = (cx, cy, z0), (cx, cy, z1)
    for i in range(seg):
        j = (i + 1) % seg
        bi, bj = (p[i][0], p[i][1], z0), (p[j][0], p[j][1], z0)
        ti, tj = (p[i][0], p[i][1], z1), (p[j][0], p[j][1], z1)
        t.append((cb, bj, bi))          # Boden -Z
        t.append((ct, ti, tj))          # Deckel +Z
        t.append((bi, bj, tj))          # Mantel
        t.append((bi, tj, ti))
    return t


def washer(z0, z1, ri, ro, seg, cx=0.0, cy=0.0):
    pi_ = _ring(cx, cy, ri, seg)
    po = _ring(cx, cy, ro, seg)
    t = []
    for i in range(seg):
        j = (i + 1) % seg
        ii0, ij0 = (pi_[i][0], pi_[i][1], z0), (pi_[j][0], pi_[j][1], z0)
        oi0, oj0 = (po[i][0], po[i][1], z0), (po[j][0], po[j][1], z0)
        ii1, ij1 = (pi_[i][0], pi_[i][1], z1), (pi_[j][0], pi_[j][1], z1)
        oi1, oj1 = (po[i][0], po[i][1], z1), (po[j][0], po[j][1], z1)
        t.append((oi1, ii1, ij1)); t.append((oi1, ij1, oj1))   # Deckel
        t.append((ii0, oi0, oj0)); t.append((ii0, oj0, ij0))   # Boden
        t.append((oi0, oi1, oj1)); t.append((oi0, oj1, oj0))   # Aussenwand
        t.append((ii0, ij1, ii1)); t.append((ii0, ij0, ij1))   # Innenwand
    return t


def hexa(v):
    q = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
    t = []
    for a, b, c, d in q:
        t.append((v[a], v[b], v[c]))
        t.append((v[a], v[c], v[d]))
    return t


def bar(length, width, z0, z1, theta):
    """Balken Laenge x Breite, um Mitte gedreht (theta rad)."""
    hx, hy = length / 2.0, width / 2.0
    loc = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
    ct, st = math.cos(theta), math.sin(theta)
    rot = [(x * ct - y * st, x * st + y * ct) for x, y in loc]
    v = [(rot[0][0], rot[0][1], z0), (rot[1][0], rot[1][1], z0),
         (rot[2][0], rot[2][1], z0), (rot[3][0], rot[3][1], z0),
         (rot[0][0], rot[0][1], z1), (rot[1][0], rot[1][1], z1),
         (rot[2][0], rot[2][1], z1), (rot[3][0], rot[3][1], z1)]
    return hexa(v)


def norm(a, b, c):
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return (nx / ln, ny / ln, nz / ln)


def write_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b" " * 80)
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            f.write(struct.pack("<3f", *norm(a, b, c)))
            for p in (a, b, c):
                f.write(struct.pack("<3f", *p))
            f.write(struct.pack("<H", 0))


# -------------------------------------------------------------- Rosette bauen
tris = []
# Grundplatte (Glas) — minimal groesser als der Rahmen, damit keine
# deckungsgleichen Randkanten entstehen (sauberer Manifold-Check)
tris += cylinder(Z0, Z1, R + 0.6, SEG)
# Maszwerk-Elemente laufen von Z0 bis Z2 => voll in die Platte eingebettet
# (echte Volumen-Ueberlappung => saubere Union, keine beruehrenden Kanten)
tris += washer(Z0, Z2, R - FRAME, R, SEG)                                   # Rahmen
tris += washer(Z0, Z2, INNER_R - INNER_W / 2, INNER_R + INNER_W / 2, SEG)   # innerer Ring
for k in range(BARS):                                                       # Speichen
    tris += bar(2 * (R - FRAME + 0.5), BARW, Z0, Z2, math.pi * k / BARS)
for i in range(N_FOIL):                                                     # Foils
    a = 2 * math.pi * i / N_FOIL
    cx, cy = FOIL_R * math.cos(a), FOIL_R * math.sin(a)
    tris += washer(Z0, Z2, FOIL_IN, FOIL_OUT, SEGS, cx, cy)
tris += cylinder(Z0, Z2, HUB_R, SEGS)                                       # Nabe


# -------------------------------------------------------------- Manifold-Check
def manifold_bad(tris):
    from collections import defaultdict
    e = defaultdict(int)
    for a, b, c in tris:
        for u, w in ((a, b), (b, c), (c, a)):
            e[frozenset((u, w))] += 1
    return sum(1 for v in e.values() if v != 2)


# -------------------------------------------------------------- SVG bauen
def svg():
    cx = cy = R
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{2*R}mm" height="{2*R}mm" '
         f'viewBox="0 0 {2*R} {2*R}">']
    s.append(f'<rect width="{2*R}" height="{2*R}" fill="#0b1020"/>')
    st = 'fill="none" stroke="#e8c37a" stroke-width="1.2"'
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{R-0.6}" {st}/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{R-FRAME}" {st}/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{INNER_R}" {st}/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="{HUB_R}" {st}/>')
    for k in range(BARS):
        a = math.pi * k / BARS
        x0, y0 = cx + (R - FRAME) * math.cos(a), cy + (R - FRAME) * math.sin(a)
        x1, y1 = cx - (R - FRAME) * math.cos(a), cy - (R - FRAME) * math.sin(a)
        s.append(f'<line x1="{x0:.2f}" y1="{y0:.2f}" x2="{x1:.2f}" y2="{y1:.2f}" {st}/>')
    for i in range(N_FOIL):
        a = 2 * math.pi * i / N_FOIL
        fx, fy = cx + FOIL_R * math.cos(a), cy + FOIL_R * math.sin(a)
        s.append(f'<circle cx="{fx:.2f}" cy="{fy:.2f}" r="{FOIL_OUT:.2f}" {st}/>')
    s.append('</svg>')
    return "\n".join(s)


# -------------------------------------------------------------- Schreiben
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
os.makedirs(os.path.join(HERE, "svg"), exist_ok=True)

bad = manifold_bad(tris)
write_stl(os.path.join(HERE, "stl", "rosette.stl"), tris)
with open(os.path.join(HERE, "svg", "rosette.svg"), "w") as f:
    f.write(svg())

print(f"Rosette: {len(tris)} Dreiecke  "
      f"{'OK wasserdicht' if bad == 0 else f'WARN {bad} offene Kanten'}")
print(f"Durchmesser {2*R:.0f} mm, Platte {BASE_TH} mm + Maszwerk {RELIEF} mm "
      f"= {Z2:.1f} mm dick.")
print("-> modelle/stl/rosette.stl  (3D)")
print("-> modelle/svg/rosette.svg  (2D)")
