#!/usr/bin/env python3
"""seiten_verbund_meter_1119.py <verbund-ordner> <SFM-AUSRICHTUNG A> <objekt.json> - VERSUCH: Vorderseiten-Modell A (an LoD2 ausgerichtet) + geklappte Rueckseite B;
B um 180 Grad um die senkrechte Achse durch die Mitte des LoD2-Objektgrundrisses drehen -> verbund_meter.npz (Meter, Modellsystem). Gegenprobe: Achse aus dem Dachprofil."""
import sys, os, json, numpy as np, cv2
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T); from sfm_lod2_ausrichten import lod2_ziel
vo, au, ob = sys.argv[1:4]; d = np.load(os.path.join(vo, "verbund.npz")); sy = json.load(open(os.path.join(vo, "symmetrie.json"))); E = np.array(sy["E"])
tr = json.load(open(au))["transformation"]; s = tr["s"]; R = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; t = np.array(tr["t"], float)
m = lambda Xl: ((np.asarray(Xl, float) @ E) - t) @ R / s                           # lokales System des Versuchs -> SfM-System A -> Modellmeter
obj = json.load(open(ob)); L, Tn, Tt, _, _, _, Te = lod2_ziel(obj, 80.0); O = L[Te]; W = O[Tt[Te] == 0]
ax = np.array([(W[:, 0].min() + W[:, 0].max()) / 2, (W[:, 1].min() + W[:, 1].max()) / 2]); print("LoD2-Objekt: x", W[:, 0].min().round(1), W[:, 0].max().round(1), "y", W[:, 1].min().round(1), W[:, 1].max().round(1), "Hoehe", O[:, 2].max().round(1), "-> Achse", ax.round(2))
pa, pbg, ca, cbg = m(d["pa"]), m(d["pb_geklappt"]), m(d["ca"]), None
import numpy.linalg as la
dreh = lambda X: np.c_[2 * ax - X[:, :2], X[:, 2]]
pb = dreh(pbg); cb = dreh(m(np.c_[2 * np.array(sy["achse"]) - d["cb"][:, :2], d["cb"][:, 2]]))      # cb in verbund.npz ist schon um die Versuchsachse gedreht -> zurueck, dann um die LoD2-Achse
# Dachprofil-Gegenprobe: oberes Ende der Dachschraege in A (Punkte 0,5 m unter der hoechsten dichten Stelle) laengs der Blickrichtung
tu = pa[np.hypot(pa[:, 0] - ax[0], pa[:, 1] - ax[1]) < 12]; z9 = np.percentile(tu[:, 2], 99.5); sp = tu[(tu[:, 2] > z9 - 3) & (tu[:, 2] < z9)]
print(f"A: Turmpunkte {len(tu)}, Hoehe 99,5 % {z9:.1f} m (LoD2 {O[:, 2].max():.1f}); oberste 3 m der Dachflaeche liegen {np.median(sp[:, :2], 0) - ax} m neben der LoD2-Achse (Soll ~0)")
np.savez(os.path.join(vo, "verbund_meter.npz"), pa=pa.astype(np.float32), pb=pb.astype(np.float32), pbg=pbg.astype(np.float32), ca=ca.astype(np.float32), cb=cb.astype(np.float32), fa=d["fa"], fb=d["fb"], achse=ax, lod2_wand=W.astype(np.float32))
print("Kameras A Mitte", np.median(ca[:, :2], 0).round(0), "| Kameras B Mitte", np.median(cb[:, :2], 0).round(0))
