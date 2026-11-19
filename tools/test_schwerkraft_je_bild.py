#!/usr/bin/env python3
"""Fester Test fuer schwerkraft_je_bild.py: synthetisches Bild einer Fassade (senkrechte Kanten) aus einer nach oben geneigten, leicht gerollten Kamera.
Erwartung: 'unten' im Kamerasystem auf 1 Grad genau; ein Bild mit nur waagerechten Kanten bekommt keine Vorgabe; plausibel() lehnt 90-Grad-Faelle ab."""
import os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import schwerkraft_je_bild as S


def drehung(neig, roll):
    a, b = np.radians(neig), np.radians(roll)
    Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]]); Rz = np.array([[np.cos(b), -np.sin(b), 0], [np.sin(b), np.cos(b), 0], [0, 0, 1]]); return Rz @ Rx


f, cx, cy, W, H = 1200.0, 800.0, 600.0, 1600, 1200
R = drehung(-20.0, 4.0)                                                       # Welt: x rechts, y unten, z vorwaerts; Kamera 20 Grad nach oben geneigt, 4 Grad gerollt
proj = lambda X: (lambda c: (f * c[0] / c[2] + cx, f * c[1] / c[2] + cy))(R @ X)
im = np.full((H, W), 200, np.uint8)
for x in np.linspace(-9, 9, 19):                                              # senkrechte Kanten (Fensterleibungen) in 20 m Abstand, 0-30 m hoch
    p0, p1 = proj(np.array([x, 2.0, 20.0])), proj(np.array([x, -30.0, 20.0])); cv2.line(im, tuple(int(v) for v in p0), tuple(int(v) for v in p1), 30, 3, cv2.LINE_AA)
vp, n = S.fluchtpunkt_senkrecht(im, np.random.default_rng(0)); assert vp is not None and n >= 12, f"kein Fluchtpunkt ({n} Linien)"
d = S.unten_kamera(vp, f, cx, cy); wahr = R @ np.array([0, 1.0, 0]); w = np.degrees(np.arccos(np.clip(d @ wahr, -1, 1)))
assert w < 1.0, f"Schwerkraft {w:.2f} Grad daneben"
assert S.plausibel(d), "echter Fall als unplausibel verworfen"
assert not S.plausibel(np.array([0.99, 0.1, 0.0])), "90-Grad-Fall (waagerechte Linien) nicht verworfen"
leer = np.full((H, W), 200, np.uint8)
for y in np.linspace(100, 1100, 12): cv2.line(leer, (100, int(y)), (1500, int(y)), 30, 3)
vp2, n2 = S.fluchtpunkt_senkrecht(leer, np.random.default_rng(0)); assert vp2 is None, "Bild ohne Senkrechte bekam eine Vorgabe"
print(f"ok: Schwerkraft {w:.2f} Grad neben der Wahrheit ({n} Linien), Filter greifen")
