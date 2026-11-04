#!/usr/bin/env python3
"""hardcode_finden.py - GENERISCH: feste Zahlen im Generator finden, die nicht aus Daten kommen (Spezialcode-Audit, automatisch und wiederholbar).

Zaehlt jede Zahl-Konstante im Python-Quelltext (AST), die
  - nicht trivial ist (0, 1, -1, 2, 0.5 und Vielfache von 90 Grad gelten als Struktur, nicht als Mass),
  - nicht in einem String/Kommentar steht (beleg-Texte zaehlen nicht),
  - nicht Standardwert eines Parameters einer Bibliotheksfunktion ist (--bibliothek: dort sind Defaults gewollt, werden separat gelistet).
Gruppiert nach Zeile/Funktion; Zeilen mit 'ANNAHME' im Kommentar werden markiert (benannt, aber trotzdem Code statt Daten).
  python3 tools/hardcode_finden.py modelle/martinstor_v4_gen.py [--min 3] [--json audit/hardcodes.json]
Exit 0 immer (Bericht); mit --max N Exit 1, wenn mehr als N Zahlen gefunden werden (fuer eine spaetere Pruefstand-Schwelle).
"""
import ast, sys, json, argparse, collections

TRIVIAL = {0, 1, -1, 2, -2, 0.5, -0.5, 90, 180, 270, 360, 100, 1000}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("datei"); ap.add_argument("--min", type=int, default=1, help="nur Zeilen mit >= so vielen Zahlen")
    ap.add_argument("--json"); ap.add_argument("--max", type=int); a = ap.parse_args()
    src = open(a.datei).read(); zeilen = src.splitlines(); baum = ast.parse(src)
    funk = {}                                                                     # Zeile -> umgebende Funktion
    for n in ast.walk(baum):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for z in range(n.lineno, (n.end_lineno or n.lineno) + 1): funk[z] = n.name          # innerste Funktion gewinnt (ast.walk: aussen zuerst)
    defaults = set()
    for n in ast.walk(baum):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in n.args.defaults + n.args.kw_defaults:
                if d is not None:
                    for c in ast.walk(d):
                        if isinstance(c, ast.Constant): defaults.add(id(c))
    netz = set()                                                                  # Segmentzahlen (Netzaufloesung, kein Mass): seg=, M.cylinder(...,n), M.sphere(r,n)
    for n in ast.walk(baum):
        if isinstance(n, ast.Call):
            fn = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            for kw in n.keywords:
                if kw.arg in ("seg", "segmente", "circular_segments", "n_seg") and isinstance(kw.value, ast.Constant): netz.add(id(kw.value))
            idx = {"cylinder": 3, "sphere": 1, "circle": 1}.get(fn)
            if idx is not None and len(n.args) > idx and isinstance(n.args[idx], ast.Constant): netz.add(id(n.args[idx]))
    neg = set()
    for n in ast.walk(baum):
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant): neg.add(id(n.operand))
    je_zeile = collections.defaultdict(list); n_def = 0
    for n in ast.walk(baum):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            v = -n.value if id(n) in neg else n.value
            if v in TRIVIAL: continue
            if id(n) in defaults: n_def += 1; continue
            if id(n) in netz: continue
            je_zeile[n.lineno].append(v)
    treffer = []
    for z in sorted(je_zeile):
        if len(je_zeile[z]) < a.min: continue
        t = zeilen[z - 1]; treffer.append(dict(zeile=z, funktion=funk.get(z, "<modul>"), anzahl=len(je_zeile[z]), werte=je_zeile[z][:12],
                                             annahme="ANNAHME" in t, daten="_M[" in t or "_PROF" in t, code=t.strip()[:140]))
    gesamt = sum(t["anzahl"] for t in treffer)
    nach_f = collections.Counter()
    for t in treffer: nach_f[t["funktion"]] += t["anzahl"]
    print(f"{a.datei}: {gesamt} feste Zahlen in {len(treffer)} Zeilen (+ {n_def} Parameter-Standardwerte nicht gezaehlt)")
    print("Nach Funktion:", ", ".join(f"{f} {n}" for f, n in nach_f.most_common()))
    print("Zeilen (meiste zuerst):")
    for t in sorted(treffer, key=lambda t: -t["anzahl"])[:40]:
        print(f"  {t['zeile']:4d} [{t['funktion']}] {t['anzahl']:2d} Zahlen{' ANNAHME' if t['annahme'] else ''}{' (mischt Daten)' if t['daten'] else ''}: {t['werte']}  | {t['code'][:90]}")
    if a.json: json.dump(dict(datei=a.datei, gesamt=gesamt, zeilen=treffer, nach_funktion=dict(nach_f)), open(a.json, "w"), indent=1, ensure_ascii=False)
    if a.max is not None and gesamt > a.max: sys.exit(1)


if __name__ == "__main__":
    main()
