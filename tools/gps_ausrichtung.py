#!/usr/bin/env python3
"""gps_ausrichtung.py <objekt.json> <kameras.json> <fotos_eigen_ordner> <dicht_ply> - Ausrichtung ueber GPS der eigenen Fotos (Exif).

Idee: Die Kamerazentren der Rekonstruktion werden auf ihre GPS-Positionen (UTM32, Lage in der Ebene) gefittet:
Maßstab, Drehung um die Lotachse, Verschiebung. Die Hoehe kommt aus der Kameraebene (Strassenfotos ~1,6 m ueber Boden, ANNAHME).
Danach wird die dichte Wolke in das Gebaeudesystem uebertragen und gegen die LoD2-Waende bewertet.

Gibt aus: Maßstab, mittlerer Abstand (Median) der Wolke zu den Waenden, Anteil innerhalb 0,5 m.
Vergleich: dieselbe Bewertung fuer die bisherige Ausrichtung (messprotokoll/SFM-AUSRICHTUNG-*.json), wenn vorhanden.
"""
import sys, os, json, glob, math, argparse
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def gps_exif(pfad):
    """(lat, lon) in Grad aus Exif oder None."""
    from PIL import Image
    try:
        e = Image.open(pfad).getexif(); gi = e.get_ifd(0x8825)
        if not gi or 2 not in gi or 4 not in gi: return None
        def dms(v): return v[0] + v[1] / 60 + v[2] / 3600
        lat = dms(gi[2]) * (-1 if gi.get(1, "N") == "S" else 1); lon = dms(gi[4]) * (-1 if gi.get(3, "E") == "W" else 1)
        return lat, lon
    except Exception:
        return None

