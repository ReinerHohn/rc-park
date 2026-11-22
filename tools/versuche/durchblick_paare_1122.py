#!/usr/bin/env python3
"""durchblick_paare_1122.py - UNTERSUCHUNG (22.11.2026): sind die von seiten_erkennen.py als 'verwechselt'/'unklar' geloeschten Querpaare von schwabentor-1122
echte gemeinsame Szene (Durchblick durch den Torbogen, Bogenlaibung, Nachbarhaeuser, Boden) oder Fassaden-Verwechslung Nord/Sued?
Liest NUR (db.db immutable, seiten.json, Masken). Je Gruppenverbindung: Paarbilder mit eingezeichneten Inlier-Zuordnungen (Vordergrundmaske grau) + Messwerte je Paar
(Inlier, Homographie-Anteil, relative Drehung aus F + Kamera-Brennweite, Verteilung der Inlier im Bild) -> <aus>/<a>_<b>/paar_NN.jpg + <aus>/messwerte.json.
  python -I tools/versuche/durchblick_paare_1122.py --sfm <pipe/sfm> --bilder <fotos> --aus DIR --verb 0-1,9-14,14-19,7-14,9-13 [--je 10] [--min-inlier 30]"""
import os, sys, json, argparse, sqlite3, random, collections
import numpy as np, cv2

MAXID = 2147483647


def lade_db(pfad):
    return sqlite3.connect(f"file:{pfad}?immutable=1", uri=True)


def kp(db, iid):
    r, c, d = db.execute("select rows, cols, data from keypoints where image_id=?", (iid,)).fetchone()
    return np.frombuffer(d, np.float32).reshape(r, c)[:, :2]


def kamera(db, iid):
    m, w, h, p = db.execute("select c.model, c.width, c.height, c.params from cameras c join images i on i.camera_id=c.camera_id where i.image_id=?", (iid,)).fetchone()
    p = np.frombuffer(p, np.float64)
    f = p[0]; cx, cy = (p[1], p[2]) if m in (0, 2, 3) else (p[2], p[3])      # SIMPLE_PINHOLE/SIMPLE_RADIAL/RADIAL: f cx cy; PINHOLE/OPENCV: fx fy cx cy
    return np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]), (w, h)


def maske(mdir, name, wh):
    if not mdir: return None
    b = os.path.splitext(name)[0]
    for p in (os.path.join(mdir, "fotos", b + ".png"), os.path.join(mdir, b + ".png")):
        if os.path.exists(p):
            m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            return cv2.resize(m, wh, interpolation=cv2.INTER_NEAREST) if m is not None else None
    return None


