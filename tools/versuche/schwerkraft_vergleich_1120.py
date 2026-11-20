"""Schwerkraft-A/B Schwabentor: jedes Modell per Aehnlichkeitstransformation (Umeyama, gemeinsame Kameras) auf 'alt' legen;
Kennzahlen: Bilder, Median-Abstand der Kamerazentren in % der Szenengroesse, Zahl Springer (> 0,4 %)."""
import sys, glob, numpy as np
sys.path.append("/media/oem/scan/venv-colmap/lib/python3.12/site-packages"); import pycolmap
def zentren(p): r = pycolmap.Reconstruction(p); return {i.name: i.projection_center() for i in r.images.values()}
def umeyama(X, Y):
    mx, my = X.mean(0), Y.mean(0); Xc, Yc = X - mx, Y - my; U, S, Vt = np.linalg.svd(Yc.T @ Xc / len(X)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / Xc.var(0).sum(); return s, R, my - s * R @ mx
ref = zentren("/media/oem/rcdaten/tmp/colmap_ab/alt/sparse/0"); Rv = np.array(list(ref.values())); gr = np.linalg.norm(Rv.max(0) - Rv.min(0))
laeufe = sorted(glob.glob("/media/oem/rcdaten/tmp/colmap_ab/*/sparse/0")) + sorted(glob.glob("/media/oem/rcdaten/tmp/schwerkraft/schwer*/sparse/0"))
for p in laeufe:
    z = zentren(p); g = [n for n in z if n in ref]; X = np.array([z[n] for n in g]); Y = np.array([ref[n] for n in g])
    s, R, t = umeyama(X, Y)
    for _ in range(3):                                    # robust: Springer aus der Anpassung nehmen
        d = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1); m = d < np.percentile(d, 90); s, R, t = umeyama(X[m], Y[m])
    d = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1) / gr * 100
    print(f"{p.split('/')[-3]:22s} Bilder {len(z):4d} | Median {np.median(d):.3f} %, p90 {np.percentile(d, 90):.3f} %, Springer >0,4 %: {(d > 0.4).sum()}")
