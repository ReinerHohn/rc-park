"""Huellen-npz (objekte_huellen.py / objekte_schnitzen.py) -> STL: Gesamt und je Objekt. Aufruf: python -I tools/huellen_stl.py IN.npz AUSVERZ"""
import sys, os, numpy as np, trimesh
z = np.load(sys.argv[1]); out = sys.argv[2]; os.makedirs(out, exist_ok=True); V = z["V"].astype(np.float64); F = z["F"]; off = np.r_[0, np.cumsum(z["ntri"])]; M = []
for k, i in enumerate(z["ids"]):
    f = F[off[k]:off[k + 1]]; u, inv = np.unique(f, return_inverse=True); m = trimesh.Trimesh(V[u], inv.reshape(-1, 3), process=False); m.export(os.path.join(out, "objekt_%04d.stl" % i)); M.append(m)
trimesh.util.concatenate(M).export(os.path.join(out, "gesamt.stl")); print(len(M), "Objekte ->", out)
