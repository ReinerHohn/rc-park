#!/usr/bin/env python3
# 22.11.2026 KREISFALL (Kantenstufe suchte nur +-0,5 m um das VORMODELL): --vorn V = Suchraum asymmetrisch -V .. +band (Meter senkrecht zur getroffenen Flaeche, je Pixel
#   mit 1/max(|cos|, 0.5) auf den Strahl umgerechnet; ausserhalb +-band Schritt --schritt_vorn, Standard 0,02) -> Vorbauten/Vordach/Traufe bis V vor der Flaeche;
#   --huelle: Strahlen, die die Flaeche verfehlen, suchen die ersten V+band m in der um V vergroesserten Huellbox (Traufe/Vordach vor dem Himmel);
#   --geraet cpu (Waechter-Test ohne GPU). Ohne --vorn/--huelle: alter Weg bitgleich (ebenen_bauplan).
# Variante von kanten_tiefe_sweep.py (12.11.): --ref_namen, --dziel (Tiefenband um Ziel), --flaeche STL --band m (Sweep je Pixel nur +-band um die Modellflaeche = keine Mehrdeutigkeit durch parallele Rippenkanten), --ziel, --nbdist, --eind. Ausgabe wie Original; Weiterverarbeitung: kanten_features.py --farbe stabil --sweep
"""Kanten-Tiefen-Sweep (GPU): fuer jedes starke Kantenpixel eines Referenzfotos (Stabilitaetskarte) die Tiefe entlang des Strahls durchsweepen;
je Tiefe zaehlen, in wie vielen Nachbarfotos an der Projektion wieder eine stabile Kante steht; Peak = 3D-Kantenpunkt. Keine Linienpaare, keine Wolke noetig.
Aufruf: kanten_tiefe_sweep.py KAM.json STABILDIR OUT.npz [--refs 40] [--nb 12] [--vmin 0.6] [--hit 0.4] [--smin 0.7] [--dmin 4] [--dmax 90] [--maxpx 40000] [--box WOLKE.npy] [--exclude ANDERER.npz] [--ref_namen a.jpg,b.jpg --diag OUT.png] [--basis_ziel 6 --basis_max 25 --tolpx 1] [--basis_rel 0.4 | --dz 0.05  --box WOLKENKANTEN.npy]"""
import sys, os, json, time, numpy as np, cv2, torch, torch.nn.functional as Fn
def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
NREF = opt("--refs", 40, int); NB = opt("--nb", 12, int); VMIN = opt("--vmin", 0.6); HIT = opt("--hit", 0.4); SMIN = opt("--smin", 0.7); DMIN = opt("--dmin", 4.0); DMAX = opt("--dmax", 90.0); BZ = opt("--basis_ziel", 6.0); BMAX = opt("--basis_max", 25.0); TOLPX = opt("--tolpx", 1, int); BREL = opt("--basis_rel", 0.0); DZ = opt("--dz", 0.0); MAXPX = opt("--maxpx", 40000, int)
dev = opt("--geraet", "cuda", str); KAM = json.load(open(sys.argv[1])); sd = sys.argv[2]; fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))]; J = len(fs); t0 = time.time()
V = []; 
for f in fs:
    v = cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0); V.append(torch.from_numpy(v).to(dev))
HW = [tuple(v.shape) for v in V]; HITM = [Fn.max_pool2d((v >= 255 * HIT).float()[None, None], 2 * TOLPX + 1, 1, TOLPX)[0, 0].to(torch.uint8) for v in V]   # Treffer mit 1 px Toleranz (Hoch-/Querformat gemischt)
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
refs = rng.choice(pool, min(NREF, len(pool)), replace=False)
if "--ref_prefix" in sys.argv: pool = np.array([i for i in pool if fs[i].startswith(opt("--ref_prefix", "", str))]); refs = rng.choice(pool, min(NREF, len(pool)), replace=False)   # z.B. nur Videoframes als Referenz
if "--ref_namen" in sys.argv: refs = np.array([fs.index(n) for n in opt("--ref_namen", "", str).split(",")])   # gezielte Referenzfotos (Diagnose)
DIAG = opt("--diag", "", str); ds = torch.linspace(DMIN, DMAX, int((DMAX - DMIN) / opt('--schritt', 0.01)), device=dev); out = []
ZENTRUM = np.median(np.load(opt("--box", "", str))[:, :3], 0) if "--box" in sys.argv else None   # Szenenmitte fuer relative Basis
VORN = opt("--vorn", 0.0); HUELLE = "--huelle" in sys.argv; NHUELLE = [0]; SK = None
ZAUTO = "--ziel_auto" in sys.argv; MM = None   # 15.11.: allgemein (Gesamtkette): Flaechen-Massstab per --flaeche_skala (Standard 0,087 = Kaufhaus), Blickziel je Referenz aus der Flaeche
if "--flaeche" in sys.argv:
    import trimesh; mm = trimesh.load(opt('--flaeche', '', str)); mm.apply_scale(opt('--flaeche_skala', 0.087)); bxs = np.array([float(v_) for v_ in opt('--box3', '14,3,6,27,12,8.4', str).split(',')]); ct = mm.triangles_center; mm = trimesh.Trimesh(mm.vertices, mm.faces[np.all((ct >= bxs[:3]) & (ct <= bxs[3:]), axis=1)], process=False); MM = mm
