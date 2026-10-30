#!/usr/bin/env python3
"""plane_segment.py — SAUBERE Flächen + Geo-Kanten statt Linien-Konfetti.
Ansatz (Computer-Vision, library-basiert): Oberflächen-NORMALEN aus dem DEM -> Felzenszwalb-
Segmentierung (skimage) gruppiert Bereiche gleicher Orientierung = zusammenhängende planare
FLÄCHEN (die 'Objekte'). Deren Ränder = die geometrischen Kanten, als Polygon vereinfacht
(approximate_polygon) = GERADE Kanten. Kein Linien-Fragment-Zoo.

  python3 tools/plane_segment.py --scale 140 --min-size 90 --out /tmp/seg.png
"""
import argparse, numpy as np, cv2, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter
from skimage.segmentation import felzenszwalb, mark_boundaries
from skimage.measure import find_contours, approximate_polygon, regionprops, label as sk_label
import insert_plate as ip


def surface_normals(Hf, cell, smooth=1.5):
    z = gaussian_filter(Hf, smooth)
    gx, gy = np.gradient(z, cell)
    nz = np.ones_like(z)
    n = np.dstack([-gx, -gy, nz])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n


def _smooth_labels(lab, px=3):
    """Flächen-Ränder ENTZACKEN: je Fläche Maske morphologisch schließen+öffnen (Treppen weg),
    dann per Mehrheits-Mode die Löcher/Overlaps auflösen. Gibt entzacktes Label-Bild zurück."""
    from scipy.ndimage import binary_closing, binary_opening, distance_transform_edt
    out = np.full(lab.shape, -1, int)
    k = np.ones((px, px), bool)
    best = np.full(lab.shape, -1.0)
    for lb in np.unique(lab):
        m = binary_opening(binary_closing(lab == lb, k), k)
        d = distance_transform_edt(m)                  # „innerster" gewinnt bei Überlapp -> glatte Grenze
        take = d > best
        out[take] = lb; best[take] = d[take]
    # Rest (von Morphologie gefressene Pixel) auf nächstgelegenes Label füllen
    from scipy.ndimage import distance_transform_edt as edt
    miss = out < 0
    if miss.any():
        idx = edt(miss, return_distances=False, return_indices=True)
        out = out[tuple(idx)]
    return out


def segment_facets(Hf, cell, scale=140.0, sigma=0.6, min_size=90, smooth=1.5, up=4):
    """Planare Flächen (Label-Bild, HOCHAUFGELÖST) + Normalen. DGM-Fenster ist grob (260x170 px),
    darum VOR der Segmentierung up-fach upsampeln -> feine, glatte Ränder statt Pixel-Treppen.
    Danach Flächen-Masken morphologisch entzacken."""
    nlo = surface_normals(Hf, cell, smooth)
    NY, NX = Hf.shape
    img = (nlo * 0.5 + 0.5).astype(np.float32)
    imgU = cv2.resize(img, (NX * up, NY * up), interpolation=cv2.INTER_CUBIC)
    imgU = np.clip(imgU, 0, 1).astype(np.float64)
    lab = felzenszwalb(imgU, scale=scale, sigma=max(sigma, 0.8),
                       min_size=int(min_size * up * up))   # min_size in Hochauflösung skalieren
    lab = _smooth_labels(lab, px=max(3, up))
    n_hi = cv2.resize(nlo, (NX * up, NY * up), interpolation=cv2.INTER_NEAREST)
    return lab, cell / up, n_hi               # lab/n in HOCHAUFLÖSUNG, cell_eff = cell/up


def facet_polys(lab, cell, min_area_mm2=150.0, rdp_mm=3.0):
    """Für jede Fläche: äußere Kontur -> vereinfachtes Polygon (Welt-mm)."""
    polys = []
    for r in regionprops(lab + 1):
        if r.area * cell * cell < min_area_mm2:
            continue
        mask = np.zeros(lab.shape, np.uint8)
        mask[r.slice][r.image] = 1
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        c = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(float)
        simp = approximate_polygon(np.column_stack([c[:, 1], c[:, 0]]), tolerance=rdp_mm / cell)
        simp = simp[:, ::-1] * cell                    # (row,col)->(x,y) mm
        if len(simp) >= 4:
            polys.append(simp)
    return polys


