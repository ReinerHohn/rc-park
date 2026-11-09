"""Dachgauben als Formfamilie (Giebelgaube: waagerechter First vom Giebelscheitel bis in die Hauptdachebene, zwei Ortgaenge, Traufe, zwei senkrechte
Frontkanten, zwei Kehlen) aus Tiefen-Sweep-Punkten, GPU-Rastersuche nach Inlierzahl. Ablauf: (1) Hauptdachebenen per RANSAC (geneigt 25-75 Grad) auf den
Punkten ueber der Traufe (--traufe z oder auto: hoechstes 0,5-m-Band, ueber dem die Punktzahl auf < 1/4 faellt), (2) Kandidaten = Punkte 0,2..1,5 m UEBER einer
Dachebene innerhalb ihres Grundrisses (xy-Abstand zu Ebeneninliern < 1 m), (3) Cluster per Kugelnachbarschaft (PyTorch3D ball_query, Labelausbreitung auf der GPU),
Cluster mit Ausdehnung 0,3..--maxbreite m und ohne Helm im Umkreis 2,5 m (--ausschluss helme.json), (4) je Cluster Rastersuche grob->fein ueber Lage entlang
Traufe t0, Lage am Hang s0, Breite w, Scheitelhoehe h_f, Fronttraufhoehe h_t, Tiefe (First geneigt vom Scheitel bis in die Dachebene; Fotobefund 6261: lange Kehlen-Dreiecke,
ein waagerechter First passte nicht), Score = Inlier - Laenge*Hintergrunddichte,
(5) Gleichheitsregel: je Reihe (gleiche Hanglage +-1 m) Median je Mass, Abweichung < --gleich_tol (0,15 m) -> Median, sonst eigener Wert (Bericht),
(6) Fotopruefung (Stabilitaetskarten, Kantenbelegung der projizierten Kanten) nur Bericht, (7) Ausgabe Segmente quelle 12.
Aufruf: gauben_fit.py SWEEP.npz OUT.json [--kam KAM.json --stabil DIR] [--zmin 10 --zmax 30] [--traufe auto] [--hmin 0.2 --hmax 1.5] [--tol 0.12] [--mind 150]
        [--maxbreite 3.5] [--ausschluss helme.json] [--gleich 1 --gleich_tol 0.15] [--ebenen 2]
Keine Objektkonstanten; Hoehenband, Traufe und Groessen sind Parameter."""
import sys, os, json, numpy as np, torch, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, "/media/oem/scan/p3d_site")
from pytorch3d.ops import ball_query
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
ZMIN, ZMAX, HMIN, HMAX, TOL, MIND = g("--zmin", 10.0), g("--zmax", 30.0), g("--hmin", 0.2), g("--hmax", 1.5), g("--tol", 0.12), g("--mind", 150, int)
MAXB, GLEICH, GTOL, EBENEN, RHO, FOTOMIN = g("--maxbreite", 3.5), g("--gleich", 1, int), g("--gleich_tol", 0.15), g("--ebenen", 2, int), g("--rho", 0.25), g("--fotomin", 0.4)
ALLE_PUNKTE, PX = g("--alle_punkte", 0, int), g("--px", 3, int)
NFOTO_G = g("--nfoto", 3, int)
FOTOVERLUST, KFOTOS, DTCAP = g("--fotoverlust", 0, int), g("--kfotos", 6, int), 20.0     # Runde 2: Fit-Ziel = Sweep-Inlier x (1 - mittlere Pixeldistanz zur Stabilitaetskante / 20 px)
dev = "cuda"; torch.cuda.set_per_process_memory_fraction(float(os.environ.get("RCPARK_GPU_ANTEIL", "0.18")))
Z = np.load(a[1]); P = Z["P"]; P = P[(P[:, 2] > ZMIN) & (P[:, 2] < ZMAX)].astype(np.float32); Pt = torch.tensor(P, device=dev)
print("Punkte im Hoehenband", len(P), flush=True)

# (1) Traufe
if g("--traufe", "auto", str) != "auto": TRAUFE = g("--traufe", 0.0)
else:
    e = np.arange(ZMIN, ZMAX + 0.5, 0.5); h, _ = np.histogram(P[:, 2], bins=e); TRAUFE = None
    for i in range(len(h) - 3, 0, -1):
        if h[i] > 0.02 * len(P) and h[i] > 4 * max(h[i + 1], 1) and h[i] > 4 * max(h[i + 2], 1): TRAUFE = float(e[i + 1]); break
    if TRAUFE is None: TRAUFE = float(np.quantile(P[:, 2], 0.8))
