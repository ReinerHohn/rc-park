#!/usr/bin/env python3
"""Fester Test (Sekunden, CPU) fuer tools/lage_proben.py - unabhaengige Lageproben als Entscheider (22.11.2026, schwabentor-1122: Nah-GPS einer Sitzung +9,4 Grad / x0,867
verzerrt, Ausrichtung im GPS-Kasten falsch).
  1 synthetisch: Turm 8 x 8 m + Haeuserzeile, Wolke auf den Waenden in der WAHREN Lage, Kameras rundum. Bezugslage = verzerrtes GPS (+9 Grad, x0,87).
    Wandfit mit Nachbarn findet die wahre Lage; Kandidat 'wahr' besteht, 'GPS-Lage' faellt; Oberkante: wahr besteht, x0,80 faellt (Dach gesehen), Wolke ohne Dach
    = kein Urteil; Kamerahoehe 1,6 m besteht, x0,8 faellt; entscheiden -> wahr gewaehlt
  2 nur GPS, keine Probe urteilsfaehig -> 'kein Urteil' (keine Wahl); zwei unvereinbare bestehende Lagen -> 'mehrdeutig'; keine besteht -> 'keine'
  3 echte Zahlen (Probe 22.11. auf Kopien, scratchpad gu/ev1.py): Abstaende der Fehllagen zum Wandfit-Bestwert 1122g +9,3 Grad/+20,5 %/5,8 m, 1122d +33 Grad,
    1122e +3,2 Grad/+24 %; 1120-Lage +0,1 Grad/-1,1 %/0,3 m -> Toleranzen trennen sie
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_lage_proben.py"""
import os, sys, math
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import lage_proben as LP

FEHLER = []
def pruef(bed, text):
    if not bed: FEHLER.append(text); print("FEHLER:", text)

rng = np.random.default_rng(4)
turm = np.array([[-4, -4], [4, -4], [4, 4], [-4, 4]], float)
zeile = np.array([[-20, 12], [20, 12], [20, 22], [-20, 22]], float)                            # Haeuserzeile noerdlich (legt Drehung/Massstab fest)
haus2 = np.array([[14, -14], [24, -14], [24, -4], [14, -4]], float)
polys = [("ziel", turm), ("zeile", zeile), ("haus2", haus2)]

def wand(poly, h, n):
    P = []
    for p0, p1 in zip(poly, np.roll(poly, -1, 0)):
        L = np.linalg.norm(p1 - p0); k = int(n * L / 10); t = rng.random(k); z = rng.random(k) * h
        P.append(np.c_[p0 + t[:, None] * (p1 - p0) + rng.normal(0, 0.05, (k, 2)), z])
    return np.vstack(P)

# Wolke: Turmwaende bis 30 m, Pyramide bis 40 m (Dach gesehen), Zeile/Haus2 bis 10 m, Boden
dach = np.c_[rng.uniform(-4, 4, (6000, 2))]; dach = np.c_[dach, 30 + 10 * (1 - np.max(np.abs(dach), 1) / 4)]
boden = np.c_[rng.uniform(-30, 30, (40000, 2)), rng.normal(0, 0.03, 40000)]; boden = boden[[not LP.in_polygon(b[None, :2], turm)[0] for b in boden]]
P_wahr = np.vstack([wand(turm, 30, 3000), dach, wand(zeile, 10, 1500), wand(haus2, 10, 1500), boden])
w = rng.uniform(0, 2 * np.pi, 120); r = rng.uniform(7, 11, 120)
C_wahr = np.c_[r * np.cos(w), r * np.sin(w), np.full(120, 1.6)]; C_wahr = C_wahr[~(np.abs(C_wahr[:, :2]) < 5).all(1)]
V = np.c_[-np.cos(w), -np.sin(w), np.zeros(120)][:len(C_wahr)]; fov = np.full(len(C_wahr), 35.0)
dom = dict(dom=lambda q: np.where((np.abs(q) <= 4).all(1), 30 + 10 * (1 - np.max(np.abs(q), 1) / 4), 0.0), dgm=lambda q: np.zeros(len(q)))
null = lambda q: np.zeros(len(q))

