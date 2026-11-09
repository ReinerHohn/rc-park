"""Spiegel-Prior (Nutzerregel 9.11.): mehrfach vorkommende Elemente gelten als gleich - beide Erker, beide Staffelgiebel, Helme, Gauben links/rechts.
Je Hoehenband: Fassadenachse (SVD), Dichte der Kantenpunkte entlang der Achse, Spiegelzentrum c0 = Lage mit maximaler Korrelation zwischen Dichte und
gespiegelter Dichte (Korr >= korr). Dann beide Haelften uebereinander legen (s' = |s - c0|), Musterhaelfte (Voxel) -> GPU-RANSAC -> Segmente auf BEIDE Seiten
zurueckspiegeln -> jede Kopie in >= nmin Fotos gegen die Stabilitaetskarte pruefen (Regel 9). Nur geprüfte Kopien (quelle 6) kommen dazu.
Aufruf: gitter_spiegel.py SWEEP.npz KAM.json STABILDIR SEG_IN.json OUT.json [--zmin 3 --zmax 30] [--band 2.0] [--korr 0.5] [--tiefe 0.6] [--tol 0.05]
  [--thr 0.3] [--nmin 3] [--stuetz 0.5] [--vox 0.03] [--minlen 0.2]
Keine Objektkonstanten."""
import sys, os, json, numpy as np, torch, cv2
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from kanten_lib import ransac_segmente
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
ZMIN, ZMAX, BAND, KORR, TIEFE = g("--zmin", 3.0), g("--zmax", 30.0), g("--band", 2.0), g("--korr", 0.5), g("--tiefe", 0.6)
TOL, THR, NMIN, STUETZ, VOX, MINLEN = g("--tol", 0.05), g("--thr", 0.3), g("--nmin", 3, int), g("--stuetz", 0.5), g("--vox", 0.03), g("--minlen", 0.2)
dev = "cuda"; Z = np.load(a[1]); P = Z["P"].astype(np.float32); KAM = json.load(open(a[2])); sd = a[3]; S0 = json.load(open(a[4]))
fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))]
KART = {}
def karte(f):
    if f not in KART: v = torch.from_numpy(cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0)).to(dev); KART[f] = torch.nn.functional.max_pool2d((v >= 255 * THR).float()[None, None], 5, 1, 2)[0, 0].to(torch.uint8)
    return KART[f]
