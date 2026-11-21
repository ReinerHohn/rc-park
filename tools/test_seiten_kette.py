#!/usr/bin/env python3
"""Fester Test (ohne GPU, Sekunden) fuer die Seitenfolge der Kette vom 21.11.2026 - synthetische Mini-Modelle (COLMAP-Textformat) und Mini-Datenbanken:
  1 seiten_blick_tor.py       zwei 'verwechselte' Bildgruppen am selben Ort mit gleicher Blickrichtung -> rc 3; auf Gegenseiten -> rc 0; im selben Bildteil -> nicht gewertet
  2 db_masken_filter.py       Zuordnungen an maskierten Merkmalen fallen weg (Maske in halber Aufloesung), Paar unter 15 wird geloescht, Quelle bleibt unveraendert
  3 brennweite_schaerfe.py    Kameras im Kreis um einen Koerper = scharf (auch drei Bilder mit gemeinsamer Kamera); ferne Frontalkamera auf flache Wand = unbestimmt;
                              Kamera mit 8 Punkten = zu_wenig; Sperrliste = beide + vorhandene Liste (vereinigt, Quellliste unveraendert)
  4 modell_lage_vergleich.py  Modell B = gedrehtes/skaliertes A mit 5 versetzten Fotos (Brennweite 8 % anders): genau diese 5 > 2 %, Rest ~0, Quelle 'eigen' traegt die Abweichung
  5 sfm_seiten_vorstufe.py    Wiederverwendung der Masken/Seitenerkennung, nur fehlende Masken neu, COLMAP-Maskennamen, Guard 'kein verwechselt -> ungeteilte DB',
                              Abbruch bei gescheiterter Seitenerkennung, DB-Bereinigung (echter Lauf sfm_db_variante: Kamera je Clip, Prior weg), Meldung fehlender Seiten
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_kette.py (pycolmap + cv2)."""
import os, sys, json, sqlite3, tempfile, shutil, contextlib, io
from types import SimpleNamespace as N
import pycolmap                                                        # (tools/py waehlt daran venv-colmap)
import numpy as np, cv2
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_blick_tor as SB, db_masken_filter as DM, brennweite_schaerfe as BS, modell_lage_vergleich as ML, sfm_seiten_vorstufe as SV

S = tempfile.mkdtemp(prefix="test_seiten_kette_"); rng = np.random.default_rng(7); W, H, F0 = 1600, 1200, 1200.0


def blick(C, ziel, hoch=(0, 0, 1)):
    """Kamera am Ort C blickt auf ziel -> (R, t) Welt -> Kamera (z = Blickrichtung, y nach unten)."""
    z = np.asarray(ziel, float) - C; z /= np.linalg.norm(z); x = np.cross(z, hoch); x /= np.linalg.norm(x); y = np.cross(z, x); R = np.array([x, y, z]); return R, -R @ np.asarray(C, float)


def quat(R):
    w = np.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    if w > 1e-6: return w, (R[2, 1] - R[1, 2]) / (4 * w), (R[0, 2] - R[2, 0]) / (4 * w), (R[1, 0] - R[0, 1]) / (4 * w)
    i = int(np.argmax(np.diag(R))); j, k = (i + 1) % 3, (i + 2) % 3; s = np.sqrt(1 + R[i, i] - R[j, j] - R[k, k]) * 2; q = [0.0] * 4
    q[0] = (R[k, j] - R[j, k]) / s; q[1 + i] = s / 4; q[1 + j] = (R[j, i] + R[i, j]) / s; q[1 + k] = (R[k, i] + R[i, k]) / s; return tuple(q)


