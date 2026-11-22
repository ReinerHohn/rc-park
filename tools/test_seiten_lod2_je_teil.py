#!/usr/bin/env python3
"""Fester Test fuer tools/seiten_lod2_je_teil.py, das Bild-x-Lot (seiten_gps_vereinen.lot_aus_bild_achsen) und die Kantenzusammenfassung des Wanddicke-Tors - ohne echte Daten.
  1 Lot: Kameras 20 Grad nach oben geneigt (Turmfotos) -> Bild-oben-Mittel kippt ~20 Grad, Bild-x-Lot < 0,5 Grad (Ursache der Schwabentor-'Doppelflaeche').
  2 Suche: Teil sieht Nord-, Westwand und Rundturm, GPS-Lage 2 m / 1,5 Grad / 4 % daneben -> wahre Lage, eindeutig, nicht am Rand.
  3 Teil sieht nur EINE lange Wand -> nicht festgelegt / mehrdeutig (kein Urteil).
  4 Wahre Lage ausserhalb des Kastens -> 'Rand' (kein Urteil).
  5 Kasten aus der GPS-Unsicherheit (wenig GPS = weit, nie ueber die Tor-Grenzen); Uebernahme-Regeln (a)(b)(c).
  6 Wanddicke-Tor: Zwischenecken werden zu einer Kante zusammengelegt; schraege Wand -> Neigung gemeldet.
  7 Verdrahtung: sfm_seiten_modelle (nur GPS-Weg, abschaltbar, Code-Stand), pipeline_objekt (RCPARK_SEITEN_OBJEKT); ohne objekt.json kein Rechenaufruf.
/media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_lod2_je_teil.py"""
import os, sys, math
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_lod2_je_teil as L
import seiten_gps_vereinen as SG
import wand_dicke_tor as WD

FEHLER = []
def pruef(bed, text):
    if not bed: FEHLER.append(text); print("FEHLER:", text)

rng = np.random.default_rng(1)

# ---------- 1 Lot
def kam(az, neig):
    f = np.array([math.cos(math.radians(neig)) * math.cos(math.radians(az)), math.cos(math.radians(neig)) * math.sin(math.radians(az)), math.sin(math.radians(neig))])
    x = np.cross(f, [0, 0, 1.0]); x /= np.linalg.norm(x); y = np.cross(f, x)                    # Bild-y zeigt nach unten (COLMAP), Bild-x waagerecht
    return np.vstack([x, y, f])
Rs = [kam(az, n) for az, n in zip(rng.uniform(-30, 30, 60), rng.uniform(12, 28, 60))]
ob = np.mean([-R[1] for R in Rs], 0); ob /= np.linalg.norm(ob); lx = SG.lot_aus_bild_achsen(Rs)
w_ob, w_lx = [math.degrees(math.acos(np.clip(v @ [0, 0, 1], -1, 1))) for v in (ob, lx)]
pruef(w_ob > 15 and w_lx < 0.5, f"Lot: Bild-oben-Mittel {w_ob:.1f} Grad, Bild-x-Lot {w_lx:.2f} Grad neben dem wahren Lot")
print(f"ok 1: Turmfotos 12-28 Grad geneigt: Bild-oben-Mittel {w_ob:.1f} Grad schief, Bild-x-Lot {w_lx:.2f} Grad")

# ---------- 2-4 Suche
haus = np.array([[-6, -6], [6, -6], [6, 6], [-6, 6.0]])
turm = np.array([[6 + 1.5 * math.cos(t), 1.5 * math.sin(t)] for t in np.linspace(-math.pi / 2, math.pi / 2, 20)])   # Rundturm an der Ostwand (x = 6)
turm = np.r_[[[6, -1.5]], turm, [[6, 1.5]]]
kanten = [haus, turm]
def wandpunkte(stuecke, n=6000):
    P = []
    for a_, b_ in stuecke:
        t = rng.random(n); P.append(a_ + t[:, None] * (b_ - a_) + rng.normal(0, 0.08, (n, 2)))
    return np.vstack(P)
