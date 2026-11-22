#!/usr/bin/env python3
"""seiten_querspur_binden.py <modell_a> <modell_b> <ursprungs-db> --gps <vereinen.json> --aus <ordner> [--dicht-a fused.ply --dicht-b fused.ply]

TEILE UEBER QUERSPUREN BINDEN (22.11.2026, Nulllauf schwabentor-1122f: das aus zwei Seitenteilen per Foto-GPS vereinte Modell ist in sich versetzt - Ostwand 1-2,5 m
ausserhalb LoD2, Westwand doppelt (~3 m dick), Treppentuermchen 4-5 m neben LoD2. Ursache: Teil 1 hat nur 24 stimmige Geotags, Bootstrap +-3,5 Grad / +-11,9 %
(vereinen_0_1_gps/vereinen.json) - das GPS legt die Teile nicht genauer zueinander, auch kein GPS-Prior-Ausgleich (tools/sfm_gps_ausgleich.py, GRENZE im Kopf).
Es fehlte eine GEOMETRISCHE Bindung: in der Ursprungs-DB gibt es 576 Querpaare Teil 0/1 mit >= 15 Inliern.
VERFAHREN (nach seiten_gps_vereinen, vor dem Zusammenlegen in tools/sfm_seiten_modelle.py):
  1. Querpaare der URSPRUNGS-Datenbank (two_view_geometries, >= MIN_INLIER_PAAR; nur lesend) zwischen Bildern von A und B. BLICK-FILTER: in der GPS-Lage von B duerfen die
     zwei Kameras eines Paares im Grundriss hoechstens MAX_AZIMUT_GRAD auseinander blicken (Register NICHTS_GEBRACHT: Paare gegenueberliegender Turmseiten - Gegenseiten-
     Verwechslung - blicken ~180 Grad auseinander; uebernommen werden nur Paare bis ~110 Grad).
  2. 2D-Zuordnung -> je Bild der bereits triangulierte 3D-Punkt des EIGENEN Teilmodells -> 3D-3D-Zuordnung (je B-Punkt der haeufigste A-Punkt, wie seiten_vereinen.punktpaare).
  3. Robuste Sim3 B -> A per RANSAC (drei Punkte, Umeyama mit det > 0: KEINE Spiegelung, KEINE Klappung). GPS = unabhaengiges VETO, nicht gemittelt: gezaehlt werden nur
     Hypothesen im GPS-KORRIDOR um B_nach_A der GPS-Vereinigung (Drehung um das Lot <= K_SIGMA x Bootstrap-Streuung, Massstab <= K_SIGMA x Bootstrap-Streuung, Kippung
     <= KIPP_MAX_GRAD, Lage der B-Kameras <= K_SIGMA x Lage-Sigma). Eine Gegenseiten-Verwechslung liegt ~180 Grad bzw. eine Turmbreite daneben und faellt durch.
     Die beste Hypothese OHNE Korridor wird mitgemeldet (zeigt, ob eine starke Fremdlage in den Paaren steckt).
  4. GUETE (jede einzeln, 'ok' nur wenn alle bestehen): Paare nach Blick-Filter, Inlier-Zahl und -Anteil, Zahl der Bildpaare, die Inlier tragen, raeumliche Ausdehnung
     der Inlier (zweitgroesste Hauptachse >= MIN_AUSDEHNUNG_M: kein Fleck, keine Linie; Ebenheit wird gemeldet - eine Ebene legt eine Sim3 fest), Bootstrap-Streuung der
     Querspur-Sim3 hoechstens MAX_SD_ANTEIL der GPS-Streuung (sonst bringt die Bindung nichts), Doppelwand danach nicht groesser.
  5. PRUEFMASS DOPPELWAND (ins JSON): Abstand der Teil-Wolken an gemeinsam gesehenen Flaechen - A-Punkte (dichte Wolke, sonst duenne) im Umkreis UEBERLAPP_M um die
     A-Seite der Inlier, je Punkt Abstand zum naechsten B-Punkt; Median/P90 in Metern VOR (GPS-Lage) und NACH (Querspur-Lage), gleiche Punktauswahl.
Ausgabe <aus>/querspur.json (ok, urteil, B_nach_A nur bei ok, B_nach_A_gps, pruefung{...}, doppelwand{vor, nach}). rc 0 = gebunden, 2 = zu wenig/keine Eingabe (nichts getan),
  3 = abgelehnt (nichts uebernehmen). Bei rc 2/3 bleibt die GPS-Lage.
NUR AUF DEM GPS-WEG: die Klappung (seiten_vereinen, Martinstor) nutzt Querpaare gegenueberliegender, aehnlicher Waende - dort sind Querspuren gerade die Verwechslung und es
  gibt kein unabhaengiges Veto; sfm_seiten_modelle ruft dieses Werkzeug darum nur nach einem GPS-Vereinen auf (Martinstor unveraendert).
GRENZEN: Laengen in Metern ueber den GPS-Massstab von A (rahmen_a.massstab, +-2 % am Schwabentor). Wiederholte Fassadenteile (Fensterachse ~3 m) koennten eine Fremdlage
  innerhalb des Korridors erzeugen - dagegen hilft nur die Inlier-Mehrheit und das Doppelwand-Mass. Kein Buendelausgleich hier (siehe sfm_seiten_modelle: GPS-Ausgleich wird
  nach einer Bindung ausgelassen, er wuerde die Teile ohne gemeinsame 3D-Punkte wieder einzeln aufs GPS ziehen).
Test: tools/test_seiten_querspur_binden.py. Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap)."""
import os, sys, json, sqlite3, collections, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
MAXID = 2147483647
MIN_INLIER_PAAR = 15     # wie seiten_vereinen.punktpaare / Auftrag (576 Paare >= 15 Inlier)
MAX_AZIMUT_GRAD = 110.0  # Register NICHTS_GEBRACHT (ALIKED+LightGlue): nur Paare bis ~110 Grad Azimut-Unterschied uebernehmen
K_SIGMA = 3.0            # ANNAHME: Korridor = 3 Sigma der GPS-Bootstrap-Streuung
KIPP_MAX_GRAD = 8.0      # ANNAHME: Lot beider GPS-Rahmen kommt aus den Bild-oben-Richtungen (kein Bootstrap); gemessen bis 5,5 Grad Kameralot neben dem Wandlot (Martinstor Nord)
DREH_MIN_GRAD = 1.0      # Untergrenzen des Korridors (ANNAHME), damit ein sehr genaues GPS die Bindung nicht ausschliesst
MASS_MIN_REL = 0.02
LAGE_MIN_M = 1.0         # ANNAHME: Untergrenze Lage-Sigma (Bodenhoehe je Teil aus der dichten Wolke ~0,5 m, Handy-GPS-Mittel)
RANSAC_M = 0.30          # ANNAHME: Inlier-Grenze 3D-3D in Metern (duenne Punkte zweier getrennt ausgeglichener Modelle)
RUNDEN = 4000
MIN_PAARE = 5            # ANNAHME: Bildpaare nach dem Blick-Filter
MIN_INLIER = 30          # ANNAHME: stimmige 3D-3D-Zuordnungen
MIN_ANTEIL = 0.20        # ANNAHME: Inlier-Anteil unter den Zuordnungen nach dem Blick-Filter
MIN_PAARE_INLIER = 3     # Inlier aus mindestens 3 verschiedenen Bildpaaren (nicht ein Zufallspaar)
MIN_AUSDEHNUNG_M = 1.0   # ANNAHME: zweitgroesste Hauptachse (Wurzel des Eigenwerts) der Inlier >= 1 m
MAX_SD_ANTEIL = 0.5      # ANNAHME: Querspur-Streuung hoechstens halb so gross wie die GPS-Streuung
UEBERLAPP_M = 1.5        # Umkreis um die Inlier fuer die Doppelwand-Probe
DOPPEL_TOL = 1.05        # Doppelwand nachher <= vorher * 1,05 + 0,02 m


