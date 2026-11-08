"""Wand-/Giebel-/Laubentiefe-Varianten des alten Generators (Teile mm, Netzrahmen m = mm*0.087; Fassadennormale (0.344,0.939,0)).
Je Gruppe +-Schritt: Laube (Arkaden) und Wand/Fassade entlang der Normalen +-0,3 m; Giebel in Richtung der Fassade (u) +-3 % um die Mitte."""
import sys, glob, os, numpy as np, trimesh
R = "/media/oem/scan/rc-park_null"; T = R + "/generator_alt/teile"; O = sys.argv[1]; mm = 1 / 0.087
n = np.array([0.344, 0.939, 0.0]); u = np.array([-n[1], n[0], 0.0])
G = {"laube": {"boegen", "piers", "pierbase", "laube", "arkadenglas", "arkadenkreuz"}, "wand": {"fassade", "waende", "balken", "cornice", "konsolen", "dachkante_gold"}, "giebel": {"giebel", "giebelglas", "giebelrahmen"}}
namen = sorted(os.path.basename(f)[2:-4] for f in glob.glob(T + "/g_*.stl")); M = {k: trimesh.load(f"{T}/g_{k}.stl", force="mesh") for k in namen}
c = np.mean([m.bounds.mean(0) for m in M.values()], axis=0)
def bau(gr, f, name):
    ms = []
    for k in namen:
        m = M[k].copy()
        if k in G[gr]: m.vertices = f(m.vertices)
        ms.append(m)
    trimesh.util.concatenate(ms).export(f"{O}_{name}.stl")
for s, t in (("P", 0.3), ("M", -0.3)):
    bau("laube", lambda v, t=t: v + n * t * mm, "laube" + s); bau("wand", lambda v, t=t: v + n * t * mm, "wand" + s)
for s, f in (("P", 1.03), ("M", 0.97)):
    def sk(v, f=f): w = v.copy(); w += np.outer((v - c) @ u * (f - 1), u); return w
    bau("giebel", sk, "giebel" + s)
print("ok")
