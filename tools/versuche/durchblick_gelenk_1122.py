#!/usr/bin/env python3
"""durchblick_gelenk_1122.py - GELENK-Messung (22.11.2026) am einen Modell aus der Stufe Durchblick (schwabentor-1122):
  1. Spuren (3D-Punkte) mit Beobachtungen aus Teil 1 UND dem Rest: Anzahl, beteiligte Bilder je Seite, Lage der Punkte (Hoehe ueber Boden, Abstand zur LoD2-Grundflaeche).
  2. Kandidaten knapp unter dem Kriterium: Querpaare Teil 1 <-> Rest mit >= --min Inliern in db.db, beide Bilder im Modell. Je Paar Sampson-Fehler der Inlier gegen die
     Epipolargeometrie AUS DEM MODELL (Posen + Kameras) -> Anteil konsistent (< --px Pixel). Dazu GPS-Standrichtungsunterschied. Nachtraeglich bestaetigt = Anteil >= --anteil.
python -I durchblick_gelenk_1122.py --modell sparse/0 --db db.db --seiten-alt seiten.json --ausrichtung SFM-AUSRICHTUNG --objekt objekt.json --bilder fotos --aus DIR"""
import os, sys, json, argparse, math, collections
import numpy as np
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
MAXID = 2147483647


