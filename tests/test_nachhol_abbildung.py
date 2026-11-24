#!/usr/bin/env python3
"""test_nachhol_abbildung.py - Nachholen ohne Nutzen (24.11.2026, Kette schwabentor-null-1122zb: seiten_luecken 29,6 min = 19 % des Laufs, 167/326 registriert,
Abbildung SfM -> Modell Massstab 0,0017 statt 10,13 / Rest 20 m, weil EINE Altkamera ~60 000 SfM-Einheiten weg lag; alle 173 neuen Kameras auf einem Punkt im Turm,
21 'belegt', 0 sehen eine Wand -> seiten_wiederholung lief nicht, Kandidaten trotzdem als 'versucht' gesperrt). NUR CPU, Sekunden, synthetisch.
Prueft:
  (1) kameras_nachtragen.abbildung_robust: ein Fernausreisser kippt die alte Mittelwert-Abbildung (Nachweis), die robuste trifft s/R/t exakt; Tor ok;
      zufaellige Zuordnung -> abbildung_tor NICHT ok (dann rc 4, keine K-Datei);
  (2) kameras_nachtragen_tor.im_gebaeude: Punkt im Grundriss unter der Oberkante -> ja; davor, darueber (Hochblick) -> nein;
  (3) altbestand_sperren + pruefen: abgeleitete Kamera im Gebaeude gesperrt (.unplausibel), Buendelkamera im Gebaeude und abgeleitete draussen bleiben;
      neue belegte Kamera im Gebaeude -> gesperrt, nicht 'belegt';
  (4) seiten_luecken.kandidaten_versucht: Versuch ohne 'abbildung_geprueft' (vor dem Tor) zaehlt nicht, nach kandidaten_merken zaehlt er;
  (5) nachhol_zwischenspeicher: 'behalten' je Gruppe (Ordner der Quelle) - fremde Objekte verdraengen den grossen Eintrag nicht.
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tests/test_nachhol_abbildung.py   Exit 0 = alles bestanden."""
import os, sys, json, time
import numpy as np
R_ = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); T = os.path.join(R_, "tools"); sys.path.insert(0, T)
from pfade import temp_ordner
import cv2

fehler = 0
D = temp_ordner("nachhol_abb_")


def pruef(ok, text):
    global fehler
    print(("ok   " if ok else "FEHLER ") + text, flush=True); fehler += 0 if ok else 1


# ---------- (1) Abbildung ----------
import kameras_nachtragen as KN
rng = np.random.default_rng(0)
M = np.c_[rng.uniform(-40, 40, 300), rng.uniform(-30, 30, 300), rng.uniform(0, 10, 300)]          # Modellrahmen (m)
Rw = cv2.Rodrigues(np.array([0.3, -1.1, 0.7]))[0]; s_w, t_w = 0.0987, np.array([-1.5, 0.04, 0.76])
S = (s_w * (Rw @ M.T)).T + t_w                                                                           # SfM-Rahmen: X_sfm = s R X_modell + t
S[7] = [60000.0, -2000.0, 900.0]                                                                         # EIN Fernausreisser (1122zb: 59 747 Einheiten)
S[11:20] += rng.normal(0, 2.0, (9, 3))                                                                   # einige falsch registrierte Altkameras
s0, R0, t0 = KN.umeyama(S, M)
pruef(abs(s0 * s_w - 1) > 0.5, f"Nachweis: Mittelwert-Abbildung auf allen kippt (Massstab {s0:.4f} statt {1 / s_w:.4f})")
s, R, t, gut, rest = KN.abbildung_robust(S, M); ok_a, g_a = KN.abbildung_tor(gut, rest)
pruef(abs(s * s_w - 1) < 1e-6 and np.allclose(R, Rw.T, atol=1e-6) and not gut[7] and gut.sum() >= 280 and ok_a,
      f"robust: Massstab {s:.4f}, {gut.sum()}/{len(gut)} im Konsens, Rest Median {np.median(rest[gut]):.4f} m, Ausreisser 7 draussen, Tor ok")
Sx = S[rng.permutation(len(S))]                                                                          # falsche Zuordnung (anderer Rahmen / andere Bilder)
s2, R2, t2, gut2, rest2 = KN.abbildung_robust(Sx, M); ok2, g2 = KN.abbildung_tor(gut2, rest2)
pruef(not ok2 and g2, f"zufaellige Zuordnung -> Tor NICHT ok ({g2})")
src = open(os.path.join(T, "kameras_nachtragen.py")).read()
pruef("return 4" in src and src.index("abbildung_tor(gut, rest)") < src.index("for im, R, C, k in neu:"), "kameras_nachtragen: Tor VOR dem Schreiben der K-Dateien, rc 4")

# ---------- (2) im Gebaeude ----------
import kameras_nachtragen_tor as KT
FF = [dict(n=[0, -1], d=[1, 0], o=[0, 0], u=[0, 10], z=[0, 20]), dict(n=[1, 0], d=[0, 1], o=[10, 0], u=[0, 10], z=[0, 20]),
      dict(n=[0, 1], d=[-1, 0], o=[10, 10], u=[0, 10], z=[0, 20]), dict(n=[-1, 0], d=[0, -1], o=[0, 10], u=[0, 10], z=[0, 20])]      # Quadrat 10 x 10 m, Normalen nach aussen


