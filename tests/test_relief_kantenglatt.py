#!/usr/bin/env python3
"""test_relief_kantenglatt.py - fester synthetischer Test (24.11.2026, Befund Lauf 1122x Schwabentor f00_wand: 392 544 Modellkanten gegen 18 975 Fotokanten,
'erfunden 0,984') fuer tools/relief_kantenglatt.py (Kettenstufe 'Feinrauschen ohne Fotokante glaetten', fassaden_kette.kantenglatt).
  (1) knick_kanten zaehlt dieselben Knickkanten wie trimesh.face_adjacency_angles auf dem Gitter von relief_einsatz.koerper (wenn trimesh da ist)
  (2) Rauschen 2 cm ohne Fotokante -> Modellkanten < 40 %, 'erfunden' sinkt, Fotokanten-Recall sinkt NICHT
  (3) belegte Stufe (Gesims 12 cm, Fotokanten an der Oberkante) bleibt: Stufenhoehe >= 0,10 m
  (4) Quaderraster (stein_id + Rille) bitgleich unberuehrt
  (5) ohne Fotokanten -> Datei-Stufe unveraendert (kein Urteil ohne Kantenstufe)
  (6) Fenster = kleinstes ungerades >= druck_min/px, mindestens 3 (kein freier Faktor)
  (7) Datei-Stufe behaelt alle Schluessel und schreibt 'kantenglatt'
  (8) Rot-Probe: ohne Glaettung bleiben die Rauschkanten (Messung nicht blind)
Werte sind Testgeometrie, kein Objektmass. < 10 s."""
import os, sys, json, tempfile
import numpy as np
H_ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"); sys.path.insert(0, H_)
import relief_kantenglatt as RK

fehler = []
def pruef(b, t):
    if not b: fehler.append(t)

px = 0.03; H, W = 200, 160; u0, z0 = 0.0, 0.0; dm = 0.0008 * 87
rng = np.random.default_rng(7); U, Z = RK.gitter(H, W, px, u0, z0)
rel = rng.normal(0, 0.02, (H, W)).astype(np.float32)
ges = Z >= 3.0; rel[ges] += 0.12                                                 # Gesims-Stufe bei z = 3 m, ueber die ganze Breite
stein = (U > 3.3) & (U < 4.2) & (Z > 4.5) & (Z < 5.4); sid = np.zeros((H, W), np.int32); sid[stein] = 1
rel[stein] = 0.2; rille = (U > 4.2) & (U < 4.27) & (Z > 4.5) & (Z < 5.4); rel[rille] = 0.08   # Stein mit Rille (Quaderraster)
uk = np.arange(0.05, W * px, 0.02); K = np.c_[uk, np.full_like(uk, 3.0), np.full_like(uk, 0.12)]   # Fotokanten an der Gesimskante
K = np.r_[K, np.c_[np.full(30, 0.3), np.linspace(1.0, 2.0, 30), np.zeros(30)]]                   # ein paar Fotokanten auf der Rauschflaeche (nicht auf Knicken)

# (1) gegen trimesh
try:
    import trimesh
    V = np.stack([U.ravel(), Z.ravel(), rel.ravel()], 1); ii, jj = np.mgrid[0:H, 0:W]; idx = ii * W + jj
    q00, q01, q10, q11 = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    m = trimesh.Trimesh(V, np.vstack([np.c_[q00, q10, q01], np.c_[q01, q10, q11]]), process=False)
    n_tm = int((m.face_adjacency_angles > np.radians(30)).sum()); n_rk = len(RK.knick_kanten(rel, px, u0, z0)) // 2
    pruef(n_tm == n_rk, f"(1) knick_kanten {n_rk} != trimesh {n_tm}")
except ImportError: pass

beh = np.zeros((H, W), bool); beh[(U > 3.25) & (U < 4.35) & (Z > 4.45) & (Z < 5.45)] = True
vor = RK.messen(rel, px, u0, z0, K); neu, info = RK.glaetten(rel, px, u0, z0, K, dm, behalten=beh); nach = RK.messen(neu, px, u0, z0, K, versatz=vor["versatz"])
# (2)
pruef(nach["modellkanten"] < 0.4 * vor["modellkanten"], f"(2) Modellkanten {vor['modellkanten']} -> {nach['modellkanten']} (< 40 % erwartet)")
pruef(nach["erfunden"] < vor["erfunden"], f"(2) erfunden {vor['erfunden']} -> {nach['erfunden']}")
pruef(nach["recall"] >= vor["recall"], f"(2) Recall sinkt {vor['recall']} -> {nach['recall']}")
# (3)
sp = (U > 0.5) & (U < 3.0); oben = sp & (Z > 3.05) & (Z < 3.3); unten = sp & (Z > 2.7) & (Z < 2.95)
stufe = float(np.median(neu[oben]) - np.median(neu[unten])); pruef(stufe >= 0.10, f"(3) Gesimsstufe nur {stufe:.3f} m")
# (4)
pruef(np.array_equal(neu[beh], rel[beh]), "(4) Quaderraster veraendert")
# (6)
pruef(RK.fenster_zellen(0.05, dm) == 3 and RK.fenster_zellen(0.02, dm) == 5 and RK.fenster_zellen(0.01, dm) == 7 and RK.fenster_zellen(0.03, dm) == 3, "(6) Fensterbreite")
# (5) + (7)
with tempfile.TemporaryDirectory() as td:
    fi = os.path.join(td, "w_test.npz"); fo = os.path.join(td, "w_test_kg.npz")
    np.savez_compressed(fi, rel=rel, a=np.zeros(2), t=np.array([1.0, 0.0]), n=np.array([0.0, -1.0]), u0=u0, z0=z0, px=px, stein_id=sid, putz_niveau_m=0.0,
                        quader_relief=json.dumps(dict(rille_breite_m=0.07)))
    r0 = RK.relief_kantenglatt(fi, fo, None, dm); pruef(r0.get("unveraendert") and not os.path.exists(fo), "(5) ohne Fotokanten nicht unveraendert")
    r1 = RK.relief_kantenglatt(fi, fo, K, dm); pruef(os.path.exists(fo) and not r1.get("unveraendert"), f"(7) Datei nicht geschrieben: {r1.get('grund')}")
    if os.path.exists(fo):
        Zo = np.load(fo); pruef({"rel", "a", "t", "n", "u0", "z0", "px", "stein_id", "putz_niveau_m", "quader_relief", "kantenglatt"} <= set(Zo.files), f"(7) Schluessel fehlen: {Zo.files}")
        pruef(np.array_equal(Zo["rel"][sid > 0], rel[sid > 0]), "(7) Steine in der Datei veraendert")
# (8)
pruef(vor["modellkanten"] > 5 * max(nach["modellkanten"], 1) or vor["erfunden"] > 0.5, f"(8) Rot-Probe: Rauschen erzeugt kaum Kanten ({vor})")

print(f"vorher {vor} | nachher {nach} | {info}")
if fehler:
    for f_ in fehler: print("FEHLER", f_)
    sys.exit(1)
print("OK test_relief_kantenglatt")
