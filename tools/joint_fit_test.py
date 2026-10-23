#!/usr/bin/env python3
"""joint_fit_test.py — ECHTER Steck-Test der Egg-Crate-Rippen (nicht abstrakte Schlitze!).

Erzeugt pro --fit-Wert ZWEI echte Rippen-Stummel mit der REALEN Joint-Geometrie aus
terrain_eggcrate.rib():
  - X-Rippe: Halb-Schlitz von OBEN bis Mitte
  - Y-Rippe: Halb-Schlitz von UNTEN bis Mitte
Beide kreuzend zusammenstecken -> das ist die echte Steck-Passung (Schlitzbreite =
Dicke + fit, inkl. Einführtrichter `flare`). Graviert ist die SCHLITZBREITE in Zehntel
(25 = 2.5 mm, 26 = 2.6 ...). Cutten, Paare stecken, das mit dem gewünschten Spiel ->
dieser --fit kommt dann in terrain_eggcrate.py.

Schnitt-Settings wie der echte Brettlauf (sonst stimmt der Kerf nicht!):
  python3 tools/joint_fit_test.py --thickness 3 --fits -0.5,-0.4,-0.3,-0.2 --passes 4 \
      --feed 150 --power 100 --out /tmp/joint
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain_eggcrate import rib
from laser_relief_kit import glyph_strokes
from laser_calib import emit


def place(poly, ox, oy):
    return [(px + ox, py + oy) for (px, py) in poly]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thickness", type=float, default=3.0)
    ap.add_argument("--fits", default="-0.5,-0.4,-0.3,-0.2",
                    help="Schlitz-Spiel-Werte mm (slotw = Dicke + fit). Negativ = Presssitz, 0 = gleich Dicke")
    ap.add_argument("--L", type=float, default=44.0, help="Rippen-Stummel-Länge mm")
    ap.add_argument("--H", type=float, default=22.0, help="Rippen-Höhe mm")
    ap.add_argument("--flare", type=float, default=0.4, help="Einführtrichter mm/Seite (wie terrain_eggcrate)")
    ap.add_argument("--passes", type=int, default=4)
    ap.add_argument("--feed", type=float, default=150)
    ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--eng-power", type=float, default=85)
    ap.add_argument("--gap", type=float, default=9.0, help="Abstand zwischen Teilen mm")
    ap.add_argument("--out", default="/tmp/joint")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)

    fits = [float(v) for v in a.fits.split(",")]
    hmid = a.H / 2.0
    hs = lambda s: a.H                       # waagerechte Oberkante (Test-Stummel)
    bs = lambda s: 0.0                       # waagerechte Unterkante
    cross = [(a.L / 2.0, hmid)]              # ein Kreuz in der Mitte

    els = []
    x = 10.0
    y_x = 10.0                               # Zeile der X-Rippen (Schlitz oben)
    y_y = y_x + a.H + a.gap                  # Zeile der Y-Rippen (Schlitz unten) darüber
    for fit in fits:
        slotw = a.thickness + fit
        lbl = f"{slotw*10:.0f}"              # 2.5 mm -> "25"
        xr = place(rib(a.L, hs, cross, slotw, True,  bs=bs, flare=a.flare), x, y_x)
        yr = place(rib(a.L, hs, cross, slotw, False, bs=bs, flare=a.flare), x, y_y)
        # Label links der Mitte (weg vom Schlitzmund), auf der Holzfläche
        els.append({"polys": [xr], "passes": a.passes,
                    "engrave": glyph_strokes(lbl, x + 3, y_x + hmid - 2, h=4)})
        els.append({"polys": [yr], "passes": a.passes,
                    "engrave": glyph_strokes(lbl, x + 3, y_y + hmid - 2, h=4)})
        x += a.L + a.gap

    fn = f"{a.out}_joint.gcode"
    emit(fn, els, a.feed, a.power, a.eng_power)
    print(f"JOINT-FIT-TEST: {len(fits)} Paare, Dicke {a.thickness} mm, Schlitze "
          + ", ".join(f"{a.thickness+f:.1f}" for f in fits) + " mm, je {} Durchgänge".format(a.passes))
    print(f"  -> {os.path.abspath(fn)}")
    print("  X-Rippe (Schlitz oben) + Y-Rippe (Schlitz unten) je Paar KREUZEND zusammenstecken.")
    print("  Das Paar mit dem gewünschten Spiel -> dessen --fit (Schlitz − Dicke) ins Gerüst.")


if __name__ == "__main__":
    main()
