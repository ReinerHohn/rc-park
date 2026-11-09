"""Regel "nie belegte Kanten verlieren" (Nutzer 9.11.: 'manche Kanten sind nicht mehr da'): Segmente eines frueheren Gitters, die im neuen fehlen
(> 70 % der Punkte weiter als 10 cm vom neuen Gitter), werden gegen die Stabilitaetskarten geprueft (>= nmin Fotos mit >= stuetz der Punkte auf einer Kante,
mehr Ja- als Nein-Fotos) und bei Beleg uebernommen (quelle 9). Prueft am Foto, nicht am Sweep-Konsens (der ist am Dach zu duenn).
Aufruf: gitter_zurueck.py VORHER.json NEU.json KAM.json STABILDIR OUT.json [--thr 0.3] [--nmin 3] [--stuetz 0.5] [--dmax 45]"""
import sys, os, json, numpy as np, torch, cv2
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
THR, NMIN, STUETZ, DMAX, TOLM = g("--thr", 0.3), g("--nmin", 3, int), g("--stuetz", 0.5), g("--dmax", 45.0), g("--tolm", 0.12)   # tolm: Lagetoleranz in Metern -> Pixel je Foto aus Abstand
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from gpu_knn import min_abstand
dev = "cuda"; V = json.load(open(a[1]))["segmente"]; N = json.load(open(a[2])); KAM = json.load(open(a[3])); sd = a[4]
fs = [f for f in sorted(KAM) if os.path.exists(os.path.join(sd, os.path.splitext(f)[0] + ".png"))]
f_ = lambda Q, X: (lambda d: np.asarray(d.cpu() if hasattr(d, "cpu") else d))(min_abstand(Q, X))
def pts(s, st=0.05):
    p0 = np.array(s[0]); p1 = np.array(s[1]); n = max(2, int(np.linalg.norm(p1 - p0) / st)); return (p0 + (p1 - p0) * np.linspace(0, 1, n)[:, None]).astype(np.float32)
NP = np.vstack([pts(s) for s in N["segmente"]]); fehlt = [s for s in V if (f_(pts(s), NP) >= 0.1).mean() > 0.7]
print("Vorgaenger", len(V), "davon im neuen Gitter fehlend", len(fehlt), flush=True)
KART = {}
def karte(f, rad):
    """Kantenmaske mit Toleranz rad Pixel (Dilatation); je Foto und Radius gecacht (Radius aus Abstand Kamera-Segment und tolm)."""
    key = (f, rad)
    if key not in KART:
        if (f, 0) not in KART: KART[(f, 0)] = (torch.from_numpy(cv2.imread(os.path.join(sd, os.path.splitext(f)[0] + ".png"), 0)).to(dev) >= 255 * THR)
        KART[key] = torch.nn.functional.max_pool2d(KART[(f, 0)].float()[None, None], 2 * rad + 1, 1, rad)[0, 0].to(torch.uint8)
    return KART[key]
def stuetzung_alle(segs):
    n = 24; A = torch.tensor([s[0] for s in segs], device=dev, dtype=torch.float32); B = torch.tensor([s[1] for s in segs], device=dev, dtype=torch.float32)
    tt = torch.linspace(0, 1, n, device=dev); Q = (A[:, None] + (B - A)[:, None] * tt[None, :, None]).reshape(-1, 3); M = len(segs); mid = ((A + B) / 2).cpu().numpy()
    ja = torch.zeros(M, device=dev, dtype=torch.int32); nein = torch.zeros(M, device=dev, dtype=torch.int32)
    for f in fs:
        k = KAM[f]; C = np.array(k["C"]); nah = torch.from_numpy((np.linalg.norm(mid - C, axis=1) < DMAX)).to(dev)
        if not nah.any(): continue
        R = torch.tensor(k["Rn"], device=dev); t = torch.tensor(k["tn"], device=dev); X = Q @ R.T + t; z = X[:, 2].clamp(min=0.3)
        dist = float(np.median(np.linalg.norm(mid - C, axis=1))); sj0 = 1500.0 / k["W"]; rad = int(np.clip(round(TOLM * k["f"] * sj0 / max(dist, 1.0)), 2, 8))   # 12 cm in Pixel bei 1500 px Breite
        Vm = karte(f, rad); sj = Vm.shape[1] / k["W"]; x = X[:, 0] / z; y = X[:, 1] / z; f1 = 1 + k["params"][3] * (x * x + y * y)
        u = ((k["f"] * x * f1 + k["cx"]) * sj).round().long(); v = ((k["f"] * y * f1 + k["cy"]) * sj).round().long(); H, W = Vm.shape
        ok = (X[:, 2] > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H); hit = torch.zeros(len(Q), device=dev); hit[ok] = Vm[v[ok], u[ok]].float()
        okm = ok.view(M, n).float().mean(1); hm = hit.view(M, n).sum(1) / ok.view(M, n).float().sum(1).clamp(min=1)
        g_ = nah & (okm >= 0.9); ja += (g_ & (hm >= STUETZ)).int(); nein += (g_ & (hm < STUETZ)).int()
    return ja.cpu().numpy(), nein.cpu().numpy()
zur = []
if fehlt:
    ja, nein = stuetzung_alle(fehlt)
    for s, j, nn in zip(fehlt, ja, nein):
        if j >= NMIN and j >= nn: s2 = list(s[:4]); s2[2] = 9; s2[3] = round(float(j) / max(j + nn, 1), 3); zur.append(s2)
N["segmente"] += zur; N["zurueck"] = dict(vorher=len(V), fehlend=len(fehlt), zurueck=len(zur)); json.dump(N, open(a[5], "w"))
z = np.array([max(s[0][2], s[1][2]) for s in zur]) if zur else np.zeros(0)
print("zurueckgeholt (fotobelegt)", len(zur), "| davon > 15 m:", int((z > 15).sum()), "| Gitter", len(N["segmente"]))