def lage(P, grad, k, t=(0, 0)):
    a = math.radians(grad); R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]]); return np.asarray(P) @ R.T * k + [t[0], t[1], 0]

P_gps = lage(P_wahr, 9.0, 0.87, (0.8, -0.5)); C_gps = lage(C_wahr, 9.0, 0.87, (0.8, -0.5)); V_gps = lage(V, 9.0, 1.0)
seg = LP.gesehene_kanten(polys, C_gps, V_gps, fov)
pruef(len(seg) >= 6, f"gesehene Kanten: {len(seg)}")
xy = LP.wandband(P_gps, {}, boden=null)
S = LP.wandfit_bestwert(xy, np.median(C_gps, 0), seg, dict(dreh_grad=15.0, mass_rel=0.25, versatz_m=4.0))
b = S.get("fein") or S.get("best")
pruef(b is not None and not S["rand"], f"Wandsuche ohne Bestwert/am Rand: {S.get('rand')}")
kand = {"wahr": (P_wahr, C_wahr), "GPS-Lage": (P_gps, C_gps), "x0,80": (lage(P_wahr, 0, 0.80), lage(C_wahr, 0, 0.80))}
cp = np.median(C_gps, 0); urt = {}
for n_, (Pk, Ck) in kand.items():
    pw = LP.wandfit_urteil(S, P_gps, Pk, cp); po = LP.probe_oberkante(Pk, {}, [turm] if n_ != "x0,80" else [turm * 0.8], dom=dom); pk = LP.probe_kamerahoehe(Pk, Ck)
    urt[n_] = [po, pk, pw]
    print(f"  {n_}: oberkante {po['urteil']} ({po.get('wert')}), kamerahoehe {pk['urteil']} ({pk.get('wert')}), wandfit {pw['urteil']} {pw.get('abstand')}")
pruef(urt["wahr"][2]["urteil"] == "besteht", f"wahre Lage muss den Wandfit bestehen: {urt['wahr'][2]}")
pruef(urt["GPS-Lage"][2]["urteil"] == "faellt", f"verzerrte GPS-Lage muss am Wandfit fallen: {urt['GPS-Lage'][2]}")
pruef(urt["wahr"][0]["urteil"] == "besteht", f"Oberkante wahr: {urt['wahr'][0]}")
pruef(urt["x0,80"][0]["urteil"] == "faellt", f"Oberkante x0,80 (Dach gesehen) muss fallen: {urt['x0,80'][0]}")
pruef(urt["wahr"][1]["urteil"] == "besteht" and urt["x0,80"][1]["urteil"] == "faellt", f"Kamerahoehe: {urt['wahr'][1].get('wert')} / {urt['x0,80'][1].get('wert')}")
ohne_dach = P_wahr[P_wahr[:, 2] < 22]                                                          # Wolke endet an der Wand (1122d: 19-23 m)
po2 = LP.probe_oberkante(lage(ohne_dach, 0, 0.8), {}, [turm * 0.8], dom=dom)
pruef(po2["urteil"] == "kein Urteil", f"Wolke ohne gesehenes Dach darf nicht urteilen: {po2['urteil']} {po2.get('grund')}")
groesser = LP.probe_oberkante(lage(P_wahr, 0, 1.25), {}, [turm * 1.25], dom=dom)
pruef(groesser["urteil"] == "faellt", f"Wolke hoeher als DOM1 muss fallen: {groesser.get('grund')}")
K = [dict(name=n_, guete=g_, proben=urt[n_]) for n_, g_ in (("GPS-Lage", 0.3), ("wahr", 0.2), ("x0,80", 0.25))]
E = LP.entscheiden(K, lambda i, j: False)
pruef(E["ergebnis"] == "belegt" and K[E["wahl"]]["name"] == "wahr", f"entscheiden muss die wahre Lage waehlen (trotz kleinerer Guete): {E}")

