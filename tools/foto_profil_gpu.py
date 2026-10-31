#!/usr/bin/env python3
"""foto_profil_gpu.py - ALLGEMEINES Abweichungsprofil Modell <-> Fotos ueber die Hoehe (kein Bauteil vorab bekannt).

Je Foto: Kamera per GPU an die Silhouette anpassen (wie foto_silhouette_gpu), dann bei hoher Aufloesung Zeile fuer Zeile die BREITE der
Turm-Silhouette im Foto und im Modell messen, in Meter umrechnen (Abstand/Brennweite der angepassten Kamera) und der Hoehe z zuordnen.
Ergebnis: Tabelle z -> Breite Foto / Breite Modell / Verhaeltnis. Ein ueber alle Fotos gleiches Verhaeltnisprofil ausser einem konstanten Faktor
(= Massstabsfehler der Kamera, wird herausgerechnet) zeigt eine echte Formabweichung - ohne dass man das Bauteil vorher kennen muss.

  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_profil_gpu.py [--stl modelle/stl/martinstor_v4_1-87.stl] [Foto-Nr ...]
Grenzen: Silhouette -> nur Breiten (nicht Tiefe/Relief); Verdeckung durch Baeume/Haeuser (ROI); Kamera d/f gekoppelt (Faktor wird normiert).
"""
import sys, json, math, numpy as np, cv2, torch
sys.path.insert(0, "/home/oem/git/rc-park/tools")
import foto_silhouette_gpu as F
dev = F.dev
lo = torch.tensor([25, -3.2, -1.25, 12, -0.15, 0.6, -120, -120.], device=dev); hi = torch.tensor([200, 3.2, 0.05, 48, 0.15, 1.8, 120, 120.], device=dev)
UP = 2          # Messaufloesung = UP x 400 px

def prep(key, width=400):
    fn, cfg = F.FOTOS[key]; im = cv2.imread(F.FD + fn); h, w = im.shape[:2]; s = width / w
    im = cv2.resize(im, (width, int(h * s)), interpolation=cv2.INTER_AREA)
    return im, ~F.sky_mask(im), cfg["roi"]

