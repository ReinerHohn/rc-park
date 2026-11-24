#!/usr/bin/env python3
"""ortsteine.py - ORTSTEINE / ECKVERZAHNUNG aus dem Wandbild (GENERISCH, 24.11.2026; Grundsatz WANDBILD = BAUPLAN, keine Musterteile, kein Hardcoding).

ANLASS (Befund Kettenlauf 1122u/v, Schwabentor Sued + Nord): an allen Turmkanten sitzen versetzte rote Sandstein-Eckquader (abwechselnd lang/kurz in die
Putzflaeche greifend, vor dem Putz) - im Modell sind die Kanten glatt. Die vorhandene Eckquader-Erkennung (bauteile.eckquader_aus_relief, quader_raster.eckquader_bloecke)
benennt nur Steine, die im gebauten Fotorelief schon stehen; wo das Relief an der Kante fehlt oder zu Putz geglaettet wurde, entsteht nichts.
BEFUND 1122w (Runde 2, 24.11.2026): Nord-Kante links viele duenne gleich lange Streifen (Lagen 0,18-0,22 m statt ~0,3; ein Block je Lage ueber 2 m ohne Stossfuge),
in der Uhrzone nichts (Nord: Mosaik endet 8 m unter der Traufe, Einzelfotos zeigen die Zone; Sued: Ziffernring der Uhr im festen Innenband -> Zeile verworfen).

ABLAUF (nur Daten der Kette, nichts von Hand):
  stein_putz_karte(rgb)      Putz = unbunt (Rot-Blau-Anteil unter der Otsu-Schwelle des Bildes) UND hell (ueber dem Bild-eigenen Hellwert des unbunten Anteils);
                             Himmel (blau) / keine Daten / dunkel-unbunt = unbekannt; rot/braun = Stein.
  mosaik_karte(fein, fid)    Klassenbild aus dem feinen Wandbild (Mosaik ortho_<fid>_fein.png: Bezugsfoto + ausgerichtete Fotos).
  ausrichten(...)            MEHRFOTO: jedes Einzelbild ortho_<fid>_einzeln/* per Verschiebung auf das Mosaik (FFT-Korrelation der Stein/Putz-Karten, grob -> fein);
                             Einigkeit im Ueberlapp = Guete. Fehl ausgerichtete / fremde Fotos fallen unter min_einig.
  karte_ergaenzen(...)       Zellen, die das Mosaik NICHT sieht (Schwabentor Nord: Uhrzone ueber 28,6 m), aus >= 3 ausgerichteten Einzelbildern mit Mehrheit fuellen.
  steinkante(...)            Fotokante der Steine nahe der LoD2-Kante (Schwabentor: 0,3-0,5 m daneben, Nachbarwand hell).
  kanten_zonen(...)          je Wandende: Zeilen mit Steinstreifen ab der Kante UND danach Putz - entweder im festen Innenband (innen_ab..innen_ab+band) ODER direkt hinter
                             dem Steinende (nah, >= min_putz_nah) - so zaehlen Zeilen neben Uhr/Wandbild im Innenband mit. Volles Quadermauerwerk zaehlt nicht.
  bestaetigen(...)           Formfamilie je Zone: ausgerichtete Einzelfotos, deren Stein/Putz-Verteilung dort mit der Karte uebereinstimmt (>= 3, sonst nicht gebaut).
  fugen_profil / steinlagen  Lagen: Spruenge im Breitenprofil (lang <-> kurz) + Laeufe laenger als 0,55 m an quer durchlaufenden Lagerfugen (Zeilen, in denen fast
                             alle Zellen dunkler als ihr Umfeld sind) geteilt - keine 0,18-m-Splitter mehr aus Steintextur.
  stossfugen(G, ...)         senkrechte Fugen je Lage (dunkle Spalten im Steinstreifen, Mindeststeinlaenge) -> Teilsteine statt eines 2-m-Balkens.
  vorsprung_messen(...)      Vorsprung = Median der Ebenen-Sweep-Tiefe (fassade/tiefe_<fid>.npz) der Steinzellen minus Putzzellen daneben; Guard 0,01-0,30 m, sonst ANNAHME = Druckmass.
  tor_kante(...)             TOR je Kante: gebaute Steinflaeche (Lagen x Breite) gegen die Steinflaeche der Karte (IoU) + Abdeckung der Ortsteinzeilen; durchgefallen = nicht gebaut.
  ortsteine_erkennen(...)    alles je Fassade -> JSON (KETTENSTUFE bauplan_ortsteine: ortsteine.py <objekt.json> --aus audit/ortsteine_auto.json --bild audit/ortsteine_auto.jpg).
  ortsteine_bauen(koerper, J) Bloecke vor die ECHTE Koerperflaeche (Strahltreffer neben dem Stein, bauteile._oberflaeche_w), um die Ecke um den Vorsprung gefuehrt;
                             Lagerfuge (Druckmass) zwischen gleich langen Nachbarlagen, Stossfuge (Druckmass) zwischen Teilsteinen.
  ortsteine_anbauen(koerper, objekt_json)  Aufruf fuer fassaden_kette.anbauen / Generator: audit/ortsteine_auto.json wenn da (oder ORTSTEINE_JSON), sonst direkt rechnen.
DRUCK (1:SCALE, MINMM): Lage >= MINMM, Steinbreite >= MINMM, Vorsprung >= 0,5 x MINMM (wie quader_raster Rillentiefe), Lager-/Stossfuge = MINMM - alle als Mass im Modell.
ANNAHMEN: Einbindung 0,10 m hinter die Flaeche; Stirn eben (Bossen nicht gemessen). Abschalten: OHNE_ORTSTEINE=1. Nur numpy/scipy/PIL (Generator-venv).
Rueckgabe main: 0 = Kanten erkannt und alle durch das Tor, 2 = mindestens eine Kante am Tor verworfen, 3 = nichts erkannt / kein Wandbild.
"""
import os, sys, json, glob, argparse
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__))
SCALE = float(os.environ.get("SCALE", "87")); MINMM = float(os.environ.get("MINMM", "0.8"))


def druck_m(faktor=1.0):
    """Druckmindestmass in Metern Wirklichkeit (MINMM mm im Massstab 1:SCALE) x faktor."""
    return faktor * MINMM * SCALE / 1000.0


def _otsu(x, lo, hi, bins=64):
    h, e = np.histogram(x, bins=bins, range=(lo, hi)); h = h.astype(np.float64); m = 0.5 * (e[1:] + e[:-1])
    w0 = np.cumsum(h); w1 = h.sum() - w0; s0 = np.cumsum(h * m); mu0 = s0 / np.maximum(w0, 1); mu1 = (s0[-1] - s0) / np.maximum(w1, 1)
    return float(m[int(np.argmax(w0 * w1 * (mu0 - mu1) ** 2))])


