#!/usr/bin/env python3
"""teilmodell_spuren_einpassen.py - Teilmodell (eigenes SfM-Netz, z. B. Handyfotos 26.11.) ueber DIREKTE 3D-SPUREN ins Hauptnetz legen und unabhaengig pruefen (27.11.2026).

WARUM: tools/teilmodell_ausrichten.py passt per Umeyama der KAMERAZENTREN der gemeinsamen Bilder ein. Die PnP-Posen der gemeinsamen Bilder im Hauptnetz sind
dort schwach, wo das Hauptnetz keine eigenen Punkte hat (Schwabentor-Bruecke: 34 Hauptnetz-Punkte im Steg-Streifen) -> Rest 1,43 m, Massstab 1,7 % daneben,
Bruecke 1 m zu hoch (DOM1-Dach +0,98 m, Dachgefaelle 2 Grad statt flach). Hier: gleiche Keypoints in gemeinsamen Bildern (Teil- und Referenzrekonstruktion aus
derselben Datenbank) = direkte 3D-3D-Paare; nur Referenzpunkte, die von >= --min_fremd Hauptnetz-Bildern (nicht Handy) getragen werden; robuste Sim3 mit fester
Meter-Schwelle im Modellrahmen (tools/sim3_robust.py). Danach UNABHAENGIGE Gegenproben (keine geht in den Fit): Lot aus Bild-x-Achsen (seiten_gps_vereinen.lot_info),
Kamerahoehe ueber DGM1 je Entfernung (Kippung), LoD2-Turmbreite (Massstab), DOM1-Dach des Stegs (Hoehe/Seite/Gefaelle), GPS (Gross-Lage).

Aufruf (venv-colmap):
  tools/py tools/teilmodell_spuren_einpassen.py --teil <teil/0> --ref <sparse_handy/0> --ausrichtung <SFM-AUSRICHTUNG.json> --objekt <objekt.json>
        [--alt <teil/0_ausgerichtet>] [--wolke vereint.ply --wolke_rahmen alt] [--aus ORDNER] [--schwelle_m 0.15] [--min_fremd 3]
Schreibt: <aus>/einpassung.json (Sim3 Teil->Modellmeter, Kennzahlen, Gegenproben, Steg-Mass), <aus>/teil_modell/ (Rekonstruktion in Modellmetern),
  <aus>/teil_sfm/ (im SfM-Rahmen des Hauptnetzes), mit --wolke <aus>/wolke_modell.ply + steg_modell.ply.
Pure Funktionen fuer den Test: steg_messen, steg_tor, kipp_aus_hoehen, direkte_paare_aus_listen.
Verwandt: tools/teilmodell_ausrichten.py (Kamerazentren, Vorlaeufer), tools/teilmodell_sim3.py (LMedS), tools/seiten_eck_koppeln.py (direkte Spuren zwischen Seiten),
tools/kamerahoehe_dgm.py, tools/dom1_kachel.py. Lizenz: pycolmap (BSD-3), numpy, scipy."""
import os, sys, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim3_robust import sim3_meter, anwenden, umeyama  # noqa: E402

STEG_NEIGUNG_MAX_GRAD = 5.0      # Nutzer-Auftrag 27.11.: geneigter Steg ohne Beleg = rot (ueberdachte Holzbruecke ist nahezu waagerecht)
MASSSTAB_LOD2_MAX = 0.03         # Turmbreite gegen LoD2 > 3 % = rot
DOM_DACH_MAX_M = 0.6             # Stegdach gegen DOM1-Rohzellen (1-m-Raster, Firstzelle unterschaetzt den First um bis ~0,3 m)
DOM_SEITE_MAX_M = 1.0            # Dachmitte quer gegen DOM1-Streifen (1-m-Raster)
HOCH_UEBER_DGM_M = 4.0           # Kameras so weit ueber Gelaende = auf Steg/Treppe (Zone fuer den Steg, Erkennen = nur Zone)


# ------------------------------------------------------------------ reine Funktionen (Test ohne Daten)
def direkte_paare_aus_listen(kp_teil, kp_ref):
    """kp_*: Liste je gemeinsames Bild: dict keypoint_index -> point3D_id. -> Liste (teil_id, ref_id) eindeutig."""
    s = set()
    for a, b in zip(kp_teil, kp_ref):
        for k, pid in a.items():
            if k in b: s.add((pid, b[k]))
    return sorted(s)


