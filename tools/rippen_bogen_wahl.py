#!/usr/bin/env python3
"""rippen_bogen_wahl.py - Rippen als Bogenkandidaten auf der Kegelflaeche testen und per Mehrfoto-Gold-Konsens auswaehlen (13.11.2026, modellbasiert statt Skelett).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/rippen_bogen_wahl.py modelle/<objekt>/objekt.json --um -8.47 --kams K-n11_06,K-6130,K-e04,K-6124,K-i08 [--aus DIR]
        [--ac 12.27] [--phi_max 67.5] [--n_ketten 40] [--schwelle 0.55] [--abstand_deg 7]
Kandidat: Bogen von (phi_oben, z=8.12) nach (phi_unten, z=6.45) auf der Achteck-Kegelflaeche (n(z)-Kurve, Radius a(z)/cos(Facettenwinkel)); Profil phi(h) = phi0 + (phi1-phi0) * h^p, p in {0.7, 1.0, 1.6}.
Score = Mittel (Top-3 der Kameras) des lokal normierten Goldwerts G-B entlang des Bogens (Max im 3x3-Umkreis). Auswahl greedy nach Score, Mindestabstand der Bogenmitten in Winkel.
Ausgabe DIR/boegen.json (Bogenparameter + 3D-Pfad u n z + Score), DIR/ueberlagerung_<kam>.jpg (gewaehlte Boegen auf dem Foto). Reine Geometrie + Bildverarbeitung."""
import sys, os, json, glob, math, numpy as np, cv2
a = sys.argv[1:]
if len(a) < 3: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
od = os.path.dirname(os.path.abspath(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); obj = json.load(open(a[0]))
UM = float(opt("--um", 0)); AC = float(opt("--ac", 12.27)); kams = opt("--kams", "").split(","); aus = opt("--aus", "."); os.makedirs(aus, exist_ok=True); PM = float(opt("--phi_max", 67.5))
NK = int(opt("--n_ketten", 40)); THR = float(opt("--schwelle", 0.55)); ABD = float(opt("--abstand_deg", 7)); ZT, ZF = 8.12, 6.45; ax = np.array([0.3338, 0.9426])
nsurf = lambda z: np.interp(z, [6.45, 6.9, 7.2, 7.4, 7.6, 7.8, 8.12], [12.55, 12.70, 13.00, 13.25, 13.43, 13.60, 13.75])
def cam(kid):
    k = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float))
    return dict(R=R, t=np.array(k["t"], float), sh=np.asarray(k.get("rahmen_verschiebung", [0, 0, 0]), float), f=k["f_px"], cx=k["cx"], cy=k["cy"], k1=float(k.get("k1") or 0))
def goldkarte(im, scale):
    g = np.clip(im[..., 1].astype(np.float32) - im[..., 0].astype(np.float32), 0, None); g = cv2.GaussianBlur(g, (0, 0), max(1.0, 0.008 * scale))
    lm = cv2.dilate(g, np.ones((max(5, int(0.25 * scale)) | 1,) * 2)); h = np.clip(g / (lm + 3.0), 0, 1); return cv2.dilate(h, np.ones((3, 3)))
def proj(K, P):
    x = (P + K["sh"]) @ K["R"].T + K["t"]; xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; r2 = xn * xn + yn * yn
    return K["f"] * xn * (1 + K["k1"] * r2) + K["cx"], K["f"] * yn * (1 + K["k1"] * r2) + K["cy"], x[:, 2]
def flaeche(phi_deg, z):
    p = np.radians(phi_deg); w = ((phi_deg + 22.5) % 45.0) - 22.5; a_ = nsurf(z) - AC; r = a_ / np.cos(np.radians(w)); return np.column_stack([UM + r * np.sin(p), AC + r * np.cos(p), z])   # (u,n,z)
def welt(P): return np.column_stack([P[:, 0] * ax[1] + P[:, 1] * ax[0], -P[:, 0] * ax[0] + P[:, 1] * ax[1], P[:, 2]])
Ks = [cam(k) for k in kams]; Is = [cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], k[2:] + "_*"))[0]) for k in kams]
probe = welt(flaeche(np.array([0.0]), np.array([7.3]))); Gs = []
for K, im in zip(Ks, Is): Gs.append(goldkarte(im, float(K["f"] / np.median(proj(K, probe)[2]))))
H = np.linspace(0, 1, 26); Z = ZT - (ZT - ZF) * H; cand = []
phis_o = np.arange(-PM, PM + 1e-9, 4.5); phis_u = np.arange(-60, 60.1, 10.0)
for p0 in phis_o:
    for p1 in phis_u:
        if abs(p1 - p0) > 80: continue
        for pw in (0.7, 1.0, 1.6):
            phi = p0 + (p1 - p0) * H ** pw; P = welt(flaeche(phi, Z)); sc = []
            for K, g in zip(Ks, Gs):
                qx, qy, qz = proj(K, P); ok = (qz > 0) & (qx >= 2) & (qx < g.shape[1] - 3) & (qy >= 2) & (qy < g.shape[0] - 3)
                if ok.sum() < 18: sc.append(0.0); continue
                sc.append(float(g[qy[ok].astype(int), qx[ok].astype(int)].mean()))
            top3 = float(np.mean(sorted(sc)[::-1][:3])); cand.append((top3, p0, p1, pw, sc))
cand.sort(key=lambda c: -c[0]); print("Kandidaten", len(cand), "Score Top/Median:", round(cand[0][0], 2), round(cand[len(cand) // 2][0], 2))
sel = []
for c in cand:
    if c[0] < THR: break
    if all(not (abs(c[1] - s[1]) < ABD and abs(c[2] - s[2]) < ABD * 1.5) for s in sel): sel.append(c)
    if len(sel) >= NK: break
res = []
for c in sel:
    phi = c[1] + (c[2] - c[1]) * H ** c[3]; P = flaeche(phi, Z); res.append(dict(phi_oben=c[1], phi_unten=c[2], p=c[3], score=round(c[0], 3), kam_scores=[round(s, 2) for s in c[4]], pfad=np.round(P, 3).tolist()))
json.dump(res, open(os.path.join(aus, "boegen.json"), "w")); print(len(res), "Boegen gewaehlt (Score >= %.2f):" % THR)
for r in res[:30]: print("  oben %6.1f unten %6.1f p %.1f Score %.2f %s" % (r["phi_oben"], r["phi_unten"], r["p"], r["score"], r["kam_scores"]))
rng = np.random.default_rng(2)
for kid, K, im in zip(kams, Ks, Is):
    o = im.copy(); allq = []
    for r in res:
        P = welt(np.array(r["pfad"])); qx, qy, _ = proj(K, P); col = tuple(int(v) for v in rng.integers(60, 255, 3)); pts = np.column_stack([qx, qy]).astype(np.int32); cv2.polylines(o, [pts], False, col, 3); allq.append(pts)
    allp = np.vstack(allq); x0, y0 = max(allp[:, 0].min() - 80, 0), max(allp[:, 1].min() - 80, 0); x1, y1 = min(allp[:, 0].max() + 80, o.shape[1]), min(allp[:, 1].max() + 80, o.shape[0]); o = o[y0:y1, x0:x1]; h = 900
    cv2.imwrite(os.path.join(aus, "ueberlagerung_%s.jpg" % kid), cv2.resize(o, (int(o.shape[1] * h / o.shape[0]), h)), [cv2.IMWRITE_JPEG_QUALITY, 85])
