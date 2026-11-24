#!/usr/bin/env python3
"""massstab_teile.py --teil <name> <sparse> <dicht.ply> [--teil ...] --bilder <fotos> --ursprung <lat> <lon> [--objekt <objekt.json>] [--aus <bericht.json>]

MASSSTAB JE TEILMODELL UNABHAENIG BELEGEN (24.11.2026, Kette schwabentor-1122, Bericht rc-park_tmp/verlorene_gewinner_2026-11-24.md Punkte 1/2/3/10).
Verwandt/Vorlaeufer: tools/buendel_stuetz.py (Kopf: Befund 17.11. GPS-Massstab 0,875 = Telefon-Nachlauf, Wegverhaeltnis 0,76 bei < 30 s), tools/gps_unsicherheit.py
(ehrliche Unsicherheit, Sitzung x Ring), tools/seiten_gps_vereinen.py (rahmen: GPS-Fit je Teil, nur < 150 m), tools/kamerahoehe_dgm.py (Steigung Modell/DGM),
tools/seiten_vereinen.py (spitze_global/stange), tools/hoehe_gegen_dom1.py + sfm_lod2_ausrichten.py:821 (Hoehenprobe, Martinstor 0,250 -> 0,0725), tools/seiten_waende_binden.py (Verbraucher).
BEFUND (Daten 1122z, Kopie /media/oem/rcdaten/tmp/massstab_1122, nur CPU):
  - Teil 1 (Ost, 33 Geotags, EINE Sitzung 13,8 min): Wegverhaeltnis GPS/Modell 3,7 m/Einheit bei < 30 s, 6,1 bei 30-120 s, 8,0-8,9 ab 120 s = TELEFON-NACHLAUF (wie 17.11.).
    Der Gesamt-Fit (8,11) liegt aber im Plateau (8,05) - die langen Paare tragen ihn. Turmspitze im eigenen Rahmen 51,4 GPS-m (DOM1 49,6 + Nadel), DGM-Steigung 0,98:
    drei Quellen einig, Massstab ~7,9-8,3.
  - Teil 0 (329 nahe Geotags, zwei Sitzungen): KEIN Nachlauf (kurze Paare 9,1, lange 8,7), aber das Nah-GPS beider Sitzungen ergibt 8,86-8,94; mit den Fernfotos
    (> 100 m, andere Fehlerumgebung, langer Hebel) 9,98. Das ist der Sitzungs-/Abschattungsfehler von 22.11. (x0,867), nicht der Nachlauf - der Zeit-Test sieht ihn nicht.
  - Die 12-14-%-Luecke (Waende 0,882 x GPS-Verhaeltnis 0,907 = 0,800) ist der Nah-GPS-Massstab von TEIL 0, nicht von Teil 1: 8,0 / 9,98 = 0,80.
VERFAHREN (je Teil, Quellen werden NICHT gemittelt):
  1. NACHLAUF-TEST (nachlauf): robuster 2D-GPS-Fit (gps_unsicherheit.robust_fit2d), Kamerapaare derselben Sitzung mit >= PAAR_MIN_M Modellabstand; Wegverhaeltnis
     q = (dG . R dC) / |dC|^2 (m je Modelleinheit, quer liegendes GPS-Rauschen blaeht nicht auf). Kurz (< KURZ_S) gegen lang (>= LANG_S), 90-%-Band per Bootstrap ueber
     Kameras. Nachlauf = kurz klar unter lang. Schrumpftest NICHT bestanden = Gesamt-Fit ausserhalb des Plateau-Bands (dann traegt das GPS den Massstab nicht).
  2. GPS-QUELLEN: 'gps_nah' (Geotags < GU.NAH_M, ehrliches Band gps_fit) nur bei bestandenem Schrumpftest; 'gps_fern' (Abstandsverhaeltnis der Fernfotos zur Mitte
     der Nahfotos, >= MIN_FERN verschiedene Geotags; fern_quelle).
  3. GEBAEUDEMASS: 'turm_dom1' - hoechstes SCHLANKES Bauteil der eigenen dichten Wolke (spitze_global + stange, Streuung <= SCHLANK_M) ueber dem eigenen Strassenboden
     (seiten_waende_binden.strassen_boden) gegen DOM1-Maximum im LoD2-Grundriss ueber LoD2-Boden (+ Nadelzuschlag, DOM1 ist fuer Nadeln blind). 'dgm_steigung' -
     Kamerahoehen gegen DGM1 an der GPS-Lage (kamerahoehe_dgm.vergleich), Band per Bootstrap; nur bei DGM-Spanne >= SPANNE_MIN_M.
  4. EINIGKEIT (einig): alle Baender ueberlappen paarweise -> 'einig', Wert = Quelle mit dem engsten Band (kein Mittel). Sonst: Gebaeudemass-Quellen unter sich einig ->
     'gps_widerlegt' (Wert = engstes Gebaeudemass, Tor rot fuer das GPS, Bericht); sonst 'uneinig' (kein Wert, Tor rot). Keine Quelle -> 'nicht_messbar'.
GRENZEN: Turmprobe braucht eine schlanke Spitze, die das Teil selbst sieht (Teil 0 1122: oben duenn, Streuung 3,8 m -> nicht messbar); DGM-Probe braucht Hoehenunterschied
  der Kamerastandorte (Teil 0: 0,6 m -> nicht messbar); der Nachlauf-Test sieht keinen zeitunabhaengigen Sitzungsfehler (Abschattung) - den deckt nur 'gps_fern'/Gebaeudemass auf.
Test: tools/test_massstab_teile.py. Python: /media/oem/scan/venv-colmap/bin/python -I (pycolmap nur in main; Kern nur numpy/scipy)."""
import os, sys, json, argparse
import numpy as np

