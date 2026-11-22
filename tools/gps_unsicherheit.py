#!/usr/bin/env python3
"""gps_unsicherheit.py - EHRLICHE Unsicherheit eines Foto-GPS-Fits (Drehung um das Lot, Massstab): Zufall (Bootstrap) PLUS systematischer Anteil je Fotositzung.

WARUM (22.11.2026, schwabentor-1122, Messung tools/versuche/lage_widerspruch_1122/): das SfM war starr und richtig, die AUSRICHTUNG falsch (-9,3 Grad, x0,80 gegen die
belegte 1120-Lage). Ursache: das Nah-GPS EINER Fotositzung (06.11. 11:30-11:41, 157 Fotos) ist systematisch verzerrt (+9,4 Grad / x0,867 gegen die richtige Lage; je nach
Blickrichtung 5-7 m zur Turmachse gezogen = Abschattung/Mehrweg am Turm). Der GPS-Anker-Kasten (3 x Bootstrap = +-2 Grad / +-4,2 %) kannte nur den Zufall: 157 Fotos
mitteln den Zufall weg, den gemeinsamen Fehler der Sitzung aber NICHT - der Kasten sperrte die Ausrichtung in die falsche Lage, LoD2 klebte am Rand.
MODELL (ANNAHMEN gekennzeichnet):
  - Fotos einer SITZUNG (EXIF-Aufnahmezeit, Luecke > SITZUNG_LUECKE_S trennt) und eines RINGS (nah < NAH_M / fern) teilen EINEN systematischen Fehler: ein Muster der
    Groesse SIGMA_SYS_M (Meter) um das Objekt. Seine Wirkung auf Drehung/Massstab einer Gruppe g ist ~ SIGMA_SYS_M / L_g (L_g = RMS-Abstand ihrer GPS-Lagen von der Mitte
    des Fits = Hebel). Der Ausgleich (kleinste Quadrate) gewichtet eine Gruppe mit W_g = n_g L_g^2; damit
        Var(Drehung) = Var(Massstab) = SIGMA^2 * Summe_g (W_g^2 / L_g^2) / (Summe_g W_g)^2,  n_eff = (Summe W)^2 / Summe W^2 (unabhaengige Gruppen).
    Eine Sitzung mit 157 Nahfotos (L ~17 m) gibt so ~11 Grad / ~20 % (1 Sigma) - nur noch ein grobes Veto (Seite, 90/180 Grad), kein Anker. Fernfotos (L 150-400 m)
    einer anderen Gruppe druecken das auf ~1 Grad (1120: 10 stimmige Fernfotos).
  - SIGMA_SYS_M = 3,4 m ANNAHME, gemessen am Kontrollobjekt schwabentor-1120 (Lage aus LoD2 + Kette, Grundriss-Tor bestanden): mittlerer Versatz des Handy-GPS je Sitzung
    3,1-3,4 m neben den Kamerastandorten (tools/seiten_lod2_je_teil.VERSATZ_SITZUNG_M); dieselben Nahfotos allein ergeben +9,4 Grad / x0,867 bei L ~17 m, d. h. eine
    wirksame Mustergroesse 2,3-2,8 m (<= 3,4: die Annahme ist eher vorsichtig). Ein Objekt, ein Handy - an weiteren Objekten pruefen.
  - Gibt es >= 2 Gruppen mit je >= MIN_GRUPPE Fotos, wird SIGMA zusaetzlich aus DEN DATEN geschaetzt (Abweichung der Einzel-Fits je Gruppe) und das GROESSERE genommen.
  - SITZUNG_LUECKE_S = 3600 s ANNAHME: am 1120 lagen die Teilsitzungen 11:3x und 11:4x (10 min auseinander) in DIESELBE Richtung daneben (korreliert); erst eine
    andere Stunde/ein anderer Tag (Satellitenstand, Laufweg) gilt als unabhaengig. Fotos ohne Aufnahmezeit bilden zusammen EINE Gruppe (vorsichtig).
Verwendet von: tools/lage_gps_pruefen.py (GPS-Tor) und tools/sfm_lod2_ausrichten.py (Startlage/GPS-Anker/Veto) - seit 22.11. (1122j) BEIDE ueber gps_fit() auf allen GPS-Kameras inkl. Fernfotos, tools/seiten_gps_vereinen.py + tools/seiten_lod2_je_teil.py (Kasten je Teil)
- EIN Mass, damit Tor und Ausrichtung nicht verschieden rechnen. Test: tools/test_gps_unsicherheit.py. Nur numpy (+ PIL fuer exif_zeit)."""
import math
import numpy as np

