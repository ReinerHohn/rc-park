#!/usr/bin/env python3
"""sfm_gps_ausgleich.py <modell> --bilder <fotoordner> --aus <ordner> [--teile teile.json]

GEMEINSAMER BUENDELAUSGLEICH MIT POSITIONS-PRIOREN AUS DEM FOTO-GPS (22.11.2026, Nulllauf schwabentor-1122: vereintes Modell aus zwei Seitenteilen, 507 Bilder, 162 mit
Geotag; die Teile wurden je fuer sich per GPS-Sim3 gelegt (tools/seiten_gps_vereinen.py), danach gab es KEINEN gemeinsamen Ausgleich).
POSITIONS-PRIOREN SIND NICHT DIE "GIFTIGEN" EXIF-PRIOREN: die Kette loescht BRENNWEITEN-Prioren (cameras.source / prior_focal_length, tools/sfm_db_variante.py --priors loeschen,
modelle/GLOBALER_MAPPER_STABIL.md Befund 1: falsche EXIF-Brennweiten bis 8,7 Mio px, im Kalibrator konstant). Die Tabelle pose_priors (Lage) bleibt dort unangetastet
(nur beim Loeschen eines Bildes), und dieses Werkzeug schreibt NICHTS in eine Datenbank: die Prioren entstehen hier im Speicher aus dem EXIF-GPS.
SCHNITTSTELLE (pycolmap 4.2.1, BSD-3; Quelltext COLMAP 4.3.dev estimators/bundle_adjustment_ceres.cc PosePriorBundleAdjuster): create_pose_prior_bundle_adjuster(BA-Optionen,
PosePriorBundleAdjustmentOptions, BundleAdjustmentConfig, [PosePrior], Reconstruction). Der Ausgleicher legt das Modell erst per RANSAC-Sim3 (alignment_ransac.max_error in
Metern) auf die Prioren, gewichtet jede Lage mit ihrer Kovarianz (Achsen einzeln) und robust (ceres.prior_position_loss_function_type CAUCHY, Skala in Sigma) und gibt das
Modell im System der Prioren zurueck. Prioren sind KARTESISCH (PosePriorCoordinateSystem.CARTESIAN); WGS84 rechnet nur der DatabaseCache des Mappers nach ENU um - hier
selbst: ENU in Metern um den GPS-Median (seiten_gps_vereinen.enu).
ABLAUF: 1. Geotags im 150-m-Umkreis; Lot = Mittel der Bild-oben-Richtungen; robuste 2D-Aehnlichkeit Kamerazentren -> GPS (RANSAC, < 12 m) = Startrahmen M0 (Modell -> ENU).
  2. WAECHTER: unabhaengige Geotags (gleicher Geotag < 0,5 m = EIN Beleg, wie fernfotos_pruefen in tools/lage_gps_pruefen.py) unter den stimmigen >= MIN_UNABH, sonst rc 2 und
     das Modell bleibt unveraendert (Martinstor 15-17 Geotags). Je Zusammenhangsstueck (Bilder ueber gemeinsame 3D-Punkte verbunden; vereinte Seiten = getrennte Stuecke)
     mindestens MIN_STUECK stimmige Geotags, sonst werden die Lagen dieses Stuecks festgehalten (keine freie Eichung).
  3. Prioren: Ost/Nord aus dem GPS, Sigma = robuste Streuung der Reste (Rayleigh, begrenzt SIGMA_H_MIN..MAX); Hoehe = eigene Hoehe nach M0 mit SIGMA_Z (Handy-GPS hat keine
     brauchbare Hoehe - ANNAHME, Quelle Hoehe bleibt DGM1/Kamerahoehe in der Ausrichtung). Eine Gruppe aus k gleichen Geotags bekommt k-fache Varianz (zaehlt wie einer).
     Nur die stimmigen Geotags (RANSAC-Inlier) gehen ein, dazu Cauchy - Ausreisser doppelt gebremst. Brennweite/Verzeichnung bleiben fest (Befund 4: frei laufen sie weg).
  4. Ergebnis zurueck ins EINGANGS-System, verankert am Teil mit den meisten Bildern (= Teil A der Vereinigung; Sim3 seiner Kameras neu -> alt): A bleibt, wo er war, die
     anderen Teile ruecken relativ zu A. Festgehaltene Stuecke werden auf ihre Eingangslage zurueckgesetzt. Je Teil die Abbildung alt -> neu (Sim3, 'delta') und die innere
     Verformung (Rest dieser Sim3, relativ zur Teilausdehnung) - damit legt tools/sfm_seiten_modelle.py die dichten Wolken der Teile nach (B_nach_A_neu = delta_B * B_nach_A),
     oder meldet sie als ungueltig (Verformung > VERFORM_MAX).
  5. UEBERNAHME nur, wenn der mittlere Bildfehler nicht schlechter wird (<= vorher * (1 + REPROJ_TOL_REL) + REPROJ_TOL_PX) UND der GPS-Rest sinkt (Median des waagerechten
     Abstands Kamera <-> Geotag, stimmige Geotags der ausgeglichenen Stuecke, vorher unter dem einen Startrahmen M0, nachher im ENU-System des Ausgleichs).
     Sonst rc 3, Modell unveraendert, Ursache im Bericht.
GRENZE (belegt am 22.11.): ohne gemeinsame 3D-Punkte zwischen den Teilen ist die Lage der Teile zueinander danach SO GENAU WIE DAS GPS JE TEIL - Schwabentor Teil 1:
  24 stimmige Geotags eng beisammen, Bootstrap +-3,5 Grad / +-12 % (vereinen_0_1_gps/vereinen.json). Die beobachteten 3 Grad Verdrehung der Teile liegen darin; der Ausgleich
  bringt sie nur zurueck, wenn das GPS je Teil genauer ist. Echte Querbindung braucht Querspuren (Querpaare der Ursprungs-DB: 576 Paare Teil 0/1, ob echt oder Gegenseiten-
  Verwechslung: UNGEPRUEFT) - nicht Teil dieses Werkzeugs.
Ausgaben: <aus>/sparse (nur bei Uebernahme), <aus>/gps_ausgleich.json (ok, urteil, Zahlen, teile{delta, verformung}, code_stand). rc 0 = uebernommen, 2 = zu wenig GPS
  (nichts getan), 3 = abgelehnt (nichts uebernommen), 4 = Eingabe fehlt. Test: tools/test_sfm_gps_ausgleich.py.
Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap). Lizenz: COLMAP/pycolmap BSD-3, numpy."""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from seiten_gps_vereinen import gps_roh, enu, aehnlich2d, basis, lot_aus_bild_achsen, RADIUS_M, GRENZE_M, MIN_GPS
from lage_gps_pruefen import GPS_GLEICH_M

