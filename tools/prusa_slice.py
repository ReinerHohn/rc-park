#!/usr/bin/env python3
"""prusa_slice.py - STL -> G-Code fuer Prusa MK4S (0.4) mit den mitgelieferten PrusaSlicer-Profilen (Aufloesung von 'inherits').
  python3 tools/prusa_slice.py teil.stl [weitere.stl ...] --out ordner [--print "0.10mm FAST DETAIL @MK4IS 0.4"] [--arrange] [--support]
Mehrere STLs werden auf einem Blech angeordnet (--arrange) oder je einzeln geschnitten."""
import argparse, os, re, subprocess, sys, tempfile
F = "/usr/share/PrusaSlicer/profiles/PrusaResearch.ini"
ap = argparse.ArgumentParser(); ap.add_argument("stl", nargs="+"); ap.add_argument("--out", required=True)
ap.add_argument("--printer", default="Original Prusa MK4 Input Shaper 0.4 nozzle")
ap.add_argument("--print", dest="prn", default="0.10mm FAST DETAIL @MK4IS 0.4")
ap.add_argument("--filament", default="Prusament PLA @PGIS")
ap.add_argument("--support", action="store_true"); ap.add_argument("--arrange", action="store_true")
ap.add_argument("--set", action="append", default=[], help="key=value Ueberschreibung")
a = ap.parse_args()
sec = {}; cur = None
for l in open(F, encoding="utf8"):
    l = l.rstrip("\n")
    m = re.match(r"^\[(\w+):(.+)\]$", l)
    if m: cur = (m.group(1), m.group(2)); sec[cur] = {}; continue
    if cur and "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1); sec[cur][k.strip()] = v.strip()
def resolve(kind, name):
    d = sec[(kind, name)]; res = {}
    for p in [x.strip() for x in d.get("inherits", "").split(";") if x.strip()]: res.update(resolve(kind, p))
    res.update({k: v for k, v in d.items() if k not in ("inherits", "renamed_from")}); return res
cfg = {}
for kind, name in (("printer", a.printer), ("print", a.prn), ("filament", a.filament)): cfg.update(resolve(kind, name))
for k in ("compatible_printers_condition", "compatible_prints_condition", "compatible_printers", "compatible_prints"): cfg.pop(k, None)
cfg["binary_gcode"] = "0"; cfg["support_material"] = "1" if a.support else cfg.get("support_material", "0")
if a.support: cfg["support_material_auto"] = "1"
for s in a.set: k, v = s.split("=", 1); cfg[k] = v
os.makedirs(a.out, exist_ok=True)
ini = os.path.join(a.out, "_profil_mk4s.ini")
open(ini, "w").write("\n".join(f"{k} = {v}" for k, v in cfg.items()) + "\n")
jobs = [a.stl] if a.arrange else [[s] for s in a.stl]
for j in jobs:
    name = os.path.splitext(os.path.basename(j[0]))[0] + ("_blech" if len(j) > 1 else "")
    outf = os.path.join(a.out, name + ".gcode")
    cmd = ["prusa-slicer", "--load", ini, "--export-gcode", "--center", "125,105", "--output", outf] + (["--dont-arrange"] if len(j) == 1 else []) + j
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(("OK  " if r.returncode == 0 and os.path.exists(outf) else "FEHLER ") + name, (r.stderr or r.stdout).strip().splitlines()[-1:] if r.returncode else "")
