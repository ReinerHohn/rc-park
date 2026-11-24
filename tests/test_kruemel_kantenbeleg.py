#!/usr/bin/env python3
"""test_kruemel_kantenbeleg.py - fester synthetischer Test (24.11.2026, Lauf 1122w Schwabentor: 'Knochen'-Blob ueber dem Torbogen Nord, Beulen im bemalten Putz Sued,
Brunnen-Wulst) fuer putz_wandbild.relief_kanten_beleg: Relief nur mit Tiefenbeleg in den triangulierten Fotokanten der Wandebene.
  (1) Blob ohne Kanten -> Wandniveau, MIT Uebergangsrand (keine Umrissstufe)
  (2) echter Koerper mit Kanten auf seiner Fronttiefe -> bleibt
  (3) Gemaelde-Blob: Kanten nur auf der Wandebene -> flach
  (4) Blob mit Kanten 1 m davor (Vordach/Galerie verdeckt) -> flach
  (5) linienhaftes Gesims ohne Kanten -> bleibt
  (6) Grat schmaler als 0,8 mm H0 -> flach
  (7) Bogen am Oeffnungsrand -> bleibt; Quadersteine (aus_maske) unberuehrt
  (8) ohne Kanten (None) -> unveraendert
  (9) Rot-Probe: Abweichungen bleiben nicht zufaellig stehen (Blob-Hoehe vorher 0,10 m)
Werte sind Testgeometrie, kein Objektmass. < 10 s."""
import os, sys, tempfile
import numpy as np
H_ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"); sys.path.insert(0, H_)
import putz_wandbild as PW

fehler = []
def pruef(b, t):
    if not b: fehler.append(t)

px = 0.05; H, W = 160, 160                      # 8 x 8 m
u0, z0 = 0.0, 0.0
uu = u0 + (np.arange(W) + 0.5) * px; zz = z0 + (H - 1 - np.arange(H) + 0.5) * px; UU, ZZ = np.meshgrid(uu, zz)
rel = np.full((H, W), 0.11, np.float32)
def kuppel(uc, zc, ru, rz, h): r = ((UU - uc) / ru) ** 2 + ((ZZ - zc) / rz) ** 2; return np.where(r < 1, h * (1 - r), 0.0)
rel += kuppel(1.5, 6.5, 0.4, 0.5, 0.10)          # (1) Blob ohne Kanten
blk = (np.abs(UU - 4.0) < 0.5) & (np.abs(ZZ - 6.5) < 0.5); rel[blk] += 0.12      # (2) echter Koerper
rel += kuppel(6.5, 6.5, 0.4, 0.4, 0.10)          # (3) Gemaelde
rel += kuppel(1.5, 4.0, 0.4, 0.4, 0.10)          # (4) verdeckt
ges = (np.abs(ZZ - 2.5) < 0.1) & (UU > 3.0) & (UU < 6.5); rel[ges] += 0.08          # (5) Gesims
grat = (np.abs(UU - 7.5) < 0.025) & (np.abs(ZZ - 4.0) < 0.6); rel[grat] += 0.10      # (6) 5 cm breiter Grat
oe = (np.abs(UU - 1.5) < 0.6) & (ZZ < 1.5); bogen = ~oe & (np.abs(UU - 1.5) < 0.8) & (ZZ < 1.7); rel[bogen] += 0.08   # (7) Bogen am Oeffnungsrand
stein = (np.abs(UU - 4.5) < 0.3) & (np.abs(ZZ - 4.2) < 0.2); rel[stein] += 0.15    # (7) Quaderstein
rel[oe] = 0.01
# Kanten (u, z, w): Wandebene w = 0; Raster ueberall auf der Wand (Gemaelde-/Putzkanten), dazu Koerperumriss auf +0,12, Vordach-Kanten auf +1,0 um (4)
K = [(u, z, 0.0) for u in np.arange(0.2, 8.0, 0.25) for z in np.arange(0.2, 8.0, 0.25)]
for t in np.linspace(0, 1, 40):
    for (ua, za, ub, zb) in ((3.5, 6.0, 4.5, 6.0), (3.5, 7.0, 4.5, 7.0), (3.5, 6.0, 3.5, 7.0), (4.5, 6.0, 4.5, 7.0)):
        K.append((ua + t * (ub - ua), za + t * (zb - za), 0.12))
for a in np.linspace(0, 2 * np.pi, 40): K.append((1.5 + 0.45 * np.cos(a), 4.0 + 0.45 * np.sin(a), 1.0))
for a in np.linspace(0, 2 * np.pi, 30): K.append((6.5 + 0.42 * np.cos(a), 6.5 + 0.42 * np.sin(a), 0.0))
K = np.array(K, float)

T = tempfile.mkdtemp(prefix="test_kruemel_kb_"); fi = os.path.join(T, "w_voll.npz"); fo = os.path.join(T, "w_kb.npz")
Zd = dict(rel=rel, a=np.array([0.0, 0.0, 0.0]), t=np.array([1.0, 0.0, 0.0]), n=np.array([0.0, -1.0, 0.0]), u0=u0, z0=z0, px=px, oeffnung=oe, wand=np.ones((H, W), bool))
np.savez_compressed(fi, **Zd)
inf = PW.relief_kanten_beleg(fi, fo, K, druck_min=0.0696, aus_maske=stein)
R = np.load(fo)["rel"]
def hub(mask): return float(R[mask].max() - 0.11)
b1 = kuppel(1.5, 6.5, 0.4, 0.5, 1.0) > 0
pruef(float((rel[b1] - 0.11).max()) > 0.09, "(9) Rot-Probe: Blob vorher nicht da")
pruef(hub(b1) < 0.005, f"(1) Blob ohne Kanten nicht flach: {hub(b1):.3f}")
ring = (kuppel(1.5, 6.5, 0.55, 0.65, 1.0) > 0)
pruef(np.abs(R[ring] - 0.11).max() < 0.005, f"(1) Uebergangsrand bleibt als Stufe: {np.abs(R[ring] - 0.11).max():.3f}")
pruef(hub(blk) > 0.11, f"(2) echter Koerper mit Kanten weg: {hub(blk):.3f}")
pruef(hub(kuppel(6.5, 6.5, 0.4, 0.4, 1.0) > 0) < 0.005, "(3) Gemaelde-Blob (Kanten auf der Wand) nicht flach")
pruef(hub(kuppel(1.5, 4.0, 0.4, 0.4, 1.0) > 0) < 0.005, "(4) Blob hinter Vordach-Kanten (1 m davor) nicht flach")
pruef(hub(ges) > 0.07, "(5) linienhaftes Gesims ohne Kanten weg")
pruef(hub(grat) < 0.005, "(6) Grat < 0,8 mm H0 nicht flach")
pruef(hub(bogen) > 0.07, "(7) Bogen am Oeffnungsrand weg")
pruef(np.allclose(R[stein], rel[stein]), "(7) Quaderstein veraendert")
pruef(np.allclose(R[oe], 0.01), "(7) Oeffnung veraendert")
inf0 = PW.relief_kanten_beleg(fi, os.path.join(T, "x.npz"), None)
pruef(inf0.get("unveraendert") and not os.path.exists(os.path.join(T, "x.npz")), "(8) ohne Kanten nicht unveraendert")
pruef(os.path.exists(fo[:-4] + ".jpg"), "Kontrollbild fehlt")
import shutil; shutil.rmtree(T, ignore_errors=True)
if fehler: print("FEHLER:", "; ".join(fehler)); sys.exit(1)
print("ok", inf)
