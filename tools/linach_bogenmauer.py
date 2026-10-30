#!/usr/bin/env python3
"""linach_bogenmauer.py — Linachtalsperre als ECHTE Gewölbereihen-Staumauer.

Der alte Generator (linachtalsperre.py) sweept geschlossene Tonnengewölbe von Fuß
bis Krone → massive Wellenwand OHNE offene Bögen (v5). Die reale Mauer (Foto 237):
schlanke geneigte Wandscheiben, dazwischen je ein GROSSER Oberbogen (offen) + ein
kleiner Unterbogen, Zwischengesims, Krone mit Laufgang/Geländer.

Ansatz: die Luftseiten-Arkade als POLYGON MIT BOGEN-LÖCHERN (shapely) extrudieren —
so entstehen echte Durchsichten statt aufgesetzter Ringe. Proportionen aus Foto 237
kalibriert, Maße aus Denkmal-Daten (143×25 m, 13 Felder, 10,8 m Spannweite).

  modelle/linachtalsperre/linach_bogenmauer.stl
  daten/linach/bm_face.png   (face-on, für tools/validate_bauwerk.py)
  daten/linach/bm_hero.png   (perspektivisch)
"""
import os, numpy as np, trimesh
from shapely.geometry import Polygon
from shapely.ops import unary_union
from trimesh.creation import extrude_polygon
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# ===== Maße (m) — Denkmal + aus Foto 237 kalibriert =========================
L, H = 143.0, 25.0
N = 13;  P = L / N                 # 11.0 m Feldteilung
SLAB = 1.2                         # Dicke der Arkaden-/Wasserwand
LEAN = 0.18                        # Böschung (Luftseite neigt sich taleinwärts mit z)
TB, DB = 1.6, 7.0                  # Wandscheibe: Dicke / Tiefe talseits am Fuß

BW = 3.2                           # sichtbare Pfeilerbreite (Foto: kräftig) -> Öffnung = P-BW
# Oberbogen (groß, rund): Kämpfer..Scheitel
OW_U = P - BW                      # Öffnungsbreite oben (~7,8 m)
Z_LO_U, Z_SP_U = 0.40*H, 0.66*H    # Unterkante / Kämpfer Oberbogen (Bogen etwas höher)
# Unterbogen (klein)
OW_L = (P - BW) * 0.55
Z_LO_L, Z_SP_L = 0.05*H, 0.20*H
OUT = "modelle/linachtalsperre"; os.makedirs(OUT, exist_ok=True)


def round_arch(xc, half_w, z_lo, z_spring):
    """Rundbogen-Öffnung: senkrechte Leibung z_lo..z_spring, Halbkreis r=half_w oben."""
    pts = [(xc-half_w, z_lo), (xc-half_w, z_spring)]
    for a in np.linspace(np.pi, 0, 24):            # Halbkreis Scheitel
        pts.append((xc + half_w*np.cos(a), z_spring + half_w*np.sin(a)))
    pts.append((xc+half_w, z_lo))
    return Polygon(pts)


# ---- Arkaden-Panel (x,z) mit echten Bogen-Löchern, dann zu 3D extrudieren ---
wall = Polygon([(-L/2, 0), (L/2, 0), (L/2, H), (-L/2, H)])
holes = []
for k in range(N):
    xc = -L/2 + (k+0.5)*P
    holes.append(round_arch(xc, OW_U/2, Z_LO_U, Z_SP_U))
    holes.append(round_arch(xc, OW_L/2, Z_LO_L, Z_SP_L))
panel2d = wall.difference(unary_union(holes))
panel = extrude_polygon(panel2d, SLAB)             # extrudiert in +Z (Dicke)
# (x, z, dicke) -> (x, dicke=y, z): Panel steht senkrecht, Dicke = Talrichtung y
panel.vertices = panel.vertices[:, [0, 2, 1]]
# Böschung: Luftseite neigt sich mit z (y -= LEAN*z)
panel.vertices[:, 1] -= LEAN * panel.vertices[:, 2]

parts = [panel]

# ---- 14 Wandscheiben (geneigte Dreiecksprismen, talseits tief am Fuß) -------
def prism(xs0):
    prof = [(SLAB, H), (SLAB, 0), (DB, 0), (DB, 0.30*H)]      # (y, z) talseits
    V = []
    for s in (-TB/2, TB/2):
        for (Y, Z) in prof:
            V.append([xs0 + s, Y - LEAN*Z, Z])
    F = [[0,1,2],[0,2,3],[4,6,5],[4,7,6],[0,4,5],[0,5,1],
         [1,5,6],[1,6,2],[2,6,7],[2,7,3],[3,7,4],[3,4,0]]
    return trimesh.Trimesh(np.array(V, float), np.array(F), process=True)

