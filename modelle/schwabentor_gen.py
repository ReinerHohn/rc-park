#!/usr/bin/env python3
"""schwabentor_gen.py - Schwabentor (Torturm), LoD2 DEBW_001000hPLcp (LGL-Kachel LoD2_32_414_5316_1_BW, GML-Attribut name='Schwabentor').
Jedes sichtbare Element meldet sich mit beleg(); Bau + Abnahme: tools/bauen_abnehmen.sh schwabentor

Zuordnung (2026-11-14): bis dahin Nachbarhaus Tvdv (First 25,8 m) - falsch. Belege fuer PLcp: GML-Name 'Schwabentor'; Rundanbau = Treppentuermchen
'Zinnfiguren-Klause' (Foto IMG_20261106_113545_1); dichte Wolke (Variante J) passt nur hier (Massstab, Muenster-Entfernung, EXIF-GPS).
Masse im Rahmen von objekt.json (u = rahmen.xhat, v = rahmen.yhat, z ueber rahmen.gelaende), aus der LGL-GroundSurface:
  Turm-Grundriss u -8,21..3,92 m, v 8,93..21,43 m (Polygon unten); Rundanbau u 0,0..3,0, v 21,3..23,9
  Wandoberkante 37,00 m (LGL), First 50,80 m (Stadt-LoD2 2025-12-03 + Wikipedia 51 m; LGL nur 45,98 -> Widerspruch in beobachtungen_offen)
  Rundanbau-Hoehe 13,72 m (LGL heights[1])
ANNAHMEN (nicht gemessen): Turmdach als Pyramide auf die Wandoberkante (echtes Dach mit Treppengiebeln fehlt); Rundanbau als Prisma ohne Haube.
"""
import os, sys, json, numpy as np
from manifold3d import Manifold as M, CrossSection

SCALE = float(os.environ.get("SCALE", "87")); K = 1000.0 / SCALE
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "stl", "schwabentor_1-{SCALE:.0f}.stl".format(SCALE=SCALE))
ELEMENTE = []
def beleg(seite, element, quelle, **masse): ELEMENTE.append(dict(seite=seite, element=element, quelle=quelle, **masse))

# LGL-GroundSurface PLcp im Rahmen (u, v), unveraendert uebernommen
TURM = [(3.92, 9.27), (3.42, 9.25), (-7.2, 8.95), (-7.67, 8.93), (-7.84, 12.59), (-8.04, 17.18), (-8.21, 20.95), (-7.64, 20.97), (0.05, 21.28),
        (1.42, 21.34), (3.0, 21.41), (3.54, 21.43), (3.66, 17.74), (3.81, 12.77)]
ANBAU = [(2.39, 23.69), (2.53, 23.61), (2.66, 23.51), (2.77, 23.38), (2.86, 23.25), (2.92, 23.09), (2.94, 23.01), (2.99, 21.11), (1.42, 21.04), (0.05, 20.99),   # Innenkante 0,3 m in den Turm (ANNAHME, verdeckt: sonst Beruehrflaeche ohne Ueberlapp -> zwei Koerper)
        
         (0.01, 22.53), (0.0, 22.78), (0.04, 23.02), (0.13, 23.26), (0.26, 23.47), (0.42, 23.66), (0.61, 23.82), (0.83, 23.93), (1.39, 23.9), (2.32, 23.73)]
WAND, FIRST, ANBAU_H = 37.00, 50.80, 13.72

def entdoppeln(p, d=0.05):
    """LoD2-Digitalisier-Doppelpunkte (< 5 cm, z. B. 3,00/21,41 neben 2,99/21,41) zusammenfuehren - sonst Splitterflaechen in der STL."""
    out = [p[0]]
    for q in p[1:]:
        if np.hypot(*(np.subtract(q, out[-1]))) >= d: out.append(q)
    if np.hypot(*(np.subtract(out[0], out[-1]))) < d: out.pop()
    return np.asarray(out, float)
def ccw(p):
    p = entdoppeln(np.asarray(p, float)); a = 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]); return p if a > 0 else p[::-1]
def prisma(poly, z0, z1): return M.extrude(CrossSection([ccw(poly)]), z1 - z0).translate((0, 0, z0))

T = entdoppeln(np.array(TURM)); su, sv = np.ptp(T[:, 0]), np.ptp(T[:, 1]); cu, cv = T.mean(0)
beleg("wand", "Turmschaft", "LoD2 DEBW_001000hPLcp (LGL): GroundSurface + Wandoberkante 37,00 m", breite_u=round(su, 2), tiefe_v=round(sv, 2), hoehe=WAND)
beleg("dach", "Turmdach", "First: Stadt-LoD2 DEBWL001000hPLcp 50,80 m + Wikipedia 51 m; ANNAHME Pyramidenform (Treppengiebel nicht gemessen)", first=FIRST)
beleg("+y", "Treppentuermchen (Rundanbau)", "LoD2 PLcp zweite GroundSurface, Hoehe 13,72 m (LGL heights[1]); Foto IMG_20261106_113545_1 'Zinnfiguren-Klause'",
      hoehe=ANBAU_H, durchmesser=round(float(np.ptp(np.array(ANBAU)[:, 0])), 2))

schaft = prisma(TURM, 0.0, WAND)
spitze = np.array([[cu, cv, FIRST]]); ring = np.c_[np.array([cu, cv]) + 0.995 * (T - [cu, cv]), np.full(len(T), WAND - 0.01)]   # Dachbasis 0,5 % innen / 1 cm tiefer: sonst Ecke-auf-Ecke-Quetschpunkte (STL zerfiel in 15 Koerper)
dach = M.hull_points(np.vstack([ring, spitze]).tolist())
anbau = prisma(ANBAU, 0.0, ANBAU_H)
model = (schaft + dach + anbau).translate((-cu, -cv, 0)).scale((K, K, K))

mesh = model.to_mesh(); V = np.asarray(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
tri = V[F]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri
with open(OUT, "wb") as f:
    f.write(b"schwabentor".ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())

# Seiten im Rahmen: xhat_utm (-0,24/0,97) = Nord (14 Grad West), yhat_utm (-0,97/-0,24) = West (frueher falsch als +x Sued / +y Ost beschriftet)
SEITEN = {"+x": "Nord", "-x": "Sued", "+y": "West", "-y": "Ost"}
json.dump([dict(e, seite_name=SEITEN.get(e["seite"], e["seite"])) for e in ELEMENTE],
          open(os.path.join(HERE, "schwabentor", "elemente.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT)
