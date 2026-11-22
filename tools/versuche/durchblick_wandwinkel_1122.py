#!/usr/bin/env python3
"""durchblick_wandwinkel_1122.py <modell> <kopplung.json|-> <objekt.json> [--schluessel M_b_nach_ausrichtung] - Wandwinkel je LoD2-Kante (wie durchblick_beleg_1122):
Punkte z 1,5-9 m, <= 3 m von der Kante, Hauptrichtung gegen Kante; dazu Kamera-GPS-Abstand (Foto-EXIF, Modellrahmen von objekt.json) fuer Kameras mit Geotag."""
import os, sys, json, math, argparse, numpy as np
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
ap = argparse.ArgumentParser(); ap.add_argument("modell"); ap.add_argument("kopplung"); ap.add_argument("objekt"); ap.add_argument("--schluessel", default="M_b_nach_ausrichtung")
ap.add_argument("--bilder"); a = ap.parse_args()
import pycolmap, wolke_grundriss_pruefen as WG, wand_dicke_tor as WD
r = pycolmap.Reconstruction(a.modell); M = np.asarray(json.load(open(a.kopplung))[a.schluessel]) if a.kopplung != "-" else np.eye(4)
P = np.array([p.xyz for p in r.points3D.values()]) @ M[:3, :3].T + M[:3, 3]
obj = json.load(open(a.objekt)); zid = obj["lod2"]["id"]
for b in WG.grundrisse(obj, 60.0):
    if b["id"] != zid: continue
    for g_ in b["ground"]:
        for p0, p1 in WD.kanten_zusammenfassen(np.asarray(g_)[:, :2]):
            L = float(np.linalg.norm(p1 - p0))
            if L < 4: continue
            e = (p1 - p0) / L; nr = np.array([e[1], -e[0]]); q = P[:, :2] - p0; s = q @ e; d = q @ nr
            w = (P[:, 2] > 1.5) & (P[:, 2] < 9) & (s > 0.5) & (s < L - 0.5) & (np.abs(d) < 3)
            if w.sum() < 30: print(f"{np.round(p0, 2).tolist()}->{np.round(p1, 2).tolist()}: n {int(w.sum())}"); continue
            Q = np.c_[s[w], d[w]]; _, _, Vt = np.linalg.svd(Q - Q.mean(0)); ang = (math.degrees(math.atan2(Vt[0, 1], Vt[0, 0])) + 90) % 180 - 90
            print(f"{np.round(p0, 2).tolist()}->{np.round(p1, 2).tolist()}: {ang:+.1f} Grad, Lage {np.median(d[w]):+.2f} m (n {int(w.sum())})")
if a.bilder:
    from paarvorwahl import gps_aus_exif
    import seiten_gps_vereinen as SG
    print("GPS-Abstand: siehe durchblick_beleg_1122 (Rahmen aus objekt.json)")