def modell(name, bilder, punkte=None, rauschen=0.0):
    """bilder = [dict(name, kam, f, R, t, sieht=[Punkt-IDs])] -> COLMAP-Textmodell in <S>/<name>; Beobachtungen = Projektion + Rauschen (px)."""
    d = os.path.join(S, name); os.makedirs(d, exist_ok=True); punkte = punkte or {}; spur = {p: [] for p in punkte}; kam = {}; zi = []
    for i, b in enumerate(bilder, 1):
        kam[b["kam"]] = b["f"]; q = quat(b["R"]); obs = []
        for p in b.get("sieht", []):
            pc = b["R"] @ punkte[p] + b["t"]
            if pc[2] <= 0.1: continue
            xy = b["f"] * pc[:2] / pc[2] + [W / 2, H / 2] + rng.normal(0, rauschen, 2) if rauschen else b["f"] * pc[:2] / pc[2] + [W / 2, H / 2]
            spur[p].append((i, len(obs))); obs.append(f"{xy[0]:.3f} {xy[1]:.3f} {p}")
        zi.append(f"{i} {q[0]:.12f} {q[1]:.12f} {q[2]:.12f} {q[3]:.12f} {b['t'][0]:.9f} {b['t'][1]:.9f} {b['t'][2]:.9f} {b['kam']} {b['name']}\n{' '.join(obs)}\n")
    open(os.path.join(d, "cameras.txt"), "w").write("".join(f"{c} SIMPLE_RADIAL {W} {H} {f} {W / 2} {H / 2} 0\n" for c, f in kam.items()))
    open(os.path.join(d, "images.txt"), "w").write("".join(zi))
    open(os.path.join(d, "points3D.txt"), "w").write("".join(f"{p} {x[0]:.6f} {x[1]:.6f} {x[2]:.6f} 128 128 128 0.5 " + " ".join(f"{a} {b}" for a, b in spur[p]) + "\n" for p, x in punkte.items() if spur[p]))
    return d


def aufruf(mod, *arg):
    alt = sys.argv; sys.argv = [mod.__name__] + [str(a) for a in arg]; puffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(puffer): rc = mod.main()
    finally: sys.argv = alt
    return rc, puffer.getvalue()


# ---------- 1 seiten_blick_tor
def gruppe(vor, n, x, ziel_x):
    return [dict(name=f"{vor}_{i:02d}.jpg", kam=1, f=F0, **dict(zip("Rt", blick(np.array([x + rng.normal(0, 1), -8 + 2.2 * i, 1.6]), (ziel_x, rng.normal(0, 2), 12.0))))) for i in range(n)]
nord = gruppe("nord", 8, 30.0, 0.0); verklebt = modell("verklebt", nord + gruppe("sued", 8, 31.0, 0.0)); getrennt = modell("getrennt", nord + gruppe("sued", 8, -30.0, 0.0))
gem = {f"nord_{i:02d}.jpg": 0 for i in range(8)} | {f"sued_{i:02d}.jpg": 1 for i in range(8)}
sj = os.path.join(S, "seiten.json"); json.dump(dict(gemeinschaft=gem, verbindungen=[dict(a=0, b=1, paare=40, urteil="verwechselt")], seiten=[dict(gruppen=[0], bilder=8), dict(gruppen=[1], bilder=8)]), open(sj, "w"))
sj1 = os.path.join(S, "seiten_ein_teil.json"); json.dump(dict(gemeinschaft=gem, verbindungen=[dict(a=0, b=1, paare=40, urteil="verwechselt")], seiten=[dict(gruppen=[0, 1], bilder=16)]), open(sj1, "w"))
rc, o = aufruf(SB, verklebt, sj, "--aus", os.path.join(S, "blick.json")); bj = json.load(open(os.path.join(S, "blick.json")))
assert rc == 3 and bj["verklebt"] == 1 and bj["paare"][0]["winkel_grad"] < 30, (rc, o)
rc, o = aufruf(SB, getrennt, sj); assert rc == 0 and "bestanden" in o and "1 pruefbare" in o, (rc, o)
rc, o = aufruf(SB, verklebt, sj1); assert rc == 0 and "0 pruefbare" in o, "Paare im selben Bildteil duerfen nicht gewertet werden: " + o
rc, o = aufruf(SB, modell("nur_nord", nord), sj); assert rc == 0 and "kein pruefbares Gruppenpaar" in o, (rc, o)
print("ok 1 seiten_blick_tor: verklebt rc 3 (Blickwinkel %.0f Grad), Gegenseiten rc 0, gleicher Bildteil nicht gewertet, eine Seite allein = Hinweis" % bj["paare"][0]["winkel_grad"])

