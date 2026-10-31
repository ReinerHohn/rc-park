#!/bin/bash
# Martinstor bauen UND abnehmen. Einziger vorgesehener Weg nach Generatoraenderungen (bricht bei Pruefstand-Fehler ab).
#   tools/martinstor_bauen.sh        -> STL 1:87 + Pruefstand (Foto-/Laser-Merkmale)
# Danach zeigen/committen/Viewer NUR wenn "alle Pruefungen bestanden". Siehe CLAUDE.md.
set -e
cd "$(dirname "$0")/.."
SCALE=87 MINMM=0.8 ~/.venvs/rcpark/bin/python modelle/martinstor_v4_gen.py
/media/oem/scan/venv-seg/bin/python -W ignore -I tools/modell_pruefstand.py modelle/stl/martinstor_v4_1-87.stl
