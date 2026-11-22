#!/usr/bin/env python3
"""Fester Test (Sekunden, ohne GPU, ohne echte Daten) fuer den 22.11.2026-Fix nach dem Nulllauf schwabentor-1122 (Lage-Tore: 20 Grad gegen GPS, Teil 1 mit 130 Bildern fehlte).
  1 seiten_gps_vereinen.b_nach_a   zwei Seitenmodelle in eigenen Systemen (gedreht, gekippt, anderer Massstab), Foto-GPS 4 m / 2,5 m Rauschen, 15 % / 7 % falsche Geotags:
                                   B wird auf A gelegt (Standorte < 3 m, Fehler <= 3 Bootstrap-Streuungen); schlechtes GPS auf B (6 m) -> abgelehnt; zu wenig GPS -> zu_wenig;
                                   zufaellige Geotags -> abgelehnt (kein Lagebeleg)
  2 seiten_gps_vereinen.gps_roh     EXIF-GPS aus einer JPEG-Datei (wie Handyfotos) wird gelesen; Bild ohne GPS fehlt
  3 sfm_lod2_ausrichten.gps_dreh_massstab   Drehung/Massstab einer Loesung gegen das GPS (Messgroesse des GPS-Tors): 20 Grad gedreht -> 20 (verworfen), 3 Grad -> bestanden,
                                   20 % falsche Geotags aendern das Urteil nicht
  4 Verdrahtung                    sfm_seiten_modelle ruft seiten_gps_vereinen + gps_seiten_pruefen; sfm_lod2_ausrichten nutzt gps_dreh_massstab im GPS-Veto mit den Torgrenzen
Python: /media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_gps_vereinen.py"""
import os, sys, math, tempfile, shutil
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import seiten_gps_vereinen as SG

rng = np.random.default_rng(5); FEHLER = []


def pruef(bed, text):
    if not bed: FEHLER.append(text); print("FEHLER:", text)


def drehung(achse, grad):
    a = np.asarray(achse, float); a /= np.linalg.norm(a); w = math.radians(grad); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(w) * K + (1 - math.cos(w)) * K @ K


def sim(s, R, t):
    M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = t; return M


def kranz(n, az0, az1, r0, r1, pre):
    az = np.radians(rng.uniform(az0, az1, n)); r = rng.uniform(r0, r1, n)
    return [f"{pre}{i:03d}.jpg" for i in range(n)], np.c_[r * np.sin(az), r * np.cos(az), np.full(n, 1.6) + rng.normal(0, 0.15, n)]     # Welt = ENU (ost, nord, hoch), Kameras 1,6 m


nA, WA = kranz(80, 320, 400, 15, 45, "a")          # Nordseite (Schwabentor: Teil 0 GPS 355 Grad)
nB, WB = kranz(30, 110, 175, 12, 35, "b")          # Suedostseite (Teil 1 GPS 146 Grad; dort 24 von 26 GPS stimmig, Rest Median 1,8 m)
GA = sim(0.13, drehung([0, 0, 1], -75) @ drehung([1, 0, 0], 4), [3.0, -2.0, 0.5]); GB = sim(0.41, drehung([0.3, 1, 0.2], 110), [-7.0, 1.0, 4.0])   # Welt -> Modell A/B
auf = lambda M, X: np.asarray(X) @ M[:3, :3].T + M[:3, 3]
CA, CB = auf(GA, WA), auf(GB, WB); obA = GA[:3, :3] @ [0, 0, 1]; obA /= np.linalg.norm(obA); obB = GB[:3, :3] @ [0, 0, 1]; obB /= np.linalg.norm(obB)
M_wahr = GA @ np.linalg.inv(GB)                    # B-Modell -> Welt -> A-Modell


def gps(namen, W, falsch=0.15, sigma=4.0):
    G = {}
    for n, w in zip(namen, W):
        G[n] = w[:2] + rng.normal(0, sigma, 2) if rng.random() > falsch else rng.uniform(-60, 60, 2)
    return G


def abweichung(M):
    """Lage der B-Kameras nach M gegen die Wahrheit (m, im Weltmassstab), Drehungsfehler (Grad), Massstabsfehler (relativ)."""
    d = np.linalg.norm(auf(M, CB) - auf(M_wahr, CB), axis=1) / 0.13
    L = M[:3, :3]; Lw = M_wahr[:3, :3]; s, sw = np.cbrt(np.linalg.det(L)), np.cbrt(np.linalg.det(Lw)); Rd = (L / s) @ (Lw / sw).T
    return float(np.median(d)), float(np.degrees(np.arccos(np.clip((np.trace(Rd) - 1) / 2, -1, 1)))), float(abs(s / sw - 1))


