#!/usr/bin/env python3
"""test_seiten_durchblick.py - Stufe 'Durchblick/Umgebung' in tools/seiten_erkennen.py (22.11.2026): einzelne starke Paare verwechselter/unklarer Verbindungen behalten.
Synthetisch (Einblendung, Uhr-Ausschnitt, flaechiges Paar, GPS-Veto, Stufe auf Mini-Datenbank) + Regression aus echten Paaren (tools/testdata/durchblick_paare.json:
schwabentor-1122 Uebereck 1->27->12 = behalten; Einblendung 14-19/9-14, Uhr/Helm 0-1, teilweise Einblendung 9-24, Martinstor 0-2/2-6 = abgelehnt). Ohne GPU, ohne Bilder."""
import sys, os, json, sqlite3, tempfile, argparse
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_erkennen as S

f = 0
def pruefe(name, ok):
    global f; print(("  ok    " if ok else "  FEHLER ") + name); f += 0 if ok else 1

rng = np.random.default_rng(0); WH = (2000, 1500)
# flaechiges Paar: 400 Punkte ueber das ganze Bild, Versatz 150 px
p0 = rng.uniform([0, 0], WH, (400, 2)); p1 = p0 + [150, 20]
m = S.paar_staerke(p0, p1, WH, WH)
pruefe("flaechiges Paar: 400 nicht-statische Inlier, >= 40 Zellen -> durchblick", m["n_eff"] == 400 and m["statisch"] == 0 and min(m["zellen0"], m["zellen1"]) >= 40 and S.durchblick_ok(m)[0] == "durchblick")
# Einblendung: 300 Punkte an derselben Bildstelle in einem Schriftband
e0 = np.c_[rng.uniform(600, 900, 300), rng.uniform(1150, 1250, 300)]
m = S.paar_staerke(e0, e0 + rng.normal(0, 0.5, e0.shape), WH, WH)
pruefe("Einblendung (Schrift an gleicher Bildstelle): statisch, n_eff 0 -> abgelehnt", m["statisch"] == 300 and m["n_eff"] == 0 and S.durchblick_ok(m)[0] == "abgelehnt")
# teilweise Einblendung: 250 echte + 60 statische
m = S.paar_staerke(np.r_[p0[:250], e0[:60]], np.r_[p1[:250], e0[:60]], WH, WH)
pruefe("teilweise Einblendung (> 10 % statisch) -> abgelehnt, Grund Einblendung", S.durchblick_ok(m)[0] == "abgelehnt" and "Einblendung" in S.durchblick_ok(m)[1])
# Uhr-Ausschnitt: 250 Punkte in einem kleinen Bildbereich (Verwechslung findet nur das entworfene Bauteil)
u0 = rng.uniform([800, 200], [1000, 400], (250, 2)); m = S.paar_staerke(u0, u0 + [300, 50], WH, WH)
pruefe("viele Inlier nur auf kleinem Bauteil (Uhr, <= 4 Zellen) -> abgelehnt", S.durchblick_ok(m)[0] == "abgelehnt" and "Zellen" in S.durchblick_ok(m)[1])
m = S.paar_staerke(p0[:150], p1[:150], WH, WH)
pruefe("150 Inlier (unter 200) -> abgelehnt", S.durchblick_ok(m)[0] == "abgelehnt")
m = S.paar_staerke(p0, p1, WH, WH)
pruefe("GPS-Veto: Standorte 170 Grad auseinander -> abgelehnt; 40 Grad / ohne GPS -> durchblick", S.durchblick_ok(m, 170)[0] == "abgelehnt" and S.durchblick_ok(m, 40)[0] == "durchblick" and S.durchblick_ok(m, None)[0] == "durchblick")

# Stufe auf einer Mini-Datenbank: Gruppen 0 und 1 (Teile mit Objektfotos), 2 (fremd); Paare 0-1 flaechig, 0-1 Einblendung, 0-2 flaechig, 0-1 schwach
d = tempfile.mkdtemp(dir=os.environ.get("TMPDIR")); db = sqlite3.connect(os.path.join(d, "t.db"))
db.executescript("create table cameras (camera_id integer primary key, model integer, width integer, height integer, params blob, prior_focal_length integer);"
                 "create table images (image_id integer primary key, name text, camera_id integer);"
                 "create table keypoints (image_id integer primary key, rows integer, cols integer, data blob);"
                 "create table two_view_geometries (pair_id integer primary key, rows integer, cols integer, data blob, config integer);")
db.execute("insert into cameras values (1, 2, 2000, 1500, NULL, 0)")
K = {1: np.r_[p0, e0], 2: np.r_[p1, e0], 3: np.r_[p1, e0], 4: np.r_[p1, e0]}
for i, n in ((1, "a.jpg"), (2, "b.jpg"), (3, "c.jpg"), (4, "d.jpg")):
    db.execute("insert into images values (?, ?, 1)", (i, n)); k = K[i].astype(np.float32); k6 = np.c_[k, np.zeros((len(k), 4), np.float32)]
    db.execute("insert into keypoints values (?, ?, 6, ?)", (i, len(k6), k6.tobytes()))
