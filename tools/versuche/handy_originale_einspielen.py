#!/usr/bin/env python3
"""Handy-Originale (per USB, mit GPS) in Fotobestaende einspielen.

Hochgeladene Fotos haben geschwaerztes GPS (Android-Fotoauswahl), Pixel sonst gleich.
- Original passt zu vorhandenem Upload (gleiche Aufnahmesekunde + gleiche Pixel-Miniatur):
  Upload wird durch das Original ersetzt (gleicher Name, GPS zurueck); alter Upload -> Sicherung.
- Sonst: als neues Foto eigen__IMG_<zeit>_usb<n>.jpg in den Bestand kopiert.
Zuordnung zum Objekt per Zeitfenster (--fenster objektordner:HHMM-HHMM, mehrfach).

Aufruf: python -I handy_originale_einspielen.py <original_ordner> <sicherung_ordner>
        --fenster /pfad/schwab_auto/fotos:1520-1559 --fenster /pfad/martinstor-1120/fotos:1600-1659 [--trocken]
"""
import argparse, glob, os, shutil, re, sys
from PIL import Image, ImageChops


def mini(p):
    im = Image.open(p).convert('L')
    im.draft('L', (200, 200))
    return im.resize((64, 48) if im.width > im.height else (48, 64))


def gleich(a, b):
    try:
        ma, mb = mini(a), mini(b)
        if ma.size != mb.size:
            return False
        h = ImageChops.difference(ma, mb).histogram()
        return sum(i * n for i, n in enumerate(h)) / (ma.width * ma.height) < 2.0
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('original'); ap.add_argument('sicherung')
    ap.add_argument('--fenster', action='append', required=True)
    ap.add_argument('--trocken', action='store_true')
    a = ap.parse_args()
    fen = []
    for f in a.fenster:
        d, z = f.rsplit(':', 1); v, b = z.split('-'); fen.append((d, v, b))
    st = {'ersetzt': 0, 'neu': 0, 'ohne_fenster': 0}
    for o in sorted(glob.glob(os.path.join(a.original, 'IMG_*.jpg'))):
        m = re.match(r'IMG_(\d{8})_(\d{6})', os.path.basename(o))
        if not m:
            continue
        tag, zeit = m.groups(); hhmm = zeit[:4]
        ziel = [d for d, v, b in fen if v <= hhmm <= b]
        if not ziel:
            st['ohne_fenster'] += 1; continue
        d = ziel[0]
        kand = [k for k in glob.glob(os.path.join(d, f'eigen__IMG_{tag}_{zeit[:4]}*.jpg'))
                if '_usb' not in k and abs(int(re.search(rf'{tag}_(\d{{6}})', k).group(1)) - int(zeit)) <= 2]
        treffer = [k for k in kand if os.path.getsize(k) == os.path.getsize(o) or gleich(k, o)]
        if treffer:
            k = treffer[0]
            if not a.trocken:
                os.makedirs(a.sicherung, exist_ok=True)
                shutil.copy2(k, os.path.join(a.sicherung, os.path.basename(k)))
                shutil.copyfile(o, k)
            st['ersetzt'] += 1
        else:
            n = 0
            while True:
                z = os.path.join(d, f'eigen__IMG_{tag}_{zeit}_usb{n}.jpg')
                if not os.path.exists(z):
                    break
                n += 1
            if not a.trocken:
                shutil.copyfile(o, z)
            st['neu'] += 1
    print(st)


if __name__ == '__main__':
    main()
