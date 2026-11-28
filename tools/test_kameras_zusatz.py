#!/usr/bin/env python3
"""Mini-Test (< 3 s, ohne pycolmap) tools/kameras_zusatz.py + gesamtkette.k_zusatz + Leser-Rueckfall pfade.foto_aus_k (28.11.2026: Handyfotos in der
Kantenstufe, aber ohne K-Datei fuer Foto-Tor/Wandbild/Foto-F1).
  1 Zusatznetz im SfM-Rahmen: K-Datei geschrieben, projiziert einen Punkt (Werkzeugrahmen X_m + T_) wie die SfM-Pose (< 1e-6 px), traegt rahmen,
    herkunft 'abgeleitet', bild_datei; Leser finden das Bild (foto_aus_k), messkamera + kamera_ok nehmen sie
  2 fremde K-Datei (handkalibriert) gleichen Namens bleibt; zu wenige Netzbeobachtungen -> verworfen
  3 Zusatznetz in anderem Rahmen -> rc 3, eigene K-Datei des Vorlaufs beiseite (.zusatz_weg), fremde unberuehrt
  4 RAHMEN.json gehoert zu anderer Ausrichtung -> rc 4, nichts geschrieben; --weg legt alle eigenen beiseite; --trocken aendert nichts
  5 Kette: abgeschaltet / ohne Zusatzordner -> --weg; rc 4 -> rote Notiz; Aufruf nach fototor_kameras und vor kamera_plausibel; Leser kennen foto_aus_k
Python: /media/oem/scan/venv-seg/bin/python -I tools/test_kameras_zusatz.py"""
import os, sys, json, glob, shutil
import numpy as np
T0 = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T0); os.environ["RCPARK_PLATZ_TOR"] = "test_ersetzt"
import ausrichtung_zusatz as AZ, kamera_rahmen as KR, kamera_sfm_guete as KG, kamera_plausibel as KP, kameras_zusatz as KZ, pfade
from PIL import Image

fehler = []
def pruef(b, t):
    if not b: fehler.append(t); print("FEHLER:", t)

rng = np.random.default_rng(1); rot = AZ.rot_aus_rvec
s = 0.1; Rt = rot([0.3, -0.2, 1.1]); tt = np.array([1.0, -2.0, 0.5]); TR = dict(s=s, rvec=[0.3, -0.2, 1.1], t=tt.tolist()); T_ = [0.5, -0.25, 0.04]
def sfm_pose(C_m, R_mc): R_cw = R_mc @ Rt.T; return R_cw, -R_cw @ (s * Rt @ C_m + tt)

A = dict(transformation=TR, kameras={}); netz = {}
for i in range(25):
    C = rng.normal(0, 10, 3) + [0, 0, 5]; Rm = rot(rng.normal(0, 1, 3)); Rw, tw = sfm_pose(C, Rm)
    A["kameras"][f"ref{i:02d}"] = dict(R=Rm.tolist(), t=(-Rm @ C).tolist(), f_px_original=1000.0, cx=500.0, cy=400.0, bild_b=1000, bild_h=800)
    netz[f"ref{i:02d}.jpg"] = (Rw, tw, "SIMPLE_RADIAL", [1000.0, 500.0, 400.0, 0.01], 1000, 800)
Cn = np.array([30.0, -4.0, 1.6]); Rn = rot([0.1, 0.4, -0.2]); Rwn, twn = sfm_pose(Cn, Rn)
for n in ("IMG_neu.jpg", "IMG_hand.jpg", "IMG_duenn.jpg"): netz[n] = (Rwn, twn, "SIMPLE_RADIAL", [900.0, 480.0, 350.0, 0.02], 960, 700)
GUETE = {n: dict(n_beob=(5 if "duenn" in n else 200)) for n in netz}
AZ.sparse_lesen = lambda sp: NETZ[0]; KG.guete = lambda sp: GUETE; NETZ = [netz]

