#!/usr/bin/env python3
"""durchblick_beleg_1122.py - BELEG-Auswertung (22.11.2026) fuer die Stufe Durchblick/Umgebung (tools/seiten_erkennen.py --durchblick) an schwabentor-1122.
Eingabe: globaler Mapper auf der Kopie db_durch (Seitenerkennung mit --durchblick, behaltene Uebereck-Paare) ueber alle Bilder des neuen Teils 0. Fragen:
  1. EIN Modell? Kameras je ALTEM Teil (seiten.json der Kette: Teil 0 Nord, Teil 1 Sued) im groessten Modell.
  2. Sim3 Teil-0-Kameras -> Ketten-Ausrichtung (SFM-AUSRICHTUNG, Meter), RANSAC-Schwelle --tol-m (eine Kettenkamera liegt 2277 km daneben) -> Rest Median < 0,3 m?
  3. Lage Teil 1 gegen GPS: Sim3 Modell -> GPS-Ortsebene einmal aus den Teil-0-Fotos, einmal aus den Teil-1-Fotos (jeweils eigene GPS-Fotos 15-300 m); Drehung, Massstab,
     Versatz zwischen beiden. Klebt Teil 1 verdreht an (B1/B3: 162-178 Grad), weichen die beiden Fits um diesen Winkel ab; die systematische GPS-Verzerrung einer Sitzung
     (+9,4 Grad / x0,867) trifft beide Fits gleich.
  4. Grundriss (Ausrichtungsrahmen, Draufsicht): Punkte grau, Kameras alter Teil 0 blau / Teil 1 rot / neu dazu gruen, LoD2-Grundflaeche schwarz.
  5. seiten_modelle_probe.json fuer tools/wand_dicke_tor.py: Teil 'kette' (Kettenmodell Teil 0 + Kettenwolke) und Teil 'durch' (neues Modell + neue Wolke).
python -I durchblick_beleg_1122.py --modell DIR/0 --seiten-alt <kette seiten.json> --ausrichtung <SFM-AUSRICHTUNG> --objekt <objekt.json> --bilder <fotos> --aus DIR
        [--kette-modell <teil0_a/0> --kette-fused <fused.ply> --durch-fused <fused.ply>]"""
import os, sys, json, argparse, math
import numpy as np
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)


def umeyama(X, Y):
    mx, my = X.mean(0), Y.mean(0); U, S, Vt = np.linalg.svd((Y - my).T @ (X - mx) / len(X)); D = np.eye(X.shape[1])
    if np.linalg.det(U @ Vt) < 0: D[-1, -1] = -1
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / (X - mx).var(0).sum(); return s, R, my - s * R @ mx


def ransac(X, Y, tol, it=3000, saat=0):
    rng = np.random.default_rng(saat); best = []
    k = X.shape[1] + 1
    for _ in range(it):
        i = rng.choice(len(X), k, replace=False)
        try: s, R, t = umeyama(X[i], Y[i])
        except Exception: continue
        inl = np.flatnonzero(np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1) < tol)
        if len(inl) > len(best): best = inl
    s, R, t = umeyama(X[best], Y[best]); return (s, R, t), best


