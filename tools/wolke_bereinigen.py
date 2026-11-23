#!/usr/bin/env python3
"""wolke_bereinigen.py - Strahl-/Ausreisser-Bereinigung der Dichtwolke (BS41, 7.11.): Foto 043 zeigt Zapfen/Streifen unter Bogen und Traufe
(Tiefenfehler entlang der Sehstrahlen). Statistik-Filter (SOR) + Radiusfilter + Normalen-Planaritaet in Open3D (venv-o3d). Ausgabe npy im Kamerarahmen (K).
  venv-o3d/bin/python tools/wolke_bereinigen.py <dicht_ordner> <objekt.json> --aus x.npy [--nb 30 --std 1.2 --r 0.12 --minpkt 15]"""
import sys, os, json, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from kamera_standort import kamera_standort   # 23.11.2026: standort_xyz > standort > Pose (231 K-Dateien ohne standort_xyz)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import open3d as o3d
ap = argparse.ArgumentParser(); ap.add_argument("dicht"); ap.add_argument("objekt"); ap.add_argument("--aus", required=True)
ap.add_argument("--nb", type=int, default=30); ap.add_argument("--std", type=float, default=1.2); ap.add_argument("--r", type=float, default=0.12); ap.add_argument("--minpkt", type=int, default=15)
a = ap.parse_args(); od = os.path.dirname(os.path.abspath(a.objekt))
import freiraum_pruefen as FP
Kd = json.load(open(os.path.join(a.dicht, "kameras_unverzerrt.json"))); S = []; M = []
for i, c in Kd.items():
    p = os.path.join(od, "messprotokoll", f"K-{i}.json")
    if not os.path.exists(p): continue
    k = json.load(open(p)).get("kamera", {})
    Sk = kamera_standort(k)
    if Sk is not None: S.append(-np.array(c["R"]).T @ np.array(c["t"])); M.append(Sk)
S = np.array(S); M = np.array(M); ms, mm = S.mean(0), M.mean(0); A = S - ms; B = M - mm
U, D, Vt = np.linalg.svd(B.T @ A / len(S)); Sg = np.eye(3); Sg[2, 2] = np.sign(np.linalg.det(U @ Vt)); Rm = U @ Sg @ Vt
s = np.trace(np.diag(D) @ Sg) / A.var(0).sum(); t0 = mm - s * Rm @ ms
X = s * (Rm @ FP.ply_lesen(os.path.join(a.dicht, "fused.ply")).T).T + t0
# Gebaeude-Ausschnitt: Nachbarn/Boden bleiben, nur grobe Himmelsausreisser (>3 sigma Hoehe) vorab
pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(X)); n0 = len(X)
pc, i1 = pc.remove_statistical_outlier(a.nb, a.std); n1 = len(pc.points)
pc, i2 = pc.remove_radius_outlier(a.minpkt, a.r); n2 = len(pc.points)
print(f"Punkte {n0} -> SOR {n1} -> Radius {n2} ({100*n2/n0:.1f} %)")
np.save(a.aus, np.asarray(pc.points, np.float32))
