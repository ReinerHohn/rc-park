#!/usr/bin/env python3
"""durchblick_knick_1122.py - KNICK an der Ecke messen (22.11.2026): relative Drehung je Eckpaar aus den eigenen Zuordnungen (Essentialmatrix mit den Modell-Kameras)
gegen die relative Drehung im Modell. Gleiche Abweichung bei allen Paaren ueber die Ecke = starrer Knick (Gelenk), dessen Winkel mit dem Wandwinkel gegen LoD2 zu vergleichen ist.
python -I durchblick_knick_1122.py <modell> <db> <paare.json [[a, b], ...]>"""
import sys, json, numpy as np, sqlite3, cv2, pycolmap
MAXID = 2147483647
r = pycolmap.Reconstruction(sys.argv[1]); I = {im.name: im for im in r.images.values() if im.has_pose}
db = sqlite3.connect(f"file:{sys.argv[2]}?immutable=1", uri=True); did = {n: i for i, n in db.execute("select image_id, name from images")}
def kp(i):
    rr, cc, dd = db.execute("select rows, cols, data from keypoints where image_id=?", (i,)).fetchone(); return np.frombuffer(dd, np.float32).reshape(rr, cc)[:, :2].astype(float)
def winkel(R): return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
for a, b in json.load(open(sys.argv[3])):
    if a not in I or b not in I: print(a, b, "nicht im Modell"); continue
    x, y = did[a], did[b]
    if x > y: x, y, a, b = y, x, b, a
    row = db.execute("select rows, cols, data from two_view_geometries where pair_id=?", (x * MAXID + y,)).fetchone()
    if not row: print(a, b, "kein Paar"); continue
    ij = np.frombuffer(row[2], np.uint32).reshape(row[0], row[1]); u0 = np.asarray(I[a].camera.cam_from_img(kp(x)[ij[:, 0]])); u1 = np.asarray(I[b].camera.cam_from_img(kp(y)[ij[:, 1]]))
    E, m = cv2.findEssentialMat(u0, u1, np.eye(3), cv2.RANSAC, 0.999, 0.002); _, R2, t2, _ = cv2.recoverPose(E, u0, u1, np.eye(3), mask=m)
    Ta = I[a].cam_from_world().matrix(); Tb = I[b].cam_from_world().matrix(); Rm = Tb[:, :3] @ Ta[:, :3].T
    D = Rm @ R2.T; ax = np.array([D[2, 1] - D[1, 2], D[0, 2] - D[2, 0], D[1, 0] - D[0, 1]]); ax = ax / (np.linalg.norm(ax) + 1e-12)
    ax_w = Tb[:, :3].T @ ax                                           # Drehachse im Weltrahmen des Modells
    print(f"{a[-12:]} | {b[-12:]}: Inlier {row[0]} (E {int(m.sum())}), Drehung Paar {winkel(R2):.1f} Grad, Modell {winkel(Rm):.1f} Grad, ABWEICHUNG {winkel(D):.1f} Grad, Achse (Welt) {np.round(ax_w, 2).tolist()}")