def dreh(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))) if R.shape == (3, 3) else float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--modell", required=True); ap.add_argument("--seiten-alt", required=True); ap.add_argument("--ausrichtung", required=True)
    ap.add_argument("--objekt", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--tol-m", type=float, default=1.0)
    ap.add_argument("--kette-modell"); ap.add_argument("--kette-fused"); ap.add_argument("--durch-fused")
    ap.add_argument("--sparse-ply", nargs=2, metavar=("MODELL", "PLY"), help="nur: Punkte eines dünnen Modells als binaere PLY (Format sfm_seiten_modelle.PLY_SATZ) schreiben und Ende "
                    "(Ersatz der dichten Wolke fuer wand_dicke_tor, wenn keine GPU frei ist - schwaecherer Beleg)")
    a = ap.parse_args(argv); import pycolmap; os.makedirs(a.aus, exist_ok=True)
    if a.sparse_ply:
        from sfm_seiten_modelle import PLY_SATZ
        rr = pycolmap.Reconstruction(a.sparse_ply[0]); X = np.array([p.xyz for p in rr.points3D.values()], np.float32); d = np.zeros(len(X), PLY_SATZ); d["p"] = X
        with open(a.sparse_ply[1], "wb") as f:
            f.write((f"ply\nformat binary_little_endian 1.0\nelement vertex {len(X)}\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\nproperty float nz\n"
                     "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n").encode()); f.write(d.tobytes())
        print(f"{len(X)} Punkte -> {a.sparse_ply[1]}"); return
    sj = json.load(open(a.seiten_alt)); g = sj["gemeinschaft"]; teil = {k: t for t, s in enumerate(sj["seiten"]) for k in s["gruppen"]}
    alt = lambda n: teil.get(g.get(n))
    eltern = os.path.dirname(a.modell.rstrip("/")); mod = sorted((d for d in os.listdir(eltern) if d.isdigit()), key=int)
    groessen = {d: pycolmap.Reconstruction(os.path.join(eltern, d)).num_reg_images() for d in mod}
    r = pycolmap.Reconstruction(a.modell); C = {im.name: np.asarray(im.projection_center()) for im in r.images.values() if im.has_pose}
    erg = dict(modelle=groessen, kameras=len(C), je_altem_teil={str(k): sum(1 for n in C if alt(n) == k) for k in sorted({alt(n) for n in C}, key=lambda x: (x is None, x))})
    print(f"Modelle {groessen}; Modell {a.modell}: {len(C)} Kameras, je altem Teil {erg['je_altem_teil']}")
    # 2. Sim3 Teil 0 -> Ausrichtung (Meter)
    au = json.load(open(a.ausrichtung)); st = {k: np.asarray(v["standort"], float) for k, v in au["kameras"].items() if v.get("standort") is not None}
    n0 = [n for n in C if alt(n) == 0 and os.path.splitext(n)[0] in st]
    (s, R, t), inl = ransac(np.array([C[n] for n in n0]), np.array([st[os.path.splitext(n)[0]] for n in n0]), a.tol_m)
    M = lambda X: (s * (R @ np.asarray(X).T)).T + t
    rest = np.linalg.norm(M(np.array([C[n] for n in n0])) - np.array([st[os.path.splitext(n)[0]] for n in n0]), axis=1)
    erg["sim3_teil0"] = dict(gemeinsam=len(n0), inlier=int(len(inl)), rest_median_inlier_m=round(float(np.median(rest[inl])), 3), rest_median_alle_m=round(float(np.median(rest)), 3), tol_m=a.tol_m)
    # wand_dicke_tor legt jeden Teil per NICHT robustem Sim3 ueber alle gemeinsamen Kameras (1. Lauf: Rest 4372 m wegen einer Kamera 'am Mond') -> Ausrichtung nur mit den Inliern
    au_i = dict(au); ok_ = {os.path.splitext(n0[i])[0] for i in inl}; au_i["kameras"] = {k: v for k, v in au["kameras"].items() if k in ok_}
    json.dump(au_i, open(os.path.join(a.aus, "ausrichtung_inlier.json"), "w"))
    print(f"Sim3 Teil 0 -> Ketten-Ausrichtung: {len(inl)}/{len(n0)} Inlier (Schwelle {a.tol_m} m), Rest Median Inlier {np.median(rest[inl]):.3f} m, alle {np.median(rest):.3f} m")
    # 3. GPS
    from paarvorwahl import gps_aus_exif; from netz_fotos_holen import geo; from seiten_erkennen import richtung
    obj = json.load(open(a.objekt)); mitte = geo(obj); gps = {}
    for n in C:
        if not n.startswith("eigen__"): continue
        q = gps_aus_exif(os.path.join(a.bilder, n))
        if q is None: continue
        w, d = richtung(mitte, q)
        if 15.0 <= d <= 300.0: gps[n] = np.array([d * math.sin(math.radians(w)), d * math.cos(math.radians(w))])     # Ost, Nord (m) um die Objektmitte
    fits = {}
    for k in (0, 1):
        nn = [n for n in gps if alt(n) == k]
        if len(nn) < 6: fits[k] = None; continue
        X = M(np.array([C[n] for n in nn]))[:, :2]; Y = np.array([gps[n] for n in nn])
        (sk, Rk, tk), ik = ransac(X, Y, 8.0)        # ANNAHME 8 m: Handy-GPS in der Gasse 5-15 m daneben
        fits[k] = dict(n=len(nn), inlier=int(len(ik)), dreh_grad=round(dreh(Rk), 1), massstab=round(float(sk), 3), t=tk.round(2).tolist(),
                       rest_median_m=round(float(np.median(np.linalg.norm((sk * (Rk @ X.T)).T + tk - Y, axis=1)[ik])), 2))
    erg["gps_fit"] = fits
    if fits.get(0) and fits.get(1):
        dd = (fits[1]["dreh_grad"] - fits[0]["dreh_grad"] + 180) % 360 - 180
        erg["teil1_gegen_teil0_gps"] = dict(drehung_grad=round(dd, 1), massstab=round(fits[1]["massstab"] / fits[0]["massstab"], 3),
                                            versatz_m=round(float(np.linalg.norm(np.array(fits[1]["t"]) - np.array(fits[0]["t"]))), 2))
    # Teil-1-Kameras ueber den Teil-0-GPS-Fit gegen ihr eigenes GPS
    if fits.get(0):
        nn = [n for n in gps if alt(n) == 1]; f0 = fits[0]; R0 = np.array([[math.cos(math.radians(f0["dreh_grad"])), -math.sin(math.radians(f0["dreh_grad"]))], [math.sin(math.radians(f0["dreh_grad"])), math.cos(math.radians(f0["dreh_grad"]))]])
        if nn:
            P = (f0["massstab"] * (R0 @ M(np.array([C[n] for n in nn]))[:, :2].T)).T + np.array(f0["t"]); d = np.linalg.norm(P - np.array([gps[n] for n in nn]), axis=1)
            erg["teil1_kameras_gegen_gps_m"] = dict(n=len(nn), median=round(float(np.median(d)), 2), p90=round(float(np.percentile(d, 90)), 2))
    print("GPS:", json.dumps({k: erg.get(k) for k in ("gps_fit", "teil1_gegen_teil0_gps", "teil1_kameras_gegen_gps_m")}))
    # 4. Grundriss
    import cv2
    P = M(np.array([p.xyz for p in r.points3D.values()]))[:, :2] if r.num_points3D() else np.zeros((0, 2))
    K = {n: M(C[n][None])[0, :2] for n in C}; Q = np.array(list(K.values()))
    try:
        import wolke_grundriss_pruefen as WG
        zid = (obj.get("lod2") or {}).get("id"); LB = [(b["id"] == zid, np.asarray(gf)[:, :2]) for b in WG.grundrisse(obj, 60.0) for gf in b["ground"]]
    except Exception as ex: print("LoD2 nicht gezeichnet:", ex); LB = []
    ziel = [g_ for z, g_ in LB if z]; mz = np.vstack(ziel).mean(0) if ziel else np.median(Q, 0)
    for name, lo, hi in (("grundriss.png", np.percentile(Q, 2, 0) - 10, np.percentile(Q, 98, 0) + 10), ("grundriss_nah.png", mz - 35, mz + 35)):
        gr = 1000; k_ = (gr - 40) / max(hi - lo); px = lambda v: (int(20 + (v[0] - lo[0]) * k_), int(gr - 20 - (v[1] - lo[1]) * k_)); im = np.full((gr, gr, 3), 255, np.uint8)
        for v in P[::max(1, len(P) // 60000)]:
            x, y = px(v)
            if 0 <= x < gr and 0 <= y < gr: im[y, x] = (160, 160, 160)
        for z, g_ in LB: cv2.polylines(im, [np.array([px(v) for v in g_], np.int32)], True, (0, 0, 0) if z else (190, 190, 190), 2 if z else 1)
        for n, v in K.items(): cv2.circle(im, px(v), 4, {0: (200, 60, 0), 1: (0, 0, 220)}.get(alt(n), (0, 170, 0)), -1)
        cv2.putText(im, f"durchblick: {len(C)} Kameras - blau alter Teil 0, rot alter Teil 1, gruen neu; schwarz LoD2", (10, 20), 0, 0.5, (0, 0, 0), 1)
        cv2.imwrite(os.path.join(a.aus, name), im); print("Grundriss ->", os.path.join(a.aus, name))
    # 5. Eingabe fuer wand_dicke_tor
    if a.kette_modell and a.kette_fused and a.durch_fused:
        sm = dict(teile=[dict(teil="kette", modell=a.kette_modell, dicht=dict(fused=a.kette_fused)), dict(teil="durch", modell=a.modell, dicht=dict(fused=a.durch_fused))],
                  vereint=["kette", "durch"], ergebnis=dict(art="vereint")); json.dump(sm, open(os.path.join(a.aus, "seiten_modelle_probe.json"), "w"), indent=1)
    json.dump(erg, open(os.path.join(a.aus, "beleg.json"), "w"), indent=1)


if __name__ == "__main__": main()
