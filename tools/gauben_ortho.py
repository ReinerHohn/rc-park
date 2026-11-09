"""Gauben Runde 3 (9.11.): Form aus dem FOTO, Lage aus der Dachebene. (1) Hauptdachebene aus dem Kantengitter (Traufe + First, wie gauben_fit --gitter), Dachviereck = Traufe..First
ueber die Traufbreite; (2) je Foto ein ORTHO der Stabilitaetskarte in Dachebenen-Koordinaten (t laengs Traufe, s hangaufwaerts waagerecht, 5 cm): Plane-Punkte projiziert, Kartenwert
(>= 0,3, 3 px dilatiert) gelesen - Kehlen und Firstende der Gauben liegen IN der Ebene, die Dreiecke erscheinen im Ortho unverzerrt und in allen Fotos an derselben Stelle (ersetzt die
Triangulation: der Schnitt des Sehstrahls mit der bekannten Ebene IST die 3D-Lage); (3) Kehlen-Dreieck-Schablonen (Breite w, Tiefe L: zwei zum Scheitel laufende Kanten + waagerechte
Front) per Template-Matching (TM_CCOEFF_NORMED) auf dem Mittel-Ortho, lokale Maxima, NMS; (4) Gate: Kantenbelegung des Dreiecksumrisses >= --fotomin (0,5) in >= --nfoto (3) Einzelfoto-Orthos;
(5) Hoehen (Fronttraufe h_t, Scheitel h_f) per GPU-Raster auf den Sweep-Punkten im Gaubenumfeld bei fester Lage/Breite/Tiefe; (6) Reihen-Gleichheitsregel (Median, 15 cm);
(7) Segmente quelle 12 (8 Kanten wie gauben_fit).
Aufruf: gauben_ortho.py SWEEP.npz GITTER.json OUT.json --kam KAM.json --stabil DIR --fotos f1.jpg,f2.jpg,... [--traufe auto] [--zmax 30] [--raster 0.05] [--schwelle 0.35]
        [--wmin 0.8 --wmax 1.8 --lmin 1.5 --lmax 3.5] [--fotomin 0.5 --nfoto 3] [--audit DIR]
Keine Objektkonstanten; Masse/Schwellen sind Parameter."""
import sys, os, json, numpy as np, torch, cv2
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
ZMAX, RAST, SCHW, FOTOMIN, NFOTO = g("--zmax", 30.0), g("--raster", 0.05), g("--schwelle", 0.35), g("--fotomin", 0.5), g("--nfoto", 3, int)
WMIN, WMAX, LMIN, LMAX = g("--wmin", 0.8), g("--wmax", 1.8), g("--lmin", 1.5), g("--lmax", 3.5)
dev = "cuda"; torch.cuda.set_per_process_memory_fraction(float(os.environ.get("RCPARK_GPU_ANTEIL", "0.1")))
SW = np.load(a[1])["P"].astype(np.float32); SG = json.load(open(a[2]))["segmente"]; KAM = json.load(open(g("--kam", "", str))); sd = g("--stabil", "", str); fotos = g("--fotos", "", str).split(",")
audit = g("--audit", os.path.dirname(a[3]), str)

# (1) Dachebene aus Gitter
S3 = np.array([[s[0], s[1]] for s in SG], dtype=float); L = np.linalg.norm(S3[:, 1] - S3[:, 0], axis=1); dz = np.abs(S3[:, 1, 2] - S3[:, 0, 2]); zm = S3[:, :, 2].mean(1); hz = (L > 2.0) & (dz < 0.1 * L)
if g("--traufe", "auto", str) != "auto": TRAUFE = g("--traufe", 0.0)
else:                                                                                               # Traufe wie gauben_fit: hoechstes 0,5-m-Band der Sweep-Punkte, ueber dem die Punktzahl auf < 1/4 faellt
    ZMIN_T = g("--zmin", 10.0); Pz = SW[(SW[:, 2] > ZMIN_T) & (SW[:, 2] < ZMAX), 2]; e = np.arange(ZMIN_T, ZMAX + 0.5, 0.5); h, _ = np.histogram(Pz, bins=e); TRAUFE = None   # Band wie gauben_fit (--zmin 10); Lauf 2 mit z > 5 fand 13,21 statt 14,33
    for i in range(len(h) - 3, 0, -1):
        if h[i] > 0.02 * len(Pz) and h[i] > 4 * max(h[i + 1], 1) and h[i] > 4 * max(h[i + 2], 1): TRAUFE = float(e[i + 1]); break
    if TRAUFE is None: TRAUFE = float(np.quantile(Pz, 0.8))
