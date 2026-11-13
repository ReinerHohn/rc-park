#!/usr/bin/env python3
"""rippen_pfad_snap.py - handgesetzte Wegpunkte (Ref-Foto, Vollbild-px) auf Goldgrat einrasten + Tiefe per Mehrfoto-Gold-Konsens (13.11.2026).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/rippen_pfad_snap.py modelle/<objekt>/objekt.json --ref K-n11_06 --kams K-6130,K-e04,K-6124,K-i08 --wege wege.json --box u0 u1 n0 n1 z0 z1 [--aus DIR]
wege.json: {"name": [[x,y],...]} Wegpunkte in Vollbild-px der Ref. Pfad = minimale Kosten (1-Gold) zwischen Wegpunkten (skimage route_through_array); je 4. Pfadpunkt Tiefe wie rippen_skelett_tiefe.py (Gold im Mittel der Gegenkameras).
Ausgabe DIR/wege3d.json {name: {px:[[x,y]], uzn:[[u,n,z]], score:[..]}}, DIR/snap_<ref>.jpg (Pfade farbig + Name). Reine Geometrie/Bildverarbeitung."""
import sys, os, json, glob, numpy as np, cv2
from skimage.graph import route_through_array
a = sys.argv[1:]
if len(a) < 6: sys.exit(__doc__)
opt = lambda n, d: a[a.index(n) + 1] if n in a else d
od = os.path.dirname(os.path.abspath(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); obj = json.load(open(a[0]))
ref = opt("--ref", None); kams = opt("--kams", "").split(","); aus = opt("--aus", "."); os.makedirs(aus, exist_ok=True); W = json.load(open(opt("--wege", "wege.json")))
i = a.index("--box"); u0, u1, n0, n1, z0, z1 = (float(v) for v in a[i + 1:i + 7]); ax = np.array([0.3338, 0.9426])
def cam(kid):
    k = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float))
    return dict(R=R, t=np.array(k["t"], float), sh=np.asarray(k.get("rahmen_verschiebung", [0, 0, 0]), float), f=k["f_px"], cx=k["cx"], cy=k["cy"], k1=float(k.get("k1") or 0))
def foto(kid): return cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0])
def goldkarte(im, scale):
    g = np.clip(im[..., 1].astype(np.float32) - im[..., 0].astype(np.float32), 0, None); g = cv2.GaussianBlur(g, (0, 0), max(1.0, 0.008 * scale))
    lm = cv2.dilate(g, np.ones((max(5, int(0.25 * scale)) | 1,) * 2)); return np.clip(g / (lm + 3.0), 0, 1)
def proj(K, P):
    x = (P + K["sh"]) @ K["R"].T + K["t"]; xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; r2 = xn * xn + yn * yn
    return K["f"] * xn * (1 + K["k1"] * r2) + K["cx"], K["f"] * yn * (1 + K["k1"] * r2) + K["cy"], x[:, 2]
def strahl(K, px, py):
    x, y = (px - K["cx"]) / K["f"], (py - K["cy"]) / K["f"]; xu, yu = x, y
    for _ in range(10): r2 = xu * xu + yu * yu; xu, yu = x / (1 + K["k1"] * r2), y / (1 + K["k1"] * r2)
    d = np.stack([xu, yu, np.ones_like(xu)], 1) @ K["R"]; d /= np.linalg.norm(d, axis=1, keepdims=True); c = -K["R"].T @ K["t"] - K["sh"]; return c, d
