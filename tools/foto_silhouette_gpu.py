#!/usr/bin/env python3
"""foto_silhouette_gpu.py - Silhouettenvergleich Modell gegen Foto (Himmelsmaske), Kameralage per GPU-Suche (Zufall + CEM). Aufruf: foto_silhouette_gpu.py 044 [seed] [out.png]. Grenzen: Quadratturm -> Azimut um 90 Grad mehrdeutig, Abstand/Brennweite gekoppelt; Anpassung gilt nur im ROI (oberer Turm)."""
import sys, json, numpy as np, cv2, torch, trimesh
dev = "cuda"
FOTOS = {
 "042": ("042_Freiburg_im_Breisgau_Martinstor_1.jpg",  dict(roi=(100, 0, 235, 165))),
 "043": ("043_Freiburg_im_Breisgau_Martinstor_2.jpg",  dict(roi=(40, 0, 290, 330))),
 "044": ("044_Freiburg_im_Breisgau_Martinstor_3.jpg",  dict(roi=(120, 0, 260, 235))),
}
FD = "/home/oem/git/rc-park/daten/martinstor/fotos/"
STL = "/home/oem/git/rc-park/modelle/stl/martinstor_v4_1-87.stl"

# Objektkonfiguration (generisch): modelle/<objekt>/objekt.json liefert Fotos (mit Seite/ROI), Foto-Ordner und STL. Umgebungsvariable OBJEKT.
import os as _os, glob as _glob
OBJEKT = _os.environ.get("OBJEKT", "/home/oem/git/rc-park/modelle/martinstor/objekt.json")
if _os.path.exists(OBJEKT):
    _o = json.load(open(OBJEKT)); _root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(OBJEKT))))
    FD = _os.path.join(_root, _o["fotos_dir"]) + "/"; STL = _os.path.join(_root, _o["stl"])
    for _nr, _cfg in _o.get("fotos", {}).items():
        _f = _glob.glob(FD + _nr + "_*")
        if _f and _cfg.get("silhouette_frei"):
            _alt = FOTOS.get(_nr, (None, {}))[1]
            FOTOS[_nr] = (_os.path.basename(_f[0]), dict(roi=tuple(_cfg["roi"]) if "roi" in _cfg else _alt.get("roi"), seite=_cfg.get("seite")))

def sky_mask(im):
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(float)
    ref = np.median(lab[:6, :], axis=(0, 1)); d = np.linalg.norm(lab - ref, axis=2)
    n, l = cv2.connectedComponents((d < 22).astype(np.uint8))
    ids = [x for x in np.unique(l[:3, :]) if x > 0]
    return np.isin(l, ids)

def load_points(n=200000, seed=0):
    m = trimesh.load(STL); m.apply_scale(87 / 1000.0)
    c = m.bounds.mean(0) if globals().get('_o', {}).get('zentrierung', 'huelle') == 'huelle' else np.zeros(3)   # objekt.json: 'achse' = Generatorachse behalten
    m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]])
    p, _ = trimesh.sample.sample_surface(m, n, seed=seed)
    return torch.as_tensor(p, dtype=torch.float32, device=dev), m

def render(P, th, W, H, f0, chunk=128):
    """th: (B,8) [d, az, el, tz, roll, fs, sx, sy] -> (B,H,W) bool Silhouette"""
    B = th.shape[0]; out = torch.zeros((B, H, W), dtype=torch.bool, device=dev)
    for i in range(0, B, chunk):
        t = th[i:i + chunk]; b = t.shape[0]
        d, az, el, tz, ro, fs, sx, sy = [t[:, k] for k in range(8)]
        tgt = torch.stack([torch.zeros_like(tz), torch.zeros_like(tz), tz], 1)
        cam = tgt + d[:, None] * torch.stack([torch.sin(az) * torch.cos(el), -torch.cos(az) * torch.cos(el), torch.sin(el)], 1)
        fwd = tgt - cam; fwd = fwd / fwd.norm(dim=1, keepdim=True)
        up = torch.tensor([0., 0., 1.], device=dev).expand_as(fwd)
        x = torch.cross(fwd, up, dim=1); x = x / x.norm(dim=1, keepdim=True)
        y = torch.cross(fwd, x, dim=1)
        # Roll um die Blickachse
        cr, sr = torch.cos(ro)[:, None], torch.sin(ro)[:, None]
        x2 = cr * x + sr * y; y2 = -sr * x + cr * y
        rel = P[None] - cam[:, None]                              # (b,N,3)
        xc = (rel * x2[:, None]).sum(2); yc = (rel * y2[:, None]).sum(2); zc = (rel * fwd[:, None]).sum(2)
        f = f0 * fs
        u = f[:, None] * xc / zc.clamp(min=1.0) + W / 2 + sx[:, None]
        v = f[:, None] * yc / zc.clamp(min=1.0) + H / 2 + sy[:, None]
        ok = (zc > 1.0) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        iu = u.floor().long().clamp(0, W - 1); iv = v.floor().long().clamp(0, H - 1)
        flat = (torch.arange(b, device=dev)[:, None] * H * W + iv * W + iu)[ok]
        m = torch.zeros(b * H * W, dtype=torch.float16, device=dev); m[flat] = 1
        m = m.view(b, 1, H, W); m = torch.nn.functional.max_pool2d(m, 3, 1, 1)
        out[i:i + b] = m[:, 0] > 0
    return out