mt = hz & (np.abs(zm - TRAUFE) < 0.6); e = np.arange(TRAUFE + 2, ZMAX, 0.5); hist = np.array([L[hz & (zm >= z) & (zm < z + 0.5)].sum() for z in e])
zf = e[int(np.where(hist >= 10)[0].max())] + 0.25 if (hist >= 10).any() else e[int(np.argmax(hist))] + 0.25; mf = hz & (np.abs(zm - zf) < 0.6)           # First = HOECHSTES Band mit >= 10 m Gitterlaenge (Lauf 1 nahm das laengste = Traufe)
P3 = np.concatenate([S3[mt].reshape(-1, 3), S3[mf].reshape(-1, 3)]); c = P3.mean(0); n = np.linalg.svd(P3 - c, full_matrices=False)[2][-1]; n = n if n[2] > 0 else -n; d = -n @ c
alpha = float(np.arccos(np.clip(n[2], -1, 1))); et = np.array([-n[1], n[0], 0.0]); et /= np.linalg.norm(et); eh = -np.array([n[0], n[1], 0.0]); eh /= np.linalg.norm(eh)
def ebene_punkt(t, s):
    """Ebenenpunkt aus (t laengs Traufe, s waagerecht hangaufwaerts)."""
    z = -(d + s * (n @ eh)) / n[2]; return t * et + s * eh + np.array([0, 0, z])
tE = S3[mt].reshape(-1, 3) @ et; sE = (S3[mt].reshape(-1, 3) @ eh).mean(); sF = (S3[mf].reshape(-1, 3) @ eh).mean(); t_lo, t_hi = float(tE.min()), float(tE.max())
print("Dachebene aus Gitter: Traufe %.2f (%d Seg.), First %.2f (%d Seg.), Neigung %.1f Grad, n %s; Dachviereck t %.1f..%.1f, s %.2f..%.2f (Tiefe %.1f m)" % (TRAUFE, mt.sum(), zf, mf.sum(), np.rad2deg(alpha), n.round(3).tolist(), t_lo, t_hi, sE, sF, sF - sE), flush=True)

