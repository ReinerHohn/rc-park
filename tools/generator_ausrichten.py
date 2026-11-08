#!/usr/bin/env python3
"""generator_ausrichten.py - BS51: alten Generator-Kaufhaus (kaufhaus_measured.glb, Meter, eigener Rahmen) in den Wolkenrahmen (Netzrahmen, m) legen.
Global: FPFH+RANSAC (Open3D, Massstab fest 1), dann ICP; Ausgabe 4x4 + Fitness/RMSE. Danach Foto-Diff des ausgerichteten Generators.
  venv-o3d/bin/python -I tools/generator_ausrichten.py glb wolke.npy aus.json [--aus-stl x.stl --box x0,y0,z0,x1,y1,z1 --voxel 0.4]"""
import sys, json, argparse, numpy as np, trimesh, open3d as o3d
ap = argparse.ArgumentParser(); ap.add_argument("glb"); ap.add_argument("wolke"); ap.add_argument("aus"); ap.add_argument("--aus-stl"); ap.add_argument("--voxel", type=float, default=0.4)
ap.add_argument("--box", default="-14.6,2.7,0.6,15.7,17.0,19.9"); ap.add_argument("--ohne", default="dachziegel,helm,sprossen")
a = ap.parse_args(); sc = trimesh.load(a.glb); skip = set(a.ohne.split(","))
parts = [g for n, g in sc.geometry.items() if n not in skip]; G = trimesh.util.concatenate(parts); print("Generator Flaechen (ohne", skip, ")", len(G.faces), "bounds", G.bounds.round(1).tolist(), flush=True)
X = np.load(a.wolke).astype(np.float64); b = np.array(a.box.split(","), float); X = X[np.all((X >= b[:3] - 0.5) & (X <= b[3:] + 0.5), 1)]; print("Wolke", len(X), flush=True)
P = trimesh.sample.sample_surface(G, 200000)[0]
def pc(x): p = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(x)); p = p.voxel_down_sample(a.voxel); p.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=a.voxel * 2.5, max_nn=30)); return p
src, dst = pc(P), pc(X); f = lambda p: o3d.pipelines.registration.compute_fpfh_feature(p, o3d.geometry.KDTreeSearchParamHybrid(radius=a.voxel * 5, max_nn=100))
r = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(src, dst, f(src), f(dst), True, a.voxel * 1.5, o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 3,
    [o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(a.voxel * 1.5)], o3d.pipelines.registration.RANSACConvergenceCriteria(2000000, 0.999))
print("RANSAC fitness", round(r.fitness, 3), "rmse", round(r.inlier_rmse, 3), flush=True)
best = r
for th in (1.0, 0.5, 0.25):
    best = o3d.pipelines.registration.registration_icp(src, dst, th, best.transformation, o3d.pipelines.registration.TransformationEstimationPointToPlane())
    print("ICP th", th, "fitness", round(best.fitness, 3), "rmse", round(best.inlier_rmse, 3), flush=True)
T = best.transformation; d = np.asarray(o3d.geometry.PointCloud(o3d.utility.Vector3dVector(P)).transform(T).compute_point_cloud_distance(o3d.geometry.PointCloud(o3d.utility.Vector3dVector(X))))
print("Abstand Generator->Wolke Median %.2f m P75 %.2f P90 %.2f; <0.1m %.0f%% <0.3m %.0f%%" % (*np.percentile(d, [50, 75, 90]), 100 * (d < .1).mean(), 100 * (d < .3).mean()))
json.dump(dict(T=np.asarray(T).tolist(), fitness=best.fitness, rmse=best.inlier_rmse), open(a.aus, "w"), indent=1)
if a.aus_stl:
    full = trimesh.util.concatenate(list(sc.geometry.values())); full.apply_transform(np.asarray(T)); full.vertices = full.vertices / 0.087; full.export(a.aus_stl); print("STL (mm, 1:87-Rahmen)", a.aus_stl, len(full.faces))
