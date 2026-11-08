#!/usr/bin/env python3
"""wolke_gruppen_fit.py - Generatorgruppen (stl_teil) gegen die WOLKE einpassen (Nutzerwunsch 7.11.: Wolke = Referenz; Foto-Diff nur Tor/Kontrolle).
Je Gruppe CMA-ES ueber (dn,du,dz,sn,su,sz) (gleiche Transformation wie baukasten_gen.stl_teil). Ziel: Vorwaerts (Gruppenstichprobe -> Wolke-Distanzfeld 5 cm, auf 0.5 m
begrenzt) + Rueckwaerts (Wolkenpunkte im Gruppenkasten +-1 m -> naechste Gruppenstichprobe, GPU cdist). Wolkenluecke (Anteil <= 0.15 m am Start < 0.15 oder Rueckpunkte < 300):
'nicht entscheidbar', Startwert bleibt (Regel 4/5). Annahme: nur wenn Anteil um >= 0.04 steigt und kein Parameter an der Grenze.
Aufruf: venv-seg/bin/python -I tools/wolke_gruppen_fit.py modelle/kaufhaus_grob/objekt.json AUS.json"""
import sys, json, os, numpy as np, trimesh, torch, cma
from scipy.ndimage import distance_transform_edt
OBJ = json.load(open(sys.argv[1])); OD = os.path.dirname(os.path.abspath(sys.argv[1])); R = "/media/oem/scan/rc-park_null/"; dev = "cuda"; K = OBJ.get("stl_massstab", 87) / 1000.0
X = np.load(R + "wolke_netzrahmen.npy").astype(np.float64)[:, :3]; b = np.array([-14.6, 2.7, 0.6, 15.7, 17.0, 19.9]); lo = b[:3] - 3; hi = b[3:] + 3; X = X[np.all((X >= lo) & (X <= hi), 1)]
z = 0.05; n3 = np.ceil((hi - lo) / z).astype(int); occ = np.ones(n3, bool); ij = np.floor((X - lo) / z).astype(int); occ[ij[:, 0], ij[:, 1], ij[:, 2]] = False
Dt = torch.from_numpy(distance_transform_edt(occ, sampling=z).astype(np.float32)).to(dev)[None, None]; lo_t = torch.tensor(lo, dtype=torch.float32, device=dev); sz_t = torch.tensor(n3 * z, dtype=torch.float32, device=dev)
def dist(Q): g = ((Q - lo_t) / sz_t * 2 - 1)[..., [2, 1, 0]]; return torch.nn.functional.grid_sample(Dt, g.reshape(1, 1, 1, -1, 3), align_corners=True, padding_mode="border").reshape(g.shape[:-1])
Xg = torch.from_numpy(X).float().to(dev); out = {}
def lies(f):
    return trimesh.load(f if os.path.isabs(f) else os.path.join(OD, f), force="mesh")
for spec in OBJ["bauteile"]:
    if not spec["typ"].startswith("stl_teil"): continue
    name = spec["typ"].split(":")[1]; ms = [lies(f) for f in spec["dateien"]]
    # Dateien sind mm im Massstab -> m
    P = np.vstack([trimesh.sample.sample_surface(m, max(500, min(6000, len(m.faces) * 3)))[0] for m in ms]) * K
    n_ = np.array(spec["achse_n"], float); n_ /= np.linalg.norm(n_); u_ = np.array([n_[1], -n_[0]])
    A = np.array([(P[:, 0].min() + P[:, 0].max()) / 2, (P[:, 1].min() + P[:, 1].max()) / 2, P[:, 2].min()]); d = P - A; cn = torch.tensor(d[:, :2] @ n_, dtype=torch.float32, device=dev); cu = torch.tensor(d[:, :2] @ u_, dtype=torch.float32, device=dev); cz = torch.tensor(d[:, 2], dtype=torch.float32, device=dev)
    At = torch.tensor(A, dtype=torch.float32, device=dev); nt = torch.tensor([n_[0], n_[1]], dtype=torch.float32, device=dev); ut = torch.tensor([u_[0], u_[1]], dtype=torch.float32, device=dev)
    def tf(p):
        dn, du, dz, sn, su, sz_ = p; a = cn * sn + dn; c = cu * su + du; h = cz * sz_ + dz
        return torch.stack([At[0] + a * nt[0] + c * ut[0], At[1] + a * nt[1] + c * ut[1], At[2] + h], -1)
    W0 = tf([0, 0, 0, 1, 1, 1]); bl = W0.min(0).values - 1.0; bh = W0.max(0).values + 1.0; Xk = Xg[((Xg >= bl) & (Xg <= bh)).all(1)]
    if len(Xk) > 3000: Xk = Xk[torch.randperm(len(Xk), device=dev)[:3000]]
    def kosten(p):
        W = tf(p); df = dist(W); f = torch.clamp(df, max=0.5).mean()
        if len(Xk) >= 300: r = torch.clamp(torch.cdist(Xk, W[::max(1, len(W) // 3000)]).min(1).values, max=0.5).mean()
        else: r = torch.zeros((), device=dev)
        return float(f + r), float((df < 0.15).float().mean()), float(df.median())
    a0 = kosten([0, 0, 0, 1, 1, 1])
    if a0[1] < 0.15 or len(Xk) < 300: out[name] = dict(status="nicht entscheidbar (Wolkenluecke)", anteil_start=round(a0[1], 3), rueckpunkte=int(len(Xk))); print(name, out[name], flush=True); continue
    lb = [-1.0, -1.0, -3.0, 0.85, 0.85, 0.85]; ub = [1.0, 1.0, 1.5, 1.2, 1.2, 1.2]; es = cma.CMAEvolutionStrategy([0, 0, 0, 1, 1, 1], 0.15, dict(bounds=[lb, ub], popsize=16, maxiter=60, verbose=-9, seed=1))
    while not es.stop():
        xs = es.ask(); es.tell(xs, [kosten(x)[0] for x in xs])
    p = es.result.xbest; k1 = kosten(p); rand = [bool(abs(v - l) < 1e-3 or abs(v - u) < 1e-3) for v, l, u in zip(p, lb, ub)]
    ok = (k1[1] - a0[1] >= 0.04) and not any(rand)
    out[name] = dict(status="angenommen" if ok else ("an Grenze" if any(rand) else "Gewinn < 0.04"), start=dict(kosten=round(a0[0], 3), anteil=round(a0[1], 3), median=round(a0[2], 3)), best=dict(kosten=round(k1[0], 3), anteil=round(k1[1], 3), median=round(k1[2], 3)),
                     params={k: round(float(v), 3) for k, v in zip(("dn", "du", "dz", "sn", "su", "sz"), p)}, an_grenze=rand, rueckpunkte=int(len(Xk))); print(name, out[name], flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)