wahr = wandpunkte([(haus[2], haus[3]), (haus[3], haus[0])] + list(zip(turm[:-1], turm[1:])), 3000)   # Nordwand (y = 6), Westwand (x = -6), Turm
c = np.array([0.0, 14.0]); d0, s0, t0 = 1.5, 1.04, np.array([2.0, -1.2])                      # GPS-Lage: gedreht, gestaucht, versetzt (wird zurueckgerechnet)
gps = ((wahr - c - t0) @ L.rz(-d0)[:2, :2].T) * s0 + c
K = dict(dreh_grad=4.0, mass_rel=0.08, versatz_m=3.5, kipp_grad=3.0)
S = L.suche(gps, c, K, kanten)
q = (gps - c) @ L.rz(S["dreh_grad"])[:2, :2].T / S["massstab"] + c + S["versatz"]; fehl = float(np.median(np.linalg.norm(q - wahr, axis=1)))
fl, _ = L.festlegung(q, kanten)
pruef(fehl < 0.3 and not S["rand"] and S["verhaeltnis"] < L.EINDEUTIG_MAX and fl > L.FEST_MIN, f"Suche Nord+West+Turm: Rest {fehl:.2f} m, {S}, Festlegung {fl:.3f}")
print(f"ok 2: Nord-/Westwand + Rundturm: wahre Lage auf {fehl:.2f} m, zweitbeste {100 * S['verhaeltnis']:.0f} %, Festlegung {fl:.2f}")
lang = wandpunkte([(np.array([-6, 6.0]), np.array([6, 6.0])), (np.array([6, 6.0]), np.array([22, 6.0]))], 6000)   # nur die Nordwand, als Strassenflucht weiter (Nachbarhaus ohne LoD2-Ziel)
gps1 = lang + [1.5, 0.0]
S1 = L.suche(gps1, c, K, kanten); q1 = (gps1 - c) @ L.rz(S1["dreh_grad"])[:2, :2].T / S1["massstab"] + c + S1["versatz"]; fl1, _ = L.festlegung(q1, kanten)
pruef(fl1 < L.FEST_MIN or S1["verhaeltnis"] > L.EINDEUTIG_MAX or S1["rand"], f"eine lange Wand galt als festgelegt: {S1}, Festlegung {fl1:.3f}")
print(f"ok 3: nur eine Wand: Festlegung {fl1:.3f}, zweitbeste {100 * S1['verhaeltnis']:.0f} %, Rand {S1['rand'] or '-'} -> kein Urteil")
gps2 = wahr + [5.5, 0.0]; S2 = L.suche(gps2, c, dict(K, versatz_m=2.0), kanten)
pruef("Versatz" in S2["rand"], f"Loesung ausserhalb des Kastens nicht als Rand erkannt: {S2}")
print(f"ok 4: wahre Lage 5,5 m neben GPS, Kasten 2 m -> Rand {S2['rand']}")

# ---------- 5 Kasten + Regeln
Kv = L.kasten(dict(dreh_sd_grad=0.75, mass_sd_rel=0.021, rest_median_m=5.0, inlier=125)); Kw = L.kasten(dict(dreh_sd_grad=3.5, mass_sd_rel=0.12, rest_median_m=1.8, inlier=24))
Kx = L.kasten(dict(dreh_sd_grad=9.0, mass_sd_rel=0.4, rest_median_m=20.0, inlier=16))   # 22.11.: Obergrenze jetzt KASTEN_MAX_* (20 Grad/25 %, ehrliche GPS-Unsicherheit)
Ke = L.kasten(dict(dreh_sd_grad=0.75, mass_sd_rel=0.021, dreh_sd_ehrlich_grad=9.5, mass_sd_ehrlich_rel=0.17, rest_median_m=5.0, inlier=125))
pruef(Ke["dreh_grad"] > 15 and Ke["mass_rel"] > 0.2, f"ehrliche Unsicherheit (eine Sitzung) muss den Kasten weiten: {Ke}")
pruef(Kw["dreh_grad"] > Kv["dreh_grad"] and Kw["mass_rel"] > Kv["mass_rel"], f"wenig GPS gibt keinen weiteren Kasten: {Kv} / {Kw}")
pruef(Kx["dreh_grad"] <= L.KASTEN_MAX_DREH and Kx["mass_rel"] <= L.KASTEN_MAX_MASS and Kx["versatz_m"] <= L.VERSATZ_MAX_M and Kv["versatz_m"] >= L.VERSATZ_SITZUNG_M, f"Kasten-Grenzen: {Kv} / {Kx}")
t_ok = dict(teil="a", eindeutig=True, gruende=[]); t_nein = dict(teil="b", eindeutig=False, gruende=["mehrdeutig"])
kv = dict(kanten=[dict(urteil="versetzt", von=[0, 0], bis=[1, 0], lageunterschied_m=1.6)], kanten_mit_beiden=1, max_lageunterschied_m=1.6, summe_lageunterschied_m=1.6)
kn = dict(kanten=[dict(urteil="ok", von=[0, 0], bis=[1, 0], lageunterschied_m=0.2)], kanten_mit_beiden=1, max_lageunterschied_m=0.2, summe_lageunterschied_m=0.2)
ok1, _ = L.entscheiden(t_ok, dict(t_ok, teil="b"), kv, kn, dict(im_korridor=True)); ok2, g2 = L.entscheiden(t_ok, t_nein, kv, kn, dict(im_korridor=True))
ok3, g3 = L.entscheiden(t_ok, dict(t_ok, teil="b"), kv, kn, dict(im_korridor=False, gruende=["Drehung"])); ok4, g4 = L.entscheiden(t_ok, dict(t_ok, teil="b"), kn, kv, dict(im_korridor=True))
pruef(ok1 and not ok2 and not ok3 and not ok4 and any("(b)" in g for g in g3) and any("(a)" in g for g in g4) and any("(c)" in g for g in g4), f"Regeln: {ok1} {g2} {g3} {g4}")
print(f"ok 5: Kasten wenig GPS {Kw['dreh_grad']} Grad / {100 * Kw['mass_rel']:.0f} % / {Kw['versatz_m']} m (viel GPS {Kv['dreh_grad']} / {100 * Kv['mass_rel']:.1f} % / {Kv['versatz_m']}); Regeln (a)(b)(c) + Eindeutigkeit")

