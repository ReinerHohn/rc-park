#!/usr/bin/env python3
"""oberkirch_measured.py — parametrischer Generator fuer das Hotel Oberkirch
(Muensterplatz 22, Freiburg; Ost-Nachbar des Historischen Kaufhauses).

ERSTER-SCHUSS-TEST der Pipeline auf ein NEUES, schlichtes Altstadthaus:
  Masse amtlich aus LOD2 (oberkirch_mass.json), Fassadengliederung + Stueckzahlen
  gezaehlt/gemessen am Foto (oberkirch_params.json). KEIN Hardcoding von Zahlen -
  alles aus den JSONs. Reine Geometrie, Elementgruppen mit eigener Farbe,
  Export je Gruppe als STL + gemeinsames GLB (gleiche Methode wie kaufhaus_measured.py).

  python3 tools/oberkirch_measured.py
"""
import json, os
import numpy as np
import trimesh
from trimesh.creation import extrude_polygon, box as tbox, cylinder as tcyl, cone as tcone
from shapely.geometry import Polygon, box as sbox

OUT = "modelle/hotel_oberkirch"
MASS = json.load(open(f"{OUT}/oberkirch_mass.json"))
P = json.load(open(f"{OUT}/oberkirch_params.json"))

# ---- gemessene Masse (m) ----
W = float(MASS["W"])
D_TRUE = float(MASS["D"])                      # 16,4 = volle LOD2-Tiefe (tiefes Grundstueck)
# Nur der STRASSEN-Vordertrakt wird gezeigt; der tiefe, niedrigere Hintertrakt (LOD2 hatte
# 3 Teile) ist zwischen den Nachbarn verdeckt. Ein einziges Dach ueber 16,4 m waere "viel zu lang".
D = float(MASS.get("model_depth", 9.0))
EAVE = float(MASS["EAVE"])
RIDGE_LOD2 = float(MASS["RIDGE"])              # 21,0 = First des TIEFEN Gesamtdachs (Doku)
PITCH = np.radians(float(MASS.get("roof_pitch_deg", 54.0)))
RIDGE = EAVE + np.tan(PITCH) * (D / 2)         # First aus realistischer Neigung ueber Vordertrakt
EG_TOP = float(MASS["EG_TOP"])
WIN_W = float(MASS["win_w"]); WIN_H = float(MASS["win_h"]); SILL_OFF = float(MASS["win_sill_off"])
DORM_W = float(MASS["dormer_w"]); DORM_H = float(MASS["dormer_h"])

NAX = int(P["n_axes"])
XFR = list(P["win_x_frac"])
NFL = int(P["n_upper_floors"])
WIN_X = [f * W for f in XFR]            # Fenster-x in m (gemessen, 2+2 gruppiert)
FRONT_T = 0.5                            # Fassaden-Wanddicke (Y-Tiefe)

# Geschoss-Unterkanten der OG (gleichmaessig zwischen EG_TOP und EAVE)
FLOOR_H = (EAVE - EG_TOP) / NFL
FLOOR_Z0 = [EG_TOP + i * FLOOR_H for i in range(NFL)]     # Unterkante je OG

# ---- Farben (RGBA), aus Foto-Pixeln ----
COL = {
    "fassade":   [222, 209, 175, 255],   # cremefarbener Putz
    "eg_sockel": [78, 60, 44, 255],       # dunkles Restaurant-Holz
    "fenster":   [40, 46, 54, 255],       # dunkles Glas
    "rahmen":    [238, 236, 228, 255],    # weisse Fensterrahmen/Sprossen
    "laeden":    [138, 156, 138, 255],    # salbeigruene Lamellenlaeden
    "kasten":    [58, 44, 34, 255],        # Blumenkasten dunkel
    "blumen":    [184, 72, 82, 255],       # Geranien rot
    "laub":      [92, 118, 72, 255],       # Grün
    "dach":      [112, 104, 106, 255],     # grau-braune Ziegel
    "gaube":     [222, 209, 175, 255],     # Gaubenkoerper (Putz, wie Fassade)
    "gaube_dach":[96, 90, 92, 255],
    "luke":      [46, 42, 44, 255],        # Dachluken dunkel
    "giebel":    [214, 201, 168, 255],     # Giebel-Dreiecke
    "schild_arm":[40, 36, 34, 255],        # schmiedeeiserner Ausleger
    "schild":    [224, 214, 180, 255],     # Schildtafel creme
    "gold":      [196, 162, 84, 255],      # Goldrahmen/Schrift
    "laterne":   [48, 44, 42, 255],
    "wappen":    [176, 150, 90, 255],
    "band":      [96, 74, 52, 255],        # Schriftband EG
}


