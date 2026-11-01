#!/usr/bin/env python3
"""schwabentor_gen.py - Generator-Rumpf (manifold3d). Jedes sichtbare Element meldet sich mit beleg(); Bau + Abnahme: tools/bauen_abnehmen.sh schwabentor"""
import os, json, numpy as np
from manifold3d import Manifold as M
SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl", "schwabentor_1-{SCALE:.0f}.stl".format(SCALE=SCALE))
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **masse))
SEITEN = {"+x": "Sued", "-x": "Nord", "+y": "Ost", "-y": "West"}
H = 51                                   # Gesamthoehe (m) - Quelle in masstabelle.json
beleg("dach", "Grundkoerper", "ANNAHME: Rumpf noch ohne Quelle", hoehe=H)
model = M.cube((8.0, 8.0, H)).translate((-4.0, -4.0, 0.0)).scale((K, K, K))
mesh = model.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tri = V[F]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
with open(OUT, "wb") as f: f.write(b"schwabentor".ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE], open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "schwabentor", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
