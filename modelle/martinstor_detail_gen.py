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
                   "martinstor_detail.stl" if SCALE == 500 else f"martinstor_detail_1-{SCALE:.0f}.stl")
SEG = 48

def rel(m):  # Relieftiefe in m, mind. MINMM im Druck
    return max(m, MINMM / K)

# ---- Masse (m) ----
D, W = 12.7, 13.4            # Schaft: D entlang Durchfahrt (x), W Fassadenbreite (y)
EAVE = 33.0                  # Traufe
ROOF_TOP = 47.0              # Dachkoerper bis Laterne
TOP = 53.0                   # Spitze (OSM height)
TW, T0, T1, TTOP = 3.4, 28.0, 36.0, 43.5   # Tuermchen: Breite, Unterkante, Traufe, Spitze

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

# ============ Schaft ============
adds.append(box(-D / 2, D / 2, -W / 2, W / 2, 0, EAVE))
adds.append(box(-D / 2 - rel(0.15), D / 2 + rel(0.15), -W / 2 - rel(0.15), W / 2 + rel(0.15), 0, 0.9))  # Sockel

# Sandstein-Sockelzone (Torseiten) mit Lagerfugen
for f in ("+x", "-x"):
    adds.append(fbox(f, -W / 2 + 1.3, W / 2 - 1.3, 0.9, 7.6, -0.05, rel(0.07)))
    for i in range(1, 12):
        z = 0.9 + i * 0.6
        cuts.append(fbox(f, -W / 2 + 1.3, W / 2 - 1.3, z - 0.035, z + 0.035, rel(0.07) - rel(0.05), 1.0))

# Gurtgesims ueber dem Tor + Konsolfries unter dem Obergeschoss + Traufgesims
for z0, z1, p in ((7.6, 8.0, 0.25), (27.4, 27.9, 0.3), (32.4, 33.0, 0.45)):
    adds.append(box(-D / 2 - rel(p), D / 2 + rel(p), -W / 2 - rel(p), W / 2 + rel(p), z0, z1))
for f, L in (("+x", W), ("-x", W), ("+y", D), ("-y", D)):
    n = int((L - 3.0) / 0.9)
    for i in range(n):
        u = -L / 2 + 1.5 + (i + 0.5) * (L - 3.0) / n
        adds.append(fbox(f, u - 0.18, u + 0.18, 26.8, 27.4, -0.05, rel(0.22)))   # Konsolen
        adds.append(fbox(f, u - 0.15, u + 0.15, 31.9, 32.4, -0.05, rel(0.3)))    # Traufkonsolen

quoins((0, 0), D / 2, W / 2, 0.9, 27.3)

# Tordurchfahrt (x-Richtung) mit Keilstein-Bogen
AW, SPR = 6.0, 4.2
cuts.append(box(-D, D, -AW / 2, AW / 2, -1, SPR))
cuts.append(M.cylinder(2 * D, AW / 2, circular_segments=96).rotate((0, 90, 0)).translate((-D, 0, SPR)))
for f in ("+x", "-x"):
    adds.append(fcyl(f, 0, SPR, AW / 2 + 0.95, -0.05, rel(0.16), seg=96))         # Bogen-Ring
    adds.append(fbox(f, -AW / 2 - 0.95, AW / 2 + 0.95, 0.9, SPR, -0.05, rel(0.16)))  # Gewaende
    s = 1 if f == "+x" else -1
    for i in range(1, 15):  # Keilstein-Fugen radial (Drehung um x-Achse)
        ang = i * 180 / 15
        r = AW / 2 + 0.5
        y, z = -s * math.cos(math.radians(ang)) * r, SPR + math.sin(math.radians(ang)) * r
        g = fbox(f, -0.035, 0.035, -0.55, 0.55, rel(0.16) - rel(0.08), 1.0)
        cuts.append(g.rotate((s * (90 - ang), 0, 0)).translate((0, y, z)))
    # Schlussstein
    adds.append(fbox(f, -0.45, 0.45, SPR + AW / 2 - 0.1, SPR + AW / 2 + 1.15, -0.05, rel(0.24)))
    for j in (-1, 1):  # Kaempfersteine
        adds.append(fbox(f, j * (AW / 2 + 0.5) - 0.6, j * (AW / 2 + 0.5) + 0.6, SPR - 0.3, SPR, -0.05, rel(0.24)))

