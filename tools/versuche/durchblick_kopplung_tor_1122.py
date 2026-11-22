#!/usr/bin/env python3
"""durchblick_kopplung_tor_1122.py - Eingaben fuer wand_dicke_tor aus der Eck-Kopplung: Ausrichtung mit den Teil-1-Kameras an der GEKOPPELTEN Lage (statt GPS der Kette)
+ seiten_modelle-JSON (Teil 0 = Ketten-teil0_a, Teil 1 = Ketten-teil1_a, je duenne PLY). Danach: wand_dicke_tor.py objekt --seiten S --ausrichtung AU.
python -I ... <kopplung.json> <ausrichtung> <teil0_modell> <teil1_modell> <ply0> <ply1> <aus_dir>"""
import os, sys, json, numpy as np, pycolmap
kj, au_p, m0, m1, ply0, ply1, aus = sys.argv[1:8]; os.makedirs(aus, exist_ok=True)
M = np.asarray(json.load(open(kj))["M_b_nach_ausrichtung"]); au = json.load(open(au_p)); r = pycolmap.Reconstruction(m1); n = 0
for im in r.images.values():
    if not im.has_pose: continue
    k = os.path.splitext(im.name)[0]; c = M[:3, :3] @ np.asarray(im.projection_center()) + M[:3, 3]
    au["kameras"].setdefault(k, {})["standort"] = c.tolist(); n += 1
json.dump(au, open(os.path.join(aus, "ausrichtung_kopplung.json"), "w"))
json.dump(dict(teile=[dict(teil="t0", modell=m0, dicht=dict(fused=ply0)), dict(teil="t1", modell=m1, dicht=dict(fused=ply1))], vereint=["t0", "t1"], ergebnis=dict(art="vereint")),
          open(os.path.join(aus, "seiten_modelle_kopplung.json"), "w"), indent=1)
print(f"{n} Teil-1-Kameras an gekoppelter Lage -> {aus}")
