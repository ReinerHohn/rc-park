#!/usr/bin/env python3
"""Mini-Test (< 2 s, ohne pycolmap) tools/ausrichtung_zusatz.py + gesamtkette.kanten_mit_zusatz (28.11.2026: registrierte Handyfotos gingen nur in die dichte
Wolke, nicht in die Kantenstufe).
  1 Zusatznetz im SfM-Rahmen der Ausrichtung: Referenzbilder bestehen das Rahmen-Tor, neue Kamera projiziert einen Modellpunkt wie die SfM-Pose (< 1e-6 px)
  2 Zusatznetz in ANDEREM Rahmen (Referenzbilder 1 m versetzt) -> abgelehnt mit Grund, keine neue Kamera
  3 zu wenige gemeinsame Referenzbilder -> abgelehnt; Name schon im Sammelordner -> uebersprungen; ohne vorbereitetes Bild -> uebersprungen
  4 Kette: ohne Zusatzordner Original-Ausrichtung/-Bilder; mit Zusatz (lauf ersetzt) -> Kopie + Linkordner an kantenstufe; rc 3 -> Original + Linkordner weg
  5 Kette ruft kanten_mit_zusatz vor der Kantenstufe auf und gibt AU_K/FV_K an kantenstufe (auch kanten_fertig)
Python: /media/oem/scan/venv-seg/bin/python -I tools/test_ausrichtung_zusatz.py"""
import os, sys, json
import numpy as np
T_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T_); os.environ["RCPARK_PLATZ_TOR"] = "test_ersetzt"
import ausrichtung_zusatz as AZ

fehler = []
def pruef(b, t):
    if not b: fehler.append(t); print("FEHLER:", t)

rng = np.random.default_rng(0)
def rot(v): return AZ.rot_aus_rvec(v)
s = 0.1; Rt = rot([0.3, -0.2, 1.1]); tt = np.array([1.0, -2.0, 0.5]); TR = dict(s=s, rvec=(np.array([0.3, -0.2, 1.1])).tolist(), t=tt.tolist())

def sfm_pose(C_m, R_mc):
    """Kamera im Modellrahmen (Zentrum C_m, Drehung R_mc) -> Pose im SfM-Rahmen (X_sfm = s R X_m + t)."""
    R_cw = R_mc @ Rt.T; C_s = s * Rt @ C_m + tt; return R_cw, -R_cw @ C_s

A = dict(transformation=TR, kameras={}, fotos_sfm=[]); netz = {}
for i in range(25):
    C = rng.normal(0, 10, 3); Rm = rot(rng.normal(0, 1, 3)); Rw, tw = sfm_pose(C, Rm)
    A["kameras"][f"ref{i}"] = dict(R=Rm.tolist(), t=(-Rm @ C).tolist(), f_px_original=1000.0, cx=500.0, cy=400.0, bild_b=1000, bild_h=800)
    netz[f"ref{i}.jpg"] = (Rw, tw, "SIMPLE_RADIAL", [1000.0, 500.0, 400.0, 0.01], 1000, 800)
Cn = np.array([3.0, -4.0, 1.6]); Rn = rot([0.1, 0.4, -0.2]); Rwn, twn = sfm_pose(Cn, Rn)
netz["IMG_neu.jpg"] = (Rwn, twn, "SIMPLE_RADIAL", [900.0, 480.0, 350.0, 0.02], 960, 700)
netz["doppelt.jpg"] = (Rwn, twn, "SIMPLE_RADIAL", [900.0, 480.0, 350.0, 0.02], 960, 700)

from pfade import temp_ordner
tmp = temp_ordner("test_ausr_zusatz_"); o1 = os.path.join(tmp, "z1"); os.makedirs(os.path.join(o1, "bilder"))
for n in ("IMG_neu.jpg", "doppelt.jpg"): open(os.path.join(o1, "bilder", n), "wb").write(b"x")
fv = os.path.join(tmp, "fotos"); os.makedirs(fv)
for n in ["ref0.jpg", "doppelt.jpg"]: open(os.path.join(fv, n), "wb").write(b"x")

