#!/usr/bin/env python3
"""Test brennweite_waehlen: Martinstor-061-Fall (Canon A650, 3601x2757 aus 4000x3000, EXIF 9,855 mm, 541,17 Pixel/mm), Seitenverhaeltnis-Regel, GPS-Abstand. Aufruf: python3 tools/test_brennweite_waehlen.py (rc 0 = ok)"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brennweite_waehlen as B
d = dict(breite=3601, hoehe=2757, modell="Canon A650", f_mm=9.855, f35=None, px_je_mm=13745.7044 / 25.4, gps=(47.99337, 7.85564, 309.0))
c = B.kandidaten(d); f = []
f += [] if len(c) == 1 else [f"beschnittenes Bild (Seitenverhaeltnis 1,306) darf nur den Kandidaten 'nur beschnitten' haben, hat {len(c)}"]
f += [] if abs(c[0][2] - 5333) < 3 else [f"f_px {c[0][2]:.1f} statt 5333"]
d2 = dict(d, breite=3648, hoehe=2736); c2 = B.kandidaten(d2); f += [] if len(c2) >= 2 and abs(c2[0][2] - 9.855 * 541.1694672 ) < 1 else ["4:3-Bild: Kandidatenliste mit 'verkleinert' erwartet"]
d3 = dict(d, px_je_mm=None, f35=44.8); c3 = B.kandidaten(d3); f += [] if c3 and abs(B.sensorbreite_mm(dict(d3, breite=4000, hoehe=3000)) - 7.62) < 0.1 else ["Sensorbreite aus f35 falsch"]
g = B.gps_abstand((47.99336812990721, 7.855637670002566, 0), 47.9937139, 7.8489466); f += [] if 495 < g < 505 else [f"GPS-Abstand {g:.0f} statt 500"]
print("\n".join(f) if f else "brennweite_waehlen ok"); sys.exit(1 if f else 0)
