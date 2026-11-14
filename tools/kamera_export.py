#!/usr/bin/env python3
"""kamera_export.py <sparse_modell> <ausgabe.json> - Kameras eines COLMAP-Modells in eine JSON-Datei (ohne pycolmap im Rechenschritt).

Zweck: pycolmap liegt in einer anderen Python-Umgebung als torch (GPU). Dieses Werkzeug laeuft in venv-colmap und
schreibt Name, Kamera-Id, Pose (R, t), Projektionszentrum und Kameraparameter je Bild. sfm_lod2_ausrichten.py kann dann
mit --kameras in der GPU-Umgebung laufen.
  /media/oem/scan/venv-colmap/bin/python -I tools/kamera_export.py <sparse> <ausgabe.json>
"""
import sys, json
import numpy as np
import pycolmap

def main():
    sparse, out = sys.argv[1], sys.argv[2]
    rec = pycolmap.Reconstruction(sparse)
    bilder = []
    for im in rec.images.values():
        cw = im.cam_from_world()
        bilder.append({"name": im.name, "cam": int(im.camera_id),
                       "R": np.asarray(cw.rotation.matrix()).tolist(), "t": np.asarray(cw.translation).tolist(),
                       "C": np.asarray(im.projection_center()).tolist()})
    kameras = {}
    for cid, cam in rec.cameras.items():
        kameras[str(cid)] = {"K": np.asarray(cam.calibration_matrix()).tolist(), "params": [float(v) for v in cam.params], "model": cam.model.name,
                             "width": int(cam.width), "height": int(cam.height)}
    json.dump({"bilder": bilder, "kameras": kameras}, open(out, "w"))
    print(f"{len(bilder)} Bilder, {len(kameras)} Kameramodelle -> {out}")

if __name__ == "__main__":
    main()
