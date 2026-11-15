#!/usr/bin/env python3
"""gruppen_punkt_tor.py <sparse> <objekt.json> <picks.json> [--tol 0.3] - TOR: derselbe Objektpunkt, aus verschiedenen FOTOGRUPPEN trianguliert, muss zusammenfallen.

Lehre Schwabentor v3 15.11.2026: der Laternenknauf lag aus den Suedfotos 5,9 m tiefer und 1,9 m weiter suedlich als aus den Nordfotos - die Fotogruppen der
Turmseiten hingen im SfM nur ueber wenige Eckpaare zusammen (Teilmodell Sued verzerrt, Massstab 0,89). Kein anderes Tor hat das gemerkt.
picks.json: {"punkt": "Laternenknauf", "gruppen": {"Nord": {"<bildname ohne Endung>": [u, v], ...}, "Sued": {...}}}  (Pixel im Originalbild).
Rechnung im SfM-Rahmen des uebergebenen Modells (Kameras direkt aus sparse, Verzeichnung SIMPLE_RADIAL/RADIAL/OPENCV per pycolmap entfernt); in Meter umgerechnet
ueber eine Aehnlichkeit auf die K-Kameras des Objekts (Umeyama ueber gemeinsame Kamerazentren, robust per Median-Rest) - so ist das Tor auch fuer ein NEUES
Modell vor dem Einbau nutzbar. Ausgabe je Gruppe: Punkt (m), Strahlabstaende; Abstaende der Gruppen untereinander. rc 3 ueber --tol.
"""
import sys, os, json, glob, argparse, numpy as np


def umeyama(A, B):
    ma, mb = A.mean(0), B.mean(0); H = (B - mb).T @ (A - ma) / len(A); U, S, Vt = np.linalg.svd(H); d = np.sign(np.linalg.det(U) * np.linalg.det(Vt)); Dm = np.diag([1, 1, d])
    R = U @ Dm @ Vt; s = np.trace(np.diag(S) @ Dm) / ((A - ma) ** 2).sum(1).mean(); return s, R, mb - s * R @ ma


def main():
    import pycolmap
    ap = argparse.ArgumentParser(); ap.add_argument("sparse"); ap.add_argument("objekt"); ap.add_argument("picks"); ap.add_argument("--tol", type=float, default=0.3); a = ap.parse_args()
    r = pycolmap.Reconstruction(a.sparse); od = os.path.dirname(os.path.abspath(a.objekt)); Pk = json.load(open(a.picks)); nach = {os.path.splitext(im.name)[0]: im for im in r.images.values() if im.has_pose}
    A, B = [], []
    for f in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        n = os.path.basename(f)[2:-5]
        if n in nach: A.append(nach[n].projection_center()); B.append(json.load(open(f))["kamera"]["standort_xyz"])
    A, B = np.array(A), np.array(B); ok = np.ones(len(A), bool)
    for _ in range(4):
        s, R, t = umeyama(A[ok], B[ok]); res = np.linalg.norm((s * (R @ A.T).T + t) - B, axis=1); ok = res < max(3 * np.median(res[ok]), 0.5)
    print(f"Aehnlichkeit auf den Objektrahmen: {int(ok.sum())} von {len(A)} Kameras, Massstab {s:.4f}, Rest Median {np.median(res[ok]):.2f} m (alle: {np.median(res):.2f} m)")
    def strahl(n, uv):
        im = nach[n]; cam = im.camera if hasattr(im, "camera") and im.camera is not None else r.cameras[im.camera_id]; xn = np.asarray(cam.cam_from_img(np.array(uv, float))).ravel()[:2]
        T = im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world; Rm = T.rotation.matrix(); d = Rm.T @ np.array([xn[0], xn[1], 1.0]); return im.projection_center(), d / np.linalg.norm(d)
    erg = {}
    for g, bilder in Pk["gruppen"].items():
        L = [strahl(n, uv) for n, uv in bilder.items() if n in nach]
        if len(L) < 2: print(f"  {g}: nur {len(L)} registrierte Bilder - kein Punkt"); continue
        M_ = np.zeros((3, 3)); b_ = np.zeros(3)
        for c, d in L: Q = np.eye(3) - np.outer(d, d); M_ += Q; b_ += Q @ c
        X = np.linalg.solve(M_, b_); rest = [float(np.linalg.norm((np.eye(3) - np.outer(d, d)) @ (X - c))) * s for c, d in L]; Xm = s * R @ X + t; erg[g] = Xm
        print(f"  {g}: {Pk.get('punkt', 'Punkt')} = ({Xm[0]:.2f} / {Xm[1]:.2f} / {Xm[2]:.2f}) m aus {len(L)} Fotos, Strahlabstaende {[round(v, 2) for v in rest]} m")
    gs = list(erg); schlecht = False
    for i in range(len(gs)):
        for j in range(i + 1, len(gs)):
            d = erg[gs[i]] - erg[gs[j]]; n_ = float(np.linalg.norm(d)); schlecht |= n_ > a.tol; print(f"  {gs[i]} - {gs[j]}: {n_:.2f} m (dx {d[0]:+.2f}, dy {d[1]:+.2f}, dz {d[2]:+.2f}){'  <-- UEBER TOLERANZ' if n_ > a.tol else ''}")
    return 3 if schlecht else 0


if __name__ == "__main__":
    sys.exit(main())
