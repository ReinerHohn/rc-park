#!/usr/bin/env python3
"""durchblick_grundriss_kopplung_1122.py <seiten_modelle_kopplung.json> <ausrichtung_kopplung.json> <objekt.json> <bild.png> - Grundriss (Wandband z 1,5-9 m) beider Teile
nach der Eck-Kopplung ueber LoD2 (Zielgebaeude rot, Nachbarn grau), Teil 0 blau, Teil 1 orange, Kameras als Punkte. Lage je Teil wie wand_dicke_tor (sim3_meter)."""
import os, sys, json, numpy as np, cv2
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
import wand_dicke_tor as WD, wolke_grundriss_pruefen as WG
sm, au, obj_p, aus = sys.argv[1:5]; obj = json.load(open(obj_p))
P, I = WD.teile_laden(json.load(open(sm)), json.load(open(au)))
LB = [(b["id"] == obj["lod2"]["id"], [np.asarray(g)[:, :2] for g in b["ground"]]) for b in WG.grundrisse(obj, 60.0)]
zg = np.vstack([g for z, gs in LB if z for g in gs]); c = zg.mean(0); R = 25.0; S = 900 / (2 * R)
px = lambda xy: np.round((np.asarray(xy) - c + R) * S * np.array([1, -1]) + np.array([0, 900])).astype(int)
img = np.full((900, 900, 3), 255, np.uint8)
for z, gs in LB:
    for g in gs: cv2.polylines(img, [px(g).reshape(-1, 1, 2)], True, (0, 0, 220) if z else (170, 170, 170), 3 if z else 1)
farbe = {0: (200, 90, 20), 1: (0, 140, 255)}
for i, (k, X) in enumerate(sorted(P.items())):
    w = (X[:, 2] > 1.5) & (X[:, 2] < 9); q = px(X[w][:, :2]); ok = (q >= 0).all(1) & (q < 900).all(1)
    for x, y in q[ok]: img[y, x] = farbe[i]
cv2.putText(img, "Teil 0 blau, Teil 1 orange (Eck-Kopplung), LoD2 rot", (10, 25), 0, 0.6, (0, 0, 0), 1)
cv2.imwrite(aus, img); print(I, "->", aus)
