"""Drahtgitter aus fusionierten Kantenpunkten: Tiefen-Sweep-Konsens (>=k Referenzfotos je Voxel) + Wolken-Kantenpunkte.
Zwei Hoehenbaender (Tiefenfehler waechst mit z): unten tol klein, oben tol gross. Danach Ausgleich je Segment (SVD ueber Inlier) und Buendel-Zusammenfassung (kanten_buendel.py separat).
Aufruf: gitter_aufbauen.py SWEEP.npz WOLKENKANTEN.npy OUT.json [--zsplit 14] [--tol_u 0.03] [--tol_o 0.15] [--k_u 3] [--k_o 2]"""
import sys, json, numpy as np, torch
sys.path.insert(0, __file__.rsplit("/", 1)[0]); from kanten_lib import ransac_segmente
def opt(n, d): return float(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
ZS = opt("--zsplit", 14); TU = opt("--tol_u", 0.03); TO = opt("--tol_o", 0.15); KU = int(opt("--k_u", 3)); KO = int(opt("--k_o", 2))
z = np.load(sys.argv[1]); P = z["P"]; ref = z["ref"]; W = np.load(sys.argv[2])[:, :3]
def konsens(P, ref, vox):
    g = np.floor(P / vox).astype(np.int64) + 5000; key = g[:, 0] * 100000000 + g[:, 1] * 10000 + g[:, 2]; u, inv = np.unique(key, return_inverse=True)
    pr = np.unique(np.stack([inv, ref], 1), axis=0); return np.bincount(pr[:, 0], minlength=len(u))[inv]
ku = konsens(P, ref, 0.06); ko = konsens(P, ref, 0.15)
U = np.vstack([P[(P[:, 2] < ZS) & (ku >= KU)], W[W[:, 2] < ZS]]); O = P[(P[:, 2] >= ZS) & (ko >= KO)]
def duenn(X, vox):                                                                           # ein Punkt je Voxel (Mittel) - RANSAC-Laufzeit ~ N je Iteration
    g = np.floor(X / vox).astype(np.int64) + 5000; key = g[:, 0] * 100000000 + g[:, 1] * 10000 + g[:, 2]; u, inv = np.unique(key, return_inverse=True)
    out = np.zeros((len(u), 3)); np.add.at(out, inv, X); return out / np.bincount(inv)[:, None]
U = duenn(U, opt("--vu", 0.03)); O = duenn(O, opt("--vo", 0.08))
print("Punkte unten", len(U), "oben", len(O), flush=True)
def ausgleich(X, S, tol):
    out = []
    for s in S:
        a = torch.tensor(s[0], device="cuda"); b = torch.tensor(s[1], device="cuda"); ab = b - a; L = ab.norm().clamp(min=1e-6); u = ab / L; w = X - a; t = (w @ u).clamp(0, float(L)); dd = (w - t[:, None] * u).norm(dim=1); m = dd < 1.5 * tol
        if int(m.sum()) < 6: out.append(s); continue
        Y = X[m]; c = Y.mean(0); _, _, Vh = torch.linalg.svd(Y - c, full_matrices=False); d = Vh[0] * (1 if float(Vh[0] @ u) >= 0 else -1); tt = (Y - c) @ d; lo, hi = torch.quantile(tt, 0.02), torch.quantile(tt, 0.98)
        out.append([(c + d * lo).tolist(), (c + d * hi).tolist(), s[2], s[3]] if float(hi - lo) > 0.3 else s)
    return out
res = []
for nm, X, tol, minpts, minlen, q in (("unten", U, TU, 25, 0.25, 1), ("oben", O, TO, 6, 1.0, 3)):
    Xt = torch.from_numpy(X.astype(np.float32)).cuda(); S = ransac_segmente(Xt, tol=tol, minlen=minlen, minpts=minpts, maxit=int(opt('--maxit', 1500)), log=False)
    S = [[s[0], s[1], q, min(1.0, s[2] / 100)] for s in S]; S = ausgleich(Xt, S, tol); print(nm, "Segmente", len(S), flush=True); res += S
json.dump({"segmente": res}, open(sys.argv[3], "w")); print("fertig", len(res))
