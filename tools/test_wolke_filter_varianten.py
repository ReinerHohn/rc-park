#!/usr/bin/env python3
"""Synthetik-Test fuer wolke_kennzahlen.py + wolke_filter_varianten.f3_filter (Schwellen werden HIER festgelegt, nicht am Kaufhaus).
Szene: Wand (x=0, 12 m breit, 8 m hoch) mit 3 cm Gauss-Rauschen und Ziegel/Putz-Farbe, eine 20-cm-Stufe (Pilaster) als echte Kante,
Boden, 3 % Ausreisser in der Luft vor der Wand (1..3 m), ein 'Person'-Cluster mit anderer Farbe (nicht entfernbar: reale Flaeche).
Pruefungen: Kennzahl p50 ~ 0,6745*sigma; F3 senkt p50 (>=30 %), entfernt >=80 % der Luftausreisser, behaelt >=97 % der Wandpunkte, Stufenkante bleibt (Stufe >= 15 cm nach Filter)."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolke_kennzahlen as WK, wolke_filter_varianten as WF


def szene(seed=0, sig=0.03):
    r = np.random.default_rng(seed); n = 250000
    u = r.uniform(-6, 6, n); z = r.uniform(0, 8, n); x = np.where((u > 1) & (u < 2.5), 0.20, 0.0) + r.normal(0, sig, n)          # Pilaster 20 cm vor der Wand
    P = np.c_[x, u, z]; N = np.tile([1.0, 0, 0], (n, 1)); N += r.normal(0, 0.08, N.shape); col = np.where((u[:, None] > 1) & (u[:, None] < 2.5), [170, 150, 120], [200, 190, 170]).astype(float) + r.normal(0, 6, (n, 3))
    ob = 7500; lu = np.c_[r.uniform(1, 3, ob), r.uniform(-6, 6, ob), r.uniform(0, 8, ob)]; Pl = np.c_[lu]; Nl = r.normal(size=(ob, 3)); cl = r.integers(0, 255, (ob, 3)).astype(float)
    return np.r_[P, Pl], np.r_[N, Nl], np.clip(np.r_[col, cl], 0, 255).astype(np.uint8), n


def main():
    P, N, C, n = szene(); cam = np.array([20.0, 0, 3.0]); E = WK.ebenen_ransac(P, None, cam, n_max=1, zmin=0.5, min_anteil=0.1)
    assert len(E) == 1 and abs(E[0]["n"][0]) > 0.99, E
    k0 = WK.kennzahlen(P, E)[0]; print("roh", k0)
    assert 1.5 < k0["rausch_p50_cm"] < 3.0, "p50 muss ~0,6745*3 cm liegen (Pilaster leicht erhoeht)"
    keep, Pn = WF.f3_filter(P, N, C); Pf = Pn[keep]; k1 = WK.kennzahlen(Pf, E)[0]; print("f3", k1)
    luft = (np.arange(len(P)) >= n); print("Luft entfernt", (~keep[luft]).mean(), "Wand behalten", keep[~luft].mean())
    assert (~keep[luft]).mean() >= 0.80 and keep[~luft].mean() >= 0.97
    assert k1["rausch_p50_cm"] <= 0.7 * k0["rausch_p50_cm"], "Rauschen nicht genug gesenkt"
    a = Pf[(Pf[:, 1] > 1.2) & (Pf[:, 1] < 2.3) & (Pf[:, 2] > 1) & (Pf[:, 2] < 7) & (Pf[:, 0] > -0.5) & (Pf[:, 0] < 0.7)][:, 0]; b = Pf[(Pf[:, 1] < 0.5) & (Pf[:, 1] > -5) & (Pf[:, 2] > 1) & (Pf[:, 2] < 7) & (Pf[:, 0] > -0.5) & (Pf[:, 0] < 0.7)][:, 0]
    stufe = np.median(a) - np.median(b); print("Stufe nach Filter", stufe); assert stufe >= 0.15
    print("OK")


if __name__ == "__main__": main()
