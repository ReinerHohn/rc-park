#!/usr/bin/env python3
"""muster_fit.py - generisches Wiederholungs-Werkzeug (Verallgemeinerung von baluster_fit.py): Zone aus dem Kantengitter, Periode mehrstufig (GPU),
Faltung, Phase per Symmetrie, Musterzelle, Kopien im Takt, JEDE Kopie einzeln in alle sehenden Fotos (Z-Puffer der Wolke), Abnahme >= 3 Fotos UND >= 30 % der Sichtfotos.
Die Formfamilie ist ein Plug-in:  --familie fenster | gaube | rotation | pfeiler | konsole
  fenster   Fensterreihe einer Fassade (zweistufig: Fensterachsen, dann Lichter in der Zelle; Pfosten/Kaempfer/Kopfform aus der gefalteten Zelle)
  gaube     Dachgauben: alle Gauben im Gaubensystem (Achse senkrecht zur Traufe) uebereinandergelegt, Formfamilie (Satteldach/Schlepp/Spitz) aus dem Kantenprofil
  rotation  Baluster (Rotationskoerper, kleine Periode): delegiert an baluster_fit.py (Regressionstest gegen formen/baluster_abgenommen.json)
  pfeiler   freistehende Rotationskoerper mit grosser Periode (Saeulen ~6 m): Zone = vertikale Kanten, Radius aus der gefalteten Zelle
  konsole   Quader-/Blockreihe (Breite, Tiefe, Hoehe aus der gefalteten Zelle)
Aufrufe (venv-seg):
  muster_fit.py --familie fenster --gitter G.json --wolke W.npz --kam KAM.json --stabil DIR --bilder DIR --out OUT.json [--rahmen ROH.json] [--band zlo,zhi] [--audit DIR]
  muster_fit.py --familie gaube   --gitter G.json --sweep A.npz,B.npz --lagen gauben_r3_lagen.json --rahmen ROH.json ... --out OUT.json
  muster_fit.py --synth fenster|gaube|pfeiler|konsole   (Beweistest: bekannte Elemente einbauen, wiederfinden, Fehler < 5 cm)
  muster_fit.py --alle --gitter G.json ... --out OUTDIR   (alle Familien, je Familie Zonen-Erkennung; fuer die Kette)
Keine Objektkonstanten: Fassadenrahmen, Band, Periodenbereich kommen aus dem Gitter (oder Parameter). Annahmen heissen 'ANNAHME:'.
Segmente quelle 16 (Fenster) / 17 (Gaube) / 13 (Rotation) im Format [[A],[B],quelle,score]."""
import sys, os, json, math, time
import numpy as np

HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
a = sys.argv; g = lambda k, d, t=float: t(a[a.index(k) + 1]) if k in a else d
QUELLEN_AUS = {13, 14, 15, 16, 17}      # eigene Ausgaben nie als Eingabe (Selbstbezug)


from kanten_tor import *
from kanten_tor import log, torch_dev, Fotos, Tor, tor_bericht, linie, flaeche_raster, sammeln, lade_wolke, wolke_kasten, TOR_K, TOR_NPKT, TOR_NFOTO, TOR_WINKEL, TOR_EINIG, NFOTO, FANTEIL, KANTE, PX, THR

# ----------------------------------------------------------------------------------------------- Gitter / Zone
def gitter_laden(pfad, schritt=0.05):
    """Gitter -> Stuetzpunkte alle `schritt` m mit Klasse (0 senkrecht, 1 waagerecht, 2 schraeg), Gewicht = Laenge je Punkt. Eigene Ausgabequellen werden ausgelassen."""
    S = [s for s in json.load(open(pfad))["segmente"] if s[2] not in QUELLEN_AUS]
    P0 = np.array([s[0] for s in S], float); P1 = np.array([s[1] for s in S], float); L = np.linalg.norm(P1 - P0, axis=1); ok = L > 1e-3
    P0, P1, L = P0[ok], P1[ok], L[ok]; dz = np.abs(P1[:, 2] - P0[:, 2]) / L
    kl = np.where(dz > 0.9, 0, np.where(dz < 0.2, 1, 2)); pts, cl, w, sid = [], [], [], []
    for i in range(len(L)):
        k = max(2, int(math.ceil(L[i] / schritt)) + 1); t = np.linspace(0, 1, k)[:, None]
        pts.append(P0[i] + (P1[i] - P0[i]) * t); cl.append(np.full(k, kl[i])); w.append(np.full(k, L[i] / k)); sid.append(np.full(k, i))
    return dict(P0=P0, P1=P1, L=L, kl=kl, P=np.vstack(pts), cl=np.concatenate(cl), w=np.concatenate(w), sid=np.concatenate(sid))


def rahmen_auto(G, zlo=-1e9, zhi=1e9):
    """Fassadenrahmen aus dem Gitter: Richtung u = laengengewichteter Winkelmodus der waagerechten Segmente (0,5-Grad-Bins, mod 180), n senkrecht,
    Frontoffset = Offsetmodus der waagerechten Laenge in 4-cm-Bins (die laengste Fassadenebene)."""
    m = (G["kl"] == 1) & (G["L"] > 0.8); d = (G["P1"] - G["P0"])[m][:, :2]; L = G["L"][m]; ang = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 180
    h = np.zeros(360)
    for A, l in zip(ang, L): h[int(A * 2) % 360] += l
    h2 = h + np.roll(h, 1) + np.roll(h, -1); k = int(np.argmax(h2)); sel = np.abs(((ang - (k + 0.5) / 2 + 90) % 180) - 90) < 1.5
    w_ = np.exp(1j * np.radians(2 * ang[sel])); phi = (np.angle((w_ * L[sel]).sum()) / 2) % math.pi; u = np.array([math.cos(phi), math.sin(phi), 0.0]); n = np.array([-u[1], u[0], 0.0])
    M = ((G["P0"] + G["P1"]) / 2)[m][sel]; of = M[:, :2] @ n[:2]; hh = np.histogram(of, bins=np.arange(of.min(), of.max() + 0.04, 0.04), weights=L[sel])
    j = int(np.argmax(hh[0])); return u, n, float(hh[1][j] + 0.02)


def zone_fenster(G, rah, band_arg=None, pmin=0.5, pmax=8.0):
    """Zone Fensterreihe: Frontebene |off - of| < 0.3; z-Laeufe der Senkrechtendichte (0,2 m geglaettet, >= 30 % des Maximums, >= 1 m hoch);
    der Lauf mit der staerksten Periodizitaet (ACF-Spitze der t-Dichte, Lags pmin..pmax) ist das Fensterband. Gibt dict(zlo, zhi, kandidaten)."""
    u, n, of = rah; P = G["P"]; fr = np.abs(P @ n - of) < 0.3; v = fr & (G["cl"] == 0)
    if band_arg: zlo, zhi = [float(x) for x in band_arg.split(",")]; return dict(zlo=zlo, zhi=zhi, kandidaten=[], quelle="Parameter --band")
    z = P[v, 2]; w = G["w"][v]; e = np.arange(z.min(), z.max() + 0.1, 0.1); h = np.histogram(z, bins=e, weights=w)[0]; h = np.convolve(h, np.ones(3) / 3, "same")
    ok = h >= 0.3 * h.max(); runs = []; i = 0
    while i < len(ok):
        if ok[i]:
            j = i
            while j < len(ok) and ok[j]: j += 1
            if (j - i) * 0.1 >= 1.0: runs.append((float(e[i]), float(e[j])))
            i = j
        else: i += 1
    kand = []
    for zl, zh in runs:
        s = v & (P[:, 2] > zl) & (P[:, 2] < zh); t = P[s] @ u; r = periode_grob(t, G["w"][s], pmin, pmax, nur_bericht=True)
        kand.append(dict(zlo=zl, zhi=zh, periodizitaet=r["acf_max"], periode=r["periode"], laenge=float(G["w"][s].sum())))
    if not kand: raise SystemExit("keine Zone fuer Fensterreihe gefunden")
    b = max(kand, key=lambda k: k["periodizitaet"] * min(1.0, k["laenge"] / 30)); return dict(zlo=b["zlo"], zhi=b["zhi"], kandidaten=kand, quelle="Gitter (Senkrechtendichte-Laeufe, staerkste Periodizitaet)")


# ----------------------------------------------------------------------------------------------- Kern: Periode, Faltung, Phase
def _acf(sig):
    torch, dev = torch_dev(); x = torch.tensor(sig - sig.mean(), device=dev, dtype=torch.float32); n = len(x); f = torch.fft.rfft(x, n=2 * n); ac = torch.fft.irfft(f * f.conj())[:n]
    ac = ac / torch.arange(n, 0, -1, device=dev, dtype=torch.float32); return (ac / ac[0].clamp(min=1e-12)).cpu().numpy()


def periode_grob(t, w, pmin, pmax, bin_=0.01, nur_bericht=False, tol_harm=0.85):
    """Mehrstufige Periodensuche. Stufe 1: ACF der Dichte (GPU-FFT), lokale Maxima; Grundperiode = kleinster Lag mit >= tol_harm x Maximum (Vielfache sind gleich stark).
    Stufe 2: Mehrharmonisches Periodogramm P(p) = sum_k |sum w exp(2 pi i k t / p)|^2 in +-4 % um den Kandidaten (Schritt 0,05 %), Plateau = p-Bereich mit >= 90 % des Maximums."""
    e = np.arange(t.min() - 0.05, t.max() + 0.05 + bin_, bin_); h = np.histogram(t, bins=e, weights=w)[0]; ac = _acf(h); lags = np.arange(len(ac)) * bin_
    s0, s1 = int(pmin / bin_), min(int(pmax / bin_), len(ac) - 2); r = 4
    lok = [i for i in range(max(s0, r), s1 - r) if ac[i] >= ac[i - r:i + r + 1].max() - 1e-12 and ac[i] > 0.02]
    if not lok: return dict(periode=None, acf_max=0.0, kandidaten=[])
    mx = max(ac[i] for i in lok); kand = sorted([(lags[i], float(ac[i])) for i in lok], key=lambda x: x[0]); grund = next(l for l, v in kand if v >= tol_harm * mx)
    res = dict(periode=float(grund), acf_max=float(mx), kandidaten=[(round(float(l), 3), round(v, 2)) for l, v in sorted(kand, key=lambda x: -x[1])[:8]])
    if nur_bericht: return res
    torch, dev = torch_dev(); T = torch.tensor(t - t.mean(), device=dev, dtype=torch.float64); W = torch.tensor(w, device=dev, dtype=torch.float64)
    ps = torch.arange(grund * 0.96, grund * 1.04, grund * 0.0004, device=dev, dtype=torch.float64); sc = torch.zeros(len(ps), device=dev, dtype=torch.float64); nb = max(20, int(grund / 0.01))
    for i, p_ in enumerate(ps):                                    # Schaerfe der Faltung: Summe h^2 (1-cm-Bins); wenige Kopien -> Hauptkeule der Fourier-Maxima ~1 m breit, nur die Schaerfe der Pfosten loest auf
        u = torch.remainder(T, p_) / p_; h = torch.bincount((u * nb).long().clamp(max=nb - 1), weights=W, minlength=nb); sc[i] = (h * h).sum()
    sc = sc.cpu().numpy(); ps = ps.cpu().numpy(); base = float(np.median(sc)); j = int(np.argmax(sc)); ok = sc >= base + 0.9 * (sc[j] - base); lo = j
    while lo > 0 and ok[lo - 1]: lo -= 1
    hi = j
    while hi < len(ok) - 1 and ok[hi + 1]: hi += 1
    res.update(periode=float(ps[j]), plateau=(float(ps[lo]), float(ps[hi])), plateau_breite=float(ps[hi] - ps[lo]), periode_grob=float(grund), schaerfe_kontrast=float(sc[j] / max(base, 1e-9))); return res


