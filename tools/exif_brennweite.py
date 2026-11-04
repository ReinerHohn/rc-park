#!/usr/bin/env python3
"""exif_brennweite.py - GENERISCH: Brennweite eines Fotos in Pixeln aus EXIF (Prior fuer den Buendelausgleich, Kaufhaus 2026-11-04).

Reihenfolge (erste gueltige Quelle gewinnt):
  1. FocalLengthIn35mmFilm  -> f_px = f35 * Bilddiagonale_px / 43,27
  2. FocalLength + FocalPlaneXResolution (Sensorbreite = Original-Pixelbreite / Aufloesung)
  3. FocalLength + Sensorbreite aus der Kamera-Sensordatenbank (AliceVision cameraSensors.db, MPL-2.0, Kopie auf der Datenplatte)
ANNAHME in allen Faellen: Bild nicht beschnitten (nur verkleinert). Beschnittene Fotos zeigen sich als Ausreisser gegen den Prior;
der Buendelausgleich fuehrt den Prior deshalb robust (Huber), nicht hart.
  python tools/exif_brennweite.py <bild>...      (Ausgabe je Bild: f_px und Quelle)
"""
import sys, os, re, math
from PIL import Image

DB = "/media/oem/scan/rc-park_daten/_kamera/cameraSensors.db"
_db = None


def _tok(s): return [t for t in re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split() if t not in ("digital", "camera")]


def sensorbreite(make, model):
    global _db
    if _db is None:
        _db = []
        if os.path.exists(DB):
            for z in open(DB, encoding="utf-8", errors="ignore"):
                p = z.strip().split(";")
                if len(p) >= 3:
                    try: _db.append((_tok(p[0]), _tok(p[1]), float(p[2])))
                    except ValueError: pass
    mt = [t for t in _tok(model) if t not in _tok(make)]
    nummer = [t for t in mt if re.search(r"\d", t)]
    if not nummer: return None
    best = None
    for mk, md, w in _db:
        if not set(nummer) <= set(md) or not set(mt) <= set(md) | set(mk): continue
        extra = len(set(md) - set(mt) - set(mk))
        if best is None or extra < best[0]: best = (extra, w)
    return best[1] if best else None


def brennweite_px(pfad, breite=None, hoehe=None):
    """(f_px, quelle) im Bild der Groesse breite x hoehe (Standard: Datei), oder (None, grund)."""
    try:
        im = Image.open(pfad); e = im.getexif(); ex = e.get_ifd(0x8769)
    except Exception as x: return None, f"EXIF nicht lesbar ({type(x).__name__})"
    W, H = im.size; bw, bh = breite or W, hoehe or H; kz = bw / W
    f35 = ex.get(41989); fl = ex.get(37386)
    if f35 and float(f35) > 0: return float(f35) * math.hypot(W, H) / 43.27 * kz, f"EXIF FocalLengthIn35mmFilm {float(f35):g} mm"
    if not fl or float(fl) <= 0: return None, "keine Brennweite im EXIF"
    fl = float(fl); xr = ex.get(41486); ein = ex.get(41488, 2); w0 = ex.get(40962)
    if xr and w0 and float(xr) > 0:
        mm = {2: 25.4, 3: 10.0, 4: 1.0}.get(int(ein))
        if mm:
            # FocalPlaneXResolution = Pixel je Laengeneinheit des NATIVEN Sensors; PixelX/YDimension = Groesse des abgelegten (ggf. beschnittenen) Bildes.
            # f_nativ_px = fl * xr / mm, Verkleinerung = Langseite jetzt / Langseite abgelegt -> beschnittfest (Pixelabstand bleibt beim Beschnitt gleich)
            h0 = ex.get(40963) or w0; lang0 = max(float(w0), float(h0)); pitch_um = mm / float(xr) * 1000
            if 0.8 < pitch_um < 12: return fl * float(xr) / mm * max(bw, bh) / lang0, f"EXIF FocalLength {fl:g} mm + FocalPlaneXResolution (Pixelabstand {pitch_um:.2f} um, beschnittfest)"
    sw = sensorbreite(e.get(271), e.get(272))
    if sw: return fl / sw * max(bw, bh), f"EXIF FocalLength {fl:g} mm + Sensordatenbank {str(e.get(272)).strip(chr(0)).strip()} ({sw} mm)"
    return None, f"FocalLength {fl:g} mm, Kamera {str(e.get(272)).strip(chr(0)).strip()!r} nicht in der Sensordatenbank"


if __name__ == "__main__":
    for p in sys.argv[1:]:
        f, q = brennweite_px(p); print(os.path.basename(p), f"{f:.0f} px" if f else "-", q)
