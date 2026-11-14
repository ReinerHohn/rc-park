#!/usr/bin/env python3
"""fotos_pruefen.py <ordner> [--quarantaene DIR] [--nur-liste] - jede Datei oeffnen; nur gueltige Bilder bleiben im Ordner.

Lehre Schwabentor 13.11.2026: eine 0-Byte-Datei (Download-Abbruch) kam in den SfM-Lauf und wurde erst dort als
BITMAP_ERROR sichtbar. Ablauf: Bild oeffnen (PIL verify + Groesse), defekte Dateien NACH quarantaene/ VERSCHIEBEN
(nie loeschen). Ausgabe: Zahl gueltig/defekt, Liste der Defekten. Exit-Code 1, wenn Defekte gefunden und verschoben wurden.
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/fotos_pruefen.py daten/<objekt>/fotos
"""
import os, sys, shutil, argparse
from PIL import Image

def pruefe(pfad):
    """(ok, grund): ok = Bild laesst sich oeffnen und hat > 0 Pixel."""
    try:
        if os.path.getsize(pfad) == 0: return False, "0 Byte"
        with Image.open(pfad) as im:
            im.verify()
        with Image.open(pfad) as im:
            w, h = im.size
        if w * h == 0: return False, "0 Pixel"
        return True, f"{w}x{h}"
    except Exception as e:
        return False, type(e).__name__ + ": " + str(e)[:80]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ordner"); ap.add_argument("--quarantaene", default=None); ap.add_argument("--nur-liste", action="store_true")
    a = ap.parse_args()
    q = a.quarantaene or os.path.join(os.path.dirname(os.path.abspath(a.ordner)), "quarantaene")
    dateien = sorted(f for f in os.listdir(a.ordner) if os.path.isfile(os.path.join(a.ordner, f)))
    defekt = []
    for f in dateien:
        ok, grund = pruefe(os.path.join(a.ordner, f))
        if not ok: defekt.append((f, grund))
    print(f"{len(dateien) - len(defekt)} gueltig, {len(defekt)} defekt von {len(dateien)} in {a.ordner}")
    for f, g in defekt: print("  DEFEKT", f, "-", g)
    if defekt and not a.nur_liste:
        os.makedirs(q, exist_ok=True)
        for f, _ in defekt: shutil.move(os.path.join(a.ordner, f), os.path.join(q, f))
        print("verschoben nach", q)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
