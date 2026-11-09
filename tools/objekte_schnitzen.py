"""Shape-from-Silhouette je 3D-Objekt (Nutzer 9.11.: aus den SAM-Linien in 3D Objekte bauen): Voxel bleiben, wenn sie in den SAM-Masken der meisten Fotos liegen, die das Objekt sehen;
vorne begrenzt durch die gemessene Wolkenoberflaeche (Hoehenfeld in u,z), hinten durch die Wandebene. Ausgabe wie objekte_huellen.py (V,F,ids,...) fuer huellen_html.py.
Aufruf: python -I tools/objekte_schnitzen.py ERG.npz MASKENDIR KAMERAS.json OBJEKT.json OUT.npz [--n 120] [--stimmen 0.5]"""
import argparse, json, os, time, numpy as np, torch
from scipy import ndimage as ndi
from skimage import measure
ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("ein", "masken", "kameras", "objekt", "aus")]; ap.add_argument("--n", type=int, default=120); ap.add_argument("--stimmen", type=float, default=0.5); ap.add_argument("--zellen", type=int, default=56); ap.add_argument("--minpts", type=int, default=300); ap.add_argument("--maxanteil", type=float, default=0.15); a = ap.parse_args()
dev = "cuda"; z = np.load(a.ein); P = z["P"]; ob = z["obj"]; rgb = z["rgb"]; fotos = [str(f) for f in z["fotos"]]; lut = torch.from_numpy(z["lut"]).to(dev); MAXM = int(z["maxm"]); cids = z["cluster_ids"]; N = len(P)
KAM = json.load(open(a.kameras)); O = json.load(open(a.objekt)); n_ = np.array(O["fassade_n"]["wert"], float); n_ = n_[:2] / np.linalg.norm(n_[:2]); U_ = np.array([n_[1], -n_[0]])
ids, cts = np.unique(ob[ob >= 0], return_counts=True); big = ids[np.argmax(cts)]
Cm = np.mean([KAM[f]["C"] for f in fotos], 0); sg = 1.0 if (Cm[:2] - P[:, :2].mean(0)) @ n_ > 0 else -1.0            # n nach aussen (Richtung der Kameras)
S = sg * (P[:, :2] @ n_); Uu = P[:, :2] @ U_; Zz = P[:, 2]; s_wand = float(np.median(S[ob == big]))
sel = [(int(i), int(c)) for i, c in zip(ids, cts) if a.minpts <= c <= a.maxanteil * N]; sel.sort(key=lambda t: -t[1]); sel = [i for i, c in sel[:a.n]]; print("Objekte", len(sel), "Wand s=%.2f" % s_wand, "n-Vorzeichen", sg, flush=True)
G = {}
for o in sel:
    m = ob == o; u, s, zz = Uu[m], S[m], Zz[m]; lo = np.array([u.min(), s.min(), zz.min()]); hi = np.array([u.max(), s.max(), zz.max()]); ext = hi - lo; vs = max(ext.max() / a.zellen, 0.015)
    sb = max(s_wand - 0.03, lo[1] - 1.5)                                                       # hinten: Wand (oder max. 1,5 m hinter der Vorderflaeche)
    lo2 = np.array([lo[0] - 2 * vs, sb, lo[2] - 2 * vs]); hi2 = np.array([hi[0] + 2 * vs, hi[1] + 2 * vs, hi[2] + 2 * vs]); dim = np.ceil((hi2 - lo2) / vs).astype(int) + 1
    if np.prod(dim) > 6e6: vs *= (np.prod(dim) / 6e6) ** (1 / 3); dim = np.ceil((hi2 - lo2) / vs).astype(int) + 1
    ci = np.floor((np.c_[u, zz] - [lo2[0], lo2[2]]) / vs).astype(int); hf = np.full((dim[0], dim[2]), -1e9, np.float32); np.maximum.at(hf, (ci[:, 0], ci[:, 1]), s.astype(np.float32))   # Vorderflaeche je (u,z)
    mk = hf > -1e8; hf = np.where(mk, hf, 0); dist, idx = ndi.distance_transform_edt(~mk, return_indices=True); hf = hf[idx[0], idx[1]]; near = dist < 3     # Luecken bis 3 Zellen mit Nachbarwert
    gu, gs, gz = np.meshgrid(np.arange(dim[0]), np.arange(dim[1]), np.arange(dim[2]), indexing="ij"); sc = lo2[1] + gs * vs; keep = near[gu, gz] & (sc <= hf[gu, gz] + vs)       # hinter der Oberflaeche
    gu, gs, gz = gu[keep], gs[keep], gz[keep]
    X = np.c_[lo2[0] + gu * vs, lo2[1] + gs * vs, lo2[2] + gz * vs]; W = np.zeros((len(X), 3)); W[:, :2] = np.outer(X[:, 0], U_) + np.outer(sg * X[:, 1], n_); W[:, 2] = X[:, 2]
    G[o] = dict(X=torch.tensor(W, dtype=torch.float32, device=dev), g=(gu, gs, gz), dim=dim, lo=lo2, vs=vs, vin=torch.zeros(len(X), device=dev), vsee=torch.zeros(len(X), device=dev), c=int(cids[o]), nviews=0)
