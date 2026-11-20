#!/bin/bash
# Punkt 7 (20.11.): PatchMatch-PR #5041 (Ebenen bei der Tiefenausbreitung erhalten) gegen gleichen Code ohne PR; Martinstor-Rueckseite, 74 entzerrte Bilder (fein_vgl/A_schnell),
# Einstellungen wie dicht_modell schnell + Fenster 11 / ncc 0,05; Fusion photometric 1600 px, min_num_pixels 3. Messung: Zeit, Wandbelegung, Fehlpunkte (wand.py)
P=/media/oem/rcdaten/tmp/pm_ab; Q=/media/oem/rcdaten/tmp/mt_seiten/fein_vgl/A_schnell
for v in ohne mit; do
  if [ $v = ohne ]; then B=/media/oem/rcdaten/colmap-test/prefix; else B=/media/oem/rcdaten/colmap-test/prefix-pm; fi
  W=$P/$v; mkdir -p $W/stereo/depth_maps $W/stereo/normal_maps $W/stereo/consistency_graphs; ln -sfn $Q/images $W/images; ln -sfn $Q/sparse $W/sparse
  cp $Q/stereo/patch-match.cfg $Q/stereo/fusion.cfg $W/stereo/
  ( source $B/colmap-umgebung.sh; t=$(date +%s)
    $B/bin/colmap patch_match_stereo --workspace_path $W --PatchMatchStereo.max_image_size 1600 --PatchMatchStereo.gpu_index 0 --PatchMatchStereo.geom_consistency 0 --PatchMatchStereo.filter 1 \
      --PatchMatchStereo.window_step 2 --PatchMatchStereo.window_radius 11 --PatchMatchStereo.filter_min_ncc 0.05 > $W/pm.log 2>&1; echo "PM $v rc $? Zeit $(( $(date +%s)-t )) s"
    $B/bin/colmap stereo_fusion --workspace_path $W --input_type photometric --output_path $W/fused.ply --StereoFusion.max_image_size 1600 --StereoFusion.min_num_pixels 3 > $W/fus.log 2>&1; echo "FUSION $v rc $?" )
done
cd /tmp && /media/oem/scan/venv-colmap/bin/python -I $P/wand.py
