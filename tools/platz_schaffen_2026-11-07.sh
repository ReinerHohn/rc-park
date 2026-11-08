#!/bin/bash
# platz_schaffen_2026-11-07.sh - NUR vom Nutzer ausfuehren:  ! bash tools/platz_schaffen_2026-11-07.sh --ja     (ohne --ja: Trockenlauf, loescht nichts)
# Loescht NUR die regenerierbaren Zwischenordner p1/ und p2/ (Pass-1/Pass-2-Renders je Foto) in Foto-Diff-Ausgaben. ergebnis.json, konfig.json, gueltigkeit.json, lauf.log
# und die Mess-Tabellen bleiben erhalten (die Zahlen stehen ausserdem in modelle/NICHTS_GEBRACHT.md). Laufende Jobs (diffpar/fein) und die aktuellen Basisdateien bleiben unberuehrt.
S=/media/oem/scan/rc-park_null; JA="$1"; L=""
for d in $S/diffpar/bench/* $S/diffpar/genteile/* $S/diffpar/genalle/* $S/diffpar/kr_v1/* $S/fenster_diff/w* $S/wettbewerb_kh2[0-9]* $S/wettbewerb_kh9g $S/wettbewerb_kh20 $S/mincut/diff_*; do
  for u in p1 p2; do [ -d "$d/$u" ] && L="$L $d/$u"; done
done
if systemctl --user list-units 'rcpark-*' --no-legend | grep -q running; then echo "HINWEIS: es laufen rcpark-Jobs; diffpar/fein ist ausgenommen. Ordner anderer laufender Jobs bitte pruefen."; fi
echo "Frei vorher:"; df -h /media/oem/scan | tail -1; [ -n "$L" ] && du -ch $L 2>/dev/null | tail -1 || echo "nichts gefunden"
[ "$JA" = "--ja" ] || { echo "Trockenlauf - mit --ja wirklich loeschen"; exit 0; }
for p in $L; do rm -rf -- "$p"; done; sync; echo "Frei nachher:"; df -h /media/oem/scan | tail -1
