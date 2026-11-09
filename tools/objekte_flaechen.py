"""Oberflaechen je 3D-Objekt direkt aus den Wolkenpunkten (Hoppe-SDF mit orientierten Normalen, GPU): KEIN Fuellen/Glaetten wie bei Voxelhuellen -> echte Kanten, offene Schalen wo nur die Vorderseite gemessen ist.
Aufruf: python -I tools/objekte_flaechen.py ERG.npz KAMERAS.json OUT.npz [--minpts 400] [--vs 0.02]"""
import argparse, json, time, sys, numpy as np, torch
sys.path.insert(0, "/media/oem/scan/p3d_site")
from pytorch3d.ops import knn_points
from skimage import measure
ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("kameras"); ap.add_argument("aus"); ap.add_argument("--minpts", type=int, default=400); ap.add_argument("--vs", type=float, default=0.02); ap.add_argument("--k", type=int, default=20); a = ap.parse_args()
dev = "cuda"; z = np.load(a.ein); P = z["P"].astype(np.float32); ob = z["obj"]; rgb = z["rgb"]; fotos = [str(f) for f in z["fotos"]]; KAM = json.load(open(a.kameras)); N = len(P); t0 = time.time()
Cm = np.mean([KAM[f]["C"] for f in fotos], 0).astype(np.float32); Pt = torch.from_numpy(P).to(dev)
nrm = torch.zeros((N, 3), device=dev)
for i in range(0, N, 4000):                                                        # Normalen: kleinster Eigenvektor der Kovarianz der k Nachbarn
    q = Pt[None, i:i + 4000]; nn = knn_points(q, Pt[None], K=a.k).idx[0]; X = Pt[nn]; X = X - X.mean(1, keepdim=True); C = X.transpose(1, 2) @ X; w, v = torch.linalg.eigh(C); nrm[i:i + 4000] = v[:, :, 0]
to = torch.from_numpy(Cm).to(dev)[None] - Pt; nrm = torch.where(((nrm * to).sum(1) < 0)[:, None], -nrm, nrm)          # zur Kameraseite orientieren
print("Normalen %.0fs" % (time.time() - t0), flush=True)
ids, cts = np.unique(ob[ob >= 0], return_counts=True); V, F, M = [], [], []; nv = 0
for o, c in zip(ids, cts):
    if c < a.minpts: continue
    m = ob == o; p = P[m]; lo = p.min(0); hi = p.max(0); ext = hi - lo; vs = max(a.vs, float(ext.max()) / 170.0); lo2 = lo - 3 * vs; dim = np.ceil((hi + 3 * vs - lo2) / vs).astype(int) + 1
    gx = torch.arange(dim[0], device=dev); gy = torch.arange(dim[1], device=dev); gz = torch.arange(dim[2], device=dev); G = torch.stack(torch.meshgrid(gx, gy, gz, indexing="ij"), -1).reshape(-1, 3).float() * vs + torch.from_numpy(lo2).to(dev)
    po = torch.from_numpy(p).to(dev); no = nrm[torch.from_numpy(np.where(m)[0]).to(dev)]; sdf = torch.zeros(len(G), device=dev); band = torch.zeros(len(G), dtype=torch.bool, device=dev)
    for i in range(0, len(G), 2_000_000):
        r = knn_points(G[None, i:i + 2_000_000], po[None], K=1); d = r.dists[0, :, 0].sqrt(); ix = r.idx[0, :, 0]; s = ((G[i:i + 2_000_000] - po[ix]) * no[ix]).sum(1); sdf[i:i + 2_000_000] = s; band[i:i + 2_000_000] = d < 1.6 * vs
    vol = sdf.view(*dim).cpu().numpy(); mk = band.view(*dim).cpu().numpy()
    if mk.sum() < 50: continue
    try: vtx, fc, _, _ = measure.marching_cubes(vol, 0.0, mask=mk)
    except Exception: continue
    if len(fc) < 20: continue
    V.append((vtx * vs + lo2).astype(np.float32)); F.append(fc.astype(np.int32) + nv); nv += len(vtx); M.append((int(o), int(c), len(fc), np.median(rgb[m], 0)))
np.savez_compressed(a.aus, V=np.vstack(V), F=np.vstack(F), ids=np.array([x[0] for x in M]), npts=np.array([x[1] for x in M]), ntri=np.array([x[2] for x in M]), farbe=np.array([x[3] for x in M]).astype(np.uint8))
print("Objekte", len(M), "Dreiecke", int(sum(x[2] for x in M)), "%.0fs" % (time.time() - t0))