def kam(C, f=1000.0, quelle="kamera_verfeinern.py: test", **extra):
    Rk = np.eye(3); t = -Rk @ np.asarray(C, float)
    return dict(rvec=[0.0, 0.0, 0.0], t=t.tolist(), f_px=f, cx=500.0, cy=400.0, k1=0.0, quelle=quelle, **extra)


pruef(KT.im_gebaeude(kam([5, 5, 2]), FF) and not KT.im_gebaeude(kam([5, -8, 2]), FF) and not KT.im_gebaeude(kam([5, 5, 40]), FF) and not KT.im_gebaeude(kam([5, 5, 2]), []),
      "im_gebaeude: innen ja; davor, Hochblick ueber dem Dach, ohne Waende nein")

# ---------- (3) Altbestand + Tor ----------
od = os.path.join(D, "modelle", "obj"); mp = os.path.join(od, "messprotokoll"); au = os.path.join(od, "audit"); os.makedirs(mp); os.makedirs(au)
json.dump(dict(fotos_dir="fotos", audit=os.path.relpath(au, D)), open(os.path.join(od, "objekt.json"), "w"))
fj = os.path.join(D, "fassaden.json"); json.dump(dict(fassaden=FF), open(fj, "w"))


def kdatei(n, k): json.dump(dict(foto=n, kamera=k), open(os.path.join(mp, f"K-{n}.json"), "w"))


kdatei("alt_innen", kam([5, 5, 2], vertrauen=True)); kdatei("buendel_innen", kam([5, 5, 2], quelle="kameras_aus_buendel.py aus dem Buendel"))
kdatei("alt_draussen", kam([5, -8, 2], vertrauen=True))
aus = KT.altbestand_sperren(mp, FF, set())
pruef([a["foto"] for a in aus] == ["alt_innen"] and os.path.exists(os.path.join(mp, "K-alt_innen.json.unplausibel")) and os.path.exists(os.path.join(mp, "K-buendel_innen.json"))
      and os.path.exists(os.path.join(mp, "K-alt_draussen.json")), f"Altbestand: nur die abgeleitete Kamera im Gebaeude gesperrt ({[a['foto'] for a in aus]})")
kdatei("neu_innen", kam([5, 5, 2], vertrauen=True)); kdatei("neu_draussen", kam([5, -15, 5], vertrauen=True))
json.dump(dict(neu=[dict(foto="neu_innen"), dict(foto="neu_draussen")]), open(os.path.join(au, "kameras_nachtragen.json"), "w"))
erg = KT.pruefen(os.path.join(od, "objekt.json"), fj)
g_innen = [g for g in erg["gesperrt"] if g["foto"] == "neu_innen"]
pruef("neu_innen" not in erg["belegt"] and g_innen and "Gebaeude" in g_innen[0]["grund"] and "neu_draussen" in erg["belegt"],
      f"Tor: neue Kamera im Gebaeude gesperrt, draussen belegt (belegt {erg['belegt']})")

# ---------- (4) versucht_kandidaten ----------
import seiten_luecken as SL
Z = os.path.join(D, "nachholen"); os.makedirs(Z); kand = []
for i in range(3):
    p = os.path.join(D, f"k{i}.jpg"); open(p, "wb").write(b"x" * (10 + i)); kand.append(p)
json.dump(dict(versuche=[dict(zeit="2026-11-24 17:50", waende=["f02"], kandidaten=SL.kand_namen(kand))]), open(os.path.join(Z, "versucht_kandidaten.json"), "w"))
v1, t1 = SL.kandidaten_versucht(Z, kand)
SL.kandidaten_merken(Z, kand, ["f02"]); v2, t2 = SL.kandidaten_versucht(Z, kand)
pruef(not v1 and "vor dem Abbildungs-Tor" in t1 and v2, f"versucht_kandidaten: alter Versuch zaehlt nicht ({t1}), neuer zaehlt ({t2[:50]})")

# ---------- (5) Zwischenspeicher je Gruppe ----------
os.environ["RCPARK_NACHHOL_CACHE"] = os.path.join(D, "speicher"); os.environ["RCPARK_NACHHOL_CACHE_N"] = "2"
import nachhol_zwischenspeicher as NZ
qa = os.path.join(D, "objA"); qb = os.path.join(D, "objB"); os.makedirs(qa); os.makedirs(qb)
open(os.path.join(qa, "db.db"), "wb").write(b"A" * 1000); open(os.path.join(qb, "db.db"), "wb").write(b"B" * 10)
NZ.ablegen("merkmale", "grossA", {"db.db": os.path.join(qa, "db.db")}, melden=None); os.utime(os.path.join(NZ.wurzel(), "merkmale", "grossA"), (time.time() - 100, time.time() - 100))
for i in range(3): NZ.ablegen("merkmale", f"b{i}", {"db.db": os.path.join(qb, "db.db")}, melden=None); os.utime(os.path.join(NZ.wurzel(), "merkmale", f"b{i}"), (time.time() - 50 + i, time.time() - 50 + i))
NZ.ablegen("merkmale", "b3", {"db.db": os.path.join(qb, "db.db")}, melden=None)
da = sorted(os.listdir(os.path.join(NZ.wurzel(), "merkmale")))
pruef(da == ["b2", "b3", "grossA"], f"Zwischenspeicher: je Gruppe 2 juengste, fremde Gruppe verdraengt den grossen Eintrag nicht ({da})")
del os.environ["RCPARK_NACHHOL_CACHE_N"]

print("BESTANDEN" if fehler == 0 else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
