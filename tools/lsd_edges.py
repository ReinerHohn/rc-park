#!/usr/bin/env python3
"""lsd_edges.py — GERADE menschgemachte Kanten im DEM robust finden (Recherche-Ergebnis):
Line Segment Detector (LSD, cv2) auf MULTI-AZIMUT-STREIFLICHT-Hillshade (0-10° Höhe hebt scharfe
Bruchkanten/Cliffs hervor; mehrere Azimute gegen den Richtungs-Bias). LSD hat ein eingebautes
a-contrario/NFA-Maß (Helmholtz): validiert nur Segmente, die unter reinem Rauschen selten wären
=> verwirft krumme Naturtextur, wo Canny+Hough 2500 Rausch-Linien produziert. Parameterarm,
gelände-unabhängig (kein Fitten).

  python3 tools/lsd_edges.py --min-len 18 --out /tmp/lsd.png
"""
import argparse, numpy as np, cv2, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scipy.ndimage import gaussian_filter
import insert_plate as ip


def hillshade(z, cell, az, alt):
    gx, gy = np.gradient(z, cell)
    slope = np.pi/2 - np.arctan(np.hypot(gx, gy))
    asp = np.arctan2(-gx, gy)
    a = np.radians(360 - az + 90); al = np.radians(alt)
    return np.clip(np.sin(al)*np.sin(slope) + np.cos(al)*np.cos(slope)*np.cos(a - asp), 0, 1)


def detect_straight_edges(Hf, cell, up=4, graze_alt=8.0,
                          azimuths=(0, 22, 45, 67, 90, 112, 135, 157),
                          min_len_mm=18.0, presmooth=5.0):
    """Gerade Kanten (Welt-mm Segmente [[x0,y0,x1,y1],...]) via LSD. Zwei komplementäre Quellen gegen
    den Richtungs-Bias (Kanten parallel zum Licht sind im Hillshade unsichtbar):
      (1) 8-Azimut-Streiflicht-Hillshade (hebt scharfe Bruchkanten/Cliffs hervor),
      (2) das SLOPE-Raster selbst (orientierungsUNabhängig — eine Kante ist dort eine Kante, egal
          aus welcher Richtung). So werden auch die Hang-Kanten gefunden, die ein einzelner
          Lichtwinkel verschluckt. presmooth unterdrückt Mikro-Textur, damit lange Kanten überleben."""
    NY, NX = Hf.shape
    zu = cv2.resize(gaussian_filter(Hf, presmooth), (NX*up, NY*up), interpolation=cv2.INTER_CUBIC)
    lsd = cv2.createLineSegmentDetector()
    rasters = [(hillshade(zu, cell/up, az, graze_alt) * 255).astype(np.uint8) for az in azimuths]
    gx, gy = np.gradient(zu, cell/up)                      # (2) Slope-Raster, orientierungsunabhängig
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    rasters.append((np.clip(slope / max(1.0, slope.max()), 0, 1) * 255).astype(np.uint8))
    segs = []
    for g in rasters:
        lines = lsd.detect(g)[0]
        if lines is None:
            continue
        for l in lines.reshape(-1, 4):
            x0, y0, x1, y1 = l / up * cell          # -> Welt-mm
            if np.hypot(x1-x0, y1-y0) >= min_len_mm:
                segs.append([x0, y0, x1, y1])
    # Dedup: nahe, gleich-orientierte Segmente zusammenfassen (Mittel-Repräsentant)
    segs = np.array(segs) if segs else np.zeros((0, 4))
    keep = []
    used = np.zeros(len(segs), bool)
    for i in range(len(segs)):
        if used[i]:
            continue
        mi = segs[i]; ai = np.arctan2(mi[3]-mi[1], mi[2]-mi[0]) % np.pi
        ci = np.array([(mi[0]+mi[2])/2, (mi[1]+mi[3])/2])
        group = [mi]
        for j in range(i+1, len(segs)):
            if used[j]:
                continue
            mj = segs[j]; aj = np.arctan2(mj[3]-mj[1], mj[2]-mj[0]) % np.pi
            cj = np.array([(mj[0]+mj[2])/2, (mj[1]+mj[3])/2])
            dang = min(abs(ai-aj), np.pi-abs(ai-aj))
            if dang < np.radians(12) and np.hypot(*(ci-cj)) < 6.0:
                used[j] = True; group.append(mj)
        keep.append(np.mean(group, axis=0))
    return np.array(keep) if keep else np.zeros((0, 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--up", type=int, default=4); ap.add_argument("--graze-alt", type=float, default=6.0)
    ap.add_argument("--min-len", type=float, default=18.0)
    ap.add_argument("--out", default="/tmp/lsd.png")
    a = ap.parse_args()

    class O: pass
    o = O(); o.dem = a.dem; o.r0 = a.r0; o.r1 = a.r1; o.c0 = a.c0; o.c1 = a.c1
    o.zoom = 1; o.mm = 0.78125; o.nscale = 3.125; o.vscale = 0.85; o.base = 12.0; o.smooth = 0.4
    Hf, cell = ip.load_hf(o); NY, NX = Hf.shape

    segs = detect_straight_edges(Hf, cell, up=a.up, graze_alt=a.graze_alt, min_len_mm=a.min_len)

    # Render: normaler Hillshade (45°) + LSD-Segmente rot
    U = a.up
    zu = gaussian_filter(cv2.resize(Hf, (NX*U, NY*U), interpolation=cv2.INTER_CUBIC), 1.0)
    img = cv2.cvtColor((hillshade(zu, cell/U, 315, 45)*255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    for x0, y0, x1, y1 in segs:
        cv2.line(img, (int(x0/cell*U), int(y0/cell*U)), (int(x1/cell*U), int(y1/cell*U)), (40, 40, 230), 2)
    txt = f"LSD Multi-Azimut-Streiflicht: {len(segs)} GERADE Kanten (min_len={a.min_len:.0f}mm) -- vs. Canny+Hough ~2500 Rausch"
    for dy, cc in ((0, (0, 0, 0)), (1, (255, 255, 255))):
        cv2.putText(img, txt, (10, 22+dy), cv2.FONT_HERSHEY_SIMPLEX, 0.46, cc, 2 if dy == 0 else 1)
    cv2.imwrite(a.out, img)
    print(f"{len(segs)} gerade Kanten -> {a.out}")


if __name__ == "__main__":
    main()
