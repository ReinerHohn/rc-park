#!/usr/bin/env python3
"""Schritt 3 — Geometrische Fusion & Relief-Baking (Blender bpy).

Das SAUBERE LoD2-Mesh ist die Druck-Basis (gerade Wände, amtliche Maße). Jede Wandfläche wird
hochgradig unterteilt und bekommt über einen **Displace-Modifier** die in Schritt 2b gebackene
Heightmap aufgeprägt → Fensterrahmen/Vorsprünge/Ornamente stehen als ECHTES Relief (Vertices) aus
der Wand, nicht als flache Textur.

Kern-Idee:
  - Displace-Stärke = gemessene metrische Tiefenspanne der Wand (span_m aus <wall>_meta.json),
    Mitte (Grauwert 0.5) = Wandebene. So ist das Relief maßstabsgetreu, nicht geschätzt.
  - Pro Wand ein eigener Modifier, der NUR die Faces dieser Wand verschiebt (Vertex-Group).
  - UV wird planar aus der Wand-Ebene (origin/u/v aus dem Meta) erzeugt → Pixel sitzt am realen Ort.

Lauf (headless):
  blender --background --python step3_relief_bake.py -- \
      --lod2 lod2.obj --walls wände/ --out relief.blend --subdiv 8 --midlevel 0.5
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector


def _argv():
    """Argumente hinter '--' an Blender vorbei an uns durchreichen."""
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--lod2", required=True, help="sauberes LoD2-Mesh (.obj/.ply/.glb)")
    ap.add_argument("--walls", required=True, help="Ordner aus Schritt 2b (index.json + wallNN_*)")
    ap.add_argument("--out", required=True, help="Ausgabe .blend (geht weiter an Schritt 4)")
    ap.add_argument("--subdiv", type=int, default=8, help="Unterteilungs-Level der Wände (mehr=feiner)")
    ap.add_argument("--midlevel", type=float, default=0.5, help="Grauwert der Wandebene (0.5 = signiert)")
    ap.add_argument("--max-strength", type=float, default=1.0, help="Deckel der Displace-Stärke in m")
    return ap.parse_args(a)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_mesh(path):
    """LoD2 laden (Format nach Endung) und als aktives Objekt zurückgeben."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    else:
        raise SystemExit(f"Format {ext} nicht unterstützt")
    # alle importierten Mesh-Teile zu EINEM Objekt verbinden
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def _load_meta_walls(folder):
    idx = json.load(open(os.path.join(folder, "index.json")))
    walls = []
    for e in idx:
        meta = json.load(open(os.path.join(folder, f"wall{e['id']:02d}_meta.json")))
        meta["img"] = os.path.join(folder, f"wall{e['id']:02d}_height.png")
        meta["id"] = e["id"]
        walls.append(meta)
    return walls


def _wall_faces(bm, meta, tol_n=0.15, tol_d=0.6):
    """Face-Indizes des aktuellen Meshes, die zu dieser Wandebene (Normale+Offset) gehören."""
    n = Vector(meta["normal"]).normalized()
    o = Vector(meta["origin"])
    d0 = o.dot(n)
    hits = []
    for f in bm.faces:
        fn = f.normal
        if fn.length < 1e-9:
            continue
        if fn.normalized().dot(n) < (1 - tol_n):
            continue
        if abs(f.calc_center_median().dot(n) - d0) > tol_d:
            continue
        hits.append(f.index)
    return hits


