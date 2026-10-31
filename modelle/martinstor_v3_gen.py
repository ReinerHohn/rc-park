#!/usr/bin/env python3
"""
martinstor_detail_gen.py — Martinstor (Freiburg) als Detail-Modell per CSG (manifold3d):
Masse aus OSM (building:part: Schaft 13,4 x 12,7 m, Traufe 33 m, Dach bis 53 m, 4 Eck-
tuermchen 28-43,5 m), Fassade nach Fotos (Wikimedia Commons) nachmodelliert:

  - Tordurchfahrt mit Rundbogen + Sandstein-Keilsteinen (Fugen geschnitten)
  - rote Sandstein-Eckquader (Laeufer/Binder abwechselnd, mit Fugen) an Schaft + Tuermchen
  - Sandstein-Sockelzone mit Lagerfugen, Gurtgesims, Konsolfries, Traufgesims
  - Fenster mit Gewaende + Sohlbank, Uhr mit Zifferblatt/Stundenmarken/Zeigern
  - Inschrift-Tafel (Torseite) + Doppeladler-Relief (Rueckseite)
  - Walmdach mit Schindel-Lagen, 4 Gauben, Laterne, Spitze mit Knauf
  - Ecktuermchen auf Auskragung (Konsole), Fenster, Pyramidendach, Knauf + Spitze

Reliefs werden auf MINMM (Standard 0,15 mm = Resin) hochgezogen, damit sie im Massstab
sichtbar bleiben.  Daten: (c) OpenStreetMap-Mitwirkende (ODbL) + eigene Nachmodellierung.

  ~/.venvs/rcpark/bin/python martinstor_detail_gen.py              # 1:500  (~107 mm)
  SCALE=250 MINMM=0.3 ~/.venvs/rcpark/bin/python martinstor_detail_gen.py   # 1:250 FDM
"""
import math, os
import numpy as np
from manifold3d import Manifold as M, CrossSection as CS, OpType

SCALE = float(os.environ.get("SCALE", "500"))
MINMM = float(os.environ.get("MINMM", "0.15"))  # kleinste Relief-Tiefe im Druck (mm)
K = 1000.0 / SCALE                               # m -> mm
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl",
                   f"martinstor_v3_1-{SCALE:.0f}.stl")
SEG = 48

def rel(m):  # Relieftiefe in m, mind. MINMM im Druck
    return max(m, MINMM / K)

# ---- Masse (m) ---- (Herleitung: LERNJOURNAL_MARTINSTOR.md, Eintrag 1+2)
H_TOTAL = 45.3                # LOD2 45,3 m = Scan-Verhaeltnis x OSM-Fussbreite
DB, WB, ZB = 11.6, 13.4, 12.5 # Steinsockel mit Tor: Tiefe (x, Durchfahrt), Breite (y), Hoehe
D, W = 9.6, 10.0              # Schaft (verputzt) AM KOPF (bei ZZ); nach unten verjuengt er sich zum Sockel
ZZ = 32.3                     # Zinnen-Unterkante = Oberkante Schaft
TOP = H_TOTAL
adds, cuts = [], []

def box(x0, x1, y0, y1, z0, z1):
    return M.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))

def fbox(face, u0, u1, z0, z1, n0, n1, c=(0.0, 0.0), h=(D / 2, W / 2)):
    """Box an einer Fassade: u = waagrecht entlang Fassade, n = Abstand nach aussen."""
    cx, cy = c; hx, hy = h
    if face == "+x": return box(cx + hx + n0, cx + hx + n1, cy + u0, cy + u1, z0, z1)
    if face == "-x": return box(cx - hx - n1, cx - hx - n0, cy - u1, cy - u0, z0, z1)
    if face == "+y": return box(cx - u1, cx - u0, cy + hy + n0, cy + hy + n1, z0, z1)
    return box(cx + u0, cx + u1, cy - hy - n1, cy - hy - n0, z0, z1)

