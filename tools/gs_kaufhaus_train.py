#!/usr/bin/env python3
"""gs_kaufhaus_train.py - 3D Gaussian Splatting (gsplat 1.5.3, DefaultStrategy) fuer das Kaufhaus, Start aus der dichten Wolke (Modellrahmen, Meter).
Kameras/Bilder aus tools/gs_kaufhaus_daten.py. Optional lernbare Kamerakorrektur je Foto (--pose, kleine Drehung/Verschiebung, L2-gehalten); Auswertungsfotos (jedes 8.) werden nicht trainiert.
Aufruf (vorher CUDA_HOME/PATH/TORCH_CUDA_ARCH_LIST setzen, siehe Auftrag; lang: via JOB_GPU_MB=5500 tools/job_start.sh):
  venv-seg/bin/python -I tools/gs_kaufhaus_train.py --daten /media/oem/scan/rc-park_null/gs_kh [--schritte 15000] [--max-gauss 1500000] [--pose 1]
Ausgabe: DIR/gs_ckpt.pt (Parameter + Posen), DIR/train_log.jsonl (Schritt, Verlust, PSNR Train, PSNR Auswertung, Anzahl Gauss)."""
import os, sys, json, math, time, argparse, numpy as np, torch, cv2
import torch.nn.functional as Fn
from gsplat import rasterization
from gsplat.strategy import DefaultStrategy
ap = argparse.ArgumentParser(); ap.add_argument("--daten", required=True); ap.add_argument("--schritte", type=int, default=15000); ap.add_argument("--max-gauss", type=int, default=1500000)
ap.add_argument("--pose", type=int, default=1); ap.add_argument("--wolke", default="modelle/kaufhaus_null5/sfm/dicht_alle_modell.npy"); ap.add_argument("--farben", default="modelle/kaufhaus_null5/sfm/dicht_alle_farben.npy"); ap.add_argument("--n-start", type=int, default=400000); a = ap.parse_args()
dev = "cuda"; D = a.daten; cams = json.load(open(os.path.join(D, "kameras.json"))); nrs = sorted(cams)
bilder = {n: torch.from_numpy(cv2.cvtColor(cv2.imread(os.path.join(D, f"bild_{n}.png")), cv2.COLOR_BGR2RGB)).to("cpu") for n in nrs}
def viewmat(n): R = np.array(cams[n]["R"]); M = np.eye(4); M[:3, :3] = R; M[:3, 3] = cams[n]["t"]; return torch.tensor(M, dtype=torch.float32, device=dev)
def Kmat(n): c = cams[n]; return torch.tensor([[c["f"], 0, c["cx"]], [0, c["f"], c["cy"]], [0, 0, 1]], dtype=torch.float32, device=dev)
ev = [n for i, n in enumerate(nrs) if i % 8 == 4]; tr = [n for n in nrs if n not in ev]
P = np.load(a.wolke).astype(np.float32); C = np.load(a.farben).astype(np.float32) / 255.0; rng = np.random.default_rng(0); idx = rng.choice(len(P), min(a.n_start, len(P)), replace=False); P, C = P[idx], C[idx]
from scipy.spatial import cKDTree
d, _ = cKDTree(P).query(P, k=4); dist = np.clip(d[:, 1:].mean(1), 0.01, 1.0)
cen = np.array([np.linalg.inv(np.array(cams[n]["R"])) @ (-np.array(cams[n]["t"])) for n in nrs]); scene_scale = 20.0   # Gebaeude ~45 m, einzelne Kameras >80 m entfernt (Max-Radius wuerde Teil-/Wachstumsschwellen 4x zu grob setzen)
print("Wolke", len(P), "Kameras", len(nrs), "Train", len(tr), "Eval", len(ev), "scene_scale", round(scene_scale, 2), flush=True)
SH = 3; N = len(P); sh = torch.zeros(N, (SH + 1) ** 2, 3); sh[:, 0] = torch.from_numpy((C - 0.5) / 0.28209479)
params = torch.nn.ParameterDict({"means": torch.nn.Parameter(torch.from_numpy(P)), "scales": torch.nn.Parameter(torch.log(torch.from_numpy(dist.astype(np.float32)))[:, None].repeat(1, 3)),
    "quats": torch.nn.Parameter(torch.nn.functional.normalize(torch.randn(N, 4), dim=-1)), "opacities": torch.nn.Parameter(torch.logit(torch.full((N,), 0.1))),
    "sh0": torch.nn.Parameter(sh[:, :1]), "shN": torch.nn.Parameter(sh[:, 1:])}).to(dev)