def _stand(m, y0=0.0):
    """extrude_polygon((x,hoehe),dicke) AUFRICHTEN: Polygon-Hoehe -> Z, Dicke -> Y (Tiefe)."""
    V = m.vertices.copy()
    m.vertices = np.c_[V[:, 0], y0 + V[:, 2], V[:, 1]]
    return m


def _valid(poly):
    if poly.is_empty:
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly if (not poly.is_empty and poly.area > 1e-4) else None


def panel(x0, x1, z0, z1, holes=(), thick=FRONT_T, y0=0.0):
    """Wandpaneel [x0,x1]x[z0,z1] minus Loecher (x0,x1,z0,z1) -> aufgerichtetes Mesh."""
    poly = sbox(x0, z0, x1, z1)
    for hx0, hx1, hz0, hz1 in holes:
        poly = poly.difference(sbox(hx0, hz0, hx1, hz1))
    poly = _valid(poly)
    if poly is None:
        return None
    return _stand(extrude_polygon(poly, thick), y0=y0)


def _slab(cx, cy, cz, sx, sy, sz):
    b = tbox(extents=(sx, sy, sz)); b.apply_translation((cx, cy, cz)); return b


def arch_poly(cx, w, z0, zspring, ztop, n=14):
    """Rechteck z0..zspring + Segmentbogen zspring..ztop (flacher Bogen) als shapely-Polygon."""
    pts = [(cx - w / 2, z0), (cx + w / 2, z0), (cx + w / 2, zspring)]
    # Segmentbogen: Kreisbogen durch (cx±w/2, zspring) und Scheitel (cx, ztop)
    s = w / 2.0; h = ztop - zspring
    R = (s * s + h * h) / (2 * h) if h > 1e-6 else 1e6
    zc = ztop - R
    for i in range(1, n):
        ang = np.pi / 2 + (i / n) * 2 * np.arctan2(s, R - h)   # ungefaehr; einfacher parametrisch
        x = cx + s * np.cos(np.pi * i / n)
        dz = np.sqrt(max(R * R - (x - cx) ** 2, 0)) + zc
        pts.append((x, dz))
    pts.append((cx - w / 2, zspring))
    return Polygon(pts)


# ---------------------------------------------------------------- Fassade
def facade_wall():
    """Cremefarbene Putzfassade EG_TOP..EAVE mit 12 Fensterloechern (NAX x NFL)."""
    holes = []
    for z0 in FLOOR_Z0:
        sill = z0 + SILL_OFF
        for cx in WIN_X:
            holes.append((cx - WIN_W / 2, cx + WIN_W / 2, sill, sill + WIN_H))
    return panel(0, W, EG_TOP, EAVE, holes=holes)


def eg_base():
    """EG-Restaurantfront (dunkles Holz) 0..EG_TOP mit Tuer + Schaufenster-Loechern."""
    holes = []
    # zentrale Tuer
    holes.append((W / 2 - 0.65, W / 2 + 0.65, 0.0, 2.5))
    # Schaufenster links/rechts der Tuer (Bogenoberkante angenaehert = hoch, rechteckig)
    neg = int(P["n_eg_windows"])
    slots = [W * 0.22, W * 0.78] if neg == 2 else [W * (i + 0.5) / max(neg, 1) for i in range(neg)]
    for sx in slots:
        holes.append((sx - 0.75, sx + 0.75, 0.9, 2.5))
    return panel(0, W, 0.0, EG_TOP, holes=holes, thick=FRONT_T + 0.12, y0=-0.12)


