#!/usr/bin/env python3
"""test_sweep_synth.py <objekt> --wolke w.npy: Beweistest der GPU-Sweep-Methode fuer ALLE aktiven Bauteile (modelle/archiv/METHODE_GPU_SWEEP.md).
Wolke = Modellflaeche um bekannten Versatz verschoben; der Sweep muss ihn auf < 3 cm zurueckfinden. Exit 1, wenn ein Bauteil durchfaellt."""
import sys, os, json, re, subprocess, argparse
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--versatz", default="0.8,-1.2,0.5;-1.5,1.0,-0.7"); a = ap.parse_args()
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); O = json.load(open(os.path.join(R, "modelle", a.objekt, "objekt.json")))
MIT = {"gaubenreihe": "satteldach:haupt"}; bad = 0
for b in O["bauteile"]:
    t = b["typ"]
    if b.get("aktiv") is False or t.startswith("satteldach"): continue
    for v in a.versatz.split(";"):
        cmd = [sys.executable, "-I", os.path.join(R, "tools", "teil_sweep_gpu.py"), a.objekt, t, "--wolke", a.wolke, "--bereich", "2.5", "--synth=" + v] + (["--mit", MIT[t.split(":")[0]]] if t.split(":")[0] in MIT else [])
        o = subprocess.run(cmd, capture_output=True, text=True).stdout; m = re.search(r"BESTER PLATZ: du (\S+) dn (\S+) dz (\S+)", o)
        if not m: print(t, v, "KEIN ERGEBNIS"); bad += 1; continue
        e = [float(x) - float(y) for x, y in zip(m.groups(), v.split(","))]; ok = max(abs(x) for x in e) < 0.03; bad += not ok
        print("%-24s Versatz %-14s Fehler %+.3f %+.3f %+.3f  %s" % (t, v, *e, "OK" if ok else "FEHL"), flush=True)
print("alle bestanden" if not bad else "%d DURCHGEFALLEN" % bad); sys.exit(1 if bad else 0)
