#!/bin/bash
# mt_global_gefiltert_1121.sh - Frage Nutzer 21.11. 12:20: scheiterte der GLOBALE Mapper am Martinstor nur, weil die Zuordnungen nicht gefiltert waren (Person als Bruecke, verwechselte Seiten)?
# Test: globaler Mapper auf der gefilterten DB (Masken + Seitenerkennung mit Masken), je Seite (teil0 = Nord 538, teil1 = Sued 102), zweimal je Seite (Laufstreuung). Vergleich: schrittweise Modelle modell_teil*.
A=/media/oem/rcdaten/tmp/mt_seiten_1121; S=/media/oem/scan/rc-park_daten/martinstor-1120; C=/media/oem/scan/colmap-build/prefix/bin/colmap
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
cp $A/db_maske_seiten.db $A/db_global.db; $C view_graph_calibrator --database_path $A/db_global.db > $A/global_kalib.log 2>&1; echo "$(date +%H:%M:%S) Kalibrierung rc $?"
for t in 1 0; do for l in a b; do
  Z=$A/global_teil${t}_$l; mkdir -p $Z; t0=$(date +%s)
  $C global_mapper --database_path $A/db_global.db --image_path $S/fotos --output_path $Z --GlobalMapper.image_list_path $A/teil$t.txt > $Z/log.txt 2>&1
  echo "$(date +%H:%M:%S) global teil$t Lauf $l: rc $?, $(( $(date +%s) - t0 )) s, Modelle $(ls -d $Z/[0-9]* 2>/dev/null | wc -l); $($C model_analyzer --path $Z/0 2>&1 | grep -E 'Registered images|Points|reprojection' | sed 's/.*] *//' | tr '\n' ';')"
done; done
