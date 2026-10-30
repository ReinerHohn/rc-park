#!/usr/bin/env python3
"""hofgut_multifoto_textur.py — MULTI-FOTO-PROJEKTION mit GEOMETRIE-ANKER (die richtige Architektur):
das bekannte 3D-Modell (LOD2+Luftbild+Laser) ist der Konsistenz-Anker. Jedes Foto wird GEGEN das
Modell registriert (Pose per Silhouette = Overlay-Bewerter) und aus seiner Pose aufs Modell projiziert.
Jede Wandfläche bekommt das Foto, das sie am frontalsten sieht → konsistente Multi-View-Textur,
robust gegen Jahreszeit/Licht (nicht Foto-gegen-Foto wie SfM). Dach = DOP.

Lauf: /tmp/rv/bin/python tools/hofgut_multifoto_textur.py
"""
import json, os, subprocess
import numpy as np
import cv2
import trimesh
from PIL import Image

MD = "modelle/hofgut_sternen"
FD = "daten/hofgut_sternen/fotos"
# Fotos mit (grober) Pose aus dem Overlay-Bewerter (Silhouetten-Fit gegen das Modell)
FOTOS = [("hf_front", 270, 18), ("g3", 285, 18), ("g2", 330, 18), ("g4", 300, 16)]
H_IMG, W_IMG = 1050, 1400
YFOV = np.radians(24)


def look_at(pos, tgt, up=(0, 0, 1)):
    f = np.array(tgt) - np.array(pos); f /= np.linalg.norm(f)
    up = np.array(up, float); s = np.cross(f, up); s /= np.linalg.norm(s); u = np.cross(s, f)
    M = np.eye(4); M[:3, 0] = s; M[:3, 1] = u; M[:3, 2] = -f; M[:3, 3] = pos
    return M


def camera(az, el, ctr, size, Rext):
    tgt = ctr - np.array([0, 0, size[2] * 0.12])
    a, e = np.radians(az), np.radians(el)
    dirv = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    pos = tgt + dirv * Rext * 4.3
    return look_at(pos, tgt), pos


def project(V, world_T_cam):
    """Welt-Vertices → Render-Bildkoordinaten (1400x1050) + Tiefe + Sichtbarkeit."""
    cam_T_world = np.linalg.inv(world_T_cam)
    Vh = np.c_[V, np.ones(len(V))]
    pc = (cam_T_world @ Vh.T).T[:, :3]
    d = -pc[:, 2]
    fy = (H_IMG / 2) / np.tan(YFOV / 2); fx = fy
    u = W_IMG / 2 + fx * pc[:, 0] / np.where(d == 0, 1e-6, d)
    v = H_IMG / 2 - fy * pc[:, 1] / np.where(d == 0, 1e-6, d)
    return np.c_[u, v], d


def render_mask(glb, az, el):
    out = f"/tmp/mf_{az}_{el}"
    subprocess.run(["/tmp/rv/bin/python", "tools/glb_render.py", glb, out, f"q,{az},{el}"],
                   capture_output=True, env={**os.environ, "PYOPENGL_PLATFORM": "egl", "GLB_LIGHT": "0.8"})
    g = cv2.cvtColor(cv2.imread(f"{out}_q.png"), cv2.COLOR_BGR2GRAY)
    return (g < 248)