SIGMA_SYS_M = 3.4          # ANNAHME (Kopf): Mustergroesse des systematischen GPS-Fehlers einer Sitzung, gemessen 1120
SITZUNG_LUECKE_S = 3600.0  # ANNAHME (Kopf): Zeitluecke, ab der eine neue, unabhaengige Sitzung beginnt
NAH_M = 100.0              # wie lage_gps_pruefen --nah: Nah- und Fernfotos haben verschiedene Fehlerumgebungen (Gasse/Turm gegen freie Sicht)
MIN_GRUPPE = 15            # Fotos je Gruppe fuer die Datenschaetzung von SIGMA (Einzel-Fit)
MIN_AUSDEHNUNG_M = 10.0    # Einzel-Fit einer Gruppe nur, wenn ihre GPS-Lagen so weit streuen
Z90 = 1.645                # 90-%-Band (wie die Bootstrap-Perzentile 5/95 des GPS-Tors)
ANKER_K = 3.0              # Kasten = ANKER_K x Sigma (wie GPS_ANKER_K / K_SIGMA)
ANKER_MAX_DREH, ANKER_MAX_MASS = 8.0, 0.08   # ist der ehrliche Kasten breiter, TRAEGT das GPS die Lage nicht (kein Anker, nur Veto) - alte feste Werte des Ankers


def exif_zeit(pfad):
    """Aufnahmezeit (Sekunden seit 1970, Ortszeit ohne Zone) aus EXIF DateTimeOriginal (Exif-IFD 36867), sonst DateTime (306); None ohne Zeit."""
    try:
        from PIL import Image
        import datetime
        e = Image.open(pfad).getexif(); t = None
        try: t = e.get_ifd(0x8769).get(36867)
        except Exception: t = None
        t = t or e.get(306)
        if not t: return None
        return datetime.datetime.strptime(str(t).strip()[:19], "%Y:%m:%d %H:%M:%S").timestamp()
    except Exception:
        return None


def sitzungen(zeiten, luecke_s=SITZUNG_LUECKE_S):
    """Zeiten (Sekunden oder None) -> Sitzungsnummer je Foto (0, 1, ...; alle ohne Zeit = -1, eine gemeinsame Gruppe)."""
    z = [None if (t is None or not np.isfinite(t)) else float(t) for t in zeiten]; nr = [-1] * len(z)
    ix = sorted((t, i) for i, t in enumerate(z) if t is not None); k = -1; letzte = None
    for t, i in ix:
        if letzte is None or t - letzte > luecke_s: k += 1
        nr[i] = k; letzte = t
    return nr


def gruppen(G, zeiten=None, nah_m=NAH_M, mitte=None, luecke_s=SITZUNG_LUECKE_S):
    """Gruppe je Foto = (Sitzung, Ring). G = GPS-Lagen (n x 2, m, Objektrahmen oder UTM relativ zur Objektmitte); mitte = Objektmitte (Standard 0,0)."""
    G = np.asarray(G, float); m = np.zeros(2) if mitte is None else np.asarray(mitte, float)
    s = sitzungen(zeiten if zeiten is not None else [None] * len(G), luecke_s); r = np.hypot(*(G - m).T) >= nah_m
    return [(int(a), int(b)) for a, b in zip(s, r)]


def _fit2d(a, b):
    ma, mb = a.mean(0), b.mean(0); a0, b0 = a - ma, b - mb; U, S, Vt = np.linalg.svd(a0.T @ b0)
    d = np.sign(np.linalg.det(Vt.T @ U.T)); D = np.diag([1, d]); R = Vt.T @ D @ U.T
    return (S * np.diag(D)).sum() / max((a0 ** 2).sum(), 1e-12), R


