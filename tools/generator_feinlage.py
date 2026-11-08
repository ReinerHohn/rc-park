"""Feinlage des Generators direkt gegen den Foto-Diff (statt gegen die Wolke): globale Kandidaten +-Schritt je Freiheitsgrad.
Aufruf: generator_feinlage.py BASIS.stl AUS_PREFIX   (mm-STL; Netzrahmen m = mm*0.087; Fassadennormale (0.344,0.939,0))"""
import sys, numpy as np, trimesh
m = trimesh.load(sys.argv[1], force="mesh"); P = sys.argv[2]; mm = 1 / 0.087
n = np.array([0.344, 0.939, 0.0]); c = m.bounds.mean(0); c[2] = m.bounds[0, 2]
def rz(w):
    a = np.radians(w); R = np.eye(4); R[:2, :2] = [[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]
    T1 = np.eye(4); T1[:3, 3] = -c; T2 = np.eye(4); T2[:3, 3] = c; return T2 @ R @ T1
def sk(s):
    S = np.diag([s, s, s, 1.0]); T1 = np.eye(4); T1[:3, 3] = -c; T2 = np.eye(4); T2[:3, 3] = c; return T2 @ S @ T1
def tr(v): T = np.eye(4); T[:3, 3] = v; return T
V = {"nP": tr(n * 0.4 * mm), "nM": tr(-n * 0.4 * mm), "zP": tr([0, 0, 0.3 * mm]), "zM": tr([0, 0, -0.3 * mm]),
     "rP": rz(1.0), "rM": rz(-1.0), "sP": sk(1.02), "sM": sk(0.98)}
for k, T in V.items():
    x = m.copy(); x.apply_transform(T); x.export(f"{P}_{k}.stl")
print(" ".join(V))
