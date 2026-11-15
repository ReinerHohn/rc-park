#!/usr/bin/env python3
"""ausrichtung_uebertragen.py - Ausrichtung eines schon ausgerichteten SfM-Modells auf ein NEUES SfM-Modell uebertragen (gemeinsame Kameras).

Warum (15.11.2026): Schwabentor v1 (196 Bilder) ist an LoD2 ausgerichtet und besteht das GPS-Tor; v2 (494 Bilder, + Video/Commons/Fernkameras)
liess sich mit sfm_lod2_ausrichten.py nicht sauber ausrichten (Massstab laeuft an die Grenze). Beide Modelle teilen ~190 eigene Fotos: die
Aehnlichkeit neu -> alt aus den gemeinsamen Kamerazentren (Umeyama, robust getrimmt) ist auf Promille genau und braucht kein LoD2.

  /media/oem/scan/venv-colmap/bin/python -I tools/ausrichtung_uebertragen.py modelle/<obj>/objekt.json --alt <SFM-AUSRICHTUNG-alt.json> --sparse <neu/sparse/0> --name <neu>
        [--dicht fused.ply -> zweiter Schritt mit venv-seg: --nur_wolke]
Schritt 1 (venv-colmap, pycolmap): schreibt messprotokoll/SFM-AUSRICHTUNG-<name>.json (gleiches Format wie sfm_lod2_ausrichten.py, verfahren = uebertragen).
Schritt 2 (venv-seg, trimesh): --nur_wolke --dicht fused.ply  -> sfm/punkte_modell_<name>.npy + punkte_farben_<name>.npy.
Namen: Quellpraefix 'eigen__' wird fuer den Abgleich abgestreift. rc 3 = zu wenig gemeinsame Kameras (< 15) oder Rest > 1 % der Ausdehnung.
"""
import sys, os, json, argparse, numpy as np
from scipy.spatial.transform import Rotation as Rot


def kern(n): n = os.path.splitext(os.path.basename(n))[0]; return n.split("__", 1)[1] if "__" in n else n


