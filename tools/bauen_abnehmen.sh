#!/bin/bash
# Bauen UND abnehmen - fuer JEDES Objekt mit modelle/<objekt>/objekt.json. Bricht bei Pruefstand-Fehler ab.
#   tools/bauen_abnehmen.sh martinstor          -> Generator aus objekt.json, dann tools/pruefstand.py
#   tools/bauen_abnehmen.sh martinstor --nur-pruefen
# Danach zeigen/committen/Viewer NUR bei "alle Pruefungen bestanden". Siehe CLAUDE.md, modelle/METHODE_MASSTABELLE.md.
set -e
cd "$(dirname "$0")/.."
OBJ="modelle/$1/objekt.json"; [ -f "$OBJ" ] || { echo "kein $OBJ"; exit 2; }
PY=/media/oem/scan/venv-seg/bin/python
if [ "$2" != "--nur-pruefen" ]; then
  GEN=$($PY -c "import json;print(json.load(open('$OBJ'))['generator'])")
  echo "+ $GEN"; eval "$GEN"
fi
$PY -W ignore -I tools/pruefstand.py "$OBJ"