MIN_UNABH = 40           # ANNAHME wie GPS_ANKER_MIN_KAM (sfm_lod2_ausrichten.py): erst ab 40 stimmigen Kameras traegt das GPS die Lage allein. Martinstor (15-17) bleibt unberuehrt.
MIN_STUECK = MIN_GPS     # 15 stimmige Geotags je Zusammenhangsstueck, wie seiten_gps_vereinen je Seitenmodell; darunter: Lagen des Stuecks fest
SIGMA_H_MIN, SIGMA_H_MAX = 2.0, 10.0   # ANNAHME: Handy-GPS 2-10 m (Auftrag: ~4 m); gemessen wird die Streuung der Reste, nur begrenzt
SIGMA_Z = 10.0           # ANNAHME: keine GPS-Hoehe; Hoehe nur schwach an der eigenen Lage gehalten (Eichung), nicht gemessen
REPROJ_TOL_REL, REPROJ_TOL_PX = 0.02, 0.02   # ANNAHME: "nicht schlechter" = hoechstens 2 % + 0,02 px (Rechenrauschen des Ausgleichs)
VERFORM_MAX = 0.002      # ANNAHME: innere Verformung eines Teils > 0,2 % seiner Ausdehnung -> dessen dichte Wolke passt nicht mehr (neu rechnen)


