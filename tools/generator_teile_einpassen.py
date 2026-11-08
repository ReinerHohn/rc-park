#!/usr/bin/env python3
"""generator_teile_einpassen.py - BS52: alten Generator BAUTEILWEISE in die Wolke einpassen (Nutzerplan 7.11.: 'Generator + Wolke immer genauer').
Je Teil (Name im GLB): Start = globale Lage T (generator_ausrichten3), dann Adam auf Verschiebung (3), Gieren (1), Skala je Achse (3, +-15 %) gegen das Distanzfeld der Wolke
(Vorwaerts) + Rueckrichtung (Wolke im Teilkasten -> Teil). Tor: Teil wird nur uebernommen, wenn Median-Abstand zur Wolke sinkt UND Skala < 15 % abweicht.
Ausgabe json je Teil (Abstand vorher/nachher, Lage) + eingepasstes GLB-aequivalente STL (mm).
  venv-seg/bin/python -I tools/generator_teile_einpassen.py glb wolke.npy T.json aus.json [--aus-stl x.stl --teile a,b,c]"""
import json, argparse, time, numpy as np, trimesh, torch
from scipy.ndimage import distance_transform_edt
ap = argparse.ArgumentParser(); ap.add_argument("glb"); ap.add_argument("wolke"); ap.add_argument("T"); ap.add_argument("aus"); ap.add_argument("--aus-stl"); ap.add_argument("--zelle", type=float, default=0.05)
ap.add_argument("--teile", default="fassade,boegen,piers,fenster,erker,rahmen,balkon,galerie,waende,giebel,gauben,gauben_rahmen,statuen,konsolen,gitter,cornice,balken"); ap.add_argument("--clip", type=float, default=0.4); ap.add_argument("--teile-dir", help="je Teil g_<name>.stl (globale Lage) und f_<name>.stl (eingepasst), mm"); ap.add_argument("--alle", action="store_true", help="alle Teile des GLB einpassen und ALLE Fits uebernehmen (Skala-Klemme +-15 %)")
a = ap.parse_args(); dev = "cuda"; t0 = time.time(); T = np.array(json.load(open(a.T))["T"]); sc = trimesh.load(a.glb)
X = np.load(a.wolke).astype(np.float64); b = np.array([-14.6, 2.7, 0.6, 15.7, 17.0, 19.9]); lo = b[:3] - 3; hi = b[3:] + 3; X = X[np.all((X >= lo) & (X <= hi), 1)]
n3 = np.ceil((hi - lo) / a.zelle).astype(int); occ = np.ones(n3, bool); ij = np.floor((X - lo) / a.zelle).astype(int); occ[ij[:, 0], ij[:, 1], ij[:, 2]] = False
Dt = torch.from_numpy(distance_transform_edt(occ, sampling=a.zelle).astype(np.float32)).to(dev)[None, None]; lo_t = torch.tensor(lo, dtype=torch.float32, device=dev); sz_t = torch.tensor(n3 * a.zelle, dtype=torch.float32, device=dev)
def dist(Q): g = ((Q - lo_t) / sz_t * 2 - 1)[..., [2, 1, 0]]; return torch.nn.functional.grid_sample(Dt, g.reshape(1, 1, 1, -1, 3), align_corners=True, padding_mode="border").reshape(g.shape[:-1])
Xg = torch.from_numpy(X).float().to(dev); Rt = torch.tensor(T[:3, :3], dtype=torch.float32, device=dev); tt = torch.tensor(T[:3, 3], dtype=torch.float32, device=dev); out = []; neue = {}
def Rz(t): c, s = torch.cos(t), torch.sin(t); z = torch.zeros_like(t); o = torch.ones_like(t); return torch.stack([torch.stack([c, -s, z], -1), torch.stack([s, c, z], -1), torch.stack([z, z, o], -1)], -2)[0]
for name in (list(sc.geometry) if a.alle else a.teile.split(",")):
    if name not in sc.geometry: continue
    g = sc.geometry[name]; n_s = min(12000, max(2000, len(g.faces) * 4)); P = torch.from_numpy(trimesh.sample.sample_surface(g, n_s)[0]).float().to(dev)
    W = P @ Rt.T + tt; ctr = W.mean(0); box_lo = W.min(0).values - 1.5; box_hi = W.max(0).values + 1.5; Xk = Xg[((Xg >= box_lo) & (Xg <= box_hi)).all(1)]
    if len(Xk) > 8000: Xk = Xk[torch.randperm(len(Xk), device=dev)[:8000]]
    if len(Xk) < 200: out.append(dict(teil=name, status="zu wenig Wolke im Kasten", punkte=int(len(Xk)))); continue
    d0 = dist(W).detach(); med0 = float(d0.median()); fr0 = float((d0 < 0.15).float().mean())
    tr = torch.zeros(3, device=dev, requires_grad=True); yw = torch.zeros(1, device=dev, requires_grad=True); ls = torch.zeros(3, device=dev, requires_grad=True); opt = torch.optim.Adam([tr, yw, ls], lr=0.01)
    pc = P.mean(0)
    def pose(): S = torch.exp(torch.clamp(ls, -0.15, 0.15)); return ((((P - pc) * S) @ Rt.T) @ Rz(yw).T) + (pc @ Rt.T + tt) + tr          # Skala/Gieren um Teilmitte, danach Verschiebung
    for it in range(500):
        opt.zero_grad(); Q = pose(); Qs = Q[torch.randperm(len(Q), device=dev)[:6000]]; fw = torch.clamp(dist(Qs), max=a.clip).mean(); rv = torch.clamp(torch.cdist(Xk, Qs).min(1).values, max=a.clip).mean(); (fw + rv).backward(); opt.step()
    Q = pose().detach(); d1 = dist(Q); med1 = float(d1.median()); fr1 = float((d1 < 0.15).float().mean()); skala = torch.exp(torch.clamp(ls, -0.15, 0.15)).detach().cpu().numpy()
    ok = (med1 < med0 - 0.01) and bool((np.abs(skala - 1) < 0.15).all()) or (a.alle and med1 <= med0); out.append(dict(teil=name, flaechen=len(g.faces), wolke_punkte=int(len(Xk)), median_vorher=round(med0, 3), median_nachher=round(med1, 3), anteil015_vorher=round(fr0, 3), anteil015_nachher=round(fr1, 3),
        verschiebung_m=tr.detach().cpu().numpy().round(3).tolist(), gieren_grad=round(float(np.rad2deg(yw.item())), 2), skala=skala.round(3).tolist(), uebernommen=ok))
    print(f"{name:14s} Median {med0:.2f} -> {med1:.2f} m | <0.15 m {fr0:.2f} -> {fr1:.2f} | Skala {skala.round(2)} | {'UEBERNOMMEN' if ok else 'verworfen'}", flush=True)
    V = torch.from_numpy(np.asarray(g.vertices)).float().to(dev); S = torch.exp(torch.clamp(ls, -0.15, 0.15)); Vf = ((((V - pc) * S) @ Rt.T) @ Rz(yw).T) + (pc @ Rt.T + tt) + tr; Vg = V @ Rt.T + tt
    mf = trimesh.Trimesh(Vf.detach().cpu().numpy(), g.faces, process=False); mg = trimesh.Trimesh(Vg.cpu().numpy(), g.faces, process=False); neue[name] = mf if ok else mg
    if a.teile_dir:
        import os; os.makedirs(a.teile_dir, exist_ok=True)
        for pre, m in (("f_", mf), ("g_", mg)): mm = m.copy(); mm.vertices = mm.vertices / 0.087; mm.export(os.path.join(a.teile_dir, pre + name + ".stl"))
json.dump(out, open(a.aus, "w"), indent=1, ensure_ascii=False); ue = [o for o in out if o.get("uebernommen")]; print(f"{len(ue)} von {len(out)} Teilen uebernommen, {round(time.time() - t0)} s")
if a.aus_stl and neue: m = trimesh.util.concatenate(list(neue.values())); m.vertices = m.vertices / 0.087; m.export(a.aus_stl); print("STL", a.aus_stl, len(m.faces))
