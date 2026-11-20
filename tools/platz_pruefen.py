#!/usr/bin/env python3
"""Platzpruefung vor Laeufen: freie GB auf Root- und Datenplatte. Exit 0 = beide ueber Grenze, Exit 3 sonst."""
import argparse, shutil, sys

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root-min-gb", type=float, default=5)
    p.add_argument("--daten-min-gb", type=float, default=5)   # Nutzer 10.11. abends: Grenze 5 GB (vorher 10)
    p.add_argument("--daten-pfad", default="/media/oem/scan")
    a = p.parse_args()
    ok = True
    for name, pfad, grenze in (("Root", "/", a.root_min_gb), ("Daten", a.daten_pfad, a.daten_min_gb)):
        try:
            frei = shutil.disk_usage(pfad).free / 1e9
        except OSError as e:
            print(f"PLATZ FEHLER: {name} ({pfad}) nicht lesbar: {e}", file=sys.stderr)
            ok = False
            continue
        zu = frei < grenze
        print(f"{name:5s} {pfad}: {frei:6.1f} GB frei (Grenze {grenze:g} GB) {'ZU WENIG' if zu else 'ok'}")
        ok = ok and not zu
    if not ok:
        print("PLATZ ZU KNAPP - Lauf abgebrochen (Exit 3). Platz schaffen, siehe modelle/archiv/STAND_2026-11-06.md G1.", file=sys.stderr)
        return 3
    return 0

if __name__ == "__main__":
    sys.exit(main())
