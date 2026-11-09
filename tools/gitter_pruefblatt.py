"""Pruefblatt: Drahtgitter auf VIELEN Fotos aus verschiedenen Richtungen pruefen (Nutzerregel: immer in allen Bildern pruefen, nicht nur IMG_6261).
(1) Je Foto Stuetzung = Anteil der projizierten Segmentpunkte (ohne Z-Puffer, im Bild), an denen die Stabilitaetskarte >= thr ist (Toleranz 2 px).
(2) Fotos nach Blickrichtung/Position in k Gruppen (k-means auf Kamerazentrum + Blickvektor), je Gruppe das Foto mit den meisten Gitterpunkten im Bild -> Kontaktbogen OUT.jpg.
(3) Ausgabe OUT.json: Stuetzung je Foto, Mittel, schwaechste 10 Fotos.
Aufruf: gitter_pruefblatt.py KAM.json STABILDIR BILDER SEG.json OUT.jpg [--k 12] [--thr 0.25] [--zmin -99] [--nur N] [--wolke KANTEN.npz|.npy --ztol 0.5]
--wolke: Z-Puffer aus der Wolke (1/4 Aufloesung, 3x3-Splat): verdeckte Gitterpunkte zaehlen nicht und werden im Blatt grau gezeichnet (sonst zaehlt Verdecktes als falsch)."""
import sys, os, json, numpy as np, cv2, torch
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
K, THR, ZMIN, ZTOL = g("--k", 12, int), g("--thr", 0.25), g("--zmin", -99.0), g("--ztol", 0.5)
WOLKE = None
if "--wolke" in a:
    w = g("--wolke", "", str); W_ = np.load(w); W_ = W_["P"] if hasattr(W_, "files") else W_; WOLKE = torch.tensor(W_[:, :3], device="cuda", dtype=torch.float32)
KAM = json.load(open(a[1])); sd = a[2]; bd = a[3]; S = json.load(open(a[4]))["segmente"]; S = [s for s in S if max(s[0][2], s[1][2]) >= ZMIN]
dev = "cuda"
pts = []; col = []
for s in S:
    p0 = np.array(s[0]); p1 = np.array(s[1]); n = max(2, int(np.linalg.norm(p1 - p0) / 0.05)); pts.append(p0 + (p1 - p0) * np.linspace(0, 1, n)[:, None]); col += [s[2]] * n
P = torch.tensor(np.vstack(pts), device=dev, dtype=torch.float32); col = np.array(col)
fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))]
if "--nur" in a: fs = fs[:g("--nur", 0, int)]
res = {}
def proj(k, V):
    R = torch.tensor(k["Rn"], device=dev, dtype=torch.float32); t = torch.tensor(k["tn"], device=dev, dtype=torch.float32); sj = V.shape[1] / k["W"]
    X = P @ R.T + t; z = X[:, 2]; x = X[:, 0] / z.clamp(min=0.3); y = X[:, 1] / z.clamp(min=0.3); f1 = 1 + k["params"][3] * (x * x + y * y)
    u = (k["f"] * x * f1 + k["cx"]) * sj; v = (k["f"] * y * f1 + k["cy"]) * sj; H, W = V.shape
    ok = (z > 1) & (u >= 0) & (u < W - 1) & (v >= 0) & (v < H - 1)
    if WOLKE is not None:                                                                    # Sichtbarkeit: Z-Puffer der Wolke bei 1/4 Aufloesung
        Xw = WOLKE @ R.T + t; zw = Xw[:, 2]; m = zw > 0.5; xw = Xw[m, 0] / zw[m]; yw = Xw[m, 1] / zw[m]; fw = 1 + k["params"][3] * (xw * xw + yw * yw)
        uw = ((k["f"] * xw * fw + k["cx"]) * sj / 4).long(); vw = ((k["f"] * yw * fw + k["cy"]) * sj / 4).long(); Hq, Wq = H // 4 + 1, W // 4 + 1
        inb = (uw >= 0) & (uw < Wq) & (vw >= 0) & (vw < Hq); zb = torch.full((Hq * Wq,), 1e9, device=dev); zb.scatter_reduce_(0, (vw[inb] * Wq + uw[inb]), zw[m][inb], reduce="amin"); zb = zb.view(Hq, Wq)
        zb = -torch.nn.functional.max_pool2d(-zb[None, None], 3, 1, 1)[0, 0]
        leer = zb > 1e8; zb7 = -torch.nn.functional.max_pool2d(-zb[None, None], 9, 1, 4)[0, 0]; zb = torch.where(leer, zb7, zb)   # Loecher (duenne Wolke, z.B. Gewoelbe) aus 9x9-Umgebung fuellen
        uq = (u / 4).long().clamp(0, Wq - 1); vq = (v / 4).long().clamp(0, Hq - 1); sichtbar = z <= zb[vq, uq] + ZTOL; ok = ok & sichtbar
    return u, v, ok
