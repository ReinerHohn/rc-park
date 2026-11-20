#!/usr/bin/env python3
"""Schritt 2b — Relief-Heightmap aus dem ausgerichteten Foto-Mesh backen (trimesh Raycast).

Für JEDE Wand des sauberen LoD2 wird gemessen, wie weit die reale Fassadenoberfläche (aus dem
ausgerichteten Foto-Mesh) vor/hinter der glatten LoD2-Wandebene liegt → **metrische Depthmap**.
Diese steuert in Schritt 3 den Displace-Modifier und drückt Fensterrahmen/Vorsprünge/Ornamente als
ECHTES Relief heraus (Vorsprung = hell/+, vertiefte Fenster = dunkel/−).

Ausgabe je Wand:  <wall>_height.png (16-bit Graustufen) + <wall>_meta.json (Origin/Achsen/Tiefenspanne).

Lauf: python step2b_bake_heightmap.py --foto foto_aligned.ply --lod2 lod2.ply --out wände/ --res 2048
"""
import argparse, json, os
import numpy as np
import trimesh
from PIL import Image


def auto_walls(lod2: trimesh.Trimesh, min_area=8.0, max_slope=0.25):
    """Fassadenebenen aus dem LoD2 finden: nahezu senkrechte Flächen nach (Normale, Ebenen-Offset) clustern.
    Gibt Liste von Wänden: dict(origin, u, v, w, h, normal)."""
    fn = lod2.face_normals
    vertical = np.abs(fn[:, 2]) < max_slope                   # senkrechte Flächen (Wände, nicht Dach/Boden)
    walls, used = [], np.zeros(len(fn), bool)
    for i in np.where(vertical)[0]:
        if used[i]:
            continue
        n = fn[i]; n = n / np.linalg.norm(n)
        # Flächen mit ähnlicher Normale UND ähnlichem Ebenen-Offset = eine Wand
        off = lod2.triangles_center @ n
        sel = vertical & (fn @ n > 0.98) & (np.abs(off - (lod2.triangles_center[i] @ n)) < 0.5)
        used |= sel
        pts = lod2.vertices[np.unique(lod2.faces[sel])]
        if trimesh.PointCloud(pts).convex_hull.area < min_area:
            continue
        up = np.array([0, 0, 1.0]); u = np.cross(up, n); u /= np.linalg.norm(u)
        o = pts.min(0)                                        # Wand-Ursprung (untere Ecke)
        pu = (pts - o) @ u; pv = (pts - o) @ up
        walls.append({"origin": o, "u": u, "v": up, "normal": n,
                      "w": float(pu.max() - pu.min()), "h": float(pv.max() - pv.min()),
                      "u0": float(pu.min()), "v0": float(pv.min())})
    return walls


def bake(foto: trimesh.Trimesh, wall: dict, res=2048, max_front=0.6, max_back=0.8):
    """Raycast von einer Ebene VOR der Wand nach innen → erster Treffer auf dem Foto-Mesh → Relieftiefe.
    Tiefe > 0 = Vorsprung (vor der Wand), < 0 = Rücksprung (vertieftes Fenster)."""
    o, u, v, n = wall["origin"], wall["u"], wall["v"], wall["normal"]
    W = max(16, int(res * wall["w"] / max(wall["w"], wall["h"])))
    H = max(16, int(res * wall["h"] / max(wall["w"], wall["h"])))
    gu = (np.arange(W) + 0.5) / W * wall["w"] + wall["u0"]
    gv = (np.arange(H) + 0.5) / H * wall["h"] + wall["v0"]
    UU, VV = np.meshgrid(gu, gv)
    base = o[None, :] + UU.ravel()[:, None] * u[None, :] + VV.ravel()[:, None] * v[None, :]
    starts = base + n[None, :] * max_front                    # Start vor der Wand
    dirs = np.tile(-n, (len(starts), 1))                      # Blick in die Wand hinein
    inter = trimesh.ray.ray_pyembree.RayMeshIntersector(foto) if trimesh.ray.has_embree \
        else trimesh.ray.ray_triangle.RayMeshIntersector(foto)
    loc, idx_ray, _ = inter.intersects_location(starts, dirs, multiple_hits=False)
    depth = np.full(len(starts), np.nan)
    if len(idx_ray):
        # Relieftiefe = Projektion des Treffers auf die Wand-Normale, relativ zur Wandebene
        rel = (loc - base[idx_ray]) @ n
        depth[idx_ray] = max_front - np.clip((starts[idx_ray] - loc) @ (-n) * 0 + 0, 0, 0) + rel * 0  # s.u.
        depth[idx_ray] = (loc @ n) - (base[idx_ray] @ n)      # vorzeichenbehaftete Relieftiefe in m
    depth = depth.reshape(H, W)
    # Löcher (keine Treffer) = Wandebene (0 Relief)
    depth = np.where(np.isnan(depth), 0.0, np.clip(depth, -max_back, max_front))
    lo, hi = float(depth.min()), float(depth.max())
    hm = ((depth - lo) / max(1e-6, hi - lo) * 65535).astype(np.uint16)
    return hm, {"lo_m": lo, "hi_m": hi, "span_m": hi - lo, "W": W, "H": H,
                "origin": o.tolist(), "u": u.tolist(), "v": v.tolist(), "normal": n.tolist(),
                "w": wall["w"], "h": wall["h"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True); ap.add_argument("--lod2", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--res", type=int, default=2048)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    foto = trimesh.load(a.foto); lod2 = trimesh.load(a.lod2)
    walls = auto_walls(lod2)
    print(f"{len(walls)} Fassadenebenen erkannt")
    index = []
    for i, wall in enumerate(walls):
        hm, meta = bake(foto, wall, a.res)
        Image.fromarray(hm).save(f"{a.out}/wall{i:02d}_height.png")
        json.dump(meta, open(f"{a.out}/wall{i:02d}_meta.json", "w"), indent=1)
        index.append({"id": i, "span_m": round(meta["span_m"], 3)})
        print(f"  Wand {i}: {meta['W']}x{meta['H']}, Relief-Spanne {meta['span_m']:.3f} m")
    json.dump(index, open(f"{a.out}/index.json", "w"), indent=1)
    print(f"-> Heightmaps + Meta in {a.out}/")


if __name__ == "__main__":
    main()
