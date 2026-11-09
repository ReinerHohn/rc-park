"""Gemeinsame GPU-Bausteine fuer die Kanten-Schleife: sequentielles RANSAC fuer 3D-Geradensegmente."""
import numpy as np, torch
def ransac_segmente(X, tol=0.015, minlen=0.15, minpts=25, seed=1, maxit=3000, log=None):
    """X: (N,3) torch cuda. Liefert Liste [p0,p1,npts]. Inlier werden entfernt, Fehlversuche verkleinern den Rest (kein Endlosloop)."""
    g = torch.Generator(device="cuda").manual_seed(seed); segs = []; alive = torch.ones(len(X), dtype=torch.bool, device="cuda")
    for it in range(maxit):
        idx = alive.nonzero().squeeze(1)
        if len(idx) < minpts: break
        Y = X[idx]; M = 3000; a = torch.randint(0, len(Y), (M,), device="cuda", generator=g)
        cand = torch.randint(0, len(Y), (M, 400), device="cuda", generator=g); dd = (Y[cand] - Y[a][:, None]).norm(dim=2); dd = torch.where((dd > 0.1) & (dd < 0.6), dd, torch.full_like(dd, 1e9)); j = dd.argmin(1); b = cand[torch.arange(M), j]; okp = dd[torch.arange(M), j] < 1e8
        A = Y[a]; Dv = Y[b] - A; Dv = Dv / Dv.norm(dim=1, keepdim=True).clamp(min=1e-9); sc = torch.zeros(M, device="cuda")
        CH = int(max(8, min(500, 3e7 // max(len(Y), 1))))                     # Blockgroesse nach Punktzahl (sonst GPU-OOM bei >100k Punkten)
        for c0 in range(0, M, CH):
            w = Y[None] - A[c0:c0 + CH, None]; t = (w * Dv[c0:c0 + CH, None]).sum(2); sc[c0:c0 + CH] = ((w - t[..., None] * Dv[c0:c0 + CH, None]).norm(dim=2) < tol).sum(1)
        sc = torch.where(okp, sc, torch.zeros_like(sc)); k = int(sc.argmax())
        if sc[k] < minpts: break
        w = Y - A[k]; t = (w * Dv[k]).sum(1); inl = (w - t[:, None] * Dv[k]).norm(dim=1) < tol; ti = t[inl]; ii = idx[inl]; o = ti.argsort(); ti = ti[o]; ii = ii[o]
        cut = torch.where(ti[1:] - ti[:-1] > 0.12)[0] + 1; runs = torch.tensor_split(torch.arange(len(ti), device="cuda"), cut.tolist()); used = False
        for rn in runs:
            if len(rn) >= minpts and float(ti[rn[-1]] - ti[rn[0]]) >= minlen:
                segs.append([(A[k] + Dv[k] * ti[rn[0]]).tolist(), (A[k] + Dv[k] * ti[rn[-1]]).tolist(), int(len(rn))]); alive[ii[rn]] = False; used = True
        if not used: alive[ii[:max(1, len(ii) // 4)]] = False
        if log and it % 100 == 0: print("  RANSAC Iter", it, "Segmente", len(segs), "Rest", int(alive.sum()), flush=True)
    return segs