def steg_messen(P, achse_mitte, achse_dir, z_dach_min=None, quer_max=4.0, laengs=(-20.0, 20.0)):
    """Steg aus Wolkenpunkten P (Modellmeter, z oben) in einer ZONE um eine Naeherungsachse. Achse wird aus Dachpunkten neu gefittet (PCA in xy).
    Dach = oberer Teil der Zonenpunkte (z > z_dach_min, Standard Median+1 m). -> dict mit Achse, Laenge (p1-p99 laengs), Breite (p2-p98 quer), Dach-/Deck-Hoehe,
    Neigung Dach (Grad, Regression z ueber laengs), Neigung Achse gegen xy (= Neigung)."""
    P = np.asarray(P, float); m = np.asarray(achse_mitte, float)[:2]; u = np.asarray(achse_dir, float)[:2]; u = u / np.linalg.norm(u); n = np.array([-u[1], u[0]])
    d = P[:, :2] - m; S = d @ u; Q = d @ n; k = (np.abs(Q) < quer_max) & (S > laengs[0]) & (S < laengs[1])
    if k.sum() < 50: return None
    zmin = np.median(P[k, 2]) + 1.0 if z_dach_min is None else z_dach_min
    kd = k & (P[:, 2] > zmin)
    if kd.sum() < 30: return None
    X = P[kd]; c = X[:, :2].mean(0); w = np.linalg.svd(X[:, :2] - c, full_matrices=False)[2][0]; w = w if w @ u > 0 else -w; nn = np.array([-w[1], w[0]])
    s = (X[:, :2] - c) @ w; q = (X[:, :2] - c) @ nn
    lo, hi = np.percentile(s, [1, 99]); kk = (s > lo) & (s < hi)
    # Gefaelle aus der OBEREN HUELLE je 2-m-Abschnitt (p95 aller Zonenpunkte) - ein fester z-Schnitt kappt einen gekippten Steg und unterschaetzt die Neigung
    sa_ = (P[k, :2] - c) @ w; qa_ = (P[k, :2] - c) @ nn; za_ = P[k, 2]; hb = []
    for b0 in np.arange(lo, hi - 1.0, 2.0):
        bb = (sa_ >= b0) & (sa_ < b0 + 2.0) & (np.abs(qa_) < quer_max)
        if bb.sum() >= 20: hb.append((b0 + 1.0, np.percentile(za_[bb], 95)))
    hb = np.array(hb); sl = np.polyfit(hb[:, 0], hb[:, 1], 1)[0] if len(hb) >= 3 else np.polyfit(s[kk], X[kk, 2], 1)[0]
    # Achsenneigung 3D: Hauptachse der Dachpunkte in 3D
    X3 = X[kk] - X[kk].mean(0); a3 = np.linalg.svd(X3, full_matrices=False)[2][0]
    neig3 = float(np.degrees(np.arcsin(min(1.0, abs(a3[2])))))
    # Deck: untere Punkte der Zone zwischen Dach und Boden, nahe der Achse
    sa = (P[:, :2] - c) @ w; qa = (P[:, :2] - c) @ nn; kdeck = (np.abs(qa) < 2.0) & (sa > lo) & (sa < hi) & (P[:, 2] < zmin) & (P[:, 2] > zmin - 6)
    deck = float(np.percentile(P[kdeck, 2], 5)) if kdeck.sum() > 30 else float("nan")
    mitte = c + 0.5 * (lo + hi) * w
    return dict(mitte_xy=[float(v) for v in mitte], richtung_xy=[float(v) for v in w], laenge_m=float(hi - lo), breite_dach_m=float(np.percentile(q, 98) - np.percentile(q, 2)),
                dach_z_p50=float(np.median(X[kk, 2])), dach_z_p98=float(np.percentile(X[kk, 2], 98)), deck_unterkante_z=deck,
                neigung_dach_grad=float(np.degrees(np.arctan(sl))), neigung_achse3d_grad=neig3, n_dach=int(kk.sum()))


