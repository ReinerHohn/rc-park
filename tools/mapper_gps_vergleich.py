#!/usr/bin/env python3
"""mapper_gps_vergleich.py FOTOORDNER SPARSE_A SPARSE_B ... - SfM-Modelle ohne LoD2 gegen Foto-GPS vergleichen (15.11.): gemeinsame eigene Fotos, robuste 2D-Aehnlichkeit je Modell, GPS-Rest; Anteil > 15 m = falsch angesetzte Bildgruppen."""
import pycolmap, numpy as np, sys, os
from PIL import Image
fd, mods = sys.argv[1], sys.argv[2:]
def gps(f):
    try:
        g = (Image.open(PFAD.get(f, os.path.join(fd, f)))._getexif() or {}).get(34853); dm = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
        la, lo = dm(g[2]), dm(g[4]); return np.array([(lo - 7.85) * 111320 * np.cos(np.radians(la)), (la - 47.99) * 110574])
    except Exception: return None
PFAD = {os.path.basename(x): x for x in __import__('glob').glob(os.path.join(fd, '**', '*'), recursive=True)}   # Unterordner (Kamera je Ordner)
C = {}
for m in mods:
    r = pycolmap.Reconstruction(m); C[m] = {os.path.basename(im.name): im.projection_center() for im in r.images.values() if im.has_pose}
gem = sorted(set.intersection(*[set(c) for c in C.values()])); P = {k: gps(k) for k in gem}; keys = [k for k in gem if P[k] is not None and ("eigen" in k or k.startswith("IMG_"))]
print("gemeinsame eigene Fotos mit GPS:", len(keys))
Y = np.array([P[k] for k in keys])
for m in mods:
    X = np.array([C[m][k] for k in keys]); Xc = X - np.median(X, 0); _, _, Vt = np.linalg.svd(Xc, full_matrices=False); X2 = Xc @ Vt[:2].T; best = None
    for sp in (1, -1):
        Z = X2 * [1, sp]; sel = np.ones(len(Z), bool)
        for _ in range(6):
            mx, my = Z[sel].mean(0), Y[sel].mean(0); U, S_, V2 = np.linalg.svd((Y[sel] - my).T @ (Z[sel] - mx) / sel.sum()); D = np.diag([1, np.sign(np.linalg.det(U @ V2))]); R = U @ D @ V2; s = np.trace(np.diag(S_) @ D) / (Z[sel] - mx).var(0).sum()
            r = np.linalg.norm((s * (R @ (Z - mx).T)).T + my - Y, axis=1); sel = r < max(2.5 * np.median(r), 10)
        if best is None or np.median(r) < np.median(best): best = r
    r = best; print(f"{'/'.join(m.rstrip('/').split('/')[-3:])}: GPS-Rest Median {np.median(r):.1f} m, p75 {np.percentile(r,75):.1f}, p90 {np.percentile(r,90):.1f}, Anteil > 15 m {np.mean(r>15)*100:.0f} % ({int((r>15).sum())} Fotos)")
