#!/usr/bin/env python3
"""test_fenster_tiefe_klein.py - fenster_tiefe_tor: kleines dunkles Loch unter der Sweep-Aufloesung wird nicht als 'keine Nische' verworfen (24.11.2026), < 10 s, nur CPU.

Befund Kettenlauf 1122u (audit/seiten.jpg, Schwabentor-1122): Sued (-x) ohne jede Oeffnung. Am Foto (113852, commons_191, od_02): EIN vergittertes Stichbogenfenster
im Sandsteingewaende unter der Uhr. Der Erkenner fand es (5 Stimmen), fenster_tiefe_tor verwarf es: Sweep im Kasten 100 % sicher, hinten 0 %, vorn 7 % ->
'gar keine Nische'. Ursache: der Ebenen-Sweep mittelt die Kosten ueber 0,44 m (11 Zellen); das Loch (~0,87 x 1,1 m, Gitter vorn) sieht in jedem Fenster
ueberwiegend Gewaende/Wand -> Wandtiefe. Das ist keine Messung.
Faelle (synthetisch, Wand 4 cm, Sweep ueberall 'gut' auf Wandtiefe - wie Sued):
  A  kleines dunkles Loch 0,5 x 0,7 m im Sandsteingewaende       -> bleibt (kein Urteil, Grund im Bericht)
  B  helles Feld (Konsolenfeld, Putzfarbe) 1,0 x 1,4 m             -> verworfen (Altverhalten, kein dunkles Loch)
  C  grosses dunkles Feld 2,0 x 2,0 m (Sweep loest es auf)          -> verworfen (Sweep-Urteil gilt)
  D  kleines dunkles Loch, aber vorn 40 % (etwas steht davor)       -> verworfen
  E  Karte ohne 'fenster_m' (aeltere Laeufe) -> Vorgabe 11 Zellen
ROT-PROBE: mit --fein auf einen leeren Ordner (kein Wandbild = Verhalten vor dem Fix) faellt A weg - genau der Befund 1122u.
"""
import sys, os, json, subprocess, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from pfade import temp_ordner
import fenster_tiefe_tor as FT

F = 0
def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1

import cv2
T = temp_ordner("test_fenster_tiefe_klein_"); au = os.path.join(T, "audit"); fo = os.path.join(T, "fassade"); leer = os.path.join(T, "leer")
for p_ in (au, fo, leer): os.makedirs(p_, exist_ok=True)
U0, Z1, C, H, W = -6.0, 14.0, 0.04, 350, 300
WAND, SAND, DUNKEL = (200, 205, 212), (95, 108, 165), (25, 25, 30)
im = np.zeros((H, W, 3), np.uint8); im[:] = WAND
px = lambda u, z: (int(round((u - U0) / C)), int(round((Z1 - z) / C)))
def kasten(u0, u1, z0, z1, farbe):
    a, b = px(u0, z1), px(u1, z0); cv2.rectangle(im, a, b, farbe, -1)
# A: Gewaende 1,0 x 1,2 m, Loch 0,5 x 0,7 m
kasten(-4.5, -3.5, 10.0, 11.2, SAND); kasten(-4.25, -3.75, 10.25, 10.95, DUNKEL)
# B: helles Feld = Wandfarbe mit Sandsteinrahmen (Konsolenfeld)
kasten(-1.0, 0.2, 10.0, 11.6, SAND); kasten(-0.9, 0.1, 10.1, 11.5, WAND)
# C: grosses dunkles Feld 2 x 2 m
kasten(1.5, 3.5, 2.0, 4.0, DUNKEL)
# D: kleines dunkles Loch wie A, vorn 40 %
kasten(-4.5, -3.5, 3.0, 4.2, SAND); kasten(-4.25, -3.75, 3.25, 3.95, DUNKEL)
rng = np.random.default_rng(1); im = np.clip(im.astype(int) + rng.integers(-3, 4, im.shape), 0, 255).astype(np.uint8)
cv2.imwrite(os.path.join(fo, "ortho_f00.png"), im)
json.dump(dict(fassaden=[dict(id="f00", raster=dict(u0=U0, z1=Z1, nu=W, nz=H, zelle=C))]), open(os.path.join(fo, "fassaden.json"), "w"))
w = np.full((H, W), 0.05, np.float32); g = np.ones((H, W), bool)
a, b = px(-4.6, 4.3), px(-3.4, 2.9); w[a[1]:b[1], a[0]:b[0]][::2] = 0.55          # D: Gitter/Strebe 0,5 m vor der Wand auf jeder zweiten Zeile
np.savez(os.path.join(fo, "tiefe_f00.npz"), w=w, gut=g, sicher=np.ones_like(w), zelle=C, u0=U0, z1=Z1, fenster_m=0.44)
json.dump(dict(wand_versatz_m=0.05), open(os.path.join(fo, "vorbauten_f00.json"), "w"))
json.dump(dict(fassaden={"f00": dict(elemente=[])}), open(os.path.join(fo, "elemente.json"), "w"))
KA = dict(u0=-4.55, u1=-3.45, z0=9.95, z1=11.25); KB = dict(u0=-1.0, u1=0.2, z0=10.0, z1=11.6); KC = dict(u0=1.5, u1=3.5, z0=2.0, z1=4.0); KD = dict(u0=-4.55, u1=-3.45, z0=2.95, z1=4.25)

