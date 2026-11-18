#!/bin/bash
# bausatz.sh <objekt> <masken (relief/a_putz.npz,relief/b_putz.npz)> [WAND_MM=2.4] [SPIEL_MM=0.3] [BAUART=tasche|einsatz] [INNEN_MM=1.0] - Bausatz fuer ZWEI Drucker in einem Lauf (17.11.2026, Nutzer):
#   grobe Teile (Koerper) auf dem Prusa MK4S mit 0,8-mm-Duese (250x210x220), feine Teile (Steinplatten) auf dem Bambu mit 0,4-mm-Duese (256).
# Ablauf: Generator mit der gewuenschten Wand in EINE EIGENE Datei (das abgenommene STL bleibt unveraendert) -> [einsatz: druck_hohl] -> druck_farbteile -> druck_rippen (RIPPEN=0 aus) -> druck_teilung (+ Verbinder) -> druck_farben -> druck_zeit je Drucker.
# BAUART tasche  (Standard, Wand >= 2,2 mm): Steinplatten liegen in Taschen der Wand (mit --ring: Innenschicht um die Gebaeudeecken, sonst bleiben dort Hoehenschnitte offen).
# BAUART einsatz (duenne Wand, z. B. 1.0):  massive Bereiche werden ausgehoehlt (druck_hohl.py), die Steinplatte ist die ganze Wand, dahinter eine Innenschicht INNEN_MM im Hohlraum.
#   Beispiel Turm: tools/bausatz.sh schwab_v3 relief/nord_putz.npz,relief/sued_putz.npz,relief/west_putz.npz 1.0 0.25 einsatz
# Das Wandmodell rc-park_stl/<objekt>_wand<NN>.stl wird wiederverwendet, wenn es juenger ist als das abgenommene STL (neu bauen: BAUSATZ_NEU=1).
# Abbruch (rc 3), wenn druck_hohl oder druck_farbteile einen Fehler melden (nicht wasserdicht, Koerper zerfaellt, offene Hoehenschnitte, Durchdringung).
# rc 3 am Ende, wenn ein Koerperteil (Schicht 0,4) oder eine Platte (0,16) eine Luftinsel behaelt (druck_luft; 17.11.2026: Uhr-Zeiger wurden Spaghetti). druck_teilung und
#   druck_farbteile stuetzen Inseln selbst (druck_luft.stuetzen) und schneiden in Inselunterseiten; Ergebnis je Teil in teilung.json/farbteile.json ('luft').
# Ausgabe: modelle/stl/<objekt>_farbteile/ (Platten, koerper.stl, schnitte/*.png), modelle/stl/<objekt>_teile/ (Koerperteile, Verbinder), je druckzeit*.json. Messwerte Turm: PIPELINE_FASSADEN.md.
set -e; cd "$(dirname "$0")/.."; O="$1"; MASKEN="$2"; WAND="${3:-2.4}"; SPIEL="${4:-0.3}"; BAUART="${5:-tasche}"; INNEN="${6:-1.0}"; [ -n "$O" ] && [ -n "$MASKEN" ] || { sed -n 2,9p "$0"; exit 2; }
[ "$BAUART" = "tasche" ] || [ "$BAUART" = "einsatz" ] || { echo "BAUART muss tasche oder einsatz sein"; exit 2; }
P=/media/oem/scan/venv-seg/bin/python; OBJ="modelle/$O/objekt.json"; R=$($P -c "import json;print(json.load(open('$OBJ'))['stl'])"); GEN=$($P -c "import json;print(json.load(open('$OBJ'))['generator'])")
RR=$(readlink -f "$R"); Z="/media/oem/scan/rc-park_stl/${O}_wand${WAND/./}.stl"; python3 tools/platz_pruefen.py || exit 3
if [ -z "$BAUSATZ_NEU" ] && [ -s "$Z" ] && [ "$Z" -nt "$RR" ]; then echo "Wandmodell $Z ist juenger als das abgenommene STL - wird benutzt (neu bauen: BAUSATZ_NEU=1)"
else
( flock -n 8 || { echo "ABBRUCH: fuer $O laeuft schon ein Bau"; exit 5; }
  cp "$RR" "/media/oem/scan/rc-park_stl/${O}_sicher.stl"; set +e; eval "WAND_MM=$WAND $GEN" > /dev/null 2>&1; RC=$?; set -e
  [ "$RC" = "0" ] && mv "$RR" "$Z"; mv "/media/oem/scan/rc-park_stl/${O}_sicher.stl" "$RR"; git checkout "modelle/$O/elemente.json" 2>/dev/null || true
  [ "$RC" = "0" ] || { echo "ABBRUCH: Generator rc $RC"; exit 4; } ) 8>"/tmp/rcpark_bau_$O.lock"