def fcyl(face, u, z, r, n0, n1, c=(0.0, 0.0), h=(D / 2, W / 2), seg=SEG):
    """Zylinder mit Achse senkrecht zur Fassade."""
    cx, cy = c; hx, hy = h
    cyl = M.cylinder(n1 - n0, r, circular_segments=seg)
    if face in ("+x", "-x"):
        s = 1 if face == "+x" else -1
        cyl = cyl.rotate((0, 90, 0))  # Achse -> +x, Bereich x in [0, n1-n0]
        x0 = cx + hx + n0 if s > 0 else cx - hx - n1
        return cyl.translate((x0, cy + s * u, z))
    s = 1 if face == "+y" else -1
    cyl = cyl.rotate((-90, 0, 0))     # Achse -> +y
    y0 = cy + hy + n0 if s > 0 else cy - hy - n1
    return cyl.translate((cx - s * u, y0, z))

def frustum(x0, y0, z0, sx0, sy0, z1, sx1, sy1):
    """Pyramidenstumpf/Walm: Rechteck (sx0,sy0) bei z0 -> (sx1,sy1) bei z1, zentriert."""
    pts = []
    for z, sx, sy in ((z0, sx0, sy0), (z1, sx1, sy1)):
        for a in (-1, 1):
            for b in (-1, 1):
                pts.append((x0 + a * sx / 2, y0 + b * sy / 2, z))
    return M.hull_points(pts)

def window(face, u, z, w, h, c=(0.0, 0.0), hh=(D / 2, W / 2), deep=0.35):
    fr, sill = rel(0.08), rel(0.14)
    adds.append(fbox(face, u - w / 2 - 0.25, u + w / 2 + 0.25, z - 0.25, z + h + 0.25, -0.05, fr, c, hh))  # Gewaende
    adds.append(fbox(face, u - w / 2 - 0.4, u + w / 2 + 0.4, z - 0.42, z - 0.22, -0.05, sill, c, hh))      # Sohlbank
    adds.append(fbox(face, u - w / 2 - 0.35, u + w / 2 + 0.35, z + h + 0.25, z + h + 0.4, -0.05, sill, c, hh))  # Sturzgesims
    cuts.append(fbox(face, u - w / 2, u + w / 2, z, z + h, -deep, 0.5, c, hh))
    cuts.append(fbox(face, u - 0.05, u + 0.05, z, z + h, -deep - 0.1, 0.5, c, hh) if w > 0.8 else M())  # Fensterkreuz-Spalt -> Mittelpfosten
    if w > 0.8:  # Mittelpfosten + Kaempfer bleiben stehen
        adds.append(fbox(face, u - 0.07, u + 0.07, z, z + h, -deep, -0.02, c, hh))
        adds.append(fbox(face, u - w / 2, u + w / 2, z + h * 0.62, z + h * 0.62 + 0.12, -deep, -0.02, c, hh))

def quoins(c, hx, hy, z0, z1, a=1.3, b=0.75, course=0.72, joint=0.07, pr=None):
    """Eckquader an allen 4 Kanten eines Rechteck-Koerpers (Mitte c, halbe Masse hx, hy)."""
    pr = pr or rel(0.12)
    cx, cy = c
    n = int((z1 - z0) / course)
    for sx in (-1, 1):
        for sy in (-1, 1):
            X, Y = cx + sx * hx, cy + sy * hy
            for i in range(n):
                za, zb = z0 + i * course, z0 + (i + 1) * course - joint
                lx, ly = (a, b) if i % 2 == 0 else (b, a)
                xa, xb = sorted((X - sx * lx, X + sx * pr))
                ya, yb = sorted((Y - sy * ly, Y + sy * pr))
                adds.append(box(xa, xb, ya, yb, za, zb))

def clock(face, z, r=1.35):
    pr = rel(0.1)
    adds.append(fbox(face, -r - 0.65, r + 0.65, z - r - 0.65, z + r + 0.65, -0.05, pr))   # Sandstein-Rahmen
    cuts.append(fcyl(face, 0, z, r + 0.12, -0.15, 0.6))                                   # Nische
    adds.append(fcyl(face, 0, z, r, -0.2, -0.15 + rel(0.06)))                             # Zifferblatt
    adds.append(fcyl(face, 0, z, 0.18, -0.2, -0.15 + rel(0.16)))                          # Nabe
    for i in range(12):  # Stundenmarken
        ang = math.radians(i * 30)
        u, zz = math.sin(ang) * r * 0.82, z + math.cos(ang) * r * 0.82
        s = 0.16 if i % 3 == 0 else 0.1
        adds.append(fbox(face, u - s, u + s, zz - s, zz + s, -0.2, -0.15 + rel(0.12)))
    for ang, ln, wd in ((math.radians(300), 0.75, 0.09), (math.radians(60), 1.1, 0.06)):  # Zeiger 10:10
        steps = 6
        for k in range(steps):
            t = (k + 0.5) / steps * ln
            u, zz = math.sin(ang) * t, z + math.cos(ang) * t
            adds.append(fbox(face, u - wd, u + wd, zz - wd, zz + wd, -0.2, -0.15 + rel(0.14)))