T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import gps_unsicherheit as GU

KURZ_S = 60.0          # ANNAHME: Paare unter 60 s Abstand zeigen den Nachlauf (17.11.: 0,76 bei < 30 s; 1122 Teil 1: 0,46 bei < 30 s)
LANG_S = 600.0         # ANNAHME: ab 10 min ist der Nachlauf abgeklungen (17.11.: 0,98 bei > 10 min)
PAAR_MIN_M = 8.0       # ANNAHME: Paare erst ab 8 m Modellabstand (Handy-GPS +-3-5 m; kuerzere Paare messen Rauschen)
MIN_PAARE = 20         # Plateau/kurz nur mit so vielen Paaren
N_BOOT = 200
MIN_FERN = 3           # verschiedene Fern-Geotags, damit 'gps_fern' eine eigene Quelle ist (gps_unsicherheit: eingefrorene Geotags = ein Beleg)
FERN_AUSREISSER = 0.25 # ANNAHME: Fernbeleg mehr als 25 % neben dem Median = falscher Geotag (1122 Teil 0: ein Geotag 1,9 km)
SCHLANK_M = 1.0        # wie seiten_waende_binden.SPITZE_SCHLANK_M: oberstes Band schlank = Spitze getroffen (1122: Teil 1 0,34 m, Teil 0 3,8 m)
NADEL_M = 1.5          # ANNAHME: DOM1 (1-m-Pixel) sieht Nadel/Knauf bis so viel zu niedrig (dach_aus_fotos 1122: Foto 50,67 m gegen DOM1-Max 49,62 m = +1,05 m)
BODEN_M = 0.5          # ANNAHME: Unsicherheit Strassenboden des Teils gegen LoD2-Boden des Objekts (Gefaelle, Bordstein)
SPANNE_MIN_M = 8.0     # wie kamerahoehe_dgm.SPANNE_MIN_M
TOL_MIN_REL = 0.02     # ANNAHME: kein Band enger als +-2 % (Modellbiegung, Lot)
Z90 = GU.Z90


