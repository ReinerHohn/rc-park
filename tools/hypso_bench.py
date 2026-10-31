#!/usr/bin/env python3
"""hypso_bench.py - Beschleunigungsvarianten der GPU-Zielfunktion: Zeit UND Gleichheit der Ergebnisse gegen die Referenz (CPU/float64/alle Punkte)."""
import sys, time, numpy as np, torch
sys.path.insert(0, "tools"); import hypso_gpu as H
stl = sys.argv[1] if len(sys.argv) > 1 else "modelle/stl/martinstor_v4_1-87.stl"
P = H.punkte(stl); C = H.combos(H.ANG, H.PH); R = H.ref_areas(H.TS0, 9)
def zeit(f, n=3):
    f(); torch.cuda.synchronize(); t = time.time()
    for _ in range(n): r = f()
    torch.cuda.synchronize(); return r, (time.time() - t) / n
# Referenz: float64, alle Punkte, Fehler auf CPU
ref_H = H.hmaps_gpu(P, C); ref_d = H.fehler(ref_H, H.TS0, 9, R); ref_e = np.abs(ref_d).mean(1); k0 = int(ref_e.argmin())
print(f"Referenz: e={ref_e[k0]:.6f}  Kombination {C[k0].tolist()}  Punkte {len(P)}")
V = [("A float64 alle Punkte (alt)", lambda: H.hmaps_gpu_t(P, C)),
     ("B float64, nur z>19 m", lambda: H.hmaps_gpu_t(P, C, zmin=19.0)),
     ("C float32 alle Punkte", lambda: H.hmaps_gpu_t(P, C, dtype=torch.float32)),
     ("D float32, nur z>19 m", lambda: H.hmaps_gpu_t(P, C, dtype=torch.float32, zmin=19.0)),
     ("E float32, z>19, Chunk 128", lambda: H.hmaps_gpu_t(P, C, dtype=torch.float32, zmin=19.0, chunk=128))]
for name, f in V:
    Ht, t = zeit(f)
    te = time.time(); d = H.fehler_gpu(Ht, H.TS0, 9, R).cpu().numpy(); torch.cuda.synchronize(); tf = time.time() - te
    e = np.abs(d).mean(1); k = int(e.argmin())
    print(f"{name:30s} Hoehenkarten {t*1000:7.0f} ms  Fehler(GPU) {tf*1000:5.0f} ms | e={e[k]:.6f} gleich={bool(np.allclose(e, ref_e, atol=0, rtol=0))} Kombi gleich={k==k0} (max |de| {np.abs(e-ref_e).max():.2e})")
