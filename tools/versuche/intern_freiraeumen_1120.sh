#!/bin/bash
# intern_freiraeumen_1120.sh - interne NVMe freiraeumen (Nutzer 20.11.2026 15:10: "alles, was wir nicht mehr brauchen, auf die SSD auslagern, intern nur was gebraucht wird").
# Je Paar QUELLE ZIEL: rsync -aH -> Pruefsummenvergleich (rsync -c Trockenlauf, ohne Symlinks, muss leer sein) -> Verknuepfungs-Pruefung
# (nichts unter scan/Repo/rcdaten zeigt mehr in QUELLE) -> ERST DANN QUELLE loeschen. Bei Abweichung: nichts geloescht, rc 1.
# Aufruf: intern_freiraeumen_1120.sh [--ohne_linksuche_rcdaten] QUELLE ZIEL [QUELLE ZIEL ...]
# Lauf nur ueber tools/job_start.sh (ionice idle, damit die Kette auf derselben USB-Platte nicht gebremst wird).
set -u
LINKWURZELN="/media/oem/scan /home/oem/git/rc-park /media/oem/rcdaten"
[ "${1:-}" = "--ohne_linksuche_rcdaten" ] && { LINKWURZELN="${LINKWURZELN_TEST:-/media/oem/scan /home/oem/git/rc-park}"; shift; }
rc=0
while [ $# -ge 2 ]; do
  Q="${1%/}"; Z="${2%/}"; shift 2
  echo "== $(date +%T) $Q -> $Z"
  [ -d "$Q" ] || { echo "FEHLT Quelle $Q"; rc=1; continue; }
  [ -L "$Q" ] && { echo "Quelle ist schon Verknuepfung - uebersprungen"; continue; }
  mkdir -p "$Z" || { rc=1; continue; }
  vor=$(du -sm "$Q" | cut -f1)
  ionice -c3 nice rsync -aH ${RSYNC_EXTRA:-} "$Q/" "$Z/" || { echo "FEHLER rsync $Q"; rc=1; continue; }
  diff_=$(ionice -c3 nice rsync -rnc --no-links --itemize-changes "$Q/" "$Z/" | grep -v '^\.d' | grep -v '^skipping non-regular' | head -20)
  if [ -n "$diff_" ]; then echo "ABWEICHUNG - nichts geloescht:"; echo "$diff_"; rc=1; continue; fi
  links=$(for w in $LINKWURZELN; do find "$w" -xdev -type l -lname "$Q/*" 2>/dev/null; done | head -5)
  if [ -n "$links" ]; then echo "VERKNUEPFUNGEN zeigen noch in die Quelle - nichts geloescht:"; echo "$links"; rc=1; continue; fi
  rm -rf "$Q" && echo "OK $(date +%T) $Q entfernt ($vor MB frei), Kopie geprueft in $Z" || { echo "FEHLER beim Entfernen $Q"; rc=1; }
done
df -h / /media/oem/scan /media/oem/Volume /media/oem/rcdaten 2>/dev/null | cut -c1-80
exit $rc
