#!/usr/bin/env python3
"""abgeschaltete_teile.py - listet Schluessel in objekt.json, die ein Teil abgeschaltet/verworfen haben (Muster *_verworfen, deaktiv*, abgeschaltet).
Anlass 12.11.: 'stirn_verworfen' (Seitengelaender Balkon) war zwei Tage abgeschaltet, obwohl am Foto sichtbar. Vor jeder Fehlteil-Runde ausfuehren.
Aufruf: python3 tools/abgeschaltete_teile.py modelle/<objekt>/objekt.json"""
import sys, json, re
if len(sys.argv) < 2: sys.exit(__doc__)
o = json.load(open(sys.argv[1])); pat = re.compile(r"verworfen|deaktiv|abgeschaltet", re.I); n = 0
def walk(d, p):
    global n
    if isinstance(d, dict):
        for k, v in d.items():
            if k == "historie": continue
            if pat.search(k): print(f"{p}/{k} = {json.dumps(v, ensure_ascii=False)[:160]}"); n += 1
            walk(v, p + "/" + str(k))
    elif isinstance(d, list):
        for i, v in enumerate(d): walk(v, p + f"[{i}]")
walk(o.get("bauteile", o), "bauteile"); print(f"{n} abgeschaltete(r) Schluessel")
