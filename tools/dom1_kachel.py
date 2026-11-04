#!/usr/bin/env python3
"""dom1_kachel.py - GENERISCH: DOM1-/DGM1-Hoehe an UTM-Lagen direkt aus den amtlichen LGL-Kacheln (GeoTIFF + .tfw = Mitte des Pixels links oben).

Ersetzt die je Objekt geschnittenen Fenster-npy (Martinstor-Fenster war um eine Lat/Lon-Lage geschnitten, Kaufhaus-Auswertung lag 1 m daneben: 2026-11-04).
  from dom1_kachel import dom1_hoehe; z = dom1_hoehe(E, N)      # NaN ausserhalb vorhandener Kacheln
"""
import glob, numpy as np

_cache = {}


def _kachel(ek, nk, art="dom1"):
    k = (art, ek, nk)
    if k not in _cache:
        f = sorted(glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/{art}_32_{ek}_{nk}_1_bw_*.tif", recursive=True))
        x = sorted(glob.glob(f"/media/oem/scan/rc-park_daten/_geo/**/{art}_32_{ek}_{nk}_1_bw_*.xyz", recursive=True))
        if not f and x:
            # Rueckfall XYZ (LGL-DGM1 liegt teils nur als xyz vor, Martinstor 2026-11-04): Zeilen "E N z" auf Pixelmitten, 1 m Raster
            P = np.loadtxt(x[0], dtype=np.float64); xc, yc = P[:, 0].min(), P[:, 1].max()
            A = np.full((int(round(yc - P[:, 1].min())) + 1, int(round(P[:, 0].max() - xc)) + 1), np.nan, np.float32)
            A[np.round(yc - P[:, 1]).astype(int), np.round(P[:, 0] - xc).astype(int)] = P[:, 2]; A[A < -100] = np.nan
            _cache[k] = (A, xc, yc, x[0])
        elif not f: _cache[k] = None
        else:
            from PIL import Image; Image.MAX_IMAGE_PIXELS = None
            A = np.array(Image.open(f[0])).astype(np.float32); A[A < -100] = np.nan; tf = [float(x) for x in open(f[0][:-4] + ".tfw")]
            _cache[k] = (A, tf[4], tf[5], f[0])
    return _cache[k]


def dom1_hoehe(E, N, art="dom1"):
    E, N = np.asarray(E, float), np.asarray(N, float); z = np.full(E.shape, np.nan)
    ek, nk = (E // 1000).astype(int), (N // 1000).astype(int)
    for a, b in set(zip(ek.ravel().tolist(), nk.ravel().tolist())):
        K = _kachel(a, b, art)
        if K is None: continue
        A, xc, yc, _ = K; m = (ek == a) & (nk == b); j = np.round(E[m] - xc).astype(int); i = np.round(yc - N[m]).astype(int)
        ok = (i >= 0) & (i < A.shape[0]) & (j >= 0) & (j < A.shape[1]); zz = np.full(m.sum(), np.nan); zz[ok] = A[i[ok], j[ok]]; z[m] = zz
    return z
