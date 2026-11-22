#!/usr/bin/env python3
"""seiten_gps_vereinen.py <modell_a> <modell_b> --bilder <fotoordner> --aus <ordner> [--dicht-a fused.ply --dicht-b fused.ply]

SEITEN UEBER DAS FOTO-GPS VEREINEN (22.11.2026, Nulllauf schwabentor-1122). Rueckfall fuer tools/sfm_seiten_modelle.py, wenn tools/seiten_vereinen.py zwei Seitenmodelle
nicht zusammenlegen kann. seiten_vereinen ist am Martinstor gebaut: es KLAPPT aehnliche Waende aufeinander (Massstab) und sucht eine Turmspitze/Helmstange (Achse). Am
Schwabentor sind die Seiten verschieden (die Seitenerkennung trennt sie zu Recht: Gruppe 0 GPS 355 Grad, Gruppe 1 GPS 146 Grad um die Turmmitte), die Klappung lieferte
Massstab B->A 0,012 (Unsinn) -> "Turmhoehen 99,6 % verschieden" -> "keine hoechsten Bauteile - Achse unbestimmt" -> Teil A allein (Kamerakranz-Luecke 173 Grad), die
Ausrichtung an LoD2 drehte die einseitige Wolke um 20 Grad, alle Lage-Tore fielen.
Verfahren ohne Vorwissen (nur EXIF-GPS der Fotos, kein LoD2): je Modell Lot aus den Kameras (Bild-oben-Richtung), Kamerazentren waagerecht per robuster 2D-Aehnlichkeit
(RANSAC, keine Spiegelung) auf das Foto-GPS (gemeinsamer ENU-Ursprung beider Modelle) -> Abbildung Modell -> ENU in Metern; Hoehe: Boden aus der dichten Wolke unter den
Kameras (sonst Kamerahoehe 1,6 m, ANNAHME). B_nach_A = (A -> ENU)^-1 * (B -> ENU). Genauigkeit per Bootstrap (Drehung, Massstab) - zu ungenau -> abgelehnt.
Ausgabe <aus>/vereinen.json im Format von seiten_vereinen (ok, urteil, B_nach_A, pruefung) mit art 'gps'. rc 0 = vereint, 3 = abgelehnt (GPS zu ungenau/uneinig),
2 = zu wenig GPS in einem der Modelle. GRENZEN: Handy-GPS liegt 5-15 m daneben - die Lage von B ist so gut wie der Mittelwert vieler Fotos (Bootstrap im Bericht);
Seitenverklebung prueft danach das Blick-Tor (tools/seiten_blick_tor.py) und das GPS-Seiten-Tor am vereinten Modell (macht sfm_seiten_modelle.py).
Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap)."""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
MIN_GPS = 15            # ANNAHME: Mindestzahl stimmiger GPS-Kameras je Modell (wie der GPS-Startkandidat in sfm_lod2_ausrichten.py)
MAX_REST_M = 8.0        # ANNAHME: Median-Rest der stimmigen GPS-Kameras je Modell (Handy-GPS ~5 m; Schwabentor Teil 0: 5,3 m)
MAX_AUSREISSER = 0.30   # ANNAHME: hoechstens 30 % der GPS-Kameras eines Modells > GRENZE_M neben dem Fit
GRENZE_M = 12.0         # wie tools/gps_seiten_pruefen.py
MAX_DREH_SD = 6.0       # ANNAHME: Bootstrap-Streuung der Drehung B gegen A (Grad); groesser = Lage von B nicht belegt
MAX_MASS_SD = 0.15      # ANNAHME: Bootstrap-Streuung des Massstabsverhaeltnisses B/A (relativ). Schwabentor-1122 Teil 1: 11,9 % (24 GPS-Kameras eng beisammen) - ueber 5 % meldet
                        # sfm_seiten_modelle.py 'ACHTUNG Massstab nur auf +-x % belegt'. Andere Massstabsquellen am 22.11. geprueft und verworfen: Kamerahoehe ueber dem Wolkenboden
                        # (Teil 0: Viertelwerte -0,24 / 1,97 m - zu verrauscht), Turmspitze (Teil 1 sieht die Spitze nicht: 24 statt 37 m), ICP der dichten Wolken (lief 19 Grad weg, Massstab 0,83)
