#!/usr/bin/env python3
"""quader_raster.py - Quaderwerk als BAUPLAN aus dem Wandbild: Lagen + Fugen aus mehreren entzerrten Einzelfotos, je Stein eine ebene Stirnflaeche
mit GEMESSENEM Vorsprung (Median der Tiefe im Stein), Fugen als druckbare Rillen (21.11.2026, Schwabentor-1120 Stadtseite).

ANLASS (Nutzer 21.11.: "Das ist noch nicht gut", Bild audit/neben_eigen__IMG_20261106_113231.jpg, Lauf 1121s): unterer Turm im Foto klares Quadermauerwerk,
im Modell klumpige 'geschmolzene' Flaeche; Eckquader oben unruhiges Rauschen statt klarer Bloecke. URSACHE (gemessen an relief/w01_*, w03_*):
  (1) gebaut wird jedes Relief 1:1 als Hoehenfeld (relief_einsatz.koerper). In den Feinreliefs (mono/misch, z < 10 m) liegt die Fugenstruktur bei
      +-2 cm (Hochpass 5 cm) = 0,2 mm H0, die Steingrossen Beulen aus Scan-Tiefpass / Mono-Hochpass bei +-9..11 cm (Tiefpass 20 cm) = 1 mm H0.
      Gedruckt/gerendert sieht man die Beulen, nicht die Fugen. Rillen gemessen p90 0,4-0,6 cm, p99 1,2-3,6 cm = 0,1-0,4 mm H0 < Mindestmass 0,8 mm.
  (2) steine_aus_foto (z >= 10 m, Eckquader): Fuge 3 cm breit/3 cm tief (0,34 mm H0, nach 3-cm-Abtastung flacher), dazu ERFUNDENE Bosse 4 cm je Stein
      (Zufallskissen 0,6-1,2) + Zufallsrauhigkeit, Steinniveau = 30-cm-geglaettetes Scan-Relief -> Steinflaechen rauschen staerker als die Fugen tief sind.
  (3) Quader-Tor je GANZER Wand: w02 (Mittelfeld Stadtseite, oben Putz/Uhr, unten Quader um den Torbogen) fiel durch (8 % < 12 %) -> unten rohes Netz-Relief.
GENERISCH (WANDBILD = BAUPLAN, keine Musterteile, keine Handwerte):
  fugen_antwort(bilder)          Mehrfoto-Antwort: je Foto oertlich normierter Hochpass (Fuge = schmale Abweichung), auf +-3 gekappt, Mittel ueber die Fotos,
                                 die die Zelle sehen (>= min_fotos) - ein Kabel/Schild in EINEM Foto kann die Mehrheit nicht ueberstimmen.
  raster_segmentieren(...)       Schichtmodell je Steinfeld (wie steine_aus_foto: Lagerfugen = Spitzen im Zeilenprofil, Stossfugen = Spitzen im Spaltenprofil je Lage,
                                 Polaritaet hell/dunkel nicht vorgegeben). Tor je Steinfeld: >= 3 Lagen 25-70 cm hoch, sonst keine Steine (kein Ziegelraster erfinden).
  quader_relief(tiefe, lab, ...) Stirnflaeche je Stein = Median der gueltigen Tiefe im Stein (Stein ohne Messung: naechster gemessener Stein), Fuge = Rille mit
                                 Breite >= MINMM x SCALE (0,8 mm H0 = 7 cm) und Tiefe >= max(gemessen, 0,5 x MINMM x SCALE) unter dem niedrigeren Nachbarstein, flacher Grund.
  eckquader_bloecke(lab, ...)    Steine am Wandende = Eckquader mit GEMESSENER Hoehe/Laenge (lang/kurz aus dem Median der Laengen, Zahnung = Wechselanteil).
  quader_auf_relief(npz, ffn)    alles zusammen fuer ein Relief der Fassaden-Kette (Einzelbilder fassade_fein/ortho_<fid>_einzeln, Steinflaeche = glatt_karte 'quader');
                                 schreibt <relief>_q.npz/.jpg. fassaden_kette.anbauen nutzt es fuer jedes gebaute Relief (OHNE_QUADER_RASTER=1 = alter Stand).
ANNAHMEN: Rillenbreite/-tiefe sind DRUCKMASS (echte Fugen 1-3 cm), Stirnflaeche eben (Bossen nicht gemessen). Nur numpy/scipy/PIL (Generator-Umgebung, kein cv2).
Probe: quader_raster.py <relief.npz> <fassade_fein-ordner> [--aus x_q.npz]
"""
import sys, os, json, glob, argparse, numpy as np
from scipy import ndimage as ndi

