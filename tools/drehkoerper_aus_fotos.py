#!/usr/bin/env python3
"""drehkoerper_aus_fotos.py - DREHKOERPER (Haube, Kegeldach, Rundturm-Schaft) aus FOTO-SILHOUETTEN mit den SfM-Kameras: gemeinsame Bausteine (23.11.2026).

Herausgezogen aus tools/laterne_aus_fotos.py (Laternenhaube, Kette 1122r), damit Laterne, Treppentuermchen und kuenftige Rundkoerper DIESELBE Messung nutzen:
 (1) Fotoauswahl ueber alle Kameras je Blickrichtungs-Sektor (fotos_streuen), frei vor Himmel laut Himmelsmasken-Cache (himmel_anteil);
 (2) Silhouette je Hoehe: Farbabstand zum Himmel (farb_halb) oder Himmelsmaske (masken_halb), auch EINSEITIG (die andere Seite steht vor einem Nachbarkoerper -> +-inf);
 (3) Profil r(z) als SEHSTRAHL-HUELLE (huelle_foto/drehprofil: groesster Querschnitt, dessen Abbild in der Silhouette liegt; K_HUELLE-kleinster Wert ueber die Fotos);
 (4) Ausgleich je Foto (zentrieren seitlich, registrieren Hoehe; achse_suchen fuer die Achse bei einseitigen Silhouetten);
 (5) Querschnitt rund/n-Eck durch Nachrechnen + gepaarten t-Test (querschnitt_synthese), rund nur als benannte ANNAHME.
Anwendung Rundkoerper (Treppentuermchen): tools/rund_aus_huelle.py.
"""
import sys, os, math, numpy as np

H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)

N_KAND = (3, 4, 5, 6, 8, 10, 12, 16)  # gepruefte Eckenzahlen (regelmaessige Vielecke; Kreis = keine Zahl gewinnt)
MIN_FOTOS = 3           # Formfamilie/Eckenzahl aus >= 3 Fotos (CLAUDE.md)
MIN_FAMILIE = 3
DUNKEL = 0.5            # Silhouette: Abstand zum Himmel > 0,5 (halber Weg Himmel -> Bauwerk)
MIN_HIMMEL = 0.8        # Fotoauswahl: >= 80 % der Randpunkte neben dem Koerper sind in der Himmelsmaske Himmel (frei vor Himmel)
SEKTOR_GRAD = 45.0      # Fotoauswahl je Blickrichtungs-Sektor ...
MAX_JE_SEKTOR = 8       # ... hoechstens 8 Fotos (die mit den meisten px/m) - sonst bestimmen 10 Fotos aus 16 Grad das Ergebnis allein
MAX_FOTOS = 40          # Speicher: 40 Fotos x 12 MP Graustufen ~ 0,5 GB
# Sicherheit einer Formwahl: gepaarter t-Wert ueber dem einseitigen 97,5-%-Quantil der t-Verteilung (Freiheitsgrade = Fotos - 1)

T975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23}
def t_grenze(n_fotos): return T975.get(max(1, n_fotos - 1), 2.2 if n_fotos <= 21 else 2.05 if n_fotos <= 31 else 1.96)


def ausdehnung(s, x, c0=0.0, schwelle=DUNKEL):
    """Aeussere Ausdehnung der Dunkelheit (erste/letzte Stelle > schwelle) -> (links, rechts) oder None."""
    j = np.where(s > schwelle)[0]
    return None if len(j) == 0 else (float(x[j[0]]), float(x[j[-1]]))


def himmel_anteil(maske, proj, A, q, zs, xr):
    """Anteil Himmel (maske True) an den Randpunkten A + x q (x = +-xr) in den Hoehen zs; Punkte ausserhalb des Bilds zaehlen als nicht Himmel."""
    H, W = maske.shape; n = 0; h = 0
    for z in zs:
        for x in xr:
            p = proj(np.array([[A[0] + x * q[0], A[1] + x * q[1], z]]))[0][0]; n += 1
            xi, yi = int(round(p[0])), int(round(p[1]))
            if 0 <= xi < W and 0 <= yi < H and maske[yi, xi]: h += 1
    return h / max(n, 1)


