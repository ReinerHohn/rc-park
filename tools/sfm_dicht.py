#!/usr/bin/env python3
"""sfm_dicht.py - dichte, farbige Punktwolke (COLMAP PatchMatch, CUDA) aus einem Seitennetz, ins Modellsystem gebracht und auf den Turm beschnitten.

Zweck: Sichtvergleich Foto-Wolke gegen Modell-STL (nicht Massnachweis - dafuer gelten die Pruefungen der Masstabelle).
Kette: undistort_images -> patch_match_stereo (GPU) -> stereo_fusion -> fused.ply -> Transformation aus SFM-AUSRICHTUNG-<seite>.json
(X_m = R^T (X_sfm - t) / s) -> Beschnitt Zylinder r <= RADIUS um die Turmachse, z in [ZMIN, ZMAX] -> dicht_<seite>_modell.npy (+ _farben.npy).
Schutz (Register BB): Bilder ohne gueltigen Tiefenbereich (Punkte hinter der Kamera = Spiegelloesung, oder keine Punkte) kommen nicht in den
dichten Arbeitsordner (gefiltertes Netz sparse_<seite>/0_dicht), sonst bricht PatchMatch mit 'depth_min > 0' ab (Nullstart 5).
  /media/oem/scan/venv-colmap/bin/python -I tools/sfm_dicht.py modelle/<objekt>/objekt.json <seite> [--radius 25] [--max-size 1600] [--nur-fusion]
Lizenz: COLMAP BSD; Fotos bleiben Messvorlage (Share-Alike-Fotos nicht in den Bausatz).
"""
import sys, os, json, math, argparse, time, shutil, resource, numpy as np, cv2
import pycolmap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from sfm_netz import tiefen
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))            # ein COLMAP-Abbruch darf keinen 1,3-GB-Core-Dump auf die Root-Platte legen (Datenplatten-Regel)

def netz_fuer_dicht(sparse, sd, seite):
    """Netz ohne Bilder, die keinen positiven Tiefenbereich haben (Cheiralitaet; selbes Kriterium wie sfm_netz.bewerten)."""
    rec = pycolmap.Reconstruction(sparse); raus = []
    for im in list(rec.images.values()):
        d = tiefen(rec, im)
        if len(d) == 0 or np.percentile(d, 5) <= 0: raus.append(im.name); rec.deregister_frame(im.frame_id)
    if not raus: return sparse
    ziel = os.path.join(sd, f"sparse_{seite}", "0_dicht"); os.makedirs(ziel, exist_ok=True); rec.write(ziel)
    print(f"ohne Tiefenbereich (Punkte hinter der Kamera/keine Punkte), nicht in der dichten Rekonstruktion: {raus} -> {rec.num_reg_images()} Bilder in {ziel}", flush=True)
    return ziel

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--zmin", type=float, default=-5.0); ap.add_argument("--zmax", type=float, default=85.0); ap.add_argument("--max-size", type=int, default=1600)
    ap.add_argument("--nur-fusion", action="store_true", help="PatchMatch ueberspringen (schon gerechnet)")
    a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt)); sd = os.path.join(od, "sfm")
    sparse = os.path.join(sd, f"sparse_{a.seite}", "0"); bilder = os.path.join(sd, f"sparse_{a.seite}_bilder"); out = os.path.join(sd, f"dicht_{a.seite}")
    S = json.load(open(os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{a.seite}.json"))); tr = S["transformation"]
    if "rvec" not in tr: raise SystemExit("Ausrichtung ohne rvec/t/s (Buendel-Anker-Variante) - zuerst sfm_ausrichten.py --schreiben")
    t0 = time.time()
    if not a.nur_fusion:
        if os.path.isdir(out): shutil.rmtree(out)           # alter Arbeitsordner = andere Kameras -> entzerrte Bilder passen nicht zu den Tiefenkarten (1600 vs 1598 px, Nullstart 6)
        os.makedirs(out, exist_ok=True); sparse = netz_fuer_dicht(sparse, sd, a.seite)
        uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = a.max_size
        pycolmap.undistort_images(out, sparse, bilder, output_type="COLMAP", undistort_options=uo)
        print(f"entzerrt {time.time() - t0:.0f} s", flush=True)
        opt = pycolmap.PatchMatchOptions(); opt.max_image_size = a.max_size; opt.geom_consistency = True; opt.gpu_index = "0"
        pycolmap.patch_match_stereo(out, options=opt); print(f"PatchMatch {time.time() - t0:.0f} s", flush=True)
    ply = os.path.join(out, "fused.ply")
    pycolmap.stereo_fusion(ply, out, output_type="ply"); print(f"Fusion {time.time() - t0:.0f} s", flush=True)
    # PLY lesen (binaer little endian, x y z nx ny nz r g b)
    import struct
    with open(ply, "rb") as f:
        header = [];
        while True:
            line = f.readline().decode("ascii").strip(); header.append(line)
            if line == "end_header": break
        n = int([h for h in header if h.startswith("element vertex")][0].split()[-1]); props = [h.split()[1:] for h in header if h.startswith("property")]
        dt = np.dtype([(p[1], {"float": "<f4", "uchar": "u1", "double": "<f8", "int": "<i4"}[p[0]]) for p in props]); arr = np.frombuffer(f.read(n * dt.itemsize), dtype=dt)
    X = np.c_[arr["x"], arr["y"], arr["z"]].astype(np.float64); C = np.c_[arr["red"], arr["green"], arr["blue"]].astype(np.uint8)
    s = float(tr["s"]); R = cv2.Rodrigues(np.array(tr["rvec"]))[0]; t = np.array(tr["t"])
    Xm = ((X - t) @ R) / s                                   # R^T (X - t) / s
    r = np.hypot(Xm[:, 0], Xm[:, 1]); k = (r <= a.radius) & (Xm[:, 2] >= a.zmin) & (Xm[:, 2] <= a.zmax)
    print(f"dichte Wolke: {len(Xm)} Punkte, davon {k.sum()} im Zylinder r<={a.radius} m, z {a.zmin}..{a.zmax}; z-Bereich {Xm[k, 2].min():.1f}..{Xm[k, 2].max():.1f} m")
    np.save(os.path.join(sd, f"dicht_{a.seite}_modell.npy"), Xm[k].astype(np.float32)); np.save(os.path.join(sd, f"dicht_{a.seite}_farben.npy"), C[k])
    print("geschrieben:", os.path.join(sd, f"dicht_{a.seite}_modell.npy"), f"({time.time() - t0:.0f} s gesamt)")

if __name__ == "__main__":
    main()
