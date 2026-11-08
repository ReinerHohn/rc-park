#!/usr/bin/env python3
"""dicht_masstab_suche.py <dicht_pts.npy> <alte_wolke.npy> <aus_T.npz> [--von 0.8 --bis 1.2 --schritt 0.02 --iter 20] [Region wie dicht_icp_fein]
Maßstab FEST je Kandidat, starre ICP (R,t) auf der Fensterwand; waehlt den Maßstab mit kleinstem getrimmten Wandfehler.
Grund: freie Aehnlichkeits-ICP schrumpft die Wolke (Maßstab driftete 1.0 -> 0.75 bei fallendem Fehler, 8.11.). Schreibt T (R,s,t) relativ zur Eingabewolke."""
import sys, numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from gpu_knn import naechster
def opt(k, d): return float(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
P = np.load(sys.argv[1]); W = np.load(sys.argv[2]); out = sys.argv[3]; it = int(opt("--iter", 20))
U0, U1, Z0, Z1 = opt("--u0", -9), opt("--u1", 9), opt("--z0", 5.5), opt("--z1", 11)
n = np.array([0.3338, 0.9426]); u = np.array([n[1], -n[0]])
def f(X): return np.c_[X[:, :2] @ u, X[:, :2] @ n, X[:, 2]]
fw = f(W); mw = (fw[:, 0] > U0) & (fw[:, 0] < U1) & (fw[:, 2] > Z0) & (fw[:, 2] < Z1); lo, hi = np.percentile(fw[mw, 1], [2, 98]); B = W[mw & (fw[:, 1] > lo - 1) & (fw[:, 1] < hi + 1)]
fp = f(P); A0 = P[(fp[:, 0] > U0 - 3) & (fp[:, 0] < U1 + 3) & (fp[:, 2] > Z0 - 1) & (fp[:, 2] < Z1 + 1) & (fp[:, 1] > lo - 3) & (fp[:, 1] < hi + 3)]
A0 = A0[np.random.default_rng(0).choice(len(A0), min(len(A0), 200000), replace=False)]; c0 = A0.mean(0)
def kabsch(X, Y):
    mx, my = X.mean(0), Y.mean(0); U, S, Vt = np.linalg.svd((Y - my).T @ (X - mx)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ D @ Vt; return R, my - R @ mx
best = None
for s in np.arange(opt("--von", 0.8), opt("--bis", 1.2) + 1e-9, opt("--schritt", 0.02)):
    As = c0 + s * (A0 - c0); R = np.eye(3); t = np.zeros(3)
    for k in range(it):
        A = (R @ As.T).T + t; d, ix = naechster(A, B); keep = d < np.quantile(d, 0.8); R2, t2 = kabsch(A[keep], B[ix[keep]]); R = R2 @ R; t = R2 @ t + t2
    A = (R @ As.T).T + t; d, _ = naechster(A, B); m = d[d < np.quantile(d, 0.8)].mean(); print("s %.3f  getrimmt-Mittel %.3f  Median %.3f" % (s, m, np.median(d)), flush=True)
    if best is None or m < best[0]: best = (m, s, R.copy(), t.copy())
m, s, R, t = best; # gesamte Abbildung p -> c0 + s*(p-c0) -> R*(.) + t  ==  s*R*p + (R@(c0-s*c0) + t)
np.savez(out, R=R, s=s, t=R @ (c0 - s * c0) + t); print("BESTER Maßstab", round(s, 3), "Fehler", round(m, 3))
