#!/usr/bin/env python3
"""bruecke_messen.py - Kettenstufe BRUECKE (ueberdachter Gang): Masse aus FOTOKANTEN + SfM-Kameras (Linien-Sweep), 27.11.2026, SPEC_SCHWABENTOR_DEMONSTRATOR Anf. 4,
Plan RECHERCHE_BRUECKE_UND_PUTZ_2026-11-27.md Teil A (B1 Zone -> B2 Kanten-Sweep -> B3 Massliste -> B4 bauteile.ueberdachter_gang).

Warum ein eigener Sweep: die Bruecke besteht aus langen GERADEN parallel zu einer Achse (Traufen, First, Deckkanten, Holm) und senkrechten Pfosten/Stuetzen.
Statt freier Kantenpunkte (kanten_tiefe_sweep_flaeche, Rauschen bei Holzlattung) wird je HYPOTHESE einer 3D-Geraden (Querschnittslage q, z bzw. Laengslage s)
in jedes Foto projiziert und gezaehlt, wie viele Fotos dort eine Kante mit passender Richtung haben (Mehrfoto-Konsens wie Stabilitaetskarten).
Die Zone (Huellquader aus Wolke/DOM1) ist nur SUCHRAUM, nie Form: Tauschtest +-30 % muss dieselben Masse liefern (tests/test_bruecke_messen.py).

Stufen (alle generisch, keine Objektwerte im Code):
  kameras_waehlen   Kameras mit Sicht auf die Zone (Projektion + Verdeckung durch die dichte Wolke, nur Sichtpruefung)
  achse_feinen      Gier/Neigung der Achse aus der Schaerfe der Laengskanten (Foto), Start = Zone
  quer_sweep        Karte S(q, z): Konsens der Fotos fuer waagrechte Laengsgeraden -> Traufen, First, Deck, Holm, Riegel
  senk_sweep        Profil S(s) je Seitenebene: senkrechte Kanten -> Pfosten (Kantenpaare), ZAEHLEN je Foto (>= 3 Fotos einig)
  enden_messen      Laengsprofil der Deck-Unterkante -> Enden a/b (Spannweite)
  treppe_zaehlen    Stufenzahl aus Stufenkanten-Hoehen per Regression ueber die Stufennummer (nie Autokorrelation allein: Oberwelle)
  saegezahn_oder_treppe  Profilform trennen (Falle Staffelgiebel 11.11.)
  massliste         Parameter-JSON fuer bauteile.ueberdachter_gang, JE WERT quelle/fotos/streuung; fehlt ein Mass -> 'fehlt' + Grund (kein Ersatzwert)

Aufruf:
  tools/py tools/bruecke_messen.py kameras KAM.json LAGE.json WOLKE.ply BILDDIR AUS.json [--max 40]
  tools/py tools/bruecke_messen.py messen  KAMWAHL.json LAGE.json BILDDIR AUSDIR [--zone_skala 1.0]
rc: 0 = Massliste geschrieben (einzelne Masse duerfen 'fehlt' sein -> Bestand-Tor ROT im Bau), 2 = Zone ohne Kanten ('Bruecke nicht belegt').
"""
import sys, os, json, math, time
import numpy as np
import cv2

# ---------------------------------------------------------------- Kameras / Projektion (SIMPLE_RADIAL wie sfm_kameras_export.py)

def projizieren(c, X):
    """Weltpunkte (N,3) -> Pixel (N,2), Tiefe (N,). c: dict Rn, tn, f, cx, cy, params (k1 an Stelle 3 bei SIMPLE_RADIAL)."""
    R = np.asarray(c["Rn"], float); t = np.asarray(c["tn"], float); Xc = X @ R.T + t; z = Xc[:, 2]
    zz = np.maximum(z, 1e-3); x = Xc[:, 0] / zz; y = Xc[:, 1] / zz
    k1 = c["params"][3] if c.get("modell", "SIMPLE_RADIAL") in ("SIMPLE_RADIAL", "RADIAL") and len(c["params"]) > 3 else 0.0
    r2 = x * x + y * y; d = 1 + k1 * r2
    return np.stack([c["f"] * x * d + c["cx"], c["f"] * y * d + c["cy"]], 1), z


class Rahmen:
    """Lokaler Brueckenrahmen: s laengs (Achse), q quer (links der Achse), z absolut. mitte = (x, y), achse = Einheitsvektor (x, y), neigung in Grad (dz/ds)."""
    def __init__(self, mitte, achse, neigung_grad=0.0, z0=0.0):
        self.m = np.asarray(mitte, float)[:2]; a = np.asarray(achse, float)[:2]; self.d = a / np.linalg.norm(a)
        self.n = np.array([-self.d[1], self.d[0]]); self.tg = math.tan(math.radians(neigung_grad)); self.z0 = z0

    def welt(self, s, q, z):
        s, q, z = np.broadcast_arrays(np.asarray(s, float), np.asarray(q, float), np.asarray(z, float))
        xy = self.m + s[..., None] * self.d + q[..., None] * self.n
        return np.concatenate([xy, (z + s * self.tg)[..., None]], -1)

    def lokal(self, X):
        X = np.asarray(X, float); r = X[:, :2] - self.m; s = r @ self.d; q = r @ self.n
        return np.stack([s, q, X[:, 2] - s * self.tg], 1)

    def gedreht(self, gier_grad=0.0, neigung_grad=None, dq=0.0):
        c, s_ = math.cos(math.radians(gier_grad)), math.sin(math.radians(gier_grad)); d = np.array([c * self.d[0] - s_ * self.d[1], s_ * self.d[0] + c * self.d[1]])
        return Rahmen(self.m + dq * self.n, d, math.degrees(math.atan(self.tg)) if neigung_grad is None else neigung_grad)


def zone_aus_lage(L, skala=1.0, skala_hoehe=None):
    """Zone (Suchraum) aus BRUECKE-LAGE.json 'steg'. skala/skala_hoehe vergroessern/verkleinern sie (Tauschtest). Liefert dict mit Rahmen + Grenzen."""
    S = L["steg"]; sh = skala if skala_hoehe is None else skala_hoehe
    R = Rahmen(S["mitte_modell_xy"], S["achse_modell_xy"], float(np.median(list(S.get("neigung_grad", {"x": 0.0}).values()))))
    lang = float(S["laenge_dach_m"]) * skala; breit = float(S.get("breite_dach_m", 4.0)) * skala
    zt = float(S["dach_first_z_m"]); zu = float(S.get("deck_unterkante_z_m", zt - 6.0)); zm = 0.5 * (zt + zu); hh = 0.5 * (zt - zu) * sh
    return dict(rahmen=R, s0=-lang / 2, s1=lang / 2, qmax=breit / 2 + 1.0 * skala, z0=zm - hh - 1.0 * sh, z1=zm + hh + 1.0 * sh)


# ---------------------------------------------------------------- Kantenbilder

def kantenbild(grau, art="lsd", min_len=25, dicke=3, sigma=1.2, lo=40, hi=110):
    """Grauwertbild -> (Kantenmaske 0/1, Gradientenrichtung in rad je Pixel).
    art 'lsd' (Standard): nur GERADE Bildkanten (OpenCV-LSD, Segmente >= min_len px, mit 'dicke' px Toleranz gezeichnet; Richtung = Segmentnormale) -
    Laub, Pflaster, Autos geben kaum lange Geraden (27.11.: Canny-Pixel liessen Baumkronen und Lattung im Sweep als Streifen stehen).
    art 'canny': Canny + Sobel (alle Kantenpixel)."""
    if art == "lsd":
        lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD); seg = lsd.detect(cv2.GaussianBlur(grau, (0, 0), 0.8))[0]
        k = np.zeros(grau.shape, np.uint8); th = np.zeros(grau.shape, np.float32)
        if seg is not None:
            seg = seg.reshape(-1, 4); L = np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1]); seg = seg[L >= min_len]
            o = np.argsort(np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1]))          # lange Segmente zuletzt (gewinnen die Richtung)
            for x1, y1, x2, y2 in seg[o]:
                a = math.atan2(y2 - y1, x2 - x1) + math.pi / 2; p1 = (int(round(x1)), int(round(y1))); p2 = (int(round(x2)), int(round(y2)))
                cv2.line(k, p1, p2, 1, dicke); cv2.line(th, p1, p2, float(a), dicke)
        return k, th
    g = cv2.GaussianBlur(grau, (0, 0), sigma); e = cv2.Canny(g, lo, hi)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3); th = np.arctan2(gy, gx)
    k = cv2.dilate((e > 0).astype(np.uint8), np.ones((3, 3), np.uint8))
    thd = th.copy(); m = e > 0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sh = np.roll(np.roll(th, dy, 0), dx, 1); mm = np.roll(np.roll(m, dy, 0), dx, 1) & ~m; thd[mm] = sh[mm]
    return k, thd


