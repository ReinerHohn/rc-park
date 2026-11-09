#!/usr/bin/env python3
"""modell_foto_overlay.py --stl x.stl --fotos kameras_netz.json --bilder dir --foto name.jpg [--wolke w.npy] --out jpg [--verdeckt aus|gestrichelt|alle] [--winkel 0.6]
Ganzes Modell (rot) + optional Wolke (gelb) in ein kalibriertes Foto projiziert - zum ANSEHEN (Regel 3/9d, Nutzer 8.11.: 'Bildfeedback ist richtig geil').

Verdeckung (Koordinator Runde 5, 2026-11-09): vorher wurden ALLE Knickkanten gezeichnet -> Dachziegelreihen erschienen durch die Fassade, ein Rueckwandfenster
hinter einem Pfeiler sah aus wie ein 'schiefes Viereck'. Jetzt: Z-Puffer des Modells exakt auf der GPU gerastert (render_kern.dreiecke_rastern, wie foto_diff --raster),
jede Kante in Stuecke ~3 px zerlegt, ein Stueck ist sichtbar, wenn seine Kameratiefe <= Z-Puffer + tol (max(0,05 m, 0,5 % der Tiefe), Pruefpunkt 1 px neben der Kante
in beiden Flaechenrichtungen, damit die eigene Kante nicht an der Nachbarflaeche scheitert). Zusaetzlich Umrisskanten (eine Flaeche zur Kamera, die andere abgewandt):
Zylinder/Kegel zeigen jetzt ihre Silhouette statt nur Ringe. --verdeckt: aus (Standard) = verdeckte Stuecke weglassen, gestrichelt = duenn/gestrichelt, alle = altes Verhalten."""
import os, sys, json, argparse, numpy as np, cv2, trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument("--stl", required=True); ap.add_argument("--fotos", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--foto", required=True)
ap.add_argument("--wolke"); ap.add_argument("--out", required=True); ap.add_argument("--winkel", type=float, default=0.6)
ap.add_argument("--verdeckt", default="aus", choices=["aus", "gestrichelt", "alle"]); ap.add_argument("--massstab", type=float, default=87.0); a = ap.parse_args()
k = json.load(open(a.fotos))[a.foto]; R = np.array(k["Rn"], float); t = np.array(k["tn"], float).ravel(); im = cv2.imread(a.bilder + "/" + a.foto, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
H, W = im.shape[:2]; f, cx, cy = float(k["f"]), float(k["cx"]), float(k["cy"])
def pr(P): X = P @ R.T + t; z = np.maximum(X[:, 2], 1e-3); return f * X[:, :2] / z[:, None] + [cx, cy], X[:, 2]
if a.wolke:
    P = np.load(a.wolke)[:, :3][::3]; uv, z = pr(P)
    for (u, v), zz in zip(uv, z):
        if zz > 1 and 0 <= u < W and 0 <= v < H: cv2.circle(im, (int(u), int(v)), 3, (0, 255, 255), -1)
m = trimesh.load(a.stl, process=False); m.apply_scale(a.massstab / 1000); mm = m.copy(); mm.merge_vertices(); V = np.asarray(mm.vertices)
C = -R.T @ t                                                                                       # Kamerazentrum (Welt)
fa = mm.face_adjacency; Nf = mm.face_normals; Fc = mm.triangles_center
vor = ((C[None] - Fc) * Nf).sum(1) > 0                                                             # Flaeche zur Kamera gewandt
knick = mm.face_adjacency_angles > a.winkel; umriss = vor[fa[:, 0]] != vor[fa[:, 1]]
sel = knick | umriss; ed = mm.face_adjacency_edges[sel]; fpaar = fa[sel]
if a.verdeckt == "alle":
    sicht = None
else:
    import torch, render_kern as RK
    depth, _, _ = RK.dreiecke_rastern(mm, R, t, f, cx, cy, W, H, als_torch=True)
    D = torch.as_tensor(np.asarray(depth.cpu() if hasattr(depth, "cpu") else depth, np.float32), device="cuda")
    p0, _ = pr(V[ed[:, 0]]); p1, _ = pr(V[ed[:, 1]]); L = np.linalg.norm(p1 - p0, axis=1); ns = np.clip(np.ceil(L / 3.0), 1, 4000).astype(int)
    ei = np.repeat(np.arange(len(ed)), ns); off = np.arange(ns.sum()) - np.repeat(np.cumsum(ns) - ns, ns); s = (off + 0.5) / np.repeat(ns, ns)
    Pw = V[ed[ei, 0]] * (1 - s)[:, None] + V[ed[ei, 1]] * s[:, None]
    def tiefe_ok(P3):
        X = P3 @ R.T + t; z = X[:, 2]; u = np.round(f * X[:, 0] / np.maximum(z, 1e-3) + cx).astype(int); v = np.round(f * X[:, 1] / np.maximum(z, 1e-3) + cy).astype(int)
        drin = (z > 1) & (u >= 0) & (u < W) & (v >= 0) & (v < H); ok = np.zeros(len(P3), bool)
        if drin.any():
            dz = D[torch.as_tensor(v[drin], device="cuda"), torch.as_tensor(u[drin], device="cuda")].cpu().numpy()
            ok[drin] = z[drin] <= dz + np.maximum(0.05, 0.005 * z[drin])
        return ok
    eps = 0.02                                                                                      # 2 cm in jede angrenzende Flaeche hinein (Kante selbst liegt auf zwei Flaechen)
    sicht = tiefe_ok(Pw)
    for j in (0, 1):
        Fi = fpaar[ei, j]; sicht |= tiefe_ok(Pw + (Fc[Fi] - Pw) / np.maximum(np.linalg.norm(Fc[Fi] - Pw, axis=1, keepdims=True), 1e-9) * eps)
    del D; torch.cuda.empty_cache()
if sicht is None:
    p0, z0 = pr(V[ed[:, 0]]); p1, z1 = pr(V[ed[:, 1]])
    for q0, q1, a0, a1 in zip(p0, p1, z0, z1):
        if a0 > 1 and a1 > 1: cv2.line(im, (int(q0[0]), int(q0[1])), (int(q1[0]), int(q1[1])), (0, 0, 255), 3)
else:
    pa, za = pr(V[ed[:, 0]]); pb, zb = pr(V[ed[:, 1]]); vorne = np.repeat((za > 1) & (zb > 1), ns)
    nsr = np.repeat(ns, ns); A_ = pa[ei] + (pb - pa)[ei] * (off / nsr)[:, None]; B_ = pa[ei] + (pb - pa)[ei] * ((off + 1) / nsr)[:, None]
    A_ = np.round(A_).astype(np.int64); B_ = np.round(B_).astype(np.int64); gross = (np.abs(A_) < 10**6).all(1) & (np.abs(B_) < 10**6).all(1)
    for i in np.nonzero(sicht & vorne & gross)[0]: cv2.line(im, (int(A_[i, 0]), int(A_[i, 1])), (int(B_[i, 0]), int(B_[i, 1])), (0, 0, 255), 3)
    if a.verdeckt == "gestrichelt":
        for i in np.nonzero(~sicht & vorne & gross & (off % 2 == 0))[0]: cv2.line(im, (int(A_[i, 0]), int(A_[i, 1])), (int(B_[i, 0]), int(B_[i, 1])), (255, 160, 0), 1)
    print(f"Kanten {len(ed)} (Knick {int(knick.sum())}, Umriss {int((umriss & ~knick).sum())}), Stuecke sichtbar {sicht.mean():.1%}")
cv2.imwrite(a.out, cv2.resize(im, None, fx=0.4, fy=0.4)); print("geschrieben", a.out)
