#!/usr/bin/env python3
"""kamera_gelaende.py <ziel> ... - Lot-Runde 22.11.2026: neigt der Kamerahoehen-Term des Feinfits das Modell? (Kamerahoehe gegen KONSTANTES h0, Gelaende aber geneigt)
Je Stand: Ebene durch die Kamerahoehen (Modellrahmen, nahe Strassenkameras) und durch das DGM1 unter den Kameras -> Gefaelle in cm/m (Richtung, in die es steigt)."""
import os, sys, json, math
import numpy as np
T = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, T)
import lage_proben as LP
W = "/home/oem/git/rc-park"


def ebene(xy, z):
    A = np.c_[xy, np.ones(len(xy))]; w = np.ones(len(z))
    for _ in range(5):
        c = np.linalg.lstsq(A * w[:, None], z * w, rcond=None)[0]; r = z - A @ c; s = 1.4826 * np.median(np.abs(r)) + 1e-6; w = 1 / np.maximum(1, np.abs(r) / (2 * s))
    return c


for z_ in sys.argv[1:]:
    obj = json.load(open(f"{W}/modelle/{z_}/objekt.json")); AU = json.load(open(f"{W}/modelle/{z_}/messprotokoll/SFM-AUSRICHTUNG-{z_}.json"))
    S = np.array([k["standort"] for k in AU["kameras"].values() if k.get("standort") is not None], float)
    S = S[np.hypot(S[:, 0], S[:, 1]) < 45]; g = LP.raster(obj, S[:, :2], "dgm1"); ok = np.isfinite(g); S, g = S[ok], g[ok]
    h = S[:, 2] - g; strasse = (h > 0.5) & (h < 3.5)
    ck = ebene(S[strasse, :2], S[strasse, 2]); cg = ebene(S[strasse, :2], g[strasse]); cd = ebene(S[strasse, :2], h[strasse])
    f = lambda c: f"{100 * math.hypot(c[0], c[1]):.1f} cm/m Richtung {math.degrees(math.atan2(c[1], c[0])):+.0f}"
    print(f"{z_}: {strasse.sum()} Strassenkameras (Hoehe ueber DGM1 Median {np.median(h[strasse]):.2f} m); Kameraebene {f(ck)}; DGM1 unter den Kameras {f(cg)}; "
          f"Kamerahoehe ueber DGM1 {f(cd)}")
