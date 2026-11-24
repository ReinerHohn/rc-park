#!/usr/bin/env python3
"""test_wandbezug_bauteile.py - fester synthetischer Test (24.11.2026, Risiken a/b aus tools/wandlage_fotokanten.py): alle Bauteile, die an einer Fassade haengen oder in sie
schneiden, nehmen Lage/Tiefe relativ zur GESETZTEN Wand (Korrektur art 'wandversatz' in audit/schleife_korrekturen.json), nicht zur LoD2-Ebene.
Koerper: Quader x -5..5, y -4..4, z 0..20; Fassade f00 (+x) per wandversatz auf w -0,35 (x 4,65) gesetzt, Scheibe z -0,05..18. Generator-Reihenfolge wie objekt_anlegen:
  A Tor (oeffnungen_aus_json, tiefe_m 0,6): Schnitt reicht 0,6 m HINTER die gesetzte Wand (x 4,05), nicht nur 0,25 m.
  B Laube (laube_aus_wandbild, Innenwand absolut bei x 2,0): Pfeiler zwischen zwei Boegen von der gesetzten Wand 0,8 m tief (x 3,85..4,65) voll, Halle dahinter frei.
  C Umgang (umgang_aus_json, z 15..16): Schwelle/Raehm liegen an der gesetzten Wand an (0,3 m eingebunden, 0,08 m vor) - kein Spalt, nichts schwebt 0,35 m vor der Wand;
    Ruecksprung 0,9 m ab der gesetzten Wand.
  D Vorbau (vorbauten_aus_json, w_wand 0 = alte Ebene): Einbindung reicht hinter die gesetzte Wand.
  E Hoehenbereich: eine Scheibe, die den Bereich nicht ueberlappt, verschiebt nichts (wandversatz_fassade z=...).
  F ein Stueck (decompose = 1).
Werte sind Testgeometrie, kein Objektmass. CPU, < 10 s."""
import os, sys, json
import numpy as np
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
from pfade import temp_ordner
import bauteile as BT
from manifold3d import Manifold as M

fehler = []
def pruef(b, t):
    print(("ok    " if b else "FEHLER ") + t, flush=True)
    if not b: fehler.append(t)

T = temp_ordner("test_wandbezug_"); A = os.path.join(T, "audit"); os.makedirs(A, exist_ok=True)
o0, d0, n0 = [5.0, 0.0], [0.0, 1.0], [1.0, 0.0]; WS = -0.35; XW = 5.0 + WS
kp = os.path.join(A, "schleife_korrekturen.json")
json.dump(dict(korrekturen=[dict(id="wl_f00", art="wandversatz", fassade="f00", o=o0, d=d0, n=n0, u0=-4.0, u1=4.0, z0=-0.05, z1=18.0, w_ist=0.0, w_soll=WS, angenommen=True)]), open(kp, "w"))
K = M.cube((10.0, 8.0, 20.0)).translate((-5.0, -4.0, 0.0))
K, _ = BT.korrekturen_aus_json(K, kp, art="wandversatz")

def fuell(K_, x0, x1, y0, y1, z0, z1):
    b = M.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0)); return (K_ ^ b).volume() / b.volume()

# A Tor
oj = os.path.join(A, "oeffnungen_auto.json")
json.dump(dict(f00=dict(o=o0, d=d0, n=n0, oeffnungen=[dict(form="rund", gebaut=True, durchfahrt=False, u=0.0, breite=2.0, kaempfer=3.0, scheitel=4.0, unten=0.0, tiefe_m=0.6)])), open(oj, "w"))
K, bel_o, _ = BT.oeffnungen_aus_json(K, oj)
fa, fb = fuell(K, XW - 0.55, XW - 0.05, -0.3, 0.3, 1.0, 2.0), fuell(K, XW - 0.70, XW - 0.65, -0.3, 0.3, 1.0, 2.0)
pruef(fa < 0.01 and fb > 0.99, f"A Tor schneidet 0,6 m ab der gesetzten Wand: offen bis 0,55 m {1 - fa:.2f}, Mauer ab 0,65 m {fb:.2f}; Beleg wandlage {bel_o[0].get('wandlage') if bel_o else None}")

