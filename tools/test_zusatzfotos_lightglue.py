#!/usr/bin/env python3
"""Test zusatzfotos_lightglue.py: Stufen/Argumente vorhanden, Modul ohne torch/pycolmap importierbar, GPU-Werkzeugliste enthaelt es;
bei vorhandenem Ergebnis (kaufhaus_handy/lg) Plausibilitaet: nicht weniger registriert als der SIFT-Lauf, Reproj < 2 px."""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zusatzfotos_lightglue as Z
hier = os.path.dirname(os.path.abspath(__file__))
for st in ("paare", "refnamen", "einlesen", "teilmodell"):
    r = subprocess.run([sys.executable, os.path.join(hier, "zusatzfotos_lightglue.py"), st, "--help"], capture_output=True, text=True); assert r.returncode == 0 and "--ziel" in r.stdout, st
assert "zusatzfotos_lightglue.py" in open(os.path.join(hier, "gpu_werkzeuge.txt")).read().split()
Zd = "/media/oem/scan/rc-park_null/kaufhaus_handy"
if os.path.exists(Zd + "/lg/registrierung.json"):
    n = json.load(open(Zd + "/lg/registrierung.json")); o = json.load(open(Zd + "/registrierung.json"))
    assert n["registriert"] >= o["registriert"], (n["registriert"], o["registriert"]); assert n["reproj_mittel_px"] < 2.0
    assert n["f_fest_px"] > 1000
print("test_zusatzfotos_lightglue: bestanden")
