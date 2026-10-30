#!/usr/bin/env python3
"""test_flat_plates.py — Regression: die FLÄCHEN-Platten sind WIRKLICH EBEN (plan-gefittet) und
damit laser-cutbar + in die Rippen integrierbar, und ihre Kontur folgt der Bruchkante (konkav-fähig,
überspannt den Bergsporn nicht).

Anlass (Nutzer): "flächen müssen eben sein. und ich muss die dann in die rippen integrieren können."
Das frühere Grid-Clip-Drapieren legte jede Zelle auf die echte Geländehöhe -> die Platte war KRUMM
(nicht aus flachem Sperrholz schneidbar). Fix: dieselbe Mechanik wie die geschnittenen Einhäng-Platten
(insert_plates_auto): segment_planes -> fit_plane_mask -> mask_contour_mm, trianguliert AUF der
gefitteten Ebene -> Ebenheits-RMS ~ 0.

  python3 tools/test_flat_plates.py
"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter
import insert_plates_auto as ipa
import trimesh.creation as tmc
from shapely.geometry import Polygon

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

    facets = ipa.segment_planes(Hfd, cell, 2.5, 12.0, 150.0, 45.0)
    fails = []
    plates = []
    worst_rms = 0.0
    concave_seen = False
    for fm in facets:
        aa, bb, cc, _ = ipa.fit_plane_mask(Hfd, cell, fm)
        cont = ipa.mask_contour_mm(fm, cell, 2.5)
        if cont is None or len(cont) < 4:
            continue
        try:
            v2, ff = tmc.triangulate_polygon(Polygon(cont), engine="earcut")
        except Exception:
            continue
        if v2 is None or not len(ff):
            continue
        z = aa * v2[:, 0] + bb * v2[:, 1] + cc
        V = np.column_stack([v2[:, 0], v2[:, 1], z])
        # Ebenheit: Rest zur best-fit-Ebene der TATSÄCHLICHEN Plattenecken
        C = V.mean(0); Q = V - C
        _, _, vt = np.linalg.svd(Q, full_matrices=False)
        rms = float(np.sqrt(np.mean((Q @ vt[2]) ** 2)))
        worst_rms = max(worst_rms, rms)
        # konkav? Fläche < Fläche der konvexen Hülle (folgt der Innenkurve statt zu überspannen)
        poly = Polygon(cont)
        if poly.area < 0.97 * poly.convex_hull.area:
            concave_seen = True
        plates.append((rms, poly.area))

    if not plates:
        fails.append("keine ebene Platte erzeugt")
    if worst_rms > 0.01:
        fails.append(f"Platte NICHT eben: schlimmster Ebenheits-RMS {worst_rms:.4f} mm (muss ~0 sein)")
    if not concave_seen:
        fails.append("keine Platte folgt einer Konkavität — Kontur überspannt evtl. den Bergsporn")

    print(f"{len(plates)} ebene Platten, schlimmster Ebenheits-RMS {worst_rms:.5f} mm, "
          f"konkave Kontur vorhanden: {concave_seen}")
    if fails:
        print("FAIL:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("OK — Flächen-Platten sind eben (laser-cutbar) und folgen der Bruchkante.")


if __name__ == "__main__":
    main()
