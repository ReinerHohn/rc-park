#!/usr/bin/env python3
"""gs_kaufhaus_netz2.py - wie gs_kaufhaus_netz.py (dort nachlesen), aber: Huelle enger (--huelle-rand, Standard 1,5 m statt 3 m integrieren / 2 m zuschneiden), nur grosse Komponenten behalten (Flaeche >= --komp-min Anteil, Standard 1 %), 2DGS-Checkpoints (ckpt zweid) werden mit rasterization_2dgs gerendert. CUDA-Umgebung per tools/gs_kaufhaus_lauf.sh.
Urspruenglicher Kopf: Netz aus dem trainierten Gaussian Splatting: Tiefenkarten (erwartete Tiefe, Alpha-normiert) aus den Trainingskameras rendern (--modus tiefe, venv-seg + gsplat),
dann TSDF-Fusion (--modus tsdf, venv-o3d, open3d VoxelBlockGrid wie tools/tsdf_netz.py) -> STL in mm (Meter*1000/87), Modellrahmen, nur Huellen-Bereich.
Aufruf: (CUDA_HOME/PATH/TORCH_CUDA_ARCH_LIST setzen)
  venv-seg/bin/python -I tools/gs_kaufhaus_netz.py --modus tiefe --daten DIR [--alpha 0.6] [--kante 0.08]
  venv-o3d/bin/python -I tools/gs_kaufhaus_netz.py --modus tsdf --daten DIR --huelle modelle/stl/kaufhaus_null5_1-87.stl --aus out.stl [--voxel 0.05] [--trunc 0.25] [--tiefe-max 60] [--gewicht 2]
Kameras = K-Kameras plus gelernte Korrektur (ckpt 'pose'); Tiefen in DIR/tiefe/<nr>.npy (float32, 0 = ungueltig), DIR/kameras_gs.json."""
import os, sys, json, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("--modus", required=True, choices=["tiefe", "tsdf"]); ap.add_argument("--daten", required=True); ap.add_argument("--alpha", type=float, default=0.6)
ap.add_argument("--kante", type=float, default=0.08, help="Tiefensprung relativ zur Tiefe zwischen Nachbarpixeln -> ungueltig (fliegende Pixel)"); ap.add_argument("--huelle"); ap.add_argument("--aus"); ap.add_argument("--voxel", type=float, default=0.05)
ap.add_argument("--trunc", type=float, default=0.25); ap.add_argument("--tiefe-max", type=float, default=60.0); ap.add_argument("--massstab", type=float, default=87); ap.add_argument("--gewicht", type=float, default=2.0); ap.add_argument("--ohne-pose", action="store_true"); ap.add_argument("--huelle-rand", type=float, default=1.5); ap.add_argument("--komp-min", type=float, default=0.01); a = ap.parse_args(); D = a.daten
if a.modus == "tiefe":
    import torch, torch.nn.functional as Fn
    from gsplat import rasterization, rasterization_2dgs
    ck = torch.load(os.path.join(D, "gs_ckpt.pt")); p = {k: v.cuda() for k, v in ck["params"].items()}; cams = json.load(open(os.path.join(D, "kameras.json"))); os.makedirs(os.path.join(D, "tiefe"), exist_ok=True); out = {}
    def rodr(w):
        th = w.norm() + 1e-12; k = w / th; Kx = torch.zeros(3, 3)
        Kx[0, 1], Kx[0, 2], Kx[1, 0], Kx[1, 2], Kx[2, 0], Kx[2, 1] = -k[2], k[1], k[2], -k[0], -k[1], k[0]; return torch.eye(3) + torch.sin(th) * Kx + (1 - torch.cos(th)) * Kx @ Kx
    for i, n in enumerate(ck["nrs"]):
        c = cams[n]; M = torch.eye(4); M[:3, :3] = torch.tensor(c["R"], dtype=torch.float32); M[:3, 3] = torch.tensor(c["t"], dtype=torch.float32)
        if not a.ohne_pose:
            T = torch.eye(4); T[:3, :3] = rodr(ck["pose"][i][:3]); T[:3, 3] = ck["pose"][i][3:]; M = T @ M
        Km = torch.tensor([[c["f"], 0, c["cx"]], [0, c["f"], c["cy"]], [0, 0, 1]], dtype=torch.float32)
        with torch.no_grad():
            ar = (p["means"], Fn.normalize(p["quats"], dim=-1), torch.exp(p["scales"]), torch.sigmoid(p["opacities"]), torch.cat([p["sh0"], p["shN"]], 1), M[None].cuda(), Km[None].cuda(), c["W"], c["H"])
            if ck.get("zweid"): col, al = rasterization_2dgs(*ar, sh_degree=3, render_mode="RGB+ED")[:2]
            else: col, al, _ = rasterization(*ar, sh_degree=3, render_mode="RGB+ED")
        d = col[0, ..., 3].cpu().numpy().copy(); al = al[0, ..., 0].cpu().numpy(); d[al < a.alpha] = 0
        for ax in (0, 1):                                                                           # Tiefensprung-Filter gegen fliegende Pixel an Silhouetten
            g = np.abs(np.diff(d, axis=ax, prepend=d[:1] if ax == 0 else d[:, :1])); r = g > a.kante * np.maximum(d, 1e-3); d[r] = 0
        np.save(os.path.join(D, "tiefe", f"{n}.npy"), d.astype(np.float32)); out[n] = dict(M=M.numpy()[:3].tolist(), K=[c["f"], c["f"], c["cx"], c["cy"]], W=c["W"], H=c["H"], gueltig=float((d > 0).mean()))
        print(n, "gueltig %.2f" % out[n]["gueltig"], "Pose", np.round(ck["pose"][i].numpy(), 3).tolist(), flush=True)
    json.dump(out, open(os.path.join(D, "kameras_gs.json"), "w")); sys.exit(0)