def stein_putz_karte(rgb, min_daten=30.0):
    """rgb (H, W, 3) eines entzerrten Fotos -> (stein, putz) bool. Schwellen aus dem Bild selbst (Otsu auf dem Rot-Blau-Anteil, Hellwert des unbunten Anteils):
    Sandstein rot/braun = Rot-Blau-Anteil hoch; Putz = unbunt und hell (Schatten auf Putz bleiben unbunt, aber dunkel -> nicht Putz, nicht Stein: unbekannt)."""
    a = np.asarray(rgb, np.float32); s = a.sum(2); daten = s > min_daten
    if daten.sum() < 100: z = np.zeros(a.shape[:2], bool); return z, z
    rb = (a[..., 0] - a[..., 2]) / (s + 1.0); v = a.max(2) / 255.0
    blau = (a[..., 2] - a[..., 0]) / (s + 1.0) > 0.03                    # Himmel/blaue Flaechen: weder Stein noch Putz
    t_rb = min(max(_otsu(rb[daten & ~blau], -0.05, 0.35), 0.03), 0.12)  # Guard: Schwelle zwischen unbunt und rot
    unbunt = daten & ~blau & (rb < t_rb)
    if unbunt.sum() < 50: return daten & ~blau, np.zeros_like(daten)
    v_hell = 0.75 * float(np.percentile(v[unbunt], 95))                   # Bild-eigener Hellwert (Belichtung je Foto verschieden)
    putz = unbunt & (v >= v_hell)
    stein = daten & ~blau & (rb >= t_rb)
    return stein, putz


def klassen(rgb):
    """Klassenbild uint8: 0 unbekannt, 1 Stein, 2 Putz."""
    st, pu = stein_putz_karte(rgb); kl = np.zeros(st.shape, np.uint8); kl[st] = 1; kl[pu] = 2
    return kl


