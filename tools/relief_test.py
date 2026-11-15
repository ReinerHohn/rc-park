#!/usr/bin/env python3
"""relief_test.py <objekt.json> <netz.npz> --ecke_a x y --ecke_b x y --feld u0 u1 z0 z1 --fotos K-A K-B ... [--px 0.01] [--aus PREFIX]

Test "Relief-Einsatz aus dem Scan-Netz" (Nutzer 15.11.2026): bringt ein Hoehenbild aus dem OpenMVS-Netz auf einer Generatorwand etwas, und ist es stabil?
Wandebene = senkrechte Ebene durch zwei am Foto gemessene Wandecken a, b (Modellrahmen). Feld = Rechteck (u entlang a->b, z) auf der Wand.
  1. Hoehenbild d(u, z) = Abstand der Netzflaeche vor der Ebene (Maximum je Zelle, Loecher bleiben Loecher), Ebenentrend (Anzug der Wand) abgezogen.
  2. Je Foto: Entzerrung des Fotos auf dieselbe Wandebene (kalibrierte K-Kamera, k1) -> Fotokanten (Canny) = unabhaengiger Beleg fuer Fugen.
  3. Kennzahlen: Lochanteil; Reliefhub p5..p95 in cm und in mm bei 1:87; Fugen-F1 = Reliefkanten gegen Fotokanten (Toleranz 3 cm), je Foto;
     Zufallsprobe (Relief um 0,37 m / 0,23 m verschoben) als Nullniveau; Stabilitaet = F1 zwischen den Fotos untereinander als Obergrenze.
netz.npz: V (Ecken im Modellrahmen), F. Schreibt PREFIX.jpg (Foto | Relief | Kanten) und PREFIX.json. Kein Eingriff in Generator/STL.
"""
import sys, os, json, argparse, numpy as np, cv2


