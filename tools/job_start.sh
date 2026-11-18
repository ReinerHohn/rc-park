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
mkdir -p "$(dirname "$LOG")" || { echo "Logordner nicht anlegbar: $(dirname "$LOG")"; exit 2; }      # 17.11.2026: fehlender Logordner liess den Dienst sofort mit rc 1 enden (nur im Journal sichtbar)
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
# BUCHUNG statt Messung (15.11.2026, Nutzer "macht das"): bisher (a) griff die Sperre nur bei Werkzeugnamen aus gpu_werkzeuge.txt - Skriptjobs mit JOB_GPU_MB
# liefen ungebremst - und (b) wurde der freie VRAM nur GEMESSEN: zwei fast gleichzeitige Starts sahen beide "frei" (3x CUDA out of memory am 15.11.).
# Jetzt: JOB_GPU_MB > 0 macht jeden Job zum GPU-Job; das Budget wird unter flock in $BUCH (NAME MiB ZEIT) gebucht. Start nur, wenn
# max(Summe der Buchungen laufender Jobs, gemessener VRAM) + Budget <= Grenze. Buchungen toter Jobs (aelter als 120 s, Dienst nicht aktiv) verfallen.
BUCH=/media/oem/scan/rc-park_daten/.gpu_buchung
[ "${JOB_OHNE_GPU_SPERRE:-0}" != "1" ] && [ "${BUDGET:-0}" -gt 0 ] 2>/dev/null && GPUJOB=1
buchen() {  # gibt 0 zurueck und bucht, wenn Platz ist; sonst 1 und setzt GRUND
  exec 9>>"$BUCH.lock"; flock 9
  local jetzt sum=0 n mb t tmp; jetzt=$(date +%s); tmp=$(mktemp)
  while read -r n mb t; do
    [ -n "$n" ] || continue
    if systemctl --user is-active --quiet "rcpark-$n" 2>/dev/null || [ $((jetzt - ${t:-0})) -lt 120 ]; then echo "$n $mb $t" >> "$tmp"; [ "$n" != "$NAME" ] && sum=$((sum + mb)); fi
  done < <(cat "$BUCH" 2>/dev/null)
  USED=$(${JOB_NVSMI:-nvidia-smi} --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -dc 0-9); USED=${USED:-0}
  local basis=$sum; [ "$USED" -gt "$basis" ] && basis=$USED
  if [ $((basis + BUDGET)) -gt "$LIMIT" ]; then GRUND="VRAM-Buchung: gebucht ${sum} MiB / gemessen ${USED} MiB + Job ${BUDGET} MiB > Grenze ${LIMIT} MiB"; mv "$tmp" "$BUCH"; flock -u 9; return 1; fi
  grep -v "^$NAME " "$tmp" > "$BUCH" 2>/dev/null || : > "$BUCH"; echo "$NAME $BUDGET $jetzt" >> "$BUCH"; rm -f "$tmp"; flock -u 9; return 0
}
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
      buchen || true
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
# RAM-BUCHUNG (18.11.2026, Kaufhaus gk2d: Fusion + Druck-Job gleichzeitig -> OOM-Kill; je Job MemoryHigh 11G, Rechner 15 GB): JOB_RAM_MB=<MiB> (Standard 2000)
# wird unter flock in $RBUCH gebucht; Start erst, wenn Summe der Buchungen laufender Jobs + eigene <= JOB_RAM_LIMIT_MB (Standard 85 % MemTotal). MemoryHigh = max(Buchung, 2G) nur bei gesetztem JOB_RAM_MB
# (JOB_MEMORY_HIGH setzt es weiter von Hand). Grosse Jobs (Fusion, Mapper, Kette) mit JOB_RAM_MB=11000 starten. JOB_OHNE_RAM_SPERRE=1 = ohne Warten.
RBUCH=/media/oem/scan/rc-park_daten/.ram_buchung; RAM_MB=${JOB_RAM_MB:-2000}; RAM_LIMIT=${JOB_RAM_LIMIT_MB:-$(awk '/^MemTotal/ {printf "%d", $2 * 0.85 / 1024}' /proc/meminfo)}
ram_buchen() {
  exec 8>>"$RBUCH.lock"; flock 8
  local jetzt sum=0 n mb t tmp; jetzt=$(date +%s); tmp=$(mktemp)
  while read -r n mb t; do
    [ -n "$n" ] || continue
    if systemctl --user is-active --quiet "rcpark-$n" 2>/dev/null || [ $((jetzt - ${t:-0})) -lt 120 ]; then echo "$n $mb $t" >> "$tmp"; [ "$n" != "$NAME" ] && sum=$((sum + mb)); fi
  done < <(cat "$RBUCH" 2>/dev/null)
  if [ $((sum + RAM_MB)) -gt "$RAM_LIMIT" ]; then RGRUND="RAM-Buchung: gebucht ${sum} MiB + Job ${RAM_MB} MiB > Grenze ${RAM_LIMIT} MiB ($(cut -d' ' -f1,2 "$tmp" | tr '\n' ' '))"; mv "$tmp" "$RBUCH"; flock -u 8; return 1; fi
  grep -v "^$NAME " "$tmp" > "$RBUCH" 2>/dev/null || : > "$RBUCH"; echo "$NAME $RAM_MB $jetzt" >> "$RBUCH"; rm -f "$tmp"; flock -u 8; return 0
}
if [ "${JOB_OHNE_RAM_SPERRE:-0}" != "1" ]; then
  T0=$(date +%s); LAST=$T0
  until ram_buchen; do
    NOW=$(date +%s); if [ "$LAST" = "$T0" ] || [ $((NOW-LAST)) -ge 600 ]; then echo "$(date +%T) $RGRUND, warte (seit $((NOW-T0)) s)"; LAST=$NOW; fi; sleep 60
  done
