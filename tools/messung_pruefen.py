#!/usr/bin/env python3
"""messung_pruefen.py - prueft, ob eine Messung ueber mehrere Fotos UEBERHAUPT GUELTIG ist, bevor ihr Ergebnis benutzt wird.

Warum dieses Werkzeug existiert: In dieser Sitzung ist FUENFMAL derselbe Fehler passiert - zwei Dinge verglichen, die nicht
dasselbe messen:
  1. echte Querschnittsflaeche (77 m2) gegen gerasterte Laserzellen (97)
  2. Sollwert aus einem Zonenmittel gegen eine Messung bei EINER Hoehe (11,1-11,9 gegen 12,60)
  3. Foto verdoppelt die freie Halbbreite, Pruefstand nahm beide Seiten (11,74 gegen 12,50)
  4. Mittelwert ueber uneinige Fotos sah aus wie ein Befund (+1,60 und +0,00 ergaben "+0,80 bestaetigt")
  5. "staerkste Kante ueber der Uhr" traf in drei Fotos drei verschiedene Kanten (1,22 / 4,54 / 0,04 m)
Die Lehre stand nach Fall 1 im Register - und ist trotzdem viermal wiedergekommen. Eine aufgeschriebene Lehre reicht nicht;
sie muss ein Werkzeug sein, das NEIN sagt.

Regel: Eine Messung desselben Merkmals in mehreren Fotos ist nur gueltig, wenn ihre Streuung zur angegebenen Unsicherheit passt.
Ist die Streuung groesser, ist die MESSUNG kaputt - nicht das Modell. Dann darf aus ihr kein Befund und kein Sollwert werden.

  pruefe(werte, sigma)        -> (gueltig, text)   werte: {"foto": wert}, sigma: erwartete Unsicherheit je Messung (m)
  Als Programm:  messung_pruefen.py "031=1.22,030=4.54,041=0.04" 0.5
"""
import sys
import numpy as np


def pruefe(werte, sigma, name="Messung"):
    """True, wenn die Streuung der Einzelwerte zur erwarteten Unsicherheit passt (Spanne <= 4*sigma und Standardabweichung <= 1,5*sigma)."""
    v = np.array(list(werte.values()), float)
    if len(v) < 2: return True, f"{name}: nur eine Messung - Streuung nicht pruefbar, Ergebnis gilt als unbestaetigt"
    spanne = float(v.max() - v.min()); sd = float(v.std(ddof=1))
    paare = ", ".join(f"{k}={x:.2f}" for k, x in werte.items())
    if spanne <= 4 * sigma and sd <= 1.5 * sigma:
        return True, f"{name}: GUELTIG ({paare}; Spanne {spanne:.2f} <= {4*sigma:.2f}, Streuung {sd:.2f} <= {1.5*sigma:.2f}) -> Mittel {v.mean():.2f}"
    return False, (f"{name}: MESSUNG UNGUELTIG ({paare}; Spanne {spanne:.2f} > {4*sigma:.2f} oder Streuung {sd:.2f} > {1.5*sigma:.2f}). "
                   f"Die Fotos messen NICHT dasselbe Merkmal - daraus darf kein Befund und kein Sollwert werden. "
                   f"Erst das Messverfahren reparieren (trifft es in jedem Foto dieselbe Kante?), dann erneut messen.")


def plausibel(wert, von, bis, name, einheit=""):
    """Haelt ein Messergebnis gegen einen Erwartungsbereich und BRICHT AB, wenn es unmoeglich ist.
    Jedes Messwerkzeug ruft das auf, BEVOR es ein Ergebnis weitergibt oder in eine Datei schreibt.
    Ausloeser (2026-11-01): luftbild_messen meldete 2712 m2 'Dachflaeche' in einem 3600-m2-Ausschnitt (die Farbmaske
    hatte Baeume und Schatten erfasst) - und das Werkzeug schrieb den daraus berechneten Versatz ungeprueft in objekt.json."""
    if von <= wert <= bis: return wert
    raise SystemExit(f"UNPLAUSIBEL: {name} = {wert:.2f} {einheit}, erwartet {von:g}..{bis:g} {einheit}. "
                     f"Das Messverfahren liefert Unsinn - erst reparieren, kein Ergebnis weitergeben.")


def main():
    werte = {k: float(v) for k, v in (s.split("=") for s in sys.argv[1].split(","))}
    gueltig, text = pruefe(werte, float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "Messung")
    print(("  " if gueltig else "  ") + text)
    sys.exit(0 if gueltig else 1)


if __name__ == "__main__":
    main()
