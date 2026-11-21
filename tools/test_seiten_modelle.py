#!/usr/bin/env python3
"""Fester Test (ohne GPU, Sekunden) fuer tools/sfm_seiten_modelle.py (21.11.2026: je Seite ein Kameramodell, je Seite eine dichte Wolke, vereinen).
Synthetischer Turm: 14 Nordbilder (x > 0, blicken nach -x) und 10 Suedbilder (x < 0, blicken nach +x), je Seite eigene Wandpunkte, KEIN gemeinsamer Punkt. Modell B (Sued) steht
in einem eigenen System (gedreht, 0,7-fach, verschoben); die wahre Abbildung B -> A ist bekannt.
  1 modelle_zusammen     vereintes Modell: alle 24 Bilder mit ihren Bild-IDs, Standorte der Suedbilder = Wahrheit (1e-6), Bildfehler < 0,01 px, Punktzahl = Summe, eine Kamera-ID
                         mit verschiedenen Werten in A und B bekommt fuer B eine neue ID, Datei laesst sich neu lesen; Bild doppelt / Spiegelung -> ValueError, nichts geschrieben
  2 wolken_zusammen      fused.ply: Punkte und Normalen von B umgerechnet, Punktzahl im Kopf; fremdes Format -> ValueError.   tiefenkarte_skalieren: Kopf bleibt, Werte x Massstab
  3 lauf_wahl            mehr Bilder > kleinerer Bildfehler > a; nur ein Lauf
  4 Kette mit Attrappen  (COLMAP, dicht_modell, seiten_vereinen ersetzt; modell_lage_vergleich, brennweite_schaerfe, seiten_blick_tor laufen echt):
                         a) rc 0 -> 'vereint': sparse 24 Bilder, vereinte dichte Wolke + Arbeitsordner (Tiefenkarte B skaliert), einsetzen -> sparse/0; zweiter Aufruf rechnet nichts neu
                         b) rc 3 -> Teil A allein, Meldung mit Pruefwerten      c) rc 0 mit GEKLEBTER Abbildung -> Blick-Tor faellt durch, Teil wieder heraus
                         d) nur ein grosser Teil -> 'grund', nichts gerechnet   e) kleiner Teil wird gemeldet
  5 Verdrahtung          iphone_sfm.py, pipeline_objekt.py und gesamtkette.py rufen das Werkzeug bzw. lesen seinen Bericht (Werkzeug ohne Aufrufer = Fehler);
                         pipeline_objekt.seiten_dicht_uebernehmen: dicht/ wird Verknuepfung auf die fertige Wolke (keine zweite Rechnung); vorhandenes dicht/ bleibt; Wolke aelter
                         als das Netz oder leer -> nicht uebernommen
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_modelle.py (pycolmap)."""
import os, sys, json, tempfile, shutil, io, contextlib
import pycolmap
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import sfm_seiten_modelle as SM

S = tempfile.mkdtemp(prefix="test_seiten_modelle_"); rng = np.random.default_rng(3); W, H = 1600, 1200


def blick(C, ziel, hoch=(0, 0, 1)):
    z = np.asarray(ziel, float) - C; z /= np.linalg.norm(z); x = np.cross(z, hoch); x /= np.linalg.norm(x); y = np.cross(z, x); R = np.array([x, y, z]); return R, -R @ np.asarray(C, float)


