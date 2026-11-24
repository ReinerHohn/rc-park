#!/usr/bin/env python3
"""test_umgang_eckquader.py - fester synthetischer Test (21.11.2026) fuer
  (1) tools/umgang_aus_fotos.py: Zone unter der Traufe aus Zeilenkanten (dunkler Ruecksprung ueber heller Wand), Pfosten als schmale dunkle Senken
      (breite dunkle Eckflaeche zaehlt nicht), Konsens ueber Fotos (Kabel in einem Foto faellt heraus), Ecken aus Wandfluchten;
  (2) bauteile.umgang_aus_json: baut nur bei gefunden=true, Ruecksprung wirklich im Koerper, Pfosten stehen;
  (3) bauteile.eckquader_aus_relief + fassaden_kette.wandende_ist_ecke: verzahnte Steine am Eckende erkannt, Steinwand ohne Putz und Wandmitte nicht.
  (4) 24.11.2026: Entzerrung auf der GESETZTEN Wandlage (rote Probe LoD2-Ebene: Unterkante um Versatz x tan(Blickhoehe) falsch), wandlage() Fallback 0,
      oberkante_belegt(): Fotokanten-Linie auf der gesetzten Wand hebt den LoD2-Deckel auf, Rauschen/keine Datei/falsche Ebene nicht.
Werte sind Testgeometrie, kein Objektmass. < 5 s."""
import os, sys, json, tempfile
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import umgang_aus_fotos as U, bauteile as B, fassaden_kette as FK
from manifold3d import Manifold as M

fehler = []
Z = U.ZELLE
# --- (1) synthetisches entzerrtes Band: z 31.4 .. 37.0 (Zeile 0 oben), u 0..8 m; Wand hell 0.8, Ruecksprung z 35..36.6 dunkel 0.3, Dach darueber 0.1
zz = np.arange(37.0, 31.4, -Z); uu = np.arange(0.0, 8.0, Z)
def band(pfosten_u, kabel=None):
    g = np.full((len(zz), len(uu)), 0.8, np.float32)
    g[(zz >= 35.0) & (zz < 36.6)] = 0.3; g[zz >= 36.6] = 0.1
    zone = (zz >= 35.0) & (zz < 36.6)
    g[np.ix_(zone, uu < 0.6)] = 0.12; g[np.ix_(zone, uu > 7.4)] = 0.12           # dunkle Ecken (Eckpfosten vor Eckquadern)
    g[np.ix_(zone, (uu > 0.6) & (uu < 1.5))] = 0.18                                 # breite dunkle Flaeche (Rueckwand-Quader) - kein Pfosten
    for p in pfosten_u: g[np.ix_(zone, np.abs(uu - p) < 0.08)] = 0.08
    if kabel is not None: g[np.ix_(zone, np.abs(uu - kabel) < 0.03)] = 0.05
    return g + np.random.default_rng(1).normal(0, 0.01, g.shape).astype(np.float32)
ok = np.ones((len(zz), len(uu)), bool); listen = []
for i, kab in enumerate((None, 5.1, None)):
    g = band([2.8, 5.4], kab); r = U.zone_aus_band(g, ok, zz)
    if r is None or abs(r[0] - 35.0) > 0.1 or r[1] < 36.4: fehler.append(f"Zone falsch: {r and r[:2]} statt 35,0..36,6"); continue
    n, L = U.pfosten_zaehlen(g, ok, zz, uu, r[0], min(r[1], 36.6)); listen.append(L)
    if kab is None and n != 4: fehler.append(f"Pfosten {n} statt 4 (2 innen + 2 Ecken), Lagen {L}")
k = U.pfosten_konsens(listen)
if k is None or len(k) != 2 or abs(k[0] - 2.8) > 0.1 or abs(k[1] - 5.4) > 0.1: fehler.append(f"Konsens {k} statt [2.8, 5.4] (Kabel nur in einem Foto)")
W4 = [dict(id=str(i), o=o, d=d, u=[-4, 4], z=[0, 36.6]) for i, (o, d) in enumerate((([4, 0], [0, 1]), ([0, 4], [-1, 0]), ([-4, 0], [0, -1]), ([0, -4], [1, 0])))]
E = U.ecken_aus_waenden(W4)
if E is None or len(E) != 4 or any(abs(abs(x) - 4) > 1e-6 for e in E for x in e): fehler.append(f"Ecken {E}")

