#!/bin/bash
# durchblick_anbau_1122.sh - starres Kettenmodell Teil 0 als Start (--input_path), schrittweiser Mapper registriert NUR die Eckbilder (Gruppe Ecke) und die Teil-1-Bilder dazu
# (22.11.2026: globaler Mapper knickte Teil 1 an einem Bild; voller Spur-Mapper ueber 573 Bilder auf CPU zu langsam). Kopie der Durchblick-DB, Ketten-Ordner nur gelesen.
set -u
A=/media/oem/rcdaten/tmp/durchblick; C=/media/oem/scan/colmap-build/prefix/bin/colmap; N=${ANBAU_FAEDEN:-14}
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
O=$A/anbau_sparse${ANBAU_NAME:-}; mkdir -p $O; t0=$(date +%s)
$C mapper --database_path $A/db_durch_mapper.db --image_path /media/oem/scan/rc-park_daten/schwabentor-1122/fotos --input_path $A/anbau_ein --output_path $O \
  --Mapper.image_list_path $A/anbau.txt --Mapper.num_threads $N --Mapper.ba_use_gpu ${ANBAU_GPU:-0} --Mapper.multiple_models 0 --Mapper.fix_existing_frames ${ANBAU_FEST:-1} --Mapper.ba_global_frames_ratio 2.0 --Mapper.ba_global_points_ratio 2.0 --Mapper.ba_global_max_num_iterations 25 > $O.log 2>&1
echo "mapper rc $? in $(( $(date +%s) - t0 )) s"
$C model_analyzer --path $O 2>&1 | grep -E 'Registered images|Points:|Mean reprojection' | sed 's/.*] *//'
