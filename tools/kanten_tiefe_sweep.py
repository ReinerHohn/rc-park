"""Kanten-Tiefen-Sweep (GPU): fuer jedes starke Kantenpixel eines Referenzfotos (Stabilitaetskarte) die Tiefe entlang des Strahls durchsweepen;
je Tiefe zaehlen, in wie vielen Nachbarfotos an der Projektion wieder eine stabile Kante steht; Peak = 3D-Kantenpunkt. Keine Linienpaare, keine Wolke noetig.
Aufruf: kanten_tiefe_sweep.py KAM.json STABILDIR OUT.npz [--refs 40] [--nb 12] [--vmin 0.6] [--hit 0.4] [--smin 0.7] [--dmin 4] [--dmax 90] [--maxpx 40000] [--box WOLKE.npy] [--exclude ANDERER.npz]"""
import sys, os, json, time, numpy as np, cv2, torch, torch.nn.functional as Fn
def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
NREF = opt("--refs", 40, int); NB = opt("--nb", 12, int); VMIN = opt("--vmin", 0.6); HIT = opt("--hit", 0.4); SMIN = opt("--smin", 0.7); DMIN = opt("--dmin", 4.0); DMAX = opt("--dmax", 90.0); MAXPX = opt("--maxpx", 40000, int)
dev = "cuda"; KAM = json.load(open(sys.argv[1])); sd = sys.argv[2]; fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))]; J = len(fs); t0 = time.time()
V = []; 
for f in fs:
    v = cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0); V.append(torch.from_numpy(v).to(dev))
HW = [tuple(v.shape) for v in V]; HITM = [Fn.max_pool2d((v >= 255 * HIT).float()[None, None], 3, 1, 1)[0, 0].to(torch.uint8) for v in V]   # Treffer mit 1 px Toleranz (Hoch-/Querformat gemischt)
print("Fotos", J, "Karten geladen %.0fs" % (time.time() - t0), flush=True)
T = lambda x: torch.tensor(np.array(x), device=dev, dtype=torch.float32)
R = T([KAM[f]["Rn"] for f in fs]); tt = T([KAM[f]["tn"] for f in fs]); C = T([KAM[f]["C"] for f in fs]); FL = T([KAM[f]["f"] for f in fs]); CX = T([KAM[f]["cx"] for f in fs]); CY = T([KAM[f]["cy"] for f in fs]); K1 = T([KAM[f]["params"][3] for f in fs]); SJ = T([HW[i][1] / KAM[f]["W"] for i, f in enumerate(fs)])
def strahl(j, u, v):                                                            # Pixel der Karte -> Weltstrahl (k1 iterativ entzerrt)
    x = (u / SJ[j] - CX[j]) / FL[j]; y = (v / SJ[j] - CY[j]) / FL[j]; xu, yu = x.clone(), y.clone()
    for _ in range(4): f = 1 + K1[j] * (xu * xu + yu * yu); xu = x / f; yu = y / f
    d = torch.stack([xu, yu, torch.ones_like(xu)], 1); d = d / d.norm(dim=1, keepdim=True); return d @ R[j]
def proj(Q, j):
    Xc = Q @ R[j].T + tt[j]; z = Xc[:, 2]; x = Xc[:, 0] / z.clamp(min=0.3); y = Xc[:, 1] / z.clamp(min=0.3); f = 1 + K1[j] * (x * x + y * y); return (FL[j] * x * f + CX[j]) * SJ[j], (FL[j] * y * f + CY[j]) * SJ[j], z
Cn = C.cpu().numpy(); Dn = R[:, 2].cpu().numpy(); rng = np.random.default_rng(0); pool = np.arange(J)
if "--exclude" in sys.argv: pool = np.setdiff1d(pool, np.unique(np.load(opt("--exclude", "", str))["ref"]))   # nur Referenzfotos, die der andere Lauf nicht benutzt hat (unabhaengige Pruefmenge)
refs = rng.choice(pool, min(NREF, len(pool)), replace=False); ds = torch.exp(torch.linspace(np.log(DMIN), np.log(DMAX), 360, device=dev)); out = []
for a in refs:
    cand = [(abs(np.linalg.norm(Cn[b] - Cn[a]) - 6.0), b) for b in range(J) if b != a and 1.0 < np.linalg.norm(Cn[b] - Cn[a]) < 25 and float(Dn[a] @ Dn[b]) > 0.6]; cand.sort(); nb = [b for _, b in cand[:NB]]
    if len(nb) < 5: continue
    ys, xs = torch.nonzero(V[a] >= 255 * VMIN, as_tuple=True)
    if len(xs) > MAXPX: p = torch.randperm(len(xs), device=dev)[:MAXPX]; ys, xs = ys[p], xs[p]
    u = xs.float() + 0.5; v = ys.float() + 0.5; best = torch.zeros(len(xs), device=dev); bd = torch.zeros(len(xs), device=dev); second = torch.zeros(len(xs), device=dev)
    for c0 in range(0, len(xs), 4000):
        sl = slice(c0, c0 + 4000); r = strahl(a, u[sl], v[sl]); N = len(r); Q = (C[a][None, None] + r[:, None] * ds[None, :, None]).reshape(-1, 3); hit = torch.zeros(N * len(ds), device=dev); vis = torch.zeros(N * len(ds), device=dev)
        for b in nb:
            uu, vv, z = proj(Q, b); ui = uu.round().long(); vi = vv.round().long(); Hb, Wb = HW[b]; ok = (z > 1) & (ui >= 0) & (ui < Wb) & (vi >= 0) & (vi < Hb)
            hit += (HITM[b][vi.clamp(0, Hb - 1), ui.clamp(0, Wb - 1)].float() * ok.float()); vis += ok.float()
        sc = (hit / vis.clamp(min=1)).view(N, len(ds)); sc = sc * (vis.view(N, len(ds)) >= 5).float()
        m, i = sc.max(1); sc2 = sc.clone(); lo = (i[:, None] - 12).clamp(min=0); hi = (i[:, None] + 12); ar = torch.arange(len(ds), device=dev)[None]; sc2[(ar >= lo) & (ar <= hi)] = 0; s2 = sc2.max(1).values
        best[sl] = m; bd[sl] = ds[i]; second[sl] = s2
    ok = (best >= SMIN) & (second <= 0.8 * best); r = strahl(a, u[ok], v[ok]); P3 = C[a][None] + r * bd[ok][:, None]; out.append((P3.cpu().numpy(), best[ok].cpu().numpy(), np.full(int(ok.sum()), a)))
    print("Ref %s: Pixel %d, eindeutiger Peak %d (%.0fs)" % (fs[a], len(xs), int(ok.sum()), time.time() - t0), flush=True)
P = np.vstack([o[0] for o in out]); S = np.concatenate([o[1] for o in out]); A = np.concatenate([o[2] for o in out]); np.savez(sys.argv[3], P=P, s=S, ref=A, fotos=np.array(fs)); print("fertig", len(P), "Punkte")
