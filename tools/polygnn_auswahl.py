#!/usr/bin/env python3
"""polygnn_auswahl.py - BS63: Zellauswahl durch vortrainiertes PolyGNN (MIT, Munich-Checkpoint) statt Min-Cut.
Zellzerlegung wie tools/wolke_mincut.py (Voxel-Vorzeichenvektor, 0,1 m); abspy/sage nicht installierbar -> eigener Graph:
Knoten = Zellen, Kanten = Voxelnachbarschaft, Queries = 16 Zufallsvoxelmitten je Zelle (ANNAHME: statt 'skeleton'-Eckpunkten).
ANNAHME: Eingabe auf Einheitswuerfel normiert (Bbox-Mitte, groesste Ausdehnung = 1).
  venv-polygnn/bin/python -I tools/polygnn_auswahl.py --aus .../polygnn/pgnn_v1.stl"""
import sys, json, argparse, numpy as np, trimesh, manifold3d as m3, torch
from omegaconf import OmegaConf
from scipy.spatial import HalfspaceIntersection, ConvexHull
sys.path.insert(0, "/media/oem/scan/polygnn_test/polygnn"); sys.path.insert(0, "/media/oem/scan/polygnn_test/shim")
R = "/media/oem/scan/rc-park_null/"
ap = argparse.ArgumentParser()
ap.add_argument("--vox", type=float, default=0.1); ap.add_argument("--merge", type=float, default=0.2)
ap.add_argument("--minpts", type=int, default=3000); ap.add_argument("--rand", type=float, default=3.0)
ap.add_argument("--norm", default="max"); ap.add_argument("--thr", type=float, default=0.5)
ap.add_argument("--seed", type=int, default=1); ap.add_argument("--aus", default=R + "polygnn/pgnn_v1.stl")
a = ap.parse_args()
box = np.array([-14.6, 2.7, 0.6, 15.7, 17.0, 19.9]); lo, hi = box[:3] - 0.5, box[3:] + 0.5
X = np.load(R + "wolke_netzrahmen.npy").astype(np.float64); X = X[np.all((X >= lo) & (X <= hi), 1)]
lo = lo - np.array([a.rand, a.rand, 0.0]); hi = hi + a.rand; print("Punkte", len(X))
E = [e for e in json.load(open(R + "wolke_foto/ebenen.json")) if e["punkte"] >= a.minpts]; E.sort(key=lambda e: -e["punkte"])
P = []
for e in E:
    n = np.array(e["n"]); n /= np.linalg.norm(n); d = e["d"]
    if any(abs(n @ q[0]) > 0.995 and abs(d - q[1] * np.sign(n @ q[0])) < a.merge for q in P): continue
    P.append((n, d))
for n_, d_ in [((1, 0, 0), -box[3]), ((-1, 0, 0), box[0]), ((0, 1, 0), -box[4]), ((0, 0, 1), -box[5]), ((0, 0, -1), box[2])]:
    P.append((np.array(n_, float), float(d_)))
v = a.vox; dims = np.ceil((hi - lo) / v).astype(int)
ix = np.stack(np.meshgrid(*[np.arange(k) for k in dims], indexing="ij"), -1).reshape(-1, 3); C = lo + (ix + 0.5) * v
code = np.zeros(len(C), np.int64)
for i, (n, d) in enumerate(P): code |= ((C @ n + d) > 0).astype(np.int64) << i
uc, cid = np.unique(code, return_inverse=True); nc = len(uc); cid3 = cid.reshape(dims); print("Ebenen", len(P), "Zellen", nc)
pair = set(); edge = np.zeros(nc, bool)
for ax in range(3):
    s0 = [slice(None)] * 3; s1 = [slice(None)] * 3; s0[ax] = slice(0, -1); s1[ax] = slice(1, None)
    A = cid3[tuple(s0)].ravel(); B = cid3[tuple(s1)].ravel(); m = A != B
    pair |= set(zip(np.minimum(A[m], B[m]).tolist(), np.maximum(A[m], B[m]).tolist()))
    for end in (0, -1):
        if ax == 2 and end == 0: continue
        sl = [slice(None)] * 3; sl[ax] = end; edge[np.unique(cid3[tuple(sl)])] = True
