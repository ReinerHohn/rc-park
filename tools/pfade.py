#!/usr/bin/env python3
"""pfade.py - EINE Stelle fuer Projektpfade und Python-Umgebungen (20.11.2026; bisher 179 Werkzeuge mit hart eingetragenen Objektnamen, 57 mit Datenpfad).
Neue Werkzeuge: `from pfade import ROOT, DATEN, objekt_dir, daten_dir, PY` statt Pfade selbst zu schreiben. Ohne Abhaengigkeiten, jede Umgebung.
  python3 tools/pfade.py            zeigt alle Pfade und prueft, ob sie da sind (rc 1 = etwas fehlt)"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools"); MODELLE = os.path.join(ROOT, "modelle")
SCAN = "/media/oem/scan"; GROSS = "/media/oem/rcdaten"                 # scan = Datenplatte (knapp), rcdaten = 2-TB-Platte fuer Grossdaten
DATEN = os.path.join(SCAN, "rc-park_daten"); JOB_LOGS = os.path.join(DATEN, "job_logs")
PY = {"seg": os.path.join(SCAN, "venv-seg/bin/python"), "col": os.path.join(SCAN, "venv-colmap/bin/python"), "gen": os.path.expanduser("~/.venvs/rcpark/bin/python")}
COLMAP = os.path.join(SCAN, "colmap-build/prefix/bin/colmap")


def objekt_dir(obj):
    """modelle/<obj> (objekt.json, masstabelle.json, audit/)."""
    return os.path.join(MODELLE, obj)


def objekt_json(obj):
    return os.path.join(objekt_dir(obj), "objekt.json")


def daten_dir(obj, anlegen=False):
    """Grossdaten eines Objekts: /media/oem/scan/rc-park_daten/<obj> (darf Symlink nach rcdaten sein)."""
    d = os.path.join(DATEN, obj)
    if anlegen: os.makedirs(d, exist_ok=True)
    return d


if __name__ == "__main__":
    fehlt = 0
    for n, p in [("ROOT", ROOT), ("SCAN", SCAN), ("GROSS", GROSS), ("DATEN", DATEN), ("JOB_LOGS", JOB_LOGS), ("COLMAP", COLMAP)] + [(f"PY[{k}]", v) for k, v in PY.items()]:
        ok = os.path.exists(p); fehlt += not ok; print(f"{'ok  ' if ok else 'FEHLT'} {n:9s} {p}")
    sys.exit(1 if fehlt else 0)
