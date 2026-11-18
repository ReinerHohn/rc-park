#!/bin/bash
# backup_rcdaten.sh ZIEL [--los] [--pruefen] [--spiegeln] [--nur rcdaten|daten|repo]       (18.11.2026, Nutzerauftrag "Backup vorbereiten")
# Sichert ALLES, was nach dem Umzug nur noch einmal existiert, auf eine ZWEITE Platte:
#   rcdaten = /media/oem/rcdaten (2-TB-SSD: alle Auslagerungen, ca. 450 GB)   daten = /media/oem/scan/rc-park_daten (Arbeitsdaten + _git_objekte = die Git-Objekte des Repos, 19 GB)
#   repo    = /home/oem/git/rc-park (Arbeitsbaum + .git; die Objekte selbst liegen unter daten/_git_objekte)
# Standard = TROCKENLAUF (zeigt nur, was kopiert wuerde). --los kopiert (rsync -aH, Symlinks bleiben Symlinks), --pruefen vergleicht danach per Pruefsumme (rsync -c, muss leer sein).
# Es wird NIE geloescht, ausser mit --spiegeln (dann --delete-after: Ziel = exaktes Abbild; ein versehentlich geloeschtes Quellstueck verschwindet dann auch im Backup - erst benutzen, wenn ein zweites Backup besteht).
# Schutz: ZIEL muss existieren, auf einer ANDEREN Platte liegen als jede Quelle, und die Markerdatei ZIEL/.rcpark_backup_ziel enthalten (einmalig anlegen: touch ZIEL/.rcpark_backup_ziel);
#   so landet kein Backup versehentlich auf der falschen Platte (z. B. der Familienvideo-Toshiba, die voll ist und nicht angefasst wird).
# Nicht gesichert (fluechtig): lost+found, tmp_alt_*, Sperr-/Buchungsdateien, *.lock, __pycache__. Aufruf Beispiel: tools/backup_rcdaten.sh /media/oem/BACKUP/rcpark --los --pruefen
set -u
Z="${1:-}"; shift || true; LOS=0; PRUEF=0; SPIEG=0; NUR=""
while [ $# -gt 0 ]; do case "$1" in --los) LOS=1;; --pruefen) PRUEF=1;; --spiegeln) SPIEG=1;; --nur) NUR="${2:-}"; shift;; *) echo "unbekannte Option $1"; exit 2;; esac; shift; done
[ -n "$Z" ] || { sed -n 2,3p "$0" | cut -c1-200; exit 2; }; Z="${Z%/}"
[ -d "$Z" ] || { echo "ZIEL $Z fehlt (Platte nicht eingehaengt?)"; exit 2; }
[ -f "$Z/.rcpark_backup_ziel" ] || { echo "Markerdatei $Z/.rcpark_backup_ziel fehlt - bewusst anlegen: touch '$Z/.rcpark_backup_ziel' (Schutz vor falscher Platte)"; exit 2; }
declare -A Q=( [rcdaten]="/media/oem/rcdaten" [daten]="/media/oem/scan/rc-park_daten" [repo]="/home/oem/git/rc-park" )
ZD=$(stat -c %d "$Z")
for k in rcdaten daten repo; do [ -n "$NUR" ] && [ "$NUR" != "$k" ] && continue
  [ "$(stat -c %d "${Q[$k]}")" = "$ZD" ] && { echo "ABBRUCH: ZIEL liegt auf derselben Platte wie ${Q[$k]} - das ist kein Backup"; exit 2; }; done
EX=(--exclude=lost+found --exclude='tmp_alt_*' --exclude='.gpu_buchung*' --exclude='.ram_buchung*' --exclude='*.lock' --exclude=__pycache__ --exclude='gpu_slots')
OPT=(-aH --info=stats1,progress2 "${EX[@]}"); [ $SPIEG = 1 ] && OPT+=(--delete-after); [ $LOS = 0 ] && OPT+=(--dry-run --itemize-changes)
LOG="${BACKUP_LOG:-/media/oem/scan/rc-park_daten/backup_$(date +%Y%m%d_%H%M%S).log}"; echo "Backup -> $Z  (los=$LOS pruefen=$PRUEF spiegeln=$SPIEG)  Log $LOG"
RC=0
for k in rcdaten daten repo; do [ -n "$NUR" ] && [ "$NUR" != "$k" ] && continue; mkdir -p "$Z/$k"
  echo "== $k: ${Q[$k]} -> $Z/$k"; rsync "${OPT[@]}" "${Q[$k]}/" "$Z/$k/" 2>&1 | tee -a "$LOG" | tail -n 6 | cut -c1-200; r=${PIPESTATUS[0]}; [ $r -ne 0 ] && [ $r -ne 24 ] && { echo "rsync rc $r bei $k"; RC=4; }     # 24 = Quelldatei waehrend des Laufs verschwunden (laufende Jobs): kein Fehler
  if [ $LOS = 1 ] && [ $PRUEF = 1 ] && [ $RC = 0 ]; then D=$(rsync -aHc --dry-run --itemize-changes "${EX[@]}" "${Q[$k]}/" "$Z/$k/" 2>&1 | grep -vE '^\.d|^cd|^\.f\.\.t\.{6} |^created directory' | head -10)
    if [ -n "$D" ]; then echo "PRUEFSUMMEN UNGLEICH ($k):"; echo "$D" | cut -c1-160; RC=5; else echo "Pruefsummen gleich ($k)"; fi; fi
done
[ $LOS = 1 ] && [ $RC = 0 ] && date +%F_%T > "$Z/.rcpark_backup_stand"; exit $RC
