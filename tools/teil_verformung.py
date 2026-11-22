#!/usr/bin/env python3
"""teil_verformung.py <sparse> <fotos> [--aus teil_verformung.json] [--faeden N] [--max-n N]   (22.11.2026, Recherche duenne Bruecken Methode 2)

VERFORMUNG EINES (TEIL-)MODELLS OHNE PUNKTZUORDNUNGEN MESSEN: "Lotfeld" + "Wandrichtungsfeld" je Kamera.
WARUM: die Brueckenkopplung (seiten_eck_koppeln) sieht innere Verformung eines Teils nicht (Eichung 22.11.: 13-16 von 20 verformten Faellen bestehen). Am
Schwabentor bleibt nach dem Lot-Fix 0,38 m Suedwand-Versatz - ist ein Teil in sich gebogen? Die Fotos selbst sagen es: jede Kamera sieht senkrechte und
waagerechte Kanten; ein STARRES Modell muss sie fuer alle Kameras in dieselben Weltrichtungen zurueckrechnen.
JE KAMERA (nur Bild + SfM-Pose, Sekunden):
  LOT: Fluchtpunkt der Senkrechten (schwerkraft_je_bild.fluchtpunkt_senkrecht, dieselbe Methode wie lot_welt) -> 'oben' im Weltrahmen W_i = -R_i^T d_i.
       Rest = Neigung von W_i gegen das robuste Modell-Lot m, zerlegt in zwei waagerechte Achsen (b1 = Hauptachse der Kameras, b2 = oben x b1).
  WANDRICHTUNG (Manhattan): jede nicht senkrechte Bildkante spannt mit dem Kamerazentrum eine Ebene (Normale R^T K^T l); ihre WAAGERECHTE Richtung ist n x m.
       Winkel in der Waagerechten modulo 90 Grad, laengengewichtetes Histogramm -> Gipfel = Wandrichtung dieser Kamera. ANNAHME: rechtwinkliges Gebaeude
       (Waende 0/90 Grad); wo das nicht gilt, ist der Gipfel schwach -> Kamera ohne Wert (kein Raten).
FELD UEBER DAS TEIL (robuste lineare Regression, Huber, je Groesse, mit der Blickneigung der Kamera als Stoergroesse - Brennweitenfehler kippen das Lot
  blickabhaengig, nicht ortsabhaengig):
  - TREND entlang b1 (Grad ueber die Teil-Laenge): lot_b1 ~ Biegung um die Querachse, lot_b2 ~ Verwindung um die Laengsachse, wand ~ Biegung um das Lot.
  - SPRUNG: bester Zweiteiler entlang b1 (Medianunterschied, beide Seiten >= 10 % / 5 Kameras) und Gruppenzerfall (2 Haufen der Restwerte, die raeumlich
    zusammenhaengen = Knick/Gelenk; verstreute Ausreisser = Rauschen).
  - RAUSCHEN: robuste Streuung je Kamera (MAD).
URTEIL je Groesse: 'trend' (|Aenderung| > TREND_GRAD und > TREND_T x Standardfehler), 'sprung' (Gruppenzerfall > SPRUNG_GRAD und raeumlich zusammenhaengend,
  oder Zweiteiler > SPRUNG_GRAD und > SPRUNG_T x Standardfehler), sonst 'starr'. Teil-Urteil = schlimmstes. GRENZEN: siehe GRENZEN-BELEG unten.
NICHT SICHTBAR (ehrlich): Massstabsverlauf (Lot und Richtung sind massstabsfrei) -> Vorschlag Massstabsfeld im Bericht 'massstabsfeld'.
Ausgabe JSON: kameras (je Kamera Werte), felder{lot_b1, lot_b2, wand}{trend_grad, t, sprung_grad, gruppen,...}, urteil, zeile (eine Zeile fuer Logs).
Exit 0 = starr, 3 = verformt (trend/sprung), 4 = kein Urteil (zu wenige Kameras mit Wert).
Funktionen fuer andere Werkzeuge: messen(rec, fotos) -> Bericht; feld(...) Kern der Auswertung (synthetisch getestet: tools/test_teil_verformung.py)."""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)

