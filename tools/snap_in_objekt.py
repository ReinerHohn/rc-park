#!/usr/bin/env python3
"""snap_in_objekt.py - wege3d.json (rippen_pfad_snap.py) -> rippen_pfade.pfade_ohne_spiegel eines erker_polygon (13.11.2026).
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/snap_in_objekt.py modelle/<objekt>/objekt.json BAUTEIL_INDEX wege3d.json "QUELLTEXT" [--du 0]
Ersetzt pfade_ohne_spiegel (Gauss-geglaettet, 5 cm Raster, Spruenge > 0,25 m trennen, Stuecke < 0,3 m verwerfen), setzt quelle_snap. --du: u-Verschiebung (z.B. fuer Spiegel/Uebertragung)."""
import sys, json, numpy as np
from scipy.ndimage import gaussian_filter1d
a = sys.argv[1:]; o = json.load(open(a[0])); r = o["bauteile"][int(a[1])]["unterbau"]["rippen_pfade"]; d = json.load(open(a[2])); du = float(a[a.index("--du") + 1]) if "--du" in a else 0.0
nor = r["pfade_ohne_spiegel"][0]["normale"]; out = []; tot = 0
for k, w in d.items():
    U = np.array(w["uzn"]); ok = np.isfinite(U[:, 0]); segs = []; cur = []
    for p, g in zip(U, ok):
        if not g or (cur and np.linalg.norm(p - cur[-1]) > 0.25):
            if len(cur) > 8: segs.append(np.array(cur))
            cur = []
        if g: cur.append(p)
    if len(cur) > 8: segs.append(np.array(cur))
    for s in segs:
        s = np.column_stack([gaussian_filter1d(s[:, i], 4, mode="nearest") for i in range(3)]); L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(s, axis=0), axis=1))]
        if L[-1] < 0.3: continue
        t = np.arange(0, L[-1], 0.05); s = np.column_stack([np.interp(t, L, s[:, i]) for i in range(3)]); s[:, 0] += du; out.append(dict(pfad=np.round(s, 3).tolist(), normale=nor)); tot += L[-1]
r["pfade_ohne_spiegel"] = out; r["quelle_snap"] = a[3]; json.dump(o, open(a[0], "w"), indent=1, ensure_ascii=False); print(len(out), "Pfade", round(tot, 1), "m")
