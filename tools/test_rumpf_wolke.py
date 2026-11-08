#!/usr/bin/env python3
"""test_rumpf_wolke.py - synthetischer Beweis fuer bauteil_rumpf_wolke (bekanntes Haus: Quader + Satteldach, gedreht 15 Grad; Rauschen 3 cm,
Ausreisser, Luecken, Sims; Szenario A = alle Seiten gesehen, B = nur Nordseite (Kameras von Norden)). Aufruf: ~/.venvs/rcpark/bin/python tools/test_rumpf_wolke.py"""
import os, sys, math, copy, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bauteil_rumpf_wolke as B
from manifold3d import Manifold as M
L, D, HE, ALPHA, TH, CEN = 18.0, 12.0, 7.0, 40.0, 15.0, np.array([2.0, 10.0]); T = math.tan(math.radians(ALPHA)); ZR = HE + T * D / 2
fails = []
def check(name, ok, info=""):
    print(("  OK   " if ok else "  FAIL ") + name + (f"  [{info}]" if info else "")); 
    if not ok: fails.append(name)
def tomodel(u, v, z):
    t = math.radians(TH); return np.c_[CEN[0] + u * math.cos(t) - v * math.sin(t), CEN[1] + u * math.sin(t) + v * math.cos(t), z]
def wahrheit():
    k = M.cube((L, D, ZR + 1)).translate((-L / 2, -D / 2, 0))
    for s in (+1, -1):
        n = np.array([0, s * T, 1.0]); n /= np.linalg.norm(n); k = k.trim_by_plane(tuple(-n), float(-(n @ np.array([0, 0, ZR]))))
    return k.rotate((0, 0, TH)).translate((CEN[0], CEN[1], 0))
def wolke(szenario, seed=1):
    rg = np.random.default_rng(seed); out = []; dens = 300                       # Punkte je m2
    def flaeche(area_pts, fn): out.append(fn(rg.random((int(area_pts), 2))))
    zroof = lambda v: ZR - T * np.abs(v)
    # Nordwand (v = +D/2) mit Fensterluecken, Sims 0.6 m davor
    nord = lambda r: tomodel(-L / 2 + r[:, 0] * L, np.full(len(r), D / 2), r[:, 1] * HE); flaeche(L * HE * dens, nord)
    sims = lambda r: tomodel(-L / 2 + r[:, 0] * L, D / 2 + 0.6 * np.ones(len(r)) * 0 + 0.6 * r[:, 1], np.full(len(r), 3.0)); flaeche(L * 0.6 * dens, sims)
    dachN = lambda r: tomodel(-L / 2 + r[:, 0] * L, (D / 2) * (1 - r[:, 1]), zroof((D / 2) * (1 - r[:, 1]))); flaeche(L * (D / 2) / math.cos(math.radians(ALPHA)) * dens, dachN)
    boden = lambda r: tomodel(-L / 2 - 3 + r[:, 0] * (L + 6), D / 2 + 1 + 5 * r[:, 1], np.full(len(r), 0.0)); flaeche((L + 6) * 5 * dens / 4, boden)
    if szenario == "A":
        sued = lambda r: tomodel(-L / 2 + r[:, 0] * L, np.full(len(r), -D / 2), r[:, 1] * HE); flaeche(L * HE * dens, sued)
        dachS = lambda r: tomodel(-L / 2 + r[:, 0] * L, -(D / 2) * (1 - r[:, 1]), zroof((D / 2) * (1 - r[:, 1]))); flaeche(L * (D / 2) / math.cos(math.radians(ALPHA)) * dens, dachS)
        for sg in (+1, -1):
            gi = lambda r, sg=sg: (lambda v, f: tomodel(np.full(len(r), sg * L / 2), v, f * zroof(v) + 0 * v))(-D / 2 + r[:, 0] * D, r[:, 1]); flaeche(D * ZR * dens / 2, gi)
    P = np.vstack(out); P = P + rg.normal(0, 0.03, P.shape)                                                  # Rauschen 3 cm
    k = rg.random(len(P)) > 0.0
    for _ in range(25):                                                                                         # Luecken: Kugeln r=0.8 m ohne Punkte
        c = P[rg.integers(len(P))]; k &= np.linalg.norm(P - c, axis=1) > 0.8
    P = P[k]; bb0, bb1 = P.min(0), P.max(0); P = np.vstack([P, bb0 + rg.random((int(0.02 * len(P)), 3)) * (bb1 - bb0)])   # 2 % Ausreisser im Kasten
    return P
def kanten_wahr(dv_sued=0.0, dv_nord=0.0, du=0.0):
    ecken = [(-L / 2 - du, -D / 2 + dv_sued), (L / 2 + du, -D / 2 + dv_sued), (L / 2 + du, D / 2 + dv_nord), (-L / 2 - du, D / 2 + dv_nord)]; xy = tomodel(np.array([e[0] for e in ecken]), np.array([e[1] for e in ecken]), np.zeros(4))[:, :2]
    return [[xy[i].tolist(), xy[(i + 1) % 4].tolist()] for i in range(4)]
def iou(par):
    a = wahrheit(); b = B.koerper(par, M, None); i = (a ^ b).volume() if False else (a - (a - b)).volume() if False else None
    inter = (a ^ b) ; ia = a.volume() + b.volume() - (a + b).volume() * 1.0  # |A|+|B|-|A u B| = |A n B|
    return ia / (a + b).volume()
