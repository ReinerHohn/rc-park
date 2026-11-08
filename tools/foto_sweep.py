#!/usr/bin/env python3
"""foto_sweep.py - GENERISCH: einen Parameter eines Bauteils in einem Bereich durchfahren und jeden Wert mit dem Foto-Diff bewerten (Peak = bester Wert).
Baut je Wert ein STL (baukasten_gen, BAUTEIL_PARAM) und startet EINEN diff_parallel-Lauf (global oder Region-Box) mit allen Kandidaten (parallel, beide Glaettungen).
  python3 tools/foto_sweep.py start NAME --obj kaufhaus_grob --typ stl_teil:erker --param dn --werte -0.4,-0.2,0,0.2,0.4 [--basis-json bp.json] [--box x0,y0,z0,x1,y1,z1] --fotos 000,016,...
  python3 tools/foto_sweep.py ergebnis NAME      # Tabelle (diff_parallel tabelle)
--basis-json: BAUTEIL_PARAM-Grundlage (weitere feste Werte, z. B. schon gefundene Parameter); der gesweepte Parameter ueberschreibt. Mehrere --param in getrennten Laeufen (Koordinatenweise)."""
import sys, os, json, subprocess, argparse, shutil
R = "/media/oem/scan/rc-park_null"; REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument("modus"); ap.add_argument("name"); ap.add_argument("--obj", default="kaufhaus_grob"); ap.add_argument("--typ"); ap.add_argument("--param"); ap.add_argument("--werte")
ap.add_argument("--basis-json"); ap.add_argument("--box"); ap.add_argument("--fotos"); ap.add_argument("--g", default="0.18,0.05"); ap.add_argument("--gpu-mb", default="1800"); a = ap.parse_args()
if a.modus == "ergebnis": os.execvp("python3", ["python3", f"{REPO}/tools/diff_parallel.py", "tabelle", a.name]); sys.exit()
base = json.load(open(a.basis_json)) if a.basis_json else {}; D = f"{R}/foto_sweep/{a.name}"; os.makedirs(D, exist_ok=True); kands = []
ref = f"{D}/ref.stl"; env0 = dict(os.environ, BAUTEIL_PARAM=json.dumps(base), SCALE="87", STL_NAME=f"fsweep_{a.name}_ref.stl", ELEMENTE_AUS=f"{D}/el.json")
for i, w in enumerate([None] + [float(x) for x in a.werte.split(",")]):
    bp = json.loads(json.dumps(base)); tag = "ref" if w is None else f"{a.param}{w:+.3f}"
    if w is not None: bp.setdefault(a.typ, {})[a.param] = w; bp[a.typ].setdefault("quelle", f"foto_sweep {a.name}")
    env = dict(os.environ, BAUTEIL_PARAM=json.dumps(bp), SCALE="87", STL_NAME=f"fsweep_{a.name}_{tag}.stl", ELEMENTE_AUS=f"{D}/el_{tag}.json")
    r = subprocess.run([os.path.expanduser("~/.venvs/rcpark/bin/python"), f"{REPO}/tools/baukasten_gen.py", a.obj], cwd=REPO, env=env, capture_output=True, text=True)
    if r.returncode: sys.exit(f"Bau {tag} fehlgeschlagen: {r.stderr[-300:]}")
    p = f"{REPO}/modelle/stl/fsweep_{a.name}_{tag}.stl"; q = f"{D}/{tag}.stl"; shutil.move(p, q); kands += ["--kandidat", f"{tag}:{q}"]
W = f"{R}/wettbewerb_kh/netze5/mvs_d03_fix.stl"
cmd = ["python3", f"{REPO}/tools/diff_parallel.py", "start", f"fs_{a.name}", "--objekt", "modelle/kaufhaus_null5/objekt.json", "--basis", f"d03fix:{W}"] + kands + ["--liste", a.fotos, "--g", a.g, "--gpu-mb", a.gpu_mb]
if a.box: cmd += ["--modi", "region", f"--box={a.box}"]
print(subprocess.run(cmd, cwd=REPO, capture_output=True, text=True).stdout[-400:])
