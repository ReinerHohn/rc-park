#!/usr/bin/env python3
"""Test Zwischenspeicher der Bildvorpruefung (bilder_vorpruefen.Speicher, 19.11.2026): Ergebnis bleibt ueber Neustart, geaenderte Datei = neue Kennung, anderer Referenzsatz = anderer Speicher."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from pfade import temp_ordner   # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
t = temp_ordner("vpcache_"); os.environ["RCPARK_CACHE"] = t
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bilder_vorpruefen as BV
a = os.path.join(t, "a.jpg"); open(a, "w").write("x"); r = os.path.join(t, "ref.jpg"); open(r, "w").write("ref")
ida = BV.bild_id(a); S = BV.Speicher([r], 60); assert S.hole("bilder", ida) is None
S.setze("bilder", ida, dict(inlier=77, foto="ref.jpg")); S.setze("paare", ida + ">" + ida, 0); S.sichern()
S2 = BV.Speicher([r], 60); assert S2.hole("bilder", ida) == dict(inlier=77, foto="ref.jpg") and S2.hole("paare", ida + ">" + ida) == 0 and S2.treffer == 2
assert BV.Speicher([r], 80).hole("bilder", ida) is None                                   # andere Schwelle -> anderer Speicher
open(a, "w").write("xy"); os.utime(a, (time.time() + 5, time.time() + 5)); assert BV.bild_id(a) != ida and S2.hole("bilder", BV.bild_id(a)) is None   # Datei geaendert
open(r, "w").write("ref2"); assert BV.Speicher([r], 60).hole("bilder", ida) is None       # Referenz geaendert -> neu rechnen
assert BV.Speicher([r], 60, an=False).hole("bilder", ida) is None and BV.bild_id(os.path.join(t, "fehlt.jpg")) is None
__import__("shutil").rmtree(t); print("ok vorpruefen_cache")
