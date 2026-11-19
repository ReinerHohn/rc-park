#!/usr/bin/env python3
"""Test wolke_gruppen_pruefen (19.11.2026): Hoehenkarte aus LoD2-Punkten, Gruppe mit Punkten hoch ueber der Strasse wird auffaellig, gute Gruppe nicht, unbewertbare Punkte zaehlen nicht."""
import os, sys, collections
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolke_gruppen_pruefen as W
assert W.gruppe("video_frames_ab__vf_012.jpg") == "video_frames_ab" and W.gruppe("eigen__001_x.jpg") == "eigen"
rng = np.random.default_rng(0)
haus = np.c_[rng.uniform(0, 10, 4000), rng.uniform(0, 10, 4000), rng.uniform(0, 15, 4000)]; turm = np.c_[rng.uniform(40, 46, 2000), rng.uniform(0, 6, 2000), rng.uniform(0, 45, 2000)]
K = W.hoehenkarte(np.vstack([haus, turm])); x0, y0, z, M = K
h = lambda x, y: M[int((y - y0) / z), int((x - x0) / z)]
assert abs(h(5, 5) - 15) < 1 and abs(h(43, 3) - 45) < 1 and abs(h(15, 5) - 15) < 1 and np.isnan(h(25, 5)), (h(5, 5), h(43, 3), h(15, 5), h(25, 5))   # 5 m neben dem Haus gilt noch dessen Hoehe, 15 m daneben: unbekannt
gut = np.c_[rng.uniform(-1, 11, 300), rng.uniform(-1, 11, 300), rng.uniform(0, 16, 300)]            # Fassade/Dach des Hauses
geist = np.c_[rng.uniform(-5, 14, 200), rng.uniform(-5, 14, 200), rng.uniform(25, 55, 200)]         # 'Haeuserzeile' 25-55 m hoch ueber einem 15-m-Haus
fern = np.c_[rng.uniform(24, 27, 100), rng.uniform(4, 6, 100), rng.uniform(60, 80, 100)]             # weit weg von jedem LoD2: nicht bewertbar
P = np.vstack([gut, geist, fern]); SG = [collections.Counter(a=5)] * 300 + [collections.Counter(b=4, a=1)] * 200 + [collections.Counter(c=3)] * 100
G, ant, bew, unm = W.bewerten(P, SG, K)
assert not G["a"]["auffaellig"] and G["a"]["anteil"] < 0.05, G["a"]; assert G["b"]["auffaellig"] and G["b"]["anteil"] > 0.9, G["b"]; assert "c" not in G, G.keys(); assert bew.sum() == 500
print("ok wolke_gruppen")