def quat(R):
    w = np.sqrt(max(0.0, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    if w > 1e-6: return w, (R[2, 1] - R[1, 2]) / (4 * w), (R[0, 2] - R[2, 0]) / (4 * w), (R[1, 0] - R[0, 1]) / (4 * w)
    i = int(np.argmax(np.diag(R))); j, k = (i + 1) % 3, (i + 2) % 3; s = np.sqrt(1 + R[i, i] - R[j, j] - R[k, k]) * 2; q = [0.0] * 4
    q[0] = (R[k, j] - R[j, k]) / s; q[1 + i] = s / 4; q[1 + j] = (R[j, i] + R[i, j]) / s; q[1 + k] = (R[k, i] + R[i, k]) / s; return tuple(q)


def modell(name, bilder, punkte, kam):
    """bilder = [dict(id, name, kam, C, ziel)], punkte = {id: xyz}, kam = {id: f} -> COLMAP-Textmodell <S>/<name> (PINHOLE ohne Verzeichnung, Beobachtung = exakte Projektion)."""
    d = os.path.join(S, name); os.makedirs(d, exist_ok=True); spur = {p: [] for p in punkte}; zi = []
    for b in bilder:
        R, t = blick(np.asarray(b["C"], float), b["ziel"]); q = quat(R); f = kam[b["kam"]]; obs = []
        for p, X in punkte.items():
            pc = R @ X + t; xy = f * pc[:2] / pc[2] + [W / 2, H / 2]
            if pc[2] > 0.1 and 0 <= xy[0] < W and 0 <= xy[1] < H: spur[p].append((b["id"], len(obs))); obs.append(f"{xy[0]:.6f} {xy[1]:.6f} {p}")
        zi.append(f"{b['id']} {q[0]:.14f} {q[1]:.14f} {q[2]:.14f} {q[3]:.14f} {t[0]:.12f} {t[1]:.12f} {t[2]:.12f} {b['kam']} {b['name']}\n{' '.join(obs)}\n")
    open(os.path.join(d, "cameras.txt"), "w").write("".join(f"{c} PINHOLE {W} {H} {f} {f} {W / 2} {H / 2}\n" for c, f in kam.items()))
    open(os.path.join(d, "images.txt"), "w").write("".join(zi))
    open(os.path.join(d, "points3D.txt"), "w").write("".join(f"{p} {x[0]:.9f} {x[1]:.9f} {x[2]:.9f} 200 100 50 0.5 " + " ".join(f"{a} {b}" for a, b in spur[p]) + "\n" for p, x in punkte.items() if len(spur[p]) >= 2))
    return d


def binaer(textordner, ziel):
    os.makedirs(ziel, exist_ok=True); pycolmap.Reconstruction(textordner).write(ziel); return ziel


# Szene: Nord 14 Bilder (IDs 1-14; Kamera 1 Fotos, Kamera 2 'Videoclip'), Sued 10 Bilder (IDs 15-24; Kamera 2 = derselbe Clip, in B ANDERS ausgeglichen, Kamera 3)
PN = {i + 1: np.array([2 + rng.uniform(-0.6, 0.6), rng.uniform(-5, 5), rng.uniform(0, 30)]) for i in range(70)}
PS = {i + 1: np.array([-2 + rng.uniform(-0.6, 0.6), rng.uniform(-5, 5), rng.uniform(0, 30)]) for i in range(60)}       # Punkt-IDs ueberschneiden sich mit Nord (wie bei zwei Mapper-Laeufen)
BN = [dict(id=i + 1, name=f"eigen__n{i:02d}.jpg" if i < 12 else f"clip__vf_{i:03d}.jpg", kam=1 if i < 12 else 2, C=(rng.uniform(40, 55), -22 + 3.3 * i, rng.uniform(1.6, 8)), ziel=(2, rng.uniform(-1, 1), 15)) for i in range(14)]
BS = [dict(id=15 + i, name=f"clip__vf_{100 + i:03d}.jpg" if i < 5 else f"eigen__s{i:02d}.jpg", kam=2 if i < 5 else 3, C=(rng.uniform(-55, -40), -15 + 3.3 * i, rng.uniform(1.6, 8)), ziel=(-2, rng.uniform(-1, 1), 15)) for i in range(10)]
mA_txt = modell("A_txt", BN, PN, {1: 1200.0, 2: 1000.0}); mB_wahr_txt = modell("B_wahr_txt", BS, PS, {2: 1010.0, 3: 1300.0})
mA = binaer(mA_txt, os.path.join(S, "A")); mBw = binaer(mB_wahr_txt, os.path.join(S, "B_wahr"))
# B in ein eigenes System legen: X_b = G(X_welt); wahre Abbildung B -> A ist G^-1
w_ = np.radians(37.0); Rg = np.array([[np.cos(w_), -np.sin(w_), 0], [np.sin(w_), np.cos(w_), 0], [0, 0, 1]]) @ np.array([[1, 0, 0], [0, np.cos(0.4), -np.sin(0.4)], [0, np.sin(0.4), np.cos(0.4)]])
G = np.eye(4); G[:3, :3] = 0.7 * Rg; G[:3, 3] = [3.0, -8.0, 1.5]; M_wahr = np.linalg.inv(G)
rB = pycolmap.Reconstruction(mBw); rB.transform(pycolmap.Sim3d(0.7, pycolmap.Rotation3d(Rg), G[:3, 3])); mB = os.path.join(S, "B"); os.makedirs(mB); rB.write(mB)
ORT = {b["name"]: np.asarray(b["C"], float) for b in BN + BS}

# ---------- 1 modelle_zusammen
z1 = os.path.join(S, "vereint1"); e1 = SM.modelle_zusammen([(mA, None), (mB, M_wahr)], z1)
V = pycolmap.Reconstruction(z1); rA = pycolmap.Reconstruction(mA)
assert V.num_reg_images() == 24 and e1["bilder"] == 24, f"vereintes Modell {V.num_reg_images()} statt 24 Bilder"
assert sorted(V.images) == list(range(1, 25)), "Bild-IDs nicht erhalten"
ab = max(float(np.linalg.norm(im.projection_center() - ORT[im.name])) for im in V.images.values()); assert ab < 1e-6, f"Standorte im vereinten Modell {ab} neben der Wahrheit"
assert V.num_points3D() == rA.num_points3D() + rB.num_points3D() == e1["punkte"], f"Punkte {V.num_points3D()} statt {rA.num_points3D()} + {rB.num_points3D()}"
XS = np.array(list(PS.values())); pb = [p.xyz for p in V.points3D.values() if p.xyz[0] < 0]; assert len(pb) == rB.num_points3D() and max(np.linalg.norm(XS - x, axis=1).min() for x in pb) < 1e-6, "Suedpunkte nicht an der wahren Stelle"
assert e1["kameras_neu"] == 1 and V.num_cameras() == 4, f"Kamera 2 (in A und B verschieden) nicht getrennt: {V.num_cameras()} Kameras, {e1['kameras_neu']} neu"
kn = {im.name: V.cameras[im.camera_id].params[0] for im in V.images.values()}
assert kn["clip__vf_012.jpg"] == 1000.0 and kn["clip__vf_100.jpg"] == 1010.0 and kn["eigen__s07.jpg"] == 1300.0 and kn["eigen__n00.jpg"] == 1200.0, f"Kamerawerte vertauscht: {kn}"
assert sum(im.num_points3D for im in V.images.values()) == sum(len(p.track.elements) for p in V.points3D.values()) > 500, "Spuren und Bildpunkte uneins"
assert all(abs(p.error - 0.5) < 1e-9 for p in V.points3D.values()), "Punktfehler nicht uebernommen"
V.update_point_3d_errors(); fe = V.compute_mean_reprojection_error(); assert fe < 0.01, f"Bildfehler des vereinten Modells {fe} px (neu gerechnet aus Lage, Kamera, Punkt)"
assert V.num_rigs() == 4 and V.num_frames() == 24 and os.path.isfile(os.path.join(z1, "vereint.json")) and os.path.isfile(os.path.join(z1, "frames.bin"))
for teile, was in (([(mA, None), (mA, None)], "Bild doppelt"), ([(mA, None), (mB, np.diag([1.0, 1.0, -1.0, 1.0]))], "Spiegelung")):
    zf = os.path.join(S, "darf_nicht")
    try: SM.modelle_zusammen(teile, zf); raise AssertionError(f"{was}: kein Fehler")
    except ValueError: pass
    assert not os.path.exists(zf), f"{was}: trotz Fehler geschrieben"
print(f"ok 1: vereintes Modell 24 Bilder, {V.num_points3D()} Punkte, Standorte {ab:.1e} neben der Wahrheit, Bildfehler {fe:.1e} px, 1 Kamera neu nummeriert")


# ---------- 2 dichte Wolke / Tiefenkarte
def ply(p, X, Nn):
    d = np.zeros(len(X), SM.PLY_SATZ); d["p"] = X; d["n"] = Nn; d["c"] = 99
    open(p, "wb").write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % len(X)).encode() + d.tobytes())