def cem(P, T, roi, H, W, f0, mu, sd, iters, B=256, seed=0):
    g = torch.Generator(device=dev).manual_seed(seed); bs, bth = -9, mu.clone()
    for _ in range(iters):
        c = torch.max(torch.min(mu + sd * torch.randn((B, 8), device=dev, generator=g), hi), lo); c[0] = bth
        sc, _ = F.score(P, c, T, roi, f0, W, H); k = sc.topk(B // 10).indices
        mu = 0.5 * mu + 0.5 * c[k].mean(0); sd = 0.7 * sd + 0.3 * c[k].std(0) + 1e-4
        if sc[k[0]].item() > bs: bs, bth = sc[k[0]].item(), c[k[0]].clone()
    return bs, bth

def fit_pose(P, key, seeds=(0, 1, 2)):
    im, T400, roi = prep(key); T = torch.as_tensor(T400, device=dev); H, W = im.shape[:2]; f0 = 5.4 / 4.29 * W; best = None
    for sd_ in seeds:
        g = torch.Generator(device=dev).manual_seed(sd_); cand = []
        for _ in range(96):
            th = lo + (hi - lo) * torch.rand((256, 8), device=dev, generator=g); sc, _ = F.score(P, th, T, roi, f0, W, H); k = sc.topk(20).indices; cand.append((sc[k], th[k]))
        sc = torch.cat([c[0] for c in cand]); th = torch.cat([c[1] for c in cand]); k = sc.topk(40).indices
        s, t = cem(P, T, roi, H, W, f0, th[k].mean(0), th[k].std(0) + 1e-3, 50, seed=sd_)
        if best is None or s > best[0]: best = (s, t)
    return best, f0

def project(th, f0, W, H, pts):
    d, az, el, tz, ro, fs, sx, sy = [float(x) for x in th]
    tgt = np.array([0, 0, tz]); cam = tgt + d * np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
    fwd = tgt - cam; fwd /= np.linalg.norm(fwd); x = np.cross(fwd, [0, 0, 1]); x /= np.linalg.norm(x); y = np.cross(fwd, x)
    cr, sr = math.cos(ro), math.sin(ro); x2 = cr * x + sr * y; y2 = -sr * x + cr * y
    rel = pts - cam; xc, yc, zc = rel @ x2, rel @ y2, rel @ fwd; f = f0 * fs
    return np.c_[f * xc / zc + W / 2 + sx, f * yc / zc + H / 2 + sy], f, d

def run_width(mask_row, x0):
    xs = np.nonzero(mask_row)[0]
    if len(xs) == 0: return None
    br = np.nonzero(np.diff(xs) > 2)[0]; runs = np.split(xs, br + 1)
    r = min(runs, key=lambda q: 0 if q[0] <= x0 <= q[-1] else min(abs(q[0] - x0), abs(q[-1] - x0)))
    return r[0], r[-1] + 1

def profil(P, key, zgrid):
    (s, th), f0 = fit_pose(P, key); im4, T4, roi = prep(key, 400); im, T, _ = prep(key, 400 * UP)
    H, W = im.shape[:2]; th2 = th.clone(); th2[6] *= UP; th2[7] *= UP
    M = F.render(P, th2[None], W, H, f0 * UP)[0].cpu().numpy()
    M = cv2.morphologyEx(M.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8)).astype(bool)
    zs = zgrid; ax, f, d = project(th.cpu().numpy(), f0, 400, im4.shape[0], np.c_[np.zeros_like(zs), np.zeros_like(zs), zs])
    ax = ax * UP; mpp = d / (f * UP)                       # Meter je Pixel (Messbild)
    out = []
    for z, (u, v) in zip(zs, ax):
        y = int(round(v))
        if y < roi[1] * UP or y >= roi[3] * UP or y >= H: out.append((z, None, None)); continue
        a = run_width(T[y], u); b = run_width(M[y], u)
        out.append((z, None if a is None else (a[1] - a[0]) * mpp, None if b is None else (b[1] - b[0]) * mpp))
    return s, out

def main():
    a = sys.argv[1:]; stl = F.STL
    if "--stl" in a: i = a.index("--stl"); stl = a[i + 1]; a = a[:i] + a[i + 2:]
    F.STL = stl; keys = a or ["042", "043", "044"]
    P, _ = F.load_points(200000); zg = np.arange(33.0, 55.0, 1.0); allr = {}
    for k in keys:
        s, prof = profil(P, k, zg); allr[k] = prof; print(f"Foto {k}: IoU {s:.3f}", flush=True)
    print("\n z (m)   " + "   ".join(f"{k}: Foto/Modell/Verh." for k in keys) + "   | Mittel Verhaeltnis (auf Median normiert)")
    rat = {k: np.array([(p / m) if (p and m and m > 0.05) else np.nan for _, p, m in allr[k]]) for k in keys}
    med = {k: np.nanmedian(rat[k][(zg >= 36) & (zg <= 48)]) for k in keys}      # konstanter Faktor = Kamera-Massstabsfehler
    for i, z in enumerate(zg):
        cells = []
        for k in keys:
            _, p, m = allr[k][i]; cells.append("   --   " if not (p and m) else f"{p:4.1f}/{m:4.1f}/{rat[k][i]:4.2f}")
        norm = [rat[k][i] / med[k] for k in keys if not np.isnan(rat[k][i])]
        mn = np.mean(norm) if norm else float("nan"); flag = "  <== Foto BREITER" if mn > 1.15 else ("  <== Foto SCHMALER" if mn < 0.85 else "")
        print(f" {z:5.1f}   " + "   ".join(cells) + f"   | {mn:5.2f}{flag}")
    json.dump({k: [(float(z), p, m) for z, p, m in v] for k, v in allr.items()}, open("/tmp/foto_profil.json", "w"))

if __name__ == "__main__":
    main()