# ===================== v3: Proportionen und Aufbau aus den Fotos =====================
HB = (DB / 2, WB / 2)          # Halbmasse Sockel (fuer Fassadenfunktionen)
HS = (D / 2, W / 2)            # Halbmasse Schaft am Kopf
GEL = {}                       # Gurtgesims-Hoehen

def prism(face, pts, n0, n1, h):
    """Prisma (Dreieck/Polygon in u,z) an einer Fassade, Dicke n0..n1 nach aussen."""
    hx, hy = h
    P = [(n, u, z) for n in (n0, n1) for (u, z) in pts]
    m = M.hull_points(P)
    if face == "+x": return m.translate((hx, 0, 0))
    if face == "-x": return m.rotate((0, 0, 180)).translate((-hx, 0, 0))
    if face == "+y": return m.rotate((0, 0, 90)).translate((0, hy, 0))
    return m.rotate((0, 0, -90)).translate((0, -hy, 0))

import random
RNG = random.Random(1900)       # fester Startwert: Ergebnis reproduzierbar

# ---------- Rumpf: unten senkrechter Steinsockel, darueber nach oben verjuengter Schaft (Foto: durchgehender Anlauf) ----------
def hxy(z):
    """Halbmasse des Rumpfs auf Hoehe z (senkrecht bis ZB, dann linear zum Schaft D x W bei ZZ)."""
    t = min(max((z - ZB) / (ZZ - ZB), 0.0), 1.0)
    return (DB / 2 + (D / 2 - DB / 2) * t, WB / 2 + (W / 2 - WB / 2) * t)

def clock3(face, z, r, hh):
    pr = rel(0.1)
    adds.append(fbox(face, -r - 0.9, r + 0.9, z - r - 0.9, z + r + 0.9, -0.05, pr, h=hh))   # Sandsteinrahmen
    cuts.append(fcyl(face, 0, z, r + 0.12, -0.15, 0.6, h=hh))
    adds.append(fcyl(face, 0, z, r, -0.2, -0.15 + rel(0.06), h=hh))
    adds.append(fcyl(face, 0, z, 0.2, -0.2, -0.15 + rel(0.16), h=hh))
    for i in range(12):
        ang = math.radians(i * 30)
        u, zz = math.sin(ang) * r * 0.82, z + math.cos(ang) * r * 0.82
        sz = 0.17 if i % 3 == 0 else 0.1
        adds.append(fbox(face, u - sz, u + sz, zz - sz, zz + sz, -0.2, -0.15 + rel(0.12), h=hh))
    for ang, ln, wd in ((math.radians(300), 0.8, 0.09), (math.radians(60), 1.2, 0.06)):
        for k in range(6):
            t = (k + 0.5) / 6 * ln
            u, zz = math.sin(ang) * t, z + math.cos(ang) * t
            adds.append(fbox(face, u - wd, u + wd, zz - wd, zz + wd, -0.2, -0.15 + rel(0.14), h=hh))

def quoins3(z0, z1, a=1.35, b=0.8, course=0.74, joint=0.07):
    """Gezahnte Eckquader entlang des verjuengten Schafts (je Lage mit den Halbmassen auf ihrer Hoehe)."""
    pr = rel(0.12)
    n = int((z1 - z0) / course)
    for i in range(n):
        za, zb = z0 + i * course, z0 + (i + 1) * course - joint
        hx, hy = hxy((za + zb) / 2)
        for sx in (-1, 1):
            for sy in (-1, 1):
                X, Y = sx * hx, sy * hy
                lg, kz = RNG.uniform(0.95, 1.75), RNG.uniform(0.55, 0.95)
                lx, ly = (lg, kz) if (i + (sx > 0) + (sy > 0)) % 2 == 0 else (kz, lg)
                pp = rel(RNG.uniform(0.08, 0.2))
                xa, xb = sorted((X - sx * lx, X + sx * pp)); ya, yb = sorted((Y - sy * ly, Y + sy * pp))
                adds.append(box(xa, xb, ya, yb, za, zb))

