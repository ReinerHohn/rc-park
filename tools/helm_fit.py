"""Turmhelme als Formfamilie (n-eckige Pyramide, Achse lotrecht) aus Tiefen-Sweep-Punkten fitten (GPU-Rastersuche), statt Geraden-RANSAC auf einem Kegel.
Ablauf: (1) Kandidaten automatisch: xy-Zellen ueber der Traufe, in denen der Punktradius mit der Hoehe faellt (Kegeltest), (2) je Kandidat Rastersuche
cx, cy, z_spitze, Neigung k (Radius r(z) = k*(z_spitze - z)) nach Inlier-Zahl |radial - r(z)| < tol, (3) Drehung der n Grate per Stabilitaetskarten (Projektion
der Grate in Fotos, Summe Kartenwert) - ohne Karten: Drehung aus dem Fussring (Segmente SEG.json nahe z_fuss), (4) Ausgabe Grate + Fussring als Segmente quelle=4.
Aufruf: helm_fit.py SWEEP.npz OUT.json [--kam KAM.json --stabil DIR] [--seg SEG.json] [--zmin 15] [--zmax 30] [--n 8] [--tol 0.12] [--mind 1500] [--zentren x,y;x,y]
Alles aus den Daten; keine Objektkonstanten (Regel: nichts Objektspezifisches)."""
import sys, os, json, numpy as np, torch, cv2
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
ZMIN, ZMAX, N, TOL, MIND = g("--zmin", 15.0), g("--zmax", 30.0), g("--n", 8, int), g("--tol", 0.12), g("--mind", 1500, int)
dev = "cuda"; Z = np.load(a[1]); P = Z["P"]; P = P[(P[:, 2] > ZMIN) & (P[:, 2] < ZMAX)]; Pt = torch.tensor(P, device=dev, dtype=torch.float32)
print("Punkte im Hoehenband", len(P), flush=True)

def kandidaten():
    """xy-Zellen (1 m) mit vielen Punkten, deren Medianradius um die Zellmitte in der oberen Haelfte kleiner ist als in der unteren (Kegel)."""
    H, xe, ye = np.histogram2d(P[:, 0], P[:, 1], bins=[np.arange(P[:, 0].min() - 1, P[:, 0].max() + 2, 1.0), np.arange(P[:, 1].min() - 1, P[:, 1].max() + 2, 1.0)])
    out = []
    for ix, iy in zip(*np.where(H >= MIND)):
        cx, cy = xe[ix] + 0.5, ye[iy] + 0.5; m = (np.abs(P[:, 0] - cx) < 1.5) & (np.abs(P[:, 1] - cy) < 1.5); Q = P[m]
        if len(Q) < MIND: continue
        zs = np.quantile(Q[:, 2], [0.1, 0.5, 0.9]); lo = Q[Q[:, 2] < zs[1]]; hi = Q[Q[:, 2] >= zs[1]]
        if zs[2] - zs[0] < 3: continue                                                          # zu flach: Dachlinie, kein Helm
        rl = np.median(np.linalg.norm(lo[:, :2] - np.median(lo[:, :2], 0), axis=1)); rh = np.median(np.linalg.norm(hi[:, :2] - np.median(hi[:, :2], 0), axis=1))
        if rh < 0.7 * rl: out.append((cx, cy, len(Q), rl, rh))
    # benachbarte Zellen zusammenfassen (groesste zuerst)
    out.sort(key=lambda t: -t[2]); fin = []
    for c in out:
        if all(abs(c[0] - f[0]) + abs(c[1] - f[1]) > 2.5 for f in fin): fin.append(c)
    return fin

if "--zentren" in a: K = [(float(x.split(",")[0]), float(x.split(",")[1]), 0, 0, 0) for x in g("--zentren", "", str).split(";")]
else: K = kandidaten()
print("Kandidaten", [(round(c[0], 1), round(c[1], 1), c[2]) for c in K], flush=True)

def fit(cx0, cy0):
    m = ((Pt[:, 0] - cx0).abs() < 2.5) & ((Pt[:, 1] - cy0).abs() < 2.5); Q = Pt[m]
    if len(Q) < 200: return None
    zq = torch.quantile(Q[:, 2], torch.tensor([0.05, 0.98], device=dev))
    cxs = torch.arange(cx0 - 1.5, cx0 + 1.5, 0.05, device=dev); cys = torch.arange(cy0 - 1.5, cy0 + 1.5, 0.05, device=dev)
    zsp = torch.arange(float(zq[1]) - 1.0, float(zq[1]) + 4.0, 0.1, device=dev); ks = torch.arange(0.05, 0.45, 0.01, device=dev)
    best = (-1, None)
    for cx in cxs:                                                                             # Raster: cx x cy x z_spitze x k, GPU-Broadcast je cx
        dx = Q[:, 0] - cx; dy = Q[:, 1][None, :] - cys[:, None]; rad = torch.sqrt(dx[None] ** 2 + dy ** 2)        # [cy, N]
        for zs_ in zsp:
            dz = (zs_ - Q[:, 2]).clamp(min=0)                                                   # [N]
            r_soll = ks[:, None] * dz[None]                                                     # [k, N]
            inl = ((rad[:, None, :] - r_soll[None]).abs() < TOL).sum(2)                        # [cy, k]
            v, i = inl.flatten().max(0)
            if float(v) > best[0]: iy, ik = divmod(int(i), len(ks)); best = (float(v), (float(cx), float(cys[iy]), float(zs_), float(ks[ik])))
    v, (cx, cy, zs_, k) = best
    # Fusshoehe: tiefste Hoehe, in der der Kegel noch belegt ist (Inlier-Dichte je 0,5-m-Scheibe > 20 % des Maximums)
    rad = torch.sqrt((Q[:, 0] - cx) ** 2 + (Q[:, 1] - cy) ** 2); inl = ((rad - k * (zs_ - Q[:, 2]).clamp(min=0)).abs() < TOL)
    zb = torch.arange(float(zq[0]), zs_, 0.5, device=dev); cnt = torch.tensor([int(((Q[:, 2] >= z) & (Q[:, 2] < z + 0.5) & inl).sum()) for z in zb], device=dev, dtype=torch.float32)
    ok = torch.where(cnt > 0.2 * cnt.max())[0]; zfuss = float(zb[ok[0]]) if len(ok) else float(zq[0])
    # Rundheit: Inlier muessen die Achse umlaufen (Helm), eine Giebelwand/Dachkante belegt nur wenige Azimut-Sektoren
    az = torch.atan2(Q[inl, 1] - cy, Q[inl, 0] - cx); sekt = int(torch.unique(((az + np.pi) / (2 * np.pi) * 16).long().clamp(0, 15)).numel())
    return dict(cx=cx, cy=cy, z_spitze=zs_, k=k, z_fuss=zfuss, r_fuss=k * (zs_ - zfuss), inlier=int(v), punkte=int(len(Q)), anteil=float(v) / len(Q), sektoren=sekt)

