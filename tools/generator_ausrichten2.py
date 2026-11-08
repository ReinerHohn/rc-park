#!/usr/bin/env python3
"""generator_ausrichten2.py - BS51b: alten Generator (Meter) in den Wolkenrahmen legen per Gittersuche (Gieren um Fassadenrichtung +-, Verschiebung u/w/z), Score = Anteil
Generatorpunkte < 0.15 m von der Wolke (getrimmt), danach ICP-Feinschritt. FPFH/RANSAC scheiterte (Fitness 0.15, Median 0.8 m: Nachbarhaeuser/Boden in der Wolke).
  venv-o3d/bin/python -I tools/generator_ausrichten2.py glb wolke.npy aus.json --aus-stl x.stl"""
import json, argparse, numpy as np, trimesh, itertools
from scipy.spatial import cKDTree
ap = argparse.ArgumentParser(); ap.add_argument("glb"); ap.add_argument("wolke"); ap.add_argument("aus"); ap.add_argument("--aus-stl"); ap.add_argument("--nur", default="fassade,boegen,piers,fenster,erker,rahmen,balkon,galerie,waende,giebel,gauben,gauben_rahmen")
a = ap.parse_args(); sc = trimesh.load(a.glb); parts = [sc.geometry[n] for n in a.nur.split(",") if n in sc.geometry]; G = trimesh.util.concatenate(parts)
P = trimesh.sample.sample_surface(G, 40000)[0]; X = np.load(a.wolke).astype(np.float64)
b = np.array([-14.6, 2.7, 0.6, 15.7, 17.0, 19.9]); X = X[np.all((X >= b[:3] - 0.5) & (X <= b[3:] + 0.5), 1)]; X = X[np.random.default_rng(0).choice(len(X), min(len(X), 400000), replace=False)]
tree = cKDTree(X); n = np.array([0.344, 0.939, 0.0]); az = np.arctan2(n[1], n[0])
def Rz(t): c, s = np.cos(t), np.sin(t); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
c0 = X[(X[:, 2] > 2)].mean(0); pc = P.mean(0); best = (-1, None)
def score(R, t, th=0.15, N=12000): Q = (P[::max(1, len(P) // N)] @ R.T) + t; d = tree.query(Q, workers=-1)[0]; return float((d < th).mean())
for flip in (0.0, np.pi):
    R0 = Rz(az + np.pi / 2 + flip)         # Generator-y-Achse -> Fassadennormale (+-)
    for dyaw in np.deg2rad(np.arange(-6, 6.1, 2)):
        R = Rz(dyaw) @ R0; base = c0 - R @ pc
        for du, dw, dz in itertools.product(np.arange(-6, 6.1, 1.0), np.arange(-4, 4.1, 1.0), np.arange(-1, 1.1, 1.0)):
            t = base + np.array([-n[1], n[0], 0]) * du + n * dw + np.array([0, 0, dz]); s = score(R, t)
            if s > best[0]: best = (s, (R, t, flip, dyaw))
    print("flip", flip, "bester Score", round(best[0], 3), flush=True)
s, (R, t, flip, dyaw) = best; print("Grob:", round(s, 3), "flip", flip, "dyaw(deg)", round(np.rad2deg(dyaw), 1), flush=True)
for step, rng in ((0.5, 1.0), (0.2, 0.5), (0.1, 0.25)):
    cand = []
    for dx, dy, dz in itertools.product(np.arange(-rng, rng + 1e-9, step), repeat=3):
        for dyaw2 in np.deg2rad(np.arange(-1.0, 1.01, 0.5)):
            R2 = Rz(dyaw2) @ R; t2 = t + np.array([dx, dy, dz]); cand.append((score(R2, t2, 0.1), R2, t2))
    s, R, t = max(cand, key=lambda c: c[0]); print("Fein", step, round(s, 3), flush=True)
d = tree.query((P @ R.T) + t, workers=-1)[0]; print("Abstand Generator->Wolke Median %.2f m P75 %.2f P90 %.2f; <0.1m %.0f%% <0.3m %.0f%% <0.6m %.0f%%" % (*np.percentile(d, [50, 75, 90]), 100 * (d < .1).mean(), 100 * (d < .3).mean(), 100 * (d < .6).mean()))
T = np.eye(4); T[:3, :3] = R; T[:3, 3] = t; json.dump(dict(T=T.tolist(), score=s), open(a.aus, "w"), indent=1)
if a.aus_stl:
    full = trimesh.util.concatenate(list(sc.geometry.values())); full.apply_transform(T); full.vertices = full.vertices / 0.087; full.export(a.aus_stl); print("STL", a.aus_stl, len(full.faces))