def stuetzung_alle(segs):
    if not segs: return np.zeros(0, int), np.zeros(0, int)
    n = 24; A = torch.tensor([s[0] for s in segs], device=dev, dtype=torch.float32); B = torch.tensor([s[1] for s in segs], device=dev, dtype=torch.float32)
    tt = torch.linspace(0, 1, n, device=dev); Q = (A[:, None] + (B - A)[:, None] * tt[None, :, None]).reshape(-1, 3); M = len(segs); mid = ((A + B) / 2).cpu().numpy()
    ja = torch.zeros(M, device=dev, dtype=torch.int32); nein = torch.zeros(M, device=dev, dtype=torch.int32)
    for f in fs:
        k = KAM[f]; C = np.array(k["C"]); nah = torch.from_numpy((np.linalg.norm(mid - C, axis=1) < 45)).to(dev)
        if not nah.any(): continue
        R = torch.tensor(k["Rn"], device=dev); t = torch.tensor(k["tn"], device=dev); X = Q @ R.T + t; z = X[:, 2].clamp(min=0.3)
        V = karte(f); sj = V.shape[1] / k["W"]; x = X[:, 0] / z; y = X[:, 1] / z; f1 = 1 + k["params"][3] * (x * x + y * y)
        u = ((k["f"] * x * f1 + k["cx"]) * sj).round().long(); v = ((k["f"] * y * f1 + k["cy"]) * sj).round().long(); H, W = V.shape
        ok = (X[:, 2] > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        hit = torch.zeros(len(Q), device=dev); hit[ok] = V[v[ok], u[ok]].float()
        okm = ok.view(M, n).float().mean(1); hm = hit.view(M, n).sum(1) / ok.view(M, n).float().sum(1).clamp(min=1)
        g_ = nah & (okm >= 0.9); ja += (g_ & (hm >= STUETZ)).int(); nein += (g_ & (hm < STUETZ)).int()
    return ja.cpu().numpy(), nein.cpu().numpy()
# Fassadenachse aus dem ganzen Gebaeude (stabiler als je Band), Spiegelzentrum je Band
c_all = np.median(P[:, :2], 0); _, _, Vt = np.linalg.svd(P[:, :2] - c_all, full_matrices=False); u = Vt[0]; nrm = Vt[1]
neu = []; bericht = []
for z0 in np.arange(ZMIN, ZMAX, BAND):
    B = P[(P[:, 2] >= z0) & (P[:, 2] < z0 + BAND)]
    if len(B) < 1500: continue
    d = (B[:, :2] - c_all) @ nrm; med = np.median(d); B2 = B[np.abs(d - med) < TIEFE]
    if len(B2) < 1000: continue
    sx = (B2[:, :2] - c_all) @ u; bins = np.arange(sx.min(), sx.max() + 0.05, 0.05); h, _ = np.histogram(sx, bins=bins); h = h.astype(np.float64); h -= h.mean()
    # Spiegelzentrum: Korrelation von h mit umgekehrtem h bei Verschiebung -> Zentrum = (Verschiebung)/2
    cc = np.correlate(h, h[::-1], "full"); cc /= max(np.sum(h * h), 1e-9); lagc = np.arange(len(cc)) - (len(h) - 1); zent = (bins[0] + bins[-1]) / 2 + lagc * 0.05 / 2
    gueltig = np.abs(zent - (sx.min() + sx.max()) / 2) < (sx.max() - sx.min()) * 0.25        # Zentrum im mittleren Bereich
    if not gueltig.any(): continue
    i = np.argmax(np.where(gueltig, cc, -9)); c0 = zent[i]; korr = cc[i]
    if korr < KORR: bericht.append(dict(z=float(z0), zentrum=float(c0), korr=round(float(korr), 3), status="keine Spiegelung")); continue
    # Musterhaelfte: s' = |s - c0|, Tiefe d, z; Voxel nur, wenn von BEIDEN Seiten belegt
    seite = np.sign(sx - c0); M = np.stack([np.abs(sx - c0), (B2[:, :2] - c_all) @ nrm, B2[:, 2]], 1).astype(np.float32)
    gidx = np.floor(M / VOX).astype(np.int64); uniq, inv = np.unique(gidx, axis=0, return_inverse=True)
    links = np.bincount(inv, weights=(seite < 0), minlength=len(uniq)); rechts = np.bincount(inv, weights=(seite > 0), minlength=len(uniq))
    beide = (links > 0) & (rechts > 0); Mv = np.zeros((len(uniq), 3), np.float32); np.add.at(Mv, inv, M); Mv /= np.bincount(inv, minlength=len(uniq))[:, None]; Mv = Mv[beide]
    if len(Mv) < 60: bericht.append(dict(z=float(z0), zentrum=float(c0), korr=round(float(korr), 3), status="zu wenig beidseitig belegt")); continue
    segs = ransac_segmente(torch.from_numpy(Mv).to(dev), tol=TOL, minlen=MINLEN, minpts=10, maxit=800, log=False)
    kand = []
    for sg in segs:
        for sgn in (-1.0, 1.0):
            q = []
            for pt in (sg[0], sg[1]): sxy = c_all + u * (c0 + sgn * pt[0]) + nrm * pt[1]; q.append([float(sxy[0]), float(sxy[1]), float(pt[2])])
            kand.append(q)
    ja, nein = stuetzung_alle(kand); gepr = verw = 0
    for q, j, nn in zip(kand, ja, nein):
        if j >= NMIN and j >= nn: neu.append([q[0], q[1], 6, round(float(j) / max(j + nn, 1), 3)]); gepr += 1
        else: verw += 1
    bericht.append(dict(z=float(z0), zentrum=round(float(c0), 2), korr=round(float(korr), 3), voxel_beidseitig=int(beide.sum()), muster_segmente=len(segs), uebernommen=gepr, verworfen=verw, status="ok"))
    print("Band z %.0f-%.0f: Spiegelzentrum s=%.2f (Korr %.2f), beidseitig belegte Voxel %d, Muster-Segmente %d -> uebernommen %d, verworfen %d" % (z0, z0 + BAND, c0, korr, beide.sum(), len(segs), gepr, verw), flush=True)
S0["segmente"] = S0["segmente"] + neu; S0["spiegel"] = bericht; json.dump(S0, open(a[5], "w")); print("neu", len(neu), "gesamt", len(S0["segmente"]))