RADIUS_M = 150.0        # GPS-Fotos weiter als 150 m vom Median = Fernaufnahmen/Ortsmarken, nicht verwenden (wie gps_seiten_pruefen)


ZEITEN = {}   # Bildname -> EXIF-Aufnahmezeit (gps_roh fuellt sie; Sitzungen der ehrlichen GPS-Unsicherheit, tools/gps_unsicherheit.py)


def gps_roh(ordner, namen):
    """{Bildname: (breite, laenge)} aus dem EXIF (Bilder ohne GPS fehlen). Nebenbei: Aufnahmezeiten in ZEITEN."""
    from PIL import Image
    import gps_unsicherheit as GU
    roh = {}
    for n in namen:
        try:
            e = Image.open(os.path.join(ordner, n)).getexif().get_ifd(0x8825)
            if not e or 2 not in e or 4 not in e: continue
            gr = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            la = gr(e[2]) * (-1 if e.get(1) == "S" else 1); lo = gr(e[4]) * (-1 if e.get(3) == "W" else 1)
            if abs(la) > 0.1 and np.isfinite(la) and np.isfinite(lo): roh[n] = (la, lo); ZEITEN[n] = GU.exif_zeit(os.path.join(ordner, n))
        except Exception: continue
    return roh


def enu(roh, la0, lo0):
    return {n: np.array([(lo - lo0) * 111320.0 * np.cos(np.radians(la0)), (la - la0) * 110540.0]) for n, (la, lo) in roh.items()}


def aehnlich2d(X, Y):
    """Y ~ s R X + t (2D, keine Spiegelung)."""
    mx, my = X.mean(0), Y.mean(0); Xc, Yc = X - mx, Y - my; U, S, Vt = np.linalg.svd(Yc.T @ Xc); D = np.eye(2); D[1, 1] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt; s = float((S * np.diag(D)).sum() / max((Xc ** 2).sum(), 1e-18)); return s, R, my - s * R @ mx


def winkel(R):
    return float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))


LOT_X_GRAD = 15.0       # wie sfm_lod2_ausrichten.py (Lot aus Kamerablick): Bild-x-Achse hoechstens 15 Grad neben der Waagerechten = Kamera stuetzt das Lot


def lot_aus_bild_achsen(Rs):
    """Lot aus den Kameradrehungen (cam_from_world, je 3x3): Richtung, auf der die Bild-x-Achsen moeglichst senkrecht stehen (kleinster Singulaervektor, gerollte Bilder
    iterativ raus), Vorzeichen aus dem Mittel der Bild-oben-Richtungen.
    22.11.2026 (Nulllauf schwabentor-1122f, Sued-'Doppelflaeche' 2,5 m): vorher war das Lot das MITTEL der Bild-oben-Richtungen. Wer einen 50-m-Turm fotografiert, neigt die
    Kamera nach oben (Median +16/+18 Grad je Seite); die Bild-oben-Richtung kippt um genau diese Neigung vom Lot weg, auf gegenueberliegenden Seiten in entgegengesetzte
    Richtung. Gemessen: Bild-oben-Lot 12,8 Grad (Teil 0) und 16,3 Grad (Teil 1) neben dem Bild-x-Lot -> Teil 1 gegen Teil 0 ~28 Grad gekippt, die Suedwand stand im
    vereinten Modell 23 Grad schraeg (Median-x von -8,7 m in 1 m Hoehe bis -3,6 m in 13 m Hoehe) = das 'zwei Streifen'-Bild. Die Bild-x-Achse bleibt beim Neigen
    waagerecht (Fotos werden nicht gerollt) - so rechnet tools/sfm_lod2_ausrichten.py das Lot seit 19.11. Rueckfall (< 8 Kameras stuetzen es): Mittel der Bild-oben-Richtungen.
    22.11.2026 EIN LOT (Lage-Pruefstand): seit heute rechnet auch die Ausrichtung (sfm_lod2_ausrichten) ihr Netzsystem mit DIESER Funktion (lot_info), Begruendung dort
    und in lot_info. Vorzeichen jetzt per MEDIAN der Bild-oben-Komponente (wie bisher die Ausrichtung) statt per Mittelwert: wenige kopfstehende/gedrehte Bilder kippen den
    Median nicht (auf 1120/1122/Kaufhaus gk/gk2/Martinstor gk3 beide gleich)."""
    return lot_info(Rs)["oben"]


