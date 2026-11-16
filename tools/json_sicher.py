#!/usr/bin/env python3
"""json_sicher.py - JSON-Dateien schreiben, ohne die alte Datei zu zerstoeren, wenn etwas schiefgeht.

Anlass 16.11.2026 (Stabilisierung): `json.dump(d, open(pfad, "w"))` leert die Datei ZUERST und schreibt dann. Ein nicht serialisierbarer Wert (numpy-Zahl), ein Abbruch
oder volle Platte mittendrin laesst eine abgeschnittene objekt.json/masstabelle.json zurueck - danach startet kein Werkzeug mehr. 15 Werkzeuge schrieben so.
schreiben(pfad, daten): erst vollstaendig in einen Text wandeln (numpy-Zahlen/-Felder werden umgewandelt), in <pfad>.neu schreiben, zurueckgelesen pruefen, dann os.replace (atomar).
"""
import os, json


def _std(o):
    try:
        import numpy as np
        if isinstance(o, np.generic): return o.item()
        if isinstance(o, np.ndarray): return o.tolist()
    except ImportError: pass
    if isinstance(o, (set, tuple)): return list(o)
    raise TypeError(f"nicht als JSON schreibbar: {type(o).__name__}")


def schreiben(pfad, daten, indent=1):
    text = json.dumps(daten, indent=indent, ensure_ascii=False, default=_std); json.loads(text)
    if os.path.islink(pfad): pfad = os.path.realpath(pfad)      # Verknuepfung erhalten
    neu = f"{pfad}.neu{os.getpid()}"
    with open(neu, "w") as f: f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(neu, pfad)
