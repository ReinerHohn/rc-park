#!/usr/bin/env python3
"""laser_calib.py — Kalibrier-Gcode fuer neues Material am S9.

Zwei Modi (fuer JEDES neue Blatt/Dicke nachfahren, Werte aendern sich mit Material+Kerf):

  pass : mehrere kleine Quadrate, jedes mit ANDERER Durchgangszahl (2/3/4/5),
         graviert beschriftet. Nach dem Lauf: welches faellt sauber raus?
         -> das ist deine Mindest-Durchgangszahl.

  fit  : mehrere Schlitze mit variabler Breite (Standard 2.4/2.6/2.8/3.0 mm),
         alle mit der jetzt bekannten Durchgangszahl geschnitten, beschriftet.
         Danach einen Materialrest (gleiche Dicke) in jeden Schlitz stecken:
         der strammste, der noch reingeht = deine Zielbreite -> --fit = Breite - Dicke.

Schnitt-Startwerte wie Kalibration: 100 %% / 300 mm/min. Gravur 85 %% / 1200.
Ablauf: Blatt an Anschlag-Ecke, `grbl_send.py --frame-only` zum Zielen, dann ohne --mark cutten.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from laser_relief_kit import glyph_strokes


def emit(fn, elements, feed, power, eng_power, eng_feed=1200):
    """elements: [{'polys':[[(x,y)..]], 'passes':n, 'engrave':[strokes]}]"""
    S = int(power*10); ES = int(eng_power*10)
    L = ["G21", "G90", "G17", "M5 S0", "G92 X0 Y0"]

    def trace(poly, close, s, f):
        L.append("M5"); L.append(f"G0 X{poly[0][0]:.2f} Y{poly[0][1]:.2f}"); L.append(f"M4 S{s}")
        for p in poly[1:]:
            L.append(f"G1 X{p[0]:.2f} Y{p[1]:.2f} F{f:.0f}")
        if close:
            L.append(f"G1 X{poly[0][0]:.2f} Y{poly[0][1]:.2f} F{f:.0f}")
        L.append("M5")

    for el in elements:                                   # Gravur zuerst (flach, kratzt nur)
        for st in el.get("engrave", []):
            trace(st, False, ES, eng_feed)
    for el in elements:                                   # dann Schnitte, pro Element eigene Passzahl
        for _ in range(el["passes"]):
            for poly in el["polys"]:
                trace(poly, True, S, feed)
    L += ["M5 S0", "G0 X0 Y0"]
    open(fn, "w").write("\n".join(L)+"\n")


def rect(x, y, w, h):
    return [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["pass", "fit"], required=True)
    ap.add_argument("--passes", type=int, default=3, help="fit-Modus: mit dieser (ermittelten) Durchgangszahl schneiden")
    ap.add_argument("--pass-list", default="2,3,4,5", help="pass-Modus: welche Durchgangszahlen testen")
    ap.add_argument("--widths", default="2.4,2.6,2.8,3.0", help="fit-Modus: Schlitzbreiten mm")
    ap.add_argument("--sq", type=float, default=12.0, help="Quadrat-Kantenlaenge mm")
    ap.add_argument("--feed", type=float, default=300); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--eng-power", type=float, default=85); ap.add_argument("--eng-feed", type=float, default=1200)
    ap.add_argument("--out", default="/tmp/calib")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)

    els = []
    x = 10.0; y = 20.0
    if a.mode == "pass":
        for p in [int(v) for v in a.pass_list.split(",")]:
            els.append({"polys": [rect(x, y, a.sq, a.sq)], "passes": p,
                        "engrave": glyph_strokes(str(p), x+a.sq/2-2, 6, h=6)})
            x += a.sq + 8
        fn = f"{a.out}_pass.gcode"
        emit(fn, els, a.feed, a.power, a.eng_power, a.eng_feed)
        print(f"PASS-TEST: Quadrate {a.pass_list} Durchgaenge, je {a.sq:.0f}mm, 100%/{a.feed:.0f}")
        print(f"  -> {os.path.abspath(fn)}")
        print("  Nach Lauf: welches Quadrat faellt sauber raus = Mindest-Durchgangszahl.")
    else:
        ws = [float(v) for v in a.widths.split(",")]
        sh = 18.0                                          # Schlitzhoehe
        for w in ws:
            els.append({"polys": [rect(x, y, w, sh)], "passes": a.passes,
                        "engrave": glyph_strokes(f"{w:.1f}".replace(".", ""), x-1, 6, h=5)})
            x += 14
        fn = f"{a.out}_fit.gcode"
        emit(fn, els, a.feed, a.power, a.eng_power, a.eng_feed)
        print(f"FIT-TEST: Schlitze {a.widths} mm, je {a.passes} Durchgaenge")
        print(f"  -> {os.path.abspath(fn)}")
        print("  Danach Materialrest (gleiche Dicke) reinstecken: strammster der noch geht = Zielbreite.")
        print(f"  --fit = Zielbreite - Materialdicke (z.B. 2.6 - 3.0 = -0.4).")


if __name__ == "__main__":
    main()