XA = np.array(list(PN.values())); XBw = XS; XB = XBw @ G[:3, :3].T + G[:3, 3]; nA = np.tile([1.0, 0, 0], (len(XA), 1)); nBw = np.tile([-1.0, 0, 0], (len(XBw), 1)); nB = nBw @ Rg.T
ply(os.path.join(S, "fa.ply"), XA, nA); ply(os.path.join(S, "fb.ply"), XB, nB)
n2 = SM.wolken_zusammen([(os.path.join(S, "fa.ply"), None), (os.path.join(S, "fb.ply"), M_wahr)], os.path.join(S, "fv.ply")); kopf = SM.ply_kopf(os.path.join(S, "fv.ply"))
d = np.frombuffer(open(os.path.join(S, "fv.ply"), "rb").read()[kopf[1]:], SM.PLY_SATZ)
assert n2 == kopf[0] == len(d) == len(XA) + len(XB), f"Punktzahl {n2}/{kopf[0]}/{len(d)}"
assert np.abs(d["p"][:len(XA)] - XA).max() < 1e-5 and np.abs(d["p"][len(XA):] - XBw).max() < 1e-4 and np.abs(d["n"][len(XA):] - nBw).max() < 1e-5 and (d["c"] == 99).all(), "vereinte Wolke: Punkte/Normalen von B falsch umgerechnet"
open(os.path.join(S, "fremd.ply"), "wb").write(b"ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nend_header\n0\n")
try: SM.wolken_zusammen([(os.path.join(S, "fa.ply"), None), (os.path.join(S, "fremd.ply"), M_wahr)], os.path.join(S, "fx.ply")); raise AssertionError("fremdes PLY-Format angenommen")
except ValueError: pass
assert not os.path.exists(os.path.join(S, "fx.ply"))
open(os.path.join(S, "t.bin"), "wb").write(b"2&2&1&" + np.array([1, 2, 0, 4], "<f4").tobytes()); SM.tiefenkarte_skalieren(os.path.join(S, "t.bin"), os.path.join(S, "t2.bin"), 0.5)
b2 = open(os.path.join(S, "t2.bin"), "rb").read(); assert b2[:6] == b"2&2&1&" and np.allclose(np.frombuffer(b2[6:], "<f4"), [0.5, 1, 0, 2]), "Tiefenkarte falsch skaliert"
print(f"ok 2: vereinte Wolke {n2} Punkte (B umgerechnet, Normalen gedreht), fremdes Format abgelehnt, Tiefenkarte skaliert")

