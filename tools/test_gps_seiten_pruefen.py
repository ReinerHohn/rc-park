#!/usr/bin/env python3
"""Fester Test gps_seiten_pruefen.urteil_2d: Kameras im Halbkreis vor und hinter einem Turm (GPS mit 4 m Rauschen), Modell gedreht+skaliert.
Richtig -> GPS-STIMMIG; Rueckseite durch den Turm auf die Vorderseite geklappt (Verkleben) -> VERDAECHTIG."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import gps_seiten_pruefen as G
rng = np.random.default_rng(1); w = np.r_[rng.uniform(-1.2, 1.2, 60), rng.uniform(np.pi - 1.2, np.pi + 1.2, 40)]; rad = rng.uniform(20, 45, 100)
Y = np.c_[rad * np.sin(w), rad * np.cos(w)] + rng.normal(0, 4, (100, 2))
a = 0.7; R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]); wahr = np.c_[rad * np.sin(w), rad * np.cos(w)]
X = (R @ wahr.T).T * 0.13 + [3, -2]
e = G.urteil_2d(X, Y); assert e["urteil"] == "GPS-STIMMIG" and e["median_m"] < 8, e
geklappt = wahr.copy(); geklappt[60:, 1] *= -1                                     # Rueckseite an der Turmachse auf die Vorderseite gespiegelt
e2 = G.urteil_2d((R @ geklappt.T).T * 0.13 + [3, -2], Y); assert e2["urteil"].startswith("VERDAECHTIG"), e2
print(f"ok: richtig {e['median_m']:.1f} m / {100*e['ausreisser']:.0f} %, verklebt {100*e2['ausreisser']:.0f} % Ausreisser -> erkannt")