MIN_KAMERAS = 12          # weniger Kameras mit Wert -> kein Urteil
WAND_GIPFEL_MIN = 0.25    # Anteil der Kantenlaenge im +-WAND_FENSTER-Fenster um den Gipfel, sonst Kamera ohne Wandwert
WAND_FENSTER = 2.0        # Grad
WAND_SUCH = 6.0           # Grad um die Hauptrichtung (zweiter Durchgang); groesser als jede gesuchte Biegung (1-3 Grad), kleiner als Nachbarhaeuser (1122: 14 Grad)
WAND_MIN_KANTEN = 8
VP_MIN_LINIEN, VP_LAENGE_REL = 10, 0.03   # Fluchtpunkt der Senkrechten je Kamera: lot_welt nutzt 12 / 6 % (Mittel ueber viele Bilder); am Quaderwerk 1122 Teil 1
                                          # fanden 12/6 % nur 12 von 127 Kameras, 10/3 % 33 von 40 (22.11.) - fuer ein FELD braucht es Werte je Kamera
# GRENZEN (Grad ueber die Teil-Laenge bzw. Sprunghoehe). BELEG 22.11.2026 siehe Kopf von GRENZEN_BELEG.
TREND_GRAD = float(os.environ.get("RCPARK_VERFORM_TREND_GRAD", "0.6"))
TREND_T = 4.0
SPRUNG_GRAD = float(os.environ.get("RCPARK_VERFORM_SPRUNG_GRAD", "2.0"))
SPRUNG_T = 6.0
GRENZEN_BELEG = """ANNAHME bis zur Eichung (Messung 22.11. im Bericht des Zweigs, Werte unten nachgetragen)."""


def basis(m, C):
    """Waagerechte Basis: b1 = Hauptachse der Punkte C senkrecht zu m, b2 = m x b1."""
    X = C - np.median(C, 0); X = X - np.outer(X @ m, m)
    _, _, Vt = np.linalg.svd(X - X.mean(0), full_matrices=False); b1 = Vt[0] - (Vt[0] @ m) * m; b1 /= np.linalg.norm(b1); b2 = np.cross(m, b1)
    return b1, b2


def ort_koordinate(C, c0, m):
    """Ort der Kameras C (n x 3) im Teil, massstabsfrei. -> (u1, u2, art, spanne).
    'bogen': Azimut um die Kernmitte c0 (in der Waagerechten zu m), an der groessten Luecke aufgeschnitten, Mitte 0, Spanne (5-95 %) = 1 -> u1 in Teil-Laengen
             entlang des Rundgangs (Turm wie Strassenfassade: der Azimut laeuft mit der Kamerakette). u2 = log(Abstand / Median-Abstand).
    'linie': Azimutspanne < 20 Grad (alle Kameras aus einer Richtung) -> Lage entlang der Hauptachse der Kamerazentren (5-95 % = 1)."""
    h = C - c0; h = h - np.outer(h @ m, m); b1, b2 = basis(m, h + c0); phi = np.degrees(np.arctan2(h @ b2, h @ b1)) % 360
    o = np.argsort(phi); gap = np.diff(np.r_[phi[o], phi[o][0] + 360]); start = phi[o][(int(np.argmax(gap)) + 1) % len(o)]; ph = (phi - start) % 360
    sp = float(np.percentile(ph, 95) - np.percentile(ph, 5)); r = np.linalg.norm(h, axis=1)
    if sp >= 20:
        return (ph - np.median(ph)) / sp, np.log(np.maximum(r, 1e-9) / np.median(r)), "bogen", sp
    s1 = h @ b1; L = float(np.percentile(s1, 95) - np.percentile(s1, 5)) or 1.0
    return (s1 - np.median(s1)) / L, (h @ b2) / L, "linie", L


def robust_lot(W):
    m = np.median(W, 0); m /= np.linalg.norm(m)
    for _ in range(4):
        a = np.degrees(np.arccos(np.clip(W @ m, -1, 1))); inn = a < max(3.0, 3 * np.median(a))
        if inn.sum() < 3: break
        m = W[inn].mean(0); m /= np.linalg.norm(m)
    return m