# Inschrift-Tafel (+x) und Doppeladler (-x) ueber dem Gurtgesims
adds.append(fbox("+x", -2.4, 2.4, 8.7, 10.5, -0.05, rel(0.14)))
cuts.append(fbox("+x", -2.1, 2.1, 9.0, 10.2, rel(0.14) - rel(0.05), 1.0))
for i in range(5):
    z = 9.15 + i * 0.22
    adds.append(fbox("+x", -1.8 + (0.3 if i == 4 else 0), 1.8 - (0.3 if i == 4 else 0), z, z + 0.09, 0, rel(0.12)))
adds.append(fbox("-x", -0.9, 0.9, 8.9, 10.7, -0.05, rel(0.1)))
eagle = [M.sphere(0.32, 24).scale((1, 0.8, 1.3)).translate((0, 0, 9.75)),
         M.sphere(0.2, 16).translate((0, -0.28, 10.35)), M.sphere(0.2, 16).translate((0, 0.28, 10.35))]
for s in (-1, 1):
    eagle.append(M.sphere(0.42, 24).scale((0.5, 1.0, 0.55)).translate((0, s * 0.5, 9.9)))
for e in eagle:
    adds.append(e.scale((rel(0.12) / 0.3, 1, 1)).translate((-D / 2 - rel(0.1), 0, 0)))

# Fenster Torseiten
for f in ("+x", "-x"):
    for u in (-2.3, 2.3):
        window(f, u, 12.0, 0.8, 1.1)
        window(f, u, 15.6, 0.8, 1.1)
    clock(f, 20.2)
    for u in (-3.0, 0.0, 3.0):
        window(f, u, 23.6, 0.85, 1.25)
    for u in (-4.3, -1.45, 1.45, 4.3):
        window(f, u, 28.8, 1.15, 2.2)
# Fenster Seiten
for f in ("+y", "-y"):
    for z in (11.0, 15.2, 19.4, 23.6):
        window(f, 0.0, z, 0.8, 1.15)
    for u in (-3.6, 0.0, 3.6):
        window(f, u, 28.8, 1.15, 2.2)

# ============ Dach ============
RD, RW = D + 1.2, W + 1.2
NC = 16  # Schindel-Lagen: gestufte Stuempfe
for i in range(NC):
    z0 = EAVE + i * (ROOF_TOP - EAVE) / NC
    z1 = EAVE + (i + 1) * (ROOF_TOP - EAVE) / NC
    t0, t1 = i / NC, (i + 1) / NC
    sx0, sy0 = RD + (1.6 - RD) * t0, RW + (2.3 - RW) * t0      # leichter First (Walm)
    sx1, sy1 = RD + (1.6 - RD) * t1, RW + (2.3 - RW) * t1
    lip = rel(0.12)
    adds.append(frustum(0, 0, z0, sx0 + 2 * lip, sy0 + 2 * lip, z1 + 0.05, sx1, sy1))
adds.append(box(-0.8, 0.8, -1.15, 1.15, ROOF_TOP - 0.1, ROOF_TOP + 0.4))                   # First-Abschluss
# Laterne mit Oeffnungen
adds.append(box(-0.75, 0.75, -0.75, 0.75, ROOF_TOP + 0.4, ROOF_TOP + 2.4))
for f in ("+x", "-x", "+y", "-y"):
    cuts.append(fbox(f, -0.3, 0.3, ROOF_TOP + 0.9, ROOF_TOP + 2.0, -0.3, 0.5, h=(0.75, 0.75)))
