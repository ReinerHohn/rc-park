"""Turmhelme als Formfamilie (n-eckige Pyramide, Achse lotrecht) aus Tiefen-Sweep-Punkten fitten (GPU-Rastersuche), statt Geraden-RANSAC auf einem Kegel.
Ablauf: (1) Kandidaten automatisch: xy-Zellen ueber der Traufe, in denen der Punktradius mit der Hoehe faellt (Kegeltest), (2) je Kandidat Rastersuche
cx, cy, z_spitze, Neigung k (Radius r(z) = k*(z_spitze - z)) nach Inlier-Zahl |radial - r(z)| < tol, (3) Drehung der n Grate per Stabilitaetskarten (Projektion
der Grate in Fotos, Summe Kartenwert) - ohne Karten: Drehung aus dem Fussring (Segmente SEG.json nahe z_fuss), (4) Ausgabe Grate + Fussring als Segmente quelle=4.
Dachebenen-Ausschluss (9.11., kleiner Helm am Dachrand): vor Kandidatentest und Kegel-Fit werden im Umfeld 2,5 m bis zu --ebenen geneigte Ebenen (RANSAC, GPU,
Neigung 25-75 Grad: Dachflaechen, keine Waende, keine Kegelfacetten) gesucht; Punkte < --etol (0,25 m) von einer Ebene mit >= --eanteil der Punkte fliegen raus.
Spitzenpruefung (Stabilitaetskarten): Projektion der Spitze liegt in >= --nfoto (3) Fotos auf einer Kante (Kartenwert >= 0,3, Toleranz 3 px); dazu die hoechste
Achsenhoehe mit Kantenbelegung (Fahnenstange zaehlt mit) als spitze_foto_max. Nur Bericht, kein Ueberschreiben der Geometrie.
Aufruf: helm_fit.py SWEEP.npz OUT.json [--kam KAM.json --stabil DIR] [--seg SEG.json] [--zmin 15] [--zmax 30] [--n 8] [--tol 0.12] [--mind 1500] [--zentren x,y;x,y]
        [--ebenen 2 --etol 0.25 --eanteil 0.2] [--nfoto 3]
Alles aus den Daten; keine Objektkonstanten (Regel: nichts Objektspezifisches)."""
import sys, os, json, numpy as np, torch, cv2
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
ZMIN, ZMAX, N, TOL, MIND = g("--zmin", 15.0), g("--zmax", 30.0), g("--n", 8, int), g("--tol", 0.12), g("--mind", 1500, int)
EBENEN, ETOL, EANTEIL, NFOTO = g("--ebenen", 2, int), g("--etol", 0.25), g("--eanteil", 0.2), g("--nfoto", 3, int)
CAP, FUSS_MIN, KMAX, MINLIER = g("--cap", 300.0), g("--fuss_min", 0.25), g("--kmax", 0.25), g("--minlier", 1000, int)             # ANNAHME Formklasse Helm: Halbwinkel <= atan(0,25) = 14 Grad (Turmhelm), flachere Kegel sind Walme/Zelte                                       # Scheibenkappung der Inlier-Gewichte; Mindestbelegung des Mantels je Scheibe fuer den Fuss
dev = "cuda"; torch.cuda.set_per_process_memory_fraction(float(os.environ.get("RCPARK_GPU_ANTEIL", "0.18")))         # VRAM-Budget (<= 1,5 GB von 8,2)
torch.manual_seed(g("--seed", 0, int)); RANSAC_IT = g("--ransac_it", 12000, int)                   # Laeufe v4/v5/v6 (9.11.) gaben am grossen Helm Spitze 22,44/22,76/26,55: Ebenen-RANSAC zufaellig -> fester Seed + 3x Iterationen
Z = np.load(a[1]); P = Z["P"]; P = P[(P[:, 2] > ZMIN) & (P[:, 2] < ZMAX)]; Pt = torch.tensor(P, device=dev, dtype=torch.float32)
print("Punkte im Hoehenband", len(P), flush=True)