UM = float(opt("--um", 0)); AC = float(opt("--ac", 12.27)); BAND = float(opt("--band", 0.12)); PHIM = float(opt("--phi_max", 72.5)); nsurf = lambda z: np.interp(z, [6.45, 6.9, 7.2, 7.4, 7.6, 7.8, 8.12], [12.55, 12.70, 13.00, 13.25, 13.43, 13.60, 13.75])
Kr = cam(ref); Ir = foto(ref); allk = [cam(k) for k in kams]; Is = [foto(k) for k in kams]
ec = np.array([[u * ax[1] + n * ax[0], -u * ax[0] + n * ax[1], z] for u in (u0, u1) for n in (n0, n1) for z in (z0, z1)]); scale_r = float(Kr["f"] / np.median(proj(Kr, ec)[2]))
Gr = goldkarte(Ir, scale_r); cost = 1.0 - np.clip(cv2.GaussianBlur(Gr, (0, 0), 2), 0, 1) + 0.02
Gs = [goldkarte(im, float(K["f"] / 5.0)) for im, K in zip(Is, allk)]; ts = np.arange(1.5, 45, 0.01); out = {}
for name, wp in W.items():
    path = []
    for p, q in zip(wp[:-1], wp[1:]):
        r, _ = route_through_array(cost, (int(p[1]), int(p[0])), (int(q[1]), int(q[0])), fully_connected=True, geometric=True); path += r if not path else r[1:]
    pts = np.array(path)[:, ::-1][::4].astype(float); c, d = strahl(Kr, pts[:, 0], pts[:, 1]); U = []; S = []
    for j in range(len(pts)):
        P = c + d[j][None, :] * ts[:, None]; u = P[:, 0] * ax[1] - P[:, 1] * ax[0]; n = P[:, 0] * ax[0] + P[:, 1] * ax[1]; z_ = P[:, 2]; dx_, dn_ = u - UM, n - AC; rho = np.hypot(dx_, dn_); phi = np.degrees(np.arctan2(dx_, dn_)); w_ = ((phi + 22.5) % 45.0) - 22.5; rs = (nsurf(np.clip(z_, 6.45, 8.12)) - AC) / np.cos(np.radians(w_))
        ok = (np.abs(phi) <= PHIM) & (z_ > z0) & (z_ < z1) & (np.abs(rho - rs) < BAND)   # Tiefenband um die gemessene Achteck-Kegelflaeche
        if not ok.any(): U.append([np.nan] * 3); S.append(0); continue
        P = P[ok]; sc = np.zeros(len(P)); N = np.zeros(len(P))
        for K, g in zip(allk, Gs):
            qx, qy, qz = proj(K, P); inb = (qz > 0) & (qx >= 2) & (qx < g.shape[1] - 3) & (qy >= 2) & (qy < g.shape[0] - 3); v = np.zeros(len(P)); xi, yi = qx[inb].astype(int), qy[inb].astype(int)
            v[inb] = np.maximum.reduce([g[yi + dy, xi + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)]); sc += v; N += inb
        sc = np.where(N >= 2, sc / np.maximum(N, 1), 0); k = int(np.argmax(sc)); Q = P[k]; U.append([Q[0] * ax[1] - Q[1] * ax[0], Q[0] * ax[0] + Q[1] * ax[1], Q[2]]); S.append(float(sc[k]))
    out[name] = dict(px=pts.tolist(), uzn=np.round(np.array(U), 3).tolist(), score=np.round(S, 2).tolist()); print(name, len(pts), "Punkte, Score-Median %.2f" % np.median(S), "gueltig", int(np.isfinite(np.array(U)[:, 0]).sum()))
json.dump(out, open(os.path.join(aus, "wege3d.json"), "w"))
o = Ir.copy(); rng = np.random.default_rng(5)
for name, r in out.items():
    col = tuple(int(v) for v in rng.integers(0, 255, 3)); cv2.polylines(o, [np.array(r["px"], np.int32)], False, (255, 0, 255), 4); p0 = r["px"][len(r["px"]) // 2]; cv2.putText(o, name, (int(p0[0]) + 8, int(p0[1])), 0, 1.4, (0, 255, 255), 3)
qa, qb, _ = proj(Kr, ec); o = o[int(max(qb.min() - 30, 0)):int(qb.max() + 30), int(max(qa.min() - 30, 0)):int(qa.max() + 30)]; cv2.imwrite(os.path.join(aus, "snap_%s.jpg" % ref), cv2.resize(o, (int(o.shape[1] * 1500 / o.shape[0]), 1500)))