def facet_plates(lab, cell2, Hf, cell, min_area_mm2=150.0, rdp_mm=5.0, max_rms=4.0):
    """Je Fläche eine EBENE Platte: Kontur (Welt-mm) + best-fit Ebene z=a*x+b*y+c (least squares
    über die Gelände-Höhen der Fläche). Nur Flächen, die WIRKLICH planar sind (RMS <= max_rms mm),
    werden als Platte ausgegeben — der Rest bleibt den Rippen überlassen. Rückgabe: Liste
    (poly_mm[N,2], (a,b,c), rms)."""
    NY, NX = Hf.shape
    out = []
    for p in facet_polys(lab, cell2, min_area_mm2, rdp_mm):
        # Gelände-Punkte der Fläche sammeln (über Bounding-Box der Kontur, Punkt-in-Polygon)
        x0, y0 = p.min(0); x1, y1 = p.max(0)
        xs = np.arange(max(0, x0), min(NX*cell, x1), cell)
        ys = np.arange(max(0, y0), min(NY*cell, y1), cell)
        if len(xs) < 2 or len(ys) < 2:
            continue
        XX, YY = np.meshgrid(xs, ys)
        from matplotlib.path import Path as _MP
        inside = _MP(p).contains_points(np.column_stack([XX.ravel(), YY.ravel()]))
        if inside.sum() < 6:
            continue
        px = XX.ravel()[inside]; py = YY.ravel()[inside]
        pz = Hf[np.clip((py/cell).astype(int), 0, NY-1), np.clip((px/cell).astype(int), 0, NX-1)]
        A = np.column_stack([px, py, np.ones_like(px)])
        coef, *_ = np.linalg.lstsq(A, pz, rcond=None)         # a,b,c
        rms = float(np.sqrt(np.mean((A @ coef - pz)**2)))
        if rms <= max_rms:                                    # nur echte Ebenen -> Platte
            out.append((p, tuple(float(v) for v in coef), rms))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--scale", type=float, default=140.0); ap.add_argument("--sigma", type=float, default=0.6)
    ap.add_argument("--min-size", type=int, default=90); ap.add_argument("--smooth", type=float, default=1.5)
    ap.add_argument("--min-area", type=float, default=150.0); ap.add_argument("--rdp", type=float, default=3.0)
    ap.add_argument("--out", default="/tmp/seg.png")
    a = ap.parse_args()

    class O: pass
    o = O(); o.dem = a.dem; o.r0 = a.r0; o.r1 = a.r1; o.c0 = a.c0; o.c1 = a.c1
    o.zoom = 1; o.mm = 0.78125; o.nscale = 3.125; o.vscale = 0.85; o.base = 12.0; o.smooth = 0.4
    Hf, cell = ip.load_hf(o); NY, NX = Hf.shape

    lab, cell2, n = segment_facets(Hf, cell, a.scale, a.sigma, a.min_size, a.smooth)   # lab/n HOCHAUFLÖSUNG
    polys = facet_polys(lab, cell2, a.min_area, a.rdp)
    nseg = lab.max() + 1

    # Render in Hochauflösung (lab/n sind schon up-fach): Flächen nach Orientierung + saubere Ränder
    base = (n * 0.5 + 0.5)[..., :3]
    col = np.zeros((*lab.shape, 3), np.uint8)
    for r in regionprops(lab + 1):
        m = (lab == r.label - 1)
        c = (base[m].mean(0) * 255).astype(np.uint8) if m.any() else np.array([128, 128, 128], np.uint8)
        col[m] = c[::-1]
    for p in polys:
        pts = (p / cell2).astype(np.int32)
        cv2.polylines(col, [pts], True, (255, 255, 255), 2)
    txt = f"Felzenszwalb-Flaechen: {len(polys)} saubere Flaechen + Kanten (scale={a.scale:.0f})"
    for dy, cc in ((0, (0, 0, 0)), (1, (255, 255, 255))):
        cv2.putText(col, txt, (10, 22+dy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cc, 2 if dy == 0 else 1)
    cv2.imwrite(a.out, col)
    print(f"{nseg} Rohsegmente -> {len(polys)} Flaechen (>= {a.min_area:.0f}mm2) -> {a.out}")


if __name__ == "__main__":
    main()
