#!/usr/bin/env python3
"""pfade_tiefe_mehrfoto.py - Tiefe der Rippenpfade entlang des 6171-Sehstrahls aus weiteren Fotos (Rippenmaske-Distanzkarten), Pruefbilder zurueckgehalten.
Aufruf: pfade_tiefe_mehrfoto.py OBJ.json --ref K-6171 --fit K-d11,K-n11_04,K-h11_112126 --pruef K-6117,K-h11_112124 --pfad bauteile/10/unterbau/rippen_pfade --achse_n nx ny [--band 0.25] [--glatt 6] [--schreiben]
Ablauf: Pfad ist in --ref lateral schon auf der Rippenmitte (pfade_nachfuehren). Je Pfadpunkt Tiefenkandidaten +-band m entlang des Strahls durch den Ref-Punkt; Kosten = Distanz (px, gekappt 40) des projizierten Punkts zur naechsten Rippenmaske in jedem --fit-Foto (Mittel ueber Fotos, in denen der Punkt im Bild liegt); Viterbi mit Glaettung (|dt| Strafe) -> Tiefe je Punkt. Bericht: Abdeckung (<=15/30 px) je --pruef-Foto vorher/nachher. Mit --schreiben ueberschreibt es die Pfade (nur wenn Pruef-Abdeckung im Mittel steigt)."""
import sys, os, json, glob, importlib.util
import numpy as np, cv2
from skimage.morphology import remove_small_objects, skeletonize
from scipy.ndimage import distance_transform_edt
_d = os.path.dirname(os.path.abspath(__file__)); sp = importlib.util.spec_from_file_location("e", os.path.join(_d, "epilinie.py")); E = importlib.util.module_from_spec(sp); sp.loader.exec_module(E)
a = sys.argv[1:]
if len(a) < 6: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
obj = json.load(open(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); od = os.path.join(root, os.path.dirname(obj["masstabelle"]))
nx, ny = [float(v) for v in a[a.index("--achse_n") + 1:a.index("--achse_n") + 3]]; nn = np.array([nx, ny]); nn /= np.linalg.norm(nn); uu = np.array([nn[1], -nn[0]])
W = lambda q: np.array([*(q[0] * uu + q[1] * nn), q[2]]); UVZ = lambda P: [round(float(P[:2] @ uu), 3), round(float(P[:2] @ nn), 3), round(float(P[2]), 3)]
r = obj
for k in opt("--pfad", "").split("/"): r = r[int(k)] if isinstance(r, list) else r[k]
ref = opt("--ref", "K-6171"); fit = [s for s in opt("--fit", "").split(",") if s]; pru = [s for s in opt("--pruef", "").split(",") if s]; band, glatt = float(opt("--band", 0.25)), float(opt("--glatt", 6))
def maske(kid):
    im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0]); f = im.astype(int); b, g, rr = f[..., 0], f[..., 1], f[..., 2]
    gold = (g > 0.62 * rr) & (rr > 140) & ((rr - b) > 70); dk = (f.max(2) < 80) & ((rr - b) < 30); gl = cv2.dilate(gold.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
    m = ((dk | gold).astype(np.uint8) * gl); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8)); m = remove_small_objects(m.astype(bool), 800).astype(np.uint8); m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    sk = skeletonize(m > 0); return distance_transform_edt(~sk).astype(np.float32)
KS = {k: E.kam(od, k) for k in [ref] + fit + pru}; DT = {k: maske(k) for k in fit + pru}
ents = r.get("pfade_ohne_spiegel", []); P0 = [np.array([W(q) for q in (e["pfad"] if isinstance(e, dict) else e)]) for e in ents]
def kost(kid, P):
    K = KS[kid]; out = np.full(len(P), np.nan)
    for i, p in enumerate(P):
        x = E.projekt(K, p)
        if x is None: continue
        xi, yi = int(round(x[0])), int(round(x[1]))
        if 0 <= yi < DT[kid].shape[0] and 0 <= xi < DT[kid].shape[1]: out[i] = min(float(DT[kid][yi, xi]), 40.0)
    return out
def abdeckung(PS, kids):
    res = {}
    for kid in kids:
        v = np.concatenate([kost(kid, P) for P in PS]); v = v[~np.isnan(v)]; res[kid] = (len(v), float((v <= 15).mean()) if len(v) else 0.0, float((v <= 30).mean()) if len(v) else 0.0)
    return res
vorher = abdeckung(P0, pru); neu = []; cs = KS[ref]["c"]; ts = np.linspace(-band, band, int(2 * band / 0.01) + 1)
for P in P0:
    d = P - cs; L = np.linalg.norm(d, axis=1); dv = d / L[:, None]; C = np.zeros((len(P), len(ts)))
    for j, t in enumerate(ts):
        Q = P + dv * t; cj = np.zeros(len(P)); nj = np.zeros(len(P))
        for kid in fit:
            k_ = kost(kid, Q); ok = ~np.isnan(k_); cj[ok] += k_[ok]; nj[ok] += 1
        C[:, j] = np.where(nj > 0, cj / np.maximum(nj, 1), 20.0)
    lam = 0.02 * glatt; D = C.copy(); bp = np.zeros(C.shape, int)
    for i in range(1, len(P)):
        pen = D[i - 1][None, :] + lam * np.abs(ts[:, None] - ts[None, :]) / 0.01 * 0.05; bp[i] = np.argmin(pen, axis=1); D[i] += pen[np.arange(len(ts)), bp[i]]
    j = int(np.argmin(D[-1])); path = [j]
    for i in range(len(P) - 1, 0, -1): j = bp[i][j]; path.append(j)
    path = path[::-1]; neu.append(np.array([P[i] + dv[i] * ts[path[i]] for i in range(len(P))])); print("Pfad: mittlere Tiefenverschiebung %.1f cm, max %.1f cm, Kosten %.1f -> %.1f px" % (np.mean([abs(ts[p]) for p in path]) * 100, max(abs(ts[p]) for p in path) * 100, C[:, int(np.argmin(np.abs(ts)))].mean(), np.mean([C[i, path[i]] for i in range(len(P))])))
nachher = abdeckung(neu, pru)
for kid in pru: print(kid, "Pruef-Abdeckung vorher: n=%d <=15px %.3f <=30px %.3f | nachher <=15px %.3f <=30px %.3f" % (vorher[kid][0], vorher[kid][1], vorher[kid][2], nachher[kid][1], nachher[kid][2]))
mv, mn = np.mean([vorher[k][2] for k in pru]), np.mean([nachher[k][2] for k in pru]); print("Mittel Pruef <=30px: %.3f -> %.3f" % (mv, mn))
if "--schreiben" in a:
    if mn <= mv: print("NICHT geschrieben: Pruef-Abdeckung steigt nicht")
    else:
        for e, Pn, i in zip(ents, neu, range(len(ents))):
            q = [UVZ(p) for p in Pn]
            if isinstance(e, dict): e["pfad"] = q
            else: r["pfade_ohne_spiegel"][i] = q
        json.dump(obj, open(a[0], "w"), indent=1, ensure_ascii=False); print("geschrieben")