adds.append(box(-DB / 2 - rel(0.15), DB / 2 + rel(0.15), -WB / 2 - rel(0.15), WB / 2 + rel(0.15), 0, 0.9))   # Plinthe
adds.append(box(-DB / 2, DB / 2, -WB / 2, WB / 2, 0.8, ZB))                                                      # Steinsockel
adds.append(frustum(0, 0, ZB - 0.01, DB, WB, ZZ, D, W))                                                          # verjuengter Schaft
HB = (DB / 2, WB / 2)

def bruchstein(f, L, hh, frei):
    """Unregelmaessige Bruchstein-Quader auf einer Sockelseite (Foto: grobe Findlinge mit tiefen Fugen).
    frei(u0,u1,z0,z1) -> True, wenn dort schon etwas anderes sitzt (Tor, Tafel, Fenster)."""
    z = 0.95
    while z < ZB - 0.3:
        hgt = RNG.uniform(0.48, 0.78)
        z1 = min(z + hgt, ZB - 0.02)
        u = -L / 2 + 0.35
        while u < L / 2 - 0.35:
            w = RNG.uniform(0.7, 1.7)
            u1 = min(u + w, L / 2 - 0.35)
            if u1 - u > 0.3 and not frei(u, u1, z, z1):
                pr = rel(RNG.uniform(0.05, 0.22))
                adds.append(fbox(f, u + 0.03, u1 - 0.03, z + 0.03, z1 - 0.03, -0.05, pr, h=hh))
            u = u1
        z = z1

def frei_x(u0, u1, z0, z1):
    return (u1 > -4.1 and u0 < 4.1 and z0 < 9.4) or (u1 > -2.6 and u0 < 2.6 and z0 < 10.7)
def frei_y(u0, u1, z0, z1):
    return (u1 > -0.95 and u0 < 0.95 and ((5.9 < z1 and z0 < 8.0) or (9.9 < z1 and z0 < 12.0)))
for f in ("+x", "-x"): bruchstein(f, WB, HB, frei_x)
for f in ("+y", "-y"): bruchstein(f, DB, HB, frei_y)
hz = hxy(ZB + 0.2)
adds.append(box(-hz[0] - 0.25, hz[0] + 0.25, -hz[1] - 0.25, hz[1] + 0.25, ZB, ZB + 0.45))                      # Gurtgesims Sockel/Schaft

# ---------- Tordurchfahrt mit Keilsteinbogen (x-Richtung) ----------
AW, SPR = 6.0, 4.2
cuts.append(box(-DB, DB, -AW / 2, AW / 2, -1, SPR))
cuts.append(M.cylinder(2 * DB, AW / 2, circular_segments=96).rotate((0, 90, 0)).translate((-DB, 0, SPR)))
for f in ("+x", "-x"):
    s_ = 1 if f == "+x" else -1
    adds.append(fcyl(f, 0, SPR, AW / 2 + 0.95, -0.05, rel(0.16), h=HB, seg=96))
    adds.append(fbox(f, -AW / 2 - 0.95, AW / 2 + 0.95, 0.9, SPR, -0.05, rel(0.16), h=HB))
    for i in range(1, 15):
        ang = i * 180 / 15
        r = AW / 2 + 0.5
        y, z = -s_ * math.cos(math.radians(ang)) * r, SPR + math.sin(math.radians(ang)) * r
        g = fbox(f, -0.035, 0.035, -0.55, 0.55, rel(0.16) - rel(0.08), 1.0, h=HB)
        cuts.append(g.rotate((s_ * (90 - ang), 0, 0)).translate((0, y, z)))
    adds.append(fbox(f, -0.45, 0.45, SPR + AW / 2 - 0.1, SPR + AW / 2 + 1.15, -0.05, rel(0.24), h=HB))
    for j in (-1, 1):
        adds.append(fbox(f, j * (AW / 2 + 0.5) - 0.6, j * (AW / 2 + 0.5) + 0.6, SPR - 0.3, SPR, -0.05, rel(0.24), h=HB))
