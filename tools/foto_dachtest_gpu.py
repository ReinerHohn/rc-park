import sys, json, numpy as np, torch, cv2
sys.path.insert(0, "/home/oem/git/rc-park/tools")
import foto_silhouette_gpu as F
dev = F.dev
P0, _ = F.load_points()
lo = torch.tensor([25, -3.2, -1.25, 12, -0.15, 0.6, -120, -120.], device=dev); hi = torch.tensor([200, 3.2, 0.05, 48, 0.15, 1.8, 120, 120.], device=dev)
def remap(P, rz1, z0=35.5, z1=46.2, top=54.8):
    z = P[:, 2].clone()
    a = (z > z0) & (z <= z1); b = z > z1
    z[a] = z0 + (z[a] - z0) * (rz1 - z0) / (z1 - z0)
    z[b] = rz1 + (z[b] - z1) * (top - rz1) / (top - z1)
    Q = P.clone(); Q[:, 2] = z; return Q
def prep(key):
    fn, cfg = F.FOTOS[key]; im = cv2.imread(F.FD + fn); h, w = im.shape[:2]; im = cv2.resize(im, (400, int(h * 400 / w)))
    return torch.as_tensor(~F.sky_mask(im), device=dev), cfg["roi"], im.shape[0], im.shape[1], 5.4 / 4.29 * im.shape[1]
def cem(P, T, roi, H, W, f0, mu, sd, iters, B=512, seed=0):
    g = torch.Generator(device=dev).manual_seed(seed); bs, bth = -9, mu.clone()
    for _ in range(iters):
        c = mu + sd * torch.randn((B, 8), device=dev, generator=g); c = torch.max(torch.min(c, hi), lo); c[0] = bth
        sc, iou = F.score(P, c, T, roi, f0, W, H); k = sc.topk(B // 10).indices
        mu = 0.5 * mu + 0.5 * c[k].mean(0); sd = 0.7 * sd + 0.3 * c[k].std(0) + 1e-4
        if sc[k[0]].item() > bs: bs, bth = sc[k[0]].item(), c[k[0]].clone()
    return bs, bth
keys = ["042", "043", "044"]; RZ = [43.5, 44.8, 46.2, 47.6, 49.0]
data = {k: prep(k) for k in keys}; starts = {}
for k in keys:      # Startposen aus der Basis (3 Zufallsstarts)
    T, roi, H, W, f0 = data[k]; starts[k] = []
    for sd_ in (0, 1, 2):
        g = torch.Generator(device=dev).manual_seed(sd_); best = []
        for _ in range(24):
            th = lo + (hi - lo) * torch.rand((1024, 8), device=dev, generator=g); sc, _ = F.score(P0, th, T, roi, f0, W, H); kk = sc.topk(20).indices; best.append((sc[kk], th[kk]))
        sc = torch.cat([b[0] for b in best]); th = torch.cat([b[1] for b in best]); kk = sc.topk(40).indices
        s, t = cem(P0, T, roi, H, W, f0, th[kk].mean(0), th[kk].std(0) + 1e-3, 50, seed=sd_); starts[k].append(t)
    print("Start", k, flush=True)
res = {}
for rz in RZ:
    P = remap(P0, rz); row = {}
    for k in keys:
        T, roi, H, W, f0 = data[k]; vals = []
        for t0 in starts[k]:
            s, t = cem(P, T, roi, H, W, f0, t0, (hi - lo) * 0.04, 35, seed=1); vals.append(s)
        row[k] = max(vals)
    row["mittel"] = float(np.mean([row[k] for k in keys])); res[rz] = row
    print(f"Dachfirst {rz:5.1f} m  " + "  ".join(f"{k}: {row[k]:.3f}" for k in keys) + f"  Mittel {row['mittel']:.3f}", flush=True)
json.dump({str(k): v for k, v in res.items()}, open("/home/oem/git/rc-park/modelle/foto_silhouette/dachtest.json", "w"), indent=1)