def eg_windows():
    """dunkle Glasflaechen hinter EG-Oeffnungen (warm = Restaurant) + Tuer."""
    parts = []
    for sx in ([W * 0.22, W * 0.78] if int(P["n_eg_windows"]) == 2 else []):
        parts.append(_slab(sx, 0.08, 1.7, 1.5, 0.08, 1.6))
    parts.append(_slab(W / 2, 0.08, 1.25, 1.3, 0.08, 2.5))   # Tuer
    return trimesh.util.concatenate(parts)


def lettering_band():
    """Schriftband 'OBERKIRCHS WEINSTUBEN' als flache Leiste oben am EG."""
    return _slab(W / 2, -0.14, EG_TOP - 0.35, W - 0.7, 0.12, 0.42)


def wappen():
    """zwei runde Wappenschilde flankierend am Schriftband."""
    parts = []
    for sx in (W * 0.12, W * 0.88):
        d = tcyl(radius=0.26, height=0.1, sections=20)
        d.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
        d.apply_translation((sx, -0.18, EG_TOP - 0.3)); parts.append(d)
    return trimesh.util.concatenate(parts)


# ---------------------------------------------------------------- Fenster
def window_glass():
    parts = []
    for z0 in FLOOR_Z0:
        sill = z0 + SILL_OFF
        for cx in WIN_X:
            parts.append(_slab(cx, FRONT_T - 0.08, sill + WIN_H / 2, WIN_W - 0.04, 0.06, WIN_H - 0.04))
    return trimesh.util.concatenate(parts)


def window_frames():
    """weisse Rahmen + Kreuzsprosse (2x2) je Fenster."""
    parts = []
    t = 0.07
    for z0 in FLOOR_Z0:
        sill = z0 + SILL_OFF
        for cx in WIN_X:
            x0, x1 = cx - WIN_W / 2, cx + WIN_W / 2
            zt, zb = sill + WIN_H, sill
            y = FRONT_T - 0.02
            # Rahmen
            parts.append(_slab(cx, y, zt, WIN_W + 0.1, 0.06, t))       # oben
            parts.append(_slab(cx, y, zb, WIN_W + 0.1, 0.06, t))       # unten (Sohlbank)
            parts.append(_slab(x0, y, sill + WIN_H / 2, t, 0.06, WIN_H))  # links
            parts.append(_slab(x1, y, sill + WIN_H / 2, t, 0.06, WIN_H))  # rechts
            # Kreuzsprosse
            parts.append(_slab(cx, y, sill + WIN_H / 2, WIN_W, 0.05, 0.045))  # Kaempfer
            parts.append(_slab(cx, y, sill + WIN_H / 2, 0.045, 0.05, WIN_H))  # Pfosten
    return trimesh.util.concatenate(parts)


def shutters():
    """je Fenster 2 gruene Lamellenlaeden (offen an der Wand, seitlich der Oeffnung)."""
    if not P.get("shutters"):
        return None
    parts = []
    sw = WIN_W * 0.52
    for z0 in FLOOR_Z0:
        sill = z0 + SILL_OFF
        for cx in WIN_X:
            for side in (-1, 1):
                sx = cx + side * (WIN_W / 2 + sw / 2)
                base = _slab(sx, -0.03, sill + WIN_H / 2, sw, 0.05, WIN_H + 0.04)
                parts.append(base)
                # Lamellen-Andeutung: 4 duenne horizontale Leisten vorn
                for k in range(4):
                    zz = sill + 0.18 + k * (WIN_H - 0.3) / 3
                    parts.append(_slab(sx, -0.065, zz, sw - 0.06, 0.02, 0.05))
    return trimesh.util.concatenate(parts)


def flower_boxes():
    if not P.get("flower_boxes"):
        return None, None
    boxes, blossoms = [], []
    for z0 in FLOOR_Z0:
        sill = z0 + SILL_OFF
        for cx in WIN_X:
            boxes.append(_slab(cx, -0.17, sill - 0.12, WIN_W + 0.1, 0.22, 0.2))
            for j in range(5):
                bx = cx - WIN_W / 2 + (j + 0.5) * (WIN_W + 0.1) / 5
                s = tcyl(radius=0.09, height=0.12, sections=8)
                s.apply_translation((bx, -0.2, sill + 0.02)); blossoms.append(s)
    return trimesh.util.concatenate(boxes), trimesh.util.concatenate(blossoms)


