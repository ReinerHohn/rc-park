#!/bin/bash
# RefineMesh-Test mit anderen Optionen, ohne die Ergebnisse der Hauptkette zu ueberschreiben.
# Nutzung: refine_test.sh <arbeitsordner> <tag> [RefineMesh-Optionen...]
# Beispiel: refine_test.sh /media/oem/scan/colmap-test/martinstor-gpuba s1 --scales 1 --max-face-area 16
# Misst Dauer und Spitzen-RAM (GNU time), Ergebnis: scene_dense_mesh_refine_<tag>.ply
set -euo pipefail
OMVS=${OMVS:-/media/oem/scan/openmvs}
dir=${1:?arbeitsordner}; tag=${2:?tag}; shift 2
cd "$dir/openmvs"
/usr/bin/time -v "$OMVS" RefineMesh scene_dense.mvs -m scene_dense_mesh.ply \
  -o "scene_dense_mesh_refine_$tag.mvs" --max-threads 0 --cuda-device "${CUDA:--2}" "$@" \
  2> >(tr '\r' '\n' | grep -E "Maximum resident|Elapsed|Exit status" > "refine_$tag.zeit") \
  | tr '\r' '\n' | grep -v -E "^(Decimated|Processed)" > "refine_$tag.log"
cat "refine_$tag.zeit"