adds.append(fbox("+x", -2.4, 2.4, 8.4, 10.2, -0.05, rel(0.14), h=HB))                    # Inschrifttafel
cuts.append(fbox("+x", -2.1, 2.1, 8.7, 9.9, rel(0.14) - rel(0.05), 1.0, h=HB))
for i in range(5):
    z = 8.85 + i * 0.22
    adds.append(fbox("+x", -1.8 + (0.3 if i == 4 else 0), 1.8 - (0.3 if i == 4 else 0), z, z + 0.09, 0, rel(0.12), h=HB))
adds.append(fbox("-x", -0.9, 0.9, 8.6, 10.4, -0.05, rel(0.1), h=HB))                      # Doppeladler (Relief)
for e in [M.sphere(0.32, 24).scale((1, 0.8, 1.3)).translate((0, 0, 9.45)),
          M.sphere(0.2, 16).translate((0, -0.28, 10.05)), M.sphere(0.2, 16).translate((0, 0.28, 10.05)),
          M.sphere(0.42, 24).scale((0.5, 1.0, 0.55)).translate((0, -0.5, 9.6)), M.sphere(0.42, 24).scale((0.5, 1.0, 0.55)).translate((0, 0.5, 9.6))]:
    adds.append(e.scale((rel(0.12) / 0.3, 1, 1)).translate((-DB / 2 - rel(0.1), 0, 0)))
for f in ("+y", "-y"):
    for z in (6.5, 10.5):
        window(f, 0.0, z, 0.5, 1.0, hh=HB)

# ---------- Schaft: Eckquader, Uhr, Schlitzfenster (alles auf der Hoehe der Verjuengung) ----------
SZ0 = ZB + 0.5
quoins3(SZ0, ZZ - 0.3)
UZ, UR = 27.0, 1.75
for f in ("+x", "-x"):
    hh = hxy(UZ)
    clock3(f, UZ, UR, hh)
    adds.append(prism(f, [(-UR - 0.98, UZ + UR + 0.88), (UR + 0.98, UZ + UR + 0.88), (0, UZ + UR + 2.0)], -0.05, rel(0.2), hh))
    for k in range(12):
        ang = math.radians(k * 30 + 15)
        u, zz = math.sin(ang) * (UR + 0.28), UZ + math.cos(ang) * (UR + 0.28)
        adds.append(fcyl(f, u, zz, 0.2, -0.2, -0.15 + rel(0.09), h=hh))
    for u in (-2.3, 0.0, 2.3):
        window(f, u, 23.2, 0.5, 0.9, hh=hxy(23.2))
    window(f, 0.0, 20.2, 0.4, 0.8, hh=hxy(20.2))
for f in ("+y", "-y"):
    for u in (-1.8, 1.8):
        window(f, u, 25.0, 0.5, 0.9, hh=hxy(25.0))
    window(f, 0.0, 21.0, 0.4, 0.8, hh=hxy(21.0))

# ---------- Zinnenkranz + Kragdach ----------
adds.append(box(-D / 2 - 0.35, D / 2 + 0.35, -W / 2 - 0.35, W / 2 + 0.35, ZZ - 0.45, ZZ))        # Kranzgesims
for f, L in (("+x", W), ("-x", W), ("+y", D), ("-y", D)):
    n = 5
    pitch = (L - 1.0) / n
    for i in range(n):
        u = -L / 2 + 0.5 + (i + 0.5) * pitch
        adds.append(fbox(f, u - 0.4, u + 0.4, ZZ, ZZ + 1.3, -0.5, 0.0, h=HS))                  # Zinne
        adds.append(fbox(f, u - 0.15, u + 0.15, ZZ + 1.3, ZZ + 1.7, 0.0, 0.5, h=HS))            # Holzkonsole
