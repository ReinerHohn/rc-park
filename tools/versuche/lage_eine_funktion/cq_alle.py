"""GPS-Fit der Ausrichtung (Lotsystem vor dem Feinfit) je Lot gegen den Tor-Fit (geschriebene Standorte) - Fixture-GPS, kameras.json, ueber 10 Seeds."""
import json, numpy as np, math, sys, os
T = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, T)
import gps_unsicherheit as GU, seiten_gps_vereinen as SG
F = json.load(open(T + "/test_gps_eine_quelle_fixture.json"))
D = "/media/oem/scan/rc-park_daten"
for fx, ziel in (("schwabentor-1120", "schwabentor-1120"), ("schwabentor-1122j_l0", "schwabentor-1122"), ("kaufhaus_gk2", "kaufhaus_gk2")):
    d = F[fx]; KJ = json.load(open(f"{D}/{ziel}/pipe/kameras.json"))
    nm = [os.path.splitext(b["name"])[0] for b in KJ["bilder"]]; C = np.array([b["C"] for b in KJ["bilder"]], float); Rs = np.array([b["R"] for b in KJ["bilder"]], float)
    ix = {n: i for i, n in enumerate(nm)}; sel = [ix.get(n) for n in d["namen"]]
    ok = np.array([s is not None for s in sel]); sel = np.array([s for s in sel if s is not None])
    G = np.array(d["gps_modell"])[ok]; Z = [z for z, o in zip(d["zeiten"], ok) if o]; M = np.array(d["kamera_modell"])[ok]
    dc = np.linalg.norm(C - np.median(C, 0), axis=1); nah = dc <= np.percentile(dc, 70); cm = C[nah].mean(0); eb = np.linalg.svd(C[nah] - cm)[2][2]
    ach = np.asarray(SG.lot_aus_bild_achsen(Rs), float); eb = eb if eb @ ach > 0 else -eb
    def zus(X):
        r = [GU.gps_fit(X, G, Z, seed=s, n_boot=40) for s in range(10)]
        return [(f["ransac"]["inlier"] if f["ransac"] else int(f["w"].sum()), f["n_fern_inlier"], round(f["sd_drehung_grad"], 1), f["anker"] is not None) for f in r]
    print(f"{fx}: {ok.sum()} von {len(ok)} Namen in kameras.json")
    print("  Tor (Modell)", sorted(set(zus(M[:, :2]))))
    for name, u in (("ebene", eb), ("bildachsen", ach)):
        e1 = np.cross(u, [1, 0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(u, e1); Cq = (C - cm) @ np.vstack([e1, e2, u]).T
        print(" ", name, sorted(set(zus(Cq[sel, :2]))))
