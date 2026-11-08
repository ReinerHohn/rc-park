#!/usr/bin/env python3
"""pose_vertrauen_gruppen.py - Posenunsicherheit der Zusatzfotos je Kameragruppe (Register DF, 2026-11-06). Nur Lesen der Eingaben.

Eingabe je Lauf: Ordner mit registrierung.json (kamera_gruppe, zoomstatus je Bild), sparse_handy/0 und db.db (verifizierte Matches).
Messungen (alle aus Daten, keine Handschwellen):
  1. Leave-one-out je Bild: PnP nur mit Punkten, die OHNE dieses Bild >= 2 andere Beobachter haben (Kamera fest) -> Abweichung gegen die endgueltige Pose
     (Zentrum m, Rotation Grad). Aggregation je Kameragruppe (Median, q90). Zentrumsfehler wird durch Punkte ohne dieses Bild bestimmt.
  2. Bootstrap je Bild: PnP auf zufaelligen 50-%-Teilmengen der eigenen Korrespondenzen -> Streuung des Zentrums.
  3. Brennweiten-Empfindlichkeit: PnP mit f * (1 +- f_unsicherheit/f_orig) (Werte aus handy_nubia_gruppen.json) -> Zentrumsverschiebung.
  4. Hoch gegen Quer: fuer Bildpaare mit verifizierten Matches (db) wird die Relativpose unabhaengig per Essentialmatrix (cv2, entzerrte Normalkoordinaten)
     geschaetzt und mit der Relativpose aus den endgueltigen Posen verglichen (Rotation Grad, Basisrichtung Grad), getrennt nach Paarart
     hoch-hoch / quer-quer / hoch-quer (hoch_zoom einzeln). Kontrolle: Paarart hoch-hoch/quer-quer ist der Massstab fuer hoch-quer.
  5. Bilder, die in mehreren Laeufen registriert sind: Zentrums- und Rotationsunterschied.
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/pose_vertrauen_gruppen.py --lauf NAME=ORDNER ... --kameras JSON --aus out.json
"""
import sys, os, json, argparse, collections, itertools
import numpy as np


def rot_grad(R1, R2):
    c = (np.trace(R1.T @ R2) - 1) / 2
    return float(np.degrees(np.arccos(np.clip(c, -1, 1))))


def richtung_grad(a, b):
    a = a / (np.linalg.norm(a) + 1e-12); b = b / (np.linalg.norm(b) + 1e-12)
    return float(np.degrees(np.arccos(np.clip(a @ b, -1, 1))))


def q(a, p):
    a = [x for x in a if x is not None]
    return float(np.quantile(a, p)) if a else None


def stat(a):
    a = [x for x in a if x is not None]
    return dict(n=len(a), median=q(a, .5), q90=q(a, .9), max=(float(max(a)) if a else None))


def relativ(P1, P2):
    """Relativpose Kamera1->Kamera2 aus Posen (R,t = cam_from_world). Rueckgabe R_rel, Basisrichtung in Kamera 2 (t_rel)."""
    R = P2[0] @ P1[0].T; t = P2[1] - R @ P1[1]
    return R, t


def pnp(pycolmap, xy, X, cam, f_faktor=1.0, seed=0, fehler=4.0):
    c = pycolmap.Camera.create_from_model_id(0, pycolmap.CameraModelId.SIMPLE_RADIAL, cam.params[0] * f_faktor, cam.width, cam.height)
    p = list(cam.params); p[0] = p[0] * f_faktor; c.params = p
    eo = pycolmap.AbsolutePoseEstimationOptions(); eo.estimate_focal_length = False; eo.ransac.max_error = fehler; eo.ransac.random_seed = seed
    r = pycolmap.estimate_and_refine_absolute_pose(xy, X, c, eo)
    if r is None: return None
    cw = r["cam_from_world"]; R = cw.rotation.matrix(); t = np.array(cw.translation)
    return R, t, -R.T @ t, int(r["num_inliers"])


