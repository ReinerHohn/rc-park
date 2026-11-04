#!/bin/bash
# job_start.sh NAME LOGDATEI BEFEHL... - lange Jobs (Nullstart, SfM, Optimierer) als eigener systemd-Benutzerdienst starten.
# Grund (2026-11-03): Claude Code beendet seine Hintergrund-Shells bei Speicherknappheit, wenn die Sitzung untaetig ist -> Nullstart mitten in der
# Registrierung abgeschossen. Ein systemd-Dienst haengt nicht an der Sitzung; MemoryHigh bremst bei Knappheit (Auslagerung) statt zu toeten.
# Status:  systemctl --user status rcpark-NAME   |  Abbruch: systemctl --user stop rcpark-NAME  |  Ende: Zeile "JOB_ENDE rc=<n>" im Log
set -e
NAME="$1"; LOG="$2"; shift 2
[ -n "$NAME" ] && [ -n "$LOG" ] && [ $# -gt 0 ] || { echo "Aufruf: job_start.sh NAME LOGDATEI BEFEHL..."; exit 2; }
if systemctl --user is-active --quiet "rcpark-$NAME"; then echo "rcpark-$NAME laeuft schon"; exit 1; fi
systemctl --user reset-failed "rcpark-$NAME" 2>/dev/null || true
CMD=$(printf '%q ' "$@")
systemd-run --user --unit "rcpark-$NAME" --collect -p MemoryHigh="${JOB_MEMORY_HIGH:-11G}" -p WorkingDirectory="$(pwd)" \
  /bin/bash -c "$CMD > '$LOG' 2>&1; rc=\$?; echo \"JOB_ENDE rc=\$rc\" >> '$LOG'; exit \$rc"
echo "gestartet: rcpark-$NAME -> $LOG"
