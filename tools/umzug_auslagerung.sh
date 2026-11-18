#!/bin/bash
# umzug_auslagerung.sh QUELLE ZIEL [--trocken | --nur_umbiegen]   (--nur_umbiegen: nichts kopieren, nur Verknuepfungen QUELLE -> ZIEL umbiegen - Schlussdurchgang nach allen Umzuegen)
#   QUELLE = Auslagerungsordner einer alten Platte (z. B. /media/oem/rcstick/rc-park_auslagern)
#   ZIEL   = neuer Ordner auf der 2-TB-SSD (z. B. /media/oem/rcdaten/auslagern_rcstick)
# 18.11.2026 (2-TB-SSD c5601887 'rcdaten', Nutzer-Plan: alles rc-park auf eine Platte). Ablauf:
#   1. rsync -aH QUELLE/ ZIEL/  (Symlinks bleiben Symlinks, NTFS -> ext4)
#   2. Pruefsummenvergleich: rsync -c Trockenlauf muss leer sein - sonst Abbruch, nichts umgebogen
#   3. alle Verknuepfungen unter /media/oem/scan, dem Repo und /media/oem/rcdaten, die in QUELLE zeigen, auf ZIEL umbiegen (Log mit alt -> neu)
#   QUELLE wird NICHT geloescht (erst nach Nutzer-Ja; private Platten!). Rueckweg: Log rueckwaerts lesen.
# Grenzen: laufende Jobs, die gerade in QUELLE schreiben, werden nicht erkannt - vorher pruefen (lsof +D QUELLE).
set -u
Q="${1%/}"; Z="${2%/}"; TROCKEN="${3:-}"
[ -d "$Q" ] && [ -n "$Z" ] || { sed -n 2,9p "$0"; exit 2; }
LOG=/media/oem/rcdaten/umzug_$(basename "$(dirname "$Q")" | tr ' ' '_')_$(date +%d%H%M).log
mkdir -p "$Z"; echo "== $Q -> $Z  ($(du -sh "$Q" 2>/dev/null | cut -f1))" | tee -a "$LOG"
if [ -n "$(lsof +D "$Q" 2>/dev/null | head -2 | tail -1)" ]; then echo "ABBRUCH: Dateien in $Q sind geoeffnet:"; lsof +D "$Q" 2>/dev/null | head -5; exit 3; fi
if [ "$TROCKEN" != "--nur_umbiegen" ]; then
# --no-links beim Nachkopieren nicht: Symlinks muessen mit. Aber vorhandene, schon umgebogene Symlinks im Ziel NICHT zuruecksetzen (--ignore-existing nur fuer Links geht nicht -> Links danach wieder umbiegen, s. Schleife + Schlussdurchgang --nur_umbiegen)
rsync -aH --info=stats1 "$Q/" "$Z/" 2>&1 | tail -3 | tee -a "$LOG"; RC=${PIPESTATUS[0]}
[ "$RC" = "0" ] || { echo "ABBRUCH: rsync rc $RC" | tee -a "$LOG"; exit 4; }
# Pruefung NUR der Dateiinhalte: Ordnerdaten (.d..t) und Symlink-Ziele (cL/.L, von Nachbar-Umzuegen bewusst umgebogen) zaehlen nicht (18.11.2026: Stick-Umzug brach daran ab)
# .f..t...... = Inhalt per Pruefsumme gleich, nur Zeitstempel (z.B. gpu_slots/mutex.lock von laufenden GPU-Jobs; 20757-Umzug brach 18.11. 17:40 daran ab)
D=$(rsync -aHc --dry-run --itemize-changes "$Q/" "$Z/" 2>&1 | grep -vE '^\.d|^cL|^\.L|^cd|^created directory|^\.f\.\.t\.{6} ' | head -20)
[ -z "$D" ] || { echo "ABBRUCH: Pruefsummen weichen ab:" | tee -a "$LOG"; echo "$D" | tee -a "$LOG"; exit 5; }
echo "Pruefsummen gleich" | tee -a "$LOG"
fi
N=0
while IFS= read -r -d '' L; do
  T=$(readlink "$L"); case "$T" in "$Q"/*|"$Q") ;; *) continue ;; esac
  NEU="$Z${T#$Q}"
  if [ "$TROCKEN" = "--trocken" ]; then echo "TROCKEN $L: $T -> $NEU"; else ln -sfn "$NEU" "$L" && echo "$L	$T	$NEU" >> "$LOG"; fi; N=$((N+1))
done < <(find /media/oem/scan /home/oem/git/rc-park /media/oem/rcdaten -xdev -type l -print0 2>/dev/null)
echo "$N Verknuepfungen umgebogen (Log $LOG); QUELLE bleibt bis Nutzer-Ja" | tee -a "$LOG"