SCALE = float(os.environ.get("SCALE", "87")); MINMM = float(os.environ.get("MINMM", "0.8"))


def druckmass(massstab=None, min_mm=None):
    """(Rillenbreite, Rillenmindesttiefe) in m am Bauwerk: Breite = min_mm x Massstab, Tiefe = halbe Breite (ANNAHME Druckmass)."""
    s = float(massstab or SCALE); m = float(min_mm or MINMM); return m * s / 1000.0, 0.5 * m * s / 1000.0


def _nf(x, w, s):
    """normierte Gauss-Faltung nur ueber gueltige Pixel (w = 0/1-Gewicht): schwarze Verdeckungsflecken der Einzelbilder zaehlen nicht."""
    return ndi.gaussian_filter(x * w, s, truncate=3.0) / np.maximum(ndi.gaussian_filter(w, s, truncate=3.0), 1e-3)


def fugen_antwort(bilder, c, ort=0.10, streu=0.15, kappe=3.0, min_fotos=2):
    """bilder: Liste von Grauwertbildern (H x W, 0 = nicht gesehen) auf DEMSELBEN Wandraster (Zelle c m). Je Foto: (1-cm-geglaettet - Ortsmittel ort m) /
    oertliche Streuung (streu m) -> +-kappe gekappt; Mittel ueber die Fotos, die die Zelle sehen. Liefert (antwort, anzahl); antwort = 0 bei < min_fotos."""
    summe = None; n = None
    for g in bilder:
        g = np.asarray(g, np.float32); da = (g > 0).astype(np.float32)
        if da.sum() < 100: continue
        gs = _nf(g, da, 1.0); m = _nf(g, da, ort / c); sd = np.sqrt(np.maximum(_nf((g - m) ** 2, da, streu / c), 0.0))
        ok = (da > 0) & (ndi.gaussian_filter(da, ort / c, truncate=3.0) > 0.5)
        # Streuung nach unten begrenzt (halber Median des Fotos): sonst blaest die oertliche Normierung das Bildrauschen auf glatten Flaechen (Putz, Wandgemaelde)
        # auf volle Fugenstaerke auf und das Stein-Tor (Randstuetze) sieht dort 'Fugen' (synthetischer Test, Gemaelde zu 96 % Steine).
        boden = max(2.0, 0.5 * float(np.median(sd[ok]))) if ok.any() else 2.0
        r = np.where(ok, np.clip((gs - m) / np.maximum(sd, boden), -kappe, kappe), 0.0)
        summe = r if summe is None else summe + r; n = ok.astype(np.int32) if n is None else n + ok
    if summe is None: return None, None
    return np.where(n >= min_fotos, summe / np.maximum(n, 1), 0.0).astype(np.float32), n


