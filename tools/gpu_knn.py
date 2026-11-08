"""gpu_knn.py - naechster Abstand auf der GPU (PyTorch3D knn_points, 0,13 s fuer 750k x 40k; torch.cdist waere 24x langsamer, KD-Baum CPU ~3 s). Nutzerregel: GPU immer nutzen.
  from gpu_knn import min_abstand;  d = min_abstand(A, B)   # fuer jede Zeile von A (N,3) der Abstand zum naechsten Punkt in B (M,3), numpy float32"""
import sys; sys.path.insert(0, "/media/oem/scan/p3d_site")
import numpy as np, torch
from pytorch3d.ops import knn_points
def min_abstand(A, B, blk=2_000_000):
    Bt = torch.as_tensor(np.asarray(B, np.float32), device="cuda")[None]; out = []
    for i in range(0, len(A), blk):
        At = torch.as_tensor(np.asarray(A[i:i + blk], np.float32), device="cuda")[None]; out.append(knn_points(At, Bt, K=1).dists[0, :, 0].sqrt().cpu().numpy())
    return np.concatenate(out)

def naechster(A, B, blk=2_000_000):
    """(Abstand, Index) des naechsten Punkts in B fuer jede Zeile von A (Ersatz fuer cKDTree(B).query(A))."""
    Bt = torch.as_tensor(np.asarray(B, np.float32), device="cuda")[None]; ds, ix = [], []
    for i in range(0, len(A), blk):
        At = torch.as_tensor(np.asarray(A[i:i + blk], np.float32), device="cuda")[None]; r = knn_points(At, Bt, K=1)
        ds.append(r.dists[0, :, 0].sqrt().cpu().numpy()); ix.append(r.idx[0, :, 0].cpu().numpy())
    return np.concatenate(ds), np.concatenate(ix)

def ball_anzahl(A, B, radius, kmax=64, blk=500_000):
    """Anzahl der Punkte von B im Radius um jede Zeile von A, GEDECKELT bei kmax (genuegt fuer Schwellen 'mindestens k Punkte'; Ersatz fuer len(query_ball_point))."""
    from pytorch3d.ops import ball_query
    Bt = torch.as_tensor(np.asarray(B, np.float32), device="cuda")[None]; out = []
    for i in range(0, len(A), blk):
        At = torch.as_tensor(np.asarray(A[i:i + blk], np.float32), device="cuda")[None]; out.append((ball_query(At, Bt, K=kmax, radius=float(radius)).idx[0] >= 0).sum(1).cpu().numpy())
    return np.concatenate(out)
