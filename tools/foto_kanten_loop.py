#!/usr/bin/env python3
"""foto_kanten_loop.py - Kanten-Schleife (Chamfer, Gradientenabstieg, GPU): STL-Kanten gegen Fotokanten, je Foto Kamera verfeinern, Abweichung je Bauteil messen.

Verfahren (Register BW, PIPELINE_H0.md Abschnitt 8c):
  1. Modellkanten = scharfe Kanten des STL (Winkel > 25 Grad), alle 0,15 m als 3D-Punkte abgetastet; Verdeckung per Tiefenpuffer aus 300 000 Oberflaechenpunkten.
  2. Fotokanten = Canny; Distanztransformation DT (Abstand zur naechsten Fotokante in Pixeln).
  3. Verlust = Mittel von min(DT(Projektion der sichtbaren Modellkante), tmax). Kamera (rvec, t, Brennweite) per Adam (PyTorch autograd, bilineares Lesen der DT), grob nach fein (tmax 60 -> 8 px).
  4. Bericht je Foto und Bauteil (Helm, Tuermchen, Zinnenkranz, Wand oben, Wand unten): Median-Abweichung in Pixeln und Metern (m = px * Tiefe / f).
     Abweichungskarte (Raster 16 x 24) als Bild: gruen < 4 px, rot > 15 px.
Kameras aus modelle/<objekt>/messprotokoll/K-<nr>.json (rvec, t, f_px, cx, cy); unbrauchbare (f_px > 20000) entfallen.
Dies ist KEIN Beleg fuer eine Modelländerung allein: erst wenn ein Bauteil auf mehreren Fotos gleichgerichtet abweicht (Mehrheitsregel wie foto_loop.py).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_kanten_loop.py [--fotos 030 031 040 041] [--objekt modelle/martinstor] [--stl ...]
"""
import sys, os, json, glob, time, math, argparse, subprocess, numpy as np, cv2, torch, trimesh
dev = "cuda"

def gpu_warten(max_mib=1500, max_s=3600):
    t0 = time.time()
    while time.time() - t0 < max_s:
        try: used = int(subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).decode().split()[0])
        except Exception: return
        if used < max_mib: return
        time.sleep(20)

def rodrigues(r):
    th = r.norm() + 1e-9; k = r / th; K = torch.zeros(3, 3, device=r.device, dtype=r.dtype)
    K[0, 1], K[0, 2], K[1, 0], K[1, 2], K[2, 0], K[2, 1] = -k[2], k[1], k[2], -k[0], -k[1], k[0]
    return torch.eye(3, device=r.device, dtype=r.dtype) + torch.sin(th) * K + (1 - torch.cos(th)) * (K @ K)

def projiziere(X, rvec, t, logf, cx, cy):
    Xc = X @ rodrigues(rvec).T + t; z = Xc[:, 2]; f = torch.exp(logf)
    return torch.stack([f * Xc[:, 0] / z + cx, f * Xc[:, 1] / z + cy], 1), z

REGIONEN = [("Helm", lambda P: (P[:, 2] > 38) & (P[:, 0].abs() < 3.2) & (P[:, 1].abs() < 3.2)),
            ("Tuermchen", lambda P: (P[:, 2] > 36.5) & (P[:, 0].abs() >= 2.8) & (P[:, 1].abs() >= 2.8)),
            ("Zinnenkranz", lambda P: (P[:, 2] > 29.5) & (P[:, 2] <= 36.5)),
            ("Wand oben", lambda P: (P[:, 2] > 15) & (P[:, 2] <= 29.5)),
            ("Wand unten/Tor", lambda P: (P[:, 2] <= 15))]

