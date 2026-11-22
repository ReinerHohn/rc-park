#!/usr/bin/env python3
"""Fester Test (Sekunden, ohne GPU) fuer das GPS-Tor tools/lage_gps_pruefen.py - Fernfotos und Anker-Kasten (22.11.2026, Lauf kette-schwabentor-anker-1122e).
Befund: tor_gps fiel bei GPS-Fit +8 Grad x1,089 (innerhalb 15 Grad / 15 %) NUR an 'Fernfotos (n 5): x4,45, 22 Grad' durch. Die 5 waren vier Fotos mit DEMSELBEN
eingefrorenen Geotag (272 m, Modell 61 m) und eine falsch registrierte Kamera (od_08, Modell 75 km weit). Fix: Fernfotos zaehlen nur, wenn ihr GPS unter dem FREIEN
Fit stimmt (lagenunabhaengig), gleiche Geotags = ein Beleg, ab 3 Belegen.
  1 synthetisch      richtige Lage besteht; falsche Geotags werden verworfen; 20 Grad / x0,80 fallen weiter durch (auch allein ueber die Fernfotos);
                     die Auswahl der stimmigen Fernfotos haengt nicht von der Lage ab
  2 echte Fixture    tools/test_lage_gps_fern_fixture.json: 1122 (vereint, +8 Grad x1,089) besteht, die 5 Fernfotos werden verworfen; dieselbe Lage nach -22 Grad x0,83
                     (1122d) gedreht faellt durch; 1120 (gute Lage) besteht weiter MIT Fernfoto-Urteil (10 stimmige), um 20 Grad gedreht faellt 1120 durch
  3 Anker-Kasten     sfm_lod2_ausrichten.gps_fit_streuung/gps_anker_kasten: Kasten aus der Bootstrap-Streuung, begrenzt [2 Grad/3 %, 8 Grad/8 %]; Verdrahtung
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_lage_gps_fern.py"""
import os, sys, math, json, io, contextlib
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import lage_gps_pruefen as LG
import sfm_lod2_ausrichten as SA

FEHLER = []
def pruef(bed, text):
    if not bed: FEHLER.append(text); print("FEHLER:", text)

def dreh(X, grad, k=1.0):
    a = math.radians(grad); R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]); return k * np.asarray(X, float) @ R.T

def urteil(namen, MU, G):
    with contextlib.redirect_stdout(io.StringIO()): return LG.urteil(list(namen), np.asarray(MU, float), np.asarray(G, float))

# 1 synthetisch: 80 Torfotos (10-40 m), 6 echte Fernfotos (150-400 m), 4x eingefrorener Geotag, 1 falsch registrierte Kamera
rng = np.random.default_rng(5); n = 80; w = rng.uniform(0, 2 * np.pi, n); r = rng.uniform(10, 40, n)
W = np.c_[r * np.cos(w), r * np.sin(w)]
wf = rng.uniform(0, 2 * np.pi, 6); rf = rng.uniform(150, 400, 6); Wf = np.c_[rf * np.cos(wf), rf * np.sin(wf)]
Wst = np.tile([[50.0, 30.0]], (4, 1)); Gst = np.tile([[230.0, 110.0]], (4, 1))                 # Modell 58 m, Geotag 255 m (gleicher Fix)
Wod = np.array([[-40000.0, 60000.0]]); God = np.array([[900.0, -1700.0]])
MU = np.vstack([W, Wf, Wst, Wod]); G = np.vstack([W + rng.normal(0, 3, (n, 2)), Wf + rng.normal(0, 6, (6, 2)), Gst, God])
nm = [f"nah{i}" for i in range(n)] + [f"fern{i}" for i in range(6)] + [f"stale{i}" for i in range(4)] + ["od"]
rc, e = urteil(nm, MU, G)
pruef(rc == 0, f"synthetisch: richtige Lage muss bestehen, rc {rc} {e.get('warnungen')}")
fe = e.get("fernfotos") or {}
pruef(fe.get("bewertet") and fe.get("n_unabhaengig") == 6, f"synthetisch: 6 echte Fernfotos muessen bewertet werden: {fe.get('n_unabhaengig')}")
pruef(sorted(v["foto"] for v in fe.get("verworfen", [])) == sorted(nm[-5:]), f"synthetisch: verworfen muessen die 4 eingefrorenen + od sein: {[v['foto'] for v in fe.get('verworfen', [])]}")
pruef(abs(fe.get("entfernung_gps_durch_modell", 0) - 1) < 0.05, f"synthetisch: Entfernungsverhaeltnis {fe.get('entfernung_gps_durch_modell')}")
for g_, k_, was in ((20, 1.0, "Drehung 20 Grad"), (0, 0.80, "Massstab 0,80"), (-22, 0.83, "-22 Grad x0,83 (1122d)")):
    rc2, e2 = urteil(nm, dreh(MU, g_, k_), G)
    pruef(rc2 == 3, f"synthetisch: {was} muss durchfallen, rc {rc2}")
    pruef(any("Fernfotos" in x for x in e2.get("warnungen", [])), f"synthetisch: {was} muss auch ueber die stimmigen Fernfotos auffallen: {e2.get('warnungen')}")
    pruef(sorted(v["foto"] for v in e2["fernfotos"]["verworfen"]) == sorted(nm[-5:]), f"synthetisch: Auswahl der Fernfotos haengt von der Lage ab ({was})")
