#!/usr/bin/env python3
"""generator_ausrichten3.py - BS51c: Generator->Wolke Ausrichtung auf GPU: Wolken-Distanzfeld (EDT, 5 cm), 1,5 Mio Kandidaten (Gieren/u/w/z) per grid_sample parallel,
Top-k per Adam (6 Freiheitsgrade: Yaw, Kippen klein, Verschiebung) verfeinert. Verlust = Mittel(min(d, 0.4 m)); Score = Anteil < 0.15 m.
  venv-seg/bin/python -I tools/generator_ausrichten3.py glb wolke.npy aus.json [--aus-stl x.stl]"""
import json, argparse, time, numpy as np, trimesh, torch
from scipy.ndimage import distance_transform_edt
ap = argparse.ArgumentParser(); ap.add_argument("glb"); ap.add_argument("wolke"); ap.add_argument("aus"); ap.add_argument("--aus-stl"); ap.add_argument("--zelle", type=float, default=0.05)
ap.add_argument("--nur", default="fassade,boegen,piers,fenster,erker,rahmen,balkon,galerie,waende,giebel,gauben,gauben_rahmen"); ap.add_argument("--clip", type=float, default=0.4)
a = ap.parse_args(); dev = "cuda"; t0 = time.time()
sc = trimesh.load(a.glb); G = trimesh.util.concatenate([sc.geometry[n] for n in a.nur.split(",") if n in sc.geometry]); P = trimesh.sample.sample_surface(G, 60000)[0]
X = np.load(a.wolke).astype(np.float64); b = np.array([-14.6, 2.7, 0.6, 15.7, 17.0, 19.9]); lo = b[:3] - 3; hi = b[3:] + 3; X = X[np.all((X >= lo) & (X <= hi), 1)]
n3 = np.ceil((hi - lo) / a.zelle).astype(int); occ = np.ones(n3, bool); ij = np.floor((X - lo) / a.zelle).astype(int); occ[ij[:, 0], ij[:, 1], ij[:, 2]] = False
D = distance_transform_edt(occ, sampling=a.zelle).astype(np.float32); print("Distanzfeld", D.shape, "in", round(time.time() - t0), "s", flush=True)
Dt = torch.from_numpy(D).to(dev)[None, None]          # (1,1,X,Y,Z)
lo_t = torch.tensor(lo, dtype=torch.float32, device=dev); sz_t = torch.tensor((n3 * a.zelle), dtype=torch.float32, device=dev)
def dist(Q):                                          # Q (...,3) Meter -> Abstand
    g = (Q - lo_t) / sz_t * 2 - 1; g = g[..., [2, 1, 0]]; s = g.shape[:-1]
    return torch.nn.functional.grid_sample(Dt, g.reshape(1, 1, 1, -1, 3), align_corners=True, padding_mode="border").reshape(s)
Pt = torch.from_numpy(P).float().to(dev); pc = Pt.mean(0); Pn = Pt - pc; c0 = torch.tensor(X[X[:, 2] > 2].mean(0), dtype=torch.float32, device=dev)
n = np.array([0.344, 0.939, 0.0]); az = np.arctan2(n[1], n[0])
def Rz(t): c, s = torch.cos(t), torch.sin(t); z = torch.zeros_like(t); o = torch.ones_like(t); return torch.stack([torch.stack([c, -s, z], -1), torch.stack([s, c, z], -1), torch.stack([z, z, o], -1)], -2)
Pn0 = Pn.clone()
def verlust(yaw, tr, N=6000):
    Q = Pn[:N] @ Rz(yaw).transpose(-1, -2) + c0 + tr[..., None, :]; d = dist(Q); return torch.clamp(d, max=a.clip).mean(-1), (d < 0.15).float().mean(-1)
