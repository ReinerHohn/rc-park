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
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    build = (mask > 0) & np.isfinite(nd) & (nd > 1.0)
    ys, xs = np.where(build)
    r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
    H = np.clip(nd, 0, 25); H[~build] = np.nan

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
            x, y = c - c0, (r1 - r)
            # vier Eckhöhen (Vertex r,c = Ecke oben-links der Zelle)
            hNW = vheight(r, c); hNE = vheight(r, c + 1); hSW = vheight(r + 1, c); hSE = vheight(r + 1, c + 1)
            if None in (hNW, hNE, hSW, hSE):
                continue
            # Top (Ecke oben-links=(x,y+1), oben-rechts=(x+1,y+1), unten-rechts=(x+1,y), unten-links=(x,y))
            quad(vid(x, y + 1, hNW), vid(x + 1, y + 1, hNE), vid(x + 1, y, hSE), vid(x, y, hSW))
            # Boden
            quad(vid(x, y, 0), vid(x + 1, y, 0), vid(x + 1, y + 1, 0), vid(x, y + 1, 0))
            # Randwände nur zum Nicht-Bau-Nachbarn, mit den passenden Eckhöhen
            edges = [(-1, 0, (x, y + 1, hNW), (x + 1, y + 1, hNE)),   # Nord
                     (1, 0, (x + 1, y, hSE), (x, y, hSW)),            # Süd
                     (0, 1, (x + 1, y + 1, hNE), (x + 1, y, hSE)),    # Ost
                     (0, -1, (x, y, hSW), (x, y + 1, hNW))]           # West
            for dr, dc, A, B in edges:
                nr, nc = r + dr, c + dc
                if not (r0 <= nr <= r1 and c0 <= nc <= c1 and build[nr, nc]):
                    ax, ay, ah = A; bx, by, bh = B
                    quad(vid(ax, ay, 0), vid(bx, by, 0), vid(bx, by, bh), vid(ax, ay, ah))

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