adds.append(box(-D / 2 + 0.2, D / 2 - 0.2, -W / 2 + 0.2, W / 2 - 0.2, ZZ, ZZ + 1.4))             # Kern hinter den Zinnen
adds.append(frustum(0, 0, ZZ + 1.4, D + 1.8, W + 1.8, ZZ + 2.9, D - 2.2, W - 2.2))               # Kupferschraege des Kragdachs
# ---------- abgesetzter Glockenstock mit Schallarkaden ----------
GX, GY, GZ0, GZ1 = D - 2.8, W - 2.8, ZZ + 2.9, ZZ + 5.4
adds.append(box(-GX / 2, GX / 2, -GY / 2, GY / 2, GZ0 - 0.1, GZ1))
quoins((0, 0), GX / 2, GY / 2, GZ0, GZ1 - 0.2, a=0.75, b=0.42, course=0.6)
for f in ("+x", "-x", "+y", "-y"):
    hh = (GX / 2, GY / 2)
    for u in (-0.85, 0.85):
        cuts.append(fbox(f, u - 0.42, u + 0.42, GZ0 + 0.55, GZ0 + 1.75, -0.7, 0.5, h=hh))
        cuts.append(fcyl(f, u, GZ0 + 1.75, 0.42, -0.7, 0.5, h=hh, seg=24))
    adds.append(fbox(f, -1.85, 1.85, GZ0 + 0.4, GZ0 + 2.5, -0.05, rel(0.1), h=hh))
    for u in (-0.85, 0.85):    # Schallarkaden wieder frei schneiden
        cuts.append(fbox(f, u - 0.42, u + 0.42, GZ0 + 0.55, GZ0 + 1.75, -0.7, 0.5, h=hh))
        cuts.append(fcyl(f, u, GZ0 + 1.75, 0.42, -0.7, 0.5, h=hh, seg=24))

# ---------- Kupferdach (glatt, oben abgeflacht) ----------
RZ0, RZ1 = GZ1, GZ1 + 3.6
adds.append(frustum(0, 0, RZ0, GX + 0.8, GY + 0.8, RZ1, 1.7, 2.1))
for sx in (-1, 1):
    for sy in (-1, 1):
        adds.append(M.sphere(0.24, 20).translate((sx * 0.85, sy * 1.05, RZ1 + 0.1)))            # Goldkugeln auf den Dachecken
# Stehfalze im Kupferdach (senkrechte Rillen, wie im Foto)
def falze(face, hb, ht, ub, ut):
    dz = RZ1 - RZ0
    th = math.degrees(math.atan2(hb - ht, dz))
    nseam = int(2 * ub / 0.62)
    for k in range(nseam):
        u = -ub + (k + 0.5) * 2 * ub / nseam
        t1 = min(1.0, (ub - abs(u) - 0.2) / (ub - ut))
        if t1 <= 0.15: continue
        t0 = 0.04
        L = (t1 - t0) * dz / math.cos(math.radians(th))
        zc = RZ0 + (t0 + t1) / 2 * dz
        xc = hb - (hb - ht) * (t0 + t1) / 2
        cut = M.cube((0.16, 0.06, L)).translate((-0.08, -0.03, -L / 2)).rotate((0, -th, 0)).translate((xc, u, zc))
        if face == "-x": cut = cut.rotate((0, 0, 180))
        elif face == "+y": cut = cut.rotate((0, 0, 90))
        elif face == "-y": cut = cut.rotate((0, 0, -90))
        cuts.append(cut)
_bx, _by = (GX + 0.8) / 2, (GY + 0.8) / 2
for f in ("+x", "-x"): falze(f, _bx, 0.85, _by, 1.05)
for f in ("+y", "-y"): falze(f, _by, 1.05, _bx, 0.85)

# ---------- Dachreiter ----------
adds.append(M.cylinder(0.5, 0.55, 0.55, 8).translate((0, 0, RZ1)))
adds.append(M.cylinder(0.45, 0.75, 0.75, 8).translate((0, 0, RZ1 + 0.5)))
adds.append(M.cylinder(TOP - (RZ1 + 0.95) - 0.55, 0.38, 0.05, 8).translate((0, 0, RZ1 + 0.95)))
adds.append(M.sphere(0.2, 16).translate((0, 0, TOP - 0.5)))
adds.append(M.cylinder(0.55, 0.05, 0.02, 8).translate((0, 0, TOP - 0.55)))