def raster_segmentieren(antwort, stein, c, lager_min=0.16, stoss_min=0.20, schwelle=2.4, schicht=(0.25, 0.70), min_lagen=3, min_feld_m2=0.3, min_stein_m2=0.01,
                        rechteckig=0.6, max_laenge=2.5, stuetze=0.08):
    """Schichtmodell je zusammenhaengendem Steinfeld. antwort: Fugenantwort (fugen_antwort, + = heller als Umgebung), stein: Steinflaeche (bool).
    Liefert (lab, fuge, info): lab = Steinnummer je Zelle (0 = keine/Fuge), fuge = Fugenlinien (1 Zelle), info = dict(polaritaet, lagen_m, felder, felder_verworfen)."""
    from scipy.signal import find_peaks
    stein = np.asarray(stein, bool); a = np.asarray(antwort, np.float32)
    o_ = max(3, int(round(0.09 / c)) | 1); komp, nk = ndi.label(ndi.binary_opening(stein, np.ones((o_, o_))))
    best = None
    for name, vz in (("hell", 1.0), ("dunkel", -1.0)):
        r = vz * a; fuge = np.zeros(stein.shape, bool); guete = 0.0; lagen_m = []; ok_f = 0; weg_f = 0
        for ki in range(1, nk + 1):
            m = komp == ki
            if m.sum() * c * c < min_feld_m2: continue
            ys, xs = np.nonzero(m); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; mm = m[y0:y1, x0:x1]; rr = np.where(mm, r[y0:y1, x0:x1], 0.0)
            nrow = mm.sum(1); p = ndi.gaussian_filter1d(rr.sum(1) / np.maximum(nrow, 1), 1.0); p[nrow < max(3, int(0.15 / c))] = 0
            if p.std() <= 1e-6: weg_f += 1; continue
            lager, pr = find_peaks(p, distance=max(1, int(lager_min / c)), prominence=schwelle * 0.5 * float(p.std()))
            sch = [d_ * c for d_ in np.diff(lager) if schicht[0] <= d_ * c <= schicht[1]]
            if len(sch) < min_lagen: weg_f += 1; continue                # Tor je Feld: kein regelmaessiges Lagenraster -> keine Steine erfinden
            ok_f += 1; guete += float(pr["prominences"].sum()); lagen_m += sch
            for l_ in lager: fuge[y0 + l_, x0:x1] |= mm[l_]
            grenzen = [0] + list(lager) + [y1 - y0]
            for b0, b1 in zip(grenzen[:-1], grenzen[1:]):
                if (b1 - b0) * c < 0.08: continue
                band = mm[b0 + 1:b1 - 1]; ncol = band.sum(0); q = ndi.gaussian_filter1d(rr[b0 + 1:b1 - 1].sum(0) / np.maximum(ncol, 1), 1.0); q[ncol < 0.6 * max(b1 - b0 - 2, 1)] = 0
                if q.std() <= 1e-6: continue
                stoss, _ = find_peaks(q, distance=max(1, int(stoss_min / c)), prominence=schwelle * 0.6 * float(q.std()))
                for s_ in stoss: fuge[y0 + b0:y0 + b1, x0 + s_] |= mm[b0:b1, s_]
        if best is None or guete > best[1]: best = (name, guete, fuge, lagen_m, ok_f, weg_f)
    name, guete, fuge, lagen_m, ok_f, weg_f = best
    lab, n = ndi.label(stein & ~fuge & _felder_mit_raster(stein, fuge, o_))      # 4er-Nachbarschaft: eine 1-Zellen-Fugenlinie trennt
    weg = dict(klein=0, form=0, stuetze=0)
    if n:
        # STEIN-TOR je Stein (Probe f00 Stadtseite 21.11.: Wandgemaelde, Vordach, Dachziegel und die Torleibung lagen im selben Steinfeld wie das Mauerwerk und
        # bekamen ein erfundenes Raster). Quader = (a) nicht winzig, (b) rechteckig (Flaeche/Huellrechteck >= rechteckig), Hoehe 0,5 x kleinste bis 1,3 x groesste Lage (Dachziegel-/Gemaelde-'Steine' sind
        # niedriger als jede Quaderlage),
        # (c) Rand gestuetzt: >= stuetze des Randrings zeigt im Mehrfoto-Wandbild eine deutliche Fuge (Antwort ueber der robusten Streuung) - Bildinhalt ohne
        # Fugen (Gemaelde, Putzflecken) hat nur die Raster-Linien, keine Fugen darunter.
        idx = np.arange(1, n + 1); fl = ndi.sum(np.ones(lab.shape), lab, idx) * c * c; sl = ndi.find_objects(lab)
        hb = np.array([(s[0].stop - s[0].start) * c for s in sl]); wb = np.array([(s[1].stop - s[1].start) * c for s in sl]); voll = fl / np.maximum(hb * wb, 1e-9)
        vz = 1.0 if name == "hell" else -1.0; rs = ndi.gaussian_filter(vz * a, 1.0); sm = rs[stein]; th = 1.48 * float(np.median(np.abs(sm - np.median(sm)))) if sm.size else 0.0
        ring = stein & (lab == 0); rl = np.where(ring, ndi.grey_dilation(lab, size=(5, 5)), 0); sup = np.nan_to_num(np.asarray(ndi.mean((rs > th).astype(np.float64), rl, idx)))
        k_klein = fl < min_stein_m2; k_form = ~k_klein & ((voll < rechteckig) | (hb > 1.3 * schicht[1]) | (hb < 0.5 * schicht[0]) | (wb > max_laenge)); k_st = ~k_klein & ~k_form & (sup < stuetze)
        weg = dict(klein=int(k_klein.sum()), form=int(k_form.sum()), stuetze=int(k_st.sum()))
        raus = idx[k_klein | k_form | k_st]
        if len(raus): lab[np.isin(lab, raus)] = 0
        lab, n = ndi.label(lab > 0)
    return lab.astype(np.int32), fuge & stein, dict(polaritaet=name, guete=round(guete, 2), lagen_m=[round(x, 3) for x in lagen_m], felder=ok_f, felder_verworfen=weg_f, steine=int(n), verworfen=weg)


def _felder_mit_raster(stein, fuge, o_):
    """nur Steinfelder, in denen das Schichtmodell Fugen gefunden hat (Felder ohne Lagenraster bleiben ohne Steine)."""
    komp, nk = ndi.label(ndi.binary_opening(stein, np.ones((o_, o_))))
    if not nk: return np.zeros(stein.shape, bool)
    hat = ndi.maximum(fuge.astype(np.int32), komp, np.arange(1, nk + 1)) > 0
    return np.r_[False, hat][komp]


