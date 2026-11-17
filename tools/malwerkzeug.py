#!/usr/bin/env python3
"""malwerkzeug.py [--aus ORDNER] [teil ...]  - druckbare Malhilfen fuer das Bemalen der Modellteile (17.11.2026, Nutzer: "Werkzeug ausdrucken, das Geiles zum Anmalen").
Teile (ohne Angabe: alle):
  griff        Malgriff 30 x 95 mm mit Rillen; oben 1,9-mm-Loch fuer einen Filamentstift (1,75) - jedes Klipsteil aus tools/druck_klips.py steckt mit seinem
               Achs-/Stiftloch darauf, man fasst das Teil beim Malen nie an; dazu eine 2-mm-Mulde fuer Knetmasse (Teile ohne Loch).
  griff_klemme Malgriff mit Klemmzange oben (Schlitz 1-4 mm, federnd) fuer flache Teile (Zeiger, Wappen, Fenster).
  flaschen     Flaschentreppe 3 Reihen x 6 Tropfflaschen (Vallejo/Army Painter, Durchmesser 25 mm -> Loch 26,5 mm), Stufen 18 mm, Etiketten sichtbar.
  drehteller   Drehteller zum Spruehen: Fuss 120 mm mit Zapfen, Teller 110 mm mit Buchse und Rand (2 Teile, flach gedruckt).
  pinsel       Pinselstaender 10 Loecher (7 mm) schraeg 15 Grad + Rinne fuer Marker.
  griffbank    Ablage fuer 6 Malgriffe (Trocknen): Loecher 31 mm.
Ausgabe: <aus>/mal_<teil>.stl, wasserdicht geprueft. Groesse/Drucker: alles grob genug fuer den MK4S 0,8 (0,4-mm-Schichten), Griff/Klemme auch Bambu.
"""
import sys, os, argparse, numpy as np, trimesh
from manifold3d import Manifold as M, CrossSection as CS, OpType
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "tools"))
from bauteile import stl_schreiben

SEG = 64


def zyl(h, r, r2=None, seg=SEG): return M.cylinder(h, r, r if r2 is None else r2, seg)


def griff():
    k = zyl(95, 15)                                                                   # Koerper
    rillen = [M.cube((3.0, 40, 70)).translate((-1.5, 13.6, 12)).rotate((0, 0, i * 30.0)) for i in range(12)]
    k = k - M.batch_boolean(rillen, OpType.Add)
    k = k + zyl(2.0, 17).translate((0, 0, 0)) + zyl(2.0, 17).translate((0, 0, 0))      # Standteller gegen Umfallen
    k = k - zyl(12, 0.95, seg=24).translate((0, 0, 95 - 11.99))                         # Stiftloch 1,9 mm
    k = k - zyl(2.0, 9).translate((0, 0, 95 - 1.99)) + zyl(2.0, 2.0).translate((0, 0, 93))   # Knetmulde, Ring um das Stiftloch bleibt
    return k - zyl(12, 0.95, seg=24).translate((0, 0, 95 - 11.99))


def griff_klemme():
    k = griff().trim_by_plane((0, 0, -1), -80.0)                                       # unterer Teil bis 80 mm
    b = M.cube((22, 8, 30), True).translate((0, 0, 80 + 15))                           # Klemmbacken-Block
    b = b - M.cube((24, 1.2, 22), True).translate((0, 0, 80 + 30 - 11 + 0.01))         # Schlitz 1,2 mm (federt auf ~4 mm)
    b = b - M.cube((24, 3.0, 3.0), True).translate((0, 0, 80 + 30 - 22))               # Entlastungsloch unten im Schlitz (Feder)
    keil = M.cube((22, 3.0, 4), True).translate((0, 0, 80 + 30 - 2)) - M.cube((24, 1.2, 6), True).translate((0, 0, 80 + 30 - 2))
    return k + b - keil.translate((0, 0, 0)) + M.cube((22, 8, 2), True).translate((0, 0, 81))


def flaschen(n=6, reihen=3, d=26.5, stufe=18.0, tief=14.0, abst=31.0):
    B = n * abst + 8; T = reihen * abst + 8; k = M()
    for r in range(reihen):
        h = 6.0 + r * stufe + tief; y0 = r * abst
        blk = M.cube((B, T - y0, h)).translate((0, y0, 0))
        k = k + blk if not k.is_empty() else blk
    loch = []
    for r in range(reihen):
        h = 6.0 + r * stufe + tief
        for i in range(n): loch.append(zyl(tief + 1, d / 2).translate((4 + abst / 2 + i * abst, 4 + abst / 2 + r * abst, h - tief)))
    k = k - M.batch_boolean(loch, OpType.Add)
    return k                                                                         # massiv lassen: Hohlraum von unten waere eine 186-mm-Bruecke; die Fuellung (15 %) spart Material im Slicer


def drehteller():
    fuss = zyl(4, 60) + zyl(10, 6, 5.5).translate((0, 0, 4))
    teller = zyl(3, 55) - zyl(4, 6.4).translate((0, 0, -0.5))
    teller = teller + (zyl(6, 55) - zyl(7, 52).translate((0, 0, -0.5))) + (zyl(9, 10) - zyl(10, 6.4).translate((0, 0, -0.5)))
    return fuss, teller


def pinsel(n=10):
    k = M.cube((n * 14 + 6, 40, 30))
    loch = [zyl(60, 3.6, seg=24).rotate((-15, 0, 0)).translate((10 + i * 14, 14, 3)) for i in range(n)]
    rinne = M.cube((n * 14 - 4, 12, 20)).translate((5, 26, 18))
    return k - M.batch_boolean(loch, OpType.Add) - rinne


def griffbank(n=6):
    k = M.cube((n * 38 + 6, 44, 20)); loch = [zyl(30, 15.5).translate((22 + i * 38, 22, 4)) for i in range(n)]
    return k - M.batch_boolean(loch, OpType.Add)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("teile", nargs="*"); ap.add_argument("--aus", default=os.path.join(ROOT, "modelle/stl/malwerkzeug")); a = ap.parse_args()
    os.makedirs(a.aus, exist_ok=True); alle = ["griff", "griff_klemme", "flaschen", "drehteller", "pinsel", "griffbank"]; rc = 0
    for t in (a.teile or alle):
        r = globals()[t](); r = r if isinstance(r, tuple) else (r,)
        for k, m in enumerate(r):
            name = f"mal_{t}" + (f"_{k + 1}" if len(r) > 1 else ""); f = os.path.join(a.aus, name + ".stl"); stl_schreiben(m, f, b"rcpark malwerkzeug")
            tm = trimesh.load(f); bb = tm.bounds; ok = tm.is_watertight and len(tm.split()) == 1
            print(f"{'ok ' if ok else 'FEHLER'} {name}: {bb[1][0]-bb[0][0]:.0f} x {bb[1][1]-bb[0][1]:.0f} x {bb[1][2]-bb[0][2]:.0f} mm, {tm.volume/1000:.1f} cm3, Stuecke {len(tm.split())}")
            rc |= 0 if ok else 3
    return rc


if __name__ == "__main__":
    sys.exit(main())
