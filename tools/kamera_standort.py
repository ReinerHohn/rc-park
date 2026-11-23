"""kamera_standort.py - Kamerastandort aus einer K-Datei (messprotokoll/K-<foto>.json, Block "kamera"), egal welcher Schreiber.

23.11.2026 (Kettenlauf 1122r, schwabentor-1122): tiefe_lokal.py stuerzte an 5 Waenden mit KeyError 'standort_xyz' ab -> fassaden_kette rc 3 ->
'bauen_mit_fassaden' lief nicht, Sued-/Ostwand ohne Relief. Ursache: die K-Dateien haben drei Schreibweisen fuer denselben Wert:
  standort_xyz  - foto_kalibrieren, kameras_aus_buendel, kamera_lod2_nachfuehren, kamera_bruecke (394 von 625 Dateien)
  standort      - kameras_nachtragen (144, 'nachregistriert'), kamera_verfeinern (87)  -> KEIN standort_xyz
  nur rvec/t    - Pose; Standort = -R^T t (gemessen: standort == -R^T t bis 4e-12 m, standort_xyz bis 0,8 mm Rundung)
Reihenfolge: standort_xyz, standort, Pose. Keine Pose und kein Standort -> None (Aufrufer ueberspringt das Foto mit Grund, nie abstuerzen)."""
import numpy as np


def _rodrigues(r):
    """Drehvektor -> Drehmatrix (wie cv2.Rodrigues; nur numpy, laeuft in jeder Umgebung)."""
    th = float(np.linalg.norm(r))
    if th < 1e-12: return np.eye(3)
    k = r / th; Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * Kx + (1 - np.cos(th)) * Kx @ Kx


def kamera_standort(K):
    """K = Inhalt von ["kamera"] -> np.array([x, y, z]) im Kamerarahmen der K-Dateien oder None."""
    if not isinstance(K, dict): return None
    for f in ("standort_xyz", "standort"):
        v = K.get(f)
        if v is not None and len(v) >= 3:
            v = np.asarray(v[:3], float)
            if np.all(np.isfinite(v)): return v
    if K.get("rvec") is not None and K.get("t") is not None and len(K["rvec"]) == 3 and len(K["t"]) == 3:
        v = -_rodrigues(np.asarray(K["rvec"], float)).T @ np.asarray(K["t"], float)
        if np.all(np.isfinite(v)): return v
    return None


def kamera_standort_grund(K):
    """-> (standort oder None, Grund-Text fuer das Ueberspringen)."""
    S = kamera_standort(K)
    return S, ("" if S is not None else "K-Datei ohne standort_xyz/standort und ohne Pose rvec/t")
