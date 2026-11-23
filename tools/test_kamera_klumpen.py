#!/usr/bin/env python3
"""Fester Test (Sekunden, CPU) fuer KAMERA-KLUMPEN (tools/lage_proben.kamera_nah / kameras_einmal, tools/sfm_lod2_ausrichten.py AUSR_KLUMPEN).
Befund Kettenlauf schwabentor-1122p (23.11.2026, lage_frueh rc 3 'oberkante besteht, kamerahoehe faellt, wandfit besteht' = WIDERSPRUCH gegen GPS x0,960):
ein stehendes Video (LMS3Va6psfY, 33 Bilder auf 1 cm, Einblendung) triangulierte 10431 von 76908 sparse-Punkten in eine 1-m-Kugel UM die Kamera. Folgen:
Kamerahoehe 0,26 m (58 von 66 Kameras ueber dem Klumpen), Massstab aus Kamerahoehe 0,0234 statt ~0,077, DGM1-Feinfit legte den Klumpen auf den Boden
(Kameras Median -0,40 m ueber DGM1; dichte Wolke ohne Klumpen +1,43 m).
  1 synthetisch: Boden + Waende, 40 Handkameras 1,6 m, dazu zwei stehende Videos (je 35 Bilder an EINER Stelle) mit zusammen ~12 % der Punkte als Klumpen um die Kamera.
    Kamerahoehe MIT Klumpen in der alten Rechnung (ohne Filter, ohne Aufnahmestellen) zu klein; neue Probe besteht (1,6 m); x0,8 faellt weiter.
  2 kamera_nah: Klumpen ganz erkannt, < 3 % der echten Punkte, Boden unter den Handkameras (1,6 m) bleibt; massstabsfrei (x0,07 SfM-Einheiten = gleiche Maske).
  3 kameras_einmal: je 35 Videobilder an einer Stelle zaehlen einmal.
  4 Aufruf in sfm_lod2_ausrichten.py vorhanden (KAMERA-KLUMPEN vor dem Lot, abschaltbar AUSR_KLUMPEN=0).
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_kamera_klumpen.py"""
import os, sys
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import lage_proben as LP

FEHLER = []
def pruef(bed, text):
    if not bed: FEHLER.append(text); print("FEHLER:", text)

rng = np.random.default_rng(23)
# Szene: Strasse 60 x 60 m, Waende an x = +-8 m bis 12 m Hoehe
boden = np.c_[rng.uniform(-30, 30, (30000, 2)), rng.normal(0, 0.03, 30000)]
wand = np.vstack([np.c_[np.full(8000, s * 8.0) + rng.normal(0, 0.05, 8000), rng.uniform(-30, 30, 8000), rng.uniform(0, 12, 8000)] for s in (-1, 1)])
echt = np.vstack([boden, wand])
C_hand = np.c_[rng.uniform(-6, 6, 40), rng.uniform(-25, 25, 40), np.full(40, 1.6) + rng.normal(0, 0.05, 40)]
c_vid = np.array([[2.0, 3.0, 1.55], [-3.0, -12.0, 1.62]])                                         # zwei stehende Videos: je 35 Bilder auf wenige mm (1122p: 58 von 66)
C_vid = np.vstack([c + rng.normal(0, 0.003, (35, 3)) for c in c_vid])
n_kl = int(0.06 * len(echt) / 0.88); kl = np.vstack([c + rng.normal(0, 0.25, (n_kl, 3)) for c in c_vid])   # Klumpen um die Kameras (Radius ~0,5-0,9 m), zusammen ~12 %
kl = kl[np.min([np.linalg.norm(kl - c, axis=1) for c in c_vid], 0) < 0.9]
P = np.vstack([echt, kl]); C = np.vstack([C_hand, C_vid]); ist_kl = np.r_[np.zeros(len(echt), bool), np.ones(len(kl), bool)]

# 2 kamera_nah
m = LP.kamera_nah(P, C)
pruef(m[ist_kl].mean() > 0.99, f"Klumpen nicht erkannt: {m[ist_kl].mean():.3f}")
pruef(m[~ist_kl].mean() < 0.03, f"zu viele echte Punkte als Klumpen: {m[~ist_kl].mean():.3f}")
unter = np.zeros(len(P), bool)
for c in C_hand: unter |= (np.hypot(*(P[:, :2] - c[:2]).T) < 1.0) & (P[:, 2] < 0.2)
pruef(not (m & unter & ~ist_kl).any(), f"Boden unter Handkameras als Klumpen verworfen: {(m & unter & ~ist_kl).sum()}")
pruef(np.array_equal(m, LP.kamera_nah(P * 0.07, C * 0.07)), "kamera_nah ist nicht massstabsfrei")
print(f"  kamera_nah: Klumpen {m[ist_kl].mean():.1%} erkannt, echte Punkte {m[~ist_kl].mean():.1%}")

# 3 kameras_einmal
e = LP.kameras_einmal(C)
pruef(len(e) == len(C_hand) + 2, f"stehendes Video zaehlt mehrfach: {len(e)} Aufnahmestellen bei {len(C_hand)} Handkameras + 2 Videos")

# 1 Kamerahoehe: alte Rechnung (ohne Filter/Aufnahmestellen) gegen neue Probe
def alt(P_, C_, r=LP.KAMERA_BODEN_R):
    from scipy.spatial import cKDTree
    b = cKDTree(P_[:, :2]); h = []
    for c in C_:
        ix = b.query_ball_point(c[:2], r); z = P_[ix, 2]; z = z[z < c[2]]
        if len(ix) >= 10 and len(z) >= 10: h.append(c[2] - np.percentile(z, 10))
    h = np.asarray(h); m0 = np.median(h); return float(np.median(h[(h > 0.25 * m0) & (h < 2 * m0)]))
h_alt = alt(P, C); pk = LP.probe_kamerahoehe(P, C); pk8 = LP.probe_kamerahoehe(P * 0.8, C * 0.8)
print(f"  Kamerahoehe alt {h_alt:.2f} m, neu {pk.get('wert')} m ({pk['urteil']}, Klumpen {pk.get('klumpen_punkte')}, Stellen {pk.get('aufnahmestellen')}), x0,8 {pk8.get('wert')} ({pk8['urteil']})")
pruef(h_alt < 1.2, f"Testszene bildet den Befund nicht nach (alte Rechnung {h_alt:.2f} m)")
pruef(pk["urteil"] == "besteht" and abs(pk["wert"] - 1.6) < 0.1, f"Kamerahoehe mit Klumpen muss bestehen: {pk}")
pruef(pk8["urteil"] == "faellt", f"x0,8 muss weiter fallen: {pk8}")
pruef(LP.probe_kamerahoehe(echt, C_hand)["urteil"] == "besteht", "ohne Klumpen muss die Probe weiter bestehen")

# 4 Aufruf in der Ausrichtung
src = open(os.path.join(T, "sfm_lod2_ausrichten.py"), encoding="utf-8").read()
i_k = src.find("LP.kamera_nah(Pg, C)"); i_lot = src.find("# 1. Lot aus der Kameraebene")
pruef(i_k > 0 and i_lot > i_k and 'AUSR_KLUMPEN' in src, "sfm_lod2_ausrichten: KAMERA-KLUMPEN-Filter fehlt oder steht nicht vor dem Lot")

print("FEHLER:", len(FEHLER)) if FEHLER else print("OK test_kamera_klumpen")
sys.exit(1 if FEHLER else 0)