ms = scene_scale; lrs = {"means": 1.6e-4 * ms, "scales": 5e-3, "quats": 1e-3, "opacities": 5e-2, "sh0": 2.5e-3, "shN": 2.5e-3 / 20}
opts = {k: torch.optim.Adam([{"params": params[k], "lr": lrs[k], "name": k}], eps=1e-15) for k in params}
strat = DefaultStrategy(refine_start_iter=500, refine_stop_iter=min(a.schritte - 2000, 10000), refine_every=100, reset_every=3000, grow_grad2d=2e-4, verbose=False); strat.check_sanity(params, opts); st = strat.initialize_state(scene_scale=scene_scale)
pose = torch.zeros(len(nrs), 6, device=dev, requires_grad=bool(a.pose)); popt = torch.optim.Adam([pose], lr=3e-4); pid = {n: i for i, n in enumerate(nrs)}
def rodr(w):
    th = w.norm() + 1e-12; k = w / th; Kx = torch.zeros(3, 3, device=dev); Kx[0, 1], Kx[0, 2], Kx[1, 0], Kx[1, 2], Kx[2, 0], Kx[2, 1] = -k[2], k[1], k[2], -k[0], -k[1], k[0]
    return torch.eye(3, device=dev) + torch.sin(th) * Kx + (1 - torch.cos(th)) * Kx @ Kx
def vm_pose(n):
    p = pose[pid[n]]; T = torch.eye(4, device=dev); T[:3, :3] = rodr(p[:3]); T[:3, 3] = p[3:]; return T @ viewmat(n)
def render(n, sh_deg, gradpose=True, vm=None):
    c = cams[n]; vmn = (vm_pose(n) if a.pose else viewmat(n)) if vm is None else vm
    col, al, info = rasterization(params["means"], Fn.normalize(params["quats"], dim=-1), torch.exp(params["scales"]), torch.sigmoid(params["opacities"]), torch.cat([params["sh0"], params["shN"]], 1),
        vmn[None], Kmat(n)[None], c["W"], c["H"], sh_degree=sh_deg, render_mode="RGB+ED", packed=False, absgrad=False)
    return col[0], al[0], info
def ssim(x, y, w=11):
    g = torch.exp(-(torch.arange(w, device=dev) - w // 2) ** 2 / (2 * 1.5 ** 2)); g = g / g.sum(); k = (g[:, None] * g[None])[None, None].repeat(3, 1, 1, 1)
    f = lambda z: Fn.conv2d(z, k, padding=w // 2, groups=3); mx, my = f(x), f(y); sx, sy, sxy = f(x * x) - mx * mx, f(y * y) - my * my, f(x * y) - mx * my
    c1, c2 = 0.01 ** 2, 0.03 ** 2; return (((2 * mx * my + c1) * (2 * sxy + c2)) / ((mx * mx + my * my + c1) * (sx + sy + c2))).mean()
def psnr(x, y): return float(-10 * torch.log10(((x - y) ** 2).mean()))
log = open(os.path.join(D, "train_log.jsonl"), "w"); t0 = time.time(); acc = []; pa = []
sch = {k: torch.optim.lr_scheduler.ExponentialLR(opts[k], 0.01 ** (1 / a.schritte)) for k in ["means"]}
for step in range(a.schritte):
    n = tr[rng.integers(len(tr))]; gt = bilder[n].to(dev).float() / 255.0; sd = min(SH, step // 1000)
    out, al, info = render(n, sd); img = out[..., :3]
    strat.step_pre_backward(params, opts, st, step, info)
    loss = 0.8 * (img - gt).abs().mean() + 0.2 * (1 - ssim(img.permute(2, 0, 1)[None], gt.permute(2, 0, 1)[None]))
    if a.pose: loss = loss + 1e-3 * (pose ** 2).sum() / len(nrs)
    loss.backward(); strat.step_post_backward(params, opts, st, step, info)
    if step >= 500 and len(params["means"]) > a.max_gauss: strat.grow_grad2d = 1e9; strat.refine_stop_iter = 0
    for o in opts.values(): o.step(); o.zero_grad(set_to_none=True)
    if a.pose: popt.step(); popt.zero_grad(set_to_none=True)
    for s_ in sch.values(): s_.step()
    acc.append(float(loss)); pa.append(psnr(img.clamp(0, 1).detach(), gt))
    if (step + 1) % 500 == 0 or step == a.schritte - 1:
        with torch.no_grad():
            pe = [psnr(render(e, SH)[0][..., :3].clamp(0, 1), bilder[e].to(dev).float() / 255.0) for e in ev]
        r = dict(schritt=step + 1, verlust=float(np.mean(acc)), psnr_train=float(np.mean(pa)), psnr_eval=float(np.mean(pe)), gauss=len(params["means"]), sek=round(time.time() - t0), vram_gb=round(torch.cuda.max_memory_allocated() / 1e9, 2))
        print(json.dumps(r), flush=True); log.write(json.dumps(r) + "\n"); log.flush(); acc = []; pa = []
torch.save({"params": {k: v.detach().cpu() for k, v in params.items()}, "pose": pose.detach().cpu(), "nrs": nrs, "eval": ev}, os.path.join(D, "gs_ckpt.pt")); print("fertig", flush=True)
