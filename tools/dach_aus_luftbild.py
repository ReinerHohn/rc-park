#!/usr/bin/env python3
"""dach_aus_luftbild.py — HARTES MODUL: Dachstruktur direkt aus dem DOP-LUFTBILD ableiten (generell).
Idee: die Dachfläche (DOP) in den Modell-Frame warpen → DISTANZTRANSFORMATION zum Dachrand → die
GRATE (medial axis) sind automatisch die Firste. Dachhöhe z = Traufe + Neigung·Abstand-zum-Rand,
gekappt auf First. So entsteht die ECHTE Firststruktur (Hauptfirst + Querschiff/Kreuz-First) aus den
Daten, ohne handgesetzte Giebel. Höhen (Traufe/First) aus roof_params.json (Laser).

Schreibt modelle/<name>/dach_luftbild.obj (Roof-Solid im Modell-Frame).
Lauf: /tmp/ml/bin/python tools/dach_aus_luftbild.py --name hofgut_sternen
"""
import argparse, json, os
import numpy as np
import cv2

DOP = "daten/ravenna/dop/dop20rgb_32_429_5306_2_bw/dop20rgb_32_430_5307_1_bw_2025.tif"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--name", required=True)
    ap.add_argument("--px-per-m", type=float, default=8.0); a = ap.parse_args()
    md = f"modelle/{a.name}"
    fr = json.load(open(f"{md}/massing_frame.json")); fp = json.load(open(f"{md}/footprint.json"))
    rp = json.load(open(f"{md}/roof_params.json"))
    E_roof = rp["roof_eave_m"]; R = rp["ridge_m"]
    o = np.array(fp["origin_utm"][:2])
    ang = -fr["rot_angle"]; Rm = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    ctr = np.array(fr["ctr"]); flip = fr["flip"]; shift = np.array(fr["shift"])
    tfw = open(os.path.splitext(DOP)[0] + ".tfw").read().split()
    pxs, _, _, pys, oxc, oyc = [float(x) for x in tfw]; E0, N0 = oxc - pxs / 2, oyc + (-pys) / 2
    dop = cv2.imread(DOP)

    # Modell-Frame-Bbox des Hauptkörpers
    def m2loc(mx, my):
        p1 = np.array([mx, my]) + shift
        if flip:
            p1 = p1 * np.array([1.0, -1.0])
        return p1 @ Rm + ctr
    # Grundriss (Hauptkörper) in Modell-Frame → bbox
    rings = []
    for t in fp["teile"]:
        if cv2.contourArea(np.array(t["ring_xy_m"], np.float32)) <= 40:
            continue
        # footprint ring ist in local-from-origin; forward transform:
        r = np.array(t["ring_xy_m"])
        p = (r - ctr) @ Rm.T
        if flip:
            p = p * np.array([1.0, -1.0])
        p = p - shift
        rings.append(p)
    allp = np.vstack(rings); x0, y0, x1, y1 = allp[:, 0].min(), allp[:, 1].min(), allp[:, 0].max(), allp[:, 1].max()
    pad = 2.0; x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
    W = int((x1 - x0) * a.px_per_m); H = int((y1 - y0) * a.px_per_m)

    # DOP in Modell-Frame warpen (Top-Down)
    def m2dop(mx, my):
        loc = m2loc(mx, my); E, N = loc[0] + o[0], loc[1] + o[1]
        return (E - E0) / pxs, (N0 - N) / (-pys)
    src = np.float32([m2dop(x0, y1), m2dop(x1, y1), m2dop(x1, y0), m2dop(x0, y0)])
    dstp = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    warp = cv2.warpPerspective(dop, cv2.getPerspectiveTransform(src, dstp), (W, H))

    # Dachfläche = dunkle Region (Schindel), gefüllt, größte Komponente
    g = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    roof = (g < 115).astype(np.uint8)
    roof = cv2.morphologyEx(roof, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    roof = cv2.morphologyEx(roof, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(roof, 8)
    if n > 1:
        roof = (lab == 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
    roof = cv2.morphologyEx(roof, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))

    # RAND REGULARISIEREN: Kontur zu geraden Kanten approximieren (keine Treppen-Traufe)
    cnts, _ = cv2.findContours(roof, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        c = max(cnts, key=cv2.contourArea)
        approx = cv2.approxPolyDP(c, 0.012 * cv2.arcLength(c, True), True)
        roof = np.zeros_like(roof); cv2.fillPoly(roof, [approx], 1)

    # DISTANZTRANSFORMATION → Grate = medial axis = Firste. KEINE Glättung → SCHARFE Firste/Grate
    # (= Gerade-Skelett-Walmdach: Abstand zum Rand × Neigung ergibt planare Dachflächen).
    dist = cv2.distanceTransform(roof, cv2.DIST_L2, 5)
    # First WAAGRECHT: feste Neigung, bei halber Gebäudetiefe erreicht (dann flach auf First gekappt)
    half_depth_px = np.percentile(dist[dist > 0], 78)                    # ~halbe Trauf-First-Spanne
    Z = E_roof + np.clip(dist / max(1e-6, half_depth_px), 0, 1) * (R - E_roof)
    Z[roof == 0] = np.nan

    # Solid aus DIREKTEN PIXEL-HÖHEN (keine Mittelung → Firste/Grate bleiben SCHARF = planare Flächen)
    def mx(c): return x0 + c / a.px_per_m
    def my(r): return y1 - r / a.px_per_m                                # Nord oben
    V, F, vi = [], [], {}
    def vid(x, y, z):
        k = (round(x, 2), round(y, 2), round(z, 2))
        if k not in vi:
            vi[k] = len(V); V.append(k)
        return vi[k]
    def quad(a_, b_, c_, d_): F.append((a_, b_, c_)); F.append((a_, c_, d_))
    base = E_roof - 0.4
    bld = np.isfinite(Z)
    ys, xs = np.where(bld); r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
    def P(r, c): return (mx(c), my(r), float(Z[r, c]))                   # Pixel = Vertex mit SEINER Höhe
    for r in range(r0, r1):
        for c in range(c0, c1):
            if not (bld[r, c] and bld[r, c + 1] and bld[r + 1, c] and bld[r + 1, c + 1]):
                continue
            NW, NE, SW, SE = P(r, c), P(r, c + 1), P(r + 1, c), P(r + 1, c + 1)
            quad(vid(*NW), vid(*NE), vid(*SE), vid(*SW))                 # Top (scharfe Grate)
            quad(vid(NW[0], NW[1], base), vid(SW[0], SW[1], base),
                 vid(SE[0], SE[1], base), vid(NE[0], NE[1], base))       # Boden
    # Randwände: pro Bau-Pixel zu Nicht-Bau-Nachbar eine vertikale Wand von base bis Pixelhöhe
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if not bld[r, c]:
                continue
            x, y, z = P(r, c); d = 1.0 / a.px_per_m
            for dr, dc, (ax, ay), (bx, by) in [(-1, 0, (x, y), (x + d, y)), (1, 0, (x + d, y - d), (x, y - d)),
                                               (0, 1, (x + d, y), (x + d, y - d)), (0, -1, (x, y - d), (x, y))]:
                if not (0 <= r + dr < H and 0 <= c + dc < W and bld[r + dr, c + dc]):
                    quad(vid(ax, ay, base), vid(bx, by, base), vid(bx, by, z), vid(ax, ay, z))
    with open(f"{md}/dach_luftbild.obj", "w") as f:
        for (x, y, z) in V:
            f.write(f"v {x} {y} {z}\n")
        for (a_, b_, c_) in F:
            f.write(f"f {a_+1} {b_+1} {c_+1}\n")
    cv2.imwrite(f"{md}/dach_luftbild_mask.png", (roof * 255))
    print(f"Dach aus Luftbild: {len(V)} Verts, First {R} m / Traufe {E_roof} m; Firste automatisch aus "
          f"Distanztransformation (Haupt- + Querschiff). -> {md}/dach_luftbild.obj")


if __name__ == "__main__":
    main()
