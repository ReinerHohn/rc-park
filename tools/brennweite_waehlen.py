#!/usr/bin/env python3
"""brennweite_waehlen.py - Pixel-Brennweite eines Einzelfotos aus EXIF herleiten und durch das Foto-GPS absichern (18.11.2026).
Anlass Martinstor K-061: EXIF 9,855 mm, Bild 3601x2757 statt Original 4000x3000 -> ob nur beschnitten (f = mm/Sensor x 4000 = 5187 px) oder verkleinert (4669 px) war offen;
die freie Brennweite im Loeser lief auf 52 km davon, weil Fernfotos mit fast ebenen Picks Brennweite und Abstand nicht trennen. Die Bildpunkte allein legen f nicht fest (Fehler 4,0-4,2 px
fuer f 3500-6000), der Abstand waechst ~ proportional zu f - also hilft nur eine unabhaengige Groesse: das GPS der Kamera.
Ablauf: (1) EXIF lesen: Brennweite mm, Kleinbild-Aequivalent (-> Sensorbreite, kein Tabellenwissen noetig), Bildgroesse, GPS. (2) Kandidaten: bevorzugt aus der Pixelgroesse (FocalPlaneXResolution; f = mm x Pixel/mm gilt bei nur beschnittenem Bild,
sonst mal W/Originalbreite), ersatzweise aus f35 (Sensorbreite) mit aktueller oder gaengiger Kamerabreite. (3) je Kandidat foto_kalibrieren laufen lassen, den horizontalen Abstand Kamera-Objekt mit dem GPS-Abstand vergleichen,
den besten nehmen. Ohne GPS: kleinste Abweichung nicht moeglich -> Kandidat 'aktuelle Breite', als ANNAHME markiert. Toleranz max(15 %, 30 m) wegen GPS-Genauigkeit; innerhalb gewinnt der erste (direkteste) Kandidat, ausserhalb keine Auswahl (rc 3).
Schreibt brennweite_px/brennweite_frei=False/brennweite_quelle in K-<foto>.json (Original wird als .vor_brennweite gesichert).
Aufruf: python3 tools/brennweite_waehlen.py modelle/<objekt>/objekt.json <foto-nr> --lat 47.9937 --lon 7.8489 [--nur-pruefen]"""
import sys, os, json, math, glob, shutil, subprocess, argparse
from PIL import Image
NATIV_BREITEN = (1600, 2048, 2272, 2592, 2816, 3000, 3072, 3264, 3456, 3648, 3872, 4000, 4032, 4160, 4288, 4608, 5184, 5472, 6000, 6240, 6720)


def _rat(v):
    try: return float(v)
    except Exception: return float(v[0]) / float(v[1]) if isinstance(v, tuple) else None


def exif_lesen(pfad):
    """dict: f_mm, f35, breite, hoehe, modell, gps (lat, lon, hoehe) oder None."""
    im = Image.open(pfad); ex = im.getexif(); sub = ex.get_ifd(0x8769); g = ex.get_ifd(0x8825); d = dict(breite=im.size[0], hoehe=im.size[1], modell=str(ex.get(0x0110, "")), f_mm=None, f35=None, gps=None)
    if 0x920A in sub: d["f_mm"] = _rat(sub[0x920A])
    if 0xA405 in sub and sub[0xA405]: d["f35"] = float(sub[0xA405])
    d["px_je_mm"] = None                                                    # Pixelgroesse des Sensors: FocalPlaneXResolution (Einheit 2 = Zoll, 3 = cm, 4 = mm)
    if 0xA20E in sub and sub.get(0xA210, 2) in (2, 3, 4): d["px_je_mm"] = _rat(sub[0xA20E]) / {2: 25.4, 3: 10.0, 4: 1.0}[sub.get(0xA210, 2)]
    if g and 2 in g and 4 in g:
        dms = lambda t, ref: (sum(_rat(x) / 60 ** i for i, x in enumerate(t))) * (-1 if ref in ("S", "W") else 1)
        d["gps"] = (dms(g[2], g.get(1, "N")), dms(g[4], g.get(3, "E")), _rat(g[6]) if 6 in g else None)
    return d


def sensorbreite_mm(d):
    """Sensorbreite aus f_mm und Kleinbild-Aequivalent (Diagonale 43,27 mm), Seitenverhaeltnis aus dem Bild; None, wenn nicht herleitbar."""
    if not (d["f_mm"] and d["f35"]): return None
    diag = 43.27 * d["f_mm"] / d["f35"]; a = max(d["breite"], d["hoehe"]) / min(d["breite"], d["hoehe"]); return diag * a / math.hypot(a, 1.0)


