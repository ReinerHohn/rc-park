"""LIMAP-Linien als Zusatzkanten am Wolkennetz: duenne Stege (4-Eck-Prismen) entlang netzferner Linien, Rahmen Wolke->STL mm = m/0.087.
Aufruf: limap_kantenzwang.py NETZ.stl LINIEN.npy AUS.stl [dicke_m=0.04]"""
import sys, numpy as np, trimesh
net = trimesh.load(sys.argv[1], force="mesh"); L = np.load(sys.argv[2]) / 0.087; d = (float(sys.argv[4]) if len(sys.argv) > 4 else 0.04) / 0.087
teile = [net]
for a, b in L:
    v = b - a; l = np.linalg.norm(v)
    if l < 1e-6: continue
    c = trimesh.creation.cylinder(radius=d / 2, height=l, sections=4)
    c.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], v / l)); c.apply_translation((a + b) / 2); teile.append(c)
trimesh.util.concatenate(teile).export(sys.argv[3]); print(len(teile) - 1, "Stege")