print("Traufe %.2f m" % TRAUFE, flush=True)

def ebene_ransac(Q, tol=0.25, it=6000, nz=(0.25, 0.9)):
    M = len(Q); idx = torch.randint(0, M, (it, 3), device=dev); p = Q[idx]
    n = torch.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], dim=1); nn = n.norm(dim=1); n = n / nn.clamp(min=1e-9)[:, None]; d = -(n * p[:, 0]).sum(1)
    ok = (nn > 1e-6) & (n[:, 2].abs() > nz[0]) & (n[:, 2].abs() < nz[1]); best = (-1, None, None)
    for c0 in range(0, it, 256):
        sl = slice(c0, c0 + 256); inl = (((Q[None] * n[sl, None]).sum(2) + d[sl, None]).abs() < tol).sum(1); inl[~ok[sl]] = -1
        v, i = inl.max(0)
        if int(v) > best[0]: best = (int(v), n[sl][i].clone(), d[sl][i].clone())
    return best

# (1) Hauptdachebenen: --gitter SEG.json = Ebene durch Traufe- und Firstlinie des Kantengitters (lange waagerechte Segmente am Traufband und im hoechsten Band; Runde 2),
#     sonst RANSAC auf Punkten ueber der Traufe (+0,3 m)
D = Pt[Pt[:, 2] > TRAUFE + 0.3]; keep = torch.ones(len(D), dtype=torch.bool, device=dev); ebenen = []
if "--gitter" in a:
    SG = json.load(open(g("--gitter", "", str)))["segmente"]; S3 = np.array([[s[0], s[1]] for s in SG], dtype=float); L = np.linalg.norm(S3[:, 1] - S3[:, 0], axis=1); dz = np.abs(S3[:, 1, 2] - S3[:, 0, 2]); zm = S3[:, :, 2].mean(1)
    hz = (L > 2.0) & (dz < 0.1 * L); mt = hz & (np.abs(zm - TRAUFE) < 0.6); e = np.arange(TRAUFE + 2, ZMAX, 0.5); hist = np.array([L[hz & (zm >= z) & (zm < z + 0.5)].sum() for z in e])
    zf = e[int(np.argmax(hist))] + 0.25; mf = hz & (np.abs(zm - zf) < 0.6); P3 = np.concatenate([S3[mt].reshape(-1, 3), S3[mf].reshape(-1, 3)])
    c = P3.mean(0); n2 = np.linalg.svd(P3 - c, full_matrices=False)[2][-1]; n2 = n2 if n2[2] > 0 else -n2; n2 = torch.tensor(n2, device=dev, dtype=torch.float32); d2 = -(n2 * torch.tensor(c, device=dev, dtype=torch.float32)).sum()
    alpha = float(torch.acos(n2[2].clamp(-1, 1))); et = torch.tensor([-n2[1], n2[0], 0.0], device=dev); et = et / et.norm(); eh = torch.tensor([n2[0], n2[1], 0.0], device=dev); eh = -eh / eh.norm().clamp(min=1e-9)
    hh = (D * n2[None]).sum(1) + d2; inl = hh.abs() < 0.4; keep &= ~inl
    ebenen.append(dict(n=n2, d=d2, alpha=alpha, et=et, eh=eh, inlier=D[inl], anzahl=int(inl.sum()), quelle="gitter Traufe %.2f (%d Seg.) + First %.2f (%d Seg.)" % (TRAUFE, mt.sum(), zf, mf.sum())))
    print("Dachebene aus Gitter: Traufe %.2f (%d Segmente), First %.2f (%d Segmente), n %s Neigung %.1f Grad, Sweep-Punkte in +-0,4 m: %d" % (TRAUFE, mt.sum(), zf, mf.sum(), [round(float(x), 3) for x in n2], np.rad2deg(alpha), int(inl.sum())), flush=True)