def robust_fit2d(M, G, schwelle=10.0, iter_=2000, seed=0):
    """Robuster 2D-Aehnlichkeitsfit G ~ s R M + t (RANSAC aus Paaren, Inlier < schwelle m, 3 Nachfits) wie das GPS-Tor (lage_gps_pruefen Konsens-Fit).
    22.11.2026 Probe teil0: der getrimmte Kleinste-Quadrate-Fit der Ausrichtung (_gpsfit) lag 25 % im Massstab neben dem Tor-Fit (eingefrorene Geotags 272 m) - die
    Bezugslage der Lageproben muss dasselbe GPS sehen wie das Tor. -> (s, R, t, inlier) oder None."""
    M = np.asarray(M, float); G = np.asarray(G, float); n = len(M); rng = np.random.default_rng(seed); best = None
    if n < 5: return None
    for _ in range(iter_):
        i = rng.choice(n, 2, replace=False)
        if np.hypot(*(G[i[0]] - G[i[1]])) < 10 or np.hypot(*(M[i[0]] - M[i[1]])) < 1e-9: continue
        s, R = _fit2d(M[i], G[i]); t = G[i].mean(0) - s * M[i].mean(0) @ R.T; inl = np.hypot(*(M @ R.T * s + t - G).T) < schwelle
        if best is None or inl.sum() > best.sum(): best = inl
    if best is None or best.sum() < 5: return None
    for _ in range(3):
        s, R = _fit2d(M[best], G[best]); t = G[best].mean(0) - s * M[best].mean(0) @ R.T; best = np.hypot(*(M @ R.T * s + t - G).T) < schwelle
        if best.sum() < 5: return None
    return float(s), R, t, best


def systematik(G, grp, w=None, sigma_m=SIGMA_SYS_M, M=None):
    """Systematischer Anteil (1 Sigma) des 2D-Aehnlichkeitsfits auf den Fotos w (Maske; Standard alle). G = GPS-Lagen (m), grp = Gruppe je Foto (gruppen()).
    M (optional, n x 2, gleiches System wie G nach dem Fit oder beliebig) = Kamerastandorte: dann wird SIGMA zusaetzlich aus den Gruppen-Einzelfits geschaetzt.
    -> dict(dreh_sd_grad, mass_sd_rel, sigma_m, sigma_quelle, n_gruppen, n_eff, gruppen=[{gruppe, n, hebel_m, gewicht}], sigma_daten_m)."""
    G = np.asarray(G, float); w = np.ones(len(G), bool) if w is None else np.asarray(w, bool)
    if w.sum() < 3: return dict(dreh_sd_grad=float("inf"), mass_sd_rel=float("inf"), sigma_m=sigma_m, n_gruppen=0, n_eff=0.0, gruppen=[], sigma_quelle="zu wenig Fotos")
    c = G[w].mean(0); X = G - c; Wg = {}; Lg = {}; ng = {}
    for i in np.flatnonzero(w):
        Wg[grp[i]] = Wg.get(grp[i], 0.0) + float(X[i] @ X[i]); ng[grp[i]] = ng.get(grp[i], 0) + 1
    for g in Wg: Lg[g] = math.sqrt(Wg[g] / ng[g])
    sig_daten = None
    if M is not None and len(Wg) >= 2:                                             # Datenschaetzung: Einzel-Fit je grosser Gruppe gegen den Fit ALLER ANDEREN Gruppen
        M = np.asarray(M, float); q = []
        for g in Wg:
            iw = np.flatnonzero(w); ig = np.array([i for i in iw if grp[i] == g]); io = np.array([i for i in iw if grp[i] != g])
            if len(ig) < MIN_GRUPPE or len(io) < MIN_GRUPPE or np.ptp(G[ig], axis=0).max() < MIN_AUSDEHNUNG_M or np.ptp(G[io], axis=0).max() < MIN_AUSDEHNUNG_M: continue
            s_g, R_g = _fit2d(M[ig], G[ig]); s_o, R_o = _fit2d(M[io], G[io]); Rd = R_g @ R_o.T
            dth = math.atan2(Rd[1, 0], Rd[0, 0]); dls = math.log(s_g / s_o)
            L_eigen = float(np.sqrt(((G[ig] - G[ig].mean(0)) ** 2).sum(1).mean()))       # Hebel des Einzel-Fits = Streuung um die eigene Mitte
            q.append(math.sqrt((dth ** 2 + dls ** 2) / 2.0) * L_eigen)              # Streuung der anderen vernachlaessigt -> eher zu gross (vorsichtig)
        if q: sig_daten = float(np.sqrt(np.mean(np.square(q))))
    sig = max(sigma_m, sig_daten or 0.0)
    SW = sum(Wg.values()); v = sum(Wg[g] ** 2 / max(Lg[g], 1e-6) ** 2 for g in Wg) / max(SW, 1e-12) ** 2; sd = sig * math.sqrt(v)
    n_eff = SW ** 2 / max(sum(x ** 2 for x in Wg.values()), 1e-12)
    return dict(dreh_sd_grad=float(math.degrees(sd)), mass_sd_rel=float(sd), sigma_m=float(sig), sigma_daten_m=sig_daten,
                sigma_quelle=("Daten (Gruppen-Einzelfits)" if sig_daten and sig_daten > sigma_m else f"ANNAHME {sigma_m} m (gemessen 1120)"),
                n_gruppen=len(Wg), n_eff=round(float(n_eff), 2),
                gruppen=[dict(gruppe=list(g), n=ng[g], hebel_m=round(Lg[g], 1), gewicht=round(Wg[g] / SW, 3)) for g in sorted(Wg, key=lambda g: -Wg[g])])


