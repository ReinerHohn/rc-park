#!/usr/bin/env python3
"""edge_diag.py — DIAGNOSE (Draufsicht): der EINSCHNITT als EINE Platte mit GERADEN Kanten.
Signal ist NICHT Canny/Hough (Rauschen auf Natur), sondern die Grenze flach<->steil:
  - flach (slope < flat_max) + an der Trasse haengend  = Talboden-Korridor (die Platte)
  - dessen Kontur, Douglas-Peucker-vereinfacht          = GERADE Kanten (= was der Nutzer nachzieht)
  - steil (slope > wall)                                = die Einschnitt-Waende (Seitenplatten)

  python3 tools/edge_diag.py --out /tmp/einschnitt.png
"""
import argparse, numpy as np, cv2
from scipy.ndimage import gaussian_filter, label, binary_closing, binary_dilation


def hillshade(z, cell, az=315, alt=45):
    gx, gy = np.gradient(z, cell)
    slope = np.pi/2 - np.arctan(np.hypot(gx, gy))
    asp = np.arctan2(-gx, gy)
    az = np.radians(360-az+90); alt = np.radians(alt)
    return np.clip(np.sin(alt)*np.sin(slope) + np.cos(alt)*np.cos(slope)*np.cos(az-asp), 0, 1)


def rdp(pts, eps):
    if len(pts) < 3: return pts
    a, b = pts[0], pts[-1]; ab = b - a; L = np.hypot(*ab)
    if L < 1e-9:
        d = np.hypot(*(pts - a).T)
    else:
        d = np.abs(ab[0]*(pts[:, 1]-a[1]) - ab[1]*(pts[:, 0]-a[0]))/L
    i = int(np.argmax(d))
    if d[i] > eps:
        return np.vstack([rdp(pts[:i+1], eps)[:-1], rdp(pts[i:], eps)])
    return np.array([a, b])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--track", default="modelle/hoellental_A3_set/track50.npy")
    ap.add_argument("--up", type=int, default=4)
    ap.add_argument("--flat-max", type=float, default=24.0)   # Grad: Talboden/flach
    ap.add_argument("--wall", type=float, default=40.0)       # Grad: Einschnitt-Wand
    ap.add_argument("--rdp", type=float, default=6.0)         # px: Kanten-Geradheit
    ap.add_argument("--corridor-mm", type=float, default=45.0) # mm: max Abstand von der Trasse (begrenzt den Cut)
    ap.add_argument("--out", default="/tmp/einschnitt.png")
    a = ap.parse_args()

    dem = np.load(a.dem).astype(float)
    z = dem[a.r0:a.r1, a.c0:a.c1]
    U = a.up; cell = 0.5/U
    zu = gaussian_filter(cv2.resize(z, (z.shape[1]*U, z.shape[0]*U), interpolation=cv2.INTER_CUBIC), 1.4)
    H, W = zu.shape
    gx, gy = np.gradient(zu, cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))

    base = (hillshade(zu, cell)*255).astype(np.uint8)
    img = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)

    # Einschnitt-Waende gelb (Kontext)
    wall = slope > a.wall
    ys, xs = np.where(wall)
    img[ys, xs] = (0.55*img[ys, xs] + 0.45*np.array([0, 210, 255])).astype(np.uint8)

    # Trasse -> Pixel (mm 0.78125, 50%)
    mm = 0.78125
    trk = None
    try:
        tr = np.load(a.track).astype(float)
        trk = np.column_stack([(tr[:, 0]/mm)*U, (tr[:, 1]/mm)*U, tr[:, 3]])
    except Exception as ex:
        print("track skip:", ex)

    # flacher Korridor, der an der Trasse haengt = Talboden-Platte
    flat = binary_closing(slope < a.flat_max, iterations=2)
    lab, nlab = label(flat)
    keep = np.zeros_like(flat)
    if trk is not None:
        seedlabs = set()
        for px, py, _ in trk:
            ci, cj = int(px), int(py)
            if 0 <= cj < H and 0 <= ci < W and lab[cj, ci] > 0:
                seedlabs.add(lab[cj, ci])
        for s in seedlabs:
            keep |= (lab == s)
        # Korridor: nur flach UND nah an der Trasse (stoppt das Auslaufen auf die Hochebene)
        trkmask = np.zeros((H, W), np.uint8)
        for i in range(len(trk)-1):
            cv2.line(trkmask, (int(trk[i, 0]), int(trk[i, 1])),
                     (int(trk[i+1, 0]), int(trk[i+1, 1])), 255, 1)
        dist = cv2.distanceTransform(255-trkmask, cv2.DIST_L2, 5)
        corridor_px = (a.corridor_mm/mm)*U
        keep &= (dist < corridor_px)
    plate_px = int(keep.sum())

    # Kontur der Platte -> Douglas-Peucker -> gerade Kanten gruen
    nseg = 0
    cnts, _ = cv2.findContours(keep.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    overlay = img.copy()
    for c in cnts:
        if cv2.contourArea(c) < (H*W)*0.01: continue
        cv2.drawContours(overlay, [c], -1, (90, 230, 90), cv2.FILLED)
        pts = c.reshape(-1, 2).astype(float)
        simp = rdp(pts, a.rdp).astype(int)
        for i in range(len(simp)):
            p = tuple(simp[i]); q = tuple(simp[(i+1) % len(simp)])
            cv2.line(img, p, q, (40, 40, 230), 2); nseg += 1
        for p in simp:
            cv2.circle(img, tuple(p), 4, (255, 255, 255), -1)
    img = cv2.addWeighted(overlay, 0.30, img, 0.70, 0)

    # Trasse zuletzt (blau=Tunnel, gruen=offen)
    if trk is not None:
        for i in range(len(trk)-1):
            p, q = trk[i], trk[i+1]
            col = (255, 120, 0) if p[2] > 0.5 else (60, 180, 60)
            cv2.line(img, (int(p[0]), int(p[1])), (int(q[0]), int(q[1])), col, 3)

    for dy, cc in ((0, (0, 0, 0)), (1, (255, 255, 255))):
        cv2.putText(img, f"GRUEN=Einschnitt-Platte ({nseg} gerade Kanten)  GELB=Waende>{a.wall:.0f}deg  BLAU=Tunnel",
                    (10, 22+dy), cv2.FONT_HERSHEY_SIMPLEX, 0.52, cc, 2 if dy == 0 else 1)
    cv2.imwrite(a.out, img)
    print(f"Platte {plate_px}px, {nseg} gerade Kanten -> {a.out} ({W}x{H})")


if __name__ == "__main__":
    main()