def quader_relief(tiefe, lab, px, gueltig=None, massstab=None, min_mm=None, min_mess=0.2):
    """Hoehenbild mit ebenen Steinen und druckbaren Rillen. tiefe: Relief (m, + = vor der Wand), lab: Steinnummern im selben Raster (0 = kein Stein),
    gueltig: Zellen mit gemessener Tiefe (sonst alle). Zellen ausserhalb der Steinflaeche bleiben unveraendert.
    Stirnflaeche = Median der gueltigen Tiefe im Stein (>= min_mess Anteil und >= 3 Zellen gemessen), sonst naechster gemessener Stein.
    Rille: Zellen der Steinflaeche naeher als Breite/2 an einer Fuge (Zelle zwischen zwei Steinen); Grund = niedrigerer Nachbarstein - Rillentiefe.
    Liefert (h, info)."""
    t = np.asarray(tiefe, np.float64); lab = np.asarray(lab, np.int32); n = int(lab.max()); info = dict(steine=n)
    if n == 0: return t.astype(np.float32), info
    g = np.ones(t.shape, bool) if gueltig is None else np.asarray(gueltig, bool)
    g = g & np.isfinite(t); idx = np.arange(1, n + 1)
    fl = ndi.sum(np.ones(t.shape), lab, idx); gm = ndi.sum(g.astype(np.float64), lab, idx)
    lg = np.where(g, lab, 0); fr = np.asarray(ndi.median(np.where(g, t, 0.0), lg, idx), np.float64) if (lg > 0).any() else np.full(n, np.nan)
    gem = (gm >= np.maximum(min_mess * fl, 3)); fr = np.where(gem, fr, np.nan)
    if not gem.any(): fr[:] = float(np.median(t[g])) if g.any() else 0.0; gem[:] = False
    elif not gem.all():                                                  # Stein ohne Messung: Front des naechsten gemessenen Steins (Abstand im Bild)
        F = np.r_[np.nan, fr][lab]; ok = np.isfinite(F) & (lab > 0)
        _, (ii, jj) = ndi.distance_transform_edt(~ok, return_indices=True); nah = F[ii, jj]
        for k in np.flatnonzero(~gem): fr[k] = float(np.median(nah[lab == k + 1]))
    stein = lab > 0; F = np.r_[np.nan, fr][lab]
    # Fugenzellen: zwischen Steinen (nicht am Rand zur Putzflaeche - dort ist schon die Stufe Stein/Putz)
    hull = ndi.binary_closing(stein, np.ones((5, 5))) | stein; fuge = hull & ~stein
    mx = ndi.maximum_filter(lab, size=5); mn = ndi.minimum_filter(np.where(stein, lab, n + 1), size=5)
    zwischen = fuge & (mn <= n) & (mx != mn)                             # Fugenzelle mit zwei verschiedenen Steinen im 5x5-Fenster
    for ax in (0, 1):                                                    # Steine, die im groeberen Raster direkt aneinanderstossen (Fugenlinie beim Abtasten verloren): Grenze = Fuge
        A_ = lab[:-1, :] if ax == 0 else lab[:, :-1]; B_ = lab[1:, :] if ax == 0 else lab[:, 1:]; m_ = (A_ > 0) & (B_ > 0) & (A_ != B_)
        if ax == 0: zwischen[:-1, :] |= m_; zwischen[1:, :] |= m_
        else: zwischen[:, :-1] |= m_; zwischen[:, 1:] |= m_
    breite, tief_min = druckmass(massstab, min_mm)
    tg = t[fuge & g]; nb = ndi.minimum_filter(np.where(stein, F, np.inf), size=5)
    tief_gem = float(np.median(np.clip(nb[fuge & g & np.isfinite(nb)] - t[fuge & g & np.isfinite(nb)], 0, None))) if (fuge & g & np.isfinite(nb)).sum() >= 10 else 0.0
    tief = max(tief_min, tief_gem)
    dt = ndi.distance_transform_edt(~zwischen) * px; rille = (hull & (dt <= 0.5 * breite)) & (ndi.binary_dilation(zwischen, np.ones((3, 3))) | stein)
    Ffill = F.copy(); okF = np.isfinite(Ffill)
    if okF.any():
        _, (ii, jj) = ndi.distance_transform_edt(~okF, return_indices=True); Ffill = Ffill[ii, jj]
    k_ = max(3, int(np.ceil(breite / px)) + 2) | 1; boden = ndi.minimum_filter(Ffill, size=k_) - tief
    h = t.copy(); h[stein] = F[stein]; h[rille] = boden[rille]
    info.update(gemessen=int(gem.sum()), front_p5_p95_m=[round(float(x), 3) for x in np.percentile(fr, [5, 95])], rille_breite_m=round(breite, 3), rille_tiefe_m=round(tief, 3),
                rille_tiefe_gemessen_m=round(tief_gem, 3), rille_mm=[round(breite * 1000 / float(massstab or SCALE), 2), round(tief * 1000 / float(massstab or SCALE), 2)],
                rillen_anteil=round(float(rille.mean()), 3), fuge_tiefe_median_m=round(float(np.median(tg)), 3) if len(tg) else None)
    return h.astype(np.float32), info


