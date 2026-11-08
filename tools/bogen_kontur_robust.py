#!/usr/bin/env python3
"""bogen_kontur_robust.py - Laibungslinie der Bogenoeffnungen aus dem Belegungsbild (bogen_aus_wolke.py: platte_loecher.png, weiss = Wolke, schwarz = leer).
Gegenueber bogen_unterkante.py: (1) Schliessen weisser Einzelpunkte im Leeren (Wolke duenn) mit Radius 8 cm, (2) je Spalte erste LEERE Zeile von oben, die mindestens 1,0 m
zusammenhaengend leer nach unten weiterlaeuft (verwirft Zacken/Pfeilerspitzen), (3) nur Spalten der Oeffnungen behalten (leer >= 1 m), Pfeiler = Luecken in der Linie.
Ausgabe: je Oeffnung Polyline (u, z) in Metern + Kennzahlen (u_links, u_rechts, Scheitel, Spannweite), Bild mit Linie.  KEINE Benennung hier.
  venv-seg/bin/python -I tools/bogen_kontur_robust.py <ordner> [--min-leer 1.0]"""
import os, sys, json, argparse, numpy as np, cv2
ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("--min-leer", type=float, default=1.0); ap.add_argument("--schliessen", type=float, default=0.08); a = ap.parse_args()
J = json.load(open(os.path.join(a.ordner, "bogen_aus_wolke.json"))); im = cv2.imread(os.path.join(a.ordner, "platte_loecher.png"), 0) > 127; zell = J["zelle"]; u0 = J["u0"]; z1 = J["z1"]; H, W = im.shape
leer = (~im).astype(np.uint8); r = max(1, int(a.schliessen / zell)); k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
leer = cv2.morphologyEx(leer, cv2.MORPH_OPEN, k)                       # weisse Einzelpunkte im Leeren entfernen? NEIN: Opening auf 'leer' entfernt DUENNE LEERE Zacken (Spalten < 8 cm); schliesst nichts
weiss_zu = cv2.morphologyEx(im.astype(np.uint8), cv2.MORPH_OPEN, k)    # weisse Streu-Punkte (< 8 cm) entfernen -> geschlossener Leerbereich
leer = (weiss_zu == 0).astype(np.uint8); mind = int(a.min_leer / zell); top = np.full(W, -1)
for x in range(W):
    col = leer[:, x]; y = 0
    while y < H:
        if col[y]:
            e = y
            while e < H and col[e]: e += 1
            if e - y >= mind: top[x] = y; break
            y = e
        else: y += 1
u = u0 + np.arange(W) * zell; z = np.where(top >= 0, z1 - top * zell, np.nan)
segs = []; x = 0
while x < W:
    if top[x] < 0: x += 1; continue
    s = x
    while x < W and top[x] >= 0 and (x == s or abs(top[x] - top[x - 1]) <= int(0.3 / zell)): x += 1
    if (x - s) * zell >= 1.5: segs.append((s, x))
vis = cv2.cvtColor((im * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
for i, (s, e) in enumerate(segs):
    for xx in range(s, e - 1): cv2.line(vis, (xx, top[xx]), (xx + 1, top[xx + 1]), (0, 0, 255), 2)
cv2.imwrite(os.path.join(a.ordner, "kontur_robust.png"), vis)
out = [dict(u_links=round(float(u[s]), 2), u_rechts=round(float(u[e - 1]), 2), spannweite_m=round(float((e - 1 - s) * zell), 2), scheitel_z=round(float(np.nanmax(z[s:e])), 3), u=np.round(u[s:e], 3).tolist(), z=np.round(z[s:e], 3).tolist()) for s, e in segs]
json.dump(out, open(os.path.join(a.ordner, "kontur_robust.json"), "w")); [print({k: v for k, v in o.items() if k not in ("u", "z")}) for o in out]
