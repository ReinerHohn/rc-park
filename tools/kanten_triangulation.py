"""3D-Linien direkt aus den Fotos (ohne Wolkenpunkte als Voraussetzung): 2D-Linien (LSD auf Grau, Lab-a, Lab-b) je Foto; je Fotopaar spannt jede 2D-Linie eine Ebene durch die Kamera auf,
der Schnitt zweier Ebenen = 3D-Linie (Abschnitt = Ueberlappung der Strahlen der Endpunkte). Kandidaten werden in anderen Fotos gegen die Median-Kantenbilder (>=2 von 3 Quellen: SAM, Canny, Farb-Sweep)
geprueft (Stufe 1: 16 Stuetzstellen x 24 Fotos, Stufe 2: 48 x alle). GPU fuer Schnitt und Pruefung, CPU-Pool fuer Kantenbilder/LSD. Danach Unterdrueckung von Doppelten.
Aufruf: python -I tools/kanten_triangulation.py KAM.json WOLKE.npy FOTOS.npz MASKEN BILDER OUT.json [--refs 12] [--partner 3] [--cpu 8]
Die Wolke dient NUR fuer den Suchkasten (Perzentile). Reihenfolge der ersten 5 Argumente wie kanten_vote_quellen.py (Modul wird mitgenutzt)."""
import sys, os, json, math, numpy as np, cv2, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import kanten_vote_quellen as KV
from concurrent.futures import ProcessPoolExecutor
def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
NREF = opt("--refs", 12, int); NPART = opt("--partner", 3, int); NCPU = opt("--cpu", 8, int); OUT = sys.argv[6]; dev = "cuda"; TOLPX = 3.0
def arbeit(f):
    _, E = KV.kantenbilder(f)
    if E is None: return f, None, None, 1.0
    h, w = E.shape[1:]; dt2 = np.minimum(cv2.distanceTransform((E.sum(0) < (1 if '--lax' in sys.argv else 2)).astype(np.uint8), cv2.DIST_L2, 3)[::2, ::2], 255).astype(np.uint8)
    im = cv2.imread(os.path.join(KV.BD, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); sc = 1500 / w; im = cv2.resize(im, (1500, int(h * sc)), interpolation=cv2.INTER_AREA); lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB); lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD); L = []
    for ch in (cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), lab[:, :, 1], lab[:, :, 2]):
        r = lsd.detect(ch)[0]
        if r is not None: L.append(r.reshape(-1, 4))
    L = np.vstack(L) / sc; ln = np.hypot(L[:, 2] - L[:, 0], L[:, 3] - L[:, 1]); L = L[ln > 0.02 * w]; ln = ln[ln > 0.02 * w]; L = L[np.argsort(-ln)[:1200]]
    return f, dt2, L.astype(np.float32), float(w)