best = []
varianten = [(mi, 1.0) for mi in (1.0, -1.0)]   # Skala 1 fest: einseitiger Verlust (Generator->Wolke) schrumpft sonst den Generator in die Wolkenmasse (BS51c)
for mi, sk in varianten:
  Pn = Pn0 * torch.tensor([mi * sk, sk, sk], device=dev)
  for flip in (0.0, np.pi):
      yaws = torch.tensor(az + np.pi / 2 + flip + np.deg2rad(np.arange(-10, 10.1, 1.0)), dtype=torch.float32, device=dev)
      u = torch.arange(-8, 8.01, 0.25, device=dev); w = torch.arange(-5, 5.01, 0.25, device=dev); z = torch.arange(-2, 2.01, 0.25, device=dev)
      nu = torch.tensor([-n[1], n[0], 0], dtype=torch.float32, device=dev); nn_ = torch.tensor(n, dtype=torch.float32, device=dev); nz = torch.tensor([0, 0, 1.0], device=dev)
      T = (u[:, None, None, None] * nu + w[None, :, None, None] * nn_ + z[None, None, :, None] * nz).reshape(-1, 3)
      for yw in yaws:
          L = torch.cat([verlust(yw.expand(len(T[i:i + 4000])), T[i:i + 4000], 3000)[0] for i in range(0, len(T), 4000)])
          k = torch.topk(-L, 3).indices
          for q in k: best.append((float(L[q]), float(yw), T[q].cpu().numpy(), mi, sk))
      print("Spiegel", mi, "Skala", sk, "flip", round(flip, 2), "Kandidaten geprueft", len(yaws) * len(T), "in", round(time.time() - t0), "s", flush=True)
best.sort(key=lambda x: x[0]); top = best[:12]; res = []
Xt = torch.from_numpy(X[np.random.default_rng(1).choice(len(X), 6000, replace=False)]).float().to(dev)
for L0, yw, tr, mi, sk in top:
    yaw = torch.tensor([yw], device=dev, requires_grad=True); trv = torch.tensor(tr[None], device=dev, requires_grad=True); ls = torch.zeros(1, device=dev, requires_grad=True); opt = torch.optim.Adam([yaw, trv, ls], lr=0.01)
    sel = torch.randperm(len(Pt), device=dev)[:8000]; Pm = Pt[sel] - pc
    for it in range(400):
        opt.zero_grad(); S = torch.exp(ls); M = torch.tensor([mi, 1.0, 1.0], device=dev) * S
        Q = (Pm * M) @ Rz(yaw)[0].T + c0 + trv[0]; fw = torch.clamp(dist(Q), max=a.clip).mean()
        dm = torch.cdist(Xt, Q).min(1).values; rv = torch.clamp(dm, max=a.clip).mean()          # Rueckrichtung: Wolke -> Generator
        (fw + rv + 0.5 * ls ** 2 / 0.05 ** 2 * 0.01).backward(); opt.step()
    Pn = Pn0 * torch.tensor([mi, 1.0, 1.0], device=dev) * torch.exp(ls.detach()); l, sco = verlust(yaw.detach(), trv.detach(), 60000)
    res.append((float(fw + rv), float(sco), float(yaw), trv.detach()[0].cpu().numpy(), mi, float(torch.exp(ls))))
    print("verfeinert (Spiegel %g Skala %.3f): Chamfer %.4f Score(<0.15 m) %.3f" % (mi, res[-1][5], res[-1][0], res[-1][1]), flush=True)
L1, s1, yw, tr, mi, sk = min(res, key=lambda r: r[0]); print('Variante Spiegel', mi, 'Skala', sk); M = np.diag([mi * sk, sk, sk]); R = Rz(torch.tensor([yw])).numpy()[0] @ M; t = c0.cpu().numpy() + tr - R @ pc.cpu().numpy()
Pw = P @ R.T + t; d = dist(torch.from_numpy(Pw).float().to(dev)).cpu().numpy()
print("ERGEBNIS Score <0.15 m %.3f | Abstand Median %.2f m P75 %.2f P90 %.2f | <0.3 m %.0f%% <0.6 m %.0f%% | yaw %.2f deg" % (s1, *np.percentile(d, [50, 75, 90]), 100 * (d < .3).mean(), 100 * (d < .6).mean(), np.rad2deg(yw)))
T4 = np.eye(4); T4[:3, :3] = R; T4[:3, 3] = t; json.dump(dict(T=T4.tolist(), score=s1, verlust=L1), open(a.aus, "w"), indent=1)
if a.aus_stl:
    full = trimesh.util.concatenate(list(sc.geometry.values())); full.apply_transform(T4); full.vertices = full.vertices / 0.087; full.export(a.aus_stl); print("STL", a.aus_stl, len(full.faces), "gesamt", round(time.time() - t0), "s")
