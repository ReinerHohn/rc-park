#!/usr/bin/env python3
"""Test bruecke_hebel (22.11.2026): Lot-Aehnlichkeit (5 Freiheitsgrade), Lot-Kante, Epipolarband (richtige Naeherung bestaetigt, 180 Grad / 3 m falsch -> verworfen),
direkte Spuren, gemeinsamer Ausgleich (starr findet die Lage, halbstarr findet eingespielte Verformung bei voller Abdeckung, unverformt -> keine Verformung), Urteil."""
import os, sys, json, numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import pycolmap, bruecke_hebel as BH, seiten_eck_koppeln as EK
from sim3_robust import matrix, anwenden
fehler = []
def pruef(ok, text): print(("ok   " if ok else "FEHL ") + text); ok or fehler.append(text)
rng = np.random.default_rng(3)

# 1 umeyama_lot: R u = v exakt, wahre Lage zurueck
u = np.array([0.1, -0.95, 0.3]); u /= np.linalg.norm(u); Rt = BH._rot(np.array([0.3, -0.5, 0.8])); v = Rt @ u
X = rng.normal(0, 5, (300, 3)); Mt = matrix(1.7, Rt, [3.0, -2.0, 1.0]); Y = anwenden(Mt, X) + rng.normal(0, 0.01, X.shape)
s, R, t = BH.umeyama_lot(X, Y, u, v)
pruef(np.allclose(R @ u, v, atol=1e-9), "umeyama_lot: Lot wird exakt abgebildet")
pruef(abs(s - 1.7) < 1e-3 and EK.winkel(R @ Rt.T) < 0.01, f"umeyama_lot: wahre Lage (s {s:.4f}, Drehfehler {EK.winkel(R @ Rt.T):.4f} Grad)")
pruef(np.allclose(BH.drehung_auf(u, -u) @ u, -u, atol=1e-9), "drehung_auf: Gegenrichtung")

# 2 kopplung_pruefen mit fitter = ohne fitter bei lot-vertraeglichen Daten; Lot-Kante
td = np.linalg.norm(X - [0, 0, -30], axis=1)
M1, p1, ok1, _ = EK.kopplung_pruefen(X, Y, EK.ausdehnung(X), EK.ausdehnung(Y), tiefe=td)
M2, p2, ok2, _ = EK.kopplung_pruefen(X, Y, EK.ausdehnung(X), EK.ausdehnung(Y), tiefe=td, fitter=lambda a, b: BH.umeyama_lot(a, b, u, v))
pruef(ok1 and ok2 and np.abs(M1 - M2).max() < 1e-2, "kopplung_pruefen: fitter (Lot) gleich der freien Sim3, wenn das Lot stimmt")
RA = BH._rot(np.array([0.0, 0.2, 0.1])); RB = BH._rot(np.array([0.5, 0.1, -0.3])); oE = np.array([0.0, 0.0, 1.0]); oA, oB = RA @ oE, RB @ oE
XE = rng.normal(0, 4, (400, 3)); MA = matrix(2.0, RA, [1, 2, 3]); MB_ = matrix(0.5, RB, [-1, 0, 2]); YA = anwenden(MA, XE); YB = anwenden(MB_, XE); tE = np.linalg.norm(XE - [0, 0, -25], axis=1)
MAg = matrix(2.0, BH._rot(np.array([0.004, 0, 0])) @ RA, [1, 2, 3])            # freie Kopplung um 0,23 Grad gekippt
lk = BH.lot_kante(XE, YA, tE, XE, YB, tE, oA, oB, MAg, MB_, EK.ausdehnung(XE), EK.ausdehnung(YA), EK.ausdehnung(YB))
Mab = lk["Ma"] @ np.linalg.inv(lk["Mb"]); Rab = EK.zerlegen(Mab)[1]
pruef(lk["ok_a"] and lk["ok_b"] and np.degrees(np.arccos(np.clip((Rab @ oB) @ oA, -1, 1))) < 1e-3, f"lot_kante: Lot B -> Lot A exakt (winkel_frei {lk['winkel_frei_grad']} Grad)")

# 3 Epipolarband + direkte Spuren an zwei synthetischen Modellen (je 3 Kameras auf eine Wand)
def modell(Rs, ts, P, cam):
    m = BH.Modell(); m.P = P.copy(); m.namen = [f"b{i}.jpg" for i in range(len(Rs))]; m.R = [np.asarray(r, float) for r in Rs]; m.t = [np.asarray(x, float) for x in ts]
    m.cam = [cam] * len(Rs); m.xy, m.pid = [], []
    for R_, t_ in zip(m.R, m.t):
        uv, z = BH._proj(R_, t_, cam, P); ok = (z > 0) & (uv[:, 0] >= 0) & (uv[:, 0] < cam.width) & (uv[:, 1] >= 0) & (uv[:, 1] < cam.height)
        m.xy.append(np.where(ok[:, None], uv, -1e6)); m.pid.append(np.where(ok, np.arange(len(P)), -1))
    m.idx = {n: i for i, n in enumerate(m.namen)}; return m
