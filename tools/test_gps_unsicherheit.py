#!/usr/bin/env python3
"""Fester Test (Sekunden, CPU) fuer tools/gps_unsicherheit.py und seine Verwendung im GPS-Tor (lage_gps_pruefen) und in der Ausrichtung (sfm_lod2_ausrichten).
Befund 22.11.2026 (schwabentor-1122): Nah-GPS EINER Sitzung systematisch +9,4 Grad / x0,867 verzerrt; Bootstrap sagte +-0,4 Grad -> Anker-Kasten sperrte die falsche Lage.
  1 synthetisch: 150 Nahfotos einer Sitzung, GPS mit Muster 'zum Turm gezogen' (3 m) -> Fit ~ x0,85 daneben; Bootstrap << Fehler, ehrlich >= Fehler/2; kein Anker.
    Dazu 10 Fernfotos (200-300 m) einer anderen Gruppe -> Unsicherheit ~1 Grad, Anker moeglich. Ohne Zeiten = eine Gruppe (vorsichtig).
  2 echte Fixture tools/test_gps_unsicherheit_fixture.json (EXIF-Zeiten zu tools/test_lage_gps_fern_fixture.json): 1122 eine Sitzung -> legt Lage NICHT fest;
    1120 mit Fernfotos -> legt fest (< 2,5 Grad); 1120 nur Nahfotos: der gemessene Fehler +9,4 Grad / x0,867 liegt innerhalb 1,5 ehrlicher Sigma.
  3 GPS-Tor mit Zeiten: 1122 geschrieben besteht, -22 Grad x0,83 faellt weiter; 1120 faellt bei 20 Grad weiter (Fernfotos); 1120 nur nah um -20 Grad faellt.
  4 Martinstor-Fall (16 Geotags, Objektstandort statt Kamera) aendert sich nicht: gps_anker_aktiv bleibt aus; Ausrichtung verdrahtet (ehrlich, Proben, Zwischenstand).
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_gps_unsicherheit.py"""
import os, sys, math, json, io, contextlib
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import gps_unsicherheit as GU
import lage_gps_pruefen as LG

FEHLER = []
def pruef(bed, text):
    if not bed: FEHLER.append(text); print("FEHLER:", text)

def dreh(X, g, k=1.0):
    a = math.radians(g); R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]); return k * np.asarray(X, float) @ R.T

# 1 synthetisch
rng = np.random.default_rng(2); n = 150; w = rng.uniform(0, 2 * np.pi, n); r = rng.uniform(10, 25, n)
M = np.c_[r * np.cos(w), r * np.sin(w)]                                                      # wahre Standorte
G = M - 3.0 * M / np.linalg.norm(M, axis=1, keepdims=True) + rng.normal(0, 2.0, (n, 2))      # zum Turm gezogen (Abschattung), Zufall 2 m
z = [1.7e9 + 5 * i for i in range(n)]                                                         # eine Sitzung, 12 min
s_, R_ = GU._fit2d(M, G); fehler_mass = abs(s_ - 1)
sy = GU.systematik(G, GU.gruppen(G, z), M=M)
boot = []
for _ in range(200):
    i = rng.choice(n, n); boot.append(GU._fit2d(M[i], G[i])[0])