def assign_wall_uv_and_group(obj, meta):
    """Planare UV aus der Wand-Ebene + Vertex-Group 'wall<ID>' für die Faces dieser Wand.
    UV: (u,v) = Projektion (vertex-origin) auf die gemessenen Wand-Achsen, normiert auf w/h."""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    face_ids = _wall_faces(bm, meta)
    if not face_ids:
        bm.free(); return 0
    u = Vector(meta["u"]).normalized(); v = Vector(meta["v"]).normalized()
    o = Vector(meta["origin"]); w = max(1e-6, meta["w"]); h = max(1e-6, meta["h"])
    uv_lay = bm.loops.layers.uv.get("wall_uv") or bm.loops.layers.uv.new("wall_uv")
    sel = set(face_ids)
    vgroup_verts = set()
    for f in bm.faces:
        if f.index not in sel:
            continue
        for loop in f.loops:
            p = loop.vert.co - o
            loop[uv_lay].uv = (p.dot(u) / w, p.dot(v) / h)
            vgroup_verts.add(loop.vert.index)
    bm.to_mesh(me); bm.free()
    vg = obj.vertex_groups.new(name=f"wall{meta['id']:02d}")
    vg.add(list(vgroup_verts), 1.0, "REPLACE")
    return len(face_ids)


def add_displace(obj, meta, subdiv, midlevel, max_strength):
    """Subdivide (per Modifier, zerstörungsfrei) + Displace-Modifier mit der Wand-Heightmap."""
    # 1) feine Unterteilung — nur EINMAL fürs ganze Objekt (alle Wände teilen sie sich)
    if "Subdiv" not in obj.modifiers:
        sub = obj.modifiers.new("Subdiv", "SUBSURF")
        sub.subdivision_type = "SIMPLE"      # SIMPLE: teilt ohne zu glätten (Wände bleiben plan)
        sub.levels = subdiv; sub.render_levels = subdiv
    # 2) Heightmap als Bild-Textur laden
    img = bpy.data.images.load(meta["img"], check_existing=True)
    tex = bpy.data.textures.new(f"relief{meta['id']:02d}", "IMAGE")
    tex.image = img; tex.extension = "EXTEND"
    # 3) Displace entlang der GEMESSENEN Wand-Normale, Stärke = Tiefenspanne in m (gedeckelt)
    span = min(max_strength, float(meta.get("span_m", 0.0)))
    mod = obj.modifiers.new(f"disp{meta['id']:02d}", "DISPLACE")
    mod.texture = tex
    mod.texture_coords = "UV"; mod.uv_layer = "wall_uv"
    # Verschiebung entlang der Vertex-Normale — bei der planen (Simple-Subsurf) Wand ist die
    # Vertex-Normale == gemessene Wand-Normale, also exakt senkrecht zur Fassade → korrektes Relief.
    mod.direction = "NORMAL"
    mod.mid_level = midlevel                 # 0.5: Grauwert 0.5 = keine Verschiebung (signiert)
    mod.strength = span                      # metrisch: voller Grauwert-Hub == span_m Meter
    mod.vertex_group = f"wall{meta['id']:02d}"   # NUR diese Wand bewegen
    return span


def main():
    a = _argv()
    reset_scene()
    obj = import_mesh(a.lod2)
    # Transform anwenden, damit Normalen/Koordinaten im Weltmaß stimmen
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True); bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    walls = _load_meta_walls(a.walls)
    print(f"{len(walls)} Wände aus {a.walls}")
    done = 0
    for meta in walls:
        nf = assign_wall_uv_and_group(obj, meta)
        if nf == 0:
            print(f"  Wand {meta['id']}: KEINE passende Fläche im LoD2 gefunden (übersprungen)")
            continue
        span = add_displace(obj, meta, a.subdiv, a.midlevel, a.max_strength)
        print(f"  Wand {meta['id']}: {nf} Faces, Relief {span:.3f} m")
        done += 1
    # Modifier backen (anwenden), damit das Relief echte Geometrie wird (nicht nur Vorschau)
    bpy.context.view_layer.objects.active = obj
    for m in list(obj.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except RuntimeError as e:
            print(f"  Modifier {m.name} nicht anwendbar: {e}")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.out))
    print(f"-> {done}/{len(walls)} Wände mit Relief, gespeichert: {a.out}")


if __name__ == "__main__":
    main()
