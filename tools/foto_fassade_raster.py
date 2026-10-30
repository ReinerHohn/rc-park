#!/usr/bin/env python3
"""foto_fassade_raster.py — GENERISCH & AUTOMATISCH: Fenster-RASTER aus einem Foto.

Kein manuelles Klicken, keine Bauwerks-Konstanten. Standard-Fassadenparsing
(translational symmetry): rektifizieren → metrischer Maßstab aus Referenzhöhe →
  * Geschoss-/Sims-Reihen aus horizontalem Kantenprofil (metrisch gefiltert)
  * Achsabstand aus Autokorrelation des vertikalen Kantenprofils, Suche NUR im
    plausiblen Fensterabstand 2,5–5 m (verhindert Rausch-Peaks)
  * Fenstergröße aus Achsabstand/Geschosshöhe abgeleitet
Gibt facade_raster.json {storey_rows_m, axis_m, win_w, win_h, confidence}.

  python3 tools/foto_fassade_raster.py --img foto.jpg --ref-height 17.6 \
      --out daten/x/raster.json --vis daten/x/raster.png
"""
import argparse, json
import numpy as np
import cv2
from scipy.ndimage import uniform_filter1d


def lsd_vps(gray):
    lsd = cv2.createLineSegmentDetector()
    segs = lsd.detect(gray)[0]
    if segs is None:
        return None, None
    S = segs.reshape(-1, 4)
    Ln = np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1]); S = S[Ln > 20]
    ang = np.degrees(np.arctan2(S[:, 3] - S[:, 1], S[:, 2] - S[:, 0]))
    a = np.abs(((ang + 90) % 180) - 90)
    vert, horiz = S[a > 75], S[a < 15]

    def vp(segs):
        if len(segs) < 2:
            return None
        def line(s):
            l = np.cross([s[0], s[1], 1], [s[2], s[3], 1]); return l / (np.linalg.norm(l[:2]) + 1e-9)
        Ls = np.array([line(s) for s in segs]); best, bn = None, -1
        rng = np.random.default_rng(0)
        for _ in range(500):
            i, j = rng.choice(len(Ls), 2, replace=False)
            v = np.cross(Ls[i], Ls[j])
            if abs(v[2]) < 1e-9:
                continue
            v /= v[2]; inl = (np.abs(Ls @ v) < 2).sum()
            if inl > bn:
                bn, best = inl, v
        return best
    return vp(vert), vp(np.vstack([horiz, S[(a >= 15) & (a <= 75)]]) if len(S) else horiz)


def rectify(img, vpv, vph):
    H, W = img.shape[:2]
    bbox = np.float32([[W*0.05, H*0.05], [W*0.95, H*0.05], [W*0.95, H*0.95], [W*0.05, H*0.95]])
    Hl = np.cross(vpv, vph); Hp = np.array([[1, 0, 0], [0, 1, 0], Hl / (Hl[2] + 1e-9)])
    p = cv2.perspectiveTransform(bbox.reshape(-1, 1, 2), Hp).reshape(-1, 2)
    w = int(np.clip(np.hypot(*(p[1]-p[0])), 300, 2200)); h = int(np.clip(np.hypot(*(p[2]-p[1])), 300, 2200))
    M = cv2.getPerspectiveTransform(p.astype(np.float32), np.float32([[0, 0], [w, 0], [w, h], [0, h]])) @ Hp
    return cv2.warpPerspective(img, M, (w, h))


def rows_from_profile(gray, mpp, min_gap_m=2.0):
    sy = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)).mean(1)
    sy = uniform_filter1d(sy, 5); thr = sy.mean() + 0.6 * sy.std()
    H = len(sy); gap = max(3, int(min_gap_m / mpp))
    peaks = [k for k in range(1, H-1) if sy[k] > thr and sy[k] >= sy[k-1] and sy[k] > sy[k+1]]
    clust = []
    for r in peaks:
        if clust and r - clust[-1][-1] < gap:
            clust[-1].append(r)
        else:
            clust.append([r])
    return [int(np.mean(c)) for c in clust]


def axis_period(gray, mpp, lo_m=2.5, hi_m=5.0):
    """dominanter Achsabstand via Autokorrelation, Suche nur in [lo_m,hi_m]."""
    sx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    col = sx.mean(0); col = col - col.mean()
    ac = np.correlate(col, col, "full")[len(col)-1:]; ac = ac / (ac[0] + 1e-9)
    lo, hi = int(lo_m / mpp), int(hi_m / mpp)
    lo = max(lo, 4); hi = min(hi, len(ac) - 2)
    if hi <= lo:
        return None, 0.0
    seg = ac[lo:hi]; k = int(np.argmax(seg)) + lo
    return k, float(ac[k])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--ref-height", type=float, required=True)
    ap.add_argument("--scale-up", type=float, default=3.0)
    ap.add_argument("--out", required=True); ap.add_argument("--vis", default="")
    a = ap.parse_args()

    img = cv2.imread(a.img)
    img = cv2.resize(img, None, fx=a.scale_up, fy=a.scale_up, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    vpv, vph = lsd_vps(gray)
    rect = rectify(img, vpv, vph) if (vpv is not None and vph is not None) else img
    rg = cv2.cvtColor(rect, cv2.COLOR_BGR2GRAY)
    Hc = rg.shape[0]
    mpp = a.ref_height / Hc                      # Maßstab: Bildhöhe ~ Referenzhöhe

    rows_px = rows_from_profile(rg, mpp)
    rows_m = sorted([round((Hc - r) * mpp, 2) for r in rows_px])   # Höhe ü. unten
    per_px, conf = axis_period(rg, mpp)
    axis_m = round(per_px * mpp, 2) if per_px else None

    # Geschosshöhe aus Reihenabständen (Median), Fenstergröße ableiten
    diffs = np.diff(sorted(rows_m)) if len(rows_m) > 1 else []
    floor_m = float(np.median(diffs)) if len(diffs) else 3.0
    win_h = round(min(1.6, 0.55 * floor_m), 2)
    win_w = round(0.42 * axis_m, 2) if axis_m else 1.0
    # Fallback/Klemmung wenn Konfidenz niedrig
    flag = "ok"
    if axis_m is None or conf < 0.25:
        axis_m = round(float(np.clip(axis_m or 3.5, 3.0, 4.0)), 2); flag = "niedrige Konfidenz → geklemmt 3–4 m"

    res = dict(img=a.img, ref_height_m=a.ref_height, m_per_px=round(mpp, 4),
               storey_rows_m=rows_m, axis_m=axis_m, floor_m=round(floor_m, 2),
               win_w=win_w, win_h=win_h, autocorr=round(conf, 2), confidence=flag)
    json.dump(res, open(a.out, "w"), indent=2, ensure_ascii=False)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.vis:
        vis = rect.copy()
        for r in rows_px:
            cv2.line(vis, (0, r), (rect.shape[1], r), (0, 0, 255), 2)
        if per_px:
            for x in range(0, rect.shape[1], per_px):
                cv2.line(vis, (x, 0), (x, rect.shape[0]), (0, 200, 0), 1)
        cv2.imwrite(a.vis, vis); print("-> vis", a.vis)
    print("-> ", a.out)


if __name__ == "__main__":
    main()
