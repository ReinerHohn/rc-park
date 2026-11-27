#!/usr/bin/env python3
"""test_farbdatei.py - gesamtkette.farbdatei: Farbdatei zur Punktdatei, auch fuer die vereinte Wolke (27.11.2026).
Vorfall: wf_ = W.replace("punkte_modell_", "punkte_farben_") traf punkte_modell.npy (vereinte Wolke) nicht; die Koordinaten gingen als Farben an
wolke_draehte -> 'RGBA values should be within 0-1 range' (Kette 1127b, Stufe draehte). Verwandt: tools/wolke_vereinigen.py, tools/gesamtkette.py (draehte, html).
Vorlaeufer: tools/test_wolken_vereinen_stufe.sh"""
import os, sys
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gesamtkette.py")).read()
i = src.index("def farbdatei"); j = src.index("\n\n", i); ns = {"os": os}; exec(src[i:j], ns); f = ns["farbdatei"]
fehler = 0
def pruef(ok, t):
    global fehler
    print(("  ok     " if ok else "  FEHLER ") + t); fehler += 0 if ok else 1
pruef(f("/x/punkte_modell_schwabentor-1122.npy") == "/x/punkte_farben_schwabentor-1122.npy", "altes Namensschema")
pruef(f("/x/wolken_vereint/punkte_modell.npy") == "/x/wolken_vereint/punkte_farben.npy", "vereinte Wolke punkte_modell.npy -> punkte_farben.npy")
for w in ("/x/punkte_modell.npy", "/x/foo.npy", "/x/punkte_modell_a.npy"):
    pruef(f(w) != w, f"ROT: nie die Punktdatei selbst als Farbdatei ({w})")
pruef(not os.path.exists(f("/x/foo.npy")), "unbekannter Name -> Pfad existiert nicht (Stufe laeuft ohne Farben, kein Absturz)")
print(f"test_farbdatei: {fehler} Fehler"); sys.exit(1 if fehler else 0)