else echo "$NAME $RAM_MB $(date +%s)" >> "$RBUCH"; fi
[ -z "${JOB_MEMORY_HIGH:-}" ] && [ -n "${JOB_RAM_MB:-}" ] && JOB_MEMORY_HIGH="$(( RAM_MB > 2048 ? RAM_MB : 2048 ))M"   # ohne JOB_RAM_MB bleibt die alte Grenze 11G
systemctl --user reset-failed "rcpark-$NAME" 2>/dev/null || true
CMD=$(printf '%q ' "$@")
# 15.11.2026 (Recherche Durchsatz + Messung: SIFT 14 min statt < 1 min, weil CPU-Ausrichtungen alle Kerne belegten): GPU-Jobs bekommen CPU-Vorrang
# (CPUWeight 1000, alle Kerne); reine CPU-Jobs (JOB_GPU_MB=0) laufen mit CPUWeight 20 auf den 12 langsamen Kernen 16-27 (JOB_CPU=alle hebt das auf).
if [ "${BUDGET:-0}" -gt 0 ] 2>/dev/null || [ "${JOB_CPU:-}" = "alle" ]; then CPUW=1000; PIN=""; else CPUW=20; PIN="taskset -c ${JOB_CPU_KERNE:-16-27} "; fi
systemd-run --user --unit "rcpark-$NAME" --collect -p MemoryHigh="${JOB_MEMORY_HIGH:-11G}" -p CPUWeight="$CPUW" --setenv=RCPARK_JOB="$NAME" --setenv=RCPARK_GPU_MB="${BUDGET:-0}" -p WorkingDirectory="$(pwd)" \
  /bin/bash -c "$PIN$CMD > '$LOG' 2>&1; rc=\$?; echo \"JOB_ENDE rc=\$rc\" >> '$LOG'; [ \"\$(cut -d' ' -f1 '$LOCK' 2>/dev/null)\" = '$NAME' ] && rm -f '$LOCK'; ( flock 9; sed -i '/^$NAME /d' '$BUCH' 2>/dev/null ) 9>>'$BUCH.lock'; ( flock 8; sed -i '/^$NAME /d' '$RBUCH' 2>/dev/null ) 8>>'$RBUCH.lock'; [ \$rc -ne 0 ] && echo \"\$(date +%FT%T) $NAME rc=\$rc log=$LOG | \$(grep -v JOB_ENDE '$LOG' | tail -2 | tr '\\n' ' ' | cut -c1-300)\" >> /media/oem/scan/rc-park_daten/job_fehler.log; exit \$rc"
if [ "${RCPARK_OHNE_GPU_WACHE:-0}" != "1" ]; then                    # GPU-Wache (Lehre 14.11.: CPU-Werkzeug lief unbemerkt auf 18 Kernen, GPU 0 %)
  systemd-run --user --unit "rcpark-$NAME-gpuwache" --collect -p WorkingDirectory="$(pwd)" /bin/bash "$(cd "$(dirname "$0")" && pwd)/gpu_wache.sh" "$NAME" "$LOG" >/dev/null 2>&1 || true
fi
echo "gestartet: rcpark-$NAME -> $LOG"