# 2 Randfaelle der Entscheidung
ku = lambda: dict(probe="x", urteil="kein Urteil")
E2 = LP.entscheiden([dict(name="a", guete=0.5, proben=[ku(), ku()]), dict(name="b", guete=0.4, proben=[ku()])], lambda i, j: True)
pruef(E2["ergebnis"] == "kein Urteil" and E2["wahl"] is None, f"nur GPS/ohne Proben muss 'kein Urteil' sein: {E2}")
bs = lambda: dict(probe="x", urteil="besteht"); fa = lambda: dict(probe="x", urteil="faellt")
E3 = LP.entscheiden([dict(name="a", guete=0.5, proben=[bs()]), dict(name="b", guete=0.4, proben=[bs()])], lambda i, j: False)
pruef(E3["ergebnis"] == "mehrdeutig" and E3["wahl"] is None, f"zwei unvereinbare bestehende Lagen: {E3}")
E4 = LP.entscheiden([dict(name="a", guete=0.5, proben=[fa(), bs()]), dict(name="b", guete=0.4, proben=[fa()])], lambda i, j: True)
pruef(E4["ergebnis"] == "keine" and E4["wahl"] is None, f"keine besteht: {E4}")
E5 = LP.entscheiden([dict(name="a", guete=0.5, proben=[bs()]), dict(name="b", guete=0.4, proben=[bs(), ku()])], lambda i, j: True)
pruef(E5["ergebnis"] == "belegt" and E5["wahl"] == 0, f"vertraegliche bestehende Lagen -> beste: {E5}")

# monoton (alt = bisherige Wahl): besteht sie -> bleibt; ohne Urteil -> bleibt ohne Beleg; widerlegt -> beste bestehende
E6 = LP.entscheiden([dict(name="alt", guete=0.5, proben=[bs()]), dict(name="b", guete=0.4, proben=[bs()])], lambda i, j: False, alt=0)
pruef(E6["ergebnis"] == "bestaetigt" and E6["wahl"] == 0, f"monoton: bestehende bisherige Wahl muss bleiben (Kaufhaus): {E6}")
E7 = LP.entscheiden([dict(name="alt", guete=0.5, proben=[ku(), ku()]), dict(name="b", guete=0.4, proben=[bs()])], lambda i, j: False, alt=0)
pruef(E7["ergebnis"] == "kein Urteil" and E7["wahl"] is None, f"monoton: bisherige Wahl ohne Urteil bleibt (kein Beleg): {E7}")
E8 = LP.entscheiden([dict(name="alt", guete=0.5, proben=[fa(), bs()]), dict(name="b", guete=0.4, proben=[bs()])], lambda i, j: False, alt=0)
pruef(E8["ergebnis"] == "belegt" and E8["wahl"] == 1, f"monoton: widerlegte bisherige Wahl wird ersetzt: {E8}")
E9 = LP.entscheiden(K, lambda i, j: False, alt=0)
pruef(E9["ergebnis"] == "belegt" and K[E9["wahl"]]["name"] == "wahr", f"monoton: GPS-Lage (beste Guete) faellt -> wahre Lage: {E9}")

# 3 echte Zahlen der Probe 22.11. (Abstand zum Wandfit-Bestwert) gegen die Toleranzen
echt = {"1122g": (9.3, 0.2053, 5.8), "1122d": (33.3, -0.028, 7.6), "1122e": (3.2, 0.243, 3.6), "GPS-Lage": (11.2, 0.158, 3.5), "1120-Lage": (0.13, -0.0115, 0.26)}
nahe = lambda d, m, t: abs(d) <= LP.TOL_DREH and abs(m) <= LP.TOL_MASS and t <= LP.TOL_M
for n_, (d, m, t) in echt.items(): pruef(nahe(d, m, t) == (n_ == "1120-Lage"), f"echte Zahl {n_}: Toleranz trennt nicht ({d}, {m}, {t})")
pruef(1.39 >= LP.KAMERAHOEHE_BEREICH[0] and 1.82 <= LP.KAMERAHOEHE_BEREICH[1], "Kamerahoehe-Bereich: 1122g 1,39 / 1120-Lage 1,82 (dichte Wolke) muessen drin liegen (Probe ist dort schwach, darf nicht falsch fallen)")

print("FEHLER:", len(FEHLER)) if FEHLER else print("OK test_lage_proben")
sys.exit(1 if FEHLER else 0)
