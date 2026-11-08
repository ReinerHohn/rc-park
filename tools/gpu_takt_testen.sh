#!/bin/bash
# gpu_takt_testen.sh - bringt Takt-Sperre der GPU (nvidia-smi -lgc) am ECHTEN Job etwas? Misst waehrend ein PatchMatch-Job laeuft (z. B. rcpark-video_dicht,
# Log mit Zeilen 'Iteration N: x.xxxs'): abwechselnd Phase A (Standard) und B (Takt gesperrt auf LO,HI), je PHASE s, 2 Durchgaenge (A B A B). Danach nvidia-smi -rgc.
#   sudo bash tools/gpu_takt_testen.sh [LOG=/media/oem/scan/rc-park_null/kaufhaus_video/dicht.log] [LO=2900] [HI=3105] [PHASE=60]
# Auswertung: mittlere Iterationszeit je Phase (KLEINER = schneller), mittlerer Takt/Leistung/Temperatur. Vorsicht: verschiedene Bilder haben verschiedene Iterationszeiten ->
# A B A B zeigt, ob der Unterschied ueber die Wiederholung hinweg stabil ist. Absturz/Instabilitaet durch Takt-Sperre ist moeglich (Nutzer akzeptiert, 6.11.).
set -u; export LC_ALL=C
LOG=${1:-/media/oem/scan/rc-park_null/kaufhaus_video/dicht.log}; LO=${2:-2900}; HI=${3:-3105}; PH=${4:-60}
[ "$(id -u)" = 0 ] || { echo "bitte mit sudo"; exit 1; }
[ -r "$LOG" ] || { echo "Log fehlt: $LOG"; exit 1; }
trap 'nvidia-smi -rgc >/dev/null 2>&1; echo "Takt-Sperre aufgehoben"' EXIT INT TERM
phase() {  # name sperre(0/1)
  if [ "$2" = 1 ]; then nvidia-smi -lgc $LO,$HI >/dev/null 2>&1 || echo "  (Sperre $LO,$HI abgelehnt)"; else nvidia-smi -rgc >/dev/null 2>&1; fi
  sleep 3; n0=$(wc -l < "$LOG"); ( for i in $(seq 1 $((PH/3))); do nvidia-smi --query-gpu=clocks.sm,power.draw,temperature.gpu --format=csv,noheader,nounits; sleep 3; done ) > /tmp/_gt.csv
  n1=$(wc -l < "$LOG")
  tail -n +$((n0+1)) "$LOG" | head -n $((n1-n0)) | grep -o "Iteration [0-9]*: [0-9.]*s" | awk -v nm="$1" '{gsub("s","",$3); s+=$3; n++} END{if(n) printf "%-9s Iterationen %3d  mittlere Zeit %.3f s", nm, n, s/n; else printf "%-9s keine Iterationszeilen (Job aktiv?)", nm}'
  awk -F, '{c+=$1; p+=$2; t+=$3; n++} END{if(n) printf "   Takt %4d MHz  Leistung %4.1f W  Temp %2d C\n", c/n, p/n, t/n}' /tmp/_gt.csv
}
echo "Job-Log: $LOG, Sperre $LO-$HI MHz, Phase $PH s"
phase "A-Std-1" 0; phase "B-Sperre-1" 1; phase "A-Std-2" 0; phase "B-Sperre-2" 1
echo "Fertig. Wenn B (Sperre) in BEIDEN Durchgaengen kleinere Zeit hat als das benachbarte A: Gewinn echt; sonst Rauschen/kein Nutzen."