def messen(x0, x1, K0, K1, wh0, wh1):
    """Zwei-Ansichten-Messwerte auf den bestaetigten Zuordnungen."""
    n = len(x0); aus = dict(n=n)
    s = max(max(wh0), max(wh1))
    H, mh = cv2.findHomography(x0, x1, cv2.RANSAC, 0.006 * s)
    aus["h_anteil"] = round(float(mh.mean()), 3) if mh is not None else None
    E, me = cv2.findEssentialMat(cv2.undistortPoints(x0.reshape(-1, 1, 2), K0, None).reshape(-1, 2), cv2.undistortPoints(x1.reshape(-1, 1, 2), K1, None).reshape(-1, 2),
                                 np.eye(3), cv2.RANSAC, 0.999, 0.003)
    if E is not None and E.shape == (3, 3):
        _, R, t, mp = cv2.recoverPose(E, cv2.undistortPoints(x0.reshape(-1, 1, 2), K0, None).reshape(-1, 2), cv2.undistortPoints(x1.reshape(-1, 1, 2), K1, None).reshape(-1, 2), np.eye(3), mask=me)
        aus["drehung_grad"] = round(float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1)))), 1)
        # Blickwinkel zwischen den optischen Achsen (z) und Basisrichtung
        z1 = R.T @ np.array([0, 0, 1.0]); aus["blick_grad"] = round(float(np.degrees(np.arccos(np.clip(z1[2], -1, 1)))), 1)
        c1 = (-R.T @ t).ravel(); c1 /= np.linalg.norm(c1) + 1e-12
        aus["basis_vs_blick0_grad"] = round(float(np.degrees(np.arccos(np.clip(c1[2], -1, 1)))), 1)   # 0 = Kamera 1 steht in Blickrichtung VOR Kamera 0 (hintereinander)
        aus["e_inlier"] = round(float((me.ravel() > 0).mean()), 3)
        # Parallaxe/Tiefe: Triangulation, Tiefenspreizung (q90/q10) in Kamera 0
        P0 = np.hstack([np.eye(3), np.zeros((3, 1))]); P1 = np.hstack([R, t])
        u0 = cv2.undistortPoints(x0.reshape(-1, 1, 2), K0, None).reshape(-1, 2).T; u1 = cv2.undistortPoints(x1.reshape(-1, 1, 2), K1, None).reshape(-1, 2).T
        X = cv2.triangulatePoints(P0, P1, u0, u1); X = X[:3] / X[3]; z = X[2]; ok = z > 0
        if ok.sum() >= 8: aus["tiefe_q90_q10"] = round(float(np.percentile(z[ok], 90) / max(np.percentile(z[ok], 10), 1e-9)), 2)
    # Verteilung: Anteil der Bildflaeche (Raster 8x8), in der Inlier liegen
    for k, x, wh in ((0, x0, wh0), (1, x1, wh1)):
        gx = np.clip((x[:, 0] / wh[0] * 8).astype(int), 0, 7); gy = np.clip((x[:, 1] / wh[1] * 8).astype(int), 0, 7)
        aus[f"zellen{k}"] = int(len(set(zip(gx, gy)))); aus[f"y_mitte{k}"] = round(float(np.median(x[:, 1]) / wh[1]), 2)
    return aus