def lot_info(Rs):
    """DAS Lot aus den Kameradrehungen (cam_from_world, je 3x3) mit Begleitwerten -> dict(oben, stuetzend (Anteil der Kameras mit Bild-x < LOT_X_GRAD neben der Waagerechten),
    n, quelle 'bildachsen' | 'bild_oben_mittel' (Rueckfall)).
    WARUM Bild-x-Achsen und nicht die Normale der Kameraebene (Entscheid 22.11.2026 an Daten; tools/versuche/lage_eine_funktion/lot_vergleich.py, lot_wand.py):
      Bezug 1 = Hochachse des LoD2+DGM1-Feinfits der geschriebenen Ausrichtung (Kippung frei), Bezug 2 = Lot aus den Wandnormalen der dichten Wolke (unabhaengig von LoD2).
      Winkel Kameraebene / Bild-x-Achsen gegen Bezug 1 und 2:  schwabentor-1120 (gute Lage) 6,6/5,9 gegen 4,4/4,1 Grad;  schwabentor-1122 2,9/1,6 gegen 4,6/3,3;
      kaufhaus_gk2 0,7/1,9 gegen 1,9/0,9;  martinstor_gk3 (Drohnenclips) 68/85 gegen 16/1,8.  Beide Kameralote liegen 1-6 Grad daneben, die Kameraebene kann aber
      KATASTROPHAL falsch sein (Drohne, Hoehenunterschiede, Teilmodelle einer Wand: Kameras auf einer Linie -> Ebenennormale unbestimmt); die Bild-x-Achsen nie.
      Am GPS gemessen (Fixture test_gps_eine_quelle_fixture.json + kameras.json 1120): GPS-Fit der Ausrichtung im Kameraebenen-Rahmen 105 von 174 Fotos, KEIN
      Fernfoto, +-11,2 Grad 'legt nicht fest' (18 von 20 Zufallsstarts), im Bild-x-Rahmen 125 von 174, 10 Fernfotos, +-1,0 Grad 'kann ankern' (20 von 20) = genau das
      GPS-Tor auf der fertigen Lage. Die 63 m hoch stehenden Fernkameras machen den RANSAC-Konsens empfindlich fuer 2,3 Grad Lotfehler.
      Feiner als ~2-4 Grad ist kein Kameralot: das richtet der LoD2/DGM1-Feinfit (Kippung frei) bzw. nach der dichten Wolke das Wandnormalen-Lot."""
    Rs = np.asarray(Rs, float).reshape(-1, 3, 3); ob = np.mean(-Rs[:, 1, :], 0); ob /= max(np.linalg.norm(ob), 1e-12)
    X = Rs[:, 0, :]; inn = np.ones(len(X), bool); up = None
    for _ in range(5):
        if inn.sum() < 8: break
        up = np.linalg.svd(X[inn], full_matrices=False)[2][2]; inn = np.abs(X @ up) < np.sin(np.radians(LOT_X_GRAD))
    if up is None or inn.sum() < 8: return dict(oben=ob, stuetzend=float(inn.mean()) if len(X) else 0.0, n=int(len(X)), quelle="bild_oben_mittel")
    up = up if np.median(-Rs[inn, 1, :] @ up) > 0 else -up                                      # Bild-y zeigt nach unten -> Bild-oben = -y
    return dict(oben=up, stuetzend=float(inn.mean()), n=int(len(X)), quelle="bildachsen")


def kameras(modell):
    """-> (Namen, Zentren n x 3, Lot oben) eines COLMAP-Modells; Lot aus den Bild-x-Achsen (lot_aus_bild_achsen: Strassenfotos werden nicht gerollt, aber geneigt)."""
    import pycolmap
    r = pycolmap.Reconstruction(modell); ims = [im for im in r.images.values() if im.has_pose]
    oben = lot_aus_bild_achsen([im.cam_from_world().rotation.matrix() for im in ims])
    return [im.name for im in ims], np.array([im.projection_center() for im in ims]), oben


