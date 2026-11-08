#!/usr/bin/env python3
"""bogen_unterkante.py - Untere Kante des Bogenbandes aus der Wolkenplatte (bogen_aus_wolke.py liefert die Belegung): je Spalte von oben das erste
zusammenhaengende belegte Band, Unterkante = erste leere Zeile danach. Ergebnis z_unter(u) = Laibungslinie (Meter), danach Scheitel/Pfeilerlage je Bogen.
Die Loecher-Methode scheiterte (BS11): Oeffnung haengt unten mit dem leeren Strassenbereich zusammen."""
import os, sys, json, numpy as np, cv2
d = sys.argv[1]; J = json.load(open(os.path.join(d, "bogen_aus_wolke.json"))); im = cv2.imread(os.path.join(d, "platte_loecher.png"), 0) > 127
H, W = im.shape; zell = J["zelle"]; u0 = J["u0"]; z1 = J["z1"]; run = int(0.10 / zell); luecke = int(0.10 / zell); zu = np.full(W, np.nan)
for x in range(W):
    col = im[:, x]; y = 0
    while y < H and not col[y]: y += 1                                   # erste belegte Zeile
    if y >= H: continue
    while y < H:                                                         # Band bis Luecke > 10 cm
        ys = y
        while y < H and col[y]: y += 1
        ye = y
        while y < H and not col[y] and (y - ye) <= luecke: y += 1        # kleine Luecken ueberspringen
        if y >= H or not col[y]: break
    zu[x] = z1 - ye * zell
u = u0 + np.arange(W) * zell; zg = cv2.GaussianBlur(zu.reshape(1, -1).astype(np.float32), (0, 0), 3).ravel()
json.dump(dict(u=np.round(u, 3).tolist(), z_unter=np.round(zu, 3).tolist()), open(os.path.join(d, "unterkante.json"), "w"))
vis = cv2.cvtColor((im * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
for x in range(W - 1):
    if np.isfinite(zu[x]) and np.isfinite(zu[x + 1]): cv2.line(vis, (x, int((z1 - zu[x]) / zell)), (x + 1, int((z1 - zu[x + 1]) / zell)), (0, 0, 255), 2)
cv2.imwrite(os.path.join(d, "unterkante.png"), vis)
# Scheitel = lokale Maxima der geglaetteten Linie (Bogenkronen), Pfeiler = lokale Minima zwischen ihnen
from scipy.signal import find_peaks
pk, _ = find_peaks(np.nan_to_num(zg, nan=0), prominence=0.4, distance=int(1.5 / zell)); tl, _ = find_peaks(-np.nan_to_num(zg, nan=0), prominence=0.4, distance=int(1.5 / zell))
print("Kronen (u, z):", [(round(float(u[i]), 2), round(float(zg[i]), 2)) for i in pk]); print("Pfeiler (u, z):", [(round(float(u[i]), 2), round(float(zg[i]), 2)) for i in tl])
