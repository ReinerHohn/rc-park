#!/usr/bin/env python3
"""wolke_pose_am_generator.py - Pose (Roll/Gier/Nick + Versatz) einer Seitenwolke gegen die OBERFLAECHE des Generator-STL (Register BW).
Ersetzt Kantenperzentil-Messungen (abdeckungsabhaengig, ungueltig). Zielfunktion: mittlerer abgeschnittener Abstand (<=0,5 m) Wolke -> STL-Flaechen der Seite.
Koordinatenabstieg ueber 6 Parameter; Bericht enthaelt je Parameter die Zielfunktion bei +-d (Eindeutigkeit: flache Kurve = schlecht bestimmt, nicht anwenden).
  /media/oem/scan/venv-mesh/bin/python -I tools/wolke_pose_am_generator.py <wolke_P.npy> <aus_P.npy> --seite sued [--stl ...] [--massstab 87]
"""
import sys, json, argparse, numpy as np, open3d as o3d
SEITEN = {"sued": (0, 1), "nord": (0, -1), "ost": (1, 1), "west": (1, -1), "alle": (None, None)}   # alle = ganze STL-Oberflaeche (oberer Turm, Tuermchen/Helm)

def pose_tf(P, p, zc=25.0):
    c = lambda a: (np.cos(np.radians(a)), np.sin(np.radians(a))); cr, sr = c(p["roll"]); cy, sy = c(p["yaw"]); cp, sp = c(p["pitch"])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]]); Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]); Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    return (P - [0, 0, zc]) @ (Rz @ Ry @ Rx).T + [0, 0, zc] + [p["dx"], p["dy"], p["dz"]]

def schaetzen(P, ref, n=30000, zlo=10, zhi=36, seed=1, zc=25.0, frei=None):
    rng = np.random.default_rng(seed); k = (P[:, 2] > zlo) & (P[:, 2] < zhi); Q = P[k]; Q = Q[rng.choice(len(Q), min(n, len(Q)), replace=False)]
    def ev(p):
        q = o3d.geometry.PointCloud(); q.points = o3d.utility.Vector3dVector(pose_tf(Q, p, zc)); return float(np.minimum(np.asarray(q.compute_point_cloud_distance(ref)), 0.5).mean())
    p = dict(roll=0., yaw=0., pitch=0., dx=0., dy=0., dz=0.); step = dict(roll=1., yaw=1., pitch=1., dx=.2, dy=.2, dz=.2); f0 = ev(p); fs = f0
    for _ in range(40):
        imp = False
        for k_ in (frei or p):
            for sg in (1, -1):
                q = dict(p); q[k_] += sg * step[k_]; f = ev(q)
                if f < f0 - 1e-5: p, f0, imp = q, f, True
        if not imp:
            step = {k_: v / 2 for k_, v in step.items()}
            if step["dx"] < 0.02: break
    d = dict(roll=1.5, yaw=1.5, pitch=1.5, dx=.3, dy=.3, dz=.3); kr = {}
    for k_ in p:
        a = dict(p); a[k_] += d[k_]; b = dict(p); b[k_] -= d[k_]; kr[k_] = round(0.5 * (ev(a) + ev(b)) - f0, 4)    # Anstieg der Zielfunktion bei +-d: gross = gut bestimmt
    return p, dict(abstand_start=round(fs, 4), abstand_ende=round(f0, 4), pose={k_: round(v, 2) for k_, v in p.items()}, anstieg_bei_abweichung=kr)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("wolke"); ap.add_argument("aus"); ap.add_argument("--seite", required=True, choices=list(SEITEN)); ap.add_argument("--stl", default="modelle/stl/martinstor_v4_1-87.stl"); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--schwelle", type=float, default=0.005, help="Parameter mit Anstieg < Schwelle gelten als nicht bestimmt und werden auf 0 gesetzt (zweiter Durchgang)"); ap.add_argument("--zlo", type=float, default=10); ap.add_argument("--zhi", type=float, default=36); ap.add_argument("--blend", nargs=2, type=float, help="z0 z1: Pose nur oberhalb, weich eingeblendet (w=0 bei z0, 1 bei z1)")
    a = ap.parse_args(); ach, sg = SEITEN[a.seite]; P = np.load(a.wolke).astype(np.float64)
    m = o3d.io.read_triangle_mesh(a.stl); m.scale(a.massstab / 1000.0, center=(0, 0, 0)); m.compute_vertex_normals(); R = m.sample_points_uniformly(400000); Rp = np.asarray(R.points); Rn = np.asarray(R.normals)
    s = ((Rn[:, ach] * sg > 0.5) if ach is not None else np.ones(len(Rp), bool)) & (Rp[:, 2] > min(8, a.zlo - 2)) & (Rp[:, 2] < max(38, a.zhi + 2)); ref = o3d.geometry.PointCloud(); ref.points = o3d.utility.Vector3dVector(Rp[s])
    zc = 0.5 * (a.zlo + a.zhi); p, rep = schaetzen(P, ref, zlo=a.zlo, zhi=a.zhi, zc=zc)
    frei = [k_ for k_, v in rep["anstieg_bei_abweichung"].items() if v >= a.schwelle]
    if len(frei) < 6: p, rep2 = schaetzen(P, ref, zlo=a.zlo, zhi=a.zhi, zc=zc, frei=frei); rep2["erster_durchgang"] = rep; rep2["frei"] = frei; rep = rep2
    Pn = pose_tf(P, p, zc)
    if a.blend: w = np.clip((P[:, 2] - a.blend[0]) / (a.blend[1] - a.blend[0]), 0, 1)[:, None]; Pn = P + w * (Pn - P)
    np.save(a.aus, Pn.astype(np.float32)); rep["zc"] = zc; print(json.dumps(rep, ensure_ascii=False))
