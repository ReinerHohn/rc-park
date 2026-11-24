#!/usr/bin/env python3
"""sohlbank_aus_fotos.py - SOHLBANK (vorspringende Leiste unter Fenster/Nische) aus den Einzelfoto-Orthos + SfM-Kameras (21.11.2026 spaet, Kettenstufe 'bauplan' nach laibung_aus_fotos).

Anlass (Schwabentor f00, Bild audit/neben_eigen__IMG_20261106_113231.jpg): unter beiden Rundbogennischen der Stadtseite liegt im Foto je eine dunkle waagerechte Leiste,
etwas breiter als die Nische; im Modell fehlte sie (kein Bauteil, kein Erkenner).
GEOMETRIE (KERNMETHODE: Masse aus Fotokanten + SfM-Kameras, >= 3 Fotos; wie laibung_aus_fotos, nur senkrecht): das Einzelfoto-Ortho legt jedes Foto auf die
Modellflaeche s (relief_fNN.png). Eine Kante in Hoehe z, die d VOR der Wand liegt, erscheint im Ortho bei z_obs; mit kappa = (z_obs - C_z)/(C_w - s) gilt EXAKT
      Y := C_z + kappa C_w = z + kappa d          (C = Kamerazentrum in Wandkoordinaten u, w, z)
also eine Gerade in kappa: Achsabschnitt = wahre Hoehe der Kante, Steigung = Abstand vor der Wand. Je Foto: das dunkle Band unter der Unterkante (Nische bzw. Fenster)
= tiefste Stelle des Zeilenprofils (Median ueber die Spalten neben dem Fenster), Oberkante/Unterkante = staerkster Hell-Dunkel-Sprung darueber/darunter (Teilpixel).
Beide Kanten je eine Ausgleichsgerade (Ausreisser > 3 MAD, mind. 1 cm, Bootstrap-Streuung): AUSKRAGUNG = groessere Steigung (die Vorderkante wandert, die Kante an der
Wand nicht), OBERKANTE = Achsabschnitt der oberen Kante, HOEHE = Abstand der Achsabschnitte. LAENGE: je Foto laeuft das Band von der Mitte nach aussen, bis es nicht
mehr dunkler als die Wand darunter ist; ein Ende zaehlt nur, wenn danach helle Wand folgt (sonst verdeckt: Mast, Kabel, Eckquader) - Median der Fotos.
Gilt nur mit >= --min_fotos Fotos, kappa-Spanne >= --k_spanne, 0 < Auskragung < 0,5 m, Streuung <= 50 % der Auskragung; sonst kein Eintrag (nichts erfinden).
Ausgabe: fenster_auto.json (je gemessenem Fenster 'sohlbank' {u0, u1, z0, z1, auskragung, fotos, ...}), Bericht sohlbank_aus_fotos.json, Bild sohlbank_<fid>.jpg.
Gebaut von bauteile.sohlbank (aus fenster_aus_json); Druckmindestmass dort (ANNAHME vermerkt).
Aufruf: sohlbank_aus_fotos.py <fenster_auto.json> <fassade_fein-ordner> <objekt.json> [--nur f00] [--aus ordner]
rc 0 = mindestens eine Sohlbank gemessen, 3 = keine (nichts geaendert).
NACHTRAG 24.11.2026 (WEG_HAND_ZU_KETTE Punkt 2: Sohlbank Nord fehlte, Band in 14 Fotos, Auskragung -0,025): Band in >= --min_fotos Fotos (Form belegt), aber
 Auskragung aus der Blickschraege unbestimmt -> annahme_bank: Auskragung = gemessene dunkle Stirnhoehe (Achsabschnitt, ANNAHME Profil so tief wie hoch),
 nur wenn sie <= der gesehenen Bandhoehe ist und die Enden in >= 3 Fotos frei liegen (sonst keine Bank); 'auskragung_quelle' nennt die ANNAHME.
"""
import sys, os, json, glob, argparse, numpy as np


def kamera_zentrum(K):
    """Kamerazentrum (Modellrahmen) aus einer K-Datei (rvec, t) - wie laibung_aus_fotos / foto_mass."""
    import cv2
    R, _ = cv2.Rodrigues(np.array(K["rvec"], float)); return -R.T @ np.array(K["t"], float)