# ---------- 2 db_masken_filter
MAXID = 2147483647
def mini_db(pfad, namen, kameras):
    c = sqlite3.connect(pfad)
    c.executescript("create table cameras(camera_id integer primary key, model integer, width integer, height integer, params blob, prior_focal_length integer);"
                    "create table images(image_id integer primary key, name text, camera_id integer); create table keypoints(image_id integer primary key, rows integer, cols integer, data blob);"
                    "create table descriptors(image_id integer primary key, rows integer, cols integer, data blob); create table matches(pair_id integer primary key, rows integer, cols integer, data blob);"
                    "create table two_view_geometries(pair_id integer primary key, rows integer, cols integer, data blob, config integer);")
    for cid, (w_, h_, f, prior) in kameras.items(): c.execute("insert into cameras values(?,2,?,?,?,?)", (cid, w_, h_, np.array([f, w_ / 2, h_ / 2, 0.0]).tobytes(), prior))
    for i, (n, cid) in enumerate(namen, 1): c.execute("insert into images values(?,?,?)", (i, n, cid))
    return c
db = os.path.join(S, "mini.db"); c = mini_db(db, [("a.jpg", 1), ("b.jpeg", 2), ("c.JPG", 3)], {k: (100, 80, 120.0, 0) for k in (1, 2, 3)})
kp = np.zeros((40, 6), np.float32); kp[:20, 0] = np.linspace(2, 45, 20); kp[20:, 0] = np.linspace(55, 98, 20); kp[:, 1] = np.linspace(5, 75, 40)   # Merkmale 0-19 linke Bildhaelfte, 20-39 rechte
for i in (1, 2, 3): c.execute("insert into keypoints values(?,?,?,?)", (i, 40, 6, kp.tobytes()))
def paar(i, j, idx): z = np.array([[k, k] for k in idx], np.uint32); return (i * MAXID + j, len(z), 2, z.tobytes())
for p_ in (paar(1, 2, range(0, 30)), paar(1, 3, range(0, 40)), paar(2, 3, range(0, 25))):
    c.execute("insert into matches values(?,?,?,?)", p_); c.execute("insert into two_view_geometries values(?,?,?,?,2)", p_)
c.commit(); c.close(); vorher = open(db, "rb").read()
md = os.path.join(S, "masken", "serie"); os.makedirs(md); m = np.full((40, 50), 255, np.uint8); m[:, :25] = 0; cv2.imwrite(os.path.join(md, "a.png"), m)   # Bild a: linke Haelfte = Vordergrund, Maske in halber Aufloesung
cv2.imwrite(os.path.join(md, "b.png"), np.full((80, 100), 255, np.uint8))
aus = os.path.join(S, "mini_maske.db"); rc, o = aufruf(DM, db, os.path.join(S, "masken"), "--aus", aus); assert rc == 0, o
c = sqlite3.connect(aus); tv = {p: (r, np.frombuffer(d, np.uint32).reshape(r, 2)) for p, r, d in c.execute("select pair_id, rows, data from two_view_geometries")}; mt = {p for p, in c.execute("select pair_id from matches")}; c.close()
assert MAXID + 2 not in tv and MAXID + 2 not in mt, "Paar a-b (30 Zuordnungen, 20 am Vordergrund -> 10 < 15) muss in beiden Tabellen geloescht sein"
assert tv[MAXID + 3][0] == 20 and tv[MAXID + 3][1][:, 0].min() == 20, "Paar a-c: nur Zuordnungen der unmaskierten rechten Haelfte bleiben"
assert tv[2 * MAXID + 3][0] == 25 and open(db, "rb").read() == vorher, "Paar b-c unberuehrt, Quell-DB unveraendert"
ber = json.load(open(aus + ".masken.json")); assert (ber["paare"], ber["gekuerzt"], ber["geloescht"], ber["zuordnungen_vorher"], ber["zuordnungen_nachher"]) == (3, 2, 1, 95, 45), ber
print("ok 2 db_masken_filter: 3 Paare -> 1 geloescht (< 15 ohne Vordergrund), 1 gekuerzt 40 -> 20, 1 unberuehrt; Maske halber Aufloesung richtig skaliert")

