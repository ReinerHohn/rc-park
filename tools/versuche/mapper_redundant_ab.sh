#!/bin/bash
# mapper_redundant_ab.sh - A/B 20.11.2026 abends. Befund (perf am laufenden Martinstor-Mapper, 610 Bilder, 1 Faden): 89 % der Zeit in der
# Schur-Elimination von Ceres (ChunkOuterProduct 60 %, BlockRandomAccessSparseMatrix::GetCell 29 %), je globalem Ausgleich 37-39 min.
# Kosten ~ Summe (Spurlaenge^2) -> lange Videospuren. COLMAP hat dafuer `--Mapper.ba_global_ignore_redundant_points3D` (Standard 0).
# Vergleich am selben Bestand, beide mit allen Faeden: Standard gegen redundante Punkte im globalen Ausgleich weglassen.
# Messgroessen: Wandzeit, registrierte Bilder, Punkte, Rueckprojektionsfehler, Zahl der Loeserfehler, Zeit in globalen Ausgleichen.
# Aufruf: mapper_redundant_ab.sh <db.db> <bilderordner> [arbeitsordner] [varianten...]   (DB wird je Lauf kopiert)
set -u; DB=$1; IMG=$2; A=${3:-/media/oem/rcdaten/tmp/mapper_redundant_ab}; shift 3 2>/dev/null; V=${*:-"std redundant"}
C=/media/oem/scan/colmap-build/prefix/bin/colmap
export LD_LIBRARY_PATH=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
mkdir -p "$A"
for v in $V; do
  case $v in std) X="";; redundant) X="--Mapper.ba_global_ignore_redundant_points3D 1";; dicht) X="--Mapper.ba_max_num_images_direct_dense_gpu_solver 1200";; *) echo "unbekannt: $v"; continue;; esac
  D0="--Mapper.ba_max_num_images_direct_dense_gpu_solver 0"; [ "$v" = dicht ] && D0=""
  z="$A/$v"; rm -rf "$z"; mkdir -p "$z"; cp "$DB" "$z/db.db"; t0=$(date +%s)
  $C mapper --database_path "$z/db.db" --image_path "$IMG" --output_path "$z" --Mapper.num_threads -1 --Mapper.ba_use_gpu 1 --Mapper.ba_gpu_index 0 $D0 $X > "$z/log.txt" 2>&1; rc=$?; t1=$(date +%s)
  gr=$(ls -d "$z"/[0-9]* 2>/dev/null | while read m; do echo "$(stat -c %s "$m/images.bin") $m"; done | sort -rn | head -1 | cut -d' ' -f2)
  echo "$(date +%T) $v: rc $rc, $((t1-t0)) s, Modelle $(ls -d "$z"/[0-9]* 2>/dev/null | wc -l), Loeserfehler $(grep -c 'Linear solver failure' "$z/log.txt"), globale Ausgleiche $(grep -c 'Global bundle adjustment' "$z/log.txt"); groesstes: $($C model_analyzer --path "$gr" 2>&1 | grep -E 'Registered images|Points|Mean reprojection error|Mean track length' | sed 's/.*] //' | tr '\n' ';')"
  rm -f "$z/db.db"
done
