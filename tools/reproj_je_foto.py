#!/usr/bin/env python3
"""reproj_je_foto.py - Reprojektionsfehler JE FOTO aus einem COLMAP-Modell (Kamera-Qualitaet; Nutzerauftrag 7.11.).
  /media/oem/scan/venv-colmap/bin/python -I tools/reproj_je_foto.py SPARSE_DIR [--aus bericht.json]
Je registriertem Bild: Zahl der Beobachtungen (Punkte3D), mittlerer/Median/p90 Reprojektionsfehler in Pixel (Bildebene, mit Kameramodell), mittlere Strahltiefe.
Ausreisser-Kameras: Median > 3 x Median aller Bilder oder p90 > 3 px oder < 100 Beobachtungen. Nur Lesen, aendert keine Kamera."""
import sys, json, argparse, numpy as np, pycolmap
ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("--aus"); a = ap.parse_args()
R = pycolmap.Reconstruction(a.sparse); rows = []
for iid, im in R.images.items():
    if not im.has_pose: continue
    cam = R.cameras[im.camera_id]; err = []; tief = []
    for p in im.points2D:
        if not p.has_point3D(): continue
        X = R.points3D[p.point3D_id].xyz; uv = im.cam_from_world() * X
        if uv[2] <= 0: continue
        pr = cam.img_from_cam(uv); err.append(float(np.linalg.norm(np.asarray(pr) - p.xy))); tief.append(float(uv[2]))
    if not err: rows.append(dict(name=im.name, n=0)); continue
    e = np.array(err); rows.append(dict(name=im.name, n=len(e), mittel=round(float(e.mean()), 3), median=round(float(np.median(e)), 3), p90=round(float(np.percentile(e, 90)), 3), tiefe_med=round(float(np.median(tief)), 1)))
med_all = float(np.median([r["median"] for r in rows if r.get("n", 0) > 0]))
for r in rows:
    r["ausreisser"] = bool(r.get("n", 0) < 100 or r.get("median", 0) > 3 * med_all or r.get("p90", 0) > 3.0)
print(f"Bilder {len(rows)}, Median-aller-Mediane {med_all:.2f} px, Ausreisser {sum(r['ausreisser'] for r in rows)}")
for r in sorted(rows, key=lambda r: -r.get("p90", 99))[:15]: print(r)
if a.aus: json.dump(rows, open(a.aus, "w"), indent=1)