# ---------- 3 brennweite_schaerfe
P = {i: np.array([rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(0, 10)]) for i in range(1, 401)}                      # Koerper mit Tiefe
P |= {i: np.array([5.0, rng.uniform(-5, 5), rng.uniform(0, 10)]) for i in range(401, 521)}                                  # flache Wand x = 5
B3 = []
for i in range(12):
    a_ = 2 * np.pi * i / 12; C = np.array([16 * np.cos(a_), 16 * np.sin(a_), 2.0 + 0.5 * (i % 3)]); R, t = blick(C, (0, 0, 5))
    B3.append(dict(name=(f"clipA__vf_{i:03d}.jpg" if i < 3 else f"eigen__{i:02d}.jpg"), kam=(1 if i < 3 else 10 + i), f=F0, R=R, t=t, sieht=list(P)))
R, t = blick(np.array([300.0, 0.0, 5.0]), (0, 0, 5)); B3.append(dict(name="netz__fern.jpg", kam=50, f=30000.0, R=R, t=t, sieht=list(range(401, 521))))    # Fernfoto frontal auf die flache Wand
R, t = blick(np.array([14.0, 3.0, 3.0]), (0, 0, 5)); B3.append(dict(name="netz__wenig.jpg", kam=51, f=F0, R=R, t=t, sieht=list(range(1, 9))))
m3 = modell("schaerfe", B3, P, rauschen=0.5)
alt_liste = os.path.join(S, "unstabil.txt"); open(alt_liste, "w").write("eigen__05.jpg\nnetz__fern.jpg\n"); alt_inhalt = open(alt_liste).read()
rc, o = aufruf(BS, m3, "--aus", os.path.join(S, "schaerfe.json"), "--liste", os.path.join(S, "unbestimmt.txt"), "--sperrliste", os.path.join(S, "sperre.txt"), "--vereinen", alt_liste, os.path.join(S, "gibt_es_nicht.txt"))
assert rc == 0, o
U = {e["bilder"][0]: e for e in json.load(open(os.path.join(S, "schaerfe.json")))["kameras"]}
assert U["netz__fern.jpg"]["urteil"] == "unbestimmt", U["netz__fern.jpg"]
assert U["netz__wenig.jpg"]["urteil"] == "zu_wenig", U["netz__wenig.jpg"]
clip = [e for e in U.values() if len(e["bilder"]) == 3]; assert len(clip) == 1 and clip[0]["urteil"] == "scharf", "drei Bilder mit gemeinsamer Kamera = EINE scharfe Kamera: %s" % clip
scharf = [n for n, e in U.items() if e["urteil"] == "scharf"]; assert len(scharf) == 10, {n: (e["urteil"], e.get("breite_proz")) for n, e in U.items()}
assert open(os.path.join(S, "unbestimmt.txt")).read().split() == ["netz__fern.jpg", "netz__wenig.jpg"]
assert open(os.path.join(S, "sperre.txt")).read().split() == ["eigen__05.jpg", "netz__fern.jpg", "netz__wenig.jpg"] and open(alt_liste).read() == alt_inhalt, "Sperrliste = Vereinigung, Quellliste unveraendert"
print("ok 3 brennweite_schaerfe: 10 Kameras scharf (Breite %.1f %%), Fernfoto unbestimmt (Breite %.0f %%, offen %s), 8 Punkte = zu_wenig; Sperrliste vereinigt 2 + 1" % (clip[0]["breite_proz"], U["netz__fern.jpg"]["breite_proz"], U["netz__fern.jpg"]["offen"]))

# ---------- 4 modell_lage_vergleich
A4 = []
for i in range(40):
    a_ = 2 * np.pi * i / 40; C = np.array([(18 + 6 * (i % 4)) * np.cos(a_), (18 + 6 * (i % 4)) * np.sin(a_), 1.5 + (i % 5)]); R, t = blick(C, (0, 0, 8))
    A4.append(dict(name=(f"eigen__{i:02d}.jpg" if i < 25 else f"clipB__vf_{i:03d}.jpg"), kam=i + 1, f=F0, R=R, t=t, C=C))
