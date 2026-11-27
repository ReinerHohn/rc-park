#!/bin/bash
# handy_fusion_nachlauf.sh - Mehrmethoden-Fusion der Handy-Teilmodell-Wolke (Nutzer 27.11.: "mehrere Methoden, mergen, lieber mehr Zeit, hoehere Qualitaet").
# A = Teilfusion (laeuft automatisch am Ende von dicht_modell.py -> $T/dicht/fused.ply), B = Kachelfusion (hier, 150 Bilder je Kachel),
# dann kachel_vereinen.py (je Raumkachel die bessere Wolke). Protokoll: $T/fusion_nachlauf.log. Je Stufe rc, Abbruch mit Grund, Zeitlimit.
T=${T:-/media/oem/rcdaten/tmp/handy_teil_dicht}
PY=/media/oem/scan/venv-colmap/bin/python
AUS=modelle/schwabentor-1122/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1122.json
cd "$(dirname "$0")/.." || exit 2
t() { echo "$(date '+%F %T') $*"; }
warte() { local l=$1 m=$2 i=0; while [ $i -lt $m ]; do grep -q '^JOB_ENDE' "$l" 2>/dev/null && { grep '^JOB_ENDE' "$l" | tail -1 | sed 's/.*rc=//'; return 0; }; sleep 30; i=$((i+30)); done; echo 99; }
t "warte auf Ende von dicht_modell (Tiefenkarten + Teilfusion, max 5 h)"
rc=$(warte "$T/dicht.log" 18000); t "ENDE dicht_modell rc=$rc"
[ "$rc" = 0 ] && [ -f "$T/dicht/fused.ply" ] || { t "HINWEIS: Teilfusion (Methode A) fehlt oder rc!=0; Kachelfusion laeuft trotzdem"; A=0; }
L=$T/kachelfusion.log
if systemctl --user is-active --quiet rcpark-handy-teil-kachel; then t "Kachelfusion laeuft schon, warte auf sie"; L="$T/kachelfusion.log"; else rm -f "$L"; JOB_RAM_MB=9500 bash tools/job_start.sh handy-teil-kachel "$L" $PY -I tools/kachelfusion.py "$T/dicht" "$T/kachel.ply" --ausrichtung $AUS --box -60 60 -60 60 --max_bilder 150 --tmp "$T/kachel_tmp"; fi
t "START kachelfusion (Methode B)"; rc=$(warte "$L" 21600); t "ENDE kachelfusion rc=$rc"; [ "$rc" = 0 ] || { t "ABBRUCH kachelfusion"; exit 1; }
[ "${A:-1}" = 0 ] && { t "FERTIG ohne Vereinigung (nur B): $T/kachel.ply"; exit 0; }
L2=$T/vereinen.log; rm -f "$L2"
JOB_RAM_MB=9500 bash tools/job_start.sh handy-teil-vereinen "$L2" $PY -I tools/kachel_vereinen.py "$T/dicht/fused.ply" "$T/kachel.ply" "$T/vereint.ply" --ausrichtung $AUS --faktor 1.3
t "START kachel_vereinen"; rc=$(warte "$L2" 7200); t "ENDE kachel_vereinen rc=$rc"; [ "$rc" = 0 ] || { t "ABBRUCH kachel_vereinen"; exit 1; }
t "FERTIG: A=$T/dicht/fused.ply B=$T/kachel.ply vereint=$T/vereint.ply (Verlust je Zone zaehlen: tools/dichte_diagnose.py, Bild ansehen)"
