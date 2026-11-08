#!/usr/bin/env python3
"""template_match_3d.py - GLOBALES 3D-Template-Matching auf der GPU (Nutzer 8.11.: Formen ueber die ganze Wolke suchen).
Wolke -> binaeres Voxelgitter (aufgeblaeht um --dil Voxel), Vorlage (STL, mm 1:87 -> m) -> Voxel, Kreuzkorrelation per torch.fft (cuda) ueber ALLE Verschiebungen
(optional --winkel Drehungen um z). Score = Anteil der Vorlagenvoxel, die auf Wolkenvoxeln liegen. Ausgabe: beste Spitzen als Verschiebung (dx,dy,dz) in m und (dn,du) fuer die Fassadenachse.
  python tools/template_match_3d.py teil1.stl [teil2.stl ...] [--res 0.1] [--dil 1] [--winkel 0] [--top 5]"""
import sys, argparse, numpy as np, trimesh, torch
ap = argparse.ArgumentParser(); ap.add_argument("stl", nargs="+"); ap.add_argument("--wolke", default="/media/oem/scan/rc-park_null/wolke_netzrahmen.npy")
ap.add_argument("--res", type=float, default=0.1); ap.add_argument("--dil", type=int, default=1); ap.add_argument("--winkel", type=float, nargs="*", default=[0.0]); ap.add_argument("--top", type=int, default=5)
ap.add_argument("--modell", default="modelle/stl/kaufhaus_p20_1-87.stl", help="Wolke auf Kasten dieses Modells (+rand) beschneiden"); ap.add_argument("--rand", type=float, default=4.0); ap.add_argument("--zmin", type=float, default=-1e9); ap.add_argument("--min_abst", type=float, default=0.0, help="Spitzen mindestens so weit auseinander (m)"); a = ap.parse_args()
dev = "cuda"; R = a.res; SC = 87.0
P = np.load(a.wolke)[:, :3].astype(np.float32); P = P[P[:, 2] >= a.zmin]
if a.modell: b = trimesh.load(a.modell, process=False).bounds * (SC / 1000.0); P = P[np.all((P >= b[0] - a.rand) & (P <= b[1] + a.rand), 1)]
T = [trimesh.load(f, process=False) for f in a.stl]; T0 = [t.copy() for t in T]
pts = np.concatenate([trimesh.sample.sample_surface(t, 60000)[0] for t in T]).astype(np.float32) * (SC / 1000.0)      # mm -> m
lo = P.min(0) - 2; hi = P.max(0) + 2; N = np.ceil((hi - lo) / R).astype(int); print("Gitter", N, "Wolkenpunkte", len(P), "Vorlagenpunkte", len(pts), flush=True)
g = torch.zeros(tuple(N), device=dev); ix = torch.tensor(((P - lo) / R).astype(np.int64), device=dev); g[ix[:, 0], ix[:, 1], ix[:, 2]] = 1
if a.dil: g = torch.nn.functional.max_pool3d(g[None, None], 2 * a.dil + 1, 1, a.dil)[0, 0]
FG = torch.fft.rfftn(g)
n_ = np.array([.3338, .9426]); u_ = np.array([n_[1], -n_[0]]); res = []
for w in a.winkel:
    c, s = np.cos(np.radians(w)), np.sin(np.radians(w)); Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
    ctr = pts.mean(0); Q = (pts - ctr) @ Rz.T + ctr                                                                      # Drehung um Schwerpunkt der Vorlage
    t = torch.zeros(tuple(N), device=dev); qi = torch.tensor(np.floor((Q - Q.min(0)) / R).astype(np.int64), device=dev); t[qi[:, 0], qi[:, 1], qi[:, 2]] = 1
    nv = float(t.sum()); corr = torch.fft.irfftn(FG * torch.conj(torch.fft.rfftn(t)), s=tuple(N)) / nv                     # corr[k] = Summe g[x+k]*t[x]
    corr[:, :, : 0] = 0
    # Verschiebung k -> Weltverschiebung: Vorlage-Voxel x liegt bei Q.min + x*R; Wolkenvoxel bei lo + (x+k)*R  => Welt-Shift = (lo - Q.min) + k*R  (relativ zur Ausgangslage der Vorlage ohne Drehung)
    v, i = torch.topk(corr.flatten(), 4000); ii = np.array(np.unravel_index(i.cpu().numpy(), tuple(N))).T; v = v.cpu().numpy()
    for sc, k in zip(v, ii):
        sh = (lo - Q.min(0)) + k * R + (Q.min(0) - pts.min(0)); res.append((float(sc), float(w), sh))
res.sort(key=lambda r: -r[0]); got = []
for sc, w, sh in res:
    if all(np.linalg.norm(sh - o[2]) > max(a.min_abst, 3 * R) for o in got): got.append((sc, w, sh))
    if len(got) >= a.top: break
for sc, w, sh in got: print(f"Score {sc:.3f}  Winkel {w:5.1f}  Shift x {sh[0]:+.2f} y {sh[1]:+.2f} z {sh[2]:+.2f}   dn {sh[:2]@n_:+.2f} du {sh[:2]@u_:+.2f} dz {sh[2]:+.2f}")
