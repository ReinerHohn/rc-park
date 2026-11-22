#!/usr/bin/env python3
"""Test seiten_eck_koppeln (22.11.2026, verallgemeinert): Kopplungs-Pruefung (stimmig / Zufall / Verformung / zu wenig), Brueckenwahl mit mehreren Teilen
(Martinstor ohne Bruecke, Verwechslung 0-1 abgelehnt, Paar ganz in einem Teil und Stueck an nur einem Teil zaehlen nicht), staerkster Spannbaum, Kreisschluss
(stimmig angenommen, Widerspruch erkannt), ein zusammenhaengendes Modell bleibt unveraendert, Verdrahtung in sfm_seiten_modelle."""
import os, sys, json, sqlite3, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_eck_koppeln as EK
from sim3_robust import matrix, anwenden
fehler = []
def pruef(ok, text): print(("ok   " if ok else "FEHL ") + text); ok or fehler.append(text)
rng = np.random.default_rng(2); X = rng.normal(0, 5, (1500, 3)); c, s = np.cos(0.4), np.sin(0.4); R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]); M = matrix(0.3, R, [2, 1, 0])
ausd = EK.ausdehnung(X); Y = anwenden(M, X) + rng.normal(0, 0.3 * 0.005 * ausd * 0.1, X.shape)
Mk, pr, ok, g = EK.kopplung_pruefen(X, Y, ausd, EK.ausdehnung(Y) * 2)
pruef(ok and np.abs(Mk - M).max() < 0.01 and 0.4 < pr["hebel"] < 0.6, f"stimmige Kopplung angenommen, Hebel gemeldet ({g}, {pr})")
_, pr, ok, g = EK.kopplung_pruefen(X, rng.normal(0, 5, X.shape), ausd)
pruef(not ok, f"Zufallspunkte (andere Flaeche) abgelehnt ({g})")
Yv = anwenden(M, X); Yv[X[:, 0] > 0] *= 1.08                                        # Verformung: eine Haelfte 8 % groesser
_, pr, ok, g = EK.kopplung_pruefen(X, Yv, ausd)
pruef(not ok, f"verformte/unbelegte Kopplung abgelehnt ({g})")
tf = rng.uniform(2, 40, len(X)); Yt = anwenden(M, X) + rng.normal(0, 1, X.shape) * (0.3 * 0.003 * tf)[:, None]; Yt[:150] += rng.normal(0, 3, (150, 3))   # Rest ~ Tiefe, 10 % Ausreisser
Mk, pr, ok, g = EK.kopplung_pruefen(X, Yt, ausd, tiefe=tf)
pruef(ok and pr["fehlermass"] == "tiefe" and np.abs(Mk - M).max() < 0.02, f"tiefenbezogen: Rest ~ Tiefe + 10 % Ausreisser angenommen ({g}, {pr})")
_, pr, ok, g = EK.kopplung_pruefen(X, rng.normal(0, 5, X.shape), ausd, tiefe=tf)
pruef(not ok, f"tiefenbezogen: Zufallspunkte abgelehnt ({g})")
_, pr, ok, g = EK.kopplung_pruefen(X[:50], Y[:50], ausd)
pruef(not ok and "gemeinsame Punkte" in g, "zu wenige gemeinsame Punkte abgelehnt")
# Brueckenwahl, drei Teile
d = __import__("pfade").temp_ordner("test_eck_"); db = os.path.join(d, "t.db"); c_ = sqlite3.connect(db)
c_.executescript("create table images (image_id integer primary key, name text); create table two_view_geometries (pair_id integer primary key, rows integer)")
nam = ["a1", "a2", "b1", "b2", "e1", "n1", "c1", "x1", "x2"]
for i, n in enumerate(nam, 1): c_.execute("insert into images values (?, ?)", (i, n))
for x, y, r in ((5, 6, 300), (1, 2, 500), (3, 6, 50)): c_.execute("insert into two_view_geometries values (?, ?)", (x * EK.MAXID + y, r))
c_.commit(); tv = {"a1": 0, "a2": 0, "b1": 1, "b2": 1, "c1": 2}
sj = dict(durchblick=[dict(a="b1", b="e1", urteil="durchblick"), dict(a="e1", b="a1", urteil="durchblick"), dict(a="a1", b="a2", urteil="durchblick"),
                      dict(a="a2", b="b2", urteil="abgelehnt"), dict(a="c1", b="x1", urteil="durchblick"), dict(a="x1", b="x2", urteil="durchblick")])
ks = EK.kandidaten(sj, tv, db)
pruef(len(ks) == 1 and ks[0]["teile"] == [0, 1] and len(ks[0]["paare"]) == 2 and set(ks[0]["bilder"]) == {"b1", "e1", "a1", "a2", "n1"},
      f"Bruecke: nur Stuecke an >= 2 Teilen, abgelehnte (Verwechslung 0-1) nie, Paar ganz in einem Teil nie, Stueck nur an Teil 2 nicht; Nachbarn dazu ({ks})")
pruef(EK.kandidaten(dict(durchblick=[]), tv, db) == [], "Martinstor-Fall: keine Brueckenpaare -> keine Kopplung")
# Spannbaum + Kreisschluss: Teile 0,1,2; wahre Lagen W[t] (Teil -> Welt); Kante i-j: M = inv(W_i) W_j (j -> i)
W = {0: np.eye(4), 1: matrix(1.1, R, [3, 0, 0]), 2: matrix(0.9, R.T, [0, 4, 1])}; au = {t: 5.0 for t in W}
K = lambda i, j, gu, st=np.eye(4): dict(i=i, j=j, M=np.linalg.inv(W[i]) @ W[j] @ st, guete=gu, sigma=0.003)
kn = [K(0, 1, 900), K(1, 2, 500), K(0, 2, 100)]
lage, weg, baum = EK.spannbaum([0, 1, 2], kn, 0); kr = EK.kreise_pruefen(kn, lage, weg, baum, au)
pruef(baum == {0, 1} and np.allclose(lage[2], W[2]) and len(kr) == 1 and kr[0]["ok"], f"Spannbaum ueber die staerksten Kanten, stimmiger Kreis angenommen ({kr})")
kn[2] = K(0, 2, 100, matrix(1.0, np.array([[np.cos(.05), -np.sin(.05), 0], [np.sin(.05), np.cos(.05), 0], [0, 0, 1]]), [0.2, 0, 0]))
lage, weg, baum = EK.spannbaum([0, 1, 2], kn, 0); kr = EK.kreise_pruefen(kn, lage, weg, baum, au)
pruef(len(kr) == 1 and not kr[0]["ok"] and kr[0]["drehung_grad"] > 2, f"Kreisschluss-Widerspruch (3 Grad) erkannt ({kr})")
o = os.path.join(d, "ein"); rc = EK.main([db, os.path.join(d, "x.json"), d, "--aus", o, "--teil", "0=/gibt/es/nicht"]); ej = json.load(open(os.path.join(o, "eck.json")))
pruef(rc == 2 and "teile" not in ej and "unveraendert" in ej["urteil"], "ein zusammenhaengendes Modell (ein Teil): Stufe aendert nichts (rc 2, keine Lage)")
src = open(os.path.join(T, "sfm_seiten_modelle.py")).read()
pruef("seiten_eck_koppeln.py" in src and "weg=\"eckmodell\"" in src and "RCPARK_ECK_KOPPELN" in src and src.index("seiten_vereinen.py\"), A[\"modell\"]") < src.index("eck_stufe(os.path"),
      "Verdrahtung in sfm_seiten_modelle (abschaltbar, erst nach der Klappung)")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
