#!/usr/bin/env python3
"""iphone_ausrichten.py <sparse/0> <wolke.npy> <aus.npy> - Aehnlichkeits-ICP (GPU knn): SfM-Punkte -> Wolke. Start: Hochachse per PCA-Minimum, 36 Drehungen um Hoehe x Massstab aus Hoehen-Verhaeltnis."""
import sys, numpy as np
sys.path.insert(0, "/media/oem/scan/p3d_site"); import torch
from pytorch3d.ops import knn_points
S = np.load(sys.argv[1]).astype(np.float32)
W = np.load(sys.argv[2])[:, :3].astype(np.float32)
def pca(X):
    c = X.mean(0); u, s, vt = np.linalg.svd(X[::10] - c, full_matrices=False); return c, vt
cs, vs = pca(S); cw, vw = pca(W)
def rob(X): lo, hi = np.percentile(X, [2, 98], 0); return hi - lo
G = lambda a: torch.tensor(a, dtype=torch.float32, device="cuda")[None]; WG = G(W[::3])
def icp(R, s, t, n=40):
    for _ in range(n):
        Q = (s * S @ R.T + t); Qg = G(Q); idx = knn_points(Qg, WG, K=1); d = idx.dists[0, :, 0].sqrt().cpu().numpy(); j = idx.idx[0, :, 0].cpu().numpy()
        k = d < max(np.percentile(d, 60), 0.3); A = S[k]; B = W[::3][j[k]]
        ma, mb = A.mean(0), B.mean(0); H = (A - ma).T @ (B - mb); U, D, Vt = np.linalg.svd(H); Dm = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]); R = Vt.T @ Dm @ U.T
        s = float(np.trace(np.diag(D) @ Dm) / ((A - ma) ** 2).sum()); t = mb - s * ma @ R.T
    return R, s, t, float(np.median(d[k])), float(k.mean())
best = None
# Hochachse SfM = kleinste PCA-Achse oder jede der 3: alle 3 Achsen x 2 Vorzeichen x 12 Drehungen, Massstab aus Ausdehnung
for ax in range(3):
    for sg in (1, -1):
        up = vs[ax] * sg; e1 = vs[(ax + 1) % 3]; e2 = np.cross(up, e1); Rs = np.stack([e1, e2, up])        # SfM -> lokal (up = z)
        for ang in np.arange(0, 360, 30):
            c, s_ = np.cos(np.radians(ang)), np.sin(np.radians(ang)); Rz = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
            R0 = vw[::-1][[0, 1, 2]].T if False else np.eye(3)
            R = Rz @ Rs; sc = np.linalg.norm(rob(W)[:2]) / max(np.linalg.norm(rob(S @ R.T)[:2]), 1e-9)
            t = W.mean(0) - sc * (S @ R.T).mean(0)
            Rr, s, tt, med, fr = icp(R, sc, t, 25)
            if best is None or med < best[0]: best = (med, Rr, s, tt, fr); print(f"ax{ax} {sg:+d} {ang:3d}  Median {med:.3f} Anteil {fr:.2f} s {s:.3f}", flush=True)
med, R, s, t, fr = best; R, s, t, med, fr = icp(R, s, t, 80); print(f"ENDE Median {med:.3f} m Anteil {fr:.2f} Massstab {s:.4f}")
np.save(sys.argv[3], np.concatenate([S @ R.T * s + t], 0).astype(np.float32)); np.savez(sys.argv[3].replace(".npy", "_T.npz"), R=R, s=s, t=t)
