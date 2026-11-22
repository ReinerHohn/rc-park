#!/usr/bin/env python3
"""schwerkraft_je_bild.py - Schwerkraft (Richtung 'unten') JE BILD aus den senkrechten Kanten, fuer den globalen Mapper (GlobalMapper.ra_use_gravity 1).

Anlass: Recherche 19.11.2026 Punkt 1 (modelle/RECHERCHE_VERBESSERUNGEN_2026-11-19.md) + Fund am Martinstor (Kameralot 2,3 Grad verkippt). Mit Schwerkraft-Vorgabe muss die
Drehungsmittelung je Kamera nur noch den Kurswinkel bestimmen; Kippen/Rollen kann nicht wegdriften. COLMAP erwartet sie in pose_priors.gravity als Richtung 'unten' im
Kamerasystem (x rechts, y unten, z Blick). Bilder ohne klare Senkrechte bekommen keine Vorgabe (COLMAP faellt dort auf die normale Mittelung zurueck).

Verfahren: Linienstuecke (LSD) mit < 25 Grad Abweichung von der Bildsenkrechten -> Fluchtpunkt der Senkrechten (RANSAC + SVD, wie tools/lot_aus_fotos.py) -> Richtung K^-1 vp,
Vorzeichen so, dass sie im Bild nach unten zeigt. Haengt von der Brennweite ab (Blick nach oben zum Turm): deshalb NACH view_graph_calibrator aufrufen (kalibrierte Brennweiten).

Aufrufe:
  --db <db> --bilder <ordner>                       Vorgaben in die Datenbank schreiben (vorhandene GPS-Vorgaben bleiben, nur gravity wird gesetzt)
  --pruefen <sparse> --bilder <ordner> [--unten x,y,z]  gegen ein fertiges Modell pruefen (unten = Weltrichtung 'unten' im Modellsystem, z. B. -lot aus seiten_vereinen; ohne: Median der Bilder)
Optionen: --min-inlier 12 (Linien am Fluchtpunkt), --max-n (nur die ersten n Bilder, Test)."""
import os, sys, argparse, sqlite3, numpy as np, cv2


def fluchtpunkt_senkrecht(grau, rng, min_inlier=12, laenge_rel=0.06):
    """-> (vp homogen in Pixeln des Originalbilds, Zahl tragender Linien) oder (None, 0)."""
    sc = 1000.0 / max(grau.shape); g = cv2.resize(grau, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA) if sc < 1 else grau; sc = min(sc, 1.0)
    L = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(g)[0]
    if L is None: return None, 0
    L = L.reshape(-1, 4) / sc; d = L[:, 2:] - L[:, :2]; ln = np.linalg.norm(d, axis=1); ang = np.degrees(np.arctan2(np.abs(d[:, 0]), np.abs(d[:, 1])))
    L = L[(ln > laenge_rel * max(grau.shape)) & (ang < 25)]
    if len(L) < min_inlier: return None, 0
    h0 = np.c_[L[:, :2], np.ones(len(L))]; h1 = np.c_[L[:, 2:], np.ones(len(L))]; lh = np.cross(h0, h1); lh /= np.linalg.norm(lh[:, :2], axis=1, keepdims=True)
    mid = 0.5 * (L[:, :2] + L[:, 2:]); dl = L[:, 2:] - L[:, :2]; best = (0, None)
    for _ in range(600):
        i, j = rng.choice(len(L), 2, replace=False); vp = np.cross(lh[i], lh[j])
        if not np.isfinite(vp).all() or np.linalg.norm(vp) == 0: continue
        dv = vp[:2][None, :] - mid * vp[2]                                             # Richtung Linienmitte -> Fluchtpunkt (auch fuer vp im Unendlichen)
        cosw = np.abs((dv * dl).sum(1)) / (np.linalg.norm(dv, axis=1) * np.linalg.norm(dl, axis=1) + 1e-12); inl = cosw > np.cos(np.radians(1.0))
        if inl.sum() > best[0]: best = (int(inl.sum()), inl)
    if best[1] is None or best[0] < min_inlier: return None, best[0]
    vp = np.linalg.svd(lh[best[1]])[2][-1]; return vp, best[0]