for _ in range(EBENEN if "--gitter" not in a else 0):
    v, n, d = ebene_ransac(D[keep])
    if v < 0.15 * int(keep.sum()): break
    if n[2] < 0: n, d = -n, -d                                                                        # Normale nach oben
    hh = (D * n[None]).sum(1) + d; inl = keep & (hh.abs() < 0.25)
    # Ebene auf ihren Inliern nachrechnen (Least Squares), dann Normale/Offset neu
    X = D[inl]; c = X.mean(0); U, S, Vt = torch.linalg.svd(X - c, full_matrices=False); n2 = Vt[-1]; n2 = n2 if n2[2] > 0 else -n2; d2 = -(n2 * c).sum()
    hh = (D * n2[None]).sum(1) + d2; inl = keep & (hh.abs() < 0.25); keep &= ~inl
    alpha = float(torch.acos(n2[2].clamp(-1, 1))); et = torch.tensor([-n2[1], n2[0], 0.0], device=dev); et = et / et.norm()        # waagerecht in der Ebene (Traufrichtung)
    eh = torch.tensor([n2[0], n2[1], 0.0], device=dev); eh = -eh / eh.norm().clamp(min=1e-9)                                           # waagerecht hangaufwaerts (gegen die Normale)
    ebenen.append(dict(n=n2, d=d2, alpha=alpha, et=et, eh=eh, inlier=D[inl], anzahl=int(inl.sum())))
    print("Dachebene: n %s d %.2f Neigung %.1f Grad, Inlier %d" % ([round(float(x), 3) for x in n2], float(d2), np.rad2deg(alpha), int(inl.sum())), flush=True)
if not ebenen: print("keine Dachebene gefunden"); json.dump({"gauben": [], "segmente": []}, open(a[2], "w")); sys.exit(0)

# (2) Kandidaten ueber einer Ebene, im Grundriss der Ebene
from gpu_knn import min_abstand
kand = []
for ie, E in enumerate(ebenen):
    hh = (Pt * E["n"][None]).sum(1) + E["d"]; m = (hh > HMIN) & (hh < HMAX); Q = Pt[m]
    if len(Q) == 0: continue
    xy = torch.cat([Q[:, :2], torch.zeros(len(Q), 1, device=dev)], 1); ixy = torch.cat([E["inlier"][:, :2], torch.zeros(len(E["inlier"]), 1, device=dev)], 1)
    dxy = torch.tensor(min_abstand(xy.cpu().numpy(), ixy.cpu().numpy()), device=dev); Q = Q[dxy < 1.0]
    kand.append((Q, ie)); print("Ebene %d: %d Kandidatenpunkte %.1f-%.1f m ueber der Ebene im Grundriss" % (ie, len(Q), HMIN, HMAX), flush=True)

# (3) Cluster: ball_query + Labelausbreitung
def cluster(Q, r=0.35, kmax=48):
    idx = ball_query(Q[None], Q[None], K=kmax, radius=r).idx[0]; lab = torch.arange(len(Q), device=dev)
    for _ in range(500):
        nb = torch.where(idx >= 0, lab[idx.clamp(min=0)], lab[:, None]); neu = torch.minimum(lab, nb.min(1).values)
        if torch.equal(neu, lab): break
        lab = neu
    return lab

helme = []
if "--ausschluss" in a:
    A = json.load(open(g("--ausschluss", "", str))); helme = [(h["cx"], h["cy"]) for h in A.get("helme", [])]
cl = []
for Q, ie in kand:
    lab = cluster(Q); E = ebenen[ie]
    for l in torch.unique(lab):
        C = Q[lab == l]
        if len(C) < MIND: continue
        t = (C * E["et"][None]).sum(1); s = (C * E["eh"][None]).sum(1); bt, bs = float(t.max() - t.min()), float(s.max() - s.min())
        cx, cy = float(C[:, 0].mean()), float(C[:, 1].mean())
        if max(bt, bs) > MAXB or max(bt, bs) < 0.3: print("  Cluster %.1f/%.1f (%d Pkt) verworfen: Ausdehnung %.1f x %.1f" % (cx, cy, len(C), bt, bs)); continue
        if any(np.hypot(cx - hx, cy - hy) < 2.5 for hx, hy in helme): print("  Cluster %.1f/%.1f verworfen: Helm" % (cx, cy)); continue
        cl.append((C, ie)); print("  Cluster %.1f/%.1f z %.1f: %d Punkte, Ausdehnung quer %.1f laengs %.1f" % (cx, cy, float(C[:, 2].mean()), len(C), bt, bs), flush=True)