def _wmedian(x, w):
    o = np.argsort(x); x, w = x[o], w[o]; c = np.cumsum(w)
    return float(x[np.searchsorted(c, 0.5 * c[-1])]) if c[-1] > 0 else float("nan")


def paare(C2, G, T_, s0, R0, w, sitz):
    """Wegverhaeltnisse der Kamerapaare (stimmige Kameras w, gleiche Sitzung, Modellabstand >= PAAR_MIN_M). -> (i, j, q, dt)."""
    iw = np.flatnonzero(w); a, b = np.triu_indices(len(iw), 1); i, j = iw[a], iw[b]
    dC = (C2[i] - C2[j]) @ np.asarray(R0).T; dG = G[i] - G[j]; L2 = np.einsum("ij,ij->i", dC, dC)
    q = np.einsum("ij,ij->i", dG, dC) / np.maximum(L2, 1e-12); dt = np.abs(T_[i] - T_[j])
    m = (np.sqrt(L2) * s0 >= PAAR_MIN_M) & (sitz[i] == sitz[j]) & (sitz[i] >= 0) & np.isfinite(dt)
    return i[m], j[m], q[m], dt[m]


def _band(i, j, q, n, rng):
    if len(q) < MIN_PAARE: return None
    m0 = _wmedian(q, np.ones(len(q))); bs = []
    for _ in range(N_BOOT):
        c = np.bincount(rng.choice(n, n), minlength=n).astype(float); wt = c[i] * c[j]
        if wt.sum() > 0: bs.append(_wmedian(q, wt))
    lo, hi = np.percentile(bs, [5, 95]); return dict(s=round(m0, 4), lo=round(float(lo), 4), hi=round(float(hi), 4), paare=int(len(q)))


def nachlauf(C2, G, zeiten, seed=0):
    """NACHLAUF-/SCHRUMPFTEST eines Teils. C2 Kameras waagerecht (n x 2, Modelleinheiten), G Geotags (n x 2, m), zeiten (s oder None).
    -> dict(messbar, s_fit, kurz, lang (je s/lo/hi/paare), kurve [(von_s, bis_s, q, paare)], nachlauf, schrumpftest_bestanden, urteil)."""
    C2, G = np.asarray(C2, float), np.asarray(G, float); T_ = np.array([np.nan if t is None else float(t) for t in zeiten]); n = len(G)
    f = GU.robust_fit2d(C2, G) if n >= 5 else None
    if f is None: return dict(messbar=False, urteil=f"kein GPS-Fit ({n} Geotags)")
    s0, R0, _, w = f; sitz = np.array(GU.sitzungen(list(T_))); rng = np.random.default_rng(seed)
    i, j, q, dt = paare(C2, G, T_, s0, R0, w, sitz)
    kurve = [(lo, hi, round(float(np.median(q[(dt >= lo) & (dt < hi)])), 4), int(((dt >= lo) & (dt < hi)).sum()))
             for lo, hi in ((0, 30), (30, 60), (60, 120), (120, 300), (300, 600), (600, 1800), (1800, GU.SITZUNG_LUECKE_S + 1)) if ((dt >= lo) & (dt < hi)).sum() >= 5]
    mk, ml = dt < KURZ_S, dt >= LANG_S
    ku = _band(i[mk], j[mk], q[mk], n, rng); la = _band(i[ml], j[ml], q[ml], n, rng)
    aus = dict(s_fit=round(float(s0), 4), inlier=int(w.sum()), kurz=ku, lang=la, kurve=kurve)
    if la is None:
        aus.update(messbar=False, nachlauf=None, schrumpftest_bestanden=None,
                   urteil=f"Schrumpftest nicht messbar: {int(ml.sum())} Paare >= {LANG_S:.0f} s in einer Sitzung (noetig {MIN_PAARE})"); return aus
    nl = bool(ku is not None and ku["hi"] < la["lo"]); ausser = not (la["lo"] <= s0 <= la["hi"])
    aus.update(messbar=True, nachlauf=nl, schrumpftest_bestanden=not ausser,
               urteil=(f"Nachlauf {'ja' if nl else 'nein'} (kurz {ku['s'] if ku else '-'} / lang {la['s']} m je Einheit); Gesamt-Fit {s0:.3f} "
                       + (f"im Plateau [{la['lo']:.3f}, {la['hi']:.3f}] - GPS-Massstab traegt" if not ausser else
                          f"AUSSERHALB des Plateaus [{la['lo']:.3f}, {la['hi']:.3f}] ({'geschrumpft' if s0 < la['lo'] else 'gestreckt'}) - GPS-Massstab traegt NICHT")))
    return aus


