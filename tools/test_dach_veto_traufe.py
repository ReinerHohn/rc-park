#!/usr/bin/env python3
"""test_dach_veto_traufe.py - DOM1-Veto darf den DACHUEBERSTAND nicht abschneiden (tools/dach_profil_wolke.dom1_veto + dom1_kachel.dom1_bilinear(klippe), 21.11.2026).
Anlass Schwabentor-1120, Kettenlauf 1121q: Handstand zeltdach_ueberstand 0,9 m -> 0,12 m (1121p noch PASST). Ursache: bauplan_dachprofil_veto (Commit 6aa5fc9ac) interpolierte
das 1-m-DOM1 bilinear ueber die Traufkante (Dachzelle 37 m neben Strassenzelle 0 m) - die Isolinie lag auf der Wand statt an der Traufkante, 56 Eingriffe, die Traufscheiben
wurden 0,7-2,4 m nach innen gesetzt. Fix: Klippen-Zellen (Ecken-Spanne > klippe) bekommen den hoeheren Wert - das Veto schneidet nur, was der Laser ausschliesst.
Synthetisch: echtes 1-m-Raster (Kachel im Cache von dom1_kachel), Zeltdach Wand halb 6,0 m + Ueberstand 0,9 m (flacher Aufschiebling +0,3 m), Traufe 37 m, Neigung 1,4, Rahmen rasterparallel (Schwabentor d = (-0,03, 1,0), 1,7 Grad: die Kante hat dann ueberall dieselbe Rasterphase; schraeg findet das Maximum entlang der Kante
immer eine guenstige Phase und der Fehler verschwindet), Traufkante 0,4 m hinter der letzten Dachzellen-Mitte.
  T7 mit Klippe bleibt der Ueberstand auch bei 1,7 / 14 / 33 Grad Drehung und verschobenem Rahmen erhalten (0,9 +-0,15).
  T1 Traufscheibe mit richtigem Ueberstand bleibt (mit Klippe), T2 ohne Klippe (alter Stand) wird sie geschnitten = Rueckschritt reproduziert,
  T3 Ueberstand wie tools/hand_vergleich.py gemessen ~0,9 (+-0,15), T4 Dachkoerper-Scheibe 1,2 m zu breit wird weiter auf die Isolinie gesetzt (Veto fuer Breite bleibt),
  T5 Traufscheibe 2,0 m zu breit (ausserhalb jeder Laserzelle) wird weiter geschnitten, T6 auf glatter Flaeche ist klippe = bilinear."""
import os, sys, copy, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dom1_kachel
from dach_profil_wolke import dom1_veto