def sim3_fit(X, Y):
    """Y ~ s R X + t (3D, keine Spiegelung) -> 4x4."""
    mx, my = X.mean(0), Y.mean(0); U, S, Vt = np.linalg.svd((Y - my).T @ (X - mx)); D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt)); R = U @ D @ Vt
    s = float((S * np.diag(D)).sum() / max(((X - mx) ** 2).sum(), 1e-18)); M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = my - s * R @ mx; return M


def anwenden(M, X): return X @ M[:3, :3].T + M[:3, 3]


def zerlege(M):
    s = float(np.cbrt(np.linalg.det(M[:3, :3]))); R = M[:3, :3] / s; return s, R, M[:3, 3]


def zu_sim3d(M):
    import pycolmap
    s, R, t = zerlege(M); return pycolmap.Sim3d(s, pycolmap.Rotation3d(R), t)


def drehwinkel(R): return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def stuecke(rec):
    """Zusammenhangsstuecke der registrierten Bilder ueber gemeinsame 3D-Punkte -> {image_id: stueck-nr (0 = groesstes)}."""
    ids = sorted(rec.reg_image_ids()); el = {i: i for i in ids}
    def f(i):
        while el[i] != i: el[i] = el[el[i]]; i = el[i]
        return i
    for p in rec.points3D.values():
        t = [e.image_id for e in p.track.elements if e.image_id in el]
        for j in t[1:]: a, b = f(t[0]), f(j); el[a] = b if a != b else el[a]
    w = {}
    for i in ids: w.setdefault(f(i), []).append(i)
    return {i: k for k, g in enumerate(sorted(w.values(), key=len, reverse=True)) for i in g}


def startrahmen(rec, G, rng):
    """Robuste 2D-Aehnlichkeit Kamerazentren -> GPS um das Lot -> (M0 4x4 Modell -> ENU [Hoehe = Modellhoehe * s], Inlier-Namen, Reste, Lot) oder Grund (str)."""
    ims = [im for im in rec.images.values() if im.has_pose]
    oben = lot_aus_bild_achsen([im.cam_from_world().rotation.matrix() for im in ims]); e1, e2 = basis(oben)   # 22.11.2026: Bild-x-Lot statt Bild-oben-Mittel (kippt um die Kameraneigung)
    k = [im for im in ims if im.name in G and np.linalg.norm(G[im.name]) < RADIUS_M]
    if len(k) < 3: return f"nur {len(k)} Geotags im {RADIUS_M:.0f}-m-Umkreis"
    C = np.array([im.projection_center() for im in k]); X = np.c_[C @ e1, C @ e2]; Y = np.array([G[im.name] for im in k]); inl = None
    for _ in range(1000):
        j = rng.choice(len(k), 2, replace=False)
        if np.linalg.norm(Y[j[0]] - Y[j[1]]) < 5 or np.linalg.norm(X[j[0]] - X[j[1]]) < 1e-9: continue
        s, R, t = aehnlich2d(X[j], Y[j]); w = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1) < GRENZE_M
        if inl is None or w.sum() > inl.sum(): inl = w
    if inl is None or inl.sum() < 3: return "kein GPS-Fit (Kameras/GPS entartet)"
    for _ in range(3):
        s, R, t = aehnlich2d(X[inl], Y[inl]); d = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1); inl = d < GRENZE_M
        if inl.sum() < 3: return "kein GPS-Fit (Kameras/GPS entartet)"
    M = np.eye(4); M[0, :3] = s * (R[0, 0] * e1 + R[0, 1] * e2); M[1, :3] = s * (R[1, 0] * e1 + R[1, 1] * e2); M[2, :3] = s * oben; M[:2, 3] = t
    return M, [im.name for im, w in zip(k, inl) if w], d, oben


