#!/usr/bin/env python3
"""Synthetischer Test fuer handy_kalibrieren.py / handy_zoom_verdacht.py: /media/oem/scan/venv-colmap/bin/python -I tools/test_handy_kalibrieren.py
Beweis: (1) f_orig + k1 werden aus Referenzpunkten + Pixeln zurueckgewonnen (Quer- UND Hochformat mit verschiedener Skala, gemeinsame Linse),
(2) ein um 2 % falsches f verschiebt die Posen (Gegenprobe: Methode sieht den f-Fehler), (3) Zoom-Klassifikation, (4) Rotations-Rodrigues."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import handy_kalibrieren as hk
import handy_zoom_verdacht as hz

rng = np.random.default_rng(3)
# Rodrigues gegen scipy
rv = rng.normal(0, .5, (5, 3)); from scipy.spatial.transform import Rotation as Ro
assert np.allclose(hk.rotmat(rv), Ro.from_rotvec(rv).as_matrix(), atol=1e-9)

F_ORIG, K1 = 2800.0, 0.02
# 12 Bilder, 6 quer (skala .5, 2000x1425) 6 hoch (skala .667, 2000x2533); Szene: Fassade mit Tiefenrelief in 25..45 m
M = 12; sk = np.array([.5] * 6 + [2 / 3] * 6); W = 2000; Hs = np.array([1425] * 6 + [2533] * 6)
cx = np.full(M, W / 2); cy = Hs / .95 / 2
Xw = np.stack([rng.uniform(-20, 20, 4000), rng.uniform(0, 25, 4000), 30 + rng.uniform(-6, 6, 4000)], 1)
rv_t = rng.normal(0, .05, (M, 3)); t_t = np.stack([rng.uniform(-8, 8, M), rng.uniform(-3, 3, M), rng.uniform(-3, 3, M)], 1)
uv = []; X = []; idx = []
for i in range(M):
    u, z = hk.projiziere(F_ORIG, K1, cx[i], cy[i], rv_t, t_t, np.full(len(Xw), i), Xw, sk)
    ok = (z > 1) & (u[:, 0] > 0) & (u[:, 0] < W) & (u[:, 1] > 0) & (u[:, 1] < Hs[i] / 1.0 + 0)
    sel = np.where(ok)[0][:350]
    uv.append(u[sel] + rng.normal(0, .5, (len(sel), 2))); X.append(Xw[sel]); idx.append(np.full(len(sel), i))
uv = np.concatenate(uv); X = np.concatenate(X); idx = np.concatenate(idx)
# Start mit falschem f (Posen aus Wahrheit gestoert)
r = hk.fit_gruppe(uv, X, idx, M, cx, cy, rv_t + rng.normal(0, .01, rv_t.shape), t_t + rng.normal(0, .3, t_t.shape), 2500., 0.0, skala=sk)
assert abs(r["f"] / F_ORIG - 1) < 0.01, r["f"]
assert abs(r["k1"] - K1) < 0.02, r["k1"]
print("Fit: f_orig %.1f (Wahrheit %.0f), k1 %.4f (Wahrheit %.3f), RMS %.2f px" % (r["f"], F_ORIG, r["k1"], K1, np.sqrt(np.mean(r["fehler_px"] ** 2))))
# Gegenprobe: f fest 2 % falsch -> Restfehler (RMS) deutlich groesser als beim freien f
r2 = hk.fit_gruppe(uv, X, idx, M, cx, cy, rv_t, t_t, F_ORIG * 1.02, 0.0, frei=(), skala=sk)
e_frei = np.sqrt(np.mean(r["fehler_px"] ** 2)); e_fest = np.sqrt(np.mean(r2["fehler_px"] ** 2))
assert e_fest > 1.5 * e_frei, (e_frei, e_fest)
print("Gegenprobe: f fest +2 %% -> RMS %.2f px gegen %.2f px (frei)" % (e_fest, e_frei))
# Zoom-Klassifikation
assert hz.klassifiziere(1.02, 0.026, .05) == "normal"
assert hz.klassifiziere(1.12, 0.026, .05) == "abweichend"
assert hz.klassifiziere(3.4, 0.026, .05) == "gezoomt"
assert abs(hz.haupt_f([2800, 2790, 2810, 2830, 9500, 9600, 2780]) - 2800) < 40
print("test_handy_kalibrieren: alle Pruefungen bestanden")
