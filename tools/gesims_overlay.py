#!/usr/bin/env python3
"""gesims_overlay.py - Profil-Leiste (Querschnitt n,z, entlang u) in Fotos projizieren: Schnittkanten an u0/u1 + Laengskanten (rot) und optional Wolkenscheibe (gelb).
  gesims_overlay.py --kam KAM.json --bilder DIR --foto NAME.jpg --out OUT.jpg --achse_n nx ny --profil "n,z;n,z;..." --u0 A --u1 B [--wolke W.npy] [--alt "n0,n1,z0,z1,u0,u1"]
Generisch (keine Objektnamen). Ausschnitt = Bounding-Box der projizierten Leiste + Rand. --alt zeichnet zusaetzlich einen Quader (blau) zum Vorher/Nachher-Vergleich."""
import json, sys, argparse, numpy as np, cv2
ap = argparse.ArgumentParser(); ap.add_argument("--kam", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--foto", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--achse_n", nargs=2, type=float, required=True); ap.add_argument("--profil", required=True); ap.add_argument("--u0", type=float, required=True); ap.add_argument("--u1", type=float, required=True)
ap.add_argument("--wolke"); ap.add_argument("--alt"); ap.add_argument("--rand", type=int, default=150); a = ap.parse_args()
k = json.load(open(a.kam)); k = k.get("kameras", k)[a.foto]; R = np.array(k["Rn"]); t = np.array(k["tn"]); f, cx, cy, k1 = k["f"], k["cx"], k["cy"], (k["params"][3] if len(k.get("params", [])) > 3 else 0.0)
n = np.array(a.achse_n); n = n / np.linalg.norm(n); u = np.array([n[1], -n[0]])
def XYZ(uu, nn, zz): uu, nn, zz = map(np.asarray, (uu, nn, zz)); return np.stack([uu * u[0] + nn * n[0], uu * u[1] + nn * n[1], zz * np.ones_like(uu * 1.0)], -1)
def proj(P):
    X = (R @ P.T).T + t; x = X[:, :2] / X[:, 2:3]; r2 = (x ** 2).sum(1, keepdims=True); x = x * (1 + k1 * r2); return x * f + [cx, cy], X[:, 2]
im = cv2.imread(f"{a.bilder}/{a.foto}"); H, Wd = im.shape[:2]
pr = [tuple(map(float, s.split(","))) for s in a.profil.split(";")]
def kanten(prof, u0, u1, col, dick=2):
    for (n1, z1), (n2, z2) in zip(prof, prof[1:] + prof[:1]):
        for uu in (u0, u1):                                           # Schnittkanten an den Enden
            A, _ = proj(XYZ(np.array([uu, uu]), np.array([n1, n2]), np.array([z1, z2]))); cv2.line(im, tuple(map(int, A[0])), tuple(map(int, A[1])), col, dick)
    for n1, z1 in prof:                                                # Laengskanten
        A, _ = proj(XYZ(np.linspace(u0, u1, 60), np.full(60, n1), np.full(60, z1))); cv2.polylines(im, [A.astype(np.int32)], False, col, dick)
if a.wolke:
    W = np.load(a.wolke, mmap_mode="r")[:, :3].astype(np.float32); Wn = W[:, :2] @ n; Wu = W[:, :2] @ u
    s = (Wu > a.u0 - 0.5) & (Wu < a.u1 + 0.5) & (Wn > min(p[0] for p in pr) - 0.25) & (Wn < max(p[0] for p in pr) + 0.25) & (W[:, 2] > min(p[1] for p in pr) - 0.3) & (W[:, 2] < max(p[1] for p in pr) + 0.3)
    uv, z = proj(W[s][::3].astype(float)); 
    for p_ in uv[z > 0]: cv2.circle(im, (int(p_[0]), int(p_[1])), 2, (0, 255, 255), -1)
if a.alt:
    n0, n1, z0, z1, u0, u1 = map(float, a.alt.split(",")); kanten([(n0, z0), (n1, z0), (n1, z1), (n0, z1)], u0, u1, (255, 128, 0), 2)
kanten(pr, a.u0, a.u1, (0, 0, 255), 2)
A, _ = proj(XYZ(np.array([a.u0, a.u1, a.u0, a.u1]), np.array([pr[0][0]] * 4), np.array([pr[0][1], pr[0][1], pr[-1][1], pr[-1][1]])))
x0, y0 = np.maximum(A.min(0).astype(int) - a.rand, 0); x1, y1 = np.minimum(A.max(0).astype(int) + a.rand, [Wd, H])
c = im[y0:y1, x0:x1]; s_ = min(3.0, 1800 / max(c.shape[:2])); c = cv2.resize(c, None, fx=s_, fy=s_)
cv2.putText(c, a.foto, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2); cv2.imwrite(a.out, c); print(a.out, c.shape)