def lauf(*extra):
    json.dump({"f00": dict(fenster=[KA, KB, KC, KD])}, open(os.path.join(au, "fenster_auto.json"), "w"))
    r = subprocess.run([sys.executable, "-I", os.path.join(HIER, "fenster_tiefe_tor.py"), os.path.join(au, "fenster_auto.json"), fo, *extra], capture_output=True, text=True)
    FE = json.load(open(os.path.join(au, "fenster_auto.json")))["f00"]["fenster"]; B = json.load(open(os.path.join(au, "fenster_tiefe_tor.json")))["f00"]
    da = lambda k: any(abs(q["u0"] - k["u0"]) < 1e-6 and abs(q["z0"] - k["z0"]) < 1e-6 for q in FE)
    return da, B, r

da, B, r = lauf("--fein", fo)
pruef(r.returncode == 0, f"fenster_tiefe_tor rc 0 {r.stderr[-300:]}")
pruef(da(KA) and "kein Urteil" in B[0]["urteil"] and "loest" in B[0]["urteil"], f"A kleines dunkles Loch im Gewaende bleibt: {B[0]['urteil']}")
pruef(not da(KB), f"B helles Feld (Konsolenfeld) weiter verworfen: {B[1]['urteil']}")
pruef(not da(KC), f"C grosses dunkles Feld (Sweep loest auf, keine Nische) verworfen: {B[2]['urteil']}")
pruef(not da(KD), f"D kleines Loch mit etwas davor (vorn {B[3]['vorn']}) verworfen: {B[3]['urteil']}")
da0, B0, _ = lauf()      # Vorgabe <ordner>_fein fehlt -> Orthos im Fassadenordner
pruef(da0(KA) and not da0(KB), "ohne --fein: Wandbild aus dem Fassadenordner")
da1, B1, _ = lauf("--fein", leer)
pruef(da1(KA), "leerer --fein-Ordner -> Fassadenordner als Rueckfall")
# ROT-PROBE: ohne jedes Wandbild (Verhalten vor dem Fix) faellt A weg
os.rename(os.path.join(fo, "ortho_f00.png"), os.path.join(fo, "ortho_f00.png.weg"))
da2, B2, _ = lauf("--fein", leer)
pruef(not da2(KA), f"ROT-PROBE ohne Wandbild: A wird wie im Lauf 1122u verworfen ({B2[0]['urteil']})")
os.rename(os.path.join(fo, "ortho_f00.png.weg"), os.path.join(fo, "ortho_f00.png"))
# E: aeltere Karte ohne fenster_m
pruef(abs(FT.sweep_fenster_m(dict(zelle=0.04)) - 0.44) < 1e-9 and abs(FT.sweep_fenster_m(dict(zelle=0.04, fenster_m=0.6)) - 0.6) < 1e-9, "E Sweep-Mittelung: gespeichert oder 11 Zellen")
# F: Folgestufe loch_gewaende - Loch kleiner als der Bogenkasten (Werte Schwabentor-1122 Sued): Stichbogen behaelt seine Hoehe (vorher kaempfer = scheitel -> ZeroDivisionError)
import loch_gewaende as LG
e = dict(u0=-0.531, u1=0.399, z0=23.197, z1=24.607, bogen=dict(form="stich", kaempfer=24.462, scheitel=24.607))
LG.eintrag_anpassen(e, dict(loch=dict(u0=-0.466, u1=0.404, z0=23.152, z1=24.212)), None)
b_ = e["bogen"]
pruef(b_["form"] == "stich" and abs(b_["scheitel"] - 24.212) < 1e-6 and abs((b_["scheitel"] - b_["kaempfer"]) - 0.145) < 2e-3, f"F Stichbogen nach Lochmessung: Stich {b_['scheitel'] - b_['kaempfer']:.3f} m (soll 0,145, vorher 0)")
try:
    import bauteile as BT
    BT.bogen_querschnitt(b_["form"], e["u1"] - e["u0"], b_["kaempfer"], b_["scheitel"], e["z0"]); pruef(True, "F Bogenquerschnitt baubar")
except ImportError: print("hinweis: bauteile nicht ladbar in dieser Umgebung")
except Exception as x: pruef(False, f"F Bogenquerschnitt wirft {x!r}")
print("FEHLER: %d" % F if F else "alle Pruefungen bestanden"); sys.exit(1 if F else 0)