def umeyama(X, Y):
    """Y ~ s R X + t"""
    mx, my = X.mean(0), Y.mean(0); Xc, Yc = X - mx, Y - my; U, S, Vt = np.linalg.svd(Yc.T @ Xc / len(X)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = np.trace(np.diag(S) @ D) / Xc.var(0).sum(); return s, R, my - s * R @ mx


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--alt"); ap.add_argument("--sparse"); ap.add_argument("--name", required=True)
    ap.add_argument("--dicht", default=""); ap.add_argument("--nur_wolke", action="store_true"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); pth = os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{a.name}.json")
    if a.nur_wolke:
        import trimesh
        T = json.load(open(pth))["transformation"]; s = T["s"]; R = Rot.from_rotvec(T["rvec"]).as_matrix(); t = np.array(T["t"])
        w = trimesh.load(a.dicht); X = np.asarray(w.vertices, float); Pm = ((X - t) / s) @ R                    # X_sfm = s R X_m + t
        os.makedirs(os.path.join(od, "sfm"), exist_ok=True); np.save(os.path.join(od, "sfm", f"punkte_modell_{a.name}.npy"), Pm.astype(np.float32))
        np.save(os.path.join(od, "sfm", f"punkte_farben_{a.name}.npy"), np.asarray(w.colors)[:, :3].astype(np.uint8))
        print(f"Wolke im Modellrahmen: {len(Pm)} Punkte, z p1 {np.percentile(Pm[:, 2], 1):.1f} .. p99 {np.percentile(Pm[:, 2], 99):.1f} m"); return 0
    import pycolmap
    A = json.load(open(a.alt)); alt = {}
    for n, k in A["kameras"].items(): Rk = np.array(k["R"], float); alt[kern(n)] = -Rk.T @ np.array(k["t"], float)          # Zentrum im Modellrahmen (m)
    rec = pycolmap.Reconstruction(a.sparse); ims = [im for im in rec.images.values() if im.has_pose]
    gem = [im for im in ims if kern(im.name) in alt]
    if len(gem) < 15: print(f"FEHLER: nur {len(gem)} gemeinsame Kameras"); return 3
    X = np.array([alt[kern(im.name)] for im in gem]); Y = np.array([im.projection_center() for im in gem]); idx = np.arange(len(gem))
    for _ in range(6):
        s, R, t = umeyama(X[idx], Y[idx]); res = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1) / s                       # Rest in Metern
        idx = np.where(res < max(3 * np.median(res), 0.05))[0]
    ausd = float(np.linalg.norm(X[idx] - X[idx].mean(0), axis=1).max())
    print(f"gemeinsame Kameras {len(gem)}, benutzt {len(idx)}; Rest Median {np.median(res[idx]):.3f} m, p90 {np.percentile(res[idx], 90):.3f} m, max (alle) {res.max():.2f} m; Ausdehnung {ausd:.1f} m; Massstab {s:.5f} SfM-Einheiten/m")
    aus = [kern(gem[i].name) for i in range(len(gem)) if i not in set(idx.tolist())]
    if aus: print(f"  {len(aus)} gemeinsame Kameras liegen in beiden Modellen verschieden (> 3x Median): {aus[:8]}{' ...' if len(aus) > 8 else ''}")
    kam = {}
    for im in ims:
        cw = im.cam_from_world(); Rc = cw.rotation.matrix() @ R; tc = (cw.rotation.matrix() @ t + np.array(cw.translation)) / s; cam = rec.cameras[im.camera_id]; pr = list(cam.params); m = cam.model.name
        kam[os.path.splitext(im.name)[0]] = dict(standort=(-Rc.T @ tc).round(2).tolist(), f_px_original=float(pr[0]), fak=1.0, off=[0.0, 0.0], R=Rc.tolist(), t=tc.tolist(),
                                                cx=float(pr[2] if m in ("PINHOLE", "OPENCV", "FULL_OPENCV") else pr[1]), cy=float(pr[3] if m in ("PINHOLE", "OPENCV", "FULL_OPENCV") else pr[2]),
                                                k=[float(v) for v in pr[3:]] if m in ("SIMPLE_RADIAL", "RADIAL") else [], bild_b=cam.width, bild_h=cam.height, hinweis="f/cx/cy in SfM-Bildpixeln")
    hz = np.array([k["standort"][2] for k in kam.values()])
    out = dict(verfahren=f"ausrichtung_uebertragen.py: Aehnlichkeit ueber {len(idx)} gemeinsame Kameras aus {os.path.basename(a.alt)} (dort: {A.get('verfahren', '?')[:80]})", sparse=a.sparse,
               fotos_sfm=sorted(kam), fotos_mit_picks=[], transformation=dict(beschreibung="X_sfm = s * R @ X_modell + t ; Modellsystem = objekt.json rahmen", s=float(s), rvec=Rot.from_matrix(R).as_rotvec().tolist(),
               t=t.tolist(), gemeinsame_kameras=int(len(idx)), rest_median_m=float(np.median(res[idx])), rest_p90_m=float(np.percentile(res[idx], 90))), kameras=kam,
               kamerahoehen=dict(median=float(np.median(hz)), auf_strassenniveau=int(np.sum((hz > -1) & (hz < 6))), n=len(hz)), quelle_ausrichtung=a.alt)
    os.makedirs(os.path.dirname(pth), exist_ok=True); json.dump(out, open(pth, "w"), indent=1, ensure_ascii=False)
    print(f"{pth}: {len(kam)} Kameras, Kamerahoehe Median {np.median(hz):.2f} m ({int(np.sum((hz > -1) & (hz < 6)))} von {len(hz)} zwischen -1 und 6 m)")
    return 3 if np.median(res[idx]) > 0.01 * ausd else 0


if __name__ == "__main__":
    sys.exit(main())
