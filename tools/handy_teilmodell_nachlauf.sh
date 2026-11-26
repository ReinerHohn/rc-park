#!/bin/bash
# handy_teilmodell_nachlauf.sh - parallele Nachtstufe: Teilmodell-Mapper NUR aus den Handyfotos (Bruecke/Treppe/Unterdurchgang, die nicht per PnP ins
# Hauptnetz kamen), dann Einpassen ins erweiterte Netz. Wartet auf "FERTIG" in $Z/nachlauf.log (Registrierung). Protokoll: $Z/teilmodell_nachlauf.log
# Hinweis: Matching (LightGlue) ist KEIN Mapper; die Registrierung ordnet nur gegen bekannte 3D-Punkte ein; dieser Schritt baut aus den Rest-Fotos ein eigenes Netz.
Z=${Z:-/media/oem/rcdaten/rc-park_daten_neu/zusatz_20261126_voll}
PY=/media/oem/scan/venv-colmap/bin/python
cd "$(dirname "$0")/.." || exit 2
t() { echo "$(date '+%F %T') $*"; }
t "warte auf FERTIG in nachlauf.log (max 6 h)"
for i in $(seq 1 720); do grep -q 'FERTIG' "$Z/nachlauf.log" && break; grep -q 'ABBRUCH' "$Z/nachlauf.log" && { t "ABBRUCH: Registrierung fehlgeschlagen"; exit 1; }; sleep 30; done
grep -q 'FERTIG' "$Z/nachlauf.log" || { t "ABBRUCH: Registrierung nicht rechtzeitig fertig"; exit 1; }
L=$Z/lg/teilmodell.log; rm -f "$L"
JOB_RAM_MB=6000 bash tools/job_start.sh handy-teilmodell-nachlauf "$L" taskset -c 0-11 $PY -I tools/handy_teilmodell.py "$Z/lg/db.db" "$Z/lg/bilder" "$Z/lg/vorbereitet.json" "$Z/lg/teilmodell" --threads 12
t "START Teilmodell-Mapper"
while ! grep -q '^JOB_ENDE' "$L" 2>/dev/null; do sleep 30; done; rc=$(grep '^JOB_ENDE' "$L" | sed 's/.*rc=//'); t "ENDE Teilmodell-Mapper rc=$rc"
[ "$rc" = 0 ] || { t "ABBRUCH Teilmodell-Mapper"; exit 1; }
t "START Einpassen"; $PY -I tools/teilmodell_ausrichten.py "$Z/lg/sparse_handy/0" "$Z/lg/teilmodell" --ausrichtung modelle/schwabentor-1122/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1122.json 2>&1 | tail -30; t "ENDE Einpassen (Ergebnis: $Z/lg/teilmodell/ausrichtung.json)"
t "FERTIG: Teilmodelle + Einpassung; Bruecke/Treppe pruefen"