q = lambda *_: None
print("== Szenario A: alle Seiten gesehen =="); PA = wolke("A"); parA = B.schaetzen(PA, {}, None, log=q)
check("A: Winkel 15 +-0.5 Grad (Modulo 90)", abs(((parA["winkel_grad"] - TH + 45) % 90) - 45) < 0.5, f"{parA['winkel_grad']:.2f}")
check("A: alle vier Waende aus Wolke", all(h == "wolke" for h in parA["wand_herkunft"].values()), str(parA["wand_herkunft"]))
d = parA["dach"]; check("A: Neigung 40 +-1 Grad", abs(math.degrees(math.atan(d["t1"])) - ALPHA) < 1.0 and abs(math.degrees(math.atan(d["t2"])) - ALPHA) < 1.0, f"{math.degrees(math.atan(d['t1'])):.2f}/{math.degrees(math.atan(d['t2'])):.2f}")
check("A: First-z +-0.15 m", abs(d["z_r"] - ZR) < 0.15, f"{d['z_r']:.3f} soll {ZR:.3f}"); check("A: Gegenseite aus Wolke (First = Ebenenschnitt)", d["gegenseite"].startswith("WOLKE"), d["gegenseite"])
check("A: IoU Koerper/Wahrheit > 0.97", iou(parA) > 0.97, f"{iou(parA):.4f}")
print("== A mit falscher Ersatzquelle (alles 2 m daneben): darf NICHT benutzt werden ==")
bad = kanten_wahr(dv_sued=-2.0, dv_nord=2.0, du=2.0); parA2 = B.schaetzen(PA, {}, bad, log=q)
check("A+Ersatz: Waende bleiben Wolke, Ersatz ungenutzt", all(h == "wolke" for h in parA2["wand_herkunft"].values()) and abs(parA2["wand"]["v1"] - parA["wand"]["v1"]) < 1e-9)
print("== Szenario B: nur Nordseite, Luecken ==")
PB = wolke("B"); parB = B.schaetzen(PB, {}, kanten_wahr(), log=q); h = parB["wand_herkunft"]
luecken = [k for k, v in h.items() if v != "wolke"]; check("B: Luecken erkannt = u0,u1,v0 (nicht v1)", sorted(luecken) == ["u0", "u1", "v0"], str(luecken))
check("B: Luecken aus Ersatz (geprueft)", all(h[k].startswith("ersatz (") for k in luecken))
check("B: N-Wand aus Wolke", h["v1"] == "wolke"); check("B: IoU mit Ersatz > 0.95", iou(parB) > 0.95, f"{iou(parB):.4f}")
check("B: First-z +-0.15 m (ohne Gegenseite)", abs(parB["dach"]["z_r"] - ZR) < 0.15, f"{parB['dach']['z_r']:.3f}"); check("B: Neigung +-1 Grad", abs(math.degrees(math.atan(parB["dach"]["t1"])) - ALPHA) < 1.0)
print("== B mit Ersatz, der der Wolke WIDERSPRICHT (Suedwand-Kante mitten im Dach) und falscher Nordkante ==")
widers = kanten_wahr(dv_sued=D * 0.75, dv_nord=1.0); parB2 = B.schaetzen(PB, {}, widers, log=q); h2 = parB2["wand_herkunft"]
check("B2: widerspruechiger Suedersatz verworfen", h2["v0"].startswith("Ersatz ohne gueltigen Kandidat") and "gespiegelt" in h2["v0"], h2["v0"])
check("B2: N-Wand unveraendert aus Wolke (Ersatz 1 m daneben ignoriert)", h2["v1"] == "wolke" and abs(parB2["wand"]["v1"] - parB["wand"]["v1"]) < 1e-9)
check("B2: Koerper nach Spiegelung ~ Wahrheit (IoU > 0.95)", iou(parB2) > 0.95, f"{iou(parB2):.4f}")
print("== B ohne jede Ersatzquelle ==")
parB3 = B.schaetzen(PB, {}, None, log=q); check("B3: Suedwand gespiegelt am First, markiert", "gespiegelt am First" in parB3["wand_herkunft"]["v0"] and "ANNAHME" in parB3["wand_herkunft"]["v0"], parB3["wand_herkunft"]["v0"])
check("B3: IoU > 0.9", iou(parB3) > 0.9, f"{iou(parB3):.4f}")
print("== Parameter: versatz/fest ==")
cf = {"versatz": {"first_z_m": 1.5}}; p1, e1 = B.anwenden(parA, cf); check("versatz first_z_m +1.5", abs(p1["dach"]["z_r"] - parA["dach"]["z_r"] - 1.5) < 1e-9 and e1[0][3] == "versatz")
p2, e2 = B.anwenden(parA, {"versatz": {"first_z_m": 1.5}, "fest": {"first_z": 20.0}}); check("fest schlaegt versatz", p2["dach"]["z_r"] == 20.0 and e2[0][3] == "fest")
p3, _ = B.anwenden(parA, {"versatz": {"neigung_grad": 2.0, "wand_v1_m": 0.3}}); check("versatz Neigung +2 Grad / Wand v1 +0.3", abs(math.degrees(math.atan(p3["dach"]["t1"])) - math.degrees(math.atan(parA["dach"]["t1"])) - 2) < 1e-6 and abs(p3["wand"]["v1"] - parA["wand"]["v1"] - 0.3) < 1e-9)
k = B.koerper(p1, M, None); check("Koerper mit Versatz: Hoehe = First", abs(k.bounding_box()[5] - p1["dach"]["z_r"]) < 1e-6)
mm = B.koerper(parA, M, None).to_mesh(); import trimesh; tm = trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts)); check("wasserdicht, 1 Koerper", tm.is_watertight and len(tm.split(only_watertight=False)) == 1)
print("\nERGEBNIS:", "ALLE BESTANDEN" if not fails else f"{len(fails)} FEHLER: {fails}"); sys.exit(1 if fails else 0)
