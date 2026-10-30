#!/usr/bin/env python3
"""mesh_druckbar.py — beliebiges (auch GEKAUFTES, nicht-druckfertiges) Mesh → druckbarer Solid.

Nimmt ein Render-/Game-Mesh (offene Flächen, non-manifold, keine Wandstärke, sich durchdringende
Teile) und macht daraus ein watertight, slicebares Modell:

  Diagnose → Reparatur (merge/normals/Löcher) → [falls nötig] Solidify per VOXEL-Remesh
  (robust gegen offene Shells/non-manifold) → Druckbarkeits-Check → STL.

  python3 tools/mesh_druckbar.py <in.stl|obj|glb|ply> <out.stl> [--pitch 0.8] [--solidify]

Das ist der de-risk fürs Münster: erst am echten Fall beweisen, dass 'kaufen + nachbearbeiten'
geht, DANN ein detailliertes Mesh kaufen.
"""
import argparse
import numpy as np
import trimesh


def diagnose(m, tag):
    opened = int((trimesh.grouping.group_rows(m.edges_sorted, require_count=1)).shape[0]) \
        if len(m.faces) else 0
    print(f"[{tag}] F={len(m.faces)} V={len(m.vertices)}  watertight={m.is_watertight}  "
          f"winding_ok={m.is_winding_consistent}  euler={m.euler_number}  "
          f"Teile={m.body_count}  offene_Kanten~{opened}  "
          f"bbox={np.round(m.extents, 1)}")
    return m.is_watertight


def repair(m):
    m.merge_vertices()
    try:
        m.update_faces(m.nondegenerate_faces())
        m.update_faces(m.unique_faces())
    except Exception:
        pass
    m.remove_unreferenced_vertices()
    trimesh.repair.fix_winding(m)
    trimesh.repair.fix_normals(m)
    try:
        trimesh.repair.fill_holes(m)
    except Exception:
        pass
    return m


def solidify_voxel(m, pitch):
    """robustes Solidify: Voxelisieren → füllen → als watertight Block-Solid (Marching-Cubes)."""
    vg = m.voxelized(pitch=pitch).fill()
    try:
        solid = vg.marching_cubes.copy()
        solid.apply_transform(vg.transform)     # Voxel-Index -> Welt (pitch + Ursprung)
        solid.merge_vertices(); trimesh.repair.fix_normals(solid)
        if solid.is_watertight:
            return solid
    except Exception:
        pass
    return vg.as_boxes()            # Fallback: Voxelwürfel-Union (immer watertight, bereits in Welt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--pitch", type=float, default=0.0, help="Voxelgröße (Modell-Einheiten); 0=auto bbox/160")
    ap.add_argument("--solidify", action="store_true", help="immer voxel-solidify (für offene Shells)")
    a = ap.parse_args()

    m = trimesh.load(a.inp, process=False, force="mesh")
    print(f"geladen: {a.inp}")
    wt = diagnose(m, "roh")

    m = repair(m)
    wt = diagnose(m, "repariert")

    if a.solidify or not wt:
        pitch = a.pitch or float(max(m.extents) / 160.0)
        print(f"-> Solidify per Voxel-Remesh (pitch={pitch:.3f})")
        m = solidify_voxel(m, pitch)
        diagnose(m, "solidified")

    # Druckbarkeits-Check
    ncomp = m.body_count
    print(f"\nDRUCKBARKEIT: watertight={m.is_watertight}  Teile={ncomp}  "
          f"Volumen={m.volume:.1f}  bbox={np.round(m.extents,1)}")
    print("  -> " + ("OK: watertight, slicebar." if m.is_watertight
                     else "ACHTUNG: noch nicht watertight — pitch kleiner oder --solidify."))
    m.export(a.out)
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
