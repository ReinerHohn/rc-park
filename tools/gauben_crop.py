#!/usr/bin/env python3
"""gauben_crop.py - Ausschnitt mit Pixelgitter (Originalpixel) um einen Modellpunkt, zum Ablesen von Bildpunkten (Messprotokoll foto_mass).
  gauben_crop.py KAM.json BILDDIR FOTO.jpg X Y Z OUT.jpg [halb_px=350] [skala=2]   (Modellrahmen in m)"""
import sys, json, numpy as np, cv2
kam = json.load(open(sys.argv[1])); k = kam[sys.argv[3]]; X = np.array([float(v) for v in sys.argv[4:7]]); out = sys.argv[7]
h = int(sys.argv[8]) if len(sys.argv) > 8 else 350; sc = float(sys.argv[9]) if len(sys.argv) > 9 else 2.0
x = np.array(k["Rn"]) @ X + np.array(k["tn"]); xn, yn = x[0] / x[2], x[1] / x[2]; k1 = float(k["params"][3]) if len(k.get("params", [])) > 3 else 0.0; r2 = xn * xn + yn * yn
u, v = k["f"] * xn * (1 + k1 * r2) + k["cx"], k["f"] * yn * (1 + k1 * r2) + k["cy"]
im = cv2.imread(f"{sys.argv[2]}/{sys.argv[3]}"); H, W = im.shape[:2]; x0, y0 = int(max(0, u - h)), int(max(0, v - h)); x1, y1 = int(min(W, u + h)), int(min(H, v + h))
c = cv2.resize(im[y0:y1, x0:x1], None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
for gx in range((x0 // 50 + 1) * 50, x1, 50):
    X_ = int((gx - x0) * sc); cv2.line(c, (X_, 0), (X_, c.shape[0]), (0, 255, 255) if gx % 100 == 0 else (0, 160, 160), 1)
    if gx % 100 == 0: cv2.putText(c, str(gx), (X_ + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
for gy in range((y0 // 50 + 1) * 50, y1, 50):
    Y_ = int((gy - y0) * sc); cv2.line(c, (0, Y_), (c.shape[1], Y_), (0, 255, 255) if gy % 100 == 0 else (0, 160, 160), 1)
    if gy % 100 == 0: cv2.putText(c, str(gy), (2, Y_ - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
cv2.imwrite(out, c); print(f"Modellpunkt im Foto ({u:.0f},{v:.0f}); Ausschnitt x {x0}-{x1} y {y0}-{y1}, Faktor {sc}")
