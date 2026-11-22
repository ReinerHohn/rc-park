#!/bin/bash
# durchblick_mapper_1122.sh <bildliste> <ausgabe> [db] - schrittweiser (spurbasierter) COLMAP-Mapper auf der Durchblick-Kopie, unter Deckel (Scope MemoryMax 5G, halbe Kerne, BA auf CPU).
# 22.11.2026: globaler Mapper band Teil 1 nur ueber 5 Spuren / EIN Bild an (Eckpaare im Modell 11-16 % konsistent) - pruefen, ob der Spur-Mapper die Ecke starr haelt.
set -u
L=$1; O=$2; A=/media/oem/rcdaten/tmp/durchblick; DB=${3:-$A/db_durch_mapper.db}; C=/media/oem/scan/colmap-build/prefix/bin/colmap; N=$(( $(nproc) / 2 ))
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
mkdir -p "$O"; t0=$(date +%s)
systemd-run --user --scope --quiet -p MemoryMax=5G $C mapper --database_path "$DB" --image_path /media/oem/scan/rc-park_daten/schwabentor-1122/fotos --output_path "$O" \
  --Mapper.image_list_path "$L" --Mapper.num_threads $N --Mapper.ba_use_gpu 0 > "$O.log" 2>&1
echo "mapper rc $? in $(( $(date +%s) - t0 )) s"
for d in "$O"/*/; do echo "$d: $($C model_analyzer --path "$d" 2>&1 | grep -E 'Registered images|Points:|Mean reprojection' | sed 's/.*] *//' | tr '\n' ' ')"; done
