#!/usr/bin/env python3
"""prim_fit_gpu.py - Satteldach (und weitere ebene Primitive) per Gradientenabstieg auf der GPU in die Punktwolke einpassen: alle Parameter zugleich, Millisekunden je Schritt.
Modell: Flaechen als Quads (Ecken = Funktionen der Parameter). Verlust = Mittel der gekappten Punkt-zu-Flaeche-Abstaende (Wolke -> naechste Flaeche; Abstand zum Quad, nicht zur Ebene)
 + Abdeckungsterm (Flaeche -> naechster Wolkenpunkt, gekappt, schwach), damit das Dach nicht zu einem Wolkenstreifen zusammenfaellt.
  /media/oem/scan/venv-seg/bin/python -I tools/prim_fit_gpu.py --wolke W.npy --start u0,u1,ntv,ztv,nf,zf,nth,zth --aus fit.json [--schritte 1500]
Wolke am Dach duenn, ~1 m zu tief (Register): Ergebnis = 'naeher an der Wolke', Foto-Diff entscheidet (Regel 5)."""
import numpy as np, torch, json, argparse, time
ap = argparse.ArgumentParser(); ap.add_argument("--wolke", required=True); ap.add_argument("--achse-n", default="0.3338,0.9426"); ap.add_argument("--start", required=True); ap.add_argument("--aus", required=True)
ap.add_argument("--kappung", type=float, default=0.5); ap.add_argument("--schritte", type=int, default=1500); ap.add_argument("--abdeckung", type=float, default=0.15); a = ap.parse_args()
dev = "cuda" if torch.cuda.is_available() else "cpu"; n = np.array([float(x) for x in a.achse_n.split(",")]); u = np.array([n[1], -n[0]])
P = np.load(a.wolke)[:, :3]; x0 = np.array([float(v) for v in a.start.split(",")]); pu, pn, pz = P[:, :2] @ u, P[:, :2] @ n, P[:, 2]
sel = (pu > x0[0] - 1.5) & (pu < x0[1] + 1.5) & (pn > x0[6] - 1.5) & (pn < x0[2] + 1.5) & (pz > x0[3] - 0.5) & (pz < x0[5] + 1.5)
Qa = np.c_[pu, pn, pz][sel]; rs = np.random.default_rng(1); Qa = Qa[rs.choice(len(Qa), min(len(Qa), 25000), replace=False)]                # Teilmenge: cdist N x M passt in den VRAM
Q = torch.tensor(Qa, dtype=torch.float32, device=dev); print("Wolkenpunkte (Teilmenge)", len(Q), "von", int(sel.sum()), "Geraet", dev)
def quad_pts(A, B, C, D, ns):
    s = torch.linspace(0, 1, ns, device=dev); S, T = torch.meshgrid(s, s, indexing="ij"); S, T = S.reshape(-1, 1), T.reshape(-1, 1)
    return (1 - S) * (1 - T) * A + S * (1 - T) * B + S * T * C + (1 - S) * T * D
def flaechen(p, ns=55):
    u0, u1, ntv, ztv, nf, zf, nth, zth = p; z0 = torch.tensor(10.5, device=dev)
    V = lambda uu, nn, zz: torch.stack([uu, nn, zz])
    F = [quad_pts(V(u0, ntv, ztv), V(u1, ntv, ztv), V(u1, nf, zf), V(u0, nf, zf), ns), quad_pts(V(u0, nf, zf), V(u1, nf, zf), V(u1, nth, zth), V(u0, nth, zth), ns)]
    return torch.cat(F)
def verlust(p):
    F = flaechen(p); d = torch.cdist(Q, F)                      # (N, M)
    d1 = d.min(1).values; d2 = d.min(0).values                  # Wolke->Flaeche, Flaeche->Wolke
    ok = (p[0] < p[1] - 5) & (p[6] < p[4]) & (p[4] < p[2]) & (p[3] < p[5]) & (p[7] < p[5])
    return torch.clamp(d1, max=a.kappung).mean() + a.abdeckung * torch.clamp(d2, max=2.0).mean() + (0 if bool(ok) else 10.0), d1
x = torch.tensor(x0, dtype=torch.float32, device=dev, requires_grad=True); opt = torch.optim.Adam([x], lr=0.03); t0 = time.time()
L0, d0 = verlust(x.detach()); print("Start Verlust", round(float(L0), 4), "Median d", round(float(d0.median()), 3))
for i in range(a.schritte):
    opt.zero_grad(); L, d = verlust(x); L.backward(); opt.step()
    if i % 300 == 0: print(i, round(float(L), 4), "Median d", round(float(d.median()), 3), flush=True)
L, d = verlust(x.detach()); print(f"Ende Verlust {float(L):.4f} Median d {float(d.median()):.3f} P90 {float(torch.quantile(d, 0.9)):.2f} in {time.time()-t0:.1f} s ({a.schritte} Schritte)")
b = x.detach().cpu().numpy(); print("Parameter", np.round(b, 3).tolist())
json.dump(dict(start=x0.tolist(), fit=b.tolist(), verlust_start=float(L0), verlust_ende=float(L), median_d_start=float(d0.median()), median_d_ende=float(d.median()), namen="u0,u1,n_traufe_v,z_traufe_v,n_first,z_first,n_traufe_h,z_traufe_h"), open(a.aus, "w"), indent=1)