def linien_treffer(kb, uv, richtung_px, wtol_grad=20.0):
    """Je Abtastpunkt (N, M, 2) einer projizierten Geraden: 1, wenn dort eine Kante liegt, deren Gradient senkrecht zur Geraden steht (+-wtol). Liefert (N, M) bool + gueltig."""
    k, th = kb; H, W = k.shape; u = np.round(uv[..., 0]).astype(int); v = np.round(uv[..., 1]).astype(int)
    ok = (u >= 0) & (u < W) & (v >= 0) & (v < H); uc = np.clip(u, 0, W - 1); vc = np.clip(v, 0, H - 1)
    hit = k[vc, uc].astype(bool) & ok
    nrm = np.arctan2(richtung_px[..., 0], -richtung_px[..., 1])             # Normale zur Bildrichtung der Geraden
    dw = np.abs(((th[vc, uc] - nrm[..., None] if nrm.ndim == uv.ndim - 2 else th[vc, uc] - nrm) + np.pi / 2) % np.pi - np.pi / 2)
    return hit & (dw < math.radians(wtol_grad)), ok


def geraden_stuetze(kams, kbs, A, B, M=48, wtol=20.0, min_px=30.0, verdeckt=None, roh=False):
    """Mehrfoto-Stuetze fuer N 3D-Strecken A->B (N,3): je Foto Trefferanteil minus Grundrauschen des Fotos; Ergebnis (N,) = Mittel ueber Fotos, in denen die Strecke
    sichtbar ist (beide Enden vor der Kamera, >= 80 % im Bild, Bildlaenge >= min_px), plus (N, J) Einzelwerte (nan = nicht sichtbar)."""
    N = len(A); t = (np.arange(M) + 0.5) / M; P = A[:, None, :] + (B - A)[:, None, :] * t[None, :, None]
    E = np.full((N, len(kams)), np.nan)
    for j, (c, kb) in enumerate(zip(kams, kbs)):
        uv, z = projizieren(c, P.reshape(-1, 3)); uv = uv.reshape(N, M, 2); z = z.reshape(N, M)
        dpx = uv[:, -1] - uv[:, 0]; lpx = np.linalg.norm(dpx, axis=1); rich = dpx / np.maximum(lpx, 1e-9)[:, None]
        hit, ok = linien_treffer(kb, uv, rich[:, None, :].repeat(M, 1), wtol)
        if verdeckt is not None: ok = ok & ~verdeckt[j](uv, z)
        sicht = (z.min(1) > 0.5) & (ok.mean(1) >= 0.8) & (lpx >= min_px)
        f = hit.sum(1) / np.maximum(ok.sum(1), 1)
        E[sicht, j] = f[sicht]
    # Grundrauschen je Foto: Median ueber alle Hypothesen (die meisten Hypothesen liegen NICHT auf einer Kante)
    if not roh: bg = np.nanmedian(E, 0); E = E - bg[None, :]
    S = np.nanmean(np.where(np.isnan(E), np.nan, E), 1) if np.isfinite(E).any() else np.zeros(N)
    S = np.where(np.isfinite(S), S, 0.0)
    return S, E


# ---------------------------------------------------------------- Sweeps

def quer_sweep(kams, kbs, R, s0, s1, qs, zs, fenster=4.0, M=24, min_px=120.0, schwelle=0.3, threads=16):
    """Querkarte fuer waagrechte Laengsgeraden: Zone in Fenster der Laenge 'fenster' geteilt (kurze Stuecke: Achsfehler/Durchhang verschmieren nicht),
    je Fenster und Foto Trefferanteil; ein Foto STIMMT fuer (q, z), wenn Trefferanteil - Grundrauschen > schwelle. Nur Fotos, in denen das Stueck >= min_px lang
    erscheint (Blick laengs der Achse = mehrdeutig, faellt so heraus). Ergebnis: K[f, z, q] = Anteil zustimmender Fotos je Fenster f (nan = kein Foto),
    S[z, q] = Mittel ueber Fenster, mitten = Fenstermitten s."""
    from concurrent.futures import ThreadPoolExecutor
    nf = max(1, int(round((s1 - s0) / fenster))); kanten = np.linspace(s0, s1, nf + 1); Q, Z = np.meshgrid(qs, zs)
    def eins(f):
        A = R.welt(np.full(Q.size, kanten[f]), Q.ravel(), Z.ravel()); B = R.welt(np.full(Q.size, kanten[f + 1]), Q.ravel(), Z.ravel())
        _, E = geraden_stuetze(kams, kbs, A, B, M=M, min_px=min_px)
        n = np.isfinite(E).sum(1); v = np.where(np.isfinite(E), E > schwelle, False).sum(1)
        return np.where(n >= 3, v / np.maximum(n, 1), np.nan).reshape(Z.shape)
    with ThreadPoolExecutor(threads) as ex: Kf = np.array(list(ex.map(eins, range(nf))))
    S = np.nanmean(Kf, 0) if np.isfinite(Kf).any() else np.zeros(Z.shape)
    return np.nan_to_num(S), Kf, 0.5 * (kanten[1:] + kanten[:-1])


def senk_sweep(kams, kbs, R, ss, qs, z_mitte, laenge=1.2, M=16, min_px=40.0, schwelle=0.3, threads=16, block=20000):
    """Karte V[q, s] fuer SENKRECHTE Strecken (Pfosten, Stuetzen) der Laenge 'laenge' um z_mitte: Anteil zustimmender Fotos (wie quer_sweep).
    Senkrechte Kanten werden im Grundriss trianguliert - die Fotos von beiden Strassenseiten und laengs schneiden sich hier unter grossem Winkel."""
    from concurrent.futures import ThreadPoolExecutor
    Sg, Qg = np.meshgrid(ss, qs); A = R.welt(Sg.ravel(), Qg.ravel(), np.full(Sg.size, z_mitte - laenge / 2)); B = A.copy(); B[:, 2] += laenge
    teile = [slice(i, min(i + block, len(A))) for i in range(0, len(A), block)]
    def eins(sl):
        _, E = geraden_stuetze(kams, kbs, A[sl], B[sl], M=M, min_px=min_px)
        n = np.isfinite(E).sum(1); v = np.where(np.isfinite(E), E > schwelle, False).sum(1)
        return np.where(n >= 3, v / np.maximum(n, 1), 0.0)
    with ThreadPoolExecutor(threads) as ex: V = np.concatenate(list(ex.map(eins, teile)))
    return V.reshape(Sg.shape)


def hoehen_profil(kams, kbs, R, s0, s1, q, zs, fenster=4.0, M=24, min_px=120.0, schwelle=0.3):
    """1D-Profil P[z] fuer waagrechte Laengsgeraden in der senkrechten Ebene q (Seitenwand, Firstachse): Anteil zustimmender Fotos, gemittelt ueber Fenster.
    BEIDSEITIG (27.11., Synthetik): eine Gerade, die wirklich in der Ebene q liegt, sehen Fotos von BEIDEN Seiten (q_kamera < q und > q) auf derselben Hoehe;
    eine Gerade aus einer anderen Ebene erscheint wegen der fast waagrechten Strahlen nur von einer Seite auf dieser Hoehe (Geisterkante).
    P = Minimum der beiden Seiten; fehlt eine Seite ganz -> P aus der einen Seite und einseitig=True."""
    zs = np.asarray(zs, float); seite = np.array([R.lokal(np.asarray(c["C"], float)[None])[0, 1] - q for c in kams])
    teile = []
    for m in (seite < 0, seite > 0):
        if m.sum() >= 2:
            S, Kf, mit = quer_sweep([k for k, x in zip(kams, m) if x], [k for k, x in zip(kbs, m) if x], R, s0, s1, np.array([float(q)]), zs, fenster=fenster, M=M, min_px=min_px, schwelle=schwelle)
            teile.append((S[:, 0], Kf[:, :, 0], mit))
    if not teile: return np.zeros(len(zs)), np.full((1, len(zs)), np.nan), np.array([0.5 * (s0 + s1)])
    if len(teile) == 1: return teile[0]
    (P1, K1, mit), (P2, K2, _) = teile
    return np.minimum(P1, P2), np.fmin(K1, K2), mit


