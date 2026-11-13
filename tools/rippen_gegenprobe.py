#!/usr/bin/env python3
"""rippen_gegenprobe.py - unabhaengige Messung: liegen die Modell-Rippenbahnen im Foto auf Gold? (13.11.2026)
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tools/rippen_gegenprobe.py modelle/<objekt>/objekt.json BAUTEIL_INDEX --kams K-6225,K-h13 [--du 0.3]
Je Rippenpfad (rippen_pfade.pfade_ohne_spiegel) werden Punkte in jede (nicht zum Einrasten benutzte) Kamera projiziert; Wert = lokal normiertes Gold G-B (Max im 3x3). Nullprobe: Pfade um --du m in u verschoben.
Ausgabe: Mittel, Anteil Punkte mit Gold > 0,5 (Treffer) fuer echt und Null. Reine Geometrie/Bildverarbeitung."""
import sys, os, json, glob, numpy as np, cv2
a = sys.argv[1:]; opt = lambda n, d: a[a.index(n) + 1] if n in a else d
od = os.path.dirname(os.path.abspath(a[0])); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a[0])))); obj = json.load(open(a[0])); ax = np.array([0.3338, 0.9426])
paths = [np.array(e["pfad"]) for e in obj["bauteile"][int(a[1])]["unterbau"]["rippen_pfade"]["pfade_ohne_spiegel"]]; du = float(opt("--du", 0.3))
def welt(P): return np.column_stack([P[:, 0] * ax[1] + P[:, 1] * ax[0], -P[:, 0] * ax[0] + P[:, 1] * ax[1], P[:, 2]])
for kid in opt("--kams", "").split(","):
    k = json.load(open(os.path.join(od, "messprotokoll", kid + ".json")))["kamera"]; R, _ = cv2.Rodrigues(np.array(k["rvec"], float)); t = np.array(k["t"], float); k1 = float(k.get("k1") or 0)
    im = cv2.imread(glob.glob(os.path.join(root, obj["fotos_dir"], kid[2:] + "_*"))[0]).astype(np.float32); g = np.clip(im[..., 1] - im[..., 0], 0, None); g = cv2.GaussianBlur(g, (0, 0), 1.5)
    lm = cv2.dilate(g, np.ones((41, 41))); G = cv2.dilate(np.clip(g / (lm + 3.0), 0, 1), np.ones((3, 3)))
    def wert(shift):
        v = []
        for p in paths:
            P = welt(p + np.array([shift, 0, 0])); x = P @ R.T + t; xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; r2 = xn * xn + yn * yn
            qx = k["f_px"] * xn * (1 + k1 * r2) + k["cx"]; qy = k["f_px"] * yn * (1 + k1 * r2) + k["cy"]; ok = (x[:, 2] > 0) & (qx >= 0) & (qx < G.shape[1] - 1) & (qy >= 0) & (qy < G.shape[0] - 1)
            v += list(G[qy[ok].astype(int), qx[ok].astype(int)])
        return np.array(v)
    e = wert(0.0); nulls = [wert(s) for s in (du, -du, 2 * du, -2 * du)]
    print("%s %d px-Punkte | echt: Mittel %.2f, Treffer(>0,5) %.0f %% | Null(+-%.1f/%.1f m u): Mittel %.2f, Treffer %.0f %%" % (kid, len(e), e.mean(), 100 * (e > 0.5).mean(), du, 2 * du, np.mean([n.mean() for n in nulls]), 100 * np.mean([(n > 0.5).mean() for n in nulls])))