ax = np.array([0.2, 0.3, 1.0]); ax /= np.linalg.norm(ax); K_ = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]]); Sd = np.eye(3) + np.sin(0.7) * K_ + (1 - np.cos(0.7)) * K_ @ K_
versetzt = {"eigen__03.jpg", "eigen__08.jpg", "eigen__13.jpg", "eigen__18.jpg", "eigen__23.jpg"}; B4 = []
for b in A4:
    C = 2.3 * Sd @ (b["C"] + (np.array([6.0, -5.0, 2.0]) if b["name"] in versetzt else 0)) + [10, -4, 2]; R = b["R"] @ Sd.T
    B4.append(dict(name=b["name"], kam=b["kam"], f=F0 * (1.08 if b["name"] in versetzt else 1.0), R=R, t=-R @ C))
rc, o = aufruf(ML, modell("lage_a", A4), modell("lage_b", B4), "--aus", os.path.join(S, "lage.json")); assert rc == 0, o
L = json.load(open(os.path.join(S, "lage.json"))); weit = {n for n, v in L["bilder"].items() if v[0] > 2}
assert L["gemeinsam"] == 40 and weit == versetzt and L["ueber2"] == 5 and L["lage_median"] < 0.1, (L["gemeinsam"], sorted(weit), L["lage_median"])
assert max(v[1] for n, v in L["bilder"].items()) < 0.1 and all(abs(L["bilder"][n][2] - 1.08) < 0.005 for n in versetzt), "Drehung gleich, Brennweite der versetzten 8 % anders"
Q = {q["quelle"]: q for q in L["quellen"]}; assert Q["eigen"]["lage_ueber2"] == 5 and Q["clipB"]["lage_ueber2"] == 0 and Q["clipB"]["bilder"] == 15, Q
rc, o = aufruf(ML, modell("lage_klein", A4[:6]), modell("lage_b", B4)); assert rc == 0 and "zu wenige gemeinsame Bilder" in o
print("ok 4 modell_lage_vergleich: 40 gemeinsame Bilder, Median %.3f %%, genau die 5 versetzten > 2 %% (Quelle eigen), Videoclip 0, Brennweite 8 %% erkannt" % L["lage_median"])

# ---------- 5 sfm_seiten_vorstufe (Unterprozesse = Attrappen; nur die DB-Bereinigung laeuft echt)
img = os.path.join(S, "fotos"); w = os.path.join(S, "arbeit"); os.makedirs(img); os.makedirs(w)
for n in ("eigen__a.jpg", "netz__b.jpeg", "netz__c.JPG", "clipA__vf_001.jpg", "clipA__vf_002.jpg", "clipA__vf_003.jpg"): open(os.path.join(img, n), "w").write("x")
rufe = []
def lauf_masken(cmd, check=False):
    rufe.append(cmd); q = cmd[cmd.index("--ausgabe") - 1]; z = os.path.join(cmd[cmd.index("--ausgabe") + 1], os.path.basename(q)); os.makedirs(z, exist_ok=True)
    for f in os.listdir(q): open(os.path.join(z, os.path.splitext(f)[0] + ".png"), "w").write("m")
    return N(returncode=0)