def modellkanten(stl, schritt=0.15):
    m = trimesh.load(stl); m.apply_scale(0.087)
    sharp = m.face_adjacency_edges[m.face_adjacency_angles > np.radians(25)]; V = np.asarray(m.vertices); pts = []; dirs = []
    for a, b in sharp:
        L = np.linalg.norm(V[b] - V[a]); n = max(2, int(math.ceil(L / schritt)) + 1); s = np.linspace(0, 1, n)[:, None]; pts.append(V[a] + s * (V[b] - V[a])); dirs.append(np.tile((V[b] - V[a]) / max(L, 1e-9), (n, 1)))
    E = np.vstack(pts).astype(np.float32); D = np.vstack(dirs).astype(np.float32); S, _ = trimesh.sample.sample_surface(m, 300000, seed=0)
    return torch.as_tensor(E, device=dev), torch.as_tensor(S.astype(np.float32), device=dev), torch.as_tensor(D, device=dev)

def sichtbar(E, S, cam, W, H):
    with torch.no_grad():
        uv, z = projiziere(S, cam["r"], cam["t"], cam["lf"], cam["cx"], cam["cy"])
        ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < W) & (uv[:, 1] >= 0) & (uv[:, 1] < H)
        iu = uv[ok, 0].floor().long().clamp(0, W - 1); iv = uv[ok, 1].floor().long().clamp(0, H - 1)
        zb = torch.full((H * W,), 1e9, device=dev); zb.scatter_reduce_(0, iv * W + iu, z[ok], reduce="amin"); zb = zb.view(1, 1, H, W)
        zb = -torch.nn.functional.max_pool2d(-zb, 7, 1, 3)[0, 0]
        ue, ze = projiziere(E, cam["r"], cam["t"], cam["lf"], cam["cx"], cam["cy"]); oke = (ze > 1) & (ue[:, 0] >= 0) & (ue[:, 0] < W - 1) & (ue[:, 1] >= 0) & (ue[:, 1] < H - 1)
        iu = ue[:, 0].floor().long().clamp(0, W - 1); iv = ue[:, 1].floor().long().clamp(0, H - 1); vis = oke & (ze <= zb[iv, iu] + 0.3)
    return vis

