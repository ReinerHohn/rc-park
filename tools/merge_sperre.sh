#!/usr/bin/env bash
# merge_sperre.sh [OBJEKT ...] - MERGE-SPERRE nach main (24.11.2026, Nutzer: "sichere das hart ab!"; Skill kette-schleife Schritt 5, tools/ketten_probelauf.sh).
# Verweigert den Merge, wenn der LETZTE Kettenlauf eines Objekts einen BESTAND RUECKSCHRITT hatte (tools/bestand_tor.py -> modelle/<objekt>/audit/bestand_tor.json,
# Feld "rueckschritt" nicht leer). Ohne Argument: alle Objekte mit bestand_tor.json. Verwandt: tools/bestand_tor.py, tools/foto_tor_bezug.py; Vorlaeufer: keiner (ketten_probelauf prueft nur den Ablauf).
# Exit: 0 = frei, 1 = GESPERRT (Zonen werden genannt), 3 = Aufruf.
# Aufheben nur durch einen neuen Kettenlauf ohne Rueckschritt (kein Handeintrag, keine Umgehung per Schalter).
cd "$(dirname "$0")/.." || exit 3
WURZEL="${RCPARK_MERGE_SPERRE_WURZEL:-modelle}"
if [ "$#" -gt 0 ]; then L=(); for o in "$@"; do L+=("$WURZEL/$o/audit/bestand_tor.json"); done
else mapfile -t L < <(ls "$WURZEL"/*/audit/bestand_tor.json 2>/dev/null); fi
GESPERRT=0
for f in "${L[@]}"; do
  [ -f "$f" ] || { echo "merge_sperre: $f fehlt (Bestand-Tor nie gelaufen) - kein Urteil, nicht gesperrt"; continue; }
  R=$(python3 -I -c "import json,sys; d=json.load(open(sys.argv[1])); r=d.get('rueckschritt') or []; print(('%s|' % d.get('zeit','?')) + '; '.join(r))" "$f") || { echo "merge_sperre: $f unlesbar - GESPERRT"; GESPERRT=1; continue; }
  Z="${R%%|*}"; RS="${R#*|}"
  if [ -n "$RS" ]; then echo "MERGE GESPERRT: $f (Lauf $Z) BESTAND RUECKSCHRITT: $RS"; GESPERRT=1
  else echo "merge_sperre: $f (Lauf $Z) ohne Rueckschritt"; fi
done
[ "$GESPERRT" = 1 ] && { echo "=> kein Merge nach main, bis ein Kettenlauf die Zonen wieder auf Bestand bringt (Bilder modelle/<objekt>/bestand/ ansehen)"; exit 1; }
exit 0
