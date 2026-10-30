#!/usr/bin/env python3
"""verify_gorge.py — MESSBARE Prüfung der Einschnitt/Schlucht-Kantenerkennung.
Rendert Hillshade (Draufsicht) + erkannte Platte + ihre Kanten, und MISST objektiv:
  wall_frac = Anteil der Kanten-Länge, der auf echter Steilwand (slope>wall-Perzentil) liegt.
Hoch = die Kanten sitzen auf den realen Schlucht-Rimsen = 'sicher erkannt'.

  python3 tools/verify_gorge.py --wall-pct 70 --no-rim 40 --rim-cap 90 --out /tmp/vg.png
"""
import argparse, numpy as np, cv2, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter
import insert_plate as ip, insert_plates_auto as ipa


def hs(z, c, az=315, alt=45):
    g1, g2 = np.gradient(z, c); sl = np.pi/2 - np.arctan(np.hypot(g1, g2)); asp = np.arctan2(-g1, g2)
    az = np.radians(360-az+90); alt = np.radians(alt)
    return np.clip(np.sin(alt)*np.sin(sl) + np.cos(alt)*np.cos(sl)*np.cos(az-asp), 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--track", default="modelle/hoellental_A3_set/track50.npy")
    ap.add_argument("--wall-pct", type=float, default=70.0)
    ap.add_argument("--flat-pct", type=float, default=45.0)
    ap.add_argument("--no-rim", type=float, default=40.0)
    ap.add_argument("--rim-cap", type=float, default=90.0)
    ap.add_argument("--rdp", type=float, default=4.0)
    ap.add_argument("--band-mm", type=float, default=4.0)   # Toleranz: wie nah an Steilwand = 'auf Rim'
    ap.add_argument("--out", default="/tmp/vg.png")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    class O: pass
    o = O(); o.dem = a.dem; o.r0 = a.r0; o.r1 = a.r1; o.c0 = a.c0; o.c1 = a.c1
    o.zoom = 1; o.mm = 0.78125; o.nscale = 3.125; o.vscale = 0.85; o.base = 12.0; o.smooth = 0.4
    Hf, cell = ip.load_hf(o); NY, NX = Hf.shape
    slope = np.degrees(np.arctan(np.hypot(*np.gradient(gaussian_filter(Hf, 1.0), cell))))
    wall_t = np.percentile(slope, a.wall_pct)
    tr = np.load(a.track).astype(float); track = [list(p) for p in tr]

    poly = ipa.einschnitt_corridor_poly(Hf, cell, track, rim_cap_mm=a.rim_cap, no_rim_mm=a.no_rim,
                                        wall_pct=a.wall_pct, flat_pct=a.flat_pct, rdp_mm=a.rdp)
    if poly is None:
        print("poly None"); return 1

    # Metrik: Anteil Kanten-Länge nah an Steilwand. Steilwand als Distanzfeld.
    wallmask = (slope > wall_t).astype(np.uint8)
    dwall = cv2.distanceTransform(1 - wallmask, cv2.DIST_L2, 5) * cell   # mm bis zur nächsten Wand
    tot = 0.0; onwall = 0.0; samples = []
    for i in range(len(poly) - 1):
        p = poly[i]; q = poly[i + 1]; seg = np.hypot(*(q - p))
        n = max(2, int(seg / (cell)))
        for t in np.linspace(0, 1, n):
            xy = p + (q - p) * t; ci = int(xy[0] / cell); cj = int(xy[1] / cell)
            if 0 <= ci < NX and 0 <= cj < NY:
                near = dwall[cj, ci] <= a.band_mm
                samples.append((xy, near))
                onwall += (seg / n) if near else 0.0
            tot += seg / n
    wall_frac = onwall / max(tot, 1e-9)

    # Render
    U = 4
    zu = gaussian_filter(cv2.resize(Hf, (NX*U, NY*U), interpolation=cv2.INTER_CUBIC), 1.2)
    img = cv2.cvtColor((hs(zu, cell/U)*255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    ys, xs = np.where(cv2.resize(slope, (NX*U, NY*U)) > wall_t)
    img[ys, xs] = (0.7*img[ys, xs] + 0.3*np.array([0, 210, 255])).astype(np.uint8)
    pts = (poly[:, :2]/cell*U).astype(np.int32)
    ov = img.copy(); cv2.fillPoly(ov, [pts], (0, 200, 0)); img = cv2.addWeighted(img, 0.7, ov, 0.3, 0)
    # Kanten: grün=auf Wand, rot=NICHT auf Wand (Fehlstellen sofort sichtbar)
    for xy, near in samples:
        c = (0, 220, 0) if near else (40, 40, 230)
        cv2.circle(img, (int(xy[0]/cell*U), int(xy[1]/cell*U)), 2, c, -1)
    for p in pts:
        cv2.circle(img, tuple(p), 4, (255, 255, 255), -1)
    txt = f"wall_frac={wall_frac*100:.0f}%  (gruen=Kante auf Steilwand, rot=daneben)  wall_pct={a.wall_pct:.0f} no_rim={a.no_rim:.0f}"
    for dy, cc in ((0, (0, 0, 0)), (1, (255, 255, 255))):
        cv2.putText(img, txt, (10, 22+dy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cc, 2 if dy == 0 else 1)
    cv2.imwrite(a.out, img)
    if not a.quiet:
        print(f"wall_frac={wall_frac*100:.1f}%  poly_pts={len(poly)}  area~{abs(sum(poly[i,0]*poly[i+1,1]-poly[i+1,0]*poly[i,1] for i in range(len(poly)-1)))/2:.0f}mm2 -> {a.out}")
    print(f"METRIC wall_frac={wall_frac*100:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
