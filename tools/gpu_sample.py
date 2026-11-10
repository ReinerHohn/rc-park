#!/usr/bin/env python3
"""gpu_sample.py - Oberflaechenpunkte aus einem Dreiecksnetz ziehen, Rechenarbeit auf der GPU, Ergebnis wie trimesh.sample.sample_surface.

Warum: trimesh.sample.sample_surface braucht fuer 2,5 Mio Punkte 1,9-7 s CPU (Fancy-Indexing ueber (n,2,3)-Felder). Hier werden DIESELBEN
Zufallszahlen (numpy-Generator mit gleichem Seed, ~60 ms) gezogen und die Dreiecksrechnung in float64 auf der GPU gemacht:
Punkte sind damit gleich dem CPU-Ergebnis bis auf Rundung (< 1e-9). Ohne CUDA (oder RENDER_CPU=1) faellt es auf trimesh zurueck.
VRAM: n x 3 x 8 B (float64) + Zufallsfelder ~ 150 MiB bei 2,5 Mio Punkten (in Bloecken von 1 Mio gerechnet).
  P = gpu_sample.sample_surface(mesh, n, seed=0)   # (n,3) float64 numpy
"""
import os
import numpy as np


def sample_surface(mesh, count, seed=0, block=1 << 20):
    T = None
    if not os.environ.get("RENDER_CPU"):
        try:
            import torch
            if torch.cuda.is_available(): T = torch
        except Exception:
            T = None
    if T is None or seed is None:
        import trimesh
        return np.asarray(trimesh.sample.sample_surface(mesh, count, seed=seed)[0])
    from trimesh.util import random_generator
    rnd = random_generator(seed).random                                   # gleiche Reihenfolge der Ziehungen wie trimesh
    cum = np.cumsum(mesh.area_faces)
    pick = rnd(count) * cum[-1]
    lens = rnd((count, 2, 1))
    V = T.as_tensor(np.asarray(mesh.vertices, np.float64), device="cuda"); F = T.as_tensor(np.asarray(mesh.faces, np.int64), device="cuda")
    cum_g = T.as_tensor(cum, device="cuda")
    out = np.empty((count, 3), np.float64)
    for a in range(0, count, block):
        b = min(count, a + block)
        fi = T.searchsorted(cum_g, T.as_tensor(pick[a:b], device="cuda"))
        rl = T.as_tensor(lens[a:b], device="cuda")
        tst = rl.sum(dim=1).reshape(-1) > 1.0
        rl = rl.clone(); rl[tst] -= 1.0; rl = rl.abs()
        v0 = V[F[fi, 0]]; e1 = V[F[fi, 1]] - v0; e2 = V[F[fi, 2]] - v0
        s = e1 * rl[:, 0] + e2 * rl[:, 1] + v0
        out[a:b] = s.cpu().numpy()
        del fi, rl, tst, v0, e1, e2, s
    return out