def gesamt(sd_dreh_zufall, sd_mass_zufall, sys):
    """Zufall (Bootstrap, 1 Sigma) und Systematik zusammen (quadratisch, unabhaengig) -> (sd_dreh_grad, sd_mass_rel)."""
    a = float(sd_dreh_zufall or 0.0); b = float(sd_mass_zufall or 0.0)
    return math.hypot(a, sys["dreh_sd_grad"]), math.hypot(b, sys["mass_sd_rel"])


def band(mitte, halb_zufall, sd_sys, z=Z90):
    """90-%-Band: Bootstrap-Halbbreite (aus Perzentilen) und systematischer Anteil quadratisch -> (unten, oben)."""
    h = math.hypot(float(halb_zufall), z * float(sd_sys)); return float(mitte) - h, float(mitte) + h


def widerspruch(dreh_grad, dreh_band, mass, mass_band, max_dreh=15.0, max_skala=0.15):
    """Regel des GPS-Tors (lage_gps_pruefen Pruefung 2), auch fuer das Veto der Ausrichtung: Warnung nur, wenn das (ehrliche) 90-%-Band 0 Grad bzw. 1,0 AUSSCHLIESST
    UND der Wert die feste Grenze ueberschreitet. -> Liste der Warnungen (leer = kein Widerspruch)."""
    w = []
    if (dreh_band[0] > 0 or dreh_band[1] < 0) and abs(dreh_grad) > max_dreh: w.append(f"Drehung {dreh_grad:.0f} Grad gegen GPS")
    if (mass_band[0] > 1 or mass_band[1] < 1) and abs(mass - 1) > max_skala: w.append(f"Massstab {mass:.2f} gegen GPS")
    return w


def anker_kasten(sd_dreh_grad, sd_mass_rel, k=ANKER_K, min_dreh=2.0, min_mass=0.03, max_dreh=ANKER_MAX_DREH, max_mass=ANKER_MAX_MASS):
    """Kasten des GPS-Ankers aus der EHRLICHEN Unsicherheit: (dreh, mass) = k x Sigma (unten begrenzt). Ist er breiter als max_dreh/max_mass -> None = das GPS traegt die
    Lage NICHT (nur Veto; Lage muessen LoD2 + unabhaengige Proben entscheiden). Frueher (bis 22.11.) wurde hier stumm auf 8 Grad/8 % gekappt."""
    if not (math.isfinite(sd_dreh_grad) and math.isfinite(sd_mass_rel)): return None
    d, m = max(k * sd_dreh_grad, min_dreh), max(k * sd_mass_rel, min_mass)
    if d > max_dreh or m > max_mass: return None
    return float(d), float(m)


def _fit2d_t(a, b):
    """Aehnlichkeit b ~ s R a + t (2D, ohne Spiegelung) - wie lage_gps_pruefen.fit2d (bitgleich)."""
    ma, mb = a.mean(0), b.mean(0); a0, b0 = a - ma, b - mb; U, S, Vt = np.linalg.svd(a0.T @ b0)
    d = np.sign(np.linalg.det(Vt.T @ U.T)); D = np.diag([1, d]); R = Vt.T @ D @ U.T
    s = (S * np.diag(D)).sum() / max((a0 ** 2).sum(), 1e-12); return s, R, mb - s * R @ ma


def _winkel(R): return float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))


