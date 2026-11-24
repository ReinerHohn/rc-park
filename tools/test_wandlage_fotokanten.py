#!/usr/bin/env python3
"""test_wandlage_fotokanten.py - fester synthetischer Test (24.11.2026, Befund 1122x f00: Koerperwand 0,32 m VOR der Fotokanten-Ebene) fuer tools/wandlage_fotokanten.py
und die Verbraucher bauteile.korrekturen_aus_json / bauteile.fenster_aus_json.
Koerper: Quader x -5..5, y -4..4, z 0..10 (LoD2-Ebenen). Vier Fassaden; Fotokanten-Sweep und dichte Wolke synthetisch:
  A f00 (+x): Fotokanten 0,30 m innen, RANSAC-Ebene, 2000 Punkte, Wolke ebenfalls innen -> VERSCHOBEN (w_soll -0,30); Zone endet 0,2/0,1 m VOR den Ecken
    (wie Schwabentor-Fassadenzonen) -> Wandenden trotzdem an den Ecken f02/f03.
  B f01 (-x): Fotokanten innen, aber schwach belegt (150 Punkte, keine RANSAC-Ebene) -> NICHT verschoben.
  C f03 (+y): Fotokanten innen belegt, Wolke auf der alten Ebene (Veto) -> NICHT verschoben.
  D Bau: Grundkoerper mit Korrektur -> f00-Wand bei x 4,70; Volumen = 9,70 x 8 x 10 (keine Rippe an den Ecken, keine Ueberlappung), Nachbarwaende ungestoert.
  E Fenster (fenster_aus_json, Laibung 0,12 m) schneidet ab der GESETZTEN Wand ins Mauerwerk (ohne Wandlage-Bezug ginge der Schnitt ins Leere).
  F Fremde Korrektur (ebenen_schleife) bleibt erhalten, zweiter Lauf ersetzt die eigenen Eintraege (keine Doppelten); ohne ebenen.json werden eigene Eintraege entfernt (rc 3).
Werte sind Testgeometrie, kein Objektmass. < 10 s."""
import os, sys, json, subprocess
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner

fehler = []
def pruef(b, t):
    print(("ok    " if b else "FEHLER ") + t, flush=True)
    if not b: fehler.append(t)

T = temp_ordner("test_wandlage_"); OB = os.path.join(T, "obj"); A = os.path.join(OB, "audit"); EB = os.path.join(T, "ebenen"); FO = os.path.join(T, "fassade")
for p_ in (A, EB, FO): os.makedirs(p_, exist_ok=True)
json.dump(dict(name="test"), open(os.path.join(OB, "objekt.json"), "w"))
rng = np.random.default_rng(7)
# Fassaden wie fassaden_gruppieren: d = n um 90 Grad, o auf der LoD2-Ebene
FA = [dict(id="f00", o=[5.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], u=[-4.0, 4.0], z=[0.0, 10.0]),
      dict(id="f01", o=[-5.0, 0.0], d=[0.0, -1.0], n=[-1.0, 0.0], u=[-4.0, 4.0], z=[0.0, 10.0]),
      dict(id="f02", o=[0.0, -4.0], d=[1.0, 0.0], n=[0.0, -1.0], u=[-5.0, 5.0], z=[0.0, 10.0]),
      dict(id="f03", o=[0.0, 4.0], d=[-1.0, 0.0], n=[0.0, 1.0], u=[-5.0, 5.0], z=[0.0, 10.0])]
json.dump(dict(fassaden=FA), open(os.path.join(FO, "fassaden.json"), "w"))


def ebene_punkte(F, w, n_, streu=0.02):
    o = np.array(F["o"]); d = np.array(F["d"]); n = np.array(F["n"]); u = rng.uniform(F["u"][0] + 0.3, F["u"][1] - 0.3, n_); z = rng.uniform(0.5, 9.5, n_); ww = w + rng.normal(0, streu, n_)
    return np.c_[o[0] + u * d[0] + ww * n[0], o[1] + u * d[1] + ww * n[1], z]


