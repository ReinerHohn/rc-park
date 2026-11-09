"""Kantenpunkte (kanten_3d_vote) -> 3D-Geradensegmente per GPU-RANSAC (sequentiell, Inlier entfernen).
Aufruf: python -I tools/kanten_segmente.py KANTEN.npz OUT.json [--sicht 6] [--anteil 0.5] [--tol 0.015] [--minlen 0.15] [--minpts 25]
Segmente = [[x,y,z],[x,y,z]] in Netzkoordinaten; Bogenstuecke entstehen als Folge kurzer Segmente (ANNAHME: spaeter Kreisfit)."""
import sys, json, numpy as np, torch
def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
sicht = opt("--sicht", 6, int); anteil = opt("--anteil", 0.5); tol = opt("--tol", 0.015); minlen = opt("--minlen", 0.15); minpts = opt("--minpts", 25, int)
z = np.load(sys.argv[1]); v = z["vis"]; r = z["kan"] / np.maximum(v, 1); m = (v >= sicht) & (r >= anteil); X = torch.from_numpy(z["P"][m]).cuda(); print("Kantenpunkte", len(X), flush=True)
g = torch.Generator(device="cuda").manual_seed(1); segs = []; alive = torch.ones(len(X), dtype=torch.bool, device="cuda")
for it in range(3000):
    idx = alive.nonzero().squeeze(1)
    if len(idx) < minpts: break
    Y = X[idx]; M = 3000; a = torch.randint(0, len(Y), (M,), device="cuda", generator=g); b = torch.randint(0, len(Y), (M,), device="cuda", generator=g)
    # zweiter Punkt in der Naehe von a: aus 400 Zufallskandidaten der naechste im Abstand 0.1..0.6 m
    cand = torch.randint(0, len(Y), (M, 400), device="cuda", generator=g); dd = (Y[cand] - Y[a][:, None]).norm(dim=2); dd = torch.where((dd > 0.1) & (dd < 0.6), dd, torch.full_like(dd, 1e9)); j = dd.argmin(1); b = cand[torch.arange(M), j]; okp = dd[torch.arange(M), j] < 1e8
    A = Y[a]; Dv = Y[b] - A; Dv = Dv / Dv.norm(dim=1, keepdim=True).clamp(min=1e-9); best = (-1, None, None); sc = torch.zeros(M, device="cuda")
    for c0 in range(0, M, 500):
        w = Y[None] - A[c0:c0 + 500, None]; t = (w * Dv[c0:c0 + 500, None]).sum(2); dist = (w - t[..., None] * Dv[c0:c0 + 500, None]).norm(dim=2); sc[c0:c0 + 500] = (dist < tol).sum(1)
    sc = torch.where(okp, sc, torch.zeros_like(sc)); k = int(sc.argmax())
    if sc[k] < minpts: break
    w = Y - A[k]; t = (w * Dv[k]).sum(1); inl = (w - t[:, None] * Dv[k]).norm(dim=1) < tol; ti = t[inl]; ii = idx[inl]; o = ti.argsort(); ti = ti[o]; ii = ii[o]
    cut = torch.where(ti[1:] - ti[:-1] > 0.12)[0] + 1; runs = torch.tensor_split(torch.arange(len(ti), device="cuda"), cut.tolist()); used = False
    for rn in runs:
        if len(rn) >= minpts and float(ti[rn[-1]] - ti[rn[0]]) >= minlen:
            p0 = A[k] + Dv[k] * ti[rn[0]]; p1 = A[k] + Dv[k] * ti[rn[-1]]; segs.append([p0.tolist(), p1.tolist(), int(len(rn))]); alive[ii[rn]] = False; used = True
    if not used: alive[ii[:max(1, len(ii) // 4)]] = False                   # Fehlversuch: Teil entfernen, Endlosschleife vermeiden
    if it % 100 == 0: print("Iter", it, "Segmente", len(segs), "Rest", int(alive.sum()), flush=True)
json.dump({"segmente": segs, "tol": tol, "quelle": sys.argv[1]}, open(sys.argv[2], "w")); print("Segmente", len(segs), "Restpunkte", int(alive.sum()))