tmp = pfade.temp_ordner("test_k_zusatz_"); od = os.path.join(tmp, "modelle", "obj"); mp = os.path.join(od, "messprotokoll"); os.makedirs(mp); os.makedirs(os.path.join(od, "audit"))
objp = os.path.join(od, "objekt.json"); json.dump(dict(fotos_dir="daten/obj/fotos", audit="modelle/obj/audit"), open(objp, "w"))
fv = os.path.join(tmp, "daten", "obj", "fotos"); os.makedirs(fv); open(os.path.join(fv, "ref00.jpg"), "wb").write(b"x")
zo = os.path.join(tmp, "zz", "lg"); os.makedirs(os.path.join(zo, "bilder")); os.makedirs(os.path.join(zo, "sparse_handy", "0")); open(os.path.join(zo, "sparse_handy", "0", "images.bin"), "wb").write(b"x"); open(os.path.join(zo, "registrierung.json"), "w").write("{}")
for n in ("IMG_neu.jpg", "IMG_hand.jpg", "IMG_duenn.jpg"): Image.new("RGB", (960, 700)).save(os.path.join(zo, "bilder", n))
au = os.path.join(mp, "SFM-AUSRICHTUNG-obj.json"); json.dump(A, open(au, "w")); KR.setzen(mp, KR.stempel(A, T_, "AU"))
json.dump(dict(foto="IMG_hand", punkte={"p": [1, 2]}, kamera=dict(rvec=[0, 0, 0], t=[0, 0, 0], f_px=1.0, cx=1.0, cy=1.0, brennweite_quelle="geloest")), open(os.path.join(mp, "K-IMG_hand.json"), "w"))
arg = [objp, "--ausrichtung", au, "--fotos", fv, "--zusatz", zo]

# 1
rc = KZ.main(arg); kp = os.path.join(mp, "K-IMG_neu.json"); k = json.load(open(kp))["kamera"] if os.path.exists(kp) else {}
pruef(rc == 0 and k, f"1 rc {rc}, K-IMG_neu fehlt={not k}")
X_m = np.array([1.0, 2.0, 3.0]); p_s = Rwn @ (s * Rt @ X_m + tt) + twn; Rk = rot(k.get("rvec", [0, 0, 0])); p_k = Rk @ (X_m + T_) + np.array(k.get("t", [0, 0, 1]))
u_s = 900 * p_s[:2] / p_s[2] + [480, 350]; u_k = k.get("f_px", 0) * p_k[:2] / p_k[2] + [k.get("cx", 0), k.get("cy", 0)]
pruef(np.allclose(u_s, u_k, atol=1e-6), f"1 Projektion {u_s} vs {u_k}")
pruef(k.get("rahmen") == KR.aktuell(mp)["id"] and k.get("herkunft") == "abgeleitet" and k.get("k1") == 0.02 and k.get("bild") == [960, 700], f"1 Felder {k}")
pruef(pfade.foto_aus_k(k) == [os.path.join(zo, "bilder", "IMG_neu.jpg")] and pfade.foto_aus_k({}) == [] and pfade.foto_aus_k(None) == [], "1 foto_aus_k")
pruef(KP.messkamera("IMG_neu", k, False) and KR.kamera_ok(kp, k, mp) and not KR.veraltet(k, mp, kp), "1 Leserfilter verwirft die Zusatzkamera")
ber = json.load(open(os.path.join(od, "audit", "kameras_zusatz.json")))
# 2
kh = json.load(open(os.path.join(mp, "K-IMG_hand.json")))
pruef(kh["kamera"]["brennweite_quelle"] == "geloest" and "IMG_hand" in ber["behalten_fremd"], "2 handkalibrierte K-Datei ueberschrieben")
pruef(not os.path.exists(os.path.join(mp, "K-IMG_duenn.json")) and any(v["foto"] == "IMG_duenn" for v in ber["verworfen"]), "2 duenne Kamera geschrieben")
# 3
NETZ[0] = {n: ((v[0], v[1] + np.array([0.0, 0.0, 1.0])) + v[2:]) for n, v in netz.items()}
rc = KZ.main(arg)
pruef(rc == 3 and not os.path.exists(kp) and os.path.exists(kp + ".zusatz_weg") and os.path.exists(os.path.join(mp, "K-IMG_hand.json")), f"3 anderer Rahmen: rc {rc}")
NETZ[0] = netz; pruef(KZ.main(arg) == 0 and os.path.exists(kp), "3 Wiederherstellung")
# 4
st = KR.aktuell(mp); KR.setzen(mp, dict(st, id="anderer00000")); rc = KZ.main(arg)
pruef(rc == 4 and not os.path.exists(kp), f"4 falscher Rahmen: rc {rc}, K bleibt={os.path.exists(kp)}")
KR.setzen(mp, st); KZ.main(arg); n0 = sorted(os.listdir(mp))
pruef(KZ.main(arg + ["--trocken"]) == 0 and KZ.main([objp, "--weg", "--trocken"]) == 3 and sorted(os.listdir(mp)) == n0, "4 trocken veraendert")
pruef(KZ.main([objp, "--weg"]) == 3 and not os.path.exists(kp) and os.path.exists(os.path.join(mp, "K-IMG_hand.json")), "4 --weg")

