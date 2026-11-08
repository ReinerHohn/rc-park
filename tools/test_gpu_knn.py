#!/usr/bin/env python3
"""test_gpu_knn.py - GPU-Nachbarsuche gleich CPU-KD-Baum? (min_abstand, naechster, ball_anzahl) auf Zufallsdaten und auf der echten Kaufhaus-Wolke. Exit 1 bei Abweichung.
  /media/oem/scan/venv-seg/bin/python -I tools/test_gpu_knn.py"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from gpu_knn import min_abstand, naechster, ball_anzahl
from scipy.spatial import cKDTree
rng = np.random.default_rng(0); bad = 0
def pruefe(name, A, B):
    global bad
    kd = cKDTree(B); d0, i0 = kd.query(A); d1 = min_abstand(A, B); d2, i2 = naechster(A, B)
    ok1 = np.abs(d0 - d1).max() < 2e-4 * max(1.0, d0.max()); ok2 = np.abs(d0 - d2).max() < 2e-4 * max(1.0, d0.max()); gl = np.mean(i0 == i2)
    c0 = np.array([len(x) for x in kd.query_ball_point(A[:20000], 0.15)]); c1 = ball_anzahl(A[:20000], B, 0.15, kmax=64); ok3 = np.array_equal(np.minimum(c0, 64), c1)
    print(f"{name:28s} min_abstand {'OK' if ok1 else 'FEHLER'}  naechster {'OK' if ok2 else 'FEHLER'} (gleicher Index {100 * gl:.2f} %)  ball_anzahl {'OK' if ok3 else 'FEHLER'}"); bad += (not ok1) + (not ok2) + (not ok3) + (gl < 0.999)
pruefe("Zufall 200k x 50k", rng.random((200000, 3)) * 30, rng.random((50000, 3)) * 30)
P = np.load("/media/oem/scan/rc-park_null/wolke_netzrahmen.npy")[:, :3].astype(np.float32); pruefe("Kaufhaus-Wolke", P[rng.choice(len(P), 300000, replace=False)], P[rng.choice(len(P), 100000, replace=False)])
sys.exit(1 if bad else 0)