if __name__ == "__main__":
    KAM = KV.KAM; P = np.load(sys.argv[2])[:, :3]; lo = np.percentile(P, 0.5, axis=0) - [3, 3, 0]; hi = np.percentile(P, 99.5, axis=0) + [3, 3, 8]; lo[2] = max(lo[2], 1.5); print("Suchkasten", lo.round(1), hi.round(1), flush=True)
    F = []; DT = []; LN = []; SJ = []                                                       # SJ = Labelbild-Breite / Kamera-Breite je Foto (Massstab zwischen Kantenbild und Kameramodell)
    with ProcessPoolExecutor(NCPU) as ex:
        for f, d2, L, wl in ex.map(arbeit, KV.fotos, chunksize=1):
            if d2 is None: continue
            SJ.append(wl / KAM[f]["W"]); F.append(f); DT.append(torch.from_numpy(d2).to(dev)); LN.append(torch.from_numpy(L).to(dev))
    J = len(F); print("Fotos", J, "Linien je Foto im Mittel", float(np.mean([len(l) for l in LN])), flush=True)
    T = lambda x: torch.tensor(np.array(x), device=dev, dtype=torch.float32)
    R = T([KAM[f]["Rn"] for f in F]); tt = T([KAM[f]["tn"] for f in F]); C = T([KAM[f]["C"] for f in F]); FL = T([KAM[f]["f"] for f in F]); CX = T([KAM[f]["cx"] for f in F]); CY = T([KAM[f]["cy"] for f in F]); K1 = T([KAM[f]["params"][3] for f in F])
    WH = [DT[j].shape for j in range(J)]; WIM = T([[KAM[f]["W"], KAM[f]["H"]] for f in F]); LO = torch.tensor(lo, device=dev, dtype=torch.float32); HI = torch.tensor(hi, device=dev, dtype=torch.float32)
    SJ = torch.tensor(SJ, device=dev, dtype=torch.float32)
    def rays(j, uv):                                                                           # Pixel (voller Massstab des Labelbilds = Originalpixel) -> Strahl im Kamerasystem (mit k1-Entzerrung)
        uv = uv / SJ[j]; x = (uv[:, 0] - CX[j]) / FL[j]; y = (uv[:, 1] - CY[j]) / FL[j]; xu, yu = x.clone(), y.clone()
        for _ in range(6): r2 = xu * xu + yu * yu; xu = x / (1 + K1[j] * r2); yu = y / (1 + K1[j] * r2)
        return torch.stack([xu, yu, torch.ones_like(xu)], 1)
    def proj(Q, j):                                                                            # Q (...,3) -> u,v (Originalpixel), z
        Xc = Q @ R[j].T + tt[j]; z = Xc[..., 2]; x = Xc[..., 0] / z.clamp(min=0.3); y = Xc[..., 1] / z.clamp(min=0.3); f = 1 + K1[j] * (x * x + y * y); return (FL[j] * x * f + CX[j]), (FL[j] * y * f + CY[j]), z
    def stuetz(Q, idx):                                                                        # Q (M,NS,3): Treffer und Sichtzahl ueber Fotos idx
        M, NS = Q.shape[:2]; hit = torch.zeros(M, device=dev); vis = torch.zeros(M, device=dev); Qf = Q.reshape(-1, 3)
        for j in idx:
            u, v, z = proj(Qf, j); H_, W_ = WH[j]; ui = (u * SJ[j] / 2).round().long(); vi = (v * SJ[j] / 2).round().long(); ok = (z > 1) & (ui >= 0) & (ui < W_) & (vi >= 0) & (vi < H_); d = DT[j][vi.clamp(0, H_ - 1), ui.clamp(0, W_ - 1)].float()
            hit += ((d <= TOLPX) & ok).float().view(M, NS).sum(1); vis += ok.float().view(M, NS).sum(1)
        return hit, vis
    # Paare
    Cn = C.cpu().numpy(); Dn = R[:, 2].cpu().numpy(); sel = [0]; feat = np.hstack([Cn / 10.0, Dn * 3.0]); dm = np.linalg.norm(feat - feat[0], axis=1)
    while len(sel) < min(NREF, J): j = int(np.argmax(dm)); sel.append(j); dm = np.minimum(dm, np.linalg.norm(feat - feat[j], axis=1))
    pairs = []
    for a in sel:
        BMIN = opt('--bmin', 2.0); BMAX = opt('--bmax', 15.0); BZ = opt('--bziel', 6.0); cand = [(abs(np.linalg.norm(Cn[b] - Cn[a]) - BZ), b) for b in range(J) if b != a and BMIN < np.linalg.norm(Cn[b] - Cn[a]) < BMAX and float(Dn[a] @ Dn[b]) > opt('--dotmin', 0.7)]; cand.sort(); pairs += [(a, b) for _, b in cand[:NPART]]
    DBG = [0, 0, 0, 0]; print("Paare", len(pairs), flush=True); rng = np.random.default_rng(0); allA = []; allB = []; allS = []; allV = []
    ts1 = torch.linspace(0.05, 0.95, 16, device=dev); ts2 = torch.linspace(0.02, 0.98, 48, device=dev)
    for (a, b) in pairs:
        La, Lb = LN[a], LN[b]; na, nb = len(La), len(Lb)
        def ebene(j, L):
            r0 = rays(j, L[:, :2]); r1 = rays(j, L[:, 2:]); w0 = r0 @ R[j]; w1 = r1 @ R[j]; N = torch.cross(w0, w1, dim=1); N = N / N.norm(dim=1, keepdim=True).clamp(min=1e-9); return N, w0 / w0.norm(dim=1, keepdim=True), w1 / w1.norm(dim=1, keepdim=True)
        NA, A0, A1 = ebene(a, La); NB, B0, B1 = ebene(b, Lb); d = torch.cross(NA[:, None].expand(na, nb, 3), NB[None].expand(na, nb, 3), dim=2); ds = d.norm(dim=2); ok = ds > 0.17; ia, ib = ok.nonzero(as_tuple=True)
        if len(ia) == 0: continue
        d = d[ia, ib] / ds[ia, ib][:, None]; M3 = torch.stack([NA[ia], NB[ib], d], 1); rhs = torch.stack([(NA[ia] * C[a]).sum(1), (NB[ib] * C[b]).sum(1), torch.zeros(len(ia), device=dev)], 1); P0 = torch.linalg.solve(M3, rhs[..., None])[..., 0]
        def trange(Cc, W0, W1):
            res = []
            for Wd in (W0, W1):
                r = P0 - Cc; bb = (d * Wd).sum(1); res.append((bb * (Wd * r).sum(1) - (d * r).sum(1)) / (1 - bb * bb).clamp(min=1e-6))
            return torch.minimum(*res), torch.maximum(*res)
        loA, hiA = trange(C[a], A0[ia], A1[ia]); loB, hiB = trange(C[b], B0[ib], B1[ib]); lo_t = torch.maximum(loA, loB); hi_t = torch.minimum(hiA, hiB); ok = (hi_t - lo_t > 0.15) & (hi_t - lo_t < 12.0)
        S0 = P0 + d * lo_t[:, None]; S1 = P0 + d * hi_t[:, None]; ok &= ((S0 > LO) & (S0 < HI)).all(1) & ((S1 > LO) & (S1 < HI)).all(1); S0, S1 = S0[ok], S1[ok]
        if len(S0) == 0: continue
        hoch = (torch.maximum(S0[:, 2], S1[:, 2]) > 15); DBG[0] += int(hoch.sum()); DBG[1] += len(S0)
        others = [j for j in range(J) if j not in (a, b)]; st1 = rng.choice(others, min(24, len(others)), replace=False).tolist(); keepA = []; keepB = []; keepS = []; keepV = []
        for c0 in range(0, len(S0), 40000):
            s0, s1 = S0[c0:c0 + 40000], S1[c0:c0 + 40000]; Q = s0[:, None] * (1 - ts1)[None, :, None] + s1[:, None] * ts1[None, :, None]; h1, v1 = stuetz(Q, st1); k = (v1 >= 0.5 * 16 * 24 * 0.25) & (h1 >= 0.6 * v1)
            if int(k.sum()) == 0: continue
            DBG[2] += int((torch.maximum(s0[k][:, 2], s1[k][:, 2]) > 15).sum()) if int(k.sum()) else 0; s0, s1 = s0[k], s1[k]; Q = s0[:, None] * (1 - ts2)[None, :, None] + s1[:, None] * ts2[None, :, None]; h2, v2 = stuetz(Q, others); sc = h2 / v2.clamp(min=1); k2 = (sc >= 0.62) & (v2 >= 48 * 4)
            DBG[3] += int((torch.maximum(s0[k2][:, 2], s1[k2][:, 2]) > 15).sum()); keepA.append(s0[k2]); keepB.append(s1[k2]); keepS.append(sc[k2]); keepV.append(v2[k2] / 48)
        if keepA:
            allA.append(torch.cat(keepA)); allB.append(torch.cat(keepB)); allS.append(torch.cat(keepS)); allV.append(torch.cat(keepV))
        print("Paar", a, b, "Kandidaten", len(S0), "gestuetzt", int(sum(len(x) for x in keepA)), flush=True)
    print("Diagnose z>15 m: Kandidaten %d von %d, nach Stufe 1: %d, nach Stufe 2: %d" % (DBG[0], DBG[1], DBG[2], DBG[3]), flush=True)
    if not allA: print("nichts gefunden"); sys.exit(0)
    A = torch.cat(allA); B = torch.cat(allB); S = torch.cat(allS); V = torch.cat(allV); L = (B - A).norm(dim=1); o = (S * L.clamp(max=3)).argsort(descending=True); A, B, S, V, L = A[o], B[o], S[o], V[o], L[o]; print("vor NMS", len(A), flush=True)
    kA = torch.zeros((0, 3), device=dev); kB = torch.zeros((0, 3), device=dev); kS = []; tq = torch.linspace(0, 1, 6, device=dev)
    def dist_zu(Q, KA, KB):
        dmin = torch.full(Q.shape[:2], 9.0, device=dev)
        for c in range(0, len(KA), 200):
            a_ = KA[c:c + 200][None, None]; ab = (KB[c:c + 200] - KA[c:c + 200])[None, None]; w = Q[:, :, None] - a_; t = ((w * ab).sum(-1) / (ab * ab).sum(-1).clamp(min=1e-9)).clamp(0, 1); dmin = torch.minimum(dmin, (w - t[..., None] * ab).norm(dim=-1).min(-1).values)
        return dmin
    for c0 in range(0, len(A), 512):
        a_, b_ = A[c0:c0 + 512], B[c0:c0 + 512]; Q = a_[:, None] * (1 - tq)[None, :, None] + b_[:, None] * tq[None, :, None]
        dup = (dist_zu(Q, kA, kB) < 0.025).all(1) if len(kA) else torch.zeros(len(a_), dtype=torch.bool, device=dev); idx = (~dup).nonzero().squeeze(1)
        for i in idx.tolist():                                                                  # innerhalb des Blocks greedy
            if len(kA) and i != idx[0]:
                q = Q[i:i + 1]
                if bool((dist_zu(q, kA[-64:], kB[-64:]) < 0.025).all()): continue
            kA = torch.cat([kA, a_[i:i + 1]]); kB = torch.cat([kB, b_[i:i + 1]]); kS.append(float(S[c0 + i]))
    print("nach NMS", len(kA), "Laenge", float((kB - kA).norm(dim=1).sum()), "m", flush=True)
    json.dump({"segmente": [[a.tolist(), b.tolist(), 0, s] for a, b, s in zip(kA, kB, kS)], "quelle": "triangulation", "fotos": J, "paare": len(pairs)}, open(OUT, "w")); print("fertig", OUT)