# ---------- 3 lauf_wahl
w = lambda b, f: dict(bilder=b, fehler_px=f)
assert SM.lauf_wahl(w(538, 0.91), w(538, 1.00), 538)[0] == "a" and SM.lauf_wahl(w(538, 1.2), w(536, 0.9), 538)[0] == "b", "kleiner Bildunterschied: der kleinere Bildfehler entscheidet"
assert SM.lauf_wahl(w(500, 0.9), w(538, 1.2), 538)[0] == "b" and SM.lauf_wahl(w(101, 1.0), w(99, 0.5), 102)[0] == "a", "deutlich mehr Bilder entscheiden vor dem Bildfehler"
assert SM.lauf_wahl(None, w(5, 1), 30)[0] == "b" and SM.lauf_wahl(w(5, 1), None, 30)[0] == "a" and SM.lauf_wahl(None, None, 30)[0] is None and SM.lauf_wahl(w(9, 1), w(9, 1), 30)[0] == "a"
print("ok 3: Wahl des Laufs (mehr Bilder, dann Bildfehler, sonst a)")

# ---------- 4 Kette mit Attrappen
mA_b = modell("A_b_txt", BN[:-2], PN, {1: 1200.0, 2: 1000.0})                           # Lauf b von Teil 0: zwei Bilder weniger
Rz = np.diag([-1.0, -1.0, 1.0, 1.0]); M_kleb = Rz @ M_wahr                               # halbe Drehung um die Turmachse: Sued steht auf der Nordseite = verklebt
ZAHL = {}