for f in fs:
    V = torch.from_numpy(cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0)).to(dev)
    Vm = torch.nn.functional.max_pool2d(V[None, None].float(), 5, 1, 2)[0, 0]
    u, v, ok = proj(KAM[f], V); n = int(ok.sum())
    if n < 200: res[f] = dict(n=n, stuetz=None); continue
    hit = (Vm[v[ok].round().long(), u[ok].round().long()] >= 255 * THR).float().mean().item(); res[f] = dict(n=n, stuetz=round(hit, 3))
gut = {f: r for f, r in res.items() if r["stuetz"] is not None}
vals = np.array([r["stuetz"] for r in gut.values()]); print("Fotos mit Gitter im Bild %d / %d | Stuetzung Mittel %.3f Median %.3f  Q10 %.3f" % (len(gut), len(fs), vals.mean(), np.median(vals), np.quantile(vals, 0.1)))
schwach = sorted(gut.items(), key=lambda kv: kv[1]["stuetz"])[:10]; print("schwaechste:", [(f, r["stuetz"]) for f, r in schwach])
# Gruppen nach Lage/Blick -> Vertreter
F = np.array([np.r_[np.array(KAM[f]["C"]) / 10.0, np.array(KAM[f]["Rn"])[2]] for f in gut]); names = list(gut)
rng = np.random.default_rng(0); cent = F[rng.choice(len(F), min(K, len(F)), replace=False)]
for _ in range(25): lab = np.argmin(((F[:, None] - cent[None]) ** 2).sum(2), 1); cent = np.array([F[lab == i].mean(0) if (lab == i).any() else cent[i] for i in range(len(cent))])
rep = [names[max(np.where(lab == i)[0], key=lambda j: gut[names[j]]["n"])] for i in range(len(cent)) if (lab == i).any()]
farbe = {0: (60, 60, 255), 1: (255, 125, 60), 2: (80, 200, 80), 3: (30, 150, 240), 4: (0, 230, 230)}
kacheln = []
for f in rep:
    im = cv2.imread(os.path.join(bd, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); k = KAM[f]; s = im.shape[1] / k["W"]
    V = torch.zeros((int(k["H"] * s), int(k["W"] * s)), device=dev); u, v, ok = proj(k, V); u = u.cpu().numpy(); v = v.cpu().numpy(); ok = ok.cpu().numpy()
    for q in np.unique(col):
        m = ok & (col == q)
        for x, y in zip(u[m].astype(int), v[m].astype(int)): cv2.circle(im, (x, y), 3, farbe.get(int(q), (0, 255, 255)), -1)
    im = cv2.resize(im, (700, int(700 * im.shape[0] / im.shape[1])))[:700]
    pad = np.zeros((700, 700, 3), np.uint8); pad[:im.shape[0], :im.shape[1]] = im; cv2.putText(pad, "%s  %.2f" % (f[:28], gut[f]["stuetz"]), (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2); kacheln.append(pad)
cols = 4; rows = (len(kacheln) + cols - 1) // cols
while len(kacheln) < rows * cols: kacheln.append(np.zeros((700, 700, 3), np.uint8))
cv2.imwrite(a[5], np.vstack([np.hstack(kacheln[r * cols:(r + 1) * cols]) for r in range(rows)]))
json.dump(dict(mittel=float(vals.mean()), median=float(np.median(vals)), q10=float(np.quantile(vals, 0.1)), fotos=res, vertreter=rep), open(os.path.splitext(a[5])[0] + ".json", "w"), indent=1); print("Blatt", a[5], "Vertreter", rep)
