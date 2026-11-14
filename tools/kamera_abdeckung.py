"""Kamera-Abdeckung rund um ein Objekt (allgemein, jedes COLMAP-Sparse-Modell).

Zweck: Luecken im Kamerakranz erkennen, BEVOR man Geometrie auf der unterbelichteten Seite glaubt. Eine Seite ohne Kameras
(am Schwabentor 2026-11-14: Azimut 30-150 Grad leer, alle 178 Kameras auf einer Halbebene) wird nur von einer Gruppe aus einer Richtung
gesehen: Tiefenmehrdeutigkeit, duenne/flache Waende, Haeuser auf der falschen Seite, durch aehnliche Turmflaechen verwechselte Posen.
Aufruf: python3 tools/kamera_abdeckung.py <sparse-ordner mit images.bin, points3D.bin> [--mitte x y z] [--luecke 90]
Ausgabe: Anzahl Kameras je 30-Grad-Sektor, groesste Luecke in Grad, Warnung wenn Luecke > --luecke. Exit-Code 2 bei Warnung.
"""
import argparse, os, struct
import numpy as np


def cams(p):
    out = []
    with open(os.path.join(p, "images.bin"), "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            f.read(4); q = struct.unpack("<4d", f.read(32)); t = struct.unpack("<3d", f.read(24)); f.read(4)
            while f.read(1) != b"\x00":
                pass
            k = struct.unpack("<Q", f.read(8))[0]; f.read(24 * k)
            w, x, y, z = q
            R = np.array([[1 - 2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1 - 2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1 - 2*(x*x+y*y)]])
            out.append(-R.T @ np.array(t))
    return np.array(out)


def mitte(p):
    with open(os.path.join(p, "points3D.bin"), "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]; pts = []
        for _ in range(n):
            f.read(8); pts.append(struct.unpack("<3d", f.read(24))); f.read(3 + 8); tl = struct.unpack("<Q", f.read(8))[0]; f.read(8 * tl)
    return np.median(np.array(pts), axis=0)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("--mitte", type=float, nargs=3); ap.add_argument("--luecke", type=float, default=90)
    a = ap.parse_args(); C = cams(a.sparse); m = np.array(a.mitte) if a.mitte else mitte(a.sparse)
    # Ebene der Kamerazentren: Hauptachsen mit der kleinsten Varianz als 'oben'
    u, s, vt = np.linalg.svd(C - C.mean(0)); e1, e2 = vt[0], vt[1]
    d = C - m; az = np.degrees(np.arctan2(d @ e2, d @ e1)) % 360
    h, e = np.histogram(az, bins=np.arange(0, 361, 30)); print("Kameras je 30-Grad-Sektor:", dict(zip(e[:-1].astype(int).tolist(), h.tolist())))
    s_az = np.sort(az); gaps = np.diff(np.r_[s_az, s_az[0] + 360]); g = gaps.max(); print("groesste Luecke: %.0f Grad (bei %.0f)" % (g, s_az[gaps.argmax()]))
    if g > a.luecke:
        print("WARNUNG: Kamerakranz hat eine Luecke > %.0f Grad. Geometrie auf der Gegenseite nicht ohne unabhaengige Fotos glauben." % a.luecke); raise SystemExit(2)


if __name__ == "__main__":
    main()