def _box(a, k):
    """Mittelwert im (k x k)-Fenster, nur numpy."""
    if k <= 1: return np.asarray(a, np.float64)
    a = np.asarray(a, np.float64)
    for ax in (0, 1):
        p = np.pad(a, [(k // 2, k - 1 - k // 2) if q == ax else (0, 0) for q in range(2)], mode="edge"); c = np.cumsum(p, axis=ax)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=ax)), c], axis=ax); a = (np.take(c, range(k, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - k), axis=ax)) / k
    return a


def verschieben(a, dy, dx):
    """a um (dy, dx) Zellen verschieben (positiv = nach unten / rechts), Rand 0: Ergebnis(x) = a(x - d)."""
    o = np.zeros_like(a); H, W = a.shape[:2]
    if abs(dy) >= H or abs(dx) >= W: return o
    ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
    xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
    o[yd, xd] = a[ys, xs]
    return o


def _blockmittel(m, f):
    H, W = m.shape; h, w = H // f, W // f
    return m[:h * f, :w * f].reshape(h, f, w, f).mean((1, 3))


def _einig(km, ke, dy, dx):
    k = verschieben(ke, dy, dx); beide = (km > 0) & (k > 0); n = int(beide.sum())
    return (float((km == k)[beide].mean()) if n else 0.0), n


def ausrichten(km, ke, c, max_m=1.5, grob=4):
    """Einzelbild-Klassenbild ke auf das Mosaik km verschieben (nur Translation: beide sind auf dieselbe Wandebene entzerrt, der Versatz kommt aus Kamera-/Ebenenfehlern).
    Grob: FFT-Korrelation der Stein-/Putz-Anteile (Bloecke grob x grob), Fenster +-max_m; fein: Bergsteigen in Zellschritten. Liefert dict(dy, dx, einig, ueberlapp) oder None."""
    from scipy.signal import fftconvolve
    Ms = [_blockmittel((km == k).astype(np.float32), grob) for k in (1, 2)]; Es = [_blockmittel((ke == k).astype(np.float32), grob) for k in (1, 2)]
    Mk, Ek = Ms[0] + Ms[1], Es[0] + Es[1]
    if Mk.sum() < 50 or Ek.sum() < 50: return None
    kor = lambda A, B: fftconvolve(A, B[::-1, ::-1], mode="full")
    ein = kor(Ms[0], Es[0]) + kor(Ms[1], Es[1]); ueb = kor(Mk, Ek)
    h, w = Ek.shape; r = max(1, int(max_m / (c * grob)))
    E_ = ein[h - 1 - r:h + r, w - 1 - r:w + r]; U_ = ueb[h - 1 - r:h + r, w - 1 - r:w + r]
    gut = U_ >= 0.5 * U_.max()
    if not gut.any(): return None
    s = np.where(gut, E_ / np.maximum(U_, 1e-6), -1.0); i, j = np.unravel_index(int(np.argmax(s)), s.shape)
    dy, dx = (i - r) * grob, (j - r) * grob
    best, n = _einig(km, ke, dy, dx)
    for schritt in (2, 1):                                               # Bergsteigen in Zellen (grob -> fein)
        besser = True
        while besser:
            besser = False
            for ddy, ddx in ((schritt, 0), (-schritt, 0), (0, schritt), (0, -schritt)):
                e_, n_ = _einig(km, ke, dy + ddy, dx + ddx)
                if e_ > best + 1e-4 and n_ >= 0.5 * n: best, n, dy, dx, besser = e_, n_, dy + ddy, dx + ddx, True
    if max(abs(dy), abs(dx)) * c > max_m + 2 * c: return None
    return dict(dy=int(dy), dx=int(dx), einig=round(best, 3), ueberlapp=n)


def einzeln_laden(dateien, form, stufe=2):
    """Einzelbilder (gleiches Raster wie das Mosaik) laden: dict(datei, rgb, kl)."""
    from PIL import Image
    out = []
    for f in dateien:
        try: im = Image.open(f).convert("RGB")
        except Exception: continue
        if stufe > 1: im = im.reduce(stufe)
        a = np.asarray(im)
        if a.shape[:2] != tuple(form): continue
        out.append(dict(datei=f, rgb=a, kl=klassen(a)))
    return out


def karte_ergaenzen(kl, hell, rgb, daten, rahmen, einz, min_fotos=3, min_mehrheit=0.7):
    """MEHRFOTO: Zellen ohne Mosaikdaten (daten False) im Wandrahmen aus den ausgerichteten Einzelbildern fuellen - Klasse nur bei >= min_fotos sehenden Fotos und
    Mehrheit >= min_mehrheit; Helligkeit/Farbe vom best ausgerichteten Foto (scharfe Fugen statt Mittelwert). Liefert (kl, hell, rgb, ergaenzt-Maske)."""
    fehlt = rahmen & ~daten
    if not fehlt.any() or len(einz) < min_fotos: return kl, hell, rgb, np.zeros_like(fehlt)
    nst = np.zeros(kl.shape, np.int16); npu = np.zeros(kl.shape, np.int16); kl = kl.copy(); hell = hell.copy(); rgb = rgb.copy()
    for e in sorted(einz, key=lambda e: e["einig"]):                      # bestes zuletzt -> dessen Farbe bleibt
        k = verschieben(e["kl"], e["dy"], e["dx"]); a = verschieben(e["rgb"], e["dy"], e["dx"])
        nst += (k == 1) & fehlt; npu += (k == 2) & fehlt
        m = fehlt & (a.sum(2) > 30); rgb[m] = a[m]; hell[m] = a[m].mean(1)
    n = nst + npu; neu = fehlt & (n >= min_fotos)
    kl[neu & (nst >= min_mehrheit * n)] = 1; kl[neu & (npu >= min_mehrheit * n)] = 2
    return kl, hell, rgb, neu & (kl > 0)


def steinkante(kl, c, j_kante, richtung, suche=0.6, innen_ab=2.0, band=1.5, min_putz=0.6, min_stein=0.5):
    """Echte Steinkante nahe der LoD2-Kante (j_kante): in den Zeilen mit Putz im Wandinneren die erste Spalte (von aussen), deren Steinanteil >= min_stein ist,
    Suchfenster +-suche m. 21.11.-Lehre: die LoD2-Kante liegt bis 0,3 m neben der Fotokante (Nachbarwand hell = 'Putz' am Rand). Liefert Spalte (oder j_kante)."""
    H, Wd = kl.shape; ns = int(suche / c); ni, nn = int(innen_ab / c), int(band / c)
    cols = j_kante + richtung * np.arange(-ns, ns + 1); cols = cols[(cols >= 0) & (cols < Wd)]
    if cols.size == 0: return j_kante
    bj = j_kante + richtung * np.arange(ni, ni + nn); bj = bj[(bj >= 0) & (bj < Wd)]
    if bj.size == 0: return j_kante
    B = kl[:, bj]; zeilen = ((B == 2).sum(1) >= min_putz * np.maximum((B > 0).sum(1), 1)) & ((B > 0).mean(1) >= 0.5)
    if zeilen.sum() < 20: return j_kante
    S_ = kl[np.ix_(zeilen, cols)]; ant = (S_ == 1).sum(0) / np.maximum((S_ > 0).sum(0), 1)
    lauf = max(2, int(0.10 / c)); k = np.convolve((ant >= min_stein).astype(int), np.ones(lauf, int), "valid") >= lauf    # Steinlauf >= 10 cm (Einzelspalte = Kantensaum)
    j = np.flatnonzero(k)
    return int(cols[j[0]]) if j.size else j_kante


def kanten_zonen(kl, c, j_kante, richtung, max_b=2.5, innen_ab=2.0, band=1.5, rand=0.15, min_stein=0.6, min_putz=0.6, min_sicht=0.5, min_hoehe=3.0, luecke=1.0, suche=0.45,
                 nah=0.6, min_putz_nah=0.8):
    """kl: Klassenbild (Zeile 0 = oben), c m/Zelle, j_kante = Spalte der Steinkante (steinkante), richtung +1 (Kante links, Wand rechts davon) / -1.
    Ortsteinzeile = Steinstreifen ab der Kante, dann Putz: im Innenband (innen_ab..innen_ab+band) ODER auf 'nah' m direkt hinter dem Steinende (>= min_putz_nah der
    gesehenen Zellen; 24.11.2026 Runde 2: Uhr/Wandbild im Innenband verwarf sonst die ganze Uhrzone).
    Liefert (zonen [(i0, i1)], breite je Zeile in m ab j_kante (nan = keine Ortsteinzeile))."""
    H, Wd = kl.shape; nb, ni, nn, nr = int(max_b / c), int(innen_ab / c), int(band / c), max(1, int(rand / c)); ns = int(suche / c); nz = int(nah / c)
    cols = j_kante + richtung * np.arange(-ns, ni + nn)
    if cols.min() < 0 or cols.max() >= Wd: cols = np.clip(cols, 0, Wd - 1)
    S = kl[:, cols]; stein = (S == 1).astype(np.float64); putz = (S == 2).astype(np.float64); seh = (S > 0); o_ = ns   # Spalte o_ = j_kante
    b_pu = putz[:, o_ + ni:].sum(1) / np.maximum(seh[:, o_ + ni:].sum(1), 1); b_seh = seh[:, o_ + ni:].mean(1)
    zeile_band = (b_pu >= min_putz) & (b_seh >= min_sicht)
    ss = _box(stein[:, :o_ + nb], 3) >= 0.5; ps = _box(putz[:, :o_ + nb], 3) >= 0.5; lauf = max(2, int(0.10 / c)); breite = np.full(H, np.nan); eins = np.ones(lauf, int)
    zeile = np.zeros(H, bool)
    for i in np.flatnonzero(ss[:, :2 * ns + 1 + lauf].any(1)):
        # Steinbeginn je Zeile im Fenster +-suche um die Kante (Fotokante schwankt je Hoehe um 10-20 cm: Ausrichtung des Mosaiks, Kantensaum), dann Randstreifen Stein,
        # Steinbreite = erster Putzlauf (>= 10 cm) danach - gezaehlt ab j_kante (Block deckt Kante bis Steinende)
        ks = np.flatnonzero(np.convolve(ss[i, :2 * ns + 1 + lauf].astype(int), eins, "valid") >= lauf)
        if not ks.size: continue
        a_ = int(ks[0]); r_ = S[i, a_:a_ + nr]; sr = r_ > 0
        if sr.mean() < min_sicht or (r_ == 1).sum() < min_stein * max(sr.sum(), 1): continue
        k = np.flatnonzero(np.convolve(ps[i, a_:].astype(int), eins, "valid") >= lauf)
        if not (k.size and k[0] * c >= rand): continue
        e_ = a_ + int(k[0])
        if not zeile_band[i]:
            sg = S[i, e_:e_ + nz]; sh = sg > 0
            if sg.size < nz // 2 or sh.mean() < min_sicht or (sg == 2).sum() < min_putz_nah * sh.sum(): continue
        zeile[i] = True; breite[i] = (e_ - o_) * c
    zl = int(luecke / c); zi = np.flatnonzero(zeile)
    for a_, b_ in zip(zi[:-1], zi[1:]):
        if 1 < b_ - a_ <= zl: zeile[a_:b_] = True
    zonen = []; i = 0
    while i < H:
        if not zeile[i]: i += 1; continue
        e = i
        while e < H and zeile[e]: e += 1
        if (e - i) * c >= min_hoehe: zonen.append((i, e))
        i = e
    return zonen, breite


def fugen_profil(H, K, c, fenster=0.2, kontrast=6.0):
    """Lagerfugen-Staerke je Zeile (0..1): Anteil der gesehenen Zellen (K > 0) eines Steinstreifens, die dunkler sind als ihr senkrechtes Umfeld (fenster m) minus kontrast.
    Eine Lagerfuge laeuft quer durch den Streifen -> fast alle Zellen der Zeile dunkel; Steintextur trifft nur Teile. (24.11.2026 Runde 2: Autokorrelation der Zeilenhelligkeit fand
    am Schwabentor keine Periode - Lagen 0,25-0,6 m wechselnd, Steine hell/dunkel -, die Fugenzeilen selbst stehen klar heraus.)"""
    H = np.asarray(H, float); seh = np.asarray(K) > 0
    if H.size == 0: return np.zeros(H.shape[0])
    k = max(3, int(fenster / c)); p = np.pad(H, ((k // 2, k - 1 - k // 2), (0, 0)), mode="edge"); cs = np.concatenate([np.zeros((1, H.shape[1])), np.cumsum(p, 0)], 0)
    loc = (cs[k:] - cs[:-k]) / k                                            # senkrechtes Mittel je Spalte
    D = (H < loc - kontrast) & seh
    s = D.sum(1) / np.maximum(seh.sum(1), 1)
    return 0.5 * (s + np.concatenate([s[:1], s[:-1]]))                      # 2 Zeilen glaetten (Fuge 1-3 cm liegt auf Zellgrenze)


def steinlagen(b, fugen, c, sprung=0.12, min_lage=None, fenster=0.08, max_lage=0.55, min_fuge=0.6):
    """Lagen einer Ortsteinzone. b: Breite je Zeile (m, nan = Luecke, Zeile 0 = oben), fugen: Lagerfugen-Staerke je Zeile (fugen_profil) oder None.
    1. Grenzen = Spruenge im Breitenprofil (|Median oben - Median unten| >= sprung) = Verzahnung lang/kurz; staerkste zuerst, Mindestabstand min_lage (Druckmass).
    2. Laeufe laenger als max_lage werden an der staerksten Fugenzeile (>= min_fuge, beide Teile >= max(min_lage, 0,2 m)) geteilt, wiederholt - nur echte, quer
       durchlaufende Fugen (24.11.2026 Runde 2: vorher 'dunkelste Zeile' -> 0,18-m-Splitter aus Steintextur, 1122w Nord 32 duenne Streifen; ohne Fuge bleibt der Stein ganz).
    Liefert [(i0, i1, breite_m)] von oben nach unten."""
    min_lage = druck_m(1.0) * 2.5 if min_lage is None else min_lage
    n = len(b); k = max(2, int(fenster / c)); bb = np.array(b, float)
    if np.isnan(bb).all(): return []
    idx = np.arange(n); g = ~np.isnan(bb); bb = np.interp(idx, idx[g], bb[g])
    m_ = int(min_lage / c)
    d = np.zeros(n)
    for i in range(k, n - k): d[i] = abs(np.median(bb[i - k:i]) - np.median(bb[i:i + k]))
    gr = [0]
    for i in np.argsort(-d):                                              # staerkste Spruenge zuerst, Mindestabstand m_
        if d[i] < sprung: break
        if all(abs(i - q) >= m_ for q in gr + [n]): gr.append(int(i))
    gr = sorted(set(gr + [n]))
    if fugen is not None:
        fv = np.asarray(fugen, float); mt = max(m_, int(0.2 / c)); ok = True
        while ok:
            ok = False
            for q in range(len(gr) - 1):
                a_, e_ = gr[q], gr[q + 1]
                if (e_ - a_) * c <= max_lage or e_ - a_ < 2 * mt: continue
                s_ = fv[a_ + mt:e_ - mt]
                if s_.size == 0: continue
                j = int(np.argmax(s_))
                if s_[j] >= min_fuge: gr.insert(q + 1, a_ + mt + j); ok = True; break
    lagen = []
    for q in range(len(gr) - 1):
        a_, e_ = gr[q], gr[q + 1]; w_ = np.array(b[a_:e_], float); w_ = w_[~np.isnan(w_)]
        if w_.size == 0 or (e_ - a_) * c < min_lage: continue
        lagen.append((a_, e_, float(np.median(w_))))
    return lagen


def stossfugen(G, c, maske=None, min_len=0.35, kontrast=6.0):
    """Senkrechte Fugen in einer Steinlage. G: Grauwerte (Zeilen der Lage, Spalten von der Kante nach innen), maske: Steinzellen (sonst alle).
    Spaltenprofil = Median der mittleren 60 % der Zeilen, entrendet (0,3 m); Fuge = lokales Minimum tiefer als max(0,8 x Streuung, kontrast) Grauwerte,
    Mindeststeinlaenge min_len (auch zu beiden Enden), staerkste zuerst. Liefert Fugenlagen in m ab der Kante (aufsteigend)."""
    G = np.asarray(G, float); h, w = G.shape
    if w * c < 2 * min_len or h < 3: return []
    r0 = int(0.2 * h); r1 = max(int(0.8 * h), r0 + 1); X = G[r0:r1].copy()
    if maske is not None: X[~np.asarray(maske, bool)[r0:r1]] = np.nan
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore"); p = np.nanmedian(X, axis=0) if X.size else np.full(w, np.nan)
    g = ~np.isnan(p)
    if g.sum() < 0.6 * w: return []
    p = np.interp(np.arange(w), np.flatnonzero(g), p[g]); f = p - _box(p[:, None], max(3, int(0.3 / c)) | 1)[:, 0]
    s = float(np.std(f)); ml = int(min_len / c); schw = -max(0.8 * s, kontrast)
    kand = [j for j in range(1, w - 1) if f[j] <= f[j - 1] and f[j] <= f[j + 1] and f[j] < schw]
    acc = []
    for j in sorted(kand, key=lambda j: f[j]):
        if j >= ml and w - j >= ml and all(abs(j - q) >= ml for q in acc): acc.append(j)
    return sorted(round(j * c, 3) for j in acc)


def vorsprung_messen(T, F, kl, c_kl, R, zeilen_stein, vmin=0.01, vmax=0.30):
    """Vorsprung Stein gegen Putz aus dem Ebenen-Sweep (tiefe_<fid>.npz: w, gut, u0, z1, zelle). zeilen_stein: Liste (z0, z1, u_a, u_b) der Steine (u_a < u_b, Wandkoordinate),
    Putzvergleich je Stein im Streifen bis 0,8 m daneben (Wandinneres). None, wenn zu wenig gute Zellen oder ausserhalb des Guards."""
    if T is None: return None, "kein Ebenen-Sweep (tiefe_<fid>.npz fehlt)"
    sys.path.insert(0, HIER)
    from nischen_fenster import plausibel
    w = np.asarray(T["w"], float); gut = np.asarray(T["gut"], bool); c = float(T["zelle"]); u0, z1 = float(T["u0"]), float(T["z1"]); H, Wd = w.shape
    uu = u0 + (np.arange(Wd) + 0.5) * c; zz = z1 - (np.arange(H) + 0.5) * c
    ji = np.clip(((uu - float(R["u0"])) / c_kl).astype(int), 0, kl.shape[1] - 1); ii = np.clip(((float(R["z1"]) - zz) / c_kl).astype(int), 0, kl.shape[0] - 1)
    K = kl[np.ix_(ii, ji)]
    st = np.zeros_like(gut); pu = np.zeros_like(gut)
    for z0_, z1_, ua, ub, ui, uj in zeilen_stein:
        rz = (zz >= z0_) & (zz <= z1_)
        st[np.ix_(rz, (uu >= ua) & (uu <= ub))] = True; pu[np.ix_(rz, (uu >= ui) & (uu <= uj))] = True
    st &= (K == 1); pu &= (K == 2)
    gut = gut & plausibel(w, gut, pu)
    if (st & gut).sum() < 20 or (pu & gut).sum() < 20: return None, f"zu wenig gute Sweep-Zellen (Stein {int((st & gut).sum())}, Putz {int((pu & gut).sum())})"
    d = float(np.median(w[st & gut]) - np.median(w[pu & gut]))
    if not vmin <= d <= vmax: return None, f"Sweep-Differenz {d:+.3f} m ausserhalb {vmin}-{vmax} m"
    return round(d, 3), f"Ebenen-Sweep: Median Stein {int((st & gut).sum())} gegen Putz {int((pu & gut).sum())} Zellen"


def mosaik_karte(fein, fid, stufe=2):
    """Klassenbild aus dem feinen Wandbild (Mosaik ortho_<fid>_fein.png: Bezugsfoto + per Homographie ausgerichtete Fotos, fein.json) -> (kl, hell, rgb, daten, n_ausgerichtet).
    Die Einzelbilder ortho_<fid>_einzeln sind NICHT gegeneinander ausgerichtet (Schwabentor f00: Vordach je Foto bis 5 m versetzt) - sie werden erst per ausrichten()
    auf das Mosaik verschoben, dann ergaenzen/bestaetigen sie."""
    from PIL import Image
    p = os.path.join(fein, f"ortho_{fid}_fein.png")
    if not os.path.exists(p): return None, None, None, None, 0
    im = Image.open(p).convert("RGB"); im = im.reduce(stufe) if stufe > 1 else im; a = np.asarray(im)
    try: n_a = sum(1 for x in json.load(open(os.path.join(fein, "fein.json")))[fid]["fotos"] if x.get("rolle") in ("bezug", "ausgerichtet"))
    except Exception: n_a = 0
    return klassen(a), a.astype(np.float32).mean(2), a.copy(), a.astype(np.int32).sum(2) > 30, n_a


def bestaetigen(einz, kl, zonen, min_sicht=0.5, min_einig=0.75, min_iou=0.5):
    """Je Zone (i0, i1, spalten) zaehlen, wie viele AUSGERICHTETE Einzelfotos (einz: dict rgb, dy, dx) dieselbe Stein/Putz-Verteilung zeigen (sehen >= min_sicht der Zone,
    Einigkeit >= min_einig, Stein-IoU >= min_iou). Fremde / falsch ausgerichtete Fotos stimmen so nicht mit. Liefert Liste der Anzahlen."""
    n = [0] * len(zonen)
    for e in einz:
        a = verschieben(e["rgb"], e["dy"], e["dx"])
        for q, (i0, i1, cols) in enumerate(zonen):
            st, pu = stein_putz_karte(a[i0:i1][:, cols]); K = kl[i0:i1][:, cols]; beide = (st | pu) & (K > 0)
            if beide.mean() < min_sicht: continue
            ein = ((st & (K == 1)) | (pu & (K == 2)))[beide].mean(); i_ = (st & (K == 1)).sum(); u_ = ((st | (K == 1)) & beide).sum()
            if ein >= min_einig and u_ > 0 and i_ / u_ >= min_iou: n[q] += 1
    return n


def tor_kante(kl, c, jk, r_, i0, i1, breite, lagen_zeilen, max_b=2.5, min_iou=0.65, min_deckung=0.8):
    """TOR je Kante: gebaute Steinflaeche (lagen_zeilen [(a, e, b_m)] relativ zu i0) gegen die Steinflaeche der Karte (kl == 1) im Streifen ab der Kante (bis max_b),
    nur gesehene Zellen; Deckung = Anteil der Ortsteinzeilen (breite nicht nan) innerhalb gebauter Lagen. Liefert dict(iou, deckung, bestanden, grund)."""
    nb = int(max_b / c); cols = np.clip(jk + r_ * np.arange(0, nb), 0, kl.shape[1] - 1); K = kl[i0:i1][:, cols]
    B = np.zeros(K.shape, bool); innen = np.zeros(i1 - i0, bool)
    for a_, e_, bw in lagen_zeilen: B[a_:e_, :int(round(bw / c))] = True; innen[a_:e_] = True
    seh = K > 0; S = K == 1
    u_ = ((B | S) & seh).sum(); iou = float((B & S & seh).sum() / u_) if u_ else 0.0
    oz = ~np.isnan(np.asarray(breite[i0:i1], float)); deck = float(innen[oz].mean()) if oz.any() else 0.0
    ok = iou >= min_iou and deck >= min_deckung
    return dict(iou=round(iou, 3), deckung=round(deck, 3), bestanden=bool(ok), grund="" if ok else f"IoU {iou:.2f} (min {min_iou}) / Deckung {deck:.2f} (min {min_deckung})")


_VORSCHAU = {}


def fassade_ortsteine(F, fein, tiefe_dir, stufe=2, min_fotos=3, min_einig_ausr=0.8, max_versatz=1.5, **kw):
    """Eine Fassade (fassade_fein/fassaden.json-Eintrag) -> dict mit Kanten/Lagen oder grund."""
    fs = sorted(glob.glob(os.path.join(fein, f"ortho_{F['id']}_einzeln", "*.png")))
    erg = dict(id=F["id"], o=F["o"], d=F["d"], n=F["n"], fotos=len(fs), kanten=[])
    R = F["raster"]; c = float(R["zelle"]) * stufe
    breite_wand = F["u"][1] - F["u"][0]
    if breite_wand < 2 * (kw.get("innen_ab", 2.0) + kw.get("band", 1.5)) - 0.5: erg["grund"] = f"Wand {breite_wand:.1f} m zu schmal fuer Kante + Wandinneres"; return erg
    kl, hell, rgb, daten, n_a = mosaik_karte(fein, F["id"], stufe)
    if kl is None: erg["grund"] = "kein feines Wandbild"; return erg
    erg["mosaik_fotos"] = n_a
    # MEHRFOTO: Einzelbilder auf das Mosaik ausrichten (Verschiebung), Mosaikluecken im Wandrahmen ergaenzen
    einz = einzeln_laden(fs, kl.shape, stufe); gut = []
    for e in einz:
        r = ausrichten(kl, e["kl"], c, max_m=max_versatz)
        if r and r["einig"] >= min_einig_ausr: e.update(r); gut.append(e)
    erg["einzeln_ausgerichtet"] = [dict(foto=os.path.basename(e["datei"]), dy_m=round(-e["dy"] * c, 2), du_m=round(e["dx"] * c, 2), einig=e["einig"]) for e in gut]
    zz = float(R["z1"]) - (np.arange(kl.shape[0]) + 0.5) * c; uu = float(R["u0"]) + (np.arange(kl.shape[1]) + 0.5) * c
    rahmen = ((zz >= F["z"][0]) & (zz <= F["z"][1]))[:, None] & ((uu >= F["u"][0]) & (uu <= F["u"][1]))[None, :]      # nur innerhalb der LoD2-Kanten (daneben sehen Schraegfotos die Nachbarseite)
    kl, hell, rgb, neu = karte_ergaenzen(kl, hell, rgb, daten, rahmen, gut, min_fotos=min_fotos)
    if neu.any():
        zn = zz[neu.any(1)]; erg["ergaenzt"] = dict(flaeche_m2=round(float(neu.sum()) * c * c, 1), z0=round(float(zn.min()), 2), z1=round(float(zn.max()), 2),
                                                    quelle=f">= {min_fotos} ausgerichtete Einzelfotos mit Mehrheit (Mosaik sieht dort nichts)")
    _VORSCHAU[F["id"]] = (rgb, c)
    tp = os.path.join(tiefe_dir, f"tiefe_{F['id']}.npz"); T = dict(np.load(tp)) if os.path.exists(tp) else None
    kand = []; zeilen_je_ende = {}
    for ende, u_k, r_ in (("anfang", F["u"][0], 1), ("ende", F["u"][1], -1)):
        jl = int(round((u_k - float(R["u0"])) / c)) if r_ > 0 else int(round((u_k - float(R["u0"])) / c)) - 1
        jk = steinkante(kl, c, jl, r_); u_s = float(R["u0"]) + (jk + (0 if r_ > 0 else 1)) * c        # Fotokante der Steine (u)
        zonen, b = kanten_zonen(kl, c, jk, r_, **{k: v for k, v in kw.items() if k in ("max_b", "innen_ab", "band", "rand", "min_hoehe")})
        zeilen_je_ende[ende] = round(float((~np.isnan(b)).sum()) * c, 2)
        for i0, i1 in zonen:
            cols = np.clip(jk + r_ * np.arange(0, int(kw.get("max_b", 2.5) / c)), 0, kl.shape[1] - 1)
            kand.append((ende, u_k, r_, jk, u_s, i0, i1, b, cols))
    erg["ortsteinzeilen_m"] = zeilen_je_ende
    best = bestaetigen(gut, kl, [(k_[5], k_[6], k_[8]) for k_ in kand]) if kand else []
    for (ende, u_k, r_, jk, u_s, i0, i1, b, cols), nb_ in zip(kand, best):
        zr = dict(ende=ende, z0=round(float(R["z1"]) - i1 * c, 2), z1=round(float(R["z1"]) - i0 * c, 2))
        if nb_ < min_fotos:
            erg.setdefault("verworfen", []).append(dict(zr, grund=f"Formfamilie nur in {nb_} ausgerichteten Einzelfotos bestaetigt (< {min_fotos})"))
            continue
        cs_ = cols[:max(2, int(0.8 / c))]                                    # Lagerfugen im Steinstreifen an der Kante (laufen quer durch)
        lg = steinlagen(b[i0:i1], fugen_profil(hell[i0:i1][:, cs_], kl[i0:i1][:, cs_], c), c)
        if len(lg) < 2: erg.setdefault("verworfen", []).append(dict(zr, grund=f"nur {len(lg)} Lage(n)")); continue
        tor = tor_kante(kl, c, jk, r_, i0, i1, b, lg, max_b=kw.get("max_b", 2.5))
        steine = []
        for a_, e_, bw in lg:
            z_hi = float(R["z1"]) - (i0 + a_) * c; z_lo = float(R["z1"]) - (i0 + e_) * c; bw = max(bw, druck_m(1.0)); nbw = max(1, int(round(bw / c)))
            cc = np.clip(jk + r_ * np.arange(nbw), 0, kl.shape[1] - 1)
            fu = stossfugen(hell[i0 + a_:i0 + e_][:, cc], c, maske=kl[i0 + a_:i0 + e_][:, cc] == 1)
            gr_ = [0.0] + [f_ for f_ in fu if f_ < bw] + [bw]
            teile = sorted([(round(u_s + gr_[q], 3), round(u_s + gr_[q + 1], 3)) if r_ > 0 else (round(u_s - gr_[q + 1], 3), round(u_s - gr_[q], 3)) for q in range(len(gr_) - 1)])
            steine.append(dict(z0=round(z_lo, 3), z1=round(z_hi, 3), b=round(bw, 3), teile=[list(t) for t in teile]))
        steine.sort(key=lambda s: s["z0"])
        zs = [(s["z0"], s["z1"]) + ((u_s, u_s + s["b"], u_s + s["b"] + 0.1, u_s + s["b"] + 0.8) if r_ > 0 else (u_s - s["b"], u_s, u_s - s["b"] - 0.8, u_s - s["b"] - 0.1)) for s in steine]
        v, vq = vorsprung_messen(T, F, kl, c, R, zs)
        bs = np.array([s["b"] for s in steine]); mitte = 0.5 * (np.percentile(bs, 25) + np.percentile(bs, 75))
        art = ["lang" if x > mitte else "kurz" for x in bs]; wech = float(np.mean([p != q for p, q in zip(art[:-1], art[1:])])) if len(art) > 1 else 0.0
        hl = np.array([s["z1"] - s["z0"] for s in steine])
        erg["kanten"].append(dict(ende=ende, u_kante=round(u_k, 3), u_stein=round(u_s, 3), richtung=r_, z0=steine[0]["z0"], z1=steine[-1]["z1"], lagen=len(steine),
                                  lage_median_m=round(float(np.median(hl)), 3), stossfugen=int(sum(len(s["teile"]) - 1 for s in steine)),
                                  lang_m=round(float(np.median(bs[bs > mitte])), 3) if (bs > mitte).any() else round(float(bs.max()), 3), kurz_m=round(float(np.median(bs[bs <= mitte])), 3),
                                  zahnung=round(wech, 2), vorsprung_m=v, vorsprung_quelle=vq, fotos_bestaetigt=int(nb_), tor=tor,
                                  aus_ergaenzung=bool(neu[i0:i1].any()), steine=steine))
    return erg


def ortsteine_erkennen(fein, tiefe_dir=None, nur=None, **kw):
    """Alle Fassaden des Wandbild-Ordners. tiefe_dir: Ordner mit tiefe_<fid>.npz (Standard: Geschwister 'fassade')."""
    FF = json.load(open(os.path.join(fein, "fassaden.json")))["fassaden"]
    tiefe_dir = tiefe_dir or os.path.join(os.path.dirname(os.path.abspath(fein)), "fassade")
    J = dict(quelle="tools/ortsteine.py", fein=fein, druckmass_m=round(druck_m(1.0), 4),
             fassaden=[fassade_ortsteine(F, fein, tiefe_dir, **kw) for F in FF if F.get("raster") and (nur is None or F["id"] in nur)])
    ks = [K for Fa in J["fassaden"] for K in Fa["kanten"]]
    J["tor"] = dict(kanten=len(ks), bestanden=sum(1 for K in ks if K["tor"]["bestanden"]), verworfen=[f"{Fa['id']} {K['ende']} z {K['z0']:.1f}-{K['z1']:.1f}: {K['tor']['grund']}"
                    for Fa in J["fassaden"] for K in Fa["kanten"] if not K["tor"]["bestanden"]])
    return J


def bild_zeichnen(J, aus, stufe_bild=2):
    """Beleg-Bild: je Fassade mit Kanten das (ergaenzte) Wandbild, daneben dasselbe mit den erkannten Steinen (cyan = durch das Tor, rot = verworfen; Teilsteine einzeln).
    Nur aus den Zwischendaten dieses Laufs (_VORSCHAU aus fassade_ortsteine)."""
    from PIL import Image, ImageDraw
    kacheln = []
    for Fa in J["fassaden"]:
        if Fa["id"] not in _VORSCHAU or not (Fa["kanten"] or Fa.get("verworfen")): continue
        rgb, c = _VORSCHAU[Fa["id"]]; im = Image.fromarray(rgb); im = im.reduce(stufe_bild) if stufe_bild > 1 else im; cb = c * stufe_bild
        ov = im.copy(); d = ImageDraw.Draw(ov); R = None
        for K in Fa["kanten"]:
            col = (0, 255, 255) if K["tor"]["bestanden"] else (255, 0, 0)
            for s in K["steine"]:
                for ua, ub in s["teile"]:
                    d.rectangle([(ua - Fa["_u0"]) / cb, (Fa["_z1"] - s["z1"]) / cb, (ub - Fa["_u0"]) / cb, (Fa["_z1"] - s["z0"]) / cb], outline=col)
        for v in Fa.get("verworfen", []):
            x = 2 if v["ende"] == "anfang" else im.size[0] - 3; d.line([(x, (Fa["_z1"] - v["z1"]) / cb), (x, (Fa["_z1"] - v["z0"]) / cb)], fill=(255, 128, 0), width=3)
        d.text((4, 4), Fa["id"], fill=(255, 255, 0))
        kacheln.append(np.hstack([np.asarray(im), np.asarray(ov), np.full((im.size[1], 8, 3), 255, np.uint8)]))
    if not kacheln: return None
    H = max(k.shape[0] for k in kacheln)
    Image.fromarray(np.hstack([np.pad(k, ((0, H - k.shape[0]), (0, 0), (0, 0))) for k in kacheln])).save(aus, quality=88)
    return aus


def ortsteine_bauen(koerper, J, einbinden=0.10, probe_ab=0.25, min_formfotos=3):
    """Bloecke aus ortsteine_erkennen() an den Koerper. Je Stein: Putzflaeche daneben per Strahl (bauteile._oberflaeche_w), Block von dort -einbinden bis +Vorsprung,
    u von der Kante (um den Vorsprung um die Ecke) bis Steinbreite; Teilsteine (Stossfugen) mit Druckmass-Fuge. Kanten mit durchgefallenem Tor werden nicht gebaut.
    Liefert (koerper, belege)."""
    sys.path.insert(0, HIER)
    from bauteile import Wand, _oberflaeche_w
    belege = []; v_min = druck_m(0.5); fuge = druck_m(1.0)
    for Fa in J.get("fassaden", []):
        if not Fa.get("kanten"): continue
        o = np.asarray(Fa["o"], float); d = np.asarray(Fa["d"], float); n = np.asarray(Fa["n"], float); W = Wand(o, o + d, o + n)
        for K in Fa["kanten"]:
            st = K["steine"]; r_ = K["richtung"]; u_s = K.get("u_stein", K["u_kante"])
            u_k = min(K["u_kante"], u_s) if r_ > 0 else max(K["u_kante"], u_s)     # Block deckt die Koerperecke (LoD2) UND die Fotokante
            fm = int(K.get("fotos_bestaetigt", 0))
            if fm < min_formfotos: belege.append(dict(seite="wand", element=f"Ortsteine {Fa['id']} {K['ende']} NICHT gebaut", quelle="tools/ortsteine.py", hinweis=f"Formfamilie nur aus {fm} Fotos (< {min_formfotos})")); continue
            if K.get("tor") and not K["tor"].get("bestanden", True):
                belege.append(dict(seite="wand", element=f"Ortsteine {Fa['id']} {K['ende']} z {K['z0']:.1f}-{K['z1']:.1f} NICHT gebaut (Tor)", quelle="tools/ortsteine.py tor_kante", hinweis=K["tor"].get("grund", ""))); continue
            gemessen = K.get("vorsprung_m") is not None
            vor = max(K["vorsprung_m"], v_min) if gemessen else v_min
            pk = [(u_s + r_ * (s["b"] + probe_ab), 0.5 * (s["z0"] + s["z1"])) for s in st]
            ws = _oberflaeche_w(koerper, W, pk)
            gebaut = []; teile = None; n_teil = 0
            for q, (s, w_s) in enumerate(zip(st, ws)):
                if w_s is None: continue
                z0_, z1_ = s["z0"], s["z1"]
                if q + 1 < len(st) and abs(st[q + 1]["b"] - s["b"]) < 0.12 and st[q + 1]["z0"] - z1_ < fuge: z1_ = z1_ - fuge     # gleich lange Nachbarlage: Lagerfuge (Druckmass)
                if z1_ - z0_ < druck_m(1.0): continue
                tl = s.get("teile") or [[u_s, u_s + s["b"]] if r_ > 0 else [u_s - s["b"], u_s]]
                tl = sorted(tl); m_ = len(tl)
                for t, (ua, ub) in enumerate(tl):
                    aussen = (t == 0) if r_ > 0 else (t == m_ - 1)               # Teilstein an der Ecke: um die Ecke gefuehrt
                    if aussen: ua, ub = (u_k - vor, ub) if r_ > 0 else (ua, u_k + vor)
                    if t > 0: ua += fuge / 2
                    if t < m_ - 1: ub -= fuge / 2
                    if ub - ua < druck_m(1.0): continue
                    k_ = W.kasten(ua, ub, z0_, z1_, w_s - einbinden, w_s + vor); teile = k_ if teile is None else teile + k_; n_teil += 1
                gebaut.append(dict(z0=round(z0_, 2), z1=round(z1_, 2), b=s["b"], teile=m_, w=round(w_s, 3)))
            if teile is None: continue
            koerper = koerper + teile
            belege.append(dict(seite="wand", element=f"Ortsteine/Eckverzahnung Fassade {Fa['id']} am Wand{K['ende']}: {len(gebaut)} Lagen ({n_teil} Steine), z {K['z0']:.1f}..{K['z1']:.1f}, lang {K['lang_m']:.2f} / kurz {K['kurz_m']:.2f} m, Zahnung {K['zahnung']:.2f}",
                               quelle=f"tools/ortsteine.py: Stein/Putz (Farbe) im feinen Wandbild (Mosaik aus {Fa.get('mosaik_fotos')} ausgerichteten Fotos"
                                      + (", Luecken aus ausgerichteten Einzelfotos ergaenzt" if K.get("aus_ergaenzung") else "") + f"), Formfamilie in {fm} von {Fa.get('fotos')} Einzelfotos bestaetigt, "
                                      f"Lagen aus Breitenspruengen + Lagerfugen, Stossfugen aus dunklen Spalten; Tor IoU {(K.get('tor') or {}).get('iou')}; Lage vor der echten Koerperflaeche (Strahltreffer)",
                               ortsteine=gebaut, vorsprung_m=round(vor, 3),
                               hinweis=(f"Vorsprung gemessen {K['vorsprung_m']} m ({K['vorsprung_quelle']})" + (f", auf Druckmass {v_min:.3f} m angehoben" if K['vorsprung_m'] < v_min else "") if gemessen else
                                        f"ANNAHME: Vorsprung = Druckmass {v_min:.3f} m ({K['vorsprung_quelle']})") + f"; Einbindung {einbinden} m (ANNAHME), Lager-/Stossfuge {fuge:.3f} m (Druckmass)"))
    return koerper, belege


def ortsteine_anbauen(koerper, objekt_json):
    """Generator-/Kettenaufruf: audit/ortsteine_auto.json (oder ORTSTEINE_JSON) lesen, sonst aus dem Wandbild rechnen (fassaden_kette.fein_ordner). OHNE_ORTSTEINE=1 = alter Stand."""
    if os.environ.get("OHNE_ORTSTEINE") == "1": return koerper, []
    od = os.path.dirname(os.path.abspath(objekt_json)); jp = os.environ.get("ORTSTEINE_JSON") or os.path.join(od, "audit", "ortsteine_auto.json")
    J = None
    if os.path.exists(jp):
        try: J = json.load(open(jp))
        except Exception: J = None
    if J is None:
        sys.path.insert(0, HIER)
        from fassaden_kette import fein_ordner
        ffn = fein_ordner(objekt_json)
        if not ffn: return koerper, []
        try: J = ortsteine_erkennen(ffn)
        except Exception as e:
            print(f"    ortsteine: FEHLER {type(e).__name__}: {str(e)[:160]}", flush=True)
            return koerper, [dict(seite="wand", element="Ortsteine NICHT gebaut", quelle="tools/ortsteine.py", hinweis=f"{type(e).__name__}: {str(e)[:160]}")]
    return ortsteine_bauen(koerper, J)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("objekt_json"); ap.add_argument("--aus", required=True, help="JSON-Ausgabe (Kette: modelle/<obj>/audit/ortsteine_auto.json)")
    ap.add_argument("--fein", help="Wandbild-Ordner (Standard: fassaden_kette.fein_ordner)"); ap.add_argument("--bild", help="Beleg-Bild (Kette: audit/ortsteine_auto.jpg)")
    ap.add_argument("--nur", nargs="*"); ap.add_argument("--stufe", type=int, default=2)
    a = ap.parse_args()
    sys.path.insert(0, HIER)
    ffn = a.fein
    if not ffn:
        from fassaden_kette import fein_ordner
        ffn = fein_ordner(a.objekt_json)
    if not ffn or not os.path.exists(os.path.join(ffn, "fassaden.json")): print("kein Wandbild (fassade_fein)"); return 3
    J = ortsteine_erkennen(ffn, nur=a.nur, stufe=a.stufe)
    for Fa in J["fassaden"]:                                              # Rasterbezug fuer das Bild (nicht ins JSON)
        F = next((F for F in json.load(open(os.path.join(ffn, "fassaden.json")))["fassaden"] if F["id"] == Fa["id"]), None)
        if F: Fa["_u0"], Fa["_z1"] = float(F["raster"]["u0"]), float(F["raster"]["z1"])
    if a.bild: bild_zeichnen(J, a.bild)
    for Fa in J["fassaden"]: Fa.pop("_u0", None); Fa.pop("_z1", None)
    os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True); json.dump(J, open(a.aus, "w"), indent=1, ensure_ascii=False)
    for Fa in J["fassaden"]:
        print(Fa["id"], Fa.get("grund", ""), f"ausgerichtet {len(Fa.get('einzeln_ausgerichtet', []))}", f"ergaenzt {Fa.get('ergaenzt')}" if Fa.get("ergaenzt") else "")
        for K in Fa["kanten"]:
            print(f"   {K['ende']}: z {K['z0']:.1f}-{K['z1']:.1f}, {K['lagen']} Lagen (Median {K['lage_median_m']} m), {K['stossfugen']} Stossfugen, lang {K['lang_m']} kurz {K['kurz_m']}, "
                  f"Zahnung {K['zahnung']}, vor {K['vorsprung_m']}, Fotos {K['fotos_bestaetigt']}, Tor {'OK' if K['tor']['bestanden'] else 'VERWORFEN'} IoU {K['tor']['iou']} Deckung {K['tor']['deckung']}")
        for v in Fa.get("verworfen", []): print(f"   verworfen {v['ende']} z {v['z0']}-{v['z1']}: {v['grund']}")
    print(f"TOR: {J['tor']['bestanden']} von {J['tor']['kanten']} Kanten bestanden")
    if not J["tor"]["kanten"]: return 3
    return 0 if J["tor"]["bestanden"] == J["tor"]["kanten"] else 2


if __name__ == "__main__":
    sys.exit(main())
