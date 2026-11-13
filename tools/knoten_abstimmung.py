#!/usr/bin/env python3
"""knoten_abstimmung.py - 3D-Knoten (Rippenkreuzungen) per Mehrfoto-Eckenabstimmung statt Handzuordnung (13.11.2026).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/knoten_abstimmung.py modelle/<objekt>/objekt.json --um -8.47 --kams K-n11_06,K-6130,K-e04,K-6124,K-i08 [--min_kams 4] [--aus DIR]
Ablauf: Gitterpunkte auf der (gemessenen) Kegelflaeche der Erkerfacetten (n(z)-Kurve + Achteck 0/+-45 Grad, +-0,1 m in n) werden in alle Kameras projiziert; je Kamera
Score = Harris-Ecken-Antwort des Goldbilds (metrische Fenstergroesse, Maximum im Umkreis 3 cm). Knoten = Punkt, dessen Score in >= min_kams Kameras hoch ist (Top-k-Mittel,
Verdeckung wird so toleriert). Ausgabe: DIR/knoten.json (Punkte u,n,z + Score + Kameras), DIR/knoten.jpg (Ausschnitte der Bestplatzierten).
Grenze: Flaechenhypothese +-0,1 m in n; Rippen ohne Kreuzung (Enden, Boegen) erzeugen keine Ecke -> nur Knoten, keine Bahnen. Reine Geometrie + Bildverarbeitung."""
import sys, os, json, glob, math, numpy as np, cv2
a = sys.argv[1:]
if len(a) < 3: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
od = os.path.dirname(os.path.abspath(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); obj = json.load(open(a[0]))
UM = float(opt("--um", 0)); kams = opt("--kams", "").split(","); mink = int(opt("--min_kams", 4)); aus = opt("--aus", "."); os.makedirs(aus, exist_ok=True)
ax = np.array([float(opt("--nx", 0.3338)), float(opt("--ny", 0.9426))]); AC, ZT, ZF = float(opt("--ac", 12.27)), 8.12, 6.45
nsurf = lambda z: np.interp(z, [6.45, 6.9, 7.2, 7.4, 7.6, 7.8, 8.12], [12.55, 12.70, 13.00, 13.25, 13.43, 13.60, 13.75])
def cam(kid):
    k = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); sh = np.asarray(k.get("rahmen_verschiebung", [0, 0, 0]), float)
    return dict(R=R, t=np.array(k["t"], float), sh=sh, f=k["f_px"], cx=k["cx"], cy=k["cy"], k1=float(k.get("k1") or 0))
def harris_map(im, scale):
    f = im.astype(np.float32); g = np.clip((f[..., 2] + f[..., 1]) / 2 - f[..., 0], 0, None); g = cv2.GaussianBlur(g, (0, 0), max(1.0, 0.012 * scale))
    bs = max(3, int(0.06 * scale) | 1); h = cv2.cornerHarris(g, bs, 3, 0.04); h = np.clip(h, 0, None); h = cv2.dilate(h, np.ones((max(3, int(0.06 * scale)) | 1,) * 2))   # Max im Umkreis ~3 cm
    return h / (np.percentile(h, 99.7) + 1e-9)
# Gitterpunkte
pts = []
for th in (0, 45, -45):
    T = math.radians(th)
    for z in np.arange(ZF + 0.05, ZT - 0.02, 0.04):
        W = 0.30 + (0.665 - 0.30) * (z - ZF) / (ZT - ZF)
        for du in np.arange(-W, W + 1e-9, 0.04):
            for dr in (-0.08, 0.0, 0.08):
                rho = nsurf(z) - AC + dr; u = UM + rho * math.sin(T) + du * math.cos(T); n = AC + rho * math.cos(T) - du * math.sin(T); pts.append((u, n, z, th))
pts = np.array(pts); P = np.column_stack([pts[:, 0] * ax[1] + pts[:, 1] * ax[0], -pts[:, 0] * ax[0] + pts[:, 1] * ax[1], pts[:, 2]])
S = np.zeros((len(P), len(kams)))
for j, kid in enumerate(kams):
    K = cam(kid); im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0]); x = (P + K["sh"]) @ K["R"].T + K["t"]
    scale = float(np.median(K["f"] / x[:, 2])); H = harris_map(im, scale); ok = x[:, 2] > 0; xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; r2 = xn * xn + yn * yn
    px = K["f"] * xn * (1 + K["k1"] * r2) + K["cx"]; py = K["f"] * yn * (1 + K["k1"] * r2) + K["cy"]; inb = ok & (px >= 0) & (px < im.shape[1] - 1) & (py >= 0) & (py < im.shape[0] - 1)
    S[inb, j] = H[py[inb].astype(int), px[inb].astype(int)]; print(kid, "px/m %.0f" % scale, "im Bild", int(inb.sum()), "von", len(P))
top = np.sort(S, axis=1)[:, ::-1][:, :mink].mean(axis=1); idx = np.argsort(-top)
# Nicht-Maximum-Unterdrueckung 0,12 m
sel = []
for i in idx:
    if top[i] < 0.25: break
    if all(np.linalg.norm(P[i] - P[k]) > 0.12 for k in sel): sel.append(i)
    if len(sel) >= 40: break
res = [dict(u=round(float(pts[i, 0]), 3), n=round(float(pts[i, 1]), 3), z=round(float(pts[i, 2]), 3), facette_grad=int(pts[i, 3]), score=round(float(top[i]), 3), kams=[kams[j] for j in range(len(kams)) if S[i, j] > 0.25]) for i in sel]
json.dump(res, open(os.path.join(aus, "knoten.json"), "w"), indent=1); print(len(res), "Knoten; Top 12:")
for r in res[:12]: print("  u %.2f n %.2f z %.2f Facette %3d Score %.2f Kameras %d" % (r["u"], r["n"], r["z"], r["facette_grad"], r["score"], len(r["kams"])))
