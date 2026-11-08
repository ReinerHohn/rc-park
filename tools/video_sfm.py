#!/usr/bin/env python3
"""video_sfm.py - SfM aus Video-Frames (Drohnenclips) mit MASKE fuer feste Einblendungen (Wasserzeichen) (Register BQ).

Ein ortsfestes Wasserzeichen wird von SIFT in jedem Frame an derselben Bildstelle gefunden und von COLMAP als starrer Punkt (Pose = 0) gematcht -> verklebt Frames, verbiegt das Netz.
Darum Maske (COLMAP: <bild>.png neben mask_path, 0 = ignorieren). Eine Kamera je Clip (Ordner), Intrinsik je Clip gemeinsam.
  /media/oem/scan/venv-colmap/bin/python -I tools/video_sfm.py <frames_wurzel> <ausgabe> --clips id1 id2 ... [--maske-kreis 0.5 0.5 0.075] [--cpu]
  --maske-kreis cx cy r  (Anteile von Breite/Hoehe bzw. Breite): Wasserzeichenkreis
"""
import sys, os, glob, shutil, argparse, json, numpy as np, cv2, pycolmap

def waehle(fs, n, manifest):
    """n Frames: Zeitreihenfolge in n gleich grosse Fenster, je Fenster der schaerfste Frame (Zeitabstand ergibt sich aus den Fenstern)."""
    sh = {}
    if os.path.exists(manifest):
        try: sh = {os.path.basename(f["file"]): float(f["sharpness"]) for f in json.load(open(manifest)).get("frames", []) if "sharpness" in f}
        except Exception: sh = {}
    def schaerfe(f):
        b = os.path.basename(f)
        if b in sh: return sh[b]
        g = cv2.imread(f, 0); return float(cv2.Laplacian(g, cv2.CV_64F).var()) if g is not None else 0.0
    out = []
    for k in range(n):
        w = fs[k * len(fs) // n:(k + 1) * len(fs) // n]
        if w: out.append(max(w, key=schaerfe))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("wurzel"); ap.add_argument("aus"); ap.add_argument("--clips", nargs="+", required=True)
    ap.add_argument("--maske-kreis", nargs=3, type=float, default=[0.5, 0.5, 0.075]); ap.add_argument("--cpu", action="store_true"); ap.add_argument("--masken-vorlage", help="Ordner mit <clip>/<frame>.png (255 benutzen, 0 ignorieren) aus video_masken.py; wird mit der Wasserzeichenmaske UND-verknuepft"); ap.add_argument("--kamera", default="OPENCV", help="COLMAP-Kameramodell; Standard OPENCV (k1,k2 + Tangential): Tiefenversatz der Drohnenclips RMS 0,88 -> 0,28 m gegenueber SIMPLE_RADIAL (Register BU, EIN Lauf)"); ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--max-frames-je-clip", type=int, default=0, help="je Clip hoechstens N Frames: gleichmaessige Zeitfenster, darin der schaerfste Frame (manifest.json 'sharpness', sonst Laplace-Varianz); 0 = alle (Register CR)")
    ap.add_argument("--matching", default="exhaustiv", choices=["exhaustiv", "sequenziell"], help="exhaustiv (Standard, Martinstor-Weg) | sequenziell = pycolmap match_sequential overlap 10 + Retrieval (Vokabelbaum, loop_detection) wenn Vokabelbaum-Datei da ist (Register CR)"); ap.add_argument("--overlap", type=int, default=10)
    a = ap.parse_args(); bild = os.path.join(a.aus, "bilder"); mask = os.path.join(a.aus, "masken"); sp = os.path.join(a.aus, "sparse"); db = os.path.join(a.aus, "db.db")
    for d in (bild, mask): shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    shutil.rmtree(sp, ignore_errors=True); os.makedirs(sp)
    if os.path.exists(db): os.remove(db)
    n = 0
    for c in a.clips:
        os.makedirs(os.path.join(bild, c)); os.makedirs(os.path.join(mask, c))
        fs = sorted(glob.glob(os.path.join(a.wurzel, c, "vf_*.jpg")))
        if a.max_frames: fs = fs[:a.max_frames]
        if a.max_frames_je_clip and len(fs) > a.max_frames_je_clip: fs = waehle(fs, a.max_frames_je_clip, os.path.join(a.wurzel, c, "manifest.json"))
        for f in fs:
            im = cv2.imread(f); h, w = im.shape[:2]; cv2.imwrite(os.path.join(bild, c, os.path.basename(f)), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
            m = np.full((h, w), 255, np.uint8); cv2.circle(m, (int(a.maske_kreis[0] * w), int(a.maske_kreis[1] * h)), int(a.maske_kreis[2] * w), 0, -1)
            if a.masken_vorlage:
                vp = os.path.join(a.masken_vorlage, c, os.path.basename(f) + ".png"); vm = cv2.imread(vp, 0) if os.path.exists(vp) else None
                if vm is not None:
                    if vm.shape != m.shape: vm = cv2.resize(vm, (w, h), interpolation=cv2.INTER_NEAREST)
                    m = np.minimum(m, vm)
            cv2.imwrite(os.path.join(mask, c, os.path.basename(f) + ".png"), m); n += 1
    print(f"{n} Frames, Maske Kreis {a.maske_kreis}", flush=True)
    ro = pycolmap.ImageReaderOptions(); ro.camera_model = a.kamera; ro.mask_path = mask
    gpu = (not a.cpu) and pycolmap.has_cuda
    if not a.cpu and not gpu: print("WARNUNG: pycolmap ohne CUDA - SIFT/Matching laufen auf der CPU", flush=True)
    dev = pycolmap.Device.cuda if gpu else pycolmap.Device.cpu; print("SIFT/Matching auf", "GPU" if gpu else "CPU", flush=True)
    pycolmap.extract_features(db, bild, camera_mode=pycolmap.CameraMode.PER_FOLDER, reader_options=ro, device=dev)
    if a.matching == "exhaustiv": pycolmap.match_exhaustive(db, device=dev)
    else:
        po = pycolmap.SequentialPairingOptions(); po.overlap = a.overlap; vt = sorted(glob.glob(os.path.expanduser("~/.cache/colmap/*vocab_tree*.bin")))
        if vt: po.loop_detection = True; po.vocab_tree_path = vt[0]; po.loop_detection_period = 10; po.loop_detection_num_images = 30
        print(f"Matching sequenziell (overlap {a.overlap}) + {'Retrieval ' + os.path.basename(vt[0])[-40:] if vt else 'OHNE Retrieval (kein Vokabelbaum in ~/.cache/colmap)'}", flush=True)
        pycolmap.match_sequential(db, pairing_options=po, device=dev)
    karten = pycolmap.incremental_mapping(db, bild, sp)
    out = []
    for k, r in sorted(karten.items(), key=lambda kv: -kv[1].num_reg_images()):
        pro_clip = {}
        for im in r.images.values(): pro_clip[im.name.split("/")[0]] = pro_clip.get(im.name.split("/")[0], 0) + 1
        out.append(dict(modell=k, bilder=r.num_reg_images(), punkte=r.num_points3D(), reproj_px=round(r.compute_mean_reprojection_error(), 2), je_clip=pro_clip))
    for o in out: print(o)
    json.dump(dict(frames=n, clips=a.clips, matching=a.matching, max_frames_je_clip=a.max_frames_je_clip, modelle=out), open(os.path.join(a.aus, "ergebnis.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