def basis(oben):
    e1 = np.cross(oben, [1.0, 0, 0] if abs(oben[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(oben, e1); return e1, e2


def rahmen(namen, C, oben, G, boden=None, rng=None, grenze=GRENZE_M, kamerahoehe=1.6):
    """Abbildung Modell -> ENU (Meter, z = Hoehe ueber dem Boden der Kameras) aus den GPS-Lagen G {Name: (ost, nord)}. boden = Punkte der dichten Wolke (n x 3) oder None.
    -> dict(n_gps, inlier, rest_median_m, ausreisser, drehung_grad, massstab, dreh_sd_grad, mass_sd_rel, M (4x4), hoehe_aus) oder dict(n_gps, grund)."""
    rng = rng or np.random.default_rng(0)
    k = [i for i, n in enumerate(namen) if n in G and np.linalg.norm(G[n]) < RADIUS_M]
    if len(k) < MIN_GPS: return dict(n_gps=len(k), grund=f"nur {len(k)} GPS-Kameras im {RADIUS_M:.0f}-m-Umkreis (noetig {MIN_GPS})")
    # Lot = Bild-oben-Richtung der Kameras: eindeutig im Vorzeichen (niemand fotografiert kopfueber) - anders als das Lot aus der Kameraebene (Kaufhaus 15.11.: kopf). Kein Spiegel-Fit:
    # bei einem kleinen Kamerabogen mit Handy-GPS passt der gespiegelte Fit fast so gut (Test 22.11.) und wuerde sonst falsch gewaehlt.
    Y = np.array([G[namen[i]] for i in k]); ob = oben; e1, e2 = basis(ob); X = np.array([[C[i] @ e1, C[i] @ e2] for i in k]); inl = None
    for _ in range(500):                                                           # RANSAC: zwei Kameras bestimmen eine 2D-Aehnlichkeit
        j = rng.choice(len(k), 2, replace=False)
        if np.linalg.norm(Y[j[0]] - Y[j[1]]) < 5 or np.linalg.norm(X[j[0]] - X[j[1]]) < 1e-9: continue
        s, R, t = aehnlich2d(X[j], Y[j]); w = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1) < grenze
        if inl is None or w.sum() > inl.sum(): inl = w
    if inl is None or inl.sum() < 3: return dict(n_gps=len(k), grund="kein GPS-Fit (Kameras/GPS entartet)")
    for _ in range(3):
        s, R, t = aehnlich2d(X[inl], Y[inl]); d = np.linalg.norm((s * (R @ X.T)).T + t - Y, axis=1); inl = d < grenze
        if inl.sum() < 3: return dict(n_gps=len(k), grund="kein GPS-Fit (Kameras/GPS entartet)")
    best = dict(d=d, rest=float(np.median(d[inl])))
    ii = np.flatnonzero(inl); dr, ms = [], []
    for _ in range(300):                                                           # Bootstrap ueber die stimmigen Kameras: Genauigkeit von Drehung und Massstab
        b = rng.choice(ii, len(ii)); s_, R_, _ = aehnlich2d(X[b], Y[b]); dr.append(winkel(R_)); ms.append(s_)
    dr = (np.array(dr) - winkel(R) + 180.0) % 360.0 - 180.0
    h = C @ ob; hk = h[[k[i] for i in ii]]; hoehe_aus = f"Kamerahoehe {kamerahoehe} m (ANNAHME)"; z0 = float(np.median(hk)) - kamerahoehe / s
    if boden is not None and len(boden) > 1000:                                    # Boden unter den GPS-Kameras aus der dichten Wolke: 3-%-Hoehe der Punkte im 5-m-Umkreis
        try:
            from scipy.spatial import cKDTree
            B2 = np.c_[boden @ e1, boden @ e2]; hb = boden @ ob; baum = cKDTree(B2); z_ = []
            for i in ii:
                nb = baum.query_ball_point(X[i], 5.0 / s)
                if len(nb) >= 30: z_.append(float(np.percentile(hb[nb], 3)))
            if len(z_) >= 5: z0 = float(np.median(z_)); hoehe_aus = f"Boden der dichten Wolke unter {len(z_)} GPS-Kameras"
        except Exception as ex: hoehe_aus += f" (Boden aus der Wolke nicht moeglich: {type(ex).__name__})"
    M = np.eye(4); M[0, :3] = s * (R[0, 0] * e1 + R[0, 1] * e2); M[1, :3] = s * (R[1, 0] * e1 + R[1, 1] * e2); M[2, :3] = s * ob; M[:2, 3] = t; M[2, 3] = -s * z0
    # 22.11.2026 EHRLICH (tools/gps_unsicherheit.py, dasselbe Mass wie GPS-Tor und Ausrichtung): Bootstrap misst nur den Zufall; der gemeinsame Fehler einer Fotositzung
    # wirkt mit Sigma/Hebel (schwabentor-1122 Teil 1: 23 Geotags eng an der Suedwand -> Hebel klein). NUR BERICHT (dreh_sd_ehrlich_grad, mass_sd_ehrlich_rel) + Kasten in
    # seiten_lod2_je_teil; die Annahme-Regeln von b_nach_a bleiben unveraendert (Vorschlag im Logbuch: Teil nur einsetzen, wenn belegt).
    import gps_unsicherheit as GU
    sd_b, sm_b = float(np.std(dr)), float(np.std(ms) / s)
    sy = GU.systematik(Y, GU.gruppen(Y, [ZEITEN.get(namen[i]) for i in k], mitte=np.median(Y[inl], 0)), inl, M=X); sd_e, sm_e = GU.gesamt(sd_b, sm_b, sy)
    return dict(n_gps=len(k), inlier=int(inl.sum()), rest_median_m=round(best["rest"], 2), ausreisser=round(float((best["d"] > grenze).mean()), 3), drehung_grad=round(winkel(R), 2),
                massstab=s, dreh_sd_grad=round(sd_b, 2), mass_sd_rel=round(sm_b, 4), dreh_sd_ehrlich_grad=round(sd_e, 2), mass_sd_ehrlich_rel=round(sm_e, 4),
                systematik=dict(dreh_sd_grad=round(sy["dreh_sd_grad"], 2), mass_sd_rel=round(sy["mass_sd_rel"], 4), n_gruppen=sy["n_gruppen"], n_eff=sy["n_eff"], sigma_m=sy["sigma_m"],
                                hebel_m=[g_["hebel_m"] for g_ in sy["gruppen"]]), hoehe_aus=hoehe_aus, M=M)


def guete(F):
    """Gruende, aus denen ein Modell-Rahmen NICHT als Lagebeleg taugt (leer = taugt)."""
    if "grund" in F: return [F["grund"]]
    g = []
    if F["inlier"] < MIN_GPS: g.append(f"nur {F['inlier']} stimmige GPS-Kameras (noetig {MIN_GPS})")
    if F["rest_median_m"] > MAX_REST_M: g.append(f"GPS-Rest Median {F['rest_median_m']:.1f} m (Grenze {MAX_REST_M:.0f})")
    if F["ausreisser"] > MAX_AUSREISSER: g.append(f"{100 * F['ausreisser']:.0f} % der GPS-Kameras > {GRENZE_M:.0f} m neben dem Fit (Grenze {100 * MAX_AUSREISSER:.0f} %)")
    return g


def b_nach_a(A, B, G, boden_a=None, boden_b=None):
    """A, B = kameras(...)-Tupel, G = GPS-ENU {Name: (ost, nord)} mit EINEM Ursprung fuer beide. -> Ergebnis-dict wie seiten_vereinen (ok, urteil, B_nach_A, pruefung)."""
    FA = rahmen(*A, G, boden_a); FB = rahmen(*B, G, boden_b); erg = dict(art="gps", rahmen_a={k: v for k, v in FA.items() if k != "M"}, rahmen_b={k: v for k, v in FB.items() if k != "M"})
    ga, gb = guete(FA), guete(FB)
    if np.linalg.det(FA["M"][:3, :3] if "M" in FA else np.eye(3)) <= 0 or np.linalg.det(FB["M"][:3, :3] if "M" in FB else np.eye(3)) <= 0:
        erg.update(ok=False, urteil="Abbildung Modell -> GPS ist keine Aehnlichkeit (Spiegelung)"); return erg
    if "grund" in FA or "grund" in FB:
        erg.update(ok=False, zu_wenig=True, urteil="zu wenig GPS: " + "; ".join([f"A: {x}" for x in ga] + [f"B: {x}" for x in gb])); return erg
    if ga or gb: erg.update(ok=False, urteil="GPS taugt nicht als Lagebeleg: " + "; ".join([f"A: {x}" for x in ga] + [f"B: {x}" for x in gb])); return erg
    M = np.linalg.inv(FA["M"]) @ FB["M"]; dsd = float(np.hypot(FA["dreh_sd_grad"], FB["dreh_sd_grad"])); msd = float(np.hypot(FA["mass_sd_rel"], FB["mass_sd_rel"]))
    pr = dict(dreh_sd_grad=round(dsd, 2), mass_sd_rel=round(msd, 4), massstab_b_nach_a=float(FB["massstab"] / FA["massstab"]))
    dse = float(np.hypot(FA.get("dreh_sd_ehrlich_grad", FA["dreh_sd_grad"]), FB.get("dreh_sd_ehrlich_grad", FB["dreh_sd_grad"]))); mse = float(np.hypot(FA.get("mass_sd_ehrlich_rel", FA["mass_sd_rel"]), FB.get("mass_sd_ehrlich_rel", FB["mass_sd_rel"])))
    pr.update(dreh_sd_ehrlich_grad=round(dse, 2), mass_sd_ehrlich_rel=round(mse, 4), lage_b_belegt=bool(dse <= MAX_DREH_SD and mse <= MAX_MASS_SD),
              hinweis_ehrlich="Zufall + systematischer Sitzungsfehler (gps_unsicherheit.py); nur Bericht - ist lage_b_belegt false, legt das GPS die Lage von B NICHT fest (Fotoluecke melden)")
    gr = []
    if dsd > MAX_DREH_SD: gr.append(f"Drehung von B gegen A nur auf +-{dsd:.1f} Grad belegt (Grenze {MAX_DREH_SD:.0f})")
    if msd > MAX_MASS_SD: gr.append(f"Massstab B/A nur auf +-{100 * msd:.0f} % belegt (Grenze {100 * MAX_MASS_SD:.0f} %)")
    erg.update(B_nach_A=M.tolist(), pruefung=pr, ok=not gr, urteil=("vereint ueber das Foto-GPS (Drehung +-%.1f Grad, Massstab +-%.0f %%)" % (dsd, 100 * msd)) if not gr else "; ".join(gr))
    return erg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--bilder", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--dicht-a"); ap.add_argument("--dicht-b"); a = ap.parse_args(argv); os.makedirs(a.aus, exist_ok=True); vj = os.path.join(a.aus, "vereinen.json")
    A = kameras(a.a); B = kameras(a.b); roh = gps_roh(a.bilder, A[0] + B[0]) if os.path.isdir(a.bilder) else {}
    if len(roh) < 2 * MIN_GPS:
        erg = dict(art="gps", ok=False, zu_wenig=True, urteil=f"zu wenig GPS: {len(roh)} Fotos mit EXIF-GPS in beiden Modellen zusammen (noetig {2 * MIN_GPS})")
    else:
        la0, lo0 = np.median([v[0] for v in roh.values()]), np.median([v[1] for v in roh.values()]); G = enu(roh, la0, lo0)
        sys.path.insert(0, T); from seiten_vereinen import ply_punkte
        da = ply_punkte(a.dicht_a) if a.dicht_a and os.path.isfile(a.dicht_a) else None; db = ply_punkte(a.dicht_b) if a.dicht_b and os.path.isfile(a.dicht_b) else None
        erg = b_nach_a(A, B, G, da, db); erg["ursprung_wgs84"] = [float(la0), float(lo0)]
    erg.update(modell_a=os.path.abspath(a.a), modell_b=os.path.abspath(a.b)); json.dump(erg, open(vj, "w"), indent=1)
    for k in ("rahmen_a", "rahmen_b"):
        f = erg.get(k) or {}
        if "inlier" in f: print(f"{k[-1].upper()}: {f['inlier']} von {f['n_gps']} GPS-Kameras stimmig, Rest Median {f['rest_median_m']} m, Drehung {f['drehung_grad']} +- {f['dreh_sd_grad']} Grad, Massstab +-{100 * f['mass_sd_rel']:.1f} %, Hoehe: {f['hoehe_aus']}")
    print(("SEITEN VEREINT (GPS): " if erg["ok"] else "WARNUNG SEITEN NICHT VEREINT (GPS): ") + erg["urteil"])
    return 0 if erg["ok"] else (2 if erg.get("zu_wenig") else 3)


if __name__ == "__main__": sys.exit(main())