ART = "test_traufe"; WH, UE, ZT, NEI, AUF = 6.0, 0.9, 37.0, 1.4, 0.3; A_ = WH + UE   # Wand halb, Ueberstand, Traufhoehe, Neigung (m je m), Anstieg des flachen Aufschieblings
E0, N0 = 500500.0, 5000500.0                                                     # Rahmen-Ursprung in UTM (Rahmen = UTM verschoben)
def aufbau(grad, cc):
    """Rahmen (d, n, c) und synthetische DOM1-Kachel: Pixelmitten auf ganzen UTM-Metern + 0,5 (wie LGL), 1 m Raster, Wert = Oberflaeche an der Pixelmitte."""
    w = np.radians(grad); d = np.array([np.cos(w), np.sin(w)]); n = np.array([-np.sin(w), np.cos(w)]); c = np.array(cc, float)
    def dach(x, y):                                                              # wahre Oberflaeche (Zeltdach bis 45 m, Strasse 0)
        q = np.c_[x, y] - c; r = np.maximum(np.abs(q @ d), np.abs(q @ n))     # Ueberstand als flacher Aufschiebling (Schwabentor-DOM1: Zellen 37,1 m von r 6,0 bis 6,75)
        z = np.where(r > WH, ZT + AUF * (A_ - r) / UE, np.minimum(ZT + AUF + NEI * (WH - r), 45.0)); z[r > A_] = 0.0; return z
    xc, yc = E0 - 39.5, N0 + 39.5; jj, ii = np.meshgrid(np.arange(80), np.arange(80)); Ec, Nc = xc + jj, yc - ii
    dom1_kachel._cache[(ART, int(E0 // 1000), int(N0 // 1000))] = (dach((Ec - E0).ravel(), (Nc - N0).ravel()).reshape(80, 80).astype(np.float32), xc, yc, "synthetisch")
    return c, d, n
c, d, n = aufbau(0.0, (0.0, 0.0))
laser = lambda kl: (lambda x, y: dom1_kachel.dom1_bilinear(E0 + np.asarray(x), N0 + np.asarray(y), ART, klippe=kl))
def scheiben():                                                                  # Wolkenprofil im Rahmen (u = d, v = n), wahr: Traufe bis A_, darueber Dachflaeche
    P = [[ZT, -A_, A_, -A_, A_, 100, []]]
    for z in np.arange(ZT + 0.5, 44.6, 0.5): h = WH - (z - ZT - AUF) / NEI; P.append([float(z), -h, h, -h, h, 100, []])
    return P
def ue_hand(P):                                                                  # wie tools/hand_vergleich.py (Traufzone 2 m, zwei mittlere Seiten, Maximum)
    un = [s for s in P if s[0] <= P[0][0] + 2.0]
    return max(sum(sorted([-s[1] - WH, s[2] - WH, -s[3] - WH, s[4] - WH])[1:3]) / 2 for s in un)
F = []
def chk(b, txt):
    print(("    ok   " if b else "FEHLER   ") + txt); F.append(not b)

P0 = scheiben(); P = copy.deepcopy(P0); E = dom1_veto(P, c, d, n, laser(3.0), tol=0.3)
chk(all(abs(P[0][i] - P0[0][i]) < 1e-9 for i in range(1, 5)), f"T1 Traufscheibe mit Ueberstand {UE} m bleibt mit Klippe ({sum(e['z'] == ZT for e in E)} Eingriffe an der Traufe)")
Q = copy.deepcopy(P0); dom1_veto(Q, c, d, n, laser(None), tol=0.3)
chk(ue_hand(Q) < UE - 0.3, f"T2 ohne Klippe (Veto Version 1) wird der Ueberstand abgeschnitten: {ue_hand(Q):.2f} m (Rueckschritt 1121q reproduziert)")
chk(abs(ue_hand(P) - UE) <= 0.15, f"T3 Ueberstand wie hand_vergleich gemessen {ue_hand(P):.2f} m (Soll {UE} +-0,15)")
R = copy.deepcopy(P0); k = 6; R[k][2] += 1.2; dom1_veto(R, c, d, n, laser(3.0), tol=0.3)
chk(abs(R[k][2] - P0[k][2]) < 0.2, f"T4 Dachkoerper z {R[k][0]:.1f}: +d 1,2 m zu breit -> {R[k][2]:.2f} (Isolinie {P0[k][2]:.2f}, Veto fuer die Breite bleibt)")
S = copy.deepcopy(P0); S[0][1] -= 2.0; dom1_veto(S, c, d, n, laser(3.0), tol=0.3)
chk(S[0][1] > P0[0][1] - 2.0 + 0.5, f"T5 Traufscheibe 2,0 m zu breit wird weiter geschnitten (-d {P0[0][1] - 2.0:.2f} -> {S[0][1]:.2f})")
x = np.random.default_rng(1).uniform(-4, 4, 500); y = np.random.default_rng(2).uniform(-4, 4, 500)
chk(np.allclose(laser(3.0)(x, y), laser(None)(x, y), equal_nan=True), "T6 auf der Dachflaeche (keine Klippe) ist klippe = bilinear")
for grad, cc in ((1.7, (0.0, 0.0)), (14.0, (0.37, 0.61)), (33.0, (-0.21, 0.44))):
    c, d, n = aufbau(grad, cc); P = scheiben(); dom1_veto(P, c, d, n, laser(3.0), tol=0.3)
    chk(abs(ue_hand(P) - UE) <= 0.15, f"T7 Drehung {grad:.1f} Grad, Rahmen {cc}: Ueberstand {ue_hand(P):.2f} m (Soll {UE} +-0,15)")
print("test_dach_veto_traufe: " + ("bestanden" if not any(F) else f"{sum(F)} FEHLER")); sys.exit(1 if any(F) else 0)