# ---------------------------------------------------------------- Dach
def roof():
    """steiles Satteldach, traufstaendig: First parallel zur Fassade (entlang X), bei y=D/2."""
    A = (0, 0, EAVE); B = (W, 0, EAVE); C = (W, D, EAVE); Dd = (0, D, EAVE)
    R0 = (0, D / 2, RIDGE); R1 = (W, D / 2, RIDGE)
    V = [A, B, C, Dd, R0, R1]
    F = [(0, 1, 5), (0, 5, 4),        # Vorderschraege
         (3, 4, 5), (3, 5, 2),        # Rueckschraege
         (0, 4, 3), (1, 2, 5),        # Giebeldreiecke (werden von gables ueberdeckt)
         (0, 3, 2), (0, 2, 1)]        # Bodenplatte
    return trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F))


def gables():
    """cremefarbene Giebel-Endwaende an x=0 und x=W (Putz, wie Fassade)."""
    parts = []
    for x, t in ((0.0, 0.4), (W - 0.4, 0.4)):
        tri = Polygon([(0, EAVE), (D, EAVE), (D / 2, RIDGE)])   # (y, z)
        m = extrude_polygon(tri, t)
        V = m.vertices.copy()
        # (poly.x=y, poly.y=z, extr=dicke->x)
        m.vertices = np.c_[x + V[:, 2], V[:, 0], V[:, 1]]
        parts.append(m)
    return trimesh.util.concatenate(parts)


def dormers():
    """NAX Gauben im unteren Vorderdach, an den Fensterachsen; Koerper + Dach + Fensterglas."""
    bodies, roofs, glass = [], [], []
    zf = EAVE + 0.15          # Fuss der Gaube knapp ueber Traufe
    yf = -0.1                 # Front leicht vor der Traufe
    for cx in WIN_X:
        # Koerper (Putz) mit Fensterloch
        body = panel(cx - DORM_W / 2, cx + DORM_W / 2, zf, zf + DORM_H,
                     holes=[(cx - DORM_W / 2 + 0.18, cx + DORM_W / 2 - 0.18, zf + 0.25, zf + DORM_H - 0.2)],
                     thick=1.0, y0=yf)
        if body is not None:
            bodies.append(body)
        # kleines Walmdaechlein
        top = zf + DORM_H
        A = (cx - DORM_W / 2 - 0.1, yf - 0.05, top); B = (cx + DORM_W / 2 + 0.1, yf - 0.05, top)
        C = (cx + DORM_W / 2 + 0.1, yf + 1.0, top); Dd = (cx - DORM_W / 2 - 0.1, yf + 1.0, top)
        pk0 = (cx - DORM_W / 4, yf + 0.5, top + 0.45); pk1 = (cx + DORM_W / 4, yf + 0.5, top + 0.45)
        roofs.append(trimesh.Trimesh(
            vertices=np.array([A, B, C, Dd, pk0, pk1], float),
            faces=np.array([(0, 1, 5), (0, 5, 4), (3, 4, 5), (3, 5, 2), (0, 4, 3), (1, 2, 5)])))
        glass.append(_slab(cx, yf + 0.05, zf + DORM_H / 2 + 0.02, DORM_W - 0.4, 0.06, DORM_H - 0.5))
    return (trimesh.util.concatenate(bodies), trimesh.util.concatenate(roofs),
            trimesh.util.concatenate(glass))


def skylights():
    """kleine Dachluken im oberen Vorderdach, auf die Schraege gelegt."""
    n = int(P.get("n_skylights", 0))
    if n <= 0:
        return None
    parts = []
    ang = np.arctan2(RIDGE - EAVE, D / 2)       # Neigung der Vorderschraege
    t = 0.6                                      # Lage auf der Schraege (0=Traufe,1=First)
    yy = t * D / 2; zz = EAVE + t * (RIDGE - EAVE)
    for i in range(n):
        cx = W * (i + 0.5) / n
        s = tbox(extents=(0.5, 0.5, 0.08))
        s.apply_transform(trimesh.transformations.rotation_matrix(-ang, [1, 0, 0]))
        s.apply_translation((cx, yy - 0.05, zz + 0.05)); parts.append(s)
    return trimesh.util.concatenate(parts)