def zone_von(q):
    """Unterkante und Breite, unter der die Sohlbank gesucht wird: Nische (aeussere Ebene) vor Fenster. Liefert (u0, u1, z_unten, fenster_u0, fenster_u1)."""
    N = q.get("nische") or q
    return float(N["u0"]), float(N["u1"]), float(N["z0"]), float(q["u0"]), float(q["u1"])


def _kante(p, z, i_lo, i_hi, vorz):
    """staerkster Sprung von p (Zeilenprofil, Index waechst mit z) zwischen i_lo..i_hi; vorz +1: nach oben heller (obere Bandkante), -1: nach unten heller.
    Teilpixel per Parabel. Liefert (z, staerke) oder None."""
    g = np.gradient(p) * vorz; i_lo = max(i_lo, 1); i_hi = min(i_hi, len(p) - 2)
    if i_hi <= i_lo: return None
    i = i_lo + int(np.argmax(g[i_lo:i_hi + 1]))
    if g[i] <= 0: return None
    a, b, c = g[i - 1], g[i], g[i + 1]; den = a - 2 * b + c; di = 0.5 * (a - c) / den if abs(den) > 1e-9 else 0.0
    return float(np.interp(i + np.clip(di, -0.5, 0.5), np.arange(len(z)), z)), float(g[i])


def band_messen(g, rast, zone, such=(0.35, 0.20), rand=None, kontrast_min=12.0, max_hoehe=0.25):
    """Dunkles waagerechtes Band unter der Zone im Graubild g (Wandraster rast = (u0, z1, zelle), 0 = kein Foto).
    zone = zone_von(q). Liefert dict(z_oben, z_unten, z_mitte, kontrast, u_links, u_rechts) - Enden None, wenn verdeckt/nicht messbar - oder None."""
    from scipy import ndimage as ndi
    u0r, z1r, c = rast; uL, uR, zu, fL, fR = zone; b = uR - uL
    rand = 0.5 + b if rand is None else rand                                  # Sohlbank kann weit ueber ein schmales Einzelfenster hinausreichen
    za, ze = zu - such[0], zu + such[1]; ua, ue = uL - rand, uR + rand
    i0, i1 = int(round((z1r - ze) / c)), int(round((z1r - za) / c)); j0, j1 = int(round((ua - u0r) / c)), int(round((ue - u0r) / c))
    if i0 < 0 or i1 > g.shape[0] or i1 - i0 < 10: return None
    j0, j1 = max(j0, 0), min(j1, g.shape[1])                                   # Suchbreite am Bildrand kappen (Enden dort gelten dann als nicht messbar)
    if j1 - j0 < 10: return None
    A = g[i0:i1, j0:j1].astype(np.float32); da = A > 0
    uu = u0r + (j0 + np.arange(A.shape[1]) + 0.5) * c; zz = z1r - (i0 + np.arange(A.shape[0]) + 0.5) * c
    # Spalten fuer das Zeilenprofil: innerhalb der Zone, aber neben dem Fenster (ueber der Sohlbank liegt dort die helle Nischensohle, nicht der dunkle Laden)
    sp = (uu > uL + 0.1 * b) & (uu < uR - 0.1 * b)
    neben = sp & ((uu < fL - 0.03) | (uu > fR + 0.03))
    if neben.sum() * c >= 0.2: sp = neben
    S = A[:, sp]; D = da[:, sp]
    if D.mean() < 0.9: return None
    Ag = ndi.gaussian_filter(np.where(da, A, np.median(A[da])), 1.0)
    p = np.median(Ag[:, sp], axis=1)[::-1]; z = zz[::-1]                     # Index waechst mit z
    imin = int(np.argmin(p)); h_max = max(2, int(max_hoehe / c))
    oben = _kante(p, z, imin, imin + h_max, +1); unten = _kante(p, z, imin - h_max, imin, -1)
    if oben is None or unten is None: return None
    ref = float(np.median(p[max(0, imin - int(0.25 / c)):max(1, imin - int(0.08 / c))])) if imin > int(0.1 / c) else float(np.median(p))
    kon = ref - float(p[imin])
    if kon < kontrast_min: return None
    zm = float(z[imin]); r_ = lambda zv: int(round((z1r - zv) / c - 0.5)) - i0
    ib0, ib1 = r_(oben[0]), r_(unten[0]) + 1; ib0, ib1 = max(0, min(ib0, r_(zm))), min(A.shape[0], max(ib1, r_(zm) + 1))
    iw0, iw1 = r_(unten[0] - 0.08), r_(unten[0] - 0.20)
    if iw1 <= iw0 or iw1 > A.shape[0]: return None
    # dunkelste Zeilen je Spalte (10. Perzentil): am Ende ist nur noch die schraeg verschobene Stirn dunkel - ein Median ueber das Band verlor sie (Laenge -35 %, synth.)
    q = np.percentile(Ag[ib0:ib1], 10, axis=0); w_ = np.median(Ag[iw0:iw1], axis=0); dunkel = (w_ - q) > 0.5 * kon
    wand = float(np.median(w_[sp]))
    def ende(richtung):
        jm = int(np.argmin(np.abs(uu - (uL + uR) / 2))); j = jm; frei = 0; letzte = None
        while 0 <= j < len(uu):
            if dunkel[j]: letzte = j; frei = 0
            else:
                frei += 1
                if frei * c >= 0.03: break
            j += richtung
        if letzte is None: return None
        k = [letzte + richtung * (1 + t) for t in range(int(0.08 / c))]; k = [x for x in k if 0 <= x < len(uu)]
        jenseits = q[k]; jw = w_[k]
        if len(jenseits) < max(2, int(0.05 / c)): return None             # Rand des Ausschnitts erreicht
        if np.median(jenseits) < wand - 0.3 * kon or np.median(jw) < wand - 0.3 * kon: return None      # danach keine helle Wand: verdeckt
        nx = letzte + richtung                                             # Teilpixel: wo (Wand - Band) die halbe Bandtiefe kreuzt (sonst 1-cm-Stufen in der Laenge)
        if not 0 <= nx < len(uu): return float(uu[letzte] + richtung * 0.5 * c)
        vl, vn = float(w_[letzte] - q[letzte]) - 0.5 * kon, float(w_[nx] - q[nx]) - 0.5 * kon
        return float(uu[letzte] + richtung * c * (vl / (vl - vn) if vl - vn > 1e-6 else 0.5))
    return dict(z_oben=round(oben[0], 4), z_unten=round(unten[0], 4), z_mitte=round(zm, 4), kontrast=round(kon, 1), u_links=ende(-1), u_rechts=ende(+1))