def kipp_aus_hoehen(C, gelaende, pivot, h0=1.5, f_scale=0.2):
    """Kippung (2 Winkel um pivot) + Augenhoehe h0, sodass Kamerahoehe ueber Gelaende konstant ist. C: Kamerazentren (n,3) Modellmeter,
    gelaende(x, y) -> z. ANNAHME: Handy in konstanter Hoehe gehalten (robust soft_l1). -> (ax, ay, h0) in rad/m."""
    from scipy.optimize import least_squares
    from scipy.spatial.transform import Rotation as Ro
    C = np.asarray(C, float); piv = np.asarray(pivot, float)
    def res(p):
        R = Ro.from_rotvec([p[0], p[1], 0]).as_matrix(); Cn = (C - piv) @ R.T + piv; return Cn[:, 2] - gelaende(Cn[:, 0], Cn[:, 1]) - p[2]
    return least_squares(res, [0.0, 0.0, h0], loss="soft_l1", f_scale=f_scale).x


def steg_tor(m, beleg_neigung=False):
    """Rot-Gruende aus Messwerten m (dict): neigung_dach_grad, massstab_lod2 (Verh.), dom_dach_dz_m, dom_seite_m. -> Liste Texte (leer = gruen)."""
    rot = []
    if m.get("neigung_dach_grad") is not None and abs(m["neigung_dach_grad"]) > STEG_NEIGUNG_MAX_GRAD and not beleg_neigung:
        rot.append("Steg %.1f Grad geneigt ohne Beleg (> %.0f)" % (m["neigung_dach_grad"], STEG_NEIGUNG_MAX_GRAD))
    if m.get("massstab_lod2") is not None and abs(m["massstab_lod2"] - 1) > MASSSTAB_LOD2_MAX:
        rot.append("Massstab gegen LoD2-Turmbreite %.3f (> %.0f %%)" % (m["massstab_lod2"], 100 * MASSSTAB_LOD2_MAX))
    if m.get("dom_dach_dz_m") is not None and abs(m["dom_dach_dz_m"]) > DOM_DACH_MAX_M:
        rot.append("Stegdach %.2f m neben DOM1" % m["dom_dach_dz_m"])
    if m.get("dom_seite_m") is not None and abs(m["dom_seite_m"]) > DOM_SEITE_MAX_M:
        rot.append("Stegdach quer %.2f m neben DOM1-Streifen" % m["dom_seite_m"])
    return rot


# ------------------------------------------------------------------ Daten
def _sfm_modell(ausrichtung):
    from scipy.spatial.transform import Rotation as Ro
    A = json.load(open(ausrichtung))["transformation"]; s = A["s"]; R = Ro.from_rotvec(A["rvec"]).as_matrix(); t = np.array(A["t"])
    Ms = np.eye(4); Ms[:3, :3] = s * R; Ms[:3, 3] = t          # Modell -> SfM
    return Ms, np.linalg.inv(Ms)


def _rahmen(objekt):
    r = json.load(open(objekt))["rahmen"]; return np.array(r["mitte_utm"]), np.array(r["xhat_utm"]), np.array(r["yhat_utm"]), float(r["gelaende"])


def _geo(objekt):
    from dom1_kachel import dom1_hoehe, dom1_bilinear
    m0, xh, yh, z0 = _rahmen(objekt)
    def utm(x, y):
        p = m0 + np.outer(np.atleast_1d(x), xh) + np.outer(np.atleast_1d(y), yh); return p[:, 0], p[:, 1]
    def dgm(x, y): E, N = utm(x, y); return dom1_bilinear(E, N, "dgm1") - z0
    def dom(x, y): E, N = utm(x, y); return dom1_bilinear(E, N, "dom1") - z0
    def dom_roh(x, y): E, N = utm(x, y); return dom1_hoehe(E, N, "dom1") - z0
    return dgm, dom, dom_roh, (m0, xh, yh, z0)


def punkt_in_polygon(xy, poly):
    xy = np.atleast_2d(xy); x, y = xy[:, 0], xy[:, 1]; px, py = poly[:, 0], poly[:, 1]; inn = np.zeros(len(xy), bool); j = len(poly) - 1
    for i in range(len(poly)):
        c = ((py[i] > y) != (py[j] > y)) & (x < (px[j] - px[i]) * (y - py[i]) / (py[j] - py[i] + 1e-12) + px[i]); inn ^= c; j = i
    return inn


