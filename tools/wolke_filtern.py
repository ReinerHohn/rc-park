#!/usr/bin/env python3
"""wolke_filtern.py - Punkte in der Luft entfernen (Register BW): (1) lokale Dichte: Radius-Ausreisser (zu wenige Nachbarn im Radius),
(2) Median-Abstand: Nachbarabstand > Median + k*MAD des jeweiligen Hoehenbands, (3) Abstand zur Generatorflaeche > --luft m (nur z > --zmin, nahe am Boden sind Strasse/Nachbarn echt).
Keine Handwerte je Objekt: Schwellen sind Parameter mit Standard, Anzahlen je Filter im Bericht.
  /media/oem/scan/venv-mesh/bin/python -I tools/wolke_filtern.py <wolke_entzerrt.npy> <aus_entzerrt.npy> [--stl modelle/stl/martinstor_v4_1-87.stl] [--massstab 87]  (Farben: <name>_farben.npy)
"""
import sys, json, argparse, numpy as np, open3d as o3d

def filtern(P, C, stl=None, massstab=87.0, nb=8, radius=0.6, k=4.0, luft=2.0, zmin=8.0):
    pc = o3d.geometry.PointCloud(); pc.points = o3d.utility.Vector3dVector(P); keep = np.ones(len(P), bool); rep = dict(punkte=int(len(P)))
    _, ind = pc.remove_radius_outlier(nb_points=nb, radius=radius); k1 = np.zeros(len(P), bool); k1[ind] = True; rep["dichte_entfernt"] = int((~k1).sum()); keep &= k1
    pc2 = pc.select_by_index(np.where(keep)[0]); idx2 = np.where(keep)[0]; nn = np.asarray(pc2.compute_nearest_neighbor_distance()); z = P[idx2, 2]; k2 = np.ones(len(idx2), bool)
    for lo in range(0, 80, 5):
        b = (z >= lo) & (z < lo + 5)
        if b.sum() > 50:
            med = np.median(nn[b]); mad = np.median(np.abs(nn[b] - med)) + 1e-6; k2[b] = nn[b] <= med + k * 1.4826 * mad
    rep["median_entfernt"] = int((~k2).sum()); keep[idx2[~k2]] = False
    if stl:
        m = o3d.io.read_triangle_mesh(stl); m.scale(massstab / 1000.0, center=(0, 0, 0)); ref = m.sample_points_uniformly(300000)
        sel = np.where(keep & (P[:, 2] > zmin))[0]; q = o3d.geometry.PointCloud(); q.points = o3d.utility.Vector3dVector(P[sel]); d = np.asarray(q.compute_point_cloud_distance(ref))
        fern = sel[d > luft]; keep[fern] = False; rep["generatorabstand_entfernt"] = int(len(fern))
    rep["uebrig"] = int(keep.sum()); return keep, rep

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("wolke"); ap.add_argument("aus"); ap.add_argument("--stl"); ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--nb", type=int, default=8); ap.add_argument("--radius", type=float, default=0.6); ap.add_argument("--k", type=float, default=4.0); ap.add_argument("--luft", type=float, default=2.0); ap.add_argument("--zmin", type=float, default=8.0)
    a = ap.parse_args(); P = np.load(a.wolke).astype(np.float64); fc = a.wolke.replace("_entzerrt.npy", "_farben.npy"); C = np.load(fc)
    keep, rep = filtern(P, C, a.stl, a.massstab, a.nb, a.radius, a.k, a.luft, a.zmin)
    np.save(a.aus, P[keep].astype(np.float32)); np.save(a.aus.replace("_entzerrt.npy", "_farben.npy"), C[keep]); print(json.dumps(rep))
