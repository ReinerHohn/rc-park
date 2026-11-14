"""Abstand dichter Wolkenpunkte zu den triangulierten Sparse-Punkten (allgemein, je Objekt).

Die Sparse-Punkte (COLMAP points3D.bin) sind mehrfach gesehen und stuetzen sich gegenseitig. Dichte Punkte,
die weit von allen Sparse-Punkten liegen, sind nicht durch die Triangulation bestaetigt.
Kennzahl ohne Einheit: Abstand / typischer Sparse-Abstand (Median des Sparse-zu-Sparse-Nachbarn).

Aufruf: python3 tools/wolke_sparse_abstand.py <dicht-ordner mit fused.ply und sparse/points3D.bin>
Ausgabe: Quantile der normierten Abstaende und Anteil ueber 5x Sparse-Abstand.
"""
import argparse, os, struct
import numpy as np
from scipy.spatial import cKDTree


def sparse_punkte(p):
    xyz = []
    with open(p, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        for _ in range(n):
            f.read(8)
            xyz.append(struct.unpack("<3d", f.read(24)))
            f.read(3 + 8)
            tl = struct.unpack("<Q", f.read(8))[0]
            f.read(8 * tl)
    return np.array(xyz)


def dicht_xyz(ply):
    with open(ply, "rb") as f:
        n = None
        while True:
            line = f.readline().decode().strip()
            if line.startswith("element vertex"):
                n = int(line.split()[-1])
            if line == "end_header":
                break
        dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"),
                       ("r", "u1"), ("g", "u1"), ("b", "u1")])
        a = np.fromfile(f, dtype=dt, count=n)
    return np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dicht")
    a = ap.parse_args()
    S = sparse_punkte(os.path.join(a.dicht, "sparse", "points3D.bin"))
    X = dicht_xyz(os.path.join(a.dicht, "fused.ply"))
    tS = cKDTree(S)
    d2, _ = tS.query(S, k=2)
    typ = np.median(d2[:, 1])
    d, _ = tS.query(X, k=1)
    r = d / typ
    print("Sparse %d, Dicht %d, typischer Sparse-Abstand %.4f" % (len(S), len(X), typ))
    print("normierter Abstand Dicht->Sparse: Median %.2f, p90 %.2f, p99 %.2f" % (
        np.median(r), np.percentile(r, 90), np.percentile(r, 99)))
    print("Anteil > 5x Sparse-Abstand: %.4f" % float(np.mean(r > 5)))


if __name__ == "__main__":
    main()