# (2) Orthos
ts = np.arange(t_lo, t_hi, RAST); ss = np.arange(sE, sF, RAST); TT, SS = np.meshgrid(ts, ss, indexing="xy")                      # Zeilen = s (hangaufwaerts), Spalten = t
PP = np.stack([ebene_punkt(t, s) for t, s in zip(TT.ravel(), SS.ravel())])
orthos = {}; roh = {}
for f in fotos:
    k = KAM[f]; V = cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0); H, W = V.shape; sj = W / k["W"]; Vd = cv2.dilate(V, np.ones((7, 7), np.uint8))
    R = np.array(k["Rn"]); t_ = np.array(k["tn"]); X = R @ PP.T + t_[:, None]; x = X[0] / X[2]; y = X[1] / X[2]; f1 = 1 + k["params"][3] * (x * x + y * y)
    u = np.round((k["f"] * x * f1 + k["cx"]) * sj).astype(int); v = np.round((k["f"] * y * f1 + k["cy"]) * sj).astype(int); ok = (X[2] > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
    O = np.zeros(len(PP), np.float32); O[ok] = Vd[v[ok], u[ok]] / 255.0; O = O.reshape(TT.shape); orthos[f] = (O >= 0.3).astype(np.float32); roh[f] = O
    print("Ortho %s: %.0f %% des Dachs im Bild, Kantenanteil %.3f" % (f, 100 * ok.mean(), orthos[f].mean()), flush=True)
    cv2.imwrite(os.path.join(audit, "gauben_ortho_%s.png" % os.path.splitext(f)[0]), (np.flipud(O) * 255).astype(np.uint8))
M = np.mean([orthos[f] for f in fotos], 0); cv2.imwrite(os.path.join(audit, "gauben_ortho_mittel.png"), (np.flipud(M) * 255).astype(np.uint8))

# (3) Dreiecksschablonen
def schablone(w, Lm):
    wp, lp = int(round(w / RAST)), int(round(Lm / RAST)); T = np.zeros((lp + 3, wp + 3), np.uint8); ax = (wp + 2) // 2
    cv2.line(T, (ax, lp + 1), (1, 1), 1, 1); cv2.line(T, (ax, lp + 1), (wp + 1, 1), 1, 1); cv2.line(T, (1, 1), (wp + 1, 1), 1, 1)      # Scheitel oben (hohe Zeile = hangaufwaerts), Front unten
    return cv2.dilate(T, np.ones((3, 3), np.uint8)).astype(np.float32), T
kand = []
for w in np.arange(WMIN, WMAX + 1e-6, 0.2):
    for Lm in np.arange(LMIN, LMAX + 1e-6, 0.25):
        Td, T = schablone(w, Lm)
        if Td.shape[0] >= M.shape[0] or Td.shape[1] >= M.shape[1]: continue
        res = cv2.matchTemplate(M, Td, cv2.TM_CCOEFF_NORMED); loc = (res >= SCHW) & (res == cv2.dilate(res, np.ones((9, 9), np.uint8)))
        for r, cidx in zip(*np.where(loc)): kand.append((float(res[r, cidx]), float(ts[cidx] + (T.shape[1] / 2) * RAST), float(ss[r] + 1 * RAST), float(w), float(Lm), r, cidx, T))
kand.sort(key=lambda x: -x[0]); fin = []
for kd in kand:
    if all(abs(kd[1] - f_[1]) > 1.2 or abs(kd[2] - f_[2]) > 1.2 for f_ in fin): fin.append(kd)
print("Schablonentreffer: %d, nach NMS %d: %s" % (len(kand), len(fin), [(round(k_[0], 2), round(k_[1], 2), round(k_[2], 2), k_[3], k_[4]) for k_ in fin]), flush=True)
if g("--detektor", "blob", str) == "blob":
    # Lauf 4 (Mittel-Ortho ANGESEHEN): die 5 Gauben erscheinen als klare, aber durch Parallaxe (Front/Scheitel liegen UEBER der Ebene) schraeg verschmierte Flecken, keine sauberen
    # Dreiecke; Traufe/First/Seiten sind helle Baender. Daher: Flecken im Dachinneren (Rand --rand 1,0 m frei) im Mittel-Ortho >= --blob 0,4, Zusammenhang, Flaeche 0,5..8 m^2;
    # Lage = unterster Fleckpunkt (Front, s minimal) in der Mitte der t-Ausdehnung, Breite = t-Ausdehnung, Tiefe = s-Ausdehnung (Parallaxe streckt beides - Bericht, Masse unsicher).
    rand = int(round(g("--rand", 1.0) / RAST)); Mi = M.copy(); Mi[:rand] = 0; Mi[-rand:] = 0; Mi[:, :rand] = 0; Mi[:, -rand:] = 0
    bw = (Mi >= g("--blob", 0.4)).astype(np.uint8); bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)); nl, lab, st, ce = cv2.connectedComponentsWithStats(bw, 8); fin = []
    for i in range(1, nl):
        A_ = st[i, 4] * RAST * RAST
        if A_ < 0.5 or A_ > 8.0: continue
        ys, xs = np.where(lab == i); r0 = int(ys.min()); w = float((xs.max() - xs.min() + 1) * RAST); Lm = float((ys.max() - ys.min() + 1) * RAST)
        t0 = float(ts[int(round(xs.mean()))]); s0 = float(ss[r0]); Td, T = schablone(min(max(w, WMIN), WMAX), min(max(Lm, LMIN), LMAX)); cidx = int(round(xs.mean())) - T.shape[1] // 2
        fin.append((float(Mi[ys, xs].mean()), t0, s0, round(w, 2), round(Lm, 2), r0, cidx, T)); print("  Fleck %d: Flaeche %.1f m^2, t %.2f s %.2f, Breite %.2f, Tiefe %.2f, mittlere Belegung %.2f" % (i, A_, t0, s0, w, Lm, fin[-1][0]), flush=True)
    fin.sort(key=lambda x: -x[0]); print("Fleckdetektor: %d Kandidaten" % len(fin), flush=True)

# (4) Gate je Einzelfoto-Ortho
gauben = []
for sc, t0, s0, w, Lm, r, cidx, T in fin:
    ys, xs = np.where(T > 0); ys = ys + r; xs = xs + cidx; bel = {}
    for f in fotos:
        O = orthos[f]; okk = (ys < O.shape[0]) & (xs < O.shape[1]); Od = cv2.dilate(O, np.ones((3, 3), np.uint8)); bel[f] = float(Od[ys[okk], xs[okk]].mean()) if okk.sum() > 10 else 0.0
    nue = sum(v >= FOTOMIN for v in bel.values()); gauben.append(dict(t0=t0, s0=s0, breite=w, tiefe=Lm, match=sc, belegung=bel, fotos_ueber=nue, bestanden=bool(nue >= NFOTO)))
    print("  Kandidat t %.2f s %.2f w %.1f L %.2f match %.2f Belegung %s -> %s" % (t0, s0, w, Lm, sc, {kf[-8:-4]: round(v, 2) for kf, v in bel.items()}, "bestanden" if nue >= NFOTO else "verworfen"), flush=True)

