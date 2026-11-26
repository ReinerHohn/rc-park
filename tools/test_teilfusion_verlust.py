#!/usr/bin/env python3
"""test_teilfusion_verlust.py - Verlustwarnung der Teilfusion (26.11.2026). Echte Zahlen von Schwabentor 1122 (fused.ply.teile.json): Teil 3 und 6 muessen warnen, Teil 2 nicht.
Verwandt: tools/teilfusion.py (verlust_warnung), tools/kachelfusion.py.
Vorlaeufer: keiner - Teilfusion hatte keine Pruefung auf Punktverlust."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import teilfusion as TF
I = [dict(teil=0, kern=126, nachbarn=21, punkte_teil=4595375, punkte_behalten=3523647), dict(teil=1, kern=106, nachbarn=41, punkte_teil=4462196, punkte_behalten=2662020),
     dict(teil=2, kern=144, nachbarn=3, punkte_teil=4812764, punkte_behalten=4681455), dict(teil=3, kern=30, nachbarn=117, punkte_teil=3487532, punkte_behalten=244708),
     dict(teil=6, kern=66, nachbarn=81, punkte_teil=3975038, punkte_behalten=875591)]
w = {x["teil"] for x in TF.verlust_warnung(I)}
assert w == {3, 6}, w
assert TF.verlust_warnung([]) == []
print("OK Verlustwarnung: Teil 3 und 6 warnen, Teil 0-2 nicht")