pr = np.array(sorted(pair)); ei = torch.tensor(np.concatenate([pr, pr[:, ::-1]]).T.copy(), dtype=torch.long); print("Kanten", len(pr))
# Normierung
ctr = (X.min(0) + X.max(0)) / 2; sc = (X.max(0) - X.min(0)).max() if a.norm == "max" else 1.0
rng = np.random.default_rng(a.seed); nq = 16
order = np.argsort(cid, kind="stable"); cnt = np.bincount(cid, minlength=nc); st = np.concatenate([[0], np.cumsum(cnt)])
Qm = np.zeros((nc, nq, 3))
for c in range(nc):
    vx = C[order[st[c]:st[c + 1]]]; Qm[c] = vx[rng.integers(0, len(vx), nq)]; Qm[c, 0] = vx.mean(0)
tn = lambda p: ((p - ctr) / sc).astype(np.float32)
pts = tn(X[rng.choice(len(X), 4096, replace=False)])
cfg = OmegaConf.create(dict(gnn="TAGCN", dataset_suffix="", sample=dict(strategy="random", length=4096, resolution=0.01), encoder="ConvONet",
    decoder="ConvONet", latent_dim_light=256, latent_dim_conv=4096, use_spatial_transformer=False, num_queries=16, dropout=False,
    convonet_kwargs=dict(unet=True, unet_kwargs=dict(depth=4, merge_mode="concat", start_filts=32), plane_resolution=128, plane_type=["xz", "xy", "yz"])))
from network import PolyGNN
dev = "cuda"; model = PolyGNN(cfg).to(dev)
sd = torch.load("/media/oem/scan/polygnn_test/polygnn/ckpt_dl/ckpt.tar", map_location=dev, weights_only=False)["state_dict"]
sd = {k.replace("module.", "", 1): x for k, x in sd.items()}; print(model.load_state_dict(sd, strict=False)); model.eval()
from torch_geometric.data import Data
d = Data(edge_index=ei); d.num_nodes = nc
d.points_4096 = torch.tensor(pts); d.batch_points_4096 = torch.zeros(len(pts), dtype=torch.long)
d.queries = torch.tensor(tn(Qm.reshape(-1, 3)).reshape(nc, nq, 3)); d.batch = torch.zeros(nc, dtype=torch.long)
d = d.to(dev)
with torch.no_grad(): out = model(d)
prob = torch.softmax(out, 1)[:, 1].cpu().numpy() if out.min() >= 0 or True else None
inside = (out.argmax(1) == 1).cpu().numpy(); inside[edge] = False
vol = cnt * v ** 3
print("Innen", int(inside.sum()), "Vol m3", float(vol[inside].sum()), "p>0.5 roh", int((out.argmax(1) == 1).sum()), "pmax", float(prob.max()))
np.save(a.aus.replace(".stl", "_inside.npy"), inside)
meshes = []
for ci in np.where(inside)[0]:
    vox = C[cid == ci]; ip = vox.mean(0); bits = uc[ci]
    hs = [[*(-n), -dd] if (bits >> i) & 1 else [*n, dd] for i, (n, dd) in enumerate(P)]
    hs += [[1, 0, 0, -hi[0]], [-1, 0, 0, lo[0]], [0, 1, 0, -hi[1]], [0, -1, 0, lo[1]], [0, 0, 1, -hi[2]], [0, 0, -1, lo[2]]]
    hs = np.array(hs, float); hs[:, 3] -= 0.003
    if np.any(hs[:, :3] @ ip + hs[:, 3] >= 0): ip = vox[np.argmin(np.max(vox @ hs[:, :3].T + hs[:, 3], 1))]
    try:
        pp = HalfspaceIntersection(hs, ip).intersections; pp = pp[np.isfinite(pp).all(1)]
        mm = trimesh.Trimesh(pp, ConvexHull(pp).simplices, process=True); trimesh.repair.fix_normals(mm); meshes.append(mm)
    except Exception: pass
ms = [m3.Manifold(m3.Mesh(mm.vertices.astype(np.float32), mm.faces.astype(np.uint32))) for mm in meshes]
if not ms: sys.exit("keine Zellen")
U = m3.Manifold.batch_boolean(ms, m3.OpType.Add); mo = U.to_mesh()
T = trimesh.Trimesh(np.asarray(mo.vert_properties)[:, :3] / 0.087, np.asarray(mo.tri_verts), process=False)
print('manifold status', U.status(), 'genus', U.genus(), 'watertight(process=False)', T.is_watertight)
print("Netz wasserdicht", T.is_watertight, "Vol mm3", T.volume, "Flaechen", len(T.faces))
import os; os.makedirs(os.path.dirname(a.aus), exist_ok=True); T.export(a.aus); print("->", a.aus)
