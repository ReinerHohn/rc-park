#!/usr/bin/env python3
"""Platzpruefung vor Laeufen: freie GB auf Root- und Datenplatte. Exit 0 = beide ueber Grenze, Exit 3 sonst."""
import argparse, shutil, sys, os, subprocess
HART_GB = 2.0   # Notgrenze: darunter wirklich abbrechen (Platte liefe voll); Nutzer 28.11.2026: von 5 auf 2 GB gesenkt (bremste die Kette: Lauf 1128c rc 3 bei 4,7 GB)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root-min-gb", type=float, default=15)   # Nutzer 21.11.2026: Mindestplatz ab sofort 15 GB
    p.add_argument("--daten-min-gb", type=float, default=15)   # Nutzer 21.11.2026: 15 GB (vorher 5)
    p.add_argument("--daten-pfad", default="/media/oem/scan")
    p.add_argument("--nicht-aufraeumen", action="store_true")
    a = p.parse_args()
    r = pruefen(a)
    if r and not a.nicht_aufraeumen:   # Nutzer 21.11.2026: "Dann nicht abbrechen, sondern anfangen aufzuraeumen."
        print("PLATZ unter Mindestgrenze -> raeume auf (tools/platz_waechter.sh einmal)", file=sys.stderr)
        subprocess.run(["bash", os.path.join(os.path.dirname(os.path.abspath(__file__)), "platz_waechter.sh"), "einmal"], stdout=sys.stderr)
        r = pruefen(a)
    if r == 1:
        print("PLATZ WARNUNG: unter Mindestgrenze, aber ueber Notgrenze %g GB - Lauf geht weiter, Aufraeumen pruefen" % HART_GB, file=sys.stderr); return 0
    if r == 2:
        print("PLATZ ZU KNAPP (unter Notgrenze %g GB) - Lauf abgebrochen (Exit 3). Platz schaffen (coredumps/journal brauchen sudo)." % HART_GB, file=sys.stderr); return 3
    return 0


def pruefen(a):
    """0 = alles ueber Grenze, 1 = unter Grenze aber ueber HART_GB, 2 = unter HART_GB oder nicht lesbar."""
    st = 0
    for name, pfad, grenze in (("Root", "/", a.root_min_gb), ("Daten", a.daten_pfad, a.daten_min_gb)):
        try:
            frei = shutil.disk_usage(pfad).free / 1e9
        except OSError as e:
            print(f"PLATZ FEHLER: {name} ({pfad}) nicht lesbar: {e}", file=sys.stderr)
            st = 2
            continue
        zu = frei < grenze
        print(f"{name:5s} {pfad}: {frei:6.1f} GB frei (Grenze {grenze:g} GB) {'ZU WENIG' if zu else 'ok'}")
        if zu: st = max(st, 2 if frei < HART_GB else 1)
    return st

if __name__ == "__main__":
    sys.exit(main())
