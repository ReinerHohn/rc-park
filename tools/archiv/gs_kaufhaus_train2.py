#!/usr/bin/env python3
"""gs_kaufhaus_train2.py - Gaussian Splatting Kaufhaus, Varianten V1-V3 (Verbesserungen gegen den schwachen ersten Lauf gs_kaufhaus_train.py; dort Test-PSNR sank 14,3 -> 13,8).
Gleiche Daten (Symlinks auf gs_kh: bild_*.png, kameras.json), gleiche Auswertungsfotos (jedes 8.), jede Verbesserung einzeln schaltbar:
  --farbe 1    V1: affine Farbkorrektur je Foto (3x3 + Versatz, Start = Identitaet, zur Identitaet gehalten) gegen Jahreszeit/Belichtung/Film. Auswertungsfotos haben keine gelernte Korrektur
               -> zusaetzlich psnr_eval_fit (nur Nicht-Himmel-Pixel; je Foto Gain/Versatz je Kanal per kleinste Quadrate, reine Diagnose, nicht Trainingsziel).
  --sw 1       V1: Fotos mit mittlerer Saettigung < --sw-schwelle (HSV-S, 0..255) = Schwarzweiss: Loss nur auf Helligkeit (Rendering -> Luma gegen Grau).
  --himmel DIR V1: Himmelsmaske (DIR/<nr>.png, 255 = Himmel; nur fuer Fotos, die eine Maske haben): Farb-/SSIM-Loss dort aus, dort Alpha -> 0 (Gewicht --w-himmel). Maske wird --erode px erodiert (Masken sind teils unvollstaendig).
  --tiefe 1    V2: Tiefenvorgabe aus der Wolke (--wolke) je Kamera projiziert: Z-Puffer, Punkte hinter dem Vordergrund (> minpool7x7 + 0,4 m) verworfen (Durchblick-Punkte), L1 relativ auf erwartete Tiefe nur dort (Gewicht --w-tiefe).
  --opa 1      V2: Opazitaetsregularisierung gegen Schwebeartefakte (mittlere Opazitaet + Binaerzwang a(1-a) ab Schritt 6000).
  --max-gauss  V2: Obergrenze (Standard 1,5 M; beim Erreichen stoppt die Verdichtung).
  --zweid 1    V3: 2DGS (gsplat rasterization_2dgs, Normalen-Konsistenz ab 7000, Verzerrung ab 3000), Strategie key_for_gradient=gradient_2dgs.
Aufruf: (CUDA_HOME/PATH/TORCH_CUDA_ARCH_LIST setzen) JOB_GPU_MB=5500 tools/job_start.sh NAME LOG venv-seg/bin/python -I tools/gs_kaufhaus_train2.py --daten gs_kh2/V1 --quelle gs_kh --farbe 1 --sw 1 --himmel modelle/kaufhaus_null5/himmelsmaske
Ausgabe: DIR/gs_ckpt.pt (+ 'farbe' falls gelernt), DIR/train_log.jsonl (Schritt, Verlust, PSNR Train, PSNR Auswertung roh/fit, Gauss, VRAM)."""
import os, sys, json, math, time, argparse, numpy as np, torch, cv2
import torch.nn.functional as Fn
from gsplat import rasterization, rasterization_2dgs
from gsplat.strategy import DefaultStrategy
ap = argparse.ArgumentParser(); ap.add_argument("--daten", required=True); ap.add_argument("--quelle", required=True, help="Ordner mit bild_*.png + kameras.json (gs_kh)")
ap.add_argument("--schritte", type=int, default=15000); ap.add_argument("--max-gauss", type=int, default=1500000); ap.add_argument("--pose", type=int, default=1)
ap.add_argument("--wolke", default="modelle/kaufhaus_null5/sfm/dicht_alle_modell.npy"); ap.add_argument("--farben", default="modelle/kaufhaus_null5/sfm/dicht_alle_farben.npy"); ap.add_argument("--n-start", type=int, default=400000)
ap.add_argument("--farbe", type=int, default=0); ap.add_argument("--sw", type=int, default=0); ap.add_argument("--sw-schwelle", type=float, default=8.0)
ap.add_argument("--himmel"); ap.add_argument("--erode", type=int, default=6); ap.add_argument("--w-himmel", type=float, default=0.1)
ap.add_argument("--tiefe", type=int, default=0); ap.add_argument("--w-tiefe", type=float, default=1.0); ap.add_argument("--opa", type=int, default=0); ap.add_argument("--zweid", type=int, default=0)
ap.add_argument("--ckpt-eval", help="nur Auswertung eines vorhandenen Checkpoints (z.B. Lauf 1 gs_kh/gs_ckpt.pt) mit den Auswertungsmetriken, dann Ende"); ap.add_argument("--vram-anteil", type=float, default=0.0, help="torch-Speicherdeckel als Anteil von 8,2 GB (Budget 5,5 GB -> 0.67)"); a = ap.parse_args()
dev = "cuda"; D = a.daten; os.makedirs(D, exist_ok=True)
if a.vram_anteil > 0: torch.cuda.set_per_process_memory_fraction(a.vram_anteil)
cams = json.load(open(os.path.join(a.quelle, "kameras.json"))); nrs = sorted(cams); json.dump(cams, open(os.path.join(D, "kameras.json"), "w"))
bilder = {n: torch.from_numpy(cv2.cvtColor(cv2.imread(os.path.join(a.quelle, f"bild_{n}.png")), cv2.COLOR_BGR2RGB)) for n in nrs}
sat = {n: float(cv2.cvtColor(bilder[n].numpy(), cv2.COLOR_RGB2HSV)[..., 1].mean()) for n in nrs}; sw = {n for n in nrs if a.sw and sat[n] < a.sw_schwelle}
himmel = {}
if a.himmel:
    for n in nrs:
        p = os.path.join(a.himmel, f"{n}.png")
        if not os.path.exists(p): continue
        k = cv2.imread(p, 0); h, w = bilder[n].shape[:2]; k = (cv2.resize(k, (w, h), interpolation=cv2.INTER_NEAREST) > 127).astype(np.uint8)
        if a.erode > 0: k = cv2.erode(k, np.ones((2 * a.erode + 1,) * 2, np.uint8))
        himmel[n] = torch.from_numpy(k.astype(bool))