def gerade(ka, Y, min_n, gruppe=None, rng=None):
    """Y = a_gruppe + kappa d (gemeinsame Steigung d, je Gruppe eigener Achsabschnitt), robust (2 Runden Ausreisser > 3 MAD, mind. 1 cm) + Bootstrap.
    Liefert dict(a (Achsabschnitt der ersten Gruppe), a_je, d, streuung_d, n, maske) oder None."""
    ka = np.asarray(ka, float); Y = np.asarray(Y, float); G = np.zeros(len(ka), int) if gruppe is None else np.unique(np.asarray(gruppe), return_inverse=True)[1]
    if len(ka) < min_n: return None
    ng = int(G.max()) + 1
    def A_(m): return np.column_stack([(G[m] == i).astype(float) for i in range(ng)] + [ka[m]])
    def fit(m): x, *_ = np.linalg.lstsq(A_(m), Y[m], rcond=None); return x
    m = np.ones(len(ka), bool); x = fit(m)
    for _ in range(2):
        r = Y - A_(np.ones(len(ka), bool)) @ x; mad = float(np.median(np.abs(r[m]))); m2 = np.abs(r) <= max(3 * 1.4826 * mad, 0.01)
        if m2.sum() < min_n or (m2 == m).all(): break
        m = m2; x = fit(m)
    rng = rng or np.random.default_rng(0); idx = np.flatnonzero(m); bs = []
    for _ in range(200):
        i_ = rng.choice(idx, len(idx)); mm = np.isin(np.arange(len(ka)), i_)
        if all((G[mm] == i).any() for i in range(ng)) and all(np.ptp(ka[mm & (G == i)]) > 1e-6 or (mm & (G == i)).sum() == 1 for i in range(ng)) and np.ptp(ka[mm]) > 1e-6: bs.append(fit(mm)[-1])
    return dict(a=float(x[0]), a_je=[float(v) for v in x[:-1]], d=float(x[-1]), streuung_d=float(np.std(bs)) if bs else None, n=int(m.sum()), maske=m)