def eckquader_bloecke(lab, px, z0, ecke_links=True, ecke_rechts=True, rand=0.10):
    """Eckquader = Steine, die bis an das Wandende reichen (<= rand m). lab: Steinnummern (Zeile 0 = oben, Spalte 0 = Wandanfang), z0 = Unterkante des Rasters.
    Je Ende: Liste dict(z0, z1, hoehe, laenge) von unten nach oben + lang/kurz (Schwelle = Mitte zwischen den Laengen-Quartilen) + Zahnung (Anteil der Lagenwechsel lang<->kurz)."""
    lab = np.asarray(lab, np.int32); H, W = lab.shape; r_ = max(1, int(round(rand / px))); erg = {}
    for ende, ok in (("anfang", ecke_links), ("ende", ecke_rechts)):
        if not ok: continue
        L = lab if ende == "anfang" else lab[:, ::-1]; ids = np.unique(L[:, :r_]); ids = ids[ids > 0]; bl = []
        for i in ids:
            ys, xs = np.nonzero(L == i)
            if xs.min() >= r_: continue
            bl.append(dict(z0=round(z0 + (H - ys.max() - 1) * px, 3), z1=round(z0 + (H - ys.min()) * px, 3), hoehe=round((ys.max() - ys.min() + 1) * px, 3), laenge=round((xs.max() + 1) * px, 3)))
        bl.sort(key=lambda b: b["z0"])
        if len(bl) >= 2:
            ls = np.array([b["laenge"] for b in bl]); q1, q3 = np.percentile(ls, [25, 75]); sw = 0.5 * (q1 + q3)
            art = ["lang" if x > sw else "kurz" for x in ls]; wechsel = float(np.mean([a_ != b_ for a_, b_ in zip(art[:-1], art[1:])]))
            for b, a_ in zip(bl, art): b["art"] = a_
            erg[ende] = dict(bloecke=bl, lang_m=round(float(np.median(ls[ls > sw])) if (ls > sw).any() else 0.0, 3), kurz_m=round(float(np.median(ls[ls <= sw])), 3), zahnung=round(wechsel, 2),
                             hoehe_median_m=round(float(np.median([b["hoehe"] for b in bl])), 3))
        elif bl: erg[ende] = dict(bloecke=bl, zahnung=0.0)
    return erg


def _fassade(Z, ffn, parallel=0.95, abstand=1.0):
    try: FF = json.load(open(os.path.join(ffn, "fassaden.json")))["fassaden"]
    except Exception: return None
    a = np.asarray(Z["a"], float)[:2]; t = np.asarray(Z["t"], float)[:2]; nw = np.asarray(Z["n"], float)[:2]; H, W = Z["rel"].shape; px = float(Z["px"]); u0 = float(Z["u0"])
    xy = a[None, :] + (u0 + (np.arange(W) + 0.5) * px)[:, None] * t[None, :]; best = None
    for F in FF:
        o = np.asarray(F["o"], float); n = np.asarray(F["n"], float)
        if n @ nw < parallel or not F.get("raster"): continue
        ab = float(np.median(np.abs((xy - o) @ n)))
        if ab <= abstand and (best is None or ab < best[0]): best = (ab, F)
    return None if best is None else best[1]


def _maske_umrechnen(Zq, key, Zz):
    """bool-Maske key aus Relief Zq (gleiche Wandgerade) in das Raster von Zz (ueber u, z). None ohne Maske."""
    if Zq is None or key not in Zq: return None
    M = np.asarray(Zq[key], bool); Hq, Wq = M.shape; pq = float(Zq["px"]); uq, zq = float(Zq["u0"]), float(Zq["z0"])
    H, W = np.asarray(Zz["rel"]).shape; px = float(Zz["px"]); u0, z0 = float(Zz["u0"]), float(Zz["z0"])
    uu = u0 + (np.arange(W) + 0.5) * px; zz = z0 + (H - 1 - np.arange(H) + 0.5) * px
    j = np.floor((uu - uq) / pq).astype(int); i = (Hq - 1 - np.floor((zz - zq) / pq)).astype(int); okj = (j >= 0) & (j < Wq); oki = (i >= 0) & (i < Hq)
    out = np.zeros((H, W), bool); out[np.ix_(oki, okj)] = M[np.ix_(i[oki], j[okj])]; return out