def _q(name, art, s, lo, hi, **kw):
    lo, hi = min(lo, s * (1 - TOL_MIN_REL)), max(hi, s * (1 + TOL_MIN_REL))
    return dict(name=name, art=art, massstab=round(float(s), 4), lo=round(float(lo), 4), hi=round(float(hi), 4), **kw)


def gps_quellen(C2, G, zeiten, nl=None, seed=0):
    """GPS-Quellen eines Teils (m je Modelleinheit, 90-%-Band). nl = Ergebnis von nachlauf (Schrumpftest). -> (quellen, bericht).
    Band 'gps_nah' = s x exp(+-Z90 x sd_massstab) (gps_fit: Zufall + Sitzungsfehler, RELATIV). NICHT massstab_90_ehrlich: gps_unsicherheit.band addiert den relativen
    Sitzungsfehler absolut (stimmt nur fuer s ~ 1 wie im GPS-Tor; bei s = 8,7 m/Einheit war das Band ~9x zu eng, 24.11.)."""
    C2, G = np.asarray(C2, float), np.asarray(G, float); mitte = np.median(G, 0); r = np.hypot(*(G - mitte).T); nah = r < GU.NAH_M; zz = list(zeiten); out, ber = [], {}
    if nah.sum() >= 5:
        f = GU.gps_fit(C2[nah], G[nah] - mitte, zeiten=[z for z, b in zip(zz, nah) if b])
        if f.get("ok"):
            s, sd = f["s"], f["sd_massstab"]; lo, hi = s * np.exp(-Z90 * sd), s * np.exp(Z90 * sd)
            ber["gps_nah"] = dict(massstab=round(s, 4), band=[round(lo, 4), round(hi, 4)], sd_rel=round(sd, 4), n=int(nah.sum()))
            if nl is None or nl.get("schrumpftest_bestanden") is not False: out.append(_q("gps_nah", "gps", s, lo, hi, n=int(nah.sum())))
            else: ber["gps_nah"]["verworfen"] = "Schrumpftest nicht bestanden: " + nl["urteil"]
            fq = fern_quelle(C2, G, nah, seed)
            if "massstab" in fq: out.append(fq)
            ber["gps_fern"] = fq
    return out, ber