def attrappe(vereinen_rc=0, matrix=M_wahr):
    def lauf(cmd, log=None):
        was = os.path.basename(cmd[2]) if cmd[0] == SM.PYC else cmd[1]; ZAHL[was] = ZAHL.get(was, 0) + 1
        if was == "view_graph_calibrator": return 0
        if was == "global_mapper":
            aus = cmd[cmd.index("--output_path") + 1]; namen = open(cmd[cmd.index("--GlobalMapper.image_list_path") + 1]).read().split(); nord = namen[0] in {b["name"] for b in BN}
            assert set(namen) == {b["name"] for b in (BN if nord else BS)}, "Bildliste des Teils falsch"; assert os.path.isfile(cmd[cmd.index("--database_path") + 1]), "Mapper ohne DB-Kopie"
            binaer((mA_b if aus.endswith("_b") else mA_txt) if nord else mB, os.path.join(aus, "0")) if nord else shutil.copytree(mB, os.path.join(aus, "0")); return 0
        if was == "dicht_modell.py":
            sp, dd = cmd[3], cmd[5]; r = pycolmap.Reconstruction(sp); nord = "eigen__n00.jpg" in {im.name for im in r.images.values()}
            for u in ("images", "stereo/depth_maps", "stereo/normal_maps"): os.makedirs(os.path.join(dd, u), exist_ok=True)
            shutil.copytree(sp, os.path.join(dd, "sparse"), dirs_exist_ok=True)
            for im in r.images.values():
                open(os.path.join(dd, "images", im.name), "w").write("x"); open(os.path.join(dd, "stereo", "depth_maps", im.name + ".photometric.bin"), "wb").write(b"1&1&1&" + np.array([10.0], "<f4").tobytes())
                open(os.path.join(dd, "stereo", "normal_maps", im.name + ".photometric.bin"), "wb").write(b"1&1&3&" + np.zeros(3, "<f4").tobytes()); open(os.path.join(dd, "stereo", "fusion.cfg"), "a").write(im.name + "\n")
            ply(os.path.join(dd, "fused.ply"), XA if nord else XB, nA if nord else nB); return 0
        if was == "seiten_vereinen.py":
            assert cmd[5].endswith("ursprung.db") and "--dicht-a" in cmd and "--dicht-b" in cmd, "seiten_vereinen ohne Ursprungs-DB oder ohne dichte Wolken"
            aus = cmd[cmd.index("--aus") + 1]; os.makedirs(aus, exist_ok=True); v = dict(ok=vereinen_rc == 0, urteil="vereint" if vereinen_rc == 0 else "Achse 24.4 % uneinig", pruefung=dict(achse_einigkeit=0.0136 if vereinen_rc == 0 else 0.244, blick_nachher=151.0))
            if vereinen_rc != 2: v["B_nach_A"] = matrix.tolist()
            json.dump(v, open(os.path.join(aus, "vereinen.json"), "w")); return vereinen_rc
        return SM._lauf(cmd, log)                                                        # modell_lage_vergleich, brennweite_schaerfe, seiten_blick_tor: echt
    return lauf


def arbeit(name, teile=((0, BN), (1, BS))):
    w_ = os.path.join(S, name); os.makedirs(w_); gem = {}
    for g, B in teile: gem.update({b["name"]: g for b in B})
    gem.update({f"eigen__klein{i}.jpg": 7 for i in range(6)}); gem.update({f"eigen__mini{i}.jpg": 8 for i in range(2)})
    json.dump(dict(gemeinschaft=gem, seiten=[dict(gruppen=[g], bilder=len(B)) for g, B in teile] + [dict(gruppen=[7], bilder=6), dict(gruppen=[8], bilder=2)], verbindungen=[dict(a=0, b=1, urteil="verwechselt", paare=50)]), open(os.path.join(w_, "seiten.json"), "w"))
    for n in ("db_mapper.db", "ursprung.db"): open(os.path.join(w_, n), "w").write(n)
    return w_


def kette(w_, **k):
    puffer = io.StringIO(); SM.LAUF = attrappe(**k)
    try:
        with contextlib.redirect_stdout(puffer): rc = SM.main([w_, os.path.join(S, "fotos"), "--db-ursprung", os.path.join(w_, "ursprung.db"), "--min-bilder", "8", "--einsetzen"])
    finally: SM.LAUF = SM._lauf
    return rc, puffer.getvalue(), json.load(open(os.path.join(w_, "seiten_modelle.json")))