def wand_winkel(linien, R, f, cx, cy, m, b1, b2, bezug=None):
    """Linien (N x 4 Pixel des SfM-Bilds) -> (Winkel modulo 90 in Grad, Gipfelanteil, Zahl Kanten im Fenster) oder (None, ...).
    bezug: Gipfel nur im Fenster +-WAND_SUCH um diese Richtung suchen (Hauptrichtung des Gebaeudes; Nachbarhaeuser in anderem Winkel - 1122 Teil 1: Gruppe bei
    +-14 Grad - sollen keine Kamera kapern)."""
    if len(linien) < WAND_MIN_KANTEN: return None, 0.0, 0
    K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]]); p0 = np.c_[linien[:, :2], np.ones(len(linien))]; p1 = np.c_[linien[:, 2:], np.ones(len(linien))]
    l = np.cross(p0, p1); n = (K.T @ l.T).T; n /= np.linalg.norm(n, axis=1, keepdims=True); nw = n @ np.asarray(R)       # R^T n je Zeile
    # Kanten nahe der Augenhoehe: Ebene fast waagerecht, Richtung schlecht bestimmt (Fehler ~ 1/sin) -> ab 10 Grad Ebenenneigung, Gewicht Laenge x sin^2
    c = np.abs(nw @ m); ok = c < 0.985; d = np.cross(nw[ok], m); d /= np.linalg.norm(d, axis=1, keepdims=True)
    w = np.linalg.norm(linien[ok, 2:] - linien[ok, :2], axis=1) * (1 - c[ok] ** 2)
    if len(d) < WAND_MIN_KANTEN: return None, 0.0, int(len(d))
    th = np.degrees(np.arctan2(d @ b2, d @ b1)) % 90.0
    z = np.exp(1j * np.radians(th * 4)); bins = np.arange(0, 90, 0.25)                 # 4-facher Winkel: Periode 90 Grad
    abst = np.abs(((th[None, :] - bins[:, None]) + 45) % 90 - 45); dichte = (w[None, :] * np.exp(-0.5 * (abst / 0.75) ** 2)).sum(1)
    if bezug is not None: dichte = np.where(np.abs(((bins - bezug) + 45) % 90 - 45) <= WAND_SUCH, dichte, 0.0)
    g = bins[int(np.argmax(dichte))]; fe = np.abs(((th - g) + 45) % 90 - 45) <= WAND_FENSTER
    if fe.sum() < WAND_MIN_KANTEN: return None, float(w[fe].sum() / w.sum()), int(fe.sum())
    zz = (w[fe] * z[fe]).sum(); wink = (np.degrees(np.angle(zz)) / 4) % 90.0
    return float(wink), float(w[fe].sum() / w.sum()), int(fe.sum())


def _kamera(arg):
    """Eine Kamera: Bild lesen, Lot + waagerechte Kanten. -> dict oder None."""
    import cv2
    import schwerkraft_je_bild as SJ
    cv2.setNumThreads(1)
    name, ordner, R, f, cx, cy, br, ho = arg
    g = SJ.bild(ordner, name)
    if g is None: return None
    sy, sx = g.shape[0] / float(ho), g.shape[1] / float(br)
    if abs(sx / sy - 1) > 0.02: return None
    import zlib; rng = np.random.default_rng(zlib.crc32(name.encode())); vp, n = SJ.fluchtpunkt_senkrecht(g, rng, VP_MIN_LINIEN, VP_LAENGE_REL); aus = dict(name=name)
    if vp is not None:
        d = SJ.unten_kamera(vp, f * sx, cx * sx, cy * sy)
        if SJ.plausibel(d): aus["unten_kam"] = d.tolist(); aus["lot_linien"] = int(n)      # posenunabhaengig (Kamerasystem)
    sc = 1000.0 / max(g.shape); gk = cv2.resize(g, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA) if sc < 1 else g; sc = min(sc, 1.0)
    L = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(gk)[0]
    if L is not None:
        L = L.reshape(-1, 4) / sc / np.array([sx, sy, sx, sy]); dl = L[:, 2:] - L[:, :2]; ln = np.linalg.norm(dl, axis=1)
        ang = np.degrees(np.arctan2(np.abs(dl[:, 0]), np.abs(dl[:, 1])))                # 0 = senkrecht im Bild
        aus["linien_quer"] = L[(ln > 0.04 * max(br, ho)) & (ang > 30)].tolist()
    return aus


