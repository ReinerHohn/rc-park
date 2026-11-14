#!/usr/bin/env python3
"""iphone_sfm.py <bilderordner> <arbeitsordner> - COLMAP-SfM (pycolmap, SIFT-GPU, exhaustive, Mapper) fuer die iPhone-Fotos; GPU von Anfang an (Nutzerregel)."""
import sys, os, pycolmap, time
img, w = sys.argv[1], sys.argv[2]; os.makedirs(w, exist_ok=True); db = f"{w}/db.db"; t = time.time()
# Vor dem Lauf: defekte Bilder nach quarantaene/ verschieben (Lehre Schwabentor 13.11.: 0-Byte-Datei brach erst im Lauf auf).
import subprocess
subprocess.run(["/media/oem/scan/venv-seg/bin/python", "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fotos_pruefen.py"), img], check=False)
so = pycolmap.FeatureExtractionOptions(); so.sift.max_num_features = 6400; so.max_image_size = 2400
# Cache: Merkmale und Paare aus einem frueheren Lauf wiederverwenden, wenn die Datenbank genau diese Fotos enthaelt (keine Qualitaetsaenderung).
import sqlite3
_n_fotos = len([f for f in os.listdir(img) if os.path.isfile(os.path.join(img, f))])
_db_ok = False
if os.path.exists(db):
    try:
        _c = sqlite3.connect(db); _ni = _c.execute("SELECT COUNT(*) FROM images").fetchone()[0]; _nm = _c.execute("SELECT COUNT(*) FROM two_view_geometries").fetchone()[0]; _c.close()
        _db_ok = (_ni == _n_fotos and _nm > 0)
    except Exception:
        _db_ok = False
if _db_ok:
    print(f"Merkmale und Paare aus Cache ({_ni} Bilder, {_nm} Paare)", flush=True)
else:
    pycolmap.extract_features(db, img, camera_mode=pycolmap.CameraMode.PER_IMAGE, extraction_options=so, device=pycolmap.Device.cuda); print("Merkmale", time.time() - t, flush=True)
    pycolmap.match_exhaustive(db, device=pycolmap.Device.cuda); print("Abgleich", time.time() - t, flush=True)
os.makedirs(f"{w}/sparse", exist_ok=True)
# Mapper: COLMAP-Binaerdatei mit CUDA (GPU-Bündelausgleich, BundleAdjustmentCeres.use_gpu). Die pycolmap-Python-Bibliothek hat keine GPU-Ceres.
COLMAP_BIN = "/media/oem/scan/colmap-build/prefix/bin/colmap"
_env = dict(os.environ, LD_LIBRARY_PATH=":".join(["/media/oem/scan/cuda-toolkit-combo/lib64", "/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib", "/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib", "/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib"]))
# ein Thread: reproduzierbare Anzahl eingehaengter Bilder (Messung 13.11.: Mehrthread 181/149/181/21, Einthread 181/181); Qualitaet vor Tempo
subprocess.run([COLMAP_BIN, "mapper", "--database_path", db, "--image_path", img, "--output_path", f"{w}/sparse",
                "--Mapper.num_threads", "1", "--Mapper.ba_use_gpu", "1", "--Mapper.ba_gpu_index", "0", "--Mapper.ba_max_num_images_direct_dense_gpu_solver", "0"], env=_env, check=True)
rec = {k: pycolmap.Reconstruction(os.path.join(f"{w}/sparse", k)) for k in sorted(os.listdir(f"{w}/sparse")) if k.isdigit()}
for k, r in rec.items(): print(k, r.summary(), flush=True)
