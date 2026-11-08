#!/usr/bin/env python3
"""netz_winding.py - Netz mit Luecken/Selbstdurchdringung -> wasserdicht per Generalized Winding Number + Marching Cubes.
Test BS40 (7.11.): behaelt die Form des besten Diff-Netzes (mvs_default), keine Lochfuellung. libigl (MPL-2, vorlaeufig) in venv-tw.
  venv-tw/bin/python tools/netz_winding.py in.stl out.stl --zelle-cm 5 --iso 0.5 [--einheit-cm 8.7]"""
import sys, argparse, numpy as np, trimesh, igl
from skimage.measure import marching_cubes
ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("aus"); ap.add_argument("--zelle-cm", type=float, default=5)
ap.add_argument("--iso", type=float, default=0.5); ap.add_argument("--einheit-cm", type=float, default=8.7, help="1 STL-Einheit in cm (87/1000 m)")
a = ap.parse_args(); m = trimesh.load(a.ein); V = np.asarray(m.vertices, np.float64); F = np.asarray(m.faces, np.int64)
h = a.zelle_cm / a.einheit_cm; lo = V.min(0) - 3 * h; hi = V.max(0) + 3 * h; n = np.ceil((hi - lo) / h).astype(int)
print("bbox", lo, hi, "Gitter", n, "Zellen", int(np.prod(n)), flush=True)
gx = lo[0] + h * np.arange(n[0]); gy = lo[1] + h * np.arange(n[1]); gz = lo[2] + h * np.arange(n[2])
P = np.stack(np.meshgrid(gx, gy, gz, indexing="ij"), -1).reshape(-1, 3)
W = np.empty(len(P))
for i in range(0, len(P), 6_000_000):
    W[i:i + 6_000_000] = igl.fast_winding_number(V, F, P[i:i + 6_000_000])
W = W.reshape(n)
if abs(W.min()) > abs(W.max()): W = -W; print("Orientierung invertiert -> W negiert")
print("W min/max", W.min(), W.max(), "innen-Anteil", float((W > a.iso).mean()), flush=True)
vv, ff, _, _ = marching_cubes(W, level=a.iso, spacing=(h, h, h)); vv += lo
o = trimesh.Trimesh(vv, ff, process=True); trimesh.repair.fix_normals(o); o.export(a.aus)
print("faces", len(o.faces), "wasserdicht", o.is_watertight, "Komponenten", len(o.split(only_watertight=False)), "Volumen", o.volume)
