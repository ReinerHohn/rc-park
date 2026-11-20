#!/bin/bash
# mapper_faeden_ab.sh - A/B 20.11.2026: der schrittweise Mapper der Kette laeuft mit `--Mapper.num_threads 1` (tools/iphone_sfm.py, seit 14.11., ohne dokumentierten Grund).
# Laut COLMAP-Quelltext steuert der Wert die Ceres-Faeden (Ableitungen im Buendelausgleich) und die RANSAC-Faeden der Lageschaetzung.
# Vergleich am selben kleinen Bestand: 1 Faden gegen alle Faeden; Messgroessen Wandzeit, registrierte Bilder, Punkte, mittlerer Rueckprojektionsfehler.
# Aufruf: mapper_faeden_ab.sh <db.db> <bilderordner> [arbeitsordner]     (DB wird je Lauf kopiert, Original bleibt unberuehrt)
set -u; DB=$1; IMG=$2; A=${3:-/media/oem/rcdaten/tmp/mapper_faeden_ab}; C=/media/oem/scan/colmap-build/prefix/bin/colmap
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
mkdir -p "$A"
for n in 1 -1; do
  z="$A/faeden_$n"; rm -rf "$z"; mkdir -p "$z"; cp "$DB" "$z/db.db"; t0=$(date +%s)
  $C mapper --database_path "$z/db.db" --image_path "$IMG" --output_path "$z" --Mapper.num_threads $n --Mapper.ba_use_gpu 1 --Mapper.ba_gpu_index 0 \
     --Mapper.ba_max_num_images_direct_dense_gpu_solver 0 > "$z/log.txt" 2>&1; rc=$?; t1=$(date +%s)
  echo "Faeden $n: rc $rc, $((t1-t0)) s, Modelle $(ls -d "$z"/[0-9]* 2>/dev/null | wc -l); $($C model_analyzer --path "$z/0" 2>&1 | grep -E 'Registered images|Points|Mean reprojection error|Mean track length' | sed 's/.*] //' | tr '\n' ';')"
  rm -f "$z/db.db"
done
