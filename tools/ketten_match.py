#!/usr/bin/env python3
"""ketten_match.py - Linienzuege (Rippen) per Mehrfoto-Zuordnung triangulieren: Ketten werden in JEDEM Foto aus der Stabilitaetskarte extrahiert (Skelett, Lueckenschluss, Kreuzungen geradeaus), dann je Kette in Foto A die Tiefe dort gewaehlt, wo ihre Projektion in Foto B auf einer Kette von B liegt (wie kante_3d, aber automatisch), und in Foto C (und D...) GEGENGEPRUEFT. Nur Zuordnungen mit bestandener Gegenprobe werden ausgegeben.
Aufruf: ketten_match.py --A ip_IMG_6171.jpg --B ip_IMG_6177.jpg --C ip_IMG_6173.jpg[,ip_IMG_6249.jpg] [--fenstA x0,y0,x1,y1] [--ziel 17.5,7.7,7.3 --radius 3.0] [--schwelle 110 --schliessen 25] [--tol 4] [--min_m 0.5] [--aus DIR --name N]
Kameras: SfM kam_lot2.json (Weltkoordinaten wie Modell), Karten: kaufhaus_alle/stabil. Ausgabe: DIR/match_<name>.json (pfad_xyz, laenge_m, abstand_B_px, abstand_C_px) + match_<name>.jpg (Foto A mit bestandenen Ketten).
Grenzen: parallele Nachbarkanten koennen mit falscher Tiefe konsistent zuordnen - deshalb Pflicht-Gegenprobe in C; nur Tiefenband um --ziel +- --radius."""
import sys, os, json
import numpy as np, cv2, torch
from skimage.morphology import skeletonize
from scipy.spatial import cKDTree
from scipy.ndimage import convolve, label
from scipy.interpolate import splprep, splev
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
a = sys.argv[1:]
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
D = "/media/oem/scan/rc-park_daten/kaufhaus_alle"; KAM = json.load(open(D + "/sfm/kam_lot2.json")); dev = "cuda" if torch.cuda.is_available() else "cpu"
FA = opt("--A", "ip_IMG_6171.jpg"); FB = opt("--B", "ip_IMG_6177.jpg"); FC = opt("--C", "ip_IMG_6173.jpg").split(","); TH = float(opt("--schwelle", 110)); CL = int(opt("--schliessen", 25)); TOL = float(opt("--tol", 4)); MINM = float(opt("--min_m", 0.5))
ZIEL = np.array([float(v) for v in opt("--ziel", "17.5,7.7,7.3").split(",")]); RAD = float(opt("--radius", 3.0)); aus = opt("--aus", "."); name = opt("--name", "match"); os.makedirs(aus, exist_ok=True)
def kamera(f): c = KAM[f]; return dict(R=np.array(c["Rn"]), t=np.array(c["tn"]), C=np.array(c["C"]), f=c["f"], cx=c["cx"], cy=c["cy"], k1=c["params"][3], W=c["W"])
def proj(K, P):
    q = P @ K["R"].T + K["t"]; x = q[:, 0] / q[:, 2]; y = q[:, 1] / q[:, 2]; s = 1 + K["k1"] * (x * x + y * y); return np.c_[K["f"] * x * s + K["cx"], K["f"] * y * s + K["cy"]], q[:, 2]
def strahl(K, uv):
    x = (uv[:, 0] - K["cx"]) / K["f"]; y = (uv[:, 1] - K["cy"]) / K["f"]; xu, yu = x.copy(), y.copy()
    for _ in range(8): r2 = xu * xu + yu * yu; xu, yu = x / (1 + K["k1"] * r2), y / (1 + K["k1"] * r2)
    d = np.c_[xu, yu, np.ones(len(x))] @ K["R"]; return K["C"], d / np.linalg.norm(d, axis=1, keepdims=True)
