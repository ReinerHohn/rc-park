#!/usr/bin/env python3
"""Fester Test (synthetisch, Sekunden, ohne GPU/pycolmap) fuer tools/seiten_querspur_binden.py (22.11.2026, Nulllauf schwabentor-1122f: per GPS vereinte Teile 1-3 m versetzt).
Synthetischer Turm 10 x 10 m, 20 m hoch. Teil A (Kameras im Norden/Westen) sieht Nord- und Westwand, Teil B (Sueden/Westen) Sued-, Westwand und die westliche Haelfte der
Nordwand. Die GPS-Lage von B liegt 4 m / 3 Grad / 5 % daneben (Bootstrap +-3,6 Grad / +-12 % wie Schwabentor Teil 1). Querpaare:
  - echte Querspuren (West-Kameras A und B, gleiche Weltpunkte, dazu 15 % falsche Zuordnungen),
  - ein Block falscher GEGENSEITEN-Paare (Kamera A blickt auf die Nordwand, Kamera B auf die Suedwand; Zuordnung Suedpunkt -> um die Turmachse gedrehter Nordpunkt).
  1 gemischt, Blick-Filter an  -> gebunden, wahre Lage (Drehung < 0,3 Grad, Lage < 0,15 m, Massstab < 0,5 %), Gegenseiten-Paare vom Blick-Filter verworfen, Doppelwand sinkt.
  2 gemischt, Blick-Filter AUS, Gegenseiten-Block mindestens so stark wie die echten -> das GPS-Veto allein findet die wahre Lage; beste Lage ohne Veto liegt ausserhalb des Korridors.
  3 nur Gegenseiten-Paare, Blick-Filter an  -> zu wenig Querspuren (rc 2), keine Matrix.
  4 nur Gegenseiten-Paare, Blick-Filter AUS -> keine Lage im GPS-Korridor, keine Matrix.
  5 GPS-Unsicherheit fehlt -> kein Veto -> nichts; Datenbank-Lesen (sqlite, Paar-Richtung A/B getauscht) richtig.
  6 Verdrahtung in sfm_seiten_modelle.py (Schalter RCPARK_QUERSPUR, Code-Stand, nur GPS-Weg, GPS-Ausgleich nach Bindung ausgelassen)."""
import os, sys, sqlite3, tempfile
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_querspur_binden as Q

rng = np.random.default_rng(7)


def rot_z(g):
    c, s = np.cos(np.radians(g)), np.sin(np.radians(g)); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rot_x(g):
    c, s = np.cos(np.radians(g)), np.sin(np.radians(g)); return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


# ---------- Welt (Meter): Turm um den Ursprung, Waende als Punktraster
W = {}; wand = {}
def raster(name, f):
    for u in np.linspace(0.3, 9.7, 18):
        for z in np.linspace(0.5, 19.5, 24):
            i = len(W); W[i] = f(u, z); wand[i] = name
raster("nord", lambda u, z: np.array([u - 5, 5.0, z])); raster("sued", lambda u, z: np.array([u - 5, -5.0, z])); raster("west", lambda u, z: np.array([-5.0, u - 5, z]))
dreh180 = lambda p: np.array([-p[0], -p[1], p[2]])                                    # halbe Drehung um die Turmachse (Gegenseite)
nord_von = {tuple(np.round(dreh180(W[i]), 6)): i for i in W if wand[i] == "nord"}

# Modelle: A = Welt / 2 (2 m je Einheit), B = beliebige Aehnlichkeit der Welt
MA = np.diag([0.5, 0.5, 0.5, 1.0]); RB = rot_x(20) @ rot_z(-70); MB = np.eye(4); MB[:3, :3] = 0.3 * RB; MB[:3, 3] = [3.0, -1.0, 2.0]
M_wahr = MA @ np.linalg.inv(MB)                                                       # B -> A
in_a = {i for i in W if wand[i] in ("nord", "west")}; in_b = {i for i in W if wand[i] in ("sued", "west") or (wand[i] == "nord" and W[i][0] < 0)}
XA = {i: Q.anwenden(MA, W[i] + rng.normal(0, 0.03, 3)[None])[0] for i in in_a}; XB = {100000 + i: Q.anwenden(MB, W[i] + rng.normal(0, 0.03, 3)[None])[0] for i in in_b}

