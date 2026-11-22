#!/usr/bin/env python3
"""durchblick_eck_nach_ausrichtung_1122.py <eck.json> <modell_a> <ausrichtung.json> <aus kopplung.json> - B_nach_A der Kettenstufe (seiten_eck_koppeln) in den
Ausrichtungsrahmen (A -> Ausrichtung per sim3_meter) -> kopplung.json mit M_b_nach_ausrichtung (fuer durchblick_wandwinkel / kopplung_tor)."""
import os, sys, json, numpy as np, pycolmap
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim3_robust import sim3_meter
ej, ma, au, aus = sys.argv[1:5]; e = json.load(open(ej)); st = {k: np.asarray(v["standort"], float) for k, v in json.load(open(au))["kameras"].items() if v.get("standort") is not None}
r = pycolmap.Reconstruction(ma); ns = [im for im in r.images.values() if im.has_pose and os.path.splitext(im.name)[0] in st]
f = sim3_meter(np.array([im.projection_center() for im in ns]), np.array([st[os.path.splitext(im.name)[0]] for im in ns]))
M = f["M"] @ np.asarray(e["B_nach_A"]); os.makedirs(os.path.dirname(os.path.abspath(aus)), exist_ok=True)
json.dump(dict(M_b_nach_ausrichtung=M.tolist(), quelle=ej, pruefung=e.get("pruefung")), open(aus, "w"), indent=1); print("Massstab B->Ausrichtung", round(float(np.cbrt(np.linalg.det(M[:3, :3]))), 4), "->", aus)
