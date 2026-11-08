#!/usr/bin/env python3
"""dicht_icp_fein.py <netz_pts.npy> <alte_wolke.npy> <aus_T.npz> [--iter 30]
Feine Aehnlichkeits-ICP (Umeyama, getrimmt) der dichten Wolke gegen die alte Wolke im Gebaeudebereich (Fassadenband). GPU-knn.
Schreibt T2 (R,s,t) so, dass p'' = s*R@p' + t auf die bereits grob ausgerichtete Wolke p' wirkt."""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from gpu_knn import naechster
P = np.load(sys.argv[1]); W = np.load(sys.argv[2]); out = sys.argv[3]; it = int(sys.argv[sys.argv.index("--iter") + 1]) if "--iter" in sys.argv else 30
def opt(k, d): return float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
U0, U1, Z0, Z1 = opt("--u0", -12), opt("--u1", 8), opt("--z0", 0.5), opt("--z1", 20); TRIM = opt("--trim", 0.7)
n = np.array([0.3338, 0.9426]); u = np.array([n[1], -n[0]])
def f(X): return np.c_[X[:, :2] @ u, X[:, :2] @ n, X[:, 2]]
fw = f(W); mw = (fw[:, 0] > U0) & (fw[:, 0] < U1) & (fw[:, 2] > Z0) & (fw[:, 2] < Z1); lo, hi = np.percentile(fw[mw, 1], [2, 98])
B = W[mw & (fw[:, 1] > lo - 1) & (fw[:, 1] < hi + 1)]
fp = f(P); A0 = P[(fp[:, 0] > U0) & (fp[:, 0] < U1) & (fp[:, 2] > Z0) & (fp[:, 2] < Z1) & (fp[:, 1] > lo - 1.5) & (fp[:, 1] < hi + 1.5)]
A0 = A0[np.random.default_rng(0).choice(len(A0), min(len(A0), 300000), replace=False)]
R = np.eye(3); sc = 1.0; t = np.zeros(3)
def umeyama(X, Y):
    mx, my = X.mean(0), Y.mean(0); Xc, Yc = X - mx, Y - my; U, S, Vt = np.linalg.svd(Yc.T @ Xc / len(X)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    Rr = U @ D @ Vt; ss = np.trace(np.diag(S) @ D) / Xc.var(0).sum(); return Rr, ss, my - ss * Rr @ mx
for k in range(it):
    A = (sc * (R @ A0.T)).T + t; d, ix = naechster(A, B); keep = d < np.quantile(d, TRIM)
    R2, s2, t2 = umeyama(A[keep], B[ix[keep]]); R = R2 @ R; sc = s2 * sc; t = s2 * (R2 @ t) + t2
    if k % 5 == 0 or k == it - 1: print(k, "Median", np.median(d).round(3), "getrimmt-Mittel", d[keep].mean().round(3), "s", round(sc, 4))
np.savez(out, R=R, s=sc, t=t); print("T2 gespeichert", out)
