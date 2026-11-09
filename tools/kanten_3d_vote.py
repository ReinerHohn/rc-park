"""3D-Kanten per Mehrfoto-Abstimmung: SAM-Grenzen jedes Fotos (Labelbild aus sam_mehrfoto_3d --kachel) auf die Wolke projizieren,
je Punkt zaehlen: in wie vielen Fotos, die den Punkt SEHEN, liegt er auf einer Maskengrenze. Echte Kanten (Kreten, Fensterrahmen, Bogen) stimmen in vielen
Fotos ueberein, Silhouetten/Verdeckungsgrenzen nur in wenigen. GPU: Projektion, Z-Puffer, Grenzbild, Zaehlung.
Aufruf: python -I tools/kanten_3d_vote.py KAMERAS.json WOLKE.npy FOTOS.npz(key fotos) MASKENDIR OUT.npz [--tol 2]"""
import sys, os, json, numpy as np, torch, torch.nn.functional as Fn
dev = "cuda"; tol = int(sys.argv[sys.argv.index("--tol") + 1]) if "--tol" in sys.argv else 2
KAM = json.load(open(sys.argv[1])); P = np.load(sys.argv[2])[:, :3].astype(np.float32); fotos = list(np.load(sys.argv[3])["fotos"]); md = sys.argv[4]; Pt = torch.from_numpy(P).to(dev); N = len(P)
vis_n = torch.zeros(N, dtype=torch.int16, device=dev); kan_n = torch.zeros(N, dtype=torch.int16, device=dev)
for j, f in enumerate(fotos):
    cp = os.path.join(md, os.path.splitext(f)[0] + ".npz")
    if not os.path.exists(cp): continue
    K = KAM[f]; lab = torch.from_numpy(np.load(cp)["lab"]).to(dev); h, w = lab.shape; s = w / K["W"]
    # Grenzbild: Label unterscheidet sich vom Nachbarn (rechts/unten); Rand zu "kein Label" zaehlt auch
    b = torch.zeros((h, w), dtype=torch.bool, device=dev); b[:, :-1] |= lab[:, :-1] != lab[:, 1:]; b[:-1, :] |= lab[:-1, :] != lab[1:, :]
    b = Fn.max_pool2d(b.float()[None, None], 2 * tol + 1, 1, tol)[0, 0] > 0; del lab
    Xc = Pt @ torch.tensor(K["Rn"], device=dev, dtype=torch.float32).T + torch.tensor(K["tn"], device=dev, dtype=torch.float32); z = Xc[:, 2]
    uv = (K["f"] * Xc[:, :2] / z.clamp(min=0.5)[:, None] + torch.tensor([K["cx"], K["cy"]], device=dev)) * s; u = uv[:, 0].round().long(); v = uv[:, 1].round().long()
    ok = (z > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h); q = 3; hz, wz = h // q + 1, w // q + 1; uc = u.clamp(0, w - 1); vc = v.clamp(0, h - 1); pz = (vc // q) * wz + (uc // q)
    zb = torch.full((hz * wz,), 1e9, device=dev); zb.scatter_reduce_(0, pz[ok], z[ok], "amin"); zm = -Fn.max_pool2d(-zb.view(1, 1, hz, wz), 9, 1, 4).view(-1)
    vis = ok & (z <= zm[pz] + 0.3); vis_n += vis.short(); kan_n += (vis & b[vc, uc]).short(); del b, zb, zm
    if j % 10 == 0: print("Foto", j + 1, "/", len(fotos), flush=True)
np.savez_compressed(sys.argv[5], P=P, vis=vis_n.cpu().numpy(), kan=kan_n.cpu().numpy())
v = vis_n.cpu().numpy(); k = kan_n.cpu().numpy(); r = k / np.maximum(v, 1); print("Punkte mit >=4 Sichten:", int((v >= 4).sum()), "Anteil Kante>=0.5:", int(((r >= 0.5) & (v >= 4)).sum()))
