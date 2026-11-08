#!/usr/bin/env python3
"""wolke_zu_netz.py - Kandidaten Punktwolke -> Netz mit VERSCHIEDENEN Algorithmen (open3d), alle im Modellrahmen als STL (mm im Massstab 1:87) fuer tools/modell_wettbewerb.py.
  /media/oem/scan/venv-o3d/bin/python -I tools/wolke_zu_netz.py --wolke W.npy --huelle MODELL.stl --aus DIR [--massstab 87] [--rand 2] [--nur poisson8,bpa,alpha1.0]
Wolke (Meter, Modellrahmen) wird auf die Huelle des Referenzmodells + rand beschnitten (Nachbarn/Strasse raus), Voxel 0,05, Ausreisser raus, Normalen (Hybrid-Suche) konsistent orientiert.
Algorithmen: poisson<tiefe> (Dichtefilter 10 %), bpa (Ball-Pivoting, Radien aus Punktabstand), alpha<a>, huelle (konvexe Huelle je Hoehenscheibe = grober Koerper)."""
import argparse, os, numpy as np, open3d as o3d, trimesh
ap = argparse.ArgumentParser(); ap.add_argument("--wolke", required=True); ap.add_argument("--huelle", required=True); ap.add_argument("--aus", required=True); ap.add_argument("--massstab", type=float, default=87)
ap.add_argument("--rand", type=float, default=2.0); ap.add_argument("--nur"); a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True); k = a.massstab / 1000.0
X = np.load(a.wolke).astype(np.float64); hb = trimesh.load(a.huelle).bounds * k; ok = np.all((X >= hb[0] - a.rand) & (X <= hb[1] + a.rand), 1); X = X[ok]
def vorbereiten(vox=0.05, nr=0.4, nn=40):
    pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(X)); pc = pc.voxel_down_sample(vox); pc, _ = pc.remove_statistical_outlier(20, 2.0)
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=nr, max_nn=nn)); pc.orient_normals_consistent_tangent_plane(30); return pc
_cache = {}
def pcloud(vox, nr):
    if (vox, nr) not in _cache: _cache[(vox, nr)] = vorbereiten(vox, nr); print("Punkte", len(_cache[(vox, nr)].points), "vox", vox, "nr", nr, flush=True)
    return _cache[(vox, nr)]
pc = pcloud(0.05, 0.4)
def raus(name, mesh):
    mesh.remove_degenerate_triangles(); mesh.remove_duplicated_vertices(); mesh.remove_non_manifold_edges(); v = np.asarray(mesh.vertices) / k; f = np.asarray(mesh.triangles)
    t = trimesh.Trimesh(v, f, process=False); t.export(os.path.join(a.aus, name + ".stl")); print(f"{name}: {len(f)} Dreiecke, wasserdicht {t.is_watertight}", flush=True)
alg = (a.nur or "poisson8,poisson9,poisson10,bpa,alpha0.5,alpha1.0").split(",")
for al in alg:
    try:
        if al.startswith("poisson"):                                               # poisson9_r0.2_q0.02_v0.03_lin_t10 : Tiefe, Normalenradius, Dichtequantil, Voxel, lineare Anpassung, Taubin-Iterationen
            tk = al.split("_"); tiefe = int(tk[0][7:]); r = {t[0]: t[1:] for t in tk[1:]}; vox, nr, q = float(r.get("v", 0.05)), float(r.get("r", 0.4)), float(r.get("q", 0.10))
            m, d = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcloud(vox, nr), depth=tiefe, scale=float(r.get("s", 1.1)), linear_fit=("lin" in tk)); d = np.asarray(d); m.remove_vertices_by_mask(d < np.quantile(d, q))
            if "t" in r: m = m.filter_smooth_taubin(number_of_iterations=int(r["t"]))
            raus(al, m)
        elif al == "bpa":
            dist = np.mean(pc.compute_nearest_neighbor_distance()); r = [dist * 1.5, dist * 3, dist * 6]; raus(al, o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(pc, o3d.utility.DoubleVector(r)))
        elif al.startswith("alpha"):
            raus(al, o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pc, float(al[5:])))
    except Exception as e: print(al, "FEHLER", str(e)[:120], flush=True)
