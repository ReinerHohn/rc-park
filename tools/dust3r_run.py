#!/usr/bin/env python3
"""dust3r_run.py — pose-freie 3D-Rekonstruktion aus WENIGEN unkalibrierten Fotos (DUSt3R, CPU).
Repliziert mini_dust3r.api.inferece_dust3r OHNE rerun (das bricht an numpy 1.26). Gibt Punktwolke
(.ply) + Mesh (.glb). State-of-the-Art statt Parametrik: Geometrie aus den Fotos gemessen.

Lauf: /tmp/ml/bin/python tools/dust3r_run.py <out_prefix> <foto1> <foto2> ...
"""
import sys, copy
import numpy as np
import torch
import trimesh
from mini_dust3r.utils.image import load_images
from mini_dust3r.inference import inference
from mini_dust3r.model import AsymmetricCroCo3DStereo
from mini_dust3r.image_pairs import make_pairs
from mini_dust3r.cloud_opt import global_aligner, GlobalAlignerMode
from mini_dust3r.viz import pts3d_to_trimesh, cat_meshes

out = sys.argv[1]; paths = sys.argv[2:]
dev = "cuda" if torch.cuda.is_available() else "cpu"
print(f"DUSt3R auf {len(paths)} Fotos, device={dev}")
# KEIN globales no_grad — die globale Ausrichtung (PointCloudOptimizer) braucht Gradienten.
model = AsymmetricCroCo3DStereo.from_pretrained("naver/DUSt3R_ViTLarge_BaseDecoder_512_dpt").to(dev)

imgs = load_images(paths, size=512, verbose=True)
if len(imgs) == 1:
    imgs = [imgs[0], copy.deepcopy(imgs[0])]; imgs[1]["idx"] = 1
pairs = make_pairs(imgs, scene_graph="complete", prefilter=None, symmetrize=True)
output = inference(pairs, model, dev, batch_size=1)
mode = GlobalAlignerMode.PointCloudOptimizer if len(imgs) > 2 else GlobalAlignerMode.PairViewer
scene = global_aligner(dust3r_output=output, device=dev, mode=mode)
if mode == GlobalAlignerMode.PointCloudOptimizer:
    scene.compute_global_alignment(init="mst", niter=100, schedule="linear", lr=0.01)

rgb = scene.imgs
pts3d = [p.numpy(force=True) for p in scene.get_pts3d()]
log_conf = scene.conf_trf(torch.tensor(3.0)); scene.min_conf_thr = float(log_conf)
masks = [m.numpy(force=True) for m in scene.get_masks()]
pc = np.concatenate([p[m] for p, m in zip(pts3d, masks)])
col = np.concatenate([c[m] for c, m in zip(rgb, masks)])
trimesh.PointCloud(pc.reshape(-1, 3), colors=(col.reshape(-1, 3) * 255).astype(np.uint8)).export(f"{out}.ply")
meshes = [pts3d_to_trimesh(r, p, m) for r, p, m in zip(rgb, pts3d, masks)]
mesh = trimesh.Trimesh(**cat_meshes(meshes))
mesh.export(f"{out}.glb")
print(f"-> {out}.ply ({len(pc)} Punkte), {out}.glb ({len(mesh.vertices)} Verts, {len(mesh.faces)} Faces)")