# nur falsche Fernfotos -> kein Fernfoto-Urteil, keine Warnung (vorher: x4,45 -> rc 3)
sel = [i for i in range(len(nm)) if not nm[i].startswith("fern")]
rc3, e3 = urteil([nm[i] for i in sel], MU[sel], G[sel])
pruef(rc3 == 0 and e3["fernfotos"]["bewertet"] is False, f"synthetisch: nur falsche Fernfotos duerfen nicht urteilen: rc {rc3} {e3['fernfotos']}")
# Fernfotos ueber einen gleichen Fix = EIN Beleg: 3 Fotos, gleicher (richtiger) Geotag -> unter 3 Belegen kein Urteil
sel2 = list(range(n)) + [n]
MU4 = np.vstack([MU[sel2], MU[[n, n]]]); G4 = np.vstack([G[sel2], G[[n, n]]])
rc4, e4 = urteil([f"x{i}" for i in range(len(MU4))], MU4, G4)
pruef(e4["fernfotos"]["n_stimmig"] == 3 and e4["fernfotos"]["n_unabhaengig"] == 1 and not e4["fernfotos"]["bewertet"], f"synthetisch: gleicher Geotag muss als ein Beleg zaehlen: {e4['fernfotos']}")

# 2 echte Fixture
F = json.load(open(os.path.join(T, "test_lage_gps_fern_fixture.json")))
a = F["schwabentor-1122"]; MUa, Ga = np.array(a["kamera_utm"]), np.array(a["gps_utm"])
rc, e = urteil(a["namen"], MUa, Ga)
pruef(rc == 0, f"1122: vereintes Modell (+8 Grad x1,089) muss bestehen, rc {rc} {e.get('warnungen')}")
vw = sorted(v["foto"] for v in e["fernfotos"]["verworfen"])
pruef(vw == sorted(["eigen__od_08"] + [f"eigen__IMG_20261106_1130{x}" for x in ("15", "17", "18", "19")]), f"1122: verworfene Fernfotos {vw}")
pruef(abs(e["gps_fit"]["drehung_grad"] - 8.0) < 0.5 and abs(e["gps_fit"]["massstab"] - 1.089) < 0.01, f"1122: GPS-Fit {e['gps_fit']}")
rc, e = urteil(a["namen"], dreh(MUa, 30.0, 1.089 / 0.83), Ga)
pruef(rc == 3 and abs(e["gps_fit"]["drehung_grad"] + 22) < 1, f"1122: Lage -22 Grad x0,83 (1122d) muss FALSCH bleiben, rc {rc} {e.get('gps_fit')}")
b = F["schwabentor-1120"]; MUb, Gb = np.array(b["kamera_utm"]), np.array(b["gps_utm"])
rc, e = urteil(b["namen"], MUb, Gb)
pruef(rc == 0 and e["fernfotos"]["bewertet"] and e["fernfotos"]["n_unabhaengig"] >= 8, f"1120: gute Lage muss bestehen und Fernfotos bewerten, rc {rc} {e.get('fernfotos', {}).get('n_unabhaengig')}")
pruef(abs(e["fernfotos"]["entfernung_gps_durch_modell"] - 1) < 0.05, f"1120: Entfernungsverhaeltnis {e['fernfotos'].get('entfernung_gps_durch_modell')}")
rc, e = urteil(b["namen"], dreh(MUb, 20.0), Gb)
pruef(rc == 3 and any("Fernfotos" in x for x in e["warnungen"]), f"1120 um 20 Grad gedreht muss (auch ueber Fernfotos) durchfallen, rc {rc} {e.get('warnungen')}")

