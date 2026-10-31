#!/usr/bin/env python3
"""testdruck_bauen.py - Testdruck fuer die Duese: Pruefplatte + echte Martinstor-Ausschnitte (1:87).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/testdruck_bauen.py [modell.stl] [--out ordner]"""
import sys, os, numpy as np, trimesh, manifold3d as M
stl = next((a for a in sys.argv[1:] if a.endswith(".stl")), "modelle/stl/martinstor_v4_1-87.stl")
out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "modelle/martinstor_fertigung/testdruck"
os.makedirs(out, exist_ok=True)
def box(x0, x1, y0, y1, z0, z1): return M.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))
def save(man, name):
    mm = man.to_mesh(); t = trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3].astype(float), np.asarray(mm.tri_verts))
    t.export(f"{out}/{name}"); return t.extents.round(1), t.is_watertight

# ---- 1. Pruefplatte: je 6 Stufen, alle Masse in mm (Modell 1:87; 1 mm = 87 mm am Original)
W = [0.4, 0.5, 0.6, 0.8, 1.0, 1.2]; P = 11.0
base = box(0, 6 * P + 4, 0, 4 * 17 + 4, 0, 1.0)
parts = [base]
for i, w in enumerate(W):                                  # A: stehende Rippen (Wanddicke), 4 mm hoch
    parts.append(box(2 + i * P, 2 + i * P + w, 3, 3 + 12, 1.0, 5.0))
for i, g in enumerate([0.2, 0.3, 0.4, 0.5, 0.6, 0.8]):     # B: Spalt zwischen zwei Bloecken
    x = 2 + i * P; parts += [box(x, x + 4.0, 20, 28, 1.0, 4.0), box(x + 4.0 + g, x + 8.0 + g, 20, 28, 1.0, 4.0)]
for i, h in enumerate([0.1, 0.2, 0.3, 0.4, 0.6, 1.0]):     # C: Reliefstufen (Hoehe ueber Platte)
    parts.append(box(2 + i * P, 2 + i * P + 8, 37, 47, 1.0, 1.0 + h))
blk = box(2, 6 * P + 2, 54, 70, 1.0, 5.0)                  # D: Bohrungen (Durchmesser)
for i, d in enumerate([0.4, 0.6, 0.8, 1.0, 1.5, 2.0]):
    blk = blk - M.Manifold.cylinder(6, d / 2, circular_segments=32).translate((2 + 5 + i * P, 62, 0.5))
parts.append(blk)
plate = parts[0]
for p in parts[1:]: plate = plate + p
print("pruefplatte_0.4.stl", *save(plate, "pruefplatte_0.4.stl"))

# ---- 2. Ausschnitte aus dem echten Modell (Koordinaten Meter am Original -> mm bei 1:87)
mm = trimesh.load(stl); man = M.Manifold(M.Mesh(np.asarray(mm.vertices, np.float32), np.asarray(mm.faces, np.uint32)))
def crop(name, x, y, z):
    s = 1000 / 87.0
    c = box(x[0] * s, x[1] * s, y[0] * s, y[1] * s, z[0] * s, z[1] * s)
    print(name, *save(man ^ c, name))
crop("test_adlertafel.stl", (-5.3, -4.55), (-1.2, 1.2), (8.1, 10.8))
crop("test_zinnen.stl", (3.6, 5.3), (-2.3, 2.3), (30.0, 32.0))
crop("test_tuermchen.stl", (3.0, 6.4), (3.4, 6.9), (29.8, 40.0))
crop("test_eckquader.stl", (3.2, 5.2), (3.6, 5.6), (18.0, 24.0))
open(f"{out}/LIES_MICH.txt", "w").write("""TESTDRUCK 0,4-mm-Duese (Martinstor 1:87)
Alles liegend/stehend wie gezeigt, 0,12 mm Schicht, 3 Waende, ohne Stuetzen (Tuermchen evtl. mit Stuetzen), PLA.
1. pruefplatte_0.4.stl  Zeilen von unten: A Rippen 0,4/0,5/0,6/0,8/1,0/1,2 mm dick (stehen sie? zusammenhaengend?)
   B Spalt 0,2/0,3/0,4/0,5/0,6/0,8 mm (welcher Spalt ist noch offen?)  C Reliefstufen 0,1/0,2/0,3/0,4/0,6/1,0 mm hoch
   D Bohrungen 0,4/0,6/0,8/1,0/1,5/2,0 mm (welche ist offen?)
2. test_adlertafel / test_zinnen / test_tuermchen / test_eckquader = echte Ausschnitte. 1 mm = 87 mm am Original.
Notieren: kleinste Rippe/Spalt/Reliefstufe/Bohrung, die sauber kommt -> das ist die Detailgrenze fuer 0,4 mm.
""")