def huber_fit(X, y, it=20):
    """Robuste lineare Regression (Huber). -> (beta, se, sigma, residuen)."""
    beta = np.linalg.lstsq(X, y, rcond=None)[0]; w = np.ones(len(y))
    for _ in range(it):
        r = y - X @ beta; s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-9; c = 1.345 * s
        w = np.where(np.abs(r) <= c, 1.0, c / np.maximum(np.abs(r), 1e-12)); Wx = X * w[:, None]
        b2 = np.linalg.lstsq(Wx.T @ X, Wx.T @ y, rcond=None)[0]
        if np.allclose(b2, beta, atol=1e-9): beta = b2; break
        beta = b2
    r = y - X @ beta; s = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-9
    try: cov = s ** 2 * np.linalg.inv((X * w[:, None]).T @ X) * (len(y) / max(w.sum(), 1.0))
    except np.linalg.LinAlgError: cov = np.full((X.shape[1], X.shape[1]), np.inf)
    return beta, np.sqrt(np.abs(np.diag(cov))), float(s), r


def gruppen(u, werte, pos, min_n):
    """Zerfaellt der Wert (1D) in zwei raeumlich zusammenhaengende Gruppen? 2-Mittel auf dem Wert, Zusammenhang = Anteil der 5 naechsten Nachbarn (Ort) in
    derselben Gruppe gegen den Zufall. -> dict(abstand_grad, klein_n, zusammenhang, zufall, namen_idx)"""
    v = np.asarray(werte, float); o = np.argsort(v); best = None
    for i in range(min_n, len(v) - min_n + 1):                                        # 1D: optimaler Zweiteiler = Schnitt der sortierten Werte
        a, b = v[o[:i]], v[o[i:]]; sse = ((a - a.mean()) ** 2).sum() + ((b - b.mean()) ** 2).sum()
        if best is None or sse < best[0]: best = (sse, i)
    if best is None: return None
    i = best[1]; lab = np.zeros(len(v), bool); lab[o[i:]] = True
    ab = abs(np.median(v[lab]) - np.median(v[~lab])); innen = 1.4826 * np.median(np.abs(np.r_[v[lab] - np.median(v[lab]), v[~lab] - np.median(v[~lab])]))
    D = np.linalg.norm(pos[:, None, :] - pos[None, :, :], axis=2); np.fill_diagonal(D, np.inf); nn = np.argsort(D, 1)[:, :5]
    gleich = float((lab[nn] == lab[:, None]).mean()); p = lab.mean(); zufall = float(p * p + (1 - p) * (1 - p))
    klein = lab if lab.sum() <= (~lab).sum() else ~lab
    return dict(abstand_grad=round(float(ab), 3), innen_grad=round(float(innen), 3), klein_n=int(klein.sum()), zusammenhang=round(gleich, 3), zufall=round(zufall, 3),
                klein_idx=np.flatnonzero(klein).tolist())