# ---------------------------------------------------------------- Hero-Details
def sign():
    """schmiedeeiserner Ausleger + ovale Schildtafel 'HOTEL OBERKIRCH' am 1. OG, mittig."""
    if not P.get("sign"):
        return None, None, None
    cx = W / 2; z = FLOOR_Z0[0] + FLOOR_H * 0.7
    arm = []
    arm.append(_slab(cx, -0.65, z + 0.55, 0.06, 1.3, 0.06))        # Horizontalarm
    arm.append(_slab(cx, -0.05, z + 0.3, 0.06, 0.06, 0.6))          # Wandstuetze
    arm.append(_slab(cx, -1.25, z + 0.15, 0.05, 0.05, 0.85))        # Haenger
    # Schildtafel (Oval ~ Zylinder, Achse Y)
    plate = tcyl(radius=0.52, height=0.08, sections=28)
    plate.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    plate.apply_scale([1.0, 1.0, 0.72])
    plate.apply_translation((cx, -1.3, z - 0.35))
    ring = tcyl(radius=0.6, height=0.05, sections=28)
    ring.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    ring.apply_scale([1.0, 1.0, 0.72])
    ring.apply_translation((cx, -1.26, z - 0.35))
    return trimesh.util.concatenate(arm), plate, ring


def lanterns():
    """zwei Wandlaternen am EG, flankierend zum Eingang."""
    n = int(P.get("n_lanterns", 0))
    if n <= 0:
        return None
    parts = []
    for sx in (W / 2 - 1.4, W / 2 + 1.4):
        parts.append(_slab(sx, -0.25, 2.7, 0.05, 0.5, 0.05))         # Arm
        body = tcyl(radius=0.17, height=0.42, sections=6)
        body.apply_translation((sx, -0.5, 2.5)); parts.append(body)
        cap = tcone(radius=0.2, height=0.18, sections=6)
        cap.apply_translation((sx, -0.5, 2.73)); parts.append(cap)
    return trimesh.util.concatenate(parts)


# ---------------------------------------------------------------- Build
def build():
    fb_box, fb_bloss = flower_boxes()
    d_body, d_roof, d_glass = dormers()
    s_arm, s_plate, s_ring = sign()
    parts = {
        "fassade": facade_wall(),
        "eg_sockel": eg_base(),
        "fenster": trimesh.util.concatenate([window_glass(), eg_windows(), d_glass]),
        "rahmen": window_frames(),
        "laeden": shutters(),
        "kasten": fb_box,
        "blumen": fb_bloss,
        "band": lettering_band(),
        "wappen": wappen(),
        "dach": roof(),
        "giebel": gables(),
        "gaube": d_body,
        "gaube_dach": d_roof,
        "luke": skylights(),
        "schild_arm": s_arm,
        "schild": s_plate,
        "gold": s_ring,
        "laterne": lanterns(),
    }
    os.makedirs(OUT, exist_ok=True)
    sc = trimesh.Scene()
    nf = 0
    for nm, m in parts.items():
        if m is None or not len(m.faces):
            print(f"  (leer {nm})"); continue
        m.visual.face_colors = COL.get(nm, [180, 180, 180, 255])
        m.export(f"{OUT}/obk_{nm}.stl")
        sc.add_geometry(m, geom_name=nm)
        nf += len(m.faces)
        print(f"  {nm}: {len(m.faces)} F")
    sc.export(f"{OUT}/oberkirch_measured.glb")
    # kombiniertes STL
    allm = trimesh.util.concatenate([m for m in parts.values() if m is not None and len(m.faces)])
    allm.export(f"{OUT}/oberkirch_measured.stl")
    print(f"-> {OUT}/oberkirch_measured.glb  ({nf} F gesamt)")
    print(f"   Masse: B{W} T{D} Trauf{EAVE} First{RIDGE}  Achsen{NAX} OG{NFL} Gauben{len(WIN_X)}")


if __name__ == "__main__":
    build()