def punkte(bilder, kam, rel, rast, q, a):
    """Je Foto das dunkle Band unter Fenster/Nische q (band_messen) mit kappa, Y, Bandhoehe H und - wo beide Enden frei sind - Laenge und Ku. Liefert Liste
    (nach Kontrastpruefung; leer = nicht genug Fotos)."""
    zone = zone_von(q); P = []
    for name, g in bilder:
        if name not in kam: continue
        Cu, Cw, Cz = kam[name]
        if Cw < 2.0: continue
        r = band_messen(g, rast, zone)
        if r is None: continue
        s = 0.0
        if rel is not None:                                                  # Modellflaeche an der Sohlbank (Ortho liegt auf ihr, nicht auf der Wandebene)
            u0r, z1r, c = rast; i = int(round((z1r - r["z_mitte"]) / c)); j0, j1 = int(round((zone[0] - u0r) / c)), int(round((zone[1] - u0r) / c))
            if 0 <= i < rel.shape[0]:
                R_ = rel[max(0, i - 3):i + 4, max(0, j0):j1]; R_ = R_[R_ > 0]
                if R_.size: s = float(np.median(R_)) / 1000.0 - 10.0
        p = dict(foto=name, s=round(s, 3), **r)
        for k in ("oben", "unten"):
            ka = (r["z_" + k] - Cz) / (Cw - s); p["kappa_" + k] = round(ka, 5); p["Y_" + k] = round(Cz + ka * Cw, 4)
        # DIFFERENZ JE FOTO (Lauf 21.11. spaet, Schwabentor f00): die Einzelfoto-Orthos liegen je Foto um einige cm verschieden (Registrierfehler der Kamera) - die
        # Kantenlage selbst gab Steigung -0,19 m (unplausibel). Die BANDHOEHE im selben Foto ist davon frei: von unten sieht man Unterseite + Stirn, also
        # H = Y_oben - Y_unten = (z_oben_vorn - z_unten_wand) + kappa d  -> Steigung = Auskragung d, Achsabschnitt = dunkle Stirnhoehe (0 = nur die Unterseite ist dunkel).
        p["kappa"] = round(0.5 * (p["kappa_oben"] + p["kappa_unten"]), 5); p["H"] = round(p["Y_oben"] - p["Y_unten"], 4)
        # LAENGE JE FOTO (gleicher Grund, waagerecht): ein Ende, dessen Vorderecke von der Kamera weg zeigt, wandert um |kappa_u| d nach aussen
        # (kappa_u = (u_ende - C_u)/(C_w - s); linkes Ende bei kappa_u < 0, rechtes bei > 0), das andere bleibt an der Wandecke: Laenge_obs = Laenge + d Ku,
        # Ku = max(0, -kappa_links) + max(0, kappa_rechts). Verschiebung des Orthos hebt sich in der Differenz auf; Unschaerfe verschiebt beide Enden gleich.
        if r["u_links"] is not None and r["u_rechts"] is not None:
            kl = (r["u_links"] - Cu) / (Cw - s); kr = (r["u_rechts"] - Cu) / (Cw - s)
            p["Ku"] = round(max(0.0, -kl) + max(0.0, kr), 5); p["laenge"] = round(r["u_rechts"] - r["u_links"], 4)
        P.append(p)
    if len(P) < a.min_fotos: return []
    ko = np.array([p["kontrast"] for p in P]); P = [p for p in P if p["kontrast"] >= a.kontrast_rel * np.median(ko)]
    return P if len(P) >= a.min_fotos else []


