#!/usr/bin/env python3
"""bauteil_overlay.py - Overlay EINES Bauteils (Knick-/Umrisskanten) auf kalibrierte Fotos, leicht (kein Z-Puffer gegen Fremdteile; nur fuer freiliegende Teile wie Gauben).
  bauteil_overlay.py KAM.json BILDDIR OUT.jpg --stl TEIL.stl [--stl TEIL2.stl ...] --fotos F1.jpg,F2.jpg,... --um X Y Z [--halb 260] [--massstab 87] [--vergleich TEIL_ALT.stl]
Ein Kachelbild je Foto (Ausschnitt um den Modellpunkt --um, Modellrahmen m). Kanten Rot (--stl), optional Cyan (--vergleich, z. B. alter Stand). Generisch."""
import sys, json, argparse, numpy as np, cv2, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("kam"); ap.add_argument("bilder"); ap.add_argument("out"); ap.add_argument("--stl", action="append", required=True)
ap.add_argument("--vergleich", action="append", default=[]); ap.add_argument("--fotos", required=True); ap.add_argument("--um", nargs=3, type=float, required=True)
ap.add_argument("--halb", type=int, default=260); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--winkel", type=float, default=20.0); ap.add_argument("--faktor", type=float, default=1.6); a = ap.parse_args()
kam = json.load(open(a.kam))
def kanten(files):
    segs = []
    for f in files:
        m = trimesh.load(f, process=False); m.apply_scale(a.massstab / 1000.0)
        E = m.face_adjacency_edges[m.face_adjacency_angles > np.radians(a.winkel)]
        bd = m.edges[trimesh.grouping.group_rows(m.edges_sorted, require_count=1)]
        for e in np.vstack([E, bd]): segs.append(m.vertices[e])
    return np.array(segs)
def proj(k, X):
    x = X @ np.array(k["Rn"]).T + np.array(k["tn"]); xn, yn = x[:, 0] / x[:, 2], x[:, 1] / x[:, 2]; k1 = float(k["params"][3]) if len(k.get("params", [])) > 3 else 0.0; r2 = xn * xn + yn * yn
    return np.stack([k["f"] * xn * (1 + k1 * r2) + k["cx"], k["f"] * yn * (1 + k1 * r2) + k["cy"]], 1)
S1 = kanten(a.stl); S2 = kanten(a.vergleich) if a.vergleich else None; tiles = []
for fo in a.fotos.split(","):
    k = kam[fo]; im = cv2.imread(f"{a.bilder}/{fo}"); u, v = proj(k, np.array([a.um]))[0]; h = a.halb
    x0, y0 = int(max(0, u - h)), int(max(0, v - h)); x1, y1 = int(min(im.shape[1], u + h)), int(min(im.shape[0], v + h))
    c = cv2.resize(im[y0:y1, x0:x1], None, fx=a.faktor, fy=a.faktor, interpolation=cv2.INTER_CUBIC)
    for S, col in ((S2, (255, 255, 0)), (S1, (0, 0, 255))):
        if S is None: continue
        P = proj(k, S.reshape(-1, 3)).reshape(-1, 2, 2)
        for p in P: cv2.line(c, tuple(int(q) for q in (p[0] - [x0, y0]) * a.faktor), tuple(int(q) for q in (p[1] - [x0, y0]) * a.faktor), col, 1, cv2.LINE_AA)
    cv2.putText(c, fo[-22:], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    c = cv2.copyMakeBorder(c, 0, int(2 * h * a.faktor) - c.shape[0], 0, int(2 * h * a.faktor) - c.shape[1], cv2.BORDER_CONSTANT); tiles.append(c)
rows = [np.hstack(tiles[i:i + 2] + ([np.zeros_like(tiles[0])] if len(tiles[i:i + 2]) == 1 else [])) for i in range(0, len(tiles), 2)]
cv2.imwrite(a.out, np.vstack(rows)); print("->", a.out)
