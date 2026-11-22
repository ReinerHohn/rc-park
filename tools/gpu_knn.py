"""gpu_knn.py - naechster Abstand auf der GPU (PyTorch3D knn_points, 0,13 s fuer 750k x 40k; torch.cdist waere 24x langsamer, KD-Baum CPU ~3 s). Nutzerregel: GPU immer nutzen.
  from gpu_knn import min_abstand;  d = min_abstand(A, B)   # fuer jede Zeile von A (N,3) der Abstand zum naechsten Punkt in B (M,3), numpy float32
22.11.2026 (Lage-Pruefstand, CPU-Laeufe waehrend eines Kettenjobs): ohne sichtbare CUDA-Karte (geraet() != 'cuda', z. B. CUDA_VISIBLE_DEVICES='') stuerzten alle drei
Funktionen ab (device='cuda' fest). Jetzt Rueckfall auf scipy cKDTree (gleiche Rueckgabe; Abstaende in float64 statt float32). Mit Karte unveraendert."""
import sys; sys.path.insert(0, "/media/oem/scan/p3d_site")
import numpy as np, torch
from pytorch3d.ops import knn_points


def geraet():
    """'cuda', wenn eine CUDA-Karte sichtbar ist, sonst 'cpu' (dann rechnen die Funktionen mit scipy cKDTree)."""
    return "cuda" if torch.cuda.is_available() else "cpu"


def min_abstand(A, B, blk=2_000_000):
    if geraet() != "cuda":
        from scipy.spatial import cKDTree
        return cKDTree(np.asarray(B, float)).query(np.asarray(A, float))[0]
    Bt = torch.as_tensor(np.asarray(B, np.float32), device="cuda")[None]; out = []
    for i in range(0, len(A), blk):
        At = torch.as_tensor(np.asarray(A[i:i + blk], np.float32), device="cuda")[None]; out.append(knn_points(At, Bt, K=1).dists[0, :, 0].sqrt().cpu().numpy())
    return np.concatenate(out)

def naechster(A, B, blk=2_000_000):
    """(Abstand, Index) des naechsten Punkts in B fuer jede Zeile von A (Ersatz fuer cKDTree(B).query(A))."""
    if geraet() != "cuda":
        from scipy.spatial import cKDTree
        return cKDTree(np.asarray(B, float)).query(np.asarray(A, float))
    Bt = torch.as_tensor(np.asarray(B, np.float32), device="cuda")[None]; ds, ix = [], []
    for i in range(0, len(A), blk):
        At = torch.as_tensor(np.asarray(A[i:i + blk], np.float32), device="cuda")[None]; r = knn_points(At, Bt, K=1)
        ds.append(r.dists[0, :, 0].sqrt().cpu().numpy()); ix.append(r.idx[0, :, 0].cpu().numpy())
    return np.concatenate(ds), np.concatenate(ix)

def ball_anzahl(A, B, radius, kmax=64, blk=500_000):
    """Anzahl der Punkte von B im Radius um jede Zeile von A, GEDECKELT bei kmax (genuegt fuer Schwellen 'mindestens k Punkte'; Ersatz fuer len(query_ball_point))."""
    if geraet() != "cuda":
        from scipy.spatial import cKDTree
        return np.minimum(cKDTree(np.asarray(B, float)).query_ball_point(np.asarray(A, float), float(radius), return_length=True), kmax)
    from pytorch3d.ops import ball_query
    Bt = torch.as_tensor(np.asarray(B, np.float32), device="cuda")[None]; out = []
    for i in range(0, len(A), blk):
        At = torch.as_tensor(np.asarray(A[i:i + blk], np.float32), device="cuda")[None]; out.append((ball_query(At, Bt, K=kmax, radius=float(radius)).idx[0] >= 0).sum(1).cpu().numpy())
    return np.concatenate(out)
