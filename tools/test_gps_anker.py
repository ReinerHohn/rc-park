#!/usr/bin/env python3
"""Fester Test (Sekunden, ohne GPU) fuer den GPS-ANKER der LoD2-Ausrichtung (22.11.2026, Nulllauf kette-schwabentor-null-1122d: vereinte Seiten 0+1,
GPS-Fit der Kameras gut, aber der LoD2-Feinfit drehte die Lage 22 Grad weg und schrumpfte den Massstab auf 0,83 -> GPS-Veto verwarf die einzige Loesung).
  1 gps_anker_aktiv     nur bei starkem Foto-GPS (>= 40 Kameras, Rest < 8 m, nicht gespiegelt); Martinstor (15-17 Geotags) -> aus = bisheriges Verhalten;
                        AUSR_GPS_ANKER=0 schaltet ab
  2 gps_anker_grenzen   Kasten um den GPS-Fit (Drehung, Kippung, Massstab, Versatz; Hoehe frei) - synthetisch: JEDE Ecke des Kastens besteht das GPS-Veto
                        (gps_dreh_massstab mit den Grenzen des GPS-Tors, Kamerarest < 12 m)
  3 echte Fixture       tools/test_gps_anker_fixture.json (160 GPS-Kameras des Nulllaufs, geschriebene Lage): die geschriebene Lage faellt durchs Veto (-22 Grad x0,83,
                        Fehler nachgestellt); GPS-Fit wie in sfm_lod2_ausrichten -> Startlage + alle Kastenecken bestehen das Veto
  4 Verdrahtung         sfm_lod2_ausrichten rechnet den Anker-Feinfit mit den Grenzen und nimmt ihn als Loesung ins Veto
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_gps_anker.py (numpy/scipy; nackter python3 hat kein scipy)"""
import os, sys, math, json, itertools
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
os.environ.pop("AUSR_GPS_ANKER", None)
import sfm_lod2_ausrichten as SA
from scipy.spatial.transform import Rotation as Rot

FEHLER = []
def pruef(bed, text):
    if not bed: FEHLER.append(text); print("FEHLER:", text)

def zu_modell(p, X): return Rot.from_rotvec(p[1:4]).apply(X) / math.exp(p[0]) + p[4:7]      # wie sfm_lod2_ausrichten.main.zu_modell

def gpsfit(Cxy, Mxy):   # wie sfm_lod2_ausrichten._gpsfit (Mxy ~ k Rg Cxy + tg, getrimmt)
    w = np.ones(len(Mxy), bool)
    for _ in range(5):
        mc, cc = Mxy[w].mean(0), Cxy[w].mean(0); U, S, V = np.linalg.svd((Mxy[w] - mc).T @ (Cxy[w] - cc))
        Rg = U @ np.diag([1, np.sign(np.linalg.det(U @ V))]) @ V; k = S.sum() / ((Cxy[w] - cc) ** 2).sum(); tg = mc - k * Rg @ cc
        res = np.linalg.norm(k * Cxy @ Rg.T + tg - Mxy, axis=1); w = res < max(2.5 * np.median(res), 8)
    return k, Rg, tg, res, w

def veto(p, Cq, G):     # beide Stufen des GPS-Vetos in sfm_lod2_ausrichten
    M = zu_modell(p, Cq)[:, :2]; rest = float(np.median(np.linalg.norm(M - G, axis=1))); dm = SA.gps_dreh_massstab(M, G)
    return rest < 12 and dm is not None and abs(dm[0]) <= SA.GPS_MAX_DREH and abs(dm[1] - 1) <= SA.GPS_MAX_MASS, rest, dm

def kasten_pruefen(Cq, G, name):
    k, Rg, tg, res, w = gpsfit(Cq[:, :2], G)
    pruef(SA.gps_anker_aktiv(int(w.sum()), float(np.median(res[w])), np.linalg.det(Rg) > 0), f"{name}: GPS-Anker muesste aktiv sein ({w.sum()} Kameras, Rest {np.median(res[w]):.1f} m)")
    p0 = np.array([math.log(1 / k), 0, 0, math.atan2(Rg[1, 0], Rg[0, 0]), tg[0], tg[1], 0.0]); lo, hi = SA.gps_anker_grenzen(p0)
    ok0, r0, dm0 = veto(p0, Cq, G); pruef(ok0, f"{name}: GPS-Startlage besteht das Veto nicht (Rest {r0:.1f}, {dm0})")
    schlecht = []
    for ecke in itertools.product(*[(lo[i], hi[i]) for i in range(6)]):
        p = np.r_[ecke, p0[6]]; ok, r, dm = veto(p, Cq, G)
        if not ok: schlecht.append((np.round(p, 3).tolist(), round(r, 1), dm))
    pruef(not schlecht, f"{name}: {len(schlecht)} von 64 Kastenecken fallen durchs GPS-Veto, z. B. {schlecht[:1]}")
    pruef(np.isinf(lo[6]) and np.isinf(hi[6]), f"{name}: Hoehe muss frei bleiben (DGM1/Kamerahoehe, nicht GPS)")
    return p0, lo, hi

