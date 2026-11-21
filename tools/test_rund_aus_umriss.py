#!/usr/bin/env python3
"""test_rund_aus_umriss.py - fester synthetischer Test fuer tools/rund_aus_umriss.py (21.11.2026).
Zylinder r 1,50 m (Mitte 0,3 / -0,2) mit Steinfugen-Textur vor gestreiftem Hintergrund, 14 Kameras im Kreis, Bilder analytisch gerendert.
Startwert wie aus der Wolke: r 1,75 m, Mitte 0,25 m daneben. Soll: r auf 3 cm, Mitte auf 5 cm, Oberkante 8 m +- 0,5 m. Ohne Dateien, < 30 s."""
import sys, os, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv2, rund_aus_umriss as RU, flaeche_ortho as FO

CX, CY, R, ZT = 0.3, -0.2, 1.5, 8.0
W, Hh, F = 480, 640, 560.0
rng = np.random.default_rng(1)


def kamera(az, d, h):
    C = np.array([CX + d * math.cos(az), CY + d * math.sin(az), h]); ziel = np.array([CX, CY, 4.0]); zv = ziel - C; zv /= np.linalg.norm(zv)
    xv = np.cross(zv, [0, 0, 1.0]); xv /= np.linalg.norm(xv); yv = np.cross(zv, xv); Rm = np.stack([xv, yv, zv]); t = -Rm @ C
    return dict(rvec=cv2.Rodrigues(Rm)[0].ravel().tolist(), t=t.tolist(), f_px=F, cx=W / 2, cy=Hh / 2, k1=0.0), C, Rm


def render(C, Rm):
    u, v = np.meshgrid(np.arange(W) + 0.5, np.arange(Hh) + 0.5); d = np.stack([(u - W / 2) / F, (v - Hh / 2) / F, np.ones_like(u)], -1) @ Rm
    ox, oy = C[0] - CX, C[1] - CY; a = d[..., 0] ** 2 + d[..., 1] ** 2; b = 2 * (ox * d[..., 0] + oy * d[..., 1]); c = ox * ox + oy * oy - R * R
    disc = b * b - 4 * a * c; t = (-b - np.sqrt(np.maximum(disc, 0))) / (2 * a); z = C[2] + t * d[..., 2]
    hit = (disc > 0) & (t > 0) & (z > 0) & (z < ZT)
    phi = np.arctan2(oy + t * d[..., 1], ox + t * d[..., 0])
    stein = 150 + 40 * ((np.floor(z / 0.35) % 2) == 0) - 60 * ((np.abs((z / 0.35) % 1 - 0.5) > 0.45) | (np.abs((phi * R / 0.6) % 1 - 0.5) > 0.46))
    hinter = 90 + 50 * (np.floor(u / 23) % 2) + 30 * np.sin(v / 17)            # Streifen = viele starke Kanten neben dem Umriss
    img = np.where(hit, stein, hinter) + rng.normal(0, 6, u.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


bilder = []
for i in range(14):
    c, C, Rm = kamera(2 * math.pi * i / 14 + 0.1, 14 + 3 * (i % 3), 1.6 + (i % 4) * 2)
    im = render(C, Rm); B = RU.Bild(c, im, (0, 0, W, Hh), FO.projektion); B.Cxy = C[:2]; B.C = C; bilder.append(B)
zs = list(np.round(np.arange(0.75, ZT + 3.0, 0.5), 2))
U = RU.vermessen(bilder, (CX + 0.25, CY - 0.1, 1.75), zs)
ok_ = U and abs(U["r"] - R) < 0.03 and math.hypot(U["x"] - CX, U["y"] - CY) < 0.05
ob = RU.oberkante(U["profil"]) if U else None
ok_ = ok_ and ob is not None and abs(ob - ZT) <= 0.5
print(("OK" if ok_ else "FEHLER") + f" rund_aus_umriss: r {U['r'] if U else None} (Soll {R}), Mitte {U['x'] if U else None}/{U['y'] if U else None} (Soll {CX}/{CY}), Oberkante {ob} (Soll {ZT}), "
      f"Fotos {U['fotos'] if U else 0}")
# Einseitige Blickrichtungen (wie Schwabentor: 112 Fotos links, 31 rechts): 10 Kameras dicht in einem 40-Grad-Faecher, 4 gegenueber
bilder2 = []
for i, az in enumerate(list(np.linspace(0.2, 0.9, 10)) + [3.0, 3.6, 4.2, 4.8]):
    c, C, Rm = kamera(az, 13 + 2 * (i % 3), 1.6 + (i % 4) * 2); B = RU.Bild(c, render(C, Rm), (0, 0, W, Hh), FO.projektion); B.Cxy = C[:2]; B.C = C; bilder2.append(B)
U2 = RU.vermessen(bilder2, (CX - 0.3, CY + 0.2, 1.8), zs)
ok2 = U2 and abs(U2["r"] - R) < 0.04 and math.hypot(U2["x"] - CX, U2["y"] - CY) < 0.06
print(("OK" if ok2 else "FEHLER") + f" rund_aus_umriss einseitig: r {U2['r'] if U2 else None}, Mitte {U2['x'] if U2 else None}/{U2['y'] if U2 else None}")
# Profil-Regeln: Glaetten (Einzelausreisser), Traufe = groesster Radius des Ueberstands, sonst Verjuengung
pr = [[z, r, 9, 0.4] for z, r in [(1, 1.6), (1.5, 1.6), (2, 2.4), (2.5, 1.6), (3, 1.6), (3.5, 1.0), (4, 1.6), (4.5, 1.6), (5, 1.85), (5.5, 1.9), (6, 1.85), (6.5, 1.4), (7, 1.1), (7.5, 0.9)]]
g = RU.glaetten(pr); t1 = RU.traufe(g, 0.5); t2 = RU.traufe([[z, r, 9, .4] for z, r in [(1, 1.6), (2, 1.6), (3, 1.6), (4, 1.6), (5, 1.2), (6, 1.0), (7, 0.8)]], 1.0)
ok3 = max(p[1] for p in g[:5]) < 1.7 and t1 == 5.0 and t2 == 4.5   # Traufe: nach Glaettung 5,0-6,0 gleich r 1,85 -> unterste = Unterkante Ueberstand
print(("OK" if ok3 else "FEHLER") + f" rund_aus_umriss Profil: geglaettet max unten {max(p[1] for p in g[:5])}, Traufe Ueberstand {t1} (Soll 5.0), Traufe Verjuengung {t2} (Soll 4.5)")
sys.exit(0 if (ok_ and ok2 and ok3) else 1)
