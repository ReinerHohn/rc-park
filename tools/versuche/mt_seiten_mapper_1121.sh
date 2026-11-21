#!/bin/bash
# mt_seiten_mapper_1121.sh - Beweis Seitenfolge Martinstor (21.11.2026): je erkannter Seite (seiten_erkennen auf maskengefilterter DB, Masken im Pruefer) ein schrittweiser Mapper.
# Eingang: /media/oem/rcdaten/tmp/mt_seiten_1121/{db_maske_seiten.db, teil1.txt (Sued 102), teil2.txt (55), teil0.txt (Nord 538)}; kleine Seiten zuerst (fruehe Zwischenmeldung).
A=/media/oem/rcdaten/tmp/mt_seiten_1121; S=/media/oem/scan/rc-park_daten/martinstor-1120; C=/media/oem/scan/colmap-build/prefix/bin/colmap
for t in 1 2 0; do
  mkdir -p $A/modell_teil$t; t0=$(date +%s)
  $C mapper --database_path $A/db_maske_seiten.db --image_path $S/fotos --output_path $A/modell_teil$t --Mapper.image_list_path $A/teil$t.txt --Mapper.num_threads -1 \
     --Mapper.ba_use_gpu 1 --Mapper.ba_gpu_index 0 --Mapper.ba_max_num_images_direct_dense_gpu_solver 0 > $A/modell_teil$t/log.txt 2>&1
  echo "$(date +%H:%M:%S) teil$t: rc $?, $(( $(date +%s) - t0 )) s, Modelle $(ls -d $A/modell_teil$t/[0-9]* 2>/dev/null | wc -l); $($C model_analyzer --path $A/modell_teil$t/0 2>&1 | grep -E 'Registered images|Points|reprojection' | sed 's/.*] *//' | tr '\n' ';')"
done