NE = dict(a=-0.3, b_u=0.0, c_z=0.0, u_ref=0.0, z_ref=0.0)
E = []
for F, w, n_, ne in ((FA[0], -0.3, 2000, NE), (FA[1], -0.3, 150, None), (FA[3], -0.3, 2000, NE)):
    sw = os.path.join(EB, F["id"] + "_sweep.npz"); P = ebene_punkte(F, w, n_); np.savez(sw, P=P)
    E.append(dict(id=F["id"] + "_wand", art="wand", fassade=F["id"], o=F["o"], d=F["d"], n=F["n"], w=w if ne else 0.0, neigung=ne, zone=([F["u"][0] + 0.2, F["u"][1] - 0.1] if F["id"] == "f00" else F["u"]) + F["z"], band=0.5,
                  sweep=sw, punkte=n_, auf_ebene_anteil=0.95 if ne else 0.3))
E.append(dict(id="f00_vb0", art="vorbau", fassade="f00", o=FA[0]["o"], d=FA[0]["d"], n=FA[0]["n"], w=0.6, zone=[-1, 1, 3, 6], band=0.8))       # keine Wand -> ignoriert
json.dump(dict(ebenen=E), open(os.path.join(EB, "ebenen.json"), "w"))
WO = np.r_[ebene_punkte(FA[0], -0.30, 20000, 0.03), ebene_punkte(FA[1], -0.30, 20000, 0.03), ebene_punkte(FA[3], 0.0, 20000, 0.03)]     # Wolke: f03 auf der LoD2-Ebene (Veto)
WP = os.path.join(T, "wolke.npy"); np.save(WP, WO.astype(np.float32))
# fremde Korrektur (wie tools/ebenen_schleife.py), muss erhalten bleiben
KP = os.path.join(A, "schleife_korrekturen.json")
json.dump(dict(quelle="tools/ebenen_schleife.py", korrekturen=[dict(id="k00", art="fleck", fassade="f02", o=FA[2]["o"], d=FA[2]["d"], n=FA[2]["n"], u0=-1.0, u1=1.0, z0=1.0, z1=2.0, w_ist=0.0, w_soll=-0.05)]), open(KP, "w"))

AUFRUF = [sys.executable, "-I", os.path.join(H, "wandlage_fotokanten.py"), os.path.join(OB, "objekt.json"), EB, "--wolke", WP, "--fassade", FO]
r = subprocess.run(AUFRUF, capture_output=True, text=True); print(r.stdout.strip()[-1500:]); print(r.stderr.strip()[-800:])
pruef(r.returncode == 0, f"Lauf rc {r.returncode}")
zeilen = [z for z in r.stdout.splitlines() if z.startswith("WANDLAGE f")]
pruef(len(zeilen) == 3 and all("alt w" in z and "neu w" in z and "uebernommen" in z for z in zeilen), f"je Wand eine Kettenlog-Zeile (alt w, neu w, Beleg, uebernommen): {len(zeilen)}")
KO = json.load(open(KP))["korrekturen"]; eig = [k for k in KO if k.get("quelle") == "tools/wandlage_fotokanten.py"]
k0 = [k for k in eig if k["fassade"] == "f00"]
pruef(len(k0) == 1 and abs(k0[0]["w_soll"] + 0.3) < 1e-6 and k0[0]["art"] == "wandversatz", f"A f00 verschoben auf -0,30: {[(k['fassade'], k['w_soll']) for k in eig]}")
pruef(bool(k0) and abs(k0[0]["u0"] - (-4.05)) < 1e-6 and abs(k0[0]["u1"] - 4.05) < 1e-6, f"A Wandenden bis an die Ecken f02/f03 (+5 cm): {k0[0]['u0'] if k0 else None}..{k0[0]['u1'] if k0 else None}")
pruef(not any(k["fassade"] == "f01" for k in eig) and "f01: alt w +0.000 m, neu w +0.000 m" in r.stdout, "B f01 schwach belegt -> nicht verschoben")
pruef(not any(k["fassade"] == "f03" for k in eig) and any(z.startswith("WANDLAGE f03") and "Wolke bestaetigt nicht" in z for z in zeilen), "C f03 Wolke widerspricht -> nicht verschoben (Veto)")
pruef(any(k.get("id") == "k00" for k in KO), "F fremde Korrektur bleibt")
WJ = json.load(open(os.path.join(A, "wandlage_fotokanten.json"))); pruef(len(WJ["waende"]) == 3, "Beleg-JSON audit/wandlage_fotokanten.json je Wand")