def quader_auf_relief(Z, ffn, min_fotos=2, massstab=None, min_mm=None, rand_ecke=(False, False), vorn_quelle=None, frei=(), nur_in=None, zone_unten=False):
    """Relief Z (dict/npz der Fassaden-Kette: rel, a, t, n, u0, z0, px; optional putz, oeffnung, vordergrund, wand) + Wandbild-Ordner (fassade_fein) ->
    (rel_neu, info) oder (None, info) ohne Fassade/Einzelbilder/Raster. Steinflaeche = Wandbild-Quaderflaeche (putz_wandbild.glatt_karte 'quader', Mehrfoto)
    ohne Oeffnungen; gemessene Tiefe = Relief ohne Putzmaske/Vordergrund/Loecher."""
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import putz_wandbild as PW
    F = _fassade(Z, ffn)
    if F is None: return None, dict(grund="keine passende Fassade im Wandbild")
    R = F["raster"]; c = float(R["zelle"]); fs = sorted(glob.glob(os.path.join(ffn, f"ortho_{F['id']}_einzeln", "*.png")))
    if len(fs) < min_fotos: return None, dict(grund=f"nur {len(fs)} Einzelbilder")
    rel = np.asarray(Z["rel"], np.float64); H, W = rel.shape; px = float(Z["px"]); u0, z0 = float(Z["u0"]), float(Z["z0"]); a = np.asarray(Z["a"], float)[:2]; t = np.asarray(Z["t"], float)[:2]
    o = np.asarray(F["o"], float); d = np.asarray(F["d"], float)
    uu = u0 + (np.arange(W) + 0.5) * px; zz = z0 + (H - 1 - np.arange(H) + 0.5) * px; uf = (a[None, :] + uu[:, None] * t[None, :] - o) @ d
    j = np.floor((uf - float(R["u0"])) / c).astype(int); i = np.floor((float(R["z1"]) - zz) / c).astype(int)
    j0, j1 = max(int(j.min()) - 5, 0), int(j.max()) + 6; i0, i1 = max(int(i.min()) - 5, 0), int(i.max()) + 6
    bilder = []
    for f in fs:
        try: im = Image.open(f).convert("L"); j1_ = min(j1, im.size[0]); i1_ = min(i1, im.size[1]); bilder.append(np.asarray(im.crop((j0, i0, j1_, i1_)), np.float32))
        except Exception: continue
    if not bilder: return None, dict(grund="Einzelbilder nicht lesbar")
    hh = min(b.shape[0] for b in bilder); ww = min(b.shape[1] for b in bilder); bilder = [b[:hh, :ww] for b in bilder]
    ant, nf = fugen_antwort(bilder, c, min_fotos=min_fotos)
    if ant is None: return None, dict(grund="keine Fotodaten")
    K = PW.glatt_karte(ffn, F["id"])
    if K is None: return None, dict(grund="keine Quaderkarte (glatt_karte)")
    kq = K["quader"]; kc = float(K["zelle"]); ii_, jj_ = np.mgrid[i0:i0 + hh, j0:j0 + ww]; qi = np.clip((ii_ * c / kc).astype(int), 0, kq.shape[0] - 1); qj = np.clip((jj_ * c / kc).astype(int), 0, kq.shape[1] - 1)
    stein = kq[qi, qj] & (nf >= min_fotos)
    ri = np.clip(i - i0, 0, hh - 1); rj = np.clip(j - j0, 0, ww - 1); innen = ((i - i0) >= 0) & ((i - i0) < hh); innen_j = ((j - j0) >= 0) & ((j - j0) < ww)
    if "oeffnung" in Z:                                                   # Oeffnungen (Tor, Fenster) sind kein Stein: Reliefmaske ins Wandbildraster
        oe = np.zeros((hh, ww), bool); oe[np.ix_(ri[innen], rj[innen_j])] = np.asarray(Z["oeffnung"], bool)[np.ix_(innen, innen_j)]
        stein &= ~ndi.binary_dilation(oe, np.ones((int(0.1 / c) | 1,) * 2))
    if stein.sum() * c * c < 0.3: return None, dict(grund="Wandbild zeigt hier kein Quaderwerk")
    lab_f, fuge, si = raster_segmentieren(ant, stein, c)
    if si["steine"] == 0: return None, dict(grund="kein Lagenraster im Wandbild", **si)
    lab = np.zeros((H, W), np.int32); lab[np.ix_(innen, innen_j)] = lab_f[np.ix_(ri[innen], rj[innen_j])]
    if "wand" in Z: lab[~np.asarray(Z["wand"], bool)] = 0
    # VOR DER WAND (Probe w02 21.11.: Vordach-Dachziegel und Wandgemaelde unter dem Vordach bekamen 'Steine'): Steine, die zu >= 20 % in der um 0,3 m
    # erweiterten Maske 'vorn' (Netz steht 0,6-2,6 m vor der Wand: Vordach, Erker, Balkon; fassaden_kette.netz_vorn) oder in einem Freikreis (Uhr) liegen, entfallen.
    weg_vorn = 0; uu2, zz2 = np.meshgrid(uu, zz)
    vm = _maske_umrechnen(vorn_quelle if vorn_quelle is not None else Z, "vorn", Z)
    sperr = ndi.binary_dilation(vm, np.ones((2 * int(0.3 / px) + 1,) * 2)) if vm is not None and vm.any() else np.zeros((H, W), bool)
    for fu, fz, fr in frei: sperr |= (uu2 - fu) ** 2 + (zz2 - fz) ** 2 <= fr ** 2
    if sperr.any() and lab.max():
        ids = np.arange(1, int(lab.max()) + 1); ant_s = np.nan_to_num(np.asarray(ndi.mean(sperr.astype(np.float64), lab, ids)))
        raus = ids[ant_s >= 0.2]; weg_vorn = int(len(raus))
        if weg_vorn: lab[np.isin(lab, raus)] = 0
    weg_zone = 0; info_zone = None
    if nur_in is not None or zone_unten:                                 # Steine nur, wo der Aufrufer Stein belegt (z. B. Fotorelief von steine_aus_foto) bzw. nur in der Steinzone von unten
        ids = np.arange(1, int(lab.max()) + 1) if lab.max() else np.zeros(0, int); bleib = np.ones(len(ids), bool)
        if nur_in is not None and len(ids): bleib &= np.nan_to_num(np.asarray(ndi.mean(np.asarray(nur_in, bool).astype(np.float64), lab, ids))) >= 0.5
        if zone_unten and len(ids):
            # Steinzone = zusammenhaengender Block von unten mit >= 30 % Steinzeilen (Luecken < 1,5 m ueberbrueckt) - wie die Steinzone der Feinrechnung (fassaden_kette).
            # Grund: auf einer Wand OHNE Quader-Tor (w02: oben Putz/Uhr, Mitte Vordach + Wandgemaelde) liest das Wandbild Dachziegel und Gemaelde als 'rau'.
            # Anteil an der Wand OHNE Oeffnungen (Torbogen: nur die Pfeiler zaehlen); Zeilen mit < 0,3 m Wand neben der Oeffnung sind neutral (keine Luecke).
            wz_ = np.ones((H, W), bool)
            if "oeffnung" in Z and np.asarray(Z["oeffnung"]).shape == (H, W): wz_ &= ~np.asarray(Z["oeffnung"], bool)
            if "wand" in Z and np.asarray(Z["wand"]).shape == (H, W): wz_ &= np.asarray(Z["wand"], bool)
            # Die Zone beginnt beim UNTERSTEN Steinblock (w02: unter 6,5 m nur Torbogen/Leibung, Netz-Gewoelbe statt Oeffnungsmaske) - darunter liegende Zeilen ohne Stein zaehlen nicht als Luecke.
            nw_ = wz_.sum(1); fr_ = np.where(nw_ * px >= 0.3, ((lab > 0) & wz_).sum(1) / np.maximum(nw_, 1), 1.0); k_ = H; luecke = 0
            lauf_ = max(2, int(round(0.5 / px)))                         # Steinblock = >= 0,5 m zusammenhaengend (einzelne Zeilen in der Leibung zaehlen nicht)
            while k_ > 0 and not (k_ - lauf_ >= 0 and (fr_[k_ - lauf_:k_] >= 0.3).all()): k_ -= 1
            zu_ = z0 + (H - k_) * px                                     # Unterkante des untersten Steinblocks
            while k_ > 0 and (fr_[k_ - 1] >= 0.3 or luecke * px < 1.5): luecke = 0 if fr_[k_ - 1] >= 0.3 else luecke + 1; k_ -= 1
            k_ += luecke; zgr = z0 + (H - k_) * px                       # Oberkante der Steinzone
            info_zone = (round(zu_, 2), round(zgr, 2))
            cz = np.asarray(ndi.mean(np.broadcast_to(zz[:, None], (H, W)).astype(np.float64), lab, ids)); bleib &= (cz <= zgr) & (cz >= zu_)
        raus = ids[~bleib]; weg_zone = int(len(raus))
        if weg_zone: lab[np.isin(lab, raus)] = 0
        if nur_in is not None: lab[~np.asarray(nur_in, bool)] = 0                 # Stein ueber den Rand der belegten Flaeche hinaus: dort abschneiden
    g = np.isfinite(rel) & (rel != 0.0)
    for k_ in ("putz", "vordergrund", "oeffnung"):
        if k_ in Z and np.asarray(Z[k_]).shape == rel.shape: g &= ~np.asarray(Z[k_], bool)
    lab = np.unique(lab, return_inverse=True)[1].reshape(lab.shape).astype(np.int32)      # Nummern lueckenlos, 0 bleibt 0; NICHT neu verbinden (Fugenlinie kann beim Abtasten fehlen)
    h, qi_ = quader_relief(rel, lab, px, gueltig=g, massstab=massstab, min_mm=min_mm)
    info = dict(fassade=F["id"], fotos=len(bilder), stein_m2=round(float(stein.sum()) * c * c, 1), weg_vorn_frei=weg_vorn, weg_zone=weg_zone, steinzone_z=info_zone, **si, **{("relief_" + k): v for k, v in qi_.items()})
    info["eckquader"] = eckquader_bloecke(lab, px, z0, *rand_ecke) if any(rand_ecke) else {}
    return h, dict(info, lab=lab)


