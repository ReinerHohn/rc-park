#!/usr/bin/env python3
"""test_repo_pfad.py - pfade.repo_pfad (22.11.2026): Schnelltest im git-Worktree liest fehlende unversionierte Eingaben (daten/<obj>/fotos, modelle/stl/*.stl)
NUR LESEND aus dem Hauptordner (RCPARK_HAUPTORDNER, setzt tools/schnelltest.sh). Prueft: absolut unveraendert; vorhandene Worktree-Datei gewinnt;
fehlt sie, Hauptordner; fehlt beides, Worktree-Pfad (Werkzeug meldet 'fehlt' wie bisher); ohne RCPARK_HAUPTORDNER nie Hauptordner."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import pfade
F = 0
def pruef(ok, t):
    global F
    print(("    ok    " if ok else "    FEHLER ") + t); F += 0 if ok else 1


with tempfile.TemporaryDirectory(prefix="test_repo_pfad_") as T:
    wt, ha = os.path.join(T, "wt"), os.path.join(T, "haupt")
    for d in (wt, ha): os.makedirs(os.path.join(d, "daten", "x", "fotos"))
    os.makedirs(os.path.join(ha, "modelle", "stl")); open(os.path.join(ha, "modelle", "stl", "x.stl"), "w").write("solid")
    os.environ.pop("RCPARK_HAUPTORDNER", None)
    pruef(pfade.repo_pfad("modelle/stl/x.stl", wt) == os.path.join(wt, "modelle/stl/x.stl"), "ohne RCPARK_HAUPTORDNER: nur der eigene Ordner")
    os.environ["RCPARK_HAUPTORDNER"] = ha
    pruef(pfade.repo_pfad("/abs/pfad", wt) == "/abs/pfad", "absoluter Pfad unveraendert")
    pruef(pfade.repo_pfad("daten/x/fotos", wt) == os.path.join(wt, "daten/x/fotos"), "vorhanden im Worktree -> Worktree")
    pruef(pfade.repo_pfad("modelle/stl/x.stl", wt) == os.path.join(ha, "modelle/stl/x.stl"), "fehlt im Worktree -> Hauptordner (lesend)")
    pruef(pfade.repo_pfad("modelle/stl/y.stl", wt) == os.path.join(wt, "modelle/stl/y.stl"), "fehlt ueberall -> Worktree-Pfad (Werkzeug meldet 'fehlt')")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "schnelltest.sh")).read()
pruef("--git-common-dir" in src and "UEBERSPRUNGEN (Eingabe fehlt)" in src and "uebersprungen" in src, "schnelltest.sh: Worktree-Erkennung, UEBERSPRUNGEN-Zeile, Zaehlung in der Ergebniszeile")
print("REPO-PFAD-TEST:", "alle ok" if not F else f"{F} FEHLER"); sys.exit(1 if F else 0)
