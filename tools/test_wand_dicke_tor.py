#!/usr/bin/env python3
"""Fester Test (synthetisch, Sekunden) fuer tools/wand_dicke_tor.py (22.11.2026, Nulllauf schwabentor-1122f: Westwand ~3 m dick aus zwei Seitenteilen).
Grundflaeche 10 x 12 m. Teil 0 sieht alle Waende richtig; Teil 1 sieht die Westwand 1,6 m nach aussen versetzt (Doppelwand), die Suedwand richtig, die Nordwand kaum.
Erwartet: West 'doppelwand' (Lageunterschied 1,6 m), Sued 'ok', Nord fuer Teil 1 'kein_urteil' (Teil 0 allein -> ok), rc 3; ein Teil in sich mit zwei Waenden -> 'dick'
(Ursache im Teil, kein Teilversatz), rc 0; nichts gemessen -> rc 2; Vordach-Punkte ueber dem Wandfussband zaehlen nicht; Schalter in gesamtkette."""
import os, sys
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import wand_dicke_tor as WD

rng = np.random.default_rng(3); g = np.array([[-5.0, -6.0], [5.0, -6.0], [5.0, 6.0], [-5.0, 6.0]])


def wand(x0, y0, x1, y1, n, aussen=(0, 0), versatz=0.0, z=(0.5, 12)):
    t = rng.uniform(0, 1, n); P = np.c_[x0 + t * (x1 - x0), y0 + t * (y1 - y0), rng.uniform(*z, n)]; P[:, :2] += versatz * np.asarray(aussen, float) + rng.normal(0, 0.05, (n, 2)); return P


t0 = np.r_[wand(-5, -6, 5, -6, 3000), wand(5, -6, 5, 6, 3000), wand(5, 6, -5, 6, 3000), wand(-5, 6, -5, -6, 3000)]
t1 = np.r_[wand(-5, -6, 5, -6, 3000), wand(-5, 6, -5, -6, 3000, aussen=(-1, 0), versatz=1.6), wand(5, 6, -5, 6, 50),
           wand(-5, -6, 5, -6, 3000, aussen=(0, -1), versatz=2.5, z=(10, 12))]                      # Vordach-Punkte 2,5 m vor der Suedwand, aber ueber dem Band
K = {tuple(k["von"]): k for k in WD.kanten_messen(g, {0: t0, 1: t1})}
west, sued, nord = K[(-5.0, 6.0)], K[(-5.0, -6.0)], K[(5.0, 6.0)]
assert west["urteil"] == "doppelwand" and abs(west["lageunterschied_m"] - 1.6) < 0.1 and west["teile"]["1"]["lage_m"] > 1.4 and abs(west["teile"]["0"]["lage_m"]) < 0.1, f"West: {west}"
assert sued["urteil"] == "ok" and sued["lageunterschied_m"] < 0.1 and sued["dicke_gesamt_m"] < 0.3, f"Sued (Vordach darf nicht zaehlen): {sued}"
assert nord["teile"]["1"]["urteil"] == "kein_urteil" and nord["urteil"] == "ok" and nord["lageunterschied_m"] is None, f"Nord: {nord}"
rc, u = WD.zusammenfassen(list(K.values())); assert rc == 3 and "doppelwand" in u, f"Zusammenfassung: {rc} {u}"
print(f"ok 1: Doppelwand West (Teile {west['lageunterschied_m']} m auseinander, Dicke {west['dicke_gesamt_m']} m), Sued ok trotz Vordach, Nord ohne Beleg von Teil 1")
t2 = np.r_[wand(-5, 6, -5, -6, 3000), wand(-5, 6, -5, -6, 3000, aussen=(-1, 0), versatz=2.5)]       # EIN Teil mit zwei Streifen (Durchfahrtswand oder Geister)
K2 = WD.kanten_messen(g, {1: t2}); w2 = [k for k in K2 if k["von"] == [-5.0, 6.0]][0]
assert w2["urteil"] == "dick" and w2["lageunterschied_m"] is None and WD.zusammenfassen(K2)[0] == 0, f"ein Teil dick: {w2}"
assert WD.zusammenfassen(WD.kanten_messen(g, {0: t0[:10]}))[0] == 2, "ohne Wandbeleg ein Urteil"
print("ok 2: ein Teil in sich dick -> 'dick' (kein Teilversatz), ohne Beleg -> rc 2")
q = open(os.path.join(T, "gesamtkette.py")).read(); assert "wand_dicke_tor.py" in q and "RCPARK_WANDDICKE" in q, "gesamtkette ruft wand_dicke_tor nicht auf"
print("ok 3: Verdrahtung in gesamtkette.py (Stufe tore, nur Messung)")
print("ALLE TESTS BESTANDEN")
