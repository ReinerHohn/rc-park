"""3D-Kanten per Mehrfoto-Abstimmung: SAM-Grenzen jedes Fotos (Labelbild aus sam_mehrfoto_3d --kachel) auf die Wolke projizieren,
je Punkt zaehlen: in wie vielen Fotos, die den Punkt SEHEN, liegt er auf einer Maskengrenze. Echte Kanten (Kreten, Fensterrahmen, Bogen) stimmen in vielen
Fotos ueberein, Silhouetten/Verdeckungsgrenzen nur in wenigen. GPU: Projektion, Z-Puffer, Grenzbild, Zaehlung.
Aufruf: python -I tools/kanten_3d_vote.py KAMERAS.json WOLKE.npy FOTOS.npz(key fotos) MASKENDIR OUT.npz [--tol 2]"""
import sys, os, json, numpy as np, torch, cv2, torch.nn.functional as Fn
dev = "cuda"; tol = int(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 2; BD = sys.argv[sys.argv.index("--bilder") + 1] if "--bilder" in sys.argv else None; SWEEP = "--sweep" in sys.argv; NMIN = int(sys.argv[sys.argv.index("--nmin") + 1]) if "--nmin" in sys.argv else 2   # --bilder: zusaetzlich feine Fotokanten (Canny) = Sprossen/Rahmen, die SAM verschmilzt
KAM = json.load(open(sys.argv[1])); P = np.load(sys.argv[2])[:, :3].astype(np.float32); fotos = list(np.load(sys.argv[3])["fotos"]); md = sys.argv[4]; Pt = torch.from_numpy(P).to(dev); N = len(P)
vis_n = torch.zeros(N, dtype=torch.int16, device=dev); kan_n = torch.zeros(N, dtype=torch.int16, device=dev)
for j, f in enumerate(fotos):
    cp = os.path.join(md, os.path.splitext(f)[0] + ".npz")
    if not os.path.exists(cp): continue
    K = KAM[f]; lab = torch.from_numpy(np.load(cp)["lab"]).to(dev); h, w = lab.shape; s = w / K["W"]
    # Grenzbild: Label unterscheidet sich vom Nachbarn (rechts/unten); Rand zu "kein Label" zaehlt auch
    b = torch.zeros((h, w), dtype=torch.bool, device=dev); b[:, :-1] |= lab[:, :-1] != lab[:, 1:]; b[:-1, :] |= lab[:-1, :] != lab[1:, :]
    if BD and SWEEP:                       # Farb-Sweep: Kanten je Farbkanal (Lab L/a/b, HSV S, G), adaptive Schwelle (Perzentil des Gradienten), Median/Mehrheit ueber die Kanaele (>= NMIN stimmen ueberein)
        im = cv2.imread(os.path.join(BD, f), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
        if im is not None:
            im = cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA); lab_ = cv2.cvtColor(im, cv2.COLOR_BGR2LAB); hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); chs = [lab_[:, :, 0], lab_[:, :, 1], lab_[:, :, 2], hsv[:, :, 1], im[:, :, 1]]; acc = np.zeros((h, w), np.uint8)
            for ch in chs:
                g = cv2.GaussianBlur(ch, (0, 0), 1.5); mag = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)); t2 = float(np.percentile(mag, 94)); e = cv2.Canny(g, max(t2 * 0.4, 1), max(t2, 2)) > 0
                acc += cv2.dilate(e.astype(np.uint8), np.ones((3, 3), np.uint8))
            b |= torch.from_numpy(acc >= NMIN).to(dev)
    elif BD:
        im = cv2.imread(os.path.join(BD, f), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)
        if im is not None: im = cv2.GaussianBlur(cv2.resize(im, (w, h), interpolation=cv2.INTER_AREA), (0, 0), 1.2); b |= torch.from_numpy(cv2.Canny(im, 50, 130) > 0).to(dev)
    b = Fn.max_pool2d(b.float()[None, None], 2 * tol + 1, 1, tol)[0, 0] > 0; del lab
    Xc = Pt @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = Xc[:, 2]
    uv = (K["f"] * Xc[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev)) * s; u = uv[:, 0].round().long(); v = uv[:, 1].round().long()
    ok = (z > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h); q = 3; hz, wz = h // q + 1, w // q + 1; uc = u.clamp(0, w - 1); vc = v.clamp(0, h - 1); pz = (vc // q) * wz + (uc // q)
    zb = torch.full((hz * wz,), 1e9, device=dev); zb.scatter_reduce_(0, pz[ok], z[ok], "amin"); zm = -Fn.max_pool2d(-zb.view(1, 1, hz, wz), 9, 1, 4).view(-1)
    vis = ok & (z <= zm[pz] + 0.3); vis_n += vis.short(); kan_n += (vis & b[vc, uc]).short(); del b, zb, zm
    if j % 10 == 0: print("Foto", j + 1, "/", len(fotos), flush=True)
np.savez_compressed(sys.argv[5], P=P, vis=vis_n.cpu().numpy(), kan=kan_n.cpu().numpy())
v = vis_n.cpu().numpy(); k = kan_n.cpu().numpy(); r = k / np.maximum(v, 1); print("Punkte mit >=4 Sichten:", int((v >= 4).sum()), "Anteil Kante>=0.5:", int(((r >= 0.5) & (v >= 4)).sum()))