np.savez_compressed(a[2] + ".cluster.npz", P=np.concatenate([C.cpu().numpy() for C, _ in cl]) if cl else np.zeros((0, 3)), label=np.concatenate([np.full(len(C), i) for i, (C, _) in enumerate(cl)]) if cl else np.zeros(0))   # Sichtkontrolle (punkte_overlay)

KAM = json.load(open(g("--kam", "", str))) if "--kam" in a else None
# (4) Primitive + Rastersuche
def segmente_gaube(E, t0, s0, w, hf, ht, tiefe):
    """Kanten der Giebelgaube [B,8,2,3] fuer Parametertensoren [B]. Fusspunkt O = Punkt der Ebene mit Traufkoordinate t0 und Hangkoordinate s0 (waagerecht).
    First vom Scheitel (O + hf) bis zum Firstende in der Dachebene, waagerecht `tiefe` hangaufwaerts (First geneigt, flacher als das Hauptdach; Fotobefund: lange Kehlen-Dreiecke)."""
    n, d, et, eh = E["n"], E["d"], E["et"], E["eh"]
    # Ebenenpunkt aus (t0, s0): O = t0*et + s0*eh + z*ez mit n.O + d = 0 -> z = -(d + s0*(n.eh)) / nz   (n.et = 0)
    z = -(d + s0 * (n * eh).sum()) / n[2]; O = t0[:, None] * et[None] + s0[:, None] * eh[None] + torch.stack([torch.zeros_like(z), torch.zeros_like(z), z], 1)
    up = torch.tensor([0, 0, 1.0], device=dev); tanA = torch.tan(torch.tensor(E["alpha"], device=dev))
    cl_ = O - (w / 2)[:, None] * et[None]; cr = O + (w / 2)[:, None] * et[None]; tl = cl_ + ht[:, None] * up[None]; tr = cr + ht[:, None] * up[None]
    apex = O + hf[:, None] * up[None]; fend = O + tiefe[:, None] * eh[None] + (tiefe * tanA)[:, None] * up[None]       # Firstende liegt in der Dachebene
    S = torch.stack([torch.stack([apex, fend], 1), torch.stack([apex, tl], 1), torch.stack([apex, tr], 1), torch.stack([tl, tr], 1),
                     torch.stack([tl, cl_], 1), torch.stack([tr, cr], 1), torch.stack([tl, fend], 1), torch.stack([tr, fend], 1)], 1)
    return S

DT_CACHE = {}
def dt_karte(f):
    """Distanztransformation (px, Kartenmassstab) zur naechsten Stabilitaetskante >= 0,3 als GPU-Tensor (float16, gedeckelt DTCAP)."""
    if f not in DT_CACHE:
        if len(DT_CACHE) >= 40: DT_CACHE.pop(next(iter(DT_CACHE)))
        V = cv2.imread(os.path.join(g("--stabil", "", str), os.path.splitext(f)[0] + ".png"), 0); dt = cv2.distanceTransform((V < 0.3 * 255).astype(np.uint8), cv2.DIST_L2, 3)
        DT_CACHE[f] = torch.tensor(np.minimum(dt, DTCAP), device=dev, dtype=torch.float16)
    return DT_CACHE[f]
def fotos_fuer(c):
    """Die KFOTOS naechsten Fotos, die den Punkt c sehen (Bildmitte-Fenster 0,55), mit Kameradaten als Tensoren."""
    if not FOTOVERLUST or KAM is None: return []
    out = []
    for f in sorted(KAM):
        k = KAM[f]
        if not os.path.exists(os.path.join(g("--stabil", "", str), os.path.splitext(f)[0] + ".png")): continue
        R = np.array(k["Rn"]); t = np.array(k["tn"]); Xc = R @ c + t
        if Xc[2] < 8 or Xc[2] > 60 or abs(Xc[0] / Xc[2]) > 0.55 or abs(Xc[1] / Xc[2]) > 0.55: continue
        out.append((float(np.linalg.norm(np.array(k["C"]) - c)), f))
    out = [f for _, f in sorted(out)[:KFOTOS]]; res = []
    for f in out:
        k = KAM[f]; DT = dt_karte(f); H, W = DT.shape
        res.append(dict(R=torch.tensor(k["Rn"], device=dev, dtype=torch.float32), t=torch.tensor(k["tn"], device=dev, dtype=torch.float32), f=k["f"], cx=k["cx"], cy=k["cy"], k1=k["params"][3], sj=W / k["W"], DT=DT, H=H, W=W, name=f))
    return res