# 5 Kette
import gesamtkette as G
AUFRUFE = []; MODUS = [4]
def fake_lauf(B_, name, cmd, log, ok=(0,), timeout=None, platz=()):
    AUFRUFE.append(cmd); rc_ = 3 if "--weg" in cmd else MODUS[0]
    json.dump(dict(rc=rc_, fehler="Rahmen passt nicht" if rc_ == 4 else None), open(os.path.join(od, "audit", "kameras_zusatz.json"), "w")); return rc_, ""
G.lauf = fake_lauf; NOT = []; G.notiz = lambda B_, n, ok, **k_: NOT.append((n, ok, k_)); G.ROOT = tmp
os.environ["RCPARK_K_ZUSATZ"] = "0"; G.k_zusatz({}, od, objp, au, fv, "/dev/null", dict(zusatzfotos=os.path.dirname(zo)))
pruef(AUFRUFE and "--weg" in AUFRUFE[-1] and NOT[-1][:2] == ("k_zusatz", True), f"5 abgeschaltet: {AUFRUFE[-1:]}")
os.environ.pop("RCPARK_K_ZUSATZ"); G.k_zusatz({}, od, objp, au, fv, "/dev/null", {})
pruef("--weg" in AUFRUFE[-1], "5 ohne Zusatzordner kein Rueckfall")
G.k_zusatz({}, od, objp, au, fv, "/dev/null", dict(zusatzfotos=os.path.dirname(zo), audit="modelle/obj/audit"))
pruef(NOT[-1][0] == "k_zusatz_ergebnis" and NOT[-1][1] is False and "Rahmen passt nicht" in NOT[-1][2].get("fehler", "") and zo in AUFRUFE[-1], f"5 rc 4 nicht rot: {NOT[-1]}")
MODUS[0] = 0; G.k_zusatz({}, od, objp, au, fv, "/dev/null", dict(zusatzfotos=os.path.dirname(zo), audit="modelle/obj/audit"))
pruef(NOT[-1][:2] == ("k_zusatz_ergebnis", True), f"5 rc 0: {NOT[-1]}")
src = open(os.path.join(T0, "gesamtkette.py")).read(); i_b = src.find('"fototor_kameras"'); i_z = src.find("k_zusatz(B, Z, ZR, AU, FV", i_b); i_p = src.find('"kamera_plausibel"', i_b)
pruef(0 < i_b < i_z < i_p, "5 k_zusatz nicht zwischen fototor_kameras und kamera_plausibel")
for f_ in ("foto_diff.py", "fassade_ortho.py", "teil_fotoform.py", "foto_tor_bezug.py"):
    pruef("foto_aus_k(" in open(os.path.join(T0, f_)).read(), f"5 {f_} findet Zusatzbilder nicht (foto_aus_k)")

shutil.rmtree(tmp, ignore_errors=True)
print("ok test_kameras_zusatz" if not fehler else f"{len(fehler)} FEHLER"); sys.exit(1 if fehler else 0)
