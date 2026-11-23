#!/usr/bin/env python3
"""Test seiten_eck_koppeln, Stand 23.11.2026 (Befund 1122t: Teil 1 'Massstab nicht belegt', Haelften 2,3 %):
(1) KAMERA-PROBE: flache Wand + gespiegelter Teil - die Punkte allein bestehen (Wand ~ eigenes Spiegelbild), die Kamerazentren nicht -> abgelehnt; richtig bleibt stimmig.
(2) TEILKAMERAS: Arbeits-DB bekommt die Intrinsik der Teilmodelle (Konflikt gemeldet, anderes Kameramodell/Groesse bleibt), Zuruecksetzen stellt alles her;
    DB ohne Kameratabelle -> nichts gesetzt; Mapper mit festen Kameras bekommt die refine-Schalter.
(3) DUENNE BRUECKE: Schwellenwahl nimmt die strengste Schwelle mit den meisten Teil-Bildern, voll -> wie bisher (erste + Sensitivitaet).
(4) Variantenwahl: Teilkameras bei Gleichstand vorn, ohne Teilkameras unveraendert (Nachmatchen nur mit >= 2 und >= SIFT).
Vorgespielte Daten, kein COLMAP, keine GPU."""
import os, sys, sqlite3, types, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_eck_koppeln as EK
from sim3_robust import matrix, anwenden
fehler = []
def pruef(ok, text): print(("ok   " if ok else "FEHL ") + text); ok or fehler.append(text)

# (1) Kamera-Probe: Wand z ~ 0 (Relief +-3 cm), Kameras 10 m davor (z = 10), Eckmodell = Sim3 der Wahrheit + Rauschen
rng = np.random.default_rng(5); n = 3000
P = np.c_[rng.uniform(-8, 8, n), rng.uniform(0, 12, n), rng.normal(0, 0.03, n)]
C = np.c_[rng.uniform(-6, 6, 12), rng.uniform(1, 3, 12), np.full(12, 10.0)]
c_, s_ = np.cos(0.7), np.sin(0.7); Rz = np.array([[c_, -s_, 0], [s_, c_, 0], [0, 0, 1]]); M = matrix(0.4, Rz, [1, -2, 3]); Mi = np.linalg.inv(M)
tf = np.linalg.norm(P - C[rng.integers(0, 12, n)], axis=1)                          # Tiefe Punkt - beobachtende Kamera (Wahrheit = Teil-Rahmen)
X = anwenden(Mi, P + rng.normal(0, 1, P.shape) * (0.002 * tf)[:, None]); CX = anwenden(Mi, C); td = tf / 0.4   # Eckrahmen: Massstab 1/0,4
ausd = EK.ausdehnung(X)
Mk, pr, ok, g = EK.kopplung_pruefen(X, P, ausd, EK.ausdehnung(P), tiefe=td, kameras=(CX, C))
pruef(ok and pr.get("kameras_rel", 1) < 0.02, f"richtige Kopplung mit Kamera-Probe stimmig ({g}, kameras_rel {pr.get('kameras_rel')})")
sp = lambda Y: Y * np.array([1, 1, -1])                                               # Spiegel an der Wandebene (Seitenverwechslung einer flachen Wand)
_, pr0, ok0, g0 = EK.kopplung_pruefen(X, sp(P), ausd, EK.ausdehnung(P), tiefe=td)
pruef(ok0, f"Gegenprobe: ohne Kameras besteht der gespiegelte flache Teil (Loch der Punkt-Pruefung, 1122t Anteil 0,815) ({g0})")
_, pr1, ok1, g1 = EK.kopplung_pruefen(X, sp(P), ausd, EK.ausdehnung(P), tiefe=td, kameras=(CX, sp(C)))
pruef(not ok1 and "Kameras widersprechen" in g1 and pr1["kameras_rel"] > 1, f"gespiegelter Teil mit Kamera-Probe abgelehnt ({g1})")
_, pr2, ok2, g2 = EK.kopplung_pruefen(X, P, ausd, EK.ausdehnung(P), tiefe=None, kameras=(CX, C))
pruef("kameras_rel" not in pr2, "ohne Tiefe keine Kamera-Probe (Fehlermass Ausdehnung unveraendert)")
pruef(EK.MASS_REL == 0.02 and EK.REST_REL == 0.005 and EK.MIN_ANTEIL == 0.8, "Kopplungsgrenzen unveraendert (Haelften 2 %, Rest 0,5 %, Anteil 80 %)")

