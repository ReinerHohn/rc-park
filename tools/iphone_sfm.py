#!/usr/bin/env python3
"""iphone_sfm.py <bilderordner> <arbeitsordner> - COLMAP-SfM (pycolmap, SIFT-GPU, exhaustive, Mapper) fuer die iPhone-Fotos; GPU von Anfang an (Nutzerregel)."""
import sys, os, pycolmap, time
img, w = sys.argv[1], sys.argv[2]; os.makedirs(w, exist_ok=True); db = f"{w}/db.db"; t = time.time()
so = pycolmap.FeatureExtractionOptions(); so.sift.max_num_features = 6400; so.max_image_size = 2400
pycolmap.extract_features(db, img, camera_mode=pycolmap.CameraMode.PER_IMAGE, extraction_options=so, device=pycolmap.Device.cuda); print("Merkmale", time.time() - t, flush=True)
pycolmap.match_exhaustive(db, device=pycolmap.Device.cuda); print("Abgleich", time.time() - t, flush=True)
os.makedirs(f"{w}/sparse", exist_ok=True)
rec = pycolmap.incremental_mapping(db, img, f"{w}/sparse"); print("Mapper", time.time() - t, flush=True)
for k, r in rec.items(): print(k, r.summary(), flush=True)