def fotos_streuen(kand, sektor=SEKTOR_GRAD, je=MAX_JE_SEKTOR, gesamt=MAX_FOTOS):
    """Fotoauswahl ueber die Blickrichtungen: kand = [(ppm, az, nr, ...)]; je Sektor die je besten (ppm), dann insgesamt hoechstens 'gesamt' (beste ppm). -> Liste."""
    sek = {}
    for k in sorted(kand, key=lambda k: -k[0]): sek.setdefault(int((k[1] % 360.0) // sektor), []).append(k)
    aus = [k for v in sek.values() for k in v[:je]]
    return sorted(aus, key=lambda k: -k[0])[:gesamt]


# ---- Haube als DREHKOERPER aus den Silhouetten (23.11.2026) ----------------------------------------------------------------------------------------
# Anlass (Kette 1122r, neben_detail_laterne: Foto Zwiebel mit Einschnuerung, Knauf, Nadel - Modell Kasten): das Median-Breitenprofil je Hoehe war von der Taille bis
# zum Bauch flach (1,17..1,22 m), weil in Fotos von schraeg unten (bis -49 Grad) die breite Krempe als Ellipse bis 0,9 m ueber ihre eigene Hoehe in die Taillen-Zeilen
# ragt (Rueckkante hoeher abgebildet) - die Taille verschwand, Familie 'geschweift' 8:5. Jetzt SEHSTRAHL-HUELLE (visual hull): je Foto und Hoehe der groesste Querschnitt
# (Kreis bzw. n-Eck), dessen Abbild ganz in der Silhouette DIESES Fotos liegt; Radius je Hoehe = K_HUELLE-kleinster Wert ueber die Fotos (Fotos von unten begrenzen die
# Taille nicht, waagrechte Fotos schon). Querschnitt rund/n-Eck durch Synthese: Huelle je Hypothese, Silhouetten neu abgebildet, Restfehler je Foto verglichen.
K_HUELLE = 3            # Radius = drittkleinster Fotowert: bis zu 2 Fotos mit zu schmaler Silhouette (helles Blech vor hellem Himmel, Kamera-Restfehler) schnueren die Haube nicht ein;
                        # am Schwabentor schnitten 195 (Haube oben hell) und ein zweites Foto mit k = 2 den Bauch auf 1,0 m (Fotos 1,25 m)
QS_PUNKTE = 96          # Punkte je Querschnitt (Kreis/n-Eck-Kanten) fuer die Abbildung
RUND_TOL = 0.10         # Silhouette RICHTUNGSUNABHAENGIG: Kreis-Huelle erklaert die Fotos hoechstens 10 % schlechter als das beste n-Eck (kein richtungsabhaengiger Anteil) ...
EGAL_TOL = 0.20         # ... UND die Ersatz-Eckenzahl (Pfosten) ist mind. 20 % schlechter als der Kreis (Fotos widersprechen ihr). Von schraeg unten (45-55 Grad) zeigt die
                        # Silhouette den Querschnitt selbst (Ellipse/Raute der Ringe), darum trennt das auch bei engem Azimut-Bereich (Schwabentor: Quadrat 0,146 m, Kreis 0,088 m).
                        # Achteck -> Kreis-Naeherung weicht <= 4 % ab (unter der Profilstreuung)


def querschnitt_einheit(n=None, phase=0.0, m=QS_PUNKTE):
    """Einheits-Querschnitt (Umkreis 1) als Punkte (m x 2): Kreis (n None) oder regelmaessiges n-Eck (Punkte gleichmaessig auf den Kanten, Ecke 0 bei Weltwinkel phase)."""
    if not n: w = np.linspace(0, 2 * math.pi, m, endpoint=False); return np.c_[np.cos(w), np.sin(w)]
    e = np.array([[math.cos(math.radians(phase + k * 360.0 / n)), math.sin(math.radians(phase + k * 360.0 / n))] for k in range(n + 1)]); j = max(1, m // n)
    return np.vstack([e[k] + (e[k + 1] - e[k]) * t for k in range(n) for t in np.arange(j) / j])


def ebene_abbilden(P, C, A, az):
    """3D-Punkte P (k x 3) -> (x', z') in der Fotoebene eines Fotos: Ebene durch die Achse A senkrecht zur waagrechten Blickrichtung az (wie zeile()), Schnitt des
    Sehstrahls Kamera C -> P mit der Ebene. Gleiches Pixel wie P - so vergleicht man Punkte ausserhalb der Ebene (Krempe, Haubenrueckseite) mit dem gemessenen Profil."""
    u = np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0]); q = np.array([u[1], -u[0], 0.0]); A3 = np.array([A[0], A[1], 0.0])
    d = P - C; t = ((A3 - C) @ u) / np.where(np.abs(d @ u) < 1e-9, -1e-9, d @ u); X = C + t[:, None] * d
    return (X - A3) @ q, X[:, 2]


def farb_halb(zeile_fn, xs, zs, x_himmel, z_ref, schwelle_fn):
    """Silhouette je Hoehe aus dem FARBABSTAND zum Himmel: zeile_fn(z0, z1, nz) -> Farbzeile (N x 3) auf xs. Himmelsfarbe = Median der Pixel mit |x| >= x_himmel im
    Referenzband z_ref (neben der Laterne, Foto frei vor Himmel); Abstand normiert auf seinen 97-%-Wert im Band; Bauwerk = Abstand > schwelle_fn(z). -> {z: (l, r)}."""
    ref = np.asarray(zeile_fn(z_ref[0], z_ref[1], 25), float); au = np.abs(xs) >= x_himmel
    if ref.ndim != 2 or not np.isfinite(ref[au]).all(1).any(): return {}
    sky = np.nanmedian(ref[au], 0); d97 = float(np.nanpercentile(np.linalg.norm(ref - sky, axis=1), 97)); out = {}
    if not d97 > 1e-6: return {}
    for z in zs:
        d = np.nan_to_num(np.linalg.norm(np.asarray(zeile_fn(z, z, 1), float) - sky, axis=1) / d97, nan=0.0); e_ = ausdehnung(d, xs, schwelle=schwelle_fn(float(z)))
        if e_: out[float(z)] = (e_[0], e_[1])
    return out


def profil_raster(halb, dz=0.05):
    """Gemessenes Foto-Profil {z: (l, r)} (x quer in der Fotoebene) -> (zg, l, r) auf dem z-Gitter; fehlende Zeilen = NaN (dort ist Himmel)."""
    zz = sorted(halb); zg = np.round(np.arange(zz[0], zz[-1] + dz / 2, dz), 3); l = np.full(len(zg), np.nan); r = np.full(len(zg), np.nan); k = {round(z, 3): v for z, v in halb.items()}
    for i, z in enumerate(zg):
        v = k.get(round(float(z), 3))
        if v is not None: l[i], r[i] = v[0], v[1]
    return zg, l, r


def _zeilen(zp, zg):
    dz = float(zg[1] - zg[0]) if len(zg) > 1 else 0.05; i = np.round((zp - zg[0]) / dz).astype(int); return i, (i >= 0) & (i < len(zg))


def _in_silhouette(xp, zp, B):
    """Liegen die abgebildeten Punkte (x', z') in der Silhouette von Foto B (l <= x' <= r der naechsten Gitterzeile)? Ausserhalb des Gitters/Himmelszeile (NaN) = nein.
    EINSEITIG (23.11.2026, Treppentuermchen vor dem Hauptturm): l = -inf / r = +inf heisst 'diese Seite steht vor einem Nachbarkoerper, Umriss nicht messbar' -> keine Schranke."""
    i, ok = _zeilen(zp, B["zg"]); i = np.clip(i, 0, len(B["zg"]) - 1); l, r = B["l"][i], B["r"][i]
    return ok & ~np.isnan(l) & ~np.isnan(r) & (xp >= l - 1e-9) & (xp <= r + 1e-9)


def _ringe(A, zs, s, quer):
    m = len(quer); return np.c_[A[0] + (s[:, None] * quer[None, :, 0]).ravel(), A[1] + (s[:, None] * quer[None, :, 1]).ravel(), np.repeat(zs, m)]


def huelle_foto(B, A, zs, quer, s_max=3.0, iters=14):
    """Je Hoehe z (zs) der groesste Massstab s (Umkreis), bei dem der Querschnitt s * quer um die Achse A in Hoehe z ganz in der Silhouette von Foto B liegt (Bisektion).
    B: dict(C [3], az, A0 [Ebene der Messung], zg, l, r). -> Array s je Hoehe."""
    lo = np.zeros(len(zs)); hi = np.full(len(zs), s_max); m = len(quer); A0 = B.get("A0", A)
    for _ in range(iters):
        s = (lo + hi) / 2; xp, zp = ebene_abbilden(_ringe(A, zs, s, quer), np.asarray(B["C"], float), A0, B["az"])
        ok = _in_silhouette(xp, zp, B).reshape(len(zs), m).all(1); lo = np.where(ok, s, lo); hi = np.where(ok, hi, s)
    return lo


def silhouette_vorhersage(B, A, zs, rs, quer, dz=0.025):
    """Ausdehnung (l, r) des Drehkoerpers (Profil zs/rs um die Achse A, Querschnitt quer) im Foto B auf dessen Gitter zg (NaN = nichts): alle Querschnitte fein in z abgebildet."""
    zf = np.arange(zs[0], zs[-1] + 1e-9, dz); rf = np.interp(zf, zs, rs); xp, zp = ebene_abbilden(_ringe(A, zf, rf, quer), np.asarray(B["C"], float), B.get("A0", A), B["az"])
    i, k = _zeilen(zp, B["zg"]); n = len(B["zg"]); l = np.full(n, np.inf); r = np.full(n, -np.inf)
    np.minimum.at(l, i[k], xp[k]); np.maximum.at(r, i[k], xp[k]); l[~np.isfinite(l)] = np.nan; r[~np.isfinite(r)] = np.nan; return l, r


def drehprofil(beob, A, zs, n=None, phase=0.0, k=K_HUELLE, s_max=3.0, einseitig=False):
    """Sehstrahl-Huelle eines Drehkoerpers mit Querschnitt (Kreis oder n-Eck/phase) um die Achse A aus mehreren Fotos. -> (r je Hoehe [Umkreis], S [Fotos x Hoehen],
    bindend [Anzahl Fotos je Hoehe innerhalb 5 % des Ergebnisses]).
    einseitig=True (Silhouetten mit +-inf-Seiten): ein Foto SCHRANKT eine Hoehe nur ein, wenn sein Wert unter s_max liegt; Hoehen mit weniger als k
    einschraenkenden Fotos -> NaN (nicht gemessen, nicht erfunden)."""
    quer = querschnitt_einheit(n, phase); S = np.array([huelle_foto(B, A, zs, quer, s_max=s_max) for B in beob])
    r = np.sort(S, 0)[min(k, len(beob)) - 1]
    if einseitig: r = np.where((S < 0.999 * s_max).sum(0) >= k, r, np.nan)
    return r, S, (S <= 1.05 * r[None, :] + 1e-3).sum(0)


def huelle_restfehler(beob, A, zs, r, n=None, phase=0.0, zband=None):
    """Restfehler je Foto: Median der Kantenabweichung (|l - l_vorh| + |r - r_vorh|) / 2 in den Zeilen des Bands zband (z0, z1); Zeile nur in einem von beiden (Messung
    oder Vorhersage) zaehlt als Halbbreite daneben."""
    quer = querschnitt_einheit(n, phase); z0, z1 = zband or (zs[0], zs[-1]); out = []
    for B in beob:
        lp, rp = silhouette_vorhersage(B, A, zs, r, quer); sel = (B["zg"] >= z0) & (B["zg"] <= z1); gm = ~np.isnan(B["l"]) & ~np.isnan(B["r"]) & sel; gp = np.isfinite(lp) & sel
        if not (gm | gp).any(): out.append(np.nan); continue
        with np.errstate(invalid="ignore"):
            e = np.where(gm & gp, (np.abs(B["l"] - lp) + np.abs(B["r"] - rp)) / 2, np.where(gm, (B["r"] - B["l"]) / 2, (rp - lp) / 2))
            # einseitige Zeilen (eine Seite +-inf = vor Nachbarkoerper): nur die gemessene Seite; Zeile ohne messbare Seite zaehlt nicht
            fl, fr = np.isfinite(B["l"]), np.isfinite(B["r"]); dl = np.abs(B["l"] - lp); dr = np.abs(B["r"] - rp)
            e = np.where(gm & gp & ~(fl & fr), np.where(fl, dl, np.where(fr, dr, np.nan)), e)
            e = np.where(gm & ~gp & ~(fl & fr), np.where(fl | fr, np.where(fl, np.abs(B["l"]), np.abs(B["r"])), np.nan), e)
        e = e[gm | gp]; e = e[np.isfinite(e)]
        out.append(float(np.median(e)) if len(e) else np.nan)
    return np.array(out)


DZ_MAX = 0.8            # Registrierung: Hoehenversatz je Foto hoechstens +-0,8 m (Schwabentor-1122: Knauf je Foto 51,6..52,4 m, Krempensprung passend zum Hoehenwinkel
DZ_SCHRITT = 0.05       # versetzt - Kameralage an der Laternenspitze einige dm unsicher; Nadelende je Foto streute 2 m)
REST_AUSREISSER = 2.0   # Foto mit Restfehler > 2 x Median aller nach der Registrierung = Silhouette unvollstaendig (helles Blech vor hellem Himmel) -> raus aus der Huelle


def zentrieren(beob, band):
    """Seitlicher Versatz je Foto: Silhouettenmitte im Band (Median von (l + r) / 2) auf 0 - die Achse liegt quer zur Blickrichtung je Foto einige dm daneben
    (Kameralage/Achse aus der Wolke); Drehkoerper sind in der Fotoebene symmetrisch zur Achse (Kamera liegt in der Symmetrieebene). Mitte nur aus dem Koerper
    (Zeilen mit > 50 % der groessten Breite; Knauf/Nadel sind wenige Pixel breit). Danach SYMMETRISCH auf die schmalere Seite: ein Fremdkoerper neben einer Seite
    (Nachbardach/Turm hinter der Haube, commons_orig2__084) verbreitert nur eine Seite und darf die Huelle nicht tragen. Setzt B['mitte'], l = -w, r = w."""
    for B in beob:
        sel = (B["zg"] >= band[0]) & (B["zg"] <= band[1]) & np.isfinite(B["l"])
        if sel.any():
            wb = (B["r"] - B["l"]) / 2; sel &= wb >= 0.5 * np.nanmax(np.where(sel, wb, np.nan))
        c = float(np.median((B["l"][sel] + B["r"][sel]) / 2)) if sel.any() else 0.0
        w = np.minimum(c - B["l"], B["r"] - c); w = np.where(w > 0, w, np.nan)
        B["mitte"] = c; B["l"] = -w; B["r"] = w
    return beob


def registrieren(beob, A, zs, band, iters=3, k=K_HUELLE):
    """HOEHENVERSATZ je Foto (Kameralage-Fehler) durch Synthese: je Foto der Versatz dz (+-DZ_MAX), bei dem seine Silhouette am besten zur Huelle der ANDEREN Fotos passt
    (Runde 1 Median der Einzel-Huellen, danach k-kleinster Wert); Versatz-Median = 0. Danach Fotos mit Restfehler > REST_AUSREISSER x Median raus.
    Setzt B['dz'] und verschiebt zg. -> (beob [nur passende], weg {nr: Grund})."""
    quer = querschnitt_einheit()
    for B in beob: B.setdefault("zg0", B["zg"].copy()); B["dz"] = 0.0
    def setz(B, dz): B["zg"] = B["zg0"] + dz
    for it in range(iters):
        for B in beob: setz(B, B["dz"])
        S = np.array([huelle_foto(B, A, zs, quer) for B in beob]); neu = []
        for i, B in enumerate(beob):
            an = np.delete(S, i, 0); r = np.median(an, 0) if it == 0 else np.sort(an, 0)[min(k, len(an)) - 1]; best = (np.inf, 0.0)
            for d in np.arange(-DZ_MAX, DZ_MAX + 1e-9, DZ_SCHRITT):
                if abs(B["dz"] + d) > DZ_MAX + 1e-9: continue
                setz(B, B["dz"] + d); e = huelle_restfehler([B], A, zs, r, zband=band)[0]
                if e < best[0] - 1e-9: best = (e, d)
            setz(B, B["dz"]); neu.append(B["dz"] + best[1])
        m_ = float(np.median(neu))
        for B, d in zip(beob, neu): B["dz"] = round(d - m_, 3)
    for B in beob: setz(B, B["dz"])
    r, _, _ = drehprofil(beob, A, zs, k=k); e = huelle_restfehler(beob, A, zs, r, zband=band); me = float(np.nanmedian(e)); weg = {}
    for B, e_ in zip(beob, e):
        B["rest"] = round(float(e_), 3)
        if not np.isfinite(e_) or e_ > REST_AUSREISSER * me: weg[B["nr"]] = f"Restfehler {e_:.2f} m > {REST_AUSREISSER} x Median {me:.2f} (Silhouette unvollstaendig/Fremdkoerper)"
    gut = [B for B in beob if B["nr"] not in weg]
    if weg and len(gut) >= MIN_FOTOS: g2, w2 = registrieren(gut, A, zs, band, iters, k); return g2, {**weg, **w2}
    return beob, {}


def querschnitt_synthese(beob, A, zs, zband, r_ref, n_kand=N_KAND, phase_schritt=5.0, facetten=None, n_fallback=None, phase_fallback=0.0):
    """Querschnitt der Haube durch SYNTHESE: je Hypothese (Kreis, n-Eck x Lage) Sehstrahl-Huelle, Silhouetten neu abgebildet, Restfehler je Foto im Haubenband.
    Entscheidung (Formfamilie nur aus >= MIN_FAMILIE Fotos, CLAUDE.md):
     1. ein n-Eck ist in >= MIN_FAMILIE Fotos besser als der Kreis UND gepaarter t-Wert ueber t_grenze -> n-Eck (Fotobeleg Silhouette);
     2. sonst Facettenprobe eindeutig (facetten = dict(n, phase, eindeutig)) -> deren n-Eck (Fotobeleg Facettenstufen);
     3. sonst Kreis, wenn die Silhouette richtungsunabhaengig ist: Kreis-Restfehler <= (1 + RUND_TOL) x bestes n-Eck UND Ersatz-Eckenzahl n_fallback
        >= (1 + EGAL_TOL) x Kreis -> 'rund' als benannte ANNAHME;
     4. sonst n_fallback (Eckenzahl der Pfosten) als ANNAHME.
    -> dict(art 'rund'|'n-eck', n, phase, quelle, annahme, rest_kreis, rest_best, t, besser_fotos, kandidaten)."""
    rk, _, _ = drehprofil(beob, A, zs); ek = huelle_restfehler(beob, A, zs, rk, zband=zband); kand = {"kreis": round(float(np.nanmedian(ek)), 4)}; best = None
    for n in n_kand:
        for ph in np.arange(0.0, 360.0 / n, phase_schritt):
            r, _, _ = drehprofil(beob, A, zs, n, ph); e = huelle_restfehler(beob, A, zs, r, n, ph, zband=zband); m_ = float(np.nanmedian(e))
            if best is None or m_ < best[0]: best = (m_, n, float(ph), e)
            kand[str(n)] = round(min(kand.get(str(n), 9.0), m_), 4)
    d_ = ek - best[3]; d_ = d_[np.isfinite(d_)]; besser = int((d_ > 0).sum())
    t = float(d_.mean() / max(d_.std(ddof=1), 1e-6) * math.sqrt(len(d_))) if len(d_) > 1 else 0.0
    erg = dict(rest_kreis=kand["kreis"], rest_best=round(best[0], 4), n_best=best[1], phase_best=best[2], t=round(t, 2), t_grenze=t_grenze(len(d_)), besser_fotos=besser, kandidaten=kand,
               rest_kreis_rel=round(kand["kreis"] / max(r_ref, 1e-6), 3))
    if besser >= MIN_FAMILIE and t >= t_grenze(len(d_)):
        return dict(erg, art="n-eck", n=best[1], phase=best[2], annahme=None, quelle=f"Silhouetten-Synthese: {best[1]}-Eck in {besser} Fotos besser als Kreis (t {t:.2f})")
    if facetten and facetten.get("eindeutig"):
        return dict(erg, art="n-eck", n=int(facetten["n"]), phase=float(facetten["phase"]), annahme=None, quelle=f"Facettenstufen: {facetten['n']}-Eck eindeutig")
    r_fb = kand.get(str(n_fallback)) if n_fallback else None
    if kand["kreis"] <= (1 + RUND_TOL) * best[0] and (r_fb is None or r_fb >= (1 + EGAL_TOL) * kand["kreis"]):
        return dict(erg, art="rund", n=None, phase=0.0, quelle="Silhouette richtungsunabhaengig",
                    annahme=f"ANNAHME: Haube rund - Silhouette richtungsunabhaengig (Kreis-Restfehler {kand['kreis']:.3f} m, bestes {best[1]}-Eck {best[0]:.3f} m, Pfosten-{n_fallback}-Eck "
                            f"{r_fb if r_fb is None else round(r_fb, 3)} m); Facetten/Rippen nicht belegt (kein n-Eck in >= {MIN_FAMILIE} Fotos signifikant besser, t {t:.2f})")
    return dict(erg, art="n-eck", n=n_fallback, phase=phase_fallback, quelle="Pfosten",
                annahme=f"ANNAHME: Haube {n_fallback}-Eck wie die Pfosten (kein n-Eck belegt, Kreis nicht richtungsunabhaengig: Kreis {kand['kreis']:.3f} m, bestes {best[1]}-Eck {best[0]:.3f} m)")


GLATT_ZEILEN = 5        # Huellenprofil: gleitender Median ueber 5 Zeilen (0,25 m) - einzelne Zeilen mit Rauschen (Blechnaht, Mischpixel) kerben sonst die Haube;
                        # Knauf (0,4 m hoch) bleibt erhalten


def glaetten(r, k=GLATT_ZEILEN):
    """Gleitender Median (ungerade Fensterlaenge k) mit Randwiederholung."""
    r = np.asarray(r, float); h = k // 2
    if len(r) < k: return r
    p = np.r_[np.full(h, r[0]), r, np.full(h, r[-1])]; return np.array([np.median(p[i:i + k]) for i in range(len(r))])


def zeile(im, c, sb, A, q, z0, z1, xs, nz=7):
    """Helligkeit quer zur Blickrichtung (x-Gitter xs in m) als Median ueber nz Hoehen zwischen z0 und z1 (volle Fotoaufloesung, bilinear)."""
    import cv2, flaeche_ortho as FO
    rows = []
    for z in np.linspace(z0, z1, nz):
        X = np.c_[A[0] + xs * q[0], A[1] + xs * q[1], np.full(len(xs), z)]; p = FO.projektion(X, c)[0] * sb
        v = cv2.remap(im, p[:, 0].astype(np.float32).reshape(1, -1), p[:, 1].astype(np.float32).reshape(1, -1), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)[0].astype(float)
        aussen = (p[:, 0] < 0) | (p[:, 1] < 0) | (p[:, 0] > im.shape[1] - 1) | (p[:, 1] > im.shape[0] - 1); v[aussen] = np.nan
        rows.append(v)
    R = np.array(rows, float)
    return np.nanmedian(R, 0)


# ---- EINSEITIGE Silhouetten (23.11.2026, Treppentuermchen am Schwabentor) --------------------------------------------------------------------------
# Ein angebauter Rundkoerper steht in fast allen Fotos vor dem Hauptturm; frei vor Himmel ist meist nur EINE Seite und das Dach. Die Laternen-Silhouette
# (aeussere Ausdehnung beider Seiten) ist dort falsch: die Wand dahinter wuerde als Koerper zaehlen. Darum je Zeile vom Achsenpunkt nach aussen bis zum Himmel;
# reicht der Koerper bis ans Suchende (Nachbarwand, Bildrand) oder liegt hinter der Kante kein Himmel -> diese Seite +-inf (keine Schranke).
HIMMEL_LAUF_M = 0.10     # Kante = erste Stelle, ab der >= 0,10 m durchgehend Himmelsfarbe folgt (Draht/Oberleitung 1-3 cm bricht den Koerper nicht ab)
HIMMEL_DAHINTER = (0.10, 0.40)   # hinter der Kante (m) muss >= 80 % Himmel sein (Farbe UND, wenn vorhanden, Himmelsmaske), sonst Seite nicht messbar
HIMMEL_ANTEIL = 0.8
ACHSE_HALB_M = 0.05      # Achsenpunkt: +-5 cm um die Achse; Himmelsfarbe dort (und Maske) = Zeile ueber der Spitze (Koerper endet) -> NaN


def einseitig_halb(d, xs, himmel=None, schwelle=DUNKEL):
    """Silhouette EINER Zeile (einseitig): d = Abstand zur Himmelsfarbe (normiert, > schwelle = Koerper) auf dem Gitter xs (m quer, 0 = Achse); himmel = bool je xs aus der
    Himmelsmaske (None = nur Farbe). -> (l, r): Kante je Seite in m, -inf/+inf = Seite nicht messbar (Koerper bis zum Suchende oder kein Himmel dahinter),
    (nan, nan) = an der Achse Himmel (ueber der Spitze)."""
    d = np.nan_to_num(np.asarray(d, float), nan=0.0); xs = np.asarray(xs, float); dx = float(xs[1] - xs[0]); n = len(xs)
    sk = d <= schwelle
    if himmel is not None: sk_m = sk & np.asarray(himmel, bool)
    else: sk_m = sk
    a = np.abs(xs) <= ACHSE_HALB_M
    if a.any() and sk_m[a].mean() >= 0.5: return np.nan, np.nan
    i0 = int(np.argmin(np.abs(xs))); lauf = max(1, int(round(HIMMEL_LAUF_M / dx))); out = []
    for sg in (-1, 1):
        i = i0; kante = None
        while 0 <= i + sg * lauf < n:
            j = i + sg * np.arange(1, lauf + 1)
            if sk[j].all(): kante = i; break
            i += sg
        if kante is None: out.append(sg * np.inf); continue
        x_k = float(xs[kante]); hin = (sg * (xs - x_k) >= HIMMEL_DAHINTER[0]) & (sg * (xs - x_k) <= HIMMEL_DAHINTER[1])
        if hin.sum() < 2 or sk_m[hin].mean() < HIMMEL_ANTEIL: out.append(sg * np.inf); continue
        out.append(x_k + sg * dx / 2)
    return out[0], out[1]


MIN_KONTRAST = 30.0      # Koerper: Farbabstand zum Himmel mind. 30 Grauwerte UND mind. 4 x die Himmelsstreuung (80-%-Wert) - ein fester Anteil des 97-%-Werts der Szene
                         # machte braunen Stein vor blauem Himmel zu 'Himmel' (dunkle Erker-Untersicht hob den Massstab, Video psfY_vf_091_2)


def himmelsfarbe(pixel, maske, max_streuung=25.0, min_pixel=200):
    """Himmelsfarbe eines Fotos = Median der Pixel (N x 3), die die Himmelsmaske als Himmel fuehrt. None, wenn zu wenige oder die Maske nicht plausibel ist
    (80 % der 'Himmels'-Pixel weiter als max_streuung Grauwerte vom Median: Maske hat Fassaden/Baeume als Himmel gefuehrt, z. B. Video psfY_vf_095).
    -> (Farbe, Kontrastschwelle T): Koerper = Abstand > T."""
    P = np.asarray(pixel, float)[np.asarray(maske, bool)]; P = P[np.isfinite(P).all(1)] if len(P) else P
    if len(P) < min_pixel: return None
    m = np.median(P, 0)
    st = float(np.percentile(np.linalg.norm(P - m, axis=1), 80))
    if st > max_streuung: return None
    return m, max(MIN_KONTRAST, 4.0 * st)


def achse_suchen(beob, A, zs, s_max, halb=0.4, schritt=0.1, k=K_HUELLE, log=None):
    """Achse (x, y) eines Drehkoerpers aus EINSEITIGEN Silhouetten: Raster +-halb um A, dann fein (schritt/2). Guete = mittlere Zahl BINDENDER Fotos je Koerperhoehe
    (Foto-Schranke innerhalb 5 % der Huelle): an der wahren Achse beruehren die Sehstrahlen aus allen Richtungen denselben Kreis; neben ihr spreizen sie sich und nur
    die k engsten binden. (Restfehler taugt einseitig nicht: eine Kante weit draussen ist kein Widerspruch, nur ein Nachbarkoerper vor Himmel.) -> (A [2], Guete)."""
    def guete(Ak):
        r, S, bd = drehprofil(beob, Ak, zs, k=k, s_max=s_max, einseitig=True); ok = np.isfinite(r) & (r > 0.05)
        return float(np.mean(bd[ok])) if ok.sum() >= 3 else -np.inf
    best = (guete(np.asarray(A, float)), np.asarray(A, float))
    for h_, s_ in ((halb, schritt), (schritt, schritt / 2)):
        c0 = best[1].copy()
        for dx in np.arange(-h_, h_ + 1e-9, s_):
            for dy in np.arange(-h_, h_ + 1e-9, s_):
                Ak = c0 + [dx, dy]; g = guete(Ak)
                if g > best[0] + 1e-9: best = (g, Ak)
    if log: log(f"  Achse: {best[1].round(3).tolist()} (Start {np.round(A, 3).tolist()}), bindende Fotos je Hoehe {best[0]:.2f}")
    return best[1], best[0]


def einschnuerung(S, r, s_max, tol=0.1):
    """Je Foto: Anteil seiner einschraenkenden Hoehen, in denen es die Huelle um mehr als tol unterschreitet (Foto schmaler als der Koerper = Maske/Kamera falsch;
    je Hoehe duerfen das hoechstens k-1 Fotos sein). -> Array je Foto."""
    ok = np.isfinite(r)[None, :] & (S < 0.999 * s_max) & (r[None, :] > 0.05)
    eng = ok & (S < (1 - tol) * np.where(np.isfinite(r), r, 0)[None, :])
    return eng.sum(1) / np.maximum(ok.sum(1), 1)


def glaetten_nan(r, k=GLATT_ZEILEN):
    """Gleitender Median ueber die gemessenen Werte (NaN bleibt NaN, zaehlt im Fenster nicht)."""
    r = np.asarray(r, float); h = k // 2; out = np.full(len(r), np.nan)
    for i in range(len(r)):
        if not np.isfinite(r[i]): continue
        w = r[max(0, i - h):i + h + 1]; w = w[np.isfinite(w)]; out[i] = float(np.median(w))
    return out
