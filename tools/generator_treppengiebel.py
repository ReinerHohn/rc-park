"""Treppengiebel-Variante des alten Generators: die beiden Giebelscheiben (Prisma, q +-4 m, Spitze 17.0 m) werden durch Treppengiebel ersetzt
(8 Stufen je Flanke am Foto 004/075 gezaehlt Z-042/Z-075 'automatisch'; ANNAHME Halbbreite aus Wolke-Dachneigung, Spitze 20.24 m = Foto-Triangulation spitze_hoehe.py in objekt.json).
Aufruf: generator_treppengiebel.py AUS.stl [--ohne-dachmuster] [--spitze 20.24] [--halbbreite 6.8] [--stufen 8]"""
import sys, glob, os, argparse, numpy as np, trimesh
from shapely.geometry import box
from shapely.ops import unary_union
ap = argparse.ArgumentParser(); ap.add_argument("aus"); ap.add_argument("--ohne-dachmuster", action="store_true"); ap.add_argument("--spitze", type=float, default=20.24); ap.add_argument("--halbbreite", type=float, default=6.8); ap.add_argument("--stufen", type=int, default=8); a = ap.parse_args()
T = "/media/oem/scan/rc-park_null/generator_alt/teile"; namen = sorted(os.path.basename(f)[2:-4] for f in glob.glob(T + "/g_*.stl")); M = {n: trimesh.load(f"{T}/g_{n}.stl", force="mesh") for n in namen}
F = M["first"].vertices * 0.087; c = F[:, :2].mean(0); _, _, V = np.linalg.svd(F[:, :2] - c); r = V[0]; pr = np.array([-r[1], r[0]])
g = M["giebel"].split(only_watertight=False); z0 = float(M["giebel"].bounds[0, 2] * 0.087); tw = 0.5; qe = a.halbbreite; sl = (a.spitze - z0) / qe
neu = []
for m in g:
    Q = m.vertices * 0.087; ar = (Q[:, :2] - c) @ r; r0, r1 = float(ar.min()), float(ar.max())
    rects = [box(-tw, z0, tw, a.spitze)]
    for sgn in (-1, 1):
        edges = np.linspace(tw, qe, a.stufen + 1)
        for k in range(a.stufen):
            qa, qb = edges[k], edges[k + 1]; zt = a.spitze - sl * (qa - tw) if True else 0; zt = a.spitze - (a.spitze - z0) * (qa - tw) / (qe - tw)
            rects.append(box(min(sgn * qa, sgn * qb) - 0.005, z0, max(sgn * qa, sgn * qb) + 0.005, zt))
    poly = unary_union(rects); s = trimesh.creation.extrude_polygon(poly, r1 - r0)      # lokal: x = q, y = z, z = Tiefe
    V3 = np.c_[s.vertices[:, 2] + r0, s.vertices[:, 0], s.vertices[:, 1]]               # (Tiefe, q, z)
    W = np.c_[c[0] + V3[:, 0] * r[0] + V3[:, 1] * pr[0], c[1] + V3[:, 0] * r[1] + V3[:, 1] * pr[1], V3[:, 2]] / 0.087
    neu.append(trimesh.Trimesh(W, s.faces, process=False))
skip = {"dachmuster", "dachrauten", "dachziegel"} if a.ohne_dachmuster else set()
trimesh.util.concatenate([M[n] for n in namen if n != "giebel" and n not in skip] + neu).export(a.aus); print("ok", a.aus, [round(float(x.volume), 1) for x in neu])