with contextlib.redirect_stdout(io.StringIO()):
    r1 = SV.masken_rechnen(img, w, lauf=lauf_masken); r2 = SV.masken_rechnen(img, w, lauf=lauf_masken)
    assert (r1["neu"], r1["ohne_maske"], r2["neu"], len(rufe)) == (6, 0, 0, 1) and rufe[0][5] == img and rufe[0][-2:] == ["--batch", "2"], (r1, r2, rufe)
    open(os.path.join(img, "eigen__neu.jpg"), "w").write("x"); r3 = SV.masken_rechnen(img, w, lauf=lauf_masken)
    assert len(rufe) == 2 and os.listdir(rufe[1][5]) == ["eigen__neu.jpg"] and r3["neu"] == 1 and r3["bilder"] == 7, "nur das neue Bild darf gerechnet werden"
    mc = os.path.join(w, "masken_colmap"); assert SV.masken_colmap(img, r1["ordner"], mc) == (7, 0) and SV.masken_colmap(img, r1["ordner"], mc) == (7, 0)
    assert sorted(os.listdir(mc))[-2:] == ["netz__b.jpeg.png", "netz__c.JPG.png"] and os.path.exists(os.path.join(mc, "netz__c.JPG.png")), sorted(os.listdir(mc))
    # Bild OHNE Maske: COLMAP wuerde es ueberspringen (MASK_ERROR) -> leere weisse Maske in Bildgroesse; kommt spaeter eine echte Maske, ersetzt die Verknuepfung die leere Datei
    cv2.imwrite(os.path.join(img, "zz_ohne.jpg"), np.zeros((30, 40), np.uint8)); assert SV.masken_colmap(img, r1["ordner"], mc) == (7, 1)
    lm = cv2.imread(os.path.join(mc, "zz_ohne.jpg.png"), 0); assert lm.shape == (30, 40) and lm.min() == 255 and not os.path.islink(os.path.join(mc, "zz_ohne.jpg.png"))
    open(os.path.join(r1["ordner"], "fotos", "zz_ohne.png"), "w").write("m"); assert SV.masken_colmap(img, r1["ordner"], mc) == (8, 0) and os.path.islink(os.path.join(mc, "zz_ohne.jpg.png"))
    os.remove(os.path.join(img, "zz_ohne.jpg"))
    def lauf_fehler(cmd, check=False): return N(returncode=1)
    os.remove(os.path.join(img, "eigen__neu.jpg")); open(os.path.join(img, "eigen__neu2.jpg"), "w").write("x")
    try: SV.masken_rechnen(img, w, lauf=lauf_fehler); raise AssertionError("gescheiterte Masken muessen abbrechen")
    except SystemExit as e_: assert "Masken gescheitert" in str(e_)
    os.remove(os.path.join(img, "eigen__neu2.jpg"))

dbq = os.path.join(w, "db.db"); c = mini_db(dbq, [("eigen__a.jpg", 1), ("clipA__vf_001.jpg", 2), ("clipA__vf_002.jpg", 3), ("clipA__vf_003.jpg", 4)], {1: (4000, 3000, 8.7e6, 1), 2: (1920, 1080, 2304.0, 0), 3: (1920, 1080, 2304.0, 0), 4: (1920, 1080, 2304.0, 0)}); c.commit(); c.close()
def seiten_json(verwechselt):
    return dict(db=dbq, gemeinschaft={f"n{i:02d}.jpg": 0 for i in range(30)} | {f"s{i:02d}.jpg": 1 for i in range(12)} | {f"f{i}.jpg": 2 for i in range(4)}, groessen=[30, 12, 4],
                verbindungen=[dict(a=0, b=1, paare=50, urteil="verwechselt" if verwechselt else "unklar")], seiten=[dict(gruppen=[0], bilder=30), dict(gruppen=[1], bilder=12)], fremd=[f"f{i}.jpg" for i in range(4)], geloeschte_paare=77)
zustand = dict(verwechselt=True, rc=3)
def lauf_seiten(cmd, check=False):
    rufe.append(cmd)
    if zustand["rc"] in (0, 3): json.dump(seiten_json(zustand["verwechselt"]), open(cmd[cmd.index("--aus") + 1], "w")); shutil.copyfile(cmd[4 if cmd[2] == "-I" else 5], cmd[cmd.index("--db-aus") + 1])
    return N(returncode=zustand["rc"])
