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


def detect_manmade(Hf, cell, sharp_pct=90.0, flat_slope=22.0, min_area_mm2=200.0,
                   rdp_mm=4.0, min_edge_mm=12.0, max_rms=4.0, steep_max_rms=3.0):
    """Menschgemachte Objekte = FLÄCHEN mit flachem Kern, die von SCHARFEN Kanten umschlossen sind,
    AN den geraden scharfen Kanten UNTERTEILT, je mit best-fit Ebene.
    Rückgabe: (surfaces[(poly_mm,(a,b,c),rms)], edges[(x0,y0,x1,y1)], cell2).
      - scharfe Kante: Schärfe > sharp_pct-Perzentil (Normale kippt abrupt)
      - gerade scharfe Kanten (LSD) werden als TRENNWÄNDE in den flachen Kern gelegt -> große
        Flächen werden dort geteilt, wo eine scharfe Kante durchläuft."""
    from scipy.ndimage import label as _lab, binary_dilation
    NY, NX = Hf.shape
    s, up = sharpness(Hf, cell); cell2 = cell / up
    sharp = s > np.percentile(s, sharp_pct)
    zu = cv2.resize(gaussian_filter(Hf, 1.0), (NX*up, NY*up), interpolation=cv2.INTER_CUBIC)
    Hu = cv2.resize(Hf, (NX*up, NY*up), interpolation=cv2.INTER_CUBIC)
    gx, gy = np.gradient(zu, cell2)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    # gerade scharfe Kanten (LSD auf der Schärfe-Karte)
    sn = np.clip(s / (np.percentile(s, 99) + 1e-9), 0, 1)
    lines = cv2.createLineSegmentDetector().detect((sn*255).astype(np.uint8))[0]
    edges = []
    barrier = np.zeros(s.shape, np.uint8)
    if lines is not None:
        for x0, y0, x1, y1 in lines.reshape(-1, 4):
            if np.hypot(x1-x0, y1-y0)*cell2 >= min_edge_mm:
                edges.append((x0*cell2, y0*cell2, x1*cell2, y1*cell2))
                cv2.line(barrier, (int(x0), int(y0)), (int(x1), int(y1)), 1, 3)   # Trennwand

    yy, xx = np.mgrid[0:s.shape[0], 0:s.shape[1]]

    def collect(core, rms_cap, min_a):
        """Zusammenhängende planare Flächen aus einem Kern-Maske-Kriterium: Rand muss scharf sein,
        Fläche wirklich eben (RMS <= rms_cap), mind. min_a mm². Gibt (poly_mm,(a,b,c),rms,pslope)."""
        res = []
        lab, nl = _lab(core)
        for li in range(1, nl+1):
            m = lab == li
            if m.sum() * cell2 * cell2 < min_a:
                continue
            ring = binary_dilation(m, iterations=4) & (~m)
            if ring.sum() == 0 or (sharp[ring].mean() < 0.30):   # Rand überwiegend scharf = menschgemacht
                continue
            px = xx[m] * cell2; py = yy[m] * cell2; pz = Hu[m]
            A = np.column_stack([px, py, np.ones_like(px)])
            coef, *_ = np.linalg.lstsq(A, pz, rcond=None)
            rms = float(np.sqrt(np.mean((A @ coef - pz)**2)))
            if rms > rms_cap:                                    # nur wirklich ebene Flächen
                continue
            pslope = float(np.degrees(np.arctan(np.hypot(coef[0], coef[1]))))
            cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            c = max(cnts, key=cv2.contourArea).astype(np.float32)
            simp = cv2.approxPolyDP(c, rdp_mm / cell2, True).reshape(-1, 2)
            if len(simp) >= 4:
                res.append((simp * cell2, tuple(float(v) for v in coef), rms, pslope))
        return res

    free = (~sharp) & (barrier == 0)
    flat_surf = collect((slope < flat_slope) & free, max_rms, min_area_mm2)             # flache + schräge Ebenen
    # schräge bis steile Ebenen (Bahndamm, Einschnitt-Wände). NICHT bis fast-senkrecht (verbindet
    # alle Steilklippen zu einem Klumpen); bis 80° deckt Wände ab, die als Ebene darstellbar sind.
    steep_surf = collect((slope >= flat_slope) & (slope < 80.0) & free, steep_max_rms, min_area_mm2)
    return flat_surf + steep_surf, edges, cell2


def detect_edges_ridges(Hf, cell, min_len_mm=14.0, thr=0.12, max_gap_mm=6.0, hough_thr=12):
    """FUSSELIGE/verrauschte Kanten robust finden — deutlich besser als LSD-auf-Schärfe-Perzentil
    (das nur SAUBERE gerade Linien fängt). Für linienhafte Bauwerke, die im Relief fusselig sind:
    Bahndamm (heller GRAT), Einschnitt (dunkler GRABEN), kantiger Tunnelausgang.
      1) RIDGE-Filter (Sato, multi-Skala) hell=Grat UND dunkel=Graben — findet linienhafte Strukturen
         auch bei Rauschen (Hessian-basiert, nicht nur ein Gradient).
      2) Canny mit HYSTERESE auf der Neigung — verbindet schwache + starke Kantenstücke zu Linien
         (die Einzel-Schwelle vorher riss fusselige Kanten auseinander).
      3) Skelett + Hough -> gerade Segmente (für die Kanten-Lineale B4).
    Rückgabe: Liste (x0,y0,x1,y1) in Welt-mm. Fällt leer zurück, wenn skimage fehlt."""
    try:
        from skimage.filters import sato
        from skimage.feature import canny
        from skimage.morphology import skeletonize
    except Exception:
        return [e for e in detect_manmade(Hf, cell)[1]]        # Fallback: alte Kanten
    NY, NX = Hf.shape
    def _nrm(a):
        a = np.asarray(a, float); return (a - a.min()) / (np.ptp(a) + 1e-9)
    gy, gx = np.gradient(gaussian_filter(Hf, 0.8), cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    rb = sato(Hf, sigmas=range(1, 5), black_ridges=False)       # heller Grat = Damm
    rd = sato(Hf, sigmas=range(1, 5), black_ridges=True)        # dunkler Graben = Einschnitt
    can = canny(_nrm(slope), sigma=1.5, low_threshold=0.1, high_threshold=0.25)
    strength = np.maximum(_nrm(rb), _nrm(rd))
    binmap = (strength > thr) | can
    from scipy.ndimage import label as _lab2                 # kleine Rausch-Inseln (<25 px) weg
    _lb, _nl = _lab2(binmap); _sz = np.bincount(_lb.ravel())
    binmap = binmap & ~np.isin(_lb, np.where(_sz < 25)[0])
    sk = skeletonize(binmap)
    lines = cv2.HoughLinesP((sk * 255).astype(np.uint8), 1, np.pi/180,
                            threshold=int(hough_thr), minLineLength=max(2, min_len_mm/cell),
                            maxLineGap=max(1, max_gap_mm/cell))
    segs = []
    if lines is not None:
        for x0, y0, x1, y1 in lines.reshape(-1, 4):
            if np.hypot(x1-x0, y1-y0) * cell >= min_len_mm:
                segs.append((float(x0*cell), float(y0*cell), float(x1*cell), float(y1*cell)))
    return segs


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