fi
set +e; EIN="$Z"; OPT="--ring"
if [ "$BAUART" = "einsatz" ]; then
  EIN="${Z%.stl}_hohl.stl"; OPT="--einsatz --innen_mm $INNEN"
  $P -W ignore -I tools/druck_hohl.py "$Z" "$EIN" --wand_mm "$WAND" --bild "${EIN%.stl}.png" | grep "Hoehenbereiche\|Volumen\|Bild\|FEHLER\|kein massiver"; RC=${PIPESTATUS[0]}
  [ "$RC" = "0" ] || { echo "ABBRUCH: druck_hohl rc $RC"; exit 3; }; [ -s "$EIN" ] || EIN="$Z"
fi
$P -W ignore -I tools/druck_farbteile.py "$O" --stl "$EIN" --wand_mm "$WAND" --spiel_mm "$SPIEL" $OPT --schicht_mm 0.16 --masken "$MASKEN" | grep "platte_\|Ringschicht:\|Koerper:\|begrenzt\|keine Platte\|Durchdringung\|offene Hoehenschnitte\|  z \|Querschnittsbilder\|->"; RC=${PIPESTATUS[0]}
[ "$RC" = "0" ] || { echo "ABBRUCH: druck_farbteile rc $RC (Meldungen oben; Schnittbilder ansehen)"; exit 3; }
KS="modelle/stl/${O}_farbteile/koerper.stl"
if [ "${RIPPEN:-1}" = "1" ]; then      # 17.11.2026: duenne Waende innen aussteifen (Demodruck Turmschaft bog sich durch); RIPPEN=0 schaltet ab
  $P -W ignore -I tools/druck_rippen.py "$KS" "${KS%.stl}_rippen.stl" --bild "modelle/stl/${O}_farbteile/rippen.png" | grep "Hauptrichtungen\|Rippen:\|Volumen\|FEHLER\|Bild"; RC=${PIPESTATUS[0]}
  [ "$RC" = "0" ] || { echo "ABBRUCH: druck_rippen rc $RC"; exit 3; }; KS="${KS%.stl}_rippen.stl"
fi
$P -W ignore -I tools/druck_teilung.py "$O" --stl "$KS" --bett_mm 222 --toleranz_mm "$SPIEL" --schicht_mm 0.4 | grep -a "^teil_\|Schnitte\|verbinder\|Luft"
$P -W ignore -I tools/druck_farben.py "$O" --eintragen | tail -1
echo "== Luftinseln (tools/druck_luft.py; 17.11.2026: schwebende Uhrzeiger wurden auf dem Bambu Spaghetti)"
LUFT=0
for f in modelle/stl/${O}_teile/teil_*.stl; do $P -W ignore -I tools/druck_luft.py "$f" --schicht_mm 0.4 | tail -1; [ "${PIPESTATUS[0]}" = "0" ] || LUFT=$((LUFT+1)); done
for f in modelle/stl/${O}_farbteile/platte_*.stl; do $P -W ignore -I tools/druck_luft.py "$f" --schicht_mm 0.16 | tail -1; [ "${PIPESTATUS[0]}" = "0" ] || LUFT=$((LUFT+1)); done
echo "== Koerper: Prusa MK4S, Duese 0,8 mm, Schicht 0,4 mm"; python3 tools/druck_zeit.py "modelle/stl/${O}_teile" --duese 0.8 --schicht 0.4 --bett 250x210x220 | tail -12
echo "== Steinplatten: Bambu, Duese 0,4 mm, Schicht 0,16 mm"; python3 tools/druck_zeit.py "modelle/stl/${O}_farbteile" --schicht 0.16 --bett 256 | tail -10
[ "$LUFT" = "0" ] || { echo "ABBRUCH rc 3: $LUFT Teil(e) mit Luftinseln - so NICHT auf den Drucker (Liste oben; teilung.json/farbteile.json 'luft')"; exit 3; }
echo "Luftinseln: keine - alle Teile ohne Slicer-Stuetzen druckbar"
