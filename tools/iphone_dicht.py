#!/usr/bin/env python3
"""iphone_dicht.py <bilder> <sparse/N> <ausgabeordner> [max_bild] - COLMAP dicht (undistort -> PatchMatch-Stereo CUDA -> Fusion). Nutzer 8.11.: Punktwolke aus iPhone-Fotos ergaenzen."""
import sys, os, pycolmap, time
img, sp, out = sys.argv[1:4]; mx = int(sys.argv[4]) if len(sys.argv) > 4 else 1600; t = time.time(); os.makedirs(out, exist_ok=True)
uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = mx; pycolmap.undistort_images(out, sp, img, undistort_options=uo); print("undistort", time.time() - t, flush=True)
o = pycolmap.PatchMatchOptions(); o.max_image_size = mx; o.gpu_index = "0"; o.geom_consistency = True
pycolmap.patch_match_stereo(out, options=o); print("patchmatch", time.time() - t, flush=True)
f = pycolmap.stereo_fusion(f"{out}/fused.ply", out, output_type="PLY", options=pycolmap.StereoFusionOptions()); print("fusion", time.time() - t, flush=True)
