#!/usr/bin/env python3
"""kanten_zeigen.py - 3D-Linien (kanten_3d.json) ueber ein Foto projizieren. Aufruf: kanten_zeigen.py kanten_3d.json dicht_dir ausrichtung foto out.jpg"""
import sys, json, os, numpy as np, cv2
a = sys.argv[1:]; L = json.load(open(a[0]))["linien"]; K = json.load(open(os.path.join(a[1], "kameras_unverzerrt.json"))); tr = json.load(open(a[2]))["transformation"]
s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float); k = K[a[3]]
im = cv2.imread(os.path.join(a[1], "images", k["bild"])); R = np.array(k["R"]); t = np.array(k["t"]); Km = np.array([[k["fx"], 0, k["cx"]], [0, k["fy"], k["cy"]], [0, 0, 1]])
for l in L:
    P = (np.array([l["p0"], l["p1"]]) * s) @ Ra.T + ta; Pc = P @ R.T + t
    if (Pc[:, 2] < 0.5).any(): continue
    uv = (Pc @ Km.T); uv = uv[:, :2] / uv[:, 2:]; col = (0, 0, 255) if l["n_fotos"] < 6 else (0, 255, 255) if l["n_fotos"] < 12 else (0, 255, 0)
    cv2.line(im, tuple(int(v) for v in uv[0]), tuple(int(v) for v in uv[1]), col, 2)
cv2.imwrite(a[4], im)