def feld(u1, u2, neig, werte, namen=None, zweiteiler=True):
    """Kern: Werte (Grad) je Kamera gegen Ort (u1 entlang, u2 quer, in Teil-Laengen) + Blickneigung. -> dict(trend_grad, se_grad, t, quer_grad, sprung_grad,
    sprung_t, sprung_bei, gruppen, rauschen_grad, n, urteil)."""
    u1, u2, neig, y = (np.asarray(x, float) for x in (u1, u2, neig, werte)); n = len(y)
    if n < MIN_KAMERAS: return dict(n=n, urteil="kein_urteil")
    X = np.c_[np.ones(n), u1, u2, np.tan(np.radians(np.clip(neig, -80, 80)))]
    beta, se, s, r = huber_fit(X, y); spanne = float(np.percentile(u1, 95) - np.percentile(u1, 5)) or 1.0
    trend = float(beta[1] * spanne); trend_se = float(se[1] * spanne); t = abs(trend) / max(trend_se, 1e-9)
    # Zweiteiler entlang u1 auf dem Rest OHNE Ortstrend (nur Blickneigung herausgerechnet)
    y0 = y - X[:, [0, 3]] @ np.linalg.lstsq(X[:, [0, 3]], y, rcond=None)[0]; o = np.argsort(u1); mn = max(5, int(0.1 * n)); sp = (0.0, None, 0.0)
    for i in range(mn, n - mn + 1):
        a, b = y0[o[:i]], y0[o[i:]]; d = float(np.median(b) - np.median(a)); se_d = s * np.sqrt(1.0 / len(a) + 1.0 / len(b)) * 1.2533
        if abs(d) / se_d > abs(sp[2]): sp = (d, i, d / se_d)
    gr = gruppen(u1, y0, np.c_[u1, u2], mn)
    zus = gr is not None and gr["zusammenhang"] - gr["zufall"] >= 0.25 and gr["abstand_grad"] > max(SPRUNG_GRAD, 4 * gr["innen_grad"])
    urteil = "starr"
    if abs(trend) > TREND_GRAD and t > TREND_T: urteil = "trend"
    if (zweiteiler and abs(sp[0]) > SPRUNG_GRAD and abs(sp[2]) > SPRUNG_T) or zus: urteil = "sprung"
    aus = dict(n=n, trend_grad=round(trend, 3), se_grad=round(trend_se, 3), t=round(t, 1), je_teil_laenge_grad=round(float(beta[1]), 3), kamera_spanne=round(spanne, 3), quer_grad=round(float(beta[2] * spanne), 3), neigung_koeff=round(float(beta[3]), 3),
               rauschen_grad=round(s, 3), sprung_grad=round(sp[0], 3), sprung_t=round(float(sp[2]), 1),
               sprung_bei_u=round(float(u1[o[sp[1]]]), 3) if sp[1] is not None else None, gruppen=gr, gruppen_knick=bool(zus), urteil=urteil)
    if gr is not None and namen is not None: aus["gruppen"] = dict({k: v for k, v in gr.items() if k != "klein_idx"}, klein_bilder=[namen[i] for i in gr["klein_idx"]][:40])
    if sp[1] is not None and namen is not None: aus["sprung_bilder"] = [namen[o[j]] for j in range(max(0, sp[1] - 2), min(n, sp[1] + 2))]
    return aus


def kern_box(rec, rand=0.5):
    """Kern der Punktwolke: 2-98 % je Achse, um 'rand' x Spanne erweitert (ferne Hintergrundpunkte - 1122 Teil 1 bis 20000 Teil-Laengen - fallen weg)."""
    P = np.array([p.xyz for p in rec.points3D.values()])
    if len(P) < 20: return None
    lo, hi = np.percentile(P, 2, 0), np.percentile(P, 98, 0); d = (hi - lo) * rand; return lo - d, hi + d


def kameras_lesen(rec):
    out = []; box = kern_box(rec)
    for im in rec.images.values():
        if not im.has_pose: continue
        cam = rec.cameras[im.camera_id]; R = im.cam_from_world().rotation.matrix()
        X = np.array([rec.points3D[p.point3D_id].xyz for p in im.points2D if p.has_point3D()]).reshape(-1, 3)
        if box is not None: X = X[np.all((X >= box[0]) & (X <= box[1]), 1)]
        B = np.median(X, 0) if len(X) >= 5 else None                                   # None: Kamera sieht den Kern nicht -> ohne Ort, nicht im Feld
        out.append(dict(name=im.name, R=R, C=im.projection_center(), B=B, f=cam.mean_focal_length(), cx=cam.principal_point_x, cy=cam.principal_point_y, br=cam.width, ho=cam.height))
    return out


