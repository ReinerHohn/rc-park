#!/bin/bash
# variante_bauen.sh - Generator-Variante bauen UND PRUEFEN, DASS SIE SICH UNTERSCHEIDET.
# Falle (2026-11-01): sed-Muster griff nicht ("TWs = 2.6" statt "TWs, T0, T1 = 2.6,") -> drei "Varianten" waren bitgleich
# mit dem Ist-Modell, der Vergleich zeigte "kein Einfluss". Seitdem bricht dieses Skript bei unveraenderter Datei ab.
#   tools/variante_bauen.sh <generator.py> <ziel.stl> <sed-ausdruck> [weitere sed-ausdruecke ...]
set -e
GEN="$1"; ZIEL="$2"; shift 2
TMP="${ZIEL%.stl}_gen.py"
ARGS=(); for e in "$@"; do ARGS+=(-e "$e"); done
# 1) NUR die Nutzer-Ausdruecke anwenden und gegen das Original pruefen (die Standard-Ersetzungen aendern die Datei immer)
sed "${ARGS[@]}" "$GEN" > "$TMP.pruef"
if cmp -s "$TMP.pruef" "$GEN"; then
  rm -f "$TMP.pruef"; echo "FEHLER: sed-Muster hat nicht gegriffen, Variante waere identisch: $*" >&2; exit 2
fi
# 2) jetzt zusaetzlich Ausgabepfad umbiegen
sed -e "s|^OUT = .*|OUT = '$ZIEL'|" -e "/^                   f\"martinstor_v4_1/d" -e "s|^_json.dump(.*|pass|" "$TMP.pruef" > "$TMP"; rm -f "$TMP.pruef"
SCALE=${SCALE:-87} MINMM=${MINMM:-0.8} ~/.venvs/rcpark/bin/python "$TMP" > /dev/null
# 3) STL muss sich vom Ist-Modell unterscheiden (Parameter koennte ohne Wirkung sein)
IST="modelle/stl/$(basename "$GEN" _gen.py)_1-${SCALE:-87}.stl"
if [ -f "$IST" ] && cmp -s "$IST" "$ZIEL"; then echo "WARNUNG: $ZIEL ist bitgleich mit $IST - Parameter ohne Wirkung?" >&2; fi
echo "gebaut: $ZIEL  ($*)"
