#!/usr/bin/env python3
"""json_sicher.py - JSON-Dateien schreiben, ohne die alte Datei zu zerstoeren, wenn etwas schiefgeht.

Anlass 16.11.2026 (Stabilisierung): `json.dump(d, open(pfad, "w"))` leert die Datei ZUERST und schreibt dann. Ein nicht serialisierbarer Wert (numpy-Zahl), ein Abbruch
oder volle Platte mittendrin laesst eine abgeschnittene objekt.json/masstabelle.json zurueck - danach startet kein Werkzeug mehr. 15 Werkzeuge schrieben so.
schreiben(pfad, daten): erst vollstaendig in einen Text wandeln (numpy-Zahlen/-Felder werden umgewandelt), in <pfad>.neu schreiben, zurueckgelesen pruefen, dann os.replace (atomar).

17.11.2026 (Durchsicht): (1) NaN/Infinity gingen durch - Python schreibt und liest 'NaN', es ist aber KEIN gueltiges JSON (Browser der 3D-Seite, jq und jeder strenge Leser scheitern
an der ganzen Datei). Jetzt: nicht-endliche Zahlen werden als null geschrieben und mit ihrem Schluesselpfad auf stderr gemeldet ('ACHTUNG json_sicher ...', die Kette sammelt solche Zeilen);
mit nan="fehler" stattdessen ValueError (alte Datei bleibt). (2) numpy-Zahlen als SCHLUESSEL ({np.int64(3): ...}) warfen TypeError (default= greift nur bei Werten) - sie werden wie
Python-Zahlen behandelt. Tupel als Schluessel bleiben ein Fehler (keine eindeutige Schreibweise).
"""
import os, sys, json, math


def _rein(o, pfad, funde):
    """Daten in reine JSON-Typen wandeln; nicht-endliche Zahlen -> None, Fundstellen (Schluesselpfad) nach `funde`."""
    try:
        import numpy as np
    except ImportError: np = None
    if np is not None:
        if isinstance(o, np.generic): o = o.item()
        elif isinstance(o, np.ndarray): o = o.tolist()
    if isinstance(o, float):
        if not math.isfinite(o): funde.append(pfad or "."); return None
        return o
    if isinstance(o, dict):
        aus = {}
        for k, v in o.items():
            if np is not None and isinstance(k, np.generic): k = k.item()
            if isinstance(k, float) and not math.isfinite(k): raise ValueError(f"nicht als JSON schreibbar: Schluessel {k!r} bei {pfad or '.'}")
            aus[k] = _rein(v, f"{pfad}.{k}" if pfad else str(k), funde)
        return aus
    if isinstance(o, (list, tuple, set)): return [_rein(v, f"{pfad}[{i}]", funde) for i, v in enumerate(o)]
    if o is None or isinstance(o, (str, int, bool)): return o
    raise TypeError(f"nicht als JSON schreibbar: {type(o).__name__} bei {pfad or '.'}")


def schreiben(pfad, daten, indent=1, nan="null"):
    funde = []; rein = _rein(daten, "", funde)
    if funde:
        text_f = f"{len(funde)} nicht-endliche Zahl(en) (NaN/Inf) in {pfad}: " + ", ".join(funde[:6]) + (" ..." if len(funde) > 6 else "")
        if nan == "fehler": raise ValueError("json_sicher: " + text_f)
        print("ACHTUNG json_sicher: " + text_f + " - als null geschrieben (NaN ist kein gueltiges JSON); Ursache im schreibenden Werkzeug klaeren", file=sys.stderr, flush=True)
    text = json.dumps(rein, indent=indent, ensure_ascii=False, allow_nan=False); json.loads(text)
    if os.path.islink(pfad): pfad = os.path.realpath(pfad)      # Verknuepfung erhalten
    neu = f"{pfad}.neu{os.getpid()}"
    with open(neu, "w") as f: f.write(text); f.flush(); os.fsync(f.fileno())
    os.replace(neu, pfad)