def umeyama2d(a, b):
    """Aehnlichkeit b ~ s R a + t in der Ebene (Rotation mit det +1)."""
    ma, mb = a.mean(0), b.mean(0); A, B = a - ma, b - mb
    U, S, Vt = np.linalg.svd(B.T @ A / len(a))
    D = np.eye(2); D[1, 1] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = (S * np.diag(D)).sum() / (A ** 2).sum() * len(a)
    t = mb - s * R @ ma
    return s, R, t

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("objekt"); ap.add_argument("kameras"); ap.add_argument("fotos_eigen"); ap.add_argument("dicht")
    ap.add_argument("--hoehe-kamera", type=float, default=1.6)
    a = ap.parse_args()
    obj = json.load(open(a.objekt)); R_ = obj["rahmen"]
    c0 = np.array(R_["mitte_utm"]); xh = np.array(R_["xhat_utm"]); yh = np.array(R_["yhat_utm"]); gel = R_["gelaende"]
    KJ = json.load(open(a.kameras))
    C = {b["name"]: np.array(b["C"]) for b in KJ["bilder"]}
    # GPS der eigenen Fotos -> UTM -> Modellkoordinaten (u,v)
    from bilder_holen import wgs84_zu_utm
    paare = []
    for pfad in sorted(glob.glob(os.path.join(a.fotos_eigen, "*.jpg"))):
        n = os.path.basename(pfad)
        if n not in C: continue
        g = gps_exif(pfad)
        if g is None: continue
        E, N = wgs84_zu_utm(g[0], g[1])
        d = np.array([E, N]) - c0
        paare.append((n, np.array([d @ xh, d @ yh]), C[n]))
    print(f"Fotos mit GPS und Kamera in der Rekonstruktion: {len(paare)}")
    if len(paare) < 10:
        print("zu wenige Paare"); return 2
    Cs = np.array([p[2] for p in paare]); Gm = np.array([p[1] for p in paare])
    # Lot aus der Kameraebene (wie sfm_lod2_ausrichten.py)
    cm = Cs.mean(0); _, sv, vt = np.linalg.svd(Cs - cm); up = vt[2]
    e1 = np.cross(up, [1, 0, 0]); e1 = e1 if np.linalg.norm(e1) > 0.1 else np.cross(up, [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(up, e1)
    B = np.vstack([e1, e2, up])
    Hs = (Cs - cm) @ B.T                                   # Kameras in SfM-Basis
    # Robust: GPS auf der Strasse hat Ausreisser -> schrittweise die schlechtesten 30 % weglassen
    gut = np.ones(len(Hs), bool)
    for _ in range(6):
        s, Rh, th = umeyama2d(Hs[gut, :2], Gm[gut])
        res = np.linalg.norm((s * Hs[:, :2] @ Rh.T + th) - Gm, axis=1)
        grenze = np.percentile(res[gut], 70); gut = res <= grenze
    print(f"robuste Anpassung: {gut.sum()} von {len(Hs)} Kameras, Restfehler Median {np.median(res[gut]):.2f} m")
    # Hoehe: Kameras auf h_kamera ueber Boden; Lot-Vorzeichen so, dass die Wolke oberhalb der Kameras liegt
    P = np.load(os.path.join(os.path.dirname(a.dicht), "..", "fused_probe.npy")) if False else None
    dt = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("nx", "<f4"), ("ny", "<f4"), ("nz", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
    raw = open(a.dicht, "rb").read(); ke = raw.index(b"end_header\n") + len(b"end_header\n")
    n_p = int([l for l in raw[:ke].decode().splitlines() if l.startswith("element vertex")][0].split()[-1])
    V = np.frombuffer(raw, dtype=dt, count=n_p, offset=ke)
    X = np.c_[V["x"], V["y"], V["z"]].astype(float)
    rng = np.random.default_rng(1); sub = X[rng.choice(len(X), min(len(X), 400000), replace=False)]
    Ys = (sub - cm) @ B.T
    if np.median(Ys[:, 2]) < np.median(Hs[:, 2]): B[2] *= -1; up = -up; Hs[:, 2] *= -1; Ys[:, 2] *= -1
    hoehe_cam = np.median(Hs[:, 2])
    dz0 = a.hoehe_kamera - s * hoehe_cam                   # Modell-Hoehe der Kamera = Annahme 1,6 m ueber Gelaende (Startwert)
    # Transformation SfM -> Modell: X_mod = S (B (X - cm)) mit Lage (s, Rh, th) und Hoehe (s, dz)
    def nach_modell_dz(Xs, dzz):
        Y = (Xs - cm) @ B.T
        hx = s * (Y[:, :2] @ Rh.T) + th
        return np.c_[hx[:, 0], hx[:, 1], s * Y[:, 2] + dzz]
    def nach_modell(Xs):
        return nach_modell_dz(Xs, dz)
    # Hoehe nicht annehmen, sondern an die Waende anpassen: bester dz ueber Abstand Wolke-Waende
    import sfm_lod2_ausrichten as AL
    T, Tn, Tt, wand2d, grund2d, nb, Te = AL.lod2_ziel(obj, 30.0)
    W = T[Te & (Tt == 0)]; wb = cKDTree(W)
    klein = sub[rng.choice(len(sub), min(len(sub), 60000), replace=False)]
    best = None
    for dz in np.arange(dz0 - 6, dz0 + 6.01, 0.25):
        dd, _ = wb.query(nach_modell_dz(klein, dz))
        m = np.median(dd)
        if best is None or m < best[0]: best = (m, dz)
    dz = best[1]
    print(f"Hoehen-Suche: dz={dz:.2f} (Startwert {dz0:.2f}), Median {best[0]:.2f} m")
    Pm = nach_modell(sub)
    d, _ = wb.query(Pm)
    print(f"GPS-Ausrichtung: Massstab s={s:.4f} (SfM je m: {1/s:.3f}), Abstand Wolke-Waende: Median {np.median(d):.2f} m, innerhalb 0,5 m: {100*np.mean(d<0.5):.1f} %")
    # Vergleich: bisherige Ausrichtung
    bisher = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "messprotokoll", "SFM-AUSRICHTUNG-*.json")))
    for f in bisher:
        try:
            tr = json.load(open(f))["transformation"]
            Rt = Rot.from_rotvec(tr["rvec"]).as_matrix(); st = float(tr["s"]); tt = np.array(tr["t"])
            Pb = (sub - tt) @ Rt / st                      # X_mod = (1/s) R^T (X - t)
            db, _ = cKDTree(W).query(Pb)
            print(f"{os.path.basename(f)}: Abstand Median {np.median(db):.2f} m, innerhalb 0,5 m: {100*np.mean(db<0.5):.1f} %")
        except Exception as e:
            print(f"{os.path.basename(f)}: nicht lesbar ({type(e).__name__})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
