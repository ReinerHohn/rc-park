#!/usr/bin/env python3
"""wolke_linienfilter.py - BS42: streicht linienartige Punktnachbarschaften (Tiefenzapfen entlang Sehstrahl). PCA je Punkt (k Nachbarn):
Linearitaet L=(l1-l2)/l1 > --lin => weg. Eingabe/Ausgabe npy (Kamerarahmen). Gemessen wird danach per wolke_ueber_foto.py --npy.
  venv-seg/bin/python -I tools/wolke_linienfilter.py in.npy out.npy [--k 25 --lin 0.85]"""
import sys, argparse, numpy as np
from scipy.spatial import cKDTree
ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("aus"); ap.add_argument("--k", type=int, default=25); ap.add_argument("--lin", type=float, default=0.85)
a = ap.parse_args(); X = np.load(a.ein).astype(np.float64); t = cKDTree(X); L = np.empty(len(X), np.float32)
for i in range(0, len(X), 200000):
    _, idx = t.query(X[i:i + 200000], k=a.k, workers=-1); N = X[idx] - X[idx].mean(1, keepdims=True)
    C = np.einsum("nki,nkj->nij", N, N) / a.k; w = np.linalg.eigvalsh(C); L[i:i + 200000] = (w[:, 2] - w[:, 1]) / np.maximum(w[:, 2], 1e-12)
    print(i, flush=True)
keep = L <= a.lin; print(f"Punkte {len(X)} -> {int(keep.sum())} ({100*keep.mean():.1f} %), Linearitaet Median {np.median(L):.2f} P90 {np.percentile(L,90):.2f}")
np.save(a.aus, X[keep].astype(np.float32))
