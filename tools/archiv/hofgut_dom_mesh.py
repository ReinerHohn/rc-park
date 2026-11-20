#!/usr/bin/env python3
"""hofgut_dom_mesh.py — ECHTE 3D-STRUKTUR aus dem LASER: baut den Baukörper (Wände+Dach als EIN
Solid) direkt aus dem nDOM-Höhenfeld (DOM1−DGM1) über dem LOD2-Grundriss. KEIN geratenes
Parametrik-Dach — die real vermessene Dachlandschaft (Firste/Walme/Gauben) im 1-m-Raster.

Schreibt modelle/hofgut_sternen/hofgut_struktur.obj (watertight-blockiges Höhenfeld-Solid).
Lauf: /tmp/ml/bin/python tools/hofgut_dom_mesh.py
"""
import json, os
import numpy as np
import cv2

MD = "modelle/hofgut_sternen"
DOM = "daten/ravenna/dom1/dom1_32_429_5306_2_bw/dom1_32_430_5307_1_bw_2017.tif"
DGM = "daten/ravenna/dgm1_32_429_5306_2_bw/dgm1_32_430_5307_1_bw_2017.xyz"


def load_dgm_grid(xyz, E0, N0, n):
    d = np.loadtxt(xyz); G = np.full((n, n), np.nan, np.float32)
    c = np.round(d[:, 0] - 0.5 - E0).astype(int); r = np.round(N0 - 0.5 - d[:, 1]).astype(int)
    ok = (c >= 0) & (c < n) & (r >= 0) & (r < n); G[r[ok], c[ok]] = d[ok, 2]
    return G


