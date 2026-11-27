#!/usr/bin/env python3
"""Fester Test (synthetisch, ~5 s) fuer tools/foto_auftrag_lage.py - Fotoauftrag fuer eine Sonderstelle mit Lagedatei (27.11.2026, Schwabentorsteg).
Ebenes Gelaende (ohne DOM/DGM), Hauptbau 10 x 10 m / 30 m, Steg 30 x 4 m (z 5..10) oestlich (Lagedatei im messprotokoll), ein 25-m-Haus auf einer Seite.
  1 Fernstandpunkte   >= 2, je Hauptbau + Steg im Bild (Spanne <= BILD_ANTEIL x Bildwinkel), nie im Haus, Azimutabstand >= MIN_AZ_ABSTAND, GPS da.
  2 Verdeckung        kein Fernstandpunkt, dessen Sicht auf die Stegmitte durch das Haus geht.  Gegenprobe: ohne Haus gibt es dort Kandidaten (Test nicht trivial).
  3 Nahstandpunkte    duenne Unterseite mit Lueckenzellen -> Standpunkte neben dem Steg, Handy nach oben; 'Deck innen' -> auf dem Steg mit zwei Blickrichtungen;
                      belegte Teile bekommen keine.
  4 ohne Lagedatei    Abbruch mit 'Lage unbekannt' statt geratener Standpunkte.
Python: /media/oem/scan/venv-seg/bin/python -I tools/test_foto_auftrag_lage.py"""
import os, sys, json, math
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import foto_auftrag_lage as FL, foto_auftrag_skizze as F

fehler = []
def pruef(b, t):
    if not b: fehler.append(t); print("FEHLER:", t)


tmp = __import__("pfade").temp_ordner("test_foto_auftrag_lage_"); mp = os.path.join(tmp, "messprotokoll", "lage_x"); os.makedirs(mp)
obj = dict(name="Test", rahmen=dict(mitte_utm=[414525.9, 5316153.75], xhat_utm=[0.0, 1.0], yhat_utm=[-1.0, 0.0], gelaende=0.0),
           rahmen_wand=dict(u0=-5, u1=5, v0=-5, v1=5), seiten_konvention={"+x": "Nord", "-x": "Sued", "+y": "West", "-y": "Ost"}, hoehe_m=40)
json.dump(dict(steg=dict(mitte_modell_xy=[0.0, -25.0], achse_modell_xy=[0.0, -1.0], laenge_m=30.0, breite_m=4.0, dach_first_z_m=10.0, deck_unterkante_z_m=5.0, laufebene_z_m=5.5)),
          open(os.path.join(mp, "STEG-LAGE.json"), "w"))
cfg = dict(wand_oben_m=30.0, sonderstellen=[dict(name="Steg", form="lage", mitte=None)]); zj = os.path.join(tmp, "zonen.json"); json.dump(cfg, open(zj, "w"))
lu_unter = [[x, y, 5.0] for x in (-1.0, 1.0) for y in (-20.0, -26.0, -32.0)]
meldung = dict(bildwinkel_grad=60.0, zonen=[dict(name="Steg Unterseite", gruppe="Steg", status="duenn", fehlt=["x"], fotos=5, faecher_grad=40, zellen_gesehen=0.2, zellen_luecke=lu_unter),
                                            dict(name="Steg Deck innen", gruppe="Steg", status="duenn", fehlt=["x"], fotos=2, faecher_grad=10, zellen_gesehen=0.1, zellen_luecke=[[0, -25, 5.5]]),
                                            dict(name="Steg Seite Nord", gruppe="Steg", status="belegt", fehlt=[], fotos=50, faecher_grad=120, zellen_gesehen=1.0, zellen_luecke=[[2, -25, 7]])])
rahmen = F.Rahmen(obj)
haus = dict(id="haus", ringe=[np.array([[30.0, -45], [70, -45], [70, -40], [30, -40]])], oben=25.0)   # Haus nordoestlich, quer vor der Sicht aus Nordost
def lauf(geb):
    si = F.Sicht(geb, rahmen, None, None, radius=260.0)
    return FL.erzeugen(None, zj, None, "Steg", None, 5, geo=False, obj=obj, cfg=cfg, meldung=meldung, sicht=si), si