def zeichnen(p0, p1, x0, x1, m0, m1, titel, aus, h=700):
    I = []
    for p, m in ((p0, m0), (p1, m1)):
        im = cv2.imread(p, cv2.IMREAD_REDUCED_COLOR_2)
        I.append(im)
    sx = []; R = []
    for (im, m, x) in ((I[0], m0, x0), (I[1], m1, x1)):
        f = h / im.shape[0]; im = cv2.resize(im, (int(im.shape[1] * f), h))
        if m is not None:
            mm = cv2.resize(m, (im.shape[1], h), interpolation=cv2.INTER_NEAREST) == 0
            im[mm] = (im[mm] * 0.35 + 90).astype(np.uint8)
        R.append(im); sx.append(f)
    # Skalierung Keypoint -> Bild: keypoints sind in Originalaufloesung (Kamerabreite)
    W0 = R[0].shape[1]; can = np.hstack(R)
    rnd = np.random.default_rng(0); idx = rnd.permutation(len(x0))[:200]
    for i in idx:
        a = (int(x0[i, 0] * S[0]), int(x0[i, 1] * S[0])); b = (int(x1[i, 0] * S[1]) + W0, int(x1[i, 1] * S[1]))
        c = tuple(int(v) for v in rnd.integers(60, 255, 3))
        cv2.line(can, a, b, c, 1, cv2.LINE_AA); cv2.circle(can, a, 3, c, -1); cv2.circle(can, b, 3, c, -1)
    cv2.rectangle(can, (0, 0), (can.shape[1], 30), (0, 0, 0), -1); cv2.putText(can, titel, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(aus, can, [cv2.IMWRITE_JPEG_QUALITY, 80])


S = [1.0, 1.0]


def main(argv=None):
    global S
    ap = argparse.ArgumentParser(); ap.add_argument("--sfm", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--verb", default="0-1,9-14,14-19,7-14,9-13"); ap.add_argument("--je", type=int, default=10); ap.add_argument("--min-inlier", type=int, default=30)
    ap.add_argument("--alle", action="store_true", help="Messwerte fuer ALLE Paare der Verbindung, nicht nur die gezeichneten"); ap.add_argument("--seiten", help="seiten.json (Standard <sfm>/seiten.json)")
    ap.add_argument("--db", help="Datenbank (Standard <sfm>/db.db)")
    a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True)
    sj = json.load(open(a.seiten or os.path.join(a.sfm, "seiten.json"))); g = sj["gemeinschaft"]
    db = lade_db(a.db or os.path.join(a.sfm, "db.db")); nm = dict(db.execute("select image_id, name from images")); gi = {i: g.get(n) for i, n in nm.items()}
    mdir = os.path.join(a.sfm, "masken") if os.path.isdir(os.path.join(a.sfm, "masken")) else None
    verb = [tuple(sorted(int(x) for x in v.split("-"))) for v in a.verb.split(",")]
    P = collections.defaultdict(list)
    for pid, rows in db.execute("select pair_id, rows from two_view_geometries where rows >= ?", (a.min_inlier,)):
        x, y = pid // MAXID, pid % MAXID; k = tuple(sorted((gi[x], gi[y]))) if gi[x] is not None and gi[y] is not None else None
        if k in verb: P[k].append((pid, rows))
    erg = {}
    for k in verb:
        L = sorted(P[k]); rnd = random.Random(0); rnd.shuffle(L); d = os.path.join(a.aus, f"{k[0]}_{k[1]}"); os.makedirs(d, exist_ok=True); M = []
        for j, (pid, rows) in enumerate(L if a.alle else L[:a.je]):
            x, y = pid // MAXID, pid % MAXID
            r, c, dat, cfg = db.execute("select rows, cols, data, config from two_view_geometries where pair_id=?", (pid,)).fetchone()
            ij = np.frombuffer(dat, np.uint32).reshape(r, c); k0 = kp(db, x); k1 = kp(db, y)
            x0 = k0[ij[:, 0]].astype(np.float64); x1 = k1[ij[:, 1]].astype(np.float64)
            K0, wh0 = kamera(db, x); K1, wh1 = kamera(db, y)
            m0 = maske(mdir, nm[x], wh0); m1 = maske(mdir, nm[y], wh1)
            mw = messen(x0, x1, K0, K1, wh0, wh1); mw.update(a=nm[x], b=nm[y], ga=gi[x], gb=gi[y], config=cfg)
            if m0 is not None and m1 is not None:
                v0 = m0[np.clip(x0[:, 1].astype(int), 0, wh0[1] - 1), np.clip(x0[:, 0].astype(int), 0, wh0[0] - 1)] == 0
                v1 = m1[np.clip(x1[:, 1].astype(int), 0, wh1[1] - 1), np.clip(x1[:, 0].astype(int), 0, wh1[0] - 1)] == 0
                mw["vordergrund_anteil"] = round(float((v0 | v1).mean()), 3)
            M.append(mw)
            if j < a.je:
                im0 = cv2.imread(os.path.join(a.bilder, nm[x]), cv2.IMREAD_REDUCED_COLOR_2); im1 = cv2.imread(os.path.join(a.bilder, nm[y]), cv2.IMREAD_REDUCED_COLOR_2)
                S = [700 / im0.shape[0] * im0.shape[0] / wh0[1], 700 / im1.shape[0] * im1.shape[0] / wh1[1]]
                t = f"G{gi[x]} {nm[x][-28:]} | G{gi[y]} {nm[y][-28:]}  n={mw['n']} H={mw['h_anteil']} dreh={mw.get('drehung_grad')} tiefe={mw.get('tiefe_q90_q10')}"
                zeichnen(os.path.join(a.bilder, nm[x]), os.path.join(a.bilder, nm[y]), x0, x1, m0, m1, t, os.path.join(d, f"paar_{j:02d}.jpg"))
        erg[f"{k[0]}-{k[1]}"] = M
        h = [m["h_anteil"] for m in M if m.get("h_anteil") is not None]; dr = [m["drehung_grad"] for m in M if m.get("drehung_grad") is not None]
        print(f"{k}: {len(P[k])} Paare >= {a.min_inlier}, gemessen {len(M)}: Inlier Median {np.median([m['n'] for m in M]):.0f}, H-Anteil Median {np.median(h):.2f}, Drehung Median {np.median(dr):.0f} Grad", flush=True)
    json.dump(erg, open(os.path.join(a.aus, "messwerte.json"), "w"), indent=1)


if __name__ == "__main__": main()