def auskragung(PP, a):
    """Gemeinsame Auskragung fuer GESCHWISTER-Sohlbaenke (PP = Liste der Punktlisten; gleiche Wand, gleiche Hoehe, aehnliche Laenge - wie die gemeinsame
    Laibungstiefe in laibung_aus_fotos): je Fenster eigener Achsabschnitt, Steigung gemeinsam. Zwei unabhaengige Messungen (Bandhoehe gegen kappa, Laenge gegen Ku);
    gueltig ist jede mit 0 < d < max, Streuung <= 50 % von d, Blickspanne >= k_spanne, >= min_fotos; beide gueltig -> inverse Varianz.
    Liefert dict(d, streuung, aus, ...) oder dict(fehler, ...)."""
    erg = {}; kand = []
    for name_, kx, ky in (("bandhoehe", "kappa", "H"), ("laenge", "Ku", "laenge")):
        X, Y, G = [], [], []
        for gi, P in enumerate(PP):
            for p in P:
                if kx in p: X.append(p[kx]); Y.append(p[ky]); G.append(gi)
        sp_ = float(np.ptp(X)) if X else 0.0; f_ = gerade(X, Y, a.min_fotos, G) if sp_ >= a.k_spanne and len(set(G)) >= 1 else None
        erg["auskragung_" + name_] = None if f_ is None else dict(d=round(f_["d"], 3), streuung=round(f_["streuung_d"] or 0, 3), fotos=f_["n"], spanne=round(sp_, 3), achsabschnitt=[round(v, 3) for v in f_["a_je"]])
        if f_ is None or f_["streuung_d"] is None: continue
        if 0.0 < f_["d"] < a.max_auskragung and f_["streuung_d"] <= 0.5 * f_["d"]: kand.append((name_, f_["d"], max(f_["streuung_d"], 0.005), f_["n"]))
    if not kand: return dict(erg, fehler="Auskragung aus keiner Messung plausibel (Bandhoehe %s, Laenge %s)" % (erg["auskragung_bandhoehe"], erg["auskragung_laenge"]))
    w_ = np.array([1.0 / x[2] ** 2 for x in kand]); d = float(np.sum(w_ * np.array([x[1] for x in kand])) / w_.sum()); sd = float(1.0 / np.sqrt(w_.sum()))
    return dict(erg, d=d, streuung=sd, aus=[x[0] for x in kand], fotos=max(x[3] for x in kand))


def abschluss(P, kam, zone, A, a):
    """Lage/Laenge einer Sohlbank mit der Auskragung A (auskragung()): Unterkante = Median Y_unten (Wandkante, wandert nicht), Oberkante = Median (Y_oben - kappa d),
    Enden je Foto um die Auswanderung der Vorderecke zurueckgerechnet, Median (verdeckte Enden zaehlen nicht). Liefert dict(u0, u1, z0, z1, ...) oder dict(fehler)."""
    d = A["d"]; z_b = float(np.median([p["Y_unten"] for p in P])); z_t = float(np.median([p["Y_oben"] - p["kappa"] * d for p in P]))
    ku_ = lambda p, u: (u - kam[p["foto"]][0]) / (kam[p["foto"]][1] - p["s"])
    L = [p["u_links"] + max(0.0, -ku_(p, p["u_links"])) * d for p in P if p["u_links"] is not None]
    R = [p["u_rechts"] - max(0.0, ku_(p, p["u_rechts"])) * d for p in P if p["u_rechts"] is not None]
    erg = dict(hoehe_streuung=round(float(np.std([p["Y_unten"] for p in P])), 3), laenge_fotos=[len(L), len(R)])
    if len(L) < a.min_fotos or len(R) < a.min_fotos: return dict(erg, fehler=f"Laenge nur aus {len(L)}/{len(R)} Fotos (links/rechts) messbar")
    u0, u1 = float(np.median(L)), float(np.median(R))
    if u1 - u0 < 0.5 * (zone[1] - zone[0]): return dict(erg, fehler=f"Band {u1 - u0:.2f} m kuerzer als die halbe Zone")
    return dict(erg, u0=round(u0, 3), u1=round(u1, 3), u_streuung=[round(float(np.std(L)), 3), round(float(np.std(R)), 3)], z1=round(max(z_t, z_b), 3), z0=round(z_b, 3))


def geschwister(PP, zonen, dz=0.15, breite=0.25):
    """Gruppen von Fenstern derselben Wand, deren Sohlbank auf gleicher Hoehe (Median z_mitte +- dz) liegt und deren Zone aehnlich breit ist (+- breite). Liste von Indexlisten."""
    zm = [float(np.median([p["z_mitte"] for p in P])) if P else None for P in PP]; frei = [i for i in range(len(PP)) if PP[i]]; gr = []
    while frei:
        i = frei.pop(0); g = [i]
        for j in list(frei):
            bi, bj = zonen[i][1] - zonen[i][0], zonen[j][1] - zonen[j][0]
            if abs(zm[i] - zm[j]) <= dz and abs(bi - bj) <= breite * max(bi, bj): g.append(j); frei.remove(j)
        gr.append(g)
    return gr


