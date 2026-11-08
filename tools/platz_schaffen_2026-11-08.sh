#!/bin/bash
# platz_schaffen_2026-11-08.sh - NUR vom Nutzer ausfuehren:  ! bash tools/platz_schaffen_2026-11-08.sh --ja     (ohne --ja: Trockenlauf, loescht nichts)
# Loescht NUR die regenerierbaren Zwischenordner p1/ und p2/ (Pass-1/Pass-2-Renders und Overlays je Foto) in FERTIGEN Foto-Diff-Laeufen vom 7./8.11.
# ergebnis.json, konfig.json, gueltigkeit.json, lauf.log bleiben (Zahlen stehen ausserdem in modelle/NICHTS_GEBRACHT.md BS56-BS88).
# AUSGENOMMEN: bog (Bogenreihe, Overlays werden noch gebraucht), druck (Druckkandidaten), sg, laufende Jobs (nur Ordner mit Datei 'fertig' in beiden global_* werden angefasst).
S=/media/oem/scan/rc-park_null/diffpar; JA="$1"; L=""
for n in dachv loo fl wvar dicht7 dicht8 gh tg tg2 hyb glaett nahs cropv boolf lim fein ksr pgnn grob1; do
  d=$S/$n; [ -d "$d" ] || continue
  ok=1; for g in $d/global_*; do [ -f "$g/fertig" ] || ok=0; done; [ $ok = 1 ] || continue
  for g in $d/global_*; do for u in p1 p2; do [ -d "$g/$u" ] && L="$L $g/$u"; done; done
done
echo "Frei vorher:"; df -h /media/oem/scan | tail -1; [ -n "$L" ] && du -ch $L 2>/dev/null | tail -1 || echo "nichts gefunden"
[ "$JA" = "--ja" ] || { echo "Trockenlauf - mit --ja wirklich loeschen"; exit 0; }
for p in $L; do rm -rf -- "$p"; done; sync; echo "Frei nachher:"; df -h /media/oem/scan | tail -1