def lod2_grundrisse(objekt, radius=150.0, puffer=0.5):
    """-> Funktion xy -> bool (in irgendeinem LoD2-Grundriss, Modellrahmen). Grundriss = GroundSurface, um puffer m vergroessert (Schwerpunkt-Skalierung)."""
    import lod2_gebaeude as L
    o = json.load(open(objekt)); m0, xh, yh, z0 = _rahmen(objekt); P = []
    for ch in L.building_chunks(open(o["lod2"]["gml"], encoding="utf-8", errors="ignore").read()):
        for typ, Q in L.polygons_from_chunk(ch):
            if typ != "GroundSurface": continue
            d = Q[:, :2] - m0; q = np.c_[d @ xh, d @ yh]
            if np.linalg.norm(q.mean(0)) > radius: continue
            c = q.mean(0); r = np.linalg.norm(q - c, axis=1).mean(); P.append(c + (q - c) * (1 + puffer / max(r, 0.1)))
    def inn(xy):
        out = np.zeros(len(np.atleast_2d(xy)), bool)
        for q in P: out |= punkt_in_polygon(xy, q)
        return out
    return inn


def direkte_paare(T, R, min_fremd=3, handy_praefix="IMG_"):
    """3D-3D-Paare ueber gleiche Keypoints gemeinsamer Bilder (Teil und Referenz aus derselben Datenbank). Nur Referenzpunkte mit >= min_fremd Bildern ohne handy_praefix."""
    rn = {i.name: i for i in R.images.values() if i.has_pose}; paare = set(); geprueft = 0
    for im in T.images.values():
        if not im.has_pose or im.name not in rn: continue
        b = rn[im.name]; pa, pb = im.points2D, b.points2D
        if len(pa) != len(pb): continue
        geprueft += 1
        for k in range(len(pa)):
            if pa[k].has_point3D() and pb[k].has_point3D() and np.allclose(pa[k].xy, pb[k].xy, atol=0.01): paare.add((pa[k].point3D_id, pb[k].point3D_id))
    X, Y, nf = [], [], []
    for a, b in paare:
        p = R.points3D[b]; f = sum(1 for e in p.track.elements if not R.images[e.image_id].name.startswith(handy_praefix))
        if f >= min_fremd: X.append(T.points3D[a].xyz); Y.append(p.xyz); nf.append(f)
    return np.array(X), np.array(Y), dict(bilder=geprueft, paare_roh=len(paare), paare=len(X))


def lies_ply(p):
    f = open(p, "rb"); h = b""
    while not h.endswith(b"end_header\n"): h += f.readline()
    n = int([l for l in h.split(b"\n") if l.startswith(b"element vertex")][0].split()[-1])
    dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
    return np.fromfile(f, dtype=dt, count=n)