def fern_quelle(C2, G, nah, seed=0):
    """FERN-GPS (Geotags >= GU.NAH_M von der Mitte; freie Sicht, langer Hebel): Abstandsverhaeltnis |G_j - Mitte_nah| / |C_j - Mitte_nah| je Fernfoto; gleiche Geotags
    (eingefroren, 1-m-Raster) = EIN Beleg. Ohne Drehung/RANSAC: ein gps_fit ueber alle kippte 1122 Teil 0 bei 1,6 Grad anderem Lot zwischen 8,73 (0 Fernfotos) und 9,98
    (10 Fernfotos). Belege > FERN_AUSREISSER vom Median fallen weg. Band: Bootstrap ueber Belege + Sitzungsfehler GU.SIGMA_SYS_M x sqrt2 / Hebel. -> Quelle oder dict(grund)."""
    C2, G = np.asarray(C2, float), np.asarray(G, float); nah = np.asarray(nah, bool)
    if nah.sum() < 5 or (~nah).sum() < MIN_FERN: return dict(grund=f"{int((~nah).sum())} Fernfotos (noetig {MIN_FERN})")
    gm, cm = G[nah].mean(0), C2[nah].mean(0); jf = np.flatnonzero(~nah & (np.hypot(*(G - gm).T) < GU.GPS_FERN_MAX_M))
    schl = {}
    for j in jf: schl.setdefault(tuple(np.round(G[j]).astype(int)), []).append(j)
    q, L = [], []
    for ix in schl.values():
        dc = float(np.median(np.hypot(*(C2[ix] - cm).T))); dg = float(np.hypot(*(G[ix[0]] - gm)))
        if dc > 1e-9: q.append(dg / dc); L.append(dg)
    q, L = np.array(q), np.array(L)
    if len(q) < MIN_FERN: return dict(grund=f"nur {len(q)} verschiedene Fern-Geotags (noetig {MIN_FERN})")
    m = np.abs(np.log(q / np.median(q))) <= np.log1p(FERN_AUSREISSER); q, L = q[m], L[m]
    if len(q) < MIN_FERN: return dict(grund=f"Fern-Geotags uneinig (nur {len(q)} innerhalb {100 * FERN_AUSREISSER:.0f} % vom Median)")
    s = float(np.median(q)); rng = np.random.default_rng(seed); bs = [np.median(q[rng.choice(len(q), len(q))]) for _ in range(N_BOOT)]
    hb = float(np.percentile(np.log(bs), 95) - np.percentile(np.log(bs), 5)) / 2; hs = Z90 * GU.SIGMA_SYS_M * np.sqrt(2) / float(np.median(L)); h = float(np.hypot(hb, hs))
    return _q("gps_fern", "gps", s, s * np.exp(-h), s * np.exp(h), belege=int(len(q)), verworfen=int((~m).sum()), hebel_m=round(float(np.median(L)), 1))


def turm_referenz(objekt, dom1=None):
    """Hoehe der Objektspitze ueber dem LoD2-Boden aus amtlichen Daten: DOM1-Maximum im LoD2-Grundriss (+ halber Nadelzuschlag) -> dict(h_m, halb_m, quelle) oder None."""
    try:
        import lod2_gebaeude as LOD2
        meta, grund, _ = LOD2.grundflaechen(objekt, objekt["lod2"]["gml"])
    except Exception: return None
    if not meta or not grund: return None
    if dom1 is None:
        from dom1_kachel import dom1_hoehe as dom1
    P = np.vstack([np.asarray(g, float)[:, :2] for g in grund]); E, N = np.meshgrid(np.arange(P[:, 0].min(), P[:, 0].max() + 1, 0.5), np.arange(P[:, 1].min(), P[:, 1].max() + 1, 0.5))
    pts = np.c_[E.ravel(), N.ravel()]; innen = np.zeros(len(pts), bool)
    for g in grund: innen |= _im_polygon(pts, np.asarray(g, float)[:, :2])
    if innen.sum() < 4: return None
    z = np.asarray(dom1(pts[innen, 0], pts[innen, 1]), float)
    if not np.isfinite(z).any(): return None
    h = float(np.nanmax(z) - meta["ground_z"])
    return dict(h_m=round(h + NADEL_M / 2, 3), halb_m=round(NADEL_M / 2 + BODEN_M, 3), dom1_max_ueber_boden_m=round(h, 3), quelle=f"DOM1-Maximum im LoD2-Grundriss {objekt['lod2'].get('id')} + Nadel {NADEL_M / 2:.2f} m")


def _im_polygon(p, poly):
    x, y = p[:, 0], p[:, 1]; inn = np.zeros(len(p), bool); n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]; x2, y2 = poly[(k + 1) % n]
        c = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / ((y2 - y1) + 1e-12) + x1); inn ^= c
    return inn


