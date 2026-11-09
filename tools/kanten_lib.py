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

def ransac_boegen(X, tol=0.015, rmin=0.25, rmax=3.0, minpts=40, minwinkel=70.0, seed=3, maxit=300, log=False):
    """Kreisboegen in 3D per RANSAC (GPU): Kreis aus 3 nahen Punkten, Inlier = Abstand zum Kreis (Ebene + radial) < tol; behalten wird der laengste lueckenlose Winkelbereich >= minwinkel.
    Rueckgabe: Liste dict(c, n, R, a0, a1, pts (Bogenpunkte), npts)."""
    g = torch.Generator(device="cuda").manual_seed(seed); out = []; alive = torch.ones(len(X), dtype=torch.bool, device="cuda")
    for it in range(maxit):
        idx = alive.nonzero().squeeze(1)
        if len(idx) < minpts: break
        Y = X[idx]; M = 2000; a = torch.randint(0, len(Y), (M,), device="cuda", generator=g); cand = torch.randint(0, len(Y), (M, 300), device="cuda", generator=g)
        dd = (Y[cand] - Y[a][:, None]).norm(dim=2); dd = torch.where((dd > 0.12) & (dd < 1.5), dd, torch.full_like(dd, 1e9)); v, j = dd.topk(2, dim=1, largest=False); b = cand[torch.arange(M), j[:, 0]]; c_ = cand[torch.arange(M), j[:, 1]]; okp = v[:, 1] < 1e8
        p1 = Y[a]; u = Y[b] - p1; w = Y[c_] - p1; n = torch.cross(u, w, dim=1); nn = (n * n).sum(1).clamp(min=1e-12); cen = p1 + torch.cross((u * u).sum(1, keepdim=True) * w - (w * w).sum(1, keepdim=True) * u, n, dim=1) / (2 * nn[:, None]); R = (cen - p1).norm(dim=1)
        nh = n / nn.sqrt()[:, None]; okp = okp & (R > rmin) & (R < rmax) & (nn > 1e-6); sc = torch.zeros(M, device="cuda"); CH = int(max(8, min(300, 2e7 // max(len(Y), 1))))
        for c0 in range(0, M, CH):
            d = Y[None] - cen[c0:c0 + CH, None]; dp = (d * nh[c0:c0 + CH, None]).sum(2); rad = (d - dp[..., None] * nh[c0:c0 + CH, None]).norm(dim=2); sc[c0:c0 + CH] = ((dp ** 2 + (rad - R[c0:c0 + CH, None]) ** 2).sqrt() < tol).sum(1)
        sc = torch.where(okp, sc, torch.zeros_like(sc)); k = int(sc.argmax())
        if sc[k] < minpts: break
        d = Y - cen[k]; dp = (d * nh[k]).sum(1); rad = (d - dp[:, None] * nh[k]).norm(dim=1); inl = ((dp ** 2 + (rad - R[k]) ** 2).sqrt() < tol); ii = idx[inl]
        e1 = (Y[b[k]] - cen[k]); e1 = e1 / e1.norm(); e2 = torch.cross(nh[k], e1, dim=0); dd_ = d[inl]; ang = torch.atan2((dd_ * e2).sum(1), (dd_ * e1).sum(1)); o = ang.argsort(); ang = ang[o]; ii = ii[o]
        gaps = torch.cat([ang[1:] - ang[:-1], (ang[:1] + 2 * np.pi) - ang[-1:]]); lueck = gaps * R[k] > 0.15; cut = torch.where(lueck)[0]
        if len(cut) == 0: runs = [(0, len(ang) - 1, 2 * np.pi)]
        else:                                                              # Laeufe zwischen den Luecken (zyklisch einfach: Start nach der groessten Luecke)
            s0 = int(cut[gaps[cut].argmax()]) + 1; order = torch.cat([torch.arange(s0, len(ang), device="cuda"), torch.arange(0, s0, device="cuda")]); angs = ang[order].clone(); angs[angs < angs[0]] += 2 * np.pi; ii = ii[order]; ang = angs; runs = []; st = 0
            for q in range(1, len(ang)):
                if (ang[q] - ang[q - 1]) * R[k] > 0.15: runs.append((st, q - 1, float(ang[q - 1] - ang[st]))); st = q
            runs.append((st, len(ang) - 1, float(ang[-1] - ang[st])))
        best = max(runs, key=lambda r_: r_[2]); st, en, span = best
        if np.degrees(span) >= minwinkel and en - st + 1 >= minpts:
            ts = torch.linspace(float(ang[st]), float(ang[en]), 12, device="cuda"); P = cen[k] + R[k] * (torch.cos(ts)[:, None] * e1 + torch.sin(ts)[:, None] * e2)
            out.append(dict(c=cen[k].tolist(), n=nh[k].tolist(), R=float(R[k]), winkel=float(np.degrees(span)), pts=P.tolist(), npts=int(en - st + 1))); alive[ii[st:en + 1]] = False
        else: alive[ii[:max(1, len(ii) // 5)]] = False
        if log and it % 50 == 0: print("  Boegen", len(out), "Rest", int(alive.sum()), flush=True)
    return out
