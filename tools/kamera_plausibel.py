#!/usr/bin/env python3
"""kamera_plausibel.py [modelle/<objekt> ...] [--beiseite] - EINE Regel fuer "kann diese Kamera stimmen?", von allen Werkzeugen benutzt, die K-Dateien schreiben.

Anlass 16.11.2026: 49 Kameras mit Standort bis 350 000 km und Brennweite bis 1,7e10 px (Abstand und Zoom sind bei fast ebenen Punkten nicht trennbar; der Ausgleich
laeuft "zum Mond"). Sie liessen das Fassadenbild stundenlang auf einem Kern haengen. Regel: Standort endlich, hoechstens `max_m` vom Bezugspunkt, Brennweite 0,3 bis 12 x Bildbreite.
Aufruf als Programm: prueft alle K-*.json der genannten Objektordner (ohne Angabe: alle), rc 3 bei Funden; --beiseite benennt sie in .unplausibel um (nichts wird geloescht).
Grenze: findet nur GROBE Ausreisser. Eine Kamera, die 50 m falsch steht, erkennt nur der Vergleich mit dem Foto (umriss_tor.py, modell_neben_foto.py).
"""
import sys, os, json, glob, numpy as np


def plausibel(f_px, bild_wh, standort, bezug=None, max_m=1500.0):
    """-> (ok, grund). bild_wh = (W, H) oder None (dann 2 x Hauptpunkt uebergeben); bezug = Punkt am Objekt (Standard Ursprung)."""
    C = np.asarray(standort, float); b = float(max(bild_wh)) if bild_wh else None
    if not np.isfinite(C).all() or not np.isfinite(f_px): return False, "Standort/Brennweite nicht endlich"
    d = float(np.linalg.norm(C - (np.zeros(3) if bezug is None else np.asarray(bezug, float))))
    if d > max_m: return False, f"Standort {d:.0f} m vom Objekt (> {max_m:.0f} m)"
    if b and not (0.3 * b <= f_px <= 12 * b): return False, f"Brennweite {f_px:.0f} px bei {b:.0f} px Bildbreite (erlaubt 0,3 bis 12 x)"
    return True, ""


def datei_pruefen(pfad):
    import cv2
    k = json.load(open(pfad)).get("kamera")
    if not isinstance(k, dict) or "rvec" not in k: return True, ""
    C = -cv2.Rodrigues(np.array(k["rvec"], float))[0].T @ np.array(k["t"], float); wh = k.get("bild") or ([2 * k["cx"], 2 * k["cy"]] if "cx" in k else None)
    return plausibel(k["f_px"], wh, C)


def main():
    arg = [x for x in sys.argv[1:] if not x.startswith("--")]; root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); n = 0
    for od in (arg or sorted(glob.glob(os.path.join(root, "modelle", "*")))):
        for f in sorted(glob.glob(os.path.join(od, "messprotokoll", "K-*.json"))):
            try: ok, g = datei_pruefen(f)
            except Exception as e: ok, g = False, f"nicht lesbar ({str(e)[:50]})"
            if not ok:
                n += 1; print(f"{os.path.basename(od)}/{os.path.basename(f)[:44]}: {g}")
                if "--beiseite" in sys.argv: os.rename(f, f + ".unplausibel")
    print(f"{n} unplausible Kamera(s)"); return 3 if n else 0


if __name__ == "__main__":
    sys.exit(main())