print("SW-Fotos", sorted(sw), "Himmelsmasken", len(himmel), "von", len(nrs), flush=True)
def viewmat(n): R = np.array(cams[n]["R"]); M = np.eye(4); M[:3, :3] = R; M[:3, 3] = cams[n]["t"]; return torch.tensor(M, dtype=torch.float32, device=dev)
def Kmat(n): c = cams[n]; return torch.tensor([[c["f"], 0, c["cx"]], [0, c["f"], c["cy"]], [0, 0, 1]], dtype=torch.float32, device=dev)
ev = [n for i, n in enumerate(nrs) if i % 8 == 4]; tr = [n for n in nrs if n not in ev]
P = np.load(a.wolke).astype(np.float32); C = np.load(a.farben).astype(np.float32) / 255.0; rng = np.random.default_rng(0)
Pall = P
def tiefenkarte(n):
    """Wolke -> Tiefenkarte (0 = keine Vorgabe). Z-Puffer; Punkte hinter dem Vordergrund (Durchblick durch Luecken der duennen Wolke) verworfen."""
    c = cams[n]; R = np.array(c["R"]); t = np.array(c["t"]); X = Pall @ R.T + t; z = X[:, 2]; ok = z > 0.5
    u = np.round(X[:, 0] / np.maximum(z, 1e-6) * c["f"] + c["cx"]).astype(int); v = np.round(X[:, 1] / np.maximum(z, 1e-6) * c["f"] + c["cy"]).astype(int)
    ok &= (u >= 0) & (u < c["W"]) & (v >= 0) & (v < c["H"]); zb = np.full(c["W"] * c["H"], np.inf, np.float32); np.minimum.at(zb, v[ok] * c["W"] + u[ok], z[ok].astype(np.float32)); zb = zb.reshape(c["H"], c["W"])
    big = np.where(np.isinf(zb), 1e4, zb).astype(np.float32); mp = cv2.erode(big, np.ones((7, 7), np.uint8)); d = np.where(np.isfinite(zb) & (zb <= mp + 0.4), zb, 0).astype(np.float32)
    if n in himmel: d[himmel[n].numpy()] = 0
    return torch.from_numpy(d)