def annahme_bank(P, kam, zone, A, gi, a, e):
    """24.11.2026 (WEG_HAND_ZU_KETTE Punkt 2; Nutzer 'Alle Masse muessen aus Fotos kommen', Plan 'belegte Form nie verwerfen'): das dunkle Band ist in >= min_fotos
    Fotos da (Form belegt), nur die AUSKRAGUNG laesst sich aus der Blickschraege nicht bestimmen (Steigung negativ/unsicher). Dann ANNAHME aus denselben Fotos:
    Auskragung = dunkle STIRNHOEHE (Achsabschnitt der Bandhoehe bei kappa 0 = Frontalsicht; ANNAHME Profil etwa so tief wie hoch), nur <= gesehene
    Bandhoehe; Lage/Hoehe/Laenge wie gemessen (abschluss: Enden frei in >= 3 Fotos, sonst keine Bank - Schattenkante ist keine Leiste). Nie eine feste Zahl."""
    ab = ((A.get("auskragung_bandhoehe") or {}).get("achsabschnitt") or [])
    hs = ab[gi] if gi < len(ab) else None; Hm = float(np.median([p["H"] for p in P]))
    # Gegenprobe 24.11. (Kopie 1122, f04 Tuer: Achsabschnitt 0,41 bei Bandhoehe ~0,2): die Stirn ist in Frontalsicht nie hoeher als das gesehene Band
    if hs is None or not (0.0 < hs <= min(Hm + 0.01, a.max_auskragung)):
        return dict(e, fehler=e.get("fehler", "") + f"; keine ANNAHME: Stirnhoehe {hs} nicht in 0..Bandhoehe {Hm:.3f}", punkte=P)
    bh = A.get("auskragung_bandhoehe") or {}
    if bh.get("d") is not None and bh.get("streuung") is not None and bh["streuung"] <= 0.02 and bh["d"] <= 2 * max(bh["streuung"], 0.005):
        return dict(e, fehler=e.get("fehler", "") + f"; keine ANNAHME: Fotos messen KEINE Auskragung ({bh['d']:+.3f} +- {bh['streuung']:.3f} m, flaches dunkles Band)", punkte=P)
    z_b = float(np.median([p["Y_unten"] for p in P]))
    if z_b + hs > zone[2] + 0.03:                                            # Band reicht in die Oeffnung/Nische hinein = deren Dunkel, keine Leiste darunter (test_sohlbank C)
        return dict(e, fehler=e.get("fehler", "") + f"; keine ANNAHME: Bandoberkante {z_b + hs:.2f} ueber der Unterkante {zone[2]:.2f} der Zone", punkte=P)
    d, her = float(hs), f"Stirnhoehe {hs:.3f} m (Achsabschnitt Bandhoehe gegen kappa, {len(P)} Fotos; Band im Median {Hm:.3f} m hoch)"
    r = abschluss(P, kam, zone, dict(d=d), a)
    if "fehler" in r: return dict(e, fehler=e.get("fehler", "") + "; keine ANNAHME: " + r["fehler"], punkte=P)     # Enden muessen aus >= 3 Fotos kommen (echte Leiste, kein Schatten)
    r["z0"] = round(z_b, 3); r["z1"] = round(z_b + hs, 3)                     # Hoehe = Stirn (Frontalsicht), passend zur ANNAHME
    laenge_q = f"Fotoenden {r.get('laenge_fotos')}"
    e = {k: v for k, v in e.items() if k != "fehler"}
    return dict(e, **r, auskragung=round(d, 3), auskragung_streuung=None, auskragung_aus=["ANNAHME"], fotos=len(P),
                auskragung_quelle=f"ANNAHME: Auskragung = {her}; Blickschraege unbestimmt ({A.get('fehler', '')[:120]}); Laenge: {laenge_q}", punkte=P)


