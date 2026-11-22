#!/usr/bin/env python3
"""test_tiefe_belegt.py - fester synthetischer Test (21.11.2026, schwabentor-1120 Westwand w00: Kruemelbaender im Relief, Lauf 1121r) fuer
  (1) putz_wandbild.tiefe_belegt: einzelne Netzinseln im Lochfeld (Tiefe ohne Mehrfoto-Beleg) unbelegt; Quaderbossen in dicht gemessener Wand
      mit grossen Netzloechern daneben (wie Nordquader w01/w03, 40 % Loch roh) bleiben >= 90 % belegt;
  (2) putz_wandbild.relief_putz_glatt: Inseln im Lochfeld -> Wandniveau, auch OHNE Putzbeleg aus Fotos (Zone ohne Einzelbild); Quaderbossen bleiben;
      Einzelzell-Spitzen weg; OHNE_TIEFENBELEG=1 laesst die Inseln stehen (Gegenprobe, alter Stand);
  (3) putz_wandbild.glatt_karte: schwarze Verdeckungsflecken in den Einzelbildern (eigenes Modell als Verdecker) sind keine Feinstruktur -> glatter Putz bleibt Putz.
Werte sind Testgeometrie, kein Objektmass. < 10 s."""
import os, sys, json, tempfile
import numpy as np, cv2
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
import putz_wandbild as PW

fehler = []
def pruef(b, t):
    if not b: fehler.append(t)

rng = np.random.default_rng(7); px = 0.05