def gps_rest(rec, G, namen, M=np.eye(4)):
    """Median des waagerechten Abstands Kamera (nach M) <-> Geotag ueber <namen>."""
    n2i = {im.name: im for im in rec.images.values() if im.has_pose}
    return float(np.median([np.linalg.norm(anwenden(M, n2i[n].projection_center()[None])[0, :2] - G[n]) for n in namen if n in n2i]))


def gruppen(G, namen):
    """{Name: Gruppengroesse} - gleiche Geotags (< GPS_GLEICH_M) bilden EINE Gruppe (eingefrorener Fix = ein Beleg)."""
    sch = {n: tuple(np.round(np.asarray(G[n]) / GPS_GLEICH_M).astype(int)) for n in namen}; z = {}
    for v in sch.values(): z[v] = z.get(v, 0) + 1
    return {n: z[v] for n, v in sch.items()}, len(z)


def ausgleich(rec, G, teile=None, seed=0):
    """Kern ohne Datei-IO. rec = pycolmap.Reconstruction (wird NICHT veraendert), G = {Bildname: (ost, nord)} in Metern, teile = {Bildname: Teil} oder None.
    -> (erg dict, neues Modell oder None). erg['ok'] True nur bei Uebernahme; erg['zu_wenig'] bei fehlendem GPS."""
    import pycolmap
    rng = np.random.default_rng(seed); erg = dict(werkzeug="sfm_gps_ausgleich.py", n_bilder=int(rec.num_reg_images()), n_geotags=sum(1 for im in rec.images.values() if im.has_pose and im.name in G))
    sr = startrahmen(rec, G, rng)
    if isinstance(sr, str): erg.update(ok=False, zu_wenig=True, urteil="zu wenig GPS: " + sr); return erg, None
    M0, inl, d, oben = sr; grp, n_unabh = gruppen(G, inl); erg.update(n_stimmig=len(inl), n_unabhaengig=n_unabh)
    if n_unabh < MIN_UNABH:
        erg.update(ok=False, zu_wenig=True, urteil=f"zu wenig GPS: {n_unabh} unabhaengige stimmige Geotags ({len(inl)} Kameras), noetig {MIN_UNABH} - Modell unveraendert"); return erg, None
    sig = float(np.clip(np.median(d[d < GRENZE_M]) / 1.1774, SIGMA_H_MIN, SIGMA_H_MAX)); erg["sigma_h_m"] = round(sig, 2)   # Median einer Rayleigh-Verteilung = 1,1774 sigma
    W = pycolmap.Reconstruction(rec); W.transform(zu_sim3d(M0))                          # Arbeitskopie im ENU-System (Meter)
    stk = stuecke(W); n2i = {im.name: i for i, im in W.images.items() if im.has_pose}
    je_stk = {}
    for n in inl: je_stk[stk[n2i[n]]] = je_stk.get(stk[n2i[n]], 0) + 1
    fest = sorted({s for s in set(stk.values()) if je_stk.get(s, 0) < MIN_STUECK})
    erg["stuecke"] = dict(anzahl=len(set(stk.values())), geotags_je_stueck={str(k): v for k, v in sorted(je_stk.items())}, festgehalten=fest)
    if len(fest) == len(set(stk.values())): erg.update(ok=False, zu_wenig=True, urteil=f"kein Zusammenhangsstueck mit {MIN_STUECK} stimmigen Geotags - Modell unveraendert"); return erg, None
    inl_frei = [n for n in inl if stk[n2i[n]] not in fest]                              # GPS-Rest nur ueber die ausgeglichenen Stuecke (vorher/nachher gleiche Auswahl)
    W.update_point_3d_errors(); reproj0 = float(W.compute_mean_reprojection_error()); rest0 = gps_rest(W, G, inl_frei)   # Fehler der Punkte frisch (gespeicherte koennen alt sein)
    priors = []
    for n in inl:
        im = W.images[n2i[n]]; z = float(im.projection_center()[2]); k = grp[n]
        priors.append(pycolmap.PosePrior(corr_data_id=im.data_id, position=np.array([G[n][0], G[n][1], z], float), position_covariance=np.diag([k * sig ** 2, k * sig ** 2, k * SIGMA_Z ** 2]),
                                         coordinate_system=pycolmap.PosePriorCoordinateSystem.CARTESIAN))
    bo = pycolmap.BundleAdjustmentOptions(); bo.refine_focal_length = False; bo.refine_extra_params = False; bo.refine_principal_point = False; bo.refine_sensor_from_rig = False; bo.print_summary = False
    po = pycolmap.PosePriorBundleAdjustmentOptions(); po.prior_position_fallback_stddev = sig; po.alignment_ransac.max_error = GRENZE_M
    po.ceres.prior_position_loss_function_type = pycolmap.LossFunctionType.CAUCHY                                   # Skala bleibt 2,795 Sigma (95 % Chi-Quadrat, 3 Freiheitsgrade)
    cf = pycolmap.BundleAdjustmentConfig()
    for i, im in W.images.items():
        if not im.has_pose: continue
        cf.add_image(i)
        if stk[i] in fest: cf.set_constant_rig_from_world_pose(im.frame_id)
    try:
        sm = pycolmap.create_pose_prior_bundle_adjuster(bo, po, cf, priors, W).solve()
        if sm is not None and hasattr(sm, "is_solution_usable") and not sm.is_solution_usable(): raise RuntimeError("Loesung nicht verwendbar")
    except Exception as ex:
        erg.update(ok=False, urteil=f"Ausgleich gescheitert ({type(ex).__name__}: {ex}) - Modell unveraendert"); return erg, None
    # Ausgleicher gibt das Modell im System der Prioren (ENU) zurueck -> Rest dort messen, dann zurueck ins Eingangssystem
    rest1 = gps_rest(W, G, inl_frei)
    alt = {im.name: im.projection_center() for im in rec.images.values() if im.has_pose}
    tz = {}
    for n in alt: tz.setdefault((teile or {}).get(n, "alle"), []).append(n)
    # zurueck ins Eingangssystem, und zwar so, dass der ANKER-Teil (meiste Bilder = Teil A der Vereinigung) bleibt, wo er war: M0 ist ein Kompromiss ueber alle Teile
    # (Test: mit M0^-1 allein wanderte A um 3 Grad x1,03) - die Folgestufen (dichte Wolke von A, Verknuepfungen) setzen A unveraendert voraus.
    anker = max(tz, key=lambda t: len(tz[t])); erg["anker_teil"] = str(anker); n2w = {im.name: im for im in W.images.values() if im.has_pose}
    W.transform(zu_sim3d(sim3_fit(np.array([n2w[n].projection_center() for n in tz[anker]]), np.array([alt[n] for n in tz[anker]]))))
    if fest:                                                                             # festgehaltene Stuecke (ohne eigenes GPS): Lage zum Anker wie im Eingang
        for i, im in W.images.items():                                                   # (sie haben keine gemeinsamen Punkte mit den anderen -> Zuruecksetzen ist widerspruchsfrei)
            if im.has_pose and stk[i] in fest: W.frames[im.frame_id].rig_from_world = rec.frames[rec.images[i].frame_id].rig_from_world
        for pid, p in W.points3D.items():
            if stk.get(p.track.elements[0].image_id) in fest and pid in rec.points3D: p.xyz = rec.points3D[pid].xyz
    W.update_point_3d_errors(); reproj1 = float(W.compute_mean_reprojection_error())
    erg.update(reproj_vorher_px=round(reproj0, 4), reproj_nachher_px=round(reproj1, 4), gps_rest_vorher_m=round(rest0, 3), gps_rest_nachher_m=round(rest1, 3))
    neu = {im.name: im.projection_center() for im in W.images.values() if im.has_pose}
    erg["teile"] = {}; s0 = zerlege(M0)[0]
    for t, ns in sorted(tz.items(), key=lambda x: str(x[0])):
        if len(ns) < 3: continue
        X = np.array([alt[n] for n in ns]); Y = np.array([neu[n] for n in ns]); D = sim3_fit(X, Y); r = np.linalg.norm(anwenden(D, X) - Y, axis=1)
        aus = float(np.linalg.norm(np.percentile(X, 95, 0) - np.percentile(X, 5, 0))); s, R, _ = zerlege(D)
        erg["teile"][str(t)] = dict(bilder=len(ns), delta=D.tolist(), drehung_grad=round(drehwinkel(R), 3), massstab=round(s, 5), verformung_median_m=round(float(np.median(r)) * s0, 4),
                                    verformung_rel=round(float(np.median(r)) / max(aus, 1e-12), 6), dicht_gueltig=bool(float(np.median(r)) / max(aus, 1e-12) <= VERFORM_MAX))
    gr = []
    if reproj1 > reproj0 * (1 + REPROJ_TOL_REL) + REPROJ_TOL_PX: gr.append(f"Bildfehler schlechter ({reproj0:.3f} -> {reproj1:.3f} px)")
    if not rest1 < rest0: gr.append(f"GPS-Rest sinkt nicht ({rest0:.2f} -> {rest1:.2f} m)")
    if gr: erg.update(ok=False, urteil="ABGELEHNT: " + "; ".join(gr) + " - Modell unveraendert"); return erg, None
    erg.update(ok=True, urteil=f"uebernommen: GPS-Rest {rest0:.2f} -> {rest1:.2f} m, Bildfehler {reproj0:.3f} -> {reproj1:.3f} px, {n_unabh} unabhaengige Geotags, Sigma {sig:.1f} m")
    return erg, W


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("modell"); ap.add_argument("--bilder", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--teile", help="JSON {Bildname: Teil} (fuer delta/Verformung je Teil)"); a = ap.parse_args(argv)
    import pycolmap
    from code_stand import code_stand
    os.makedirs(a.aus, exist_ok=True); jp = os.path.join(a.aus, "gps_ausgleich.json")
    if not os.path.isfile(os.path.join(a.modell, "images.bin")): json.dump(dict(ok=False, urteil=f"Modell fehlt: {a.modell}"), open(jp, "w")); print("FEHLER GPS-AUSGLEICH: Modell fehlt"); return 4
    rec = pycolmap.Reconstruction(a.modell); namen = [im.name for im in rec.images.values() if im.has_pose]
    roh = gps_roh(a.bilder, namen) if os.path.isdir(a.bilder) else {}
    if len(roh) < 3: erg, W = dict(ok=False, zu_wenig=True, urteil=f"zu wenig GPS: {len(roh)} Fotos mit EXIF-GPS"), None
    else:
        la0, lo0 = np.median([v[0] for v in roh.values()]), np.median([v[1] for v in roh.values()])
        erg, W = ausgleich(rec, enu(roh, la0, lo0), json.load(open(a.teile)) if a.teile else None); erg["ursprung_wgs84"] = [float(la0), float(lo0)]
    erg.update(modell=os.path.abspath(a.modell), code_stand=code_stand("sfm_gps_ausgleich.py", wurzel=T))
    if W is not None:
        sp = os.path.join(a.aus, "sparse"); os.makedirs(sp, exist_ok=True); W.write(sp); erg["sparse"] = sp
    json.dump(erg, open(jp, "w"), indent=1, ensure_ascii=False)
    print(("GPS-AUSGLEICH: " if erg["ok"] else "GPS-AUSGLEICH NICHT UEBERNOMMEN: ") + erg["urteil"])
    return 0 if erg["ok"] else (2 if erg.get("zu_wenig") else 3)


if __name__ == "__main__": sys.exit(main())
