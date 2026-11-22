#!/usr/bin/env python3
"""Test seiten_eck_koppeln (22.11.2026): Kopplungs-Pruefung (stimmig / Zufall / Massstab-Verformung), Brueckenwahl (Martinstor ohne Bruecke, Verwechslung 0-1 abgelehnt,
Paar ganz in einem Teil zaehlt nicht), Verdrahtung in sfm_seiten_modelle."""
import os, sys, json, sqlite3, tempfile, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_eck_koppeln as EK
from sim3_robust import matrix, anwenden
fehler = []
def pruef(ok, text): print(("ok   " if ok else "FEHL ") + text); ok or fehler.append(text)
rng = np.random.default_rng(2); X = rng.normal(0, 5, (1500, 3)); c, s = np.cos(0.4), np.sin(0.4); R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]); M = matrix(0.3, R, [2, 1, 0])
ausd = EK.ausdehnung(X); Y = anwenden(M, X) + rng.normal(0, 0.3 * 0.005 * ausd * 0.1, X.shape)
Mk, pr, ok, g = EK.kopplung_pruefen(X, Y, ausd)
pruef(ok and np.abs(Mk - M).max() < 0.01, f"stimmige Kopplung angenommen ({g}, {pr})")
_, pr, ok, g = EK.kopplung_pruefen(X, rng.normal(0, 5, X.shape), ausd)
pruef(not ok, f"Zufallspunkte (andere Flaeche) abgelehnt ({g})")
Yv = anwenden(M, X); Yv[X[:, 0] > 0] *= 1.08                                        # Verformung: ferne Haelfte 8 % groesser
_, pr, ok, g = EK.kopplung_pruefen(X, Yv, ausd)
pruef(not ok, f"verformte/unbelegte Kopplung abgelehnt ({g})")
_, pr, ok, g = EK.kopplung_pruefen(X[:50], Y[:50], ausd)
pruef(not ok and "gemeinsame Punkte" in g, "zu wenige gemeinsame Punkte abgelehnt")
# Brueckenwahl
d = __import__("pfade").temp_ordner("test_eck_"); db = os.path.join(d, "t.db"); c_ = sqlite3.connect(db)
c_.executescript("create table images (image_id integer primary key, name text); create table two_view_geometries (pair_id integer primary key, rows integer)")
for i, n in enumerate(["a1", "a2", "b1", "b2", "e1", "n1"], 1): c_.execute("insert into images values (?, ?)", (i, n))
for x, y, r in ((5, 6, 300), (1, 2, 500), (3, 6, 50)): c_.execute("insert into two_view_geometries values (?, ?)", (x * EK.MAXID + y, r))
c_.commit(); A, B = {"a1", "a2"}, {"b1", "b2"}
sj = dict(durchblick=[dict(a="b1", b="e1", urteil="durchblick"), dict(a="e1", b="a1", urteil="durchblick"), dict(a="a1", b="a2", urteil="durchblick"),
                      dict(a="a2", b="b2", urteil="abgelehnt")])
br, liste = EK.eckbilder(sj, A, B, db)
pruef(len(br) == 2 and set(liste) == {"b1", "e1", "a1", "a2", "n1"}, f"Bruecke: nur Paare ueber die Teilgrenze, abgelehnte (Verwechslung 0-1) nie; starke Nachbarn dazu ({liste})")
pruef(EK.eckbilder(dict(durchblick=[]), A, B, db) == ([], []), "Martinstor-Fall: keine Brueckenpaare -> keine Kopplung")
src = open(os.path.join(T, "sfm_seiten_modelle.py")).read()
pruef("seiten_eck_koppeln.py" in src and "weg=\"eckmodell\"" in src and "RCPARK_ECK_KOPPELN" in src, "Verdrahtung in sfm_seiten_modelle (abschaltbar)")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