def regularize_roof(H, build, min_cells=14):
    """Dachflächen-Regularisierung: Zellen nach NeigungsRICHTUNG clustern (Walm-/Giebelflächen haben
    je eine Richtung), je zusammenhängende Fläche eine EBENE fitten (least squares) und die Höhen
    darauf SNAPPEN → crispe Dachflächen + scharfe Firstlinien statt weicher Blob. (RANSAC-artig.)"""
    Hs = cv2.GaussianBlur(np.nan_to_num(H, nan=0), (5, 5), 0)
    gx = cv2.Sobel(Hs, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(Hs, cv2.CV_32F, 0, 1, ksize=5)
    mag = np.hypot(gx, gy)
    az = (np.degrees(np.arctan2(gy, gx)) + 360) % 360
    sector = np.where(mag < 0.12, 8, (az // 45).astype(int) % 8)   # 8 Richtungen + „flach"(8)
    lab = np.full(H.shape, -1, np.int32)
    out = H.copy()
    nextlab = 0
    for s in range(9):
        m = (build & (sector == s) & np.isfinite(H)).astype(np.uint8)
        nc, cc = cv2.connectedComponents(m, 8)
        for k in range(1, nc):
            reg = cc == k
            if reg.sum() < min_cells:
                continue
            ys, xs = np.where(reg)
            A = np.c_[xs, ys, np.ones(len(xs))]; z = H[ys, xs]
            coef, *_ = np.linalg.lstsq(A, z, rcond=None)         # Ebene z = a*x+b*y+c
            out[ys, xs] = A @ coef
            lab[reg] = nextlab; nextlab += 1
    return out


def main():
    tfw = open(os.path.splitext(DOM)[0] + ".tfw").read().split()
    px, _, _, py, oxc, oyc = [float(x) for x in tfw]
    E0, N0 = oxc - px / 2, oyc - py / 2
    D = cv2.imread(DOM, cv2.IMREAD_UNCHANGED).astype(np.float32); n = D.shape[0]
    G = load_dgm_grid(DGM, E0, N0, n)
    nd = cv2.medianBlur((D - G).astype(np.float32), 3)            # Objekthöhe, leicht entrauscht

    fp = json.load(open(f"{MD}/footprint.json")); o = np.array(fp["origin_utm"][:2])
    mask = np.zeros((n, n), np.uint8)
    for t in fp["teile"]:
        r_ = np.array(t["ring_xy_m"]) + o
        c = np.round(r_[:, 0] - 0.5 - E0).astype(np.int32); rr = np.round(N0 - 0.5 - r_[:, 1]).astype(np.int32)
        cv2.fillPoly(mask, [np.c_[c, rr]], 1)
    build = mask > 0                                          # NUR sauberer LOD2-Grundriss (keine Vegetations-Fins)
    # nDOM innerhalb des Grundrisses auf Dach-Höhen einschränken + Löcher füllen (Bäume/Fehlstellen)
    H = np.where(build & np.isfinite(nd), np.clip(nd, 2.0, 20.0), np.nan).astype(np.float32)
    holes = (build & ~np.isfinite(H)).astype(np.uint8)
    if holes.any():
        Hf = np.nan_to_num(H, nan=0).astype(np.float32)
        Hf = cv2.inpaint(np.clip(Hf * 12, 0, 255).astype(np.uint8), holes, 5, cv2.INPAINT_TELEA).astype(np.float32) / 12
        H = np.where(build & ~np.isfinite(H), Hf, H)
    H = cv2.medianBlur(np.nan_to_num(H, nan=0).astype(np.float32), 3)   # Laser = GROB-Form/Validator-Pfeiler,
    H[~build] = np.nan                                                  # NICHT als Geometrie (Details zu klein fürs 1m-Raster)
    ys, xs = np.where(build)
    r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()

    # Transform in den Fassaden-Frame (konsistent mit hofgut_massing)
    fr = json.load(open(f"{MD}/massing_frame.json"))
    a = -fr["rot_angle"]; Rm = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    ctr = np.array(fr["ctr"]); flip = fr["flip"]; shift = np.array(fr["shift"])

    def to_model(c, r):                                        # Gitter-Ecke (r,c) → Modell-x,y
        loc = np.array([E0 + c - o[0], (N0 - r) - o[1]])
        p = (loc - ctr) @ Rm.T
        if flip:
            p = p * np.array([1.0, -1.0])
        p = p - shift
        return float(p[0]), float(p[1])

    # DURCHGEHENDE Oberfläche über Gitter-ECKEN: Vertex-Höhe = Mittel der angrenzenden Bauzellen
    # → keine Lücken zwischen Nachbarzellen; Randwände nur am Gebäuderand; Boden bei 0.
    V, F = [], []
    vi = {}

    def vid(x, y, z):
        k = (round(x, 3), round(y, 3), round(z, 3))
        if k not in vi:
            vi[k] = len(V); V.append(k)
        return vi[k]

    def quad(a, b, c, d):
        F.append((a, b, c)); F.append((a, c, d))

    def vheight(r, c):                                            # Eckhöhe aus den 4 angrenzenden Zellen
        vals = [H[rr, cc] for rr, cc in [(r - 1, c - 1), (r - 1, c), (r, c - 1), (r, c)]
                if 0 <= rr < n and 0 <= cc < n and np.isfinite(H[rr, cc])]
        return float(np.mean(vals)) if vals else None

    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if not build[r, c]:
                continue
            hNW = vheight(r, c); hNE = vheight(r, c + 1); hSW = vheight(r + 1, c); hSE = vheight(r + 1, c + 1)
            if None in (hNW, hNE, hSW, hSE):
                continue
            NW = to_model(c, r); NE = to_model(c + 1, r); SW = to_model(c, r + 1); SE = to_model(c + 1, r + 1)
            # Top
            quad(vid(*NW, hNW), vid(*NE, hNE), vid(*SE, hSE), vid(*SW, hSW))
            # Boden
            quad(vid(*SW, 0), vid(*SE, 0), vid(*NE, 0), vid(*NW, 0))
            # Randwände zum Nicht-Bau-Nachbarn, mit passenden Eckhöhen
            edges = [(-1, 0, NW, hNW, NE, hNE),   # Nord
                     (1, 0, SE, hSE, SW, hSW),    # Süd
                     (0, 1, NE, hNE, SE, hSE),    # Ost
                     (0, -1, SW, hSW, NW, hNW)]   # West
            for dr, dc, A, ah, B, bh in edges:
                nr, nc = r + dr, c + dc
                if not (r0 <= nr <= r1 and c0 <= nc <= c1 and build[nr, nc]):
                    quad(vid(*A, 0), vid(*B, 0), vid(*B, bh), vid(*A, ah))

    with open(f"{MD}/hofgut_struktur.obj", "w") as f:
        for (x, y, z) in V:
            f.write(f"v {x} {y} {z}\n")
        for (a, b, c) in F:
            f.write(f"f {a+1} {b+1} {c+1}\n")
    print(f"ECHTE 3D-Struktur aus Laser-nDOM: {len(V)} Verts, {len(F)} Faces, "
          f"Grundfläche {c1-c0}×{r1-r0} m, Firsthöhe {H[build].max():.1f} m")
    print(f"-> {MD}/hofgut_struktur.obj")


if __name__ == "__main__":
    main()