sd_boot = float(np.std(boot))
print(f"  synthetisch: Massstabsfehler {fehler_mass:.3f}, Bootstrap-Sigma {sd_boot:.4f}, ehrlich systematisch {sy['mass_sd_rel']:.3f}")
pruef(sd_boot < fehler_mass / 4, f"synthetisch: Bootstrap {sd_boot:.4f} sollte den Fehler {fehler_mass:.3f} NICHT abdecken (Nachstellung)")
pruef(sy["mass_sd_rel"] >= fehler_mass / 2, f"synthetisch: ehrliche Sigma {sy['mass_sd_rel']:.3f} muss den Sitzungsfehler {fehler_mass:.3f} abdecken (>= halb)")
e = GU.ehrlich(G, np.ones(n, bool), z, M=M, sd_dreh_zufall=0.3, sd_mass_zufall=sd_boot)
pruef(e["anker"] is None, f"synthetisch: eine Nah-Sitzung darf nicht ankern: {e['text']}")
wf = rng.uniform(0, 2 * np.pi, 10); rf = rng.uniform(200, 300, 10); Mf = np.c_[rf * np.cos(wf), rf * np.sin(wf)]; Gf = Mf + rng.normal(0, 3.0, (10, 2))
Ma, Ga = np.vstack([M, Mf]), np.vstack([G, Gf]); za = z + [1.7e9 + 9000 + 60 * i for i in range(10)]
e2 = GU.ehrlich(Ga, np.ones(len(Ga), bool), za, M=Ma, sd_dreh_zufall=0.3, sd_mass_zufall=0.01)
pruef(e2["anker"] is not None and e2["dreh_sd_grad"] < 2.5, f"synthetisch: mit Fernfotos muss das GPS ankern: {e2['text']}")
e3 = GU.ehrlich(G, np.ones(n, bool), None, M=M)
pruef(e3["systematik"]["n_gruppen"] == 1, "ohne Zeiten muss alles EINE Gruppe sein")
pruef(GU.sitzungen([0, 100, 5000, None, 5100]) == [0, 0, 1, -1, 1], f"Sitzungen: {GU.sitzungen([0, 100, 5000, None, 5100])}")

# 2 echte Fixture
F = json.load(open(os.path.join(T, "test_lage_gps_fern_fixture.json"))); Z = json.load(open(os.path.join(T, "test_gps_unsicherheit_fixture.json")))
def urteil(nm, MU, G_, z_):
    with contextlib.redirect_stdout(io.StringIO()): return LG.urteil(list(nm), np.asarray(MU, float), np.asarray(G_, float), zeiten=z_)
erg = {}
for k in ("schwabentor-1122", "schwabentor-1120"):
    a = F[k]; rc, e_ = urteil(a["namen"], a["kamera_utm"], a["gps_utm"], Z["zeiten"][k]); erg[k] = (rc, e_)
g22, g20 = erg["schwabentor-1122"][1]["gps_fit"], erg["schwabentor-1120"][1]["gps_fit"]
print(f"  1122: +-{g22['sd_drehung_grad']:.1f} Grad / +-{100 * g22['sd_massstab']:.0f} %, festgelegt {g22['lage_festgelegt']}; 1120: +-{g20['sd_drehung_grad']:.1f} Grad, festgelegt {g20['lage_festgelegt']}")
pruef(not g22["lage_festgelegt"] and 6 < g22["sd_drehung_grad"] < 25, f"1122 (eine Sitzung, nur nah) darf die Lage nicht festlegen: {g22['sd_drehung_grad']}")
pruef(g20["lage_festgelegt"] and g20["sd_drehung_grad"] < 2.5, f"1120 (Fernfotos) muss die Lage festlegen: {g20['sd_drehung_grad']}")
a = F["schwabentor-1120"]; G20 = np.array(a["gps_utm"]); nah = np.hypot(*G20.T) < 100
sel = lambda X: [x for x, b in zip(X, nah) if b]
rcn, en = urteil(sel(a["namen"]), np.array(a["kamera_utm"])[nah], G20[nah], sel(Z["zeiten"]["schwabentor-1120"])); gn = en["gps_fit"]
print(f"  1120 nur nah: Fit {gn['drehung_grad']:+.1f} Grad x{gn['massstab']:.3f}, ehrlich +-{gn['sd_drehung_grad']:.1f} Grad / +-{100 * gn['sd_massstab']:.0f} %, Bootstrap 90 % {gn['drehung_90']}")
pruef(abs(gn["drehung_grad"]) <= 1.5 * gn["sd_drehung_grad"] and abs(gn["massstab"] - 1) <= 1.5 * gn["sd_massstab"], f"1120 nur nah: gemessener Sitzungsfehler muss in 1,5 ehrlichen Sigma liegen: {gn}")
pruef(abs(gn["drehung_grad"]) > 5 * (gn["drehung_90"][1] - gn["drehung_90"][0]) / (2 * GU.Z90), "1120 nur nah: Bootstrap allein haette den Fehler ausgeschlossen (Nachstellung des Befunds)")