# a) vereint
wa_ = arbeit("ka"); ZAHL.clear(); rc, aus, B = kette(wa_); assert rc == 0, f"Kette a rc {rc}\n{aus[-1500:]}"
t0, t1 = [t for t in B["teile"] if t.get("gerechnet")]; E = B["ergebnis"]
assert ZAHL["global_mapper"] == 4 and ZAHL["view_graph_calibrator"] == 1 and ZAHL["dicht_modell.py"] == 2 and ZAHL["seiten_vereinen.py"] == 1 and ZAHL["seiten_blick_tor.py"] == 1, f"Aufrufe {ZAHL}"
assert t0["gewaehlt"] == "a" and "mehr registrierte Bilder" in t0["regel"] and t0["laeufe"]["a"]["bilder"] == 14 and t0["laeufe"]["b"]["bilder"] == 12, f"Wahl Teil 0: {t0['gewaehlt']} {t0['regel']}"
assert t0["ab"] and t0["ab"]["gemeinsam"] == 12 and t0["ab"]["lage_median_proz"] < 0.01 and t1["ab"]["gemeinsam"] == 10, f"a/b-Abweichung fehlt: {t0.get('ab')}"
assert t0["sperrliste"]["bilder"] is not None and all("sekunden" in t["laeufe"][l] for t in (t0, t1) for l in "ab")
assert B["teil_a"] == 0 and B["vereint"] == [0, 1] and B["nicht_vereint"] == [] and E["art"] == "vereint" and t1["vereinen"]["rc"] == 0 and t1["vereinen"]["blick_tor"] == 0, f"nicht vereint: {B.get('vereint')} {E}\n{aus[-800:]}"
assert pycolmap.Reconstruction(E["sparse"]).num_reg_images() == 24 and pycolmap.Reconstruction(os.path.join(wa_, "sparse", "0")).num_reg_images() == 24 and os.path.isfile(os.path.join(wa_, "sparse", "0", "vereint.json")), "vereintes Modell nicht eingesetzt"
assert SM.ply_kopf(E["fused"])[0] == len(XA) + len(XB) == E["punkte"] and pycolmap.Reconstruction(os.path.join(E["dicht"], "sparse")).num_reg_images() == 24 and len(os.listdir(os.path.join(E["dicht"], "images"))) == 24
tk = lambda n: float(np.frombuffer(open(os.path.join(E["dicht"], "stereo", "depth_maps", n + ".photometric.bin"), "rb").read()[6:], "<f4")[0])
assert abs(tk("eigen__n00.jpg") - 10.0) < 1e-6 and abs(tk("eigen__s07.jpg") - 10.0 / 0.7) < 1e-4, f"Tiefenkarten im vereinten Ordner: A {tk('eigen__n00.jpg')}, B {tk('eigen__s07.jpg')} (soll 10 und 14,29)"
assert len(open(os.path.join(E["dicht"], "stereo", "fusion.cfg")).read().split()) == 24 and os.path.getmtime(E["fused"]) >= os.path.getmtime(os.path.join(wa_, "sparse", "0", "images.bin")), "dichte Wolke aelter als das eingesetzte Netz"
assert any("Teil 2 (6 Bilder) unter 8" in m for m in B["meldungen"]) and any("1 Bildteil(e) mit weniger als 5" in m for m in B["meldungen"]), f"kleine Teile nicht gemeldet: {B['meldungen']}"
assert not os.path.exists(os.path.join(wa_, "seiten_modelle", "db_global.db")), "DB-Kopie nicht aufgeraeumt"
ZAHL.clear(); rc, aus, B2 = kette(wa_); n_neu = sum(ZAHL.get(k, 0) for k in ("global_mapper", "view_graph_calibrator", "dicht_modell.py", "seiten_vereinen.py", "modell_lage_vergleich.py", "brennweite_schaerfe.py"))
assert rc == 0 and n_neu == 0 and B2["ergebnis"]["art"] == "vereint" and os.path.isdir(os.path.join(wa_, "sparse", "0")), f"zweiter Aufruf rechnete neu: {ZAHL}"
assert len([d_ for d_ in os.listdir(wa_) if d_.startswith("sparse.alt_")]) == 1, "vorhandenes sparse/ nicht beiseitegelegt"
# b) abgelehnt
wb_ = arbeit("kb"); rc, aus, B = kette(wb_, vereinen_rc=3); E = B["ergebnis"]
assert rc == 0 and E["art"] == "teil_a_allein" and B["vereint"] == [0] and B["nicht_vereint"] == [1] and pycolmap.Reconstruction(os.path.join(wb_, "sparse", "0")).num_reg_images() == 14, f"rc 3: {E}"
assert any("Teil 1 (10 Bilder) NICHT vereint" in m and "ABGELEHNT" in m and "0.244" in m for m in B["meldungen"]) and any("ALLEIN" in m for m in B["meldungen"]) and "ACHTUNG SEITENMODELLE" in aus, f"Ablehnung nicht gemeldet: {B['meldungen']}"
assert SM.ply_kopf(E["fused"])[0] == len(XA) and E["dicht"].endswith(os.path.join("teil0", "dicht"))
wb2 = arbeit("kb2"); rc, aus, B = kette(wb2, vereinen_rc=2); assert B["ergebnis"]["art"] == "teil_a_allein" and any("zu wenige Verbindungen" in m for m in B["meldungen"]), "rc 2 nicht gemeldet"
# c) geklebt
wc_ = arbeit("kc"); rc, aus, B = kette(wc_, matrix=M_kleb); t1 = [t for t in B["teile"] if t.get("gerechnet")][1]
assert B["ergebnis"]["art"] == "teil_a_allein" and t1["vereinen"]["blick_tor"] == 3 and any("Blick-Tor" in m and "DURCH" in m for m in B["meldungen"]) and pycolmap.Reconstruction(os.path.join(wc_, "sparse", "0")).num_reg_images() == 14, f"verklebte Abbildung nicht abgefangen: {B['meldungen']}"
# d) nur ein grosser Teil
wd_ = arbeit("kd", teile=((0, BN),)); ZAHL.clear(); rc, aus, B = kette(wd_); assert rc == 2 and B.get("grund") and not ZAHL and not os.path.isdir(os.path.join(wd_, "sparse")), f"ein Teil: rc {rc}, {ZAHL}"
print("ok 4: Kette - vereint (24 Bilder, Wolke, Tiefenkarten, Wiederverwendung), abgelehnt/zu wenig -> Teil A allein gemeldet, verklebt -> Blick-Tor, ein Teil -> nichts gerechnet")

