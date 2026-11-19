#!/usr/bin/env python3
"""test_stabil_schnitt.py - Schnelltest fuer tools/sfm_stabil_schnitt.schnitt(): synthetische Kameras entlang einer Strasse (fast kollinear, wie Martinstor),
Lauf B = Aehnlichkeitstransformation von A (Drehung 40 Grad, Massstab 2,3, Versatz) plus Rauschen; 30 % der Kameras in B bewusst verschoben/verdreht.
Erwartung: genau die verschobenen gelten als unstabil, die uebrigen als stabil (auch bei kollinearen Standorten, weil die Drehung aus den Rotationen kommt)."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sfm_stabil_schnitt import schnitt


def rot(ax, grad):
    ax = np.asarray(ax, float); ax /= np.linalg.norm(ax); a = np.radians(grad); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


rng = np.random.default_rng(3); n = 120
A = {}
for i in range(n):   # Strasse entlang x, Querstreuung klein, Hoehe 1,5 m +- 0,3
    c = np.array([i * 0.5, rng.normal(0, 0.8), 1.5 + rng.normal(0, 0.3)]); R = rot([0, 0, 1], rng.normal(0, 15)) @ rot([1, 0, 0], 90)
    A[f"bild_{i:03d}.jpg"] = (c, R, i)
S = rot([0.2, 0.3, 1], 40); s = 2.3; t = np.array([10, -4, 2.0])
B = {}; weg = set(rng.choice(list(A), size=int(0.3 * n), replace=False))
for k, (c, R, i) in A.items():
    cb = s * S @ c + t + rng.normal(0, 0.01, 3); Rb = R @ S.T @ rot(rng.normal(size=3), rng.normal(0, 0.2))
    if k in weg: cb = cb + rng.normal(0, 1.0, 3) * s; Rb = Rb @ rot(rng.normal(size=3), 6 + abs(rng.normal(0, 3)))
    B[k] = (cb, Rb, i)
stabil, ber, reste = schnitt(A, B, lage=0.10, rot=2.0)
falsch_stabil = sorted(stabil & weg); falsch_unstabil = sorted((set(A) - weg) - stabil)
ok = not falsch_stabil and len(falsch_unstabil) <= 2 and ber["gemeinsam"] == n
print("stabil", len(stabil), "erwartet", n - len(weg), "| verschobene faelschlich stabil:", len(falsch_stabil), "| unverschobene faelschlich unstabil:", len(falsch_unstabil), "| Median Lage rel", ber["lage_median_rel"], "Rot", ber["rot_median_grad"])
sys.exit(0 if ok else 1)