def ketten(f, fenster=None):
    sm = cv2.imread(f"{D}/stabil/{f[:-4]}.png", 0); sc = KAM[f]["W"] / sm.shape[1]
    msk = (sm > TH).astype(np.uint8)
    if fenster is not None: w = np.zeros_like(msk); x0, y0, x1, y1 = [int(v / sc) for v in fenster]; w[y0:y1, x0:x1] = 1; msk *= w
    cl = max(3, int(CL / sc)) | 1; msk = cv2.morphologyEx(msk, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cl, cl))); sk = skeletonize(msk > 0)
    nb = convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - 1; jd = cv2.dilate((sk & (nb >= 3)).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool); seg = sk & ~jd
    lab, ns = label(seg, structure=np.ones((3, 3))); jl, nj = label(jd, structure=np.ones((3, 3))); segs = []
    for i in range(1, ns + 1):
        ys, xs = np.nonzero(lab == i)
        if len(xs) < 8: continue
        P = np.c_[xs, ys]; n = len(P); pr = cKDTree(P).query_pairs(1.5, output_type="ndarray")
        if len(pr) == 0: continue
        A = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n)).tocsr(); A = A + A.T; d0 = dijkstra(A, indices=0, unweighted=True); a_ = int(np.argmax(np.where(np.isinf(d0), -1, d0)))
        da, pred = dijkstra(A, indices=a_, unweighted=True, return_predecessors=True); b_ = int(np.argmax(np.where(np.isinf(da), -1, da))); s = [b_]
        while s[-1] != a_ and pred[s[-1]] >= 0: s.append(int(pred[s[-1]]))
        segs.append(P[s[::-1]].astype(float))
    tang = lambda S, e, k=10: ((S[-1] - S[-1 - min(k, len(S) - 1)]) if e else (S[0] - S[min(k, len(S) - 1)])) / (np.linalg.norm((S[-1] - S[-1 - min(k, len(S) - 1)]) if e else (S[0] - S[min(k, len(S) - 1)])) + 1e-9)
    jp = np.array(np.nonzero(jd)).T[:, ::-1]; ends = []
    if len(jp):
        jt = cKDTree(jp)
        for si, S in enumerate(segs):
            for e in (0, 1):
                p = S[-1] if e else S[0]; dd, jj = jt.query(p)
                if dd <= 4.5: ends.append((si, e, p, tang(S, bool(e)), int(jl[jp[jj][1], jp[jj][0]])))
    paare = []; MAXW = np.cos(np.radians(40))
    for jid in set(e[4] for e in ends):
        E_ = [e for e in ends if e[4] == jid]
        for i in range(len(E_)):
            for j in range(i + 1, len(E_)):
                if E_[i][0] == E_[j][0]: continue
                c = float(E_[i][3] @ (-E_[j][3])); v = E_[j][2] - E_[i][2]; vn = np.linalg.norm(v); g = 1.0 if vn < 3 else min(float(E_[i][3] @ (v / vn)), float(-E_[j][3] @ (v / vn)))
                if c >= MAXW and g >= MAXW - 0.1: paare.append((c + g, E_[i], E_[j]))
    paare.sort(key=lambda t: -t[0]); ben = set(); nach = {}
    for _, e1, e2 in paare:
        k1, k2 = (e1[0], e1[1]), (e2[0], e2[1])
        if k1 in ben or k2 in ben: continue
        ben |= {k1, k2}; nach.setdefault(e1[0], []).append((e1[1], e2[0], e2[1])); nach.setdefault(e2[0], []).append((e2[1], e1[0], e1[1]))
    bes = set(); out = []
    for s0 in range(len(segs)):
        if s0 in bes: continue
        cur, vorg = s0, None
        while True:
            nn = [n for n in nach.get(cur, []) if n[1] != vorg]
            if not nn or nn[0][1] == s0: break
            vorg, cur = cur, nn[0][1]
        reihe = [cur]; seen = {cur}
        while True:
            nn = [n for n in nach.get(cur, []) if n[1] not in seen]
            if not nn: break
            cur = nn[0][1]; reihe.append(cur); seen.add(cur)
        bes |= seen; P = []; vor = None
        for k, si in enumerate(reihe):
            S = segs[si]
            if k == 0 and len(reihe) > 1: ok = [n for n in nach[si] if n[1] == reihe[1]][0]; S = S if ok[0] == 1 else S[::-1]
            elif k > 0: S = S if np.linalg.norm(S[0] - vor) <= np.linalg.norm(S[-1] - vor) else S[::-1]
            P.append(S); vor = S[-1]
        out.append(np.vstack(P) * sc)
    return out