def turm_probe(P_m, ref, mj):
    """P_m: dichte Wolke des Teils im EIGENEN Lotsystem (z = Lot), Meter nach dem GPS-Massstab mj. ref = turm_referenz. -> Quelle (dict) oder dict(grund)."""
    from seiten_vereinen import spitze_global, stange
    from seiten_waende_binden import strassen_boden
    if not ref: return dict(grund="keine DOM1/LoD2-Referenz der Objekthoehe")
    sb = strassen_boden(P_m)
    if len(sb) < 10: return dict(grund=f"Strassenboden des Teils nicht messbar ({len(sb)} Zellen)")
    boden = float(np.median(list(sb.values()))); sg = spitze_global(P_m)
    if sg is None: return dict(grund="keine Spitze in der Wolke")
    H = float(sg[1] - boden); st = stange(P_m, sg[0], H, boden) if H > 0 else None
    if st is None or st[3] > SCHLANK_M: return dict(grund=f"Spitze nicht schlank (Streuung {None if st is None else round(st[3], 2)} m > {SCHLANK_M} m) - Teil sieht die Objektspitze nicht", hoehe_m=round(H, 2))
    k = ref["h_m"] / H
    if not 0.5 < k < 2.0: return dict(grund=f"Turmhoehe {H:.1f} m gegen Referenz {ref['h_m']:.1f} m unplausibel (Faktor {k:.2f})", hoehe_m=round(H, 2))
    rel = ref["halb_m"] / H
    return _q("turm_dom1", "gebaeude", mj * k, mj * k * (1 - rel), mj * k * (1 + rel), hoehe_gps_m=round(H, 2), referenz_m=ref["h_m"], boden_zellen=len(sb), streuung_spitze_m=round(st[3], 2))


def dgm_probe(h_einheiten, he, mj, seed=0):
    """Kamerahoehen (Modelleinheiten entlang des Lots) gegen DGM1-Erwartung he (m). -> Quelle oder dict(grund)."""
    import kamerahoehe_dgm as KD
    h = np.asarray(h_einheiten, float) * mj; he = np.asarray(he, float); e = KD.vergleich(h, he)
    if e.get("steigung") is None or (e.get("spanne_m") or 0) < SPANNE_MIN_M: return dict(grund=f"DGM-Steigung nicht messbar (Spanne {e.get('spanne_m')} m)", **{k: e.get(k) for k in ("n", "spanne_m")})
    rng = np.random.default_rng(seed); n = len(h); bs = []
    for _ in range(N_BOOT):
        b = rng.choice(n, n); s_ = KD.vergleich(h[b], he[b]).get("steigung")
        if s_: bs.append(mj / s_)
    if len(bs) < N_BOOT // 2: return dict(grund="DGM-Steigung im Bootstrap instabil")
    lo, hi = np.percentile(bs, [5, 95])
    return _q("dgm_steigung", "gebaeude", mj / e["steigung"], lo, hi, steigung=e["steigung"], spanne_m=e["spanne_m"], n=e["n"], rest_m=e["rest_m"])


def _ueber(a, b): return a["lo"] <= b["hi"] and b["lo"] <= a["hi"]


def einig(quellen):
    """Einigkeitsregel (KEIN Mittel). -> dict(urteil, massstab, lo, hi, quelle, tor ('gruen'/'rot'/None), meldung)."""
    q = [x for x in quellen if x and "massstab" in x]
    if not q: return dict(urteil="nicht_messbar", massstab=None, tor=None, meldung="keine Quelle fuer den Massstab")
    eng = lambda L: min(L, key=lambda x: np.log(x["hi"] / x["lo"]))
    streit = [(a["name"], b["name"]) for k, a in enumerate(q) for b in q[k + 1:] if not _ueber(a, b)]
    if not streit:
        e = eng(q); return dict(urteil="einig", massstab=e["massstab"], lo=e["lo"], hi=e["hi"], quelle=e["name"], tor="gruen",
                                meldung=f"{len(q)} Quellen einig ({', '.join(x['name'] for x in q)}), engste: {e['name']} {e['massstab']:.4f} [{e['lo']:.4f}, {e['hi']:.4f}]")
    geb = [x for x in q if x["art"] == "gebaeude"]
    txt = "; ".join(f"{a} gegen {b}" for a, b in streit) + " | " + ", ".join(f"{x['name']} {x['massstab']:.4f} [{x['lo']:.4f}, {x['hi']:.4f}]" for x in q)
    if geb and all(_ueber(a, b) for k, a in enumerate(geb) for b in geb[k + 1:]):
        e = eng(geb); return dict(urteil="gps_widerlegt", massstab=e["massstab"], lo=e["lo"], hi=e["hi"], quelle=e["name"], tor="rot",
                                  meldung=f"MASSSTAB-TOR ROT (GPS widerlegt, Gebaeudemass gilt): {txt}")
    return dict(urteil="uneinig", massstab=None, tor="rot", meldung=f"MASSSTAB-TOR ROT (Quellen uneinig, kein Massstab belegt): {txt}")


