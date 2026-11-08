#!/usr/bin/env python3
"""test_gpu_gleichwertig.py - BEWEIS: Ist die GPU-Fassung von foto_diff gleichwertig zur CPU-Fassung? (2026-11-04, Nutzerauftrag)

Die GPU-Fassung ist nicht bitgleich (andere Zufallspunkte der Oberflaechenabtastung, float32). Massstab fuer "gleichwertig" ist das
Stichproben-Rauschen der Methode selbst: CPU Saat 0 gegen CPU Saat 1 (FD_SAAT). Bestanden, wenn je Kennzahl die mittlere Abweichung
|GPU - CPU0| hoechstens FAKTOR x |CPU1 - CPU0| + Untergrenze ist (ANNAHME FAKTOR 2: GPU darf nicht deutlich mehr streuen als ein Saatwechsel).
Laeuft alle Faelle parallel (Nutzerregel). Ergebnis: <audit>/test_gpu_gleichwertig.json
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/test_gpu_gleichwertig.py modelle/<obj>/objekt.json --fotos 004,010,023 [--faktor 2]
"""
import sys, os, json, argparse, subprocess, tempfile, numpy as np
from concurrent.futures import ThreadPoolExecutor

TOOLS = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(TOOLS); PY = "/media/oem/scan/venv-seg/bin/python"
KENN = {"anteil_modellkanten_ohne_foto": 0.002, "anteil_fotokanten_ohne_modell": 0.002, "kosten0": 0.002}   # Untergrenze je Kennzahl (ANNAHME: Rundung/Rauschen unter 0,2 %)


def lauf(objp, nr, modus, saat, aus):
    env = dict(os.environ, FD_SAAT=str(saat), FD_RASTER="0"); env.pop("FD_PUNKTE_DIR", None)          # beweist die PUNKT-Fassung GPU = CPU (Raster ist absichtlich anders, eigener Beweis test_foto_diff)
    if modus == "gpu": env["FD_GPU"] = "1"
    else: env.pop("FD_GPU", None)
    a = os.path.join(aus, f"{modus}{saat}", nr); os.makedirs(a, exist_ok=True)
    r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(TOOLS, "foto_diff.py"), objp, nr, "--aus", a], cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode not in (0, 1): raise SystemExit(f"foto_diff {modus}{saat} {nr} rc {r.returncode}: {r.stderr[-400:]}")
    e = json.load(open(os.path.join(a, f"foto_diff_{nr}.json")))
    return dict(anteil_modellkanten_ohne_foto=e["anteil_modellkanten_ohne_foto"], anteil_fotokanten_ohne_modell=e["anteil_fotokanten_ohne_modell"], kosten0=(e.get("versatz") or {}).get("kosten0"),
                gpu=bool(e.get("gpu")))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--fotos", required=True); ap.add_argument("--faktor", type=float, default=2.0); ap.add_argument("--aus")
    ap.add_argument("--parallel", type=int, default=4, help="gleichzeitige foto_diff-Prozesse (RAM ~2,4 GB je Prozess)"); a = ap.parse_args()
    objp = os.path.abspath(a.objekt); obj = json.load(open(objp)); fotos = a.fotos.split(",")
    aus = a.aus or tempfile.mkdtemp(prefix="test_gpu_gleichwertig_", dir="/media/oem/scan/rc-park_null")
    faelle = [(nr, m, s) for nr in fotos for m, s in (("cpu", 0), ("cpu", 1), ("gpu", 0))]
    with ThreadPoolExecutor(a.parallel) as ex: erg = dict(zip(faelle, ex.map(lambda x: lauf(objp, x[0], x[1], x[2], aus), faelle)))
    if not all(erg[(nr, "gpu", 0)]["gpu"] for nr in fotos): raise SystemExit("GPU-Fassung lief nicht (kein 'gpu' im Bericht)")
    tab, ok = {}, True
    for k, unter in KENN.items():
        saat = [abs(erg[(nr, "cpu", 1)][k] - erg[(nr, "cpu", 0)][k]) for nr in fotos if erg[(nr, "cpu", 0)][k] is not None]
        gpu = [abs(erg[(nr, "gpu", 0)][k] - erg[(nr, "cpu", 0)][k]) for nr in fotos if erg[(nr, "cpu", 0)][k] is not None]
        grenze = a.faktor * float(np.mean(saat)) + unter; b = float(np.mean(gpu)) <= grenze; ok &= b
        tab[k] = dict(saatwechsel_cpu=round(float(np.mean(saat)), 5), gpu_gegen_cpu=round(float(np.mean(gpu)), 5), grenze=round(grenze, 5), bestanden=b)
        print(f"  {k:32s} Saatwechsel CPU {np.mean(saat):.4f} | GPU-CPU {np.mean(gpu):.4f} | Grenze {grenze:.4f} -> {'ok' if b else 'NICHT'}")
    ad = os.path.join(ROOT, obj.get("audit", os.path.relpath(os.path.dirname(objp), ROOT) + "/audit")); os.makedirs(ad, exist_ok=True)
    res = dict(fotos=fotos, faktor=a.faktor, kennzahlen=tab, je_foto={f"{nr}_{m}{s}": v for (nr, m, s), v in erg.items()}, bestanden=ok, arbeit=aus)
    json.dump(res, open(os.path.join(ad, "test_gpu_gleichwertig.json"), "w"), indent=1)
    print("BEWEIS GPU gleichwertig:", "BESTANDEN" if ok else "NICHT BESTANDEN"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
