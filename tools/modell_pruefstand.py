#!/usr/bin/env python3
"""modell_pruefstand.py - ABGELOEST durch tools/pruefstand.py + modelle/martinstor/masstabelle.json (generisch, kein Code je Objekt).
Bleibt als Weiterleitung, damit alte Aufrufe/Dokumente weiter funktionieren:
  modell_pruefstand.py [stl]  ==  pruefstand.py modelle/martinstor/objekt.json [--stl stl]
"""
import os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = [sys.executable, "-W", "ignore", "-I", os.path.join(root, "tools", "pruefstand.py"), os.path.join(root, "modelle", "martinstor", "objekt.json")]
if len(sys.argv) > 1 and not sys.argv[1].startswith("-"): args += ["--stl", sys.argv[1]]
os.execv(sys.executable, args)