adds.append(frustum(0, 0, ROOF_TOP + 2.4, 1.9, 1.9, ROOF_TOP + 2.6, 1.9, 1.9))
adds.append(frustum(0, 0, ROOF_TOP + 2.6, 1.9, 1.9, TOP - 0.5, 0.08, 0.08))
adds.append(M.sphere(0.32, 24).translate((0, 0, TOP - 0.55)))
adds.append(M.cylinder(1.3, 0.07, 0.02, 12).translate((0, 0, TOP - 0.3)))

# Gauben (eine pro Dachseite)
def dormer(face):
    zb, w, h = EAVE + 3.2, 1.7, 1.7
    t = (zb - EAVE) / (ROOF_TOP - EAVE)
    half = ((RD + (1.6 - RD) * t) if face in ("+x", "-x") else (RW + (2.3 - RW) * t)) / 2
    hb = (half, half)
    body = fbox(face, -w / 2, w / 2, zb, zb + h, -2.5, 0.6, h=hb)
    pts = []
    for n in (-2.5, 0.75):
        for u in (-w / 2 - 0.2, w / 2 + 0.2):
            pts.append((n, u, zb + h))
        pts.append((n, 0.0, zb + h + 1.0))
    ridge = M.hull_points(pts)
    if face == "+x": ridge = ridge.translate((half, 0, 0))
    elif face == "-x": ridge = ridge.rotate((0, 0, 180)).translate((-half, 0, 0))
    elif face == "+y": ridge = ridge.rotate((0, 0, 90)).translate((0, half, 0))
    else: ridge = ridge.rotate((0, 0, -90)).translate((0, -half, 0))
    adds.append(body); adds.append(ridge)
    cuts.append(fbox(face, -0.45, 0.45, zb + 0.3, zb + 1.35, 0.3, 1.0, h=hb))
for f in ("+x", "-x", "+y", "-y"):
    dormer(f)

# ============ Ecktuermchen ============
for sx in (-1, 1):
    for sy in (-1, 1):
        c = (sx * (D / 2 - 0.2), sy * (W / 2 - 0.2))
        hh = (TW / 2, TW / 2)
        # Auskragung: umgekehrter Stumpf (Konsole) 25,4 -> 28 m, plus Ringe
        adds.append(frustum(c[0], c[1], 25.4, 0.9, 0.9, T0, TW, TW))
        for z in (26.2, 27.0):
            w_ = 0.9 + (TW - 0.9) * (z - 25.4) / (T0 - 25.4)
            adds.append(frustum(c[0], c[1], z - 0.12, w_ + 2 * rel(0.1), w_ + 2 * rel(0.1), z + 0.05, w_ + 2 * rel(0.1), w_ + 2 * rel(0.1)))
        adds.append(box(c[0] - TW / 2, c[0] + TW / 2, c[1] - TW / 2, c[1] + TW / 2, T0, T1))
        quoins(c, TW / 2, TW / 2, T0 + 0.1, T1 - 0.6, a=0.75, b=0.45, course=0.6)
        p = rel(0.2)
        adds.append(box(c[0] - TW / 2 - p, c[0] + TW / 2 + p, c[1] - TW / 2 - p, c[1] + TW / 2 + p, T1 - 0.45, T1))
        for f in ("+x", "-x", "+y", "-y"):
            window(f, 0.0, 31.2, 0.55, 1.1, c=c, hh=hh, deep=0.25)
        adds.append(frustum(c[0], c[1], T1, TW + 0.5, TW + 0.5, TTOP - 0.6, 0.1, 0.1))
        adds.append(M.sphere(0.22, 20).translate((c[0], c[1], TTOP - 0.6)))
        adds.append(M.cylinder(0.9, 0.05, 0.015, 10).translate((c[0], c[1], TTOP - 0.45)))

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
