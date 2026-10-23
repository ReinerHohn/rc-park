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


def segment_facets(Hf, cell, scale=140.0, sigma=0.6, min_size=90, smooth=1.5):
    """Planare Flächen (Label-Bild) + ihre Normalen. Felzenszwalb auf dem Normalen-Bild."""
    n = surface_normals(Hf, cell, smooth)
    img = (n * 0.5 + 0.5).astype(np.float64)           # Normalen -> [0,1]-RGB
    lab = felzenszwalb(img, scale=scale, sigma=sigma, min_size=min_size)
    return lab, n


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

    lab, n = segment_facets(Hf, cell, a.scale, a.sigma, a.min_size, a.smooth)
    polys = facet_polys(lab, cell, a.min_area, a.rdp)
    nseg = lab.max() + 1

    # Render: Flächen eingefärbt nach Normalen-Orientierung + saubere Kanten-Polygone
    U = 4
    base = (n * 0.5 + 0.5)[..., :3]
    labU = cv2.resize(lab.astype(np.int32), (NX*U, NY*U), interpolation=cv2.INTER_NEAREST)
    # mittlere Normalenfarbe je Fläche
    col = np.zeros((NY*U, NX*U, 3), np.uint8)
    for r in regionprops(lab + 1):
        m = (labU == r.label - 1)
        c = (base[r.slice][r.image].mean(0) * 255).astype(np.uint8) if r.image.any() else np.array([128,128,128],np.uint8)
        col[m] = c[::-1]
    for p in polys:
        pts = (p / cell * U).astype(np.int32)
        cv2.polylines(col, [pts], True, (255, 255, 255), 1)
    txt = f"Felzenszwalb-Flaechen: {len(polys)} saubere Flaechen + Kanten (scale={a.scale:.0f})"
    for dy, cc in ((0, (0, 0, 0)), (1, (255, 255, 255))):
        cv2.putText(col, txt, (10, 22+dy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cc, 2 if dy == 0 else 1)
    cv2.imwrite(a.out, col)
    print(f"{nseg} Rohsegmente -> {len(polys)} Flaechen (>= {a.min_area:.0f}mm2) -> {a.out}")


if __name__ == "__main__":
    main()
