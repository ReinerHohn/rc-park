#!/usr/bin/env python3
"""test_ortho_vergleich.py - zwei Ausgabeordner von fassade_ortho.py bildweise vergleichen (17.11.2026, fuer Beschleunigungen "bei gleichem Ergebnis").

  /media/oem/scan/venv-seg/bin/python -I tools/test_ortho_vergleich.py <referenz> <neu> [--muster 'ortho_f*.png'] [--alle] [--max-stufe 1] [--max-anteil 0.001]
Je Bild: Anzahl abweichender Werte, groesste Abweichung (Graustufen). Fehlende/zusaetzliche Dateien und andere Bildgroessen zaehlen als Fehler.
--alle = alle PNG rekursiv (auch abdeckung/relief/struktur/uneinig und die Einzelbilder). rc 0 = innerhalb der Grenzen, rc 1 = nicht.
"""
import os, sys, glob, argparse
import numpy as np, cv2


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("ref"); ap.add_argument("neu"); ap.add_argument("--muster", default="ortho_f*.png"); ap.add_argument("--alle", action="store_true")
    ap.add_argument("--max-stufe", type=int, default=1); ap.add_argument("--max-anteil", type=float, default=0.001); ap.add_argument("--leise", action="store_true")
    a = ap.parse_args(argv)
    def liste(d): return sorted(os.path.relpath(p, d) for p in (glob.glob(os.path.join(d, "**", "*.png"), recursive=True) if a.alle else glob.glob(os.path.join(d, a.muster))))
    R, N = liste(a.ref), liste(a.neu); fehler = 0; werte = 0; anders = 0; gmax = 0; gleich = 0
    for f in sorted(set(R) ^ set(N)): print(f"  FEHLT in {'neu' if f in R else 'referenz'}: {f}"); fehler += 1
    for f in sorted(set(R) & set(N)):
        x = cv2.imread(os.path.join(a.ref, f), cv2.IMREAD_UNCHANGED); y = cv2.imread(os.path.join(a.neu, f), cv2.IMREAD_UNCHANGED)
        if x is None or y is None or x.shape != y.shape or x.dtype != y.dtype: print(f"  ANDERE FORM {f}: {None if x is None else x.shape} / {None if y is None else y.shape}"); fehler += 1; continue
        d = np.abs(x.astype(np.int64) - y.astype(np.int64)); n = int((d > 0).sum()); mx = int(d.max()) if d.size else 0
        werte += d.size; anders += n; gmax = max(gmax, mx); gleich += n == 0
        if n and not a.leise: print(f"  {f}: {n} von {d.size} Werten anders ({n / d.size:.5%}), groesste Abweichung {mx}")
    ant = anders / max(werte, 1); gut = fehler == 0 and len(R) > 0 and gmax <= a.max_stufe and ant < a.max_anteil
    print(f"VERGLEICH {len(set(R) & set(N))} Bilder, {gleich} bitgleich, {anders} von {werte} Werten anders ({ant:.5%}), groesste Abweichung {gmax}, Dateifehler {fehler} -> {'GLEICH' if gut else 'ABWEICHUNG'}")
    return 0 if gut else 1


if __name__ == "__main__":
    sys.exit(main())
