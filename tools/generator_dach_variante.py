"""Dach-Massing-Variante: z-Skalierung der Dachteile um die Traufhoehe (Beleg: Wolke-RANSAC Dachneigung 55 statt 59 Grad, BS57).
Aufruf: generator_dach_variante.py AUS_PREFIX s1,s2,..  (Teile-Verzeichnis generator_alt/teile, mm)"""
import sys, glob, os, numpy as np, trimesh
R = "/media/oem/scan/rc-park_null"; T = R + "/generator_alt/teile"; Z0 = 121.0
DACH = {"dach", "dachziegel", "dachmuster", "dachrauten", "first", "giebel", "giebelglas", "giebelrahmen", "gauben", "gauben_dach", "gauben_rahmen"}
namen = sorted(os.path.basename(f)[2:-4] for f in glob.glob(T + "/g_*.stl"))
for s in map(float, sys.argv[2].split(",")):
    ms = []
    for n in namen:
        m = trimesh.load(f"{T}/g_{n}.stl", force="mesh")
        if n in DACH:
            v = m.vertices.copy(); v[:, 2] = Z0 + (v[:, 2] - Z0) * s; m = trimesh.Trimesh(v, m.faces, process=False)
        ms.append(m)
    trimesh.util.concatenate(ms).export(f"{sys.argv[1]}_s{s:.2f}.stl"); print("ok", s)