# (2) Teilkameras in einer Mini-DB
d = __import__("pfade").temp_ordner("test_eck_tk_"); db = os.path.join(d, "t.db"); c = sqlite3.connect(db)
c.executescript("create table images (image_id integer primary key, name text, camera_id integer);"
                "create table cameras (camera_id integer, model integer, width integer, height integer, params blob, source integer, primary key(camera_id, source))")
alt = {1: [1000.0, 500, 400, 0.0], 2: [2000.0, 960, 540, 0.0], 3: [3000.0, 512, 384, 0.0], 4: [800.0, 320, 240, 0.0]}
for i, (m, w, h) in {1: (2, 1000, 800), 2: (2, 1920, 1080), 3: (2, 1024, 768), 4: (2, 640, 480)}.items():
    c.execute("insert into cameras values (?,?,?,?,?,2)", (i, m, w, h, np.array(alt[i], np.float64).tobytes()))
for i, (nm, k) in enumerate((("a1", 1), ("b1", 2), ("b2", 2), ("a2", 2), ("x", 3), ("v", 4)), 1): c.execute("insert into images values (?,?,?)", (i, nm, k))
c.commit(); c.close()
kam = lambda f, w, h, mod=2: types.SimpleNamespace(model=types.SimpleNamespace(value=mod), width=w, height=h, params=np.array([f, w / 2, h / 2, 0.01]))
bild = lambda nm, k: types.SimpleNamespace(name=nm, camera_id=k, has_pose=True)
R = {0: types.SimpleNamespace(images={1: bild("a1", 1), 2: bild("a2", 2), 3: bild("v", 4)}, cameras={1: kam(1111, 1000, 800), 2: kam(2100, 1920, 1080), 4: kam(900, 640, 480, mod=4)}),
     1: types.SimpleNamespace(images={1: bild("b1", 7), 2: bild("b2", 7)}, cameras={7: kam(2222, 1920, 1080)})}
alt_z, info = EK.teilkameras_setzen(db, ["a1", "a2", "b1", "b2", "x", "v"], R)
lies = lambda: {i: np.frombuffer(p, np.float64) for i, p in sqlite3.connect(db).execute("select camera_id, params from cameras")}
p = lies()
pruef(abs(p[1][0] - 1111) < 1e-9 and abs(p[2][0] - 2222) < 1e-9 and abs(p[3][0] - 3000) < 1e-9 and abs(p[4][0] - 800) < 1e-9,
      f"Intrinsik der Teile gesetzt; geteilte Kamera -> Teil mit den meisten Bildern (Teil 1: 2 gegen 1); fremdes Bild + anderes Kameramodell bleiben ({ {k: v[0] for k, v in p.items()} })")
pruef(info["gesetzt"] == 2 and info["konflikte"] == 1 and info["bilder_ohne_teilkamera"] == 2, f"Bericht: gesetzt/Konflikte/ohne Teilkamera ({info})")
EK.teilkameras_zurueck(db, alt_z); p = lies()
pruef(all(np.allclose(p[i], alt[i]) for i in alt), "Zuruecksetzen stellt die Arbeits-DB wieder her (SIFT-Variante des naechsten Stuecks unberuehrt)")
eck = types.SimpleNamespace(images={1: bild("x", 9), 2: bild("a1", 8)}, cameras={9: kam(3333, 1024, 768), 8: kam(5555, 1000, 800)})
alt_e, info_e = EK.teilkameras_setzen(db, ["a1", "x"], R, ersatz=eck); p = lies()
pruef(abs(p[3][0] - 3333) < 1e-9 and abs(p[1][0] - 1111) < 1e-9 and info_e["kameras_aus_eckmodell"] == 1,
      f"Bild ohne Teil bekommt die verfeinerte Intrinsik des SIFT-Eckmodells, Teil hat Vorrang ({info_e})")