tiefen = {}
if a.tiefe:
    t0 = time.time(); tiefen = {n: tiefenkarte(n) for n in nrs}; print("Tiefenvorgaben", len(tiefen), "mittlere Abdeckung %.4f" % np.mean([float((v > 0).float().mean()) for v in tiefen.values()]), "%.0f s" % (time.time() - t0), flush=True)
idx = rng.choice(len(P), min(a.n_start, len(P)), replace=False); P, C = P[idx], C[idx]
from scipy.spatial import cKDTree
d, _ = cKDTree(P).query(P, k=4); dist = np.clip(d[:, 1:].mean(1), 0.01, 1.0); scene_scale = 20.0
print("Wolke", len(P), "Kameras", len(nrs), "Train", len(tr), "Eval", len(ev), flush=True)
SH = 3; N = len(P); sh = torch.zeros(N, (SH + 1) ** 2, 3); sh[:, 0] = torch.from_numpy((C - 0.5) / 0.28209479)
params = torch.nn.ParameterDict({"means": torch.nn.Parameter(torch.from_numpy(P)), "scales": torch.nn.Parameter(torch.log(torch.from_numpy(dist.astype(np.float32)))[:, None].repeat(1, 3)),
    "quats": torch.nn.Parameter(torch.nn.functional.normalize(torch.randn(N, 4), dim=-1)), "opacities": torch.nn.Parameter(torch.logit(torch.full((N,), 0.1))),
    "sh0": torch.nn.Parameter(sh[:, :1]), "shN": torch.nn.Parameter(sh[:, 1:])}).to(dev)
ms = scene_scale; lrs = {"means": 1.6e-4 * ms, "scales": 5e-3, "quats": 1e-3, "opacities": 5e-2, "sh0": 2.5e-3, "shN": 2.5e-3 / 20}
opts = {k: torch.optim.Adam([{"params": params[k], "lr": lrs[k], "name": k}], eps=1e-15) for k in params}
strat = DefaultStrategy(refine_start_iter=500, refine_stop_iter=min(a.schritte - 2000, 10000), refine_every=100, reset_every=3000, grow_grad2d=2e-4, verbose=False, key_for_gradient="gradient_2dgs" if a.zweid else "means2d")
strat.check_sanity(params, opts); st = strat.initialize_state(scene_scale=scene_scale)
pose = torch.zeros(len(nrs), 6, device=dev, requires_grad=bool(a.pose)); popt = torch.optim.Adam([pose], lr=3e-4); pid = {n: i for i, n in enumerate(nrs)}
cM = torch.eye(3, device=dev)[None].repeat(len(nrs), 1, 1).requires_grad_(bool(a.farbe)); cB = torch.zeros(len(nrs), 3, device=dev, requires_grad=bool(a.farbe)); copt = torch.optim.Adam([cM, cB], lr=1e-3)
def rodr(w):
    th = w.norm() + 1e-12; k = w / th; Kx = torch.zeros(3, 3, device=dev); Kx[0, 1], Kx[0, 2], Kx[1, 0], Kx[1, 2], Kx[2, 0], Kx[2, 1] = -k[2], k[1], k[2], -k[0], -k[1], k[0]
    return torch.eye(3, device=dev) + torch.sin(th) * Kx + (1 - torch.cos(th)) * Kx @ Kx
def vm_pose(n):
    p = pose[pid[n]]; T = torch.eye(4, device=dev); T[:3, :3] = rodr(p[:3]); T[:3, 3] = p[3:]; return T @ viewmat(n)
