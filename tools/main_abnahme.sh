#!/bin/bash
# Abnahme auf main nach einem Kreis-Merge/Revert (10.11.): haelt den Merge-Lock der Kreis-Spuren, damit kein Spur-Merge
# auf halb geschriebene Erzeugnisse/masstabelle.json trifft (a021633 r4 scheiterte so), und committet die Erzeugnisse sofort.
# Aufruf: tools/job_start.sh abnahme_main LOG bash tools/main_abnahme.sh <objekt> "<Commit-Text>"
set -u
cd "$(dirname "$0")/.." || exit 1
OBJ="$1"; TXT="${2:-Abnahme main}"
LOCK=/media/oem/scan/rc-park_kreis/$OBJ/merge.lock
exec 9>"$LOCK"; flock 9
OUT=$(bash tools/bauen_abnehmen.sh "$OBJ" 2>&1); RC=$?
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
