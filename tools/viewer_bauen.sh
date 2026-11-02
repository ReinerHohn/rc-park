#!/bin/bash
# viewer_bauen.sh <objekt> [ausgabe.html] - 3D-Viewer in EINEM Befehl: Modell-STL (Referenz), Nullstart-/Vergleichs-STL, Nebengebaeude, rohe + entzerrte Fotowolke (mit Farben).
# Einheiten: --stl = mm bei 1:massstab (Viewer rechnet selbst), --stl2 = METER (hier umgerechnet). Pfade: --sfm/--punkte/--dicht relativ zum Objektordner.
# Die Veroeffentlichung macht nicht das Skript, sondern der Artifact-Aufruf in der Sitzung (gleiche URL, Version steigt).
set -e
O=${1:-martinstor}; cd "$(dirname "$0")/.."; OD=modelle/$O
OUT=${2:-${TMPDIR:-/tmp}/${O}_3d.html}; T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
PY=/media/oem/scan/venv-seg/bin/python
ARGS=(--sfm messprotokoll/SFM-AUSRICHTUNG-nord.json --punkte sfm/dicht_nord_modell.npy --stl --titel "Martinstor 3D" --out "$OUT")
# entzerrte Wolke + Farben (gleiche Punktfolge wie roh) als farbige dichte Wolke
if [ -f $OD/sfm/dicht_nord_entzerrt.npy ] && [ -f $OD/sfm/dicht_nord_farben.npy ]; then
  cp $OD/sfm/dicht_nord_entzerrt.npy $T/dicht_e.npy; cp $OD/sfm/dicht_nord_farben.npy $T/dicht_e_farben.npy; ARGS+=(--dicht $T/dicht_e.npy)
fi
# Nullstart-STL (mm 1:87) -> Meter
NS=modelle/stl/${O}_null_v4_1-87.stl
if [ -f "$NS" ]; then $PY -W ignore -I -c "import trimesh,sys; m=trimesh.load('$NS'); m.apply_scale(87/1000); m.export('$T/null_m.stl')"; ARGS+=(--stl2 $T/null_m.stl); fi
# Nebengebaeude (Meter, Modellsystem) aus objekt.json
for P in $(python3 -I -c "import json;[print(v['stl_m']) for v in json.load(open('$OD/objekt.json')).get('nebengebaeude',{}).values() if v.get('stl_m')]"); do
  [ -f "$P" ] && ARGS+=(--stl2 "$PWD/$P")
done
python3 -I tools/sfm_html_viewer.py $OD/objekt.json "${ARGS[@]}" | tail -n 1