roh = os.path.join(w, "masken"); rufe.clear()
with contextlib.redirect_stdout(io.StringIO()) as aus_:
    d1, b1 = SV.seiten(dbq, img, w, roh, lauf=lauf_seiten); d2, b2 = SV.seiten(dbq, img, w, roh, lauf=lauf_seiten)
    assert d1 == d2 == os.path.join(w, "db_seiten.db") and len(rufe) == 1 and b1["teile"] == [30, 12] and b1["fremd"] == 4 and b1["getrennt"], (d1, b1, len(rufe))
    assert "--streng" in rufe[0] and "--masken" in rufe[0] and "--referenz" not in rufe[0] and "ACHTUNG SEITEN GETRENNT: 2 Bildteile" in aus_.getvalue()
    zustand.update(verwechselt=False, rc=3)                                # --streng meldet rc 3 auch ohne 'verwechselt'-Urteil des Pruefers
    c = sqlite3.connect(dbq); c.execute("insert into images values(9, 'eigen__z.jpg', 1)"); c.commit(); c.close(); os.utime(dbq, (1, 1))   # Eingangs-DB geaendert -> neu rechnen
    d3, b3 = SV.seiten(dbq, img, w, roh, lauf=lauf_seiten); assert len(rufe) == 2 and d3 == dbq and not b3["getrennt"] and "Guard" in b3["hinweis"], (d3, b3)
    d4, b4 = SV.seiten(dbq, img, w, roh, lauf=lauf_seiten, modus="immer"); assert len(rufe) == 2 and d4.endswith("db_seiten.db") and b4["getrennt"]
    os.rename(os.path.join(img, "eigen__a.jpg"), os.path.join(img, "IMG_a.jpg")); os.utime(dbq, (2, 2)); SV.seiten(dbq, img, w, roh, lauf=lauf_seiten)
    assert rufe[-1][-2:] == ["--referenz", ""], "Ordner ohne 'eigen__'-Namen: jedes Bild zaehlt als Objektfoto (sonst waere alles FREMD)"
    zustand.update(rc=1); os.utime(dbq, (3, 3))
    try: SV.seiten(dbq, img, w, roh, lauf=lauf_seiten); raise AssertionError("gescheiterte Seitenerkennung muss abbrechen")
    except SystemExit as e_: assert "Seitenerkennung gescheitert" in str(e_)
    # DB-Bereinigung echt (tools/sfm_db_variante.py): drei Videobilder -> eine Kamera, unsinniger EXIF-Prior (8,7 Mio px) weg; zweiter Aufruf = wiederverwendet
    dm1 = SV.bereinigen(dbq, w); zeit = os.path.getmtime(dm1); dm2 = SV.bereinigen(dbq, w)
    c = sqlite3.connect(dm1); kam = c.execute("select camera_id, params, prior_focal_length from cameras").fetchall(); vid = {r[0] for r in c.execute("select camera_id from images where name like 'clipA%'")}; c.close()
    assert dm1 == dm2 == os.path.join(w, "db_mapper.db") and os.path.getmtime(dm2) == zeit and len(kam) == 2 and len(vid) == 1, (dm1, kam, vid)
    assert all(pr == 0 for _, _, pr in kam) and abs(np.frombuffer([p for k, p, _ in kam if k == 1][0], np.float64)[0] - 1.2 * 4000) < 1e-6, "Prior geloescht, Brennweite = Schaetzung 1,2 x Bildbreite"
    c = sqlite3.connect(dbq); assert c.execute("select count(*) from cameras").fetchone()[0] == 4, "Quell-DB bleibt unveraendert"; c.close()
    def lauf_kaputt(cmd, check=False): return N(returncode=2)
    os.utime(dbq, (4, 4)); os.makedirs(os.path.join(S, "leer")); assert SV.bereinigen(dbq, os.path.join(S, "leer"), lauf=lauf_kaputt) == dbq, "gescheiterte Bereinigung: Mapper auf der Eingangs-DB (gemeldet)"
sj5 = os.path.join(S, "seiten5.json"); json.dump(seiten_json(True), open(sj5, "w"))
Lm, meld = SV.teile_im_modell(sj5, {"0": {f"n{i:02d}.jpg" for i in range(28)}, "1": {f"s{i:02d}.jpg" for i in range(11)}})
assert Lm[0]["im_modell"] == {"0": 28, "1": 0} and Lm[1]["im_modell"] == {"0": 0, "1": 11} and len(meld) == 1 and "Teil 1 (12 Bilder) FEHLT im Modell 0" in meld[0], (Lm, meld)
Lm, meld = SV.teile_im_modell(sj5, {"0": {f"n{i:02d}.jpg" for i in range(28)} | {f"s{i:02d}.jpg" for i in range(9)}}); assert len(meld) == 1 and "2 Bildteile ohne echte Verbindung" in meld[0], meld
Lm, meld = SV.teile_im_modell(sj5, {"0": {f"n{i:02d}.jpg" for i in range(28)}}); assert "in keinem Modell" in meld[0], meld
print("ok 5 sfm_seiten_vorstufe: Masken/Seitenerkennung wiederverwendet, nur neues Bild gerechnet, COLMAP-Maskennamen, Guard ohne 'verwechselt', Abbruch bei Fehler, Bereinigung 4 -> 2 Kameras, fehlende Seite gemeldet")
shutil.rmtree(S, ignore_errors=True)
