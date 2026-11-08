#!/usr/bin/env python3
"""tsdf_netz.py - TSDF-Fusion aus COLMAP-Tiefenkarten (geometric.bin) + Posen -> Netz (open3d), Modellrahmen, STL mm. Kandidat fuer tools/modell_wettbewerb.py.
  venv-o3d/bin/python -I tools/tsdf_netz.py --dicht DIR --kameras kameras.json --ausrichtung A.json --huelle M.stl --aus out.stl [--voxel 0.05] [--trunc 0.25] [--tiefe-max 60] [--massstab 87]"""
import argparse, json, os, numpy as np, open3d as o3d, trimesh, cv2
ap = argparse.ArgumentParser(); [ap.add_argument(f"--{k}", required=True) for k in ("dicht", "kameras", "ausrichtung", "huelle", "aus")]
ap.add_argument("--voxel", type=float, default=0.05); ap.add_argument("--trunc", type=float, default=0.25); ap.add_argument("--tiefe-max", type=float, default=60.0); ap.add_argument("--massstab", type=float, default=87); ap.add_argument("--art", default="geometric"); a = ap.parse_args()
def dmap(p):
    with open(p, "rb") as f:
        w, h, c = (int(x) for x in [bytes(), ][0:0] or [0, 0, 0]) if False else (0, 0, 0)
        b = f.read(); i = 0; hd = []; amp = 0
        while amp < 3: amp += b[i:i + 1] == b"&"; i += 1
        w, h, c = (int(x) for x in b[:i].decode().strip("&").split("&")[:3]); return np.frombuffer(b[i:], np.float32).reshape(c, h, w, order="F").transpose(1, 2, 0)[..., 0] if False else np.frombuffer(b[i:], np.float32).reshape((w, h, c), order="F").transpose(1, 0, 2)[..., 0]
cams = json.load(open(a.kameras)); tr = json.load(open(a.ausrichtung))["transformation"]; s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float)
import open3d.core as o3c
dev = o3c.Device("CPU:0")
vbg = o3d.t.geometry.VoxelBlockGrid(attr_names=("tsdf", "weight"), attr_dtypes=(o3c.float32, o3c.float32), attr_channels=((1), (1)), voxel_size=a.voxel * s, block_resolution=16, block_count=400000, device=dev)   # Tensor-API (die klassische ScalableTSDFVolume lieferte in open3d 0.20 auch fuer eine Testebene kein Netz)
print('Massstab s (COLMAP-Einheiten je Meter):', s, flush=True); n = 0
for name, c in cams.items():
    p = os.path.join(a.dicht, "stereo", "depth_maps", f"{name}.{a.art}.bin")
    if not os.path.exists(p): continue
    d = dmap(p); H, W = c["H"], c["W"]
    if d.shape != (H, W): d = cv2.resize(d, (W, H), interpolation=cv2.INTER_NEAREST)
    d = np.where((d > 0) & (d < a.tiefe_max * s), d, 0).astype(np.float32); fx, fy, cx, cy = c["K"]
    K = o3c.Tensor(np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], np.float64)); E = o3c.Tensor(np.array(c["M"] + [[0, 0, 0, 1]], np.float64)[:4]); dep = o3d.t.geometry.Image(o3c.Tensor(np.ascontiguousarray(d)))
    blk = vbg.compute_unique_block_coordinates(dep, K, E, 1.0, a.tiefe_max * s); vbg.integrate(blk, dep, K, E, 1.0, a.tiefe_max * s); n += 1
print("integriert", n, "Tiefenkarten", flush=True)
m = vbg.extract_triangle_mesh(weight_threshold=2.0).to_legacy(); print("roh", len(m.vertices), "Eckpunkte", np.asarray(m.vertices).min(0) if len(m.vertices) else None, np.asarray(m.vertices).max(0) if len(m.vertices) else None, flush=True); V = ((np.asarray(m.vertices) - ta) @ Ra) / s; k = a.massstab / 1000.0; hb = trimesh.load(a.huelle).bounds * k
ok = np.all((V >= hb[0] - 2) & (V <= hb[1] + 2), 1); f = np.asarray(m.triangles); fk = ok[f].all(1); t = trimesh.Trimesh(V, f[fk], process=False); t.remove_unreferenced_vertices(); t.vertices = t.vertices / k; t.export(a.aus)
print(a.aus, len(t.faces), "Dreiecke, wasserdicht", t.is_watertight)