# --- (1) tiefe_belegt
Hn, Wn = 300, 120; fl = np.ones((Hn, Wn), bool)
loch = np.zeros((Hn, Wn), bool); loch[20:120, 10:110] = True                     # Lochfeld (texturarmer Putz oben, Netz fehlt)
insel = loch & (rng.random((Hn, Wn)) < 0.12); insel &= ~np.roll(insel, 1, 0) & ~np.roll(insel, 1, 1)   # vereinzelte Netzzellen im Lochfeld
gem = ~loch | insel
quader = np.zeros((Hn, Wn), bool)
for i in range(160, 290, 7):                                                     # Bossen 30 x 60 cm (6 x 12 Zellen), Fuge 1 Zelle
    for j in range(2 + (i // 7 % 2) * 6, Wn - 12, 13): quader[i:i + 6, j:j + 12] = True
grossloch = np.zeros((Hn, Wn), bool)
for (i, j) in ((170, 20), (220, 70), (250, 5)): grossloch[i:i + 20, j:j + 20] = True     # grosse Netzloecher in der Quaderwand (wie roh 40 %)
gem &= ~grossloch
B = PW.tiefe_belegt(gem, fl, px)
pruef(float(B[insel].mean()) < 0.05, f"Netzinseln im Lochfeld belegt ({B[insel].mean():.2f}, soll < 0,05)")
q_ = quader & gem; pruef(float(B[q_].mean()) >= 0.9, f"Quaderbossen nicht belegt ({B[q_].mean():.2f}, soll >= 0,9)")
pruef(float(B[~loch & ~grossloch].mean()) >= 0.95, f"dicht gemessene Wand nicht belegt ({B[~loch & ~grossloch].mean():.2f})")

# --- (2) relief_putz_glatt auf einer Wand wie relief_roh (Niveau 'vorstand' 0,11, Loch = 0,11)
rel = np.full((Hn, Wn), 0.11, np.float32); rel[insel] += 0.12                    # Inseln 12 cm vor der Wand (w00: 10-13 cm)
rel[quader & gem] += 0.06                                                          # Bossen 6 cm
spitz = np.zeros((Hn, Wn), bool); spitz[140:150:3, 20:100:7] = True; rel[spitz] += 0.08   # Einzelzell-Spitzen in gemessener Putzflaeche
Zd = dict(rel=rel, a=np.array([0.0, 0.0]), t=np.array([1.0, 0.0]), n=np.array([0.0, 1.0]), u0=0.0, z0=0.0, px=px, oeffnung=np.zeros((Hn, Wn), bool),
          wand=fl.copy(), loch=(loch & ~insel) | grossloch)                       # relief_roh: Loch = Zelle ohne Netz
T = temp_ordner("test_tiefe_belegt_"); f_in = os.path.join(T, "w00_voll.npz"); np.savez_compressed(f_in, **Zd)
putz = np.zeros((Hn, Wn), bool); putz[125:155, :] = True                          # Putzbeleg aus Fotos nur in einem Streifen; Lochfeld ohne Einzelbild (wie w00 ueber z 23,6 m)
for ohne in ("", "1"):
    os.environ["OHNE_TIEFENBELEG"] = ohne
    f_out = os.path.join(T, f"w00_glatt{ohne}.npz"); info = PW.relief_putz_glatt(f_in, f_out, putz.copy())
    G = np.load(f_out); r = G["rel"]; niv = float(G["putz_niveau_m"])
    fuge = ~quader & gem & (np.arange(Hn)[:, None] >= 160) & (np.arange(Hn)[:, None] < 286) & (np.arange(Wn)[None, :] < Wn - 12)
    weg = float((np.abs(r[insel] - niv) < 0.01).mean()); bleibt = float(np.median(r[quader & gem]) - np.median(r[fuge]))       # Bosse gegen Fuge (Wandniveau = Bossenflaeche)
    if ohne:
        pruef(weg < 0.5, f"Gegenprobe OHNE_TIEFENBELEG: Inseln sollten stehen bleiben (glatt {weg:.2f})")
    else:
        pruef(weg >= 0.95, f"Netzinseln im Lochfeld nicht auf Wandniveau ({weg:.2f}, soll >= 0,95)")
        pruef(bleibt >= 0.05, f"Quaderbossen verloren (Bosse - Fuge {bleibt * 100:.1f} cm, soll >= 5)")
        pruef(float(np.abs(r[spitz] - niv).max()) < 0.02, f"Einzelzell-Spitzen stehen ({np.abs(r[spitz] - niv).max() * 100:.0f} cm)")
        pruef(info.get("unbelegt_kruemel_m2", 0) > 0, f"Info ohne unbelegt_kruemel_m2: {info}")
        pruef("tiefe_unbelegt" in G.files, "tiefe_unbelegt fehlt im npz")
os.environ.pop("OHNE_TIEFENBELEG", None)

# --- (3) glatt_karte: Verdeckungsflecken (schwarz) auf glattem Putz
FF = os.path.join(T, "fassade_fein"); os.makedirs(os.path.join(FF, "ortho_f00_einzeln")); c = 0.01
R = dict(u0=0.0, z1=6.0, nu=400, nz=600, zelle=c)
json.dump(dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[1.0, 0.0], n=[0.0, 1.0], raster=R)]), open(os.path.join(FF, "fassaden.json"), "w"))
for k in range(5):
    g = np.full((R["nz"], R["nu"], 3), 205, np.uint8) + rng.integers(0, 2, (R["nz"], R["nu"], 1)).astype(np.uint8)
    for _ in range(40):                                                              # Flecken 6-15 cm, je Foto anders (Parallaxe der Kruemel)
        i, j, s = rng.integers(20, R["nz"] - 20), rng.integers(20, R["nu"] - 20), rng.integers(3, 8)
        cv2.circle(g, (int(j), int(i)), int(s), (0, 0, 0), -1)
    cv2.imwrite(os.path.join(FF, "ortho_f00_einzeln", f"foto{k}.png"), g)
K = PW.glatt_karte(FF, "f00"); pruef(K is not None, "glatt_karte: keine Karte")
if K is not None:
    a_ = float(K["putz"][2:-2, 2:-2].mean()); pruef(a_ >= 0.9, f"glatter Putz mit Verdeckungsflecken nicht Putz ({a_:.2f}, soll >= 0,9)")

if fehler:
    for f in fehler: print("FEHLER:", f)
    sys.exit(1)
print("ALLE BESTANDEN (Netzinseln im Lochfeld glatt, Quaderbossen bleiben, Spitzen weg, Gegenprobe alt, Verdeckungsflecken kein Struktur-Beleg)")