def plausibel(d, max_rollen=10.0):
    """Gemessen Martinstor 20.11. (260 Bilder gegen das Modell): ohne Filter Median 1,0 Grad, aber Ausreisser bis 90 Grad (waagerechte statt senkrechter Linien).
    Rollen (Drehung um die Blickachse) ist bei Hand-, Drohnen- und Videobildern klein; 'unten' muss naeher an Bild-unten als an Bild-quer liegen."""
    return abs(np.degrees(np.arctan2(d[0], d[1]))) <= max_rollen and d[1] > 0.5


def unten_kamera(vp, f, cx, cy):
    """Fluchtpunkt -> Einheitsrichtung 'unten' im Kamerasystem (y zeigt im Bild nach unten)."""
    d = np.array([(vp[0] - cx * vp[2]) / f, (vp[1] - cy * vp[2]) / f, vp[2]]); d /= np.linalg.norm(d)
    return d if d[1] > 0 else -d


def kamera_K(model, params):
    p = np.frombuffer(params, np.float64)
    if model in (0, 2, 3, 8): return p[0], p[1], p[2]                                  # SIMPLE_PINHOLE, SIMPLE_RADIAL, RADIAL, SIMPLE_RADIAL_FISHEYE: f, cx, cy
    return 0.5 * (p[0] + p[1]), p[2], p[3]                                             # PINHOLE/OPENCV...: fx, fy, cx, cy


def bild(ordner, name):
    return cv2.imread(os.path.join(ordner, name), cv2.IMREAD_GRAYSCALE | cv2.IMREAD_IGNORE_ORIENTATION)


def in_db(db, ordner, min_inlier=12, max_n=None):
    c = sqlite3.connect(db); rng = np.random.default_rng(0)
    cams = {cid: (m, p) for cid, m, p in c.execute("select camera_id, model, params from cameras")}
    vorh = {iid: pid for pid, iid in c.execute("select pose_prior_id, corr_data_id from pose_priors where corr_sensor_type = 0")}
    nan3, nan9 = np.full(3, np.nan).tobytes(), np.full(9, np.nan).tobytes(); n = gesetzt = 0
    for iid, name, cid in c.execute("select image_id, name, camera_id from images order by image_id").fetchall()[:max_n]:
        n += 1; g = bild(ordner, name)
        if g is None: continue
        vp, k = fluchtpunkt_senkrecht(g, rng, min_inlier)
        if vp is None: continue
        f, cx, cy = kamera_K(*cams[cid]); d = unten_kamera(vp, f, cx, cy)
        if not plausibel(d): continue
        gesetzt += 1
        if iid in vorh: c.execute("update pose_priors set gravity = ? where pose_prior_id = ?", (d.tobytes(), vorh[iid]))
        else: c.execute("insert into pose_priors (corr_data_id, corr_sensor_id, corr_sensor_type, position, position_covariance, gravity, coordinate_system) values (?, ?, 0, ?, ?, ?, -1)", (iid, cid, nan3, nan9, d.tobytes()))
    c.commit(); print(f"SCHWERKRAFT: {gesetzt} von {n} Bildern mit Vorgabe (Rest ohne klare Senkrechte)"); return gesetzt


def pruefen(sparse, ordner, unten_welt, min_inlier=12, max_n=None):
    import pycolmap
    r = pycolmap.Reconstruction(sparse); rng = np.random.default_rng(0); fehler = []; welt = []; kam = []
    u = None if unten_welt is None else np.asarray(unten_welt, float) / np.linalg.norm(unten_welt)
    for im in list(r.images.values())[:max_n]:
        g = bild(ordner, im.name)
        if g is None: continue
        vp, k = fluchtpunkt_senkrecht(g, rng, min_inlier)
        if vp is None: continue
        cam = r.cameras[im.camera_id]; f, cx, cy = cam.mean_focal_length(), cam.principal_point_x, cam.principal_point_y; d = unten_kamera(vp, f, cx, cy)
        if not plausibel(d): continue
        if u is None: welt.append(im.cam_from_world().rotation.matrix().T @ d); kam.append((im, d)); continue
        wahr = im.cam_from_world().rotation.matrix() @ u; fehler.append(np.degrees(np.arccos(np.clip(d @ wahr, -1, 1))))
    if u is None:                                                                        # ohne bekannte Senkrechte: Median der Bilder als Bezug (zeigt die Streuung, nicht den gemeinsamen Fehler)
        u = np.median(np.array(welt), 0); u /= np.linalg.norm(u)
        fehler = [np.degrees(np.arccos(np.clip(d @ (im.cam_from_world().rotation.matrix() @ u), -1, 1))) for im, d in kam]
    e = np.array(fehler); print(f"PRUEFUNG: {len(e)} von {min(len(r.images), max_n or 10**9)} Bildern mit Vorgabe; Winkelfehler Median {np.median(e):.2f}, p90 {np.percentile(e, 90):.2f}, "
                               f"ueber 5 Grad {(e > 5).sum()}, ueber 20 Grad {(e > 20).sum()}"); return e


