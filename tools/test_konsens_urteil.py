#!/usr/bin/env python3
"""Test der Konsens-Annahme (global_mapper_konsens.urteil, 19.11.2026): gutes Modell traegt; duennes Rueckgrat / wenig Bilder / kein Clip -> Gruende + Ursache + Abhilfe."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from global_mapper_konsens import urteil
gut = dict(schnitt=dict(gemeinsam=881, stabil=630), bewertung=dict(n_reg=833))                    # Martinstor 19.11.
g, u, ab = urteil(gut, 1032, 17); assert g == [] and u == [] and ab == "", (g, u, ab)
duenn = dict(schnitt=dict(gemeinsam=60, stabil=20), bewertung=dict(n_reg=55))
g, u, ab = urteil(duenn, 70, 0); assert len(g) == 1 and "Rueckgrat" in g[0], g
assert any("70 Bilder" in x for x in u) and any("kein Videoclip" in x for x in u), u; assert "Video-Rundgang" in ab
g, u, ab = urteil(dict(schnitt=dict(gemeinsam=40, stabil=25), bewertung=dict(n_reg=40)), 300, 5); assert len(g) == 2 and "unter 30" in g[0] and "unter 50 %" in g[1], g; assert "nominell" in u[0], u
g, u, ab = urteil(None, 500, 2, lief=False); assert g and "ohne Ergebnis" in g[0] and "2 Videoclip" in u[0], (g, u)
print("ok konsens_urteil")