# ---------- Geometrie
def umeyama(P, Q):
    """Q ~ s R P + t, det R = +1 (keine Spiegelung) -> (s, R, t)."""
    mp, mq = P.mean(0), Q.mean(0); H = (Q - mq).T @ (P - mp) / len(P); U, S, Vt = np.linalg.svd(H); D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt)) or 1.0]); R = U @ D @ Vt
    s = float((S * np.diag(D)).sum() / max(1e-18, ((P - mp) ** 2).sum(1).mean())); return s, R, mq - s * R @ mp


def matrix(s, R, t):
    M = np.eye(4); M[:3, :3] = s * R; M[:3, 3] = t; return M


def zerlege(M):
    M = np.asarray(M, float); s = float(np.cbrt(np.linalg.det(M[:3, :3]))); return s, M[:3, :3] / s, M[:3, 3]


def anwenden(M, X): return np.asarray(X, float) @ np.asarray(M)[:3, :3].T + np.asarray(M)[:3, 3]


def lot_aus_kameras(Rs):
    """Lot = Mittel der Bild-oben-Richtungen (wie seiten_gps_vereinen.kameras)."""
    o = np.mean([-np.asarray(R)[1] for R in Rs], 0); return o / np.linalg.norm(o)


def azimut_unterschied(v1, v2, lot):
    """Winkel (Grad) zwischen zwei Blickrichtungen im Grundriss (senkrecht zum Lot)."""
    a = v1 - (v1 @ lot) * lot; b = v2 - (v2 @ lot) * lot; na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9: return 0.0
    return float(np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1, 1))))


