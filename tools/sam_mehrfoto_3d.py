"""3D-Objekte aus der Wolke per SAM auf vielen kalibrierten Fotos (Nutzer 9.11.: 'das reale 3D-Objekt so wie es die Wolke darstellt').
Je Foto SAM-Masken (grob->fein, kleinere ueberschreiben), jeder sichtbare Wolkenpunkt (GPU-Tiefenpuffer gegen Verdeckung) bekommt die Masken-Nummer;
Masken verschiedener Fotos mit grosser gemeinsamer Punktmenge (IoU) werden vereint (Union-Find); je Punkt Mehrheitsentscheid der Objekt-Nummer. Ausgabe: npz mit Objekt je Punkt.
Aufruf: python -I tools/sam_mehrfoto_3d.py --kameras K.json --bilder DIR --wolke W.npy --ausgabe out.npz [--nfotos 80]"""
import argparse, json, os, sys, time, numpy as np, torch, cv2
import torch.nn.functional as Fn
ap = argparse.ArgumentParser(); ap.add_argument("--kameras", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--wolke", required=True); ap.add_argument("--ausgabe", required=True)
ap.add_argument("--nfotos", type=int, default=80); ap.add_argument("--iou", type=float, default=0.3); ap.add_argument("--minpts", type=int, default=150); ap.add_argument("--cache", default=None); ap.add_argument("--kachel", type=int, default=0, help="Kachelkantenlaenge in Originalpixeln (0 = Ganzbild 1024)"); ap.add_argument("--ppc", type=int, default=24); a = ap.parse_args()
os.environ.setdefault("HF_HOME", "/media/oem/scan/tools_src/hf_cache"); dev = "cuda"
KAM = json.load(open(a.kameras)); P = np.load(a.wolke)[:, :3].astype(np.float32); N = len(P); RGB = np.load(os.path.join(os.path.dirname(a.wolke), "j_crop_rgb2.npy")) if os.path.exists(os.path.join(os.path.dirname(a.wolke), "j_crop_rgb2.npy")) else None
Pt = torch.from_numpy(P).to(dev); cache = a.cache or os.path.splitext(a.ausgabe)[0] + "_masken"; os.makedirs(cache, exist_ok=True); SL = 1024
def projekt(K, s):
    Xc = Pt @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = Xc[:, 2]
    uv = (K["f"] * Xc[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev)) * s; return uv, z
# Fotoauswahl: viele Punkte im Bild, dann Kameras moeglichst verschieden (weitester Punkt)
sc = []
for f, K in KAM.items():
    s = SL / max(K["W"], K["H"]); uv, z = projekt(K, s); w, h = K["W"] * s, K["H"] * s; ok = (z > 1) & (uv[:, 0] >= 0) & (uv[:, 0] < w) & (uv[:, 1] >= 0) & (uv[:, 1] < h); sc.append((int(ok.sum()), f))
sc.sort(reverse=True); cand = [f for n, f in sc[:200] if n > 0.15 * N]; C = np.array([KAM[f]["C"] for f in cand]); Dd = np.array([np.array(KAM[f]["Rn"])[2] for f in cand])
feat = np.hstack([C / 10.0, Dd * 2.0]); sel = [0]; dm = np.linalg.norm(feat - feat[0], axis=1)
while len(sel) < min(a.nfotos, len(cand)): j = int(np.argmax(dm)); sel.append(j); dm = np.minimum(dm, np.linalg.norm(feat - feat[j], axis=1))
fotos = [cand[i] for i in sel]; print("Fotos:", len(fotos), "von", len(KAM), flush=True)
from transformers import pipeline
gen = pipeline("mask-generation", model="facebook/sam-vit-large", device=0)
J = len(fotos); L = torch.full((N, J), -1, dtype=torch.int32, device=dev); MAXM = 20000; t0 = time.time()
for j, f in enumerate(fotos):
    K = KAM[f]; cp = os.path.join(cache, os.path.splitext(f)[0] + (".npz" if a.kachel else ".npy"))
    if a.kachel:
        if os.path.exists(cp): lab = np.load(cp)["lab"]
        else:
            im = cv2.imread(os.path.join(a.bilder, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
            if im is None: continue
            from PIL import Image
            h, w = im.shape[:2]; MS = []                                                    # Masken als (x0,y0,bool-Ausschnitt) im Originalmass
            sk = SL / max(w, h); ims = cv2.resize(im, (int(round(w * sk)), int(round(h * sk))), interpolation=cv2.INTER_AREA)
            r = gen(Image.fromarray(ims[:, :, ::-1]), points_per_batch=32, pred_iou_thresh=0.86, stability_score_thresh=0.9)
            for m in r["masks"]:
                m = np.asarray(m.cpu() if hasattr(m, "cpu") else m).astype(np.uint8); yy, xx = np.where(m)
                if len(yy) < 40: continue
                x0, x1, y0, y1 = int(xx.min() / sk), min(int(xx.max() / sk) + 2, w), int(yy.min() / sk), min(int(yy.max() / sk) + 2, h)
                cr = cv2.resize(m[int(y0 * sk):int(y1 * sk) + 1, int(x0 * sk):int(x1 * sk) + 1], (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST).astype(bool)
                if cr.sum() > 400 and cr.sum() < 0.4 * w * h: MS.append((x0, y0, cr))
            tk = a.kachel; st = int(tk * 0.7)
            for y0 in sorted(set(list(range(0, max(h - tk, 0) + 1, st)) + [max(h - tk, 0)])):
                for x0 in sorted(set(list(range(0, max(w - tk, 0) + 1, st)) + [max(w - tk, 0)])):
                    tile = im[y0:y0 + tk, x0:x0 + tk]; th, tw = tile.shape[:2]
                    r = gen(Image.fromarray(tile[:, :, ::-1]), points_per_batch=16, points_per_crop=a.ppc, pred_iou_thresh=0.86, stability_score_thresh=0.9)
                    for m in r["masks"]:
                        m = np.asarray(m.cpu() if hasattr(m, "cpu") else m).astype(bool); yy, xx = np.where(m)
                        if len(yy) < 400: continue
                        if (x0 > 0 and xx.min() <= 1) or (y0 > 0 and yy.min() <= 1) or (x0 + tk < w and xx.max() >= tw - 2) or (y0 + tk < h and yy.max() >= th - 2): continue     # am Kachelrand abgeschnitten
                        if len(yy) > 0.4 * w * h: continue
                        MS.append((x0 + int(xx.min()), y0 + int(yy.min()), m[yy.min():yy.max() + 1, xx.min():xx.max() + 1]))
                    torch.cuda.empty_cache()
            MS.sort(key=lambda t: -int(t[2].sum())); lab = np.full((h, w), -1, np.int32)
            for i, (x0, y0, m) in enumerate(MS[:MAXM - 1]): lab[y0:y0 + m.shape[0], x0:x0 + m.shape[1]][m] = i
            np.savez_compressed(cp, lab=lab); torch.cuda.empty_cache()
        h, w = lab.shape; s = w / K["W"]
    else:
        s = SL / max(K["W"], K["H"]); w, h = int(round(K["W"] * s)), int(round(K["H"] * s))
        if os.path.exists(cp): lab = np.load(cp)
        else:
            im = cv2.imread(os.path.join(a.bilder, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
            if im is None: continue
            im = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA); from PIL import Image
            r = gen(Image.fromarray(im[:, :, ::-1]), points_per_batch=64, pred_iou_thresh=0.86, stability_score_thresh=0.9)
            ms = [np.asarray(m.cpu() if hasattr(m, "cpu") else m).astype(bool) for m in r["masks"]]; ms = [m for m in ms if 300 < m.sum() < 0.4 * w * h]; ms.sort(key=lambda m: -m.sum())
            lab = np.full((h, w), -1, np.int32)
            for i, m in enumerate(ms[:MAXM - 1]): lab[m] = i
            np.save(cp, lab); torch.cuda.empty_cache()
    lt = torch.from_numpy(lab).to(dev); uv, z = projekt(K, s); u = uv[:, 0].round().long(); v = uv[:, 1].round().long(); ok = (z > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    q = 3 if a.kachel else 1; hz, wz = h // q + 1, w // q + 1; pz = (v.clamp(0, h - 1) // q) * wz + (u.clamp(0, w - 1) // q); pix = v.clamp(0, h - 1) * w + u.clamp(0, w - 1)
    zb = torch.full((hz * wz,), 1e9, device=dev); zb.scatter_reduce_(0, pz[ok], z[ok], "amin"); zm = -Fn.max_pool2d(-zb.view(1, 1, hz, wz), 9, 1, 4).view(-1)
    vis = ok & (z <= zm[pz] + 0.3); lb = lt.view(-1)[pix]; good = vis & (lb >= 0); L[good, j] = (j * MAXM + lb[good]).int(); del lt, zb, zm
    print("Foto %d/%d %s Masken %d sichtbare Punkte mit Maske %d  %.0fs" % (j + 1, J, f, int(lab.max()) + 1, int(good.sum()), time.time() - t0), flush=True)
del gen; torch.cuda.empty_cache()
# Kanten zwischen Masken verschiedener Fotos: IoU der Punktmengen
size = {}; 
for j in range(J):
    u_, c_ = torch.unique(L[:, j][L[:, j] >= 0], return_counts=True)
    for k, c in zip(u_.tolist(), c_.tolist()): size[k] = c
par = {k: k for k in size}
def find(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
ne = 0
for i in range(J):
    Li = L[:, i]
    for j in range(i + 1, J):
        Lj = L[:, j]; m = (Li >= 0) & (Lj >= 0)
        if int(m.sum()) < 100: continue
        key = Li[m].long() * (J * MAXM + 1) + Lj[m].long(); u_, c_ = torch.unique(key, return_counts=True); ki = (u_ // (J * MAXM + 1)).tolist(); kj = (u_ % (J * MAXM + 1)).tolist()
        for x, y, c in zip(ki, kj, c_.tolist()):
            if c >= 40 and c / (size[x] + size[y] - c) >= a.iou:
                rx, ry = find(x), find(y)
                if rx != ry: par[rx] = ry; ne += 1
    print("Paare Foto %d/%d  Vereinigungen %d" % (i + 1, J, ne), flush=True)
roots = {}; cid = {}
for k in size: r = find(k); cid[k] = roots.setdefault(r, len(roots))
lut = torch.full((J * MAXM + 1,), -1, dtype=torch.int32, device=dev)
for k, c in cid.items(): lut[k] = c
Cl = torch.empty_like(L)
for c0 in range(0, J, 16): blk = L[:, c0:c0 + 16]; cb = lut[blk.long().clamp(min=0)]; cb[blk < 0] = -1; Cl[:, c0:c0 + 16] = cb; del cb
neg = -(torch.arange(J, device=dev, dtype=torch.int32) + 2)[None, :]; Cl = torch.where(Cl < 0, neg.expand_as(Cl), Cl)
mode = torch.mode(Cl, dim=1).values; cnt = (Cl == mode[:, None]).sum(1); obj = torch.where((mode >= 0) & (cnt >= 2), mode, torch.full_like(mode, -1))
ids, cts = torch.unique(obj[obj >= 0], return_counts=True); keep = ids[cts >= a.minpts]; ok = torch.isin(obj, keep); obj = torch.where(ok, obj, torch.full_like(obj, -1))
ob = obj.cpu().numpy(); ids = np.unique(ob[ob >= 0]); rem = {int(o): i for i, o in enumerate(ids)}; ob2 = np.array([rem.get(int(o), -1) for o in ob], np.int32)
np.savez_compressed(a.ausgabe, P=P, obj=ob2, rgb=RGB if RGB is not None else np.zeros((N, 3), np.uint8), cnt=cnt.cpu().numpy().astype(np.int16), fotos=np.array(fotos))
print("FERTIG Objekte %d, Punkte mit Objekt %d von %d, %.0fs" % (len(ids), int((ob2 >= 0).sum()), N, time.time() - t0), flush=True)