# --- (2) Bau aus JSON
turm = M.cube((8, 8, 37)).translate((-4, -4, 0))
with tempfile.TemporaryDirectory() as T:
    f = os.path.join(T, "u.json")
    json.dump(dict(gefunden=False, grund="test"), open(f, "w")); k0, b0 = B.umgang_aus_json(turm, f)
    if abs(k0.volume() - turm.volume()) > 1e-6 or "NICHT" not in b0[0]["element"] or "umgang" in b0[0]["element"].lower(): fehler.append("gefunden=false baut trotzdem / Beleg heisst Umgang")
    json.dump(dict(gefunden=True, z0=35.0, z1=36.6, pfosten_je_seite=4, ecken=E, fotos_gut=3, waende=[]), open(f, "w")); k1, b1 = B.umgang_aus_json(turm, f)
    if not b1 or b1[0].get("pfosten_je_seite") != 4: fehler.append(f"Beleg ohne Pfostenzahl: {b1}")
    # Ruecksprung: Mitte der Nordwand in Umganghoehe 0,5 m innen ist leer, Pfosten an der Ecke steht
    probe = lambda x, y, z: (k1 ^ M.cube((0.04, 0.04, 0.04)).translate((x - 0.02, y - 0.02, z - 0.02))).volume() > 1e-6
    if probe(3.5, 1.0, 35.8): fehler.append("kein Ruecksprung hinter den Pfosten")
    if not probe(3.98, 3.85, 35.8): fehler.append("Eckpfosten fehlt")
    if not probe(3.5, 1.0, 34.0): fehler.append("Wand unter dem Umgang fehlt")

# --- (3) Eckquader: Wand 5 m breit, Putz 0, Steine (Bosse 0,05) am Anfang verzahnt 0,6 / 1,2 m breit in 0,5-m-Lagen ueber z 20..30; Wandmitte Putz
px = 0.05; h = int(16 / px); w = int(5 / px); rel = np.zeros((h, w), np.float32); z0 = 16.0
for j in range(20):                                        # Lagen von z 20 bis 30
    za, zb = 20 + 0.5 * j, 20 + 0.5 * (j + 1); r0, r1 = int((z0 + h * px - zb) / px), int((z0 + h * px - za) / px)
    rel[r0:r1, :int((1.2 if j % 2 else 0.6) / px)] = 0.05; rel[r0, :int(1.2 / px)] = -0.02     # Lagerfuge
q = B.eckquader_aus_relief(rel, px, z0, 0.0, True, True)
if len(q) != 1 or q[0]["ende"] != "anfang" or abs(q[0]["z0"] - 20) > 0.6 or abs(q[0]["z1"] - 30) > 0.6 or q[0]["lagen"] < 10: fehler.append(f"Eckquader nicht erkannt: {q}")
if B.eckquader_aus_relief(np.full((h, w), 0.05, np.float32), px, z0, 0.0, True, True): fehler.append("volle Steinwand als Eckquader gemeldet")
if B.eckquader_aus_relief(rel, px, z0, 0.0, False, True): fehler.append("Eckquader an einem Wandende ohne Ecke gemeldet")
WW = [dict(name="a", a=[0, 0], b=[4, 0]), dict(name="b", a=[4.2, 0], b=[9, 0]), dict(name="c", a=[9, 0], b=[9, 5])]
if FK.wandende_ist_ecke(WW, WW[0], "b") or not FK.wandende_ist_ecke(WW, WW[0], "a") or not FK.wandende_ist_ecke(WW, WW[1], "b"): fehler.append("wandende_ist_ecke falsch")

# Koerperflaeche messen (Fotosteine sitzen darauf statt auf der Netzebene): Wand bei x = 0, Wandebene bei x = 0,15 -> -0,15; Fensterloch in einer Probe faellt als Ausreisser heraus
kw = M.cube((10, 10, 30)).translate((-10, -5, 0)) - M.cube((1, 1, 1)).translate((-0.5, -0.5, 9.5))
fl = FK.koerper_flaeche(kw, [0.15, 0], [0, 1], [1, 0], [(0, 10), (1, 20), (-1, 5)])
if fl is None or abs(fl + 0.15) > 0.02: fehler.append(f"koerper_flaeche {fl} statt -0,15")


