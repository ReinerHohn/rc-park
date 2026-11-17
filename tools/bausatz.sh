#!/bin/bash
# bausatz.sh <objekt> <masken (relief/a_putz.npz,relief/b_putz.npz)> [WAND_MM=2.4] [SPIEL_MM=0.3] - Bausatz fuer ZWEI Drucker in einem Lauf (17.11.2026, Nutzer):
#   grobe Teile (Koerper) auf dem Prusa MK4S mit 0,8-mm-Duese (250x210x220), feine Teile (Steinplatten) auf dem Bambu mit 0,4-mm-Duese (256).
# Ablauf: Generator mit dickerer Wand in EINE EIGENE Datei (das abgenommene STL bleibt unveraendert) -> druck_farbteile -> druck_teilung (+ Verbinder) -> druck_farben -> druck_zeit je Drucker.
# Ausgabe: modelle/stl/<objekt>_farbteile/ (Platten, koerper.stl), modelle/stl/<objekt>_teile/ (Koerperteile, Verbinder), je druckzeit*.json. Messwerte Turm: PIPELINE_FASSADEN.md.
set -e; cd "$(dirname "$0")/.."; O="$1"; MASKEN="$2"; WAND="${3:-2.4}"; SPIEL="${4:-0.3}"; [ -n "$O" ] && [ -n "$MASKEN" ] || { sed -n 2,5p "$0"; exit 2; }
P=/media/oem/scan/venv-seg/bin/python; OBJ="modelle/$O/objekt.json"; R=$($P -c "import json;print(json.load(open('$OBJ'))['stl'])"); GEN=$($P -c "import json;print(json.load(open('$OBJ'))['generator'])")
RR=$(readlink -f "$R"); Z="/media/oem/scan/rc-park_stl/${O}_wand${WAND/./}.stl"; python3 tools/platz_pruefen.py || exit 3
( flock -n 8 || { echo "ABBRUCH: fuer $O laeuft schon ein Bau"; exit 5; }
  cp "$RR" "/media/oem/scan/rc-park_stl/${O}_sicher.stl"; set +e; eval "WAND_MM=$WAND $GEN" > /dev/null 2>&1; RC=$?; set -e
  [ "$RC" = "0" ] && mv "$RR" "$Z"; mv "/media/oem/scan/rc-park_stl/${O}_sicher.stl" "$RR"; git checkout "modelle/$O/elemente.json" 2>/dev/null || true
  [ "$RC" = "0" ] || { echo "ABBRUCH: Generator rc $RC"; exit 4; } ) 8>"/tmp/rcpark_bau_$O.lock"
$P -W ignore -I tools/druck_farbteile.py "$O" --stl "$Z" --wand_mm "$WAND" --spiel_mm "$SPIEL" --masken "$MASKEN" | grep "platte_\|Koerper:\|begrenzt\|->"
$P -W ignore -I tools/druck_teilung.py "$O" --stl "modelle/stl/${O}_farbteile/koerper.stl" --bett_mm 222 --toleranz_mm "$SPIEL" | grep -a "^teil_\|Schnitte\|verbinder"
$P -W ignore -I tools/druck_farben.py "$O" --eintragen | tail -1
echo "== Koerper: Prusa MK4S, Duese 0,8 mm, Schicht 0,4 mm"; python3 tools/druck_zeit.py "modelle/stl/${O}_teile" --duese 0.8 --schicht 0.4 --bett 250x210x220 | tail -12
echo "== Steinplatten: Bambu, Duese 0,4 mm, Schicht 0,16 mm"; python3 tools/druck_zeit.py "modelle/stl/${O}_farbteile" --schicht 0.16 --bett 256 | tail -9
