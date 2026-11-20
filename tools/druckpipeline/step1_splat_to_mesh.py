#!/usr/bin/env python3
"""Schritt 1 — Hochdetailliertes Foto-Mesh aus 3D-Gaussian-Splatting.

Nach dem 3DGS-Training (Nerfstudio `ns-train splatfacto` bzw. Postshot) liegen vor:
  (A) eine dichte Punktwolke (Splat-Zentren / exportierte Points), ODER
  (B) posierte RGB-D-Frames (gerenderte Tiefen + Kameras aus dem nerfstudio-dataparser).

Dieses Modul erzeugt daraus ein dichtes, detailreiches Dreiecksnetz, das die FEINEN Fassadendetails
als echte Geometrie (Vertices) abbildet — per **Poisson** (aus Punktwolke) oder **TSDF-Fusion**
(aus RGB-D). Poisson ist der robuste Default für eine Splat-Punktwolke.

Export-Hinweise:
  Nerfstudio:  ns-export gaussian-splat --load-config <cfg> --output-dir exp/   # -> splat.ply
               ns-export pointcloud     --load-config <cfg> --num-points 3000000 --output-dir exp/
  Postshot:    Export als .ply Pointcloud / .ply Splat.

Lauf:  python step1_splat_to_mesh.py --pointcloud splat.ply --out foto_mesh.ply --depth 11
"""
import argparse
import numpy as np
import open3d as o3d


def mesh_from_pointcloud(pcd_path: str, depth: int = 11, density_quantile: float = 0.05,
                         voxel: float = 0.0) -> o3d.geometry.TriangleMesh:
    """Dichtes Mesh aus Punktwolke via Screened Poisson. Entfernt niederdichte (ausgefranste) Bereiche."""
    pcd = o3d.io.read_point_cloud(pcd_path)
    if voxel > 0:                                             # optional ausdünnen (Rauschen/Speicher)
        pcd = pcd.voxel_down_sample(voxel)
    # 1) Normalen schätzen + konsistent orientieren (Poisson braucht gerichtete Normalen)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 3 if voxel else 0.1, max_nn=50))
    pcd.orient_normals_consistent_tangent_plane(k=30)
    # 2) Screened Poisson Reconstruction → wasserdichtes, dichtes Mesh
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth, width=0, scale=1.1, linear_fit=False)
    # 3) niederdichte Zipfel (Hallucinations an den Rändern) wegschneiden
    dens = np.asarray(densities)
    keep = dens > np.quantile(dens, density_quantile)
    mesh.remove_vertices_by_mask(~keep)
    mesh.remove_degenerate_triangles(); mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges(); mesh.compute_vertex_normals()
    return mesh


def mesh_from_rgbd_tsdf(frames: list, intrinsic: o3d.camera.PinholeCameraIntrinsic,
                        voxel_length: float = 0.01, sdf_trunc: float = 0.04) -> o3d.geometry.TriangleMesh:
    """TSDF-Fusion aus posierten RGB-D-Frames (frames: list[(rgb_path, depth_path, extrinsic_4x4)]).
    Liefert sehr saubere, fein aufgelöste Oberflächen, wenn Tiefen+Posen gut sind (Alternative zu Poisson)."""
    vol = o3d.pipelines.integration.ScalableTSDFVolume(
        voxel_length=voxel_length, sdf_trunc=sdf_trunc,
        color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8)
    for rgb_path, depth_path, extr in frames:
        color = o3d.io.read_image(rgb_path); depth = o3d.io.read_image(depth_path)
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color, depth, depth_scale=1000.0, depth_trunc=5.0, convert_rgb_to_intensity=False)
        vol.integrate(rgbd, intrinsic, np.linalg.inv(np.asarray(extr)))
    mesh = vol.extract_triangle_mesh(); mesh.compute_vertex_normals()
    return mesh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pointcloud", help="3DGS-Punktwolke .ply (Poisson-Pfad)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--depth", type=int, default=11, help="Poisson-Octree-Tiefe (höher=mehr Detail, langsamer)")
    ap.add_argument("--voxel", type=float, default=0.0, help="optionale Downsample-Voxelgröße in m")
    ap.add_argument("--density-quantile", type=float, default=0.05)
    a = ap.parse_args()
    if not a.pointcloud:
        raise SystemExit("Bitte --pointcloud angeben (TSDF-Pfad per mesh_from_rgbd_tsdf importieren).")
    mesh = mesh_from_pointcloud(a.pointcloud, a.depth, a.density_quantile, a.voxel)
    o3d.io.write_triangle_mesh(a.out, mesh)
    print(f"Foto-Mesh: {len(mesh.vertices)} Verts, {len(mesh.triangles)} Faces -> {a.out}")


if __name__ == "__main__":
    main()
