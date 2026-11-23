#!/usr/bin/env python3
"""bruecke2_suedwand_1122.py <ergebnis.json> <teil_a> <teil_b> <ausrichtung.json> <objekt.json> --aus DIR  (22.11.2026)
Jede Kopplungsvariante B->A aus bruecke2_selbsttest (--echt) in den Ausrichtungsrahmen (A -> Ausrichtung per sim3_meter ueber die Kamerastandorte, wie
durchblick_eck_nach_ausrichtung_1122) und Wandwinkel/Lage je LoD2-Kante (durchblick_wandwinkel_1122) - die Suedwand ist reine PRUEFUNG (LoD2), nicht angepasst."""
import os, sys, json, argparse, subprocess, re, numpy as np, pycolmap
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
from sim3_robust import sim3_meter
ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("ergebnis", "teil_a", "teil_b", "ausrichtung", "objekt")]; ap.add_argument("--aus", required=True); a = ap.parse_args()
os.makedirs(a.aus, exist_ok=True); e = json.load(open(a.ergebnis))
st = {k: np.asarray(v["standort"], float) for k, v in json.load(open(a.ausrichtung))["kameras"].items() if v.get("standort") is not None}
r = pycolmap.Reconstruction(a.teil_a); ns = [im for im in r.images.values() if im.has_pose and os.path.splitext(im.name)[0] in st]
f = sim3_meter(np.array([im.projection_center() for im in ns]), np.array([st[os.path.splitext(im.name)[0]] for im in ns]))
var = {k: v for k, v in (e.get("_M") or {}).items() if v} | {"ausgleich_" + k: v["M"] for k, v in (e.get("ausgleich") or {}).items() if v.get("M")}
if ((e.get("fuehren") or {}).get("epipolar") or {}).get("M"): var["epipolar"] = e["fuehren"]["epipolar"]["M"]
out = {}
for k, M in var.items():
    if isinstance(M, str): M = json.loads(M)
    kj = os.path.join(a.aus, f"kopplung_{k}.json"); json.dump(dict(M_b_nach_ausrichtung=(f["M"] @ np.asarray(M, float)).tolist(), quelle=a.ergebnis, variante=k), open(kj, "w"))
    o = subprocess.run([sys.executable, "-I", os.path.join(T, "versuche", "durchblick_wandwinkel_1122.py"), a.teil_b, kj, a.objekt], capture_output=True, text=True).stdout
    w = {z.split(":")[0]: z.split(":", 1)[1].strip() for z in o.splitlines() if "->" in z and ":" in z}; out[k] = w
    sued = [v for kk, v in w.items() if kk.startswith("[-7.67, 8.93]")]; print(f"{k:28s} Suedwand {sued[0] if sued else '-'}", flush=True)
json.dump(out, open(os.path.join(a.aus, "suedwand.json"), "w"), indent=1)
