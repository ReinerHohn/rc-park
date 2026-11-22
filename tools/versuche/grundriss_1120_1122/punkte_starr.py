"""Teil 0: Sim3 aus Kamerazentren 1122->1120 (SfM) auf die 1122-Punkte anwenden -> passen die Punkte zu 1120? (starr oder nicht)"""
import os, json
import numpy as np, pycolmap
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
D = "/media/oem/scan/rc-park_daten"; M = "/home/oem/git/rc-park/modelle"; OUT = os.path.dirname(os.path.abspath(__file__))
def sim3(X, Y):
    mx, my = X.mean(0), Y.mean(0); U, S, Vt = np.linalg.svd((Y - my).T @ (X - mx)); Dm = np.eye(3); Dm[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ Dm @ Vt
    s = (S * np.diag(Dm)).sum() / ((X - mx) ** 2).sum(); return s, R, my - s * R @ mx
r0 = pycolmap.Reconstruction(f"{D}/schwabentor-1120/pipe/sfm/sparse/0")
a0 = json.load(open(f"{M}/schwabentor-1120/messprotokoll/SFM-AUSRICHTUNG-schwabentor-1120.json")); T = a0["transformation"]; s0 = T["s"]; R0 = Rotation.from_rotvec(T["rvec"]).as_matrix(); t0 = np.array(T["t"])
to_obj0 = lambda X: (np.asarray(X) - t0) @ R0 / s0
C0 = {im.name: im.projection_center() for im in r0.images.values() if im.has_pose}
P0 = to_obj0(np.array([p.xyz for p in r0.points3D.values()]))
for teil, pfad in (("teil0", f"{D}/schwabentor-1122/pipe/sfm/seiten_modelle/teil0_b/0"), ("teil1", f"{D}/schwabentor-1122/pipe/sfm/seiten_modelle/teil1_b/0")):
    r1 = pycolmap.Reconstruction(pfad); C1 = {im.name: im.projection_center() for im in r1.images.values() if im.has_pose}
    nm = sorted(set(C0) & set(C1)); X = np.array([C1[n] for n in nm]); Y = to_obj0(np.array([C0[n] for n in nm]))
    keep = np.ones(len(nm), bool)
    for _ in range(5):
        s, R, t = sim3(X[keep], Y[keep]); r = np.linalg.norm(X @ (s * R).T + t - Y, axis=1); keep = r < max(3 * np.median(r[keep]), 0.2)
    P1 = np.array([p.xyz for p in r1.points3D.values()]) @ (s * R).T + t
    tr = cKDTree(P0); d, _ = tr.query(P1, distance_upper_bound=5.0); d[~np.isfinite(d)] = 5.0
    w1 = (P1[:, 2] > 1.5) & (P1[:, 2] < 9)
    print(f"{teil}: gemeinsame Kameras {len(nm)}, Inlier {keep.sum()}, Kamerarest Median {np.median(r[keep]):.3f} m; 1122-Punkte (Wandband) -> naechster 1120-Punkt: Median {np.median(d[w1]):.2f} m, <0,3 m {np.mean(d[w1]<0.3)*100:.0f} %")
    np.save(f"{OUT}/{teil}_im_1120rahmen.npy", P1[w1].astype(np.float32))
    q = P1[w1]; q = q[np.abs(q[:, 1] - 15) < 4]; h, e = np.histogram(q[:, 0], bins=np.arange(-16, 12, 0.25)); top = np.argsort(-h)[:4]
    print("   Schnitt y11-19 x-Gipfel: " + ", ".join(f"{e[i]:+.2f} ({h[i]})" for i in sorted(top)))
q = P0[(P0[:, 2] > 1.5) & (P0[:, 2] < 9)]; q = q[np.abs(q[:, 1] - 15) < 4]; h, e = np.histogram(q[:, 0], bins=np.arange(-16, 12, 0.25)); top = np.argsort(-h)[:6]
print("1120 sparse Schnitt y11-19 x-Gipfel: " + ", ".join(f"{e[i]:+.2f} ({h[i]})" for i in sorted(top)))