# ---------- 1 b_nach_a
G = gps(nA, WA); G.update(gps(nB, WB, falsch=0.07, sigma=2.5))
e = SG.b_nach_a((nA, CA, obA), (nB, CB, obB), G)
pruef(e["ok"] and "B_nach_A" in e, f"GPS-Vereinen abgelehnt: {e.get('urteil')}")
if "B_nach_A" in e:
    d, w, s = abweichung(np.array(e["B_nach_A"])); print(f"  B auf A: Standorte {d:.2f} m, Drehung {w:.2f} Grad, Massstab {100 * s:.1f} % neben der Wahrheit; Bootstrap {e['pruefung']}")
    # Genauigkeit = die des Handy-GPS (hier 30 Kameras, 2,5 m Rauschen); Pflicht: Standorte < 3 m und der Bootstrap meldet den Fehler ehrlich (hoechstens 3 Streuungen)
    pruef(d < 3.0 and w < max(3 * e["pruefung"]["dreh_sd_grad"], 2.0) and s < max(3 * e["pruefung"]["mass_sd_rel"], 0.03), f"GPS-Vereinen ungenau oder Bootstrap zu optimistisch: {d:.2f} m / {w:.2f} Grad / {100 * s:.1f} % gegen {e['pruefung']}")
    pruef(SG.MAX_DREH_SD >= e["pruefung"]["dreh_sd_grad"] > 0 and e["pruefung"]["mass_sd_rel"] > 0, f"Bootstrap fehlt: {e['pruefung']}")
    pruef(e["rahmen_b"]["inlier"] >= 0.75 * len(nB) and e["rahmen_a"]["ausreisser"] < 0.3, f"falsche Geotags nicht abgetrennt: {e['rahmen_a']}, {e['rahmen_b']}")
G2 = dict(G); G2.update(gps(nB, WB, falsch=0.15, sigma=6.0))                          # schlechtes Handy-GPS auf Seite B: Bootstrap muss das ehrlich melden -> abgelehnt
e2 = SG.b_nach_a((nA, CA, obA), (nB, CB, obB), G2)
pruef(not e2["ok"] and "B_nach_A" in e2 and "nur auf" in e2["urteil"], f"ungenaues GPS als Lagebeleg angenommen: {e2.get('urteil')} {e2.get('pruefung')}")
if "B_nach_A" in e2:
    d2, w2, s2 = abweichung(np.array(e2["B_nach_A"])); pruef(w2 < 3 * max(e2["pruefung"]["dreh_sd_grad"], 0.5) and s2 < 3 * e2["pruefung"]["mass_sd_rel"], f"Bootstrap unterschaetzt den Fehler: {w2:.1f} Grad / {100 * s2:.0f} % gegen {e2['pruefung']}")
G3 = dict(G); [G3.pop(n) for n in nB[8:]]
e3 = SG.b_nach_a((nA, CA, obA), (nB, CB, obB), G3); pruef(not e3["ok"] and e3.get("zu_wenig") and "B_nach_A" not in e3, f"8 GPS-Kameras in B angenommen: {e3.get('urteil')}")
G4 = dict(G); G4.update({n: rng.uniform(-40, 40, 2) for n in nB})
e4 = SG.b_nach_a((nA, CA, obA), (nB, CB, obB), G4); pruef(not e4["ok"] and "B_nach_A" not in e4, f"zufaellige Geotags als Lagebeleg angenommen: {e4.get('urteil')}")
print(f"ok 1: B ueber das Foto-GPS auf A gelegt; ungenaues GPS ({e2['urteil'][:45]}...), zu wenig GPS ({e3['urteil'][:40]}...) und zufaellige Geotags ({e4['urteil'][:50]}...) abgelehnt")