# Kameras: blicken auf ihre Wand; Merkmal j = j-ter gesehener Punkt
def kamera(pos, ziel_wand, im_modell, M, off):
    sicht = sorted(i for i in im_modell if wand[i] == ziel_wand); b = np.mean([W[i] for i in sicht], 0) - pos; b /= np.linalg.norm(b)
    return dict(p3d=np.array([i + off for i in sicht], np.int64), blick=(M[:3, :3] / np.cbrt(np.linalg.det(M[:3, :3]))) @ b, C=Q.anwenden(M, pos[None])[0], welt=sicht)
KA, KB = {}, {}
for k in range(8): KA[f"a_west{k}"] = kamera(np.array([-25.0, -6 + 2 * k, 1.6]), "west", in_a, MA, 0); KA[f"a_nord{k}"] = kamera(np.array([-6 + 2 * k, 25.0, 1.6]), "nord", in_a, MA, 0)
for k in range(8): KB[f"b_west{k}"] = kamera(np.array([-25.0, -8 + 2 * k, 1.6]), "west", in_b, MB, 100000); KB[f"b_sued{k}"] = kamera(np.array([-6 + 2 * k, -25.0, 1.6]), "sued", in_b, MB, 100000)
ref_b = np.array([k["C"] for k in KB.values()]); lot = np.array([0, 0, 1.0])


def echte_paare(anzahl=8, falsch_anteil=0.15):
    L = []
    for k in range(anzahl):
        a, b = KA[f"a_west{k % 8}"], KB[f"b_west{(k + 1) % 8}"]; ja = {w: j for j, w in enumerate(a["welt"])}
        m = [(ja[w], j) for j, w in enumerate(b["welt"]) if w in ja]; n_f = int(falsch_anteil * len(m))
        m += [(int(rng.integers(len(a["welt"]))), int(rng.integers(len(b["welt"])))) for _ in range(n_f)]; L.append((f"a_west{k % 8}", f"b_west{(k + 1) % 8}", np.array(m)))
    return L


def gegenseiten_paare(anzahl=8, anteil=1.0):
    L = []
    for k in range(anzahl):
        a, b = KA[f"a_nord{k % 8}"], KB[f"b_sued{k % 8}"]; ja = {w: j for j, w in enumerate(a["welt"])}
        m = [(ja[nord_von[tuple(np.round(W[w], 6))]], j) for j, w in enumerate(b["welt"]) if nord_von.get(tuple(np.round(W[w], 6))) in ja and (j % 100) < 100 * anteil]
        L.append((f"a_nord{k % 8}", f"b_sued{k % 8}", np.array(m)))
    return L


# GPS-Lage von B: 4 m waagerecht, 3 Grad um das Lot (um die Mitte der B-Kameras), 5 % Massstab daneben - im A-System
c = np.median(Q.anwenden(M_wahr, ref_b), 0); F = np.eye(4); F[:3, :3] = 1.05 * rot_z(3.0); F[:3, 3] = c - 1.05 * rot_z(3.0) @ c + np.array([2.0, 0.0, 0.0])   # 2 Einheiten = 4 m
M_gps = F @ M_wahr
VJ = dict(ok=True, B_nach_A=M_gps.tolist(), pruefung=dict(dreh_sd_grad=3.61, mass_sd_rel=0.1205), rahmen_a=dict(massstab=2.0, inlier=125, rest_median_m=5.04), rahmen_b=dict(massstab=1.0, inlier=24, rest_median_m=1.81))
G = Q.gps_unsicherheit(VJ); assert isinstance(G, dict) and G["m_je_einheit"] == 2.0 and G["lage_sd_m"] == Q.LAGE_MIN_M, f"GPS-Unsicherheit: {G}"
assert Q.korridor(M_gps, G, lot, ref_b)["im_korridor"] and Q.korridor(M_wahr, G, lot, ref_b)["im_korridor"], "wahre Lage liegt nicht im GPS-Korridor (Testaufbau)"
kl = np.eye(4); kl[:3, :3] = rot_z(180.0); assert not Q.korridor(kl @ M_wahr, G, lot, ref_b)["im_korridor"], "Gegenseite liegt im Korridor"


def lage_fehler(M):
    s, R, _ = Q.zerlege(M @ np.linalg.inv(M_wahr)); d = np.median(np.linalg.norm(Q.anwenden(M, ref_b) - Q.anwenden(M_wahr, ref_b), axis=1)) * 2.0
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))), float(d), float(s - 1)


