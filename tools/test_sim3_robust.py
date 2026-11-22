#!/usr/bin/env python3
"""Test sim3_robust.sim3_meter (22.11.2026): eine Kamera "am Mond" darf die Lage nicht verschieben; zu viele Ausreisser -> None; wand_dicke_tor nutzt die robuste Sim3."""
import os, sys, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from sim3_robust import sim3_meter, matrix, anwenden, umeyama
fehler = []
def pruef(ok, text): print(("ok   " if ok else "FEHL ") + text); ok or fehler.append(text)
rng = np.random.default_rng(1); X = rng.normal(0, 3, (200, 3)); c, s_ = np.cos(0.7), np.sin(0.7); R = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
M_wahr = matrix(2.5, R, np.array([10.0, -4.0, 1.0])); Y = anwenden(M_wahr, X) + rng.normal(0, 0.05, X.shape)
Y1 = Y.copy(); Y1[17] += 4000.0                                                   # Kamera am Mond
f = sim3_meter(X, Y1); r_alt = np.linalg.norm(anwenden(matrix(*umeyama(X, Y1)), X) - anwenden(M_wahr, X), axis=1)
pruef(f is not None and not f["inlier"][17] and f["n_inlier"] >= 195, f"Mond-Kamera als Ausreisser erkannt ({None if f is None else f['n_inlier']} stimmig)")
pruef(f is not None and np.abs(f["M"] - M_wahr).max() < 0.05, "Lage trotz Mond-Kamera richtig")
pruef(np.median(r_alt) > 5, f"Gegenprobe: alter Umeyama ueber alle verschiebt um {np.median(r_alt):.0f} m")
Y2 = Y.copy(); Y2[:120] += rng.normal(0, 50, (120, 3))
pruef(sim3_meter(X, Y2) is None, "Mehrheit Ausreisser -> keine Lage (None)")
pruef(sim3_meter(X[:2], Y[:2]) is None, "weniger als 3 Punkte -> None")
src = open(os.path.join(T, "wand_dicke_tor.py")).read()
pruef("fit = sim3_meter(X, Y)" in src and "M = sim3_fit(X, Y)" not in src, "wand_dicke_tor.teile_laden nutzt sim3_meter")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
