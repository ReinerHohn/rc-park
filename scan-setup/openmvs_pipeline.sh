#!/bin/bash
# OpenMVS-Kette: Densify -> ReconstructMesh -> RefineMesh -> TextureMesh
# Nutzung: openmvs_pipeline.sh <arbeitsordner-mit-openmvs/scene.mvs> [ab-schritt]
# Schritte: 1=densify 2=mesh 3=refine 4=texture. Jeder Schritt wird uebersprungen,
# wenn sein Ergebnis schon existiert; "ab-schritt" erzwingt Neulauf ab dort
# (die .dmap-Tiefenkarten bleiben dabei erhalten, Densify rechnet nur neu fusionieren).
set -euo pipefail

OMVS=${OMVS:-/media/oem/scan/openmvs}
dir=${1:?arbeitsordner}; from=${2:-0}
cd "$dir/openmvs"
[ -f scene.mvs ] || { echo "scene.mvs fehlt in $dir/openmvs" >&2; exit 1; }

step() {  # nr name ergebnis befehl...
  local nr=$1 name=$2 out=$3; shift 3
  if [ -f "$out" ] && [ "$nr" -lt "$from" -o "$from" = 0 ]; then
    echo ">>> $name: $out vorhanden, uebersprungen"; return
  fi
  echo ">>> $name"; local t=$SECONDS
  "$OMVS" "$@" 2>&1 | tr '\r' '\n' | grep -v -E "^(Estimated|Geometric|Dense fused|Refine)" | tee "$name.log" | tail -3
  echo "    $name fertig in $((SECONDS-t))s"
}

step 1 densify scene_dense.mvs DensifyPointCloud scene.mvs --resolution-level 0 --max-threads 0 -w "$PWD"
step 2 mesh    scene_dense_mesh.ply ReconstructMesh scene_dense.mvs -o scene_dense_mesh.mvs --max-threads 0
step 3 refine  scene_dense_mesh_refine.mvs RefineMesh scene_dense.mvs -m scene_dense_mesh.ply -o scene_dense_mesh_refine.mvs --max-threads 0 --cuda-device -2
step 4 texture scene_dense_mesh_refine_texture.glb TextureMesh scene_dense.mvs -m scene_dense_mesh_refine.ply -o scene_dense_mesh_refine_texture.mvs --export-type glb --max-threads 0
echo ">>> FERTIG: $PWD/scene_dense_mesh_refine_texture.glb"
