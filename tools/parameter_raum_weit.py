#!/usr/bin/env python3
"""parameter_raum_weit.py <objekt> <typ[,typ..]> <aus.json> [lage=1.2] [mass=0.5]
Breite Fit-Grenzen (Regel 9c(a): Grenzen > erwarteter Fehler). Je Parameter um den Startwert (objekt.json):
Lage (u, n, z, mitte, wand, aussen, vorn, hinten, traufe, spitze_z, unterkante, oberkante, vor, dn, du, dz) +-lage m; Neigung/pitch +-2;
Masse (breite, tiefe, auskragung, dicke, hoehe...) +-mass*Wert (mind. 0,3 m); t in [0,1]. Parameter ohne Raum bleiben ohne."""
import sys, json, os
od = os.path.join(os.path.dirname(__file__), "..", "modelle", sys.argv[1]); typen = sys.argv[2].split(","); out = sys.argv[3]
lage = float(sys.argv[4]) if len(sys.argv) > 4 else 1.2; mass = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5
obj = json.load(open(os.path.join(od, "objekt.json"))); raum = json.load(open(os.path.join(od, "parameter_raum.json"))); neu = {"_doku": "automatisch breit (parameter_raum_weit.py)"}
LAGE = ("u", "mitte", "wand_n", "aussen", "n_", "z_", "unterkante", "oberkante", "vor", "spitze_z", "dn", "du", "dz", "traufe")
for t in typen:
    sp = next(b for b in obj["bauteile"] if b["typ"] == t); neu[t] = {}
    for k, v in raum.get(t, {}).items():
        if not (isinstance(v, dict) and "lo" in v): continue
        x = float(v.get("start", sp.get(k)))
        if k == "t": lo, hi = 0.0, 1.0
        elif "pitch" in k: lo, hi = x - 2.0, x + 2.0
        elif any(k.startswith(p) or k.endswith(p) or p in k for p in LAGE): lo, hi = x - lage, x + lage
        else: d = max(0.3, mass * abs(x)); lo, hi = max(0.0, x - d) if x >= 0 else x - d, x + d
        neu[t][k] = {"lo": round(lo, 3), "hi": round(hi, 3), "start": round(x, 4)}
json.dump(neu, open(out, "w"), indent=1); print(out, {t: len(v) for t, v in neu.items() if t != "_doku"})