e, si = lauf([haus]); fern = [s for s in e["standpunkte"] if s["art"] == "fern"]; nah = [s for s in e["standpunkte"] if s["art"] == "nah"]
# 1
pruef(len(fern) >= 2, f"1 nur {len(fern)} Fernstandpunkte")
from matplotlib.path import Path
for s in fern:
    p = np.array([s["x"], s["y"]]); pruef(not Path(haus["ringe"][0]).contains_point(p), f"1 {s['nr']} steht im Haus")
    pruef(s.get("lat") and s.get("lon") and s["blick_kompass_grad"] is not None, f"1 {s['nr']} ohne GPS/Blick")
    pkt = np.array([[-5, -5], [-5, 5], [5, -5], [5, 5], [0, -10], [0, -40]]); a = np.sort(np.degrees(np.arctan2(*(pkt - p).T[::-1])) % 360); sp = 360 - np.diff(np.r_[a, a[0] + 360]).max()
    pruef(sp <= FL.BILD_ANTEIL * 60.0 + 1e-6, f"1 {s['nr']}: Hauptbau + Steg nicht zugleich im Bild ({sp:.0f} Grad)")
az = [math.degrees(math.atan2(s["y"] + 25, s["x"])) for s in fern]
pruef(all(abs((a - b + 180) % 360 - 180) >= FL.MIN_AZ_ABSTAND - 3 for i, a in enumerate(az) for b in az[i + 1:]), f"1 Fernstandpunkte zu eng: {az}")
# 2 Verdeckung: Sichtlinie zur Stegmitte darf das Haus (25 m) nicht schneiden, wenn sie unter 25 m bleibt (ebenes Gelaende, Auge 1,6 m)
def durchs_haus(p, ziel=np.array([0.0, -25.0])):
    return any(Path(haus["ringe"][0]).contains_point(p + t * (ziel - p)) for t in np.linspace(0.02, 0.98, 200))
pruef(not any(durchs_haus(np.array([s["x"], s["y"]])) for s in fern), "2 Fernstandpunkt sieht durch das Haus")
_, n_mit = FL.fern_kandidaten(rahmen, si, (-5, 5, -5, 5, 30.0), __import__("abdeckung_meldung").lage_lesen(os.path.join(mp, "STEG-LAGE.json")), 60.0, 30.0, 50)
si0 = F.Sicht([], rahmen, None, None, radius=260.0); L = __import__("abdeckung_meldung").lage_lesen(os.path.join(mp, "STEG-LAGE.json"))
alle0, n_ohne = FL.fern_kandidaten(rahmen, si0, (-5, 5, -5, 5, 30.0), L, 60.0, 30.0, alle=True)
pruef(any(durchs_haus(x["p"]) for x in alle0) and n_ohne > n_mit, f"2 Gegenprobe: ohne Haus keine zusaetzlichen Kandidaten hinter dem Haus ({n_ohne} / {n_mit}) - Pruefung 2 waere trivial")
# 3 Nahstandpunkte
un = [s for s in nah if s["teil"] == "Steg Unterseite"]; de = [s for s in nah if s["teil"] == "Steg Deck innen"]
pruef(len(un) >= 2 and all(s["neigung_grad"] > 20 and abs(s["x"]) > 2 for s in un), f"3 Unterseite: Standpunkte fehlen/nicht neben dem Steg/nicht nach oben: {un}")
pruef(len(de) >= 1 and all(abs(s["x"]) < 2 and s.get("blick2_kompass_grad") is not None for s in de), f"3 Deck innen: nicht auf dem Steg oder ohne zweite Blickrichtung: {de}")
pruef(not any(s["teil"] == "Steg Seite Nord" for s in nah), "3 belegter Teil bekommt Nahstandpunkte")
md = FL.markdown(e, obj); pruef("nubia" in md and "Wasserzeichen AUS" in md and "F1" in md and "N1" in md, "3 Markdown ohne Handy-Hinweise/Nummern")
# 4 ohne Lagedatei
os.remove(os.path.join(mp, "STEG-LAGE.json"))
try: FL.erzeugen(None, zj, None, "Steg", None, 5, geo=False, obj=obj, cfg=cfg, meldung=meldung, sicht=si); ok4 = False
except SystemExit as ex: ok4 = "Lage unbekannt" in str(ex)
pruef(ok4, "4 ohne Lagedatei kein Abbruch mit 'Lage unbekannt'")
print(f"fern {len(fern)}, nah {len(nah)}, Kandidaten mit Haus {n_mit} / ohne {n_ohne}")
if fehler: print(f"ROT: {len(fehler)} Fehler"); sys.exit(1)
print("ok test_foto_auftrag_lage")
