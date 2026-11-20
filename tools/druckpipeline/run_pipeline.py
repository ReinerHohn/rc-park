#!/usr/bin/env python3
"""run_pipeline.py — Orchestrator der 4-Schritt-Druckpipeline.

Kettet step1 → step2 → step2b → step3 → step4 und schreibt alle Zwischendateien in ein
Arbeitsverzeichnis, sodass jeder Schritt einzeln wiederholbar ist. Schritte 1/2/2b laufen im
Python-Environment (open3d/trimesh), Schritte 3/4 rufen Blender headless auf.

Beispiel:
  python run_pipeline.py \
      --splat splat.ply --lod2 lod2.ply --lidar lidar.ply \
      --blender /usr/bin/blender --work out/ --name hofgut \
      [--terrain lidar_floor.ply] [--skip 1,2]

--skip überspringt bereits erzeugte Schritte (nutzt vorhandene Zwischendateien).
"""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def run(cmd):
    print("\n$ " + " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"Schritt fehlgeschlagen (exit {r.returncode}): {cmd[0]} {cmd[1] if len(cmd)>1 else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splat", required=True, help="3DGS-Punktwolke .ply (Schritt 1)")
    ap.add_argument("--lod2", required=True, help="georef. LoD2-Mesh .ply/.obj")
    ap.add_argument("--lidar", default="", help="optionale LiDAR-Punktwolke .ply")
    ap.add_argument("--terrain", default="", help="optionale LiDAR-Geländefläche als Sockel (Schritt 4)")
    ap.add_argument("--blender", default="blender", help="Pfad zur Blender-Binary")
    ap.add_argument("--work", default="out", help="Arbeitsverzeichnis für Zwischendateien")
    ap.add_argument("--name", default="model", help="Basisname der Ausgaben")
    ap.add_argument("--depth", type=int, default=11, help="Poisson-Tiefe (Schritt 1)")
    ap.add_argument("--subdiv", type=int, default=8, help="Wand-Unterteilung (Schritt 3)")
    ap.add_argument("--skip", default="", help="z.B. '1,2' um Schritte zu überspringen")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    skip = set(s.strip() for s in a.skip.split(",") if s.strip())

    foto_mesh = os.path.join(a.work, f"{a.name}_foto_mesh.ply")
    aligned = os.path.join(a.work, f"{a.name}_aligned.ply")
    walls = os.path.join(a.work, "waende")
    relief = os.path.join(a.work, f"{a.name}_relief.blend")
    out_stl = os.path.join(a.work, f"{a.name}_print.stl")

    # 1) 3DGS-Punktwolke → dichtes Foto-Mesh
    if "1" not in skip:
        run([PY, os.path.join(HERE, "step1_splat_to_mesh.py"),
             "--pointcloud", a.splat, "--out", foto_mesh, "--depth", str(a.depth)])

    # 2) Alignment + Skalierung auf LoD2 (+ LiDAR)
    if "2" not in skip:
        cmd = [PY, os.path.join(HERE, "step2_align_icp.py"),
               "--foto", foto_mesh, "--lod2", a.lod2, "--out", aligned]
        if a.lidar:
            cmd += ["--lidar", a.lidar]
        run(cmd)

    # 2b) Relief-Heightmaps je Wand backen
    if "2b" not in skip:
        run([PY, os.path.join(HERE, "step2b_bake_heightmap.py"),
             "--foto", aligned, "--lod2", a.lod2, "--out", walls])

    # 3) Blender: Wände subdividen + Displace-Relief
    if "3" not in skip:
        run([a.blender, "--background", "--python", os.path.join(HERE, "step3_relief_bake.py"), "--",
             "--lod2", a.lod2, "--walls", walls, "--out", relief, "--subdiv", str(a.subdiv)])

    # 4) Blender: Make-Manifold, Boden schließen, (Gelände-Union), STL-Export
    if "4" not in skip:
        cmd = [a.blender, "--background", "--python", os.path.join(HERE, "step4_solidify_print.py"), "--",
               "--in", relief, "--out", out_stl]
        if a.terrain:
            cmd += ["--terrain", a.terrain]
        run(cmd)

    print(f"\n=== Pipeline fertig -> {out_stl} ===")


if __name__ == "__main__":
    main()
