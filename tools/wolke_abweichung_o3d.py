#!/usr/bin/env python3
"""wolke_abweichung_o3d.py - Wolke->Netz-Abstand (Open3D RaycastingScene, speicherschonend; trimesh closest_point lief bei 748k Flaechen in OOM, 7.11.) je Hoehenband und 3-m-Fassadenabschnitt.
  venv-o3d/bin/python -I tools/wolke_abweichung_o3d.py --wolke wolke_netzrahmen.npy --netz name:pfad.stl ... --aus karte.json [--n 300000]
Wolke: Netzrahmen (m, K-Rahmen minus rahmen_verschiebung) aus fused.ply (Umeyama, siehe wolke_front.py); Netz STL mm * massstab/1000 (Netzrahmen). Fassadenachse d = (-ny, nx) der Hauptfassade (0,344/0,939)."""
import json, argparse, numpy as np, open3d as o3d, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("--wolke", required=True); ap.add_argument("--netz", action="append", required=True); ap.add_argument("--aus", required=True)
ap.add_argument("--n", type=int, default=300000); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--rv-z", type=float, default=0.431); a = ap.parse_args()
X = np.load(a.wolke).astype(np.float32); X = X[np.random.default_rng(0).choice(len(X), min(a.n, len(X)), replace=False)]
n = np.array([0.344, 0.939]); n /= np.linalg.norm(n); dv = np.array([-n[1], n[0]]); u = X[:, :2] @ dv; z = X[:, 2] + a.rv_z; out = {}
for spec in a.netz:
    nm, p = spec.split(":", 1); m = trimesh.load(p, force="mesh"); V = (np.asarray(m.vertices) * (a.massstab / 1000.0)).astype(np.float32)
    lo, hi = V.min(0) - 1.0, V.max(0) + 1.0; k = np.all((X >= lo) & (X <= hi), 1)   # nur Wolke im Gebaeudequader (Boden/Nachbarhaeuser ausserhalb der Netzhuelle +1 m waeren sonst "Abweichung")
    Xk = X[k]; uk = u[k]; zk = z[k]
    sc = o3d.t.geometry.RaycastingScene(); sc.add_triangles(o3d.core.Tensor(V), o3d.core.Tensor(np.asarray(m.faces, np.uint32)))
    d = sc.compute_distance(o3d.core.Tensor(Xk)).numpy() * 100.0; zb = np.floor(zk).astype(int); ub = np.floor(uk / 3.0).astype(int)
    bands = {int(b): dict(n=int((zb == b).sum()), p90=round(float(np.percentile(d[zb == b], 90)), 1), ueber5=round(float((d[zb == b] > 5).mean()), 3)) for b in np.unique(zb) if (zb == b).sum() > 2000}
    zellen = []
    for b in np.unique(zb):
        for c in np.unique(ub):
            mk = (zb == b) & (ub == c)
            if mk.sum() > 800 and (d[mk] > 5).mean() > 0.3: zellen.append(dict(z=int(b), u_m=int(c) * 3, n=int(mk.sum()), ueber5=round(float((d[mk] > 5).mean()), 2)))
    out[nm] = dict(median_cm=round(float(np.median(d)), 2), p90_cm=round(float(np.percentile(d, 90)), 2), ueber5=round(float((d > 5).mean()), 3), baender=bands, problemzellen=zellen)
    print(f"{nm:10s} Median {np.median(d):.2f} cm P90 {np.percentile(d, 90):.2f} cm >5cm {(d > 5).mean() * 100:.1f} % Problemzellen {len(zellen)}", flush=True)
    for b, v in sorted(bands.items()): print(f"   z {b:2d} m: n {v['n']:6d} P90 {v['p90']:5.1f} cm  >5cm {v['ueber5'] * 100:4.1f} %")
json.dump(out, open(a.aus, "w"), indent=1)
