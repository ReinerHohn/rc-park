#!/usr/bin/env python3
"""lod2_to_blender.py — GENERISCH: echtes LOD2-Gebäude (+ Detail) → selbst-enthaltenes
Blender-Skript. Die echte Geometrie (Grundriss/L-Form/Vorbau/Dach) wird als Vertices/Faces
EINGEBETTET; Details (Balkone/Gauben/Kamine) werden hier berechnet und mit eingebettet.
Blender baut daraus 1:1 das Modell — kein externer Import, kein Raten.

  python3 tools/lod2_to_blender.py --gml .../LoD2_32_430_5307_1_BW.gml \
     --name "Hofgut Sternen" --front-az 180 --out modelle/hofgut_sternen/hofgut_blender.py
"""
import argparse, os, sys
import numpy as np
import trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as L
import gebaeude_detailer as D


def simple_balconies(walls, front, levels, proj):
    """Deck + obere/untere Leiste je Front-Segment (ohne Pfosten = wenig Faces)."""
    parts = []
    for z0 in levels:
        for p0, p1, n in D.plane_cut_segments(walls, z0, front, 0.25, "wall"):
            ln = np.linalg.norm(p1[:2] - p0[:2])
            if ln < 1.0:
                continue
            out = np.array([n[0], n[1], 0.0]) * proj
            A, B = p0.copy(), p1.copy(); A[2] = B[2] = z0
            quad = [A, B, B + out, A + out]
            parts.append(trimesh.Trimesh(vertices=np.array(quad + [q - [0, 0, 0.18] for q in quad]),
                                         faces=D._boxfaces(), process=True))
            e0, e1 = A + out, B + out
            d = e1 - e0; ang = np.arctan2(d[1], d[0]); mid = (e0 + e1) / 2
            for zz in (z0 + 0.9, z0 + 0.1):
                bar = trimesh.creation.box(extents=(np.linalg.norm(d), 0.08, 0.08))
                bar.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
                bar.apply_translation((mid[0], mid[1], zz)); parts.append(bar)
    return trimesh.util.concatenate(parts) if parts else None


def py_mesh(m, cx, cy):
    """trimesh → (verts, faces) Listen, X/Y zentriert, gerundet."""
    V = m.vertices.copy(); V[:, 0] -= cx; V[:, 1] -= cy
    verts = [[round(float(x), 3) for x in v] for v in V]
    faces = [[int(i) for i in f] for f in m.faces]
    return verts, faces


