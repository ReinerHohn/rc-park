#!/bin/bash
# foto_check.sh <objekt> <fotodatei> [auftrag-nr] - Sofort-Urteil fuer ein vor Ort hochgeladenes Foto (Nutzer 16.11.2026: "ja, passt oder passt nicht").
# Braucht: modelle/<objekt>/audit/fotoauftrag.json (aus tools/foto_auftrag.py, die .json neben der HTML-Seite dorthin kopieren) und den Fassadenordner.
# Ausgabe: Urteil je Auftrag als Text + Bild <scratch>/check_<name>.jpg mit eingezeichnetem Zielbereich (gruen = passt, rot = nein) - dem Nutzer zurueckschicken.
set -e
OBJ=$1; FOTO=$2; NR=${3:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd); D=/media/oem/scan/rc-park_daten/$OBJ
FAS=$D/fassade_fein; [ -f "$FAS/fassaden.json" ] || FAS=$D/fassade
EXTRA=$(ls $ROOT/modelle/stl/*_1-87.stl 2>/dev/null | grep -v "/${OBJ}_1-87.stl" | grep -i "nachbar" | paste -sd, -)
AUS=${TMPDIR:-/tmp}/check_$(basename "${FOTO%.*}").jpg
/media/oem/scan/venv-seg/bin/python -W ignore -I $ROOT/tools/foto_schnellcheck.py $ROOT/modelle/$OBJ/objekt.json $FAS $ROOT/modelle/$OBJ/audit/fotoauftrag.json "$FOTO" ${EXTRA:+--stl $EXTRA} ${NR:+--auftrag-nr $NR} --aus "$AUS" || true
echo "Bild: $AUS"
