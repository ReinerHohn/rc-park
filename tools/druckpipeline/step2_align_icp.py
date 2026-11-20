#!/usr/bin/env python3
"""Schritt 2 — Automatisches Alignment & Registrierung (Open3D).

Das 3DGS-Foto-Mesh ist SKALENFREI und in beliebiger Lage. Es wird auf das georeferenzierte LoD2-Mesh
+ die LiDAR-Punktwolke ausgerichtet UND metrisch skaliert, sodass es exakt in das amtliche
Koordinatensystem passt (gemeinsamer geometrischer Anker für alles Weitere).

Strategie (robust, grob→fein):
  1. Grob-Skalierung über Bounding-Box-Diagonale (bringt beide in dieselbe Größenordnung).
  2. Grob-Registrierung über FPFH-Features + RANSAC (findet die Lage ohne Startschätzung).
  3. Fein-ICP MIT Skalierung (Umeyama / with_scaling=True) → exakter Sim(3)-Fit (Rotation+Translation+Scale).
  4. Fein-ICP Punkt-zu-Ebene gegen LoD2+LiDAR kombiniert → bündige Flächen.

Lauf: python step2_align_icp.py --foto foto_mesh.ply --lod2 lod2.ply --lidar lidar.ply --out foto_aligned.ply
"""
import argparse
import numpy as np
import open3d as o3d


def _down_fpfh(pcd, voxel):
    d = pcd.voxel_down_sample(voxel)
    d.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2, max_nn=30))
    fpfh = o3d.pipelines.registration.compute_fpfh_feature(
        d, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 5, max_nn=100))
    return d, fpfh


def align(foto_pcd, target_pcd, voxel=0.5):
    # 1) Grob-Skalierung über BBox-Diagonale
    def diag(p): e = p.get_axis_aligned_bounding_box().get_extent(); return float(np.linalg.norm(e))
    s0 = diag(target_pcd) / max(1e-6, diag(foto_pcd))
    foto_pcd.scale(s0, center=foto_pcd.get_center())

    # 2) Grob-Registrierung FPFH + RANSAC (scale-invariant genug nach Grob-Skalierung)
    src_d, src_f = _down_fpfh(foto_pcd, voxel); tgt_d, tgt_f = _down_fpfh(target_pcd, voxel)
    ransac = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        src_d, tgt_d, src_f, tgt_f, mutual_filter=True, max_correspondence_distance=voxel * 1.5,
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
        ransac_n=3, checkers=[o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
                              o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(voxel * 1.5)],
        criteria=o3d.pipelines.registration.RANSACConvergenceCriteria(400000, 0.999))
    T_coarse = ransac.transformation

    # 3) Fein-ICP MIT Skalierung (Sim3: Rotation+Translation+Scale) — korrigiert Restskala exakt
    icp_s = o3d.pipelines.registration.registration_icp(
        foto_pcd, target_pcd, voxel * 1.5, T_coarse,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(with_scaling=True),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=80))
    # 4) Fein-ICP Punkt-zu-Ebene (bündige Flächen, enger Threshold)
    target_pcd.estimate_normals()
    icp_p = o3d.pipelines.registration.registration_icp(
        foto_pcd, target_pcd, voxel * 0.4, icp_s.transformation,
        o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=60))
    return s0, icp_p.transformation, icp_p.fitness, icp_p.inlier_rmse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True, help="Foto-Mesh .ply aus Schritt 1 (skalenfrei)")
    ap.add_argument("--lod2", required=True, help="georef. LoD2-Mesh/-Punktwolke .ply")
    ap.add_argument("--lidar", default="", help="optional LiDAR-Punktwolke .ply (ergänzt das Ziel)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--voxel", type=float, default=0.5)
    a = ap.parse_args()

    foto = o3d.io.read_triangle_mesh(a.foto)
    foto_pcd = foto.sample_points_uniformly(200000) if len(foto.triangles) else o3d.io.read_point_cloud(a.foto)
    lod2 = o3d.io.read_triangle_mesh(a.lod2)
    tgt = lod2.sample_points_uniformly(200000) if len(lod2.triangles) else o3d.io.read_point_cloud(a.lod2)
    if a.lidar:
        tgt += o3d.io.read_point_cloud(a.lidar)             # LiDAR ergänzt Gelände/Proportionen

    s0, T, fit, rmse = align(foto_pcd, tgt, a.voxel)
    # Transform auf das VOLLE Foto-Mesh anwenden (nicht nur die Sample-Punkte)
    foto.scale(s0, center=foto.get_center()); foto.transform(T)
    o3d.io.write_triangle_mesh(a.out, foto)
    np.save(a.out + ".transform.npy", {"scale0": s0, "T": np.asarray(T)}, allow_pickle=True)
    print(f"Alignment: fitness={fit:.3f} rmse={rmse:.3f} m, Grob-Skala s0={s0:.3f} -> {a.out}")


if __name__ == "__main__":
    main()
