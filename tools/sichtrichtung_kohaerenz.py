"""Sichtrichtungs-Kohaerenz je Wolkenpunkt (allgemein, fuer jedes Objekt mit Dichte-Wolke + vis + Kameras).

Idee: Eine echte sichtbare Oberflaeche wird nur aus einer Halbraum-Seite gesehen, alle Sichtstrahlen
(Kamera -> Punkt) zeigen also ungefaehr in dieselbe Richtung. Sehen Kameras von GEGENUEBERLIEGENDEN
Seiten denselben Punkt, ist der Punkt ein Mischtreffer (Doppelgeometrie / falsches Gegenstueck).
Kennzahl: Kohaerenz = |Mittel der Einheits-Sichtstrahlen| in 0..1. Niedrig = widerspruechlich.

Aufruf:
  python3 tools/sichtrichtung_kohaerenz.py <objekt-sfm-ordner> <dicht-ordner> [--min_sicht 3] [--schwelle 0.5]
  <objekt-sfm-ordner>: enthaelt sparse/cameras.bin und sparse/images.bin (COLMAP, Bildindex = sortierte ID)
  <dicht-ordner>: enthaelt fused.ply (SfM-Frame, Reihenfolge wie vis) und fused.ply.vis
Ausgabe: <dicht-ordner>/kohaerenz.npz (je Punkt Kohaerenz, Anzahl Sichtungen), Zusammenfassung auf stdout.

Hinweis: vis-Index = Position der Bild-ID in der SORTIERTEN Bildliste (am Schwabentor geprueft: 150/150).

ERGEBNIS Schwabentor (2026-11-14, NEGATIV): Der verschobene Fluegel hat Kohaerenz-Median 0,97 (Fassade 0,95).
Er wird von einer Kameragruppe aus EINER Richtung gesehen. Der Test erkennt den Fehler also NICHT. Er
bleibt als Werkzeug, taugt aber nicht als Fehlerdetektor fuer gruppenweise falsche Posen.
"""
import argparse, os, struct
import numpy as np


def read_cameras_images(sparse):
    with open(os.path.join(sparse, "images.bin"), "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        imgs = []
        for _ in range(n):
            iid = struct.unpack("<i", f.read(4))[0]
            q = struct.unpack("<4d", f.read(32)); t = struct.unpack("<3d", f.read(24))
            f.read(4)
            while f.read(1) != b"\x00":
                pass
            n2d = struct.unpack("<Q", f.read(8))[0]
            f.read(24 * n2d)
            imgs.append((iid, q, t))
    imgs.sort(key=lambda x: x[0])
    centers = []
    for iid, q, t in imgs:
        w, x, y, z = q
        R = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        centers.append(-R.T @ np.array(t))
    return np.array(centers)


def vis_flach(p):
    b = np.fromfile(p, dtype="<u4")
    n = int(b[0]) | (int(b[1]) << 32)
    i = 2
    pts, cams = [], []
    for k in range(n):
        c = int(b[i]); cams.append(b[i + 1:i + 1 + c]); pts.append(np.full(c, k, np.int64)); i += 1 + c
    return np.concatenate(pts), np.concatenate(cams).astype(np.int64)


def fused_xyz(ply):
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
    ap.add_argument("sfm"); ap.add_argument("dicht")
    ap.add_argument("--min_sicht", type=int, default=3)
    ap.add_argument("--schwelle", type=float, default=0.5)
    a = ap.parse_args()
    X = fused_xyz(os.path.join(a.dicht, "fused.ply"))
    cams = read_cameras_images(os.path.join(a.sfm, "sparse"))
    pidx, cidx = vis_flach(os.path.join(a.dicht, "fused.ply.vis"))
    n = len(X)
    ray = X[pidx] - cams[cidx]
    ray /= np.linalg.norm(ray, axis=1, keepdims=True)
    sumv = np.zeros((n, 3)); np.add.at(sumv, pidx, ray)
    cnt = np.bincount(pidx, minlength=n)
    with np.errstate(divide="ignore", invalid="ignore"):
        koh = np.linalg.norm(sumv, axis=1) / cnt
    koh[cnt == 0] = np.nan
    np.savez(os.path.join(a.dicht, "kohaerenz.npz"), koh=koh, cnt=cnt)
    ok = cnt >= a.min_sicht
    print("Punkte", n, "mit >= %d Sichtungen" % a.min_sicht, int(ok.sum()))
    print("Kohaerenz Median %.3f, Anteil < %.2f: %.3f" % (np.nanmedian(koh[ok]), a.schwelle, float(np.mean(koh[ok] < a.schwelle))))


if __name__ == "__main__":
    main()