def lot_welt(kameras, ordner, n_max=150, min_inlier=12, seed=0, oben_ref=None):
    """LOT IM WELTRAHMEN aus den Fluchtpunkten der Senkrechten (22.11.2026, Lot-Runde: Gegenprobe zum Lot der Ausrichtung, unabhaengig von Wolke und LoD2).
    kameras: Liste dict(name, R (cam_from_world 3x3), f, cx, cy, breite, hoehe) in den Pixeln des SfM-Bilds; die Datei in <ordner> darf eine andere Groesse haben
    (Massstab je Achse, nur wenn das Seitenverhaeltnis passt, sonst uebersprungen). -> dict(oben (3), n, streuung_median_grad, streuung_p90_grad) oder None.
    Robust: Median der Weltrichtungen je Bild, dann Mittel der Bilder < 3 Grad daneben (Ausreisser: Rollen, Fehl-Fluchtpunkte). Vorzeichen nach oben_ref, sonst 'Bild-oben'."""
    rng = np.random.default_rng(seed); ks = list(kameras)
    if n_max and len(ks) > n_max: ks = [ks[i] for i in sorted(rng.choice(len(ks), n_max, replace=False))]
    W = []
    for k in ks:
        g = bild(ordner, k["name"])
        if g is None: continue
        sy, sx = g.shape[0] / float(k["hoehe"]), g.shape[1] / float(k["breite"])
        if abs(sx / sy - 1) > 0.02: continue                                              # anderes Bild (gedreht/beschnitten) - nicht raten
        vp, _ = fluchtpunkt_senkrecht(g, rng, min_inlier)
        if vp is None: continue
        d = unten_kamera(vp, k["f"] * sx, k["cx"] * sx, k["cy"] * sy)
        if not plausibel(d): continue
        W.append(-(np.asarray(k["R"], float).T @ d))                                     # 'oben' in Weltkoordinaten
    if len(W) < 8: return None
    W = np.array(W); m = np.median(W, 0); m /= np.linalg.norm(m)
    for _ in range(3):
        a = np.degrees(np.arccos(np.clip(W @ m, -1, 1))); inn = a < 3.0
        if inn.sum() < 5: break
        m = W[inn].mean(0); m /= np.linalg.norm(m)
    if oben_ref is not None and m @ np.asarray(oben_ref, float) < 0: m = -m
    a = np.degrees(np.arccos(np.clip(W @ m, -1, 1)))
    return dict(oben=m.tolist(), n=int(len(W)), getragen=int((a < 3.0).sum()), streuung_median_grad=float(np.median(a)), streuung_p90_grad=float(np.percentile(a, 90)))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--db"); ap.add_argument("--pruefen"); ap.add_argument("--bilder", required=True); ap.add_argument("--unten")
    ap.add_argument("--min-inlier", type=int, default=12); ap.add_argument("--max-n", type=int); a = ap.parse_args(argv)
    if a.pruefen: pruefen(a.pruefen, a.bilder, [float(x) for x in a.unten.split(",")] if a.unten else None, a.min_inlier, a.max_n); return 0
    if a.db: return 0 if in_db(a.db, a.bilder, a.min_inlier, a.max_n) else 3
    ap.error("--db oder --pruefen")


if __name__ == "__main__": sys.exit(main())
