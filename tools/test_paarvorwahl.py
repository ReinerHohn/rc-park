#!/usr/bin/env python3
"""Test paarvorwahl.py (synthetisch): (1) Abstand stimmt (0,001 Grad Breite = 111,2 m), (2) ohne GPS bleibt jedes Paar, (3) Radius 0 = unveraendert,
(4) Wahrheitspaare (Abstand < Radius, auch mit GPS-Rauschen 10 m) gehen nie verloren, (5) weit entfernte Paare entfallen, (6) Mischfall mit/ohne GPS,
(7) EXIF-Lesen: JPEG mit GPS-Block wird gelesen, JPEG ohne -> None."""
import sys, os, random, tempfile, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paarvorwahl as P

assert abs(P.abstand_m((48.0, 7.85), (48.001, 7.85)) - 111.2) < 0.5
random.seed(1)
# 60 Bilder in 3 Gruppen (je 100 m Streuung), Gruppen 2 km auseinander; GPS-Rauschen 10 m (~0,00009 Grad)
gps = {}; gruppe = {}
for g, (la0, lo0) in enumerate([(48.00, 7.85), (48.02, 7.85), (48.00, 7.88)]):
    for i in range(20):
        n = f"b{g}_{i:02d}"; gruppe[n] = g
        gps[n] = (la0 + random.uniform(-0.0005, 0.0005) + random.gauss(0, 0.00009), lo0 + random.uniform(-0.0007, 0.0007) + random.gauss(0, 0.00013))
alle = list(itertools.combinations(sorted(gps), 2))
kept, st = P.gps_filter(alle, gps, 0)
assert len(kept) == len(alle) and st["entfernt"] == 0
kept, st = P.gps_filter(alle, {}, 300)
assert len(kept) == len(alle) and st["ohne_gps"] == len(alle)
kept, st = P.gps_filter(alle, gps, 300)
ks = set(kept)
innen = [(x, y) for x, y in alle if gruppe[x] == gruppe[y]]
assert all(p in ks for p in innen), "Paare derselben Gruppe verloren"
assert all(gruppe[x] == gruppe[y] for x, y in kept), "Paare ueber 2 km nicht entfernt"
assert st["entfernt"] == len(alle) - len(innen) and st["entfernt"] > 0
# Mischfall: Bilder ohne GPS behalten alle ihre Paare
teil = {n: v for n, v in gps.items() if not n.endswith("_00")}
k2, s2 = P.gps_filter(alle, teil, 300)
assert all(p in set(k2) for p in alle if p[0].endswith("_00") or p[1].endswith("_00"))
assert s2["ohne_gps"] > 0
print(f"Vorwahl: {st['vorher']} -> {st['nachher']} Paare (entfernt {st['entfernt']}), Wahrheitspaare verloren: 0")
# EXIF
from PIL import Image
with tempfile.TemporaryDirectory() as d:
    im = Image.new("RGB", (8, 8)); ex = im.getexif()
    ex.get_ifd(0x8825)  # legt IFD an
    ex[0x8825] = {1: "N", 2: (48.0, 0.0, 36.0), 3: "E", 4: (7.0, 51.0, 0.0)}
    f = os.path.join(d, "mit.jpg"); im.save(f, exif=ex)
    g = P.gps_aus_exif(f)
    assert g is not None and abs(g[0] - 48.01) < 1e-6 and abs(g[1] - 7.85) < 1e-6, g
    f2 = os.path.join(d, "ohne.jpg"); Image.new("RGB", (8, 8)).save(f2)
    assert P.gps_aus_exif(f2) is None and P.gps_aus_exif(os.path.join(d, "fehlt.jpg")) is None
print("test_paarvorwahl: bestanden")