def schreibe_ply(p, a):
    with open(p, "wb") as f:
        f.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty float nx\nproperty float ny\n"
                 "property float nz\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % len(a)).encode()); a.tofile(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teil", required=True); ap.add_argument("--ref", required=True); ap.add_argument("--ausrichtung", required=True); ap.add_argument("--objekt", required=True)
    ap.add_argument("--alt"); ap.add_argument("--wolke"); ap.add_argument("--aus", required=True); ap.add_argument("--schwelle_m", type=float, default=0.15)
    ap.add_argument("--min_fremd", type=int, default=3); ap.add_argument("--radius_m", type=float, default=80.0)
    a = ap.parse_args(); import pycolmap
    from seiten_gps_vereinen import lot_info
    os.makedirs(a.aus, exist_ok=True); Ms, Mi = _sfm_modell(a.ausrichtung); dgm, dom, dom_roh, rahmen = _geo(a.objekt)
    T = pycolmap.Reconstruction(a.teil); R = pycolmap.Reconstruction(a.ref); erg = dict(teil=a.teil, ref=a.ref, ausrichtung=a.ausrichtung)
    in_lod2 = lod2_grundrisse(a.objekt)
    # 1) direkte Spuren -> Sim3 Teil -> Modellmeter
    X, Y, info = direkte_paare(T, R, a.min_fremd); Ym = anwenden(Mi, Y); k = np.linalg.norm(Ym[:, :2], axis=1) < a.radius_m
    r = sim3_meter(X[k], Ym[k], schwelle_m=a.schwelle_m, runden=3000, min_anteil=0.05)
    if r is None: print("KEINE Einpassung (zu wenige stimmige Spuren)", info); return 2
    M = r["M"]; s = float(np.cbrt(np.linalg.det(M[:3, :3])))
    erg["spuren"] = dict(info, im_radius=int(k.sum()), inlier=r["n_inlier"], rest_median_m=r["rest_median_m"], massstab_m_je_teileinheit=s, M_teil_modell=M.tolist())
    print("Spuren:", json.dumps(erg["spuren"] | dict(M_teil_modell="..."), ensure_ascii=False), flush=True)
    kand = {"spuren": M}
    if a.alt:
        A_ = pycolmap.Reconstruction(a.alt); tc = {i.name: np.array(i.projection_center()) for i in T.images.values() if i.has_pose}
        ac = {i.name: np.array(i.projection_center()) for i in A_.images.values() if i.has_pose}; nm = sorted(set(tc) & set(ac))
        s_, R_, t_ = umeyama(np.array([tc[n] for n in nm]), np.array([ac[n] for n in nm])); Ma = np.eye(4); Ma[:3, :3] = s_ * R_; Ma[:3, 3] = t_; kand["alt"] = Mi @ Ma
    # 2) Gegenproben je Kandidat
    tc = {i.name: np.array(i.projection_center()) for i in T.images.values() if i.has_pose}; tr = [i.cam_from_world().rotation.matrix() for i in T.images.values() if i.has_pose]
    rc = {i.name: anwenden(Mi, np.array([i.projection_center()]))[0] for i in R.images.values() if i.has_pose}
    nm = sorted(tc); Ct = np.array([tc[n] for n in nm]); L = lot_info(np.array(tr))
    erg["kandidaten"] = {}
    for kn, Mk in kand.items():
        z = {}; C = anwenden(Mk, Ct); Rk = Mk[:3, :3] / np.cbrt(np.linalg.det(Mk[:3, :3])); up = Rk @ L["oben"]
        z["lot_bildx_neigung_grad"] = float(np.degrees(np.arccos(np.clip(up[2], -1, 1))))
        gem = [i for i, n in enumerate(nm) if n in rc]; e = np.linalg.norm(C[gem] - np.array([rc[nm[i]] for i in gem]), axis=1)
        z["kamerazentren_gegen_pnp_m"] = dict(median=float(np.median(e)), p90=float(np.percentile(e, 90)), n=len(gem))
        g = dgm(C[:, 0], C[:, 1]); o = dom(C[:, 0], C[:, 1]); h = C[:, 2] - g; frei = (o - g < 0.5) & (np.abs(h - np.median(h)) < 1.5)
        piv = np.median(anwenden(Mk, X[k][r["inlier"]]), 0)
        ax, ay, h0 = kipp_aus_hoehen(C[frei], dgm, piv)
        z["kamerahoehe_dgm"] = dict(n=int(frei.sum()), kipp_x_grad=float(np.degrees(ax)), kipp_y_grad=float(np.degrees(ay)), h0_m=float(h0), pivot=piv.tolist())
        hoch = (h > HOCH_UEBER_DGM_M) & (o - g > 3.0) & ~in_lod2(C[:, :2])   # ueber Gelaende, unter Dach (DOM), AUSSERHALB jedes LoD2-Gebaeudes = Steg (Zone)
        z["kameras_hoch"] = int(hoch.sum()); z["_hoch"] = C[hoch]
        erg["kandidaten"][kn] = z
    # 3) Steg-Zone aus hochstehenden Kameras (Linie), Messung aus Wolke
    if a.wolke:
        W = lies_ply(a.wolke); P0 = np.stack([W["x"], W["y"], W["z"]], 1).astype(np.float64)
        Ma_s = np.linalg.inv(Ms @ kand["alt"]) if "alt" in kand else None   # Wolke liegt im SfM-Rahmen der ALTEN Einpassung
        if Ma_s is None: print("--wolke braucht --alt (Rahmen der Wolke)"); return 2
        Xt = anwenden(Ma_s, P0); del P0
        for kn, Mk in kand.items():
            z = erg["kandidaten"][kn]; H_ = z.pop("_hoch")
            if len(H_) < 5: z["steg"] = None; continue
            H_ = H_[np.abs(H_[:, 2] - np.median(H_[:, 2])) < 0.7]          # Steg = gleiche Hoehe; Treppenkameras (steigend) fallen weg
            c = H_[:, :2].mean(0); w = np.linalg.svd(H_[:, :2] - c, full_matrices=False)[2][0]; sh = (H_[:, :2] - c) @ w; zc = float(np.median(H_[:, 2]))
            Pm = anwenden(Mk, Xt); d = Pm[:, :2] - c; dsx = d @ w
            zone = (np.abs(d @ np.array([-w[1], w[0]])) < 6) & (dsx > sh.min() - 3) & (dsx < sh.max() + 3) & (Pm[:, 2] < zc + 5.0)   # Dach <= 5 m ueber Kamera
            st = steg_messen(Pm[zone], c, w, z_dach_min=zc + 0.5, laengs=(sh.min() - 3, sh.max() + 3))
            if st: st["kameras_steg"] = int(len(H_)); st["kamera_z_median"] = zc; st["hinweis"] = "Zone grob (Laenge/Breite/Deck inkl. Anschluesse); Tor nutzt nur Dach gegen DOM1 + Gefaelle"
            if st:
                cm, cw = np.array(st["mitte_xy"]), np.array(st["richtung_xy"]); cn = np.array([-cw[1], cw[0]]); ss = np.arange(-0.4, 0.41, 0.1) * st["laenge_m"]
                dz, dq = [], []
                for sv in ss:
                    qs = np.arange(-5, 5.01, 0.25); p = cm + sv * cw; dd = dom(p[0] + qs * cn[0], p[1] + qs * cn[1]); top = dd > dd.max() - 0.5; dq.append(float((qs * top).sum() / top.sum()))
                    pp = Pm[zone]; ds = (pp[:, :2] - p) @ cw; dqq = (pp[:, :2] - p) @ cn; kk = (np.abs(ds) < 1) & (np.abs(dqq) < 4) & (pp[:, 2] > st["dach_z_p50"] - 1.5)
                    if kk.sum() > 30: dz.append(float(np.percentile(pp[kk, 2], 98) - dd.max())); dq[-1] = float(np.median(dqq[kk]) - dq[-1])
                    else: dq.pop()
                st["dom_dach_dz_m"] = float(np.median(dz)) if dz else None; st["dom_seite_m"] = float(np.median(dq)) if dq else None
                st["dgm_unter_mitte"] = float(dgm(cm[0], cm[1])[0])
            z["steg"] = st
            if kn == "spuren":
                Rn = (Mk @ Ma_s)[:3, :3]; Rn = Rn / np.cbrt(np.linalg.det(Rn))
                schreibe_ply(os.path.join(a.aus, "wolke_modell.ply"), _neu(W, Pm, Rn)); schreibe_ply(os.path.join(a.aus, "steg_modell.ply"), _neu(W[zone], Pm[zone], Rn))
        del Xt
    for z in erg["kandidaten"].values(): z.pop("_hoch", None)
    # 4) Massstab gegen LoD2-Turmbreite steht im Bewertungsskript (braucht Wolke + LoD2), hier Tor auf Steg
    for kn, z in erg["kandidaten"].items():
        st = z.get("steg") or {}
        z["tor_rot"] = steg_tor(dict(neigung_dach_grad=st.get("neigung_dach_grad"), dom_dach_dz_m=st.get("dom_dach_dz_m"), dom_seite_m=st.get("dom_seite_m")))
        print(kn, json.dumps({kk: v for kk, v in z.items()}, ensure_ascii=False), flush=True)
    # 5) Rekonstruktion schreiben
    Tm = pycolmap.Reconstruction(a.teil); sc = s; Rm = M[:3, :3] / sc
    Tm.transform(pycolmap.Sim3d(sc, pycolmap.Rotation3d(Rm), M[:3, 3])); od = os.path.join(a.aus, "teil_modell"); os.makedirs(od, exist_ok=True); Tm.write(od)
    Mss = Ms @ M; ss_ = float(np.cbrt(np.linalg.det(Mss[:3, :3]))); Ts = pycolmap.Reconstruction(a.teil)
    Ts.transform(pycolmap.Sim3d(ss_, pycolmap.Rotation3d(Mss[:3, :3] / ss_), Mss[:3, 3])); od = os.path.join(a.aus, "teil_sfm"); os.makedirs(od, exist_ok=True); Ts.write(od)
    json.dump(erg, open(os.path.join(a.aus, "einpassung.json"), "w"), indent=1, ensure_ascii=False, default=float)
    print("FERTIG", a.aus); return 0


def _neu(W, P, Rn):
    """Punkte P (schon im Modellrahmen) + Normalen um Rn gedreht (Wolken-Rahmen -> Modell)."""
    o = W.copy(); o["x"], o["y"], o["z"] = P[:, 0], P[:, 1], P[:, 2]
    N = np.stack([W["nx"], W["ny"], W["nz"]], 1).astype(np.float64) @ Rn.T; o["nx"], o["ny"], o["nz"] = N[:, 0], N[:, 1], N[:, 2]
    return o


if __name__ == "__main__":
    sys.exit(main())
