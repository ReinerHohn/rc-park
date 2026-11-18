#!/usr/bin/env python3
"""importe_pruefen.py - findet Importe lokaler Module (tools/*.py), deren Namen es nicht mehr gibt (18.11.2026).
Anlass: der Umbau 497af805 hatte 14 Bausteine aus tools/bauteile.py entfernt (box, fbox, Bau, ...), die Generatoren importierten sie weiter und brachen erst
beim Lauf. Geprueft: 'from modul import name' und 'modul.name' in tools/, modelle/ und modelle/*/. rc 3 bei Funden. Aufruf: python3 tools/importe_pruefen.py"""
import ast, os, glob, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); mods = {os.path.basename(p)[:-3]: p for p in glob.glob(os.path.join(R, "tools", "*.py"))}

def defs(p):
    s = set()
    for n in ast.walk(ast.parse(open(p).read())):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)): s.add(n.name)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store): s.add(n.id)
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: s.add((a.asname or a.name).split(".")[0])
    return s

def main():
    import warnings; warnings.simplefilter("ignore"); D = {m: defs(p) for m, p in mods.items()}; bad = set()
    for p in glob.glob(os.path.join(R, "tools", "*.py")) + glob.glob(os.path.join(R, "modelle", "*.py")) + glob.glob(os.path.join(R, "modelle", "*", "*.py")):
        try: t = ast.parse(open(p).read())
        except Exception: continue
        alias = {}
        for n in ast.walk(t):
            if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module in mods:
                bad |= {(p, n.module, a.name) for a in n.names if a.name != "*" and a.name not in D[n.module]}
            if isinstance(n, ast.Import): alias.update({a.asname or a.name: a.name for a in n.names if a.name in mods})
        for n in ast.walk(t):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in alias and n.attr not in D[alias[n.value.id]]:
                src = open(p).read()
                if f'hasattr({n.value.id}, "{n.attr}")' not in src: bad.add((p, alias[n.value.id], n.attr))
    for p, m, a in sorted(bad): print(f"FEHLT: {os.path.relpath(p, R)} importiert {m}.{a} - gibt es nicht mehr")
    print(f"{len(bad)} fehlende Importe"); return 3 if bad else 0

if __name__ == "__main__": sys.exit(main())