def messen(rec, fotos, faeden=4, max_n=None, roh=None):
    """rec: pycolmap.Reconstruction (oder Pfad). roh: vorher gemessene _kamera-Ergebnisse {name: dict} (Wiederverwendung, z. B. verformte Kopie desselben Teils:
    die Bildmessung haengt nur am Bild, nicht an der Pose - nur Lot/Richtung werden mit den neuen Posen neu gerechnet). -> (Bericht, roh)."""
    import pycolmap
    if isinstance(rec, str): rec = pycolmap.Reconstruction(rec)
    ks = [k for k in kameras_lesen(rec) if k["B"] is not None]
    if max_n and len(ks) > max_n: ks = [ks[i] for i in sorted(np.random.default_rng(0).choice(len(ks), max_n, replace=False))]
    roh = dict(roh or {}); fehlt = [k for k in ks if k["name"] not in roh]
    if fehlt:
        args = [(k["name"], fotos, k["R"], k["f"], k["cx"], k["cy"], k["br"], k["ho"]) for k in fehlt]
        if faeden > 1:
            import multiprocessing as mp
            with mp.get_context("spawn").Pool(faeden) as p: res = p.map(_kamera, args, chunksize=4); p.close(); p.join()   # sauber beenden (terminate -> glog-Absturzmeldungen von pycolmap)
        else: res = [_kamera(x) for x in args]
        for k, r_ in zip(fehlt, res): roh[k["name"]] = r_ or dict(name=k["name"], fehlt=True)
    W, idx = [], []
    for i, k in enumerate(ks):
        r_ = roh.get(k["name"]) or {}
        if "unten_kam" in r_: W.append(-(k["R"].T @ np.asarray(r_["unten_kam"]))); idx.append(i)
    bericht = dict(kameras_gesamt=len(ks), lot_kameras=len(W))
    if len(W) < MIN_KAMERAS: bericht.update(urteil="kein_urteil", grund=f"nur {len(W)} Kameras mit Lot (< {MIN_KAMERAS})", zeile=f"VERFORMUNG: kein Urteil ({len(W)} Kameras mit Lot)"); return bericht, roh
    # ORT einer Kamera = Lage ihres ZENTRUMS auf dem Rundgang (ort_koordinate). Erster Versuch 22.11. (Blickpunkt = Median der gesehenen Punkte entlang der
    # Hauptachse der Punkte) taugte nicht: an Tuermen blicken alle Kameras auf die Mitte (1122 Teil 0: 6/8 der Kameras in +-0,03 Teil-Laengen) - die SfM-Drift
    # waechst aber entlang der KAMERAKETTE um das Gebaeude. Kameras, die den Kern nicht sehen (Blickpunkt fehlt), bleiben draussen.
    W = np.array(W); m = robust_lot(W); C = np.array([k["C"] for k in ks]); P = np.array([p.xyz for p in rec.points3D.values()])
    box = kern_box(rec); P = P[np.all((P >= box[0]) & (P <= box[1]), 1)] if box is not None else P
    b1, b2 = basis(m, P); c0 = np.median(P, 0); u1, u2, ortart, L = ort_koordinate(C, c0, m)
    blick = np.array([k["R"][2] for k in ks]); neig = np.degrees(np.arcsin(np.clip(blick @ m, -1, 1)))   # Blickneigung (+ = nach oben)
    namen = [k["name"] for k in ks]; idx = np.array(idx)
    e1 = np.degrees(np.arcsin(np.clip(W @ b1, -1, 1))); e2 = np.degrees(np.arcsin(np.clip(W @ b2, -1, 1)))
    felder = dict(lot_b1=feld(u1[idx], u2[idx], neig[idx], e1, [namen[i] for i in idx]), lot_b2=feld(u1[idx], u2[idx], neig[idx], e2, [namen[i] for i in idx]))
    def wand_lauf(bezug):
        wv, wi, gip = [], [], []
        for i, k in enumerate(ks):
            r_ = roh.get(k["name"]) or {}
            if not r_.get("linien_quer"): continue
            w, ant, nk = wand_winkel(np.asarray(r_["linien_quer"], float), k["R"], k["f"], k["cx"], k["cy"], m, b1, b2, bezug)
            if w is not None and ant >= (WAND_GIPFEL_MIN if bezug is None else WAND_GIPFEL_MIN / 2): wv.append(w); wi.append(i); gip.append(ant)
        return np.array(wv), np.array(wi, int), gip
    wv, wi, gip = wand_lauf(None)                                                     # 1. Durchgang: Hauptrichtung = Gipfel der Kamera-Gipfel (Histogramm, nicht Median)
    if len(wv) >= MIN_KAMERAS:
        bins = np.arange(0, 90, 0.25); dch = np.exp(-0.5 * ((np.abs(((wv[None, :] - bins[:, None]) + 45) % 90 - 45)) / 0.75) ** 2).sum(1); g = float(bins[int(np.argmax(dch))])
        wv, wi, gip = wand_lauf(g)                                                    # 2. Durchgang: je Kamera nur im Fenster um die Hauptrichtung
        z = np.exp(1j * np.radians(4 * wv)); g = (np.degrees(np.angle(np.median(z.real) + 1j * np.median(z.imag))) / 4) % 90
    if len(wv) >= MIN_KAMERAS:
        rw = ((wv - g) + 45) % 90 - 45; felder["wand"] = feld(u1[wi], u2[wi], neig[wi], rw, [namen[i] for i in wi], zweiteiler=False); felder["wand"]["richtung_grad"] = round(float(g), 2)
        felder["wand"]["gipfel_median"] = round(float(np.median(gip)), 3)
    else: felder["wand"] = dict(n=len(wv), urteil="kein_urteil", grund="zu wenige Kameras mit klarer Wandrichtung (Gebaeude nicht rechtwinklig oder wenig Kanten)")
    rang = {"kein_urteil": 0, "starr": 1, "trend": 2, "sprung": 3}; schlimm = max(felder.values(), key=lambda f: rang[f["urteil"]])["urteil"]
    if all(f["urteil"] == "kein_urteil" for f in felder.values()): schlimm = "kein_urteil"
    deut = dict(lot_b1="Biegung um die Querachse", lot_b2="Verwindung um die Laengsachse", wand="Biegung um das Lot")
    teile = [f"{deut[k]} {f['trend_grad']:+.2f} Grad (t {f['t']:.0f}), Sprung {f['sprung_grad']:+.2f} (t {f['sprung_t']:.0f}){', Gruppenknick' if f.get('gruppen_knick') else ''}"
             for k, f in felder.items() if "trend_grad" in f]
    bericht.update(ort=ortart, spanne=round(float(L), 4), lot=m.tolist(), achse_b1=b1.tolist(), achse_b2=b2.tolist(), wand_kameras=len(wv), felder=felder, urteil=schlimm,
                   massstabsfeld="nicht gemessen: Lot/Wandrichtung sind massstabsfrei. Vorschlag: wiederkehrende Hoehen (Quaderlagen/Gesimse) je Wandabschnitt mit "
                                 "foto_mass/Kantenstufe, Verhaeltnis entlang b1 (Aufwand ~1 Tag, braucht Fassadenbild je Abschnitt)",
                   zeile=f"VERFORMUNG {schlimm.upper()}: " + "; ".join(teile))
    bericht["kameras"] = [dict(name=namen[i], u1=round(float(u1[i]), 3), u2=round(float(u2[i]), 3), neigung_grad=round(float(neig[i]), 1)) for i in range(len(ks))]
    for j, i in enumerate(idx): bericht["kameras"][i].update(lot_b1=round(float(e1[j]), 3), lot_b2=round(float(e2[j]), 3))
    for j, i in enumerate(wi if len(wv) >= MIN_KAMERAS else []): bericht["kameras"][i]["wand"] = round(float(rw[j]), 3)
    return bericht, roh


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("sparse"); ap.add_argument("fotos"); ap.add_argument("--aus")
    ap.add_argument("--faeden", type=int, default=4); ap.add_argument("--max-n", type=int); ap.add_argument("--roh", help="Bildmessungen zwischenspeichern/wiederverwenden (JSON)")
    a = ap.parse_args(argv); roh = json.load(open(a.roh)) if a.roh and os.path.isfile(a.roh) else None
    b, roh = messen(a.sparse, a.fotos, a.faeden, a.max_n, roh)
    if a.roh: json.dump(roh, open(a.roh, "w"))
    b["modell"] = a.sparse; print(b["zeile"])
    if a.aus: os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True); json.dump(b, open(a.aus, "w"), indent=1, ensure_ascii=False)
    return {"starr": 0, "trend": 3, "sprung": 3}.get(b["urteil"], 4)


if __name__ == "__main__": sys.exit(main())
