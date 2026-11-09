"""Huellen (Dreiecksnetze) je 3D-Objekt aus sam_mehrfoto_3d.py: Punktmenge -> Voxel (GPU-Zaehlung + Glaettung) -> Schliessen/Fuellen -> Marching Cubes.
Aufruf: python -I tools/objekte_huellen.py IN.npz OUT.npz [--minpts 300] [--zellen 48]"""
import argparse, numpy as np, torch, time
from scipy import ndimage as ndi
from skimage import measure
ap = argparse.ArgumentParser(); ap.add_argument("ein"); ap.add_argument("aus"); ap.add_argument("--minpts", type=int, default=300); ap.add_argument("--zellen", type=int, default=48); a = ap.parse_args()
z = np.load(a.ein); P = z["P"]; ob = z["obj"]; rgb = z["rgb"]; ids, cts = np.unique(ob[ob >= 0], return_counts=True); V = []; F = []; META = []; t0 = time.time(); dev = "cuda"
def blur3(x, s):
    r = int(3 * s) + 1; k = torch.exp(-0.5 * (torch.arange(-r, r + 1, device=dev, dtype=torch.float32) / s) ** 2); k /= k.sum(); k = k.view(1, 1, -1)
    for ax in range(3):
        kk = k.reshape([1, 1] + [-1 if i == ax else 1 for i in range(3)]); pad = [0, 0, 0, 0, 0, 0]; pad[(2 - ax) * 2:(2 - ax) * 2 + 2] = [r, r]
        x = torch.nn.functional.conv3d(torch.nn.functional.pad(x, pad), kk)
    return x
nv = 0
for oi, n in zip(ids, cts):
    if n < a.minpts: continue
    p = P[ob == oi].astype(np.float64); lo, hi = p.min(0), p.max(0); ext = hi - lo; vs = max(ext.max() / a.zellen, 0.03); dim = np.ceil(ext / vs).astype(int) + 6
    ij = np.floor((p - lo) / vs).astype(int) + 3; g = torch.zeros(tuple(dim), device=dev); idx = torch.from_numpy(ij).to(dev); g.index_put_((idx[:, 0], idx[:, 1], idx[:, 2]), torch.ones(len(idx), device=dev), accumulate=True)
    b = blur3((g > 0).float()[None, None], 1.3)[0, 0].cpu().numpy(); m = b > 0.12; m = ndi.binary_closing(m, iterations=1); m = ndi.binary_fill_holes(m)
    if m.sum() < 8: continue
    mm = ndi.gaussian_filter(m.astype(np.float32), 0.8)
    try: vtx, fc, _, _ = measure.marching_cubes(mm, 0.5)
    except Exception: continue
    vtx = vtx * vs + lo - 3 * vs; F.append(fc.astype(np.int32) + nv); V.append(vtx.astype(np.float32)); nv += len(vtx); META.append((int(oi), int(n), len(fc), np.median(rgb[ob == oi], 0)))
np.savez_compressed(a.aus, V=np.vstack(V), F=np.vstack(F), ids=np.array([m[0] for m in META]), npts=np.array([m[1] for m in META]), ntri=np.array([m[2] for m in META]), farbe=np.array([m[3] for m in META]).astype(np.uint8))
print("Objekte", len(META), "Dreiecke", int(sum(m[2] for m in META)), "%.0fs" % (time.time() - t0))