def main(argv=None):
    ap = argparse.ArgumentParser(); [ap.add_argument(f"--{k}", required=True) for k in ("modell", "db", "seiten-alt", "ausrichtung", "objekt", "bilder", "aus")]
    ap.add_argument("--teile-b", default="1", help="alte Teile (seiten.json der Kette), die zur Seite B zaehlen, z. B. 1,2"); ap.add_argument("--min", type=int, default=30); ap.add_argument("--px", type=float, default=4.0); ap.add_argument("--anteil", type=float, default=0.8)
    a = ap.parse_args(argv); import pycolmap, sqlite3; os.makedirs(a.aus, exist_ok=True)
    import importlib.util
    sp = importlib.util.spec_from_file_location("B", os.path.join(T, "versuche", "durchblick_beleg_1122.py")); B = importlib.util.module_from_spec(sp); sp.loader.exec_module(B)
    import seiten_erkennen as SE
    sj = json.load(open(a.seiten_alt)); g = sj["gemeinschaft"]; teil = {k: t for t, s in enumerate(sj["seiten"]) for k in s["gruppen"]}
    TB = {int(x) for x in a.teile_b.split(",")}; seite = lambda n: 1 if teil.get(g.get(n)) in TB else 0      # 1 = Seite B (alte Teile --teile-b), 0 = alles andere
    r = pycolmap.Reconstruction(a.modell); I = {i: im for i, im in r.images.items() if im.has_pose}; nm = {i: im.name for i, im in I.items()}
    # Ausrichtung (Meter) wie im Beleg
    au = json.load(open(a.ausrichtung)); st = {k: np.asarray(v["standort"], float) for k, v in au["kameras"].items() if v.get("standort") is not None}
    C = {im.name: np.asarray(im.projection_center()) for im in I.values()}; n0 = [n for n in C if seite(n) == 0 and os.path.splitext(n)[0] in st]
    (s, R, t), _ = B.ransac(np.array([C[n] for n in n0]), np.array([st[os.path.splitext(n)[0]] for n in n0]), 1.0); M = lambda X: (s * (R @ np.asarray(X).T)).T + t
    import wolke_grundriss_pruefen as WG
    obj = json.load(open(a.objekt)); zid = obj["lod2"]["id"]; gf = [np.asarray(x)[:, :2] for b in WG.grundrisse(obj, 60.0) if b["id"] == zid for x in b["ground"]][0]
    class _P:
        @staticmethod
        def contains_point(p):
            x, y = p; c = False
            for i in range(len(gf)):
                (x1, y1), (x2, y2) = gf[i], gf[(i + 1) % len(gf)]
                if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
            return c
    poly = _P()
    def randabstand(p):
        d = min(np.linalg.norm(np.cross(np.r_[gf[(i + 1) % len(gf)] - gf[i], 0], np.r_[p - gf[i], 0]))[()] / max(np.linalg.norm(gf[(i + 1) % len(gf)] - gf[i]), 1e-9)
                for i in range(len(gf)))
        return -d if poly.contains_point(p) else d
    # 1. Spuren
    gel = []; bilder = {0: collections.Counter(), 1: collections.Counter()}
    for pid, p in r.points3D.items():
        sei = collections.Counter(seite(nm[el.image_id]) for el in p.track.elements if el.image_id in nm)
        if sei[0] and sei[1]:
            q = M(p.xyz[None])[0]; gel.append(dict(z=round(float(q[2]), 2), rand_m=round(float(randabstand(q[:2])), 2), n0=sei[0], n1=sei[1]))
            for el in p.track.elements:
                if el.image_id in nm: bilder[seite(nm[el.image_id])][nm[el.image_id]] += 1
    z = np.array([x["z"] for x in gel]) if gel else np.zeros(0); rd = np.array([x["rand_m"] for x in gel]) if gel else np.zeros(0)
    erg = dict(spuren=len(gel), bilder_teil1=len(bilder[1]), bilder_rest=len(bilder[0]), bilder_teil1_liste=bilder[1].most_common(15), bilder_rest_liste=bilder[0].most_common(15))
    if len(gel):
        erg.update(z_q=np.percentile(z, [10, 50, 90]).round(2).tolist(), boden_anteil=round(float((z < 1.0).mean()), 3), rand_q=np.percentile(rd, [10, 50, 90]).round(2).tolist(),
                   an_wand_anteil=round(float((np.abs(rd) < 1.5).mean()), 3), weiter_weg_anteil=round(float((rd > 5).mean()), 3))
    print(f"GELENK: {len(gel)} Spuren mit Beobachtungen aus Teil 1 UND Rest; Bilder Teil 1 {len(bilder[1])}, Rest {len(bilder[0])}")
    print("  " + json.dumps({k: erg.get(k) for k in ("z_q", "boden_anteil", "rand_q", "an_wand_anteil", "weiter_weg_anteil")}))
    print("  Teil-1-Bilder:", bilder[1].most_common(8)); print("  Rest-Bilder:", bilder[0].most_common(8))
    # 2. Kandidaten
    db = sqlite3.connect(f"file:{a.db}?immutable=1", uri=True); did = {n: i for i, n in db.execute("select image_id, name from images")}; mid = {im.name: im for im in I.values()}
    wh = {i: (w, h) for i, w, h in db.execute("select i.image_id, c.width, c.height from images i join cameras c on c.camera_id = i.camera_id")}
    from paarvorwahl import gps_aus_exif; from netz_fotos_holen import geo; mitte = geo(obj); gps = {}
    def az(n):
        if n not in gps:
            q = gps_aus_exif(os.path.join(a.bilder, n)); gps[n] = None
            if q is not None:
                w, d = SE.richtung(mitte, q); gps[n] = w if 15 <= d <= 300 else None
        return gps[n]
    def kp(i):
        rr, cc, dd = db.execute("select rows, cols, data from keypoints where image_id=?", (i,)).fetchone(); return np.frombuffer(dd, np.float32).reshape(rr, cc)[:, :2].astype(float)
    def Fm(ia, ib):
        A_, B_ = mid[ia], mid[ib]; Ta = A_.cam_from_world().matrix(); Tb = B_.cam_from_world().matrix()
        Ra, ta = Ta[:, :3], Ta[:, 3]; Rb, tb = Tb[:, :3], Tb[:, 3]; Rr = Rb @ Ra.T; tr = tb - Rr @ ta
        tx = np.array([[0, -tr[2], tr[1]], [tr[2], 0, -tr[0]], [-tr[1], tr[0], 0]]); return tx @ Rr
    def norm(im, x):
        return np.asarray(im.camera.cam_from_img(x))
    kand = [(pid, rows, cols, dat, cfg, pid // MAXID, pid % MAXID) for pid, rows, cols, dat, cfg in
            db.execute("select pair_id, rows, cols, data, config from two_view_geometries where rows >= ?", (a.min,)).fetchall()]
    inv = {i: n for n, i in did.items()}; aus = []
    for pid, rows, cols, dat, cfg, x, y in kand:
        na, nb = inv[x], inv[y]
        if na not in mid or nb not in mid or seite(na) == seite(nb): continue
        ij = np.frombuffer(dat, np.uint32).reshape(rows, cols); p0 = kp(x)[ij[:, 0]]; p1 = kp(y)[ij[:, 1]]; m = SE.paar_staerke(p0, p1, wh[x], wh[y])
        E = Fm(na, nb); u0 = norm(mid[na], p0); u1 = norm(mid[nb], p1); h0 = np.c_[u0, np.ones(len(u0))]; h1 = np.c_[u1, np.ones(len(u1))]
        Ex0 = h0 @ E.T; Etx1 = h1 @ E; num = np.sum(h1 * Ex0, 1) ** 2; den = Ex0[:, 0] ** 2 + Ex0[:, 1] ** 2 + Etx1[:, 0] ** 2 + Etx1[:, 1] ** 2
        f = mid[na].camera.mean_focal_length(); samp = np.sqrt(num / np.maximum(den, 1e-18)) * f          # Sampson in Pixeln (ungefaehr)
        st_ = np.linalg.norm(p0 - p1, axis=1) < SE.DURCH_STATISCH * max(max(wh[x]), max(wh[y]))
        kons = float((samp[~st_] < a.px).mean()) if (~st_).sum() else 0.0
        wa, wb = az(na), az(nb); dw = abs((wa - wb + 180) % 360 - 180) if wa is not None and wb is not None else None
        aus.append(dict(a=na, b=nb, ga=g.get(na), gb=g.get(nb), cfg=cfg, **m, konsistent=round(kons, 3), sampson_median_px=round(float(np.median(samp[~st_])), 2) if (~st_).sum() else None, gps_dw=None if dw is None else round(dw)))
    aus.sort(key=lambda d: -d["n_eff"])
    best = [d for d in aus if d["konsistent"] >= a.anteil and d["n_eff"] >= 15 and d["statisch"] <= SE.DURCH_MAX_STATISCH * max(d["n"], 1)]
    print(f"KANDIDATEN Teil 1 <-> Rest im Modell (>= {a.min} Inlier): {len(aus)}; nachtraeglich konsistent (>= {a.anteil:.0%} der Inlier < {a.px} px, n_eff >= 15, <= 10 % statisch): {len(best)}")
    for d in aus[:25]: print(f"  {d['a'][-24:]} G{d['ga']} | {d['b'][-24:]} G{d['gb']}  n {d['n']} n_eff {d['n_eff']} stat {d['statisch']} Zellen {d['zellen0']}/{d['zellen1']} konsistent {d['konsistent']} Sampson {d['sampson_median_px']} GPS {d['gps_dw']} cfg {d['cfg']}")
    json.dump(dict(gelenk=erg, kandidaten=aus), open(os.path.join(a.aus, "gelenk.json"), "w"), indent=1)


if __name__ == "__main__": main()
