#!/usr/bin/env python3
"""test_quellfilter_gpu.py [workspace] - GPU-Zaehlung des Quellfilters gleich der CPU-Zaehlung (26.11.2026). Ohne Workspace: synthetischer Test (eine Ebene + Hintergrund).
Mit Workspace (entzerrt: sparse/, stereo/depth_maps): 300 000 Punkte der Wolke, alle Kameras; Soll: >= 99,9 % gleiche nq UND nv, Entscheidungen 'weg' >= 99,99 % gleich.
Verwandt: tools/quellfilter.py, tools/quellfilter_gpu.py. Vorlaeufer: keiner - die CPU-Rechnung war nie gegen eine zweite Implementierung gemessen."""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quellfilter as QF
from pfade import temp_ordner


def synthetisch():
    d = temp_ordner("test_quellfilter_gpu_"); h, w = 60, 80; tief = np.full((h, w), 10.0, np.float32); tief[:, :40] = 5.0
    f = os.path.join(d, "t.bin"); open(f, "wb").write(f"{w}&{h}&1&".encode() + tief.tobytes())
    rng = np.random.default_rng(1); X = np.c_[rng.uniform(-2, 2, 4000), rng.uniform(-1.5, 1.5, 4000), rng.choice([5.0, 10.0, 7.0], 4000)].astype(np.float32)
    kam = [((80.0, 80.0, 40.0, 30.0), np.eye(3, dtype=np.float32), np.zeros(3, np.float32), 80, 60, QF.Karte(f))]
    return X, kam


def main():
    if len(sys.argv) > 1:
        ws = sys.argv[1]; P = QF.ply_lesen(os.path.join(ws, "fused.ply")); sel = np.arange(0, len(P), max(1, len(P) // 300000)); X = np.stack([P["x"][sel], P["y"][sel], P["z"][sel]], 1); kam = QF.kameras_aus_workspace(ws)
    else: X, kam = synthetisch()
    t0 = time.time(); nq, nv = QF.zaehlen(X, kam, 8); tc = time.time() - t0; t0 = time.time(); g = QF.zaehlen_gpu(X, kam); tg = time.time() - t0
    assert g is not None, "GPU-Weg lieferte nichts (Rueckfall) - Torch-Umgebung/CUDA pruefen"
    gq, gv = g; gl = float(((nq == gq) & (nv == gv)).mean()); we = float((QF.entscheiden(nq, nv) == QF.entscheiden(gq, gv)).mean())
    print(f"{len(X)} Punkte, {len(kam)} Kameras: CPU {tc:.1f} s, GPU {tg:.1f} s (inkl. Start); nq+nv gleich {100 * gl:.3f} %, Entscheidung gleich {100 * we:.4f} %")
    assert gl >= 0.999 and we >= 0.9999, "GPU und CPU zaehlen verschieden"; print("OK Quellfilter GPU = CPU"); return 0


if __name__ == "__main__":
    sys.exit(main())
