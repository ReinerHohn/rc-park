#!/usr/bin/env python3
"""Beweis profil_diff: synthetische Wand + 2 Erker; Modell = Wahrheit -> 0 Abweichungen; rechter Erker um 0,8 m verschoben -> Abweichung erkannt (Exit-Logik, nicht Zufall)."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import profil_diff as P
rng = np.random.default_rng(0); F = dict(n=[0.0, 1.0], d=[1.0, 0.0], o=[0.0, 0.0])
def flaeche(u0, u1, s, z0, z1, n): return np.c_[rng.uniform(u0, u1, n), np.full(n, s), rng.uniform(z0, z1, n)]
def haus(er):                                   # Wand s=0 + Erker (u0,u1) 0,8 m vor der Wand, z 5..11
    L = [flaeche(-12, 12, 0.0, 0, 14, 90000)]
    for u0, u1 in er: L += [flaeche(u0, u1, 0.8, 5, 11, 20000), flaeche(u0, u0 + 0.01, 0.4, 5, 11, 100)]
    return np.vstack(L)
W = haus([(-9.75, -8.0), (8.25, 9.75)]) + rng.normal(0, 0.03, (1, 3)) * 0
W = W + rng.normal(0, 0.03, W.shape)
ok = P.vergleich(haus([(-9.75, -8.0), (8.25, 9.75)]), W, F, [5, 8, 11], "vorsprung", 0.3)
schief = P.vergleich(haus([(-9.75, -8.0), (7.45, 8.95)]), W, F, [5, 8, 11], "vorsprung", 0.3)
n_ok = sum(z["urteil"] == "ABWEICHUNG" for e in ok for z in e["laeufe"]); n_bad = sum(z["urteil"] == "ABWEICHUNG" for e in schief for z in e["laeufe"])
print("Wahrheit: Abweichungen", n_ok, "| 0,8 m verschoben: Abweichungen", n_bad)
assert n_ok == 0 and n_bad >= 1, "profil_diff taugt nicht"; print("test_profil_diff: bestanden")