def lauf_auswerten(name, ordner, kam, seed=0, n_boot=15, n_max=1500):
    import pycolmap, cv2
    rec = pycolmap.Reconstruction(os.path.join(ordner, "sparse_handy", "0")); reg = json.load(open(os.path.join(ordner, "registrierung.json")))
    neu = {n: v for n, v in reg["bilder"].items() if v.get("status") == "registriert"}
    imgs = {i.name: i for i in rec.images.values() if i.has_pose and i.name in neu}
    rng = np.random.default_rng(seed); zeilen = {}
    for n, im in imgs.items():
        cam = rec.cameras[im.camera_id]; cw = im.cam_from_world(); R0 = cw.rotation.matrix(); t0 = np.array(cw.translation); c0 = -R0.T @ t0
        xy_all = []; X_all = []; xy_loo = []; X_loo = []
        for p2 in im.points2D:
            if not p2.has_point3D(): continue
            pt = rec.points3D[p2.point3D_id]; xy_all.append(p2.xy); X_all.append(pt.xyz)
            if sum(1 for e in pt.track.elements if e.image_id != im.image_id) >= 2: xy_loo.append(p2.xy); X_loo.append(pt.xyz)
        xy_all = np.array(xy_all); X_all = np.array(X_all); xy_loo = np.array(xy_loo); X_loo = np.array(X_loo)
        z = dict(gruppe=neu[n].get("kamera_gruppe"), zoomstatus=neu[n].get("zoomstatus"), n_punkte=int(len(X_all)), n_loo=int(len(X_loo)),
                 abstand_ref_m=neu[n].get("naechste_referenzkamera_m"), reproj_px=neu[n].get("reproj_mittel_px"))
        def kappe(xy, X):
            if len(X) > n_max:
                ii = rng.choice(len(X), n_max, replace=False); return xy[ii], X[ii]
            return xy, X
        if len(X_loo) >= 12:
            a, b = kappe(xy_loo, X_loo); r = pnp(pycolmap, a, b, cam, 1.0, seed)
            if r: z["loo_zentrum_m"] = float(np.linalg.norm(r[2] - c0)); z["loo_rot_grad"] = rot_grad(r[0], R0); z["loo_inlier"] = r[3]
        if len(X_all) >= 12:
            xa, Xa = kappe(xy_all, X_all); bz = []
            for k in range(n_boot):
                ii = rng.choice(len(Xa), max(12, len(Xa) // 2), replace=False); r = pnp(pycolmap, xa[ii], Xa[ii], cam, 1.0, seed + k)
                if r: bz.append(r[2])
            if len(bz) >= 5: bz = np.array(bz); z["boot_streuung_m"] = float(np.sqrt(np.mean(np.sum((bz - bz.mean(0)) ** 2, 1))))
            fu = kam["kameras"].get(z["gruppe"], {}); fr = fu.get("f_unsicherheit", 0) / fu.get("f_orig", 1)
            if fr:
                vs = []
                for ff in (1 - fr, 1 + fr):
                    r = pnp(pycolmap, xa, Xa, cam, ff, seed)
                    if r: vs.append(float(np.linalg.norm(r[2] - c0)))
                if vs: z["f_empfindlich_m"] = max(vs); z["f_rel_unsicherheit"] = fr
        z["zentrum"] = [float(x) for x in c0]; z["R"] = R0.tolist()
        zeilen[n] = z
    # Hoch gegen Quer: Zweibild-Relativpose
    db = pycolmap.Database.open(os.path.join(ordner, "db.db")); n2id = {i.name: i.image_id for i in rec.images.values()}
    paare = []
    for a_, b_ in itertools.combinations(sorted(imgs), 2):
        ia, ib = n2id[a_], n2id[b_]; i1, i2 = (ia, ib) if ia < ib else (ib, ia)
        try: g = db.read_two_view_geometry(i1, i2)
        except Exception: continue
        m = np.asarray(g.inlier_matches)
        if len(m) < 80: continue
        n1, n2 = (a_, b_) if ia < ib else (b_, a_)
        k1 = db.read_keypoints(n2id[n1])[:, :2]; k2 = db.read_keypoints(n2id[n2])[:, :2]
        c1 = rec.cameras[imgs[n1].camera_id]; c2 = rec.cameras[imgs[n2].camera_id]
        u1 = np.array([c1.cam_from_img(p) for p in k1[m[:, 0]]], float); u2 = np.array([c2.cam_from_img(p) for p in k2[m[:, 1]]], float)
        ok = np.isfinite(u1).all(1) & np.isfinite(u2).all(1); u1, u2 = u1[ok], u2[ok]
        if len(u1) < 50: continue
        E, mask = cv2.findEssentialMat(u1, u2, focal=1.0, pp=(0, 0), method=cv2.RANSAC, prob=0.999, threshold=3.0 / float(c1.params[0]))
        if E is None or E.shape != (3, 3): continue
        ninl, Rr, tr, _ = cv2.recoverPose(E, u1, u2, focal=1.0, pp=(0, 0), mask=mask)
        if ninl < 40: continue
        def pose(nn): cw = imgs[nn].cam_from_world(); return cw.rotation.matrix(), np.array(cw.translation)
        Rm, tm = relativ(pose(n1), pose(n2))
        g1, g2 = zeilen[n1]["gruppe"], zeilen[n2]["gruppe"]; fm = lambda g: "hoch" if g.startswith("hoch") else "quer"
        art = "-".join(sorted([fm(g1), fm(g2)])); art_z = "-".join(sorted([g1, g2]))
        paare.append(dict(a=n1, b=n2, art=art, art_gruppen=art_z, inlier_E=int(ninl), rot_fehler_grad=rot_grad(Rr, Rm), basis_fehler_grad=richtung_grad(tr.ravel(), tm), basis_m=float(np.linalg.norm(tm))))
    return name, zeilen, paare


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--lauf", action="append", required=True); ap.add_argument("--kameras", required=True); ap.add_argument("--aus", required=True)
    a = ap.parse_args(argv); kam = json.load(open(a.kameras)); out = dict(laeufe={}, hinweis="Alle Zahlen aus Daten; keine Schwellen gesetzt.")
    alle = {}
    for l in a.lauf:
        n, o = l.split("=", 1); _, z, p = lauf_auswerten(n, o, kam); alle[n] = z
        je = collections.defaultdict(list)
        for k, v in z.items(): je[v["gruppe"]].append(v)
        grp = {}
        for g, vs in sorted(je.items(), key=lambda x: str(x[0])):
            ze = lambda key: [v.get(key) for v in vs]
            grp[g] = dict(n=len(vs), zoomstatus_unbekannt=sum(1 for v in vs if v["zoomstatus"] == "unbekannt"), loo_zentrum_m=stat(ze("loo_zentrum_m")), loo_rot_grad=stat(ze("loo_rot_grad")),
                          boot_streuung_m=stat(ze("boot_streuung_m")), f_empfindlich_m=stat(ze("f_empfindlich_m")), reproj_px=stat(ze("reproj_px")), abstand_ref_m=stat(ze("abstand_ref_m")))
        pa = collections.defaultdict(list)
        for x in p: pa[x["art"]].append(x)
        pg = collections.defaultdict(list)
        for x in p: pg[x["art_gruppen"]].append(x)
        sf = lambda L: dict(n=len(L), rot_fehler_grad=stat([x["rot_fehler_grad"] for x in L]), basis_fehler_grad=stat([x["basis_fehler_grad"] for x in L]), basis_m=stat([x["basis_m"] for x in L]))
        out["laeufe"][n] = dict(ordner=o, gruppen=grp, paare_je_art={k: sf(v) for k, v in sorted(pa.items())}, paare_je_gruppenart={k: sf(v) for k, v in sorted(pg.items())}, n_paare=len(p), paare=p)
    namen = list(alle)
    if len(namen) > 1:
        ge = {}
        for A, B in itertools.combinations(namen, 2):
            for n in set(alle[A]) & set(alle[B]):
                ge[f"{A}/{B}/{n}"] = dict(zentrum_m=float(np.linalg.norm(np.array(alle[A][n]["zentrum"]) - np.array(alle[B][n]["zentrum"]))), rot_grad=rot_grad(np.array(alle[A][n]["R"]), np.array(alle[B][n]["R"])), gruppe=alle[A][n]["gruppe"])
        out["mehrfach_registriert"] = ge
    out["bilder"] = {L: {n: {k: v for k, v in z.items() if k != "R"} for n, z in zz.items()} for L, zz in alle.items()}
    json.dump(out, open(a.aus, "w"), indent=1, default=float)
    for L, d in out["laeufe"].items():
        print("==", L)
        for g, s in d["gruppen"].items(): print(g, "n", s["n"], "zoom_unbekannt", s["zoomstatus_unbekannt"], "LOO m med/q90", s["loo_zentrum_m"]["median"], s["loo_zentrum_m"]["q90"], "LOO Grad", s["loo_rot_grad"]["median"], "boot m", s["boot_streuung_m"]["median"], "f m", s["f_empfindlich_m"]["median"])
        for k, s in d["paare_je_art"].items(): print("paare", k, s["n"], "rot", s["rot_fehler_grad"]["median"], s["rot_fehler_grad"]["q90"], "basis", s["basis_fehler_grad"]["median"], s["basis_fehler_grad"]["q90"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
