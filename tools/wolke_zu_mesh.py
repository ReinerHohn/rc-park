#!/usr/bin/env python3
"""wolke_zu_mesh.py - farbiges, geschlossenes Netz direkt aus der dichten Punktwolke (Poisson), ohne Handwerte; belegt/geschaetzt getrennt (Register BR).

Wolke (+ optional Videowolke) -> Normalen (nach aussen von der Turmachse) -> Poisson (open3d, MIT) -> Randbereiche geringer Dichte abschneiden -> Vertex-Farben vom naechsten
Wolkenpunkt. Je Netzecke Abstand zum naechsten Messpunkt: <= --belegt Meter = BELEGT, sonst GESCHAETZT (Poisson fuellt Luecken glatt). Ausgabe: farbig.ply, belegt.ply
(geschaetzte Flaechen rot), nur_belegt.ply (Netz ohne geschaetzte Dreiecke), bericht.json (Anteile belegt/geschaetzt, Hoehenverlauf).
  /media/oem/scan/venv-mesh/bin/python -I tools/wolke_zu_mesh.py <wolke_entzerrt.npy> <ausgabe_ordner> [--video dicht_modell.npy dicht_farben.npy] [--depth 9] [--belegt 0.4]
"""
import os, sys, json, argparse, numpy as np, open3d as o3d

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("wolke"); ap.add_argument("aus"); ap.add_argument("--video", nargs=2); ap.add_argument("--depth", type=int, default=9); ap.add_argument("--belegt", type=float, default=0.4)
    ap.add_argument("--dichte-quantil", type=float, default=0.06); ap.add_argument("--zmin-video", type=float, default=38.0); ap.add_argument("--rand", type=float, default=9.0); a = ap.parse_args()
    os.makedirs(a.aus, exist_ok=True); P = np.load(a.wolke).astype(np.float64); fc = a.wolke.replace("_entzerrt.npy", "_farben.npy"); C = np.load(fc).astype(np.float64) / 255.0
    if len(C) != len(P): C = np.full((len(P), 3), 0.6)
    if a.video:
        V = np.load(a.video[0]).astype(np.float64); Cv = np.load(a.video[1]).astype(np.float64) / 255.0; k = (V[:, 2] >= a.zmin_video) & (np.abs(V[:, 0]) <= a.rand) & (np.abs(V[:, 1]) <= a.rand); P = np.vstack([P, V[k]]); C = np.vstack([C, Cv[k]]); print(f"Videopunkte ab {a.zmin_video} m: {k.sum()}")
    k = (np.abs(P[:, 0]) < 14) & (np.abs(P[:, 1]) < 14) & (P[:, 2] > 0) & (P[:, 2] < 70); P, C = P[k], C[k]; print(f"{len(P)} Punkte")
    pc = o3d.geometry.PointCloud(); pc.points = o3d.utility.Vector3dVector(P); pc.colors = o3d.utility.Vector3dVector(C)
    pc, ind = pc.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0); P = np.asarray(pc.points); C = np.asarray(pc.colors); print(f"nach Ausreisserfilter {len(P)}")
    pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.6, max_nn=40)); N = np.asarray(pc.normals); out = P - np.c_[np.zeros(len(P)), np.zeros(len(P)), P[:, 2]]      # nach aussen von der Turmachse (x,y), z-Anteil ignoriert
    s = np.sign((N[:, :2] * out[:, :2]).sum(1) + 1e-9); N = N * s[:, None]; pc.normals = o3d.utility.Vector3dVector(N)
    mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pc, depth=a.depth); d = np.asarray(dens); mesh.remove_vertices_by_mask(d < np.quantile(d, a.dichte_quantil))
    V_ = np.asarray(mesh.vertices); tree = o3d.geometry.KDTreeFlann(pc); col = np.zeros((len(V_), 3)); dist = np.zeros(len(V_))
    for i, v in enumerate(V_):
        _, idx, d2 = tree.search_knn_vector_3d(v, 1); col[i] = C[idx[0]]; dist[i] = np.sqrt(d2[0])
    bel = dist <= a.belegt; mesh.vertex_colors = o3d.utility.Vector3dVector(col); o3d.io.write_triangle_mesh(os.path.join(a.aus, "farbig.ply"), mesh)
    c2 = col.copy(); c2[~bel] = 0.75 * c2[~bel] * np.array([0.4, 0.4, 0.4]) + np.array([0.55, 0.05, 0.05]); mesh.vertex_colors = o3d.utility.Vector3dVector(c2); o3d.io.write_triangle_mesh(os.path.join(a.aus, "belegt.ply"), mesh)
    T = np.asarray(mesh.triangles); tb = bel[T].all(1); m2 = o3d.geometry.TriangleMesh(mesh); m2.triangles = o3d.utility.Vector3iVector(T[tb]); m2.vertex_colors = o3d.utility.Vector3dVector(col); m2.remove_unreferenced_vertices(); o3d.io.write_triangle_mesh(os.path.join(a.aus, "nur_belegt.ply"), m2)
    z = V_[:, 2]; hv = []
    for lo in range(0, 70, 10):
        kk = (z >= lo) & (z < lo + 10)
        if kk.sum() > 20: hv.append(dict(z=[lo, lo + 10], ecken=int(kk.sum()), belegt_anteil=round(float(bel[kk].mean()), 3)))
    rep = dict(punkte=int(len(P)), ecken=int(len(V_)), dreiecke=int(len(T)), belegt_anteil=round(float(bel.mean()), 3), belegt_schwelle_m=a.belegt, depth=a.depth, hoehenverlauf=hv)
    json.dump(rep, open(os.path.join(a.aus, "bericht.json"), "w"), indent=1); print(f"Netz {len(V_)} Ecken, {len(T)} Dreiecke; belegt {bel.mean():.0%}")
    for h in hv: print(f"  z {h['z'][0]:2d}-{h['z'][1]:2d} m: belegt {h['belegt_anteil']:.0%} ({h['ecken']} Ecken)")

if __name__ == "__main__":
    main()
