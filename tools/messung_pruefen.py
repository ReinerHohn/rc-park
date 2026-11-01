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

  kamera_tauglich(kam, z_von, z_bis) -> (ok, text)  Darf diese Kamera in dieser Hoehenzone messen (Ankerzone, nicht RMS)?
  pruefe(werte, sigma)        -> (gueltig, text)   werte: {"foto": wert}, sigma: erwartete Unsicherheit je Messung (m)
  Als Programm:  messung_pruefen.py "031=1.22,030=4.54,041=0.04" 0.5
"""
import sys, os, json
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


RAND_M = 2.0          # so weit darf ueber die Ankerzone hinaus gemessen werden (Ankerhoehen streuen selbst um ~1 m)


def kamera_zone(kam):
    """Hoehenbereich, in dem eine geloeste Kamera INTERPOLIERT (= benutzbar ist): von der tiefsten bis zur hoechsten
    Ankerhoehe, plus Rand. foto_kalibrieren.py schreibt 'ankerzone_z' ins Protokoll."""
    z = kam.get("ankerzone_z")
    return (None, None) if not z else (float(z[0]) - RAND_M, float(z[1]) + RAND_M)


def kamera_tauglich(kam, z_von, z_bis, name="Kamera", hart=True):
    """Darf MIT DIESER KAMERA in der Hoehenzone z_von..z_bis gemessen werden?

    Warum nicht einfach der Anker-RMS: der schliesst auch die bewaehrten Strassenkameras aus (K-030: 56,7 px = 1,97 %
    der Bildhoehe - und sie misst trotzdem gut). Der Fehler ist nicht Rauschen, sondern EXTRAPOLATION.
    Ausloeser (2026-11-01): K-060 (Schraegluftbild) hat ALLE Anker bei 41-60 m. Innerhalb dieser Zone gibt sie die
    Tuermchenspitzen auf 0,7 m genau wieder; 20 m tiefer rechnet sie die Oberkante der Westwand (30,5 m) auf 23,8 m -
    6,7 m daneben. tools/fehlteile_finden.py hat sie trotzdem ueber das ganze Bild laufen lassen und sechs 'erfundene
    Teile' bei 33-39 m gemeldet - alle wertlos. Eine aufgeschriebene Lehre reicht nicht; die Sperre muss im Weg stehen."""
    lo, hi = kamera_zone(kam)
    H = (kam.get("bild") or [None, None])[1]; rms = kam.get("rms_px")
    guete = f"Anker-RMS {rms:.1f} px" + (f" = {rms / H * 100:.2f} % der Bildhoehe" if rms and H else "") if rms else "ohne Guetezahl"
    if lo is None:
        return True, f"{name}: keine Ankerzone im Protokoll ({guete}) - Ergebnis gilt als unbestaetigt, bitte neu kalibrieren"
    if lo <= z_von and z_bis <= hi:
        return True, f"{name}: benutzbar fuer z {z_von:.1f}..{z_bis:.1f} m (Ankerzone {lo:.1f}..{hi:.1f} m, {guete})"
    text = (f"{name}: AUSSERHALB DER ANKERZONE. Gemessen werden soll z {z_von:.1f}..{z_bis:.1f} m, Anker tragen nur "
            f"{lo:.1f}..{hi:.1f} m ({guete}). Dort extrapoliert die Loesung - daraus darf kein Mass, kein Fehlteil und "
            f"kein Sollwert werden. Erst Anker IN dieser Hoehenzone picken, dann foto_kalibrieren.py erneut.")
    if hart: raise SystemExit("KAMERA AUSSERHALB IHRER ZONE: " + text)
    return False, text


def main():
    if sys.argv[1] == "kamera":                       # messung_pruefen.py kamera <K-datei.json> <z_von> <z_bis>
        K = json.load(open(sys.argv[2])); zv, zb = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (0.0, 1e9)
        ok, txt = kamera_tauglich(K["kamera"], zv, zb, os.path.basename(sys.argv[2]), hart=False)
        print("  " + txt); sys.exit(0 if ok else 1)
    werte = {k: float(v) for k, v in (s.split("=") for s in sys.argv[1].split(","))}
    gueltig, text = pruefe(werte, float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "Messung")
    print(("  " if gueltig else "  ") + text)
    sys.exit(0 if gueltig else 1)


if __name__ == "__main__":
    main()
