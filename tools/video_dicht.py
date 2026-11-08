#!/usr/bin/env python3
"""video_dicht.py - dichte Wolke aus dem Video-SfM (video_sfm.py) und Transformation in den Modellrahmen (aus video_ausrichten.py) (Register BQ).
  /media/oem/scan/venv-colmap/bin/python -I tools/video_dicht.py modelle/<objekt>/objekt.json <video_sfm_ordner> [--modell 1] [--max-size 1280]
Ausgabe: <video_sfm_ordner>/dicht/fused.ply, <video_sfm_ordner>/dicht_modell.npy (x y z im Modellrahmen, Meter; Massstab aus dem Nordnetz!) + dicht_farben.npy
"""
import sys, os, json, struct, argparse, numpy as np, pycolmap, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from video_netz import netz_info, video_modell

def ply(fp):
    with open(fp, "rb") as f:
        h = []
        while True:
            l = f.readline().decode("ascii").strip(); h.append(l)
            if l == "end_header": break
        n = int([x for x in h if x.startswith("element vertex")][0].split()[-1]); pr = [x.split()[1:] for x in h if x.startswith("property")]
        dt = np.dtype([(p[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[p[0]]) for p in pr]); return np.frombuffer(f.read(n * dt.itemsize), dtype=dt)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("video"); ap.add_argument("--modell", default="1"); ap.add_argument("--max-size", type=int, default=1280)
    ap.add_argument("--aus", default="video_ausrichtung.json", help="Dateiname unter audit/ mit der Ausrichtung DIESES Videos (wie video_ausrichten.py --aus); ersetzt das Sandbox-Objekt (Plan M1)"); a = ap.parse_args(); a.modell = video_modell(a.video, a.modell)
    od = os.path.dirname(os.path.abspath(a.objekt)); out = os.path.join(a.video, "dicht"); t0 = time.time()
    if not os.path.exists(os.path.join(out, "fused.ply")):
        os.makedirs(out, exist_ok=True); uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = a.max_size
        pycolmap.undistort_images(out, os.path.join(a.video, "sparse", a.modell), os.path.join(a.video, "bilder"), output_type="COLMAP", undistort_options=uo); print(f"entzerrt {time.time() - t0:.0f} s", flush=True)
        opt = pycolmap.PatchMatchOptions(); opt.max_image_size = a.max_size; opt.geom_consistency = True; opt.gpu_index = "0"; pycolmap.patch_match_stereo(out, options=opt); print(f"PatchMatch {time.time() - t0:.0f} s", flush=True)
        pycolmap.stereo_fusion(os.path.join(out, "fused.ply"), out, output_type="ply"); print(f"Fusion {time.time() - t0:.0f} s", flush=True)
    arr = ply(os.path.join(out, "fused.ply")); X = np.c_[arr["x"], arr["y"], arr["z"]].astype(np.float64); C = np.c_[arr["red"], arr["green"], arr["blue"]].astype(np.uint8)
    o = json.load(open(os.path.join(od, "audit", a.aus))); S = json.load(open(netz_info(a.objekt)["ausr"]))["transformation"]
    s, R, t = o["skala_video_zu_nord"], np.array(o["R"]), np.array(o["t"]); Rm = pycolmap.Rotation3d(np.array(S["rvec"])).matrix(); tm = np.array(S["t"])
    Xm = ((s * (X @ R.T) + t - tm) @ Rm) / S["s"]
    np.save(os.path.join(a.video, "dicht_modell.npy"), Xm.astype(np.float32)); np.save(os.path.join(a.video, "dicht_farben.npy"), C)
    try:                                                                         # Clip-Zugehoerigkeit je Punkt (aus fused.ply.vis): Grundlage der Clip-Konsistenzpruefung in video_merge.py (Register BR)
        import struct
        rec = pycolmap.Reconstruction(os.path.join(out, "sparse")); clips = sorted({im.name.split("/")[0] for im in rec.images.values()}); cid = {i: clips.index(im.name.split("/")[0]) for i, im in rec.images.items()}
        b = open(os.path.join(out, "fused.ply.vis"), "rb").read(); n = struct.unpack_from("<Q", b, 0)[0]; off = 8; anz = np.zeros((n, len(clips)), np.uint8)
        for q in range(n):
            kq = struct.unpack_from("<I", b, off)[0]; off += 4
            for i in struct.unpack_from("<%dI" % kq, b, off): anz[q, cid.get(i, 0)] += 1
            off += 4 * kq
        np.save(os.path.join(a.video, "punkt_clips.npy"), anz); json.dump(clips, open(os.path.join(a.video, "punkt_clips.json"), "w"))
    except Exception as e: print("WARNUNG: Clip-Zuordnung nicht erstellt:", e, flush=True)
    k = (np.abs(Xm[:, 0]) < 7) & (np.abs(Xm[:, 1]) < 7); print(f"{len(Xm)} Punkte, nahe Ursprung {k.sum()}" + (f", z p50/p99/max nahe Ursprung: {np.percentile(Xm[k, 2], [50, 99, 100]).round(1)}" if k.sum() else "") + f"; z p1/p50/p99 gesamt: {np.percentile(Xm[:, 2], [1, 50, 99]).round(1)}")

if __name__ == "__main__":
    main()