NZ = tuple(float(x) for x in g("--nz", "0.3,0.85", str).split(","))
def ebene_ransac(Q, tol=ETOL, it=None, nz=NZ):
    it = it or RANSAC_IT
    """Beste geneigte Ebene (3 Punkte -> Ebene, Inlier |Abstand| < tol) in Q [M,3] GPU; nur Normalen mit nz in --nz (0,3..0,85) = Dachneigung 32-72 Grad
    (Waende nz~0, steile Kegelfacetten nz~k und Ebenen durch Kegelflanken > 72 Grad bleiben, flache/waagerechte Traufringe nz > 0,85 bleiben). Gibt (Inlier, n, d) oder None."""
    M = len(Q)
    if M < 50: return None
    idx = torch.randint(0, M, (it, 3), device=dev); p = Q[idx]
    n = torch.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], dim=1); nn = n.norm(dim=1); n = n / nn.clamp(min=1e-9)[:, None]; d = -(n * p[:, 0]).sum(1)
    ok = (nn > 1e-6) & (n[:, 2].abs() > nz[0]) & (n[:, 2].abs() < nz[1]); best = (-1, None, None)
    for c0 in range(0, it, 512):
        sl = slice(c0, c0 + 512); inl = (((Q[None] * n[sl, None]).sum(2) + d[sl, None]).abs() < tol).sum(1); inl[~ok[sl]] = -1
        v, i = inl.max(0)
        if int(v) > best[0]: best = (int(v), n[sl][i], d[sl][i])
    return best if best[0] > 0 else None

def ohne_dachebene(Q):
    """Maske der Punkte von Q [M,3] GPU, die zu KEINER grossen geneigten Ebene (>= EANTEIL der Restpunkte) gehoeren; bis zu EBENEN Ebenen nacheinander."""
    keep = torch.ones(len(Q), dtype=torch.bool, device=dev); info = []
    for _ in range(EBENEN):
        r = ebene_ransac(Q[keep])
        if r is None or r[0] < EANTEIL * int(keep.sum()): break
        v, n, d = r; keep &= ((Q * n[None]).sum(1) + d).abs() >= ETOL; info.append(dict(inlier=v, n=[round(float(x), 3) for x in n], d=round(float(d), 2)))
    return keep, info

def kandidaten():
    """xy-Zellen (1 m) mit vielen Punkten, deren Medianradius um die Zellmitte in der oberen Haelfte kleiner ist als in der unteren (Kegel) -
    nach Abzug der Dachebenen im Umfeld 2,5 m (sonst mischt die Dachschraege hinter einem Randhelm in den Kegeltest)."""
    H, xe, ye = np.histogram2d(P[:, 0], P[:, 1], bins=[np.arange(P[:, 0].min() - 1, P[:, 0].max() + 2, 1.0), np.arange(P[:, 1].min() - 1, P[:, 1].max() + 2, 1.0)])
    out = []
    for ix, iy in zip(*np.where(H >= MIND)):
        cx, cy = xe[ix] + 0.5, ye[iy] + 0.5; mu = ((Pt[:, 0] - cx).abs() < 2.5) & ((Pt[:, 1] - cy).abs() < 2.5); U = Pt[mu]
        keep, _ = ohne_dachebene(U); U = U[keep]; Q = U[((U[:, 0] - cx).abs() < 1.5) & ((U[:, 1] - cy).abs() < 1.5)].cpu().numpy()
        if len(Q) < MIND / 3: continue
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
    keep, einfo = ohne_dachebene(Q); n_roh = int(len(Q)); Q = Q[keep]                             # Dachebenen raus, Fit nur auf dem Rest
    print("  Umfeld %.1f/%.1f: %d Punkte, Dachebenen %s -> %d Restpunkte" % (cx0, cy0, n_roh, einfo, len(Q)), flush=True)
    if len(Q) < 200: return None
    zq = torch.quantile(Q[:, 2], torch.tensor([0.05, 0.98], device=dev))
    # Dichte-Normierung je 0,5-m-Scheibe: Gewicht min(1, CAP/n_scheibe) - sonst zieht die dichte Traufzone (Tausende Punkte bei z 13-14) den Kegel breit/hoch (Lauf v3: Spitze 24,7 statt 22,4)
    si = ((Q[:, 2] - float(zq[0])) / 0.5).long().clamp(min=0); ns = torch.bincount(si).float(); wgt = (CAP / ns[si]).clamp(max=1.0)
    cxs = torch.arange(cx0 - 1.5, cx0 + 1.5, 0.05, device=dev); cys = torch.arange(cy0 - 1.5, cy0 + 1.5, 0.05, device=dev)
    zsp = torch.arange(float(zq[1]) - 1.0, float(zq[1]) + 4.0, 0.1, device=dev); ks = torch.arange(0.05, 0.45, 0.01, device=dev)
    best = (-1, None)
    for cx in cxs:                                                                             # Raster: cx x cy x z_spitze x k, GPU-Broadcast je cx
        dx = Q[:, 0] - cx; dy = Q[:, 1][None, :] - cys[:, None]; rad = torch.sqrt(dx[None] ** 2 + dy ** 2)        # [cy, N]
        for zs_ in zsp:
            dz = (zs_ - Q[:, 2]).clamp(min=0)                                                   # [N]
            r_soll = ks[:, None] * dz[None]                                                     # [k, N]
            inl = (((rad[:, None, :] - r_soll[None]).abs() < TOL).float() * wgt[None, None]).sum(2)   # [cy, k] gewichtete Inlier
            v, i = inl.flatten().max(0)
            if float(v) > best[0]: iy, ik = divmod(int(i), len(ks)); best = (float(v), (float(cx), float(cys[iy]), float(zs_), float(ks[ik])))
    vw, (cx, cy, zs_, k) = best
    # Fusshoehe: von der Spitze abwaerts, solange der Kegelmantel in der 0,5-m-Scheibe belegt ist: Belegung = Inlier / Punkte im Zylinder r(z)+0,3 >= FUSS_MIN (0,25);
    # die Traufzone darunter hat viele Punkte, aber nur Zufallstreffer auf dem verlaengerten Kegel (kleine Belegung) -> dort endet der Helm
    rad = torch.sqrt((Q[:, 0] - cx) ** 2 + (Q[:, 1] - cy) ** 2); rs = k * (zs_ - Q[:, 2]).clamp(min=0); inl = ((rad - rs).abs() < TOL); v = int(inl.sum())
    zb = torch.arange(float(zq[0]), zs_, 0.5, device=dev); zfuss = float(zq[0]); beleg = []
    for z in zb.flip(0):
        sch = (Q[:, 2] >= z) & (Q[:, 2] < z + 0.5); nzyl = int((sch & (rad < rs + 0.3)).sum()); ni = int((sch & inl).sum()); b = ni / max(nzyl, 1); beleg.append((round(float(z), 1), ni, nzyl, round(b, 2)))
        if nzyl >= 10 and (b < FUSS_MIN or ni < 5) and float(z) < zs_ - 1.0: zfuss = float(z) + 0.5; break
    else: zfuss = float(zb[0])
    # Rundheit: Inlier muessen die Achse umlaufen (Helm), eine Giebelwand/Dachkante belegt nur wenige Azimut-Sektoren
    az = torch.atan2(Q[inl, 1] - cy, Q[inl, 0] - cx); sekt = int(torch.unique(((az + np.pi) / (2 * np.pi) * 16).long().clamp(0, 15)).numel())
    # Anteil im Zylinder des Helms (Radius r_fuss+0,3, z_fuss-0,3..z_spitze+0,5) statt im ganzen 5x5-m-Fenster: sonst haengt der Wert von --zmin/Fenstergroesse ab
    rf = k * (zs_ - zfuss); zyl = (rad < rf + 0.3) & (Q[:, 2] > zfuss - 0.3) & (Q[:, 2] < zs_ + 0.5); nz = max(int(zyl.sum()), 1)
    return dict(cx=cx, cy=cy, z_spitze=zs_, k=k, z_fuss=zfuss, r_fuss=rf, inlier=int(v), inlier_gewichtet=round(vw, 1), punkte=int(len(Q)), punkte_roh=n_roh, dachebenen=einfo, anteil=float((inl & zyl).sum()) / nz,
                anteil_fenster=float(v) / len(Q), punkte_zylinder=nz, sektoren=sekt, belegung_scheiben=beleg)

