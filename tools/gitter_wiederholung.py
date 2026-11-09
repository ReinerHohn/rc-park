"""Wiederholungs-Prior (Nutzerregel 9.11.): sich wiederholende Elemente (Balkonsaeulen, Fenster, Zacken, Konsolen) als generelle Regel nutzen.
Je Hoehenband (1 m Schritte) und Fassadenrichtung: Periode der Kantenpunkt-Dichte entlang der Fassade per Autokorrelation; alle Instanzen auf EINE
Musterzelle falten (Koordinate modulo Periode) -> dort ist die schwache Kante jeder Einzelinstanz in der Summe stark -> GPU-RANSAC auf der Musterzelle ->
Segmente an alle Positionen zurueckkopieren -> jede Kopie in >= nmin Fotos gegen die Stabilitaetskarte pruefen (Regel 9: Anzahl nur am Foto). Nur geprüfte Kopien bleiben.
Aufruf: gitter_wiederholung.py SWEEP.npz KAM.json STABILDIR SEG_IN.json OUT.json [--zmin 3 --zmax 16] [--band 1.0] [--pmin 0.25 --pmax 3.0] [--korr 0.45]
  [--nrep 4] [--tiefe 0.5] [--tol 0.04] [--thr 0.3] [--nmin 3] [--stuetz 0.5] [--vox 0.02]
Keine Objektkonstanten; alles aus den Daten."""
import sys, os, json, numpy as np, torch, cv2
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from kanten_lib import ransac_segmente
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
ZMIN, ZMAX, BAND = g("--zmin", 3.0), g("--zmax", 16.0), g("--band", 1.0); PMIN, PMAX, KORR = g("--pmin", 0.25), g("--pmax", 3.0), g("--korr", 0.45)
NREP, TIEFE, TOL, THR, NMIN, STUETZ, VOX = g("--nrep", 4, int), g("--tiefe", 0.5), g("--tol", 0.04), g("--thr", 0.3), g("--nmin", 3, int), g("--stuetz", 0.5), g("--vox", 0.02)
dev = "cuda"; Z = np.load(a[1]); P = Z["P"].astype(np.float32); KAM = json.load(open(a[2])); sd = a[3]; S0 = json.load(open(a[4]))
fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))]
KART = {}
def karte(f):
    if f not in KART: v = torch.from_numpy(cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0)).to(dev); KART[f] = torch.nn.functional.max_pool2d((v >= 255 * THR).float()[None, None], 5, 1, 2)[0, 0].to(torch.uint8)   # uint8: 440 Karten ~1,3 GB statt 5 GB
    return KART[f]
def stuetzung_alle(segs):
    """Vektorisiert: fuer ALLE Kandidatensegmente je Foto auf einmal. Rueckgabe ja[M], nein[M] = Zahl Fotos mit/ohne Kantenbeleg (>= STUETZ der Punkte auf Karte)."""
    if not segs: return np.zeros(0, int), np.zeros(0, int)
    n = 24; A = torch.tensor([s[0] for s in segs], device=dev, dtype=torch.float32); B = torch.tensor([s[1] for s in segs], device=dev, dtype=torch.float32)
    tt = torch.linspace(0, 1, n, device=dev); Q = (A[:, None] + (B - A)[:, None] * tt[None, :, None]).reshape(-1, 3); M = len(segs); mid = ((A + B) / 2).cpu().numpy()
    ja = torch.zeros(M, device=dev, dtype=torch.int32); nein = torch.zeros(M, device=dev, dtype=torch.int32)
    for f in fs:
        k = KAM[f]; C = np.array(k["C"]); nah = torch.from_numpy((np.linalg.norm(mid - C, axis=1) < 40)).to(dev)
        if not nah.any(): continue
        R = torch.tensor(k["Rn"], device=dev); t = torch.tensor(k["tn"], device=dev); X = Q @ R.T + t; z = X[:, 2].clamp(min=0.3)
        V = karte(f); sj = V.shape[1] / k["W"]; x = X[:, 0] / z; y = X[:, 1] / z; f1 = 1 + k["params"][3] * (x * x + y * y)
        u = ((k["f"] * x * f1 + k["cx"]) * sj).round().long(); v = ((k["f"] * y * f1 + k["cy"]) * sj).round().long(); H, W = V.shape
        ok = (X[:, 2] > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H)
        hit = torch.zeros(len(Q), device=dev); hit[ok] = V[v[ok], u[ok]].float()
        okm = ok.view(M, n).float().mean(1); hm = hit.view(M, n).sum(1) / ok.view(M, n).float().sum(1).clamp(min=1)
        g_ = nah & (okm >= 0.9); ja += (g_ & (hm >= STUETZ)).int(); nein += (g_ & (hm < STUETZ)).int()
    return ja.cpu().numpy(), nein.cpu().numpy()
