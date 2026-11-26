#!/usr/bin/env python3
"""teilmodell_ausrichten.py <hauptmodell-sparse> <teilmodelle-ordner> [--ausrichtung SFM-AUSRICHTUNG.json] [--min_gemeinsam 4]

Teilmodelle aus tools/handy_teilmodell.py ins HAUPTMODELL einpassen: gemeinsame Bilder (in beiden mit Pose) -> Aehnlichkeitsabbildung (Umeyama) der Kamerazentren,
RANSAC gegen falsche Paare. Meldet je Teilmodell: gemeinsame Bilder, Inlier, Massstab, mittlerer Rest in m (Hauptmodell-Einheit, mit --ausrichtung auch Modellmeter).
Ein Teilmodell ohne genug gemeinsame Bilder (< --min_gemeinsam) bleibt UNAUSGERICHTET (keine Lage geraten). Schreibt <teilmodelle>/<n>_ausgerichtet/ + ausrichtung.json.
Verwandt: tools/handy_teilmodell.py, tools/kameras_nachtragen.py (Umeyama gemeinsame Bilder -> Modellrahmen), modelle/METHODE_SEITEN_SFM.md.
Vorlaeufer: kameras_nachtragen.py (gleiche Rechnung fuer neu eingeordnete Bilder, nicht fuer eigene Teilmodelle)."""
import os, sys, json, argparse
import numpy as np


def umeyama(A, B):
    """s, R, t mit B ~ s R A + t."""
    ma, mb = A.mean(0), B.mean(0); a, b = A - ma, B - mb
    U, S, Vt = np.linalg.svd(b.T @ a / len(A)); D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0: D[2, 2] = -1
    R = U @ D @ Vt; s = (S * np.diag(D)).sum() / (a ** 2).sum() * len(A) / len(A) * len(A) / len(A)
    s = np.trace(np.diag(S) @ D) / ((a ** 2).sum() / len(A)); t = mb - s * R @ ma
    return s, R, t


def ransac(A, B, iters=500, tol=None, rng=np.random.default_rng(0)):
    n = len(A); best = None
    if tol is None: tol = 0.05 * np.linalg.norm(B.max(0) - B.min(0)) + 1e-9
    for _ in range(iters):
        i = rng.choice(n, 3, replace=False); s, R, t = umeyama(A[i], B[i])
        if not np.isfinite(s) or s <= 0: continue
        e = np.linalg.norm((s * (R @ A.T)).T + t - B, axis=1); inl = e < tol
        if best is None or inl.sum() > best[0].sum(): best = (inl, s, R, t)
    if best is None: return None
    inl = best[0]; s, R, t = umeyama(A[inl], B[inl]); e = np.linalg.norm((s * (R @ A[inl].T)).T + t - B[inl], axis=1)
    return inl, s, R, t, e


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("haupt"); ap.add_argument("teil"); ap.add_argument("--ausrichtung"); ap.add_argument("--min_gemeinsam", type=int, default=4)
    a = ap.parse_args(); import pycolmap, cv2
    H = pycolmap.Reconstruction(a.haupt); hc = {i.name: np.array(i.projection_center()) for i in H.images.values() if i.has_pose}
    sm = 1.0
    if a.ausrichtung: sm = 1.0 / json.load(open(a.ausrichtung))["transformation"]["s"]
    out = {}
    for d in sorted(x for x in os.listdir(a.teil) if x.isdigit()):
        M = pycolmap.Reconstruction(os.path.join(a.teil, d)); mc = {i.name: np.array(i.projection_center()) for i in M.images.values() if i.has_pose}
        gem = sorted(set(hc) & set(mc)); z = dict(bilder=len(mc), gemeinsam=len(gem), punkte=M.num_points3D())
        if len(gem) < a.min_gemeinsam: z["status"] = f"UNAUSGERICHTET (gemeinsam {len(gem)} < {a.min_gemeinsam})"
        else:
            A = np.array([mc[n] for n in gem]); B = np.array([hc[n] for n in gem]); r = ransac(A, B)
            if r is None: z["status"] = "UNAUSGERICHTET (RANSAC ohne Loesung)"
            else:
                inl, s, R, t, e = r; z.update(inlier=int(inl.sum()), massstab=float(s), rest_mittel_m=float(e.mean() * sm), rest_max_m=float(e.max() * sm), status="ausgerichtet" if inl.sum() >= a.min_gemeinsam else "UNSICHER")
                if z["status"] == "ausgerichtet":
                    M.transform(pycolmap.Sim3d(s, pycolmap.Rotation3d(R), t)); od = os.path.join(a.teil, d + "_ausgerichtet"); os.makedirs(od, exist_ok=True); M.write(od)
        out[d] = z; print(d, json.dumps(z, ensure_ascii=False), flush=True)
    json.dump(out, open(os.path.join(a.teil, "ausrichtung.json"), "w"), indent=1, ensure_ascii=False); return 0


if __name__ == "__main__":
    sys.exit(main())