def foto_dts(im):
    """4 Distanztransformationen (Kantenrichtung 0/45/90/135 Grad), nur lange Kanten (> 20 px)."""
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (3, 3), 0); ed = cv2.Canny(g, 50, 140)
    n, lab, st, _ = cv2.connectedComponentsWithStats((ed > 0).astype(np.uint8), connectivity=8); keep = np.isin(lab, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 20]); ed = (keep * 255).astype(np.uint8)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3); ang = (np.degrees(np.arctan2(gy, gx)) + 90) % 180   # Kantenrichtung = Gradient + 90
    b = ((ang + 22.5) // 45).astype(int) % 4; out = []
    for k in range(4): out.append(cv2.distanceTransform(((ed > 0) & (b == k)) == 0, cv2.DIST_L2, 5).astype(np.float32) if False else cv2.distanceTransform((~((ed > 0) & (b == k))).astype(np.uint8), cv2.DIST_L2, 5))
    return torch.as_tensor(np.stack(out), device=dev, dtype=torch.float32), float((ed > 0).mean())

def dt_lesen(DT, uv, W, H, bins=None):
    if DT.dim() == 3:
        g = torch.stack([uv[:, 0] / (W - 1) * 2 - 1, uv[:, 1] / (H - 1) * 2 - 1], 1)[None, None]
        v = torch.nn.functional.grid_sample(DT[None], g, align_corners=True, padding_mode="border")[0, :, 0, :]      # (4,N)
        return v.gather(0, bins[None])[0]
    return dt_lesen_alt(DT, uv, W, H)

def kantenbin(E, D, cam):
    """Richtungsklasse der projizierten Modellkante (0/45/90/135 Grad im Bild)."""
    with torch.no_grad():
        a, _ = projiziere(E, cam["r"], cam["t"], cam["lf"], cam["cx"], cam["cy"]); b, _ = projiziere(E + 0.1 * D, cam["r"], cam["t"], cam["lf"], cam["cx"], cam["cy"])
        ang = torch.rad2deg(torch.atan2(b[:, 1] - a[:, 1], b[:, 0] - a[:, 0])) % 180; return (((ang + 22.5) // 45).long()) % 4

def dt_lesen_alt(DT, uv, W, H):
    g = torch.stack([uv[:, 0] / (W - 1) * 2 - 1, uv[:, 1] / (H - 1) * 2 - 1], 1)[None, None]
    return torch.nn.functional.grid_sample(DT[None, None], g, align_corners=True, padding_mode="border")[0, 0, 0]

def verfeinern(E, S, D, cam, DT, W, H):
    r = cam["r"].clone().requires_grad_(True); t = cam["t"].clone().requires_grad_(True); lf = cam["lf"].clone().requires_grad_(True)
    opt = torch.optim.Adam([dict(params=[r], lr=2e-3), dict(params=[t], lr=0.05), dict(params=[lf], lr=3e-3)])
    for tmax in (60., 30., 15., 8.):
        for it in range(60):
            if it % 20 == 0: c2 = dict(cam, r=r.detach(), t=t.detach(), lf=lf.detach()); vis = sichtbar(E, S, c2, W, H); bins = kantenbin(E, D, c2)
            uv, z = projiziere(E[vis], r, t, lf, cam["cx"], cam["cy"]); d = dt_lesen(DT, uv, W, H, bins[vis]); loss = torch.clamp(d, max=tmax).mean()
            opt.zero_grad(); loss.backward(); opt.step()
    return dict(cam, r=r.detach(), t=t.detach(), lf=lf.detach())

def bericht_und_karte(E, S, D, cam, DT, im, W, H, pfad):
    vis = sichtbar(E, S, cam, W, H); uv, z = projiziere(E, cam["r"], cam["t"], cam["lf"], cam["cx"], cam["cy"]); d = dt_lesen(DT, uv, W, H, kantenbin(E, D, cam)); f = float(torch.exp(cam["lf"]))
    Pn = E; res = {}
    for name, fn in REGIONEN:
        k = fn(Pn) & vis
        if int(k.sum()) < 30: continue
        dk = d[k]; med = float(dk.median()); res[name] = dict(punkte=int(k.sum()), median_px=round(med, 1), median_m=round(med * float(z[k].median()) / f, 3), anteil_ueber_8px=round(float((dk > 8).float().mean()), 2))
    vis_img = im.copy(); gx, gy = 16, 24; ov = vis_img.copy(); u = uv[vis].detach().cpu().numpy(); dd = d[vis].detach().cpu().numpy()
    for i in range(gx):
        for j in range(gy):
            x0, x1, y0, y1 = int(i * W / gx), int((i + 1) * W / gx), int(j * H / gy), int((j + 1) * H / gy)
            k = (u[:, 0] >= x0) & (u[:, 0] < x1) & (u[:, 1] >= y0) & (u[:, 1] < y1)
            if k.sum() < 8: continue
            m = float(np.median(dd[k])); c = (0, 200, 0) if m < 4 else ((0, 200, 255) if m < 9 else ((0, 120, 255) if m < 15 else (0, 0, 230)))
            cv2.rectangle(ov, (x0, y0), (x1 - 1, y1 - 1), c, -1)
    vis_img = cv2.addWeighted(ov, 0.35, vis_img, 0.65, 0)
    for p in u[::3]: cv2.circle(vis_img, (int(p[0]), int(p[1])), 1, (255, 255, 255), -1)
    cv2.imwrite(pfad, vis_img); return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fotos", nargs="*"); ap.add_argument("--objekt", default="modelle/martinstor"); ap.add_argument("--stl", default="modelle/stl/martinstor_v4_1-87.stl"); ap.add_argument("--breite", type=int, default=640); ap.add_argument("--versatz-tuermchen", nargs=3, type=float, default=None, help="Nulltest: nur die 4 Eck-Tuermchen (z>36.5, |x|,|y|>2.8) um dx dy dz verschieben (Vorzeichen: nach aussen = +, je Ecke gespiegelt)"); ap.add_argument("--versatz", nargs=3, type=float, default=None, help="Nulltest: STL um dx dy dz Meter verschieben (Modellrahmen); Ausgabe nach audit/foto_kanten_versatz_<dx>_<dy>_<dz>")
    a = ap.parse_args(); gpu_warten(); out = os.path.join(a.objekt, "audit", "foto_kanten" if not a.versatz else "foto_kanten_versatz_%g_%g_%g" % tuple(a.versatz)); os.makedirs(out, exist_ok=True); E, S, D = modellkanten(a.stl)
    if a.versatz_tuermchen:
        out = os.path.join(a.objekt, "audit", "foto_kanten_tuerm_%g_%g_%g" % tuple(a.versatz_tuermchen)); os.makedirs(out, exist_ok=True); sv = torch.tensor(a.versatz_tuermchen, device=dev, dtype=torch.float32)
        def vs(X):
            m = (X[:, 2] > 36.5) & (X[:, 0].abs() > 2.8) & (X[:, 1].abs() > 2.8); X = X.clone(); X[m] += torch.sign(X[m]) * sv * torch.tensor([1, 1, 0], device=dev) + torch.tensor([0, 0, 1.], device=dev) * sv[2]; return X
        E = vs(E); S = vs(S)
    if a.versatz: sh = torch.tensor(a.versatz, device=dev, dtype=torch.float32); E = E + sh; S = S + sh
    print("Kantenpunkte", len(E), flush=True)
    nrs = a.fotos or [os.path.basename(p)[2:-5] for p in sorted(glob.glob(os.path.join(a.objekt, "messprotokoll", "K-*.json")))]; log = dict(start=time.strftime("%Y-%m-%d %H:%M"), fotos={})
    for nr in nrs:
        Kd = json.load(open(os.path.join(a.objekt, "messprotokoll", f"K-{nr}.json"))); k = Kd.get("kamera", Kd)
        if "rvec" not in k or k.get("f_px", 0) > 20000: print(nr, "keine brauchbare Kamera"); continue
        fn = glob.glob(f"daten/martinstor/fotos/{nr}_*")
        if not fn: continue
        im0 = cv2.imread(fn[0]); h0, w0 = im0.shape[:2]; s = a.breite / w0; im = cv2.resize(im0, (a.breite, int(h0 * s)), interpolation=cv2.INTER_AREA); H, W = im.shape[:2]
        DT, kd = foto_dts(im)
        cam = dict(r=torch.tensor(k["rvec"], device=dev, dtype=torch.float32), t=torch.tensor(k["t"], device=dev, dtype=torch.float32), lf=torch.tensor(math.log(k["f_px"] * s), device=dev, dtype=torch.float32), cx=k.get("cx", w0 / 2) * s, cy=k.get("cy", h0 / 2) * s)
        vor = bericht_und_karte(E, S, D, cam, DT, im, W, H, f"{out}/vorher_{nr}.png"); cam2 = verfeinern(E, S, D, cam, DT, W, H); nach = bericht_und_karte(E, S, D, cam2, DT, im, W, H, f"{out}/nachher_{nr}.png")
        log["fotos"][nr] = dict(vorher=vor, nachher=nach, f_px_nachher=round(float(torch.exp(cam2["lf"])) / s, 1), rvec=[float(x) for x in cam2["r"]], t=[float(x) for x in cam2["t"]])
        print(nr, "Median px vorher/nachher:", {n: (vor.get(n, {}).get("median_px"), nach[n]["median_px"]) for n in nach}, flush=True)
        json.dump(log, open(f"{out}/foto_kanten.json", "w"), indent=1, ensure_ascii=False)
    print("fertig ->", out)

if __name__ == "__main__":
    main()