def teil_massstab(C, Rs, G, zeiten, ll=None, P=None, mj=None, ursprung=None, ref=None, lot=None, dgm_hoehen=None, seed=0):
    """Alles je Teil. C Kamerazentren (n x 3, nur Kameras mit Geotag), Rs ihre Rotationen (cam_from_world), G Geotags ENU (n x 2), zeiten, ll (lat, lon) fuer die DGM-Probe,
    P dichte Wolke (Modell), mj GPS-Massstab des Teils (m je Einheit, fuer die Meterangaben der Wolke), ref = turm_referenz. -> dict(nachlauf, gps, quellen, ergebnis, lot)."""
    from seiten_gps_vereinen import lot_aus_bild_achsen, basis
    C = np.asarray(C, float); G = np.asarray(G, float)
    if lot is None:
        lot = lot_aus_bild_achsen(Rs)
        if P is not None and len(P) > 1000:
            from seiten_vereinen import lot_aus_waenden
            lw, nw = lot_aus_waenden(P, lot); lot = lw if nw else lot
    lot = np.asarray(lot, float) / np.linalg.norm(lot); e1, e2 = basis(lot); C2 = np.c_[C @ e1, C @ e2]
    nl = nachlauf(C2, G, zeiten, seed); qg, ber = gps_quellen(C2, G, zeiten, nl, seed); quellen = list(qg); geb = {}
    if mj is None: mj = nl.get("s_fit")
    if P is not None and mj:
        tp = turm_probe(np.c_[P @ e1, P @ e2, P @ lot] * mj, ref, mj); geb["turm_dom1"] = tp
        if "massstab" in tp: quellen.append(tp)
    if mj and (dgm_hoehen is not None or (ll is not None and ursprung is not None)):
        try:
            if dgm_hoehen is None:
                import kamerahoehe_dgm as KD
                dgm_hoehen, _ = KD.erwartete_hoehen(ll, ursprung)
            dp = dgm_probe(C @ lot, dgm_hoehen, mj, seed)
        except Exception as ex: dp = dict(grund=f"DGM-Probe nicht moeglich ({type(ex).__name__}: {ex})")
        geb["dgm_steigung"] = dp
        if "massstab" in dp: quellen.append(dp)
    return dict(nachlauf=nl, gps=ber, gebaeude=geb, quellen=quellen, ergebnis=einig(quellen), lot=[float(x) for x in lot])


def verhaeltnis(ea, eb):
    """Belegtes Massstabsverhaeltnis B -> A (A-Einheiten je B-Einheit = m_B / m_A) aus zwei teil_massstab-Ergebnissen, Band aus beiden Baendern. None, wenn ein Teil keinen Wert hat."""
    a, b = ea["ergebnis"], eb["ergebnis"]
    if a.get("massstab") is None or b.get("massstab") is None: return None
    r = b["massstab"] / a["massstab"]; la, lb = np.log(a["hi"] / a["lo"]) / 2, np.log(b["hi"] / b["lo"]) / 2; h = float(np.hypot(la, lb))
    return dict(wert=round(r, 5), lo=round(r * np.exp(-h), 5), hi=round(r * np.exp(h), 5), quelle_a=a["quelle"], quelle_b=b["quelle"], urteil_a=a["urteil"], urteil_b=b["urteil"])