# 1
A2, neu, ber = AZ.erweitern(A, os.listdir(fv), [(o1, netz)], min_gem=20)
e = ber["ordner"][0]; pruef(e["rahmen_ok"] and e["zentrum_median_m"] < 1e-9, f"1 Rahmen-Tor: {e}")
pruef(list(neu) == ["IMG_neu"], f"1 neu {list(neu)}"); k = A2["kameras"].get("IMG_neu", {})
X_m = np.array([1.0, 2.0, 3.0]); X_s = s * Rt @ X_m + tt
p_sfm = Rwn @ X_s + twn; p_mod = np.array(k.get("R", np.eye(3))) @ X_m + np.array(k.get("t", [0, 0, 0]))
pruef(np.allclose(p_sfm[:2] / p_sfm[2], p_mod[:2] / p_mod[2], atol=1e-9), "1 Projektion neue Kamera weicht ab")
pruef(np.allclose(k.get("standort"), np.round(Cn, 2)) and k.get("bild_b") == 960 and k.get("cx") == 480.0 and k.get("k") == [0.02], f"1 Eintrag {k}")
pruef(e["uebersprungen_name"] == ["doppelt.jpg"], f"3 Name im Sammelordner: {e['uebersprungen_name']}")
pruef("IMG_neu" in A2["fotos_sfm"] and len(A["kameras"]) == 25, "1 Original veraendert oder fotos_sfm fehlt")
# 2
netz2 = {n: ((v[0], v[1] + np.array([0.0, 0.0, 1.0])) + v[2:]) for n, v in netz.items()}
A3, neu3, ber3 = AZ.erweitern(A, os.listdir(fv), [(o1, netz2)], min_gem=20)
pruef(not ber3["ordner"][0]["rahmen_ok"] and not neu3 and "weichen ab" in ber3["ordner"][0].get("grund", ""), f"2 anderer Rahmen nicht abgelehnt: {ber3}")
# 3
A4, neu4, ber4 = AZ.erweitern(A, [], [(o1, netz)], min_gem=30)
pruef(not ber4["ordner"][0]["rahmen_ok"] and not neu4, "3 zu wenige gemeinsame nicht abgelehnt")
os.remove(os.path.join(o1, "bilder", "IMG_neu.jpg")); A5, neu5, ber5 = AZ.erweitern(A, [], [(o1, netz)])
pruef("IMG_neu.jpg" in ber5["ordner"][0]["ohne_bild"] and "IMG_neu" not in neu5, "3 ohne Bild nicht uebersprungen")
open(os.path.join(o1, "bilder", "IMG_neu.jpg"), "wb").write(b"x")
AZ.links_anlegen(os.path.join(tmp, "lk"), fv, os.listdir(fv), neu)
pruef(sorted(os.listdir(os.path.join(tmp, "lk"))) == ["IMG_neu.jpg", "doppelt.jpg", "ref0.jpg"], "1 Linkordner")

# 4 Kette
import gesamtkette as G
Z = os.path.join(tmp, "obj"); os.makedirs(Z); KD = os.path.join(tmp, "kanten"); AU = os.path.join(tmp, "AU.json"); json.dump(A, open(AU, "w"))
B = dict(schritte=[], _pfad=os.path.join(tmp, "bericht.json")); MODUS = [0]; AUFRUFE = []
def fake_lauf(B_, name, cmd, log, ok=(0,), timeout=None, platz=()):
    AUFRUFE.append(cmd); i = cmd.index("--aus_json"); aj = cmd[i + 1]; ab = cmd[cmd.index("--aus_bilder") + 1]; os.makedirs(ab, exist_ok=True)
    json.dump(A, open(aj, "w")); json.dump(dict(ordner=[dict(ordner=o1, rahmen_ok=True, neu=1)], neu_gesamt=1, kameras_gesamt=26), open(aj + ".bericht.json", "w"))
    if not os.path.lexists(os.path.join(ab, "x.jpg")): os.symlink(AU, os.path.join(ab, "x.jpg"))
    return MODUS[0], ""
G.lauf = fake_lauf
r = G.kanten_mit_zusatz(B, Z, AU, fv, KD, "/dev/null", {})
pruef(r == (AU, fv) and not AUFRUFE, f"4 ohne Zusatz: {r}")
lg = os.path.join(tmp, "zz", "lg"); os.makedirs(os.path.join(lg, "sparse_handy", "0")); open(os.path.join(lg, "registrierung.json"), "w").write("{}")
open(os.path.join(lg, "sparse_handy", "0", "images.bin"), "wb").write(b"x")
r = G.kanten_mit_zusatz(B, Z, AU, fv, KD, "/dev/null", dict(zusatzfotos=os.path.join(tmp, "zz")))
pruef(r == (os.path.join(KD, "zusatz", "ausrichtung_mit_zusatz.json"), os.path.join(KD, "zusatz", "bilder")) and AUFRUFE and lg in AUFRUFE[-1], f"4 mit Zusatz: {r}")
MODUS[0] = 3; r = G.kanten_mit_zusatz(B, Z, AU, fv, KD, "/dev/null", dict(zusatzfotos=os.path.join(tmp, "zz")))
pruef(r == (AU, fv) and not os.path.isdir(os.path.join(KD, "zusatz", "bilder")), f"4 rc 3: {r}, Linkordner bleibt={os.path.isdir(os.path.join(KD, 'zusatz', 'bilder'))}")
# 5
src = open(os.path.join(T_, "gesamtkette.py")).read()
pruef("AU_K, FV_K = kanten_mit_zusatz(" in src and '"tools/kantenstufe.py", ZR, "--ausrichtung", AU_K, "--bilder", FV_K' in src and src.count('"--ausrichtung", AU_K, "--bilder", FV_K') == 2,
      "5 Kette gibt AU_K/FV_K nicht an kantenstufe + kanten_fertig")

import shutil; shutil.rmtree(tmp, ignore_errors=True)
print("ok test_ausrichtung_zusatz" if not fehler else f"{len(fehler)} FEHLER"); sys.exit(1 if fehler else 0)