# 1 aktiv / Fallback
pruef(not SA.gps_anker_aktiv(16, 3.0), "Martinstor (16 Geotags) darf keinen GPS-Anker bekommen")
pruef(SA.gps_anker_aktiv(148, 4.5), "Schwabentor-Nulllauf (148 Kameras, 4,5 m) muss den GPS-Anker bekommen")
pruef(not SA.gps_anker_aktiv(148, 9.0), "Rest 9 m darf nicht ankern")
pruef(not SA.gps_anker_aktiv(148, 4.5, det_pos=False), "gespiegelter GPS-Fit darf nicht ankern")
pruef(not SA.gps_anker_aktiv(148, float("nan")), "Rest NaN darf nicht ankern")
os.environ["AUSR_GPS_ANKER"] = "0"; pruef(not SA.gps_anker_aktiv(148, 4.5), "AUSR_GPS_ANKER=0 muss abschalten"); os.environ.pop("AUSR_GPS_ANKER")

# 2 synthetisch: Kameras im Kranz um ein Tor, SfM-System gedreht/skaliert, GPS 4 m Rauschen, 10 % falsche Geotags
rng = np.random.default_rng(11); n = 150; wkl = rng.uniform(0, 2 * np.pi, n); rad = rng.uniform(10, 35, n)
Mw = np.c_[rad * np.cos(wkl), rad * np.sin(wkl), rng.normal(1.6, 0.3, n)]                    # wahre Kameras (m, Modellsystem)
s_w, th_w = 0.12, math.radians(171); Cq = Rot.from_rotvec([0, 0, -th_w]).apply(Mw - [3, -2, 0]) * s_w    # SfM-Lotsystem
G = Mw[:, :2] + rng.normal(0, 4.0 / math.sqrt(2), (n, 2)); f = rng.random(n) < 0.1; G[f] += rng.uniform(-60, 60, (f.sum(), 2))
p0, lo, hi = kasten_pruefen(Cq, G, "synthetisch")
pruef(abs(math.exp(p0[0]) / s_w - 1) < 0.05, f"synthetisch: GPS-Massstab {math.exp(p0[0]):.4f} statt {s_w}")
pruef(abs(((math.degrees(p0[3]) - 171 + 180) % 360) - 180) < 3, f"synthetisch: GPS-Drehung {math.degrees(p0[3]):.1f} statt 171")
# der Fehler des Nulllaufs: LoD2 zieht 22 Grad / Massstab 0,83 weg -> ohne Kasten Veto rot, im Kasten (Randwert) gruen
p_frei = p0.copy(); p_frei[3] -= math.radians(22); p_frei[0] -= math.log(0.83)
pruef(not veto(p_frei, Cq, G)[0], "synthetisch: 22 Grad / x0,83 neben GPS muss das Veto verfehlen (Nachstellung)")
p_kast = np.clip(p_frei, lo, hi); pruef(veto(p_kast, Cq, G)[0], "synthetisch: im Kasten geklemmte Lage muss das Veto bestehen")

# 3 echte Fixture des Nulllaufs
F = json.load(open(os.path.join(T, "test_gps_anker_fixture.json"))); Xm = np.array(F["kamera_modell"]); Gf = np.array(F["gps"])
ok_g, r_g, dm_g = veto(np.zeros(7), Xm, Gf)   # Identitaet = geschriebene Lage
pruef(not ok_g and dm_g is not None and dm_g[0] < -15 and dm_g[1] < 0.88, f"Fixture: geschriebene Lage muesste wie im Nulllauf durchfallen (-22 Grad x0,83), ist {dm_g}")
Cq_f = Rot.from_rotvec([0, 0, 1.0]).apply(Xm) * 0.1031                                       # beliebiges SfM-System (Massstab der geschriebenen Loesung)
kasten_pruefen(Cq_f, Gf, "Fixture")

# 4 Verdrahtung
q = open(os.path.join(T, "sfm_lod2_ausrichten.py")).read()
pruef("gps_anker_aktiv(" in q and "fein(_pa, Q, grenzen=_gr)" in q and "_anker_p.append" in q, "sfm_lod2_ausrichten: Anker-Feinfit nicht verdrahtet")
pruef("if grenzen is not None: lo, hi" in q, "fein() benutzt die Ankergrenzen nicht")
pruef("grenzen=_gr_wahl" in q, "Bootstrap der verankerten Loesung nicht im Kasten")

print("GPS-ANKER-TEST:", "bestanden" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
