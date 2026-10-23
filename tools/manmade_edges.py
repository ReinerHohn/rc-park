#!/usr/bin/env python3
"""manmade_edges.py — menschgemachte Objekte über SCHARFE Kanten erkennen (+ Flächen darin).
Idee: natürliches Gelände ist GLATT (Normale dreht langsam), menschgemachtes (Einschnitt, Damm,
Mauer, Trasse) hat SCHARFE Kanten (Normale kippt abrupt). Kantenschärfe = |grad(Normale)|.
Hohe Schärfe + GERADE (LSD) = menschgemachte Kante. Die davon umschlossenen flachen Bereiche =
die 'Flächen darin'. Stufe 1 hier: die Schärfe-Karte + Schwelle visualisieren (trennt sie den
Einschnitt vom glatten Berg?).

  python3 tools/manmade_edges.py --out /tmp/sharp.png
"""
import argparse, numpy as np, cv2, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter
import insert_plate as ip


def sharpness(Hf, cell, smooth=1.0, up=4):
    """Kantenschärfe-Karte (hochaufgelöst): |grad(Normale)| — hoch an scharfen Kanten, ~0 auf
    glattem Naturgelände. Rückgabe (sharp[up*NY,up*NX], up)."""
    NY, NX = Hf.shape
    z = gaussian_filter(Hf, smooth)
    zu = cv2.resize(z, (NX*up, NY*up), interpolation=cv2.INTER_CUBIC)
    c = cell / up
    gx, gy = np.gradient(zu, c)
    nrm = np.dstack([-gx, -gy, np.ones_like(zu)])
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    # wie schnell dreht die Normale räumlich = Oberflächen-Krümmung/Schärfe
    s = np.zeros(zu.shape)
    for k in range(3):
        gxk, gyk = np.gradient(nrm[..., k], c)
        s += gxk**2 + gyk**2
    return np.sqrt(s), up


def detect_manmade(Hf, cell, sharp_pct=90.0, flat_slope=22.0, min_area_mm2=200.0, rdp_mm=4.0):
    """Menschgemachte Objekte = FLÄCHEN mit flachem Kern, die von SCHARFEN Kanten umschlossen sind.
    Rückgabe: (surface_polys[Welt-mm], sharp_edges_lsd[(x0,y0,x1,y1)], cell2).
      - scharfe Kante: Schärfe > sharp_pct-Perzentil (Normale kippt abrupt)
      - Fläche darin: flacher Kern (slope < flat_slope) UND nicht selbst scharf, dessen RAND aber
        scharf ist (vom sharp-Ring umschlossen) => menschgemacht, nicht glatter Naturhang."""
    from scipy.ndimage import label as _lab, binary_dilation
    NY, NX = Hf.shape
    s, up = sharpness(Hf, cell); cell2 = cell / up
    sharp = s > np.percentile(s, sharp_pct)
    zu = cv2.resize(gaussian_filter(Hf, 1.0), (NX*up, NY*up), interpolation=cv2.INTER_CUBIC)
    gx, gy = np.gradient(zu, cell2)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    flatcore = (slope < flat_slope) & (~sharp)
    lab, nl = _lab(flatcore)
    polys = []
    for li in range(1, nl+1):
        m = lab == li
        area = m.sum() * cell2 * cell2
        if area < min_area_mm2:
            continue
        ring = binary_dilation(m, iterations=3) & (~m)
        if ring.sum() == 0 or (sharp[ring].mean() < 0.33):     # Rand muss überwiegend scharf sein
            continue
        cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(float)
        eps = rdp_mm / cell2
        simp = cv2.approxPolyDP(c.astype(np.float32).reshape(-1, 1, 2), eps, True).reshape(-1, 2)
        if len(simp) >= 4:
            polys.append(simp * cell2)
    # gerade scharfe Kanten (LSD auf der Schärfe-Karte)
    sn = np.clip(s / (np.percentile(s, 99) + 1e-9), 0, 1)
    lines = cv2.createLineSegmentDetector().detect((sn*255).astype(np.uint8))[0]
    edges = []
    if lines is not None:
        for x0, y0, x1, y1 in lines.reshape(-1, 4):
            if np.hypot(x1-x0, y1-y0)*cell2 >= 12:
                edges.append((x0*cell2, y0*cell2, x1*cell2, y1*cell2))
    return polys, edges, cell2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--pct", type=float, default=90.0)   # Schwelle: oberste pct% Schärfe = scharfe Kante
    ap.add_argument("--out", default="/tmp/sharp.png")
    a = ap.parse_args()

    class O: pass
    o = O(); o.dem = a.dem; o.r0 = a.r0; o.r1 = a.r1; o.c0 = a.c0; o.c1 = a.c1
    o.zoom = 1; o.mm = 0.78125; o.nscale = 3.125; o.vscale = 0.85; o.base = 12.0; o.smooth = 0.4
    Hf, cell = ip.load_hf(o); NY, NX = Hf.shape

    s, up = sharpness(Hf, cell)
    thr = np.percentile(s, a.pct)
    # Heatmap
    sn = np.clip(s / (np.percentile(s, 99) + 1e-9), 0, 1)
    heat = cv2.applyColorMap((sn*255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    # scharfe Kanten (über Schwelle) rot über ein Hillshade legen
    def hs(z, c, az=315, alt=45):
        g1, g2 = np.gradient(z, c); sl = np.pi/2-np.arctan(np.hypot(g1, g2)); asp = np.arctan2(-g1, g2)
        az = np.radians(360-az+90); alt = np.radians(alt)
        return np.clip(np.sin(alt)*np.sin(sl)+np.cos(alt)*np.cos(sl)*np.cos(az-asp), 0, 1)
    base = (hs(cv2.resize(gaussian_filter(Hf, 1.0), (NX*up, NY*up)), cell/up)*255).astype(np.uint8)
    over = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    over[s > thr] = (0.25*over[s > thr] + 0.75*np.array([40, 40, 230])).astype(np.uint8)
    combo = np.hstack([heat, over])
    for dy, cc in ((0, (0, 0, 0)), (1, (255, 255, 255))):
        cv2.putText(combo, f"links: Kantenschaerfe-Karte  |  rechts: scharfe Kanten (>{a.pct:.0f}%) = menschgemacht-Kandidaten",
                    (10, 22+dy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cc, 2 if dy == 0 else 1)
    cv2.imwrite(a.out, combo)
    print(f"Schaerfe-Schwelle(pct {a.pct})={thr:.4f}, scharfe Pixel={int((s>thr).sum())} -> {a.out}")


if __name__ == "__main__":
    main()
