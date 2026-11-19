#!/usr/bin/env python3
"""sfm_stabil_schnitt.py <sparse_A/0> <sparse_B/0> --ausgabe <ordner> [--lage 0.10] [--rot 2.0] [--liste unstabil.txt]
Konsens zweier Laeufe des globalen Mappers (gleiche Eingabe, andere Zufalls-Startwerte; Messung Schwabentor 19.11.: 38 % der Kameras > 10 % Kernradius,
30 % Rotation > 2 Grad zwischen seed 1 und 2). Richtet B ueber die Kamerarotationen (chordaler Mittelwert) und Standorte (Massstab/Versatz, robust) auf A aus,
markiert jede Kamera als STABIL (Lage-Rest < lage x Kernradius UND Rotation < rot Grad) oder UNSTABIL (auch: nur in einem Lauf registriert).
Schreibt Modell A ohne die unstabilen Kameras nach --ausgabe (deregister_frame, Punkte bleiben) und die Namen der unstabilen Bilder in --liste,
damit Stufe 2 sie gegen das feste Rueckgrat neu einhaengt (`colmap mapper --input_path <ausgabe> --Mapper.fix_existing_frames 1`).
Python: /media/oem/scan/venv-colmap/bin/python -I"""
import sys, os, json, argparse
import numpy as np   # pycolmap nur in posen()/main() (Schnelltest prueft schnitt() mit venv-seg ohne pycolmap)

_cfw = lambda im: im.cam_from_world() if callable(im.cam_from_world) else im.cam_from_world


def posen(r):
    return {os.path.basename(im.name): (im.projection_center(), _cfw(im).rotation.matrix(), im.image_id) for im in r.images.values() if im.has_pose}


def schnitt(A, B, lage=0.10, rot=2.0):
    """gibt (stabil: set Namen, bericht dict, reste je Name)"""
    keys = [k for k in A if k in B]
    if len(keys) < 5: return set(), dict(fehler="zu wenig gemeinsame Bilder", gemeinsam=len(keys)), {}
    X = np.array([B[k][0] for k in keys]); Y = np.array([A[k][0] for k in keys]); RB = np.array([B[k][1] for k in keys]); RA = np.array([A[k][1] for k in keys]); sel = np.ones(len(keys), bool)
    for _ in range(8):
        M = sum(RA[i].T @ RB[i] for i in np.where(sel)[0]); U, _, Vt = np.linalg.svd(M); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ D @ Vt   # Welt B -> Welt A
        mx, my = X[sel].mean(0), Y[sel].mean(0); Xr = (R @ (X - mx).T).T; s = float(np.sum((Y[sel] - my) * Xr[sel]) / np.sum(Xr[sel] ** 2))
        r = np.linalg.norm(s * Xr + my - Y, axis=1); w = np.array([np.degrees(np.arccos(np.clip((np.trace(RA[i] @ (RB[i] @ R.T).T) - 1) / 2, -1, 1))) for i in range(len(keys))])
        neu = (r < max(2.5 * np.median(r), 1e-9)) & (w < max(2.5 * np.median(w), 0.5))
        if neu.sum() < 4 or neu.sum() == sel.sum() and (neu == sel).all(): break
        sel = neu
    rk = float(np.linalg.norm(Y[sel] - Y[sel].mean(0), axis=1).mean())
    ok = (r < lage * rk) & (w < rot); stabil = {k for k, o in zip(keys, ok) if o}
    reste = {k: dict(lage_rel=round(float(r[i] / rk), 4), rot_grad=round(float(w[i]), 2)) for i, k in enumerate(keys)}
    ber = dict(gemeinsam=len(keys), nur_A=len(set(A) - set(B)), nur_B=len(set(B) - set(A)), stabil=len(stabil), unstabil=len(keys) - len(stabil), kernradius=rk,
               lage_median_rel=round(float(np.median(r) / rk), 4), rot_median_grad=round(float(np.median(w)), 2), anteil_unstabil_proz=round(100 * (1 - len(stabil) / len(keys))))
    return stabil, ber, reste


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--ausgabe", required=True); ap.add_argument("--lage", type=float, default=0.10)
    ap.add_argument("--rot", type=float, default=2.0); ap.add_argument("--liste", default=""); a = ap.parse_args()
    import pycolmap; ra, rb = pycolmap.Reconstruction(a.a), pycolmap.Reconstruction(a.b); A, B = posen(ra), posen(rb)
    stabil, ber, reste = schnitt(A, B, a.lage, a.rot)
    if "fehler" in ber: print(json.dumps(ber)); sys.exit(2)
    weg = [k for k in A if k not in stabil]
    for k in weg:
        im = ra.images[A[k][2]]
        if im.has_frame_id and ra.exists_frame(im.frame_id) and ra.frame(im.frame_id).has_pose: ra.deregister_frame(im.frame_id)
    os.makedirs(a.ausgabe, exist_ok=True); ra.write(a.ausgabe)
    unstabil = sorted(set(weg) | (set(B) - set(A)))
    if a.liste: open(a.liste, "w").write("\n".join(unstabil) + "\n")
    ber.update(ausgabe=a.ausgabe, verbleibend=ra.num_reg_images(), liste=a.liste, lage_schwelle=a.lage, rot_schwelle=a.rot)
    json.dump(dict(bericht=ber, reste=reste), open(os.path.join(a.ausgabe, "schnitt.json"), "w"), indent=1)
    print(json.dumps(ber))


if __name__ == "__main__": main()