def spitzen_2d(S, abst=3, schwelle=None, maxn=20):
    """Lokale Maxima einer Karte (Pixelabstand >= abst), absteigend; schwelle Vorgabe = Median + 4 x MAD (robust)."""
    if schwelle is None:
        med = np.median(S); mad = np.median(np.abs(S - med)) + 1e-9; schwelle = med + 6 * 1.4826 * mad
    d = cv2.dilate(S.astype(np.float32), np.ones((2 * abst + 1, 2 * abst + 1), np.uint8))
    yy, xx = np.where((S >= d - 1e-12) & (S > schwelle)); o = np.argsort(-S[yy, xx])
    return [(int(yy[i]), int(xx[i]), float(S[yy[i], xx[i]])) for i in o[:maxn]]


def spitzen_1d(p, abst=2, schwelle=None):
    p = np.asarray(p, float)
    if schwelle is None:
        med = np.median(p); mad = np.median(np.abs(p - med)) + 1e-9; schwelle = med + 4 * 1.4826 * mad
    out = []
    for i in range(len(p)):
        lo, hi = max(0, i - abst), min(len(p), i + abst + 1)
        if p[i] > schwelle and p[i] >= p[lo:hi].max() - 1e-12 and (not out or i - out[-1] > abst): out.append(i)
    return out


def subpixel(p, i):
    """Parabel-Feinlage eines Maximums im Profil."""
    if 0 < i < len(p) - 1:
        a, b, c = p[i - 1], p[i], p[i + 1]; dn = a - 2 * b + c
        if dn < 0: return i + 0.5 * (a - c) / dn
    return float(i)


# ---------------------------------------------------------------- Deutung des Querschnitts

