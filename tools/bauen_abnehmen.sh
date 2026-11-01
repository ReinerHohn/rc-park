#!/bin/bash
# Bauen UND abnehmen - fuer JEDES Objekt mit modelle/<objekt>/objekt.json. Bricht bei Pruefstand-Fehler ab.
#   tools/bauen_abnehmen.sh martinstor          -> Generator aus objekt.json, dann tools/pruefstand.py, dann tools/seiten_audit.py (Sichtblatt)
#   tools/bauen_abnehmen.sh martinstor --nur-pruefen
# Danach zeigen/committen/Viewer NUR bei "alle Pruefungen bestanden" UND nachdem das Sichtblatt angesehen wurde (Lehre F5/F6).
set -e
cd "$(dirname "$0")/.."
OBJ="modelle/$1/objekt.json"; [ -f "$OBJ" ] || { echo "kein $OBJ"; exit 2; }
PY=/media/oem/scan/venv-seg/bin/python
if [ "$2" != "--nur-pruefen" ]; then
  GEN=$($PY -c "import json;print(json.load(open('$OBJ'))['generator'])")
  echo "+ $GEN"; eval "$GEN"
fi
set +e; $PY -W ignore -I tools/pruefstand.py "$OBJ"; RC=$?; set -e
$PY -W ignore -I tools/seiten_audit.py "$OBJ"     # Sichtblatt auch bei rotem Pruefstand (man will hinsehen)
# Automatische Foto-Diagnosen fuer jedes Foto mit kalibrierter Kamera (Breite je Hoehe in Metern, fehlende/erfundene Teile).
# Werkzeuge pruefen ihre Kameraguete selbst und steigen bei schlechter Kamera aus - kein Handgriff noetig.
for KJ in modelle/$1/messprotokoll/K-*.json; do
  [ -f "$KJ" ] || continue
  NR=$(basename "$KJ" .json); NR=${NR#K-}
  $PY -c "import json,sys; d=json.load(open('$KJ')); sys.exit(0 if 'kamera' in d else 1)" || continue
  echo "--- Foto $NR"
  OBJEKT="$OBJ" $PY -W ignore -I tools/foto_breitenprofil.py "$OBJ" "$NR" --eintragen 2>&1 | grep -E "Kamera-Guete|unbrauchbar|messbar;|AUFFAELLIG|Beobachtung" || true
  OBJEKT="$OBJ" $PY -W ignore -I tools/fehlteile_finden.py "$OBJ" "$NR" --top 6 2>&1 | grep -E "FEHLT|ERFUNDEN|Beobachtung" || true
done
exit $RC
