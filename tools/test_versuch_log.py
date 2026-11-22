#!/usr/bin/env python3
"""Test versuch_log: Eintrag, Identitaetswarnung (BS7-Fall), Fehlschlag, Liste. Exit 0 = ALLE BESTANDEN."""
import os, sys, json, tempfile, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import versuch_log as VL
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
d = temp_ordner(); oj = os.path.join(d, "objekt.json"); open(oj, "w").write("{}")
r1 = VL.log(oj, "wettbewerb", "--a 1", {"c": {"mittel": -0.10401, "median": -0.1104}})
assert r1["warnung"] is None
r2 = VL.log(oj, "wettbewerb", "--a 1 --raster", {"c": {"median": -0.1104, "mittel": -0.10402}})        # gleiche Zahlen (4 Stellen), andere Argumente
assert r2["warnung"] and "IDENTISCH" in r2["warnung"], r2
r3 = VL.log(oj, "wettbewerb", "--a 1 --raster2", {"c": {"mittel": -0.0811, "median": -0.0748}}); assert r3["warnung"] is None
r4 = VL.log(oj, "wettbewerb", "--x", {}, status="keine_werte", notiz="Maske fehlt"); assert r4["status"] == "keine_werte"
assert len(VL.lesen(oj)) == 4 and os.path.exists(os.path.join(d, "VERSUCHE_AUTO.md"))
print("ALLE BESTANDEN")
