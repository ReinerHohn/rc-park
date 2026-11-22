#!/usr/bin/env python3
"""gps_seiten_pruefen.py <sparse-modell> --bilder <ordner> [--grenze 12]

Seitenpruefung OHNE Vorwissen (20.11.2026, Schwabentor/Martinstor-Verkleben): Kamerazentren des Modells werden waagerecht (Lot = Mittel der
Bild-oben-Richtungen) robust per 2D-Aehnlichkeit (Drehung, Massstab, Verschiebung, KEINE Spiegelung) auf die Foto-GPS-Lagen (EXIF, ENU in m) gelegt.
Verklebte Seiten (Rueckseite auf die Vorderseite geklappt) sitzen dann zig Meter neben ihrem GPS -> Anteil Ausreisser ueber --grenze (Handy-GPS ~5 m).
Ausgabe: Zahl GPS-Bilder, Median-Rest in m, Anteil > grenze, Urteil. rc 3 = verdaechtig (>= 15 % Ausreisser bei >= 25 GPS-Bildern im 150-m-Umkreis), rc 2 = zu wenig GPS."""
import os, sys, argparse, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def gps_enu(ordner, namen):
    from PIL import Image
    roh = {}
    for n in namen:
        try:
            e = Image.open(os.path.join(ordner, n)).getexif().get_ifd(0x8825)
            if not e or 2 not in e or 4 not in e: continue
            gr = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            lat = gr(e[2]) * (-1 if e.get(1) == "S" else 1); lon = gr(e[4]) * (-1 if e.get(3) == "W" else 1)
            if abs(lat) > 0.1: roh[n] = (lat, lon)
        except Exception: continue
    if not roh: return {}
    la0, lo0 = np.median([v[0] for v in roh.values()]), np.median([v[1] for v in roh.values()])
    return {n: np.array([(lo - lo0) * 111320 * np.cos(np.radians(la0)), (la - la0) * 110540]) for n, (la, lo) in roh.items()}


def aehnlich2d(X, Y):
    mx, my = X.mean(0), Y.mean(0); Xc, Yc = X - mx, Y - my; U, S, Vt = np.linalg.svd(Yc.T @ Xc); D = np.eye(2); D[1, 1] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = (S * np.diag(D)).sum() / (Xc ** 2).sum(); return s, R, my - s * R @ mx


def pruefen(modell, ordner, grenze=12.0, rng=np.random.default_rng(0)):
    import pycolmap
    r = pycolmap.Reconstruction(modell); ims = list(r.images.values())
    from seiten_gps_vereinen import lot_aus_bild_achsen                                  # 22.11.2026: Lot aus Bild-x-Achsen (Bild-oben-Mittel kippt um die Kameraneigung, Schwabentor 13-16 Grad)
    oben = lot_aus_bild_achsen([im.cam_from_world().rotation.matrix() for im in ims if im.has_pose])
    e1 = np.cross(oben, [1, 0, 0] if abs(oben[0]) < 0.9 else [0, 1, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(oben, e1)
    G = gps_enu(ordner, [im.name for im in ims]); n = [im.name for im in ims if im.name in G and np.linalg.norm(G[im.name]) < 150]
    # 20.11.: Martinstor hat nur 16 GPS-Bilder (Wikimedia, Fernaufnahmen bis 300 m, gemischte Guete) -> falscher Alarm 'verdaechtig'. Daher >= 25 Bilder im 150-m-Umkreis.
    if len(n) < 25: return dict(gps=len(n), urteil="ZU WENIG GPS (unter 25 im 150-m-Umkreis, keine Aussage)"), 2
    C = {im.name: im.projection_center() for im in ims}; X = np.array([[C[k] @ e1, C[k] @ e2] for k in n]); Y = np.array([G[k] for k in n])
    e = urteil_2d(X, Y, grenze, rng); e["weit"] = [k for k, x in zip(n, e.pop("rest")) if x > grenze]; return e, (3 if e["ausreisser"] >= 0.15 else 0)


def urteil_2d(X, Y, grenze=12.0, rng=np.random.default_rng(0)):
    """X: Modell-Zentren waagerecht (n x 2), Y: GPS ENU in m (n x 2)."""
    best = None; n = X
    for _ in range(400):                                                                # RANSAC: 2 Punkte bestimmen eine 2D-Aehnlichkeit
        i = rng.choice(len(n), 2, replace=False)
        if np.linalg.norm(X[i[0]] - X[i[1]]) < 1e-9 or np.linalg.norm(Y[i[0]] - Y[i[1]]) < 5: continue
        s, R, t = aehnlich2d(X[i], Y[i]); d = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1); k = (d < grenze).sum()
        if best is None or k > best[0]: best = (k, d < grenze)
    s, R, t = aehnlich2d(X[best[1]], Y[best[1]]); d = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1)
    aus = float((d > grenze).mean()); urteil = "VERDAECHTIG (Seite verklebt?)" if aus >= 0.15 else "GPS-STIMMIG"
    return dict(gps=len(n), median_m=float(np.median(d)), ausreisser=aus, urteil=urteil, rest=d)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("modell"); ap.add_argument("--bilder", required=True); ap.add_argument("--grenze", type=float, default=12.0); a = ap.parse_args(argv)
    e, rc = pruefen(a.modell, a.bilder, a.grenze)
    print(f"GPS-SEITEN: {e['gps']} GPS-Bilder" + (f", Rest Median {e['median_m']:.1f} m, ueber {a.grenze:.0f} m: {100 * e['ausreisser']:.0f} %" if "median_m" in e else "") + f" -> {e['urteil']}")
    return rc


if __name__ == "__main__": sys.exit(main())
