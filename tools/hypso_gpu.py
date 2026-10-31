#!/usr/bin/env python3
"""hypso_gpu.py - Hypsometrie-Vergleich Modell gegen LiDAR-DOM, GPU (PyTorch/CUDA) mit identischem CPU-Weg.

Zielfunktion der Massoptimierung: fuer viele Drehungen/Raster-Phasen gleichzeitig die Hoehenkarte des Modells
(Max-Hoehe je 1-m-Zelle) bilden und je Hoehenstufe t die Flaeche > t im Umkreis r um die Spitze mit dem DOM vergleichen.
GPU: ein einziger Scatter-Max ueber alle Kombinationen (Chunks). CPU: gleiche Rechnung mit numpy (Referenz, Fallback).
Selbsttest (GPU == CPU, bit-gleich):  /media/oem/scan/venv-seg/bin/python -I tools/hypso_gpu.py --selbsttest
"""
import sys, time, numpy as np, trimesh
DOM = "/media/oem/scan/tmp/mt_dom/mt_win.npy"; GELAENDE = 277.98; N = 60
REF = np.load(DOM) - GELAENDE
YY, XX = np.mgrid[:N, :N]
PR = np.unravel_index(np.argmax(REF), REF.shape)

def punkte(stl, max_edge=0.45):
    """Flaechenschwerpunkte des fein unterteilten Modells in Metern (Modell-STL ist 1:87 in mm)."""
    m = trimesh.load(stl); m.apply_scale(87 / 1000.0)
    if not m.is_watertight: raise ValueError("Modell nicht wasserdicht")
    v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=max_edge, max_iter=14)
    return np.ascontiguousarray(v[f].mean(1))

def ref_areas(TS, r):
    return np.array([max(int(((REF > t) & (np.hypot(YY - PR[0], XX - PR[1]) <= r)).sum()), 1) for t in TS], float)

def combos(angs, phs):
    return np.array([(a, dx, dy) for a in angs for dx in phs for dy in phs], float)

# ------------------------------------------------------------------ CPU (Referenz)
def hmaps_cpu(P, C):
    out = np.zeros((len(C), N, N))
    for k, (a, dx, dy) in enumerate(C):
        c, s = np.cos(np.radians(a)), np.sin(np.radians(a))
        x = c * P[:, 0] - s * P[:, 1] + dx; y = s * P[:, 0] + c * P[:, 1] + dy
        ix = np.floor(x + N / 2).astype(int); iy = np.floor(N / 2 - y).astype(int)
        ok = (ix >= 0) & (ix < N) & (iy >= 0) & (iy < N)
        np.maximum.at(out[k], (iy[ok], ix[ok]), P[ok, 2])
    return out

# ------------------------------------------------------------------ GPU
def hmaps_gpu(P, C, chunk=48, device="cuda"):
    import torch
    Pt = torch.as_tensor(P, dtype=torch.float64, device=device)
    out = torch.zeros((len(C), N, N), dtype=torch.float64, device=device)
    for i in range(0, len(C), chunk):
        c = torch.as_tensor(C[i:i + chunk], dtype=torch.float64, device=device)
        a = torch.deg2rad(c[:, 0])[:, None]; dx = c[:, 1][:, None]; dy = c[:, 2][:, None]
        x = torch.cos(a) * Pt[None, :, 0] - torch.sin(a) * Pt[None, :, 1] + dx
        y = torch.sin(a) * Pt[None, :, 0] + torch.cos(a) * Pt[None, :, 1] + dy
        ix = torch.floor(x + N / 2).long(); iy = torch.floor(N / 2 - y).long()
        ok = (ix >= 0) & (ix < N) & (iy >= 0) & (iy < N)
        b = torch.arange(len(c), device=device)[:, None].expand_as(ix)
        flat = (b * N * N + iy.clamp(0, N - 1) * N + ix.clamp(0, N - 1))[ok]
        z = Pt[None, :, 2].expand_as(x)[ok]
        h = torch.zeros(len(c) * N * N, dtype=torch.float64, device=device)
        h.scatter_reduce_(0, flat, z, reduce="amax", include_self=True)
        out[i:i + len(c)] = h.view(len(c), N, N)
    return out.cpu().numpy()

def fehler(H, TS, r, R):
    """H: (B,N,N) -> d (B, len(TS)) = Flaeche_Modell / Flaeche_Laser - 1 (Spitze = hoechste Zelle, erste bei Gleichstand)."""
    B = len(H); flat = H.reshape(B, -1).argmax(1); py, px = flat // N, flat % N
    D = np.hypot(YY[None] - py[:, None, None], XX[None] - px[:, None, None]) <= r
    A = np.stack([((H > t) & D).sum((1, 2)) for t in TS], 1)
    return A / R[None] - 1

def auswerten(P, TS, r, C, gpu=True):
    R = ref_areas(TS, r)
    H = hmaps_gpu(P, C) if gpu else hmaps_cpu(P, C)
    d = fehler(H, TS, r, R); e = np.abs(d).mean(1); k = int(np.argmin(e))
    return dict(e=float(e[k]), med=float(np.median(np.abs(d[k]))), kombi=C[k].tolist(), d=d[k], alle=e, top=float(P[:, 2].max()))

TS0 = (20, 24, 28, 32, 35, 38, 40, 42, 44, 46, 48, 50, 52)       # Optimierungsstufen
TS1 = (22, 26, 30, 33, 36, 39, 41, 43, 45, 47, 49, 51)           # zurueckgehaltene Stufen (Validierung)
ANG = np.arange(86, 112, 1.0); PH = np.arange(-1, 1.01, .25)     # feines Raster: 26*9*9 = 2106 Kombinationen

def selbsttest(stl="modelle/stl/martinstor_v4_1-87.stl"):
    import torch
    P = punkte(stl); C = combos(np.arange(88, 110, 2.0), (-1, -.5, 0, .5, 1))
    t0 = time.time(); Hc = hmaps_cpu(P, C); tc = time.time() - t0
    t0 = time.time(); Hg = hmaps_gpu(P, C); torch.cuda.synchronize(); tg = time.time() - t0
    gleich = bool((Hc == Hg).all()); print(f"Hoehenkarten CPU==GPU (bit-gleich): {gleich}   max Abw {np.abs(Hc-Hg).max():.3e}")
    for TS, r in ((TS0, 9), (TS1, 9), (TS0, 13)):
        a = auswerten(P, TS, r, C, gpu=False); b = auswerten(P, TS, r, C, gpu=True)
        print(f"  r={r} {len(TS)} Stufen: e CPU {a['e']:.6f}  GPU {b['e']:.6f}  gleich={a['e']==b['e'] and a['kombi']==b['kombi']}")
    Cf = combos(ANG, PH); t0 = time.time(); auswerten(P, TS0, 9, Cf, gpu=True); tg2 = time.time() - t0
    print(f"Zeit {len(C)} Kombinationen: CPU {tc:.1f} s, GPU {tg:.2f} s  | feines Raster ({len(Cf)} Kombinationen) GPU gesamt {tg2:.1f} s")
    return gleich

if __name__ == "__main__":
    if "--selbsttest" in sys.argv: sys.exit(0 if selbsttest() else 1)