fw = [float(v) for v in opt("--fenstA", "900,380,2300,1960").split(",")]
cA = ketten(FA, fw); cB = ketten(FB); cC = {f: ketten(f) for f in FC}
print("Ketten A", len(cA), "B", len(cB), "C", {f: len(v) for f, v in cC.items()})
KA, KB = kamera(FA), kamera(FB); KC = {f: kamera(f) for f in FC}
allB = np.vstack(cB); labB = np.concatenate([np.full(len(c), k) for k, c in enumerate(cB)]); treeB = cKDTree(allB); treeC = {f: cKDTree(np.vstack(v)) for f, v in cC.items()}
dA = float(np.linalg.norm(KA["C"] - ZIEL)); ts = np.arange(max(dA - RAD, 1.0), dA + RAD, 0.02); res = []
from scipy.signal import medfilt
for ia, P2 in enumerate(cA):
    pp = P2[::6]
    if len(pp) < 6: continue
    o, d = strahl(KA, pp); Q = (o[None, None] + d[:, None] * ts[None, :, None]).reshape(-1, 3); uv, z = proj(KB, Q)
    dist, ix = treeB.query(uv); dist = dist.reshape(len(pp), len(ts)); lab = labB[ix].reshape(len(pp), len(ts)); dist[z.reshape(len(pp), len(ts)) < 0.5] = 99
    best = None
    for b in np.unique(lab[dist < TOL]):                                  # je B-Kette: Tiefe je Punkt = Treffer mit kleinstem Abstand auf GENAU dieser Kette
        dd = np.where((lab == b) & (dist < TOL), dist, 99.0); tb = ts[dd.argmin(1)]; ok = dd.min(1) < TOL
        if ok.mean() < 0.7: continue
        s_ = np.arange(len(pp), dtype=float); tt = np.interp(s_, s_[ok], tb[ok]); tm = medfilt(tt, 5); ok &= np.abs(tt - tm) < 0.06
        sprung = float(np.abs(np.diff(tm)).max()) if len(tm) > 1 else 9
        if ok.mean() < 0.7 or sprung > 0.25: continue
        sc = ok.mean() - 0.1 * float(np.median(dd.min(1)[ok]))
        if best is None or sc > best[0]: best = (sc, b, tm, ok, float(np.median(dd.min(1)[ok])))
    if best is None: continue
    _, b, tt, ok, dmed = best; P3 = o + d * tt[:, None]; dmin = np.array([dmed])
    try: tck, _ = splprep(P3.T, s=len(P3) * 0.0016); Qs = np.array(splev(np.linspace(0, 1, 32), tck)).T
    except Exception: continue
    L = float(np.linalg.norm(np.diff(Qs, axis=0), axis=1).sum())
    if L < MINM or L > 4.0: continue
    dc = {}
    for f in FC:
        uvc, zc = proj(KC[f], P3); W = KAM[f]["W"]; vis = (zc > 0.5) & (uvc[:, 0] > 0) & (uvc[:, 0] < W) & (uvc[:, 1] > 0)
        dc[f] = float(np.median(treeC[f].query(uvc[vis])[0])) if vis.sum() >= 5 else None
    gv = [v for v in dc.values() if v is not None]; res.append(dict(klasse="Kette", laenge_m=round(L, 2), abstand_B_px=round(dmed, 2), abstand_C_px={k: (None if v is None else round(v, 1)) for k, v in dc.items()}, bestanden=bool(gv and np.mean(gv) < float(opt("--c_tol", 40))), pfad_xyz=Qs.round(3).tolist(), pixel=P2[::4].tolist(), belegt=round(float(ok.mean()), 2)))
bes = [r for r in res if r["bestanden"]]; print(f"{len(res)} zugeordnet, {len(bes)} mit bestandener Gegenprobe (Mittel C < {opt("--c_tol", 40)} px)")
for i, r in enumerate(sorted(res, key=lambda r: -r["laenge_m"])[:20]): print(i, r["laenge_m"], "B", r["abstand_B_px"], "C", r["abstand_C_px"], "OK" if r["bestanden"] else "-")
json.dump(bes, open(os.path.join(aus, f"match_{name}.json"), "w"))
im = cv2.imread(f"{D}/bilder/{FA}"); rng = np.random.default_rng(1)
for r in bes: col = tuple(int(v) for v in rng.integers(80, 255, 3)); cv2.polylines(im, [np.array(r["pixel"], np.int32)], False, col, 6)
x0, y0, x1, y1 = [int(v) for v in fw]; cr = im[y0:y1, x0:x1]; cv2.imwrite(os.path.join(aus, f"match_{name}.jpg"), cv2.resize(cr, None, fx=1000 / cr.shape[0], fy=1000 / cr.shape[0]))