def blickziel(a, n=24):                                                         # Median der Treffer eines n x n-Strahlengitters mit der Modellflaeche (None = Foto sieht das Modell kaum)
    Hh, Ww = HW[a]; g = torch.stack(torch.meshgrid(torch.linspace(0, Ww - 1, n, device=dev), torch.linspace(0, Hh - 1, n, device=dev), indexing="xy"), -1).reshape(-1, 2)
    rr = strahl(a, g[:, 0], g[:, 1]).cpu().numpy(); loc, _, _ = MM.ray.intersects_location(np.repeat(Cn[a][None], len(rr), 0), rr, multiple_hits=False)
    return np.median(loc, 0) if len(loc) >= 0.05 * n * n else None
for a in refs:
    bz, bmax = BZ, BMAX
    if '--dziel' in sys.argv:
        zp_ = np.array([float(v) for v in opt('--ziel', '20,7,7', str).split(',')]); d_ = float(np.linalg.norm(Cn[a] - zp_)); ds = torch.linspace(max(d_ - opt('--dziel', 2.5), 1.0), d_ + opt('--dziel', 2.5), int(2 * opt('--dziel', 2.5) / opt('--schritt', 0.01)), device=dev)
    if BREL > 0 and ZENTRUM is not None: da = float(np.linalg.norm(Cn[a] - ZENTRUM)); bz = BREL * da; bmax = 3 * bz   # Basis ~ Abstand Kamera-Szene (nah: kurz, fern: lang)
    if DZ > 0 and ZENTRUM is not None:                                             # Basis nach Tiefenaufloesung: 1 px Verschiebung = DZ Meter -> b_min = d^2 / (f_px * DZ)
        da = float(np.linalg.norm(Cn[a] - ZENTRUM)); fpx = float(FL[a] * SJ[a]); bmin = da * da / (fpx * DZ); bz = max(1.5, 1.5 * bmin); bmax = min(opt("--basis_max", 25.0), max(6.0, 4 * bmin))
    if ZENTRUM is not None and float(np.linalg.norm(Cn[a] - ZENTRUM)) > opt("--dmax_ref", 1e9): continue        # ferne Referenzfotos liefern nur Rauschen (Test 6254: 10 % < 10 cm)
    ZP = blickziel(a) if ZAUTO else np.array([float(v) for v in opt('--ziel', '20,7,7', str).split(',')])
    if ZP is None: continue
    cand = [(-abs(np.linalg.norm(Cn[b] - Cn[a])), b) for b in range(J) if b != a and 1.0 < np.linalg.norm(Cn[b] - Cn[a]) < bmax and float(Dn[b] @ ((ZP - Cn[b]) / np.linalg.norm(ZP - Cn[b]))) > 0.8 and np.linalg.norm(ZP - Cn[b]) < opt('--nbdist', 30.0)]; cand.sort(); nb = [b for _, b in cand[::max(1, len(cand) // NB)][:NB]]
    if len(nb) < 5: continue
    ys, xs = torch.nonzero(V[a] >= 255 * VMIN, as_tuple=True)
    fw = [float(v) for v in opt('--fenster', '0,0,99999,99999', str).split(',')]; kf = (xs.float() / SJ[a] >= fw[0]) & (xs.float() / SJ[a] < fw[2]) & (ys.float() / SJ[a] >= fw[1]) & (ys.float() / SJ[a] < fw[3]); ys, xs = ys[kf], xs[kf]
    if len(xs) > MAXPX: p = torch.randperm(len(xs), device=dev)[:MAXPX]; ys, xs = ys[p], xs[p]
    u = xs.float() + 0.5; v = ys.float() + 0.5
    if '--flaeche' in sys.argv:
        mm = MM
        rr = strahl(a, u, v).cpu().numpy(); oo = np.repeat(Cn[a][None], len(rr), 0); loc, ir, it = mm.ray.intersects_location(oo, rr, multiple_hits=False); tz0 = np.full(len(rr), np.nan); tz0[ir] = np.linalg.norm(loc - Cn[a], axis=1)
        BAND = opt('--band', 0.25)
        if VORN > 0:                                                             # 22.11.2026: Suchraum vor der Flaeche (modellfreier Messkoerper), je Pixel auf den Strahl umgerechnet
            sk = np.ones(len(rr)); cs = np.abs(np.einsum("ij,ij->i", rr[ir], np.asarray(mm.face_normals)[it])); sk[ir] = 1.0 / np.maximum(cs, 0.5)
            if HUELLE:                                                           # Strahlen ohne Treffer: Eintritt in die um VORN vergroesserte Huellbox, dort die ersten VORN + band m
                lo3, hi3 = mm.bounds[0] - VORN, mm.bounds[1] + VORN; fe = np.isnan(tz0); d_ = rr[fe]; d_ = np.where(np.abs(d_) < 1e-9, 1e-9, d_)
                t1 = (lo3 - Cn[a]) / d_; t2 = (hi3 - Cn[a]) / d_; tin = np.minimum(t1, t2).max(1); tout = np.maximum(t1, t2).min(1); ok_ = (tout > tin) & (tin > 0.5)
                ix_ = np.flatnonzero(fe)[ok_]; tz0[ix_] = tin[ok_] + VORN; sk[ix_] = 1.0; NHUELLE[0] += len(ix_)
            kn = ~np.isnan(tz0); SK = torch.from_numpy(sk[kn]).float().to(dev)
        kk = torch.from_numpy(~np.isnan(tz0)).to(dev); ys, xs, u, v = ys[kk], xs[kk], u[kk], v[kk]; T0 = torch.from_numpy(tz0[~np.isnan(tz0)]).float().to(dev)
        if VORN > 0:
            st, stv = opt('--schritt', 0.01), opt('--schritt_vorn', 0.02); nv_ = int(round((VORN - BAND) / stv)) if VORN > BAND else 0
            ds = torch.cat([torch.linspace(-VORN, -BAND, nv_ + 1, device=dev)[:-1] if nv_ else torch.zeros(0, device=dev), torch.linspace(-BAND, BAND, int(2 * BAND / st) + 1, device=dev)])
        else: ds = torch.linspace(-BAND, BAND, int(2 * BAND / opt('--schritt', 0.01)) + 1, device=dev)
    else: T0 = torch.zeros(len(xs), device=dev)
    if not (VORN > 0 and '--flaeche' in sys.argv): SK = None
    best = torch.zeros(len(xs), device=dev); bd = torch.zeros(len(xs), device=dev); second = torch.zeros(len(xs), device=dev)
    for c0 in range(0, len(xs), 4000):
        sl = slice(c0, c0 + 4000); r = strahl(a, u[sl], v[sl]); N = len(r); dsp = ds[None, :] * SK[sl][:, None] if SK is not None else ds[None, :]; Q = (C[a][None, None] + r[:, None] * (T0[sl][:, None] + dsp)[:, :, None]).reshape(-1, 3); hit = torch.zeros(N * len(ds), device=dev); vis = torch.zeros(N * len(ds), device=dev)
        for b in nb:
            uu, vv, z = proj(Q, b); ui = uu.round().long(); vi = vv.round().long(); Hb, Wb = HW[b]; ok = (z > 1) & (ui >= 0) & (ui < Wb) & (vi >= 0) & (vi < Hb)
            hit += (HITM[b][vi.clamp(0, Hb - 1), ui.clamp(0, Wb - 1)].float() * ok.float()); vis += ok.float()
        sc = (hit / vis.clamp(min=1)).view(N, len(ds)); sc = sc * (vis.view(N, len(ds)) >= 5).float()
        m, i = sc.max(1); sc2 = sc.clone()
        if VORN > 0: sc2[(ds[None, :] - ds[i][:, None]).abs() <= 0.125] = 0           # Nebengipfel-Sperre in Metern (+-12 Schritte zu 1 cm), auch bei groeberem Schritt vor der Flaeche
        else: lo = (i[:, None] - 12).clamp(min=0); hi = (i[:, None] + 12); ar = torch.arange(len(ds), device=dev)[None]; sc2[(ar >= lo) & (ar <= hi)] = 0
        s2 = sc2.max(1).values
        best[sl] = m; bd[sl] = T0[sl] + (dsp[torch.arange(N, device=dev), i] if SK is not None else ds[i]); second[sl] = s2
    ok = (best >= SMIN) & (second <= opt('--eind', 0.8) * best)
    if DIAG:                                                                     # Diagnosebild: gruen = Peak gefunden, rot = kein eindeutiger Peak, grau = Karte
        im = cv2.cvtColor(V[a].cpu().numpy(), cv2.COLOR_GRAY2BGR); yy = ys.cpu().numpy(); xx = xs.cpu().numpy(); okn = ok.cpu().numpy(); im[yy[~okn], xx[~okn]] = (0, 0, 255); im[yy[okn], xx[okn]] = (0, 255, 0); cv2.imwrite(DIAG.replace(".png", "_%s.png" % os.path.splitext(fs[a])[0]), im)
    r = strahl(a, u[ok], v[ok]); P3 = C[a][None] + r * bd[ok][:, None]; out.append((P3.cpu().numpy(), best[ok].cpu().numpy(), np.full(int(ok.sum()), a)))
    print("Ref %s: Pixel %d, eindeutiger Peak %d (%.0fs)" % (fs[a], len(xs), int(ok.sum()), time.time() - t0), flush=True)
P = np.vstack([o[0] for o in out]); S = np.concatenate([o[1] for o in out]); A = np.concatenate([o[2] for o in out]); np.savez(sys.argv[3], P=P, s=S, ref=A, fotos=np.array(fs)); print("fertig", len(P), "Punkte" + (f" (Suchraum {VORN:.2f} m vor bis {opt('--band', 0.25):.2f} m hinter der Flaeche, {NHUELLE[0]} Strahlen ueber die Huelle)" if VORN > 0 else ""))
