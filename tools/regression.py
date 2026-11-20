#!/usr/bin/env python3
"""regression.py - BEWEIS, dass eine Werkzeug-/Generatoraenderung nichts veraendert: die Auswertungskette eines Objekts laufen lassen und
alle Ergebnisdateien gegen einen Schnappschuss vergleichen (Zahlen mit Toleranz, Texte exakt).

Konfiguration als DATEN in modelle/<objekt>/objekt.json["regression"]:
  {"kette": ["<Kommando mit {PY} {RC} {OBJ} {OD}>", ...],            # deterministische Kette ab der vorhandenen Wolke (kein SfM, kein GPU)
   "dateien": {"name": {"pfad": "relativ zu OD", "art": "json|stl|masstabelle|pruefbericht", "toleranz": 0.01, "ignorieren": ["historie", ...]}}}
  {PY} = Analyse-Python (venv-seg), {RC} = Generator-Python (rcpark), {OBJ} = objekt.json, {OD} = Objektordner.

  regression.py modelle/<objekt>/objekt.json --schnappschuss     # Kette laufen lassen, Ergebnisse nach <OD>/regression/basis/ kopieren
  regression.py modelle/<objekt>/objekt.json --pruefen           # Kette laufen lassen, gegen basis vergleichen; Exit 1 bei Abweichung
  regression.py modelle/<objekt>/objekt.json --pruefen --ohne-kette   # nur vergleichen (Kette lief schon)
Vergleichsregeln: json = rekursiv, Zahlen |a-b| <= toleranz (relativ 1e-6 zusaetzlich), Listen gleicher Laenge elementweise, ignorierte
Schluessel ausgelassen; stl = Dreieckszahl exakt, Volumen/Bounding-Box relativ 1e-6; masstabelle = Pruefungen (name, wert, soll) + Messungen;
pruefbericht = werte (toleranz) + je Pruefung ok-Flag. Ausgabe: je Datei OK/ABWEICHUNG mit den ersten Unterschieden.
Umgebung: python3 genuegt fuer die Steuerung (Kettenschritte laufen mit {PY}/{RC}), stl-Vergleich braucht trimesh -> `tools/py tools/regression.py ...`.
Exit: 0 = identisch, 1 = Abweichung oder Kettenschritt fehlgeschlagen, 2 = objekt.json ohne "regression" (nichts geprueft). Pflicht nach jeder tools-Aenderung.
"""
import sys, os, json, shutil, subprocess, argparse, numpy as np

PY = "/media/oem/scan/venv-seg/bin/python"; RC = os.path.expanduser("~/.venvs/rcpark/bin/python")

def stl_stats(pfad):
    import trimesh
    m = trimesh.load(pfad, force="mesh"); b = m.bounds
    return dict(dreiecke=int(len(m.faces)), volumen=float(m.volume), bbox=[[float(x) for x in b[0]], [float(x) for x in b[1]]], wasserdicht=bool(m.is_watertight))

def lade(spec, od):
    p = os.path.join(od, spec["pfad"]); art = spec.get("art", "json")
    if art == "stl": return stl_stats(p)
    d = json.load(open(p))
    if art == "masstabelle": return dict(pruefungen=[dict(name=q["name"], wert=q["wert"], soll=q["soll"]) for q in d["pruefungen"]], messungen=d["messungen"])
    if art == "pruefbericht": return dict(werte=d["werte"], ok={q["name"]: q["ok"] for q in d["pruefungen"]}, bestanden=d.get("bestanden"))
    return d

def vergleiche(a, b, tol, ign, pfad="", out=None):
    if out is None: out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in ign: continue
            if k not in a: out.append(f"{pfad}/{k}: nur im neuen Stand"); continue
            if k not in b: out.append(f"{pfad}/{k}: fehlt im neuen Stand"); continue
            vergleiche(a[k], b[k], tol, ign, f"{pfad}/{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): out.append(f"{pfad}: Laenge {len(a)} -> {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)): vergleiche(x, y, tol, ign, f"{pfad}[{i}]", out)
    elif isinstance(a, bool) or isinstance(b, bool):
        if a != b: out.append(f"{pfad}: {a} -> {b}")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if not (np.isnan(a) and np.isnan(b)) and abs(a - b) > tol + 1e-6 * max(abs(a), abs(b)): out.append(f"{pfad}: {a} -> {b}")
    else:
        if a != b: out.append(f"{pfad}: {str(a)[:60]!r} -> {str(b)[:60]!r}")
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--schnappschuss", action="store_true"); ap.add_argument("--pruefen", action="store_true"); ap.add_argument("--ohne-kette", action="store_true")
    a = ap.parse_args(); obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od)); R = obj.get("regression")
    if not R: print(f"KEINE Regressions-Konfiguration in {a.objekt} (objekt.json[\"regression\"] fehlt) - nichts geprueft"); return 2      # 16.11.2026: brach mit KeyError ab
    basis = os.path.join(od, "regression", "basis"); os.makedirs(basis, exist_ok=True)
    if not a.ohne_kette:
        for cmd in R["kette"]:
            c = cmd.format(PY=PY, RC=RC, OBJ=os.path.relpath(a.objekt, repo), OD=os.path.relpath(od, repo)); print("+", c[:140])
            r = subprocess.run(c, shell=True, cwd=repo, capture_output=True, text=True)
            if r.returncode not in (0, 1) or "Traceback" in r.stderr or "Traceback" in r.stdout:   # Pruefstand darf rot sein (rc 1), ein Absturz nie
                print(r.stdout[-1500:], r.stderr[-1500:]); sys.exit(f"Kettenschritt fehlgeschlagen (rc {r.returncode})")
    if a.schnappschuss:
        for name, spec in R["dateien"].items():
            json.dump(lade(spec, od), open(os.path.join(basis, name + ".json"), "w"), indent=1, ensure_ascii=False)
        json.dump(dict(kette=R["kette"], hinweis="Schnappschuss der Ergebnisdateien; Vergleich mit regression.py --pruefen"), open(os.path.join(basis, "_info.json"), "w"), indent=1, ensure_ascii=False)
        print(f"Schnappschuss: {len(R['dateien'])} Dateien nach {basis}")
    if a.pruefen:
        fehler = 0
        for name, spec in R["dateien"].items():
            bp = os.path.join(basis, name + ".json")
            if not os.path.exists(bp): print(f"  ?  {name}: kein Schnappschuss"); continue
            diff = vergleiche(json.load(open(bp)), lade(spec, od), float(spec.get("toleranz", 0.01)), set(spec.get("ignorieren", [])) | {"datum", "historie"})
            if diff: fehler += 1; print(f"  ABWEICHUNG {name} ({len(diff)}):"); [print("      " + d) for d in diff[:8]]
            else: print(f"  OK         {name}")
        print("REGRESSION:", "identisch - nichts verloren" if not fehler else f"{fehler} Datei(en) weichen ab"); sys.exit(1 if fehler else 0)

if __name__ == "__main__":
    main()
