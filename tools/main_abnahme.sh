#!/bin/bash
# Abnahme auf main nach einem Kreis-Merge/Revert (10.11.): haelt den Merge-Lock der Kreis-Spuren, damit kein Spur-Merge
# auf halb geschriebene Erzeugnisse/masstabelle.json trifft (a021633 r4 scheiterte so), und committet die Erzeugnisse sofort.
# Aufruf: tools/job_start.sh abnahme_main LOG bash tools/main_abnahme.sh <objekt> "<Commit-Text>"
set -u
cd "$(dirname "$0")/.." || exit 1
OBJ="$1"; TXT="${2:-Abnahme main}"
LOCK=/media/oem/scan/rc-park_kreis/$OBJ/merge.lock
exec 9>"$LOCK"; flock 9
# CUDA-Speicher voll (fremde GPU-Jobs) ist ein Infrastrukturfehler, kein rotes Modell (10.11. 13:2x: Pruefstand-OOM -> faelschlich ROT):
# warten, bis >= 2,5 GB frei sind (hoechstens 10 min), und wiederholen - bis 6 Versuche, wie sh_tor im Kreis.
for V in 1 2 3 4 5 6; do
  OUT=$(bash tools/bauen_abnehmen.sh "$OBJ" 2>&1); RC=$?
  echo "$OUT" | grep -qE "out of memory|OutOfMemoryError|CUDA_ERROR_OUT_OF_MEMORY" || break
  echo "OOM in der Abnahme (Versuch $V/6) - warte auf freien GPU-Speicher"
  for i in $(seq 40); do sleep 15; F=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1); [ "${F:-0}" -ge 2500 ] && [ $i -ge 2 ] && break; done
done
echo "$OUT"
if [ $RC -eq 0 ] && echo "$OUT" | grep -q "alle Pruefungen bestanden"; then
  git add -u modelle/
  git commit -q -m "$TXT: alle Pruefungen bestanden

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01BMC5F7JqzthTsrTAV2gKLz" && git log --oneline -1
  echo "MAIN_ABNAHME GRUEN"
else
  echo "MAIN_ABNAHME ROT (rc $RC) - Erzeugnisse NICHT committet, Arbeitsbaum bleibt fuer Ansicht"
  exit 1
fi
