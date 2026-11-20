#!/bin/bash
# mt_eng_varianten_1120.sh - wartet, bis die beiden Mapperlaeufe von 20:52 fertig sind, und rechnet dann ALLEIN (saubere Zeiten) am engen Martinstor-Satz (1156 Bilder)
# die Varianten selten (globale Ausgleiche seltener/kuerzer, Video-Voreinstellung der Entwickler) und dicht (DENSE_SCHUR auf der GPU bis 1200 Bilder; perf 21:25: GetCell 20 % + Mutex 13 % der Mapperzeit
# entfallen bei dichter Kameramatrix). Bezug = Lauf "eng" von 20:52 (lief parallel zu einem zweiten Mapper -> Zeit nur grob), deshalb zum Schluss "eng" noch einmal allein.
S=/media/oem/scan/rc-park_daten/martinstor-1120; A=/media/oem/rcdaten/tmp/martinstor_inkr_1120
while systemctl --user is-active -q rcpark-mt_inkr_eng2 || systemctl --user list-units 'rcpark-kette-*' --no-legend --state=active | grep -vq gpuwache; do sleep 60; done   # erst wenn Mapper UND jede Kette fertig sind (Lehre 21:33: Messlaeufe allein, Buchung der Kette deckt spaete Stufen nicht)
mkdir -p $A/allein
BILDLISTE=$A/bilder_eng.txt bash "$(dirname "$0")/mapper_redundant_ab.sh" $S/pipe/sfm/db.db $S/fotos $A/allein selten dicht