def gps_fit(C, G, zeiten=None, nah_m=NAH_M, seed=0, n_boot=400, n_ransac=3000):
    """DER GPS-Fit (EINE Quelle der Wahrheit, 22.11.2026): Kamerastandorte C (n x 2, beliebiges System: SfM-Lotsystem der Ausrichtung ODER Modell/UTM des Tors)
    -> Foto-GPS G (n x 2, m, relativ zur Objektmitte): G ~ s R C + t. ALLE Fotos mit GPS zaehlen, auch die Fernfotos (langer Hebel); falsch registrierte Kameras und
    falsche Geotags fallen im robusten Konsens heraus. Ablauf = bisheriges GPS-Tor (lage_gps_pruefen.urteil Pruefung 2, unveraendert verschoben): Start mit dem
    Kamerakern (75 %), 5 x getrimmt, robuster Konsens (RANSAC < 10 m, gilt ab >= 40 % und >= 10 Fotos), Bootstrap (Zufall), ehrliches Band (Zufall + Sitzung x Ring).
    WARUM (Lauf kette-schwabentor-null-1122j): die Ausrichtung nahm nur den Kamerakern (70 %, ohne die 10 Fernfotos bei 320 m) -> 'GPS traegt nicht' (1 Gruppe,
    +-10,4 Grad), das Tor rechnete mit ihnen -> 'kann ankern' (2 Gruppen, +-1 Grad). Zwei Quellen, zwei Urteile ueber dasselbe GPS.
    Lot und Mitte der Ausrichtung rechnen weiter NUR mit dem Kamerakern (Lehre 15.11.) - das betrifft diesen Fit nicht.
    -> dict(ok, grund, s, R, t, drehung_grad (Fit), w (Inlier), res, ransac, drehung_90/massstab_90 (Bootstrap 5/50/95), drehung_90_ehrlich, massstab_90_ehrlich,
            sd_drehung_grad, sd_massstab (gesamt 1 Sigma), anker (Kasten oder None), systematik, rest_median_m, n_fern_inlier)."""
    C = np.asarray(C, float); G = np.asarray(G, float); n_ = len(G)
    if n_ < 5 or len(C) != n_: return dict(ok=False, grund="zu wenige Fotos mit GPS")
    _dm = np.hypot(*(C - np.median(C, 0)).T); w = _dm <= np.percentile(_dm, 75)   # 15.11.: Start nur mit dem Kamerakern - km-weit versetzte Kameras kippten den Fit
    for _ in range(5):
        if w.sum() < 3 or not np.isfinite(C[w]).all(): return dict(ok=False, grund="fit nicht moeglich")
        try: s, R, t = _fit2d_t(C[w], G[w])
        except np.linalg.LinAlgError: return dict(ok=False, grund="fit konvergiert nicht")
        res = np.hypot(*(C @ R.T * s + t - G).T); w = res < max(np.percentile(res, 80), 15)
    rng = np.random.default_rng(seed); best = None; ransac = None
    for _ in range(n_ransac):
        i3 = rng.choice(n_, 2, replace=False)
        if np.hypot(*(G[i3[0]] - G[i3[1]])) < 10 or np.hypot(*(C[i3[0]] - C[i3[1]])) < 1e-6: continue
        try: s_, R_, t_ = _fit2d_t(C[i3], G[i3])
        except np.linalg.LinAlgError: continue
        inl = np.hypot(*(C @ R_.T * s_ + t_ - G).T) < 10.0
        if best is None or inl.sum() > best.sum(): best = inl
    if best is not None and best.sum() >= max(10, 0.4 * n_):
        for _ in range(3): s, R, t = _fit2d_t(C[best], G[best]); res = np.hypot(*(C @ R.T * s + t - G).T); best = res < 10.0
        if best.sum() >= max(10, 0.4 * n_): w = best; ransac = dict(inlier=int(best.sum()), von=int(n_))
    s, R, t = _fit2d_t(C[w], G[w]); res = np.hypot(*(C @ R.T * s + t - G).T)
    ys, ss = [], []; iw = np.flatnonzero(w)
    for _ in range(n_boot):
        i = rng.choice(iw, len(iw)); s_, R_, _ = _fit2d_t(C[i], G[i]); ys.append(_winkel(R_)); ss.append(s_)
    yb = np.percentile(ys, [5, 50, 95]); sb = np.percentile(ss, [5, 50, 95])
    sy = systematik(G, gruppen(G, zeiten, nah_m), w, M=C)
    yb_e = band(yb[1], (yb[2] - yb[0]) / 2, sy["dreh_sd_grad"]); sb_e = band(sb[1], (sb[2] - sb[0]) / 2, sy["mass_sd_rel"])
    sd_d, sd_m = gesamt((yb[2] - yb[0]) / (2 * Z90), (sb[2] - sb[0]) / (2 * Z90 * max(sb[1], 1e-9)), sy); ak = anker_kasten(sd_d, sd_m)
    fern = np.hypot(*G.T) >= nah_m
    return dict(ok=True, grund="", s=float(s), R=R, t=t, drehung_grad=_winkel(R), w=w, res=res, ransac=ransac, drehung_90=yb, massstab_90=sb,
                drehung_90_ehrlich=yb_e, massstab_90_ehrlich=sb_e, sd_drehung_grad=float(sd_d), sd_massstab=float(sd_m), anker=ak, systematik=sy,
                rest_median_m=float(np.median(res[w])), n_fern_inlier=int((w & fern).sum()), n=int(n_))


