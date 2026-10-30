#!/usr/bin/env python3
"""elementcheck.py — ELEMENT-FÜR-ELEMENT Foto↔Modell, inkl. der BLINDEN FLECKEN die selfcheck nie
zeigte (Dach-SEITE/Rand, Erker-FENSTER, Helm-PROFIL, Statuen-FUSS, Gesims-LINIENZAHL, Seitenbogen,
Balkon). Zweck: nicht die Gestalt/Mitte, sondern jedes Sub-Element eng gegen SEIN bestes Foto.

Warum: die alten Checker prüften nur Build/Bounds/Watertight + fixe Mittel-Crops → konnten genau die
vom User gefundenen Fehler NICHT melden. Diese Kacheln erzwingen das Hinschauen an den Rändern.

Lauf:  /tmp/rv/bin/python tools/elementcheck.py   → /tmp/elementcheck.png  (dann mit AUGEN prüfen)
"""
import os
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np, trimesh, pyrender
from PIL import Image, ImageDraw

ROOT = "/home/md/git/rc-park"
GLB = f"{ROOT}/modelle/kaufhaus_freiburg/kaufhaus_measured.glb"
F = f"{ROOT}/daten/kaufhaus_freiburg/fotos"
# name -> (fotodatei, foto-box frac, render-key, modell-box frac)   render-key: front|oblique|oriel
ELEMENTS = [
    ("Dach-SEITE (rot?)",    "kh_erker.jpg",  (0.55, 0.00, 1.00, 0.45), "oblique", (0.00, 0.00, 0.30, 0.55)),
    ("Dach-Mitte+Gauben",    "kh_jm3289.jpg", (0.24, 0.05, 0.78, 0.40), "front",   (0.10, 0.00, 0.90, 0.40)),
    ("Erker-FENSTER",        "kh_erker.jpg",  (0.55, 0.55, 0.88, 0.92), "oriel",   (0.66, 0.42, 1.00, 0.78)),
    ("Erker-HELM Profil",    "kh_erker.jpg",  (0.58, 0.12, 0.98, 0.60), "oriel",   (0.66, 0.00, 1.00, 0.45)),
    ("Statuen-FUSS",         "kh_jm3289.jpg", (0.30, 0.35, 0.70, 0.66), "front",   (0.24, 0.33, 0.78, 0.66)),
    ("Gesims-LINIEN",        "kh_jm3289.jpg", (0.30, 0.30, 0.70, 0.42), "front",   (0.20, 0.30, 0.80, 0.46)),
    ("Balkon-Brüstung",      "kh_jm3289.jpg", (0.19, 0.55, 0.55, 0.73), "front",   (0.16, 0.50, 0.58, 0.72)),
    ("Seiten-Unterdurchgang","kh_jm3289.jpg", (0.72, 0.60, 0.86, 0.95), "oblique", (0.00, 0.45, 0.22, 0.95)),
]


def look_at(p, t, up=(0, 0, 1)):
    f = np.array(t)-np.array(p); f = f/np.linalg.norm(f); up = np.array(up, float)
    s = np.cross(f, up); s = s/np.linalg.norm(s); u = np.cross(s, f)
    M = np.eye(4); M[:3, 0] = s; M[:3, 1] = u; M[:3, 2] = -f; M[:3, 3] = p; return M


def render(views):
    ts = trimesh.load(GLB); sc = pyrender.Scene.from_trimesh_scene(ts, ambient_light=[0.42]*3)
    b = ts.bounds; ctr = b.mean(0); size = b[1]-b[0]; R = float(size.max())
    sc.add(pyrender.DirectionalLight(intensity=2.6), pose=look_at(ctr+np.array([0.3, -0.6, 0.9])*R, ctr))
    sc.add(pyrender.DirectionalLight(intensity=1.0), pose=look_at(ctr+np.array([-0.6, -0.3, 0.4])*R, ctr))
    cam = pyrender.PerspectiveCamera(yfov=np.radians(26)); cn = sc.add(cam); r = pyrender.OffscreenRenderer(1200, 950)
    tgt = ctr-np.array([0, 0, size[2]*0.1]); out = {}
    for nm, az, el in views:
        a, e = np.radians(az), np.radians(el); dv = np.array([np.cos(e)*np.cos(a), np.cos(e)*np.sin(a), np.sin(e)])
        sc.set_pose(cn, look_at(tgt+dv*R*4.2, tgt)); col, _ = r.render(sc, flags=pyrender.RenderFlags.RGBA)
        al = col[:, :, 3:4]/255.0; im = Image.fromarray((col[:, :, :3]*al+255*(1-al)).astype(np.uint8))
        a2 = np.asarray(im); mask = a2.sum(2) < 744; ys, xs = np.where(mask)
        out[nm] = im.crop((xs.min(), ys.min(), xs.max(), ys.max()))
    r.delete(); return out


def cbox(im, box):
    w, h = im.size
    return im.crop((int(w*box[0]), int(h*box[1]), int(w*box[2]), int(h*box[3])))


def main():
    rv = render([("front", 270, 6), ("oblique", 240, 14), ("oriel", 300, 13)])
    TH = 230; cells = []
    for name, pf, fb, rk, mb in ELEMENTS:
        pc = cbox(Image.open(f"{F}/{pf}").convert("RGB"), fb)
        mc = cbox(rv[rk], mb)
        def rs(im):
            return im.resize((max(1, int(im.width*TH/im.height)), TH))
        pc, mc = rs(pc), rs(mc)
        cell = Image.new("RGB", (pc.width+mc.width+14, TH+22), (238, 238, 238))
        cell.paste(pc, (0, 22)); cell.paste(mc, (pc.width+14, 22))
        ImageDraw.Draw(cell).text((4, 5), f"{name}   FOTO | MODELL", fill=(0, 0, 0))
        cells.append(cell)
    ncol = 2
    rows = [cells[i:i+ncol] for i in range(0, len(cells), ncol)]
    rww = [sum(c.width for c in r)+10*len(r) for r in rows]
    sheet = Image.new("RGB", (max(rww)+10, sum(max(c.height for c in r) for r in rows)+10*len(rows)+10), (255, 255, 255))
    y = 10
    for r in rows:
        x = 10
        for c in r:
            sheet.paste(c, (x, y)); x += c.width+10
        y += max(c.height for c in r)+10
    sheet.save("/tmp/elementcheck.png")
    print("-> /tmp/elementcheck.png  — JEDES Sub-Element (inkl. Dach-Seite/Erker-Fenster/Helm-Profil/")
    print("   Statuen-Fuß/Gesims-Linien/Seitenbogen/Balkon) eng Foto↔Modell. JETZT mit Augen prüfen.")


if __name__ == "__main__":
    main()
