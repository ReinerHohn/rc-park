#!/usr/bin/env python3
"""saeulen_breite_suche.py - Breite JEDES verlaengerten Pfeilers vom Foto-Diff bestimmen lassen (statt Mittelprofil; Nutzer 7.11.: echter Unterschied darf nicht untergehen).
Je Pfeiler i und Breite w (--breiten): Netz = Basis + Prismen (alle anderen Pfeiler = Median), Bewertung NUR in der Bildregion des Pfeilers (foto_diff --region quader, Box = Pfeiler +- --rand m, z 0..--hoehe)
auf den gleichen Fotos/Masken wie der Wettbewerb. Ausgabe: Tabelle kosten_lr je (Pfeiler, Breite) + beste Breite je Pfeiler (Mittel ueber beurteilbare Fotos, n angegeben). Kein Auswaehlen nach Passung:
feste Fotoliste. Aufruf siehe Kopf von tools/modell_wettbewerb.py (Masken: --maske-von).
  venv-seg/bin/python -I tools/saeulen_breite_suche.py OBJ.json --stl BASIS.stl --anker A --wolke W.npy --maske-von DIR --aus DIR --liste 000,004,... [--breiten 0.5,0.7,0.9,1.1] [--kerne 3]"""
import sys, os, json, glob, subprocess, argparse, numpy as np
from concurrent.futures import ThreadPoolExecutor
T = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--stl", required=True); ap.add_argument("--anker", required=True); ap.add_argument("--wolke", required=True)
ap.add_argument("--maske-von", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--liste", required=True); ap.add_argument("--breiten", default="0.5,0.7,0.9,1.1")
ap.add_argument("--kerne", type=int, default=3); ap.add_argument("--rand", type=float, default=1.0); ap.add_argument("--hoehe", type=float, default=3.2); ap.add_argument("--python-o3d", default="/media/oem/scan/venv-o3d/bin/python"); a = ap.parse_args()
os.makedirs(a.aus, exist_ok=True); info = os.path.join(a.aus, "saeulen.json"); fotos = a.liste.split(","); Ws = [float(x) for x in a.breiten.split(",")]
base = [a.python_o3d, os.path.join(T, "saeulen_schliessen.py"), "--stl", a.stl, "--anker", a.anker, "--wolke", a.wolke, "--profil", "median"]
subprocess.run(base + ["--aus", os.path.join(a.aus, "median.stl"), "--info", info], check=True, capture_output=True); S = json.load(open(info)); med = float(np.median([s["w"] for s in S])); print("Pfeiler:", [(round(s["x"], 1), round(s["y"], 1)) for s in S], "Median-Breite", round(med, 2))
jobs = []
for i, s in enumerate(S):
    for w in Ws:
        bw = [med] * len(S); bw[i] = w; stl = os.path.join(a.aus, f"p{i}_w{w}.stl")
        if not os.path.exists(stl): subprocess.run(base + ["--breiten", ",".join(f"{x:.3f}" for x in bw), "--aus", stl], check=True, capture_output=True)
        box = f"{s['x']-a.rand},{s['y']-a.rand},{s['z_boden']},{s['x']+a.rand},{s['y']+a.rand},{s['z_boden']+a.hoehe}"
        for nr in fotos: jobs.append((i, w, stl, nr, box))
def lauf(j):
    i, w, stl, nr, box = j; o = os.path.join(a.aus, "p2", f"p{i}_w{w}", nr); m = os.path.join(a.maske_von, f"{nr}.png")
    if not glob.glob(os.path.join(o, "foto_diff_*.json")):
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="", FD_RASTER="0"); subprocess.run([sys.executable, "-W", "ignore", "-I", os.path.join(T, "foto_diff.py"), a.objekt, nr, "--stl", stl, "--aus", o, "--bewertung-maske", m, "--region", "quader", "--region-box=" + box], capture_output=True, text=True, env=env)
    f = glob.glob(os.path.join(o, "foto_diff_*.json"))
    if not f: return j, None
    e = json.load(open(f[0])); return j, e.get("kosten_lr")
res = {}
with ThreadPoolExecutor(a.kerne) as ex:
    for j, v in ex.map(lauf, jobs): res[(j[0], j[1], j[3])] = v
out = {}
for i, s in enumerate(S):
    print(f"Pfeiler {i} bei ({s['x']:.1f}|{s['y']:.1f}), Messbreite Netz {s['w']:.2f}"); best = None
    for w in Ws:
        v = [res[(i, w, nr)] for nr in fotos if res.get((i, w, nr)) is not None]; mw = float(np.mean(v)) if v else None; out[f"{i}|{w}"] = dict(mittel=mw, n=len(v))
        print(f"  Breite {w:.2f}: lr {mw if mw is None else round(mw, 4)} (n={len(v)})")
        if mw is not None and (best is None or mw < best[1]): best = (w, mw)
    print("  beste Breite:", best)
json.dump(out, open(os.path.join(a.aus, "ergebnis.json"), "w"), indent=1)
