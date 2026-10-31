#!/usr/bin/env python3
"""foto_vggt_test.py - NUR TEST (VGGT-1B ist CC BY-NC 4.0, siehe modelle/LIZENZ_WERKZEUGE.md).
Rekonstruiert aus mehreren Martinstor-Fotos mit VGGT Kameras + Punktwolke, legt die Wolke per Aehnlichkeitstransformation
(Massstab, Drehung, Verschiebung; Kamerahoehe/Gesamthoehe als Anker) an das Modell und schreibt Abweichungen je Hoehe.

  /media/oem/scan/venv-seg/bin/python -I tools/foto_vggt_test.py 042 043 044 [...Foto-Nummern]  --out /pfad/ausgabe
"""
import sys, os, glob, json, numpy as np, torch
sys.path[:0] = ["/media/oem/scan/vggt/deps", "/media/oem/scan/vggt/repo"]
from vggt.models.vggt import VGGT
from vggt.utils.load_fn import load_and_preprocess_images
from vggt.utils.pose_enc import pose_encoding_to_extri_intri
from vggt.utils.geometry import unproject_depth_map_to_point_map

FD = "/home/oem/git/rc-park/daten/martinstor/fotos/"
W = "/media/oem/scan/vggt/gewichte/model.safetensors"

def main():
    a = sys.argv[1:]; out = "/tmp/vggt_out"
    if "--out" in a:
        i = a.index("--out"); out = a[i + 1]; a = a[:i] + a[i + 2:]
    nums = [x for x in a if not x.startswith("--")]
    os.makedirs(out, exist_ok=True)
    files = [glob.glob(FD + f"{n}_*")[0] for n in nums]
    dev = "cuda"; dt = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    model = VGGT(); from safetensors.torch import load_file
    model.load_state_dict(load_file(W)); model.eval(); model.aggregator.to(dtype=dt); model.to(dev)
    imgs = load_and_preprocess_images(files).to(dev)
    with torch.no_grad(), torch.autocast("cuda", dtype=dt):
        pred = model(imgs[None])
    ext, intr = pose_encoding_to_extri_intri(pred["pose_enc"], imgs.shape[-2:])
    pts = unproject_depth_map_to_point_map(pred["depth"][0].float().cpu().numpy(), ext[0].float().cpu().numpy(), intr[0].float().cpu().numpy())
    conf = pred["depth_conf"][0].float().cpu().numpy()
    cols = imgs.permute(0, 2, 3, 1).cpu().numpy()
    np.savez_compressed(out + "/vggt.npz", pts=pts, conf=conf, cols=cols, ext=ext[0].float().cpu().numpy(), intr=intr[0].float().cpu().numpy(), files=np.array(files))
    print("Fotos", len(files), "Punkte", pts.shape, "Konfidenz Median", float(np.median(conf)))

if __name__ == "__main__":
    main()
