#!/usr/bin/env python3
"""element_front.py - Frontansicht (orthogonal, Malerverfahren, Lichtschattierung) eines STL (mm, 1:87) auf eine Fassadenebene (fassaden.json) fuer den Sichtvergleich
neben dem Ortho/Foto. Aufruf: element_front.py FASSADEN_JSON FID AUS.jpg STL [STL...] [--ortho ortho.png]  (mehrere STL nebeneinander, darunter das Ortho)"""
import sys, json, numpy as np, cv2, trimesh


def front(stl, F, massstab=87.0, zelle=0.025, tmin=-8.0, tmax=3.0):
    m = trimesh.load(stl); V = np.asarray(m.vertices) * massstab / 1000.0; fc = np.asarray(m.faces)
    o = np.array(F["o"]); n = np.array(F["n"]); d = np.array(F["d"]); r = F["raster"]
    u = (V[:, :2] - o) @ d; t = (V[:, :2] - o) @ n; z = V[:, 2]
    W = int((r["nu"] * r["zelle"]) / zelle); H = int((r["nz"] * r["zelle"]) / zelle)
    X = (u - r["u0"]) / zelle; Y = (r["z1"] - z) / zelle
    tri = fc; tm = t[tri].mean(1); keep = (tm > tmin) & (tm < tmax) & (X[tri].max(1) > 0) & (X[tri].min(1) < W) & (Y[tri].max(1) > 0) & (Y[tri].min(1) < H)
    tri = tri[keep]; tm = tm[keep]; order = np.argsort(tm)           # klein (hinten) zuerst, vorn zuletzt
    nv = np.cross(V[tri[:, 1]] - V[tri[:, 0]], V[tri[:, 2]] - V[tri[:, 0]]); nv /= (np.linalg.norm(nv, axis=1, keepdims=True) + 1e-12)
    licht = np.array([0.35, -0.45, 0.82]); lic = np.abs(nv @ licht); img = np.full((H, W, 3), 235, np.uint8)
    for k in order:       # Farbe = Tiefe hinter der Fassadenebene (t): Oeffnungen/Laibung dunkel, Wandflaeche hell; Schattierung nur leicht
        c = int(np.clip(235 + tm[k] * 38, 25, 250) * (0.8 + 0.2 * lic[k])); p = np.c_[X[tri[k]], Y[tri[k]]].astype(np.int32)
        cv2.fillConvexPoly(img, p, (c, c, c))
    return img


def main():
    a = sys.argv[1:]; ortho = None
    if "--ortho" in a: i = a.index("--ortho"); ortho = a[i + 1]; del a[i:i + 2]
    FA = json.load(open(a[0]))["fassaden"]; F = next(f for f in FA if f["id"] == a[1]); aus = a[2]; bilder = [front(s, F) for s in a[3:]]
    if ortho:
        o = cv2.imread(ortho); bilder.append(cv2.resize(o, (bilder[0].shape[1], bilder[0].shape[0])))
    y0 = int(bilder[0].shape[0] * 0.5); out = np.vstack([b[y0:] for b in bilder])
    cv2.imwrite(aus, out, [cv2.IMWRITE_JPEG_QUALITY, 90]); print(aus, out.shape)


if __name__ == "__main__":
    main()
