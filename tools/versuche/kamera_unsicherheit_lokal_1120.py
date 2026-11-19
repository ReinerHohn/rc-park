# Unsicherheit je Kamera lokal: Punkte fest, 6 Lageparameter, numerische Jacobi der Rueckprojektion -> Kovarianz des Kamerazentrums (Anteil der Szenengroesse)
import pycolmap, numpy as np, glob
V = "/media/oem/rcdaten/tmp/colmap_ab"
def gross(n): ms = sorted(glob.glob(f"{V}/{n}/sparse/*/")); return max((pycolmap.Reconstruction(m) for m in ms), key=lambda r: r.num_reg_images())
ref = gross("alt"); C = {i.name: i.projection_center() for i in ref.images.values()}; gr = np.ptp(np.array(list(C.values())), 0).max()
def ume(P, Q):
    mp, mq = P.mean(0), Q.mean(0); U, S, Vt = np.linalg.svd((Q - mq).T @ (P - mp)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ D @ Vt; s = (S * np.diag(D)).sum() / ((P - mp) ** 2).sum(); return s, R, mq - s * R @ mp
sprung = {k: 0.0 for k in C}
for n in ("neu", "neu_wdh", "neu_ceres", "neu_ceres_kovarianz", "alt_ceres"):
    g = {i.name: i.projection_center() for i in gross(n).images.values()}; k = sorted(set(g) & set(C)); P = np.array([g[x] for x in k]); Q = np.array([C[x] for x in k])
    for _ in range(3):
        s, R, t = ume(P, Q); d = np.linalg.norm(s * P @ R.T + t - Q, axis=1); m = d < 5 * np.median(d); s, R, t = ume(P[m], Q[m])
    for x, dd in zip(k, np.linalg.norm(s * P @ R.T + t - Q, axis=1) / gr): sprung[x] = max(sprung[x], dd)
def rodr(w):
    th = np.linalg.norm(w)
    if th < 1e-12: return np.eye(3)
    k = w / th; K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]); return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K
u = {}; npkt = {}
for im in ref.images.values():
    obs = [(p.xy, ref.points3D[p.point3D_id].xyz) for p in im.points2D if p.has_point3D()]
    if len(obs) < 10: continue
    x = np.array([o[0] for o in obs]); X = np.array([o[1] for o in obs]); cam = ref.cameras[im.camera_id]; T = im.cam_from_world(); R0 = T.rotation.matrix(); c0 = im.projection_center()
    def proj(p):
        R = rodr(p[:3]) @ R0; c = c0 + p[3:]; Xc = (X - c) @ R.T; return np.asarray(cam.img_from_cam(Xc))
    f0 = proj(np.zeros(6)); ok = np.isfinite(f0).all(1) & (((X - c0) @ R0.T)[:, 2] > 0); x, X = x[ok], X[ok]
    if len(x) < 10: continue
    f0 = proj(np.zeros(6)); J = np.zeros((2 * len(x), 6)); h = np.r_[np.full(3, 1e-6), np.full(3, 1e-6 * gr)]
    for j in range(6):
        e = np.zeros(6); e[j] = h[j]; J[:, j] = ((proj(e) - proj(-e)) / (2 * h[j])).ravel()
    if not np.isfinite(J).all(): continue
    r = (f0 - x).ravel(); sig2 = max(r @ r / max(1, len(r) - 6), 0.25)
    try: S = np.linalg.inv(J.T @ J) * sig2
    except np.linalg.LinAlgError: S = np.full((6, 6), np.inf)
    u[im.name] = float(np.sqrt(np.trace(S[3:, 3:]))) / gr; npkt[im.name] = len(x)
k = sorted(set(u) & set(sprung)); us = np.array([u[x] for x in k]); sp = np.array([sprung[x] for x in k])
from scipy.stats import spearmanr
print(f"{len(k)} Kameras; Unsicherheit Zentrum Median {1e6*np.median(us):.1f} ppm, p95 {1e6*np.percentile(us,95):.1f} ppm der Szene; Rangkorrelation mit Sprung {spearmanr(us, sp)[0]:.2f}")
import os; spr = sp > float(os.environ.get("GRENZE", "0.01"))
for q in (90, 95, 99): print(f"  springend {spr.sum()}; davon unter den unsichersten {100-q} %: {(spr & (us >= np.percentile(us, q))).sum()}")
for x in np.array(k)[spr]: print(f"   {x[:55]}: Sprung {100*sprung[x]:.1f} %, Unsicherheits-Rang {100*(us < u[x]).mean():.0f}. Perzentil, {npkt[x]} Punkte")