def phase_symmetrie(t, w, p, gewicht_zentrum=None, nb=60):
    """Phase: t mod p in [-p/2,p/2]; Phase mit kleinster Spiegelasymmetrie der gefalteten Dichte (Achse + gegenueberliegende Achse sind beide symmetrisch:
    Entscheidung = die Achse, um die die Dichte konzentrierter ist, |x| < 0,3 p)."""
    ph = np.arange(0, p, 0.004); best = []
    for f in ph:
        u = np.remainder(t - f + p / 2, p) - p / 2; h = np.histogram(u, bins=nb, range=(-p / 2, p / 2), weights=w)[0]; best.append(np.abs(h - h[::-1]).sum() / max(h.sum(), 1e-9))
    best = np.array(best); cand = []
    for i in np.argsort(best)[:200]:
        if all(abs(((ph[i] - c + p / 2) % p) - p / 2) > 0.05 for c, _ in cand): cand.append((float(ph[i]), float(best[i])))
        if len(cand) >= 4: break
    cand = [c for c in cand if c[1] <= 1.5 * cand[0][1] + 0.02]
    # Gegenachsen hinzu
    cand2 = []
    for c, s in cand: cand2 += [(c % p, s), ((c + p / 2) % p, s)]
    def zentr(f):
        u = np.remainder(t - f + p / 2, p) - p / 2; return float(w[np.abs(u) < 0.3 * p].sum())
    f = max(cand2, key=lambda x: zentr(x[0]) - 5 * x[1] * w.sum()); return float(f[0]), float(f[1])


def instanzen_ungefaltet(t, w, bin_=0.05, k=10.0, min_abst=0.3):
    """Instanzen aus dem UNGEFALTETEN Histogramm (Lehre Koerper-Agent: feste Periode verschmierte die Konsolen, Abstaende 1,45..1,93 statt konstant 2,0): Bloecke = Bins >= Median + k MAD, zusammenhaengend,
    Lage = gewichtete Mitte. Regelmaessigkeit = MAD der Nachbarabstaende / Median: starr (< 5 %) -> starre Faltung zulaessig, sonst Instanzen einzeln ausrichten (Periode nur Startwert)."""
    e = np.arange(t.min() - bin_, t.max() + 2 * bin_, bin_); h = np.histogram(t, bins=e, weights=w)[0]; hs = np.convolve(h, np.ones(3) / 3, "same"); med = float(np.median(hs)); mad = float(np.median(np.abs(hs - med))) + 1e-9
    ok = hs >= med + k * mad; bl = []; i = 0
    while i < len(ok):
        if ok[i]:
            j = i
            while j < len(ok) and ok[j]: j += 1
            c = float((((e[i:j] + bin_ / 2) * hs[i:j]).sum()) / hs[i:j].sum()); bl.append(c); i = j
        else: i += 1
    bl2 = []
    for c in bl:
        if not bl2 or c - bl2[-1] > min_abst: bl2.append(c)
    d_ = np.diff(bl2); reg = float(np.median(np.abs(d_ - np.median(d_))) / np.median(d_)) if len(d_) >= 2 else None
    return dict(lagen=[float(x) for x in bl2], abstaende=[float(x) for x in d_], abstand_median=float(np.median(d_)) if len(d_) else None, abstand_streuung_rel=reg, starr=bool(reg is not None and reg < 0.05))


def falten(t, p, ph): return np.remainder(t - ph + p / 2, p) - p / 2


def peaks_1d(x, h, rel=0.35, min_abst=0.1):
    """Lokale Maxima von h(x) >= rel*max, Mindestabstand min_abst, Position parabolisch gemittelt (gewichteter Schwerpunkt +-2 Bins)."""
    out = []; hm = h.max()
    for i in np.argsort(-h):
        if h[i] < rel * hm: break
        if all(abs(x[i] - o[0]) > min_abst for o in out):
            lo, hi = max(0, i - 2), min(len(h), i + 3); out.append((float((x[lo:hi] * h[lo:hi]).sum() / h[lo:hi].sum()), float(h[i])))
    return sorted(out)


def poly_pts(Pv, schritt=0.03):
    """Polylinienstuetzen -> Punkte alle `schritt` m."""
    out = []
    for A, B in zip(Pv[:-1], Pv[1:]):
        A = np.asarray(A, float); B = np.asarray(B, float); k = max(2, int(np.linalg.norm(B - A) / schritt)); out.append(A + (B - A) * np.linspace(0, 1, k)[:, None])
    return np.vstack(out)


# ----------------------------------------------------------------------------------------------- Overlay
def overlay(F, segs_gut, segs_schlecht, foto, ziel, crop_um=None, marker=None, W=None):
    """Segmente (Listen von Polylinien Nx3) in ein Foto zeichnen: gruen = abgenommen, rot = nicht. crop_um = 3D-Punkt, um den ausgeschnitten wird (Radius 1/3 Bildbreite)."""
    import cv2
    f = [x for x in F.KAM if x.endswith(foto) or foto in x]; assert f, foto; f = f[0]; k = F.KAM[f]
    bd = F.bd; pf = os.path.join(bd, f); pf = pf if os.path.exists(pf) else os.path.join(bd, os.path.splitext(f)[0] + ".jpg"); im = cv2.imread(pf); sj = im.shape[1] / k["W"]
    def zeichne(polys, col):
        for P in polys:
            u, v, z = F.proj(f, np.asarray(P)); u = u * sj; v = v * sj; ok = z > 1
            for i in range(len(u) - 1):
                if ok[i] and ok[i + 1]: cv2.line(im, (int(u[i]), int(v[i])), (int(u[i + 1]), int(v[i + 1])), col, max(2, int(im.shape[1] / 1000)), cv2.LINE_AA)
    zeichne(segs_schlecht, (0, 0, 255)); zeichne(segs_gut, (0, 255, 0))
    if crop_um is not None:
        pts = np.asarray(crop_um); u, v, z = F.proj(f, pts); u = u * sj; v = v * sj; ok = z > 1
        if ok.any():
            x0, x1, y0, y1 = int(max(0, u[ok].min() - 150 * sj)), int(min(im.shape[1], u[ok].max() + 150 * sj)), int(max(0, v[ok].min() - 150 * sj)), int(min(im.shape[0], v[ok].max() + 150 * sj)); im = im[y0:y1, x0:x1]
    s = 1600 / max(im.shape[:2]); 
    if s < 1: im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    cv2.imwrite(ziel, im, [cv2.IMWRITE_JPEG_QUALITY, 88]); return ziel


def kontrolle_punkte(pts, dt, u):
    """Gegenprobe: gleicher Umriss entlang u um dt verschoben (Position zwischen den Kopien)."""
    return pts + dt * np.asarray(u)[None, :]


