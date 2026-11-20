#!/usr/bin/env python3
"""Fester Test fuer modell_zerlegen.stuecke: zwei Bildgruppen ohne gemeinsame Punkte in EINEM Modell (Martinstor-Fall 20.11.) muessen getrennt werden;
eine schwache Bruecke (< min_punkte gemeinsame Punkte) trennt, eine starke verbindet."""
import os, sys
from types import SimpleNamespace as N
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import modell_zerlegen as Z

def modell(bruecke):
    pts = {}; k = 0
    for grp in ([1, 2, 3, 4], [5, 6, 7]):
        for _ in range(40): pts[k] = N(track=N(elements=[N(image_id=i) for i in grp])); k += 1
    for _ in range(bruecke): pts[k] = N(track=N(elements=[N(image_id=4), N(image_id=5)])); k += 1
    return N(images={i: None for i in range(1, 8)}, points3D=pts)

s = Z.stuecke(modell(0)); assert [len(x) for x in s] == [4, 3], s
s = Z.stuecke(modell(10), min_punkte=15); assert [len(x) for x in s] == [4, 3], "schwache Bruecke haette trennen muessen"
s = Z.stuecke(modell(20), min_punkte=15); assert [len(x) for x in s] == [7], "starke Bruecke haette verbinden muessen"
print("ok: unverbundene Stuecke getrennt, Bruecken-Schwelle greift")
