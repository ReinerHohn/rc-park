#!/bin/bash
# Lot-Runde 22.11.2026: Lage-Pruefstand vorher (AUSR_LOT=bildachsen = Vorgaengerzweig) / nachher (Fluchtpunkt-Lot, Kippung fest), CPU, nacheinander (EIN Lauf zur Zeit).
# Aufruf: tools/versuche/lot_runde/pruefstand_lauf.sh [stand ...]   Ausgabe /media/oem/rcdaten/tmp/lot_runde/{nachher,vorher}/
cd "$(dirname "$0")/../../.." || exit 2
A=/media/oem/rcdaten/tmp/lot_runde; export TMPDIR=/media/oem/rcdaten/tmp
ST=("$@"); [ ${#ST[@]} -gt 0 ] || ST=(schwabentor-1122 schwabentor-1120)
for s in "${ST[@]}"; do
  echo "=== nachher $s $(date +%T)"; tools/py tools/lage_pruefstand.py --stand "$s" --aus "$A/nachher" --cpu
done
for s in "${ST[@]}"; do
  echo "=== vorher (AUSR_LOT=bildachsen) $s $(date +%T)"; AUSR_LOT=bildachsen tools/py tools/lage_pruefstand.py --stand "$s" --aus "$A/vorher" --cpu
done
echo "=== fertig $(date +%T)"
