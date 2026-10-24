#!/usr/bin/env python3
"""test_flat_bench.py — Regression: flache Platte endet GENERELL an der Bruchkante zum Berghang
und überspannt die Innenkurve/den Bergsporn NICHT.

Anlass: die flache Fläche (Talboden/Straße) 'stoppt nicht, wo der Berg in der Innenkurve hochgeht'.
Zwei Ursachen: (1) flach=slope<22° -> Platte wuchs bis zur 22°-Linie den Hang hoch; (2) sie wurde als
vereinfachtes Polygon gerendert -> überspannte die konkave Innenkurve und deckte den Bergsporn mit ab.
Fix: detect_flat_benches liefert MASKEN (enge Neigungsschwelle), terrain_eggcrate rendert sie per
Grid-Clip -> die Platte folgt der echten Flachkante.

Test (reales A3-Fenster als Fixture): die flachen Bänke dürfen fast KEINE steilen Hang-Zellen
enthalten (sonst blutet die Platte den Berg hoch / überspannt den Sporn).

  python3 tools/test_flat_bench.py
"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter
import manmade_edges as mm

MM, NSCALE, VSCALE, BASE = 0.78125, 3.125, 0.85, 12.0
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    Z = np.load(os.path.join(HERE, "testdata", "a3_window_dem.npy")).astype(float)
    Z = np.where(Z < -1000, np.nan, Z)
    if np.isnan(Z).any():
        Z = np.where(np.isnan(Z), np.nanmin(Z), Z)
    wd = Z[::-1]
    cell = MM
    Hfd = gaussian_filter(wd - float(wd.min()), 0.4) * NSCALE * VSCALE + BASE

    # unabhängiges Maß: ECHTE Geländeneigung in Grad (0.25 m DGM), NICHT die Detektor-Metrik
    gy, gx = np.gradient(gaussian_filter(wd, 0.4), 0.25)
    real_slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    benches = mm.detect_flat_benches(Hfd, cell, flat_deg=11.0, min_area_mm2=150.0)
    fails = []

    if not benches:
        fails.append("keine flache Bank erkannt")
    else:
        # über ALLE Bank-Zellen: Anteil, der in Wirklichkeit steil ist (>25°) = Hochbluten/Sporn-Bridge
        allm = np.zeros(Hfd.shape, bool)
        for tup in benches:
            allm |= tup[0]
        steep_frac = float((real_slope[allm] > 25.0).mean())
        p95 = float(np.percentile(real_slope[allm], 95))
        if steep_frac > 0.05:
            fails.append(f"{steep_frac*100:.1f}% der Bank-Zellen sind real steiler als 25° "
                         f"(Platte blutet den Hang hoch / überspannt Sporn; erlaubt <5%)")
        if p95 > 28.0:
            fails.append(f"95%-Neigung der Bank-Zellen = {p95:.0f}° (muss <=28° sein — sonst Hang-Bleed)")
        big = max(benches, key=lambda t: t[0].sum())
        if big[0].sum() * cell * cell < 1000.0:
            fails.append("größte Bank unplausibel klein (<1000 mm²) — Talboden sollte erkannt sein")
        print(f"{len(benches)} flache Bänke, größte {big[0].sum()} px, "
              f"Bank-Zellen real-steil>25°: {steep_frac*100:.1f}%, 95%-Neigung {p95:.0f}°")

    if fails:
        print("FAIL:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("OK — flache Bänke enden an der Bruchkante (kein Hang-Bleed, kein Sporn-Bridge).")


if __name__ == "__main__":
    main()
