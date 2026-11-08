#!/usr/bin/env python3
"""Stufe 2: Merkmalsabgleich (SIFT+Ratio+Fundamental-RANSAC) aller Quellfotos gegen Referenzpools und untereinander.
Eingabe: AUS/inventar_roh.json (+inventar_ref.json), AUS/cache/*.npz. Ausgabe AUS/abgleich.json.
Inlier-Zahl ist ein HINWEIS (kein Beweis): wiederholte Fassadenmuster koennen falsche Treffer geben."""
import os
os.environ["OMP_NUM_THREADS"] = "1"; os.environ["OPENBLAS_NUM_THREADS"] = "1"; os.environ["MKL_NUM_THREADS"] = "1"
import json, sys, time, numpy as np, cv2
from multiprocessing import Pool
cv2.setNumThreads(1)
AUS = "/media/oem/TOSHIBA EXT/rc-park_auslagern/nubia_sortierung"
CACHE = AUS + "/cache"
NMAX = 800
D = {}   # key -> (pts, desc float32 root)

def lade(k):
    z = np.load(f"{CACHE}/{k}.npz")
    pts, d = z["pts"], z["d"].astype(np.float32)
    if len(d) > NMAX:   # feste Zufallsauswahl (Antwortzeit); Reihenfolge der SIFT-Ausgabe ist nicht nach Staerke
        sel = np.random.default_rng(7).choice(len(d), NMAX, replace=False); pts, d = pts[sel], d[sel]
    if len(d):
        d /= (d.sum(1, keepdims=True) + 1e-6); d = np.sqrt(d)
    return pts, d

def paar(a, b):
    pa, da = D[a]; pb, db = D[b]
    if len(da) < 20 or len(db) < 20: return 0
    S = da @ db.T
    i2 = np.argpartition(-S, 1, axis=1)[:, :2]
    s2 = np.take_along_axis(S, i2, 1)
    o = np.argsort(-s2, axis=1)
    i1 = np.take_along_axis(i2, o, 1)[:, 0]
    ss = np.take_along_axis(s2, o, 1)
    d1 = np.sqrt(np.maximum(2 - 2 * ss[:, 0], 0))
    d2 = np.sqrt(np.maximum(2 - 2 * ss[:, 1], 0))
    mut = np.argmax(S, axis=0)[i1] == np.arange(len(da))
    ok = (d1 < 0.8 * d2) & mut
    if ok.sum() < 15: return 0
    p1 = pa[ok]; p2 = pb[i1[ok]]
    try:
        F, mask = cv2.findFundamentalMat(p1, p2, cv2.FM_RANSAC, 2.0, 0.999, 1000)
    except cv2.error:
        return 0
    return int(mask.sum()) if mask is not None else 0

def job(ab):
    a, bs = ab
    return a, [(b, paar(a, b)) for b in bs]

if __name__ == "__main__":
    inv = json.load(open(AUS + "/inventar_roh.json")) + json.load(open(AUS + "/inventar_ref.json"))
    inv = [r for r in inv if r["ok"]]
    for r in inv:
        D[r["key"]] = lade(r["key"])
    q = [r for r in inv if r["typ"] == "quelle"]
    md5_vorh = {r["md5"] for r in inv if r["typ"] in ("vorhanden", "eingang_root")}
    pools = {"kaufhaus_handy": [r for r in inv if r["typ"] in ("vorhanden", "eingang_root")],
             "kaufhaus_web": [r for r in inv if r["typ"] == "ref_kaufhaus"],
             "martinstor_web": [r for r in inv if r["typ"] == "ref_martinstor"]}
    # eindeutige Quell-md5 (Dubletten nur einmal rechnen)
    rep = {}
    for r in q: rep.setdefault(r["md5"], r)
    qk = [r["key"] for r in rep.values()]
    refk = sorted({r["key"] for p in pools.values() for r in p})
    import datetime
    def ts(r): return datetime.datetime.strptime(r["datum"], "%Y:%m:%d %H:%M:%S").timestamp() if r.get("datum") else 0
    T = {r["key"]: ts(r) for r in rep.values()}
    jobs = []
    for i, a in enumerate(qk):
        nb = [b for b in qk[i + 1:] if abs(T[b] - T[a]) <= 300]
        jobs.append((a, nb + refk))
    print(len(qk), "eindeutige Quellbilder,", len(refk), "Referenzen", flush=True)
    res = {}
    with Pool(22) as p:
        for n, (a, lst) in enumerate(p.imap_unordered(job, jobs, chunksize=2)):
            res[a] = [(b, v) for b, v in lst if v >= 15]
            if n % 50 == 0: print(n, flush=True)
    json.dump({"paare": res, "pools": {k: [r["key"] for r in v] for k, v in pools.items()}}, open(AUS + "/abgleich.json", "w"))
    print("fertig")