EK.teilkameras_zurueck(db, alt_e)
db2 = os.path.join(d, "ohne.db"); sqlite3.connect(db2).executescript("create table images (image_id integer primary key, name text, camera_id integer)")
a2, i2 = EK.teilkameras_setzen(db2, ["a1"], R)
pruef(a2 == [] and i2["gesetzt"] == 0, f"DB ohne Kameratabelle: nichts gesetzt, Variante entfaellt ({i2})")
befehle = []; sc = EK.subprocess.call
EK.subprocess.call = lambda cmd, **kw: befehle.append(cmd) or 0
try:
    EK.mapper(["a1"], db, d, os.path.join(d, "m1"), 2, 30); EK.mapper(["a1"], db, d, os.path.join(d, "m2"), 2, 20, kameras_fest=True)
finally: EK.subprocess.call = sc
arg = lambda cmd, k: cmd[cmd.index(k) + 1] if k in cmd else None
pruef(arg(befehle[0], "--Mapper.ba_refine_focal_length") is None and arg(befehle[1], "--Mapper.ba_refine_focal_length") == "0"
      and arg(befehle[1], "--Mapper.ba_refine_extra_params") == "0" and arg(befehle[1], "--Mapper.abs_pose_min_num_inliers") == "20",
      "Mapper: feste Kameras nur in der Teilkameras-Variante (Brennweite/Verzeichnung nicht verfeinert)")

# (3) Duenne Bruecke: Schwellenwahl
w, s, f = EK.schwelle_waehlen([(30, "m", 35), (20, "m", 35)], 35)
pruef((w, s, f) == (0, 1, True), "volle Bruecke: strengste Schwelle + naechste als Sensitivitaet, fertig (wie bisher)")
pruef(EK.schwelle_waehlen([(30, "m", 29)], 35)[2] is False, "duenn (29/35 Teil-Bilder): Leiter laeuft weiter")
pruef(EK.schwelle_waehlen([(30, "m", 29), (20, "m", 35), (15, "m", 35)], 35) == (1, 2, True), "1122t-Fall: Schwelle 20 registriert alle 35 -> Wahl 20, Sensitivitaet 15")
pruef(EK.schwelle_waehlen([(30, "m", 29), (20, "m", 29), (15, "m", 30), (12, "m", 30), (10, "m", 30)], 35) == (2, 3, False),
      "nie voll: strengste mit den meisten (Gleichstand -> strengere), Sensitivitaet die naechste")
pruef(EK.schwelle_waehlen([], 5) == (None, None, False), "keine Treffer: keine Wahl")

# (4) Variantenwahl
g = lambda *t: {x: None for x in t}
pruef(EK.variante_waehlen(dict(sift=g(0), nachmatchen=g(), teilkameras=g(0, 1))) == "teilkameras", "Teilkameras koppelt beide Teile, SIFT nur einen -> Teilkameras")
pruef(EK.variante_waehlen(dict(sift=g(0, 1), nachmatchen=g(0, 1), teilkameras=g(0, 1))) == "teilkameras", "Gleichstand -> Teilkameras (gleiche Kamerageometrie wie die Teile)")
pruef(EK.variante_waehlen(dict(sift=g(0, 1), teilkameras=g(1))) == "sift", "Teilkameras mit nur einem Teil zaehlt nicht")
pruef(EK.variante_waehlen(dict(sift=g(0), nachmatchen=g(0, 1))) == "nachmatchen" and EK.variante_waehlen(dict(sift=g(0, 1, 2), nachmatchen=g(0, 1))) == "sift"
      and EK.variante_waehlen(dict(sift=g(), nachmatchen=g())) == "sift", "ohne Teilkameras unveraendert (Nachmatchen nur mit >= 2 und >= SIFT)")
src = open(os.path.join(T, "seiten_eck_koppeln.py")).read()
pruef("RCPARK_ECK_TEILKAMERAS" in src and "teilkameras_zurueck(db, alt)" in src and "kameras=kamerazentren(" in src, "Verdrahtung: Schalter, Zuruecksetzen im finally, Kamera-Probe in koppeln")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