# D Bau: Grundkoerper + Korrektur (Generatorweg: korrekturen_aus_json(art='wandversatz') am Grundkoerper)
import bauteile as BT
M = BT.M
K0 = M.cube((10.0, 8.0, 10.0)).translate((-5.0, -4.0, 0.0))
json.dump(dict(korrekturen=[k for k in KO if k.get("art") == "wandversatz"]), open(os.path.join(A, "nur_wandversatz.json"), "w"))
K1, bel = BT.korrekturen_aus_json(K0, os.path.join(A, "nur_wandversatz.json"), art="wandversatz")
bb = K1.bounding_box(); bb = (bb if isinstance(bb, (tuple, list)) else (bb.min, bb.max))
mn, mx = (np.array(bb[0])[:3], np.array(bb[1])[:3]) if len(bb) == 2 else (np.array(bb[:3]), np.array(bb[3:]))
pruef(abs(mx[0] - 4.7) < 1e-3 and abs(mn[0] + 5.0) < 1e-3, f"D f00-Wand bei x {mx[0]:.3f} (Soll 4,700), f01 unberuehrt bei {mn[0]:.3f}")
pruef(abs(mn[1] + 4.0) < 1e-3 and abs(mx[1] - 4.0) < 1e-3 and abs(mn[2]) < 1e-3 and abs(mx[2] - 10.0) < 1e-3, f"D Nachbarwaende/Boden/Oberkante ungestoert: y {mn[1]:.2f}..{mx[1]:.2f}, z {mn[2]:.2f}..{mx[2]:.2f}")
pruef(abs(K1.volume() - 9.7 * 8 * 10) < 1e-3, f"D Volumen {K1.volume():.3f} = 9,7 x 8 x 10 = 776 (keine Rippe/kein Spalt an den Ecken)")
pruef(len(K1.decompose()) == 1, "D ein Stueck")

# E Fenster ab der gesetzten Wand
FJ = os.path.join(A, "fenster_test.json")
json.dump({"f00": dict(o=FA[0]["o"], d=FA[0]["d"], n=FA[0]["n"], fenster=[dict(u0=-1.0, u1=1.0, z0=2.0, z1=4.0, stimmen_min=3)])}, open(FJ, "w"))
Wd = BT.Wand(np.array(FA[0]["o"]), np.array(FA[0]["o"]) + np.array(FA[0]["d"]), aussen=np.array(FA[0]["o"]) + np.array(FA[0]["n"]))
probe = Wd.kasten(-0.5, 0.5, 2.5, 3.5, -0.36, -0.32)       # Mauerwerk direkt hinter der gesetzten Wand (w -0,30) im Fensterfeld
os.replace(KP, KP + ".weg"); K_alt, _ = BT.fenster_aus_json(K1, FJ); os.replace(KP + ".weg", KP)
K_neu, bel_f = BT.fenster_aus_json(K1, FJ)
v_alt, v_neu = (K_alt ^ probe).volume(), (K_neu ^ probe).volume()
pruef(v_alt > 0.9 * probe.volume() and v_neu < 0.05 * probe.volume(), f"E Fenster schneidet ab der gesetzten Wand (Mauerwerk im Fensterfeld: ohne Bezug {v_alt:.3f}, mit {v_neu:.3f} m3)")
pruef(any("gesetzte Wandlage" in b_.get("element", "") for b_ in bel_f), "E Beleg nennt die Bezugsebene")

# F zweiter Lauf: keine Doppelten; ohne ebenen.json eigene Eintraege weg
r2 = subprocess.run(AUFRUF, capture_output=True, text=True); KO2 = json.load(open(KP))["korrekturen"]
pruef(r2.returncode == 0 and len([k for k in KO2 if k.get("quelle") == "tools/wandlage_fotokanten.py"]) == 1 and len(KO2) == 2, f"F zweiter Lauf ersetzt eigene Eintraege ({len(KO2)} Eintraege)")
os.rename(os.path.join(EB, "ebenen.json"), os.path.join(EB, "ebenen_alt.json"))
r3 = subprocess.run(AUFRUF, capture_output=True, text=True); KO3 = json.load(open(KP))["korrekturen"]
pruef(r3.returncode == 3 and not any(k.get("quelle") == "tools/wandlage_fotokanten.py" for k in KO3) and any(k.get("id") == "k00" for k in KO3), f"F ohne ebenen.json: rc {r3.returncode}, eigene Eintraege entfernt, fremde bleiben")

print("FEHLER:" if fehler else "ALLE PRUEFUNGEN BESTANDEN", *fehler, sep="\n  "); sys.exit(1 if fehler else 0)
