"""LO-RANSAC-Idee fuer GU.gps_fit: Konsens erst nach lokaler Verfeinerung zaehlen (Top-K Hypothesen) - bleibt der Tor-Fit auf den Fixtures gleich, wird der Ebene-Rahmen stabil?"""
import json, numpy as np, math, sys, os
T = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, T)
import gps_unsicherheit as GU, seiten_gps_vereinen as SG
F = json.load(open(T + "/test_gps_eine_quelle_fixture.json")); D = "/media/oem/scan/rc-park_daten"

def konsens_lo(C, G, n_ransac=3000, seed=0, top=30):
    n_ = len(G); rng = np.random.default_rng(seed); hyp = []
    for _ in range(n_ransac):
        i3 = rng.choice(n_, 2, replace=False)
        if np.hypot(*(G[i3[0]] - G[i3[1]])) < 10 or np.hypot(*(C[i3[0]] - C[i3[1]])) < 1e-6: continue
        s_, R_, t_ = GU._fit2d_t(C[i3], G[i3]); inl = np.hypot(*(C @ R_.T * s_ + t_ - G).T) < 10.0; hyp.append((int(inl.sum()), inl))
    hyp.sort(key=lambda h: -h[0]); seen = set(); best = None
    for c, inl in hyp:
        k = inl.tobytes()
        if k in seen: continue
        seen.add(k)
        b = inl.copy()
        for _ in range(3):
            if b.sum() < 3: break
            s, R, t = GU._fit2d_t(C[b], G[b]); b = np.hypot(*(C @ R.T * s + t - G).T) < 10.0
        if best is None or b.sum() > best.sum(): best = b
        if len(seen) >= top: break
    return best

for fx, ziel in (("schwabentor-1120", "schwabentor-1120"), ("schwabentor-1122j_l0", "schwabentor-1122"), ("kaufhaus_gk2", "kaufhaus_gk2")):
    d = F[fx]; KJ = json.load(open(f"{D}/{ziel}/pipe/kameras.json"))
    nm = [os.path.splitext(b["name"])[0] for b in KJ["bilder"]]; C = np.array([b["C"] for b in KJ["bilder"]], float)
    ix = {n: i for i, n in enumerate(nm)}; sel = np.array([ix[n] for n in d["namen"]])
    G = np.array(d["gps_modell"]); M = np.array(d["kamera_modell"])
    dc = np.linalg.norm(C - np.median(C, 0), axis=1); nah = dc <= np.percentile(dc, 70); cm = C[nah].mean(0); eb = np.linalg.svd(C[nah] - cm)[2][2]
    ach = np.asarray(SG.lot_aus_bild_achsen(np.array([b["R"] for b in KJ["bilder"]], float)), float); eb = eb if eb @ ach > 0 else -eb
    e1 = np.cross(eb, [1, 0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(eb, e1); Cq = ((C - cm) @ np.vstack([e1, e2, eb]).T)[sel, :2]
    fern = np.hypot(*G.T) >= 100
    for name, X in (("modell", M[:, :2]), ("ebene", Cq)):
        r = [konsens_lo(X, G, seed=s) for s in range(10)]
        alt = [GU.gps_fit(X, G, d["zeiten"], seed=s, n_boot=10)["w"] for s in range(10)]
        print(fx, name, "LO", sorted(set((int(b.sum()), int((b & fern).sum())) for b in r)), "alt", sorted(set((int(b.sum()), int((b & fern).sum())) for b in alt)),
              "LO==alt(seed0)", bool((r[0] == alt[0]).all()))