def teil_aus_modell(modell, bilder, ursprung, P=None, mj=None, ref=None):
    """Teil direkt aus dem Sparse-Modell (pycolmap) + Fotos (EXIF-GPS/Zeit) -> teil_massstab-Ergebnis (+ n_kameras)."""
    import pycolmap
    import seiten_gps_vereinen as SG
    from kamerahoehe_dgm import erwartete_hoehen
    r = pycolmap.Reconstruction(modell); ims = [im for im in r.images.values() if im.has_pose]; namen = [im.name for im in ims]
    roh = SG.gps_roh(bilder, namen); k = [i for i, n in enumerate(namen) if n in roh]
    if len(k) < 5: return dict(ergebnis=dict(urteil="nicht_messbar", massstab=None, tor=None, meldung=f"nur {len(k)} Kameras mit Geotag"), n_kameras=len(namen))
    ll = [roh[namen[i]] for i in k]; la0, lo0 = ursprung; R_ = 6378137.0; L = np.asarray(ll, float)
    G = np.c_[np.radians(L[:, 1] - lo0) * R_ * np.cos(np.radians(la0)), np.radians(L[:, 0] - la0) * R_]
    C = np.array([ims[i].projection_center() for i in k]); Rs = [ims[i].cam_from_world().rotation.matrix() for i in k]; z = [SG.ZEITEN.get(namen[i]) for i in k]
    try: he, _ = erwartete_hoehen(ll, ursprung)
    except Exception: he = None
    e = teil_massstab(C, Rs, G, z, P=P, mj=mj, ref=ref, dgm_hoehen=he); e["n_kameras"] = len(namen); e["n_geotags"] = len(k); return e


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0]); ap.add_argument("--teil", nargs=3, action="append", metavar=("NAME", "SPARSE", "DICHT"), required=True)
    ap.add_argument("--bilder", required=True); ap.add_argument("--ursprung", nargs=2, type=float, required=True); ap.add_argument("--objekt"); ap.add_argument("--vereinen")
    ap.add_argument("--aus"); a = ap.parse_args(argv)
    from seiten_waende_binden import ply_lesen
    ref = turm_referenz(json.load(open(a.objekt))) if a.objekt else None; vj = json.load(open(a.vereinen)) if a.vereinen else {}
    mjs = [(vj.get("rahmen_a") or {}).get("massstab"), (vj.get("rahmen_b") or {}).get("massstab")]
    erg = dict(referenz=ref, teile={})
    for k, (name, sp, dp) in enumerate(a.teil):
        P = ply_lesen(dp) if dp and os.path.isfile(dp) else None
        e = teil_aus_modell(sp, a.bilder, a.ursprung, P=P, mj=mjs[k] if k < 2 else None, ref=ref); erg["teile"][name] = e
        print(f"TEIL {name}: {e['ergebnis']['meldung']}"); print(f"   Nachlauf: {(e.get('nachlauf') or {}).get('urteil')}")
        for q, v in (e.get("gebaeude") or {}).items(): print(f"   {q}: {v.get('massstab', v.get('grund'))}")
    if len(a.teil) >= 2:
        n0, n1 = a.teil[0][0], a.teil[1][0]; erg["verhaeltnis_b_nach_a"] = verhaeltnis(erg["teile"][n0], erg["teile"][n1]); print("VERHAELTNIS B->A:", erg["verhaeltnis_b_nach_a"])
    if a.aus: json.dump(erg, open(a.aus, "w"), indent=1, ensure_ascii=False, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    return 0 if all(t["ergebnis"].get("tor") != "rot" for t in erg["teile"].values()) else 3


if __name__ == "__main__": sys.exit(main())
