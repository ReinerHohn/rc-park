#!/usr/bin/env python3
"""relief_trend.py - robuste Ausgleichsebene fuer Hoehenbilder (tools/tiefe_lokal.py, tools/relief_mischen.py). Nur numpy.

Warum (21.11.2026, Schwabentor w01): die Ebene wurde per kleinsten Quadraten ueber ALLE Zellen gelegt. Ein echter Vorsprung (unterste 1,6 m der Wand
+25..40 cm vor der Steinflaeche) zog sie schief: Hoehenbild oben +5, Mitte -8, unten +15 cm, Hub p5-p95 28,8 cm - als waere die Wand geneigt.
Jetzt: Ebene nur aus der Wandflaeche - iterativ beschnitten (Zellen weiter als k * robuste Streuung von der Ebene fallen heraus: Vorspruenge, Ruecksprunge,
Stoerkoerper), Startwert aus Zeilen-/Spaltenmedianen (schon robust). Gueltigkeits-Guard: zu wenig Wandzellen -> Rueckfall auf kleinste Quadrate (Meldung).
"""
import numpy as np


def robuste_ebene(x, y, d, k=2.5, iter_=12, min_anteil=0.3, min_zellen=50):
    """Ebene d ~ c0 * x + c1 * y + c2 durch die Wandflaeche. x, y, d: 1-D-Felder gleicher Laenge (nur gueltige Zellen).
    Rueckgabe (c (3,), drin (bool je Zelle), info dict: robust (bool), anteil_wand, streuung_m)."""
    x = np.asarray(x, np.float64); y = np.asarray(y, np.float64); d = np.asarray(d, np.float64); n = len(d)
    G = np.c_[x, y, np.ones(n)]
    if n < 3: return np.zeros(3), np.ones(n, bool), dict(robust=False, anteil_wand=1.0, streuung_m=0.0, grund="zu wenig Zellen")
    c_lsq = np.linalg.lstsq(G, d, rcond=None)[0]
    if n < min_zellen: return c_lsq, np.ones(n, bool), dict(robust=False, anteil_wand=1.0, streuung_m=float(np.std(d - G @ c_lsq)), grund="zu wenig Zellen")
    # Start: Steigungen aus Medianen je Zeile/Spalte (ein Vorsprung ueber ganze Zeilen kippt den Median der Zeile, aber nicht den Theil-Sen-Schaetzer ueber die Zeilen)
    def steigung(a, b):
        ua = np.unique(np.round(a)); 
        if len(ua) < 3: return 0.0
        idx = np.searchsorted(ua, np.round(a)); m = np.array([np.median(b[idx == i]) for i in range(len(ua))])
        if len(ua) > 400: s_ = np.linspace(0, len(ua) - 1, 400).astype(int); ua, m = ua[s_], m[s_]
        i, j = np.triu_indices(len(ua), 1); return float(np.median((m[j] - m[i]) / (ua[j] - ua[i])))
    c = np.zeros(3); c[0] = steigung(x, d); c[1] = steigung(y, d - c[0] * x); c[2] = float(np.median(d - c[0] * x - c[1] * y))
    drin = np.ones(n, bool); s = 0.0
    for _ in range(iter_):
        r = d - G @ c; s = 1.4826 * float(np.median(np.abs(r - np.median(r[drin]))[drin])) + 1e-4
        neu = np.abs(r - np.median(r[drin])) <= k * s
        if neu.sum() < max(3, min_anteil * n): break
        c_neu = np.linalg.lstsq(G[neu], d[neu], rcond=None)[0]
        fertig = np.array_equal(neu, drin) and np.allclose(c_neu, c); drin = neu; c = c_neu
        if fertig: break
    if drin.sum() < max(3, min_anteil * n):
        return c_lsq, np.ones(n, bool), dict(robust=False, anteil_wand=float(drin.mean()), streuung_m=float(np.std(d - G @ c_lsq)), grund=f"Wandflaeche nur {drin.mean()*100:.0f} % < {min_anteil*100:.0f} %")
    return c, drin, dict(robust=True, anteil_wand=float(drin.mean()), streuung_m=float(s), grund="")