cam = pycolmap.Camera(model="PINHOLE", width=1600, height=1200, params=[1200.0, 1200.0, 800.0, 600.0])
W = np.c_[rng.uniform(-8, 8, 1500), rng.uniform(-5, 5, 1500), rng.uniform(19.97, 20.03, 1500)]   # Wand bei z = 20 (Relief +-3 cm)
def kams(xs, gier):
    Rs, ts = [], []
    for x, g in zip(xs, gier):
        R_ = BH._rot(np.array([0, np.radians(g), 0])); C = np.array([x, 0.4 * abs(x) - 1.0, 0.3 * x]); Rs.append(R_); ts.append(-R_ @ C)
    return Rs, ts
RAk, tAk = kams([-6, -4, -2], [8, 5, 3]); RBk, tBk = kams([1, 3, 5], [-2, -5, -8])
A = modell(RAk, tAk, W, cam); B0 = modell(RBk, tBk, W, cam)
for i in range(3): B0.namen[i] = f"c{i}.jpg"
B0.idx = {n: i for i, n in enumerate(B0.namen)}
MBt = matrix(0.6, BH._rot(np.array([0.2, -0.4, 0.3])), [2.0, 1.0, -3.0]); B = B0.transformiert(MBt); M_AB = np.linalg.inv(MBt)      # B im eigenen Rahmen, Wahrheit B -> A
kp = BH.kandidaten_paare(A, B.transformiert(M_AB))
pruef(len(kp) >= 3, f"kandidaten_paare: {len(kp)} Paare mit Ueberlappung bei richtiger Naeherung")
aus = __import__("pfade").temp_ordner("test_bruecke_hebel"); npz = os.path.join(aus, "lg.npz"); D = {"meta": np.array(json.dumps(dict(groesse={})))}
for a, b, _ in kp:                                                                     # "LightGlue": echte Zuordnungen = gleicher Wandpunkt (Pixel + 0,3 px Rauschen)
    i, j = A.idx[a], B.idx[b]; w = np.flatnonzero((A.pid[i] >= 0) & (B.pid[j] >= 0))[:400]
    D["kp_" + a] = (A.xy[i] + rng.normal(0, 0.3, A.xy[i].shape)).astype(np.float32); D["kp_" + b] = (B.xy[j] + rng.normal(0, 0.3, B.xy[j].shape)).astype(np.float32)
    D[f"m_{a}|{b}"] = np.c_[w, w].astype(np.int32)
np.savez(npz, **D)
st, sp = BH.paare_pruefen(npz, A, B, M_AB, 0.004)
pruef(st["paare_bestaetigt"] == len(kp) and len(sp) > 300, f"paare_pruefen richtig: {st['paare_bestaetigt']}/{len(kp)} Paare, {len(sp)} direkte Spuren")
Md, pr, ok, g, Xd, Yd, tdd = BH.direkt_koppeln(A, B, sp)
ge = BH.ausgleich_epipolar(A, B, st["_z2d"], matrix(1.0, BH._rot(np.array([0.01, -0.008, 0.004])), [0.1, 0.05, 0]) @ M_AB)
de = EK.winkel(EK.zerlegen(ge["M_AB"] @ np.linalg.inv(M_AB))[1]); dv = np.median(np.linalg.norm(anwenden(ge["M_AB"], B.P) - anwenden(M_AB, B.P), axis=1))
pruef(de < 0.05 and dv < 0.05, f"ausgleich_epipolar (2D-2D, ohne 3D an der Naht): aus 0,8 Grad / 0,1 m Start -> {de:.3f} Grad, {dv:.3f} m")
pruef(ok and BH.bestaetigt(Md, M_AB, B.P, 0.004)[0], f"direkte Kopplung stimmig und bestaetigt die Naeherung ({g})")
c = np.median(anwenden(M_AB, B.P), 0)
for nm, Mf in (("180 Grad", (lambda D_: D_)(np.block([[BH._rot(np.array([0, np.pi, 0])), (c - BH._rot(np.array([0, np.pi, 0])) @ c)[:, None]], [np.zeros((1, 3)), np.ones((1, 1))]])) @ M_AB),
               ("3 m Versatz laengs der Basis", matrix(1, np.eye(3), [3.0, 0, 0]) @ M_AB), ("3 m Versatz quer", matrix(1, np.eye(3), [0, 3.0, 0]) @ M_AB)):
    # falsche Naeherung darf sich NICHT selbst bestaetigen: entweder verwirft das Band die Paare, oder die direkte Kopplung weicht von der Naeherung ab (und liegt bei
    # der Wahrheit = zurueckgefuehrt). Versatz laengs der Kamerabasis laesst die Epipolargeometrie fast gleich (Band blind) - dann traegt die direkte 3D-Kopplung.
    st2, sp2 = BH.paare_pruefen(npz, A, B, Mf, 0.004); Mn = BH.direkt_koppeln(A, B, sp2)[0] if sp2 else None
    selbst = Mn is not None and BH.bestaetigt(Mn, Mf, B.P, 0.004)[0]; zurueck = Mn is not None and BH.bestaetigt(Mn, M_AB, B.P, 0.004)[0]
    pruef(not selbst and (st2["paare_bestaetigt"] == 0 or zurueck), f"Negativprobe {nm}: Band verwirft {st2['paare_verworfen_band']}/{st2['paare_gematcht']}, bestaetigt sich nicht selbst"
          + (", direkte Kopplung fuehrt zur Wahrheit zurueck" if zurueck else ""))

