#!/usr/bin/env python3
"""test_dach_dom1_veto.py - DOM1-Veto des Wolken-Dachprofils (tools/dach_profil_wolke.dom1_veto, 21.11.2026).
Anlass Schwabentor-1120: Hoehen-Tor meldete Dach +1,62 m ueber DOM1 (k 0,9605) - sah aus wie 3,5 % Hoehenmassstab, war aber ein zu breites Wolkenprofil
(Rauschsaum + gespiegelte Seiten) auf einem 56-Grad-Dach; Traufe/Grundriss stimmten.
Synthetisch: Walmdach (Traufe 37, Neigung 1,5, Laser bis 45) in einem um 14 Grad gedrehten, verschobenen Rahmen; Laterne darueber fuer den Laser unsichtbar.
  T1 Seite 1,2 m zu weit -> auf Laser-Isolinie (+-0,1 m), T2 Seite 0,2 m zu weit (< tol) bleibt, T3 passende Seiten bleiben,
  T4 Laterne (z ueber Lasermaximum - 0,5) bleibt, T5 ohne Laser (NaN) kein Eingriff, T6 genau ein Eingriff."""
import os, sys, copy, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dach_profil_wolke import dom1_veto

w = np.radians(14); d = np.array([np.cos(w), np.sin(w)]); n = np.array([-np.sin(w), np.cos(w)]); c = np.array([-2.1, 15.2]); A_, B_ = 6.0, 5.5   # Traufe halb (u, v)
def laser(x, y):
    q = np.c_[x, y] - c; u, v = np.abs(q @ d), np.abs(q @ n)                                         # Walm: First entlang u
    z = 37.0 + 1.5 * np.minimum(A_ - u, B_ - v) ; z = np.minimum(z, 45.0); z[(u > A_) | (v > B_)] = 0.0; return z
def soll(z):                                                                       # halbe Breiten der Isolinie z
    h = (z - 37.0) / 1.5; return A_ - h, B_ - h
P = []
for z in np.arange(37.5, 44.6, 0.5):
    a, b = soll(z); P.append([float(z), -a, a, -b, b, 100, []])
for z in (45.5, 46.0, 46.5): P.append([z, -1.0, 1.0, -1.0, 1.0, 100, []])          # Laterne (Laser sieht sie nicht)
P0 = copy.deepcopy(P); F = []
k1 = 4; P[k1][1] -= 1.2                  # T1: -d 1,2 m zu weit
k2 = 6; P[k2][4] += 0.2                  # T2: +n 0,2 m zu weit (unter tol 0,3)
k4 = len(P) - 1; P[k4][2] += 0.8          # T4: Laterne breiter - Laser blind, bleibt
E = dom1_veto(P, c, d, n, laser, tol=0.3)
def chk(b, txt):
    print(("    ok   " if b else "FEHLER   ") + txt); F.append(not b)
chk(abs(P[k1][1] - P0[k1][1]) < 0.12, f"T1 -d 1,2 m zu weit -> {P[k1][1]:+.2f} (Soll {P0[k1][1]:+.2f})")
chk(abs(P[k2][4] - (P0[k2][4] + 0.2)) < 1e-9, "T2 +n 0,2 m zu weit (< tol) bleibt")
rest = [(i, j) for i in range(len(P) - 3) for j in range(1, 5) if (i, j) not in ((k1, 1), (k2, 4)) and abs(P[i][j] - P0[i][j]) > 1e-9]
chk(not rest, f"T3 passende Seiten unveraendert ({len(rest)} geaendert)")
chk(abs(P[k4][2] - (P0[k4][2] + 0.8)) < 1e-9, "T4 Laterne ueber dem Lasermaximum bleibt (Laser blind)")
Q = copy.deepcopy(P0); Q[k1][1] -= 1.2
chk(not dom1_veto(Q, c, d, n, lambda x, y: np.full(len(x), np.nan), tol=0.3) and Q[k1][1] == P0[k1][1] - 1.2, "T5 ohne Laserkachel kein Eingriff")
chk(len(E) == 1 and E[0]["seite"] == "-d", f"T6 genau ein Eingriff ({len(E)})")
print("test_dach_dom1_veto: " + ("bestanden" if not any(F) else f"{sum(F)} FEHLER")); sys.exit(1 if any(F) else 0)