def foto_verlust(S, fotos):
    """S [B,8,2,3] -> mittlere Pixeldistanz [B] der 5 Stuetzpunkte je Kante zur naechsten Stabilitaetskante ueber die Fotos (ausserhalb des Bildes = DTCAP)."""
    if not fotos: return torch.zeros(S.shape[0], device=dev)
    tt = torch.linspace(0.1, 0.9, 5, device=dev); tot = torch.zeros(S.shape[0], device=dev)
    for c0 in range(0, S.shape[0], 16384):                                                        # Bloecke (Lauf v8: OOM bei 400k Kombinationen auf einmal)
        Sb = S[c0:c0 + 16384]; P = (Sb[:, :, 0, None] + (Sb[:, :, 1] - Sb[:, :, 0])[:, :, None] * tt[None, None, :, None]).reshape(Sb.shape[0], -1, 3)   # [b,40,3]
        for k in fotos:
            X = P @ k["R"].T + k["t"]; z = X[..., 2].clamp(min=0.3); x = X[..., 0] / z; y = X[..., 1] / z; f1 = 1 + k["k1"] * (x * x + y * y)
            u = ((k["f"] * x * f1 + k["cx"]) * k["sj"]).round().long(); v = ((k["f"] * y * f1 + k["cy"]) * k["sj"]).round().long(); inb = (u >= 0) & (u < k["W"]) & (v >= 0) & (v < k["H"]) & (X[..., 2] > 0.3)
            dd = torch.full(u.shape, DTCAP, device=dev); dd[inb] = k["DT"][v[inb], u[inb]].float(); tot[c0:c0 + 16384] += dd.mean(1)
    return tot / len(fotos)

def inlier_score(C, S, rho, fotos=()):
    """C [N,3], S [B,8,2,3] -> Score [B] = (Inlier (Abstand zu einer Kante < TOL) - Laenge*rho) * (1 - Fotoverlust/DTCAP)."""
    A_ = S[:, :, 0]; B_ = S[:, :, 1]; AB = B_ - A_; L2 = (AB ** 2).sum(-1).clamp(min=1e-9)                     # [B,8,3]
    best = torch.full((S.shape[0],), -1e9, device=dev); blk = max(8, min(256, int(1.5e7 / (8 * max(len(C), 1)))))   # Blockgroesse nach Punktzahl (VRAM-Deckel 1,5 GB; OOM Lauf v6 bei 256 x 8 x 20k Punkten)
    for c0 in range(0, S.shape[0], blk):
        sl = slice(c0, c0 + blk); Ap = A_[sl][:, :, None]; ABp = AB[sl][:, :, None]                        # [b,8,1,3]
        tt = (((C[None, None] - Ap) * ABp).sum(-1) / L2[sl][:, :, None]).clamp(0, 1)                      # [b,8,N]
        dist = (C[None, None] - (Ap + tt[..., None] * ABp)).norm(dim=-1).min(1).values                     # [b,N]
        inl = (dist < TOL).sum(1).float(); best[sl] = inl - rho * L2[sl].sqrt().sum(1)
    if fotos: best = best * (1 - foto_verlust(S, fotos) / DTCAP).clamp(min=0)
    return best

