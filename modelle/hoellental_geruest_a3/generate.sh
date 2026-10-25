#!/usr/bin/env bash
# Hoellental-Hirschsprung Geruest — ERZEUGEN + PACKEN in einem Rutsch.
# Alle Fixes sind im Generator: robuste Rippen (Auto-Nudge/Hoehen-Naht), Tunnel MIT Dach
# (massstaeblicher Lichtraum), Kanten-Lineale zum Aufkleben, snap-edges.
#
# Nutzung:   ./modelle/hoellental_geruest_a3/generate.sh [OUT-ORDNER]
#            (Default-OUT = /tmp/hoellental_cutset ; "." waere der Modell-Ordner selbst)
set -euo pipefail

# Repo-Wurzel finden (Skript laeuft von ueberall)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT="${1:-/tmp/hoellental_cutset}"
mkdir -p "$OUT"

echo "== 1/3  GENERIEREN -> $OUT =="
python3 tools/terrain_eggcrate.py \
  --dem daten/hoellental/dgm025_full.npy \
  --mm 0.78125 --nscale 3.125 --zoom 1 \
  --r0 470 --r1 640 --c0 3310 --c1 3570 \
  --vscale 0.85 --nx 12 --ny 8 --thickness 3 --base 12 --rib-depth 0 \
  --trans-frac 1.0 --smooth 0.6 --min-gap 7 \
  --tunnel --track daten/hoellental/hoellental_track_50.npy \
  --tunnel-w-m 4.0 --tunnel-h-m 5.5 --roof-min 2.0 \
  --split-len 0 --edge-min-len 18 --fit -0.50 --gcode \
  --out "$OUT"
# --split-len 0 = KEINE Fingerzinken-Teilung (Rippen <=203mm passen aufs 410-Bett) -> weniger
#   Teile, keine duennen Zinken-Zaehne. --edge-min-len 18 = keine winzigen Fuzzel-Lineale.

echo "== 2/3  RIPPEN auf A3-Bretter packen =="
python3 tools/laser_pack.py "$OUT" --sheet 410x297 --passes 2 --nest --margin 4 \
  --exclude 'K*' --out "$OUT/bretter"

echo "== 3/3  KANTEN-LINEALE (K*) separat packen =="
# Blatt bewusst 400 (nicht 410): der Nest-Rastert nur das größte Polygon -> dünne gekrümmte
# Lineale können am 410-Rand minimal überlaufen. 400 lässt Sicherheits-Reserve zum S9-Fenster.
python3 tools/laser_pack.py "$OUT" --sheet 400x290 --passes 2 --nest --margin 3 \
  --only 'K*' --out "$OUT/bretter_lineale"
# WICHTIG vor dem Schneiden: echten G-Code-Bereich prüfen (muss <= 410x400 sein):
#   grep -oE 'X-?[0-9.]+' brett1.gcode | ... | min/max

echo ""
echo "FERTIG."
echo "  Rippen-Bretter : $OUT/bretter/"
echo "  Lineal-Bretter : $OUT/bretter_lineale/"
echo "  3D-Vorschau    : $OUT/_zusammenbau.html   (drehbar: Rippen + Relief + Tunnel)"
echo "  Schneiden      : python3 tools/grbl_send.py $OUT/bretter/brett1.gcode   (pro Brett)"