def spitze_pruefen(h):
    """Stabilitaetskarten: in wie vielen Fotos liegt die projizierte Spitze auf einer Kante (Kartenwert >= 0,3 im 3-px-Umfeld)? Zusaetzlich entlang der
    Achse (z_fuss .. z_spitze+3, 0,1 m) die hoechste Hoehe, die noch in >= NFOTO Fotos Kante hat (spitze_foto_max; Fahnenstange zaehlt mit)."""
    if "--kam" not in a or "--stabil" not in a: return None
    KAM = json.load(open(g("--kam", "", str))); sd = g("--stabil", "", str); zz = np.arange(h["z_fuss"], h["z_spitze"] + 3.0, 0.1); treffer = np.zeros(len(zz), int); nf = 0; fotos_spitze = []
    i0 = min(int(round((h["z_spitze"] - h["z_fuss"]) / 0.1)), len(zz) - 1)
    for f in sorted(KAM):
        pf = os.path.join(sd, os.path.splitext(f)[0] + ".png")
        if not os.path.exists(pf): continue
        k = KAM[f]; R = np.array(k["Rn"]); t = np.array(k["tn"]); Xc = R @ np.array([h["cx"], h["cy"], h["z_spitze"]]) + t
        if Xc[2] < 8 or Xc[2] > 60 or abs(Xc[0] / Xc[2]) > 0.6 or abs(Xc[1] / Xc[2]) > 0.6: continue
        V = cv2.imread(pf, 0); H, W = V.shape; sj = W / k["W"]; nf += 1
        X = (R @ np.stack([np.full_like(zz, h["cx"]), np.full_like(zz, h["cy"]), zz]) + t[:, None]); x = X[0] / X[2]; y = X[1] / X[2]; f1 = 1 + k["params"][3] * (x * x + y * y)
        u = np.round((k["f"] * x * f1 + k["cx"]) * sj).astype(int); v = np.round((k["f"] * y * f1 + k["cy"]) * sj).astype(int)
        kante = lambda i: 3 <= u[i] < W - 3 and 3 <= v[i] < H - 3 and V[v[i] - 3:v[i] + 4, u[i] - 3:u[i] + 4].max() >= 0.3 * 255
        for i in range(len(zz)):
            if kante(i): treffer[i] += 1
        if kante(i0): fotos_spitze.append(f)
    if nf == 0: return None
    ok = np.where(treffer >= NFOTO)[0]
    return dict(fotos_sehen=nf, fotos_spitze_auf_kante=int(treffer[i0]), bestanden=bool(treffer[i0] >= NFOTO), spitze_foto_max=float(zz[ok[-1]]) if len(ok) else None,
                achse_treffer=[int(x) for x in treffer[::5]], beispiele=fotos_spitze[:5])

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
    if h is None or h["inlier"] < MINLIER: print("Kandidat", c[:2], "kein Fit / zu wenig Inlier (%s < %d; Lauf v5: Staffelgiebel-Kopf -5,8/10,1 mit 782 Inliern, r 0,52)" % (None if h is None else h["inlier"], MINLIER), flush=True); continue
    if h["k"] > KMAX: print("Kandidat", c[:2], "verworfen: Neigung k %.2f > %.2f (Halbwinkel %.0f Grad: flacher Kegel/Walm, kein Helm; Lauf v4 fand so Gaube+Dachschraege bei 3,7/10,2)" % (h["k"], KMAX, np.rad2deg(np.arctan(h["k"]))), flush=True); continue
    if h["anteil"] < g("--anteil", 0.3) or h["sektoren"] < g("--sektoren", 10, int):
        print("Kandidat", c[:2], "verworfen: Anteil %.2f Sektoren %d (Giebel/Dachkante, kein Helm); Fit war Mitte %.2f %.2f Spitze %.2f Fuss %.2f r %.2f k %.2f Inlier %d Zyl %d" % (h["anteil"], h["sektoren"], h["cx"], h["cy"], h["z_spitze"], h["z_fuss"], h["r_fuss"], h["k"], h["inlier"], h["punkte_zylinder"]), flush=True); continue
    dopp = [j for j, h2 in enumerate(helme) if np.hypot(h2["cx"] - h["cx"], h2["cy"] - h["cy"]) < 1.5]          # Nachbarzelle fand denselben Helm: besseren Zylinderanteil behalten
    if dopp:
        if h["anteil"] <= helme[dopp[0]]["anteil"]: print("Kandidat", c[:2], "ist derselbe Helm wie", (round(helme[dopp[0]]["cx"], 2), round(helme[dopp[0]]["cy"], 2)), "- verworfen", flush=True); continue
        print("Kandidat", c[:2], "ersetzt schwaecheren Doppelfund", flush=True); helme.pop(dopp[0]); seg = [s for s in seg if np.hypot(s[0][0] - h["cx"], s[0][1] - h["cy"]) > 1.5 and np.hypot(s[1][0] - h["cx"], s[1][1] - h["cy"]) > 1.5]
    phi, info = drehung(h); h["phi"] = phi; h["drehung_info"] = info; h["spitze_foto"] = spitze_pruefen(h); helme.append(h)
    print("  Spitzenpruefung Foto:", h["spitze_foto"], "\n  Scheibenbelegung (z, Inlier, Zylinder, Anteil) von oben:", h["belegung_scheiben"], flush=True)
    ap = [h["cx"], h["cy"], h["z_spitze"]]; ring = [[h["cx"] + h["r_fuss"] * np.cos(phi + 2 * np.pi * j / N), h["cy"] + h["r_fuss"] * np.sin(phi + 2 * np.pi * j / N), h["z_fuss"]] for j in range(N)]
    for j in range(N): seg.append([ap, ring[j], 4, 1.0]); seg.append([ring[j], ring[(j + 1) % N], 4, 1.0])
    print("Helm: Mitte %.2f %.2f  Spitze z %.2f  Fuss z %.2f r %.2f  Neigung %.2f  Inlier %d/%d (Zylinderanteil %.2f, Sektoren %d)  Drehung %.0f deg %s" % (h["cx"], h["cy"], h["z_spitze"], h["z_fuss"], h["r_fuss"], h["k"], h["inlier"], h["punkte"], h["anteil"], h["sektoren"], np.rad2deg(phi), info), flush=True)
json.dump({"helme": helme, "segmente": seg}, open(a[2], "w"), indent=1); print("fertig", len(helme), "Helme,", len(seg), "Segmente")
