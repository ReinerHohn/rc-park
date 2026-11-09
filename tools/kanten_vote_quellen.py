"""Kantenabstimmung mit GETRENNTEN Quellen (SAM-Grenze, Grau-Canny, Farb-Sweep) fuer die Median-Fusion (kanten_fusion.py).
CPU: Kantenbilder je Foto parallel (ProcessPool, Fenster von Fotos im Voraus); GPU: Projektion, Z-Puffer, Zaehlung je Quelle.
Aufruf: python -I tools/kanten_vote_quellen.py KAM.json WOLKE.npy FOTOS.npz MASKEN BILDER OUT.npz [--tol 2] [--nmin 3] [--cpu 6]
Ausgabe: P, vis, kan (n_quellen x N), quellen (Namen)."""
import sys, os, json, collections, numpy as np, cv2, torch, torch.nn.functional as Fn
from concurrent.futures import ProcessPoolExecutor
def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
TOL = opt("--tol", 2, int); NMIN = opt("--nmin", 3, int); NCPU = opt("--cpu", 6, int)
KAM = json.load(open(sys.argv[1])); wolke = sys.argv[2]; fotos = list(np.load(sys.argv[3])["fotos"]); MD = sys.argv[4]; BD = sys.argv[5]; OUT = sys.argv[6]
NAMEN = ["sam", "canny", "sweep"]
def kantenbilder(f):
    cp = os.path.join(MD, os.path.splitext(f)[0] + ".npz")
    if not os.path.exists(cp): return f, None
    lab = np.load(cp)["lab"]; h, w = lab.shape; b = np.zeros((h, w), bool); b[:, :-1] |= lab[:, :-1] != lab[:, 1:]; b[:-1, :] |= lab[:-1, :] != lab[1:, :]
    im = cv2.imread(os.path.join(BD, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION); im = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA)
    gr = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 1.2); can = cv2.Canny(gr, 50, 130) > 0
    lab_ = cv2.cvtColor(im, cv2.COLOR_BGR2LAB); hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); acc = np.zeros((h, w), np.uint8)
    for ch in (lab_[:, :, 0], lab_[:, :, 1], lab_[:, :, 2], hsv[:, :, 1], im[:, :, 1]):
        g = cv2.GaussianBlur(ch, (0, 0), 1.5); mag = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)); t2 = float(np.percentile(mag, 94)); acc += cv2.dilate((cv2.Canny(g, max(t2 * 0.4, 1), max(t2, 2)) > 0).astype(np.uint8), np.ones((3, 3), np.uint8))
    return f, np.stack([b, can, acc >= NMIN])
if __name__ == "__main__":
    dev = "cuda"; P = np.load(wolke)[:, :3].astype(np.float32); Pt = torch.from_numpy(P).to(dev); N = len(P)
    vis_n = torch.zeros(N, dtype=torch.int16, device=dev); kan_n = torch.zeros((len(NAMEN), N), dtype=torch.int16, device=dev)
    with ProcessPoolExecutor(NCPU) as ex:
        fut = collections.deque(); it = iter(fotos); pend = 0
        for _ in range(NCPU + 2):
            f = next(it, None)
            if f is not None: fut.append(ex.submit(kantenbilder, f))
        j = 0
        while fut:
            f, E = fut.popleft().result(); nf = next(it, None)
            if nf is not None: fut.append(ex.submit(kantenbilder, nf))
            if E is None: continue
            K = KAM[f]; h, w = E.shape[1:]; s = w / K["W"]; B = [Fn.max_pool2d(torch.from_numpy(E[i]).to(dev).float()[None, None], 2 * TOL + 1, 1, TOL)[0, 0] > 0 for i in range(len(NAMEN))]
            Xc = Pt @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = Xc[:, 2]
            uv = (K["f"] * Xc[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev)) * s; u = uv[:, 0].round().long(); v = uv[:, 1].round().long(); ok = (z > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
            uc = u.clamp(0, w - 1); vc = v.clamp(0, h - 1); q = 3; hz, wz = h // q + 1, w // q + 1; pz = (vc // q) * wz + (uc // q)
            zb = torch.full((hz * wz,), 1e9, device=dev); zb.scatter_reduce_(0, pz[ok], z[ok], "amin"); zm = -Fn.max_pool2d(-zb.view(1, 1, hz, wz), 9, 1, 4).view(-1); vis = ok & (z <= zm[pz] + 0.3)
            vis_n += vis.short()
            for i in range(len(NAMEN)): kan_n[i] += (vis & B[i][vc, uc]).short()
            j += 1; print("Foto", j, "/", len(fotos), flush=True)
    np.savez_compressed(OUT, P=P, vis=vis_n.cpu().numpy(), kan=kan_n.cpu().numpy(), quellen=np.array(NAMEN))
    v = vis_n.cpu().numpy(); k = kan_n.cpu().numpy(); r = k / np.maximum(v, 1)
    for i, nm in enumerate(NAMEN): print(nm, "Punkte (>=6 Sichten, Anteil>=0.5):", int(((v >= 6) & (r[i] >= 0.5)).sum()))
