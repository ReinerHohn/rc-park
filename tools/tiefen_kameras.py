#!/usr/bin/env python3
"""tiefen_kameras.py - GENERISCH: Kameras eines COLMAP-Dichte-Arbeitsordners (sfm_dicht.py, entzerrte PINHOLE-Bilder) als JSON exportieren,
damit Werkzeuge ohne pycolmap (venv-seg: textur_projektion.py) die Tiefenkarten stereo/depth_maps/<bild>.geometric.bin nutzen koennen.
  /media/oem/scan/venv-colmap/bin/python -I tools/tiefen_kameras.py <arbeitsordner>     -> <arbeitsordner>/kameras_unverzerrt.json
Auch: lies_tiefe(pfad) -> (H, W) float32 (0 = keine Tiefe); COLMAP-Format 'W&H&C&' + float32 spaltenweise.
"""
import sys, os, json, numpy as np


def lies_tiefe(p):
    with open(p, "rb") as f:
        kopf = b""; n = 0
        while n < 3:
            c = f.read(1); kopf += c; n += c == b"&"
        W, H, C = [int(x) for x in kopf.decode().split("&")[:3]]
        a = np.fromfile(f, np.float32)
    return a.reshape((W, H, C), order="F").transpose(1, 0, 2)[:, :, 0]


def main():
    import pycolmap
    ws = sys.argv[1]; r = pycolmap.Reconstruction(os.path.join(ws, "sparse")); out = {}
    for im in r.images.values():
        c = r.cameras[im.camera_id]; p = list(c.params); cw = im.cam_from_world()
        if c.model.name == "PINHOLE": fx, fy, cx, cy = p
        elif c.model.name == "SIMPLE_PINHOLE": fx = fy = p[0]; cx, cy = p[1:3]
        else: sys.exit(f"{im.name}: Kameramodell {c.model.name} - erwartet entzerrte PINHOLE-Bilder")
        out[os.path.splitext(im.name)[0]] = dict(bild=im.name, W=c.width, H=c.height, fx=fx, fy=fy, cx=cx, cy=cy, R=np.asarray(cw.rotation.matrix()).tolist(), t=np.asarray(cw.translation).tolist())
    json.dump(out, open(os.path.join(ws, "kameras_unverzerrt.json"), "w")); print(len(out), "Kameras ->", os.path.join(ws, "kameras_unverzerrt.json"))


if __name__ == "__main__":
    main()
