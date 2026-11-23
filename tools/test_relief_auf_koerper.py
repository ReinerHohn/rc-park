#!/usr/bin/env python3
"""Test (24.11.2026, Kette 1122u Schwabentor Sued w05): berechnete Steine muessen VOR dem Grundkoerper ankommen.
Befund: Mono-Relief (165 Steine) und Feinrelief (misch) der Quaderwaende wurden mit trend=True auf der Ausgleichsebene des Netzes gebaut; die lag 0,23-0,26 m
HINTER der gemessenen Koerperflaeche (Wandversatz) -> Steine im Koerper versenkt, Quaderzone im Modell glatt. Synthetisch: Wand x = 0, Netzebene -0,3 m,
Steine +5 cm, Mono mit Putzniveau +0,14 m (w01_mono). Soll: in Mono- und Misch-Feld steht Steinvolumen vor der Wand; RELIEF_NETZEBENE=1 (alter Stand) muss rot sein."""
import os, sys, json, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
from manifold3d import Manifold as M
import fassaden_kette as FK
from pfade import temp_ordner

PX = 0.02; STEIN = 0.05


def relief(pfad, u0, u1, z0, z1, steine, ebene=-0.3, px=PX, niv=0.0):
    W, H = int(round((u1 - u0) / px)), int(round((z1 - z0) / px)); rel = np.zeros((H, W), np.float32)
    if steine:                                                          # Quader 0,6 x 0,3 m, Fugen 4 cm (Rille -2 cm wie quader_raster), Stirn 5 cm ueber dem Fugengrund
        rel[:] = -0.02; rel[0, 0] = 0.0                                 # rel == 0 = Loch/ohne Netz (relief_roh) - zaehlt nicht zur Wand
        ii, jj = np.mgrid[0:H, 0:W]; lage = (ii * px) // 0.3
        rel[(((jj * px + 0.3 * (lage % 2)) % 0.6) > 0.04) & (((ii * px) % 0.3) > 0.04)] = STEIN - 0.02
    np.savez_compressed(pfad, rel=rel, a=np.array([0.0, 0.0]), t=np.array([0.0, 1.0]), n=np.array([1.0, 0.0]), u0=u0, z0=z0, px=px,
                        oeffnung=np.zeros((H, W), bool), ebene_abstand_m=ebene, trend_je_m=np.zeros(2), putz_niveau_m=niv)


def vor_wand(k, u0, u1, z0, z1):
    return (k ^ M.cube((0.5, u1 - u0 - 0.2, z1 - z0 - 0.2)).translate((0.01, u0 + 0.1, z0 + 0.1))).volume()


def lauf(alt):
    td = temp_ordner("test_relief_auf_koerper_"); od = os.path.join(td, "obj_relief_auf_koerper_test")
    os.makedirs(os.path.join(od, "audit")); os.makedirs(os.path.join(od, "relief")); json.dump({}, open(os.path.join(od, "objekt.json"), "w"))
    WL = [dict(name="w00", a=[0, 0], b=[0, 4], aussen=[5, 2], quader=True, mono=dict(datei="w00_mono.npz")),       # Quaderwand mit Mono-Relief z 0-10
          dict(name="w01", a=[0, 5], b=[0, 9], aussen=[5, 7], quader=True, fein_feld=[0.0, 4.0, 0.0, 10.0])]        # Quaderwand mit Feinrelief (misch)
    json.dump(dict(waende=WL), open(os.path.join(od, "audit", "fassaden_kette.json"), "w"))
    relief(os.path.join(od, "relief", "w00_voll.npz"), 0, 4, 0, 20, False, px=0.05)
    relief(os.path.join(od, "relief", "w00_mono.npz"), 0.1, 3.9, 0, 10, True, niv=0.14)       # Putzniveau 0,14 m ueber dem Steinmedian (w01_mono 1122u): Bezug muss der Median sein
    for nm in ("w01_voll", "w01_misch"):                                  # w01: eigenes a (u = y - 5)
        relief(os.path.join(od, "relief", nm + ".npz"), 0, 4, 0, 20 if nm.endswith("voll") else 10, nm.endswith("misch"), px=0.05 if nm.endswith("voll") else PX)
        Z = dict(np.load(os.path.join(od, "relief", nm + ".npz"))); Z["a"] = np.array([0.0, 5.0]); np.savez_compressed(os.path.join(od, "relief", nm + ".npz"), **Z)
    basis = M.cube((10, 12, 22)).translate((-10, -1.5, 0))               # Grundkoerper: Wandflaeche bei x = 0 (gemessene Flaeche), Netzebene der Reliefs -0,3 m
    alt_env = os.environ.get("RELIEF_NETZEBENE")
    if alt: os.environ["RELIEF_NETZEBENE"] = "1"
    else: os.environ.pop("RELIEF_NETZEBENE", None)
    try: k, bel = FK.anbauen(basis, os.path.join(od, "objekt.json"))
    finally:
        if alt_env is None: os.environ.pop("RELIEF_NETZEBENE", None)
        else: os.environ["RELIEF_NETZEBENE"] = alt_env
    import shutil; shutil.rmtree(td, ignore_errors=True)
    return vor_wand(k, 0.1, 3.9, 0, 10), vor_wand(k, 5.0, 9.0, 0, 10)


fehler = []
# erwartet: Steinanteil ~ (0,56/0,6)*(0,26/0,3) = 81 % der Flaeche, 5 cm vor der Wand (+ Sockel 5 mm)
mono, misch = lauf(False)
soll_mono = 0.5 * 3.6 * 9.8 * STEIN; soll_misch = 0.5 * 3.8 * 9.8 * STEIN
if mono < soll_mono: fehler.append(f"Mono-Steine nicht vor der Wand: {mono:.3f} m3 < {soll_mono:.3f}")
if misch < soll_misch: fehler.append(f"Misch-Steine nicht vor der Wand: {misch:.3f} m3 < {soll_misch:.3f}")
if mono > 3.6 * 9.8 * (STEIN + 0.02): fehler.append(f"Mono-Relief steht zu weit vor: {mono:.3f} m3")
mono_a, misch_a = lauf(True)                                          # Gegenprobe alter Stand: Steine versenkt
if mono_a > 0.1 * soll_mono or misch_a > 0.1 * soll_misch: fehler.append(f"Gegenprobe RELIEF_NETZEBENE=1 nicht versenkt ({mono_a:.3f}/{misch_a:.3f} m3) - Test misst nichts")
if fehler: print("FEHLER relief_auf_koerper:", "; ".join(fehler)); sys.exit(1)
print(f"    ok Mono {mono:.3f} m3 / Misch {misch:.3f} m3 Steine vor der Wand (alter Stand {mono_a:.3f}/{misch_a:.3f})")
