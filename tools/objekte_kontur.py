"""Scharfe Objektkanten aus den SAM-Konturen aller Fotos (Nutzer 9.11.: Kanten im Foto erkennen, auf die Oberflaeche umrechnen, ueber viele Fotos abstimmen).
Je Foto und Objekt: Masken-Kontur in Originalaufloesung, Tiefe aus den Objektpunkten (Z-Puffer, dilatiert), verdeckte Konturpixel (anderes Objekt davor) verworfen -> 3D-Konturpunkte.
Je Objekt Abstimmung in der Fassadenprojektion (u,z, Raster 1,5 cm) -> Umriss (Loecher erhalten, gerade Stuecke), Netz (objekte_flaechen.py) wird daran zugeschnitten.
Aufruf: python -I tools/objekte_kontur.py ERG.npz MASKENDIR KAMERAS.json OBJEKT.json FLAECHEN.npz OUT.npz [--stimmen 2]"""
import argparse, json, os, time, numpy as np, torch, cv2, torch.nn.functional as Fn
ap = argparse.ArgumentParser(); [ap.add_argument(x) for x in ("ein", "masken", "kameras", "objekt", "flaechen", "aus")]; ap.add_argument("--stimmen", type=int, default=2); ap.add_argument("--zelle", type=float, default=0.015); a = ap.parse_args()
dev = "cuda"; z = np.load(a.ein); P = z["P"]; ob = z["obj"]; fotos = [str(f) for f in z["fotos"]]; lut = torch.from_numpy(z["lut"]).to(dev); MAXM = int(z["maxm"]); cids = z["cluster_ids"]
KAM = json.load(open(a.kameras)); O = json.load(open(a.objekt)); n_ = np.array(O["fassade_n"]["wert"], float)[:2]; n_ /= np.linalg.norm(n_); U_ = np.array([n_[1], -n_[0]])
FL = np.load(a.flaechen); sel = [int(i) for i in FL["ids"]]; Pt = torch.from_numpy(P.astype(np.float32)).to(dev); obt = torch.from_numpy(ob).to(dev); PTS = {o: [] for o in sel}; t0 = time.time()
for j, f in enumerate(fotos):
    cp = os.path.join(a.masken, os.path.splitext(f)[0] + ".npz")
    if not os.path.exists(cp): continue
    lab = np.load(cp)["lab"]; h, w = lab.shape; K = KAM[f]; s = w / K["W"]; R = torch.tensor(K["Rn"], device=dev, dtype=torch.float32); T = torch.tensor(K["tn"], device=dev, dtype=torch.float32); c0 = torch.tensor([K["cx"], K["cy"]], device=dev)
    Xc = Pt @ R.T + T; zc = Xc[:, 2]; uv = (K["f"] * Xc[:, :2] / zc.clamp(min=0.5)[:, None] + c0) * s; u = uv[:, 0].round().long(); v = uv[:, 1].round().long(); ok = (zc > 1) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    q = 3; hz, wz = h // q + 1, w // q + 1; zb = torch.full((hz * wz,), 1e9, device=dev); zb.scatter_reduce_(0, (v[ok] // q) * wz + (u[ok] // q), zc[ok], "amin"); zall = -Fn.max_pool2d(-zb.view(1, 1, hz, wz), 9, 1, 4)[0, 0]   # nahester Punkt je Pixel (alle Objekte)
    lt = torch.from_numpy(lab).to(dev).long(); CL = lut[j * MAXM + lt.clamp(min=0)].long(); CL[lt < 0] = -1
    for o in sel:
        c = int(cids[o]); idx = torch.nonzero((obt == o) & ok).squeeze(1)
        if len(idx) < 50: continue
        uo, vo, zo = u[idx], v[idx], zc[idx]; x0, x1, y0, y1 = int(uo.min()) - 25, int(uo.max()) + 26, int(vo.min()) - 25, int(vo.max()) + 26; x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, w), min(y1, h)
        if x1 - x0 < 8 or y1 - y0 < 8 or (x1 - x0) * (y1 - y0) > 4e7: continue
        m = (CL[y0:y1, x0:x1] == c)
        if int(m.sum()) < 300: continue
        dz = torch.full(((y1 - y0) * (x1 - x0),), 1e9, device=dev); dz.scatter_reduce_(0, (vo - y0) * (x1 - x0) + (uo - x0), zo, "amin"); dz = -Fn.max_pool2d(-dz.view(1, 1, y1 - y0, x1 - x0), 21, 1, 10)[0, 0]    # Tiefe der Objektpunkte, auf Nachbarpixel ausgedehnt
        mk = m.cpu().numpy().astype(np.uint8); cs, _ = cv2.findContours(mk, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        if not cs: continue
        pts = np.vstack([c_[:, 0, :] for c_ in cs if len(c_) >= 8]);
        if len(pts) == 0: continue
        px_ = torch.from_numpy(pts[:, 0]).to(dev); py_ = torch.from_numpy(pts[:, 1]).to(dev); d = dz[py_, px_]; good = d < 1e8
        gx, gy = px_[good] + x0, py_[good] + y0; d = d[good]; occ = zall[(gy // q).clamp(0, hz - 1), (gx // q).clamp(0, wz - 1)]; keep = occ >= d - 0.25                          # verdeckt: anderes Objekt deutlich davor
        gx, gy, d = gx[keep], gy[keep], d[keep]
        if len(d) < 20: continue
        pc = torch.stack([(gx.float() / s - K["cx"]) / K["f"] * d, (gy.float() / s - K["cy"]) / K["f"] * d, d], 1) if False else torch.stack([((gx.float() + 0.0) / s - K["cx"]) / K["f"] * d, ((gy.float() + 0.0) / s - K["cy"]) / K["f"] * d, d], 1)
        # Pixel (gx,gy) liegen im skalierten Bild (s) -> zurueck in Kameramass: uv_kam = pix / s
        pc = torch.stack([((gx.float() / s) - K["cx"]) / K["f"] * d, ((gy.float() / s) - K["cy"]) / K["f"] * d, d], 1)
        X = ((pc - T) @ R).cpu().numpy(); PTS[o].append(np.c_[X[:, :2] @ U_, X[:, 2]].astype(np.float32))
    torch.cuda.empty_cache()
    if j % 10 == 0: print("Foto %d/%d %.0fs" % (j + 1, len(fotos), time.time() - t0), flush=True)
# Abstimmung + Umriss + Zuschnitt
V = FL["V"]; F = FL["F"]; off = np.r_[0, np.cumsum(FL["ntri"])]; V2 = []; F2 = []; M2 = []; nv = 0; OUT = {}; rb = a.zelle
for k, o in enumerate(sel):
    if not PTS[o]: continue
    Q = np.vstack(PTS[o]); lo = Q.min(0) - 5 * rb; hi = Q.max(0) + 5 * rb; dim = np.ceil((hi - lo) / rb).astype(int) + 1
    if dim.max() > 4000: continue
    H = np.zeros((dim[1], dim[0]), np.float32); ij = np.floor((Q - lo) / rb).astype(int); np.add.at(H, (ij[:, 1], ij[:, 0]), 1)
    ring = (H >= a.stimmen).astype(np.uint8); ring = cv2.morphologyEx(ring, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)); cs, hi_ = cv2.findContours(ring, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)
    if not cs: continue
    dep = []
    for i in range(len(cs)):
        d_ = 0; pr = hi_[0][i][3]
        while pr >= 0: d_ += 1; pr = hi_[0][pr][3]
        dep.append(d_)
    msk = np.zeros_like(ring)                                                                      # Konturen sind Kantenlinien: Tiefe 1 = Innenkante des Umrissrings (Objekt), Tiefe 2 = Aussenkante eines eingeschlossenen Rings (Loch)
    for dd in range(1, 5):
        for i, c in enumerate(cs):
            if dep[i] != dd or len(c) < 8: continue
            if dd % 2 == 1 and dd == 1: cv2.fillPoly(msk, [c], 1)
            elif dd == 2 and cv2.contourArea(c) > 40: cv2.fillPoly(msk, [c], 0)
            elif dd == 3: cv2.fillPoly(msk, [c], 0)
            elif dd == 4: cv2.fillPoly(msk, [c], 1)
    if msk.sum() == 0:                                                                               # kein geschlossener Ring: Aussenkontur fuellen
        for i, c in enumerate(cs):
            if dep[i] == 0 and len(c) >= 8: cv2.fillPoly(msk, [c], 1)
    f0, f1 = off[k], off[k + 1]; tri = F[f0:f1]; cen = V[tri].mean(1); uu = cen[:, :2] @ U_; zz = cen[:, 2]; ci = np.floor((uu - lo[0]) / rb).astype(int); cj = np.floor((zz - lo[1]) / rb).astype(int)
    inn = (ci >= 0) & (ci < dim[0]) & (cj >= 0) & (cj < dim[1]); keep = np.zeros(len(tri), bool); keep[inn] = msk[cj[inn], ci[inn]] > 0
    if keep.sum() < 10: continue
    t2 = tri[keep]; uq, inv = np.unique(t2, return_inverse=True); V2.append(V[uq]); F2.append(inv.reshape(-1, 3).astype(np.int32) + nv); nv += len(uq); M2.append((o, int(FL["npts"][k]), int(keep.sum()), FL["farbe"][k]))
    OUT[int(o)] = dict(n_konturpunkte=int(len(Q)), flaeche_m2=round(float(msk.sum()) * rb * rb, 3), kept=int(keep.sum()), of=int(len(tri)))
np.savez_compressed(a.aus, V=np.vstack(V2), F=np.vstack(F2), ids=np.array([m[0] for m in M2]), npts=np.array([m[1] for m in M2]), ntri=np.array([m[2] for m in M2]), farbe=np.array([m[3] for m in M2]).astype(np.uint8))
json.dump(OUT, open(os.path.splitext(a.aus)[0] + "_konturen.json", "w"))
print("Objekte", len(M2), "Dreiecke", int(sum(m[2] for m in M2)), "von", int(len(F)), "%.0fs" % (time.time() - t0))
