#!/usr/bin/env python3
"""wolke_abweichungskarte.py - Wolke->Netz-Abstand ueber das ganze Gebaeude, getrennt nach Hoehenband (z) und Fassadenabschnitt (u entlang der Fassade): wo ist das Netz schlecht?
  venv-seg/bin/python -I tools/wolke_abweichungskarte.py objekt.json --dicht D --netz name:pfad.stl ... --aus karte.json [--n 400000]
Netz mm->K-Rahmen m; Wolke Umeyama-Rahmen. Ausgabe je Netz: Gesamt-Median/P90 und je Band (1 m) P90 + Anteil > 5 cm; Zellen mit > 30 % ueber 5 cm = Problemzonen."""
import os, sys, json, argparse, numpy as np, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import wolke_front as WF
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--dicht", required=True); ap.add_argument("--netz", action="append", required=True); ap.add_argument("--aus", required=True)
ap.add_argument("--n", type=int, default=200000); ap.add_argument("--rv-z", type=float, default=0.431); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--normale", default="0.344,0.939"); a = ap.parse_args()
od = os.path.dirname(os.path.abspath(a.objekt)); s, Rm, t0, CM, rest = WF.rahmen_umeyama(a.dicht, od); X, _ = WF.ply_farbe(os.path.join(a.dicht, "fused.ply")); X = s * (Rm @ X.T).T + t0
X = X[np.random.default_rng(0).choice(len(X), min(a.n, len(X)), replace=False)]
n = np.array([float(v) for v in a.normale.split(",")]); n /= np.linalg.norm(n); dv = np.array([-n[1], n[0]]); u = X[:, :2] @ dv; z = X[:, 2]
out = {}
for spec in a.netz:
    nm, p = spec.split(":", 1); m = trimesh.load(p, force="mesh"); m.vertices = m.vertices * (a.massstab / 1000.0) + np.array([0, 0, a.rv_z])
    d = np.concatenate([trimesh.proximity.closest_point(m, X[i:i + 20000])[1] for i in range(0, len(X), 20000)]) * 100;   # in Bloecken (OOM bei 750k-Flaechen-Netz, 7.11.)
    zb = np.floor(z).astype(int); ub = np.floor(u / 3.0).astype(int)
    bands = {int(b): dict(n=int((zb == b).sum()), p90=round(float(np.percentile(d[zb == b], 90)), 1), ueber5=round(float((d[zb == b] > 5).mean()), 3)) for b in np.unique(zb) if (zb == b).sum() > 2000}
    zellen = []
    for b in np.unique(zb):
        for c in np.unique(ub):
            mk = (zb == b) & (ub == c)
            if mk.sum() > 800 and (d[mk] > 5).mean() > 0.3: zellen.append(dict(z=int(b), u_m=int(c) * 3, n=int(mk.sum()), ueber5=round(float((d[mk] > 5).mean()), 2)))
    out[nm] = dict(median_cm=round(float(np.median(d)), 2), p90_cm=round(float(np.percentile(d, 90)), 2), ueber5=round(float((d > 5).mean()), 3), baender=bands, problemzellen=zellen)
    print(f"{nm:14s} Median {np.median(d):.2f} cm P90 {np.percentile(d, 90):.2f} cm >5cm {(d > 5).mean() * 100:.1f} %  Problemzellen {len(zellen)}", flush=True)
json.dump(out, open(a.aus, "w"), indent=1)