def render(n, sh_deg, vm=None):
    """liefert Bild (H,W,3), erwartete Tiefe (H,W), Alpha (H,W), Extras (nur 2DGS: Normalen, Flaechennormalen, Verzerrung), info"""
    c = cams[n]; vmn = (vm_pose(n) if a.pose else viewmat(n)) if vm is None else vm; args = (params["means"], Fn.normalize(params["quats"], dim=-1), torch.exp(params["scales"]), torch.sigmoid(params["opacities"]), torch.cat([params["sh0"], params["shN"]], 1), vmn[None], Kmat(n)[None], c["W"], c["H"])
    if a.zweid:
        col, al, nor, snor, dist_, med, info = rasterization_2dgs(*args, sh_degree=sh_deg, render_mode="RGB+ED", packed=False, absgrad=False, distloss=True); ex = (nor[0], snor[0], dist_[0, ..., 0])
    else:
        col, al, info = rasterization(*args, sh_degree=sh_deg, render_mode="RGB+ED", packed=False, absgrad=False); ex = None
    return col[0, ..., :3], col[0, ..., 3], al[0, ..., 0], ex, info
def ssim(x, y, w=11):
    g = torch.exp(-(torch.arange(w, device=dev) - w // 2) ** 2 / (2 * 1.5 ** 2)); g = g / g.sum(); k = (g[:, None] * g[None])[None, None].repeat(3, 1, 1, 1)
    f = lambda z: Fn.conv2d(z, k, padding=w // 2, groups=3); mx, my = f(x), f(y); sx, sy, sxy = f(x * x) - mx * mx, f(y * y) - my * my, f(x * y) - mx * my
    c1, c2 = 0.01 ** 2, 0.03 ** 2; return (((2 * mx * my + c1) * (2 * sxy + c2)) / ((mx * mx + my * my + c1) * (sx + sy + c2))).mean()
def psnr(x, y): return float(-10 * torch.log10(((x - y) ** 2).mean().clamp_min(1e-10)))
def luma(x): return (x * torch.tensor([0.299, 0.587, 0.114], device=dev)).sum(-1, keepdim=True).expand(*x.shape[:-1], 3)
def msk_psnr(x, y, m): return psnr(x[m], y[m]) if m is not None else psnr(x, y)
def fitpsnr(x, y, m=None):
    """Diagnose: je Kanal Gain/Versatz per kleinste Quadrate (Belichtungsunterschied herausgerechnet)"""
    z = torch.empty_like(x)
    for ch in range(3): xm = x[..., ch][m] if m is not None else x[..., ch].flatten(); ym = y[..., ch][m] if m is not None else y[..., ch].flatten(); A = torch.stack([xm, torch.ones_like(xm)], 1); s = torch.linalg.lstsq(A, ym[:, None]).solution[:, 0]; z[..., ch] = (x[..., ch] * s[0] + s[1])
    return msk_psnr(z.clamp(0, 1), y, m)
def evaluieren():
    """roh = alle Pixel (vergleichbar mit Lauf 1); ohne_himmel = nur Nicht-Himmel-Pixel der Auswertungsfotos mit Maske (Himmel wird bei Himmelsmaske absichtlich schwarz/transparent); fit = zusaetzlich Gain/Versatz je Kanal je Foto."""
    pe, pn, pf = [], [], []
    for e in ev:
        im_ = render(e, SH)[0].clamp(0, 1); g_ = bilder[e].to(dev).float() / 255.0; m = (~himmel[e].to(dev)) if e in himmel else None
        pe.append(psnr(im_, g_)); pn.append(msk_psnr(im_, g_, m)); pf.append(fitpsnr(im_, g_, m))
    return pe, pn, pf
if a.ckpt_eval:
    ck = torch.load(a.ckpt_eval); 
    for k in params: params[k] = torch.nn.Parameter(ck['params'][k].to(dev))
    pose.data = ck['pose'].to(dev)
    with torch.no_grad(): pe, pn, pf = evaluieren()
    print(json.dumps(dict(ckpt=a.ckpt_eval, gauss=len(params['means']), psnr_eval=float(np.mean(pe)), psnr_eval_ohne_himmel=float(np.mean(pn)), psnr_eval_fit_ohne_himmel=float(np.mean(pf)))), flush=True); sys.exit(0)
log = open(os.path.join(D, "train_log.jsonl"), "w"); t0 = time.time(); acc = []; pa = []; parts = {}
sch = {k: torch.optim.lr_scheduler.ExponentialLR(opts[k], 0.01 ** (1 / a.schritte)) for k in ["means"]}
for step in range(a.schritte):
    n = tr[rng.integers(len(tr))]; gt = bilder[n].to(dev).float() / 255.0; sd = min(SH, step // 1000)
    img, ed, al, ex, info = render(n, sd)
    strat.step_pre_backward(params, opts, st, step, info)
    if a.farbe: i_ = pid[n]; Mi = cM[i_] - cM.mean(0) + torch.eye(3, device=dev); Bi = cB[i_] - cB.mean(0); imgc = (img @ Mi.T + Bi).clamp(0, 1)   # Eichung: Mittel ueber alle Fotos = Identitaet (sonst driftet die Szenenfarbe in die Korrektur)
    else: imgc = img
    if n in sw: imgc = luma(imgc); gt = luma(gt)
    sk = himmel[n].to(dev) if n in himmel else None
    if sk is not None: gt = torch.where(sk[..., None], imgc.detach(), gt)
    loss = 0.8 * (imgc - gt).abs().mean() + 0.2 * (1 - ssim(imgc.permute(2, 0, 1)[None], gt.permute(2, 0, 1)[None])); parts = {"farb": float(loss)}
    if sk is not None and sk.any(): ls = a.w_himmel * (al[sk] ** 2).mean(); loss = loss + ls; parts["himmel"] = float(ls)
    if a.farbe: lf = 1.0 * ((Mi - torch.eye(3, device=dev)) ** 2).sum() + 1.0 * (Bi ** 2).sum(); loss = loss + lf
    if a.tiefe:
        dz = tiefen[n].to(dev); v = (dz > 0) & (al > 0.3)
        if v.any(): lt = a.w_tiefe * ((ed[v] - dz[v]).abs() / dz[v].clamp_min(1.0)).mean(); loss = loss + lt; parts["tiefe"] = float(lt)
    if a.opa:
        o = torch.sigmoid(params["opacities"]); lo = 2e-3 * o.mean()
        if step >= 6000: lo = lo + 1e-2 * (o * (1 - o)).mean()
        loss = loss + lo; parts["opa"] = float(lo)
    if a.zweid:
        nor, snor, dis = ex
        if step >= 7000: ln = 0.05 * ((1 - (nor * snor).sum(-1)) * al.detach()).mean(); loss = loss + ln; parts["normal"] = float(ln)
        if step >= 3000: ld = 0.01 * dis.mean(); loss = loss + ld; parts["dist"] = float(ld)
    if a.pose: loss = loss + 1e-3 * (pose ** 2).sum() / len(nrs)
    loss.backward(); strat.step_post_backward(params, opts, st, step, info)
    if step >= 500 and len(params["means"]) > a.max_gauss: strat.grow_grad2d = 1e9; strat.refine_stop_iter = 0
    for o_ in opts.values(): o_.step(); o_.zero_grad(set_to_none=True)
    if a.pose: popt.step(); popt.zero_grad(set_to_none=True)
    if a.farbe: copt.step(); copt.zero_grad(set_to_none=True)
    for s_ in sch.values(): s_.step()
    acc.append(float(loss)); pa.append(psnr(imgc.clamp(0, 1).detach(), gt))
    if (step + 1) % 500 == 0 or step == a.schritte - 1:
        with torch.no_grad():
            pe, pn, pf = evaluieren()
        r = dict(schritt=step + 1, verlust=float(np.mean(acc)), psnr_train=float(np.mean(pa)), psnr_eval=float(np.mean(pe)), psnr_eval_ohne_himmel=float(np.mean(pn)), psnr_eval_fit_ohne_himmel=float(np.mean(pf)), gauss=len(params["means"]), sek=round(time.time() - t0), vram_gb=round(torch.cuda.max_memory_allocated() / 1e9, 2), teile={k: round(v, 4) for k, v in parts.items()})
        print(json.dumps(r), flush=True); log.write(json.dumps(r) + "\n"); log.flush(); acc = []; pa = []
torch.save({"params": {k: v.detach().cpu() for k, v in params.items()}, "pose": pose.detach().cpu(), "nrs": nrs, "eval": ev, "zweid": bool(a.zweid), "farbeM": cM.detach().cpu(), "farbeB": cB.detach().cpu()}, os.path.join(D, "gs_ckpt.pt")); print("fertig", flush=True)