# ---------- 5 Verdrahtung
q = lambda n: open(os.path.join(T, n)).read()
assert "SM.modelle(" in q("iphone_sfm.py") and "SM.dicht_vereinen(" in q("iphone_sfm.py") and "RCPARK_SEITEN_MODELLE" in q("iphone_sfm.py"), "iphone_sfm.py ruft sfm_seiten_modelle nicht auf"
assert "seiten_modelle.json" in q("pipeline_objekt.py") and "seiten_modelle" in q("gesamtkette.py"), "pipeline_objekt.py/gesamtkette.py lesen seiten_modelle.json nicht"
import pipeline_objekt as PO
def daten(name, alter_wolke=0, leer=False):
    d_ = os.path.join(S, name); sp = os.path.join(d_, "sfm", "sparse", "0"); q_ = os.path.join(d_, "sfm", "seiten_modelle", "vereint", "dicht"); os.makedirs(sp); os.makedirs(q_)
    open(os.path.join(sp, "images.bin"), "w").write("x"); ply(os.path.join(q_, "fused.ply"), XA[:0] if leer else XA, nA[:0] if leer else nA)
    if alter_wolke: os.utime(os.path.join(q_, "fused.ply"), (os.path.getmtime(os.path.join(sp, "images.bin")) - alter_wolke,) * 2)
    json.dump(dict(ergebnis=dict(art="vereint", dicht=q_)), open(os.path.join(d_, "sfm", "seiten_modelle.json"), "w")); return d_, sp
with contextlib.redirect_stdout(io.StringIO()):
    d_, sp = daten("po1"); assert PO.seiten_dicht_uebernehmen(d_, sp) and os.path.islink(os.path.join(d_, "dicht")) and PO.ply_punkte(os.path.join(d_, "dicht", "fused.ply")) == len(XA), "dichte Wolke nicht uebernommen"
    assert not PO.seiten_dicht_uebernehmen(d_, sp), "vorhandenes dicht/ ueberschrieben"
    d_, sp = daten("po2", alter_wolke=60); assert not PO.seiten_dicht_uebernehmen(d_, sp) and not os.path.lexists(os.path.join(d_, "dicht")), "Wolke aelter als das Netz uebernommen"
    d_, sp = daten("po3", leer=True); assert not PO.seiten_dicht_uebernehmen(d_, sp), "leere Wolke uebernommen"
    d_, sp = daten("po4"); os.remove(os.path.join(d_, "sfm", "seiten_modelle.json")); assert not PO.seiten_dicht_uebernehmen(d_, sp), "ohne Bericht uebernommen"
print("ok 5: Verdrahtung in iphone_sfm.py, pipeline_objekt.py, gesamtkette.py; dichte Wolke wird uebernommen statt doppelt gerechnet")
shutil.rmtree(S, ignore_errors=True)
