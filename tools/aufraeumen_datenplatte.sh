#!/bin/bash
# aufraeumen_datenplatte.sh - gibt Platz auf /media/oem/scan frei, OHNE Ergebnisse zu loeschen (Stand 2026-11-03, Platte 99 % voll).
# Loescht NUR regenerierbare Zwischenprodukte der dichten Rechnung (entzerrte Bilder + Tiefen-/Normalenkarten) in den FERTIGEN Laeufen
# boden, d1, d1_cv, d1_cv2 sowie die ueberfluessige Umgebung venv-o3d (Open3D liegt in venv-mesh). Ergebnisse (fused.ply, dicht_modell.npy,
# dicht_farben.npy, sparse/, bilder/) bleiben. sued_f8y3 wird NIE angefasst (laeuft).
#   tools/aufraeumen_datenplatte.sh          # nur anzeigen, was weg koennte (Trockenlauf)
#   tools/aufraeumen_datenplatte.sh --ja     # wirklich loeschen
set -u; export LC_ALL=C
VS=/media/oem/scan/rc-park_daten/martinstor/video_sfm
ZIELE=()
for lauf in boden d1 d1_cv d1_cv2; do
  for sub in images stereo; do ZIELE+=("$VS/$lauf/dicht/$sub"); done
done
ZIELE+=("/media/oem/scan/venv-o3d")

# Schutz: laufende dichte Rechnung auf diesen Ordnern -> abbrechen
if pgrep -f "video_dicht.py|patch_match|sued_dicht" >/dev/null 2>&1; then
  echo "HINWEIS: es laeuft eine dichte Rechnung; geloescht wird nur in boden/d1/d1_cv/d1_cv2 (nie sued_f8y3)."
fi

echo "Vorher:"; df -h /media/oem/scan | tail -1
SUMME=0
for z in "${ZIELE[@]}"; do
  [ -e "$z" ] || { echo "  (fehlt)  $z"; continue; }
  # Pfad-Sicherheit: muss unter einem der erlaubten Wurzeln liegen und tief genug sein
  case "$z" in
    $VS/boden/dicht/*|$VS/d1/dicht/*|$VS/d1_cv/dicht/*|$VS/d1_cv2/dicht/*|/media/oem/scan/venv-o3d) ;;
    *) echo "ABBRUCH: unerlaubter Pfad $z"; exit 1;;
  esac
  KB=$(du -sk "$z" 2>/dev/null | cut -f1); SUMME=$((SUMME + KB))
  printf "  %8.1f GB  %s\n" "$(echo "$KB/1048576" | bc -l)" "$z"
done
printf "Summe: %.1f GB\n" "$(echo "$SUMME/1048576" | bc -l)"

if [ "${1:-}" != "--ja" ]; then echo "Trockenlauf - nichts geloescht. Mit --ja ausfuehren."; exit 0; fi

# Ergebnisse muessen vorhanden sein, bevor wir die Zwischenprodukte des Laufs loeschen
for lauf in boden d1 d1_cv d1_cv2; do
  if [ ! -s "$VS/$lauf/dicht/fused.ply" ] || [ ! -s "$VS/$lauf/dicht_modell.npy" ]; then
    echo "UEBERSPRUNGEN $lauf: fused.ply/dicht_modell.npy fehlt - Zwischenprodukte bleiben"
    for sub in images stereo; do ZIELE=("${ZIELE[@]/$VS\/$lauf\/dicht\/$sub}"); done
  fi
done
for z in "${ZIELE[@]}"; do [ -n "$z" ] && [ -e "$z" ] && rm -rf -- "$z" && echo "geloescht $z"; done
echo "Nachher:"; df -h /media/oem/scan | tail -1