def dreh_teile(Rd, lot):
    """Drehung Rd -> (Drehung um das Lot in Grad, vorzeichenbehaftet; Kippung in Grad = Winkel zwischen Rd*lot und lot)."""
    kipp = float(np.degrees(np.arccos(np.clip((Rd @ lot) @ lot, -1, 1))))
    e1 = np.cross(lot, [1.0, 0, 0] if abs(lot[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(lot, e1); x = Rd @ e1
    return float(np.degrees(np.arctan2(x @ e2, x @ e1))), kipp


# ---------- GPS-Korridor
def gps_unsicherheit(vj):
    """vereinen.json der GPS-Vereinigung -> dict(M, dreh_sd, mass_sd, lage_sd_m, m_je_einheit) oder Grund (str)."""
    if not vj.get("ok") or "B_nach_A" not in vj: return "GPS-Vereinigung nicht angenommen"
    pr = vj.get("pruefung") or {}; ra, rb = vj.get("rahmen_a") or {}, vj.get("rahmen_b") or {}
    if "dreh_sd_grad" not in pr or "mass_sd_rel" not in pr: return "GPS-Unsicherheit (Bootstrap) fehlt in vereinen.json"
    if not ra.get("massstab") or not ra.get("inlier") or not rb.get("inlier"): return "GPS-Rahmen (Massstab/Geotags) fehlt in vereinen.json"
    lage = float(np.hypot(ra.get("rest_median_m", 5.0) / np.sqrt(ra["inlier"]), rb.get("rest_median_m", 5.0) / np.sqrt(rb["inlier"])))   # Mittel vieler Geotags (ANNAHME: unabhaengig)
    return dict(M=np.asarray(vj["B_nach_A"], float), dreh_sd=float(pr["dreh_sd_grad"]), mass_sd=float(pr["mass_sd_rel"]), lage_sd_m=max(lage, LAGE_MIN_M), m_je_einheit=float(ra["massstab"]))


def korridor(M, G, lot, ref_b, k=K_SIGMA):
    """Abweichung der Sim3 M (B -> A) von der GPS-Lage G['M'] und ob sie im Korridor liegt. ref_b = Bezugspunkte in B (Kamerazentren von B).
    -> dict(dreh_lot_grad, kipp_grad, massstab_rel, lage_m, lage_grenze_m, im_korridor, gruende)."""
    sq, Rq, _ = zerlege(M); sg, Rg, _ = zerlege(G["M"]); dl, kp = dreh_teile(Rq @ Rg.T, lot); mr = sq / sg - 1.0; mj = G["m_je_einheit"]
    Xg = anwenden(G["M"], ref_b); Xq = anwenden(M, ref_b); lage = float(np.median(np.linalg.norm(Xq - Xg, axis=1))) * mj
    c = np.median(Xg, 0); r = float(np.median(np.linalg.norm((Xg - c) - np.outer((Xg - c) @ lot, lot), axis=1))) * mj   # Hebel um die Mitte der B-Kameras (dort traegt das GPS)
    lg = k * float(np.sqrt(G["lage_sd_m"] ** 2 + (np.radians(G["dreh_sd"]) * r) ** 2 + (G["mass_sd"] * r) ** 2))
    gd, gm = k * max(G["dreh_sd"], DREH_MIN_GRAD), k * max(G["mass_sd"], MASS_MIN_REL); gr = []
    if abs(dl) > gd: gr.append(f"Drehung um das Lot {dl:+.1f} Grad neben GPS (Grenze {gd:.1f})")
    if kp > KIPP_MAX_GRAD: gr.append(f"Kippung {kp:.1f} Grad (Grenze {KIPP_MAX_GRAD:.0f})")
    if abs(np.log1p(mr)) > np.log1p(gm): gr.append(f"Massstab {100 * mr:+.1f} % neben GPS (Grenze {100 * gm:.0f} %)")
    if lage > lg: gr.append(f"Lage der B-Kameras {lage:.1f} m neben GPS (Grenze {lg:.1f} m)")
    return dict(dreh_lot_grad=round(dl, 3), kipp_grad=round(kp, 3), massstab_rel=round(mr, 5), lage_m=round(lage, 3), dreh_grenze_grad=round(gd, 2), mass_grenze_rel=round(gm, 4),
                lage_grenze_m=round(lg, 2), hebel_m=round(r, 2), im_korridor=not gr, gruende=gr)


def sim3_ransac(P, Q, thr, im_korridor=None, runden=RUNDEN, saat=0):
    """RANSAC-Sim3 P -> Q (drei Punkte, keine Spiegelung). im_korridor(M) -> bool: nur solche Hypothesen zaehlen (GPS-Veto); None = alle.
    -> (M, inlier-Maske) oder (None, None)."""
    if len(P) < 3: return None, None
    rng = np.random.default_rng(saat); best = None; nb = -1
    for _ in range(runden):
        ix = rng.choice(len(P), 3, replace=False); A = Q[ix]
        if np.linalg.norm(np.cross(A[1] - A[0], A[2] - A[0])) < 1e-6 * max(1e-12, np.linalg.norm(A[1] - A[0]) ** 2): continue   # kollinear
        s, R, t = umeyama(P[ix], Q[ix])
        if not np.isfinite(s) or s <= 0: continue
        inl = np.linalg.norm(s * P @ R.T + t - Q, axis=1) < thr; n = int(inl.sum())
        if n <= nb or n < 3: continue
        M = matrix(s, R, t)
        if im_korridor is not None and not im_korridor(M): continue
        best, nb = inl, n
    if best is None: return None, None
    inl = best; s, R, t = umeyama(P[inl], Q[inl]); Mbest = matrix(s, R, t)
    if im_korridor is not None and not im_korridor(Mbest): return None, None         # Ausgleich ueber alle Inlier verlaesst den Korridor -> keine belastbare Lage
    for _ in range(3):                                                               # nachschaerfen; verlaesst die Verfeinerung den Korridor, gilt die letzte gueltige Lage
        neu = np.linalg.norm(anwenden(Mbest, P) - Q, axis=1) < thr
        if neu.sum() < 3: break
        s, R, t = umeyama(P[neu], Q[neu]); M = matrix(s, R, t)
        if im_korridor is not None and not im_korridor(M): break
        Mbest, inl = M, neu
    inl = np.linalg.norm(anwenden(Mbest, P) - Q, axis=1) < thr
    return Mbest, inl


# ---------- Zuordnungen aus den Querpaaren
def zuordnungen(KA, KB, paare, M_gps, lot, max_azimut=MAX_AZIMUT_GRAD):
    """KA/KB {Bildname: dict(p3d = Punkt-IDs je Merkmal (-1 = keiner), blick = Blickrichtung im eigenen System)}, paare = [(Name A, Name B, m (k x 2: Merkmal A, Merkmal B))].
    Blick-Filter in der GPS-Lage. -> dict(P_ids, Q_ids, paar_je_zuordnung (Liste von Mengen), paare_gesamt, paare_blick_ok, azimute)."""
    Rg = zerlege(M_gps)[1]; kor = {}; trg = {}; n_ok = 0; az = []
    for j, (a, b, m) in enumerate(paare):
        if a not in KA or b not in KB: continue
        w = azimut_unterschied(np.asarray(KA[a]["blick"], float), Rg @ np.asarray(KB[b]["blick"], float), lot); az.append(round(w, 1))
        if w > max_azimut: continue
        n_ok += 1; pa, pb = KA[a]["p3d"], KB[b]["p3d"]; m = np.asarray(m).reshape(-1, 2); m = m[(m[:, 0] < len(pa)) & (m[:, 1] < len(pb))]
        qa, qb = pa[m[:, 0]], pb[m[:, 1]]; ok = (qa >= 0) & (qb >= 0)
        for u, v in zip(qb[ok], qa[ok]): kor.setdefault(int(u), collections.Counter())[int(v)] += 1; trg.setdefault((int(u), int(v)), set()).add(j)
    L = [(u, c.most_common(1)[0][0]) for u, c in kor.items()]
    return dict(P_ids=[u for u, _ in L], Q_ids=[v for _, v in L], paar_je_zuordnung=[trg[x] for x in L], paare_gesamt=len(paare), paare_blick_ok=n_ok, azimute=az)


# ---------- Doppelwand
def doppelwand(DA, DB, Q_inl, M_vor, M_nach, mj, umkreis_m=UEBERLAPP_M, n_max=300000, saat=0):
    """Abstand der Teil-Wolken an gemeinsam gesehenen Flaechen: A-Punkte im Umkreis der Inlier (A-Seite), je Punkt Abstand zum naechsten B-Punkt (nach M_vor bzw. M_nach),
    Median/P90 in Metern. Gleiche Punktauswahl vorher/nachher. -> dict(vor, nach) oder None (zu wenig Ueberlappung)."""
    from scipy.spatial import cKDTree
    rng = np.random.default_rng(saat); DA = np.asarray(DA, float); DB = np.asarray(DB, float)
    if len(DA) > n_max: DA = DA[rng.choice(len(DA), n_max, replace=False)]
    if len(DB) > n_max: DB = DB[rng.choice(len(DB), n_max, replace=False)]
    d, _ = cKDTree(np.asarray(Q_inl, float)).query(DA, distance_upper_bound=umkreis_m / mj); X = DA[np.isfinite(d)]
    if len(X) < 50 or len(DB) < 50: return None
    erg = {}
    for k, M in (("vor", M_vor), ("nach", M_nach)):
        dd = cKDTree(anwenden(M, DB)).query(X)[0] * mj; erg[k] = dict(median_m=round(float(np.median(dd)), 3), p90_m=round(float(np.percentile(dd, 90)), 3), n=int(len(X)))
    return erg


# ---------- Kern
def binden(KA, KB, XA, XB, paare, G, lot, ref_b, DA=None, DB=None, max_azimut=MAX_AZIMUT_GRAD, saat=0):
    """Kern ohne Datei-IO. XA/XB {Punkt-ID: xyz}, G = gps_unsicherheit(...), ref_b = Kamerazentren von B, DA/DB dichte Wolken (sonst duenne Punkte fuer die Doppelwand).
    -> Ergebnis-dict (ok, urteil, zu_wenig, B_nach_A bei ok, pruefung, doppelwand)."""
    mj = G["m_je_einheit"]; Z = zuordnungen(KA, KB, paare, G["M"], lot, max_azimut); pr = dict(paare_gesamt=Z["paare_gesamt"], paare_blick_ok=Z["paare_blick_ok"], zuordnungen=len(Z["P_ids"]),
        max_azimut_grad=max_azimut, azimut_median_grad=float(np.median(Z["azimute"])) if Z["azimute"] else None)
    erg = dict(art="querspur", B_nach_A_gps=G["M"].tolist(), pruefung=pr)
    if Z["paare_blick_ok"] < MIN_PAARE or len(Z["P_ids"]) < MIN_INLIER:
        erg.update(ok=False, zu_wenig=True, urteil=f"zu wenig Querspuren: {Z['paare_blick_ok']} Paare nach dem Blick-Filter (noetig {MIN_PAARE}), {len(Z['P_ids'])} 3D-Zuordnungen (noetig {MIN_INLIER}) - GPS-Lage bleibt"); return erg
    P = np.array([XB[u] for u in Z["P_ids"]], float); Q = np.array([XA[v] for v in Z["Q_ids"]], float); thr = RANSAC_M / mj
    ink = lambda M: korridor(M, G, lot, ref_b)["im_korridor"]
    Mf, inf_ = sim3_ransac(P, Q, thr, None, saat=saat)                               # ohne Veto: nur zur Meldung (steckt eine starke Fremdlage in den Paaren?)
    if Mf is not None:
        kf = korridor(Mf, G, lot, ref_b); pr["bester_ohne_gps"] = dict(inlier=int(inf_.sum()), im_korridor=kf["im_korridor"], dreh_lot_grad=kf["dreh_lot_grad"], lage_m=kf["lage_m"])
    M, inl = sim3_ransac(P, Q, thr, ink, saat=saat + 1)
    if M is None: erg.update(ok=False, urteil="ABGELEHNT: keine Querspur-Lage im GPS-Korridor (Querpaare zeigen eine andere Lage - Gegenseiten-Verwechslung?) - GPS-Lage bleibt"); return erg
    k = korridor(M, G, lot, ref_b); n = int(inl.sum()); pi = set().union(*[Z["paar_je_zuordnung"][i] for i in np.flatnonzero(inl)])
    ev = np.sqrt(np.clip(np.sort(np.linalg.eigvalsh(np.cov((Q[inl] * mj).T)))[::-1], 0, None)) if n >= 4 else np.zeros(3)
    rng = np.random.default_rng(saat + 2); ii = np.flatnonzero(inl); dr, ms = [], []; s0, R0, _ = zerlege(M)
    for _ in range(200):                                                             # Bootstrap der Querspur-Sim3 ueber die Inlier
        b = rng.choice(ii, len(ii)); s_, R_, _ = umeyama(P[b], Q[b]); dr.append(np.degrees(np.arccos(np.clip((np.trace(R_ @ R0.T) - 1) / 2, -1, 1)))); ms.append(s_ / s0 - 1)
    rest = float(np.median(np.linalg.norm(anwenden(M, P[inl]) - Q[inl], axis=1))) * mj
    pr.update(inlier=n, inlier_anteil=round(n / len(P), 3), paare_mit_inliern=len(pi), ausdehnung_m=[round(float(x), 2) for x in ev], eben=bool(ev[2] < 0.1 * max(ev[1], 1e-9)),
              rest_median_m=round(rest, 3), querspur_sd=dict(dreh_grad=round(float(np.sqrt(np.mean(np.square(dr)))), 3), massstab_rel=round(float(np.std(ms)), 4)), abweichung_gps=k)
    D = (DA, DB) if DA is not None and DB is not None else (np.array(list(XA.values())), np.array(list(XB.values())))
    dw = doppelwand(D[0], D[1], Q[inl], G["M"], M, mj); erg["doppelwand"] = dw; erg["doppelwand_aus"] = "dicht" if DA is not None and DB is not None else "duenn"
    gr = []
    if n < MIN_INLIER: gr.append(f"nur {n} stimmige Zuordnungen (noetig {MIN_INLIER})")
    if n / len(P) < MIN_ANTEIL: gr.append(f"Inlier-Anteil {100 * n / len(P):.0f} % (noetig {100 * MIN_ANTEIL:.0f} %)")
    if len(pi) < MIN_PAARE_INLIER: gr.append(f"Inlier aus nur {len(pi)} Bildpaaren (noetig {MIN_PAARE_INLIER})")
    if ev[1] < MIN_AUSDEHNUNG_M: gr.append(f"Inlier auf einem Fleck/einer Linie (zweite Hauptachse {ev[1]:.2f} m, noetig {MIN_AUSDEHNUNG_M:.1f})")
    if pr["querspur_sd"]["dreh_grad"] > MAX_SD_ANTEIL * G["dreh_sd"] and pr["querspur_sd"]["dreh_grad"] > 0.2: gr.append(f"Querspur-Drehung nur auf +-{pr['querspur_sd']['dreh_grad']:.2f} Grad (GPS +-{G['dreh_sd']:.2f}) - kein Gewinn")
    if pr["querspur_sd"]["massstab_rel"] > MAX_SD_ANTEIL * G["mass_sd"] and pr["querspur_sd"]["massstab_rel"] > 0.005: gr.append(f"Querspur-Massstab nur auf +-{100 * pr['querspur_sd']['massstab_rel']:.1f} % (GPS +-{100 * G['mass_sd']:.1f} %) - kein Gewinn")
    if dw and dw["nach"]["median_m"] > dw["vor"]["median_m"] * DOPPEL_TOL + 0.02: gr.append(f"Doppelwand nachher groesser ({dw['vor']['median_m']:.2f} -> {dw['nach']['median_m']:.2f} m)")
    if gr: erg.update(ok=False, urteil="ABGELEHNT: " + "; ".join(gr) + " - GPS-Lage bleibt"); return erg
    erg.update(ok=True, B_nach_A=M.tolist(), urteil=f"gebunden ueber {n} Querspuren aus {len(pi)} Bildpaaren (Rest {rest:.2f} m); gegen GPS {k['dreh_lot_grad']:+.1f} Grad, Massstab {100 * k['massstab_rel']:+.1f} %, Lage {k['lage_m']:.1f} m"
               + (f"; Doppelwand Median {dw['vor']['median_m']:.2f} -> {dw['nach']['median_m']:.2f} m, P90 {dw['vor']['p90_m']:.2f} -> {dw['nach']['p90_m']:.2f} m" if dw else "; Doppelwand nicht messbar (zu wenig Ueberlappung)"))
    return erg


# ---------- Datei-IO
def modell_lesen(pfad):
    """-> (K {Name: dict(p3d, blick, C, R)}, X {Punkt-ID: xyz})."""
    import pycolmap
    r = pycolmap.Reconstruction(pfad); K = {}
    for im in r.images.values():
        if not im.has_pose: continue
        R = im.cam_from_world().rotation.matrix(); K[im.name] = dict(p3d=np.array([q.point3D_id if q.has_point3D() else -1 for q in im.points2D], dtype=np.int64), blick=R[2], R=R, C=np.asarray(im.projection_center()))
    return K, {i: np.asarray(q.xyz) for i, q in r.points3D.items()}


def querpaare(db, namen_a, namen_b, min_inlier=MIN_INLIER_PAAR):
    """Bildpaare A-B der Datenbank (two_view_geometries, nur lesend) -> [(Name A, Name B, m (k x 2: Merkmal A, Merkmal B))]."""
    d = sqlite3.connect(f"file:{db}?mode=ro", uri=True); nm = dict(d.execute("select image_id, name from images")); idn = {v: k for k, v in nm.items()}
    ia = [idn[n] for n in namen_a if n in idn]; ib = [idn[n] for n in namen_b if n in idn]; ids = []
    for x in ia:
        for y in ib: ids.append(min(x, y) * MAXID + max(x, y))
    L = []
    for k in range(0, len(ids), 900):
        blk = ids[k:k + 900]
        for pid, rows, data in d.execute(f"select pair_id, rows, data from two_view_geometries where rows >= ? and pair_id in ({','.join('?' * len(blk))})", [min_inlier] + blk):
            if not data: continue
            x, y = nm[pid // MAXID], nm[pid % MAXID]; m = np.frombuffer(data, np.uint32).reshape(-1, 2).astype(np.int64)
            L.append((x, y, m) if x in namen_a else (y, x, m[:, ::-1]))
    d.close(); return L


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("db"); ap.add_argument("--gps", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--dicht-a"); ap.add_argument("--dicht-b"); ap.add_argument("--max-azimut", type=float, default=MAX_AZIMUT_GRAD); a = ap.parse_args(argv)
    os.makedirs(a.aus, exist_ok=True); qj = os.path.join(a.aus, "querspur.json")
    try: from code_stand import code_stand; cs = code_stand("seiten_querspur_binden.py", wurzel=T)
    except Exception: cs = None
    def ende(erg, rc):
        erg.update(modell_a=os.path.abspath(a.a), modell_b=os.path.abspath(a.b), db=os.path.abspath(a.db), gps=os.path.abspath(a.gps), code_stand=cs); json.dump(erg, open(qj, "w"), indent=1, ensure_ascii=False)
        pr = erg.get("pruefung") or {}
        if "zuordnungen" in pr: print(f"Querpaare {pr['paare_gesamt']}, nach Blick-Filter {pr['paare_blick_ok']}, 3D-Zuordnungen {pr['zuordnungen']}" + (f", Inlier {pr['inlier']} ({100 * pr['inlier_anteil']:.0f} %) aus {pr['paare_mit_inliern']} Paaren" if "inlier" in pr else ""))
        if pr.get("bester_ohne_gps"): print(f"beste Lage OHNE GPS-Veto: {pr['bester_ohne_gps']}")
        if erg.get("doppelwand"): print(f"Doppelwand ({erg.get('doppelwand_aus')}): vorher {erg['doppelwand']['vor']}, nachher {erg['doppelwand']['nach']}")
        print(("QUERSPUR GEBUNDEN: " if erg.get("ok") else "QUERSPUR NICHT UEBERNOMMEN: ") + erg["urteil"]); return rc
    try: G = gps_unsicherheit(json.load(open(a.gps)))
    except Exception as ex: G = f"GPS-Ergebnis nicht lesbar ({type(ex).__name__})"
    if isinstance(G, str): return ende(dict(art="querspur", ok=False, zu_wenig=True, urteil="keine GPS-Lage als Veto: " + G), 2)
    KA, XA = modell_lesen(a.a); KB, XB = modell_lesen(a.b)
    try: paare = querpaare(a.db, set(KA), set(KB))
    except Exception as ex: return ende(dict(art="querspur", ok=False, zu_wenig=True, urteil=f"Ursprungs-Datenbank nicht lesbar ({type(ex).__name__}: {ex})"), 2)
    from seiten_vereinen import ply_punkte
    DA = ply_punkte(a.dicht_a, 1000000) if a.dicht_a and a.dicht_b and os.path.isfile(a.dicht_a) and os.path.isfile(a.dicht_b) else None; DB = ply_punkte(a.dicht_b, 1000000) if DA is not None else None
    erg = binden(KA, KB, XA, XB, paare, G, lot_aus_kameras([k["R"] for k in KA.values()]), np.array([k["C"] for k in KB.values()]), DA, DB, a.max_azimut)
    return ende(erg, 0 if erg["ok"] else (2 if erg.get("zu_wenig") else 3))


if __name__ == "__main__": sys.exit(main())