neu = []; bericht = []
for z0 in np.arange(ZMIN, ZMAX, BAND):
    B = P[(P[:, 2] >= z0) & (P[:, 2] < z0 + BAND)]
    if len(B) < 2000: continue
    # Fassadenrichtung: Hauptachse der xy-Verteilung (gewichtet); Fassadentiefe-Filter um die Hauptebene
    c = np.median(B[:, :2], 0); U, s, Vt = np.linalg.svd(B[:, :2] - c, full_matrices=False); u = Vt[0]; nrm = Vt[1]
    d = (B[:, :2] - c) @ nrm; med = np.median(d); B2 = B[np.abs(d - med) < TIEFE]
    if len(B2) < 1500: continue
    sx = (B2[:, :2] - c) @ u; h, edges = np.histogram(sx, bins=np.arange(sx.min(), sx.max() + 0.02, 0.02)); h = h.astype(np.float64) - h.mean()
    ac = np.correlate(h, h, "full")[len(h) - 1:]; ac /= max(ac[0], 1e-9); lags = np.arange(len(ac)) * 0.02
    m = (lags >= PMIN) & (lags <= PMAX)
    if not m.any(): continue
    i = np.argmax(np.where(m, ac, -1)); per = lags[i]; staerke = ac[i]
    if staerke < KORR or (sx.max() - sx.min()) / per < NREP: bericht.append(dict(z=float(z0), periode=float(per), korr=float(staerke), status="keine Wiederholung")); continue
    # Phase: Verschiebung, bei der die gefaltete Dichte am spitzesten ist (groesstes Maximum)
    best = (-1, 0.0)
    for ph in np.arange(0, per, 0.02):
        hh, _ = np.histogram((sx - ph) % per, bins=int(per / 0.02) + 1); best = max(best, (hh.max(), ph))
    ph = best[1]; idx = np.floor((sx - ph) / per); s_fold = (sx - ph) % per; kopien = np.unique(idx);
    # Musterzelle: Punkte in Zellkoordinaten (s_fold entlang Fassade, d Tiefe, z) -> RANSAC
    dd = (B2[:, :2] - c) @ nrm; M = np.stack([s_fold, dd, B2[:, 2]], 1).astype(np.float32)
    # Ausduennen auf VOX, damit RANSAC schnell bleibt; Gewicht = Punkte je Voxel (Belegung ueber alle Instanzen)
    gidx = np.floor(M / VOX).astype(np.int64); _, inv, cnt = np.unique(gidx, axis=0, return_inverse=True, return_counts=True)
    Mv = np.zeros((cnt.size, 3), np.float32); np.add.at(Mv, inv, M); Mv /= cnt[:, None]; Mv = Mv[cnt >= max(2, len(kopien) // 3)]      # nur Voxel, die in mehreren Instanzen belegt sind
    if len(Mv) < 50: bericht.append(dict(z=float(z0), periode=float(per), korr=float(staerke), status="Musterzelle leer")); continue
    segs = ransac_segmente(torch.from_numpy(Mv).to(dev), tol=TOL, minlen=0.12, minpts=8, maxit=600, log=False)
    kand = []
    for sg in segs:
        for kk in kopien:
            q = []
            for pt in (sg[0], sg[1]):
                sxy = c + u * (pt[0] + ph + kk * per) + nrm * pt[1]; q.append([float(sxy[0]), float(sxy[1]), float(pt[2])])
            kand.append(q)
    ja, nein = stuetzung_alle(kand); gepr = verw = 0
    for q, j, nn in zip(kand, ja, nein):
        if j >= NMIN and j >= nn: neu.append([q[0], q[1], 5, round(float(j) / max(j + nn, 1), 3)]); gepr += 1
        else: verw += 1
    bericht.append(dict(z=float(z0), periode=round(float(per), 3), korr=round(float(staerke), 3), kopien=int(len(kopien)), muster_segmente=len(segs), uebernommen=gepr, verworfen=verw, status="ok"))
    print("Band z %.1f: Periode %.2f m (Korr %.2f), %d Instanzen, Muster-Segmente %d -> Kopien uebernommen %d, verworfen %d" % (z0, per, staerke, len(kopien), len(segs), gepr, verw), flush=True)
S0["segmente"] = S0["segmente"] + neu; S0["wiederholung"] = bericht; json.dump(S0, open(a[5], "w")); print("neu", len(neu), "gesamt", len(S0["segmente"]))
