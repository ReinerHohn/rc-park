#!/usr/bin/env python3
"""Synthetischer Test fuer pose_vertrauen.py: /media/oem/scan/venv-colmap/bin/python -I tools/test_pose_vertrauen.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pose_vertrauen as pv

rng = np.random.default_rng(1)
# 1) Rotationswinkel
def rz(a):
    c, s = np.cos(a), np.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
assert abs(pv.rot_winkel_grad(np.eye(3), rz(np.radians(7))) - 7) < 1e-6

# 2) PnP synthetisch: bekannte Pose wird zurueckgewonnen; falsches f verschiebt Zentrum ~ df/f * Tiefe (Annahme der Schwellenableitung)
R = rz(0.3) @ np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float); c = np.array([5., -3., 2.])
t = -R @ c; f, cx, cy = 1400., 1000., 700.
X = rng.uniform(-15, 15, (400, 3)) + R.T @ np.array([0, 0, 30.]) + c
uv, z = pv.projiziere(R, t, f, cx, cy, 0.0, X)
ok = (z > 1) & (abs(uv[:, 0] - cx) < 1000) & (abs(uv[:, 1] - cy) < 700); uv, X, z = uv[ok], X[ok], z[ok]
uv = uv + rng.normal(0, 0.5, uv.shape)
r = pv.pnp(uv, X, (f, cx, cy, 0.0), 2000, 1400, 1.0)
assert np.linalg.norm(r["c"] - c) < 0.05, r["c"]
r2 = pv.pnp(uv, X, (f, cx, cy, 0.0), 2000, 1400, 1.02)
err = np.linalg.norm(r2["c"] - c); erw = 0.02 * np.median(z)
assert 0.5 * erw < err < 1.6 * erw, (err, erw)
print("PnP ok: exakt %.3f m, f+2%% %.2f m (erwartet ~%.2f)" % (np.linalg.norm(r["c"] - c), err, erw))

# 3) Schwelle aus Kreuz: Fehler steigt mit d -> d_max liegt davor
zl = [{"d": d, "fehler_m": e} for d in (0, 2, 4, 6) for e in (0.01 * (d + 1),) * 10]
d_ok, tab = pv.schwelle_aus_kreuz(zl, 0.05)
assert d_ok == 4, (d_ok, tab)
assert pv.schwelle_aus_kreuz(zl, 0.001)[0] is None

# 4) Klassifikation: gute Pose sicher, Ausreisser (15 m Abweichung) unbrauchbar, grosser Abstand unsicher, nur ein Lauf unsicher
s = {"abstand_sicher_m": 12., "abstand_unbrauchbar_m": None, "abw_sicher_m": .1, "abw_unbrauchbar_m": .5, "abw_sicher_grad": .06,
     "inlier_min": 30, "inlier_sicher": 30}
gut = {"inlier": 300, "abstand_ref_m": 3., "pose_abw_m": .05, "pose_abw_grad": .05}
assert pv.klassifiziere(gut, s)[0] == "sicher"
assert pv.klassifiziere(dict(gut, pose_abw_m=15.), s)[0] == "unbrauchbar"
assert pv.klassifiziere(dict(gut, abstand_ref_m=15.), s)[0] == "unsicher"
assert pv.klassifiziere(dict(gut, nur_ein_lauf=True), s)[0] == "unsicher"
assert pv.klassifiziere(dict(gut, inlier=10), s)[0] == "unbrauchbar"
print("alle Tests bestanden")
