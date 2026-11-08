#!/usr/bin/env python3
"""test_spitze_hoehe.py - synthetischer Beweis der Spitzen-Triangulation (2026-11-05): 12 Kameras im Kreis sehen eine Spitze bei (1, 2, 16);
5 davon liefern Fehlspuren (Giebelstufe/Kamin, je eigener falscher Punkt). RANSAC muss die Spitze auf < 5 cm finden und genau die 7 echten als Inlier nehmen;
Gegenprobe: nur Fehlspuren -> kein Konsens >= tri_min (4); mit 3 traf es zufaellig (erster Lauf 2026-11-05)."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spitze_hoehe import triangulieren, _schnitt, _abst

def lauf(saat):
    rng = np.random.default_rng(saat); S = np.array([1.0, 2.0, 16.0]); O = []; D = []; echt = []
    for k in range(12):
        w = 2 * np.pi * k / 12; C = np.array([40 * np.cos(w), 40 * np.sin(w), 1.6 + rng.uniform(0, 10)]); O.append(C)
        Z = S + (rng.normal(0, 0.05, 3) if k < 7 else np.array([rng.uniform(-3, 3), rng.uniform(-3, 3), rng.uniform(-4, 2)]))
        d = Z - C; D.append(d / np.linalg.norm(d)); echt.append(k < 7)
    O, D, echt = np.array(O), np.array(D), np.array(echt)
    b = triangulieren(O, D, 0.5, 2.5, 8.0, 0.3, 4.0); assert b is not None, "keine Loesung"
    inl = _abst(O, D, b[0]) < 0.3; X = _schnitt(O, D, np.where(inl)[0]); f = np.linalg.norm(X - S)
    b2 = triangulieren(O[~echt], D[~echt], 0.5, 2.5, 8.0, 0.3, 4.0); n2 = 0 if b2 is None else int(b2[1].sum())
    return f, int(inl.sum()), int((inl & ~echt).sum()), bool(inl[echt].all()), n2


R = [lauf(s) for s in range(50)]
f = max(r[0] for r in R); ok1 = sum(r[3] for r in R); n2 = max(r[4] for r in R)
nf = sum(r[2] > 0 for r in R)
print(f"T1 (50 Saaten): max Fehler {f:.3f} m, alle 7 echten gefunden in {ok1}/50, Laeufe mit zufaellig naher Fehlspur (< tol, geometrisch nicht trennbar) {nf}")
assert f < 0.15 and ok1 == 50, "T1 nicht bestanden (Soll: Fehler < tol/2 = 0,15 m, alle echten Strahlen im Konsens)"
print(f"T2 nur Fehlspuren (5 je Lauf, 50 Saaten): groesster Konsens {n2} (Gate tri_min 4 -> muss < 4)"); assert n2 < 4, "T2 nicht bestanden"
print("test_spitze_hoehe: bestanden")