# ---------- 2 gps_roh (EXIF wie Handyfotos)
S = tempfile.mkdtemp(prefix="test_gps_vereinen_")
try:
    from PIL import Image
    ex = Image.Exif(); ex[0x8825] = {1: "N", 2: (47.0, 59.0, 34.5), 3: "E", 4: (7.0, 51.0, 14.5)}
    Image.new("RGB", (8, 8)).save(os.path.join(S, "mit.jpg"), exif=ex); Image.new("RGB", (8, 8)).save(os.path.join(S, "ohne.jpg"))
    r = SG.gps_roh(S, ["mit.jpg", "ohne.jpg", "fehlt.jpg"])
    pruef(set(r) == {"mit.jpg"} and abs(r["mit.jpg"][0] - (47 + 59 / 60 + 34.5 / 3600)) < 1e-6 and abs(r["mit.jpg"][1] - (7 + 51 / 60 + 14.5 / 3600)) < 1e-6, f"EXIF-GPS falsch gelesen: {r}")
    E = SG.enu({"x": (47.0 + 10 / 110540.0, 7.0)}, 47.0, 7.0); pruef(np.allclose(E["x"], [0, 10], atol=1e-6), f"ENU falsch: {E}")
    print("ok 2: EXIF-GPS gelesen (Bild ohne GPS fehlt), ENU in Metern")
finally: shutil.rmtree(S, ignore_errors=True)

# ---------- 3 gps_dreh_massstab (GPS-Veto der Ausrichtung)
import sfm_lod2_ausrichten as SA
Gp = rng.uniform(-40, 40, (60, 2)); rot = lambda g: np.array([[math.cos(math.radians(g)), -math.sin(math.radians(g))], [math.sin(math.radians(g)), math.cos(math.radians(g))]])
X20 = (Gp - 3.0) @ rot(-20).T + rng.normal(0, 3, (60, 2)); X3 = Gp @ rot(3).T * 1.05 + rng.normal(0, 3, (60, 2))
d20, s20 = SA.gps_dreh_massstab(X20, Gp); d3, s3 = SA.gps_dreh_massstab(X3, Gp)
pruef(abs(d20 - 20) < 2 and abs(d20) > SA.GPS_MAX_DREH, f"20-Grad-Loesung: {d20:.1f} Grad")
pruef(abs(d3 + 3) < 2 and abs(s3 * 1.05 - 1) < 0.05 and abs(d3) <= SA.GPS_MAX_DREH and abs(s3 - 1) <= SA.GPS_MAX_MASS, f"3-Grad-Loesung: {d3:.1f} Grad x{s3:.3f}")
Gf = Gp.copy(); Gf[:12] = rng.uniform(-200, 200, (12, 2)); d20f, _ = SA.gps_dreh_massstab(X20, Gf); pruef(abs(d20f - 20) < 3, f"falsche Geotags kippen das Urteil: {d20f:.1f} Grad")
pruef(SA.gps_dreh_massstab(X3[:5], Gp[:5]) is None, "5 Kameras: kein Urteil erwartet")
print(f"ok 3: GPS-Veto misst Drehung {d20:.1f} Grad (verworfen) / {d3:.1f} Grad x{s3:.2f} (bestanden), robust gegen 20 % falsche Geotags")

# ---------- 4 Verdrahtung
q = lambda n: open(os.path.join(T, n)).read()
pruef("seiten_gps_vereinen.py" in q("sfm_seiten_modelle.py") and "gps_seiten_pruefen.py" in q("sfm_seiten_modelle.py") and "RCPARK_SEITEN_GPS" in q("sfm_seiten_modelle.py"), "sfm_seiten_modelle ruft den GPS-Rueckfall nicht")
pruef("gps_dreh_massstab(zu_modell(" in q("sfm_lod2_ausrichten.py") and "GPS_MAX_DREH" in q("sfm_lod2_ausrichten.py"), "sfm_lod2_ausrichten: GPS-Veto ohne Drehung/Massstab")
pruef("max_dreh\", type=float, default=15.0" in q("lage_gps_pruefen.py") and "max_skala\", type=float, default=0.15" in q("lage_gps_pruefen.py") and SA.GPS_MAX_DREH == 15.0 and SA.GPS_MAX_MASS == 0.15,
      "Grenzen des Ausrichtungs-Vetos weichen vom GPS-Tor ab")
print("ok 4: Verdrahtung (Seitenmodelle -> GPS-Rueckfall + GPS-Seiten-Tor; Ausrichtung -> Drehungs-/Massstabs-Veto mit den Grenzen des GPS-Tors)")
if FEHLER: print(f"FEHLER: {len(FEHLER)} Pruefung(en) nicht bestanden"); sys.exit(1)
print("ALLE PRUEFUNGEN BESTANDEN")
