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


def repo_pfad(rel, root=None):
    """Pfad einer Repo-Eingabe (objekt.json 'fotos_dir', 'stl', ...): absolut -> unveraendert; sonst <root>/<rel>. Fehlt es dort und ist RCPARK_HAUPTORDNER gesetzt
    (tools/schnelltest.sh in einem git-Worktree: unversionierte Eingaben wie daten/<obj>/fotos, modelle/stl/*.stl liegen nur im Hauptordner), dann <haupt>/<rel> -
    NUR ZUM LESEN (22.11.2026: jeder Agent verlor eine Runde an 3 roten Schnelltest-Zeilen wegen fehlender unversionierter Eingaben)."""
    if os.path.isabs(rel): return rel
    p = os.path.join(root or ROOT, rel); h = os.environ.get("RCPARK_HAUPTORDNER")
    if not os.path.exists(p) and h and os.path.exists(os.path.join(h, rel)): return os.path.join(h, rel)
    return p


TEMP_KANDIDATEN =(os.path.join(GROSS, "tmp"), os.path.join(SCAN, "rc-park_tmp"))   # 22.11.2026: Root (48 GB) lief zweimal voll, u. a. /tmp/test_vordach_* je 23 MB nach jedem Schnelltest


def temp_wurzel():
    """Wurzel fuer Temp-Ordner, NIE Root, wenn es anders geht: $TMPDIR (gesetzt, vorhanden, beschreibbar) -> /media/oem/rcdaten/tmp -> /media/oem/scan/rc-park_tmp
    -> System-Temp (nur wenn keine Datenplatte eingehaengt ist; die Unterordner liegen AUF der Platte, fehlt sie, fehlt auch der Ordner)."""
    for k in (os.environ.get("TMPDIR") or "",) + TEMP_KANDIDATEN:
        if k and os.path.isdir(k) and os.access(k, os.W_OK): return k
    import tempfile
    return tempfile.gettempdir()


def temp_ordner(prefix="tmp_"):
    """Neuer Temp-Ordner unter temp_wurzel(), der beim Prozessende entfernt wird (atexit: auch nach Ausnahme/assert/sys.exit, nicht nach SIGKILL).
    RCPARK_TEST_BEHALTEN=1 laesst ihn zum Ansehen stehen (Pfad wird gemeldet). Ersatz fuer tempfile.mkdtemp in Tests und Selbsttests."""
    import tempfile, atexit, shutil
    d = tempfile.mkdtemp(prefix=prefix, dir=temp_wurzel())
    if os.environ.get("RCPARK_TEST_BEHALTEN") == "1": print(f"(Temp-Ordner bleibt stehen: {d})", file=sys.stderr)
    else: atexit.register(shutil.rmtree, d, True)
    return d


if __name__ == "__main__":
    fehlt = 0
    for n, p in [("ROOT", ROOT), ("SCAN", SCAN), ("GROSS", GROSS), ("DATEN", DATEN), ("JOB_LOGS", JOB_LOGS), ("COLMAP", COLMAP)] + [(f"PY[{k}]", v) for k, v in PY.items()]:
        ok = os.path.exists(p); fehlt += not ok; print(f"{'ok  ' if ok else 'FEHLT'} {n:9s} {p}")
    sys.exit(1 if fehlt else 0)