def score(P, th, T, roi, f0, W, H, hcam_w=0.02):
    x0, y0, x1, y1 = roi
    M = render(P, th, W, H, f0)[:, y0:y1, x0:x1]; Tr = T[None, y0:y1, x0:x1]
    inter = (M & Tr).sum((1, 2)).float(); uni = (M | Tr).sum((1, 2)).float()
    iou = inter / uni.clamp(min=1)
    camz = th[:, 3] + th[:, 0] * torch.sin(th[:, 2])                # Kamerahoehe ueber Grund
    pen = hcam_w * ((camz - 1.7) / 3.0) ** 2
    return iou - pen, iou

def fit(key, seed=0, nrand=30000, iters=60, B=1024):
    fn, cfg = FOTOS[key]; im = cv2.imread(FD + fn); h, w = im.shape[:2]; s = 400 / w
    im = cv2.resize(im, (400, int(h * s))); H, W = im.shape[:2]
    T = torch.as_tensor(~sky_mask(im), device=dev); roi = cfg["roi"]
    f0 = 5.4 / 4.29 * W                                      # Pentax 5,4 mm an 1/2,5"-Sensor (Annahme), wird per fs angepasst
    P, _ = load_points(); g = torch.Generator(device=dev).manual_seed(seed)
    lo = torch.tensor([25, -3.2, -1.25, 12, -0.15, 0.6, -120, -120.], device=dev); hi = torch.tensor([200, 3.2, 0.05, 48, 0.15, 1.8, 120, 120.], device=dev)
    # Stufe 1: Zufall
    best = []
    for _ in range(nrand // B):
        th = lo + (hi - lo) * torch.rand((B, 8), device=dev, generator=g)
        sc, iou = score(P, th, T, roi, f0, W, H); k = sc.topk(20).indices; best.append((sc[k], th[k]))
    sc = torch.cat([b[0] for b in best]); th = torch.cat([b[1] for b in best]); k = sc.topk(40).indices
    mu = th[k].mean(0); sd = th[k].std(0) + 1e-3; bs, bth = sc[k[0]].item(), th[k[0]].clone()
    # Stufe 2: CEM
    for it in range(iters):
        cand = mu + sd * torch.randn((B, 8), device=dev, generator=g); cand = torch.max(torch.min(cand, hi), lo)
        sc, iou = score(P, cand, T, roi, f0, W, H); k = sc.topk(B // 10).indices
        mu = 0.5 * mu + 0.5 * cand[k].mean(0); sd = 0.6 * sd + 0.4 * cand[k].std(0) + 1e-4
        if sc[k[0]].item() > bs: bs, bth = sc[k[0]].item(), cand[k[0]].clone()
    sc, iou = score(P, bth[None], T, roi, f0, W, H)
    return dict(key=key, score=sc.item(), iou=iou.item(), th=bth.tolist(), f0=f0, W=W, H=H, roi=roi), im, T, P

def overlay(res, im, P, path):
    th = torch.tensor(res["th"], device=dev)[None]
    M = render(P, th, res["W"], res["H"], res["f0"])[0].cpu().numpy().astype(np.uint8)
    vis = im.copy(); cnt, _ = cv2.findContours(M, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(vis, cnt, -1, (0, 0, 255), 1); x0, y0, x1, y1 = res["roi"]; cv2.rectangle(vis, (x0, y0), (x1, y1), (0, 255, 0), 1)
    cv2.imwrite(path, cv2.resize(vis, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC))

if __name__ == "__main__":
    key = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    res, im, T, P = fit(key, seed)
    print(json.dumps(res, default=float))
    overlay(res, im, P, sys.argv[3] if len(sys.argv) > 3 else f"/tmp/fit_{key}.png")