def kandidaten(d):
    """Liste (Text, Originalbreite, f_px). Bevorzugt die Pixelgroesse aus FocalPlaneXResolution (Canon u. a.): f_px = f_mm * Pixel/mm gilt, wenn das Bild nur BESCHNITTEN ist; war es von einer
    Originalbreite n auf W verkleinert, gilt f_px * W/n. Ohne diese Angabe: Sensorbreite aus f35, f_px = f_mm/Sensor x Breite (Breite = aktuelle oder gaengige Kamerabreite)."""
    W = max(d["breite"], d["hoehe"]); asp = W / min(d["breite"], d["hoehe"])
    folgen = [n for n in NATIV_BREITEN if W < n <= 1.6 * W] if any(abs(asp / x - 1) < 0.004 for x in (4 / 3, 3 / 2, 16 / 9)) else []   # reines Verkleinern erhaelt das Seitenverhaeltnis; sonst wurde beschnitten
    if d["f_mm"] and d["px_je_mm"]:
        f0 = d["f_mm"] * d["px_je_mm"]; return [("nur beschnitten (Pixelgroesse aus FocalPlaneResolution)", W, f0)] + [(f"von {n} px auf {W} px verkleinert", n, f0 * W / n) for n in folgen]
    sm = sensorbreite_mm(d)
    if not sm: return []
    return [("aktuelle Breite (nur verkleinert/unbearbeitet)", W, d["f_mm"] / sm * W)] + [(f"Originalbreite {n} px (nur beschnitten)", n, d["f_mm"] / sm * n) for n in folgen]


def gps_abstand(gps, lat, lon):
    return math.hypot((gps[0] - lat) * 111200.0, (gps[1] - lon) * 111320.0 * math.cos(math.radians(lat)))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("foto"); ap.add_argument("--lat", type=float, required=True); ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--nur-pruefen", action="store_true"); ap.add_argument("--toleranz", type=float, default=0.15); ap.add_argument("--python", default=sys.executable); a = ap.parse_args(argv)
    root = os.path.dirname(os.path.abspath(__file__)).rsplit("/tools", 1)[0]; obj = json.load(open(a.objekt)); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
    fn = glob.glob(os.path.join(root, obj["fotos_dir"], a.foto + "_*"))[0]; d = exif_lesen(fn); kp = os.path.join(od, "messprotokoll", f"K-{a.foto}.json")
    print(f"EXIF: {d['modell']} f={d['f_mm']} mm, f35={d['f35']}, Pixel/mm={d['px_je_mm']}, Bild {d['breite']}x{d['hoehe']}, GPS {d['gps']}")
    cands = kandidaten(d)
    if not cands: print("weder FocalPlaneResolution noch f35 im EXIF: keine Brennweite herleitbar - keine Auswahl"); return 3
    print(f"{len(cands)} Kandidaten")
    if not d["gps"]:
        t, n, f = cands[0]; print(f"kein GPS: nur '{t}' f={f:.0f} px als ANNAHME"); res = [(t, f, None)]
    else:
        gd = gps_abstand(d["gps"], a.lat, a.lon); print(f"GPS-Abstand zum Objekt: {gd:.0f} m"); res = []; orig = open(kp).read()
        try:
            for t, n, f in cands:
                K = json.loads(orig); K["brennweite_px"] = round(f, 1); K["brennweite_frei"] = False; K.pop("kamera", None); json.dump(K, open(kp, "w"), indent=1, ensure_ascii=False)
                r = subprocess.run([a.python, "-W", "ignore", "-I", os.path.join(root, "tools", "foto_kalibrieren.py"), a.objekt, a.foto], capture_output=True, text=True, cwd=root)
                k = json.load(open(kp)).get("kamera")
                if not k: print(f"  f={f:.0f}: Kalibrierung ohne Ergebnis"); continue
                ab = k["abstand_zur_achse"]; res.append((t, f, ab)); print(f"  f={f:.0f} px ({t}): Abstand {ab:.0f} m, RMS {k['rms_px']:.1f} px, Abweichung zum GPS {ab - gd:+.0f} m")
        finally: open(kp, "w").write(orig)
        res = [x for x in res if x[2] is not None]
        if not res: print("keine Kandidatenrechnung gelang"); return 3
        tol = max(a.toleranz * gd, 30.0)                                  # GPS einer Kompaktkamera ist nur auf ~10-30 m genau: innerhalb davon gewinnt der physikalisch direkteste Kandidat (erster)
        ok = [x for x in res if abs(x[2] - gd) <= tol]
        if not ok: print(f"kein Kandidat innerhalb {tol:.0f} m vom GPS-Abstand: keine Auswahl"); return 3
        t, f, ab = ok[0] if res[0] in ok else min(ok, key=lambda x: abs(x[2] - gd))
    print(f"GEWAEHLT: f={f:.0f} px - {t}" + ("" if d["gps"] else " (ANNAHME, kein GPS)"))
    if a.nur_pruefen: return 0
    shutil.copy(kp, kp + ".vor_brennweite"); K = json.load(open(kp)); K["brennweite_px"] = round(f, 1); K["brennweite_frei"] = False; K.pop("kamera", None)
    K["brennweite_quelle"] = f"EXIF {d['f_mm']} mm, Pixelgroesse " + (f"{1000 / d['px_je_mm']:.3f} um (FocalPlaneResolution)" if d["px_je_mm"] else "aus f35-Sensorbreite") + f": {t}; " + (f"GPS-Abstand {gps_abstand(d['gps'], a.lat, a.lon):.0f} m gegen Fit {ab:.0f} m" if d["gps"] else "ANNAHME ohne GPS")
    json.dump(K, open(kp, "w"), indent=1, ensure_ascii=False); print("K-Datei aktualisiert (Original: .vor_brennweite); foto_kalibrieren neu laufen lassen"); return 0


if __name__ == "__main__": sys.exit(main())
