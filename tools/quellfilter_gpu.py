#!/usr/bin/env python3
"""quellfilter_gpu.py <eingabe.npz> <aus.npz> - GPU-Zaehlung fuer tools/quellfilter.py (Nutzerregel: GPU immer nutzen; Messung 26.11.2026: CPU 286 s fuer 21,5 Mio Punkte x 645 Kameras).
Gleiche Rechnung wie quellfilter.zaehlen_bild (Projektion, Quelle |d-z| < TOL_Q z, Freiraum d > 0 und Fenster-Minimum > (1+TOL_V) z), nur in torch. Laeuft in der Torch-Umgebung
(venv-seg), weil pycolmap und torch in keiner Umgebung zusammen liegen; quellfilter.py exportiert Kameras + Punkte und startet dieses Werkzeug als Unterprozess.
Eingabe: X (n,3 float32), K (m,4), R (m,3,3), t (m,3), b, h (m,), dateien (m, Pfad der Tiefenkarte oder ''), tol_q, tol_v, rand. Ausgabe: nq, nv (int32).
Verwandt: tools/quellfilter.py (Aufrufer, CPU-Rueckfall + Gleichheitstest), tools/dichte_diagnose.py. Vorlaeufer: quellfilter.zaehlen (CPU, 4 Threads)."""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BLOCK = 4_000_000


def main():
    import torch, torch.nn.functional as F
    import quellfilter as QF
    Z = np.load(sys.argv[1], allow_pickle=True); dev = "cuda"
    X = torch.as_tensor(Z["X"], device=dev); n = len(X); nq = torch.zeros(n, dtype=torch.int32, device=dev); nv = torch.zeros(n, dtype=torch.int32, device=dev)
    tol_q, tol_v, rand = float(Z["tol_q"]), float(Z["tol_v"]), int(Z["rand"])
    for j in range(len(Z["dateien"])):
        f = str(Z["dateien"][j])
        if not f: continue
        d = torch.as_tensor(QF.tiefe_lesen(f).copy(), device=dev); H, W = d.shape; bb, hh = float(Z["b"][j]), float(Z["h"][j])
        t_inf = torch.where(d > 0, d, torch.full_like(d, float("inf")))
        if rand > 0: tmin = -F.max_pool2d((-t_inf)[None, None], 2 * rand + 1, 1, rand)[0, 0]
        else: tmin = t_inf
        tmin = torch.where(torch.isfinite(tmin), tmin, torch.zeros_like(tmin)) if rand > 0 else d
        sx, sy = W / bb, H / hh; K = Z["K"][j]; Rm = torch.as_tensor(Z["R"][j], device=dev, dtype=torch.float32); tv = torch.as_tensor(Z["t"][j], device=dev, dtype=torch.float32)
        for a in range(0, n, BLOCK):
            Q = X[a:a + BLOCK] @ Rm.T + tv; z = Q[:, 2]; zs = torch.where(z > 0.1, z, torch.ones_like(z))
            u = float(K[0]) * Q[:, 0] / zs + float(K[2]); v = float(K[1]) * Q[:, 1] / zs + float(K[3])
            ok = (z > 0.1) & (u >= 0) & (u < bb - 1) & (v >= 0) & (v < hh - 1)
            ui = torch.clamp(torch.round(u * sx).long(), 0, W - 1); vi = torch.clamp(torch.round(v * sy).long(), 0, H - 1)
            dd = d[vi, ui]; dm = tmin[vi, ui]
            nq[a:a + BLOCK] += (ok & (torch.abs(dd - z) < tol_q * z)).int(); nv[a:a + BLOCK] += (ok & (dd > 0) & (dm > (1 + tol_v) * z)).int()
    np.savez(sys.argv[2], nq=nq.cpu().numpy(), nv=nv.cpu().numpy()); print("GPU-Zaehlung fertig", n, "Punkte", len(Z["dateien"]), "Karten", flush=True)


if __name__ == "__main__":
    main()