def querschnitt_deuten(S, qs, zs, abst=3):
    """Spitzen der Querkarte -> Kanten-Paare (symmetrisch um eine gemeinsame Mitte qc) + Firstkante. Keine Objektzahlen: Paarung nach gleicher Hoehe
    (|dz| <= 2 Rasterschritte) und gemeinsamer Mitte (Median der Paar-Mitten). Liefert dict mit paare [(z, q_links, q_rechts, stuetze)], first, mitte."""
    dq = qs[1] - qs[0]; dz = zs[1] - zs[0]; P = spitzen_2d(S, abst=abst, maxn=40)
    pk = [(zs[0] + subpixel(S[:, x], y) * dz, qs[0] + subpixel(S[y, :], x) * dq, v) for y, x, v in P]
    paare = []
    for i in range(len(pk)):
        for j in range(i + 1, len(pk)):
            (za, qa, va), (zb, qb, vb) = pk[i], pk[j]
            if abs(za - zb) <= 2.5 * dz and abs(qa - qb) > 1.0: paare.append(((za + zb) / 2, min(qa, qb), max(qa, qb), min(va, vb)))
    if not paare: return dict(paare=[], first=None, mitte=None, spitzen=pk)
    mitten = np.array([(a + b) / 2 for _, a, b, _ in paare]); w = np.array([v for *_, v in paare])
    qc = float(np.median(mitten[np.argsort(-w)[:max(3, len(w) // 2)]]))
    paare = [p for p in paare if abs((p[1] + p[2]) / 2 - qc) <= 3 * dq]
    # je Hoehe nur das staerkste Paar (Doppelkanten der Lattung)
    paare.sort(key=lambda p: -p[3]); keep = []
    for p in paare:
        if all(abs(p[0] - k[0]) > 2.5 * dz or abs((p[2] - p[1]) - (k[2] - k[1])) > 0.3 for k in keep): keep.append(p)
    keep.sort(key=lambda p: p[0])
    first = None
    zmax = max(p[0] for p in keep) if keep else -1e9
    for z, q, v in pk:
        if abs(q - qc) <= 3 * dq and z > zmax + 2 * dz and (first is None or v > first[2]): first = (z, q, v)
    return dict(paare=keep, first=first, mitte=qc, spitzen=pk)


# ---------------------------------------------------------------- Treppe / Saegezahn (rein 1D, synthetisch pruefbar)

def leiter_fit(werte, a_min, a_max=None, tol=0.3, schritte=4000):
    """Regelmaessige Leiter x_k = x0 + k a in einer Liste gefundener Lagen (Pfosten laengs, Stufenkanten in der Hoehe) - mit Luecken, Doppel- und Fehlfunden.
    GENERISCH, 27.11.2026. Nie Autokorrelation allein (Falle 03.11.: springt auf die Oberwelle): je Kandidat a (logarithmisches Raster a_min..a_max)
    Guete = Anteil Funde mit |Rest| < tol a  x  Anteil BELEGTER Sprossen zwischen erster und letzter. a/2 belegt nur jede zweite Sprosse (Guete halbiert),
    2a erklaert nur die Haelfte der Funde (Guete halbiert). Danach Gerade x = x0 + k a per kleinsten Quadraten auf den Treffern.
    Liefert dict(n_sprossen, a, x0, rest, nummern, guete, treffer) oder dict(n_sprossen=None, grund)."""
    x = np.sort(np.asarray(werte, float))
    if len(x) < 3: return dict(n_sprossen=None, grund=f"nur {len(x)} Funde (< 3)")
    a_max = a_max if a_max is not None else (x[-1] - x[0]) / 2
    if not a_max > a_min > 0: return dict(n_sprossen=None, grund=f"Suchbereich ungueltig a {a_min}..{a_max}")
    best = None
    for a in np.exp(np.linspace(np.log(a_min), np.log(a_max), schritte)):
        ph = np.angle(np.mean(np.exp(2j * np.pi * x / a))) / (2 * np.pi) * a
        k = np.round((x - ph) / a); r = x - ph - k * a; tr = np.abs(r) < tol * a
        if tr.sum() < 3: continue
        belegt = len(np.unique(k[tr])) / (k[tr].max() - k[tr].min() + 1)
        g = tr.mean() * belegt
        if best is None or g > best[0] + 1e-9: best = (g, a, ph)
    if best is None: return dict(n_sprossen=None, grund="keine Leiter mit >= 3 Treffern")
    g, a, ph = best; k = np.round((x - ph) / a); tr = np.abs(x - ph - k * a) < tol * a
    A = np.stack([np.ones(tr.sum()), k[tr]], 1); (x0, a2), *_ = np.linalg.lstsq(A, x[tr], rcond=None)
    k = np.round((x - x0) / a2); tr = np.abs(x - x0 - k * a2) < tol * a2; r = x[tr] - x0 - k[tr] * a2
    kmin, kmax = int(k[tr].min()), int(k[tr].max())
    return dict(n_sprossen=kmax - kmin + 1, a=float(a2), x0=float(x0 + kmin * a2), rest=float(np.sqrt(np.mean(r ** 2))), guete=float(g),
                nummern=(k[tr] - kmin).astype(int).tolist(), treffer=x[tr].tolist(), belegt=int(len(np.unique(k[tr]))))


def treppe_zaehlen(hoehen, steigung_min=0.05, steigung_max=0.4, min_stufen=2):
    """Stufenzahl aus den Hoehen gefundener Stufen-VORDERKANTEN (inkl. Austrittskante oben). Steigungsbereich = Suchraum (DIN-uebliche Grenzen als Parameter,
    keine Objektwerte). Stufen = Sprossen - 1 (die Kante am Fuss ist der Boden, jede weitere eine Stufe). Liefert dict(stufen, steigung, z0, rest, guete)."""
    L = leiter_fit(hoehen, steigung_min, steigung_max)
    if L["n_sprossen"] is None: return dict(stufen=None, grund=L["grund"])
    if L["n_sprossen"] - 1 < min_stufen: return dict(stufen=None, grund=f"nur {L['n_sprossen'] - 1} Stufen")
    if L["rest"] > 0.25 * L["a"]: return dict(stufen=None, grund=f"Kanten passen auf keine Stufenleiter (Rest {L['rest']:.3f} bei {L['a']:.3f})")
    return dict(stufen=L["n_sprossen"] - 1, steigung=L["a"], z0=L["x0"], rest=L["rest"], guete=L["guete"], belegt=L["belegt"])


def saegezahn_oder_treppe(x, z, tol=None):
    """Profilform eines Laufs (x laengs, z Hoehe, fein abgetastet): 'treppe' = waagrechte Auftritte + senkrechte Setzstufen; 'saegezahn' = schraege Flanken
    (Rampe mit Kerben); 'rampe' = glatt. Kriterium: Anteil der Laenge mit |dz/dx| ~ 0 (Auftritte) und Anteil mit |dz/dx| sehr gross (Setzstufen)
    gegen Anteil schraeger Stuecke. Liefert (art, kennzahlen)."""
    x = np.asarray(x, float); z = np.asarray(z, float); o = np.argsort(x); x, z = x[o], z[o]
    dx = np.diff(x); dzv = np.diff(z); ok = dx > 1e-9; g = dzv[ok] / dx[ok]; L = dx[ok]
    gm = abs((z[-1] - z[0]) / max(x[-1] - x[0], 1e-9))
    flach = L[np.abs(g) < 0.15 * gm].sum(); schraeg = L[(np.abs(g) >= 0.15 * gm) & (np.abs(g) < 4 * gm)].sum(); steil = (np.abs(dzv[ok][np.abs(g) >= 4 * gm])).sum()
    hub = abs(z[-1] - z[0]) + 1e-9; Lg = L.sum()
    kz = dict(anteil_flach=float(flach / Lg), anteil_schraeg=float(schraeg / Lg), hub_steil=float(steil / hub), steigung_mittel=float(gm))
    # Sprungzahl: Vorzeichenwechsel der Abweichung von der Ausgleichsgeraden
    if kz["anteil_flach"] > 0.6 and kz["hub_steil"] > 0.6: return "treppe", kz
    if kz["anteil_schraeg"] > 0.5 and kz["hub_steil"] > 0.3: return "saegezahn", kz
    if kz["anteil_schraeg"] > 0.8: return "rampe", kz
    return "unklar", kz


# ---------------------------------------------------------------- Wolke nur fuer Sicht (Verdeckung), nie Form

def ply_lesen(pfad, nmax=3_000_000, seed=0):
    """xyz aus binaerem PLY (float x,y,z am Anfang, beliebige weitere Felder); zufaellig auf nmax ausgeduennt."""
    with open(pfad, "rb") as f:
        kopf = b""
        while not kopf.endswith(b"end_header\n"): kopf += f.readline()
        props = []; n = 0
        for z in kopf.decode().splitlines():
            p = z.split()
            if p[:2] == ["element", "vertex"]: n = int(p[2])
            elif p[:1] == ["property"]: props.append((p[2], {"float": "<f4", "double": "<f8", "uchar": "u1", "int": "<i4", "uint": "<u4"}[p[1]]))
        a = np.fromfile(f, dtype=np.dtype(props), count=n)
    X = np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64)
    if len(X) > nmax: X = X[np.random.default_rng(seed).choice(len(X), nmax, replace=False)]
    return X


def tiefenpuffer(c, X, teiler=8):
    """Kleinster Abstand je Rasterzelle (Bild / teiler) aus Wolkenpunkten -> Funktion verdeckt(uv, z, rand)."""
    W, H = c["W"] // teiler + 1, c["H"] // teiler + 1; uv, z = projizieren(c, X); ok = (z > 0.3) & (uv[:, 0] >= 0) & (uv[:, 0] < c["W"]) & (uv[:, 1] >= 0) & (uv[:, 1] < c["H"])
    b = np.full(H * W, np.inf); idx = (uv[ok, 1] // teiler).astype(int) * W + (uv[ok, 0] // teiler).astype(int); np.minimum.at(b, idx, z[ok])
    b = b.reshape(H, W); b = -cv2.dilate(-np.where(np.isfinite(b), b, 1e6).astype(np.float32), np.ones((1, 1), np.uint8)).astype(np.float64)
    # duenne Einzeltreffer (Blaetter, Leitungen) nicht als Wand: Zelle zaehlt erst, wenn mind. die Haelfte ihrer 3x3-Nachbarn ebenfalls nah ist
    med = cv2.medianBlur(np.minimum(b, 1e4).astype(np.float32), 3).astype(np.float64)
    def verdeckt(uvq, zq, rand=1.5):
        u = np.clip((uvq[..., 0] // teiler).astype(int), 0, W - 1); v = np.clip((uvq[..., 1] // teiler).astype(int), 0, H - 1)
        return med[v, u] < zq - rand
    return verdeckt


def ausser_zone(X, zone, rand=0.5):
    """Wolkenpunkte AUSSERHALB der Zone (die Bruecke verdeckt sich nicht selbst; Verdecker sind Baeume, Haeuser, Turm)."""
    l = zone["rahmen"].lokal(X); innen = (l[:, 0] > zone["s0"] - rand) & (l[:, 0] < zone["s1"] + rand) & (np.abs(l[:, 1]) < zone["qmax"] + rand) & (l[:, 2] > zone["z0"] - rand) & (l[:, 2] < zone["z1"] + rand)
    return X[~innen]


def kameras_waehlen(K, zone, X=None, nmax=40, min_sicht=0.6, dmax=80.0):
    """Kameras mit freier Sicht auf die Zone (Stichprobe von Zonenpunkten: im Bild, vor der Kamera, nicht durch die Wolke verdeckt).
    Rangfolge: Sichtanteil, dann Blickrichtungs-Vielfalt (gierig nach Winkel um die Achse). Liefert Liste (name, sichtanteil, azimut_quer, abstand)."""
    R = zone["rahmen"]; ss = np.linspace(zone["s0"], zone["s1"], 13); qq = np.linspace(-zone["qmax"] + 1, zone["qmax"] - 1, 3); zz = np.linspace(zone["z0"] + 1, zone["z1"] - 1, 4)
    S_, Q_, Z_ = np.meshgrid(ss, qq, zz); P = R.welt(S_.ravel(), Q_.ravel(), Z_.ravel())
    out = []
    for name, c in K.items():
        C = np.asarray(c["C"]); dist = float(np.linalg.norm(C[:2] - R.m))
        if dist > dmax: continue
        uv, z = projizieren(c, P); ok = (z > 0.5) & (uv[:, 0] >= 0) & (uv[:, 0] < c["W"]) & (uv[:, 1] >= 0) & (uv[:, 1] < c["H"])
        if ok.mean() < min_sicht: continue
        if X is not None:
            v = tiefenpuffer(c, X)(uv, z); ok = ok & ~v
        if ok.mean() < min_sicht: continue
        cl = R.lokal(C[None])[0]; out.append((name, float(ok.mean()), float(math.degrees(math.atan2(cl[2] - 7.0, cl[1]))), dist, float(cl[0]), float(cl[1])))
    out.sort(key=lambda r: -r[1])
    # Vielfalt: gierig - naechste Kamera maximiert den kleinsten Abstand (Querwinkel, Laengslage) zu den gewaehlten
    if len(out) > nmax:
        wahl = [out[0]]; rest = out[1:]
        while len(wahl) < nmax and rest:
            dmin = [min(abs(r[2] - w[2]) / 10.0 + abs(r[4] - w[4]) / 5.0 for w in wahl) * r[1] for r in rest]
            i = int(np.argmax(dmin)); wahl.append(rest.pop(i))
        out = wahl
    return out


def bild_laden(bilddir, name, c):
    im = cv2.imread(os.path.join(bilddir, name), cv2.IMREAD_GRAYSCALE)
    if im is None: raise FileNotFoundError(os.path.join(bilddir, name))
    if im.shape[1] != c["W"] or im.shape[0] != c["H"]: im = cv2.resize(im, (c["W"], c["H"]), interpolation=cv2.INTER_AREA)
    return im


# ---------------------------------------------------------------- Messkette (B2 Sweep -> B3 Massliste)

def _wert(w, quelle, status="gemessen", streuung=None, n_fotos=None, **kw):
    d = dict(wert=None if w is None else float(w), status=status, quelle=quelle)
    if streuung is not None: d["streuung_m"] = float(streuung)
    if n_fotos is not None: d["fotos"] = int(n_fotos)
    d.update(kw); return d


def _fehlt(grund, **kw):
    return dict(wert=None, status="fehlt", grund=grund, **kw)


def profil_spitzen(p, achse, Kf=None, abst_m=0.12, rel=0.35, fenster_halb=0.3, k_mad=2.0):
    """Spitzen eines Konsensprofils mit Feinlage, Staerke und Streuung ueber die Fenster (Kf[f, i]): je Fenster das Maximum im +-fenster_halb um die Spitze."""
    d = achse[1] - achse[0]; pk = spitzen_1d(p, abst=max(1, int(round(abst_m / d))), schwelle=max(np.median(p) + k_mad * 1.4826 * np.median(np.abs(p - np.median(p))), rel * p.max()))
    out = []
    for i in pk:
        x = achse[0] + subpixel(p, i) * d; st = None; nf = None
        if Kf is not None:
            w = max(1, int(round(fenster_halb / d))); lo, hi = max(0, i - w), min(len(p), i + w + 1); xs = []
            for f in range(Kf.shape[0]):
                k = Kf[f, lo:hi]
                if np.isfinite(k).any() and np.nanmax(k) > 0.5 * p[i]: xs.append(achse[lo + int(np.nanargmax(k))])
            nf = len(xs); st = float(np.std(xs)) if len(xs) >= 2 else None
        out.append(dict(x=float(x), v=float(p[i]), streuung=st, fenster=nf))
    return out


def messen(kams, kbs, zone, raster=0.04, z_strasse=None, reserve=0.6, lauf_min=0.8, pfosten_abstand_min=0.5, bruestung_bereich=(0.5, 1.4), log=print, kern_s=None):
    """B2+B3: Kanten-Sweeps in der Zone (Suchraum = Zone + reserve) -> Massliste (je Wert quelle/streuung/status) + Parameter fuer bauteile.ueberdachter_gang.
    Keine Objektwerte: alle Zahlen sind Suchraeume/Rasterweiten. Fehlt ein Mass -> status 'fehlt' + Grund; der Bau meldet es ROT (bauteile.bruecke_tor)."""
    R = zone["rahmen"]; sm = 0.5 * (zone["s0"] + zone["s1"]); hl = 0.5 * (zone["s1"] - zone["s0"]) * (1 + reserve)
    qm = zone["qmax"] * (1 + reserve); zm = 0.5 * (zone["z0"] + zone["z1"]); hz = 0.5 * (zone["z1"] - zone["z0"]) * (1 + reserve)
    ss = np.arange(sm - hl, sm + hl + 1e-9, raster); qs = np.arange(-qm, qm + 1e-9, raster); zs = np.arange(zm - hz, zm + hz + 1e-9, raster / 2)
    M_ = {}; diag = {}; t0 = time.time()
    # --- 1 senkrechte Kanten im Grundriss (Pfosten) -> Wandebenen
    V = senk_sweep(kams, kbs, R, ss, qs, zm); diag["V"] = V
    k0_, k1_ = kern_s if kern_s is not None else (sm - 0.35 * (zone["s1"] - zone["s0"]), sm + 0.35 * (zone["s1"] - zone["s0"]))
    kern = (ss >= k0_) & (ss <= k1_)   # Kernbereich: sicher auf der Bruecke, nie Treppe/Anbau
    r = np.percentile(V[:, kern], 97, axis=1); diag["r"] = r
    kq = spitzen_1d(r, abst=max(1, int(round(0.2 / raster))), schwelle=np.median(r) + 2 * 1.4826 * np.median(np.abs(r - np.median(r))))
    if not kq:
        return dict(status="nicht belegt", grund="keine senkrechten Kanten (Pfosten) in der Zone", parameter={}), diag
    zone_qc = 0.0; i1 = max(kq, key=lambda i: r[i]); prof = lambda i: V[max(0, i - 1):i + 2].max(0)
    profk = lambda i: prof(i)[kern]
    kand = []
    lokal = [i for i in range(1, len(r) - 1) if r[i] >= r[i - 1] and r[i] >= r[i + 1]]          # Gegenseite: jedes lokale Maximum (schwaecher gesehen), Entscheid per Paarkorrelation
    for i in lokal:
        if abs(qs[i] - qs[i1]) >= lauf_min and (qs[i] - zone_qc) * (qs[i1] - zone_qc) < 0:   # Gegenseite liegt jenseits der Zonenmitte (Zone = Suchraum, Mitte +-0,5 m)
            a_, b_ = profk(i1), profk(i); c = float(np.corrcoef(a_, b_)[0, 1]); kand.append((c, i))
    kand.sort(reverse=True); i2 = kand[0][1] if kand and kand[0][0] >= 0.3 else None
    log("  Gegenseiten-Kandidaten (Korrelation, q): " + ", ".join(f"{c:.2f}@{qs[i]:+.2f}" for c, i in kand[:5]))
    log(f"  Wandebenen: q {qs[i1]:+.2f} (Staerke {r[i1]:.2f})" + (f", Gegenseite q {qs[i2]:+.2f} (Korrelation der Pfostenprofile {kand[0][0]:.2f})" if i2 is not None else ", Gegenseite NICHT gefunden") + f"  [{time.time() - t0:.0f}s]")
    waende = [i1] + ([i2] if i2 is not None else [])
    if i2 is not None:
        qL, qR = sorted([qs[i1] + subpixel(r, i1) * 0 , qs[i2]]); qL = min(qs[i1], qs[i2]) ; qR = max(qs[i1], qs[i2])
        M_["breite"] = _wert(qR - qL, "senkrechte Fotokanten (Pfostenebenen beider Seiten, Grundriss-Sweep)", streuung=raster, korrelation=round(kand[0][0], 3))
        qc = 0.5 * (qL + qR)
    else:
        M_["breite"] = _fehlt("Gegenseite der Pfosten nicht gefunden (Korrelation < 0,3) - Fotos der anderen Seite fehlen"); qL = qR = qc = float(qs[i1])
    # --- 2 Pfosten laengs: Leiter im Kernbereich, dann nach aussen fortsetzen, solange die Fotos dort Pfosten zeigen (Enden = wo die Leiter abreisst)
    lagen = []; pw = np.max([prof(i) for i in waende], 0)
    for i in waende:
        p = prof(i); thr = np.median(p[kern]) + 2 * 1.4826 * np.median(np.abs(p[kern] - np.median(p[kern])))
        lagen += [ss[k] for k in spitzen_1d(p, abst=max(1, int(round(0.3 / raster))), schwelle=thr) if kern[k]]
    diag["pfosten_funde"] = lagen
    L = leiter_fit(lagen, pfosten_abstand_min) if len(lagen) >= 3 else dict(n_sprossen=None, grund="zu wenige Pfostenfunde")
    sa = sb = None
    if L["n_sprossen"] is None: M_["pfosten"] = _fehlt(L["grund"])
    else: log(f"  Pfostenleiter im Kernbereich: Abstand {L['a']:.2f} m, {L['belegt']} Funde, Rest {L['rest']:.2f}")
    # --- 3 Hoehen: Profil waagrechter Laengsgeraden in den Wandebenen (nur zwischen den Enden)
    s0m, s1m = k0_, k1_
    # Hoehenbereich der Pfosten (senkrechte Kanten an den gefundenen Pfostenlagen, kurze Stuecke je Hoehe): Deck und Traufe liegen an seinen Enden
    if L.get("n_sprossen"):
        lg = np.array(L["treffer"]); zz = np.arange(zs[0], zs[-1], 0.1); prof_z = []
        for zc in zz:
            A = R.welt(lg, np.full(len(lg), qs[i1]), np.full(len(lg), zc - 0.15)); B = A.copy(); B[:, 2] += 0.3
            Sv, _ = geraden_stuetze(kams, kbs, A, B, M=8, min_px=10.0); prof_z.append(np.median(Sv))
        prof_z = np.array(prof_z); diag["pfosten_z"] = prof_z; j = int(np.argmin(np.abs(zz - zm))); thr = 0.5 * prof_z[max(0, j - 3):j + 4].max()
        lo = j; hi = j
        while lo > 0 and prof_z[lo - 1] > thr: lo -= 1
        while hi < len(zz) - 1 and prof_z[hi + 1] > thr: hi += 1
        zp0, zp1 = float(zz[lo]), float(zz[hi]); log(f"  Pfosten reichen z {zp0:.2f}..{zp1:.2f}")
        M_["pfosten_hoehe"] = _wert(zp1 - zp0, "senkrechte Fotokanten an den Pfostenlagen, Hoehenprofil (halbe Spitzenhoehe)", streuung=0.1, z_unten=round(zp0, 2), z_oben=round(zp1, 2))
        # (nur Diagnose; zur Begrenzung zu unscharf: 27.11. z 7,28..8,18 bei sichtbar 5,4..8,4 m)
    beste = None
    for i in waende:
        P, Kf, _ = hoehen_profil(kams, kbs, R, s0m, s1m, qs[i], zs); sp = profil_spitzen(P, zs, Kf, rel=0.15, k_mad=1.0); diag[f"hoehen_q{qs[i]:+.2f}"] = P
        if beste is None or (len(sp) and max(x["v"] for x in sp) > max([x["v"] for x in beste[1]] or [0])): beste = (qs[i], sp, P)
    qw, sp, P = beste; log("  Hoehenspitzen (q %+.2f): " % qw + ", ".join(f"{x['x']:.2f}({x['v']:.2f},{x['fenster']}F)" for x in sp))
    nwin = max(1, int(round((s1m - s0m) / 4.0)))
    # Brueckenkanten laufen durch (fast) alle Fenster; Strassen-/Anbaukanten nur durch einzelne (27.11.: Kante z 2,0 = Strassengelaender)
    sp = [x for x in sp if (x["fenster"] or 0) >= 0.5 * nwin]
    # Bauwerk-Cluster: von der staerksten Kante aus nur Kanten mit Abstand <= 1,2 m zur Nachbarkante (Strassenkanten liegen getrennt darunter, 27.11. Tauschtest 1,3)
    if sp:
        sp.sort(key=lambda x: x["x"]); k0 = max(range(len(sp)), key=lambda i: sp[i]["v"]); lo = hi = k0
        while lo > 0 and sp[lo]["x"] - sp[lo - 1]["x"] <= 1.2: lo -= 1
        while hi < len(sp) - 1 and sp[hi + 1]["x"] - sp[hi]["x"] <= 1.2: hi += 1
        sp = sp[lo:hi + 1]
    stark = [x for x in sp if x["v"] >= 0.4 * max(x["v"] for x in sp)] if sp else []
    if len(stark) < 2:
        for k in ("unterkante", "traufe", "laufebene", "holm", "riegel"): M_[k] = _fehlt("weniger als zwei starke waagrechte Kanten in der Wandebene")
    else:
        uk = min(stark, key=lambda x: x["x"]); tr = max(stark, key=lambda x: x["x"]); inner = [x for x in sp if uk["x"] < x["x"] < tr["x"]]
        q_ = "waagrechte Fotokanten, Hoehenprofil in der Pfostenebene q %+.2f" % qw
        M_["unterkante"] = _wert(uk["x"], q_ + " (unterste starke Kante)", streuung=uk["streuung"], n_fotos=None, fenster=uk["fenster"])
        M_["traufe"] = _wert(tr["x"], q_ + " (oberste starke Kante unter dem Dach)", streuung=tr["streuung"], fenster=tr["fenster"])
        lf = [x for x in inner if 0.1 <= x["x"] - uk["x"] <= 1.0]
        M_["laufebene"] = _wert(lf[0]["x"], q_ + " (erste Kante ueber der Unterkante = Deckoberkante/Stirnbrett)", streuung=lf[0]["streuung"], hinweis="ANNAHME: Stirnbrett-Oberkante = Laufebene") if lf else _fehlt("keine Kante 0,1-1,0 m ueber der Unterkante")
        zb = M_["laufebene"]["wert"]
        if zb is not None:
            ho = [x for x in inner if bruestung_bereich[0] <= x["x"] - zb <= bruestung_bereich[1]]
            M_["holm"] = _wert(max(ho, key=lambda x: x["v"])["x"], q_ + " (staerkste Kante im Bruestungsbereich)", streuung=max(ho, key=lambda x: x["v"])["streuung"]) if ho else _fehlt("kein Bruestungsholm gefunden")
        else: M_["holm"] = _fehlt("Laufebene fehlt")
        zh = M_["holm"]["wert"]
        zr0 = (zh if zh is not None else (zb + bruestung_bereich[1] if zb is not None else None))
        ri = [x for x in inner if zr0 is not None and x["x"] > zr0 + 0.3]
        M_["riegel"] = _wert(max(ri, key=lambda x: x["x"])["x"], q_ + " (hoechste Kante unter der Traufe)", streuung=max(ri, key=lambda x: x["x"])["streuung"]) if ri else _fehlt("keine Riegelkante unter der Traufe (Seitenfeld reicht bis unters Dach?)")
    # --- 3b Enden: Stuetze der durchgehenden Laengskanten (Unterkante, Traufe, staerkste innere) in 2-m-Fenstern ueber den ganzen Suchraum;
    #     Ende = wo sie (vom Kern aus) unter 30 % der Kernstuetze fallen, ohne Luecke (mit Lueckenbruecke lief es 27.11. in Anbau/Hang weiter)
    zu = M_.get("unterkante", {}).get("wert")
    if zu is not None:
        zl = sorted({round(x["x"], 2) for x in stark})
        _, Kd, mit = quer_sweep(kams, kbs, R, ss[0], ss[-1], np.array([qw]), np.array(zl), fenster=1.0, min_px=25.0, schwelle=0.2)
        d_ = np.nanmean(Kd[:, :, 0], 1); diag["deck_laengs"] = np.nan_to_num(d_, nan=-1); kern_w = (mit >= k0_) & (mit <= k1_)
        thr = 0.3 * np.nanmedian(d_[kern_w]); j0 = int(np.argmin(np.abs(mit - 0.5 * (k0_ + k1_)))); ok = np.nan_to_num(d_, nan=-1) >= thr; lo = hi = j0
        while lo > 0 and ok[lo - 1]: lo -= 1
        while hi < len(mit) - 1 and ok[hi + 1]: hi += 1
        hw = 0.5 * (mit[1] - mit[0]); sa, sb = float(mit[lo] - hw), float(mit[hi] + hw)
        rand = (lo == 0) or (hi == len(mit) - 1)
        M_["spannweite"] = _wert(sb - sa, "Laengsprofil der durchgehenden waagrechten Fotokanten (Abriss < 30 % der Kernstuetze, 1-m-Fenster)", streuung=1.0,
                                 s_a=round(sa, 2), s_b=round(sb, 2), hinweis="Suchraumrand erreicht - Ende evtl. ausserhalb" if rand else "")
        log(f"  Enden (Laengskanten): s {sa:+.2f}..{sb:+.2f} = {sb - sa:.2f} m" + (" (RAND des Suchraums!)" if rand else ""))
        if L.get("n_sprossen"):
            a_ = L["a"]; ph = L["x0"]; k0 = math.ceil((sa - ph) / a_ - 0.3); k1 = math.floor((sb - ph) / a_ + 0.3); lg_ = [ph + k * a_ for k in range(k0, k1 + 1)]
            M_["pfosten"] = _wert(len(lg_), "Pfostenleiter (Abstand/Phase aus senkrechten Fotokanten im Kern) zwischen den Deck-Enden", abstand_m=round(a_, 3), rest_m=round(L["rest"], 3),
                                  belegt_kern=L["belegt"], lagen_s=[round(x, 3) for x in lg_], zaehlung="Sweep-Konsens; Fotozaehlung siehe zaehlung_pfosten")
            log(f"  Pfosten zwischen den Enden: {len(lg_)} (erste s {lg_[0]:+.2f}, letzte {lg_[-1]:+.2f})")
    else: M_["spannweite"] = _fehlt("Unterkante fehlt - Enden nicht messbar")
    M_.setdefault("pfosten", _fehlt("keine Pfostenleiter"))
    # --- 4 First in der Gangmitte
    zt = M_.get("traufe", {}).get("wert")
    if zt is not None and M_["breite"]["status"] != "fehlt":
        zsf = zs[zs > zt + 0.2]; Pf, Kff, _ = hoehen_profil(kams, kbs, R, s0m, s1m, qc, zsf); spf = profil_spitzen(Pf, zsf, Kff) if len(zsf) > 4 else []
        diag["first_profil"] = Pf
        if spf:
            f_ = max(spf, key=lambda x: x["x"] if x["v"] >= 0.5 * max(y["v"] for y in spf) else -1e9)
            M_["first"] = _wert(f_["x"], "waagrechte Fotokanten, Hoehenprofil in der Gangmitte q %+.2f (hoechste starke Kante)" % qc, streuung=f_["streuung"])
        else: M_["first"] = _fehlt("keine Firstkante ueber der Traufe")
    else: M_["first"] = _fehlt("Traufe oder Breite fehlt")
    # --- 5 Dachueberstand: Querkarte aussen neben der Wandebene in Traufhoehe
    if zt is not None:
        best_u = []
        for seite, q0 in ((-1, qL), (1, qR)) if M_["breite"]["status"] != "fehlt" else ((-1 if qw < 0 else 1, qw),):
            qa = np.arange(raster, 1.5 + 1e-9, raster); qq = q0 + seite * qa; za = np.arange(zt - 0.3, zt + 0.6 + 1e-9, raster / 2)
            S2, Kf2, _ = quer_sweep(kams, kbs, R, s0m, s1m, qq, za); diag[f"traufe_{seite}"] = S2
            pk = spitzen_2d(S2, abst=2, schwelle=0.5 * S2.max(), maxn=3)
            if pk and S2.max() > 0.1: best_u.append((qa[pk[0][1]], za[pk[0][0]], pk[0][2]))
        if best_u:
            u_ = max(best_u, key=lambda x: x[2])
            M_["ueberstand"] = _wert(u_[0], "Querkarte waagrechter Fotokanten neben der Wandebene (Traufkante)", streuung=raster, z_traufkante=round(u_[1], 3), staerke=round(u_[2], 3),
                                     hinweis="Querlage aus fast waagrechten Strahlen schlecht bestimmt (Strassenfotos); nur grob")
        else: M_["ueberstand"] = _fehlt("keine Traufkante neben der Wandebene")
    else: M_["ueberstand"] = _fehlt("Traufe fehlt")
    # --- 6 Stuetzen unter dem Deck (senkrechte Kanten zwischen Strasse und Unterkante)
    zu = M_.get("unterkante", {}).get("wert")
    if zu is not None and z_strasse is not None and zu - z_strasse > 1.0:
        hst = 0.6 * (zu - z_strasse); Vs = senk_sweep(kams, kbs, R, ss, qs, 0.5 * (zu + z_strasse), laenge=hst); diag["V_stuetzen"] = Vs
        med = np.median(Vs); mad = 1.4826 * np.median(np.abs(Vs - med)); pk = spitzen_2d(Vs, abst=int(round(0.5 / raster)), schwelle=max(med + 8 * mad, 0.3), maxn=12)
        kandidaten = [dict(s=round(float(ss[x]), 2), q=round(float(qs[y]), 2), konsens=round(v, 3)) for y, x, v in pk]
        M_["stuetzen"] = _fehlt("Kandidaten aus senkrechten Kanten unter dem Deck, Querschnitt/Zugehoerigkeit (Treppenanlage?) nicht gemessen" if kandidaten else "keine senkrechten Kanten unter dem Deck - 'keine Stuetzen' nur mit Fotobeleg",
                                kandidaten=kandidaten)
    else: M_["stuetzen"] = _fehlt("Unterkante oder Strassenhoehe fehlt")
    if M_.get("pfosten", {}).get("status") == "gemessen" and M_.get("laufebene", {}).get("wert") is not None and M_.get("riegel", {}).get("wert") is not None:
        Z = zaehlung_pfosten(kams, kbs, R, M_["pfosten"]["lagen_s"], qw, M_["holm"]["wert"] + 0.1 if M_.get("holm", {}).get("wert") else M_["laufebene"]["wert"] + 0.3, M_["riegel"]["wert"] - 0.05)
        M_["pfosten"]["zaehlung_am_foto"] = dict(einig=Z["einig"], fotos=[o for o in Z["je_foto"] if o["voll"]][:12])
        diag["zaehlung"] = Z
        log(f"  Pfosten-Zaehlung am Foto: {Z['einig']} Fotos sehen alle {Z['n']} Pfosten und keinen dazwischen; voll sichtbar in {sum(o['voll'] for o in Z['je_foto'])} Fotos")
        if Z["einig"] < 3:
            M_["pfosten"]["status"] = "fehlt"; M_["pfosten"]["grund"] = f"Pfostenzahl {Z['n']} nur in {Z['einig']} Fotos bestaetigt (< 3) - Zaehlung am Foto nicht einig"
    M_["treppe"] = _fehlt("Treppe nicht gemessen: Stufenkanten-Sweep der Treppenzone fehlt (Fotos zeigen eine Podesttreppe mit Wendung am Ende a, im Baustein nur gerader Lauf)")
    if kern_s is None and sa is not None and sb - sa > 4.0:
        # zweiter Durchgang: Kern = mittlere 70 % der GEMESSENEN Enden (nicht der Zone) -> Ergebnis unabhaengig vom Suchraum (Tauschtest 27.11.)
        log(f"  2. Durchgang mit Kern s {sa + 0.15 * (sb - sa):+.2f}..{sb - 0.15 * (sb - sa):+.2f} (aus den gemessenen Enden)")
        return messen(kams, kbs, zone, raster, z_strasse, reserve, lauf_min, pfosten_abstand_min, bruestung_bereich, log, kern_s=(sa + 0.15 * (sb - sa), sb - 0.15 * (sb - sa)))
    return dict(status="gemessen", parameter=M_, rahmen=dict(mitte=R.m.tolist(), achse=R.d.tolist(), neigung_grad=math.degrees(math.atan(R.tg))), qc=qc, s_a=sa, s_b=sb,
                fotos=len(kams), sekunden=round(time.time() - t0, 1)), diag


def zaehlung_pfosten(kams, kbs, R, lagen, q, z0, z1, min_len_px=40.0, treffer=0.5):
    """ZAEHLEN AM FOTO (Regel: Anzahlen nur am Foto, >= 3 Fotos einig): je Foto jede Pfostenlage (senkrechte Strecke z0..z1 in der Wandebene q) einzeln pruefen
    (Trefferanteil gerader Bildkanten >= treffer) UND die Feldmitten dazwischen (dort darf KEIN Pfosten stehen). Ein Foto zaehlt 'voll', wenn alle Lagen im Bild sind.
    Liefert dict(je_foto=[{foto, gefunden, im_bild, mitten_treffer, voll}], einig=n Fotos mit voll & gefunden == alle & mitten 0, n)."""
    lagen = np.asarray(lagen, float); a = np.median(np.diff(lagen)) if len(lagen) > 1 else 1.0; mitten = lagen[:-1] + a / 2
    def stuecke(ss):
        A = R.welt(ss, np.full(len(ss), q), np.full(len(ss), z0)); B = R.welt(ss, np.full(len(ss), q), np.full(len(ss), z1)); return A, B
    out = []; versatz = np.arange(-0.15, 0.151, 0.03)          # Pfosten haben zwei Kanten (+-Breite/2); die Leiterlage trifft eine davon
    for j, (c, kb) in enumerate(zip(kams, kbs)):
        def best(ss):
            E = np.stack([geraden_stuetze([c], [kb], *stuecke(ss + dv), M=24, min_px=min_len_px, roh=True)[1][:, 0] for dv in versatz], 1)
            return np.where(np.isfinite(E).all(1), np.nanmax(E, 1), np.nan)
        e = best(lagen); em = best(mitten)
        im = np.isfinite(e); gef = int(np.sum(e[im] >= treffer)); mt = int(np.sum(em[np.isfinite(em)] >= treffer))
        out.append(dict(foto=j, im_bild=int(im.sum()), gefunden=gef, mitten_treffer=mt, voll=bool(im.all())))
    einig = [o for o in out if o["voll"] and o["gefunden"] == len(lagen) and o["mitten_treffer"] == 0]
    return dict(n=int(len(lagen)), je_foto=out, einig=len(einig), einig_fotos=[o["foto"] for o in einig])


TAUSCH_TOL = dict(breite=0.15, unterkante=0.15, laufebene=0.15, holm=0.15, riegel=0.15, traufe=0.15, first=0.15, ueberstand=0.15, spannweite=1.0, pfosten=0.0)


def tausch_pruefen(ml, andere, tol=TAUSCH_TOL):
    """TAUSCHTEST in der Stufe (Memory 25.11. 'gegen zirkulaere Messung'): dieselbe Messung mit veraenderter Zone (Suchraum +-30 %) muss je Parameter dasselbe
    liefern. Abweichung > tol -> status 'instabil' (+ Werte), Bau meldet ROT. Nie den Mittelwert nehmen."""
    for k, t in tol.items():
        v = ml["parameter"].get(k)
        if not v or v.get("wert") is None: continue
        ws = [a["parameter"].get(k, {}).get("wert") for a in andere]
        if any(w is None for w in ws) or max(abs(w - v["wert"]) for w in ws) > t + 1e-9:
            v["tausch_werte"] = [None if w is None else round(w, 3) for w in ws]; v["status"] = "fehlt" if v["status"] == "fehlt" else "instabil"
            v["grund"] = (v.get("grund", "") + "; " if v.get("grund") else "") + f"Tauschtest (Zone +-30 %): {[round(w, 2) if w is not None else None for w in ws]} gegen {v['wert']:.2f} (> {t} m)"
        else: v["tausch_werte"] = [round(w, 3) for w in ws]
    return ml


def gang_parameter(ml, massstab=87.0, min_mm=0.8):
    """Massliste -> Parameter-dict fuer bauteile.ueberdachter_gang (Achse im Modellrahmen). Fehlende Masse -> Eintrag in 'fehlt' (Bau meldet ROT),
    NIE ein Ersatzwert. Nicht messbare Dicken (Wand, Dach, Pfosten) = Druck-Mindestmass, im Beleg als ANNAHME (PLAN: 'sonst Druck-Mindestmass')."""
    P_ = ml["parameter"]; w = lambda k: P_.get(k, {}).get("wert"); fehlt = [dict(bauteil=k, grund=v.get("grund", "")) for k, v in P_.items() if v.get("status") in ("fehlt", "instabil")]
    dmin = min_mm * massstab / 1000.0
    if None in (w("spannweite"), w("breite"), w("laufebene"), w("traufe"), ml.get("s_a")):
        return None, fehlt + [dict(bauteil="bruecke", grund="Grundmass fehlt (spannweite/breite/laufebene/traufe)")]
    R = Rahmen(ml["rahmen"]["mitte"], ml["rahmen"]["achse"], ml["rahmen"]["neigung_grad"]); qc = ml["qc"]
    a = R.welt(ml["s_a"], qc, 0.0)[:2]; b = R.welt(ml["s_b"], qc, 0.0)[:2]; B = w("breite"); zb = w("laufebene")
    P = dict(achse=dict(a=a.tolist(), b=b.tolist()), breite=B, z_boden=zb, hoehe=w("traufe") - zb, boden_dicke=zb - w("unterkante") if w("unterkante") else None,
             wand_dicke=dmin, einbinden=0.0, quelle="bruecke_messen (Fotokanten-Sweep, Teilmodell-Kameras)", fehlt=fehlt)
    u = w("ueberstand"); zf = w("first")
    if zf is not None and u is not None:
        P["dach"] = dict(form="sattel", neigung_grad=math.degrees(math.atan2(zf - w("traufe"), B / 2 + u)), ueberstand=u, dicke=dmin)
    elif zf is not None:
        P["dach"] = dict(form="sattel", neigung_grad=math.degrees(math.atan2(zf - w("traufe"), B / 2)), ueberstand=0.0, dicke=dmin)
    if w("pfosten") and w("holm") is not None:
        lag = [x - ml["s_a"] for x in P_["pfosten"]["lagen_s"]]
        P["seiten"] = dict(art="offen", pfosten=int(w("pfosten")), pfosten_lagen=lag, pfosten_breite=dmin, bruestung=w("holm") - zb,
                           riegel=(w("traufe") - w("riegel")) if w("riegel") is not None else dmin)
    return P, fehlt


def lauf_messen(kamwahl, lage, ausdir, skala=1.0, skala_h=None, z_strasse=None, tausch=True):
    from concurrent.futures import ThreadPoolExecutor
    W = json.load(open(kamwahl)); L = json.load(open(lage)); os.makedirs(ausdir, exist_ok=True)
    zone = zone_aus_lage(L, skala, skala_h); names = list(W["kameras"]); kams = [W["kameras"][n] for n in names]
    if z_strasse is None:
        try: z_strasse = float(str(L["steg"]["strasse_z_m"]).replace(",", ".").split("-")[-1].split()[0])
        except (KeyError, ValueError, IndexError): z_strasse = None
    with ThreadPoolExecutor(16) as ex: kbs = list(ex.map(lambda nc: kantenbild(bild_laden(W["bilddir"], nc[0], nc[1])), zip(names, kams)))
    ml, diag = messen(kams, kbs, zone, z_strasse=z_strasse)
    if tausch and ml["status"] == "gemessen":
        andere = [messen(kams, kbs, zone_aus_lage(L, skala * f, (skala_h or skala) * f), z_strasse=z_strasse, log=lambda *_: None)[0] for f in (0.7, 1.3)]
        tausch_pruefen(ml, [a for a in andere]); print("  Tauschtest:", ", ".join(f"{k} {v['tausch_werte']}" for k, v in ml["parameter"].items() if v.get("status") == "instabil") or "stabil")
    ml.update(kameras=names, zone_skala=skala, zone_skala_hoehe=skala_h, z_strasse=z_strasse, lage=os.path.abspath(lage))
    P, fehlt = gang_parameter(ml) if ml["status"] == "gemessen" else (None, [dict(bauteil="bruecke", grund=ml.get("grund"))])
    ml["gang"] = P; ml["fehlt"] = fehlt
    json.dump(ml, open(os.path.join(ausdir, "massliste_bruecke.json"), "w"), indent=1, ensure_ascii=False)
    Z = diag.pop("zaehlung", None)
    if Z: json.dump(dict(Z, je_foto=[dict(o, foto=names[o["foto"]]) for o in Z["je_foto"]], einig_fotos=[names[i] for i in Z["einig_fotos"]]), open(os.path.join(ausdir, "zaehlung_pfosten.json"), "w"), indent=1)
    np.savez_compressed(os.path.join(ausdir, "sweep_diag.npz"), **{k: np.asarray(v, dtype=float) for k, v in diag.items()})
    print("Massliste ->", os.path.join(ausdir, "massliste_bruecke.json"), "| fehlt:", ", ".join(f["bauteil"] for f in fehlt) or "nichts")
    return 0 if ml["status"] == "gemessen" else 2


def main():
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    cmd = sys.argv[1]
    def opt(n, d, t=float): return t(sys.argv[sys.argv.index(n) + 1]) if n in sys.argv else d
    if cmd == "kameras":
        K = json.load(open(sys.argv[2])); L = json.load(open(sys.argv[3])); X = ply_lesen(sys.argv[4], nmax=opt("--wolke_n", 2_000_000, int))
        zone = zone_aus_lage(L); X = ausser_zone(X, zone); wahl = kameras_waehlen(K, zone, X, nmax=opt("--max", 40, int), min_sicht=opt("--min_sicht", 0.6))
        json.dump(dict(kameras={w[0]: K[w[0]] for w in wahl}, wahl=wahl, bilddir=sys.argv[5]), open(sys.argv[6], "w"))
        for w in wahl: print("%-28s sicht %.2f querwinkel %+6.1f abst %5.1f s %+6.1f q %+6.1f" % w)
        print(len(wahl), "Kameras ->", sys.argv[6])
    elif cmd == "messen":
        sys.exit(lauf_messen(sys.argv[2], sys.argv[3], sys.argv[4], skala=opt("--zone_skala", 1.0), skala_h=opt("--zone_skala_hoehe", None), z_strasse=opt("--z_strasse", None), tausch="--ohne_tausch" not in sys.argv))
    else:
        print(__doc__); sys.exit(2)


if __name__ == "__main__":
    main()
