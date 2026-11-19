#!/bin/bash
# FlexGlue (neuer COLMAP-Bau c1b5a967) auf den Martinstor-Paaren: $1 = Paarliste, $2 = DB, $3 = min_covisibility
source /media/oem/rcdaten/colmap-test/prefix/colmap-umgebung.sh; export LD_LIBRARY_PATH=/media/oem/rcdaten/colmap-test/cuda12-onnx/pip/nvidia/cublas/lib:/media/oem/rcdaten/colmap-test/cuda12-onnx/pip/nvidia/cuda_runtime/lib:/media/oem/rcdaten/colmap-test/cuda12-onnx/pip/nvidia/cudnn/lib:/media/oem/rcdaten/colmap-test/cuda12-onnx/pip/nvidia/cufft/lib:$LD_LIBRARY_PATH
t=$(date +%s); /media/oem/rcdaten/colmap-test/prefix/bin/colmap matches_importer --database_path $2 --match_list_path $1 --match_type pairs \
  --FeatureMatching.type FLEXGLUE --FlexGlueMatching.image_path /media/oem/scan/rc-park_daten/martinstor_gk3/fotos --FlexGlueMatching.min_covisibility $3 --FlexGlueMatching.num_workers_per_gpu 1 --FlexGlueMatching.num_inferences_per_gpu 1 --FlexGlueMatching.feature_cache_size 16; echo "ERGEBNIS rc $? Zeit $(( $(date +%s)-t )) s"
