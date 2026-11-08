#!/usr/bin/env python3
"""paarvorwahl.py - GPS-Vorwahl fuer Bildpaare (2026-11-06). Reine Funktionen, nur numpy/PIL, kein torch/pycolmap.

Zweck: die quadratische grobe Matching-Stufe von zusatzfotos_lightglue.py (Zusatz x Referenz, Zusatz x Zusatz) verkleinern.
Regel (konservativ, Handy-GPS in Altstadtgassen ist 5-20 m ungenau): ein Paar entfaellt NUR, wenn BEIDE Bilder GPS haben UND der Abstand
groesser als der Radius ist. Fehlt GPS bei einem Bild, bleibt das Paar immer. Ohne Radius (0/None) aendert sich nichts.
ANNAHME: Radius so gross waehlen, dass auch Turm-oben-Aufnahmen (hoeher, seitlich versetzt) und Gassenfotos Partner behalten; Wert kommt vom Aufrufer.
Lizenz: nur eigener Code (numpy BSD, Pillow HPND).
"""
import math


def gps_aus_exif(pfad):
    """(breite, laenge) in Grad aus EXIF oder None."""
    try:
        from PIL import Image
        g = Image.open(pfad).getexif().get_ifd(0x8825)
        if not g or 2 not in g or 4 not in g: return None
        def grad(t, ref):
            v = float(t[0]) + float(t[1]) / 60.0 + float(t[2]) / 3600.0
            return -v if ref in ("S", "W") else v
        la = grad(g[2], g.get(1, "N")); lo = grad(g[4], g.get(3, "E"))
        return None if (la == 0 and lo == 0) else (la, lo)
    except Exception:
        return None


def abstand_m(p, q):
    """Grosskreis-Abstand in Metern (Haversine)."""
    la1, lo1, la2, lo2 = map(math.radians, (p[0], p[1], q[0], q[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000.0 * math.asin(min(1.0, math.sqrt(h)))


def gps_filter(paare, gps, radius_m):
    """paare: Liste (x, y); gps: dict name -> (breite, laenge) (fehlende Namen = kein GPS). Rueckgabe (behalten, Statistik)."""
    if not radius_m or radius_m <= 0:
        return list(paare), dict(vorher=len(paare), nachher=len(paare), entfernt=0, ohne_gps=0)
    keep = []; ohne = 0
    for x, y in paare:
        a, b = gps.get(x), gps.get(y)
        if a is None or b is None: ohne += 1; keep.append((x, y)); continue
        if abstand_m(a, b) <= radius_m: keep.append((x, y))
    return keep, dict(vorher=len(paare), nachher=len(keep), entfernt=len(paare) - len(keep), ohne_gps=ohne)
