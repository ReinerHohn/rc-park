#!/usr/bin/env python3
"""test_grundriss_geklaert.py - am Foto geklaerte Strassenhaufen (objekt.json grundriss_haufen_geklaert) duerfen eine falsche Lage nicht durchwinken.

Anlass 22.11.2026 (schwabentor-1122, Lage 8 Grad / x0,92 neben GPS und LoD2): der Strassenhaufen der versetzten Ost-/Nordwaende
(348 813 Punkte, Mitte 20,7/8,8) lag 0,5 m neben dem in schwabentor-1120 geklaerten Platz-Haufen (44 105 Punkte, Mitte 20,7/9,3, Radius 6 m).
Ein mitkopierter Eintrag haette Tor A (das einzige harte Grundriss-Tor) bestehen lassen. Regel: Eintrag mit "punkte" gilt nur bis 2x so viele Punkte.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wolke_grundriss_pruefen import haufen_geklaert

F = 0
def pruef(bed, text):
    global F
    if not bed: F += 1; print("FEHLER", text)
    else: print("ok", text)

gekl_1120 = [dict(mitte=[20.7, 9.3], radius_m=6.0, punkte=44105, befund="Platz-Umgebung")]
pruef(haufen_geklaert(dict(mitte=[20.7, 9.3], punkte=44105), gekl_1120) == "Platz-Umgebung", "1120 selbst: geklaerter Haufen bleibt geklaert (Kontrolle nicht strenger)")
pruef(haufen_geklaert(dict(mitte=[21.0, 9.0], punkte=80000), gekl_1120) == "Platz-Umgebung", "etwas mehr Punkte (neue dichte Wolke, < 2x) bleibt geklaert")
pruef(haufen_geklaert(dict(mitte=[20.7, 8.8], punkte=348813), gekl_1120) is None, "1122: 7,9x so grosser Haufen an derselben Stelle gilt NICHT als geklaert")
pruef(haufen_geklaert(dict(mitte=[30.0, 9.3], punkte=1000), gekl_1120) is None, "anderer Ort (> Radius) nicht geklaert")
alt = [dict(mitte=[-12.2, 3.8], radius_m=6.0, befund="Erker Nachbarhaus")]      # schwab_v3: Eintrag ohne 'punkte' -> altes Verhalten (nur Lage)
pruef(haufen_geklaert(dict(mitte=[-11.9, 3.5], punkte=2795), alt) == "Erker Nachbarhaus", "Eintrag ohne 'punkte' (schwab_v3): wie bisher nur nach Lage")
print("FEHLER gesamt", F); sys.exit(1 if F else 0)
