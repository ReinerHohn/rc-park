#!/usr/bin/env python3
"""lod2_textured.py — GENERISCH: echtes LOD2-Gebäude mit ECHTER TEXTUR.
  Dach  <- DOP-Orthofoto (geometrisch exakt: gleiche UTM-Koordinaten, planar-UV)
  Front <- rektifiziertes Fassadenfoto (planar u-z-UV)
Export: texturiertes glb + Vorschau-PNG (Textur per Face-UV abgetastet).
"""
import argparse, os, sys
import numpy as np
import trimesh
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as L
import gebaeude_detailer as D


def dop_crop(dop_tif, Emin, Nmin, bx, by):
    import rasterio
    from rasterio.windows import from_bounds
    with rasterio.open(dop_tif) as ds:
        win = from_bounds(Emin, Nmin, Emin + bx, Nmin + by, ds.transform)
        img = np.transpose(ds.read(window=win)[:3], (1, 2, 0))
    return np.ascontiguousarray(img)                 # row0 = Nmax (oben)


def texvis(uv, image_rgb):
    im = Image.fromarray(image_rgb.astype(np.uint8))
    return trimesh.visual.TextureVisuals(uv=uv, image=im)


def facecolor_from_tex(mesh, image_rgb):
    """Vorschau: pro Face UV-Mittel → Texturfarbe."""
    uv = mesh.visual.uv
    H, W = image_rgb.shape[:2]
    cols = []
    for f in mesh.faces:
        u, v = uv[f].mean(0)
        px = int(np.clip(u, 0, 1) * (W - 1)); py = int((1 - np.clip(v, 0, 1)) * (H - 1))
        cols.append(image_rgb[py, px] / 255.0)
    return np.array(cols)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml", required=True); ap.add_argument("--name", default="")
    ap.add_argument("--front-az", type=float, default=180)
    ap.add_argument("--dop", required=True)
    ap.add_argument("--facade", required=True)
    ap.add_argument("--ref-height", type=float, default=17.6)
    ap.add_argument("--outdir", required=True); ap.add_argument("--prefix", default="tex")
    a = ap.parse_args()

    picked = L.extract(a.gml, name=a.name or None, radius=40)
    allpts = np.vstack([P for _, polys in picked for _, P in polys])
    o = np.array([allpts[:, 0].min(), allpts[:, 1].min(), allpts[:, 2].min()])
    bx, by = np.ptp(allpts[:, 0]), np.ptp(allpts[:, 1])
    az = np.radians(a.front_az); front = np.array([np.sin(az), np.cos(az)])

    roof = L.build_mesh(picked, types={"RoofSurface"}, origin=o)[0]
    walls = L.build_mesh(picked, types={"WallSurface", "ClosureSurface"}, origin=o)[0]
    # grobe LOD2-Flächen fein unterteilen → Textur sampled sauber (nicht verschmiert)
    for _ in range(3):
        roof = roof.subdivide()
    for _ in range(2):
        walls = walls.subdivide()

    # --- Dach: DOP planar-UV. glTF: v=0 = oben (Bildzeile 0 = Nordrand/maxN) → v = 1 - y/by ---
    dop = dop_crop(a.dop, o[0], o[1], bx, by)           # row0 = maxN
    ruv = np.c_[roof.vertices[:, 0] / bx, 1.0 - roof.vertices[:, 1] / by]
    roof.visual = texvis(ruv, dop)

    # --- Front-Wände: rektifiziertes Fassadenfoto, planar (x/bx, z/zmax) ---
    import foto_fassade_raster as FR
    import cv2
    img = cv2.imread(a.facade); img = cv2.resize(img, None, fx=3, fy=3)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    vpv, vph = FR.lsd_vps(g)
    rect = FR.rectify(img, vpv, vph) if (vpv is not None and vph is not None) else img
    facade_rgb = cv2.cvtColor(rect, cv2.COLOR_BGR2RGB)   # row0 = oben (Giebel)
    # Front-Faces separieren
    zmax = walls.vertices[:, 2].max()
    fn = walls.face_normals
    front_mask = (fn[:, :2] @ front) > 0.30
    fw = walls.submesh([np.where(front_mask)[0]], append=True)
    ow = walls.submesh([np.where(~front_mask)[0]], append=True)
    # u entlang echter Front-Breite (senkrecht zu front), v = 1 - z/zmax (v=0 oben)
    uaxis = np.array([-front[1], front[0]])              # horizontale Richtung in der Front
    pu = fw.vertices[:, :2] @ uaxis
    fuv = np.c_[(pu - pu.min()) / max(np.ptp(pu), 1e-6), 1.0 - fw.vertices[:, 2] / zmax]
    fw.visual = texvis(fuv, facade_rgb)
    ow.visual.face_colors = [210, 200, 175, 255]

    # --- Details (3D-Tiefe, einfarbig) ---
    balk = D.simple_balconies(walls, front, [3.1, 6.1], 1.3) if hasattr(D, "simple_balconies") else None
    eave, ridge = 9.0, zmax
    gauben = trimesh.util.concatenate([x for x in [D.dormer_row(roof, eave + f*(ridge-eave), n, front)
                                                   for f, n in [(0.30, 7), (0.62, 6)]] if x])
    kamine = D.chimneys(roof, 3)
    for m, col in [(gauben, [70, 55, 46, 255]), (kamine, [110, 96, 90, 255])]:
        if m is not None:
            m.visual.face_colors = col

    os.makedirs(a.outdir, exist_ok=True)
    scene = trimesh.Scene()
    scene.add_geometry(roof, geom_name="dach")
    scene.add_geometry(fw, geom_name="front")
    scene.add_geometry(ow, geom_name="wand")
    for nm, m in [("gauben", gauben), ("kamine", kamine)]:
        if m is not None and len(m.faces):
            scene.add_geometry(m, geom_name=nm)
    glb = f"{a.outdir}/{a.prefix}_textured.glb"
    scene.export(glb)
    print(f"-> {glb}  ({os.path.getsize(glb)/1024:.0f} kB)")

    # --- Vorschau-Render (Textur abgetastet) ---
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    allt, allc = [], []
    for m, img_rgb in [(roof, dop), (fw, facade_rgb)]:
        allt.append(m.vertices[m.faces]); allc.append(facecolor_from_tex(m, img_rgb))
    for m, col in [(ow, (0.82, 0.78, 0.69)), (gauben, (0.27, 0.22, 0.18)), (kamine, (0.43, 0.38, 0.35))]:
        if m is not None and len(m.faces):
            n = m.face_normals; sh = 0.55 + 0.45*np.clip(n[:, 2], 0, 1)
            allt.append(m.vertices[m.faces]); allc.append(np.clip(np.array(col)[None]*sh[:, None], 0, 1))
    tris = np.concatenate(allt); fc = np.concatenate(allc); V = tris.reshape(-1, 3)
    fig = plt.figure(figsize=(16, 7), facecolor="white")
    for k, (azv, el, t) in enumerate([(-90, 6, "Talseite (Fassadenfoto)"), (-60, 14, "schräg"),
                                       (-90, 82, "Dach = DOP-Orthofoto")]):
        ax = fig.add_subplot(1, 3, k+1, projection="3d")
        d = np.array([np.cos(np.radians(azv)), np.sin(np.radians(azv)), 0]); order = np.argsort(-(tris.mean(1)@d))
        ax.add_collection3d(Poly3DCollection(tris[order], facecolors=fc[order], linewidths=0))
        ax.set_xlim(V[:,0].min(),V[:,0].max()); ax.set_ylim(V[:,1].min(),V[:,1].max()); ax.set_zlim(0,V[:,2].max()*1.25)
        ax.set_box_aspect((np.ptp(V[:,0]),np.ptp(V[:,1]),np.ptp(V[:,2])*1.25))
        ax.view_init(elev=el, azim=azv); ax.set_axis_off(); ax.set_title(t, fontsize=10)
    prev = f"{a.outdir}/{a.prefix}_textured_preview.png"
    plt.tight_layout(); plt.savefig(prev, dpi=130, bbox_inches="tight", facecolor="white")
    print(f"-> {prev}")


if __name__ == "__main__":
    main()
