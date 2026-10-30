#!/usr/bin/env python3
"""
colmap_gpu.py — Bilder -> dichte Punktwolke -> Mesh, maximal auf der GPU (pycolmap-cuda12).

  GPU:  SIFT-Extraktion, SIFT-Matching (sequentiell + Vokabelbaum), PatchMatch-Stereo
  CPU:  GLOMAP (globales SfM, viel schneller als inkrementell), Fusion, Poisson-Mesh

Meshroom rechnet das Matching nur auf der CPU — hier laeuft es auf der RTX.
Bilder in Unterordnern = je Ordner eine Kamera (z.B. ein Ordner pro Video); Einzelfotos
liegen am besten je in einem eigenen Ordner (eigene Brennweite).

Installation (einmalig, ~360 MB, im RAM weil Linux-Root voll):
  python3 -m venv --system-site-packages /dev/shm/venv-colmap
  /dev/shm/venv-colmap/bin/pip install --no-cache-dir pycolmap-cuda12

  /dev/shm/venv-colmap/bin/python colmap_gpu.py <bilder-ordner> <arbeits-ordner> [--max-size 2000]
"""
import argparse, os, shutil, time
# pycolmap-Wheel bringt kein CA-Bundle mit -> Vokabelbaum-Download scheitert sonst (Curl SSL 77)
os.environ.setdefault("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt")
import pycolmap

def t(msg, t0=[time.time()]):
    print(f"[{(time.time()-t0[0])/60:5.1f} min] {msg}", flush=True)

ap = argparse.ArgumentParser()
ap.add_argument("images"); ap.add_argument("work")
ap.add_argument("--max-size", type=int, default=2000, help="max Bildkante fuer PatchMatch")
ap.add_argument("--overlap", type=int, default=15, help="sequentielle Nachbarn")
a = ap.parse_args()
assert pycolmap.has_cuda, "pycolmap ohne CUDA - pycolmap-cuda12 installieren"
os.makedirs(a.work, exist_ok=True)
db = os.path.join(a.work, "database.db")

# Flacher Ordner (z.B. webfotos.py: video_frames/<VideoID>_0001.jpg)? -> je Video ein Unterordner
# per Symlink, damit jedes Video eine eigene Kamera bekommt (Commons-Fotos: je Foto eine Kamera)
if not any(e.is_dir() for e in os.scandir(a.images)):
    grp = os.path.join(a.work, "bilder")
    for f in sorted(os.listdir(a.images)):
        if not f.lower().endswith((".jpg", ".jpeg", ".png")): continue
        stem = os.path.splitext(f)[0]
        cam = stem.rsplit("_", 1)[0] if "_" in stem else stem
        os.makedirs(os.path.join(grp, cam), exist_ok=True)
        dst = os.path.join(grp, cam, f)
        if not os.path.lexists(dst): os.symlink(os.path.abspath(os.path.join(a.images, f)), dst)
    t(f"flacher Ordner -> {len(os.listdir(grp))} Kameras in {grp}")
    a.images = grp
sparse, dense = os.path.join(a.work, "sparse"), os.path.join(a.work, "dense")

if not os.path.exists(db):
    t("SIFT-Extraktion (GPU)")
    ext = pycolmap.FeatureExtractionOptions(); ext.sift.max_num_features = 8192
    pycolmap.extract_features(db, a.images, camera_mode=pycolmap.CameraMode.PER_FOLDER,
                              extraction_options=ext, device=pycolmap.Device.cuda)
matched = os.path.join(a.work, ".matching_fertig")
if not os.path.exists(matched):  # bereits gematchte Paare ueberspringt COLMAP -> Neustart setzt hier fort
    t("Matching sequentiell (GPU)")
    seq = pycolmap.SequentialPairingOptions(); seq.overlap = a.overlap; seq.quadratic_overlap = True
    pycolmap.match_sequential(db, pairing_options=seq, device=pycolmap.Device.cuda)
    t("Matching Vokabelbaum (GPU) - verbindet Videos/Fotos untereinander")
    try:
        vt = pycolmap.VocabTreePairingOptions(); vt.num_images = 60
        pycolmap.match_vocabtree(db, pairing_options=vt, device=pycolmap.Device.cuda)
    except Exception as e:
        t(f"Vokabelbaum fehlgeschlagen ({e}) -> exhaustive")
        pycolmap.match_exhaustive(db, device=pycolmap.Device.cuda)
    open(matched, "w").close()

if not os.path.exists(os.path.join(sparse, "0")):
    t("GLOMAP globales SfM")
    os.makedirs(sparse, exist_ok=True)
    try:
        recs = pycolmap.global_mapping(db, a.images, sparse)
    except Exception as e:
        t(f"GLOMAP fehlgeschlagen ({e}) -> inkrementell")
        recs = pycolmap.incremental_mapping(db, a.images, sparse)
    best = max(recs.values(), key=lambda r: r.num_reg_images())
    for k, r in recs.items():
        t(f"  Modell {k}: {r.num_reg_images()} Bilder, {r.num_points3D()} Punkte")
    # groesstes Modell nach sparse/0 legen
    bk = [k for k, r in recs.items() if r is best][0]
    if bk != 0:
        shutil.move(os.path.join(sparse, "0"), os.path.join(sparse, "0_alt")) if os.path.exists(os.path.join(sparse, "0")) else None
        best.write(os.path.join(sparse, "0"))
rec = pycolmap.Reconstruction(os.path.join(sparse, "0"))
t(f"Rekonstruktion: {rec.num_reg_images()} / {rec.num_images()} Bilder ausgerichtet, {rec.num_points3D()} Punkte")

if not os.path.exists(os.path.join(dense, "fused.ply")):
    t("Entzerren")
    uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = a.max_size
    pycolmap.undistort_images(dense, os.path.join(sparse, "0"), a.images, undistort_options=uo)
    t("PatchMatch-Stereo (GPU)")
    pm = pycolmap.PatchMatchOptions(); pm.max_image_size = a.max_size; pm.geom_consistency = True
    pycolmap.patch_match_stereo(dense, options=pm)
    t("Fusion")
    pycolmap.stereo_fusion(os.path.join(dense, "fused.ply"), dense)
t("Poisson-Mesh")
po = pycolmap.PoissonMeshingOptions(); po.depth = 11; po.trim = 7
pycolmap.poisson_meshing(os.path.join(dense, "fused.ply"), os.path.join(a.work, "mesh.ply"), options=po)
t(f"fertig: {a.work}/mesh.ply (+ dense/fused.ply)")