# ---------- 6 Wanddicke-Tor
g = np.array([[0, 0], [3.7, 0.05], [8.3, 0.1], [12.0, 0.2], [12.0, 12.0], [0, 12.0]])
kz = WD.kanten_zusammenfassen(g); pruef(len(kz) == 4 and max(np.linalg.norm(b - a) for a, b in kz) > 11.9, f"Zwischenecken nicht zusammengelegt: {kz}")
z = rng.uniform(1.5, 9, 20000); P = np.c_[rng.uniform(1, 11, 20000), -0.5 + (z - 1.5) * math.tan(math.radians(20)), z]   # Suedwand 20 Grad schraeg
Kd = WD.kanten_messen(g, {"t": P}); ks = [k for k in Kd if k["von"][1] < 1 and k["bis"][1] < 1][0]
pruef(abs(abs(ks["teile"]["t"].get("neigung_grad", 0)) - 20) < 3 and ks.get("schraeg_teile") == ["t"], f"schraege Wand nicht gemeldet: {ks}")
print(f"ok 6: Zwischenecken -> {len(kz)} Kanten; schraege Wand Neigung {ks['teile']['t'].get('neigung_grad')} Grad, Dicke {ks['teile']['t']['dicke_m']} m")

# ---------- 7 Verdrahtung
src = open(os.path.join(T, "sfm_seiten_modelle.py")).read(); po = open(os.path.join(T, "pipeline_objekt.py")).read()
i_q, i_l, i_k = src.find("qs = querspur_stufe("), src.find("lo = lod2_stufe("), src.find('weg="klappung"')
pruef(0 < i_k < i_q < i_l and src.count("lod2_stufe(") == 2 and 'RCPARK_LOD2_JE_TEIL' in src and '"seiten_lod2_je_teil.py"' in src and '"gps+lod2"' in src, "sfm_seiten_modelle: Stufe nicht (nur) auf dem GPS-Weg nach der Querspur-Stufe verdrahtet")
pruef(po.count("RCPARK_SEITEN_OBJEKT=oj") == 2, "pipeline_objekt gibt objekt.json nicht an iphone_sfm weiter")
import sfm_seiten_modelle as SM
aufrufe = []; alt = SM.LAUF; SM.LAUF = lambda cmd, log=None: aufrufe.append(cmd) or 0; os.environ.pop("RCPARK_SEITEN_OBJEKT", None)
try: r = SM.lod2_stufe("/nicht/da", dict(teil=0, modell="/x"), dict(teil=1, modell="/y"), "/a.ply", "/b.ply", "/v.json", "/f")
finally: SM.LAUF = alt
pruef(not r.get("ok") and not aufrufe and "nicht gerechnet" in r.get("urteil", ""), f"ohne objekt.json gerechnet: {r} {aufrufe}")
print("ok 7: Verdrahtung (nur GPS-Weg nach der Querspur-Stufe, abschaltbar, Code-Stand der Nachstufe, objekt.json ueber pipeline_objekt; ohne objekt.json kein Aufruf)")

print("ALLE TESTS BESTANDEN" if not FEHLER else f"{len(FEHLER)} FEHLER"); sys.exit(1 if FEHLER else 0)
