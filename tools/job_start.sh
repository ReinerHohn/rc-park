#!/bin/bash
# job_start.sh NAME LOGDATEI BEFEHL... - lange Jobs (Nullstart, SfM, Optimierer) als eigener systemd-Benutzerdienst starten.
# Grund (2026-11-03): Claude Code beendet seine Hintergrund-Shells bei Speicherknappheit, wenn die Sitzung untaetig ist -> Nullstart mitten in der
# Registrierung abgeschossen. Ein systemd-Dienst haengt nicht an der Sitzung; MemoryHigh bremst bei Knappheit (Auslagerung) statt zu toeten.
# GPU-Sperre (G5): enthaelt der Befehl ein Werkzeug aus tools/gpu_werkzeuge.txt, wartet der Start (60 s Takt, Hinweis alle 10 min), solange
#   (a) /media/oem/scan/rc-park_daten/.gpu_lock (Jobname PID Zeit) auf einen laufenden Job zeigt ODER (b) nvidia-smi fremde Compute-Prozesse zeigt.
#   (JOB_NVSMI=<cmd> ersetzt nvidia-smi, nur fuer Tests.) Der Job schreibt die Sperre beim Start und loescht sie am Ende (nur wenn sie seinen Namen traegt). JOB_OHNE_GPU_SPERRE=1 ueberspringt alles.
# VRAM-BUDGET (6.11., modelle/GPU_PARALLEL_UNTERSUCHUNG.md): JOB_GPU_MB=<MiB> (z.B. 2500) = dieser Job darf PARALLEL zu anderen GPU-Jobs laufen, wenn belegter VRAM + Budget <= JOB_GPU_LIMIT_MB
#   (Standard 7000 von 8188; Absturz ab ~7,8 GB Summe gemessen). Er beachtet eine Exklusiv-Sperre, schreibt selbst KEINE (Exklusiv-Jobs warten ueber nvidia-smi auf ihn). Der Job muss sein Budget selbst einhalten
#   (SIFT: max_image_size 1600 = RCPARK_SIFT_MAX=1600, Torch: PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True + torch.cuda.set_per_process_memory_fraction).
#   Ohne JOB_GPU_MB nimmt job_start.sh das Budget aus tools/gpu_budget.txt (Zeile '<werkzeug.py> <MiB> ...', gleicher Treffer wie gpu_werkzeuge.txt); kein Eintrag = exklusiv.
# Status:  systemctl --user status rcpark-NAME   |  Abbruch: systemctl --user stop rcpark-NAME  |  Ende: Zeile "JOB_ENDE rc=<n>" im Log
set -e
NAME="$1"; LOG="$2"; shift 2
[ -n "$NAME" ] && [ -n "$LOG" ] && [ $# -gt 0 ] || { echo "Aufruf: job_start.sh NAME LOGDATEI BEFEHL..."; exit 2; }
python3 "$(dirname "$0")/platz_pruefen.py" --daten-min-gb "${RCPARK_DATEN_MIN_GB:-5}" || exit 3   # Nutzer 10.11. abends: Standard 5 GB. Nutzer 7.11. nachts: "scheiss auf die 10 GB" -> RCPARK_DATEN_MIN_GB=5 nur bewusst setzen   # Platztor (G1)
if systemctl --user is-active --quiet "rcpark-$NAME"; then echo "rcpark-$NAME laeuft schon"; exit 1; fi
LOCK=/media/oem/scan/rc-park_daten/.gpu_lock
GPUJOB=0; BUDGET=${JOB_GPU_MB:-0}; LIMIT=${JOB_GPU_LIMIT_MB:-7000}
if [ "${JOB_OHNE_GPU_SPERRE:-0}" != "1" ]; then
  while read -r W; do
    [ -n "$W" ] || continue
    case "$*" in *"$W"*) GPUJOB=1
      [ -z "${JOB_GPU_MB:-}" ] && { BUDGET=$(awk -v w="$W" '$1==w {print $2; exit}' "$(dirname "$0")/gpu_budget.txt" 2>/dev/null | tr -dc 0-9); BUDGET=${BUDGET:-0}; }   # Budget aus tools/gpu_budget.txt (ohne Eintrag = exklusiv)
      break;; esac
  done < "$(dirname "$0")/gpu_werkzeuge.txt"
