#!/usr/bin/env python3
"""video_sfm.py - SfM aus Video-Frames (Drohnenclips) mit MASKE fuer feste Einblendungen (Wasserzeichen) (Register BQ).

Ein ortsfestes Wasserzeichen wird von SIFT in jedem Frame an derselben Bildstelle gefunden und von COLMAP als starrer Punkt (Pose = 0) gematcht -> verklebt Frames, verbiegt das Netz.
Darum Maske (COLMAP: <bild>.png neben mask_path, 0 = ignorieren). Eine Kamera je Clip (Ordner), Intrinsik je Clip gemeinsam.
  /media/oem/scan/venv-colmap/bin/python -I tools/video_sfm.py <frames_wurzel> <ausgabe> --clips id1 id2 ... [--maske-kreis 0.5 0.5 0.075] [--cpu]
  --maske-kreis cx cy r  (Anteile von Breite/Hoehe bzw. Breite): Wasserzeichenkreis
"""
import sys, os, glob, shutil, argparse, json, numpy as np, cv2, pycolmap

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("wurzel"); ap.add_argument("aus"); ap.add_argument("--clips", nargs="+", required=True)
    ap.add_argument("--maske-kreis", nargs=3, type=float, default=[0.5, 0.5, 0.075]); ap.add_argument("--cpu", action="store_true"); ap.add_argument("--kamera", default="SIMPLE_RADIAL", help="COLMAP-Kameramodell; OPENCV/FULL_OPENCV = k1,k2 + Tangential gegen Doming (Register BU)"); ap.add_argument("--max-frames", type=int, default=0)
    a = ap.parse_args(); bild = os.path.join(a.aus, "bilder"); mask = os.path.join(a.aus, "masken"); sp = os.path.join(a.aus, "sparse"); db = os.path.join(a.aus, "db.db")
    for d in (bild, mask): shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    shutil.rmtree(sp, ignore_errors=True); os.makedirs(sp)
    if os.path.exists(db): os.remove(db)
    n = 0
    for c in a.clips:
        os.makedirs(os.path.join(bild, c)); os.makedirs(os.path.join(mask, c))
        fs = sorted(glob.glob(os.path.join(a.wurzel, c, "vf_*.jpg")))
        if a.max_frames: fs = fs[:a.max_frames]
        for f in fs:
            im = cv2.imread(f); h, w = im.shape[:2]; cv2.imwrite(os.path.join(bild, c, os.path.basename(f)), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
            m = np.full((h, w), 255, np.uint8); cv2.circle(m, (int(a.maske_kreis[0] * w), int(a.maske_kreis[1] * h)), int(a.maske_kreis[2] * w), 0, -1)
            cv2.imwrite(os.path.join(mask, c, os.path.basename(f) + ".png"), m); n += 1
    print(f"{n} Frames, Maske Kreis {a.maske_kreis}", flush=True)
    ro = pycolmap.ImageReaderOptions(); ro.camera_model = a.kamera; ro.mask_path = mask
    gpu = (not a.cpu) and pycolmap.has_cuda
    if not a.cpu and not gpu: print("WARNUNG: pycolmap ohne CUDA - SIFT/Matching laufen auf der CPU", flush=True)
    dev = pycolmap.Device.cuda if gpu else pycolmap.Device.cpu; print("SIFT/Matching auf", "GPU" if gpu else "CPU", flush=True)
    pycolmap.extract_features(db, bild, camera_mode=pycolmap.CameraMode.PER_FOLDER, reader_options=ro, device=dev)
    pycolmap.match_exhaustive(db, device=dev)
    karten = pycolmap.incremental_mapping(db, bild, sp)
    out = []
    for k, r in sorted(karten.items(), key=lambda kv: -kv[1].num_reg_images()):
        pro_clip = {}
        for im in r.images.values(): pro_clip[im.name.split("/")[0]] = pro_clip.get(im.name.split("/")[0], 0) + 1
        out.append(dict(modell=k, bilder=r.num_reg_images(), punkte=r.num_points3D(), reproj_px=round(r.compute_mean_reprojection_error(), 2), je_clip=pro_clip))
    for o in out: print(o)
    json.dump(dict(frames=n, clips=a.clips, modelle=out), open(os.path.join(a.aus, "ergebnis.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