def kanten_f1(a, b, tol_px):
    da = cv2.distanceTransform((~a).astype(np.uint8), cv2.DIST_L2, 3); db = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 3)
    p = float((db[a] <= tol_px).mean()) if a.any() else 0.0; r = float((da[b] <= tol_px).mean()) if b.any() else 0.0
    return (2 * p * r / (p + r) if p + r else 0.0), p, r


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("netz"); ap.add_argument("--ecke_a", nargs=2, type=float, required=True)
    ap.add_argument("--ecke_b", nargs=2, type=float, required=True); ap.add_argument("--feld", nargs=4, type=float, required=True)
    ap.add_argument("--fotos", nargs="+", required=True); ap.add_argument("--px", type=float, default=0.01); ap.add_argument("--aus", default=""); a = ap.parse_args()
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
    A = np.array(a.ecke_a); B = np.array(a.ecke_b); t = (B - A) / np.linalg.norm(B - A); n = np.array([t[1], -t[0]])
    cm = np.array(json.load(open(os.path.join(od, "messprotokoll", a.fotos[0] + ".json")))["kamera"]["standort_xyz"][:2])
    if (cm - A) @ n < 0: n = -n                                                        # Normale zeigt zur Kamera (nach aussen)
    u0, u1, z0, z1 = a.feld; px = a.px; W = int(round((u1 - u0) / px)); H = int(round((z1 - z0) / px))
    Z = np.load(a.netz); V = Z["V"].astype(np.float64); tri = V[Z["F"]]
    c = tri.mean(1); uu = (c[:, :2] - A) @ t; dd = (c[:, :2] - A) @ n; ok = (uu > u0 - 0.1) & (uu < u1 + 0.1) & (np.abs(dd) < 0.6) & (c[:, 2] > z0 - 0.1) & (c[:, 2] < z1 + 0.1); tri = tri[ok]
    w = np.random.default_rng(0).dirichlet((1, 1, 1), (len(tri), 12)); P = (w[:, :, :, None] * tri[:, None, :, :]).sum(2).reshape(-1, 3)   # 12 Punkte je Dreieck
    uu = (P[:, :2] - A) @ t; dd = (P[:, :2] - A) @ n; iu = ((uu - u0) / px).astype(int); iv = (H - 1 - (P[:, 2] - z0) / px).astype(int); g = (iu >= 0) & (iu < W) & (iv >= 0) & (iv < H)
    hm = np.full((H, W), -9, np.float32); np.maximum.at(hm, (iv[g], iu[g]), dd[g].astype(np.float32)); loch = hm < -5
    lochanteil_roh = float(loch.mean()); fl = cv2.dilate(hm, np.ones((3, 3), np.uint8)); hm[loch] = fl[loch]; loch = hm < -5     # Nadelloecher (1 Zelle) aus den Nachbarn, groessere Loecher bleiben
    yy, xx = np.mgrid[0:H, 0:W]; G = np.c_[xx[~loch], yy[~loch], np.ones((~loch).sum())]; ko = np.linalg.lstsq(G, hm[~loch], rcond=None)[0]
    rel = hm - (ko[0] * xx + ko[1] * yy + ko[2]); rel[loch] = 0.0; anzug = float(-ko[1] / px)      # m je m Hoehe: + = Netzflaeche tritt nach oben VOR die Ebene (Schiefstand des Rahmens oder echte Wandneigung - mit Gegenseite pruefen)
    q5, q95 = np.percentile(rel[~loch], [5, 95]); hub = float(q95 - q5)
    r8 = np.clip((rel - q5) / max(hub, 1e-6) * 255, 0, 255).astype(np.uint8); r8 = cv2.GaussianBlur(r8, (0, 0), 1.5); kr = cv2.Canny(r8, 40, 100) > 0; kr[cv2.dilate(loch.astype(np.uint8), np.ones((9, 9))) > 0] = False
    # Fotos auf die Wandebene entzerren
    Xw = np.c_[(A[0] + (u0 + (xx + 0.5) * px) * t[0]).ravel(), (A[1] + (u0 + (xx + 0.5) * px) * t[1]).ravel(), (z0 + (H - 1 - yy + 0.5) * px).ravel()]
    orth, kf = [], []
    for kid in a.fotos:
        K = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; import glob
        fn = (glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + ".*")) or glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*")))[0]; im = cv2.imread(fn)
        R = cv2.Rodrigues(np.array(K["rvec"]))[0]; pc = Xw @ R.T + np.array(K["t"]); x = pc[:, 0] / pc[:, 2]; y = pc[:, 1] / pc[:, 2]; k1 = float(K.get("k1") or 0); f_ = 1 + k1 * (x * x + y * y)
        mx = (K["f_px"] * x * f_ + K["cx"]).reshape(H, W).astype(np.float32); my = (K["f_px"] * y * f_ + K["cy"]).reshape(H, W).astype(np.float32)
        o = cv2.remap(im, mx, my, cv2.INTER_LINEAR); orth.append(o); gr = cv2.GaussianBlur(cv2.cvtColor(o, cv2.COLOR_BGR2GRAY), (0, 0), 1.5); kf.append(cv2.Canny(gr, 30, 80) > 0)
    tol = 0.03 / px; res = dict(werkzeug="relief_test.py", feld=a.feld, px_m=px, lochanteil=round(float(loch.mean()), 4), lochanteil_vor_nadelfuellung=round(lochanteil_roh, 4), hub_p5_p95_cm=round(hub * 100, 1),
                                 hub_mm_bei_1_87=round(hub * 1000 / 87, 3), vortritt_nach_oben_m_je_m=round(anzug, 4), fotos={})
    for kid, k in zip(a.fotos, kf):
        f1, p, r = kanten_f1(kr, k, tol); null = np.mean([kanten_f1(np.roll(kr, (int(dy / px), int(dx / px)), (0, 1)), k, tol)[0] for dx, dy in ((0.37, 0.23), (-0.41, 0.31), (0.29, -0.43))])
        # Fugen-Korrelation: Fugen liegen TIEF (Relief klein) und sind HELL (Moertel) -> Hochpass beider Bilder (minus Gauss 15 cm) muss negativ korrelieren;
        # Suche des besten Versatzes +-30 cm = Lagefehler des Reliefs gegen das Foto; Nullniveau = Versatz 0,3-0,45 m
        o_ = orth[a.fotos.index(kid)]; gh = cv2.cvtColor(o_, cv2.COLOR_BGR2GRAY).astype(np.float32); sg = 0.15 / px
        gh = cv2.GaussianBlur(gh, (0, 0), 1.0) - cv2.GaussianBlur(gh, (0, 0), sg); rh = cv2.GaussianBlur(rel, (0, 0), 1.0) - cv2.GaussianBlur(rel, (0, 0), sg); m_ = int(0.5 / px)   # Rand > Suchweite
        def ncc(dx, dy):
            A_ = rh[m_:-m_, m_:-m_]; B_ = gh[m_ + dy:H - m_ + dy, m_ + dx:W - m_ + dx]; A_ = A_ - A_.mean(); B_ = B_ - B_.mean(); return float((A_ * B_).sum() / (np.sqrt((A_ ** 2).sum() * (B_ ** 2).sum()) + 1e-9))
        sch = int(0.30 / px); best = min(((ncc(dx, dy), dx, dy) for dx in range(-sch, sch + 1) for dy in range(-sch, sch + 1)), key=lambda v: v[0])
        nullk = [ncc(int(dx / px), int(dy / px)) for dx, dy in ((0.37, 0.23), (-0.41, 0.31), (0.29, -0.43), (-0.33, -0.39))]
        res["fotos"][kid] = dict(fugen_korrelation=round(ncc(0, 0), 3), fugen_korrelation_bester_versatz=round(best[0], 3), versatz_cm=[round(best[1] * px * 100, 1), round(-best[2] * px * 100, 1)],
                                 fugen_korrelation_null=[round(v, 3) for v in nullk], f1=round(f1, 3), reliefkanten_mit_fotokante=round(p, 3), fotokanten_mit_reliefkante=round(r, 3), f1_verschoben_null=round(float(null), 3))
    if len(kf) > 1: res["f1_foto_gegen_foto"] = round(kanten_f1(kf[0], kf[1], tol)[0], 3)
    pre = a.aus or os.path.join(od, "audit", "relief_test"); json.dump(res, open(pre + ".json", "w"), indent=1)
    lx = np.gradient(rel, px, axis=1); lz = np.gradient(rel, px, axis=0)
    def schatt(k): s = 0.75 - 0.5 * k * lx + 0.7 * k * lz; return cv2.cvtColor((np.clip(s, 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    kb = np.zeros((H, W, 3), np.uint8); kb[kf[0]] = (0, 255, 255); kb[kr] = (0, 0, 255); kb[kr & (cv2.dilate(kf[0].astype(np.uint8), np.ones((7, 7))) > 0)] = (0, 255, 0)
    bl = [orth[0], np.full((H, W, 3), 190, np.uint8), schatt(1.0), schatt(3.0), kb]; tx = ["Foto entzerrt", "glatt (Generator)", "Relief 1x", "Relief 3x", "Kanten: gelb Foto, rot/gruen Relief"]
    for b_, t_ in zip(bl, tx): cv2.putText(b_, t_, (6, 22), 0, 0.6, (255, 0, 255), 2)
    cv2.imwrite(pre + ".jpg", np.hstack(bl)); print(json.dumps(res, indent=1)); print("->", pre + ".jpg")


if __name__ == "__main__":
    main()