t0 = time.time()
for j, f in enumerate(fotos):
    cp = os.path.join(a.masken, os.path.splitext(f)[0] + (".npz" if os.path.exists(os.path.join(a.masken, os.path.splitext(f)[0] + ".npz")) else ".npy"))
    lab = np.load(cp); lab = lab["lab"] if cp.endswith(".npz") else lab; h, w = lab.shape; K = KAM[f]; s_ = w / K["W"]
    lt = torch.from_numpy(lab).to(dev).long(); CL = lut[j * MAXM + lt.clamp(min=0)].long(); CL[lt < 0] = -1; area = torch.bincount(CL[CL >= 0], minlength=int(lut.max()) + 2); CLf = CL.view(-1)
    R = torch.tensor(K["Rn"], device=dev, dtype=torch.float32); T = torch.tensor(K["tn"], device=dev, dtype=torch.float32); c0 = torch.tensor([K["cx"], K["cy"]], device=dev)
    for o, g in G.items():
        if int(area[g["c"]]) < 400: continue                                                  # Objekt in diesem Foto nicht (gross genug) segmentiert
        Xc = g["X"] @ R.T + T; zc = Xc[:, 2]; uv = (K["f"] * Xc[:, :2] / zc.clamp(min=0.5)[:, None] + c0) * s_; u = uv[:, 0].round().long(); v = uv[:, 1].round().long(); ok = (zc > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
        ins = ok & (CLf[v.clamp(0, h - 1) * w + u.clamp(0, w - 1)] == g["c"]); g["vin"] += ins.float(); g["vsee"] += ok.float(); g["nviews"] += 1
    del lt, CL
    if j % 10 == 0: print("Foto %d/%d %.0fs" % (j + 1, len(fotos), time.time() - t0), flush=True)
V, F, M = [], [], []; nv = 0
for o, g in G.items():
    vin, vse = g["vin"].cpu().numpy(), g["vsee"].cpu().numpy(); ok = (vse >= 3) & (vin >= a.stimmen * vse); gu, gs, gz = g["g"]
    if ok.sum() < 20: continue
    grid = np.zeros(g["dim"], np.float32); grid[gu[ok], gs[ok], gz[ok]] = 1.0; grid = ndi.gaussian_filter(grid, 0.7)
    try: vtx, fc, _, _ = measure.marching_cubes(np.pad(grid, 1), 0.5)
    except Exception: continue
    vtx = (vtx - 1) * g["vs"] + g["lo"]; W3 = np.zeros((len(vtx), 3), np.float32); W3[:, :2] = np.outer(vtx[:, 0], U_) + np.outer(sg * vtx[:, 1], n_); W3[:, 2] = vtx[:, 2]
    V.append(W3); F.append(fc.astype(np.int32) + nv); nv += len(W3); M.append((o, int((ob == o).sum()), len(fc), np.median(rgb[ob == o], 0)))
np.savez_compressed(a.aus, V=np.vstack(V), F=np.vstack(F), ids=np.array([m[0] for m in M]), npts=np.array([m[1] for m in M]), ntri=np.array([m[2] for m in M]), farbe=np.array([m[3] for m in M]).astype(np.uint8))
print("Objekte", len(M), "Dreiecke", int(sum(m[2] for m in M)), "%.0fs" % (time.time() - t0))