def paar(x, y, ij, cfg=3):
    ij = np.asarray(ij, np.uint32); db.execute("insert into two_view_geometries values (?, ?, 2, ?, ?)", (x * S.MAXID + y, len(ij), ij.tobytes(), cfg))
idx = np.arange(400); ie = np.arange(400, 700)
paar(1, 2, np.c_[idx, idx])            # a-b flaechig (Gruppe 0 - 1)
paar(1, 3, np.c_[ie, ie], 7)           # a-c Einblendung (Gruppe 0 - 1)
paar(1, 4, np.c_[idx, idx])            # a-d flaechig, aber d in fremder Gruppe 2
db.commit()
g = {1: 0, 2: 1, 3: 1, 4: 2}; nm = {1: "a.jpg", 2: "b.jpg", 3: "c.jpg", 4: "d.jpg"}
L = S.durchblick_stufe(db, nm, g, {(0, 1), (0, 2)}, {0, 1})
u = {(x["a"], x["b"]): x["urteil"] for x in L}
pruefe("Stufe: flaechiges Paar zwischen Objektteilen behalten, Einblendung abgelehnt, Paar zu fremder Gruppe gar nicht gemessen", u == {("a.jpg", "b.jpg"): "durchblick", ("a.jpg", "c.jpg"): "abgelehnt"})
pruefe("Stufe: echte Verbindungen (nicht in falsch) werden nicht angefasst", S.durchblick_stufe(db, nm, g, set(), {0, 1}) == [])
# BRUECKE ERWEITERN: e (Gruppe 0) - b (Gruppe 1) nur 80 flaechige Inlier -> zurueck, weil 0-1 bestaetigt; f (Gruppe 3) - a 80 Inlier -> nicht gemessen (0-3 ohne starkes Paar)
for i, n in ((5, "e.jpg"), (6, "f.jpg")):
    k = np.r_[p0, e0].astype(np.float32); db.execute("insert into images values (?, ?, 1)", (i, n)); db.execute("insert into keypoints values (?, ?, 6, ?)", (i, len(k), np.c_[k, np.zeros((len(k), 4), np.float32)].tobytes()))
i80 = np.arange(0, 400, 5); paar(2, 5, np.c_[i80, i80]); paar(1, 6, np.c_[i80, i80]); db.commit()
g.update({5: 0, 6: 3}); nm.update({5: "e.jpg", 6: "f.jpg"})
L = S.durchblick_stufe(db, nm, g, {(0, 1), (0, 3)}, {0, 1, 3}, bruecke_min=30)
u = {(x["a"], x["b"]): (x["urteil"], bool(x.get("bruecke"))) for x in L}
pruefe("Bruecke erweitern: schwaches Paar einer bestaetigten Verbindung zurueck, an unbestaetigter Verbindung nicht gemessen",
       u.get(("b.jpg", "e.jpg")) == ("durchblick", True) and ("a.jpg", "f.jpg") not in u)
pruefe("Bruecke erweitern ohne bruecke_min (Standard) = alte Stufe", ("b.jpg", "e.jpg") not in {(x["a"], x["b"]) for x in S.durchblick_stufe(db, nm, g, {(0, 1), (0, 3)}, {0, 1, 3})})

# Verdrahtung in main(): Schalter, Loeschung ueberspringt behaltene Paare, seiten.json-Feld, EIN Aufruf
src = open(os.path.join(T, "seiten_erkennen.py")).read()
pruefe("Verdrahtung: --durchblick / RCPARK_SEITEN_DURCHBLICK=1, ein Aufruf durchblick_einbauen, Loeschung ohne behaltene Paare, 'durchblick' in seiten.json",
       '"--durchblick"' in src and 'RCPARK_SEITEN_DURCHBLICK' in src and src.count("= durchblick_einbauen(") == 1 and "pid not in behalten" in src and "durchblick=[" in src)

# Regression aus echten Paaren
R = json.load(open(os.path.join(T, "testdata", "durchblick_paare.json")))
falsch_ = []
for r in R:
    m = S.paar_staerke(np.array(r["p0"]), np.array(r["p1"]), r["wh0"], r["wh1"]); u = S.durchblick_ok(m)[0]
    if u != r["erwartung"]: falsch_.append(f"{r['text']}: {u} (n_eff {m['n_eff']}, statisch {m['statisch']}, Zellen {m['zellen0']}/{m['zellen1']})")
pruefe(f"Regression {len(R)} echte Paare (Uebereck behalten; Einblendung, Uhr/Helm, Martinstor-Verwechslung abgelehnt)" + (": " + "; ".join(falsch_) if falsch_ else ""), not falsch_ and len(R) >= 10)
sys.exit(1 if f else 0)