# ----------------------------------------------------------------------------------------------- Familie fenster
def zellen_lesen_fenster(G, rah, z, p, ph, kopf=0.8):
    """Gefaltete Zelle einer Fenstergruppe lesen (nur Gitter): Pfostenkamm (Mitte c, Lichtbreite wl, n), Hoehen, Waagerechte mit x-Laeufen, Kopfform. Gibt (zelle, ph_neu)."""
    u, n, of = rah; P = G["P"]; zlo, zhi = z["zlo"], z["zhi"]; fr = np.abs(P @ n - of) < 0.3; zb = fr & (P[:, 2] > zlo - 0.6) & (P[:, 2] < zhi + kopf)
    tt = P[zb] @ u; zz = P[zb, 2]; cl = G["cl"][zb]; ww = G["w"][zb]; X = falten(tt, p, ph)
    hb = np.arange(-p / 2, p / 2 + 0.015, 0.015); xb = (hb[:-1] + hb[1:]) / 2; qv = (cl == 0) & (zz > zlo) & (zz < zhi); hv = np.histogram(X[qv], bins=hb, weights=ww[qv])[0]
    hv_s = np.convolve(hv, np.ones(3) / 3, "same"); hs = hv_s + hv_s[::-1]
    # Stufe 2: Lichtbreite = erstes ACF-Maximum (Lags 0,4..1,6 m) der Pfostendichte in |x| < 2,2
    cen = np.abs(xb) < min(p / 2 - 0.1, 2.2); ac = _acf(hs[cen]); lag = np.arange(len(ac)) * 0.015; lo_, hi_ = int(0.4 / 0.015), int(min(1.6, p / 2) / 0.015)
    lok = [i for i in range(lo_, hi_) if ac[i] >= ac[i - 2:i + 3].max() - 1e-12 and ac[i] > 0.05]; fk = sorted([(float(lag[i]), float(ac[i])) for i in lok], key=lambda q: -q[1]); wl0 = fk[0][0] if fk else 0.9
    # Ausdehnung der Waagerechten (Zeilenband) -> n
    qh = (cl == 1) & (zz > zlo) & (zz < zhi); hb2 = np.arange(-p / 2, p / 2 + 0.05, 0.05); hh = np.histogram(X[qh], bins=hb2, weights=ww[qh])[0]; hx = (hb2[:-1] + hb2[1:]) / 2
    thr_ = 0.3 * np.sort(hh)[-len(hh) // 4:].mean(); dicht = hh >= thr_; i0 = int(np.argmin(np.abs(hx)))
    lo_i = i0; hi_i = i0; gap = 0
    for i in range(i0, -1, -1):
        if dicht[i]: lo_i = i; gap = 0
        else:
            gap += 1
            if gap > 6: break
    gap = 0
    for i in range(i0, len(hx)):
        if dicht[i]: hi_i = i; gap = 0
        else:
            gap += 1
            if gap > 6: break
    ext = (hx[lo_i] - 0.025, hx[hi_i] + 0.025); breite = ext[1] - ext[0]; n_licht = max(1, int(round(breite / wl0)))
    # Pfostenkamm x_k = c + (k - n/2) * wl, k = 0..n: Mitte c und wl durch Gittersuche gegen die gemessenen Pfostenspitzen (nicht symmetrisiert)
    pk = [q for q in peaks_1d(xb, hv_s, 0.15, 0.4) if abs(q[0]) < p / 2 - 0.2]; pkx = np.array([q[0] for q in pk]); pkw = np.array([q[1] for q in pk]); best = (1e9, 0.0, wl0)
    for c in np.arange(-0.4, 0.4, 0.005):
        for w_ in np.arange(wl0 - 0.1, wl0 + 0.1, 0.004):
            sx = c + (np.arange(n_licht + 1) - n_licht / 2) * w_; d_ = sum(min(np.abs(sx_ - pkx).min() if len(pkx) else 0.3, 0.3) for sx_ in sx)
            if d_ < best[0]: best = (d_, float(c), float(w_))
    _, c, wl = best; px = [float(c + (k - n_licht / 2) * wl) for k in range(n_licht + 1)]; ph_neu = float(ph + c); X = X - c; px = [x - c for x in px]
    log("Zelle: Pfostenspitzen (x, Gewicht) %s ; Lichtbreite ACF-Kandidaten %s ; Waagerechte x %.2f..%.2f -> n = %d; Kamm: Mitte %+.3f (Phase %.3f -> %.3f), Lichtbreite %.3f, Pfosten x %s, Abweichung zu Spitzen %s cm" % (
        [(round(a, 3), round(b, 1)) for a, b in pk], [(round(a, 3), round(b, 2)) for a, b in fk[:3]], ext[0], ext[1], n_licht, c, ph, ph_neu, wl, np.round(px, 3).tolist(), [round(100 * float(np.abs(x - (pkx - c)).min()), 1) if len(pkx) else None for x in px]))
    # Pfostenhoehen je Pfostenspalte (Innen/Aussen): 0,5 %/99,5 %-Quantil der Senkrechten in +-0,07 m der Pfostenspalte
    ci_all = np.round((tt - ph) / p).astype(int)
    def spalte(x):
        """Pfostenspalte: je Kopie (Fensterachse) Minimum/Maximum der Senkrechten in +-0,07 m, dann Median ueber die Kopien (Clutter einzelner Kopien faellt heraus)."""
        s_ = (cl == 0) & (np.abs(X - x) < 0.07) & (zz > zlo - 0.6) & (zz < zhi + kopf); mn, mx = [], []
        for c_ in np.unique(ci_all[s_]):
            q_ = s_ & (ci_all == c_)
            if q_.sum() >= 8: mn.append(zz[q_].min()); mx.append(zz[q_].max())
        return (float(np.median(mn)), float(np.median(mx))) if len(mn) >= 2 else None
    sp = [spalte(x) for x in px]; aussen = [sp[0], sp[-1]]; innen = sp[1:-1]
    z_sohl = float(np.median([s_[0] for s_ in sp if s_])); z_aussen = float(np.median([s_[1] for s_ in aussen if s_])) if any(aussen) else None; z_innen = float(np.median([s_[1] for s_ in innen if s_])) if any(innen) else z_aussen
    log("Pfostenspalten (z unten, z oben): %s -> Sohle %.2f, Aussenpfosten bis %.2f, Innenpfosten bis %.2f" % ([None if s_ is None else (round(s_[0], 2), round(s_[1], 2)) for s_ in sp], z_sohl, z_aussen, z_innen))
    # Waagerechte mit x-Laeufen
    xin = (X > px[0] - 0.1) & (X < px[-1] + 0.1); q = (cl == 1) & xin & (zz > z_sohl + 0.3) & (zz < z_innen + 0.3); zbins = np.arange(z_sohl, z_innen + 0.3, 0.03); hz = np.histogram(zz[q], bins=zbins, weights=ww[q])[0]; zc = (zbins[:-1] + zbins[1:]) / 2
    zp = peaks_1d(zc, np.convolve(hz, np.ones(3) / 3, "same"), 0.25, 0.25); horiz = []
    for zv, wgt in zp:
        s_ = q & (np.abs(zz - zv) < 0.07); hx_ = np.histogram(X[s_], bins=hb2, weights=ww[s_])[0]; ok = hx_ >= 0.3 * hx_.max(); i = 0
        while i < len(ok):
            if ok[i]:
                j = i
                while j < len(ok) and (ok[j] or (j + 1 < len(ok) and ok[j + 1])): j += 1
                if (j - i) * 0.05 >= 0.3: horiz.append(dict(z=float(zv), x0=float(hb2[i]), x1=float(hb2[j]), gewicht=float(hx_[i:j].sum())))
                i = j + 1
            else: i += 1
    log("Waagerechte (z, x0..x1): %s" % [(round(h["z"], 2), round(h["x0"], 2), round(h["x1"], 2)) for h in horiz])
    # Kopfform: schraege Kanten zwischen Aussen- und Innenpfosten; Gerade durch (x_aussen, z_aussen) - (x_innen, z_innen); Restabstand der schraegen Kantenpunkte
    xa, xi = px[-1], (px[-2] if n_licht >= 2 else None); kopf_f = dict(art="flach", z=z_innen); kopf_rest = None
    if n_licht >= 2 and z_aussen is not None and z_innen > z_aussen + 0.15:
        s_ = (cl == 2) & (np.abs(X) > abs(xi) + 0.05) & (np.abs(X) < abs(xa) - 0.05) & (zz > z_aussen - 0.3) & (zz < z_innen + 0.3); xs_, zs_, ws_ = np.abs(X[s_]), zz[s_], ww[s_]
        if s_.sum() >= 10:
            a0, b0 = z_aussen, (z_innen - z_aussen) / (abs(xi) - abs(xa))                      # Start: Gerade Aussenpfostenkopf -> Innenpfostenkopf; dann robuste Anpassung (3 Runden, |Rest| < 0,1 m, gewichtete Ausgleichsgerade)
            for _ in range(4):
                r_ = zs_ - (a0 + b0 * (xs_ - abs(xa))); m_ = np.abs(r_) < 0.1
                if m_.sum() < 8: break
                A_ = np.stack([np.ones(m_.sum()), xs_[m_] - abs(xa)], 1); sw = np.sqrt(ws_[m_]); a0, b0 = np.linalg.lstsq(A_ * sw[:, None], zs_[m_] * sw, rcond=None)[0]
            res_ = zs_ - (a0 + b0 * (xs_ - abs(xa))); kopf_rest = dict(n=int(s_.sum()), median=float(np.median(res_)), anteil_unter_5cm=float((np.abs(res_) < 0.05).mean()), anteil_unter_10cm=float((np.abs(res_) < 0.10).mean()))
            z_a2 = float(a0); z_i2 = float(a0 + b0 * (abs(xi) - abs(xa)))
            kopf_f = dict(art="giebelkopf", z_aussen=z_a2, z_innen_schraege=z_i2, z_innen=z_innen, x_aussen=abs(xa), x_innen=abs(xi), neigung_grad=float(np.degrees(np.arctan2(z_i2 - z_a2, abs(xa) - abs(xi)))), z_scheitel=z_innen)
    log("Kopfform: %s ; Restabstand schraege Kanten zur Geraden: %s" % (kopf_f, kopf_rest))
    kaem = []
    for k in range(n_licht):
        xm = 0.5 * (px[k] + px[k + 1]); c_ = [h for h in horiz if h["x0"] - 0.05 <= xm <= h["x1"] + 0.05 and z_sohl + 0.3 < h["z"] < z_innen - 0.3]; kaem.append(float(max(c_, key=lambda h: h["gewicht"])["z"]) if c_ else None)
    log("Kaempferhoehe je Licht (staerkste Waagerechte, die die Lichtmitte ueberdeckt): %s" % kaem)
    return dict(periode=p, phase=ph_neu, lichtbreite=wl, n_licht=n_licht, pfosten_x=px, kaempfer_je_licht=kaem, z_sohl=z_sohl, z_aussen=z_aussen, z_innen=z_innen, waagerechte=horiz, kopf=kopf_f, kopf_rest=kopf_rest, ausdehnung_waagerechte=ext, lichtbreite_acf=fk[:3]), ph_neu


def umriss_gruppe(zelle, tc, u, n, of, schritt=0.03):
    """Umriss einer Fenstergruppe an der Stelle t=tc (Polylinien Nx3): Pfosten, Kopfform, Waagerechte, Sohle. Rueckgabe dict(gruppe=Punkte, lichter=[Punkte je Licht], polys=[Polylinien])."""
    px = zelle["pfosten_x"]; ks = zelle["kopf"]; zs = zelle["z_sohl"]
    W_ = lambda x, zv: u * (tc + x) + n * of + np.array([0, 0, zv])
    def pfosten_top(k): return (ks.get("z_aussen", zelle["z_aussen"]) if k in (0, len(px) - 1) and len(px) > 2 else zelle["z_innen"])
    polys = []
    for k, x in enumerate(px): polys.append(np.array([W_(x, zs), W_(x, pfosten_top(k))]))
    if ks["art"] == "giebelkopf":
        zi_s = ks["z_innen_schraege"]; pk = [W_(px[0], ks["z_aussen"]), W_(px[1], zi_s), W_(px[1], zelle["z_innen"])] + [W_(x, zelle["z_innen"]) for x in px[2:-1]] + [W_(px[-2], zelle["z_innen"]), W_(px[-2], zi_s), W_(px[-1], ks["z_aussen"])]; polys.append(np.array(pk))
    else: polys.append(np.array([W_(px[0], zelle["z_innen"]), W_(px[-1], zelle["z_innen"])]))
    for h in zelle["waagerechte"]: polys.append(np.array([W_(max(h["x0"], px[0]), h["z"]), W_(min(h["x1"], px[-1]), h["z"])]))
    polys.append(np.array([W_(px[0], zs), W_(px[-1], zs)]))
    lichter = []
    for k in range(len(px) - 1):
        xa, xb = px[k], px[k + 1]; top = lambda x: np.interp(abs(x), [0, 1e9], [0, 1]) and 0
        za = pfosten_top(k); zb = pfosten_top(k + 1); lichter.append(dict(x=[tc + xa, tc + xb], umriss=poly_pts([W_(xa, zs), W_(xa, za), W_(xb, zb), W_(xb, zs), W_(xa, zs)], schritt)))
    return dict(gruppe=np.vstack([poly_pts(pl, schritt) for pl in polys]), lichter=lichter, polys=polys)


def fam_fenster(G, W, fotos, rah, z, out, audit=None):
    """Fensterreihe: Periode (Fensterachsen) -> Phase -> gefaltete Zelle -> Lichter (feine Periode) -> Hoehen/Kopf -> Kopien -> Lagesuche -> Fotoabnahme je Gruppe UND je Licht."""
    u, n, of = rah; P = G["P"]; zlo, zhi = z["zlo"], z["zhi"]; fr = np.abs(P @ n - of) < 0.3; v = fr & (G["cl"] == 0) & (P[:, 2] > zlo) & (P[:, 2] < zhi)
    t = P[v] @ u; w = G["w"][v]; res = dict(familie="fenster", zone=dict(u=u.tolist(), n=n.tolist(), off_front=of, zlo=zlo, zhi=zhi, quelle=z["quelle"], kandidaten=z.get("kandidaten")))
    pr = periode_grob(t, w, g("--pmin", 0.5), g("--pmax", 8.0)); log("Stufe 1 Fensterachsen: Periode %.4f m (grob %.3f, ACF %.2f), Plateau %.3f..%.3f (Breite %.3f m), Kandidaten %s" % (pr["periode"], pr["periode_grob"], pr["acf_max"], pr["plateau"][0], pr["plateau"][1], pr["plateau_breite"], pr["kandidaten"]))
    p = pr["periode"]; ph, asym = phase_symmetrie(t, w, p); log("Phase %.3f m (Spiegelasymmetrie %.3f)" % (ph, asym))
    iu = instanzen_ungefaltet(t, w); res["instanzen_ungefaltet"] = iu; log("Ungefaltete Instanzen (Bloecke >= Median + 10 MAD): %d Lagen %s, Abstaende %s, Streuung relativ %s -> %s" % (len(iu["lagen"]), np.round(iu["lagen"], 2).tolist(), np.round(iu["abstaende"], 2).tolist(), None if iu["abstand_streuung_rel"] is None else round(iu["abstand_streuung_rel"], 3), "STARR (Faltung zulaessig)" if iu["starr"] else "UNREGELMAESSIG: Instanzen einzeln ausrichten, Periode nur Startwert"))
    zelle, ph = zellen_lesen_fenster(G, rah, z, p, ph); zelle["plateau"] = pr["plateau"]; zelle["plateau_breite"] = pr["plateau_breite"]; res["zelle"] = zelle
    tt = P[v] @ u; t0, t1 = float(tt.min()), float(tt.max()); i0 = int(np.floor((t0 - ph) / p)) - 1; i1 = int(np.ceil((t1 - ph) / p)) + 1; tcs = [(i, ph + i * p) for i in range(i0, i1 + 1) if t0 - 1.0 <= ph + i * p <= t1 + 1.0]
    log("Kopien im Takt: %d (t %.1f..%.1f)" % (len(tcs), t0, t1))
    if fotos is None: res["kopien"] = [dict(index=i, t=tc) for i, tc in tcs]; return res, None, zelle
    # Lagesuche je Kopie (+-lage, 2,5 cm) ueber das Mittel des Kantenanteils (jedes 3. Foto), dann Medianverschiebung in die gemeinsame Phase
    lage = g("--lage", 0.15); sh = np.arange(-lage, lage + 1e-6, 0.025); sc = np.zeros((len(sh), len(tcs)))
    for a_, d_ in enumerate(sh):
        U_ = [umriss_gruppe(zelle, tc + d_, u, n, of) for _, tc in tcs]; r_ = fotos.abnahme([dict(pts=q["gruppe"], mitte=q["lichter"][len(q["lichter"]) // 2]["umriss"].mean(0)) for q in U_], W, schritt=3)
        sc[a_] = [x["kantenanteil_mittel"] or 0 for x in r_]
    dts = sh[np.argmax(sc, 0)]; log("Lagesuche je Kopie: dt %s (Mittel-Kantenanteil beste %s)" % (np.round(dts, 3).tolist(), np.round(sc.max(0), 2).tolist()))
    ok_ = sc.max(0) > 0.25; dmed = float(np.median(dts[ok_])) if ok_.any() else 0.0; ph += dmed; res["phase_foto"] = ph; res["phase_korrektur_foto"] = dmed; zelle["phase"] = ph; log("Phasenkorrektur aus den Fotos (Median %d Kopien): %+.3f m -> Phase %.3f" % (ok_.sum(), dmed, ph))
    tcs = [(i, ph + i * p) for i, _ in tcs]; U = [umriss_gruppe(zelle, tc, u, n, of) for _, tc in tcs]; dt_k = g("--kontroll", 0.5 * p)
    mit = lambda q: q["lichter"][len(q["lichter"]) // 2]["umriss"].mean(0)
    ab = fotos.abnahme([dict(pts=q["gruppe"], mitte=mit(q)) for q in U], W, kontroll=[kontrolle_punkte(q["gruppe"], dt_k, u) for q in U])
    ab_l = fotos.abnahme([dict(pts=l["umriss"], mitte=l["umriss"].mean(0)) for q in U for l in q["lichter"]], W, kontroll=[kontrolle_punkte(l["umriss"], dt_k, u) for q in U for l in q["lichter"]]); j = 0; inst = []
    for (i, tc), q, a_ in zip(tcs, U, ab):
        lt = []
        for l in q["lichter"]:
            b = ab_l[j]; j += 1; lt.append(dict(x=[float(x) for x in l["x"]], **{k_: b[k_] for k_ in ("fotos_gesehen", "fotos_kante", "bestanden", "kontrolle_kante", "kontrolle_gesehen", "kantenanteil_median")}))
        inst.append(dict(index=i, t=tc, mitte=[float(x) for x in mit(q)], lichter=lt, n_lichter_bestanden=sum(l["bestanden"] for l in lt), **{k_: a_[k_] for k_ in ("fotos_gesehen", "fotos_kante", "bestanden", "kontrolle_kante", "kontrolle_gesehen", "kantenanteil_median", "fotos")}))
    for q in inst: log("  Gruppe %3d t %7.2f  Fotos gesehen %3d Kante %3d (Kontrolle %3d/%3d) Median %.2f  Lichter bestanden %d/%d  %s" % (q["index"], q["t"], q["fotos_gesehen"], q["fotos_kante"], q["kontrolle_kante"], q["kontrolle_gesehen"], q["kantenanteil_median"] or 0, q["n_lichter_bestanden"], zelle["n_licht"], "OK" if q["bestanden"] else "--"))
    res["instanzen"] = inst; res["anzahl_gruppen_fotogeprueft"] = sum(q["bestanden"] for q in inst); res["anzahl_lichter_fotogeprueft"] = sum(l["bestanden"] for q in inst if q["bestanden"] for l in q["lichter"])
    seg = []
    for q, qi in zip(U, inst):
        if qi["bestanden"]:
            for pl in q["polys"]: seg += [[pl[k_].tolist(), pl[k_ + 1].tolist(), 16, 1.0] for k_ in range(len(pl) - 1)]
    res["segmente"] = seg; return res, U, zelle


# ----------------------------------------------------------------------------------------------- Familie gaube
def dachebene_fit(W, u, n, off_lo, off_hi, zmin):
    """Dachebene z = a + b*off (off = -P@n = Abstand nach hinten) aus der Wolke: RANSAC (4000 Paare auf 30000 Punkten, Steigung -2..-0,5, Inlier |Rest| < 0,12 m), dann Kleinste Quadrate auf den Inliern (4 Runden)."""
    off = -(W @ n); m = (off > off_lo) & (off < off_hi) & (W[:, 2] > zmin); X = off[m]; Z = W[m, 2].astype(np.float64); rng = np.random.default_rng(1); sub = rng.choice(len(X), min(len(X), 30000), replace=False); xs, zs = X[sub], Z[sub]
    i1 = rng.integers(0, len(xs), 4000); i2 = rng.integers(0, len(xs), 4000); dx = xs[i2] - xs[i1]; ok = np.abs(dx) > 0.5; i1, i2, dx = i1[ok], i2[ok], dx[ok]; b = (zs[i2] - zs[i1]) / dx; a = zs[i1] - b * xs[i1]; ok = (b < -0.5) & (b > -2.0); a, b = a[ok], b[ok]; best = (-1, 0, 0)
    for k in range(0, len(a), 200):
        cnt = (np.abs(zs[None, :] - a[k:k + 200, None] - b[k:k + 200, None] * xs[None, :]) < 0.12).sum(1); j = int(np.argmax(cnt))
        if cnt[j] > best[0]: best = (int(cnt[j]), float(a[k + j]), float(b[k + j]))
    _, a0, b0 = best; A = np.c_[np.ones(len(X)), X]; c = np.array([a0, b0])
    for _ in range(4):
        k = np.abs(Z - A @ c) < 0.12
        if k.sum() < 100: break
        c = np.linalg.lstsq(A[k], Z[k], rcond=None)[0]
    return float(c[0]), float(c[1]), float(k.mean())


def dach_zone_aus_gitter(G, u, n, W=None):
    """Dachzone ohne Konstanten: (1) Gitter: lange schraege Segmente quer zur Fassade (Neigung 35-70 Grad, > 1 m) -> off-Bereich; reicht das nicht (< 20 Segmente) (2) Hough auf der Wolke: z = a + b*off,
    b in [-2,-0,5] (Schritt 0,01), Spitze der a-Histogramm (10 cm) der oberen Haelfte der Punkte; Zone = off 5..95 % der Inlier."""
    P0, P1, L = G["P0"], G["P1"], G["L"]; d = P1 - P0; dz = np.abs(d[:, 2]) / L; q = (dz > 0.55) & (dz < 0.95) & (L > 1.0) & (np.abs(d[:, :2] @ u[:2]) / L < 0.5)
    if q.sum() >= 20:
        M = (P0 + P1) / 2; off = -(M[q] @ n); return float(np.percentile(off, 5)), float(np.percentile(off, 95)), float(np.percentile(M[q][:, 2], 5)), int(q.sum())
    rng = np.random.default_rng(0); Wt = W[rng.choice(len(W), min(len(W), 400000), replace=False)]; Wt = Wt[Wt[:, 2] > np.median(Wt[:, 2])]; off = -(Wt @ n); best = (0, 0, 0)
    for b in np.arange(-2.0, -0.5, 0.01):
        h = np.histogram(Wt[:, 2] - b * off, bins=np.arange((Wt[:, 2] - b * off).min(), (Wt[:, 2] - b * off).max() + 0.1, 0.1))[0]; k = int(h.max())
        if k > best[0]: best = (k, b, int(h.argmax()))
    k, b, ia = best; r_ = Wt[:, 2] - b * off; a0 = r_.min() + ia * 0.1 + 0.05; m = np.abs(r_ - a0) < 0.15
    return float(np.percentile(off[m], 5)), float(np.percentile(off[m], 95)), float(np.percentile(Wt[m][:, 2], 5)), int(m.sum())


def gaube_blobs(W, u, n, a, b, off_lo, off_hi, zmin, y_min=0.3, rast=0.1, amin=1.0, amax=8.0):
    """Zone Gauben: Ausbuchtung y (senkrecht ueber der Dachebene) > y_min; Hoehenkarte (Maximum je 10-cm-Zelle), Morphologie-Schluss, zusammenhaengende Komponenten mit Flaeche amin..amax m2."""
    import cv2
    from scipy import ndimage as ndi
    nz = 1 / math.hypot(1, b); t = W @ u; off = -(W @ n); y = (W[:, 2] - (a + b * off)) * nz; m = (off > off_lo) & (off < off_hi) & (W[:, 2] > zmin) & (y > -0.3) & (y < 3.0)
    t0 = float(t[m].min()); ti = ((t[m] - t0) / rast).astype(int); oi = ((off[m] - off_lo) / rast).astype(int); H = np.full((oi.max() + 2, ti.max() + 2), -9.0); np.maximum.at(H, (oi, ti), y[m])
    occ = cv2.morphologyEx((H > y_min).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)); lab, nl = ndi.label(occ); out = []
    for i in range(1, nl + 1):
        q = lab == i; A = q.sum() * rast * rast
        if A < amin or A > amax: continue
        yy, xx = np.where(q); out.append(dict(flaeche=float(A), t=(float(xx.min() * rast + t0), float(xx.max() * rast + t0)), off=(float(yy.min() * rast + off_lo), float(yy.max() * rast + off_lo)), t_mitte=float(xx.mean() * rast + t0), off_mitte=float(yy.mean() * rast + off_lo)))
    return sorted(out, key=lambda q: q["t_mitte"])


def gaube_hoehenkarten(W, u, n, a, b, zentren, hx=2.0, d0=-2.5, d1=2.5, r=0.05):
    """Je Zentrum (t, off) Hoehenkarte y_max(x, d) relativ zum Zentrum, x in +-hx, d = off - off0 in d0..d1 (Zellen r)."""
    nz = 1 / math.hypot(1, b); t = W @ u; off = -(W @ n); y = (W[:, 2] - (a + b * off)) * nz; out = []
    for t0, o0 in zentren:
        m = (np.abs(t - t0) < hx + 0.3) & (off - o0 > d0 - 0.3) & (off - o0 < d1 + 0.3) & (y > -0.3) & (y < 3.0); xi = np.round((t[m] - t0 + hx) / r).astype(int); di = np.round((off[m] - o0 - d0) / r).astype(int)
        nx, nd = int(round(2 * hx / r)) + 1, int(round((d1 - d0) / r)) + 1; ok = (xi >= 0) & (xi < nx) & (di >= 0) & (di < nd); S_ = np.zeros((nd, nx)); C_ = np.zeros((nd, nx)); np.add.at(S_, (di[ok], xi[ok]), y[m][ok]); np.add.at(C_, (di[ok], xi[ok]), 1.0); H = np.where(C_ >= 2, S_ / np.maximum(C_, 1), -9.0); out.append(H)      # Zellenmittel (unverzerrt gegen Rauschen, Maximum waere +2 sigma hoch)
    return out


def gaube_ausrichten(Hs, r=0.05, iter_=3, such=0.6):
    """Gemeinsame Musterzelle: Belegungskarten (H > 0,3) per FFT-Kreuzkorrelation (GPU) an das Mittel ausrichten (Verschiebung +-such m), Mittel neu, 3 Runden. Gibt (Verschiebungen dx,dd in m, Mittelkarte)."""
    torch, dev = torch_dev(); O = torch.tensor(np.stack([(H > 0.3).astype(np.float32) for H in Hs]), device=dev); nk = len(Hs); sh = np.zeros((nk, 2)); K = int(such / r)
    for _ in range(iter_):
        T = torch.zeros_like(O)
        for i in range(nk): T[i] = torch.roll(O[i], shifts=(int(round(sh[i, 1] / r)), int(round(sh[i, 0] / r))), dims=(0, 1))
        mean = T.mean(0)
        for i in range(nk):
            ref = (mean * nk - T[i]) / max(nk - 1, 1); F = torch.fft.rfft2(O[i]); Fr = torch.fft.rfft2(ref); cc = torch.fft.irfft2(Fr * F.conj(), s=O[i].shape)             # cc[s] = sum ref(x) O(x - s)... -> Verschiebung, die O auf ref schiebt
            cc = torch.roll(cc, shifts=(K, K), dims=(0, 1))[:2 * K + 1, :2 * K + 1]; k = int(torch.argmax(cc)); dd, dx = divmod(k, 2 * K + 1); sh[i] = [(dx - K) * r * -1, (dd - K) * r * -1]
            sh[i] = [(K - dx) * r * -1 * -1, (K - dd) * r * -1 * -1] if False else sh[i]
    return sh


def gaube_modelle(x, d, par, fam):
    """Hoehenfeld (senkrecht ueber der Dachebene, m) einer Gaube; Koordinaten x (lateral), d (off-Richtung, + = zur Traufe/Front). par = Parameter je Familie.
    schlepp: [w, d1 (Front), h1 (Fronthoehe), m (Hoehenabfall je m nach hinten)]  -> h = h1 - m*(d1-d) fuer |x|<w/2, d<=d1, h>0 (Pultdach, Frontflaeche senkrecht)
    satteldach: [w, d1, hr (First an der Front), m, k] -> h = hr - m*(d1-d) - k*|x| (Giebel mit Walm-frei, k = tan Dachneigung), >0
    flach: [w, d1, h1, m] mit |x|<w/2 und h = h1 (Kasten; m=0) -> Sonderfall schlepp mit m=0."""
    x = x - par[-1]                                                   # letzter Parameter = seitlicher Versatz x0 (Blobmitte ist nicht die Achse)
    if fam == "schlepp" or fam == "flach":
        w, d1, h1, m = par[:4]; h = h1 - m * (d1 - d); mask = (np.abs(x) <= w / 2) & (d <= d1)
    else:
        w, d1, hr, m, k = par[:5]; h = hr - m * (d1 - d) - k * np.abs(x); mask = (np.abs(x) <= w / 2) & (d <= d1)
    return np.where(mask & (h > 0.0), h, 0.0)


def gaube_fit_familien(Hm, hx, d0, r, fam_liste=("schlepp", "satteldach"), starts=300, seed=1):
    """Familien gegen die Mittel-Hoehenkarte Hm (Median ueber ausgerichtete Gauben; leere Zellen = 0) anpassen: Zufallsstarts + scipy least_squares, Rest = RMS ueber alle Zellen im Fenster."""
    from scipy.optimize import least_squares
    nd, nx = Hm.shape; X = (np.arange(nx) * r - hx)[None, :] * np.ones((nd, 1)); Dd = (np.arange(nd) * r + d0)[:, None] * np.ones((1, nx)); obs = np.where(Hm > 0.3, Hm, 0.0); rng = np.random.default_rng(seed); res = {}
    for fam in fam_liste:
        lo = np.array([0.8, -0.8, 0.3, 0.05] + ([0.0] if fam == "satteldach" else []) + [-0.3]); hi = np.array([3.0, 1.8, 1.6, 1.0] + ([1.5] if fam == "satteldach" else []) + [0.3]); best = None
        for _ in range(starts):
            p0 = lo + (hi - lo) * rng.random(len(lo))
            try: r_ = least_squares(lambda p: ((lambda m_: np.where(m_ > 0.3, m_, 0.0) - obs)(gaube_modelle(X, Dd, p, fam))).ravel(), p0, bounds=(lo, hi), diff_step=0.02, max_nfev=80)      # beide Seiten bei 0,3 m (Dachrauschen) abgeschnitten: Schwanz unter 0,3 m ist nicht beobachtbar
            except Exception: continue
            if best is None or r_.cost < best.cost: best = r_
        rms = float(np.sqrt(2 * best.cost / obs.size)); res[fam] = dict(par=[float(x) for x in best.x], rms=rms)
    return res


def gaube_umriss(par, fam, t0, o0, a, b, u, n, dx=0.0, dd=0.0, schritt=0.03):
    """3D-Umriss einer Gaube (Polylinien): Front-Rechteck/-Giebel, Seitenkanten, Dachkanten bis zum Schnitt mit der Dachebene."""
    nz = 1 / math.hypot(1, b)
    def Wp(x, off, y): return u * (t0 + dx + x) - n * (o0 + dd + off) + np.array([0, 0, a + b * (o0 + dd + off) + y / nz])        # y senkrecht ueber der Ebene -> z-Anteil y/nz (Normale schraeg: Naeherung in z)
    dx = dx + par[-1]; par = list(par[:-1])
    if fam in ("schlepp", "flach"):
        w, d1, h1, m = par; db = d1 - h1 / m if m > 1e-3 else d1 - 3.0; db = max(db, d1 - 3.0); hb = max(h1 - m * (d1 - db), 0.0)
        P = [[Wp(-w / 2, d1, 0), Wp(-w / 2, d1, h1), Wp(w / 2, d1, h1), Wp(w / 2, d1, 0), Wp(-w / 2, d1, 0)], [Wp(-w / 2, d1, h1), Wp(-w / 2, db, hb)], [Wp(w / 2, d1, h1), Wp(w / 2, db, hb)], [Wp(-w / 2, db, hb), Wp(w / 2, db, hb)]]
    else:
        w, d1, hr, m, k = par; he = max(hr - k * w / 2, 0.0); db = d1 - hr / m if m > 1e-3 else d1 - 3.0; db = max(db, d1 - 3.0); hrb = max(hr - m * (d1 - db), 0.0); heb = max(he - m * (d1 - db), 0.0)
        P = [[Wp(-w / 2, d1, 0), Wp(-w / 2, d1, he), Wp(0, d1, hr), Wp(w / 2, d1, he), Wp(w / 2, d1, 0), Wp(-w / 2, d1, 0)], [Wp(0, d1, hr), Wp(0, db, hrb)], [Wp(-w / 2, d1, he), Wp(-w / 2, db, heb)], [Wp(w / 2, d1, he), Wp(w / 2, db, heb)]]
    return [np.array(q) for q in P]


def fam_gaube(G, W, fotos, rah, out, audit=None):
    u, n, of = rah; u = np.array(u); n = np.array(n); lo, hi, zmin, nseg = dach_zone_aus_gitter(G, u, n, W); lo, hi = g("--dach_off_lo", lo), g("--dach_off_hi", hi)
    log("Dachzone (Gitter-Segmente bzw. Hough der Wolke, %d Stuetzen): off %.2f..%.2f, z ab %.2f" % (nseg, lo, hi, zmin))
    a_, b_, inl = dachebene_fit(W, u, n, lo, hi, zmin); log("Dachebene aus der Wolke: z = %.3f %+.4f * off (Neigung %.1f Grad, Inlieranteil %.2f)" % (a_, b_, math.degrees(math.atan(-b_)), inl))
    bl = gaube_blobs(W, u, n, a_, b_, lo, hi, zmin); log("Zone Gauben: %d Ausbuchtungen (Flaeche 1..8 m2, y > 0,3 m ueber der Dachebene): %s" % (len(bl), [(round(x["t_mitte"], 2), round(x["off_mitte"], 2), round(x["flaeche"], 1)) for x in bl]))
    res = dict(familie="gaube", dachebene=dict(a=a_, b=b_, inlier=inl), blobs=bl)
    if len(bl) < 2: log("zu wenige Gauben fuer die Faltung"); res["instanzen"] = []; return res, None
    Hs = gaube_hoehenkarten(W, u, n, a_, b_, [(x["t_mitte"], x["off_mitte"]) for x in bl]); sh = gaube_ausrichten(Hs); r = 0.05; hx = 2.0; d0 = -2.5
    log("Ausrichtung (dx, dd) je Gaube in m: %s" % np.round(sh, 2).tolist())
    # ausgerichtete Karten uebereinanderlegen: Median ueber Gauben (Zellen, die in >= 50 % der Gauben belegt sind), sonst 0
    St = np.stack([np.roll(H, shift=(int(round(s_[1] / r)), int(round(s_[0] / r))), axis=(0, 1)) for H, s_ in zip(Hs, sh)]); occ = (St > 0.3).mean(0); Hm = np.where(occ >= 0.5, np.median(np.where(St > 0.3, St, np.nan), axis=0, where=True) if False else np.nanmedian(np.where(St > 0.3, St, np.nan), axis=0), 0.0); Hm = np.nan_to_num(Hm, nan=0.0)
    fits = gaube_fit_familien(Hm, hx, d0, r); log("Formfamilien gegen die gemittelte Hoehenkarte: " + "; ".join("%s RMS %.3f m par %s" % (k, v["rms"], np.round(v["par"], 3).tolist()) for k, v in fits.items()))
    fam = min(fits, key=lambda k: fits[k]["rms"]); res["fits"] = fits; res["familie_gaube"] = fam
    np.save(os.path.join(os.path.dirname(out) or ".", "gauben_mittelkarte.npy"), Hm)
    # Je Gaube eigener Fit der gewaehlten Familie (Streuung = Faltungsgewinn) und Fotoabnahme
    par = fits[fam]["par"]; inst = []; U = []
    for i, (x, s_) in enumerate(zip(bl, sh)):
        U.append(gaube_umriss(par, fam, x["t_mitte"], x["off_mitte"], a_, b_, u, n, dx=-s_[0], dd=-s_[1]))
    if fotos is not None:
        kandidaten = {}
        for fk in fits:
            Uk = [gaube_umriss(fits[fk]["par"], fk, x["t_mitte"], x["off_mitte"], a_, b_, u, n, dx=-s_[0], dd=-s_[1]) for x, s_ in zip(bl, sh)]
            ab = fotos.abnahme([dict(pts=np.vstack([poly_pts(p_, 0.04) for p_ in q]), mitte=np.vstack(q).mean(0)) for q in Uk], W, nfoto=NFOTO); kandidaten[fk] = ab
            log("Foto-Gegenprobe Familie %s: Kantenanteil Mittel je Gaube %s, abgenommen %d/%d" % (fk, [round(q["kantenanteil_mittel"] or 0, 2) for q in ab], sum(q["bestanden"] for q in ab), len(ab)))
        res["foto_je_familie"] = {k: [{kk: vv for kk, vv in q.items()} for q in v] for k, v in kandidaten.items()}
        ab = kandidaten[fam]
    else: ab = [dict(bestanden=False) for _ in bl]
    for i, (x, s_, q) in enumerate(zip(bl, sh, ab)): inst.append(dict(index=i, t=x["t_mitte"] - s_[0], off=x["off_mitte"] - s_[1], par=par, familie=fam, **{k_: q.get(k_) for k_ in ("fotos_gesehen", "fotos_kante", "kantenanteil_median", "kontrolle_kante", "kontrolle_gesehen", "bestanden")}))
    for q in inst: log("  Gaube %d t %.2f off %.2f  Fotos gesehen %s Kante %s Median %s  %s" % (q["index"], q["t"], q["off"], q["fotos_gesehen"], q["fotos_kante"], q["kantenanteil_median"], "OK" if q["bestanden"] else "--"))
    seg = []
    for q, qi in zip(U, inst):
        if qi["bestanden"]:
            for pl in q: seg += [[pl[k_].tolist(), pl[k_ + 1].tolist(), 17, 1.0] for k_ in range(len(pl) - 1)]
    res["instanzen"] = inst; res["segmente"] = seg; res["anzahl_fotogeprueft"] = sum(q["bestanden"] for q in inst); return res, U


def tor_params_fenster(Z):
    """Zelle (Mass-Dict wie fam_fenster) + Gruppen-t -> Parameterliste des Tors. Z = dict(u, n, of, tcs, p, z_sohl, z_aussen, z_innen, pfosten_x, kaempfer=[z je Licht], kopf_z=[je Licht Scheitel? ]).
    Kaempfer je Licht getrennt (Nutzerbefund: mittlerer Kaempfer falsch)."""
    u, n, of = np.array(Z["u"]), np.array(Z["n"]), Z["of"]; tcs = Z["tcs"]; px = Z["pfosten_x"]; nl = len(px) - 1; zs = Z["z_sohl"]; zin = Z["z_innen"]; zau = Z["z_aussen"]; p = Z["p"]; wl = Z["wl"]
    Wp = lambda tc, x, zv: u * (tc + x) + n * of + np.array([0, 0, zv]); ptop = lambda k: zau if k in (0, nl) else zin
    def gruppe(tc, dt=0.0, kz=None, dpx=None, kopf=None):
        px_ = [x + (dpx[0] if dpx and k == dpx[1] else 0.0) for k, x in enumerate(px)]; zk = list(Z["kaempfer"]) if kz is None else list(kz); L = []
        for k, x in enumerate(px_): L.append(linie(Wp(tc + dt, x, zs), Wp(tc + dt, x, ptop(k))))
        for k in range(nl): L.append(linie(Wp(tc + dt, px_[k], zk[k]), Wp(tc + dt, px_[k + 1], zk[k])))
        L.append(linie(Wp(tc + dt, px_[0], zs), Wp(tc + dt, px_[-1], zs)))
        zi = zin if kopf is None else kopf; L.append(linie(Wp(tc + dt, px_[1], zi), Wp(tc + dt, px_[-2], zi)) if nl >= 2 else linie(Wp(tc + dt, px_[0], zi), Wp(tc + dt, px_[-1], zi))); return np.vstack(L)
    par = []; tol_ph = max(0.05, min(0.1 * p, 0.15))
    par.append(dict(name="phase_fenstergruppen", werte=np.arange(-p / 2, p / 2 + 1e-9, 0.02), gesetzt=0.0, tol=tol_ph, feat=lambda v: sammeln([(gruppe(tc, dt=v), i) for i, tc in enumerate(tcs)])))
    # Unterpositionen = Licht-Index; Spiegelsymmetrie koppelt nur Gegenstuecke (k und nl-1-k), die Mitte bleibt frei (Nutzerbefund: Mittel-Kaempfer/-Scheitel hoeher)
    paare = []
    for k in range((nl + 1) // 2): paare.append(sorted({k, nl - 1 - k}))
    def kaem_feat(ks): return lambda v: sammeln([(linie(Wp(tc, px[k_] + 0.05, v), Wp(tc, px[k_ + 1] - 0.05, v)), i) for i, tc in enumerate(tcs) for k_ in ks])
    for ks in paare: par.append(dict(name="kaempferhoehe_licht" + "+".join(str(k_) for k_ in ks), werte=np.arange(zs + 0.3, zin + 0.05, 0.02), gesetzt=float(np.mean([Z["kaempfer"][k_] for k_ in ks])), tol=0.05, feat=kaem_feat(ks)))
    pp = []
    for k in range((nl + 2) // 2): pp.append(sorted({k, nl - k}))
    def pf_feat(ks): return lambda v: sammeln([(linie(Wp(tc, px[k_] + (v if k_ <= nl / 2 else -v), zs + 0.2), Wp(tc, px[k_] + (v if k_ <= nl / 2 else -v), ptop(k_) - 0.2)), i) for i, tc in enumerate(tcs) for k_ in ks])
    for ks in pp: par.append(dict(name="pfostenlage_" + "+".join(str(k_) for k_ in ks) + " (gespiegelt)", werte=np.arange(-wl / 2, wl / 2 + 1e-9, 0.01), gesetzt=0.0, tol=0.05, feat=pf_feat(ks)))
    par.append(dict(name="kopfscheitel_mittel(innen)", werte=np.arange(zin - 0.5, zin + 0.5 + 1e-9, 0.02), gesetzt=zin, tol=0.05, feat=lambda v: sammeln([(linie(Wp(tc, px[1], v), Wp(tc, px[-2], v)) if nl >= 2 else linie(Wp(tc, px[0], v), Wp(tc, px[-1], v)), i) for i, tc in enumerate(tcs)])))
    if nl >= 2: par.append(dict(name="kopfhoehe_aussen(gespiegelt)", werte=np.arange(zau - 0.5, zau + 0.5 + 1e-9, 0.02), gesetzt=zau, tol=0.05, feat=lambda v: sammeln([(np.vstack([linie(Wp(tc, px[0], v), Wp(tc, px[1], zin)), linie(Wp(tc, px[-1], v), Wp(tc, px[-2], zin))]), i) for i, tc in enumerate(tcs)])))
    zen = np.array([Wp(tc, 0, 0.5 * (zs + zin)) for tc in tcs]); return par, zen


def tor_params_konsole(Z):
    """Konsolenreihe: Z = dict(u, n, of, along=[...], z0, z1 (Plattenunterkante), tiefe, breite_oben, breite_unten, periode). Parameter: Phase aller Konsolen (+-p/2).
    Wolke: Vorderflaeche der Konsole (Trapez, Raster); Fotos: Umriss der Vorderflaeche."""
    u, n, of = np.array(Z["u"]), np.array(Z["n"]), Z["of"]; al = Z["along"]; tvor = of + Z["tiefe"]
    Wp = lambda a_, zv, vor=None: u * a_ + n * (tvor if vor is None else of + vor) + np.array([0, 0, zv]); bo, bu = Z["breite_oben"] / 2, Z["breite_unten"] / 2
    def eck(a_, dt): return [Wp(a_ + dt - bo, Z["z1"]), Wp(a_ + dt + bo, Z["z1"]), Wp(a_ + dt + bu, Z["z0"]), Wp(a_ + dt - bu, Z["z0"])]
    def umriss(a_, dt): e = eck(a_, dt); return np.vstack([linie(e[i], e[(i + 1) % 4]) for i in range(4)])
    p = Z["periode"]; par = [dict(name="phase_konsolen", werte=np.arange(-p / 2, p / 2 + 1e-9, 0.02), gesetzt=0.0, tol=max(0.05, min(0.1 * p, 0.15)), feat=lambda v: sammeln([(umriss(a_, v), i) for i, a_ in enumerate(al)]), feat_wolke=lambda v: sammeln([(flaeche_raster([e for e in eck(a_, v)]), i) for i, a_ in enumerate(al)]))]
    zen = np.array([Wp(a_, 0.5 * (Z["z0"] + Z["z1"])) for a_ in al]); return par, zen


def tor_params_rotation(Z):
    """Rotationskoerper-Reihe (Baluster): Z = dict(achsen=[[x,y,..]], zlo, zhi, r, u, periode). Parameter: Phase (+-p/2). Fotos: die beiden Silhouettenlinien (+-r laengs u) gegen den Sobelbetrag des Originalfotos
    (Stabilitaetskarten sind fuer 4-px-Teile zu grob); Wolke: Achsenlinie, Zaehlung der Punkte im Radius 0,075 (Schaft deckt die Achse, die Luecke zwischen den Staeben nicht)."""
    u = np.array(Z["u"]); ax = np.array(Z["achsen"]); r = Z["r"]; p = Z["periode"]
    def lin(v, spec): return [(np.vstack([linie(np.r_[a_[:2] + u[:2] * (v + off), Z["zlo"]], np.r_[a_[:2] + u[:2] * (v + off), Z["zhi"]]) for off, _ in spec]), i, 1.0) if False else (None) for i, a_ in enumerate(ax)]
    def lin(v, spec):
        out = []
        for i, a_ in enumerate(ax):
            for off, w_ in spec: out.append((linie(np.r_[a_[:2] + u[:2] * (v + off), Z["zlo"]], np.r_[a_[:2] + u[:2] * (v + off), Z["zhi"]]), i, w_))
        return out
    zen = np.array([np.r_[a_[:2], 0.5 * (Z["zlo"] + Z["zhi"])] for a_ in ax])
    return [dict(name="phase_%s" % Z.get("name", "rotation"), werte=np.arange(-p / 2, p / 2 + 1e-9, 0.01), gesetzt=0.0, tol=0.05, feat=lambda v: sammeln(lin(v, [(-r, 1.0), (r, 1.0), (-p / 2, -1.0), (p / 2, -1.0)])), feat_wolke=lambda v: sammeln(lin(v, [(0.0, 1.0), (-p / 2, -1.0), (p / 2, -1.0)])), modus="gradient", r_wolke=0.03, kmax=16)], zen


def tor_laufen(F, cloud, WK, par, zen):
    T = Tor(F, cloud); T.F_cloudW = WK; res = []
    for q in par:
        if "feat_wolke" in q: log("Parameter %s: Wolke gegen Flaechenraster, Fotos gegen Umriss" % q["name"])
        o = T.sweep_zwei(q, zen) if "feat_wolke" in q else T.sweep(q["name"], q["feat"], q["werte"], q["gesetzt"], q["tol"], zen, r_wolke=q.get("r_wolke"), kmax=q.get("kmax", 4), modus=q.get("modus", "karte")); res.append(o)
    return res


def _sweep_zwei(s, q, zen):
    """Parameter mit getrennten Merkmalen fuer Wolke (Flaeche) und Fotos (Umriss): zwei Sweeps, Urteil kombiniert."""
    o_f = s.sweep(q["name"], q["feat"], q["werte"], q["gesetzt"], q["tol"], zen, modus=q.get("modus", "karte")); o_w = s.sweep(q["name"], q["feat_wolke"], q["werte"], q["gesetzt"], q["tol"], zen, r_wolke=q.get("r_wolke"), kmax=q.get("kmax", 4))
    o = dict(o_f); o["wolke"] = o_w["wolke"]; o["urteil"] = s.urteil(o); return o


Tor.sweep_zwei = _sweep_zwei


# ----------------------------------------------------------------------------------------------- main
def main_fenster():
    G = gitter_laden(g("--gitter", "", str)); W = lade_wolke(g("--wolke", "", str)); fotos = Fotos(g("--kam", "", str), g("--stabil", "", str), g("--bilder", "", str))
    if "--rahmen" in a:
        R = json.load(open(g("--rahmen", "", str))); rah = (np.array(R["u"]), np.array(R["n"]), float(R["off_front"])); log("Rahmen aus %s: u %s off_front %.3f" % (g("--rahmen", "", str), np.round(rah[0][:2], 4).tolist(), rah[2]))
    else: rah = rahmen_auto(G); log("Rahmen automatisch aus dem Gitter: u %s off_front %.3f" % (np.round(rah[0][:2], 4).tolist(), rah[2]))
    z = zone_fenster(G, rah, g("--band", None, str)); log("Zone: z %.2f..%.2f (%s); Kandidaten %s" % (z["zlo"], z["zhi"], z["quelle"], z["kandidaten"]))
    res, kop, zelle = fam_fenster(G, W, fotos, rah, z, g("--out", "", str), g("--audit", None, str))
    res.pop("_kop", None); U = kop; json.dump(res, open(g("--out", "", str), "w"), indent=1); log("geschrieben:", g("--out", "", str))
    if "--audit" in a and U:
        os.makedirs(g("--audit", "", str), exist_ok=True)
        for foto in g("--fotos", "ip_IMG_6120,ip_IMG_6261", str).split(","):
            gut = [pl for q, qi in zip(U, res["instanzen"]) if qi["bestanden"] for pl in q["polys"]]; schl = [pl for q, qi in zip(U, res["instanzen"]) if not qi["bestanden"] for pl in q["polys"]]
            try: overlay(fotos, gut, schl, foto, os.path.join(g("--audit", "", str), "muster_fenster_%s_entwurf.jpg" % foto), crop_um=np.vstack([pl for q in U for pl in q["polys"]])[::3])
            except AssertionError as e: log("Foto fehlt", e)


def Z_aus_instanzen(fam, I):
    """Instanzdatei (muster_fit-Ausgabe, Koerper v11, baluster_abgenommen) -> Z-Dict der Familie (nur Kantenlieferant; die Pruefung selbst ist neutral in kanten_tor.py)."""
    if fam == "fenster":
        if "zelle" in I:
            z_ = I["zelle"]; zo = I["zone"]; tcs = [q["t"] for q in I["instanzen"] if q["bestanden"]]
            return dict(u=zo["u"], n=zo["n"], of=zo["off_front"], tcs=tcs, p=z_["periode"], z_sohl=z_["z_sohl"], z_aussen=z_["z_aussen"], z_innen=z_["z_innen"], pfosten_x=z_["pfosten_x"], kaempfer=[k_ if k_ is not None else 0.5 * (z_["z_sohl"] + z_["z_innen"]) for k_ in z_["kaempfer_je_licht"]], wl=z_["lichtbreite"])
        F_ = I["fenster"]; w = F_["w_licht"]; nl = F_["n_licht"]
        return dict(u=I["u"], n=I["n"], of=I["off_front"], tcs=[g_["mitte"] for g_ in F_["gruppen"]], p=F_["periode"], z_sohl=F_["z_sohl"], z_aussen=F_["z_schulter"], z_innen=F_["z_scheitel"], pfosten_x=[(k - nl / 2) * w for k in range(nl + 1)], kaempfer=[F_["z_kaempfer"]] * nl, wl=w)
    if fam == "konsole":
        K = json.load(open(g("--konsolen", "", str))); B = I["balkon"]; kons = K["konsolen"]
        return dict(u=I["u"], n=I["n"], of=I["off_front"], along=[k_["along"] for k_ in kons], z0=float(np.median([k_["z0"] for k_ in kons])), z1=B["platte"]["z0"], tiefe=B["platte"]["tiefe"] - 0.15, breite_oben=0.45, breite_unten=0.2, periode=K["periode"])
    if fam == "rotation":
        pr = I["profil"]; r = max(q[0] for q in pr) if pr else 0.07; z_ = I["band"]
        return dict(achsen=[x["mitte"] for x in I["baluster"]], zlo=z_[0] + 0.05, zhi=z_[1] - 0.05, r=r, u=I["fassade"]["richtung"] + [0.0], periode=I["periode"])
    raise SystemExit("Familie %s nicht angelegt" % fam)


def kanten_aus_Z(fam, Z):
    """Kanten + Kopplungsgruppen der Familie. Die Familie kennt KEINE Hoehen-Sonderfaelle: alle gleichartigen Kanten einer Zelle (z. B. alle Kaempfer) liegen in EINER Gruppe; das Tor trennt sie bei Bedarf selbst auf."""
    E = []
    if fam == "fenster":
        u, n, of = np.array(Z["u"]), np.array(Z["n"]), Z["of"]; px = Z["pfosten_x"]; nl = len(px) - 1; zs, zin, zau = Z["z_sohl"], Z["z_innen"], Z["z_aussen"]; Wp = lambda tc, x, zv: (u * (tc + x) + n * of + np.array([0, 0, zv])).tolist()
        for gi, tc in enumerate(Z["tcs"]):
            for k, x in enumerate(px): E.append(dict(id="g%d_pfosten%d" % (gi, k), A=Wp(tc, x, zs), B=Wp(tc, x, zau if k in (0, nl) else zin), gruppe="pfosten", vorzeichen=1.0))
            for k in range(nl): E.append(dict(id="g%d_kaempfer%d" % (gi, k), A=Wp(tc, px[k], Z["kaempfer"][k]), B=Wp(tc, px[k + 1], Z["kaempfer"][k]), gruppe="kaempfer"))
            E.append(dict(id="g%d_sohle" % gi, A=Wp(tc, px[0], zs), B=Wp(tc, px[-1], zs), gruppe="sohle"))
            if nl >= 2:
                E.append(dict(id="g%d_kopf_mitte" % gi, A=Wp(tc, px[1], zin), B=Wp(tc, px[-2], zin), gruppe="kopf_mitte")); E.append(dict(id="g%d_kopf_schraeg_l" % gi, A=Wp(tc, px[0], zau), B=Wp(tc, px[1], zin), gruppe="kopf_schraeg")); E.append(dict(id="g%d_kopf_schraeg_r" % gi, A=Wp(tc, px[-1], zau), B=Wp(tc, px[-2], zin), gruppe="kopf_schraeg"))
        return dict(rahmen=dict(n=n.tolist(), u=u.tolist(), off_front=of), kanten=E)
    if fam == "konsole":
        u, n, of = np.array(Z["u"]), np.array(Z["n"]), Z["of"]; tvor = of + Z["tiefe"]; Wp = lambda a_, zv: (u * a_ + n * tvor + np.array([0, 0, zv])).tolist(); bo, bu = Z["breite_oben"] / 2, Z["breite_unten"] / 2
        for i, a_ in enumerate(Z["along"]):
            E += [dict(id="k%d_links" % i, A=Wp(a_ - bu, Z["z0"]), B=Wp(a_ - bo, Z["z1"]), gruppe="kons_flanke_l"), dict(id="k%d_rechts" % i, A=Wp(a_ + bu, Z["z0"]), B=Wp(a_ + bo, Z["z1"]), gruppe="kons_flanke_r"),
                  dict(id="k%d_unten" % i, A=Wp(a_ - bu, Z["z0"]), B=Wp(a_ + bu, Z["z0"]), gruppe="kons_unten"), dict(id="k%d_oben" % i, A=Wp(a_ - bo, Z["z1"]), B=Wp(a_ + bo, Z["z1"]), gruppe="kons_oben")]
        return dict(rahmen=dict(n=n.tolist(), u=u.tolist(), off_front=of), kanten=E)
    if fam == "rotation":
        u = np.array(Z["u"]); r = Z["r"]; nn = np.array([-u[1], u[0], 0.0])
        for i, a_ in enumerate(Z["achsen"]):
            for sg, nm in ((-1, "links"), (1, "rechts")): E.append(dict(id="b%d_%s" % (i, nm), A=(np.r_[np.array(a_[:2]) + u[:2] * sg * r, Z["zlo"]]).tolist(), B=(np.r_[np.array(a_[:2]) + u[:2] * sg * r, Z["zhi"]]).tolist(), gruppe="silhouette_" + nm))
        return dict(rahmen=dict(n=nn.tolist(), u=u.tolist()), kanten=E)
    raise SystemExit(fam)


def main_pruefen():
    """muster_fit.py --pruefen INSTANZEN.json --familie fenster|konsole|rotation ...: Beleg-Tor ueber die Parameter der Familie (alte Parameter-Sicht, getrennt Wolke/Fotos).
    muster_fit.py --kanten_aus INSTANZEN.json --familie F --out KANTEN.json: Kanten + Kopplungsgruppen fuer tools/kanten_tor.py (neutrales Tor)."""
    fam = g("--familie", "", str); I = json.load(open(g("--pruefen", g("--kanten_aus", "", str), str))); Z = Z_aus_instanzen(fam, I)
    if "--kanten_aus" in a:
        K = kanten_aus_Z(fam, Z); json.dump(K, open(g("--out", "", str), "w")); log("Kanten:", len(K["kanten"]), "Gruppen:", sorted({k_["gruppe"] for k_ in K["kanten"]}), "->", g("--out", "", str)); return
    WK = lade_wolke(g("--wolke", "", str)); fotos = Fotos(g("--kam", "", str), g("--stabil", "", str), g("--bilder", "", str))
    par, zen = {"fenster": tor_params_fenster, "konsole": tor_params_konsole, "rotation": tor_params_rotation}[fam](Z)
    cloud = wolke_kasten(WK, [x for x in g("--sweep", "", str).split(",") if x], zen, 3.0); log("Pruefkasten: %d Wolken-/Sweeppunkte, %d Instanzen, %d Parameter" % (len(cloud), len(zen), len(par)))
    res = tor_laufen(fotos, cloud, WK, par, zen); tor_bericht(res)
    korr = {o["name"]: o["urteil"]["wert"] for o in res if o["urteil"]["status"] == "KORRIGIERT"}
    json.dump(dict(familie=fam, eingabe=g("--pruefen", "", str), parameter=[{k_: v for k_, v in o.items()} for o in res], korrigierte_werte_offset=korr, quelle="beleg_tor", gruen=all(o["urteil"]["status"] in ("GRUEN", "BESTAETIGT") for o in res)), open(g("--out", "", str), "w"), indent=1, default=float)
    log("Tor gesamt:", ", ".join("%s=%s" % (o["name"], o["urteil"]["status"]) for o in res))


def main_gaube():
    G = gitter_laden(g("--gitter", "", str)); W = lade_wolke(g("--wolke", "", str)); fotos = Fotos(g("--kam", "", str), g("--stabil", "", str), g("--bilder", "", str))
    R = json.load(open(g("--rahmen", "", str))) if "--rahmen" in a else None; rah = (np.array(R["u"]), np.array(R["n"]), float(R["off_front"])) if R else rahmen_auto(G)
    res, U = fam_gaube(G, W, fotos, rah, g("--out", "", str)); json.dump(res, open(g("--out", "", str), "w"), indent=1, default=float); log("geschrieben:", g("--out", "", str))
    if "--audit" in a and U:
        os.makedirs(g("--audit", "", str), exist_ok=True)
        for foto in g("--fotos", "ip_IMG_6120,ip_IMG_6261", str).split(","):
            gut = [pl for q, qi in zip(U, res["instanzen"]) if qi["bestanden"] for pl in q]; schl = [pl for q, qi in zip(U, res["instanzen"]) if not qi["bestanden"] for pl in q]
            try: overlay(fotos, gut, schl, foto, os.path.join(g("--audit", "", str), "muster_gaube_%s_entwurf.jpg" % foto), crop_um=np.vstack([pl for q in U for pl in q])[::3])
            except AssertionError as e: log("Foto fehlt", e)


# ----------------------------------------------------------------------------------------------- Beweistests (--synth)
def synth_fenster(seed=5):
    """Synthetisches Gitter: Fassade um 20 Grad gedreht, 5 Gruppen (Periode 3,97 m) a 3 Lichter (0,885 m), Pfosten, Kaempfer (Seite 1,40 / Mitte 1,95 ueber Sohle 0,0), Giebelkopf, + Traufe/Clutter.
    Pruefung: Rahmen, Zone, Periode, Phase, Lichter, Pfostenlage, Hoehen. Fehler < 5 cm."""
    import tempfile
    rng = np.random.default_rng(seed); ang = math.radians(20); u = np.array([math.cos(ang), math.sin(ang), 0.0]); n = np.array([-u[1], u[0], 0.0]); of = -7.3; per = 3.97; wl = 0.885; px = [(k - 1.5) * wl for k in range(4)]; S = []
    W_ = lambda x, zv: (u * x + n * of + np.array([0, 0, zv])).tolist(); z0, zk_s, zk_m, zt_a, zt_i = 10.3, 11.70, 12.27, 12.59, 13.30; ph0 = 0.47
    for gi in range(5):
        tc = ph0 + (gi - 2) * per + 20 * 0
        for k, x in enumerate(px): S.append([W_(tc + x, z0 + rng.normal(0, .01)), W_(tc + x, (zt_a if k in (0, 3) else zt_i) + rng.normal(0, .01)), 0, 1.0])
        for k in range(3): zk = zk_m if k == 1 else zk_s; S.append([W_(tc + px[k], zk), W_(tc + px[k + 1], zk), 0, 1.0])
        S.append([W_(tc + px[0], zt_a), W_(tc + px[1], zt_i), 0, 1.0]); S.append([W_(tc + px[3], zt_a), W_(tc + px[2], zt_i), 0, 1.0]); S.append([W_(tc + px[1], zt_i), W_(tc + px[2], zt_i), 0, 1.0])
    for x in np.arange(-12, 12, 1.5): S.append([W_(x, 14.6), W_(x + 1.5, 14.6), 0, 1.0]); S.append([W_(x, 8.4), W_(x + 1.5, 8.4), 0, 1.0])               # Traufe / Balkon als lange Waagerechte
    for _ in range(150): x = rng.uniform(-12, 12); zz = rng.uniform(3, 9); S.append([W_(x, zz), W_(x + rng.normal(0, .2), zz + rng.uniform(.3, 1.2)), 0, 1.0])  # Clutter
    tmp = tempfile.mkdtemp(prefix="muster_synth_"); pf = tmp + "/g.json"; json.dump({"segmente": S}, open(pf, "w")); G = gitter_laden(pf)
    u2, n2, of2 = rahmen_auto(G); fe = []
    if abs(abs(u2 @ u) - 1) > 1e-3 or abs(abs(n2 @ [*n[:2], 0]) - 1) > 1e-3: fe.append("Rahmenwinkel")
    sg = 1 if u2 @ u > 0 else -1; of_err = abs(of2 - (of if sg > 0 else -of)); z = zone_fenster(G, (u2, n2, of2)); log("Synth Fenster: Rahmen u %s (wahr %s), off_front %.3f (wahr %.3f), Zone z %.2f..%.2f" % (np.round(u2[:2], 4).tolist(), np.round(u[:2], 4).tolist(), of2, of if sg > 0 else -of, z["zlo"], z["zhi"]))
    P = G["P"]; fr = np.abs(P @ n2 - of2) < 0.3; v = fr & (G["cl"] == 0) & (P[:, 2] > z["zlo"]) & (P[:, 2] < z["zhi"]); t = P[v] @ u2; w = G["w"][v]; pr = periode_grob(t, w, 0.5, 8.0); ph, _ = phase_symmetrie(t, w, pr["periode"])
    zelle, ph2 = zellen_lesen_fenster(G, (u2, n2, of2), z, pr["periode"], ph); e = {}
    e["periode"] = abs(pr["periode"] - per); tc_w = ((ph0 * sg) % per); e["phase"] = abs(((ph2 - tc_w + per / 2) % per) - per / 2); e["lichtbreite"] = abs(zelle["lichtbreite"] - wl); e["n_licht"] = abs(zelle["n_licht"] - 3)
    e["pfosten"] = float(np.max(np.abs(np.sort(np.abs(zelle["pfosten_x"])) - np.sort(np.abs(px))))) if len(zelle["pfosten_x"]) == 4 else 9; e["z_sohl"] = abs(zelle["z_sohl"] - z0); e["z_innen"] = abs(zelle["z_innen"] - zt_i); e["z_aussen"] = abs(zelle["z_aussen"] - zt_a)
    kaem = zelle["kaempfer_je_licht"]; e["kaempfer_mitte"] = abs((kaem[1] or 0) - zk_m); e["kaempfer_seite"] = max(abs((kaem[0] or 0) - zk_s), abs((kaem[2] or 0) - zk_s))
    for k_, v_ in e.items(): log("  Synth Fenster %-16s Fehler %.4f %s" % (k_, v_, "OK" if v_ < (0.05 if k_ != "n_licht" else 0.5) else "ZU GROSS"))
    ok = all(v_ < 0.05 for k_, v_ in e.items() if k_ != "n_licht") and e["n_licht"] < 0.5 and not fe; log("SYNTH fenster:", "BESTANDEN" if ok else "FEHLGESCHLAGEN", fe); return 0 if ok else 1


def synth_gaube(seed=7):
    """Synthetisches Dach (Neigung 50 Grad, Ziegelrauschen 4 cm) mit 5 gleichen Schleppgauben (w 1,6, h1 0,70, m 0,45, Front 0,8 m vor der Mitte) auf zwei Reihen; Zone/Faltung/Formfit; Fehler w/h1/m < 5 cm (m: 0,05) und Familie = schlepp."""
    rng = np.random.default_rng(seed); a, b = 30.0, -1.19; u = np.array([1.0, 0, 0]); n = np.array([0, -1.0, 0]); w, d1, h1, m = 1.6, 0.8, 0.70, 0.45; pos = [(-9.0, 10.3), (-6.0, 8.2), (-3.0, 10.3), (0.0, 8.2), (3.0, 10.3)]; pts = []
    x = rng.uniform(-12, 7, 400000); o = rng.uniform(4, 12, 400000); keep = np.ones(len(x), bool)
    for t0, o0 in pos: keep &= ~((np.abs(x - t0) < w / 2 + 0.02) & (o - o0 > d1 - 2.2) & (o - o0 < d1 + 0.02))            # unter der Gaube gibt es keine Dachpunkte (Photogrammetrie sieht nur die Oberflaeche)
    pts.append(np.c_[x[keep], o[keep], a + b * o[keep] + rng.normal(0, 0.04, keep.sum())])          # Dach (y = off in dieser Synth: off = -P@n = y)
    nz = 1 / math.hypot(1, b)
    for t0, o0 in pos:
        xs = rng.uniform(-w / 2, w / 2, 20000); dd = rng.uniform(d1 - 2.2, d1, 20000); hh = h1 - m * (d1 - dd); k = hh > 0.02; xs, dd, hh = xs[k], dd[k], hh[k]
        pts.append(np.c_[t0 + xs, o0 + dd, a + b * (o0 + dd) + hh / nz + rng.normal(0, 0.02, len(xs))])                                         # Dachflaeche der Gaube
        for sx in (-w / 2, w / 2):
            q = rng.uniform(0, 1, 8000); dd = rng.uniform(d1 - 2.2, d1, 8000); hh = (h1 - m * (d1 - dd)); k = hh > 0.02; pts.append(np.c_[t0 + sx + 0 * dd[k], o0 + dd[k], a + b * (o0 + dd[k]) + q[k] * hh[k] / nz])       # Wangen
        q = rng.uniform(0, 1, 6000); xs = rng.uniform(-w / 2, w / 2, 6000); pts.append(np.c_[t0 + xs, o0 + d1 + 0 * q, a + b * (o0 + d1) + q * h1 / nz])                                # Front
    W = np.vstack(pts).astype(np.float64); bl = gaube_blobs(W, u, n, a, b, 3.5, 12.5, 15.0 - 100, y_min=0.3, amin=0.8)
    a_, b_, inl = dachebene_fit(W, u, n, 4, 12, -100); log("Synth Gaube: Dachebene a %.3f (wahr %.3f) b %.4f (wahr %.4f); Blobs %d (wahr 5)" % (a_, a, b_, b, len(bl)))
    if len(bl) != 5: log("SYNTH gaube: FEHLGESCHLAGEN (Blobs)"); return 1
    Hs = gaube_hoehenkarten(W, u, n, a_, b_, [(x_["t_mitte"], x_["off_mitte"]) for x_ in bl]); sh = gaube_ausrichten(Hs); r = 0.05; St = np.stack([np.roll(H, shift=(int(round(s_[1] / r)), int(round(s_[0] / r))), axis=(0, 1)) for H, s_ in zip(Hs, sh)])
    occ = (St > 0.3).mean(0); Hm = np.nan_to_num(np.where(occ >= 0.5, np.nanmedian(np.where(St > 0.3, St, np.nan), axis=0), 0.0), nan=0.0); fits = gaube_fit_familien(Hm, 2.0, -2.5, r)
    for k_, v_ in fits.items(): log("  Synth Gaube Familie %s: RMS %.3f par %s" % (k_, v_["rms"], np.round(v_["par"], 3).tolist()))
    fam = min(fits, key=lambda k_: fits[k_]["rms"]); p = fits["schlepp"]["par"]; e = dict(w=abs(p[0] - w), h1=abs(p[2] - h1), m=abs(p[3] - m)); log("  Synth Gaube Fehler (schlepp): %s; gewaehlte Familie %s" % ({k_: round(v_, 3) for k_, v_ in e.items()}, fam))
    ok = e["w"] < 0.05 and e["h1"] < 0.05 and e["m"] < 0.05 and fam == "schlepp"; log("SYNTH gaube:", "BESTANDEN" if ok else "FEHLGESCHLAGEN"); return 0 if ok else 1


if __name__ == "__main__" and "--synth" in a:
    which = g("--synth", "fenster", str); rc = 0
    if which in ("fenster", "alle"): rc |= synth_fenster()
    if which in ("gaube", "alle"): rc |= synth_gaube()
    if which in ("tor", "alle"):
        import kanten_tor; rc |= kanten_tor.synth_tor()
    if which in ("pfeiler", "konsole", "rotation"): log("SYNTH %s: nur Kantenlieferant (kanten_aus_Z) angelegt, Beweistest ueber kanten_tor.py --synth (Wiederholungs-Kanten, Mittel-Hoehe/Phase); eigener Zellenfit NICHT gebaut" % which)
    sys.exit(rc)
if __name__ == "__main__" and "--synth" not in a and "--familie" in a:
    fam = g("--familie", "", str)
    if "--pruefen" in a or "--kanten_aus" in a: main_pruefen()
    elif fam == "fenster": main_fenster()
    elif fam == "gaube": main_gaube()
