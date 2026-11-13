#!/usr/bin/env python3
"""rippen_pfade_tor.py - Rippenpfade per Fremdfoto-Treffer aussortieren (13.11.2026, Tor statt Augenmass).
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/rippen_pfade_tor.py modelle/<objekt>/objekt.json BAUTEIL_INDEX --kams K-6225,K-h13 [--min 0.4] [--schreiben]
Pfad bleibt, wenn der Mittelwert der Gold-Treffer (> 0,5, 3x3-Max, lokal normiertes G-B) ueber die Kameras (mit Punkten im Bild) >= --min. Ohne --schreiben nur Liste."""
import sys, os, json, glob, numpy as np, cv2
a = sys.argv[1:]; opt = lambda n, d: a[a.index(n) + 1] if n in a else d
od = os.path.dirname(os.path.abspath(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); obj = json.load(open(a[0])); ax = np.array([0.3338, 0.9426]); thr = float(opt("--min", 0.4))
rp = obj["bauteile"][int(a[1])]["unterbau"]["rippen_pfade"]; ents = rp["pfade_ohne_spiegel"]; cams = []
for kid in opt("--kams", "").split(","):
    k = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float)
    im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0]).astype(np.float32); g = cv2.GaussianBlur(np.clip(im[..., 1] - im[..., 0], 0, None), (0, 0), 1.5)
    cams.append((k, R, t, cv2.dilate(np.clip(g / (cv2.dilate(g, np.ones((41, 41))) + 3), 0, 1), np.ones((3, 3)))))
def ev(p, c):
    k, R, t, G = c; W = np.column_stack([p[:, 0] * ax[1] + p[:, 1] * ax[0], -p[:, 0] * ax[0] + p[:, 1] * ax[1], p[:, 2]]); x = W @ R.T + t; xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; r2 = xn * xn + yn * yn; kk = float(k.get("k1") or 0)
    qx = k["f_px"] * xn * (1 + kk * r2) + k["cx"]; qy = k["f_px"] * yn * (1 + kk * r2) + k["cy"]; ok = (qx >= 0) & (qx < G.shape[1] - 1) & (qy >= 0) & (qy < G.shape[0] - 1); return G[qy[ok].astype(int), qx[ok].astype(int)]
keep = []; tot0 = tot1 = 0
for i, e in enumerate(ents):
    p = np.array(e["pfad"]); h = [float((v > 0.5).mean()) for v in (ev(p, c) for c in cams) if len(v)]; m = float(np.mean(h)) if h else 1.0; L = 0.05 * len(p); tot0 += L
    print(i, "L %.2f m" % L, "Treffer", ["%.0f%%" % (100 * x) for x in h], "->", "behalten" if m >= thr else "VERWORFEN")
    if m >= thr: keep.append(e); tot1 += L
print("Pfade %d -> %d, Laenge %.1f -> %.1f m" % (len(ents), len(keep), tot0, tot1))
if "--schreiben" in a:
    rp["pfade_ohne_spiegel"] = keep; rp["quelle_tor"] = "13.11.2026 Pfade mit Fremdfoto-Treffer < %.2f (Kameras %s) verworfen (tools/rippen_pfade_tor.py)" % (thr, opt("--kams", "")); json.dump(obj, open(a[0], "w"), indent=1, ensure_ascii=False)