def sohlbank_messen(bilder, kam, rel, rast, fenster, a):
    """Alle Fenster einer Wand -> je Fenster dict(u0, u1, z0, z1, auskragung, ...) oder dict(fehler, punkte)."""
    PP = [punkte(bilder, kam, rel, rast, q, a) for q in fenster]; Z = [zone_von(q) for q in fenster]; out = [None] * len(fenster)
    for i, P in enumerate(PP):
        if not P: out[i] = dict(fehler=f"weniger als {a.min_fotos} Fotos zeigen ein dunkles Band", punkte=P)
    for g in geschwister(PP, Z):
        A = auskragung([PP[i] for i in g], a)
        for gi, i in enumerate(g):
            e = dict(A, geschwister=len(g)); e.pop("d", None); e.pop("streuung", None)
            if "fehler" in A:
                out[i] = dict(e, punkte=PP[i])
                if len(PP[i]) >= a.min_fotos: out[i] = annahme_bank(PP[i], kam, Z[i], A, gi, a, e)
                continue
            e.update(abschluss(PP[i], kam, Z[i], A, a), auskragung=round(A["d"], 3), auskragung_streuung=round(A["streuung"], 3), auskragung_aus=A["aus"])
            out[i] = dict(e, punkte=PP[i])
    return out


def bild(pfad, tafeln):
    """Je Fenster Bandhoehe H gegen kappa (Ausreisser grau) mit Ausgleichsgerade; Steigung = Auskragung, Achsabschnitt = dunkle Stirnhoehe."""
    import cv2
    W_, H_ = 360, 260; out = []
    for name, e in tafeln:
        im = np.full((H_, W_, 3), 255, np.uint8); P = [p for p in e.get("punkte", []) if "H" in p]
        if P:
            K = np.array([[p["kappa"], p["H"]] for p in P]); k0, k1 = 0.0, K[:, 0].max() + 0.05; y0, y1 = 0.0, K[:, 1].max() + 0.03
            X = lambda v: int(20 + (v - k0) / (k1 - k0 + 1e-9) * (W_ - 40)); Yp = lambda v: int(H_ - 25 - (v - y0) / (y1 - y0 + 1e-9) * (H_ - 50))
            for p, r in zip(P, K): cv2.circle(im, (X(r[0]), Yp(r[1])), 3, (170, 170, 170) if p["foto"] in e.get("ausreisser", []) else (200, 0, 0), -1)
            if "auskragung" in e:
                dd = e["auskragung"]; h0 = float(np.median(K[:, 1] - K[:, 0] * dd)); cv2.line(im, (X(k0), Yp(h0 + k0 * dd)), (X(k1), Yp(h0 + k1 * dd)), (0, 0, 220), 1)
        cv2.putText(im, name[:44], (5, 14), 0, 0.4, (0, 0, 0), 1)
        cv2.putText(im, (f"Auskragung {e['auskragung']:.3f} +-{e['auskragung_streuung'] if e.get('auskragung_streuung') is not None else 'ANNAHME'} m, {e['fotos']} Fotos" if "auskragung" in e else "") + (" " + e["fehler"][:40] if "fehler" in e else ""), (5, 30), 0, 0.38, (0, 0, 160), 1)
        cv2.putText(im, "kappa -> Bandhoehe H (Steigung = Auskragung)", (5, H_ - 6), 0, 0.35, (90, 90, 90), 1); out.append(im)
    if out: cv2.imwrite(pfad, np.hstack(out))