# (5) Hoehen aus Sweep-Punkten (GPU-Raster h_t, h_f bei fester Lage), (6) Reihen, (7) Segmente
tanA = np.tan(alpha); SWt = torch.tensor(SW, device=dev); tsw = SWt @ torch.tensor(et, device=dev, dtype=torch.float32); ssw = SWt @ torch.tensor(eh, device=dev, dtype=torch.float32)
hsw = SWt @ torch.tensor(n, device=dev, dtype=torch.float32) + d
def kanten(gb, ht, hf):
    O = ebene_punkt(gb["t0"], gb["s0"]); up = np.array([0, 0, 1.0]); cl, cr = O - gb["breite"] / 2 * et, O + gb["breite"] / 2 * et; tl, tr = cl + ht * up, cr + ht * up
    apex = O + hf * up; fend = ebene_punkt(gb["t0"], gb["s0"] + gb["tiefe"])
    return [(apex, fend), (apex, tl), (apex, tr), (tl, tr), (tl, cl), (tr, cr), (tl, fend), (tr, fend)]
for gb in gauben:
    m = (tsw > gb["t0"] - gb["breite"]) & (tsw < gb["t0"] + gb["breite"]) & (ssw > gb["s0"] - 0.5) & (ssw < gb["s0"] + gb["tiefe"] + 0.5) & (hsw > -0.3) & (hsw < 2.5); C = SWt[m]
    gb["sweep_punkte"] = int(len(C)); best = (-1, 0.5, 1.0)
    if len(C) >= 50:
        for ht in np.arange(0.2, 1.01, 0.1):
            for hf in np.arange(ht + 0.1, 2.01, 0.1):
                K = kanten(gb, ht, hf); A_ = torch.tensor(np.array([k_[0] for k_ in K]), device=dev, dtype=torch.float32); B_ = torch.tensor(np.array([k_[1] for k_ in K]), device=dev, dtype=torch.float32)
                AB = B_ - A_; L2 = (AB ** 2).sum(-1).clamp(min=1e-9); tt = (((C[None] - A_[:, None]) * AB[:, None]).sum(-1) / L2[:, None]).clamp(0, 1)
                inl = int(((C[None] - (A_[:, None] + tt[..., None] * AB[:, None])).norm(dim=-1).min(0).values < 0.25).sum())
                if inl > best[0]: best = (inl, float(ht), float(hf))
    gb["h_traufe"], gb["h_first"], gb["sweep_inlier"] = best[1], best[2], max(best[0], 0); gb["hoehen_quelle"] = "Sweep-Raster" if best[0] > 0 else "ANNAHME 0,5/1,0 (zu wenig Sweep-Punkte)"
reihen = []
for gb in sorted([x for x in gauben if x["bestanden"]], key=lambda x: x["s0"]):
    if reihen and abs(gb["s0"] - reihen[-1][0]["s0"]) < 1.0: reihen[-1].append(gb)
    else: reihen.append([gb])
for ri, R_ in enumerate(reihen):
    for gb in R_: gb["reihe"] = ri
    if len(R_) < 2: continue
    for key in ("breite", "tiefe", "h_traufe", "h_first"):
        med = float(np.median([gb[key] for gb in R_]))
        for gb in R_:
            gb[key + "_einzeln"] = gb[key]
            if abs(gb[key] - med) <= 0.15: gb[key] = med
            else: gb.setdefault("abweichend", []).append(key)
    print("Reihe %d (%d Gauben, s0 ~ %.2f): Median Breite %.2f Tiefe %.2f Traufe %.2f First %.2f" % (ri, len(R_), np.mean([gb["s0"] for gb in R_]), *[np.median([gb[k_] for gb in R_]) for k_ in ("breite", "tiefe", "h_traufe", "h_first")]), flush=True)
seg = []
for gb in gauben:
    gb["mitte_front"] = [float(x) for x in ebene_punkt(gb["t0"], gb["s0"])]
    if not gb["bestanden"]: continue
    for p0, p1 in kanten(gb, gb["h_traufe"], gb["h_first"]): seg.append([[float(x) for x in p0], [float(x) for x in p1], 12, round(min(gb["belegung"].values()), 3)])
json.dump({"traufe": TRAUFE, "first": zf, "dachebene": dict(n=n.tolist(), d=float(d), alpha=alpha, et=et.tolist(), eh=eh.tolist(), t=[t_lo, t_hi], s=[float(sE), float(sF)]), "fotos": fotos, "gauben": gauben, "segmente": seg}, open(a[3], "w"), indent=1)
print("fertig: %d Kandidaten, %d bestanden, %d Segmente" % (len(gauben), sum(gb["bestanden"] for gb in gauben), len(seg)))
