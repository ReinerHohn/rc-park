#!/usr/bin/env python3
"""test_seiten_bruecke_kette.py - Befund Kette 1122q (23.11.2026): Suedseite (Teil 1) nicht gebaut, Fernfotos abgeschnitten.
Ursache 1: die Kette rief tools/seiten_erkennen.py nie mit --durchblick auf -> seiten.json 'durchblick' leer -> Eck-Kopplung 'keine bestaetigten Brueckenpaare'
           -> GPS-Weg -> Teil 1 weggelassen. Fix: sfm_seiten_vorstufe gibt standardmaessig --durchblick-getrennt (Paare melden + in db_seiten behalten,
           Teile NICHT vereinen - ein Mapper ueber die duenne Bruecke knickte 1122 um 16-25 Grad).
Ursache 2: Fernsicht-Gruppe (10 Fernfotos) hatte 11 Bilder < --min-bilder 12 -> Pruefer sah sie nie -> keine 'unklare' Verbindung -> --streng schnitt sie ab
           -> lage_frueh nur Nah-GPS (+9,9 Grad x0,902). Fix: fernsicht_behalten nimmt dann die staerkste ungepruefte Verbindung.
Vorgespielte Mini-Datenbank (zwei Bildteile + ein Uebereck-Paar), Attrappen statt Unterprozess. Ohne GPU, ohne Bilder."""
import sys, os, json, sqlite3
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_erkennen as S, sfm_seiten_vorstufe as SV, pfade

f = 0
def pruefe(name, ok):
    global f; print(("  ok    " if ok else "  FEHLER ") + name); f += 0 if ok else 1

# ---------- 1 Fernsicht-Regel: Gruppe, die der Pruefer nie sah
verb = [dict(a=0, b=1, paare=50, urteil="echt")]
quer = {(0, 5): [None] * 73, (3, 5): [None] * 6, (0, 1): [None] * 50}
beh = S.fernsicht_behalten(verb, {5}, quer)
pruefe("Fernsicht-Gruppe ohne Pruefer-Urteil (1122q Gruppe 26, 11 Bilder): staerkste ungepruefte Verbindung (0, 5) behalten, als 'ungeprueft' gemeldet",
       beh == {(0, 5)} and any(v.get("fernsicht_behalten") and v["urteil"] == "ungeprueft" and (v["a"], v["b"]) == (0, 5) for v in verb))
verb = [dict(a=0, b=5, paare=73, urteil="verwechselt")]
pruefe("Fernsicht-Gruppe mit 'verwechselt'-Urteil: nichts behalten (Pruefer-Urteil bleibt)", S.fernsicht_behalten(verb, {5}, quer) == set())
verb = [dict(a=3, b=5, paare=30, urteil="unklar"), dict(a=0, b=5, paare=20, urteil="echt")]
pruefe("Fernsicht-Gruppe mit 'unklarer' Verbindung: alte Regel (staerkste unklare)", S.fernsicht_behalten(verb, {5}, quer) == {(3, 5)})
pruefe("ohne quer (alter Aufruf) unveraendert: Gruppe ohne Urteil -> nichts", S.fernsicht_behalten([], {5}) == set())

# ---------- 2 --durchblick-getrennt auf einer Mini-Datenbank: Teil A (1-4), Teil B (5-8), Uebereck-Paar 4-5 (300 flaechige Inlier)
d = pfade.temp_ordner("test_bruecke_kette_"); dbp = os.path.join(d, "db.db"); db = sqlite3.connect(dbp)
db.executescript("create table cameras (camera_id integer primary key, model integer, width integer, height integer, params blob, prior_focal_length integer);"
                 "create table images (image_id integer primary key, name text, camera_id integer);"
                 "create table keypoints (image_id integer primary key, rows integer, cols integer, data blob);"
                 "create table matches (pair_id integer primary key, rows integer, cols integer, data blob);"
                 "create table two_view_geometries (pair_id integer primary key, rows integer, cols integer, data blob, config integer);")
db.execute("insert into cameras values (1, 2, 2000, 1500, NULL, 0)")
rng = np.random.default_rng(0); P = rng.uniform([0, 0], [2000, 1500], (400, 2))
for i in range(1, 9):
    k = (P + [20 * i, 5 * i]).astype(np.float32)
    db.execute("insert into images values (?, ?, 1)", (i, f"eigen__{i}.jpg")); db.execute("insert into keypoints values (?, ?, 6, ?)", (i, 400, np.c_[k, np.zeros((400, 4), np.float32)].tobytes()))
def paar(x, y, n):
    ij = np.c_[np.arange(n), np.arange(n)].astype(np.uint32); pid = x * S.MAXID + y
    db.execute("insert into two_view_geometries values (?, ?, 2, ?, 3)", (pid, n, ij.tobytes())); db.execute("insert into matches values (?, ?, 2, ?)", (pid, n, ij.tobytes()))
