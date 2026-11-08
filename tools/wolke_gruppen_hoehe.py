#!/usr/bin/env python3
"""wolke_gruppen_hoehe.py - Generatorgruppen DIREKT an der Wolke messen (Nutzerwunsch 7.11.: 'Wolke als Referenz').
Je Gruppe (ausgerichtete Teile f_<name>.stl, mm; Netzrahmen m = mm*0.087): Verschiebung dz (-1..+4 m) und z-Skala sz (0.9..1.5 um die Unterkante) scannen;
Mass = Anteil der Gruppenoberflaeche (Stichprobe) <= 0.15 m von der Wolke (Distanzfeld 5 cm, GPU), plus Medianabstand. Rueckrichtung: Anteil Wolkenpunkte im
Gruppenkasten <= 0.15 m von der Gruppe. Ausgabe JSON mit bestem dz/sz je Gruppe (Startwerte fuer parameter_raum, Quelle 'Wolke Distanzfeld').
Aufruf: venv-seg/bin/python -I tools/wolke_gruppen_hoehe.py AUS.json"""
import sys, json, os, numpy as np, trimesh, torch
from scipy.ndimage import distance_transform_edt
R = "/media/oem/scan/rc-park_null/"; T = R + "generator_alt/teile/"; dev = "cuda"
G = {"giebel": ["giebel", "giebelglas", "giebelrahmen"], "first": ["first"], "dach": ["dach", "dachziegel", "dachmuster", "dachrauten"], "gauben": ["gauben", "gauben_dach", "gauben_rahmen"],
     "helme": ["helm", "helm_gruen", "helm_hell", "helm_rot"], "erker": ["erker"], "laube": ["boegen", "piers", "pierbase", "laube"], "fassade": ["fassade", "waende"]}
X = np.load(R + "wolke_netzrahmen.npy").astype(np.float64)[:, :3]; b = np.array([-14.6, 2.7, 0.6, 15.7, 17.0, 19.9]); lo = b[:3] - 3; hi = b[3:] + 3; X = X[np.all((X >= lo) & (X <= hi), 1)]
z = 0.05; n3 = np.ceil((hi - lo) / z).astype(int); occ = np.ones(n3, bool); ij = np.floor((X - lo) / z).astype(int); occ[ij[:, 0], ij[:, 1], ij[:, 2]] = False
Dt = torch.from_numpy(distance_transform_edt(occ, sampling=z).astype(np.float32)).to(dev)[None, None]; lo_t = torch.tensor(lo, dtype=torch.float32, device=dev); sz_t = torch.tensor(n3 * z, dtype=torch.float32, device=dev)
def dist(Q): g = ((Q - lo_t) / sz_t * 2 - 1)[..., [2, 1, 0]]; return torch.nn.functional.grid_sample(Dt, g.reshape(1, 1, 1, -1, 3), align_corners=True, padding_mode="border").reshape(g.shape[:-1])
out = {}
for g, ns in G.items():
    ms = [trimesh.load(T + f"f_{n}.stl", force="mesh") for n in ns if os.path.exists(T + f"f_{n}.stl")]
    if not ms: continue
    P = np.vstack([trimesh.sample.sample_surface(m, max(500, min(6000, len(m.faces) * 3)))[0] for m in ms]) * 0.087; P = torch.from_numpy(P).float().to(dev); z0 = float(P[:, 2].min())
    res = []
    for sz in np.arange(0.9, 1.51, 0.05):
        for dz in np.arange(-1.0, 4.01, 0.1):
            Q = P.clone(); Q[:, 2] = z0 + (P[:, 2] - z0) * sz + dz; d = dist(Q); res.append((float((d < 0.15).float().mean()), float(d.median()), float(sz), float(dz)))
    base = [r for r in res if abs(r[2] - 1.0) < 1e-6 and abs(r[3]) < 1e-6][0]; best = max(res)
    out[g] = dict(anteil_start=round(base[0], 3), median_start=round(base[1], 3), anteil_best=round(best[0], 3), median_best=round(best[1], 3), sz=round(best[2], 2), dz=round(best[3], 2), z_unterkante=round(z0, 2), z_oberkante_start=round(float(P[:, 2].max()), 2))
    print(g, out[g], flush=True)
json.dump(out, open(sys.argv[1], "w"), indent=1)
