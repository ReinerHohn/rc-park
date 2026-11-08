#!/usr/bin/env python3
"""teil_wolke_fit.py - jede stl_teil-Gruppe (Verschiebung dn/du/dz, Skalierung sn/su/sz um den Anker, wie baukasten_gen.stl_teil) per Gradientenabstieg auf der GPU in die
dichte Punktwolke einpassen. Verlust = gekappter Abstand Wolkenpunkt -> Teilflaeche (nur Wolkenpunkte im Kasten des Teils + Rand), schwach regularisiert. Gruppen mit duenner Wolke
(dach, staffelgiebel, gauben, figuren) werden NICHT eingepasst (Wolke blind/unzuverlaessig, Regel 5), nur gemeldet.
  /media/oem/scan/venv-seg/bin/python -I tools/teil_wolke_fit.py <objekt.json> --wolke W.npy --aus fit.json [--gruppen fassade,fenster,erker,helme]
Ergebnis: je Gruppe Parameter + Median/P90-Abstand vor/nach. Foto-Diff entscheidet danach (Wolkennaehe != Fotonaehe, BS91)."""
import numpy as np, torch, json, argparse, os, sys, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--gruppen", default="fassade,fenster,erker,helme")
ap.add_argument("--kappung", type=float, default=0.25); ap.add_argument("--schritte", type=int, default=600); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--reg", type=float, default=0.02); ap.add_argument("--dmax", type=float, default=0.8); ap.add_argument("--smax", type=float, default=0.1); ap.add_argument("--lr", type=float, default=0.01); ap.add_argument("--zmin", type=float, default=-1e9); a = ap.parse_args()
dev = "cuda" if torch.cuda.is_available() else "cpu"; K = 1000.0 / a.massstab; OD = os.path.dirname(os.path.abspath(a.objekt)); O = json.load(open(a.objekt))
P = np.load(a.wolke)[:, :3].astype(np.float32); out = {}
for spec in O["bauteile"]:
    if not spec["typ"].startswith("stl_teil:"): continue
    nm = spec["typ"].split(":")[1]
    if nm not in a.gruppen.split(","): continue
    n_ = np.array(spec["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    M = [trimesh.load(f if os.path.isabs(f) else os.path.join(OD, f), process=False) for f in spec["dateien"]]
    pts = []
    for m in M:
        m.apply_scale(1 / K); X, _ = trimesh.sample.sample_surface(m, max(2000, int(25000 * m.area / sum(mm.area for mm in M))), seed=1); pts.append(np.asarray(X))
    X = np.vstack(pts).astype(np.float32); allv = np.vstack([np.asarray(m.vertices) for m in M]); lo, hi = allv.min(0), allv.max(0); A = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]], np.float32)
    box_lo, box_hi = lo - a.dmax, hi + a.dmax; Pc = P[np.all((P > box_lo) & (P < box_hi), axis=1) & (P[:, 2] > a.zmin)]
    if len(Pc) > 40000: Pc = Pc[np.random.default_rng(1).choice(len(Pc), 40000, replace=False)]
    print(f"{nm}: Teilpunkte {len(X)}, Wolkenpunkte im Kasten {len(Pc)}", flush=True)
    if len(Pc) < 3000: out[nm] = dict(uebersprungen=f"zu wenig Wolke ({len(Pc)})"); continue
    Xt = torch.tensor(X, device=dev); Pt = torch.tensor(Pc, device=dev); At = torch.tensor(A, device=dev); nT = torch.tensor(n_, dtype=torch.float32, device=dev); uT = torch.tensor(u_, dtype=torch.float32, device=dev)
    def trans(p):
        dn, du, dz, sn, su, sz = p; d = Xt - At; cn = (d[:, :2] @ nT) * sn + dn; cu = (d[:, :2] @ uT) * su + du; cz = d[:, 2] * sz + dz
        return torch.stack([At[0] + cn * nT[0] + cu * uT[0], At[1] + cn * nT[1] + cu * uT[1], At[2] + cz], 1)
    def verlust(p):
        Y = trans(p); d = torch.cdist(Pt, Y).min(1).values
        return torch.clamp(d, max=a.kappung).mean() + a.reg * (((p[:3]) ** 2).sum() + 4 * ((p[3:] - 1) ** 2).sum()), d
    p0 = torch.tensor([0, 0, 0, 1, 1, 1], dtype=torch.float32, device=dev); L0, d0 = verlust(p0)
    p = p0.clone().requires_grad_(True); opt = torch.optim.Adam([p], lr=a.lr)
    lo_b = torch.tensor([-a.dmax] * 3 + [1 - a.smax] * 3, device=dev); hi_b = torch.tensor([a.dmax] * 3 + [1 + a.smax] * 3, device=dev)
    for i in range(a.schritte):
        opt.zero_grad(); L, d = verlust(p); L.backward(); opt.step()
        with torch.no_grad(): p.copy_(torch.max(torch.min(p, hi_b), lo_b))
    L1, d1 = verlust(p.detach()); pb = p.detach().cpu().numpy()
    out[nm] = dict(dn=float(pb[0]), du=float(pb[1]), dz=float(pb[2]), sn=float(pb[3]), su=float(pb[4]), sz=float(pb[5]), median_vor=float(d0.median()), median_nach=float(d1.median()), mittel_gekappt_vor=float(torch.clamp(d0, max=a.kappung).mean()),
                  mittel_gekappt_nach=float(torch.clamp(d1, max=a.kappung).mean()), wolkenpunkte=int(len(Pc)))
    print(f"  {nm}: gekappter Mittelabstand {out[nm]['mittel_gekappt_vor']:.4f} -> {out[nm]['mittel_gekappt_nach']:.4f}; Median {out[nm]['median_vor']:.3f} -> {out[nm]['median_nach']:.3f}; dn {pb[0]:+.2f} du {pb[1]:+.2f} dz {pb[2]:+.2f} s {pb[3]:.3f}/{pb[4]:.3f}/{pb[5]:.3f}", flush=True)
json.dump(out, open(a.aus, "w"), indent=1)