# ---------- Ecktuermchen: Sandsteinturm + achteckiger Erker mit Fachwerk-Bruestung und Arkade ----------
TWs, T0, T1 = 2.9, 28.4, 35.0
OR = 1.35                                    # Erker-Radius
for sx in (-1, 1):
    for sy in (-1, 1):
        _h = hxy(T0 + 1.0)
        c = (sx * (_h[0] - 0.45), sy * (_h[1] - 0.45))
        hh = (TWs / 2, TWs / 2)
        adds.append(frustum(c[0], c[1], 26.2, 0.9, 0.9, T0, TWs, TWs))                        # Auskragung (Konsole)
        for z in (27.0, 27.8):
            w_ = 0.9 + (TWs - 0.9) * (z - 26.2) / (T0 - 26.2)
            adds.append(frustum(c[0], c[1], z - 0.12, w_ + 2 * rel(0.1), w_ + 2 * rel(0.1), z + 0.05, w_ + 2 * rel(0.1), w_ + 2 * rel(0.1)))
        adds.append(box(c[0] - TWs / 2, c[0] + TWs / 2, c[1] - TWs / 2, c[1] + TWs / 2, T0, T1))
        quoins(c, TWs / 2, TWs / 2, T0 + 0.1, T1 - 0.7, a=0.8, b=0.5, course=0.58)
        p = rel(0.22)
        adds.append(box(c[0] - TWs / 2 - p, c[0] + TWs / 2 + p, c[1] - TWs / 2 - p, c[1] + TWs / 2 + p, T1 - 0.5, T1))   # Kranz
        for f in ("+x", "-x", "+y", "-y"):
            window(f, 0.0, 31.0, 0.4, 0.9, c=c, hh=hh, deep=0.25)
        # Erker: Bruestung (achteckig) mit X-Fachwerk
        adds.append(M.cylinder(0.95, OR, OR, 8).rotate((0, 0, 22.5)).translate((c[0], c[1], T1)))
        for k in range(8):
            for sgn in (-1, 1):
                cut = M.cube((0.5, 0.085, 0.95)).translate((-0.25 + OR * math.cos(math.radians(22.5)) , -0.04, -0.47)).rotate((sgn * 38, 0, 0)).translate((0, 0, 0))
                # Schlitz entlang der Seitenflaeche k (Normale bei k*45 Grad)
                cut = cut.translate((0, 0, T1 + 0.48)).rotate((0, 0, k * 45)).translate((c[0], c[1], 0))
                cuts.append(cut)
        # offene Arkade: Kern + 8 schlanke Saeulen + Deckring
        adds.append(M.cylinder(1.45, 0.55, 0.55, 8).translate((c[0], c[1], T1 + 0.95)))
        for k in range(8):
            a = math.radians(k * 45 + 22.5)
            adds.append(M.cylinder(1.4, 0.11, 0.11, 8).translate((c[0] + (OR - 0.14) * math.cos(a), c[1] + (OR - 0.14) * math.sin(a), T1 + 0.95)))
        adds.append(M.cylinder(0.22, OR + 0.1, OR + 0.1, 8).rotate((0, 0, 22.5)).translate((c[0], c[1], T1 + 2.3)))
        # spitzes Kupferdach, Kugel, Spitze
        adds.append(M.cylinder(2.85, OR + 0.28, 0.06, 8).rotate((0, 0, 22.5)).translate((c[0], c[1], T1 + 2.52)))
        adds.append(M.sphere(0.22, 20).translate((c[0], c[1], T1 + 5.37)))
        adds.append(M.cylinder(0.6, 0.045, 0.015, 8).translate((c[0], c[1], T1 + 5.45)))
# ============ CSG ============
cuts = [c for c in cuts if not c.is_empty()]
body = M.batch_boolean(adds, OpType.Add)
model = M.batch_boolean([body] + cuts, OpType.Subtract).scale((K, K, K))

mesh = model.to_mesh()
V = np.asarray(mesh.vert_properties)[:, :3].astype(np.float32)
F = np.asarray(mesh.tri_verts)
tri = V[F]
nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
rec["n"], rec["v"] = nrm, tri
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "wb") as f:
    f.write(b"martinstor_detail (c) OSM ODbL + rc-park".ljust(80, b" "))
    f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
lo, hi = V.min(0), V.max(0)
print(f"{len(adds)} Teile, {len(cuts)} Schnitte -> {len(F):,} Dreiecke, Genus {model.genus()}, "
      f"Volumen {model.volume()/1000:.1f} cm3")
print(f"1:{SCALE:.0f}: {hi[0]-lo[0]:.1f} x {hi[1]-lo[1]:.1f} x {hi[2]-lo[2]:.1f} mm -> {OUT}")
