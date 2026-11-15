#!/usr/bin/env python3
"""schwabentor_gen.py - Schwabentor (Torturm), LoD2 DEBW_001000hPLcp (LGL-Kachel LoD2_32_414_5316_1_BW, GML-Attribut name='Schwabentor').
Jedes sichtbare Element meldet sich mit beleg(); Bau + Abnahme: tools/bauen_abnehmen.sh schwabentor

Zuordnung (2026-11-14): bis dahin Nachbarhaus Tvdv (First 25,8 m) - falsch. Belege fuer PLcp: GML-Name 'Schwabentor'; Rundanbau = Treppentuermchen
'Zinnfiguren-Klause' (Foto IMG_20261106_113545_1); dichte Wolke (Variante J) passt nur hier (Massstab, Muenster-Entfernung, EXIF-GPS).
Baukoerper allgemein aus tools/dach_bauen.py (gleich fuer jedes Objekt): LoD2-Grundrisse + Dach aus Laser DOM1 (schwabentor/dach.json,
tools/dach_vermessen.py: Walm/Zelt 56 Grad, First 45,5 m, RMS 0,26 m) + Spitze bis objekt.json hoehe_m 50,8 m (Stadt-LoD2 + Wikipedia 51 m).
ANNAHMEN: Spitzenform (Pyramide); Treppentuermchen Flachdach auf LoD2-Wandoberkante (Haube nicht gemessen); Treppengiebel/Gauben fehlen.
"""
import os, sys, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from dach_bauen import gebaeude_aus_lod2, seiten_aus_rahmen

SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
OUT = os.path.join(HERE, "stl", "schwabentor_1-{SCALE:.0f}.stl".format(SCALE=SCALE))
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **masse))

koerper, belege, haupt = gebaeude_aus_lod2(os.path.join(HERE, "schwabentor", "objekt.json"))
for b in belege: beleg(**b)
cu, cv = haupt.mean(0)
model = koerper.scale((K, K, K))   # 15.11.2026: NICHT zentrieren - STL bleibt im Rahmen (objekt.json rahmen); die Fotowerkzeuge (zentrierung 'achse') erwarten STL = Rahmen, sonst liegt das Modell um (cu, cv) neben Kameras/Wolke

mesh = model.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tri = V[F]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
with open(OUT, "wb") as f:
    f.write(b"schwabentor".ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())

SEITEN = seiten_aus_rahmen(json.load(open(os.path.join(HERE, "schwabentor", "objekt.json"))))   # +x Nord, +y West (aus rahmen.xhat/yhat)
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE],
          open(os.path.join(HERE, "schwabentor", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
