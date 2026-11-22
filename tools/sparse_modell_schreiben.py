#!/usr/bin/env python3
"""sparse_modell_schreiben.py - COLMAP-Modell ins Modellsystem (Meter) bringen, aus einer geschriebenen Ausrichtung (messprotokoll/SFM-AUSRICHTUNG-<name>.json).

22.11.2026 (Lauf kette-schwabentor-anker-1122e): sfm_lod2_ausrichten.py laeuft in der Kette mit --kameras/--dicht in der GPU-Umgebung ohne pycolmap und laedt dort kein
COLMAP-Modell - sfm/sparse_modell_<name> wurde darum nie geschrieben ("AttributeError 'NoneType' object has no attribute 'Sim3d'"). Die Kette braucht es nicht; die
Handwerkzeuge (sfm_lod2_buendel, foto_auswahl, abdeckung, nullstart-Verzerrung) schon. Dieses Werkzeug rechnet es nachtraeglich aus der Transformation der JSON
(X_sfm = s * R @ X_modell + t  ->  X_modell = R^T (X_sfm - t) / s), dieselbe Formel wie sfm_lod2_ausrichten.py beim direkten Schreiben.
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/sparse_modell_schreiben.py <objekt.json> <SFM-AUSRICHTUNG-<name>.json> <sparse_dir> [--aus DIR]
        (Standard --aus: <objektordner>/sfm/sparse_modell_<name>; <name> aus dem Dateinamen der Ausrichtung). rc 0 = geschrieben, 2 = Kameras passen nicht zur JSON.
"""
import os, sys, json, argparse
import numpy as np
from scipy.spatial.transform import Rotation as Rot


def sim_aus_ausrichtung(tr):
    """(Massstab, Rotation 3x3, Verschiebung) der Abbildung SfM -> Modell aus transformation{s, rvec, t} (X_sfm = s R X_m + t)."""
    s = float(tr["s"]); R = Rot.from_rotvec(tr["rvec"]).as_matrix(); t = np.asarray(tr["t"], float)
    return 1.0 / s, R.T, -R.T @ t / s


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ausrichtung"); ap.add_argument("sparse"); ap.add_argument("--aus", default="")
    a = ap.parse_args()
    import pycolmap
    A = json.load(open(a.ausrichtung)); sk, Rk, tk = sim_aus_ausrichtung(A["transformation"])
    name = os.path.basename(a.ausrichtung)[len("SFM-AUSRICHTUNG"):-len(".json")].lstrip("-")
    ziel = a.aus or os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "sfm", "sparse_modell" + (("_" + name) if name else ""))
    rec = pycolmap.Reconstruction(a.sparse)
    rec.transform(pycolmap.Sim3d(sk, pycolmap.Rotation3d(Rk), tk))
    kam = A.get("kameras", {}); d = []
    for im in rec.images.values():
        nr = os.path.splitext(im.name)[0]
        if nr in kam and im.has_pose: d.append(np.linalg.norm(np.asarray(im.projection_center()) - np.asarray(kam[nr]["standort"], float)))
    med = float(np.median(d)) if d else float("inf")
    print(f"Probe: {len(d)} Kameras auch in der Ausrichtung, Standort-Abweichung Median {med:.3f} m")
    if not d or med > 0.05:
        print("FEHLER: transformierte Kameras passen nicht zu den Standorten der Ausrichtung (falsches sparse-Modell?) - nichts geschrieben"); return 2
    os.makedirs(ziel, exist_ok=True); rec.write(ziel); print("geschrieben:", ziel, "(COLMAP-Modell im Modellsystem, Meter)"); return 0


if __name__ == "__main__":
    sys.exit(main())