TEMPLATE = '''"""
{title} — Blender-Aufbau mit ECHTER LOD2-Geometrie (Grundriss/Vorbau/Dach amtlich).
Generiert von tools/lod2_to_blender.py. In Blender einfügen & ausführen.
Details (Balkone/Gauben/Kamine) an die echten Talseiten-Flächen gesetzt.
"""
import bpy

# ---- eingebettete Gruppen: name -> (rgba, verts, faces) ----
GROUPS = {groups}

def _clear():
    for o in list(bpy.data.objects):
        if o.name.startswith("HG_"):
            bpy.data.objects.remove(o, do_unlink=True)

def mat(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = False; m.diffuse_color = rgba
    return m

def mesh_obj(name, verts, faces, material):
    me = bpy.data.meshes.new(name); me.from_pydata(verts, [], faces); me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material)
    return ob

def build():
    _clear()
    for name, (rgba, verts, faces) in GROUPS.items():
        if verts and faces:
            mesh_obj("HG_" + name, verts, faces, mat("HG_" + name, rgba))
    print("{title}: {nparts} Gruppen gebaut")

build()
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--center", default="")
    ap.add_argument("--front-az", type=float, default=None)
    ap.add_argument("--dgm", default=""); ap.add_argument("--dgm-origin", default="")
    ap.add_argument("--socle", type=float, default=3.0)
    ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--balc-levels", type=int, default=2)
    ap.add_argument("--balc-proj", type=float, default=1.3)
    ap.add_argument("--dormer-rows", default="0.30:7,0.62:6")
    ap.add_argument("--chimneys", type=int, default=3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    center = tuple(float(x) for x in a.center.split(",")) if a.center else None
    picked = L.extract(a.gml, name=a.name or None, center=center, radius=40)
    if not picked:
        sys.exit("kein Gebäude gefunden")
    allpts = np.vstack([P for _, polys in picked for _, P in polys])
    o = np.array([allpts[:, 0].min(), allpts[:, 1].min(), allpts[:, 2].min()])
    ctr_en = allpts[:, :2].mean(0)

    # Talseite
    front = None
    if a.front_az is not None:
        az = np.radians(a.front_az); front = np.array([np.sin(az), np.cos(az)])
    elif a.dgm and a.dgm_origin:
        oe = tuple(float(x) for x in a.dgm_origin.split(","))
        front = D.front_from_dgm(a.dgm, oe, ctr_en)
    if front is None:
        front = D.front_from_footprint(allpts[:, :2] - o, ctr_en - o)
    print(f"Talseite Azimut {np.degrees(np.arctan2(front[0],front[1]))%360:.0f}°")

    # ECHTE Geometrie
    roof = L.build_mesh(picked, types={"RoofSurface"}, origin=o)[0]
    walls = L.build_mesh(picked, types={"WallSurface", "ClosureSurface"}, origin=o)[0]
    sockel, wand = D.split_z(walls, a.socle)

    levels = [a.socle + i * a.floor + 0.1 for i in range(a.balc_levels)]
    balkone = simple_balconies(walls, front, levels, a.balc_proj)

    eave = min([m.get("eave_m") for m, _ in picked if m.get("eave_m")] or [a.socle + a.balc_levels*a.floor])
    ridge = max([m.get("ridge_m") for m, _ in picked if m.get("ridge_m")] or [eave + 8])
    rows = []
    for spec in a.dormer_rows.split(","):
        frac, n = spec.split(":")
        r = D.dormer_row(roof, eave + float(frac) * (ridge - eave), int(n), front)
        if r: rows.append(r)
    gauben = trimesh.util.concatenate(rows) if rows else None
    kamine = D.chimneys(roof, a.chimneys)

    # X/Y zentrieren
    cx, cy = (allpts[:, 0].min() + np.ptp(allpts[:, 0]) / 2 - o[0],
              allpts[:, 1].min() + np.ptp(allpts[:, 1]) / 2 - o[1])

    palette = {"sockel": (0.42, 0.40, 0.37, 1), "wand": (0.80, 0.70, 0.47, 1),
               "dach": (0.16, 0.11, 0.09, 1), "balkone": (0.28, 0.18, 0.11, 1),
               "gauben": (0.30, 0.22, 0.17, 1), "kamine": (0.35, 0.31, 0.29, 1)}
    meshes = {"sockel": sockel, "wand": wand, "dach": roof,
              "balkone": balkone, "gauben": gauben, "kamine": kamine}
    groups = {}
    for nm, m in meshes.items():
        if m is None or len(m.faces) == 0:
            continue
        v, f = py_mesh(m, cx, cy)
        groups[nm] = (list(palette[nm]), v, f)
        print(f"  {nm}: {len(v)} V / {len(f)} F")

    # literal rendern (kompakt)
    body = "{\n" + ",\n".join(
        f'  "{nm}": ({rgba}, {v}, {f})' for nm, (rgba, v, f) in groups.items()) + "\n}"
    code = TEMPLATE.format(title=a.name or "LOD2-Gebäude", groups=body, nparts=len(groups))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(code)
    print(f"\n-> {a.out}  ({os.path.getsize(a.out)/1024:.0f} kB, {len(groups)} Gruppen, echte Geometrie eingebettet)")


if __name__ == "__main__":
    main()
