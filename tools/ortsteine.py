#!/usr/bin/env python3
"""ortsteine.py - ORTSTEINE / ECKVERZAHNUNG aus dem Wandbild (GENERISCH, 24.11.2026; Grundsatz WANDBILD = BAUPLAN, keine Musterteile, kein Hardcoding).

ANLASS (Befund Kettenlauf 1122u/v, Schwabentor Sued + Nord): an allen Turmkanten sitzen versetzte rote Sandstein-Eckquader (abwechselnd lang/kurz in die
Putzflaeche greifend, vor dem Putz) - im Modell sind die Kanten glatt. Die vorhandene Eckquader-Erkennung (bauteile.eckquader_aus_relief, quader_raster.eckquader_bloecke)
benennt nur Steine, die im gebauten Fotorelief schon stehen; wo das Relief an der Kante fehlt oder zu Putz geglaettet wurde, entsteht nichts.

ABLAUF (nur Daten der Kette, nichts von Hand):
  stein_putz_karte(rgb)      Putz = unbunt (Rot-Blau-Anteil unter der Otsu-Schwelle des Bildes) UND hell (ueber dem Bild-eigenen Hellwert des unbunten Anteils);
                             Himmel (blau) / keine Daten / dunkel-unbunt = unbekannt; rot/braun = Stein.
  mosaik_karte(fein, fid)    Klassenbild aus dem feinen Wandbild (Mosaik aus Bezugsfoto + ausgerichteten Fotos). Die Einzelbilder sind NICHT gegeneinander ausgerichtet
                             (Schwabentor f00: bis 5 m versetzt, ein Foto der Gegenseite) - Zellen-Mehrheit ueber sie verschmiert die Kanten.
  steinkante(...)            Fotokante der Steine nahe der LoD2-Kante (Schwabentor: 0,3-0,5 m daneben, Nachbarwand hell).
  kanten_zonen(...)          je Wandende: Zeilen, in denen das Wandinnere (Band ab innen_ab) Putz ist UND ab der Kante (je Zeile +-0,3 m gesucht) ein Steinstreifen
                             beginnt = Ortsteinzone (volles Quadermauerwerk zaehlt nicht). Steinbreite je Zeile = ab der Kante bis zum ersten Putzlauf.
  bestaetigen(...)           Formfamilie je Zone: Einzelfotos, deren Stein/Putz-Verteilung dort mit dem Mosaik uebereinstimmt (>= 3, sonst nicht gebaut).
  steinlagen(b, hell, ...)   Lagen: Spruenge im Breitenprofil (lang <-> kurz) + Lagerfugen (dunkle Zeilen im Randstreifen, Lagenhoehe aus der Fugen-Periodik)
                             fuer lange gleich breite Laeufe.
  vorsprung_messen(...)      Vorsprung = Median der Ebenen-Sweep-Tiefe (fassade/tiefe_<fid>.npz) der Steinzellen minus Putzzellen daneben (gleiche Zeilen);
                             Guard 0,01-0,30 m, sonst ANNAHME = Druckmass.
  ortsteine_erkennen(...)    alles je Fassade -> JSON-faehiges dict (Kette/Probe: ortsteine.py <objekt.json> --aus x.json).
  ortsteine_bauen(koerper, J) Bloecke vor die ECHTE Koerperflaeche (Strahltreffer neben dem Stein, bauteile._oberflaeche_w), um die Ecke um den Vorsprung gefuehrt;
                             Lagerfuge (Druckmass) nur zwischen gleich langen Nachbarlagen (sonst zeigt der Sprung die Lage).
  ortsteine_anbauen(koerper, objekt_json)  Aufruf fuer fassaden_kette.anbauen / Generator: audit/ortsteine_auto.json wenn da (oder ORTSTEINE_JSON), sonst direkt rechnen.
DRUCK (1:SCALE, MINMM): Lage >= MINMM, Steinbreite >= MINMM, Vorsprung >= 0,5 x MINMM (wie quader_raster Rillentiefe), Lagerfuge = MINMM - alle als Mass im Modell.
ANNAHMEN: Einbindung 0,10 m hinter die Flaeche; Stirn eben (Bossen nicht gemessen). Abschalten: OHNE_ORTSTEINE=1. Nur numpy/scipy/PIL (Generator-venv).
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


def _box(a, k):
    """Mittelwert im (k x k)-Fenster, nur numpy."""
    if k <= 1: return np.asarray(a, np.float64)
    a = np.asarray(a, np.float64)
    for ax in (0, 1):
        p = np.pad(a, [(k // 2, k - 1 - k // 2) if q == ax else (0, 0) for q in range(2)], mode="edge"); c = np.cumsum(p, axis=ax)
        c = np.concatenate([np.zeros_like(np.take(c, [0], axis=ax)), c], axis=ax); a = (np.take(c, range(k, c.shape[ax]), axis=ax) - np.take(c, range(0, c.shape[ax] - k), axis=ax)) / k
    return a


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


def kanten_zonen(kl, c, j_kante, richtung, max_b=2.5, innen_ab=2.0, band=1.5, rand=0.15, min_stein=0.6, min_putz=0.6, min_sicht=0.5, min_hoehe=3.0, luecke=1.0, suche=0.3):
    """kl: Klassenbild (Zeile 0 = oben), c m/Zelle, j_kante = Spalte der Steinkante (steinkante), richtung +1 (Kante links, Wand rechts davon) / -1.
    Liefert (zonen [(i0, i1)], breite je Zeile in m ab j_kante (nan = keine Ortsteinzeile))."""
    H, Wd = kl.shape; nb, ni, nn, nr = int(max_b / c), int(innen_ab / c), int(band / c), max(1, int(rand / c)); ns = int(suche / c)
    cols = j_kante + richtung * np.arange(-ns, ni + nn)
    if cols.min() < 0 or cols.max() >= Wd: cols = np.clip(cols, 0, Wd - 1)
    S = kl[:, cols]; stein = (S == 1).astype(np.float64); putz = (S == 2).astype(np.float64); seh = (S > 0); o_ = ns   # Spalte o_ = j_kante
    b_pu = putz[:, o_ + ni:].sum(1) / np.maximum(seh[:, o_ + ni:].sum(1), 1); b_seh = seh[:, o_ + ni:].mean(1)
    zeile = (b_pu >= min_putz) & (b_seh >= min_sicht)
    ss = _box(stein[:, :o_ + nb], 3) >= 0.5; ps = _box(putz[:, :o_ + nb], 3) >= 0.5; lauf = max(2, int(0.10 / c)); breite = np.full(H, np.nan); eins = np.ones(lauf, int)
    for i in np.flatnonzero(zeile):
        # Steinbeginn je Zeile im Fenster +-suche um die Kante (Fotokante schwankt je Hoehe um 10-20 cm: Ausrichtung des Mosaiks, Kantensaum), dann Randstreifen Stein,
        # Steinbreite = erster Putzlauf (>= 10 cm) danach - gezaehlt ab j_kante (Block deckt Kante bis Steinende)
        ks = np.flatnonzero(np.convolve(ss[i, :2 * ns + 1 + lauf].astype(int), eins, "valid") >= lauf)
        if not ks.size: zeile[i] = False; continue
        a_ = int(ks[0]); r_ = S[i, a_:a_ + nr]; sr = r_ > 0
        if sr.mean() < min_sicht or (r_ == 1).sum() < min_stein * max(sr.sum(), 1): zeile[i] = False; continue
        k = np.flatnonzero(np.convolve(ps[i, a_:].astype(int), eins, "valid") >= lauf)
        if k.size and k[0] * c >= rand: breite[i] = (a_ + k[0] - o_) * c
        else: zeile[i] = False
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


def lagen_periode(hell, c, lo=0.18, hi=1.2, min_r=0.15):
    """Lagenhoehe (m) aus der Autokorrelation des entrendeten Helligkeitsprofils (Lagerfugen dunkel, periodisch); None ohne deutliche Spitze (r >= min_r)."""
    h = np.asarray(hell, float)
    if h.size < int(3 * hi / c): return None
    f = h - _box(h[:, None], max(3, int(hi / c)) | 1)[:, 0]; f = f - f.mean(); n = f.size
    ac = np.correlate(f, f, "full")[n - 1:] / (np.dot(f, f) + 1e-9)
    a, b = max(1, int(lo / c)), min(n - 1, int(hi / c))
    if b <= a + 2: return None
    seg = ac[a:b]; pk = [i for i in range(1, len(seg) - 1) if seg[i] >= seg[i - 1] and seg[i] >= seg[i + 1] and seg[i] >= min_r]
    return (a + pk[0]) * c if pk else None


def steinlagen(b, hell, c, sprung=0.12, min_lage=None, fenster=0.08, max_lage=None):
    """Lagen einer Ortsteinzone. b: Breite je Zeile (m, nan = Luecke, Zeile 0 = oben), hell: mittlere Helligkeit des Randstreifens je Zeile (Fugen dunkel).
    Grenzen = Spruenge im Breitenprofil (|Median oben - Median unten| >= sprung) und - nur in Laeufen laenger als max_lage - die dunkelste Fugenzeile.
    Liefert [(i0, i1, breite_m)] von oben nach unten; Lagen < min_lage (Druckmass) werden dem Nachbarn zugeschlagen."""
    min_lage = druck_m(1.0) * 2.5 if min_lage is None else min_lage
    n = len(b); k = max(2, int(fenster / c)); bb = np.array(b, float)
    if np.isnan(bb).all(): return []
    idx = np.arange(n); g = ~np.isnan(bb); bb = np.interp(idx, idx[g], bb[g])
    d = np.zeros(n)
    for i in range(k, n - k): d[i] = abs(np.median(bb[i - k:i]) - np.median(bb[i:i + k]))
    gr = [0]; m_ = int(min_lage / c)
    for i in np.argsort(-d):                                              # staerkste Spruenge zuerst, Mindestabstand min_lage
        if d[i] < sprung: break
        if all(abs(i - q) >= m_ for q in gr + [n]): gr.append(int(i))
    gr = sorted(set(gr + [n]))
    hs = [gr[q + 1] - gr[q] for q in range(len(gr) - 1)]; med = np.median(hs) * c if hs else 0.0
    if max_lage is None:
        p_ = lagen_periode(hell, c, lo=min_lage) if hell is not None else None      # Lagenhoehe aus der Fugen-Periodik des Randstreifens, sonst aus den Spruengen
        max_lage = 1.5 * p_ if p_ else (1.6 * med if med > 0 else 1.0)
    if hell is not None:                                                  # lange Laeufe gleicher Breite an der dunkelsten Fugenzeile teilen
        hv = np.asarray(hell, float); ok = True
        while ok:
            ok = False
            for q in range(len(gr) - 1):
                a_, e_ = gr[q], gr[q + 1]
                if (e_ - a_) * c <= max_lage: continue
                s_ = hv[a_ + m_:e_ - m_]
                if s_.size < 3: continue
                tr = _box(s_[:, None], max(3, int(0.3 / c)))[:, 0]; f_ = s_ - tr; j = int(np.argmin(f_))
                if f_[j] < -0.5 * np.std(s_): gr.insert(q + 1, a_ + m_ + j); ok = True; break
    lagen = []
    for q in range(len(gr) - 1):
        a_, e_ = gr[q], gr[q + 1]; w_ = np.array(b[a_:e_], float); w_ = w_[~np.isnan(w_)]
        if w_.size == 0 or (e_ - a_) * c < min_lage: continue
        lagen.append((a_, e_, float(np.median(w_))))
    return lagen


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
    """Klassenbild aus dem feinen Wandbild (Mosaik ortho_<fid>_fein.png: Bezugsfoto + per Homographie ausgerichtete Fotos, fein.json) -> (kl, hell, n_ausgerichtet).
    24.11.2026: die Einzelbilder ortho_<fid>_einzeln sind NICHT gegeneinander ausgerichtet (Schwabentor f00: Vordach je Foto bis 5 m versetzt, ein Foto der Gegenseite) -
    eine Zellen-Mehrheit ueber sie verschmiert die Kanten; sie dienen nur zur Bestaetigung je Zone (bestaetigen)."""
    from PIL import Image
    p = os.path.join(fein, f"ortho_{fid}_fein.png")
    if not os.path.exists(p): return None, None, 0
    im = Image.open(p).convert("RGB"); im = im.reduce(stufe) if stufe > 1 else im; a = np.asarray(im)
    st, pu = stein_putz_karte(a); kl = np.zeros(st.shape, np.uint8); kl[st] = 1; kl[pu] = 2
    try: n_a = sum(1 for x in json.load(open(os.path.join(fein, "fein.json")))[fid]["fotos"] if x.get("rolle") in ("bezug", "ausgerichtet"))
    except Exception: n_a = 0
    return kl, a.astype(np.float32).mean(2), n_a


def bestaetigen(dateien, kl, zonen, stufe=2, min_sicht=0.5, min_einig=0.75, min_iou=0.5):
    """Je Zone (i0, i1, spalten) zaehlen, wie viele Einzelfotos dieselbe Stein/Putz-Verteilung zeigen (sehen >= min_sicht der Zone, Einigkeit >= min_einig,
    Stein-IoU >= min_iou). Fehl ausgerichtete Fotos stimmen so nicht mit. Liefert Liste der Anzahlen."""
    from PIL import Image
    n = [0] * len(zonen)
    for f in dateien:
        try: im = Image.open(f).convert("RGB")
        except Exception: continue
        if stufe > 1: im = im.reduce(stufe)
        a = np.asarray(im)
        if a.shape[:2] != kl.shape: continue
        for q, (i0, i1, cols) in enumerate(zonen):
            st, pu = stein_putz_karte(a[i0:i1][:, cols]); K = kl[i0:i1][:, cols]; beide = (st | pu) & (K > 0)
            if beide.mean() < min_sicht: continue
            ein = ((st & (K == 1)) | (pu & (K == 2)))[beide].mean(); i_ = (st & (K == 1)).sum(); u_ = ((st | (K == 1)) & beide).sum()
            if ein >= min_einig and u_ > 0 and i_ / u_ >= min_iou: n[q] += 1
    return n


def fassade_ortsteine(F, fein, tiefe_dir, stufe=2, min_fotos=3, **kw):
    """Eine Fassade (fassade_fein/fassaden.json-Eintrag) -> dict mit Kanten/Lagen oder grund."""
    fs = sorted(glob.glob(os.path.join(fein, f"ortho_{F['id']}_einzeln", "*.png")))
    erg = dict(id=F["id"], o=F["o"], d=F["d"], n=F["n"], fotos=len(fs), kanten=[])
    R = F["raster"]; c = float(R["zelle"]) * stufe
    breite_wand = F["u"][1] - F["u"][0]
    if breite_wand < 2 * (kw.get("innen_ab", 2.0) + kw.get("band", 1.5)) - 0.5: erg["grund"] = f"Wand {breite_wand:.1f} m zu schmal fuer Kante + Wandinneres"; return erg
    kl, hell, n_a = mosaik_karte(fein, F["id"], stufe)
    if kl is None: erg["grund"] = "kein feines Wandbild"; return erg
    erg["mosaik_fotos"] = n_a
    tp = os.path.join(tiefe_dir, f"tiefe_{F['id']}.npz"); T = dict(np.load(tp)) if os.path.exists(tp) else None
    kand = []
    for ende, u_k, r_ in (("anfang", F["u"][0], 1), ("ende", F["u"][1], -1)):
        jl = int(round((u_k - float(R["u0"])) / c)) if r_ > 0 else int(round((u_k - float(R["u0"])) / c)) - 1
        jk = steinkante(kl, c, jl, r_); u_s = float(R["u0"]) + (jk + (0 if r_ > 0 else 1)) * c        # Fotokante der Steine (u)
        zonen, b = kanten_zonen(kl, c, jk, r_, **{k: v for k, v in kw.items() if k in ("max_b", "innen_ab", "band", "rand", "min_hoehe")})
        for i0, i1 in zonen:
            cols = np.clip(jk + r_ * np.arange(0, int(kw.get("max_b", 2.5) / c)), 0, kl.shape[1] - 1)
            kand.append((ende, u_k, r_, jk, u_s, i0, i1, b, cols))
    best = bestaetigen(fs, kl, [(k_[5], k_[6], k_[8]) for k_ in kand], stufe=stufe) if kand else []
    for (ende, u_k, r_, jk, u_s, i0, i1, b, cols), nb_ in zip(kand, best):
        if nb_ < min_fotos:
            erg.setdefault("verworfen", []).append(dict(ende=ende, z0=round(float(R["z1"]) - i1 * c, 2), z1=round(float(R["z1"]) - i0 * c, 2), grund=f"Formfamilie nur in {nb_} Einzelfotos bestaetigt (< {min_fotos})"))
            continue
        hs = hell[i0:i1][:, cols[:max(2, int(0.3 / c))]].mean(1)
        lg = steinlagen(b[i0:i1], hs, c)
        if len(lg) < 2: continue
        steine = []
        for a_, e_, bw in lg:
            z_hi = float(R["z1"]) - (i0 + a_) * c; z_lo = float(R["z1"]) - (i0 + e_) * c
            steine.append(dict(z0=round(z_lo, 3), z1=round(z_hi, 3), b=round(max(bw, druck_m(1.0)), 3)))
        steine.sort(key=lambda s: s["z0"])
        zs = [(s["z0"], s["z1"]) + ((u_s, u_s + s["b"], u_s + s["b"] + 0.1, u_s + s["b"] + 0.8) if r_ > 0 else (u_s - s["b"], u_s, u_s - s["b"] - 0.8, u_s - s["b"] - 0.1)) for s in steine]
        v, vq = vorsprung_messen(T, F, kl, c, R, zs)
        bs = np.array([s["b"] for s in steine]); mitte = 0.5 * (np.percentile(bs, 25) + np.percentile(bs, 75))
        art = ["lang" if x > mitte else "kurz" for x in bs]; wech = float(np.mean([p != q for p, q in zip(art[:-1], art[1:])])) if len(art) > 1 else 0.0
        erg["kanten"].append(dict(ende=ende, u_kante=round(u_k, 3), u_stein=round(u_s, 3), richtung=r_, z0=steine[0]["z0"], z1=steine[-1]["z1"], lagen=len(steine),
                                  lang_m=round(float(np.median(bs[bs > mitte])), 3) if (bs > mitte).any() else round(float(bs.max()), 3), kurz_m=round(float(np.median(bs[bs <= mitte])), 3),
                                  zahnung=round(wech, 2), vorsprung_m=v, vorsprung_quelle=vq, fotos_bestaetigt=int(nb_), steine=steine))
    return erg


def ortsteine_erkennen(fein, tiefe_dir=None, nur=None, **kw):
    """Alle Fassaden des Wandbild-Ordners. tiefe_dir: Ordner mit tiefe_<fid>.npz (Standard: Geschwister 'fassade')."""
    FF = json.load(open(os.path.join(fein, "fassaden.json")))["fassaden"]
    tiefe_dir = tiefe_dir or os.path.join(os.path.dirname(os.path.abspath(fein)), "fassade")
    return dict(quelle="tools/ortsteine.py", fein=fein, druckmass_m=round(druck_m(1.0), 4),
                fassaden=[fassade_ortsteine(F, fein, tiefe_dir, **kw) for F in FF if F.get("raster") and (nur is None or F["id"] in nur)])


def ortsteine_bauen(koerper, J, einbinden=0.10, probe_ab=0.25, min_formfotos=3):
    """Bloecke aus ortsteine_erkennen() an den Koerper. Je Stein: Putzflaeche daneben per Strahl (bauteile._oberflaeche_w), Block von dort -einbinden bis +Vorsprung,
    u von der Kante (um den Vorsprung um die Ecke) bis Steinbreite. Liefert (koerper, belege)."""
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
            gemessen = K.get("vorsprung_m") is not None
            vor = max(K["vorsprung_m"], v_min) if gemessen else v_min
            pk = [(u_s + r_ * (s["b"] + probe_ab), 0.5 * (s["z0"] + s["z1"])) for s in st]
            ws = _oberflaeche_w(koerper, W, pk)
            gebaut = []; teile = None
            for q, (s, w_s) in enumerate(zip(st, ws)):
                if w_s is None: continue
                z0_, z1_ = s["z0"], s["z1"]
                if q + 1 < len(st) and abs(st[q + 1]["b"] - s["b"]) < 0.12 and st[q + 1]["z0"] - z1_ < fuge: z1_ = z1_ - fuge     # gleich lange Nachbarlage: Lagerfuge (Druckmass)
                if z1_ - z0_ < druck_m(1.0): continue
                ua, ub = (u_k - vor, u_s + s["b"]) if r_ > 0 else (u_s - s["b"], u_k + vor)
                k_ = W.kasten(ua, ub, z0_, z1_, w_s - einbinden, w_s + vor); teile = k_ if teile is None else teile + k_
                gebaut.append(dict(z0=round(z0_, 2), z1=round(z1_, 2), b=s["b"], w=round(w_s, 3)))
            if teile is None: continue
            koerper = koerper + teile
            belege.append(dict(seite="wand", element=f"Ortsteine/Eckverzahnung Fassade {Fa['id']} am Wand{K['ende']}: {len(gebaut)} Steine, z {K['z0']:.1f}..{K['z1']:.1f}, lang {K['lang_m']:.2f} / kurz {K['kurz_m']:.2f} m, Zahnung {K['zahnung']:.2f}",
                               quelle=f"tools/ortsteine.py: Stein/Putz (Farbe) im feinen Wandbild (Mosaik aus {Fa.get('mosaik_fotos')} ausgerichteten Fotos), Formfamilie in {fm} von {Fa.get('fotos')} Einzelfotos bestaetigt, Lagen aus Breitenspruengen + Fugenzeilen; Lage vor der echten Koerperflaeche (Strahltreffer)",
                               ortsteine=gebaut, vorsprung_m=round(vor, 3),
                               hinweis=(f"Vorsprung gemessen {K['vorsprung_m']} m ({K['vorsprung_quelle']})" + (f", auf Druckmass {v_min:.3f} m angehoben" if K['vorsprung_m'] < v_min else "") if gemessen else
                                        f"ANNAHME: Vorsprung = Druckmass {v_min:.3f} m ({K['vorsprung_quelle']})") + f"; Einbindung {einbinden} m (ANNAHME), Lagerfuge {fuge:.3f} m nur zwischen gleich langen Lagen (Druckmass)"))
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
    ap.add_argument("--nur", nargs="*"); ap.add_argument("--stufe", type=int, default=2)
    a = ap.parse_args()
    sys.path.insert(0, HIER)
    from fassaden_kette import fein_ordner
    ffn = fein_ordner(a.objekt_json)
    if not ffn: print("kein Wandbild (fassade_fein)"); return 2
    J = ortsteine_erkennen(ffn, nur=a.nur, stufe=a.stufe)
    os.makedirs(os.path.dirname(os.path.abspath(a.aus)), exist_ok=True); json.dump(J, open(a.aus, "w"), indent=1, ensure_ascii=False)
    for Fa in J["fassaden"]:
        print(Fa["id"], Fa.get("grund", ""), "; ".join(f"{K['ende']}: z {K['z0']:.1f}-{K['z1']:.1f}, {K['lagen']} Lagen, lang {K['lang_m']} kurz {K['kurz_m']}, Zahnung {K['zahnung']}, vor {K['vorsprung_m']} ({K['vorsprung_quelle'][:60]})" for K in Fa["kanten"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
