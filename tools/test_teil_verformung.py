#!/usr/bin/env python3
"""Synthetischer Test teil_verformung.py (Sekunden): Feldauswertung (Trend / Sprung / starr), Wandrichtung aus projizierten waagerechten 3D-Kanten,
Rundgang-Koordinate."""
import os, sys
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import teil_verformung as TV


def main():
    rng = np.random.default_rng(3); n = 120; u1 = rng.uniform(-0.5, 0.5, n); u2 = rng.normal(0, 0.1, n); neig = rng.uniform(0, 40, n); rausch = rng.normal(0, 0.5, n)
    f = TV.feld(u1, u2, neig, rausch); assert f["urteil"] == "starr", f
    f = TV.feld(u1, u2, neig, rausch + 3.0 * u1); assert f["urteil"] == "trend" and abs(f["je_teil_laenge_grad"] - 3.0) < 0.4, f
    f = TV.feld(u1, u2, neig, rausch + 1.0 * u1); print("1 Grad Biegung:", f["urteil"], f["trend_grad"], "t", f["t"])
    k = TV.feld(u1, u2, neig, rausch + np.where(u1 > 0.2, 10.0, 0.0)); assert k["urteil"] == "sprung" and k["gruppen_knick"], k
    v = TV.feld(u1, u2, neig, rausch + np.where(rng.random(n) < 0.1, 10.0, 0.0)); assert not v["gruppen_knick"], v      # verstreute Ausreisser: kein Knick
    print("OK Feld: starr / Trend 3 Grad / Sprung 10 Grad mit Gruppenknick / Ausreisser ohne Knick")
    # Wandrichtung: Kamera blickt waagerecht nach +y, Welt z oben; waagerechte Kanten in Richtung 30 Grad und 120 Grad auf einer Wand bei y = 10
    f_, cx, cy = 1000.0, 960.0, 540.0; Rcw = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float); C = np.zeros(3); m = np.array([0, 0, 1.0])
    L = []
    for w in (30.0, 120.0):
        d = np.array([np.cos(np.radians(w)), np.sin(np.radians(w)), 0])
        for z in np.linspace(-2, 3, 8):
            for x0 in (-3, 0, 3):
                P0 = np.array([x0, 10, z]); P1 = P0 + 1.5 * d; p = []
                for X in (P0, P1):
                    xc = Rcw @ (X - C); p += [f_ * xc[0] / xc[2] + cx, f_ * xc[1] / xc[2] + cy]
                L.append(p)
    wink, ant, nk = TV.wand_winkel(np.array(L), Rcw, f_, cx, cy, m, np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
    assert wink is not None and abs(((wink - 30) + 45) % 90 - 45) < 0.2, (wink, ant, nk); print(f"OK Wandrichtung {wink:.2f} (soll 30 mod 90), Gipfelanteil {ant:.2f}")
    # Rundgang: Kameras auf einem Bogen 0-120 Grad um den Ursprung -> u1 laeuft mit dem Azimut
    a = np.radians(np.linspace(0, 120, 50)); Cc = np.c_[20 * np.cos(a), 20 * np.sin(a), np.zeros(50)]
    u, _, art, sp = TV.ort_koordinate(Cc, np.zeros(3), m); assert art == "bogen" and np.all(np.diff(u) > 0) and abs(u[-1] - u[0] - 1 / 0.9) < 0.05, (art, u[:3], u[-1] - u[0])
    print("OK Rundgang-Koordinate"); print("ALLE OK")


if __name__ == "__main__": main()
