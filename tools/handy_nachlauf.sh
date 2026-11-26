#!/bin/bash
# handy_nachlauf.sh - wartet auf das Ende von LightGlue "paare" (JOB_ENDE im lg_paare.log), dann einlesen -> registrieren (--je-bild) fuer die
# Handyfotos 26.11. (Schwabentor). Jede Stufe schreibt Beginn/Ende/rc nach $Z/nachlauf.log; bei Fehler bricht die Kette mit Grund ab (kein stilles Weiter).
# Start: bash tools/job_start.sh handy-nachlauf $Z/nachlauf.log bash tools/handy_nachlauf.sh
Z=${Z:-/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261126_voll}
D=${D:-/media/oem/scan/rc-park_daten/schwabentor-1122}
PY=/media/oem/scan/venv-colmap/bin/python
cd "$(dirname "$0")/.." || exit 2
t() { echo "$(date '+%F %T') $*"; }
t "warte auf Ende von lg_paare (max 4 h)"
for i in $(seq 1 480); do
  grep -q '^JOB_ENDE' "$Z/lg_paare.log" && break; sleep 30
done
grep -q '^JOB_ENDE rc=0' "$Z/lg_paare.log" || { t "ABBRUCH: lg_paare nicht erfolgreich beendet: $(grep '^JOB_ENDE' "$Z/lg_paare.log")"; exit 1; }
t "lg_paare fertig"
t "START einlesen"; $PY -I tools/zusatzfotos_lightglue.py einlesen --ziel "$Z" --ref-sparse "$D/pipe/sfm/sparse/0"; rc=$?; t "ENDE einlesen rc=$rc"
[ $rc = 0 ] && [ -d "$Z/lg/ref_tri" ] || { t "ABBRUCH: einlesen fehlgeschlagen (Rig-Kennungen Ref-DB gegen sparse pruefen, Lehre UEBERGABE)"; exit 1; }
t "START registrieren --je-bild"; $PY -I tools/zusatzfotos_registrieren.py registrieren --sparse "$Z/lg/ref_tri" --aus "$Z/lg" --je-bild; rc=$?; t "ENDE registrieren rc=$rc"
[ $rc = 0 ] || { t "ABBRUCH: registrieren fehlgeschlagen"; exit 1; }
t "FERTIG: Ergebnis in $Z/lg (Einordnungsquote mit 97/241 vergleichen)"
