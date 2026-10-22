#!/usr/bin/env bash
# zusammenbau.sh — oeffnet das interaktive 3D-Zusammenbau-Tool im Browser.
#
# Das Tool (eigene Farbe je Rippe + Rippen-ID-Suche + drehbar) wird von
# tools/terrain_eggcrate.py bei jedem Lauf als _zusammenbau.html / _assembled.html
# in den --out-Ordner geschrieben. Dieses Script oeffnet es nur.
#
# Nutzung:
#   ./zusammenbau.sh                      # Default: modelle/hoellental_geruest_a3
#   ./zusammenbau.sh <modell-ordner>      # anderer Satz
#   ./zusammenbau.sh <ordner> assembled   # statt Zusammenbau die reine 3D-Ansicht
set -euo pipefail

DIR="${1:-modelle/hoellental_geruest_a3}"
WHICH="${2:-zusammenbau}"            # zusammenbau | assembled

case "$WHICH" in
  assembled) PREF=(_assembled.html _zusammenbau.html) ;;
  *)         PREF=(_zusammenbau.html _assembled.html) ;;
esac

HTML=""
for f in "${PREF[@]}"; do
  if [ -f "$DIR/$f" ]; then HTML="$DIR/$f"; break; fi
done

if [ -z "$HTML" ]; then
  echo "!! Keine Zusammenbau-HTML in '$DIR' gefunden."
  echo "   Erst das Geruest erzeugen, z.B.:"
  echo "   python3 tools/terrain_eggcrate.py ... --out $DIR   (schreibt _zusammenbau.html)"
  exit 1
fi

ABS="$(cd "$(dirname "$HTML")" && pwd)/$(basename "$HTML")"
echo "Oeffne: $ABS"

# robuster Opener-Fallback
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$ABS" >/dev/null 2>&1 &
elif command -v firefox  >/dev/null 2>&1; then
  firefox "$ABS" >/dev/null 2>&1 &
elif command -v sensible-browser >/dev/null 2>&1; then
  sensible-browser "$ABS" >/dev/null 2>&1 &
else
  echo "Kein Browser-Opener gefunden. Datei manuell oeffnen:"
  echo "  file://$ABS"
fi
