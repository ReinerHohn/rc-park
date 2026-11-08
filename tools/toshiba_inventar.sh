#!/bin/bash
# toshiba_inventar.sh [MOUNT] - schreibt modelle/TOSHIBA_INVENTAR_roh.txt (Groessen, nur Lesen). NTFS/HDD langsam: im Hintergrund starten.
M="${1:-/media/oem/TOSHIBA EXT}"; O="$(dirname "$0")/../modelle/TOSHIBA_INVENTAR_roh.txt"
{ echo "## Stand $(date '+%Y-%m-%d %H:%M')"; df -h "$M" | tail -1
  echo "## rc-park_auslagern (Tiefe 3)"; du -h --max-depth=3 "$M/rc-park_auslagern" 2>/dev/null | sort -k2
  echo "## uebrige Ordner oberste Ebene (nur Groesse)"; for d in "$M"/*/; do case "$d" in */rc-park_auslagern/) ;; *) du -sh "$d" 2>/dev/null;; esac; done
  echo "## Dateien oberste Ebene"; find "$M" -maxdepth 1 -type f -printf '%s\t%f\n' 2>/dev/null; } > "$O"
echo fertig >> "$O"
