#!/usr/bin/env python3
"""snap_in_objekt.py - wege3d.json (rippen_pfad_snap.py) -> rippen_pfade.pfade_ohne_spiegel eines erker_polygon (13.11.2026).
Aufruf: /media/oem/scan/venv-seg/bin/python -I tools/snap_in_objekt.py modelle/<objekt>/objekt.json BAUTEIL_INDEX wege3d.json "QUELLTEXT" [--du 0] [--um -8.47] [--anhaengen]
Normale je Achteck-Facette (0/+-45/+-90 Grad um (um, 12,27)) gedreht, Pfade an Facettengrenzen geteilt.
Ersetzt pfade_ohne_spiegel (Gauss-geglaettet, 5 cm Raster, Spruenge > 0,25 m trennen, Stuecke < 0,3 m verwerfen), setzt quelle_snap. --du: u-Verschiebung (z.B. fuer Spiegel/Uebertragung)."""
import sys, json, numpy as np
from scipy.ndimage import gaussian_filter1d
a = sys.argv[1:]; o = json.load(open(a[0])); r = o["bauteile"][int(a[1])]["unterbau"]["rippen_pfade"]; d = json.load(open(a[2])); du = float(a[a.index("--du") + 1]) if "--du" in a else 0.0
nor = [0.0, 0.796, -0.605]; UM = float(a[a.index("--um") + 1]) if "--um" in a else -8.47; AC = 12.27; out = []; tot = 0
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
        t = np.arange(0, L[-1], 0.05); s = np.column_stack([np.interp(t, L, s[:, i]) for i in range(3)]); s[:, 0] += du
        # je Achteck-Facette eigene Normale (um die Hochachse gedreht): Pfad an Facettengrenzen teilen (1 Punkt Ueberlappung)
        phi = np.degrees(np.arctan2(s[:, 0] - du - UM, s[:, 1] - AC)); fi = np.round(phi / 45.0).astype(int); cut = [0] + [j for j in range(1, len(s)) if fi[j] != fi[j - 1]] + [len(s)]
        for a_, b_ in zip(cut[:-1], cut[1:]):
            seg = s[max(a_ - 1, 0):min(b_ + 1, len(s))]
            if len(seg) < 4: continue
            f_ = int(np.bincount(fi[a_:b_] + 4).argmax()) - 4; th = np.radians(45.0 * f_); out.append(dict(pfad=np.round(seg, 3).tolist(), normale=[round(nor[1] * np.sin(th), 4), round(nor[1] * np.cos(th), 4), nor[2]]))
        tot += L[-1]
r["pfade_ohne_spiegel"] = (r["pfade_ohne_spiegel"] + out) if "--anhaengen" in a else out; r["quelle_snap"] = a[3]; json.dump(o, open(a[0], "w"), indent=1, ensure_ascii=False); print(len(out), "Pfade", round(tot, 1), "m")
