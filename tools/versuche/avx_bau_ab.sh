#!/bin/bash
# avx_bau_ab.sh - A/B 20.11.2026: COLMAP/Ceres-Bau vom 13.11. (ohne AVX2/FMA) gegen Testbau mit -O3 -march=native (/media/oem/rcdaten/colmap-opt/prefix).
# Gleiche Eingaben, je Bau: (1) Buendelausgleich CPU, (2) Buendelausgleich GPU-Loeser (8 Iterationen, Martinstor-Konsensmodell), (3) schrittweiser Mapper Schwabentor 203 Bilder, alle Faeden.
# Messgroessen: Wandzeit, Endkosten bzw. Bilder/Punkte/Rueckprojektionsfehler. Reihenfolge alt-neu-alt je Messung gegen Waermedrift. Aendert nichts an der Kette.
set -u; T=/media/oem/rcdaten/tmp/avx_ab; mkdir -p $T; M=/media/oem/scan/rc-park_daten/martinstor-1120/pipe/sfm/sparse_konsens/0
ALT=/media/oem/scan/colmap-build/prefix/bin/colmap; NEU=/media/oem/rcdaten/colmap-opt/prefix/bin/colmap
LA=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
LN=$(bash -c 'source /media/oem/rcdaten/colmap-opt/prefix/colmap-umgebung.sh >/dev/null 2>&1; echo $LD_LIBRARY_PATH')
ba(){ # name bin lib gpu
  local t0=$(date +%s.%N); mkdir -p $T/ba_$1; LD_LIBRARY_PATH=$3 $2 bundle_adjuster --input_path $M --output_path $T/ba_$1 --BundleAdjustmentCeres.max_num_iterations 8 --BundleAdjustmentCeres.use_gpu $4 > $T/ba_$1.log 2>&1
  echo "BA $1: rc $? $(awk -v a=$t0 -v b=$(date +%s.%N) 'BEGIN{printf "%.0f s", b-a}') $(grep -E 'Final cost' $T/ba_$1.log | tr -s ' ')"; }
mp(){ # name bin lib
  local z=$T/mp_$1; rm -rf $z; mkdir -p $z; cp /media/oem/scan/rc-park_daten/schwabentor/sfm/db.db $z/db.db; local t0=$(date +%s)
  LD_LIBRARY_PATH=$3 $2 mapper --database_path $z/db.db --image_path /home/oem/git/rc-park/daten/schwabentor/fotos --output_path $z --Mapper.num_threads -1 --Mapper.ba_use_gpu 1 --Mapper.ba_gpu_index 0 --Mapper.ba_max_num_images_direct_dense_gpu_solver 0 > $z/log.txt 2>&1
  echo "Mapper $1: rc $? $(( $(date +%s)-t0 )) s; $(LD_LIBRARY_PATH=$3 $2 model_analyzer --path $z/0 2>&1 | grep -E 'Registered images|Points|Mean reprojection' | sed 's/.*] //' | tr '\n' ';')"; rm -f $z/db.db; }
echo "Neu-Bau: $(LD_LIBRARY_PATH=$LN $NEU -h 2>&1 | head -1)"
ba cpu_alt1 $ALT $LA 0; ba cpu_neu $NEU $LN 0; ba cpu_alt2 $ALT $LA 0
ba gpu_alt1 $ALT $LA 1; ba gpu_neu $NEU $LN 1; ba gpu_alt2 $ALT $LA 1
mp alt1 $ALT $LA; mp neu $NEU $LN; mp alt2 $ALT $LA