def fit(C, E):
    t = (C * E["et"][None]).sum(1); s = (C * E["eh"][None]).sum(1); tm, sm = float(t.median()), float(s.min()); fotos = fotos_fuer(C.mean(0).cpu().numpy())
    flaeche = max(float(t.max() - t.min()) * float(s.max() - s.min()), 0.5); rho = len(C) / flaeche * 2 * TOL * RHO     # Hintergrund: Bruchteil der Gleichverteilungsdichte je m Kante (Punkte sitzen auf Kanten, nicht gleichverteilt)
    def raster(*achsen):
        G = torch.meshgrid(*achsen, indexing="ij"); G = [x.flatten() for x in G]
        gueltig = (G[5] >= G[3] / np.tan(E["alpha"]) - 1e-6) & (G[4] < G[3])                   # First nicht steiler als das Hauptdach; Fronttraufe unter dem Scheitel
        sc_ = inlier_score(C, segmente_gaube(E, *G), rho, fotos); sc_[~gueltig] = -1e9; i = int(sc_.argmax())
        return [float(x[i]) for x in G], float(sc_[i])
    ar = lambda lo, hi, st: torch.arange(lo, hi + st / 2, st, device=dev)
    # grob (t0, s0, Breite, Scheitelhoehe, Fronttraufhoehe, Tiefe), dann fein um das Optimum (+-1 Grobschritt, Viertelschritte)
    grob = (0.1, 0.1, 0.15, 0.15, 0.15, 0.3)
    p, sc1 = raster(ar(tm - 0.4, tm + 0.4, grob[0]), ar(sm - 0.3, sm + 0.9, grob[1]), ar(0.4, 1.6, grob[2]), ar(0.3, 1.5, grob[3]), ar(0.1, 0.7, grob[4]), ar(0.5, 3.5, grob[5]))
    p, sc2 = raster(*[ar(p[i] - grob[i], p[i] + grob[i], grob[i] / 2) for i in range(6)])
    p, sc3 = raster(*[ar(p[i] - grob[i] / 2, p[i] + grob[i] / 2, grob[i] / 4) for i in range(6)])
    S = segmente_gaube(E, *[torch.tensor([x], device=dev) for x in p])[0]
    A_ = S[:, 0]; AB = S[:, 1] - S[:, 0]; L2 = (AB ** 2).sum(-1); tt = (((C[None] - A_[:, None]) * AB[:, None]).sum(-1) / L2[:, None]).clamp(0, 1)
    dist = (C[None] - (A_[:, None] + tt[..., None] * AB[:, None])).norm(dim=-1).min(0).values; inl = int((dist < TOL).sum())
    fv = float(foto_verlust(S[None], fotos)[0]) if fotos else None
    return dict(t0=p[0], s0=p[1], breite=p[2], h_first=p[3], h_traufe=p[4], tiefe=p[5], score=sc3, inlier=inl, punkte=int(len(C)), anteil=inl / len(C), fotoverlust_px=fv, fit_fotos=[k["name"] for k in fotos]), S

gauben = []
for C, ie in cl:
    E = ebenen[ie]
    if ALLE_PUNKTE:                                                                              # Fit auf ALLEN Sweep-Punkten im Umfeld des Clusters (Kehlen/Firstende liegen IN der Dachebene, nicht 0,2 m darueber)
        t = (C * E["et"][None]).sum(1); s = (C * E["eh"][None]).sum(1); hh = (Pt * E["n"][None]).sum(1) + E["d"]; tp = (Pt * E["et"][None]).sum(1); sp = (Pt * E["eh"][None]).sum(1)
        m = (tp > t.min() - 0.4) & (tp < t.max() + 0.4) & (sp > s.min() - 0.4) & (sp < s.max() + 1.5) & (hh > -0.3) & (hh < 2.0); C = Pt[m]
    gparams, S = fit(C, E); gparams["ebene"] = ie; O = S[3, 0].cpu().numpy() * 0.5 + S[3, 1].cpu().numpy() * 0.5
    gparams.update(mitte_front=[float(x) for x in O]); gauben.append(gparams)
    print("  Gaube Front %.2f %.2f %.2f: Breite %.2f  First +%.2f  Traufe +%.2f  Tiefe %.2f  Inlier %d/%d  Score %.0f" % (*O, gparams["breite"], gparams["h_first"], gparams["h_traufe"], gparams["tiefe"], gparams["inlier"], len(C), gparams["score"]), flush=True)

# (5) Gleichheitsregel je Reihe (gleiche Hanglage)
if GLEICH and len(gauben) >= 2:
    reihen = []
    for gb in sorted(gauben, key=lambda x: x["s0"]):
        if reihen and abs(gb["s0"] - reihen[-1][0]["s0"]) < 1.0: reihen[-1].append(gb)
        else: reihen.append([gb])
    for ri, R in enumerate(reihen):
        for gb in R: gb["reihe"] = ri
        if len(R) < 2: continue
        for key in ("breite", "h_first", "h_traufe", "tiefe"):
            med = float(np.median([gb[key] for gb in R]))
            for gb in R:
                gb[key + "_einzeln"] = gb[key]
                if abs(gb[key] - med) <= GTOL: gb[key] = med
                else: gb.setdefault("abweichend", []).append(key)
        print("Reihe %d (%d Gauben): Median Breite %.2f First %.2f Traufe %.2f Tiefe %.2f; Abweichungen (Breite, First, Tiefe):" % (ri, len(R), *[np.median([gb[k] for gb in R]) for k in ("breite", "h_first", "h_traufe", "tiefe")]),
              [(round(gb["breite_einzeln"] - gb["breite"], 2), round(gb["h_first_einzeln"] - gb["h_first"], 2), round(gb["tiefe_einzeln"] - gb["tiefe"], 2)) for gb in R], flush=True)