def quader_datei(f_in, ffn, f_out=None, **kw):
    """quader_auf_relief fuer eine Reliefdatei; schreibt <f_in>_q.npz (+ .jpg: links vorher, rechts nachher, schattiert). Liefert (pfad, info) - pfad = f_in ohne Ergebnis."""
    f_out = f_out or f_in[:-4] + "_q.npz"
    if os.path.exists(f_out) and os.path.getmtime(f_out) >= max(os.path.getmtime(f_in), os.path.getmtime(__file__), os.path.getmtime(os.path.join(ffn, "fassaden.json")) if os.path.exists(os.path.join(ffn, "fassaden.json")) else 0.0) and os.environ.get("QUADER_NEU") != "1":
        try: return f_out, dict(json.loads(str(np.load(f_out)["quader_raster"])), zwischenstand=True)      # Generator laeuft je Kette mehrfach: Ergebnis wiederverwenden
        except Exception: pass
    Z = dict(np.load(f_in)); h, info = quader_auf_relief(Z, ffn, **kw)
    if h is None:
        if os.path.exists(f_out): os.remove(f_out)                        # altes Ergebnis gilt nicht mehr
        return f_in, info
    lab = info.pop("lab"); Z["rel"] = h; Z["stein_id"] = lab; Z["quader_raster"] = json.dumps(info, ensure_ascii=False); np.savez_compressed(f_out, **Z)
    try:
        from PIL import Image
        def sch(r): px = float(Z["px"]); lx = np.gradient(r, px, axis=1); lz = np.gradient(r, px, axis=0); return (np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8)
        alt = np.asarray(np.load(f_in)["rel"], np.float64); Image.fromarray(np.hstack([sch(alt), np.full((alt.shape[0], 4), 255, np.uint8), sch(h)])).save(f_out[:-4] + ".jpg", quality=88)
    except Exception: pass
    return f_out, info


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("fein"); ap.add_argument("--aus"); ap.add_argument("--vorn", help="Relief mit Maske 'vorn' (sonst die eigene)")
    ap.add_argument("--zone_unten", action="store_true", help="nur Steinzone von unten (Wand ohne Quader-Tor)"); ap.add_argument("--nur_stein", action="store_true", help="nur wo das Relief Stein ist (> Putzniveau + 1 cm; Fotorelief)")
    a = ap.parse_args(); Z = np.load(a.relief); kw = dict(zone_unten=a.zone_unten, vorn_quelle=dict(np.load(a.vorn)) if a.vorn else None)
    if a.nur_stein: kw["nur_in"] = np.asarray(Z["rel"]) > float(Z["putz_niveau_m"] if "putz_niveau_m" in Z.files else 0.0) + 0.01
    p, info = quader_datei(a.relief, a.fein, a.aus, **kw); info.pop("lab", None); print(p, json.dumps(info, ensure_ascii=False)[:1500]); return 0 if p != a.relief else 2


if __name__ == "__main__":
    sys.exit(main())
