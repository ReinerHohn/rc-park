#!/usr/bin/env python3
"""dicht_verformen.py <dicht_pts.npy> <alte_wolke.npy> <aus_prefix> [--iter 15] [--u0 -14 --u1 14 --z0 4 --z1 12] [--ordnung 2]
Verformende Ausrichtung (Regel: Wolken verziehen sich ueber 25 m Fassade, starre Aehnlichkeit reicht nicht):
glattes Verschiebungsfeld d(u,n,z) = Polynom (Ordnung 1 = affin, 2 = +quadratisch) je Komponente, aus getrimmten GPU-NN-Korrespondenzen
(dichte Wolke -> alte Wolke) im Wandbereich, iteriert. Schreibt <prefix>_koef.npy und <prefix>_pts.npy (verformte dichte Wolke)."""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from gpu_knn import naechster
def opt(k, d): return float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
P = np.load(sys.argv[1]); W = np.load(sys.argv[2]); pre = sys.argv[3]; it = int(opt("--iter", 15)); od = int(opt("--ordnung", 2)); U0, U1, Z0, Z1 = opt("--u0", -14), opt("--u1", 14), opt("--z0", 4), opt("--z1", 12)
n = np.array([0.3338, 0.9426]); u = np.array([n[1], -n[0]])
def f(X): return np.c_[X[:, :2] @ u, X[:, :2] @ n, X[:, 2]]
def basis(F):  # Polynom in (u, n-13, z-8) auf Maßstab ~10 m
    a, b, c = F[:, 0] / 10, (F[:, 1] - 13) / 10, (F[:, 2] - 8) / 10; cols = [np.ones_like(a), a, b, c]
    if od >= 2: cols += [a * a, a * c, c * c]
    return np.stack(cols, 1)
fw = f(W); mw = (fw[:, 0] > U0) & (fw[:, 0] < U1) & (fw[:, 2] > Z0) & (fw[:, 2] < Z1) & (fw[:, 1] > 9) & (fw[:, 1] < 20); B = W[mw]
Fp = f(P); sel = (Fp[:, 0] > U0) & (Fp[:, 0] < U1) & (Fp[:, 2] > Z0) & (Fp[:, 2] < Z1) & (Fp[:, 1] > 9) & (Fp[:, 1] < 21)
A0 = P[sel][np.random.default_rng(0).choice(sel.sum(), min(sel.sum(), 300000), replace=False)]
K = basis(f(A0)).shape[1]; C = np.zeros((K, 3)); 
def anwenden(X, C): return X + basis(f(X)) @ C
for k in range(it):
    A = anwenden(A0, C); d, ix = naechster(A, B); keep = d < np.quantile(d, 0.75); Bm = B[ix[keep]]; Am = A0[keep]
    # Fehler im Rahmen: Ziel = Bm - Am = basis @ C (kleinste Quadrate, leicht regularisiert)
    Phi = basis(f(Am)); C = np.linalg.solve(Phi.T @ Phi + 1e-3 * np.eye(K), Phi.T @ (Bm - Am))
    if k % 3 == 0 or k == it - 1: print(k, "Median", np.median(d).round(3), "getrimmt", d[keep].mean().round(3), "max |C|", np.abs(C).max().round(2))
np.save(pre + "_koef.npy", C); np.save(pre + "_pts.npy", anwenden(P, C).astype(np.float32)); print("gespeichert", pre)
