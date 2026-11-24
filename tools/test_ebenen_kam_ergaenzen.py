#!/usr/bin/env python3
"""test_ebenen_kam_ergaenzen.py - fester synthetischer Test (24.11.2026, Befund 1122z f02/Ost: 1316 Fotokantenpunkte, 49 frontale SfM-Kameras nicht in kam_wahl)
fuer tools/ebenen_bauplan.frontal_kameras: je Wand werden frontale Kameras aus kam.json ergaenzt.
Wand: o (0,0), d (1,0), n (0,-1) (Normale nach -y), Zone u -5..5, z 0..20. Kameras (f 3000 px, 3000 x 4000):
  A frontal 40 m vor der Wand, Blick auf die Wand            -> GEWAEHLT
  B frontal 60 m, gleicher Blick                             -> GEWAEHLT (A vor B: bessere Aufloesung zuerst)
  C 40 m HINTER der Wand (andere Seite, Blick +y)            -> NICHT
  D vor der Wand, Blick parallel zur Wand (90 Grad)          -> NICHT
  E frontal, aber 200 m (6,7 cm/px > 3 cm/px)                -> NICHT
  F frontal 5 m (Wand nur zum kleinen Teil im Bild)          -> NICHT
  G frontal 40 m, schon in kam_wahl                          -> NICHT doppelt
  n_max = 1 -> nur A. Werte sind Testgeometrie, kein Objektmass. < 2 s."""
import os, sys
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from ebenen_bauplan import frontal_kameras

fehler = []
def pruef(b, t):
    print(("ok    " if b else "FEHLER ") + t, flush=True)
    if not b: fehler.append(t)


def kam(C, ziel, f=3000.0, W=3000, H_=4000):
    C = np.array(C, float); z = np.array(ziel, float) - C; z /= np.linalg.norm(z); up = np.array([0, 0, 1.0])
    x = np.cross(z, up); x /= np.linalg.norm(x); y = np.cross(z, x); R = np.stack([x, y, z])      # Zeilen = Kamera-Achsen in Weltkoordinaten (Rn[2] = Blickrichtung)
    return dict(Rn=R.tolist(), tn=(-R @ C).tolist(), C=C.tolist(), f=f, cx=W / 2, cy=H_ / 2, W=W, H=H_)


e = dict(o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], w=0.0, zone=[-5.0, 5.0, 0.0, 20.0])
K = {"A.jpg": kam([0, -40, 2], [0, 0, 10]), "B.jpg": kam([3, -60, 2], [0, 0, 10]), "C.jpg": kam([0, 40, 2], [0, 0, 10]), "D.jpg": kam([-30, -3, 10], [30, -3, 10]),
     "E.jpg": kam([0, -200, 2], [0, 0, 10]), "F.jpg": kam([0, -5, 1.5], [0, 0, 3]), "G.jpg": kam([-2, -40, 2], [0, 0, 10])}
# Selbstkontrolle der Testkamera: Wandmitte projiziert ins Bild von A
R = np.array(K["A.jpg"]["Rn"]); X = R @ np.array([0, 0, 10.0]) + np.array(K["A.jpg"]["tn"]); pruef(X[2] > 0 and abs(3000 * X[0] / X[2]) < 1500, "Testkamera A sieht die Wandmitte")
g = frontal_kameras(K, e, {"G.jpg": K["G.jpg"]}, n_max=24)
pruef(g[:2] == ["A.jpg", "B.jpg"], f"frontal A, B gewaehlt, beste Aufloesung zuerst ({g})")
for x, grund in (("C.jpg", "hinter der Wand"), ("D.jpg", "Blick parallel zur Wand"), ("E.jpg", "zu grob (> 3 cm/px)"), ("F.jpg", "Wand nur zum Teil im Bild"), ("G.jpg", "schon in kam_wahl")):
    pruef(x not in g, f"{x} nicht gewaehlt ({grund})")
pruef(frontal_kameras(K, e, {}, n_max=1) == ["A.jpg"], "n_max begrenzt")
pruef(frontal_kameras({}, e, {}) == [], "ohne kam.json keine Ergaenzung")
print("FEHLER:", len(fehler)) if fehler else print("alle Pruefungen bestanden")
sys.exit(1 if fehler else 0)
