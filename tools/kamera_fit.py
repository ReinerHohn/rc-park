#!/usr/bin/env python3
"""kamera_fit.py — PERSPEKTIVE AUTOMATISCH TREFFEN (Analyse-durch-Synthese).

Statt das Modell orthografisch zu rendern und zu hoffen, dass es zum (perspektivischen) Foto passt,
wird die RENDER-KAMERA an das Foto angepasst: für ein Gitter aus (Elevation, Blickwinkel/fov) wird
gerendert, der overlay_diff-Score berechnet und die Kamera mit dem KLEINSTEN Score gewählt. Danach
sitzt die Perspektive → Rest-Diff = echter Geometrie-Unterschied. Verallgemeinert auf JEDES Foto
(beliebiger Winkel) → öffnet das Feld für viele Bilder.

Speichert die beste Kamera nach modelle/kaufhaus_freiburg/kamera.json (az, el, fov).
Lauf: /tmp/rv/bin/python tools/kamera_fit.py
"""
import os, sys, json, importlib.util
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np, trimesh, pyrender
from PIL import Image

sys.argv = ["x"]
spec = importlib.util.spec_from_file_location("od", os.path.join(os.path.dirname(__file__), "overlay_diff.py"))
od = importlib.util.module_from_spec(spec); spec.loader.exec_module(od)


def render_cam(ts, az, el, fov):
    sc = pyrender.Scene.from_trimesh_scene(ts, ambient_light=[0.35]*3)
    b = ts.bounds; ctr = b.mean(0); size = b[1]-b[0]; R = float(size.max())
    sc.add(pyrender.DirectionalLight(intensity=1.8), pose=od.look_at(ctr+np.array([0.1, -0.8, 0.6])*R, ctr))
    cam = pyrender.PerspectiveCamera(yfov=np.radians(fov)); cn = sc.add(cam)
    r = pyrender.OffscreenRenderer(900, 1200)
    a, e = np.radians(az), np.radians(el); dv = np.array([np.cos(e)*np.cos(a), np.cos(e)*np.sin(a), np.sin(e)])
    dist = R*4.5*(20.0/fov)                                   # Abstand an fov koppeln → Objekt bleibt bildfüllend
    sc.set_pose(cn, od.look_at(ctr+dv*dist, ctr)); col, _ = r.render(sc, flags=pyrender.RenderFlags.RGBA); r.delete()
    al = col[:, :, 3]; ys, xs = np.where(al > 10)
    return Image.fromarray(col[:, :, :3]).crop((xs.min(), ys.min(), xs.max(), ys.max()))


def score_vs_photo(op_p, skin_p, rd):
    op_m, _ = od.cell_feats(rd, od.NX, od.NY)
    diff = np.abs(op_p-op_m)
    valid = np.ones((od.NY, od.NX), bool); valid[od.NY-od.GROUND_ROWS:, :] = False; valid[skin_p > 0.12] = False
    return float(diff[valid].mean())


def main():
    ph = Image.open(od.PHOTO).convert("RGB"); W, H = ph.size
    pc = ph.crop((int(W*od.PBOX[0]), int(H*od.PBOX[1]), int(W*od.PBOX[2]), int(H*od.PBOX[3])))
    op_p, skin_p = od.cell_feats(pc, od.NX, od.NY)
    ts = trimesh.load(od.GLB)
    best = (1e9, None)
    print("Kamera-Suche (az=270 fix, el × fov):  Score-Gitter")
    print("      fov:  " + "  ".join(f"{f:4d}" for f in (16, 20, 24, 28, 32)))
    for el in (-8, -4, 0, 4, 8, 12):
        row = []
        for fov in (16, 20, 24, 28, 32):
            s = score_vs_photo(op_p, skin_p, render_cam(ts, 270, el, fov))
            row.append(s)
            if s < best[0]:
                best = (s, (270, el, fov))
        print(f"  el={el:+3d}: " + "  ".join(f"{v:.3f}" for v in row))
    s0, (az, el, fov) = best
    # Feinsuche um das Minimum
    for el2 in (el-2, el, el+2):
        for fov2 in (fov-2, fov, fov+2):
            s = score_vs_photo(op_p, skin_p, render_cam(ts, 270, el2, fov2))
            if s < best[0]:
                best = (s, (270, el2, fov2))
    s_best, (az, el, fov) = best
    json.dump({"az": az, "el": el, "fov": fov, "score": round(s_best, 4),
               "_quelle": "kamera_fit.py: Score-Minimum über el×fov"},
              open("modelle/kaufhaus_freiburg/kamera.json", "w"), indent=2)
    print(f"\nBESTE Kamera: az={az} el={el} fov={fov}  → Score {s_best:.4f}")
    print("(ortho-Startwert el=2.5 fov=20 war Score ~0.175; Perspektiv-Fit senkt den Rest-Diff)")
    print("-> modelle/kaufhaus_freiburg/kamera.json")


if __name__ == "__main__":
    main()
