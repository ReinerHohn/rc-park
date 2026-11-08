#!/usr/bin/env python3
"""kamera_profil.py - eigenes Handy EINMAL kalibrieren (Brennweite, Hauptpunkt, Verzeichnung) per ChArUco-Tafel (OpenCV, Apache-2.0), 2026-11-05.

Wozu: eigene Handyfotos (feste 1x-Hauptlinse) als Zusatzquelle der Pipeline; mit bekanntem Kameraprofil muss SfM die Linse nicht je Gebaeude schaetzen.
  vorlage:  kamera_profil.py vorlage <png>              -> Tafel 11x8 Felder zum Anzeigen auf einem Bildschirm (Vollbild) oder Ausdrucken
  rechnen:  kamera_profil.py rechnen <ordner> <profil.json> [--feld-mm X]
            ~20 Fotos der Tafel aus verschiedenen Winkeln/Abstaenden, Tafel auch in den Bildecken; Feldgroesse in mm am Bildschirm/Ausdruck
            messen (fuer Brennweite/Verzeichnung genuegt jede Groesse, Massstab der Tafel geht nicht ein).
Profil: fx, fy, cx, cy, k1, k2, p1, p2, k3, Bildgroesse, Reprojektionsfehler (px), Kameramodell (EXIF Make/Model), Anzahl Fotos.
Tor: Reprojektionsfehler <= 1,0 px und >= 12 Fotos mit >= 20 Ecken, sonst Exit 1 (Profil nicht geschrieben).
"""
import sys, os, json, glob, argparse
import numpy as np, cv2

SPALTEN, ZEILEN, WOERTERBUCH = 11, 8, cv2.aruco.DICT_5X5_100


def tafel(feld=1.0):
    d = cv2.aruco.getPredefinedDictionary(WOERTERBUCH); return cv2.aruco.CharucoBoard((SPALTEN, ZEILEN), feld, feld * 0.75, d), d


def exif_kamera(p):
    try:
        import PIL.Image, PIL.ExifTags
        e = PIL.Image.open(p).getexif(); t = {PIL.ExifTags.TAGS.get(k, k): v for k, v in e.items()}; return f"{t.get('Make', '?')} {t.get('Model', '?')}".strip()
    except Exception: return "?"


def main(argv=None):
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    v = sp.add_parser("vorlage"); v.add_argument("png"); v.add_argument("--px", type=int, default=2200)
    r = sp.add_parser("rechnen"); r.add_argument("ordner"); r.add_argument("profil"); r.add_argument("--feld-mm", type=float, default=20.0)
    a = ap.parse_args(argv)
    if a.cmd == "vorlage":
        b, _ = tafel(); img = b.generateImage((a.px, int(a.px * ZEILEN / SPALTEN)), marginSize=60); cv2.imwrite(a.png, img); print(f"Vorlage {a.png} ({SPALTEN}x{ZEILEN} Felder)"); return
    b, d = tafel(a.feld_mm / 1000.0); det = cv2.aruco.CharucoDetector(b)
    fotos = sorted(sum((glob.glob(os.path.join(a.ordner, e)) for e in ("*.jpg", "*.JPG", "*.jpeg", "*.png", "*.heic")), []))
    obj_p, img_p, groesse, genutzt = [], [], None, []
    for p in fotos:
        im = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if im is None: continue
        if groesse is None: groesse = im.shape[::-1]
        if im.shape[::-1] != groesse: print(f"  {os.path.basename(p)}: andere Bildgroesse {im.shape[::-1]} - uebersprungen (Zoom/Linse gewechselt?)"); continue
        cc, ci, _, _ = det.detectBoard(im)
        if ci is None or len(ci) < 20: print(f"  {os.path.basename(p)}: {0 if ci is None else len(ci)} Ecken - zu wenig"); continue
        op, ip = b.matchImagePoints(cc, ci); obj_p.append(op); img_p.append(ip); genutzt.append(os.path.basename(p))
    if len(obj_p) < 12: raise SystemExit(f"nur {len(obj_p)} brauchbare Fotos (>= 12 noetig)")
    rms, K, dist, _, _ = cv2.calibrateCamera(obj_p, img_p, groesse, None, None)
    dist = dist.ravel().tolist() + [0.0] * 5
    prof = dict(kamera=exif_kamera(os.path.join(a.ordner, genutzt[0])), bild=list(groesse), fx=K[0, 0], fy=K[1, 1], cx=K[0, 2], cy=K[1, 2],
                k1=dist[0], k2=dist[1], p1=dist[2], p2=dist[3], k3=dist[4], reprojektion_px=round(float(rms), 3), fotos=len(genutzt), quelle="kamera_profil.py ChArUco (OpenCV calibrateCamera)")
    print(json.dumps(prof, indent=1))
    if rms > 1.0: raise SystemExit(f"Reprojektionsfehler {rms:.2f} px > 1,0 - Profil NICHT geschrieben (unscharfe Fotos? Tafel gewoelbt?)")
    json.dump(prof, open(a.profil, "w"), indent=1); print(f"Profil -> {a.profil}")


if __name__ == "__main__":
    main()
