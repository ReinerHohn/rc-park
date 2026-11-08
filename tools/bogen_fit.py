#!/usr/bin/env python3
"""bogen_fit.py - robuster Kreisbogen-Fit je Bogen an die Laibungslinie (bogen_unterkante.py -> unterkante.json), Kontur ZUERST messen, danach benennen.
Schritte: obere Huellkurve (Perzentil 85 ueber 30 cm: Zacken an Pfeilern/Zwickeln nach unten fallen weg) -> Kronen als Maxima ueber 3,5 m Abstand -> je Krone Fenster +-halbe Spannweite ->
RANSAC-Kreis (3 Punkte, 2 cm Toleranz) nur ueber Punkte oberhalb zmin (Pfeilerzone raus) -> Mittelpunkt (u, z), Radius, RMS, Inlierzahl.
Benennung (erst danach): Mittelpunkt auf Kaempferhoehe -> Rundbogen; Mittelpunkt DARUNTER (R > halbe Spannweite) -> Stich-/Segmentbogen. Kaempferhoehe/Spannweite aus Pfeilerlage sind HIER NICHT gemessen (Pfeilerzone leer) -> nur Kronenhoehe, R, Mittelpunkt.
  venv-seg/bin/python -I tools/bogen_fit.py <ordner mit unterkante.json> [--zmin 3.5] [--halb 2.0]"""
import os, sys, json, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("ordner"); ap.add_argument("--zmin", type=float, default=3.5); ap.add_argument("--halb", type=float, default=2.0); ap.add_argument("--tol", type=float, default=0.02); a = ap.parse_args()
J = json.load(open(os.path.join(a.ordner, "unterkante.json"))); u = np.array(J["u"]); z = np.array(J["z_unter"], float); ok = np.isfinite(z); zell = float(np.median(np.diff(u)))
w = int(0.30 / zell); env = np.full_like(z, np.nan)
for i in range(len(z)):
    s = z[max(0, i - w):i + w + 1]; s = s[np.isfinite(s)]
    if len(s) > 3: env[i] = np.percentile(s, 85)
sm = np.array([np.nanmean(env[max(0, i - int(0.2 / zell)):i + int(0.2 / zell) + 1]) for i in range(len(z))])
from scipy.signal import find_peaks
pk, _ = find_peaks(np.nan_to_num(sm, nan=0), distance=int(3.5 / zell), prominence=0.3, height=a.zmin)
rng = np.random.default_rng(0); erg = []
for i in pk:
    m = ok & (np.abs(u - u[i]) <= a.halb) & (z >= a.zmin); P = np.c_[u[m], z[m]]
    if len(P) < 30: continue
    best = None
    for _ in range(3000):
        q = P[rng.choice(len(P), 3, replace=False)]; A = np.c_[2 * q, np.ones(3)]; b = (q ** 2).sum(1)
        try: c = np.linalg.solve(A, b)
        except np.linalg.LinAlgError: continue
        R2 = c[2] + c[0] ** 2 + c[1] ** 2
        if R2 <= 0: continue
        R = np.sqrt(R2)
        if not (1.0 < R < 8.0 and abs(c[0] - u[i]) < 0.35 and c[1] < 4.5): continue                              # Bogen symmetrisch zur Krone (+-35 cm), Mittelpunkt unterhalb 4,5 m
        d = np.abs(np.hypot(P[:, 0] - c[0], P[:, 1] - c[1]) - R); ii = d < a.tol; n = int(ii.sum())
        if ii.sum() < 20 or (P[ii, 0] < c[0]).sum() < 0.25 * n or (P[ii, 0] > c[0]).sum() < 0.25 * n: continue    # beide Flanken muessen tragen (kein Ein-Flanken-Kreis)
        if best is None or n > best[0]: best = (n, c[0], c[1], R)
    if best is None: continue
    n, cu, cz, R = best; d = np.abs(np.hypot(P[:, 0] - cu, P[:, 1] - cz) - R); inl = d < 2 * a.tol
    # Verfeinerung: Kleinste Quadrate auf Inliern
    Q = P[inl]; A = np.c_[2 * Q, np.ones(len(Q))]; b = (Q ** 2).sum(1); c, *_ = np.linalg.lstsq(A, b, rcond=None); R = float(np.sqrt(c[2] + c[0] ** 2 + c[1] ** 2)); cu, cz = float(c[0]), float(c[1])
    rms = float(np.sqrt(np.mean((np.hypot(Q[:, 0] - cu, Q[:, 1] - cz) - R) ** 2)))
    erg.append(dict(u_krone=round(float(u[i]), 2), krone_z=round(cz + R, 3), mittelpunkt_u=round(cu, 3), mittelpunkt_z=round(cz, 3), radius=round(R, 3), rms_cm=round(rms * 100, 2), inlier=int(inl.sum()), punkte=len(P), u_von=round(float(Q[:, 0].min()), 2), u_bis=round(float(Q[:, 0].max()), 2), z_tiefster_inlier=round(float(Q[:, 1].min()), 2)))
json.dump(erg, open(os.path.join(a.ordner, "bogen_fit.json"), "w"), indent=1)
for e in erg: print(e)
if len(erg) > 1:
    ab = np.diff([e["u_krone"] for e in erg]); print("Kronenabstand (m):", np.round(ab, 2).tolist(), "R:", [e["radius"] for e in erg], "Kronenhoehe:", [e["krone_z"] for e in erg])
