#!/usr/bin/env python3
"""kamera_guete_gegenprobe.py - Sichtprobe der Kameraguete: je Foto SfM-Beobachtung (gruen), Projektion der LOO-Punkte mit gespeicherter Pose (blau) und mit LOO-Pose (rot),
Gitter-v12-Segmente mit gespeicherter lot2-Pose (gelb). Gute Fotos: gruen/blau/rot decken sich. Aufruf: venv-seg python -I tools/kamera_guete_gegenprobe.py NAME [NAME...]"""
import sys, os, json, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kamera_guete_lot2 import Szene, verzerre, D
from kamera_linienfein import segment_punkte
S = Szene(); OUT = "/home/oem/git/rc-park/modelle/kaufhaus_grob3/audit/kamera_guete"; os.makedirs(OUT, exist_ok=True)
P, _, _ = segment_punkte(schritt=0.3)
for name in sys.argv[1:]:
    iid = S.name2id[name]; v = S.im[iid]; e = S.loo(iid, rng=np.random.default_rng(0)); img = cv2.imread(f"{D}/bilder_alle/{name}"); sc = 0.3; img = cv2.resize(img, None, fx=sc, fy=sc)
    if e is not None:
        X = e["X"]; par = v["par"]
        for R, t, col in ((v["R"], v["t"], (255, 80, 0)), (e["R"], e["t"], (0, 0, 255))):
            Xc = X @ R.T + t; px = verzerre(Xc[:, :2] / Xc[:, 2:3], par) * sc
            for p in px:
                if 0 <= p[0] < img.shape[1] and 0 <= p[1] < img.shape[0]: cv2.circle(img, (int(p[0]), int(p[1])), 3, col, 1)
        uv = verzerre(e["u"], par) * sc
        for p in uv: cv2.circle(img, (int(p[0]), int(p[1])), 1, (0, 255, 0), -1)
    k = S.kam[name]; R = np.array(k["Rn"]); t = np.array(k["tn"]); Xc = P @ R.T + t; ok = Xc[:, 2] > 2
    u = Xc[ok, :2] / Xc[ok, 2:3]; k1 = k["params"][3]; px = (k["f"] * u * (1 + k1 * (u * u).sum(1)[:, None]) + [k["cx"], k["cy"]]) * sc
    for p in px:
        if 0 <= p[0] < img.shape[1] and 0 <= p[1] < img.shape[0]: cv2.circle(img, (int(p[0]), int(p[1])), 1, (0, 220, 255), -1)
    cv2.imwrite(f"{OUT}/{name[:-4]}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80]); print(name, "->", f"{OUT}/{name[:-4]}.jpg")
