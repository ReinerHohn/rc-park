#!/usr/bin/env python3
"""foto_render_seite.py - Foto | schattierter Modell-Render nebeneinander (Kamera aus kameras.json der gemeinsamen Anpassung).
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_render_seite.py KAMERAS.json AUS.jpg 031 021 ... [--hoch 1400]
Render: Punktwolke (Oberflaeche, 1,2 Mio Punkte), Farbe = Normale gegen Lichtrichtung, Tiefenpuffer (nahester Punkt gewinnt)."""
import sys, json, glob, cv2, numpy as np, trimesh
sys.path.insert(0, __file__.rsplit("/", 1)[0]); import foto_silhouette_gpu as F, foto_profil_gpu as PG
def render(nr, th, hoch, m, P, Nrm):
    im = cv2.imread(glob.glob(F.FD + nr + "_*")[0]); h, w = im.shape[:2]; s = hoch / h; W2, H2 = int(w * s), hoch; k = W2 / 400.
    im = cv2.resize(im, (W2, H2), interpolation=cv2.INTER_AREA); t = np.array(th, float); t[6] *= k; t[7] *= k
    uv, f, d = PG.project(t, 5.4 / 4.29 * 400 * k, W2, H2, P)
    cam = None
    import math
    dd, az, el, tz = t[0], t[1], t[2], t[3]
    cam = np.array([0, 0, tz]) + dd * np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])
    zc = np.linalg.norm(P - cam, axis=1); vdir = (cam - P) / zc[:, None]; lit = np.clip((Nrm * vdir).sum(1), 0, 1)
    sh = (60 + 190 * np.clip(0.3 * lit + 0.7 * np.clip((Nrm * np.array([0.4, -0.5, 0.75])).sum(1), 0, 1), 0, 1)).astype(np.uint8)
    img = np.full((H2, W2, 3), 235, np.uint8); zb = np.full((H2, W2), 1e9); order = np.argsort(-zc)
    for i in order[::1]:
        u, v = int(uv[i, 0]), int(uv[i, 1])
        if 0 <= u < W2 and 0 <= v < H2 and lit[i] > 0.05 and zc[i] < zb[v, u] + 0.3: zb[v, u] = min(zb[v, u], zc[i]); img[max(0, v - 1):v + 1, max(0, u - 1):u + 1] = (sh[i], sh[i], sh[i])
    return np.hstack([im, img])
if __name__ == "__main__":
    a = sys.argv[1:]; hoch = 1400
    if "--hoch" in a: i = a.index("--hoch"); hoch = int(a[i + 1]); a = a[:i] + a[i + 2:]
    kam = json.load(open(a[0])); out = a[1]; nrs = a[2:]
    m = trimesh.load("modelle/stl/martinstor_v4_1-87.stl"); m.apply_scale(87 / 1000.0); c = m.bounds.mean(0); m.apply_translation([-c[0], -c[1], -m.bounds[0, 2]])
    P, fi = trimesh.sample.sample_surface(m, 1200000, seed=0); Nrm = m.face_normals[fi]
    rows = [render(nr, kam[nr]["th"], hoch, m, P, Nrm) for nr in nrs]; cv2.imwrite(out, np.hstack(rows) if len(rows) == 1 else np.vstack(rows) if rows[0].shape[0] < 900 else np.hstack(rows))