# 4 gemeinsamer Ausgleich: starr findet die Lage aus gestoerter Naeherung; halbstarr bei voller Abdeckung
Mstart = matrix(1.0, BH._rot(np.array([0.01, -0.01, 0.005])), [0.05, 0, 0]) @ M_AB
g = BH.ausgleich(dict(direkt=(Xd, Yd, tdd)), Mstart)
pruef(EK.winkel(EK.zerlegen(g["M_AB"] @ np.linalg.inv(M_AB))[1]) < 0.02, f"ausgleich starr: Drehfehler {EK.winkel(EK.zerlegen(g['M_AB'] @ np.linalg.inv(M_AB))[1]):.4f} Grad")
P = rng.uniform([-30, -2, -5], [30, 2, 5], (3000, 3)); fp = BH.feld_parameter(P, [0, 0, 1.0]); Pd = BH.feld(fp, 0.04, np.radians(2.0))(P)[0]   # B verformt
tt = np.full(len(P), 20.0)
gh = BH.ausgleich(dict(direkt=(Pd, P, tt)), np.eye(4), fp=BH.feld_parameter(Pd, [0, 0, 1.0]), verformung=True)
pruef(abs(gh["a"] + 0.04) < 0.006 and abs(np.degrees(gh["b"]) + 2.0) < 0.3, f"halbstarr: eingespielte Verformung zurueck (a {gh['a']:+.4f}, b {np.degrees(gh['b']):+.2f} Grad; erwartet -0,04 / -2)")
pruef(BH.verformung_urteil(gh)[0], "halbstarr: Verformung signifikant")
g0 = BH.ausgleich(dict(direkt=(P + rng.normal(0, 0.02, P.shape), P, tt)), np.eye(4), fp=fp, verformung=True)
pruef(not BH.verformung_urteil(g0)[0], f"halbstarr unverformt: keine Verformung ({BH.verformung_urteil(g0)[1]})")
pruef(not BH.verformung_urteil(dict(a=0.3, b=0.0, sigma_a=0.001, sigma_b=0.001))[0], "Guard: 30 % Verformung = falsches Teil, nicht verbiegen")

# 5 Urteil
pruef(BH.urteil_kante(0.5, 0.1, 500)[0] == "stark" and BH.urteil_kante(0.16, 0.7, 0)[0] == "duenn" and BH.urteil_kante(0.06, None, 0)[0] == "zu duenn"
      and BH.urteil_kante(0.5, 0.1, 500, kreis_ok=False)[0] == "zu duenn", "urteil_kante: stark / duenn / zu duenn / Kreiswiderspruch")
# 6 Radar (verbund_schwachstellen/1) traegt das Urteil, Startbilder fuer das Nachmessen
rd = dict(urteil="zu_duenn", ausloeser=["s1", "s2"], schwachstellen=[dict(id="s1", art="bruecke", bilder=["x.jpg"], teile=[0, 1], staerke=dict(spuren_quer=12, knoten_disjunkt=1)),
          dict(id="s2", art="gelenk", bilder=["b1.jpg"], staerke=dict(spuren_quer=200, knoten_disjunkt=3)), dict(id="s3", art="schnitt", bilder=["q.jpg"], teile=[2, 3])])
pruef(BH.radar_urteil(rd, 0, 1, {"x.jpg"})[0] == "zu duenn" and BH.radar_urteil(rd, 5, 6, {"b1.jpg"})[:3:2] == ("duenn", ["b1.jpg"]) and BH.radar_urteil(rd, 2, 3, set())[0] == "stark"
      and BH.radar_urteil(None, 0, 1, set())[0] is None, "radar_urteil: zu duenn / duenn + Startbild / nicht Ausloeser = stark / ohne Radar = Rueckfall")
kp2 = BH.kandidaten_paare(A, B.transformiert(M_AB), start=["b2.jpg"])
pruef(kp2 and kp2[0][0] == "b2.jpg", "kandidaten_paare: Radar-Startbilder zuerst")
print("FEHLER:" if fehler else "alle ok", len(fehler)); sys.exit(1 if fehler else 0)