fi
if [ "$GPUJOB" = 1 ]; then
  T0=$(date +%s); LAST=$T0
  while :; do
    GRUND=""
    if [ -f "$LOCK" ]; then
      read -r LN LP _ < "$LOCK" || true
      if [ -n "$LN" ] && [ "$LN" != "$NAME" ] && { systemctl --user is-active --quiet "rcpark-$LN" 2>/dev/null || { [ -n "$LP" ] && kill -0 "$LP" 2>/dev/null; }; }; then
        GRUND="GPU belegt durch $LN"
      fi
    fi
    if [ -z "$GRUND" ] && [ "$BUDGET" -gt 0 ]; then
      USED=$(${JOB_NVSMI:-nvidia-smi} --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -dc 0-9); USED=${USED:-0}
      [ $((USED + BUDGET)) -gt "$LIMIT" ] && GRUND="VRAM-Budget: belegt ${USED} MiB + Job ${BUDGET} MiB > Grenze ${LIMIT} MiB"
    elif [ -z "$GRUND" ] && [ -n "$(${JOB_NVSMI:-nvidia-smi} --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' \n')" ]; then
      GRUND="GPU belegt durch fremden Prozess (nvidia-smi: $(${JOB_NVSMI:-nvidia-smi} --query-compute-apps=pid --format=csv,noheader | tr '\n' ' '))"
    fi
    [ -z "$GRUND" ] && break
    NOW=$(date +%s)
    if [ "$LAST" = "$T0" ] || [ $((NOW-LAST)) -ge 600 ]; then echo "$(date +%T) $GRUND, warte (seit $((NOW-T0)) s)"; LAST=$NOW; fi
    sleep 60
  done
  [ "$BUDGET" -gt 0 ] || echo "$NAME $$ $(date +%FT%T)" > "$LOCK"      # Budget-Jobs laufen parallel, ohne Exklusiv-Sperre
fi
systemctl --user reset-failed "rcpark-$NAME" 2>/dev/null || true
CMD=$(printf '%q ' "$@")
# 15.11.2026 (Recherche Durchsatz + Messung: SIFT 14 min statt < 1 min, weil CPU-Ausrichtungen alle Kerne belegten): GPU-Jobs bekommen CPU-Vorrang
# (CPUWeight 1000, alle Kerne); reine CPU-Jobs (JOB_GPU_MB=0) laufen mit CPUWeight 20 auf den 12 langsamen Kernen 16-27 (JOB_CPU=alle hebt das auf).
if [ "${BUDGET:-0}" -gt 0 ] 2>/dev/null || [ "${JOB_CPU:-}" = "alle" ]; then CPUW=1000; PIN=""; else CPUW=20; PIN="taskset -c ${JOB_CPU_KERNE:-16-27} "; fi
systemd-run --user --unit "rcpark-$NAME" --collect -p MemoryHigh="${JOB_MEMORY_HIGH:-11G}" -p CPUWeight="$CPUW" -p WorkingDirectory="$(pwd)" \
  /bin/bash -c "$PIN$CMD > '$LOG' 2>&1; rc=\$?; echo \"JOB_ENDE rc=\$rc\" >> '$LOG'; [ \"\$(cut -d' ' -f1 '$LOCK' 2>/dev/null)\" = '$NAME' ] && rm -f '$LOCK'; exit \$rc"
if [ "${RCPARK_OHNE_GPU_WACHE:-0}" != "1" ]; then                    # GPU-Wache (Lehre 14.11.: CPU-Werkzeug lief unbemerkt auf 18 Kernen, GPU 0 %)
  systemd-run --user --unit "rcpark-$NAME-gpuwache" --collect -p WorkingDirectory="$(pwd)" /bin/bash "$(cd "$(dirname "$0")" && pwd)/gpu_wache.sh" "$NAME" "$LOG" >/dev/null 2>&1 || true
fi
echo "gestartet: rcpark-$NAME -> $LOG"
