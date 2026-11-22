#!/usr/bin/env python3
"""durchblick_vereint_ply_1122.py <seiten_modelle.json> <ausrichtung.json> <aus.ply> [n_max] - Teile per wand_dicke_tor.teile_laden (sim3_meter) in den Ausrichtungsrahmen
legen und als EINE binaere PLY (PLY_SATZ, ohne Farbe) schreiben - Eingabe fuer wolke_grundriss_pruefen.py."""
import os, sys, json, numpy as np
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
import wand_dicke_tor as WD
from sfm_seiten_modelle import PLY_SATZ
sm, au, aus = sys.argv[1:4]; n_max = int(sys.argv[4]) if len(sys.argv) > 4 else 3000000
P, I = WD.teile_laden(json.load(open(sm)), json.load(open(au)), n_max=n_max); X = np.vstack(list(P.values()))
d = np.zeros(len(X), PLY_SATZ); d["p"] = X[:, :3]; d["n"] = X[:, 3:6]
with open(aus, "wb") as f:
    f.write((f"ply\nformat binary_little_endian 1.0\nelement vertex {len(d)}\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\n"
             f"property float nz\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n").encode()); f.write(d.tobytes())
print(I, len(d), "->", aus)