# B Laube vor Innenwand (absolut x 2,0)
aj = os.path.join(A, "oeffnungen_aussen.json")
R = lambda u0, u1: [[u0, 0.0], [u1, 0.0], [u1, 4.0], [u0, 4.0]]
json.dump(dict(f00=dict(o=o0, d=d0, n=n0, oeffnungen=[dict(klasse="bogen", umriss=R(1.2, 2.2)), dict(klasse="bogen", umriss=R(2.8, 3.8))])), open(aj, "w"))
IW = [dict(name="iw0", fassade="f00", a=[5.0, -4.0], b=[5.0, 4.0], aussen=[6.0, 0.0], versatz=-3.0, u=[0.0, 8.0], z=[0.0, 6.0])]
K, bel_l = BT.laube_aus_wandbild(K, IW, aj, pfeiler_tiefe=0.8)
fp, fh, fo = fuell(K, XW - 0.75, XW - 0.05, 2.3, 2.7, 1.0, 3.0), fuell(K, 2.1, XW - 0.9, 2.3, 2.7, 1.0, 3.0), fuell(K, XW - 0.75, XW - 0.05, 1.4, 2.0, 1.0, 3.0)
pruef(fp > 0.99 and fh < 0.01 and fo < 0.01, f"B Laube: Pfeiler 0,8 m ab gesetzter Wand voll {fp:.2f}, Halle frei {1 - fh:.2f}, Bogen offen {1 - fo:.2f}")

# C Umgang
uj = os.path.join(A, "umgang_auto.json")
json.dump(dict(gefunden=True, z0=15.0, z1=16.0, pfosten_je_seite=3, ecken=[[5.0, -4.0], [5.0, 4.0], [-5.0, 4.0], [-5.0, -4.0]]), open(uj, "w"))
K, bel_u = BT.umgang_aus_json(K, uj)
fr, fv = fuell(K, XW - 0.25, XW + 0.06, -1.0, 1.0, 15.03, 15.17), fuell(K, XW + 0.10, XW + 0.40, -3.0, 3.0, 15.0, 16.0)
fz, fm = fuell(K, XW - 0.85, XW - 0.05, -2.5, -1.5, 15.4, 15.6), fuell(K, XW - 1.05, XW - 0.95, -2.5, -1.5, 15.4, 15.6)
pruef(fr > 0.99 and fv < 0.01, f"C Umgang: Schwelle an der gesetzten Wand voll {fr:.2f}, nichts 0,1-0,4 m davor {fv:.3f}")
pruef(fz < 0.01 and fm > 0.99, f"C Umgang: Ruecksprung 0,9 m ab gesetzter Wand offen {1 - fz:.2f}, Mauer dahinter {fm:.2f}")

# D Vorbau mit w_wand 0 (alte Ebene)
vj = os.path.join(A, "vorbauten_auto.json")
json.dump(dict(fassaden=[dict(id="f00", o=o0, d=d0, n=n0, w_wand=0.0, gruppen=[dict(w=[[0.6, 0.6], [0.6, 0.6]], raster=0.5, u0=-3.0, u1=-2.0, z0=8.0, z1=9.0, koerper=dict(w_median=0.6))])]), open(vj, "w"))
K, _ = BT.vorbauten_aus_json(K, vj)
fs = fuell(K, XW + 0.01, 5.0, -2.9, -2.1, 8.1, 8.9)
pruef(fs > 0.99, f"D Vorbau: kein Spalt zwischen gesetzter Wand und Vorbau ({fs:.2f} gefuellt)")

# E Hoehenbereich
w_in, w_aus = BT.wandversatz_fassade(kp, o0, n0, z=(15.0, 16.0)), BT.wandversatz_fassade(kp, o0, n0, z=(18.5, 19.5))
pruef(abs(w_in - WS) < 1e-9 and w_aus == 0.0, f"E Hoehenbereich: im Bereich {w_in:+.2f}, ueber der Scheibe {w_aus:+.2f}")

# F ein Stueck
nt = len(K.decompose())
pruef(nt == 1, f"F ein Stueck: {nt} Koerper")
print("FEHLER: %d" % len(fehler) if fehler else "ALLE OK"); sys.exit(1 if fehler else 0)