for k in range(N+1):
    parts.append(prism(-L/2 + k*P))

# ---- geneigte Wasserwand hinter der Arkade (dünn, hält Wasser) --------------
def box(x0, x1, y0, y1, z0, z1):
    return trimesh.creation.box(bounds=[[x0, y0, z0], [x1, y1, z1]])

nz = 18; zs = np.linspace(0, H, nz); xs = np.linspace(-L/2, L/2, 90)
Gf = np.zeros((nz, 90, 3)); Gb = np.zeros((nz, 90, 3))
for i, z in enumerate(zs):
    y0 = SLAB + DB*0.4 - LEAN*z
    for j, x in enumerate(xs):
        Gf[i, j] = [x, y0, z]; Gb[i, j] = [x, y0 + 0.8, z]
def thick(G0, G1):
    m, n = G0.shape[:2]; off = m*n
    V = np.vstack([G0.reshape(-1,3), G1.reshape(-1,3)]); F = []
    ix = lambda b,i,j: b*off + i*n + j
    for i in range(m-1):
        for j in range(n-1):
            F += [[ix(0,i,j),ix(0,i,j+1),ix(0,i+1,j+1)],[ix(0,i,j),ix(0,i+1,j+1),ix(0,i+1,j)]]
            F += [[ix(1,i,j),ix(1,i+1,j+1),ix(1,i,j+1)],[ix(1,i,j),ix(1,i+1,j),ix(1,i+1,j+1)]]
    return trimesh.Trimesh(V, np.array(F), process=True)
parts.append(thick(Gf, Gb))

# ---- Krone: Fahrweg + Geländer ---------------------------------------------
parts.append(box(-L/2, L/2, -LEAN*H-0.5, SLAB+DB*0.4+0.8, H, H+0.9))
parts.append(box(-L/2, L/2, -LEAN*H-0.5, -LEAN*H-0.3, H+0.9, H+1.9))        # Handlauf luftseits
for x in np.arange(-L/2+1, L/2, 2.4):
    parts.append(box(x-0.07, x+0.07, -LEAN*H-0.5, -LEAN*H-0.3, H+0.9, H+1.9))

# ---- Widerlager ------------------------------------------------------------
parts.append(box(-L/2-5, -L/2, -LEAN*H-1, DB, 0, H+1))
parts.append(box(L/2, L/2+5, -LEAN*H-1, DB, 0, H+1))

dam = trimesh.util.concatenate(parts)
trimesh.repair.fix_normals(dam)
dam.export(f"{OUT}/linach_bogenmauer.stl")
print(f"Bogenmauer: {len(dam.vertices)}V/{len(dam.faces)}F  "
      f"bbox {dam.extents.round(1)}  watertight={dam.is_watertight}")

# ===== Render — ORTHOGRAFISCH face-on (sauber, für Validator + Foto-Vergleich) =
from matplotlib.collections import PolyCollection
BG = (0.95, 0.96, 0.98)                               # hell: Durchsicht klar vom Beton trennbar

def render_face(fn, view_from_air=True):
    tris = dam.triangles                              # (F,3,3)
    ymean = tris[:, :, 1].mean(axis=1)
    # Luftseite = kleines y; von dort schauen -> größere y zuerst zeichnen (Maler)
    order = np.argsort(-ymean if view_from_air else ymean)
    n = dam.face_normals
    toward = (-n[:, 1]) if view_from_air else n[:, 1]
    shade = 0.45 + 0.55 * np.clip(toward, 0, 1)        # dem Betrachter zugewandt = heller
    polys = [t[:, [0, 2]] for t in tris[order]]
    cols = [(0.70*s, 0.69*s, 0.66*s) for s in shade[order]]
    fig, ax = plt.subplots(figsize=(12, 2.8))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors="none"))
    ax.set_xlim(-L/2-6, L/2+6); ax.set_ylim(-1.5, H+3.5)
    ax.set_aspect("equal"); ax.axis("off")
    fig.savefig(fn, dpi=130, facecolor=BG, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig); print("render ->", fn)

render_face("daten/linach/bm_face.png", view_from_air=True)
render_face("daten/linach/bm_water.png", view_from_air=False)
