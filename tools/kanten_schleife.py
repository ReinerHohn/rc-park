"""Kanten-Schleife: Drahtgitter <-> echte Fotos, iterativ. Je Durchgang: (1) Segmente in alle Fotos projizieren (Z-Puffer-Sichtbarkeit),
Unterstuetzung = Anteil der sichtbaren Fotos mit SAM-Grenze (Distanzbild <= tol px) auf dem Segment; (2) schwache Segmente loeschen;
(3) Segmente per GPU-Zufallssuche (Endpunkte) auf maximale Fotounterstuetzung verschieben; (4) Kantenpunkte ohne Segment -> neue Kandidaten (RANSAC), nur mit Fotounterstuetzung behalten.
Aufruf: python -I tools/kanten_schleife.py KAM.json KANTEN.npz FOTOS.npz MASKEN BILDER SEG_IN.json OUT.json AUDITPREFIX [--iter 6] [--tol 3] [--min 0.3] [--fix FIX.json]
Segmente in --fix (vom Editor, Nutzerkorrektur) werden nie geloescht/verschoben."""
import sys, os, json, time, numpy as np, torch, cv2, torch.nn.functional as Fn
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from kanten_lib import ransac_segmente
def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
NIT = opt("--iter", 6, int); TOL = opt("--tol", 3.0); MIN = opt("--min", 0.3); dev = "cuda"
KAM = json.load(open(sys.argv[1])); kz = np.load(sys.argv[2]); P = kz["P"]; vis_n = kz["vis"]; ratio = kz["kan"] / np.maximum(vis_n, 1); EP = torch.from_numpy(P[(vis_n >= 6) & (ratio >= 0.5)]).to(dev)
fotos = list(np.load(sys.argv[3])["fotos"]); md = sys.argv[4]; bd = sys.argv[5]; Pt = torch.from_numpy(P).to(dev)
DT = []; ZM = []; INF = []; t0 = time.time()
for f in fotos:
    cp = os.path.join(md, os.path.splitext(f)[0] + ".npz")
    if not os.path.exists(cp): continue
    K = KAM[f]; lab = np.load(cp)["lab"]; h, w = lab.shape; s = w / K["W"]; b = np.zeros((h, w), bool); b[:, :-1] |= lab[:, :-1] != lab[:, 1:]; b[:-1, :] |= lab[:-1, :] != lab[1:, :]
    dt = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 3); DT.append(torch.from_numpy(np.minimum(dt[::2, ::2], 255).astype(np.uint8)).to(dev)); INF.append((f, K, s, h, w))
    lt = Pt @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = lt[:, 2]
    uv = (K["f"] * lt[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev)) * s; u = uv[:, 0].round().long(); v = uv[:, 1].round().long(); ok = (z > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    q = 3; hz, wz = h // q + 1, w // q + 1; pz = (v.clamp(0, h - 1) // q) * wz + (u.clamp(0, w - 1) // q); zb = torch.full((hz * wz,), 1e9, device=dev); zb.scatter_reduce_(0, pz[ok], z[ok], "amin"); ZM.append(-Fn.max_pool2d(-zb.view(1, 1, hz, wz), 9, 1, 4).view(-1))
print("Fotos", len(INF), "Vorbereitung %.0fs" % (time.time() - t0), flush=True)
def stuetzung(Q):
    """Q (M,3) -> (weich_summe, Sichtzahl) ueber alle Fotos."""
    ws = torch.zeros(len(Q), device=dev); vn = torch.zeros(len(Q), device=dev)
    for j, (f, K, s, h, w) in enumerate(INF):
        lt = Q @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = lt[:, 2]
        uv = (K["f"] * lt[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev)) * s; u = uv[:, 0].round().long(); v = uv[:, 1].round().long(); ok = (z > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
        uc = u.clamp(0, w - 1); vc = v.clamp(0, h - 1); wz = w // 3 + 1; vis = ok & (z <= ZM[j][(vc // 3) * wz + (uc // 3)] + 0.3); d = DT[j][vc // 2, uc // 2].float()
        ws += vis * torch.exp(-(d / TOL) ** 2); vn += vis
    return ws, vn
NS = 48; tt = torch.linspace(0, 1, NS, device=dev)
def seg_score(A, B):
    """A,B (S,3) Endpunkte -> (Anteil gestuetzt je Segment, mittlere Sichtzahl)"""
    Q = (A[:, None] * (1 - tt)[None, :, None] + B[:, None] * tt[None, :, None]).reshape(-1, 3); ws, vn = stuetzung(Q); ws = ws.view(len(A), NS); vn = vn.view(len(A), NS); m = vn >= 3
    return (ws * m).sum(1) / (vn * m).sum(1).clamp(min=1), vn.mean(1)
def abstand_zu_segmenten(X, A, B):
    d = torch.full((len(X),), 9.0, device=dev)
    for c in range(0, len(A), 100):
        a = A[c:c + 100][None]; ab = (B[c:c + 100] - A[c:c + 100])[None]; w = X[:, None] - a; t = ((w * ab).sum(2) / (ab * ab).sum(2).clamp(min=1e-9)).clamp(0, 1); d = torch.minimum(d, (w - t[..., None] * ab).norm(dim=2).min(1).values)
    return d
S = json.load(open(sys.argv[6]))["segmente"]; fix = json.load(open(opt("--fix", "/dev/null", str)))["segmente"] if "--fix" in sys.argv and os.path.exists(opt("--fix", "", str)) else []
A = torch.tensor([s[0] for s in S], device=dev, dtype=torch.float32); B = torch.tensor([s[1] for s in S], device=dev, dtype=torch.float32); NF = torch.zeros(len(A), dtype=torch.bool, device=dev)
if fix: A = torch.cat([A, torch.tensor([s[0] for s in fix], device=dev, dtype=torch.float32)]); B = torch.cat([B, torch.tensor([s[1] for s in fix], device=dev, dtype=torch.float32)]); NF = torch.cat([NF, torch.ones(len(fix), dtype=torch.bool, device=dev)])
hist = []; g = torch.Generator(device=dev).manual_seed(7)
def bericht(it, nm):
    sc, vn = seg_score(A, B); L = (B - A).norm(dim=1); dEP = abstand_zu_segmenten(EP, A, B); rec = float((dEP < 0.03).float().mean()); prec = float((sc * L).sum() / L.sum())
    print("%s: Segmente %d  Laenge %.1f m  Praezision(Foto-Stuetzung, laengengew.) %.3f  Recall(Kantenpunkte<3cm) %.3f" % (nm, len(A), float(L.sum()), prec, rec), flush=True); hist.append(dict(it=it, n=len(A), laenge=float(L.sum()), praez=prec, recall=rec)); return sc, vn
sc, vn = bericht(0, "Start")
for it in range(1, NIT + 1):
    # (2) schwache Segmente loeschen (nur bei ausreichender Sicht, nie Nutzerkorrekturen)
    kill = (sc < MIN) & (vn >= 3) & (~NF); A, B, NF = A[~kill], B[~kill], NF[~kill]; print("  geloescht:", int(kill.sum()), flush=True)
    # (3) Verschieben: Endpunkte zufaellig stoeren, weiche Foto-Stuetzung maximieren
    sig = [0.04, 0.03, 0.02, 0.015, 0.01, 0.01][min(it - 1, 5)]; C = 24; cand = []
    for c in range(C + 1):
        dA = torch.randn_like(A, generator=g) * sig * (c > 0); dB = torch.randn_like(B, generator=g) * sig * (c > 0); cand.append((A + dA, B + dB))
    sc0, _ = seg_score(A, B); best = sc0.clone(); bA, bB = A.clone(), B.clone()
    for (cA, cB) in cand[1:]:
        s_, v_ = seg_score(cA, cB); better = (s_ > best + 0.01) & (~NF) & (v_ >= 3); bA[better] = cA[better]; bB[better] = cB[better]; best = torch.where(better, s_, best)
    print("  verschoben:", int((best > sc0).sum()), flush=True); A, B = bA, bB
    # (4) neue Kandidaten aus unerklaerten Kantenpunkten
    dEP = abstand_zu_segmenten(EP, A, B); R = EP[dEP > 0.04]; neu = ransac_segmente(R, tol=0.015, minlen=0.15, minpts=25, seed=it)
    if neu:
        nA = torch.tensor([s[0] for s in neu], device=dev, dtype=torch.float32); nB = torch.tensor([s[1] for s in neu], device=dev, dtype=torch.float32); s_, v_ = seg_score(nA, nB); keep = (s_ >= MIN) & (v_ >= 3)
        A = torch.cat([A, nA[keep]]); B = torch.cat([B, nB[keep]]); NF = torch.cat([NF, torch.zeros(int(keep.sum()), dtype=torch.bool, device=dev)]); print("  neu:", int(keep.sum()), "von", len(neu), flush=True)
    sc, vn = bericht(it, "Durchgang %d" % it)
    json.dump({"segmente": [[a.tolist(), b.tolist(), 0, float(s_)] for a, b, s_ in zip(A, B, sc)], "historie": hist, "fix": int(NF.sum())}, open(sys.argv[7], "w"))
# Overlay: 3 Fotos mit den meisten sichtbaren Segmentpunkten, Linien gruen (gestuetzt) -> rot (ungestuetzt)
Q = (A[:, None] * (1 - tt)[None, :, None] + B[:, None] * tt[None, :, None]).reshape(-1, 3); cnt = []
for j, (f, K, s, h, w) in enumerate(INF):
    lt = Q @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = lt[:, 2]; uv = (K["f"] * lt[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev)) * s
    ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < w) & (uv[:, 1] >= 0) & (uv[:, 1] < h); cnt.append(int(ok.sum()))
for j in np.argsort(cnt)[::-1][:3]:
    f, K, s, h, w = INF[j]; im = cv2.imread(os.path.join(bd, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); im = cv2.resize(im, (w, h)); lt = Q @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = lt[:, 2]
    uv = ((K["f"] * lt[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev)) * s); u = uv[:, 0].round().long(); v = uv[:, 1].round().long(); ok = (z > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    uc = u.clamp(0, w - 1); vc = v.clamp(0, h - 1); vis = ok & (z <= ZM[j][(vc // 3) * (w // 3 + 1) + (uc // 3)] + 0.3); d = DT[j][vc // 2, uc // 2].float(); uvn = uv.cpu().numpy().reshape(len(A), NS, 2); vv = vis.cpu().numpy().reshape(len(A), NS); dn = d.cpu().numpy().reshape(len(A), NS)
    for i in range(len(A)):
        for k in range(NS - 1):
            if vv[i, k] and vv[i, k + 1]: col = (0, 200, 0) if dn[i, k] <= TOL else (0, 0, 255); cv2.line(im, tuple(np.round(uvn[i, k]).astype(int)), tuple(np.round(uvn[i, k + 1]).astype(int)), col, 3, cv2.LINE_AA)
    cv2.imwrite("%s_%s.jpg" % (sys.argv[8], os.path.splitext(f)[0]), cv2.resize(im, (w // 2, h // 2)))
print("fertig", sys.argv[7])
