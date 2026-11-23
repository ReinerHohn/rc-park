#!/usr/bin/env python3
"""Test (24.11.2026, Kette 1122u Schwabentor): Abnahme "Anzahl getrennte Koerper 2 (Soll 1)" - zweiter Koerper = Galerie-Pfosten f00 bei u 4,25, Kasten aus den
Fotokanten nur bis u 4,09: der Pfosten (0,22 m) stand 5 cm neben Kasten und Raehm frei in der Luft. Soll: vorbauten_aus_json zieht ihn an das Kastenende -> 1 Koerper."""
import os, sys, json, shutil
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from manifold3d import Manifold as M
import bauteile as B
from pfade import temp_ordner

td = temp_ordner("test_vorbau_pfosten_")
try:
    J = dict(fassaden=[dict(id="f00", o=[0.0, 0.0], d=[0.0, 1.0], n=[1.0, 0.0], w_wand=0.0, gruppen=[dict(
        u0=-4, u1=4.6, z0=9.8, z1=20.4, raster=0.2, w=[[0.0]], koerper={}, galerie=dict(z_dach=15.98),
        kanten_mass=dict(ausladung=1.27, kasten=dict(z_unten=10.81, z_oben=12.05, u0=-3.81, u1=4.09, breite=7.9),
                         pfosten=[dict(u=-3.45, breite=None), dict(u=4.25, breite=None)]))])])
    f = os.path.join(td, "vorbauten_auto.json"); json.dump(J, open(f, "w"))
    wand = M.cube((6, 10, 20)).translate((-6, -5, 0))
    k, bel = B.vorbauten_aus_json(wand, f)
    n = len([t for t in k.decompose() if t.volume() > 1e-6])
    if n != 1: print(f"FEHLER vorbau_pfosten: {n} getrennte Koerper (Pfosten neben dem Kasten frei)"); sys.exit(1)
    if "gerueckt" not in json.dumps(bel, ensure_ascii=False): print("FEHLER vorbau_pfosten: Verschiebung nicht im Beleg"); sys.exit(1)
    print("    ok Pfosten neben dem Kastenende an den Kasten gerueckt, 1 Koerper, Beleg nennt es")
finally:
    shutil.rmtree(td, ignore_errors=True)
