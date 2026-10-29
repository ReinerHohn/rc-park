#!/usr/bin/env python3
"""glb_render.py — echtes texturiertes Offscreen-Rendering (pyrender/EGL).
Mit venv-Python ausführen:  /tmp/rv/bin/python tools/glb_render.py <glb> <out_prefix> [az,el ...]
"""
import os, sys
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np, trimesh, pyrender
from PIL import Image


def look_at(cam_pos, target, up=(0, 0, 1)):
    f = np.array(target) - np.array(cam_pos); f = f / np.linalg.norm(f)
    up = np.array(up, float)
    s = np.cross(f, up); s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    M = np.eye(4)
    M[:3, 0] = s; M[:3, 1] = u; M[:3, 2] = -f; M[:3, 3] = cam_pos
    return M


def _sky_bg(h, w):
    """sanfter Himmel-Verlauf (hell oben → etwas dunkler unten) als Hintergrund."""
    top = np.array([170, 188, 208]); bot = np.array([208, 214, 216])
    t = np.linspace(0, 1, h)[:, None, None]
    return (top*(1-t) + bot*t).astype(np.uint8) * np.ones((h, w, 3), np.uint8)


def render(glb, out_prefix, views):
    ts = trimesh.load(glb)
    LS = float(os.environ.get("GLB_LIGHT", "1.0"))          # Licht-Skala (1.0=hell default; <1 realistischer/dunkler)
    amb = 0.30 * LS + 0.08
    sc = pyrender.Scene.from_trimesh_scene(ts, ambient_light=[amb, amb, amb + 0.02]) \
        if isinstance(ts, trimesh.Scene) else pyrender.Scene(ambient_light=[amb]*3)
    if not isinstance(ts, trimesh.Scene):
        sc.add(pyrender.Mesh.from_trimesh(ts))
        bounds = ts.bounds
    else:
        bounds = ts.bounds
    ctr = bounds.mean(0); size = (bounds[1] - bounds[0]); R = float(np.max(size))
    # kräftigeres gerichtetes Licht (sattere Farben, klare Form) statt flachem Ambient
    sc.add(pyrender.DirectionalLight(color=[1, 0.98, 0.93], intensity=2.5 * LS),
           pose=look_at(ctr + np.array([0.35, -0.6, 0.9]) * R, ctr))
    sc.add(pyrender.DirectionalLight(color=[0.82, 0.87, 1.0], intensity=0.9 * LS),
           pose=look_at(ctr + np.array([-0.6, -0.3, 0.4]) * R, ctr))
    cam = pyrender.PerspectiveCamera(yfov=np.radians(24))   # Telephoto = wenig Verzerrung
    cam_node = sc.add(cam, pose=np.eye(4))
    H, Wd = 1050, 1400
    r = pyrender.OffscreenRenderer(Wd, H)
    tgt = ctr - np.array([0, 0, size[2]*0.12])              # Blickziel etwas tiefer (Fassade zentriert)
    bg = _sky_bg(H, Wd)
    for nm, az, el in views:
        a, e = np.radians(az), np.radians(el)
        dirv = np.array([np.cos(e)*np.cos(a), np.cos(e)*np.sin(a), np.sin(e)])
        pos = tgt + dirv * R * 4.3
        sc.set_pose(cam_node, look_at(pos, tgt))
        col, _ = r.render(sc, flags=pyrender.RenderFlags.RGBA)
        al = col[:, :, 3:4].astype(np.float32) / 255.0      # über Himmel compositen
        comp = (col[:, :, :3].astype(np.float32) * al + bg.astype(np.float32) * (1-al)).astype(np.uint8)
        Image.fromarray(comp).save(f"{out_prefix}_{nm}.png")
        print(f"-> {out_prefix}_{nm}.png")
    r.delete()


if __name__ == "__main__":
    glb, out = sys.argv[1], sys.argv[2]
    views = []
    for a in sys.argv[3:]:
        nm, az, el = a.split(",")
        views.append((nm, float(az), float(el)))
    if not views:
        views = [("front", 90, 5), ("oblique", 60, 18), ("aerial", 90, 78)]
    render(glb, out, views)