import open3d as o3d, open3d.core as o3c, trimesh
cams = json.load(open(os.path.join(D, "kameras_gs.json"))); dev = o3c.Device("CPU:0")
vbg = o3d.t.geometry.VoxelBlockGrid(attr_names=("tsdf", "weight"), attr_dtypes=(o3c.float32, o3c.float32), attr_channels=((1), (1)), voxel_size=a.voxel, block_resolution=16, block_count=200000, device=dev)
n = 0; hb0 = trimesh.load(a.huelle).bounds * (a.massstab / 1000.0)   # nur Tiefen innerhalb Huelle +3 m integrieren (Speicher, Fliegerpixel/Boden/Himmel weg)
for nr, c in cams.items():
    d = np.load(os.path.join(D, "tiefe", f"{nr}.npy")); d = np.where((d > 0) & (d < a.tiefe_max), d, 0).astype(np.float32); fx, fy, cx, cy = c["K"]
    Mm = np.array(c["M"] + [[0, 0, 0, 1]]); uu, vv = np.meshgrid(np.arange(d.shape[1]), np.arange(d.shape[0])); Xc = np.stack([(uu - cx) / fx * d, (vv - cy) / fy * d, d], -1).reshape(-1, 3); Xw = (Xc - Mm[:3, 3]) @ Mm[:3, :3]
    d = np.where(np.all((Xw >= hb0[0] - a.huelle_rand) & (Xw <= hb0[1] + a.huelle_rand), 1).reshape(d.shape), d, 0).astype(np.float32)
    if not (d > 0).any(): print("keine Tiefe in Huelle:", nr); continue
    K = o3c.Tensor(np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], np.float64)); E = o3c.Tensor(np.array(c["M"] + [[0, 0, 0, 1]], np.float64)); dep = o3d.t.geometry.Image(o3c.Tensor(np.ascontiguousarray(d)))
    blk = vbg.compute_unique_block_coordinates(dep, K, E, 1.0, a.tiefe_max); vbg.integrate(blk, dep, K, E, 1.0, a.tiefe_max, a.trunc / a.voxel); n += 1
print("integriert", n, "Tiefenkarten", flush=True)
m = vbg.extract_triangle_mesh(weight_threshold=a.gewicht).to_legacy(); V = np.asarray(m.vertices); print("roh", len(V), "Eckpunkte", len(m.triangles), "Dreiecke", flush=True)
k = a.massstab / 1000.0; hb = trimesh.load(a.huelle).bounds * k; ok = np.all((V >= hb[0] - a.huelle_rand) & (V <= hb[1] + a.huelle_rand), 1); f = np.asarray(m.triangles); fk = ok[f].all(1)
t = trimesh.Trimesh(V, f[fk], process=False); t.remove_unreferenced_vertices(); ges = t.area; teile = t.split(only_watertight=False); beh = [q for q in teile if q.area >= a.komp_min * ges]; print("Komponenten", len(teile), "behalten", len(beh), "Flaeche behalten %.3f" % (sum(q.area for q in beh) / ges), flush=True)
t = trimesh.util.concatenate(beh); t.vertices = t.vertices / k; t.export(a.aus); print(a.aus, len(t.faces), "Dreiecke, wasserdicht", t.is_watertight)