def main():
    import cv2
    ap = argparse.ArgumentParser(); ap.add_argument("fenster"); ap.add_argument("fein"); ap.add_argument("objekt"); ap.add_argument("--nur", nargs="*"); ap.add_argument("--aus")
    ap.add_argument("--min_fotos", type=int, default=3, help="Masse aus >= 3 Fotos (CLAUDE.md)")
    ap.add_argument("--k_spanne", type=float, default=0.1, help="Spanne der Blickschraege kappa ueber die Fotos (sonst ist die Steigung nicht bestimmt)")
    ap.add_argument("--kontrast_rel", type=float, default=0.4, help="Fotos mit Bandkontrast < 40 %% des Medians (unscharf, Gegenlicht) zaehlen nicht")
    ap.add_argument("--max_auskragung", type=float, default=0.5)
    a = ap.parse_args()
    aus = a.aus or os.path.dirname(os.path.abspath(a.fenster)); os.makedirs(aus, exist_ok=True)
    J = json.load(open(a.fenster)); FF = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    mp = os.path.join(os.path.dirname(os.path.abspath(a.objekt)), "messprotokoll")
    bericht = {}; n_ok = 0
    for fid, F in J.items():
        if not isinstance(F, dict) or not F.get("fenster") or (a.nur and fid not in a.nur): continue
        ed = os.path.join(a.fein, f"ortho_{fid}_einzeln")
        if fid not in FF or not os.path.isdir(ed): bericht[fid] = "keine Einzelfoto-Orthos"; continue
        rs = FF[fid]["raster"]; rast = (rs["u0"], rs["z1"], rs["zelle"]); o = np.array(FF[fid]["o"], float); d = np.array(FF[fid]["d"], float); n = np.array(FF[fid]["n"], float)
        rp = os.path.join(a.fein, f"relief_{fid}.png"); rel = cv2.imread(rp, cv2.IMREAD_UNCHANGED) if os.path.exists(rp) else None
        U0 = min(zone_von(q)[0] for q in F["fenster"]) - 1.0; U1 = max(zone_von(q)[1] for q in F["fenster"]) + 1.0
        Z0 = min(zone_von(q)[2] for q in F["fenster"]) - 1.0; Z1 = max(zone_von(q)[2] for q in F["fenster"]) + 1.0
        kam, bilder = {}, []
        for p in sorted(glob.glob(os.path.join(ed, "*.png"))):
            name = os.path.basename(p)[:-4]; kf = os.path.join(mp, f"K-{name}.json")
            if not os.path.exists(kf): continue
            K = json.load(open(kf)).get("kamera")
            if not isinstance(K, dict) or "rvec" not in K: continue
            C = kamera_zentrum(K); kam[name] = (float((C[:2] - o) @ d), float((C[:2] - o) @ n), float(C[2]))
            g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            if g is None: continue
            i0, i1 = max(0, int((rast[1] - Z1) / rast[2])), int((rast[1] - Z0) / rast[2]); j0, j1 = max(0, int((U0 - rast[0]) / rast[2])), int((U1 - rast[0]) / rast[2])
            G = np.zeros_like(g); G[i0:i1, j0:j1] = g[i0:i1, j0:j1]; bilder.append((name, G))     # nur der Streifen um die Unterkanten (gleiches Raster)
        L = []; tafel = []
        for q, e in zip(F["fenster"], sohlbank_messen(bilder, kam, rel, rast, F["fenster"], a)):
            e["fenster"] = [q["u0"], q["u1"], q["z0"], q["z1"]]; L.append(e); tafel.append((f"{fid} u {q['u0']:+.2f}..{q['u1']:+.2f}", e))
            if "fehler" in e: print(f"{fid} u {q['u0']:+.2f}: keine Sohlbank - {e['fehler']}"); q.pop("sohlbank", None); continue
            q["sohlbank"] = {k: e.get(k) for k in ("u0", "u1", "z0", "z1", "auskragung", "auskragung_streuung", "fotos", "geschwister", "auskragung_aus", "auskragung_bandhoehe", "auskragung_laenge", "u_streuung", "laenge_fotos", "auskragung_quelle")}
            q["sohlbank"]["quelle"] = (f"Fotos: dunkles Band unter der Unterkante (Einzelfoto-Orthos + SfM-Kameras), Auskragung aus {'+'.join(e['auskragung_aus'])} gegen die Blickschraege, "
                                       f"{e['fotos']} Fotos, {e['geschwister']} Geschwister gemeinsam (tools/sohlbank_aus_fotos.py)" + (" - " + e["auskragung_quelle"] if e.get("auskragung_quelle") else ""))
            n_ok += 1; print(f"{fid} u {q['u0']:+.2f}: SOHLBANK u {e['u0']:+.2f}..{e['u1']:+.2f} z {e['z0']:.2f}..{e['z1']:.2f} Auskragung {e['auskragung']:.3f} " + (f"+-{e['auskragung_streuung']:.3f} m" if e.get('auskragung_streuung') is not None else "m ANNAHME") + f" ({e['fotos']} Fotos)")
        bericht[fid] = L; bild(os.path.join(aus, f"sohlbank_{fid}.jpg"), tafel)
    json.dump(bericht, open(os.path.join(aus, "sohlbank_aus_fotos.json"), "w"), indent=1, ensure_ascii=False, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x))
    if not n_ok: print("keine Sohlbank gemessen"); return 3
    json.dump(J, open(os.path.join(aus, os.path.basename(a.fenster)), "w"), indent=1); print(f"-> {n_ok} Sohlbaenke gemessen"); return 0


if __name__ == "__main__": sys.exit(main())