def main():
    sc = trimesh.load(f"{MD}/hofgut_massing.glb")
    walls = sc.geometry["waende"]; roof = sc.geometry["daecher"]
    ctr = walls.bounds.mean(0) if False else None
    full = trimesh.util.concatenate([walls, roof])
    ctr = full.bounds.mean(0); size = full.bounds[1] - full.bounds[0]; Rext = float(size.max())

    V = walls.vertices; Fn = walls.face_normals; faces = walls.faces
    # je Foto: Pose-Kamera, Render-Silhouette→Foto-Maske Homographie, Vertex-UV, Blickrichtung
    photo_uv = []; photo_img = []; view_dir = []
    for name, az, el in FOTOS:
        mp = f"{FD}/{name}_mask.png"
        if not os.path.exists(mp):
            photo_uv.append(None); photo_img.append(None); view_dir.append(None); continue
        wtc, pos = camera(az, el, ctr, size, Rext)
        uv_ren, d = project(V, wtc)
        # Render-Silhouette (Modell) bbox vs Foto-Gebäude bbox → Homographie (Ausrichtung Render↔Foto)
        rmask = render_mask(f"{MD}/hofgut_massing.glb", az, el)
        rys, rxs = np.where(rmask); rb = (rxs.min(), rys.min(), rxs.max(), rys.max())
        pm = cv2.imread(mp, 0) > 127; pys, pxs = np.where(pm); pb = (pxs.min(), pys.min(), pxs.max(), pys.max())
        srcq = np.float32([[rb[0], rb[1]], [rb[2], rb[1]], [rb[2], rb[3]], [rb[0], rb[3]]])
        dstq = np.float32([[pb[0], pb[1]], [pb[2], pb[1]], [pb[2], pb[3]], [pb[0], pb[3]]])
        Hom = cv2.getPerspectiveTransform(srcq, dstq)
        uvh = cv2.perspectiveTransform(uv_ren.reshape(-1, 1, 2).astype(np.float32), Hom).reshape(-1, 2)
        img = cv2.cvtColor(cv2.imread(f"{FD}/{name}.jpg"), cv2.COLOR_BGR2RGB)
        ph, pw = img.shape[:2]
        uvn = np.c_[uvh[:, 0] / pw, 1 - uvh[:, 1] / ph]        # normierte UV (v geflippt)
        photo_uv.append(uvn); photo_img.append(Image.fromarray(img))
        view_dir.append((ctr - pos) / np.linalg.norm(ctr - pos))

    # je Fläche: bestes Foto = frontalste Sicht (Normale·-Blick) unter den gültigen
    assign = np.full(len(faces), -1)
    best = np.full(len(faces), -1.0)
    for pi, vd in enumerate(view_dir):
        if vd is None:
            continue
        score = -(Fn @ vd)                                     # >0 = Fläche schaut zur Kamera
        uvn = photo_uv[pi]
        inb = np.all((uvn[faces] >= 0) & (uvn[faces] <= 1), axis=(1, 2))   # alle 3 Ecken im Foto
        for fi in range(len(faces)):
            if score[fi] > 0.25 and inb[fi] and score[fi] > best[fi]:
                best[fi] = score[fi]; assign[fi] = pi

    out = trimesh.Scene()
    # Dach = DOP (vorhandene Dachtextur wiederverwenden)
    import hofgut_texturieren as HT
    fr = json.load(open(f"{MD}/massing_frame.json")); fp = json.load(open(f"{MD}/footprint.json"))
    teximg, _ = HT.dop_roof_texture((roof.bounds[0], roof.bounds[1]), fr, np.array(fp["origin_utm"][:2]))
    roof.visual = trimesh.visual.TextureVisuals(
        uv=np.c_[(roof.vertices[:, 0] - roof.bounds[0][0]) / (roof.bounds[1][0] - roof.bounds[0][0]),
                 (roof.vertices[:, 1] - roof.bounds[0][1]) / (roof.bounds[1][1] - roof.bounds[0][1])], image=teximg)
    out.add_geometry(roof, geom_name="dach_dop")

    FM = json.load(open(f"{MD}/farben.json"))
    for pi in range(len(FOTOS)):
        fsel = np.where(assign == pi)[0]
        if len(fsel) == 0:
            continue
        uvn = photo_uv[pi]
        # Submesh mit eigener UV aufbauen (re-indexed)
        vmap = {}
        nv, nf, nuv = [], [], []
        for f in faces[fsel]:
            tri = []
            for vidx in f:
                if vidx not in vmap:
                    vmap[vidx] = len(nv); nv.append(V[vidx]); nuv.append(uvn[vidx])
                tri.append(vmap[vidx])
            nf.append(tri)
        m = trimesh.Trimesh(vertices=np.array(nv), faces=np.array(nf), process=False)
        m.visual = trimesh.visual.TextureVisuals(uv=np.array(nuv), image=photo_img[pi])
        out.add_geometry(m, geom_name=f"foto_{FOTOS[pi][0]}")
    # unzugeordnete Flächen → Holz
    un = np.where(assign == -1)[0]
    if len(un):
        w = walls.submesh([un], append=True); w.visual.face_colors = [int(c) for c in FM["og_lauben"]] + [255]
        out.add_geometry(w, geom_name="waende_holz")
    out.export(f"{MD}/hofgut_multifoto.glb")
    n_tex = sum(1 for pi in range(len(FOTOS)) if (assign == pi).any())
    print(f"Multi-Foto-Textur: {n_tex} Fotos projiziert, {int((assign>=0).sum())}/{len(faces)} Flaechen texturiert, "
          f"{len(un)} Holz. -> {MD}/hofgut_multifoto.glb")


if __name__ == "__main__":
    main()