def gps_fit_widerspruch(f, max_dreh=15.0, max_skala=0.15):
    """Regel des GPS-Tors (Pruefung 2) auf einen gps_fit(): Bootstrap-Median gegen das ehrliche Band und die festen Grenzen. -> Liste der Warnungen."""
    return widerspruch(float(f["drehung_90"][1]), f["drehung_90_ehrlich"], float(f["massstab_90"][1]), f["massstab_90_ehrlich"], max_dreh, max_skala)


def gps_fit_text(f):
    """Eine Zeile fuer Logs (gleich in Tor und Ausrichtung)."""
    if not f.get("ok"): return f"GPS-Fit nicht moeglich: {f.get('grund')}"
    sy = f["systematik"]
    return (f"GPS-Fit (eine Quelle, alle GPS-Fotos inkl. Fernfotos): {f['ransac']['inlier'] if f['ransac'] else int(f['w'].sum())} von {f['n']} Fotos (davon fern {f['n_fern_inlier']}), "
            f"Rest Median {f['rest_median_m']:.1f} m; ehrlich +-{f['sd_drehung_grad']:.1f} Grad / +-{100 * f['sd_massstab']:.1f} % (systematisch {sy['dreh_sd_grad']:.1f} Grad aus "
            f"{sy['n_gruppen']} Gruppe(n) Sitzung x Ring, n_eff {sy['n_eff']})" + (f" -> GPS kann ankern (Kasten +-{f['anker'][0]:.1f} Grad / {100 * f['anker'][1]:.1f} %)" if f["anker"]
                                                                                    else " -> GPS legt die Lage NICHT fest (nur grobes Veto)"))


def ehrlich(G, w, zeiten=None, M=None, sd_dreh_zufall=0.0, sd_mass_zufall=0.0, nah_m=NAH_M):
    """Bequemer Gesamtaufruf: -> dict(systematik, dreh_sd_grad, mass_sd_rel (gesamt 1 Sigma), anker (Kasten oder None), urteil_text)."""
    sy = systematik(G, gruppen(G, zeiten, nah_m), w, M=M); sd, sm = gesamt(sd_dreh_zufall, sd_mass_zufall, sy); ak = anker_kasten(sd, sm)
    txt = (f"GPS-Unsicherheit ehrlich: Drehung +-{sd:.1f} Grad, Massstab +-{100 * sm:.1f} % (1 Sigma; Zufall {float(sd_dreh_zufall or 0):.1f} Grad / {100 * float(sd_mass_zufall or 0):.1f} %, "
           f"systematisch {sy['dreh_sd_grad']:.1f} Grad / {100 * sy['mass_sd_rel']:.1f} % aus {sy['n_gruppen']} Gruppe(n), n_eff {sy['n_eff']}, Sigma {sy['sigma_m']:.1f} m {sy['sigma_quelle']})"
           + (f" -> GPS-Anker moeglich (Kasten +-{ak[0]:.1f} Grad / {100 * ak[1]:.1f} %)" if ak else " -> GPS TRAEGT DIE LAGE NICHT (nur grobes Veto: Seite, 90/180 Grad)"))
    return dict(systematik=sy, dreh_sd_grad=sd, mass_sd_rel=sm, anker=ak, text=txt)