# 1 gemischt, Blick-Filter an
e = Q.binden(KA, KB, XA, XB, echte_paare() + gegenseiten_paare(), G, lot, ref_b)
assert e["ok"] and "B_nach_A" in e, f"1: nicht gebunden: {e['urteil']} {e['pruefung']}"
w, d, s = lage_fehler(np.array(e["B_nach_A"])); w0, d0, s0 = lage_fehler(M_gps)
assert w < 0.3 and d < 0.15 and abs(s) < 0.005, f"1: Lage falsch: {w:.3f} Grad, {d:.3f} m, Massstab {s:+.4f} (GPS: {w0:.2f} Grad, {d0:.2f} m, {s0:+.3f})"
assert e["pruefung"]["paare_blick_ok"] == 8 and e["pruefung"]["paare_gesamt"] == 16, f"1: Gegenseiten-Paare nicht vom Blick-Filter verworfen: {e['pruefung']}"
dw = e["doppelwand"]; assert dw and dw["nach"]["median_m"] < 0.15 and dw["vor"]["median_m"] > 3 * dw["nach"]["median_m"], f"1: Doppelwand {dw}"
print(f"ok 1: gemischt -> gebunden ({w:.3f} Grad, {d:.3f} m, Massstab {100 * s:+.2f} %; GPS lag {w0:.1f} Grad / {d0:.1f} m / {100 * s0:+.0f} % daneben), Doppelwand {dw['vor']['median_m']} -> {dw['nach']['median_m']} m")

# 2 Blick-Filter aus: Gegenseiten-Block mindestens so stark wie die echten -> ABGELEHNT (Querpaare mehrheitlich Verwechslung, Korridor-Lage nicht belegt);
#   Gegenseiten-Block schwaecher (ein Viertel der Punkte) -> das GPS-Veto allein haelt die wahre Lage
e = Q.binden(KA, KB, XA, XB, echte_paare(4) + gegenseiten_paare(8), G, lot, ref_b, max_azimut=180.0); bo = e["pruefung"]["bester_ohne_gps"]
assert not e["ok"] and "B_nach_A" not in e and "mehrheitlich Gegenseite" in e["urteil"] and not bo["im_korridor"], f"2a: Gegenseiten-Mehrheit nicht abgelehnt: {e['urteil']} {bo}"
e = Q.binden(KA, KB, XA, XB, echte_paare(4) + gegenseiten_paare(8, anteil=0.25), G, lot, ref_b, max_azimut=180.0); bo = e["pruefung"]["bester_ohne_gps"]
assert e["ok"], f"2b: nicht gebunden: {e['urteil']}"
w, d, s = lage_fehler(np.array(e["B_nach_A"]))
assert w < 0.3 and d < 0.15 and abs(s) < 0.005 and bo["im_korridor"], f"2b: GPS-Veto fand die wahre Lage nicht: {w:.3f} Grad, {d:.3f} m, {bo}"
print("ok 2: Blick-Filter aus - Gegenseiten-Mehrheit abgelehnt; Gegenseite in der Minderheit -> wahre Lage gebunden")

# 3 nur Gegenseiten-Paare, Blick-Filter an
e = Q.binden(KA, KB, XA, XB, gegenseiten_paare(), G, lot, ref_b)
assert not e["ok"] and e.get("zu_wenig") and "B_nach_A" not in e and e["pruefung"]["paare_blick_ok"] == 0, f"3: {e}"
# 4 nur Gegenseiten-Paare, Blick-Filter aus
e = Q.binden(KA, KB, XA, XB, gegenseiten_paare(), G, lot, ref_b, max_azimut=180.0)
assert not e["ok"] and "B_nach_A" not in e and "GPS-Korridor" in e["urteil"], f"4: {e['urteil']}"
print("ok 3/4: nur Gegenseiten-Paare -> nichts uebernommen (Blick-Filter: zu wenig; ohne Filter: keine Lage im GPS-Korridor)")

# 7 SCHWABENTOR 1122 nachgestellt (Voragent auf DB-Kopie): 559 Querpaare, nur 39 unter 110 Grad Blickunterschied, 1691 3D-3D-Paare, deren Konsens 167 Grad x1,21 neben
#   der GPS-Lage liegt (Gegenseiten-Verwechslung) -> nichts uebernehmen, mit und ohne Blick-Filter
r7 = np.random.default_rng(11); F7 = np.eye(4); F7[:3, :3] = 1.21 * rot_z(167.0)
KA7, KB7, XA7, XB7, P7 = {}, {}, {}, {}, []
for i in range(1691):
    w_ = np.array([r7.uniform(-5, 5), r7.choice([-5.0, 5.0]), r7.uniform(0.5, 19.5)]) if i % 2 else np.array([r7.choice([-5.0, 5.0]), r7.uniform(-5, 5), r7.uniform(0.5, 19.5)])
    XB7[300000 + i] = Q.anwenden(MB, w_[None])[0]; XA7[200000 + i] = Q.anwenden(MA @ F7, (w_ + r7.normal(0, 0.03, 3))[None])[0]
