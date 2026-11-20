#!/usr/bin/env python3
"""diff_parallel.py - Foto-Diff-Auswertung (modell_wettbewerb.py) PARALLEL statt nacheinander (7.11., 'Zeit ist Geld'): je (Glaettung, Modus) ein eigener Job ueber
tools/job_start.sh mit JOB_GPU_MB (Standard 2500) - der Job-Starter laesst so viele parallel laufen, wie das VRAM-Budget (7000 MiB) erlaubt.
  python3 tools/diff_parallel.py start NAME --objekt modelle/kaufhaus_null5/objekt.json --basis B:pfad.stl --kandidat X:pfad.stl [--kandidat ...] --liste 000,004,.. [--g 0.18,0.05] [--modi global,region --box x0,y0,z0,x1,y1,z1]
  python3 tools/diff_parallel.py tabelle NAME            # Mittel/Median je Kandidat, besser/schlechter je Konfiguration (wartet nicht)
Ausgabe: /media/oem/scan/rc-park_null/diffpar/NAME/<modus>_<g>/ (ergebnis.json, log).
Weitere Optionen: --g 0.18,0.05 (Glaettungen), --gpu-mb 2500, --masken DIR. Umgebung: python3 genuegt (Jobs laufen mit venv-seg).
"""
import sys, os, json, argparse, subprocess, shutil, glob
R = "/media/oem/scan/rc-park_null"; REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = "/media/oem/scan/venv-seg/bin/python"
ap = argparse.ArgumentParser(); ap.add_argument("modus"); ap.add_argument("name"); ap.add_argument("--objekt", default="modelle/kaufhaus_null5/objekt.json"); ap.add_argument("--basis")
ap.add_argument("--kandidat", action="append", default=[]); ap.add_argument("--liste"); ap.add_argument("--g", default="0.18,0.05"); ap.add_argument("--modi", default="global"); ap.add_argument("--box")
ap.add_argument("--gpu-mb", default="2500"); ap.add_argument("--masken", default=R + "/wettbewerb_kh9g/masken"); a = ap.parse_args(); D = f"{R}/diffpar/{a.name}"
if a.modus == "start":
    os.makedirs(D, exist_ok=True); namen = [k.split(":")[0] for k in a.kandidat] + [a.basis.split(":")[0]]
    for g in a.g.split(","):
        for modus in a.modi.split(","):
            A = f"{D}/{modus}_{g}"; os.makedirs(A + "/masken", exist_ok=True)
            for f in glob.glob(a.masken + "/*.png"):
                for n in namen:
                    t = f"{A}/masken/{n}_{os.path.basename(f)}"
                    if not os.path.exists(t): shutil.copy(f, t)
            kand = " ".join(f"--kandidat {k}" for k in [a.basis] + a.kandidat); extra = f"--fd-arg=--region=quader --fd-arg=--region-box={a.box}" if modus == "region" else ""
            sh = f"{A}/lauf.sh"; open(sh, "w").write(f"#!/bin/bash\ncd {REPO}\nPYTORCH_CUDA_ALLOC_CONF=expandable_segments:True {PY} -W ignore -I tools/modell_wettbewerb.py {a.objekt} --aus {A} {kand} --basis {a.basis.split(':')[0]} --raster --kerne 1 --fd-arg=--glaettung={g} --liste {a.liste} {extra}\necho fertig > {A}/fertig\n"); os.chmod(sh, 0o755)
            env = dict(os.environ, JOB_GPU_MB=a.gpu_mb); jn = f"dp-{a.name}-{modus}-{g}".replace(".", "")
            print(subprocess.run([f"{REPO}/tools/job_start.sh", jn, f"{A}/lauf.log", sh], env=env, capture_output=True, text=True).stdout.strip().splitlines()[-1])
else:
    import numpy as np
    for d in sorted(glob.glob(D + "/*_*")):
        p = d + "/ergebnis.json"
        if not os.path.exists(p): print(os.path.basename(d), "noch nicht fertig" if not os.path.exists(d + "/fertig") else "kein Ergebnis"); continue
        r = json.load(open(p)); ph = sorted({k.split("|")[1] for k in r}); ks = sorted({k.split("|")[0] for k in r}); B = ks[0] if "B" not in ks else "B"
        print(os.path.basename(d), "Fotos", len(ph))
        for k in ks:
            ok = [x for x in ph if f"{k}|{x}" in r and r[f"{k}|{x}"].get("lr") is not None and (k == B or r.get(f"{B}|{x}", {}).get("lr") is not None)]; v = np.array([r[f"{k}|{x}"]["lr"] for x in ok]); 
            if k == B: print(f"  {k} (Basis) Mittel {v.mean():+.4f} Median {np.median(v):+.4f}"); continue
            bv = np.array([r[f"{B}|{x}"]["lr"] for x in ok]); dl = v - bv
            print(f"  {k} Mittel {v.mean():+.4f} Median {np.median(v):+.4f} | gegen Basis {dl.mean():+.4f}, besser {int((dl < -1e-4).sum())} schlechter {int((dl > 1e-4).sum())}")
