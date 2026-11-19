#!/usr/bin/env python3
"""Fester Test fuer seiten_vereinen.py (Anlass Martinstor 19.11.2026: Achse 2 m zur Kameraseite verschoben, Kameralot 2,3 Grad verkippt).
Synthetischer Turm 10 x 10 m, 40 m Wand, Walmdach bis 55 m, Helmstange bis 60 m, Achse bei (-0,9 / -0,2). Gesehen wird nur die Vorderseite (+x) und die vordere Dachhaelfte,
wie in einer Seitenwolke. Erwartung: stange() trifft die Achse auf 0,15 m (die Verschiebung der alten Wege entstand an echten Daten durch Verschmierung, synthetisch nicht nachgebildet);
lot_aus_waenden() holt ein um 2,3 Grad verkipptes Startlot auf 0,3 Grad zurueck."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import seiten_vereinen as V

rng = np.random.default_rng(1); ax = np.array([-0.9, -0.2]); P = []
for _ in range(60000):                                                                 # Vorderwand x = +5 und Seitenwaende y = +-5 (nur vordere Haelfte gesehen)
    z = rng.uniform(0, 40); w = rng.integers(3)
    if w == 0: P.append((5.0, rng.uniform(-5, 5), z))
    else: P.append((rng.uniform(0, 5), 5.0 if w == 1 else -5.0, z))
for _ in range(30000):                                                                 # vordere Dachflaeche: von x=+5 (40 m) zur Achse (55 m)
    f = rng.uniform(0, 1); P.append((5.0 * (1 - f), rng.uniform(-5, 5) * (1 - f), 40 + 15 * f))
for _ in range(2500): P.append((rng.normal(0, 0.08), rng.normal(0, 0.08), rng.uniform(55, 60)))   # Helmstange
for _ in range(40000): P.append((rng.uniform(15, 40), rng.choice([-12.0, 12.0]), rng.uniform(0, 15)))  # Nachbarhaeuser (Wandflaechen y = +-12)
X = np.array(P) + np.r_[ax, 0] + rng.normal(0, 0.02, (len(P), 3)); wm = np.r_[ax + [5.0, 0.0]]; H = 40.0
s = V.stange(X, wm, H, 0.0); assert s is not None, "stange: nichts gefunden"
assert np.linalg.norm(s[0] - ax) < 0.15, f"stange {s[0]} statt {ax}"
kipp = np.radians(2.3); up0 = np.array([np.sin(kipp), 0.0, np.cos(kipp)])
u, n = V.lot_aus_waenden(X, up0); assert n > 300, f"zu wenig Wandnormalen {n}"
w = np.degrees(np.arccos(abs(u[2]))); assert w < 0.3, f"Lot {w:.2f} Grad neben der Senkrechten (Start 2,3)"
print(f"ok: Stange {np.linalg.norm(s[0] - ax):.3f} m neben der Achse, Lot {w:.2f} Grad (Start 2,30, {n} Normalen)")
