#!/usr/bin/env python3
"""hofgut_texturieren.py — GANZES Gebäude aus echten Daten als Oberfläche auf die KORREKTE Struktur:
  Dach   <- DOP-Luftbild (georeferenziert, Top-Down-UV)
  Front  <- echtes Frontfoto (freigestellt, planare x-z-UV auf die Front-Wandflächen)
  Rest   <- dunkles Holz (gemessene Farbe)
Keine graue Parametrik mehr — Holz/Lüftlmalerei/Fresko/Galerien kommen aus dem Foto.

Lauf: /tmp/rv/bin/python tools/hofgut_texturieren.py
"""
import json, os
import numpy as np
import cv2
import trimesh
from PIL import Image

MD = "modelle/hofgut_sternen"
DOP = "daten/ravenna/dop/dop20rgb_32_429_5306_2_bw/dop20rgb_32_430_5307_1_bw_2025.tif"
FOTO = "daten/hofgut_sternen/fotos/g2.jpg"   # g2 deckt die GANZE Fassadenbreite ab (hf_front schneidet rechts ab)


def dop_roof_texture(roof_bounds, fr, o):
    ang = -fr["rot_angle"]; Rm = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    ctr = np.array(fr["ctr"]); flip = fr["flip"]; shift = np.array(fr["shift"])
    tfw = open(os.path.splitext(DOP)[0] + ".tfw").read().split()
    px, _, _, py, oxc, oyc = [float(x) for x in tfw]; E0, N0 = oxc - px / 2, oyc + (-py) / 2
    dop = cv2.imread(DOP)

    def m2d(mx, my):
        p1 = np.array([mx, my]) + shift
        if flip:
            p1 = p1 * np.array([1.0, -1.0])
        loc = p1 @ Rm + ctr
        return (loc[0] + o[0] - E0) / px, (N0 - (loc[1] + o[1])) / (-py)
    (x0, y0, _), (x1, y1, _) = roof_bounds
    W, H = 1024, max(8, int(1024 * (y1 - y0) / (x1 - x0)))
    src = np.float32([m2d(x0, y1), m2d(x1, y1), m2d(x1, y0), m2d(x0, y0)])
    tex = cv2.warpPerspective(dop, cv2.getPerspectiveTransform(src, np.float32([[0, 0], [W, 0], [W, H], [0, H]])), (W, H))
    return Image.fromarray(cv2.cvtColor(tex, cv2.COLOR_BGR2RGB)), (x0, x1, y0, y1)


def facade_texture():
    """Frontfoto SAUBER auf die Wandzone zuschneiden: nur Gebäude (Maske), kein Vordergrund/Zaun."""
    im = cv2.imread(FOTO); m = cv2.imread(FOTO.replace(".jpg", "_mask.png"), 0)
    mb = m > 127
    ys, xs = np.where(mb); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    # Wandzone = unter dem Dach (Dachanteil ~0.46) bis knapp über den Fuß (Vordergrund-Terrasse weg)
    yw0 = int(y0 + 0.46 * (y1 - y0)); yw1 = int(y1 - 0.04 * (y1 - y0))
    crop = im[yw0:yw1, x0:x1].copy()
    mm = mb[yw0:yw1, x0:x1]
    # Nicht-Gebäude-Pixel mit dem Spalten-Median der Wand füllen (statt schwarz) → keine Löcher
    for c in range(crop.shape[1]):
        col = crop[:, c][mm[:, c]]
        if len(col):
            crop[:, c][~mm[:, c]] = np.median(col, axis=0).astype(np.uint8)
    return Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))


def main():
    fr = json.load(open(f"{MD}/massing_frame.json")); fp = json.load(open(f"{MD}/footprint.json"))
    o = np.array(fp["origin_utm"][:2])
    sc = trimesh.load(f"{MD}/hofgut_massing.glb")
    roof = sc.geometry["daecher"]; walls = sc.geometry["waende"]
    FM = json.load(open(f"{MD}/farben.json"))

    # Dach <- DOP
    teximg, _ = dop_roof_texture((roof.bounds[0], roof.bounds[1]), fr, o)
    roof.visual = trimesh.visual.TextureVisuals(
        uv=np.c_[(roof.vertices[:, 0] - roof.bounds[0][0]) / (roof.bounds[1][0] - roof.bounds[0][0]),
                 (roof.vertices[:, 1] - roof.bounds[0][1]) / (roof.bounds[1][1] - roof.bounds[0][1])],
        image=teximg)

    # Wände: Front-Flächen (-Y) <- Frontfoto; Rest <- Holz
    fn = walls.face_normals
    front = fn[:, 1] < -0.3                                   # alle front-zugewandten Flächen (auch leicht schräge)
    (wx0, wy0, wz0), (wx1, wy1, wz1) = walls.bounds[0], walls.bounds[1]
    front_mesh = walls.submesh([np.where(front)[0]], append=True)
    rest_mesh = walls.submesh([np.where(~front)[0]], append=True)
    fac = facade_texture()
    V = front_mesh.vertices
    uv = np.c_[(V[:, 0] - wx0) / (wx1 - wx0), (V[:, 2] - wz0) / (wz1 - wz0)]   # x→u, z→v (aufrecht)
    front_mesh.visual = trimesh.visual.TextureVisuals(uv=uv, image=fac)
    rest_mesh.visual.face_colors = [int(c) for c in FM["og_lauben"]] + [255]

    out = trimesh.Scene()
    out.add_geometry(roof, geom_name="dach_dop")
    out.add_geometry(front_mesh, geom_name="fassade_foto")
    out.add_geometry(rest_mesh, geom_name="waende_holz")
    out.export(f"{MD}/hofgut_tex.glb")
    print(f"-> {MD}/hofgut_tex.glb (Dach=DOP, Front=Frontfoto, Rest=Holz) — alles aus echten Daten")


if __name__ == "__main__":
    main()
