#!/usr/bin/env python3
"""online_dach_registrieren.py - Webfotos (verschiedene Kameras, EXIF-Brennweite je Bild) ueber den vorhandenen Weg zusatzfotos_registrieren.py
registrieren (2026-11-09, Auftrag Dachluecke). Je Bild EINE eigene Kameragruppe (f aus EXIF bzw. Schaetzung), ohne Aenderung am Werkzeug:
gruppe_von_bild() wird nur in diesem Prozess ersetzt.
Stufen: rein   --orig DIR --herkunft JSON --aus ZIEL [--lang 2400]   (verkleinern, Kameraparameter-JSON ZIEL/kameras_je_bild.json schreiben)
        reg    --stufe vorbereiten|merkmale|registrieren ... wird vom Aufrufer als zusatzfotos_registrieren-Argumente durchgereicht
Aufruf reg: python -I tools/online_dach_registrieren.py reg <zusatzfotos_registrieren-Argumente>
Sensorbreiten (ANNAHME aus Kameramodell, Hersteller/Datenblatt, nicht gemessen): siehe SENSOR_MM."""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SENSOR_MM = {"Canon PowerShot A650 IS": 7.44, "Canon EOS 5D Mark II": 36.0 * 5250 / 5616, "NIKON D3100": 23.1, "PENTAX Optio 50L": 7.18}   # Breite der LANGEN Seite in mm


def rein(argv):
    import argparse
    from PIL import Image
    ap = argparse.ArgumentParser(); ap.add_argument("--orig", required=True); ap.add_argument("--herkunft", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--lang", type=int, default=2400); ap.add_argument("--f-unbekannt", type=float, default=1.0, help="ANNAHME f/lange Seite fuer Bilder ohne EXIF (Archivscans)")
    a = ap.parse_args(argv); os.makedirs(a.aus + "/rein", exist_ok=True); kam = {}; info = {}
    H = {m["datei"]: m for m in json.load(open(a.herkunft))}
    for f in sorted(glob.glob(a.orig + "/od_*.jpg")):
        n = os.path.basename(f)
        try: im = Image.open(f); im.load()
        except Exception: continue
        W, Hh = im.size; ex = im.getexif(); sub = ex.get_ifd(0x8769); fmm = sub.get(37386); mod = " ".join(str(ex.get(k, "")).strip() for k in (272,)).strip()
        lang = max(W, Hh); s = min(1.0, a.lang / lang); im = im.convert("RGB")
        if s < 1: im = im.resize((int(round(W * s)), int(round(Hh * s))), Image.LANCZOS)
        im.save(f"{a.aus}/rein/{n}", quality=95)
        if fmm and mod in SENSOR_MM: f_px = float(fmm) / SENSOR_MM[mod] * lang * s; quelle = f"EXIF {fmm} mm, Sensor {SENSOR_MM[mod]:.2f} mm (ANNAHME Modell {mod})"
        else: f_px = a.f_unbekannt * lang * s; quelle = f"ANNAHME f = {a.f_unbekannt} x lange Seite (kein EXIF)"
        kam[n.replace(".jpg", "")] = dict(f_orig=f_px, k1=0.0, quelle=quelle); info[n] = dict(orig=[W, Hh], skala=s, quelle=quelle, titel=H.get(n, {}).get("titel"))
    json.dump(dict(kameras=kam), open(a.aus + "/kameras_je_bild.json", "w"), indent=1); json.dump(info, open(a.aus + "/rein_info.json", "w"), indent=1, ensure_ascii=False)
    print(len(kam), "Bilder")


def reg(argv):
    import zusatzfotos_registrieren as Z
    def gruppe(n, info, zoom=None): return os.path.splitext(n)[0], "bewertet"
    Z.gruppe_von_bild = gruppe
    Z.main(argv)


if __name__ == "__main__":
    {"rein": rein, "reg": reg}[sys.argv[1]](sys.argv[2:])
