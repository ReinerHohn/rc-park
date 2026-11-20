#!/bin/bash
# mapper_loeser_ab.sh - A/B 20.11.2026 (Profil per perf: 81 % der Mapperzeit = Schur-Elimination auf der CPU; im Log 769 x "Linear solver failure" in 46 globalen Ausgleichen
# = jede gescheiterte Loesung wirft eine ganze Schur-Elimination weg). Frage: scheitert nur der duenn besetzte GPU-Loeser (cuDSS, unsere Einstellung
# ba_max_num_images_direct_dense_gpu_solver 0) oder jeder? Gleicher Bestand (Schwabentor 203 Bilder), alle Faeden, je Variante: Zeit, Loeserfehler, Bilder/Punkte/Fehler.
set -u; A=/media/oem/rcdaten/tmp/mapper_loeser_ab; C=${COLMAP:-/media/oem/scan/colmap-build/prefix/bin/colmap}; mkdir -p $A
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
lauf(){ local n=$1; shift; local z=$A/$n; rm -rf $z; mkdir -p $z; cp /media/oem/scan/rc-park_daten/schwabentor/sfm/db.db $z/db.db; local t0=$(date +%s)
  $C mapper --database_path $z/db.db --image_path /home/oem/git/rc-park/daten/schwabentor/fotos --output_path $z --Mapper.num_threads -1 "$@" > $z/log.txt 2>&1
  echo "$n: rc $? $(( $(date +%s)-t0 )) s, Loeserfehler $(grep -c 'Linear solver failure' $z/log.txt); $($C model_analyzer --path $z/0 2>&1 | grep -E 'Registered images|Points|Mean reprojection' | sed 's/.*] //' | tr '\n' ';')"; rm -f $z/db.db; }
lauf gpu_duenn_heute --Mapper.ba_use_gpu 1 --Mapper.ba_gpu_index 0 --Mapper.ba_max_num_images_direct_dense_gpu_solver 0
lauf gpu_dicht       --Mapper.ba_use_gpu 1 --Mapper.ba_gpu_index 0 --Mapper.ba_max_num_images_direct_dense_gpu_solver 1000
lauf cpu             --Mapper.ba_use_gpu 0
lauf gpu_colmap_standard --Mapper.ba_use_gpu 1 --Mapper.ba_gpu_index 0
