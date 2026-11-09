"""Netz-Zuschnitt per SAM-Masken-Abstimmung (robuster als Umrisslinien): je Dreieck (Schwerpunkt) in jedem Foto prufen, ob es innerhalb der SAM-Maske SEINES Objekts liegt (nur wo es sichtbar ist: Z-Puffer aller Schwerpunkte).
Dreieck bleibt bei >= anteil der Sichtfotos (mind. 2). GPU. Aufruf: python -I tools/objekte_zuschnitt.py ERG.npz MASKENDIR KAMERAS.json FLAECHEN.npz OUT.npz [--anteil 0.6]"""
import argparse, json, os, time, numpy as np, torch, torch.nn.functional as Fn
ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("ein", "masken", "kameras", "flaechen", "aus")]; ap.add_argument("--anteil", type=float, default=0.6); ap.add_argument("--minsicht", type=int, default=2); ap.add_argument("--tol", type=float, default=0.15); a = ap.parse_args()
dev = "cuda"; z = np.load(a.ein); fotos = [str(f) for f in z["fotos"]]; lut = torch.from_numpy(z["lut"]).to(dev); MAXM = int(z["maxm"]); cids = z["cluster_ids"]; KAM = json.load(open(a.kameras)); FL = np.load(a.flaechen)
V = FL["V"]; F = FL["F"]; ntri = FL["ntri"]; idsF = FL["ids"]; off = np.r_[0, np.cumsum(ntri)]; oid = np.zeros(len(F), np.int64)
for k in range(len(idsF)): oid[off[k]:off[k + 1]] = k
cen = torch.from_numpy(V[F].mean(1).astype(np.float32)).to(dev); ctri = torch.from_numpy(cids[idsF][oid]).to(dev).long(); nT = len(F); vin = torch.zeros(nT, device=dev); vse = torch.zeros(nT, device=dev); t0 = time.time()
for j, f in enumerate(fotos):
    cp = os.path.join(a.masken, os.path.splitext(f)[0] + ".npz")
    if not os.path.exists(cp): continue
    lab = np.load(cp)["lab"]; h, w = lab.shape; K = KAM[f]; s = w / K["W"]; R = torch.tensor(K["Rn"], device=dev, dtype=torch.float32); T = torch.tensor(K["tn"], device=dev, dtype=torch.float32); c0 = torch.tensor([K["cx"], K["cy"]], device=dev)
    Xc = cen @ R.T + T; zc = Xc[:, 2]; uv = (K["f"] * Xc[:, :2] / zc.clamp(min=0.5)[:, None] + c0) * s; u = uv[:, 0].round().long(); v = uv[:, 1].round().long(); ok = (zc > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    q = 3; hz, wz = h // q + 1, w // q + 1; zb = torch.full((hz * wz,), 1e9, device=dev); pz = (v.clamp(0, h - 1) // q) * wz + (u.clamp(0, w - 1) // q); zb.scatter_reduce_(0, pz[ok], zc[ok], "amin"); zm = -Fn.max_pool2d(-zb.view(1, 1, hz, wz), 5, 1, 2).view(-1)
    vis = ok & (zc <= zm[pz] + a.tol); lt = torch.from_numpy(lab).to(dev).long(); CL = lut[j * MAXM + lt.clamp(min=0)].long(); CL[lt < 0] = -1; lb = CL.view(-1)[v.clamp(0, h - 1) * w + u.clamp(0, w - 1)]
    seg = vis & (lb >= 0)                                                                               # Foto hat an dieser Stelle ueberhaupt eine Maske (sonst keine Aussage)
    vse += seg.float(); vin += (seg & (lb == ctri)).float(); del lt, CL, zb
    if j % 10 == 0: print("Foto %d/%d %.0fs" % (j + 1, len(fotos), time.time() - t0), flush=True)
keep = ((vse >= a.minsicht) & (vin >= a.anteil * vse)).cpu().numpy(); print("Dreiecke behalten", int(keep.sum()), "von", nT)
V2, F2, M2, nv = [], [], [], 0
for k in range(len(idsF)):
    m = keep[off[k]:off[k + 1]]
    if m.sum() < 10: continue
    t = F[off[k]:off[k + 1]][m]; uq, inv = np.unique(t, return_inverse=True); V2.append(V[uq]); F2.append(inv.reshape(-1, 3).astype(np.int32) + nv); nv += len(uq); M2.append((int(idsF[k]), int(FL["npts"][k]), int(m.sum()), FL["farbe"][k]))
np.savez_compressed(a.aus, V=np.vstack(V2), F=np.vstack(F2), ids=np.array([x[0] for x in M2]), npts=np.array([x[1] for x in M2]), ntri=np.array([x[2] for x in M2]), farbe=np.array([x[3] for x in M2]).astype(np.uint8))
print("Objekte", len(M2), "Dreiecke", int(sum(x[2] for x in M2)), "%.0fs" % (time.time() - t0))
