"""Statistische Pruefung des Drahtgitters gegen eine UNABHAENGIGE Sweep-Punktmenge (andere Referenzfotos als beim Aufbau).
Je Segment: Punktzahl n im Schlauch (tol_u unten / tol_o oben, linear mit z), Dichte n/L, Zahl verschiedener Referenzfotos, robuste Querstreuung (MAD).
Segmente mit refs < rmin ODER Dichte unter Quantil werden als Streuer markiert/entfernt.
Aufruf: gitter_statistik.py SEG.json PUNKTE_B.npz OUT.json [--tol_u 0.05] [--tol_o 0.2] [--rmin 3] [--dmin 4] [--zsplit 14] [--bericht]"""
import sys, json, numpy as np, torch
a = sys.argv; g = lambda k, d: float(a[a.index(k) + 1]) if k in a else d
tu, to, rmin, dmin, zs = g("--tol_u", 0.05), g("--tol_o", 0.2), int(g("--rmin", 3)), g("--dmin", 4.0), g("--zsplit", 14.0)
S = json.load(open(a[1])); seg = S["segmente"]; Z = np.load(a[2]); P = torch.tensor(Z["P"], device="cuda", dtype=torch.float32); RF = torch.tensor(Z["ref"], device="cuda")
res = []
for s in seg:
    p0 = torch.tensor(s[0], device="cuda", dtype=torch.float32); p1 = torch.tensor(s[1], device="cuda", dtype=torch.float32); d = p1 - p0; L = d.norm().item(); u = d / max(L, 1e-9)
    tol = tu + (to - tu) * min(1.0, max(0.0, (max(s[0][2], s[1][2]) - 8) / (zs + 8 - 8)))
    # Vorfilter Kugel um die Mitte
    m = (p0 + p1) / 2; near = (P - m).norm(dim=1) < L / 2 + 0.5; Q = P[near]; r = RF[near]
    if len(Q) == 0: res.append((0, 0, L, 0.0, tol, 0.0)); continue
    w = Q - p0; t = w @ u; perp = (w - t[:, None] * u).norm(dim=1); tl = (t > -0.1) & (t < L + 0.1); ok = (perp < tol) & tl; ring = int(((perp >= tol) & (perp < 3 * tol) & tl).sum())
    n = int(ok.sum()); nr = int(torch.unique(r[ok]).numel()) if n else 0; mad = float((perp[ok] - perp[ok].median()).abs().median()) if n > 2 else 0.0
    res.append((n, nr, L, mad, tol, n / max(ring / 8.0, 1.0)))
R = np.array(res); dens = R[:, 0] / np.maximum(R[:, 2], 0.05)
for s, (n, nr, L, mad, tol, kon), dn in zip(seg, res, dens): s.append({"nB": n, "refsB": nr, "dichteB": round(float(dn), 2), "madB": round(mad, 4), "kontrastB": round(kon, 2)})
hi = np.array([max(s[0][2], s[1][2]) >= 13 for s in seg])
print("Segmente", len(seg), "| refs>=%d: %d (hoch: %d von %d)" % (rmin, (R[:, 1] >= rmin).sum(), (R[hi, 1] >= rmin).sum(), hi.sum()))
for lab, mk in (("unten", ~hi), ("oben", hi)): print(lab, "Median n %.0f refs %.0f dichte %.1f" % (np.median(R[mk, 0]), np.median(R[mk, 1]), np.median(dens[mk])))
kmin = g("--kmin", 0.0); keep = (R[:, 1] >= rmin) & (R[:, 5] >= kmin)
print("Kontrast Quantile 10/25/50/75/90 unten", np.round(np.quantile(R[~hi, 5], [.1, .25, .5, .75, .9]), 2), "oben", np.round(np.quantile(R[hi, 5], [.1, .25, .5, .75, .9]), 2))
S["segmente"] = [s for s, k in zip(seg, keep) if k]; print("behalten", len(S["segmente"])); json.dump(S, open(a[3], "w"))