# 3 Tor mit Zeiten
a = F["schwabentor-1122"]; z22 = Z["zeiten"]["schwabentor-1122"]
pruef(erg["schwabentor-1122"][0] == 0, f"1122 geschrieben muss bestehen: {erg['schwabentor-1122'][1].get('warnungen')}")
rc, e_ = urteil(a["namen"], dreh(a["kamera_utm"], -22, 0.83), a["gps_utm"], z22); pruef(rc == 3, f"1122 -22 Grad x0,83 muss fallen: {e_.get('warnungen')}")
a = F["schwabentor-1120"]; z20 = Z["zeiten"]["schwabentor-1120"]
rc, e_ = urteil(a["namen"], dreh(a["kamera_utm"], 20), a["gps_utm"], z20); pruef(rc == 3, "1120 um 20 Grad muss fallen (Fernfotos)")
rc, e_ = urteil(sel(a["namen"]), dreh(np.array(a["kamera_utm"])[nah], -20), G20[nah], sel(z20)); pruef(rc == 3, f"1120 nur nah um -20 Grad muss fallen: {e_.get('warnungen')}")
pruef(rcn == 0, f"1120 nur nah (richtige Lage) muss bestehen: {en.get('warnungen')}")

# 4 Martinstor unveraendert + Verdrahtung
import sfm_lod2_ausrichten as SA
pruef(not SA.gps_anker_aktiv(16, 3.0), "Martinstor (16 Geotags): kein GPS-Anker")
q = open(os.path.join(T, "sfm_lod2_ausrichten.py")).read()
pruef("GU.ehrlich(" in q and "GPS_EHRLICH[\"anker\"] is None" in q and "LP.entscheiden(" in q and "_zw_sichern()" in q, "sfm_lod2_ausrichten: ehrliche Unsicherheit/Proben/Zwischenstand nicht verdrahtet")
pruef("if GPS_PRUEF is not None:\n            # 22.11.2026 EHRLICHE" in q, "ehrliche Unsicherheit darf nur mit GPS-Fit (GPS_PRUEF) rechnen - Martinstor ohne GPS bleibt unveraendert")
pruef("GU.gps_fit(" in open(os.path.join(T, "lage_gps_pruefen.py")).read() and "systematik(" in open(os.path.join(T, "gps_unsicherheit.py")).read().split("def gps_fit(")[1] and "GU.systematik(" in open(os.path.join(T, "seiten_gps_vereinen.py")).read(), "Tor/Seiten-GPS muessen dasselbe Mass nehmen")
qg = open(os.path.join(T, "gesamtkette.py")).read()
import lage_proben as _LPR                                                   # 22.11.2026: Regel als Funktion lage_proben.lage_bestanden/tor_rc (Kette + Lage-Pruefstand)
pruef('__import__("lage_proben").lage_bestanden' in qg and "_LPR.tor_rc(" in qg and not _LPR.lage_bestanden(dict(gps=0, grundriss=0, lage_proben=3))
      and _LPR.lage_bestanden(dict(gps=0, grundriss=0, lage_proben=None)) and _LPR.tor_rc(dict(lage_proben=dict(ergebnis="mehrdeutig")))[0] == 3,
      "gesamtkette: Lageproben 'keine/mehrdeutig' muessen die Lage-Tore verwerfen")

print("FEHLER:", len(FEHLER)) if FEHLER else print("OK test_gps_unsicherheit")
sys.exit(1 if FEHLER else 0)
