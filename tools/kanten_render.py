#!/usr/bin/env python3
"""kanten_render.py - Modell (STL/PLY in Metern, Modellrahmen) aus der Pose eines kalibrierten Fotos rendern, neben das Foto legen.
  kanten_render.py modell.stl dicht_dir ausrichtung foto out.jpg [skala 0.5] [--maske-foto-ohne]
Schattierung = Normale x Sichtrichtung, Tiefe farbig; Mitte = Kantenueberlagerung (Tiefen-/Normalen-Spruenge) auf dem Foto."""
import sys, os, json, numpy as np, cv2, trimesh
def render(m, K, R, t, s, Ra, ta, sc):
    W, H = int(K["W"] * sc), int(K["H"] * sc); fx, fy, cx, cy = K["fx"] * sc, K["fy"] * sc, K["cx"] * sc, K["cy"] * sc
    Rc = np.array(K["R"]); tc = np.array(K["t"]); Cw = -Rc.T @ tc; Cm = ((Cw - ta) @ Ra) / s; Rm = Rc @ Ra.T * 1.0       # x_cam = Rc (s Ra^T Xm + ta) + tc = s*Rc Ra^T Xm + ...
    u, v = np.meshgrid(np.arange(W) + .5, np.arange(H) + .5); d = np.stack([(u - cx) / fx, (v - cy) / fy, np.ones_like(u)], -1).reshape(-1, 3)
    dm = d @ Rm; dm /= np.linalg.norm(dm, axis=1, keepdims=True)
    loc, ri, fi = m.ray.intersects_location(np.tile(Cm, (len(dm), 1)), dm, multiple_hits=False)
    z = np.full(W * H, np.nan); z[ri] = np.linalg.norm(loc - Cm, axis=1); nn = m.face_normals[fi]; sh = np.zeros(W * H); sh[ri] = np.abs((nn * dm[ri]).sum(1))
    return z.reshape(H, W), sh.reshape(H, W)
if __name__ == "__main__":
    a = sys.argv[1:]; sc = float(a[5]) if len(a) > 5 else 0.5; m = trimesh.load(a[0]); K = json.load(open(os.path.join(a[1], "kameras_unverzerrt.json")))[a[3]]
    tr = json.load(open(a[2]))["transformation"]; s = float(tr["s"]); Ra = cv2.Rodrigues(np.array(tr["rvec"], float))[0]; ta = np.array(tr["t"], float)
    z, sh = render(m, K, None, None, s, Ra, ta, sc); H, W = z.shape
    ph = cv2.resize(cv2.imread(os.path.join(a[1], "images", K["bild"])), (W, H)); g = (np.clip(sh, 0, 1) * 220 + 20).astype(np.uint8); g[~np.isfinite(z)] = 255; g = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    zz = np.nan_to_num(z, nan=0); e = (cv2.Canny(cv2.normalize(zz, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8), 30, 90) > 0) | (cv2.Canny((sh * 255).astype(np.uint8), 40, 120) > 0)
    ov = ph.copy(); ov[e] = (0, 0, 255)
    cv2.imwrite(a[4], cv2.hconcat([ph, g, ov]), [cv2.IMWRITE_JPEG_QUALITY, 88]); np.save(a[4].replace(".jpg", "_z.npy"), z)
