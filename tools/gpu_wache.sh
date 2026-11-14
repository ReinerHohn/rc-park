#!/bin/bash
# gpu_wache.sh NAME LOG - waehrend Job rcpark-NAME laeuft: alle 60 s CPU-Last (cgroup cpu.stat) und GPU-Nutzung (nvidia-smi compute-apps) pruefen.
# > 4 Kerne im Mittel UND kein Prozess des Jobs auf der GPU (2 Messungen hintereinander) -> WARNUNG ins Job-Log + /media/oem/scan/rc-park_daten/gpu_warnungen.log.
# Lehre 2026-11-14 (Nutzer: "warum macht die GPU nichts?"): video_suchen.py lief mit OpenCV-SIFT auf 18 Kernen, GPU 0 % - zweimal am selben Tag
# unbemerkt. Die Wache meldet so etwas nach 2 min, statt dass der Nutzer es sieht. Gestartet automatisch von tools/job_start.sh (RCPARK_OHNE_GPU_WACHE=1 schaltet ab).
NAME="$1"; LOG="$2"; U="rcpark-$NAME"; WL=/media/oem/scan/rc-park_daten/gpu_warnungen.log
sleep 20
CG=$(systemctl --user show -p ControlGroup --value "$U" 2>/dev/null); D="/sys/fs/cgroup$CG"
[ -n "$CG" ] && [ -f "$D/cpu.stat" ] || exit 0
alt=$(awk '/usage_usec/ {print $2}' "$D/cpu.stat"); schlecht=0; gemeldet=0
while systemctl --user is-active --quiet "$U"; do
  sleep 60
  [ -f "$D/cpu.stat" ] || break
  neu=$(awk '/usage_usec/ {print $2}' "$D/cpu.stat"); kerne=$(( (neu - alt) / 60000000 )); alt=$neu
  gpu=0
  for p in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do grep -qx "$p" "$D/cgroup.procs" 2>/dev/null && gpu=1; done
  if [ "$kerne" -gt 4 ] && [ "$gpu" = 0 ]; then schlecht=$((schlecht + 1)); else schlecht=0; fi
  if [ "$schlecht" -ge 2 ] && [ "$gemeldet" = 0 ]; then
    M="$(date +%FT%T) WARNUNG GPU-WACHE: $U rechnet auf ${kerne} CPU-Kernen ohne GPU - Werkzeug auf GPU umstellen (Nutzerregel), Job pruefen"
    echo "$M" >> "$LOG"; echo "$M" >> "$WL"; gemeldet=1
  fi
done
