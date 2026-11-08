#!/usr/bin/env python3
"""wolke_streiffilter.py - BS43: Punkte streichen, deren PCA-Normale von KEINER Aufnahmeposition aus 'frontal' gesehen wird
(max_c |n.v_c| < --schwelle, v_c = Einheitsvektor Punkt->Kamerazentrum c): Streifen entlang der Sehstrahlen. Kameras aus messprotokoll/K-*.json standort_xyz (Kamerarahmen).
  venv-seg/bin/python -I tools/wolke_streiffilter.py in.npy objekt.json out.npy [--k 20 --schwelle 0.35]"""
import sys, os, json, glob, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("objekt"); ap.add_argument("aus"); ap.add_argument("--k", type=int, default=20); ap.add_argument("--schwelle", type=float, default=0.35)
a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt))
C = np.array([json.load(open(p))["kamera"]["standort_xyz"] for p in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")) if "standort_xyz" in json.load(open(p)).get("kamera", {})], float)
print("Kameras", len(C)); X = np.load(a.ein).astype(np.float64); m = np.empty(len(X), np.float32)
sys.path.insert(0, "/media/oem/scan/p3d_site"); import torch; from pytorch3d.ops import knn_points         # GPU (Nutzerregel): kNN + Eigenzerlegung batchweise auf CUDA
def kleinster_ev(A):
    """Eigenvektor zum kleinsten Eigenwert symmetrischer 3x3 (geschlossen, Smith; torch.linalg.eigh batched belegt auf CUDA ~0,5 MB je Matrix = 101 GiB bei 200k)."""
    q = (A[:, 0, 0] + A[:, 1, 1] + A[:, 2, 2]) / 3; p1 = A[:, 0, 1] ** 2 + A[:, 0, 2] ** 2 + A[:, 1, 2] ** 2
    p2 = (A[:, 0, 0] - q) ** 2 + (A[:, 1, 1] - q) ** 2 + (A[:, 2, 2] - q) ** 2 + 2 * p1; p = (p2 / 6).sqrt().clamp_min(1e-30)
    B = (A - q[:, None, None] * torch.eye(3, dtype=A.dtype, device=A.device)) / p[:, None, None]; r = (torch.linalg.det(B) / 2).clamp(-1, 1)
    lam = q + 2 * p * torch.cos(torch.acos(r) / 3 + 2 * np.pi / 3); M = A - lam[:, None, None] * torch.eye(3, dtype=A.dtype, device=A.device)
    c = torch.stack([torch.linalg.cross(M[:, 0], M[:, 1]), torch.linalg.cross(M[:, 0], M[:, 2]), torch.linalg.cross(M[:, 1], M[:, 2])], 1)
    j = c.norm(dim=2).argmax(1); e = c[torch.arange(len(c)), j]; return e / e.norm(dim=1, keepdim=True).clamp_min(1e-30)
dev = "cuda"; Xg = torch.tensor(X - X.mean(0), dtype=torch.float32, device=dev)[None]; Cg = torch.tensor(C - X.mean(0), dtype=torch.float32, device=dev)
for i in range(0, len(X), 200000):
    q = Xg[:, i:i + 200000]; idx = knn_points(q, Xg, K=a.k).idx[0]; Nn = Xg[0][idx]; Nn = Nn - Nn.mean(1, keepdim=True)
    n = kleinster_ev(torch.einsum("nki,nkj->nij", Nn, Nn).double()).float()
    V = Cg[None] - q[0][:, None, :]; V = V / V.norm(dim=2, keepdim=True)
    m[i:i + 200000] = torch.einsum("ni,nci->nc", n, V).abs().max(1).values.cpu().numpy()
keep = m >= a.schwelle; print(f"Punkte {len(X)} -> {int(keep.sum())} ({100*keep.mean():.1f} %), max|n.v| Median {np.median(m):.2f} P10 {np.percentile(m,10):.2f}")
np.save(a.aus, X[keep].astype(np.float32))
