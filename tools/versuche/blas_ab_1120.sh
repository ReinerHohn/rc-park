#!/bin/bash
# blas_ab_1120.sh - A/B 20.11.2026: unser COLMAP-Bau rechnet die CPU-Algebra (CHOLMOD/Ceres) mit der langsamen Referenz-BLAS (libblas3 3.12, 1 Faden).
# Vergleich am selben Modell, gleicher Buendelausgleich (8 Iterationen): (A) Referenz-BLAS, (B) OpenBLAS-OpenMP per LD_LIBRARY_PATH (ohne Installation,
# Paket nur entpackt nach /media/oem/rcdaten/tmp/openblas_test), (C) GPU-Loeser (cuDSS) als Bezug. Messgroessen: Wandzeit, Endkosten (muss gleich sein).
# Aufruf: blas_ab_1120.sh MODELL_ORDNER [ITER]
set -u; M=$1; IT=${2:-8}; T=/media/oem/rcdaten/tmp/openblas_test; C=/media/oem/scan/colmap-build/prefix/bin/colmap
BASIS=/media/oem/scan/cuda-toolkit-combo/lib64:/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib:/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib:/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib
OB=$T/root/usr/lib/x86_64-linux-gnu/openblas-openmp
lauf(){ # name libpfad gpu [env...]
  local n=$1 lp=$2 g=$3; shift 3; mkdir -p $T/aus_$n; local t0=$(date +%s.%N)
  env LD_LIBRARY_PATH=$lp "$@" $C bundle_adjuster --input_path "$M" --output_path $T/aus_$n --BundleAdjustmentCeres.max_num_iterations $IT --BundleAdjustmentCeres.use_gpu $g > $T/log_$n.txt 2>&1; local rc=$?
  local t1=$(date +%s.%N); echo "$n: rc $rc  $(awk -v a=$t0 -v b=$t1 'BEGIN{printf "%.0f s", b-a}')  BLAS=$(env LD_LIBRARY_PATH=$lp ldd $C | grep 'libblas.so.3' | awk '{print $3}' | grep -o 'openblas[^/]*\|x86_64-linux-gnu/libblas' | head -1)  $(grep -E 'Final cost|Linear solver  |Total  ' $T/log_$n.txt | tr -s ' ' | tr '\n' ';' | cut -c1-200)"
}
lauf A_referenz $BASIS 0
lauf B_openblas $OB:$BASIS 0 OMP_NUM_THREADS=16
lauf C_gpu $BASIS 1
lauf D_gpu_openblas $OB:$BASIS 1 OMP_NUM_THREADS=16