# (6) Fotopruefung + (7) Segmente
def kanten_belegung(S, KAM, sd):
    """Anteil der Kantenstuetzpunkte (alle 10 cm) mit Stabilitaetswert >= 0,3 im 3-px-Umfeld, gemittelt ueber Fotos, die die Gaube sehen (max 40 Fotos)."""
    pts = np.concatenate([s0_[None] + (s1_ - s0_)[None] * np.linspace(0, 1, max(2, int(np.linalg.norm(s1_ - s0_) / 0.1)))[:, None] for s0_, s1_ in S]); c = pts.mean(0); vals = []; nf = 0
    sicht = []
    for f in sorted(KAM):
        pf = os.path.join(sd, os.path.splitext(f)[0] + ".png")
        if not os.path.exists(pf): continue
        k = KAM[f]; R = np.array(k["Rn"]); t = np.array(k["tn"]); Xc = R @ c + t
        if Xc[2] < 8 or Xc[2] > 60 or abs(Xc[0] / Xc[2]) > 0.55 or abs(Xc[1] / Xc[2]) > 0.55: continue
        sicht.append(f)
    for f in sicht[::max(1, len(sicht) // 40)]:                                                 # gleichmaessig ueber alle Sichtfotos verteilt, nicht nur die ersten 40 alphabetisch
        pf = os.path.join(sd, os.path.splitext(f)[0] + ".png"); k = KAM[f]; R = np.array(k["Rn"]); t = np.array(k["tn"])
        V = cv2.imread(pf, 0); H, W = V.shape; sj = W / k["W"]; X = (R @ pts.T + t[:, None]); x = X[0] / X[2]; y = X[1] / X[2]; f1 = 1 + k["params"][3] * (x * x + y * y)
        u = np.round((k["f"] * x * f1 + k["cx"]) * sj).astype(int); v = np.round((k["f"] * y * f1 + k["cy"]) * sj).astype(int); ok = (u >= 3) & (u < W - 3) & (v >= 3) & (v < H - 3)
        if ok.sum() < 0.8 * len(u): continue
        Vd = cv2.dilate(V, np.ones((2 * PX + 1, 2 * PX + 1), np.uint8)); vals.append(float((Vd[v[ok], u[ok]] >= 0.3 * 255).mean())); nf += 1
        if nf >= 40: break
    return dict(fotos=nf, belegung=float(np.mean(vals)) if vals else None, fotos_ueber=int(sum(v_ >= FOTOMIN for v_ in vals)), belegung_q90=float(np.quantile(vals, 0.9)) if vals else None)

seg = []
for gb in gauben:
    E = ebenen[gb["ebene"]]; S = segmente_gaube(E, *[torch.tensor([gb[k]], device=dev) for k in ("t0", "s0", "breite", "h_first", "h_traufe", "tiefe")])[0].cpu().numpy()
    gb["bestanden"] = True
    if KAM is not None and "--stabil" in a:
        gb["foto"] = kanten_belegung(S, KAM, g("--stabil", "", str)); gb["bestanden"] = gb["foto"]["fotos_ueber"] >= NFOTO_G
        print("  Gaube %s Fotopruefung %s -> %s" % ([round(x, 1) for x in gb["mitte_front"]], gb["foto"], "bestanden" if gb["bestanden"] else "VERWORFEN (Kantenbelegung >= %.2f in weniger als %d Fotos)" % (FOTOMIN, NFOTO_G)), flush=True)
    if not gb["bestanden"]: continue
    for s0_, s1_ in S: seg.append([[float(x) for x in s0_], [float(x) for x in s1_], 12, round(min(1.0, gb["anteil"] + 0.3), 3)])
for E in ebenen: E.pop("inlier"); E.update(n=[float(x) for x in E["n"]], d=float(E["d"]), et=[float(x) for x in E["et"]], eh=[float(x) for x in E["eh"]])
json.dump({"traufe": TRAUFE, "dachebenen": ebenen, "gauben": gauben, "segmente": seg}, open(a[2], "w"), indent=1); print("fertig", len(gauben), "Gauben,", len(seg), "Segmente")
