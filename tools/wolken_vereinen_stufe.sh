#!/bin/bash
# wolken_vereinen_stufe.sh <objekt.json> <name> <wolke.ply|npy> <rahmen> [lagetor] - Schlussstufe JEDER Nachtkette mit neuer dichter Wolke (27.11.2026, Nutzer: "Immer vereinen").
# 1. neue Wolke ins Register modelle/<obj>/wolken.json eintragen (tools/wolke_vereinigen.py --anmelden; gleicher Name = ersetzen),
# 2. Lagetor des Eintrags pruefen (teilmodell:<ausrichtung.json>#<n> | spuren:<einpassung.json>); UNSICHER -> Grund melden, NICHT vereinen (rc 3), Eintrag bleibt (spaeter neu geprueft),
# 3. ALLE Register-Wolken vereinen (Job ueber tools/job_start.sh, JOB_RAM_MB=${WV_RAM_MB:-5000}, JOB_CPU=alle - keine E-Kern-Bindung) -> ${WV_AUS:-/media/oem/rcdaten/tmp/wolken_vereint/<obj>}/,
# 4. Ergebnis: Zeilen OK/NICHT je Quelle + Punkte je Zone; rc 0 = vereint, 3 = neue Quelle nicht vereint oder Zone ROT (vereint < beste Quelle), sonst Fehler.
# rahmen: modell | sfm:<SFM-AUSRICHTUNG.json> | matrix:<json>#<schluessel>   (siehe Kopf tools/wolke_vereinigen.py). Dummy-Test: tools/test_wolken_vereinen_stufe.sh
# Verwandt: tools/wolke_vereinigen.py (Werkzeug), tools/wolken_vereinen_kette.py (gleicher Schritt in tools/gesamtkette.py), tools/teilmodell_ausrichten.py (Lagetor).
# Vorlaeufer: Schritt 3 in tools/handy_dicht_nachlauf.sh (nur mit pipe/dicht/fused.ply vereint, ohne Lagetor/Register); handy_fusion_nachlauf.sh vereinte gar nicht.
OBJ=$1; NAME=$2; WOLKE=$3; RAHMEN=${4:-modell}; LT=${5:-}
[ -n "$OBJ" ] && [ -n "$NAME" ] && [ -n "$WOLKE" ] || { echo "Aufruf: wolken_vereinen_stufe.sh <objekt.json> <name> <wolke> <rahmen> [lagetor]"; exit 2; }
cd "$(dirname "$0")/.." || exit 2
PY=${WV_PY:-/media/oem/scan/venv-colmap/bin/python}
t() { echo "$(date '+%F %T') wolken_vereinen: $*"; }
[ -f "$WOLKE" ] || { t "ABBRUCH: $WOLKE fehlt"; exit 2; }
O=$(basename "$(dirname "$(readlink -f "$OBJ")")"); AUSD=${WV_AUS:-/media/oem/rcdaten/tmp/wolken_vereint/$O}; L=$AUSD.log
$PY -I tools/wolke_vereinigen.py --objekt "$OBJ" --anmelden "$NAME=$(readlink -f "$WOLKE")@$RAHMEN@$LT" || { t "ABBRUCH: anmelden rc $?"; exit 2; }
g=$($PY -I -c "import sys; sys.path.insert(0, 'tools'); import wolke_vereinigen as W; ok, txt = W.lagetor_pruefen(sys.argv[1]); print(txt); sys.exit(0 if ok else 3)" "$LT"); rc=$?; t "Lagetor $NAME: $g"
[ "$rc" = 0 ] || { t "NICHT VEREINT: $NAME - Lagetor UNSICHER ($g). Eintrag bleibt im Register, wird beim naechsten Vereinen neu geprueft."; exit 3; }
if [ "${WV_DIREKT:-0}" = 1 ]; then $PY -I tools/wolke_vereinigen.py --objekt "$OBJ" --aus "$AUSD" > "$L" 2>&1; echo "JOB_ENDE rc=$?" >> "$L"
else
  rm -f "$L"; JOB_CPU=alle JOB_RAM_MB=${WV_RAM_MB:-5000} bash tools/job_start.sh "wolken-vereinen-$O" "$L" $PY -I tools/wolke_vereinigen.py --objekt "$OBJ" --aus "$AUSD" || { t "ABBRUCH: job_start"; exit 2; }
  i=0; until grep -q '^JOB_ENDE' "$L" 2>/dev/null || [ $i -ge "${WV_MAX_S:-5400}" ]; do sleep 30; i=$((i+30)); done
fi
rc=$(grep '^JOB_ENDE' "$L" 2>/dev/null | tail -1 | sed 's/.*rc=//'); rc=${rc:-99}
grep -E '^(OK  |NICHT|  [A-Z].*=|VEREINIGT|ROT)' "$L" | cut -c1-300
grep -q "^NICHT .*\"name\": \"$NAME\"" "$L" && { t "NICHT VEREINT: $NAME (Grund oben, Lage-/Ueberlapp-Tor) - uebrige Quellen vereint"; [ "$rc" = 0 ] && rc=3; }
t "ENDE rc=$rc -> $AUSD (vereint.json, punkte_modell.npy)"; exit "$rc"
