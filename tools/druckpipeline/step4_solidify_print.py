#!/usr/bin/env python3
"""Schritt 4 — Post-Processing für den 3D-Druck (Blender bpy): Solid-Making, Manifold, Export.

Das Relief-Mesh aus Schritt 3 ist ein detailreiches, aber evtl. offenes Oberflächennetz.
Hier wird daraus ein druckbarer, wasserdichter Volumenkörper:

  1. Make-Manifold  — Löcher/Nicht-Mannigfaltigkeiten automatisch schließen (3D-Print-Toolbox
                      `mesh.print3d_clean_non_manifold`, Fallback: Fill-Holes + Recalc-Normals).
  2. Unterseite schließen — das Gebäude auf eine ebene Grundfläche kappen & deckeln → solider Boden.
  3. (optional) Geländeplatte aus LiDAR als solider Sockel UNTER dem Gebäude, dann Boolean-UNION,
                sodass Gebäude + Sockel EIN wasserdichter Körper sind (kein schwebendes Haus).
  4. Validieren (0 non-manifold, 0 Löcher) & als fehlerfreie .STL/.OBJ exportieren.

Lauf (headless):
  blender --background --python step4_solidify_print.py -- \
      --in relief.blend --out hofgut_print.stl [--terrain lidar_floor.ply] [--z-floor auto]
"""
import bpy, bmesh, sys, os
from mathutils import Vector


def _argv():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="relief.blend aus Schritt 3 (oder .obj/.stl)")
    ap.add_argument("--out", required=True, help="Ziel .stl ODER .obj (Format nach Endung)")
    ap.add_argument("--terrain", default="", help="optionale LiDAR-Geländefläche (.ply/.obj) als Sockel")
    ap.add_argument("--z-floor", default="auto", help="Boden-Z zum Kappen ('auto' = Mesh-Minimum)")
    ap.add_argument("--base-thickness", type=float, default=2.0, help="Dicke der Geländeplatte in m")
    return ap.parse_args(a)


def _enable_print3d():
    """3D-Print-Toolbox aktivieren (liefert robustes make-manifold)."""
    try:
        bpy.ops.preferences.addon_enable(module="object_print3d_utils")
        return True
    except Exception:
        return False


def load_scene(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        {".obj": bpy.ops.wm.obj_import, ".ply": bpy.ops.wm.ply_import,
         ".stl": bpy.ops.wm.stl_import}[ext](filepath=path)
    obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True)
    return obj


def make_manifold(obj, has_print3d):
    """Alle Löcher/offenen Kanten schließen → wasserdicht."""
    bpy.context.view_layer.objects.active = obj
    if has_print3d:
        try:
            bpy.ops.mesh.print3d_clean_non_manifold()      # schließt Löcher + räumt Non-Manifold
            return
        except Exception as e:
            print(f"  print3d_clean fehlgeschlagen ({e}), Fallback.")
    # Fallback ohne Add-on: doppelte Verts verschmelzen, Löcher füllen, Normalen neu
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=1e-4)
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.mesh.select_non_manifold()
    bpy.ops.mesh.fill_holes(sides=0)                       # 0 = beliebig große Löcher
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def close_bottom(obj, z_floor):
    """Unter z_floor abschneiden und die Schnittfläche deckeln → ebener, solider Boden."""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    if z_floor == "auto":
        z = min(v.co.z for v in bm.verts)
    else:
        z = float(z_floor)
    # knapp über dem Minimum kappen, damit das Relief vollständig bleibt
    zc = z + 1e-4
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                                 plane_co=(0, 0, zc), plane_no=(0, 0, 1), clear_inner=True)
    # offene Rand-Schleife an der Schnittebene schließen
    edges = [e for e in bm.edges if e.is_boundary]
    if edges:
        bmesh.ops.edgenet_fill(bm, edges=edges)
        bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    return zc


def add_terrain_base(obj, terrain_path, z_top, thickness):
    """LiDAR-Gelände laden, zu einer soliden Platte extrudieren (Oberkante an Gebäudefuß),
    dann Boolean-UNION mit dem Gebäude → EIN wasserdichter Körper."""
    ext = os.path.splitext(terrain_path)[1].lower()
    {".obj": bpy.ops.wm.obj_import, ".ply": bpy.ops.wm.ply_import,
     ".stl": bpy.ops.wm.stl_import}[ext](filepath=terrain_path)
    terr = bpy.context.selected_objects[0]
    # Gelände-Oberfläche nach unten zu Volumen schließen (Solidify)
    sol = terr.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = thickness; sol.offset = -1.0           # Material nach unten
    bpy.context.view_layer.objects.active = terr
    bpy.ops.object.modifier_apply(modifier="Solidify")
    # Boolean-UNION: Gebäude + Sockel verschmelzen
    bpy.context.view_layer.objects.active = obj
    boo = obj.modifiers.new("Union", "BOOLEAN")
    boo.operation = "UNION"; boo.solver = "EXACT"; boo.object = terr
    bpy.ops.object.modifier_apply(modifier="Union")
    bpy.data.objects.remove(terr, do_unlink=True)


def report(obj, has_print3d):
    """Kurzer Druckbarkeits-Check: offene Kanten / non-manifold zählen."""
    bm = bmesh.new(); bm.from_mesh(obj.data)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    open_edges = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    status = "OK (wasserdicht)" if non_manifold == 0 and open_edges == 0 else "WARNUNG"
    print(f"  Druckbarkeit: non-manifold={non_manifold}, offene Kanten={open_edges} -> {status}")
    return non_manifold == 0 and open_edges == 0


def export(obj, out):
    bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    ext = os.path.splitext(out)[1].lower()
    out = os.path.abspath(out)
    if ext == ".stl":
        bpy.ops.wm.stl_export(filepath=out, export_selected_objects=True, apply_modifiers=True)
    elif ext == ".obj":
        bpy.ops.wm.obj_export(filepath=out, export_selected_objects=True, apply_modifiers=True)
    else:
        raise SystemExit("Nur .stl oder .obj als Ziel")
    print(f"-> exportiert: {out}")


def main():
    a = _argv()
    has_print3d = _enable_print3d()
    obj = load_scene(a.inp)
    make_manifold(obj, has_print3d)                        # 1) Löcher/Non-Manifold schließen
    zc = close_bottom(obj, a.z_floor)                      # 2) Unterseite deckeln (solider Boden)
    if a.terrain:                                          # 3) optional Gelände-Sockel + Union
        add_terrain_base(obj, a.terrain, zc, a.base_thickness)
        make_manifold(obj, has_print3d)                    # nach dem Boolean erneut säubern
    ok = report(obj, has_print3d)                          # 4) Check
    export(obj, a.out)
    print("FERTIG" + ("" if ok else "  (mit Warnung — Mesh im Slicer prüfen)"))


if __name__ == "__main__":
    main()