# 3 Anker-Kasten aus der Bootstrap-Streuung
pruef(SA.gps_anker_kasten(None) == (SA.GPS_ANKER_DREH, SA.GPS_ANKER_MASS), "Kasten ohne Streuung = alte feste Werte")
pruef(SA.gps_anker_kasten((0.1, 0.002)) == (SA.GPS_ANKER_DREH_MIN, SA.GPS_ANKER_MASS_MIN), "Kasten: Untergrenze")
pruef(SA.gps_anker_kasten((5.0, 0.05)) == (SA.GPS_ANKER_DREH, SA.GPS_ANKER_MASS), "Kasten: Obergrenze")
pruef(SA.gps_anker_kasten((float("nan"), 0.01)) == (SA.GPS_ANKER_DREH, SA.GPS_ANKER_MASS), "Kasten: NaN -> feste Werte")
Cxy = dreh(MUa, 37.0, 0.11) + [3.0, -1.0]                                                       # beliebiges SfM-System der 1122-Kameras
nahm = np.hypot(*MUa.T) < 500
wk = nahm & (np.linalg.norm(Ga - MUa, axis=1) < 10)                                              # Kameras, deren Geotag stimmt
st = SA.gps_fit_streuung(Cxy[nahm], Ga[nahm], wk[nahm])
pruef(st is not None and 0.1 < st[0] < 1.5 and 0.003 < st[1] < 0.03, f"1122: Bootstrap-Streuung des GPS-Fits {st} (erwartet ~0,4 Grad / ~1,3 % wie das GPS-Tor)")
kd, km = SA.gps_anker_kasten(st)
pruef(kd < SA.GPS_ANKER_DREH and km < SA.GPS_ANKER_MASS, f"1122: Kasten aus der Streuung ({kd:.1f} Grad, {100 * km:.1f} %) muss enger sein als der feste (8 Grad / 8 %), an dessen Rand LoD2 drueckte")
q = open(os.path.join(T, "sfm_lod2_ausrichten.py")).read()
pruef("gps_fit_streuung(Cxy, Mxy, w_)" in q and 'dreh=GPS_ANKER["kasten_drehung_grad"]' in q, "sfm_lod2_ausrichten: Kasten aus der Streuung nicht verdrahtet")
pruef("if rec is None or pycolmap is None:" in q, "sfm_lod2_ausrichten: sparse_modell-Schreiben ohne COLMAP-Modell nicht abgefangen")
pruef(os.path.isfile(os.path.join(T, "sparse_modell_schreiben.py")), "tools/sparse_modell_schreiben.py fehlt")
import sparse_modell_schreiben as SMS
from scipy.spatial.transform import Rotation as Rot
s0, R0, t0 = 0.137, Rot.from_rotvec([0.3, -1.1, 0.7]).as_matrix(), np.array([1.0, -2.0, 3.0]); Xm = rng.normal(0, 10, (5, 3)); Xs = s0 * Xm @ R0.T + t0
sk, Rk, tk = SMS.sim_aus_ausrichtung(dict(s=s0, rvec=Rot.from_matrix(R0).as_rotvec().tolist(), t=t0.tolist()))
pruef(np.allclose(sk * Xs @ Rk.T + tk, Xm, atol=1e-9), "sparse_modell_schreiben: Umkehrabbildung SfM -> Modell falsch")

print("LAGE-GPS-FERN-TEST:", "bestanden" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
