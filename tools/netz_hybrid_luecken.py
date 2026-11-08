#!/usr/bin/env python3
"""netz_hybrid_luecken.py - BS46: Hybrid Wolkennetz + Generator-/LoD2-Flaechen NUR in Wolkenluecken.
Basis (Wolkennetz) bleibt unveraendert; Flaechen des Zusatznetzes (Generator) werden uebernommen, wenn ihr Schwerpunkt
 (a) weiter als --luecke m von jedem Wolkenpunkt liegt UND (b) weiter als --netz m vom Basisnetz. Einheiten: STL mm * 0.087 = Netzrahmen-m.
  venv-seg/bin/python -I tools/netz_hybrid_luecken.py basis.stl zusatz.stl wolke.npy out.stl [--luecke 1.0 --netz 1.0]"""
import sys, argparse, numpy as np, trimesh
from scipy.spatial import cKDTree
ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("basis", "zusatz", "wolke", "aus")]
ap.add_argument("--luecke", type=float, default=1.0); ap.add_argument("--netz", type=float, default=1.0); ap.add_argument("--rand", type=float, default=0.5, help="Rand (m) um die Basis-bbox, nur dort darf das Zusatznetz liefern"); ap.add_argument("--hoehe-min", type=float, default=-1e9)
a = ap.parse_args(); s = 0.087
B = trimesh.load(a.basis); Z = trimesh.load(a.zusatz)
v, f = trimesh.remesh.subdivide_to_size(Z.vertices, Z.faces, max_edge=0.5 / s); Z = trimesh.Trimesh(v, f, process=False); X = np.load(a.wolke).astype(np.float64)
c = Z.triangles_center * s
dW = cKDTree(X).query(c, workers=-1)[0]
Bp = trimesh.sample.sample_surface(B, 400000)[0] * s; dB = cKDTree(Bp).query(c, workers=-1)[0]
lo = (B.bounds[0] - a.rand / s) * s; hi = (B.bounds[1] + a.rand / s) * s; im = np.all((c >= lo) & (c <= hi), 1)
keep = im & (dW > a.luecke) & (dB > a.netz) & (c[:, 2] > a.hoehe_min)
print(f"Zusatzflaechen {len(Z.faces)} -> uebernommen {int(keep.sum())} ({100*keep.mean():.1f} %); Wolkenabstand Median {np.median(dW):.2f} m, Netzabstand Median {np.median(dB):.2f} m")
Zk = Z.submesh([np.where(keep)[0]], append=True) if keep.any() else None
out = trimesh.util.concatenate([B, Zk]) if Zk is not None else B
out.export(a.aus); print("faces", len(out.faces))