for j in range(559):
    ids = [i for i in range(1691) if i % 559 == j]; az = 60.0 if j < 39 else 170.0; ba = np.array([1.0, 0, 0]); bw = rot_z(az) @ ba
    KA7[f"a{j}"] = dict(p3d=np.array([200000 + i for i in ids], np.int64), blick=ba); KB7[f"b{j}"] = dict(p3d=np.array([300000 + i for i in ids], np.int64), blick=Q.zerlege(M_gps)[1].T @ bw)
    P7.append((f"a{j}", f"b{j}", np.c_[np.arange(len(ids)), np.arange(len(ids))]))
ref7 = np.array([Q.anwenden(MB, np.array([[-25.0, y, 1.6]]))[0] for y in range(-8, 9, 2)])
for ma in (Q.MAX_AZIMUT_GRAD, 180.0):
    e = Q.binden(KA7, KB7, XA7, XB7, P7, G, lot, ref7, max_azimut=ma); pr = e["pruefung"]
    assert not e["ok"] and "B_nach_A" not in e, f"7: Schwabentor-Verwechslung uebernommen (Blick {ma}): {e['urteil']}"
    assert pr["paare_blick_ok"] == (39 if ma < 180 else 559), f"7: Blick-Filter {pr}"
    bo = pr.get("bester_ohne_gps") or {}; assert bo and not bo["im_korridor"] and abs(abs(bo["dreh_lot_grad"]) - 164) < 2, f"7: Fremdlage nicht als 167 Grad (gegen die 3 Grad verdrehte GPS-Lage: 164) erkannt: {bo}"
print(f"ok 7: Schwabentor-1122-Lage (559 Querpaare, 39 unter 110 Grad, 1691 Zuordnungen, Konsens 167 Grad x1,21) -> abgelehnt: {e['urteil'][:110]}")

# 5 GPS fehlt; Datenbank lesen
assert isinstance(Q.gps_unsicherheit(dict(ok=True, B_nach_A=np.eye(4).tolist(), pruefung=dict(dreh_sd_grad=2.0, mass_sd_rel=0.08))), str), "GPS-Rahmen fehlt, trotzdem Veto"
assert isinstance(Q.gps_unsicherheit(dict(ok=False)), str)
with tempfile.TemporaryDirectory() as td:
    db = os.path.join(td, "t.db"); con = sqlite3.connect(db); con.execute("create table images (image_id integer, name text)"); con.execute("create table two_view_geometries (pair_id integer, rows integer, cols integer, data blob)")
    for i, n in ((1, "b1"), (2, "a1"), (3, "a2")): con.execute("insert into images values (?, ?)", (i, n))
    m = np.array([[5, 7]] * 20, np.uint32); con.execute("insert into two_view_geometries values (?, ?, 2, ?)", (1 * Q.MAXID + 2, 20, m.tobytes()))   # Bild 1 (B) zuerst
    con.execute("insert into two_view_geometries values (?, ?, 2, ?)", (1 * Q.MAXID + 3, 10, m[:10].tobytes())); con.commit(); con.close()
    L = Q.querpaare(db, {"a1", "a2"}, {"b1"})
    assert len(L) == 1 and L[0][0] == "a1" and L[0][1] == "b1" and (L[0][2] == [7, 5]).all(), f"5: Querpaare falsch gelesen: {L}"
print("ok 5: ohne GPS-Rahmen kein Veto; Datenbank (nur lesend, Richtung getauscht, < 15 Inlier weg)")

# 6 Verdrahtung
q = open(os.path.join(T, "sfm_seiten_modelle.py")).read()
assert "seiten_querspur_binden.py" in q and "RCPARK_QUERSPUR" in q and '"seiten_querspur_binden.py"' in q.split("NACHSTUFE = (")[1].split(")")[0], "sfm_seiten_modelle: Stufe/Schalter/Code-Stand fehlt"
print("ok 6: Verdrahtung in sfm_seiten_modelle.py")
print("ALLE TESTS BESTANDEN")
