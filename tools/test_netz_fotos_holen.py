#!/usr/bin/env python3
"""Test netz_fotos_holen (19.11.2026): Suchbegriffe aus objekt.json, Zwischenspeicher je Quelle (frisch = uebersprungen), Trockenlauf ohne Netz."""
import os, sys, json, tempfile, time, io, contextlib, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
import netz_fotos_holen as N
b, s = N.suchbegriffe(dict(name="Martinstor", ort="Freiburg im Breisgau, Kaiser-Joseph-Strasse", bildquellen=dict(commons=dict(suchen=["Martinstor Freiburg", "martinstor"]))))
assert b == ["Martinstor Freiburg im Breisgau", "Martinstor", "Martinstor Freiburg"] and s == "Freiburg im Breisgau", (b, s)
t = temp_ordner("netz_"); oj = os.path.join(t, "objekt.json"); json.dump(dict(name="Testtor", ort="Teststadt", koordinate_utm=[414127.0, 5316243.0]), open(oj, "w"))
g = N.geo(json.load(open(oj))); assert abs(g[0] - 47.993) < 0.01 and abs(g[1] - 7.849) < 0.01, g
aus = os.path.join(t, "netz"); os.makedirs(aus); json.dump({q: dict(zeit=time.time(), rc=0, bilder=3) for q in ("openverse", "commons_geo", "hochblick")}, open(os.path.join(aus, "netz_stand.json"), "w"))
f = io.StringIO()
with contextlib.redirect_stdout(f): rc = N.main([oj, "--aus", aus])                       # alles frisch -> kein Aufruf, rc 0
assert rc == 0 and f.getvalue().count("uebersprungen") == 3, f.getvalue()
f = io.StringIO()
with contextlib.redirect_stdout(f): rc = N.main([oj, "--aus", aus, "--neu", "--trocken"])
o = f.getvalue(); assert rc == 0 and "openverse_holen.py" in o and "--lat 47.99" in o and "online_ansichten_holen.py" in o and "Teststadt Luftbild" in o, o
shutil.rmtree(t); print("ok netz_fotos_holen")
