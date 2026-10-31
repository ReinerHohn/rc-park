#!/usr/bin/env python3
"""optimierung_validieren.py - Prueft, ob eine 'Verbesserung' echt ist oder nur Anpassung ans Raster (Ueberanpassung).
Bewertet zwei STL (alt, neu) mit vier Massstaeben, die NICHT zur Optimierung gehoerten:
  M1 andere Hoehenstufen (zwischen den optimierten)   M2 grosser Umkreis (13 m statt 9 m)
  M3 feineres Raster (Phase 0,25 m, Drehung 1 Grad)   M4 punktweise Hoehe im 4,5-m-Umkreis der Spitze
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/optimierung_validieren.py alt.stl neu.stl"""
import sys, numpy as np, trimesh
DOM = "/media/oem/scan/tmp/mt_dom/mt_win.npy"; N = 60
ref = np.load(DOM) - 277.98
yy, xx = np.mgrid[:N, :N]; PR = np.unravel_index(np.argmax(ref), ref.shape)
def area(A, pk, t, r): return int(((A > t) & (np.hypot(yy - pk[0], xx - pk[1]) <= r)).sum())

def load(stl):
    m = trimesh.load(stl); m.apply_scale(87 / 1000.0)
    v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=0.3, max_iter=14)
    return v[f].mean(1)

def hmap(P, ang, dx, dy):
    c, s = np.cos(np.radians(ang)), np.sin(np.radians(ang))
    x = c * P[:, 0] - s * P[:, 1] + dx; y = s * P[:, 0] + c * P[:, 1] + dy
    ix = np.floor(x + N / 2).astype(int); iy = np.floor(N / 2 - y).astype(int)
    ok = (ix >= 0) & (ix < N) & (iy >= 0) & (iy < N); H = np.zeros((N, N)); np.maximum.at(H, (iy[ok], ix[ok]), P[ok, 2]); return H

def hyps(P, TS, r, angs, phs):
    R = [max(area(ref, PR, t, r), 1) for t in TS]; best = None
    for a in angs:
        for dx in phs:
            for dy in phs:
                H = hmap(P, a, dx, dy); pm = np.unravel_index(np.argmax(H), H.shape)
                d = np.array([area(H, pm, t, r) / q - 1 for t, q in zip(TS, R)]); e = np.abs(d).mean()
                if best is None or e < best[0]: best = (e, a, dx, dy, np.median(np.abs(d)))
    return best

def punktweise(P):
    win = np.hypot(yy - PR[0], xx - PR[1]) <= 4.5; best = None
    for a in np.arange(86, 112, 1.0):
        for dx in np.arange(-1.5, 1.51, .25):
            for dy in np.arange(-1.5, 1.51, .25):
                H = hmap(P, a, dx, dy); e = np.abs(H - ref)[win].mean()
                if best is None or e < best[0]: best = (e, (H - ref)[win].mean())
    return best

if __name__ == "__main__":
    names = sys.argv[1:]; Ps = [load(x) for x in names]
    T1 = (22, 26, 30, 33, 36, 39, 41, 43, 45, 47, 49, 51); T0 = (20, 24, 28, 32, 35, 38, 40, 42, 44, 46, 48, 50, 52)
    short = [x.split("/")[-1][:12] for x in names]
    print(f"{'Mass':34s}" + "".join(f"{n:>16s}" for n in short), flush=True)
    for nm, fn in (("Optimierungsziel (13 Stufen)", lambda P: hyps(P, T0, 9, np.arange(88, 110, 2.0), (-1, -.5, 0, .5, 1))),
                   ("M1 andere Stufen", lambda P: hyps(P, T1, 9, np.arange(88, 110, 2.0), (-1, -.5, 0, .5, 1))),
                   ("M2 Umkreis 13 m", lambda P: hyps(P, T0, 13, np.arange(88, 110, 2.0), (-1, -.5, 0, .5, 1))),
                   ("M3 feines Raster", lambda P: hyps(P, T1, 9, np.arange(86, 112, 1.0), np.arange(-1, 1.01, .25)))):
        r = [fn(P) for P in Ps]
        print(f"{nm:34s}" + "".join(f"{100*x[0]:10.1f} % m{100*x[4]:3.0f}" for x in r), flush=True)
    r = [punktweise(P) for P in Ps]
    print(f"{'M4 punktweise Hoehe, |m|':34s}" + "".join(f"{x[0]:11.2f} m   " for x in r))
