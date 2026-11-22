#!/usr/bin/env python3
"""test_haufen_klaeren.py - synthetisch: Grundriss-Tor klaert Strassenhaufen automatisch (tools/haufen_klaeren.py, 22.11.2026).

Doppelwand (versetzte Kopie einer Wand, Band 1,5-9 m lueckenlos) = ROT; Mast, Oberleitung, oben haengender Erker, Sichtstrahl-Faecher = geklaert;
zu duenne eigene Waende (keine Eichung) = nicht geklaert (streng). Belege der echten Faelle im Docstring von haufen_klaeren.py.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import haufen_klaeren as HK

F = 0
def pruef(bed, text):
    global F
    if not bed: F += 1; print("FEHLER", text)
    else: print("ok", text)

rng = np.random.default_rng(1)
def wand(x0, y0, y1, n, zlo=0.0, zhi=12.0, dicke=0.05):                   # senkrechte Wand x = x0, y0..y1
    return np.c_[x0 + rng.normal(0, dicke, n), rng.uniform(y0, y1, n), rng.uniform(zlo, zhi, n)]

eigen = wand(3.7, 9, 21, 150000)                                           # eigene Ostwand (Eichung): 12 m lang, voll
L = HK.blatt_suche(eigen)[0]["laenge_voll_m"]; pruef(L >= 10, f"eigene 12-m-Wand als Blatt erkannt ({L} m)")
# Doppelwand: Kopie 3 m vor der Ostwand
r = HK.klaeren(wand(6.7, 9, 21, 60000), eigen); pruef(not r["geklaert"] and r["urteilsfaehig"], "Doppelwand 3 m vor der Wand bleibt ROT: " + r["befund"])
r = HK.klaeren(wand(6.7, 12, 18, 30000), eigen); pruef(not r["geklaert"], "auch ein 6-m-Stueck versetzter Wand bleibt ROT")
# Umgebung: Masten, Oberleitung (oben), Erker (unten leer), Faecher (schraege Strahlen von Kameras aus)
mast = np.vstack([np.c_[rng.normal(x, 0.08, 3000), rng.normal(y, 0.08, 3000), rng.uniform(0, 9, 3000)] for x, y in [(10, 5), (14, 12), (18, 8)]])
leitung = np.c_[rng.uniform(5, 30, 8000), 10 + rng.normal(0, 0.05, 8000), 7.5 + rng.normal(0, 0.1, 8000)]
erker = wand(5.8, 14, 20, 20000, zlo=6.0, zhi=12.0, dicke=0.1)
cams = rng.uniform([20, -5], [40, 25], (40, 2)); strahlen = []
for c in cams:
    ziel = np.array([4.5, rng.uniform(9, 21)]); t = rng.uniform(0.0, 0.8, 600)[:, None]; zc = 1.6
    p = c + t * (ziel - c); z = zc + t[:, 0] * rng.uniform(-1, 8) + rng.normal(0, 0.3, 600); strahlen.append(np.c_[p, z])
haufen = np.vstack([mast, leitung, erker, np.vstack(strahlen)])
r = HK.klaeren(haufen, eigen); pruef(r["geklaert"] and r["urteilsfaehig"], f"Mast/Oberleitung/Erker/Faecher geklaert ({r['laengstes_haufenblatt_m']} m < {r['grenze_m']} m)")
r = HK.klaeren(np.vstack([haufen, wand(6.7, 9, 21, 60000)]), eigen); pruef(not r["geklaert"], "Umgebung + Doppelwand zusammen bleibt ROT")
# streng: eigene Waende zu duenn -> keine Eichung -> nicht geklaert
r = HK.klaeren(haufen, wand(3.7, 9, 21, 800)); pruef(not r["geklaert"] and not r["urteilsfaehig"], "duenne eigene Wand: nicht urteilsfaehig, nicht geklaert")
r = HK.klaeren(haufen, None); pruef(not r["geklaert"], "ohne Eichpunkte nicht geklaert")
print("FEHLER gesamt", F); sys.exit(1 if F else 0)
