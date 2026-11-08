#!/usr/bin/env python3
"""teil_wolke_sweep.py - GENERISCH: jeden Parameter jeder stl_teil-Gruppe (dn,du,dz Verschiebung; sn,su,sz Skalierung, wie baukasten_gen.stl_teil) in einem WEITEN Bereich durchfahren (Sweep),
den Peak im Matching mit der Punktwolke suchen und behalten. Ohne Gradienten, kein enger Suchraum: findet auch Werte weit vom Start (Dach lag 1,6 m daneben).
Ablauf je Gruppe: (1) 2D-Gitter dn x dz (gekoppelt, Dach: Hang!), (2) 1D-Sweeps aller 6 Parameter nacheinander, 3 Runden mit schrumpfendem Bereich, (3) Peak-Schaerfe melden
(Score-Kurve je Parameter: Tiefe des Peaks gegen Rand). Score = gekappter Mittelabstand Wolkenpunkt -> Teilflaeche (kleiner = besser).
  /media/oem/scan/venv-seg/bin/python -I tools/teil_wolke_sweep.py <objekt.json> --wolke W.npy --aus out.json [--gruppen dach,staffelgiebel,erker,...] [--dmax 3 --smax 0.4 --zmin 9.8]
Wolke vs Foto: Ergebnis = Kandidat, Foto-Diff entscheidet (BS91)."""
import numpy as np, torch, json, argparse, os, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--wolke", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--gruppen", default="")
ap.add_argument("--kappung", type=float, default=0.4); ap.add_argument("--dmax", type=float, default=3.0); ap.add_argument("--smax", type=float, default=0.4); ap.add_argument("--zmin", type=float, default=-1e9)
ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--raster", type=int, default=41); a = ap.parse_args()
dev = "cuda" if torch.cuda.is_available() else "cpu"; K = 1000.0 / a.massstab; OD = os.path.dirname(os.path.abspath(a.objekt)); O = json.load(open(a.objekt)); P = np.load(a.wolke)[:, :3].astype(np.float32); out = {}
NAMEN = ["dn", "du", "dz", "sn", "su", "sz"]
for spec in O["bauteile"]:
    if not spec["typ"].startswith("stl_teil:"): continue
    nm = spec["typ"].split(":")[1]
    if a.gruppen and nm not in a.gruppen.split(","): continue
    n_ = np.array(spec["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    M = [trimesh.load(f if os.path.isabs(f) else os.path.join(OD, f), process=False) for f in spec["dateien"]]
    for m in M: m.apply_scale(1 / K)
    ar = sum(m.area for m in M); X = np.vstack([np.asarray(trimesh.sample.sample_surface(m, max(500, int(8000 * m.area / ar)), seed=1)[0]) for m in M]).astype(np.float32)
    allv = np.vstack([np.asarray(m.vertices) for m in M]); lo, hi = allv.min(0), allv.max(0); A = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]], np.float32)
    sel = np.all((P > lo - a.dmax) & (P < hi + a.dmax), axis=1) & (P[:, 2] > a.zmin); Pc = P[sel]
    if len(Pc) > 20000: Pc = Pc[np.random.default_rng(1).choice(len(Pc), 20000, replace=False)]
    print(f"{nm}: Teilpunkte {len(X)}, Wolkenpunkte {len(Pc)}", flush=True)
    if len(Pc) < 2000: out[nm] = dict(uebersprungen=f"zu wenig Wolke ({len(Pc)})"); continue
    Xt = torch.tensor(X, device=dev); Pt = torch.tensor(Pc, device=dev); At = torch.tensor(A, device=dev); nT = torch.tensor(n_, dtype=torch.float32, device=dev); uT = torch.tensor(u_, dtype=torch.float32, device=dev)
    def score(p):
        dn, du, dz, sn, su, sz = p; d = Xt - At; cn = (d[:, :2] @ nT) * sn + dn; cu = (d[:, :2] @ uT) * su + du; cz = d[:, 2] * sz + dz
        Y = torch.stack([At[0] + cn * nT[0] + cu * uT[0], At[1] + cn * nT[1] + cu * uT[1], At[2] + cz], 1); tot = 0.0
        with torch.no_grad():
            for i in range(0, len(Pt), 5000): tot += float(torch.clamp(torch.cdist(Pt[i:i + 5000], Y).min(1).values, max=a.kappung).sum())
        return tot / len(Pt)
    p = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]; s0 = score(p); kurven = {}
    g = np.linspace(-a.dmax, a.dmax, 25); best = (s0, 0.0, 0.0)                                           # (1) 2D dn x dz
    for dn in g:
        for dz in g:
            s = score([dn, p[1], dz] + p[3:]); best = min(best, (s, float(dn), float(dz)))
    p[0], p[2] = best[1], best[2]; print(f"  2D dn x dz: Peak dn {p[0]:+.2f} dz {p[2]:+.2f}  Score {s0:.4f} -> {best[0]:.4f}", flush=True)
    for runde, f in enumerate((1.0, 0.35, 0.12)):                                                          # (2) 1D-Sweeps, schrumpfender Bereich um den aktuellen Wert
        for j, name in enumerate(NAMEN):
            half = (a.dmax if j < 3 else a.smax) * f; vals = np.linspace(p[j] - half, p[j] + half, a.raster); sc = []
            for v in vals:
                q = list(p); q[j] = float(v); sc.append(score(q))
            k = int(np.argmin(sc)); p[j] = float(vals[k])
            if runde == 0: kurven[name] = dict(werte=[round(float(x), 3) for x in vals[::4]], score=[round(x, 4) for x in sc[::4]], peak=float(vals[k]), tiefe=float(np.median(sc) - min(sc)))
    s1 = score(p); out[nm] = dict(zip(NAMEN, p), score_vor=s0, score_nach=s1, kurven=kurven, wolkenpunkte=int(len(Pc)))
    print(f"  {nm}: Score {s0:.4f} -> {s1:.4f}; " + " ".join(f"{k} {v:+.3f}" for k, v in zip(NAMEN, p)), flush=True)
    print("  Peak-Tiefe (Median - Minimum) je Parameter: " + " ".join(f"{k} {kurven[k]['tiefe']:.4f}" for k in NAMEN), flush=True)
json.dump(out, open(a.aus, "w"), indent=1)