for A in ((1, 2, 3, 4), (5, 6, 7, 8)):
    for i in A:
        for j in A:
            if i < j: paar(i, j, 400)
paar(4, 5, 300); db.commit(); db.close()
pa = os.path.join(d, "pruefer.json")

def lauf(name, *extra):
    aus = os.path.join(d, name + ".json"); dba = os.path.join(d, name + ".db")
    rc = S.main([dbp, d, "--aus", aus, "--db-aus", dba, "--streng", "--min-bilder", "2", "--min-paare", "1", "--pruefer-aus", pa] + list(extra))
    c = sqlite3.connect(dba); n45 = c.execute("select count(*) from two_view_geometries where pair_id = ?", (4 * S.MAXID + 5,)).fetchone()[0]; c.close()
    return rc, json.load(open(aus)), n45

# Gemeinschaften bestimmen, dann Pruefer-Zwischenstand ohne Urteile (die Bruecke ist eine ungepruefte, schwache Verbindung wie 1122q Gruppe 1 <-> 9)
S.main([dbp, d, "--aus", pa, "--streng", "--min-bilder", "2", "--min-paare", "99", "--trocken"]); g0 = json.load(open(pa))
pruefe("Mini-Datenbank: zwei Gemeinschaften zu je 4 Bildern", g0["groessen"] == [4, 4])
rc, s0, n0 = lauf("ohne")
pruefe("ohne Durchblick (Kette bis 23.11.): zwei Teile, 'durchblick' leer, Brueckenpaar in db_seiten geloescht", len(s0["seiten"]) == 2 and s0["durchblick"] == [] and n0 == 0)
rc, s1, n1 = lauf("getrennt", "--durchblick-getrennt")
pruefe("--durchblick-getrennt: zwei Teile BLEIBEN, Brueckenpaar 4-5 in 'durchblick' gemeldet und in db_seiten behalten (fuer seiten_eck_koppeln)",
       len(s1["seiten"]) == 2 and [(x["a"], x["b"]) for x in s1["durchblick"]] == [("eigen__4.jpg", "eigen__5.jpg")] and n1 == 1 and s1.get("durchblick_getrennt") is True)
rc, s2, n2 = lauf("vereint", "--durchblick")
pruefe("--durchblick (alter Versuch): Teile ueber die Bruecke vereint", len(s2["seiten"]) == 1 and n2 == 1)

# ---------- 3 Verdrahtung in der Kette: sfm_seiten_vorstufe gibt --durchblick-getrennt (Standard), RCPARK_SEITEN_DURCHBLICK=0 aus, =1 vereint
w = os.path.join(d, "w"); img = os.path.join(d, "img"); roh = os.path.join(d, "roh")
for x in (w, img, roh): os.makedirs(x, exist_ok=True)
open(os.path.join(img, "eigen__1.jpg"), "w").close()
rufe = []
def attrappe(cmd, check=False):
    rufe.append(cmd); a = cmd[cmd.index("--aus") + 1]; b = cmd[cmd.index("--db-aus") + 1]
    json.dump(dict(verbindungen=[], seiten=[dict(gruppen=[0], bilder=1)], fremd=[], groessen=[1]), open(a, "w")); open(b, "w").close()
    return type("R", (), dict(returncode=0))()
alt = os.environ.get("RCPARK_SEITEN_DURCHBLICK")
try:
    os.environ.pop("RCPARK_SEITEN_DURCHBLICK", None); SV.seiten(dbp, img, w, roh, lauf=attrappe)
    os.environ["RCPARK_SEITEN_DURCHBLICK"] = "0"; SV.seiten(dbp, img, w, roh, lauf=attrappe)
    os.environ["RCPARK_SEITEN_DURCHBLICK"] = "1"; SV.seiten(dbp, img, w, roh, lauf=attrappe)
    os.environ["RCPARK_SEITEN_DURCHBLICK"] = "1"; SV.seiten(dbp, img, w, roh, lauf=attrappe)
finally:
    if alt is None: os.environ.pop("RCPARK_SEITEN_DURCHBLICK", None)
    else: os.environ["RCPARK_SEITEN_DURCHBLICK"] = alt
pruefe("Vorstufe Standard: seiten_erkennen mit --durchblick-getrennt", len(rufe) >= 1 and "--durchblick-getrennt" in rufe[0] and "--durchblick" not in rufe[0])
pruefe("Vorstufe RCPARK_SEITEN_DURCHBLICK=0: ohne Durchblick, neu gerechnet (Schalter im Stand)", len(rufe) >= 2 and not any(x.startswith("--durchblick") for x in rufe[1]))
pruefe("Vorstufe RCPARK_SEITEN_DURCHBLICK=1: --durchblick (vereint), danach wiederverwendet", len(rufe) == 3 and "--durchblick" in rufe[2])
sys.exit(1 if f else 0)