# --- (4) 24.11.2026 GESETZTE WANDLAGE (Befund Hoehen-Angleich 1122: entzerrt auf der LoD2-Ebene, Wand 0,29-0,36 m dahinter) + LoD2-Deckel nur ohne Fotokanten-Beleg
import cv2
F4 = dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, -1.0], u=[-4.0, 4.0], z=[0.0, 36.97]); WV = -0.4                 # Wand liegt 0,4 m HINTER der LoD2-Ebene
C4 = np.array([0.3, -15.0, 1.6]); fw = np.array([0.0, 15.0, 32.4]); fw /= np.linalg.norm(fw); rx = np.cross(fw, [0, 0, 1.0]); rx /= np.linalg.norm(rx); ry = np.cross(fw, rx)
R4 = np.array([rx, ry, fw]); K4 = dict(rvec=cv2.Rodrigues(R4)[0].ravel().tolist(), t=(-R4 @ C4).tolist(), f_px=900.0, cx=400.0, cy=500.0, k1=0.0)
uu4, vv4 = np.meshgrid(np.arange(800) + 0.5, np.arange(1000) + 0.5); r4 = np.stack([(uu4 - 400) / 900, (vv4 - 500) / 900, np.ones_like(uu4)], -1) @ R4
lam = (-WV - C4[1]) / r4[..., 1]; zw = C4[2] + lam * r4[..., 2]                                                              # Schnitt mit der wahren Wand y = 0,4
img = np.where(zw < 35.0, 0.8, np.where(zw < 36.6, 0.3, 0.1)) * 255; img = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
def zone4(wv):
    zt = 36.97; dz_ = U.band_verschiebung(wv, C4, np.array(F4["o"]) + wv * np.array(F4["n"]), np.array(F4["n"]), zt, 5.0)
    b4, ok4, _, zz4 = U.band_entzerren(F4, K4, img, zt - 5.0 + dz_, zt + 0.6 + dz_, wv)
    return U.zone_aus_band(cv2.cvtColor(b4, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0, ok4, zz4)
z_alt, z_neu = zone4(0.0), zone4(WV); print(f"  (4) Umgang-Unterkante LoD2-Ebene {z_alt and round(z_alt[0], 2)}, gesetzte Wand {z_neu and round(z_neu[0], 2)} (Soll 35,0)")
if z_neu is None or abs(z_neu[0] - 35.0) > 0.06: fehler.append(f"(4) gesetzte Wandlage: Umgang-Unterkante {z_neu and round(z_neu[0], 2)} statt 35,0 +- 0,06")
if z_alt is None or abs(z_alt[0] - 35.0) < 0.2: fehler.append(f"(4) rote Probe: LoD2-Ebene muesste die Unterkante > 0,2 m falsch setzen (Versatz x tan Blickhoehe), ist {z_alt and round(z_alt[0], 2)}")
with tempfile.TemporaryDirectory() as td4:
    kj = os.path.join(td4, "schleife_korrekturen.json")
    if U.wandlage(F4, kj, (32.0, 37.6)) != 0.0: fehler.append("(4) ohne schleife_korrekturen.json: Wandlage muss 0 (LoD2, Fallback) sein")
    json.dump(dict(korrekturen=[dict(id="wl_f00", art="wandversatz", o=[0.0, 0.0], n=[0.0, -1.0], w_soll=WV, angenommen=True)]), open(kj, "w"))
    if abs(U.wandlage(F4, kj, (32.0, 37.6)) - WV) > 1e-9: fehler.append(f"(4) Wandlage aus schleife_korrekturen.json {U.wandlage(F4, kj, (32.0, 37.6))} statt {WV}")
rng4 = np.random.default_rng(4); n4 = 300
lin = np.c_[rng4.uniform(-3, 3, n4), np.full(n4, -WV) + rng4.normal(0, 0.03, n4), np.full(n4, 37.3) + rng4.normal(0, 0.02, n4)]; ref4 = np.resize(np.arange(5), n4)
rausch = np.c_[rng4.uniform(-3, 3, 200), np.full(200, -WV) + rng4.normal(0, 0.05, 200), rng4.uniform(36.5, 38.0, 200)]
b_ja, _ = U.oberkante_belegt(np.vstack([lin, rausch]), np.r_[ref4, rng4.integers(0, 9, 200)], [F4], {"f00": WV}, 37.3)
b_nein, _ = U.oberkante_belegt(rausch, rng4.integers(0, 9, 200), [F4], {"f00": WV}, 37.3)
b_lod2, _ = U.oberkante_belegt(np.vstack([lin, rausch]), np.r_[ref4, rng4.integers(0, 9, 200)], [F4], {"f00": 0.0}, 37.3)   # Linie liegt 0,4 m hinter der LoD2-Ebene
if not b_ja: fehler.append("(4) Fotokanten-Linie in z1 auf der gesetzten Wand nicht als Beleg erkannt (Deckel bliebe)")
if b_nein or U.oberkante_belegt(None, None, [F4], {}, 37.3)[0]: fehler.append("(4) Rauschen/keine Kanten duerfen den LoD2-Deckel nicht aufheben")
if b_lod2: fehler.append("(4) Kante 0,4 m hinter der gepruefen Ebene darf nicht belegen (Toleranz 0,15 m)")
if fehler: print("FEHLER umgang/eckquader:", "; ".join(fehler)); sys.exit(1)
print("OK umgang/eckquader: Zone + 4 Pfosten (Kabel/Eckflaeche ignoriert), Bau mit Ruecksprung, Eckquader nur an der Ecke mit Putz daneben; Umgang auf gesetzter Wandlage, LoD2-Deckel nur ohne Fotokanten-Beleg")
