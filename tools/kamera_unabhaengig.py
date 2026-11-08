#!/usr/bin/env python3
"""kamera_unabhaengig.py - UNABHAENGIGE Kameraprobe (Leave-One-Out-Registrierung, Gegenstueck zum zirkulaeren Wolke-ueber-Foto, BS10).
Foto aus dem Buendel nehmen (Beobachtungen loeschen), Buendel ohne dieses Foto neu ausgleichen, dann das Foto NUR aus seinen Merkmalen gegen die uebrigen Punkte (2D-3D, PnP+Verfeinerung,
Intrinsik wie im Buendel fest) neu registrieren. Abweichung der neuen von der alten Pose = Mass, wie stark die Kamera vom Rest des Buendels getragen wird.
  venv-colmap/bin/python -I tools/kamera_unabhaengig.py <sparse/0> --fotos 114,004,000 [--s 1.0 (Maszstab SfM->m)] [--aus x.json]
Aussage nur relativ: ein Foto, das ohne sich selbst fast dort landet, wo es war, ist vom Rest bestimmt (gut); grosse Abweichung = wackelig ODER Foto traegt Punkte allein."""
import sys, json, argparse, copy, numpy as np, pycolmap
ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("--fotos", required=True); ap.add_argument("--s", type=float, default=1.0); ap.add_argument("--aus")
a = ap.parse_args(); erg = {}
for nr in a.fotos.split(","):
    rec = pycolmap.Reconstruction(a.sparse); iid = [i for i, im in rec.images.items() if im.name.split(".")[0].split("_")[0] == nr]
    if not iid: erg[nr] = "nicht im Buendel"; continue
    im = rec.images[iid[0]]; cam = rec.cameras[im.camera_id]; T0 = im.cam_from_world(); C0 = im.projection_center(); R0 = T0.rotation.matrix()
    p2 = []; p3 = []; pid = []
    for k, p in enumerate(im.points2D):
        if p.has_point3D(): p2.append(p.xy.copy()); pid.append(p.point3D_id)
    ctr0 = {i: m.projection_center().copy() for i, m in rec.images.items() if i != iid[0]}                  # Zentren VOR dem Neuausgleich (Eichrahmen)
    fid = im.frame_id; rec.deregister_frame(fid)
    ok = [i for i, q in enumerate(pid) if q in rec.points3D and rec.points3D[q].track.length() >= 2]
    opt = pycolmap.BundleAdjustmentOptions(); pycolmap.bundle_adjustment(rec, opt)
    ok = [i for i in ok if pid[i] in rec.points3D]
    ids = [i for i in ctr0 if i in rec.images and rec.images[i].has_pose]; A = np.array([rec.images[i].projection_center() for i in ids]); B = np.array([ctr0[i] for i in ids])       # Eichrahmen: BA ohne Foto verschiebt/skaliert das Gesamtsystem -> Sim3 nachher->vorher
    ma, mb = A.mean(0), B.mean(0); U, D, Vt = np.linalg.svd((B - mb).T @ (A - ma) / len(A)); Sg = np.eye(3); Sg[2, 2] = np.sign(np.linalg.det(U @ Vt)); Rm = U @ Sg @ Vt; sc = np.trace(np.diag(D) @ Sg) / (A - ma).var(0).sum(); tt = mb - sc * Rm @ ma
    rest = np.linalg.norm(sc * (Rm @ A.T).T + tt - B, axis=1)
    if len(ok) < 12: erg[nr] = f"zu wenig 2D-3D ({len(ok)})"; continue
    P2 = np.array([p2[i] for i in ok], float); P3 = np.array([rec.points3D[pid[i]].xyz for i in ok], float)
    e = pycolmap.AbsolutePoseEstimationOptions(); e.ransac.max_error = 4.0; r = pycolmap.estimate_and_refine_absolute_pose(P2, P3, cam, e, pycolmap.AbsolutePoseRefinementOptions(), False)
    if r is None or "cam_from_world" not in r: erg[nr] = "Registrierung fehlgeschlagen"; continue
    T1 = r["cam_from_world"]; R1 = T1.rotation.matrix(); C1a = -R1.T @ T1.translation; C1 = sc * Rm @ C1a + tt; R1 = R1 @ Rm.T                       # Pose im Vor-Rahmen
    P3 = sc * (Rm @ P3.T).T + tt
    dR = R1 @ R0.T; ang = np.degrees(np.arccos(np.clip((np.trace(dR) - 1) / 2, -1, 1)))
    def proj(T): Xc = (T[0] @ P3.T).T + T[1]; return np.c_[Xc[:, 0] / Xc[:, 2], Xc[:, 1] / Xc[:, 2]] * cam.params[0] + np.array([cam.params[1], cam.params[2]])      # Lochkamera, k1 vernachlaessigt (nur Vergleich alt/neu)
    u0 = proj((R0, T0.translation)); u1 = proj((R1, -R1 @ C1)); px_vers = np.linalg.norm(u1 - u0, axis=1)
    erg[nr] = dict(eichrest_cm=round(float(np.median(rest)) * 100, 2), n_2d3d=len(ok), inlier=int(r.get("num_inliers", -1)), versatz_zentrum_m=round(float(np.linalg.norm(C1 - C0)) * a.s, 3), drehung_grad=round(float(ang), 3), f_px=cam.params[0], px_verschiebung_median=round(float(np.median(px_vers)), 2), px_verschiebung_p90=round(float(np.percentile(px_vers, 90)), 2), bildbreite=cam.width)
    print(nr, erg[nr], flush=True)
if a.aus: json.dump(erg, open(a.aus, "w"), indent=1)
