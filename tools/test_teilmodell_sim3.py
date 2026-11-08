#!/usr/bin/env python3
"""Test teilmodell_sim3: synthetische Sim3 (mit Ausreissern, Rauschen, fast ebene Anker), Rotationsvariante, Entartungsmass."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from teilmodell_sim3 import umeyama, anwenden, sim3_robust, rotation_mittel, skala_aus_zentren, entartung, winkel


def zufalls_rot(rng):
    q = rng.normal(size=4); q /= np.linalg.norm(q); w, x, y, z = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def main():
    rng = np.random.default_rng(1)
    for it in range(20):
        s0 = rng.uniform(0.2, 30); R0 = zufalls_rot(rng); t0 = rng.normal(size=3) * 50
        A = rng.normal(size=(40, 3)) * 5; B = anwenden(s0, R0, t0, A) + rng.normal(size=(40, 3)) * 0.01
        n_out = 8; B[:n_out] += rng.normal(size=(n_out, 3)) * 20           # 20 % grobe Ausreisser
        r = sim3_robust(A, B, seed=it)
        assert abs(r["s"] / s0 - 1) < 0.01, (it, r["s"], s0)
        assert winkel(r["R"], R0) < 0.5, it
        assert not r["inlier"][:n_out].any() and r["inlier"][n_out:].all(), it
    # Rotationsvariante: Referenzrotationen aus Welt-Sim3 abgeleitet; Anker entlang einer Linie (Zentren allein entartet)
    s0 = 3.0; R0 = zufalls_rot(rng); t0 = np.array([5., -2, 7])
    n = 12; A = np.stack([np.linspace(0, 10, n), rng.normal(size=n) * 0.01, rng.normal(size=n) * 0.01], 1)
    Rs = [zufalls_rot(rng) for _ in range(n)]; Rr = [r_ @ R0.T for r_ in Rs]         # cam_from_world_ref = cam_from_world_teil * R^T
    B = anwenden(s0, R0, t0, A)
    Rm, ang = rotation_mittel(Rs, Rr)
    assert winkel(Rm, R0) < 1e-2 and max(ang) < 1e-2
    s, t = skala_aus_zentren(A, B, Rm)
    assert abs(s - s0) < 1e-6 and np.allclose(t, t0, atol=1e-5)
    e = entartung(A); assert e["mittel_zu_gross"] < 0.01 and e["klein_zu_gross"] < 0.01
    e2 = entartung(rng.normal(size=(30, 3))); assert e2["klein_zu_gross"] > 0.3
    print("test_teilmodell_sim3: bestanden")


if __name__ == "__main__":
    main()
