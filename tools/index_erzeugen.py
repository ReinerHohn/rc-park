#!/usr/bin/env python3
"""index_erzeugen.py - schreibt tools/INDEX.md: je Werkzeug eine Zeile (Name, Umgebung, erste Docstring-Zeile). Fuer KI-Suche statt 970 Dateien lesen.
Aufruf: python3 tools/index_erzeugen.py   (nach neuen Werkzeugen erneut laufen lassen)"""
import ast, os, re, warnings
warnings.simplefilter("ignore", SyntaxWarning)
T = os.path.dirname(os.path.abspath(__file__)); zeilen = []
def umgebung(src):
    if re.search(r"^\s*(import|from)\s+pycolmap", src, re.M): return "col"
    if re.search(r"^\s*(import|from)\s+(torch|cv2|kornia|lightglue)", src, re.M): return "seg"
    if re.search(r"^\s*(import|from)\s+(trimesh|manifold3d|shapely)", src, re.M): return "gen"
    return "-"
for f in sorted(os.listdir(T)):
    p = os.path.join(T, f)
    if f.endswith(".py"):
        src = open(p, errors="replace").read()
        try: d = ast.get_docstring(ast.parse(src)) or ""
        except SyntaxError: d = ""
        kurz = " ".join(d.split("\n\n")[0].split())[:200] or "(kein Docstring)"
        gruppe = "test" if f.startswith("test_") else "werkzeug"
        zeilen.append((gruppe, f"- `{f}` [{umgebung(src)}] {kurz}"))
    elif f.endswith(".sh"):
        k = [l[1:].strip() for l in open(p, errors="replace").read().splitlines()[1:6] if l.startswith("#")]
        zeilen.append(("shell", f"- `{f}` {' '.join(k)[:200] or '(kein Kopfkommentar)'}"))
kopf = ("# Werkzeug-Index (erzeugt von tools/index_erzeugen.py - nicht von Hand pflegen)\n"
        "Umgebung: col = /media/oem/scan/venv-colmap (pycolmap), seg = /media/oem/scan/venv-seg (torch/CUDA), gen = ~/.venvs/rcpark (trimesh), - = beliebig. Suche: `grep -i <stichwort> tools/INDEX.md`.\n")
out = [kopf]
for g, t in (("shell", "## Shell"), ("werkzeug", "## Python-Werkzeuge"), ("test", "## Tests")):
    out += ["", t] + [z for gg, z in zeilen if gg == g]
open(os.path.join(T, "INDEX.md"), "w").write("\n".join(out) + "\n")
print(f"INDEX: {len(zeilen)} Eintraege, ohne Docstring {sum('(kein' in z for _, z in zeilen)}")