def drehung(h):
    """Drehwinkel der Grate: Stabilitaetskarten (Summe Kartenwerte entlang der projizierten Grate ueber alle Fotos, die den Helm sehen), sonst 0."""
    if "--kam" not in a or "--stabil" not in a: return 0.0, None
    KAM = json.load(open(g("--kam", "", str))); sd = g("--stabil", "", str); fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))]
    ap = np.array([h["cx"], h["cy"], h["z_spitze"]]); best = (-1, 0.0); karten = {}
    phis = np.arange(0, 2 * np.pi / N, np.deg2rad(2.0)); score = np.zeros(len(phis)); nf = 0
    for f in fs:
        k = KAM[f]; R = np.array(k["Rn"]); t = np.array(k["tn"]); Xc = R @ ap + t
        if Xc[2] < 8 or Xc[2] > 60: continue
        x = Xc[0] / Xc[2]; y = Xc[1] / Xc[2]
        if abs(x) > 0.6 or abs(y) > 0.6: continue                                              # Helm nicht/kaum im Bild
        V = cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0); H, W = V.shape; sj = W / k["W"]; nf += 1
        def pr(X):
            Xc = R @ X + t; x = Xc[0] / Xc[2]; y = Xc[1] / Xc[2]; f1 = 1 + k["params"][3] * (x * x + y * y); return (k["f"] * x * f1 + k["cx"]) * sj, (k["f"] * y * f1 + k["cy"]) * sj
        for i, phi in enumerate(phis):
            s = 0.0
            for j in range(N):
                ang = phi + 2 * np.pi * j / N; fu = np.array([h["cx"] + h["r_fuss"] * np.cos(ang), h["cy"] + h["r_fuss"] * np.sin(ang), h["z_fuss"]])
                for tt in np.linspace(0.05, 0.95, 24):
                    u, v = pr(ap + (fu - ap) * tt); ui, vi = int(round(u)), int(round(v))
                    if 1 <= ui < W - 1 and 1 <= vi < H - 1: s += V[vi - 1:vi + 2, ui - 1:ui + 2].max() / 255.0
            score[i] += s
    if nf == 0: return 0.0, None
    return float(phis[int(np.argmax(score))]), dict(fotos=nf, bestes=float(score.max()), mittel=float(score.mean()))

helme = []; seg = []
for c in K:
    h = fit(c[0], c[1])
    if h is None or h["inlier"] < 150: print("Kandidat", c[:2], "kein Fit", flush=True); continue
    if h["anteil"] < g("--anteil", 0.3) or h["sektoren"] < g("--sektoren", 10, int): print("Kandidat", c[:2], "verworfen: Anteil %.2f Sektoren %d (Giebel/Dachkante, kein Helm)" % (h["anteil"], h["sektoren"]), flush=True); continue
    phi, info = drehung(h); h["phi"] = phi; h["drehung_info"] = info; helme.append(h)
    ap = [h["cx"], h["cy"], h["z_spitze"]]; ring = [[h["cx"] + h["r_fuss"] * np.cos(phi + 2 * np.pi * j / N), h["cy"] + h["r_fuss"] * np.sin(phi + 2 * np.pi * j / N), h["z_fuss"]] for j in range(N)]
    for j in range(N): seg.append([ap, ring[j], 4, 1.0]); seg.append([ring[j], ring[(j + 1) % N], 4, 1.0])
    print("Helm: Mitte %.2f %.2f  Spitze z %.2f  Fuss z %.2f r %.2f  Neigung %.2f  Inlier %d/%d  Drehung %.0f deg %s" % (h["cx"], h["cy"], h["z_spitze"], h["z_fuss"], h["r_fuss"], h["k"], h["inlier"], h["punkte"], np.rad2deg(phi), info), flush=True)
json.dump({"helme": helme, "segmente": seg}, open(a[2], "w"), indent=1); print("fertig", len(helme), "Helme,", len(seg), "Segmente")
