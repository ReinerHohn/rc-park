#!/usr/bin/env python3
"""traufe_aus_fotos.py - TRAUFE DES HAUPTDACHS aus FOTOKANTEN (Mehrfoto-Kanten-Sweep mit den SfM-Kameras), 21.11.2026.

Anlass (Nutzer: "Das ist noch nicht gut", audit/neben_eigen__IMG_20261106_113231.jpg): im Foto steht das Hauptdach als dicke, dunkle Traufe ueber die Wand,
im Kettenmodell nur ein duenner Abschluss - bauteile.dach_aus_profil baut die unterste Wolkenscheibe als 2-cm-Platte, die Kette meldete den Ueberstand nur
"aus der Wolke (vorlaeufig)". KERNMETHODE: Form aus Fotokanten + Triangulation, die Wolke liefert nur den Rahmen (dach_profil.json: Achse o, Richtungen d/n, Wandebene).

Verfahren je Seite (-d, +d, -n, +n) - Kanten-Tiefen-Sweep fuer WAAGRECHTE Kanten parallel zur Seite:
 1. Kameras vor der Seite (Abstand > 3 m vor der Wandebene, Hoehenwinkel EL_MIN..EL_MAX), gleichmaessig ueber den Hoehenwinkel bis --max-fotos.
 2. Hypothese (a, z): waagrechte Linie im Abstand a vor der Wandebene (wand_halb des Dachprofils) in Hoehe z, mittlere ANTEIL der Seitenlaenge (Ecken/Grate
    und Nachbarn an den Enden fallen weg). Je Foto: mittlerer Grauwertgradient QUER zur projizierten Linie (Vorzeichen: hell unten/dunkel oben = negativ),
    geteilt durch den mittleren Gradientenbetrag auf allen Hypothesen dieses Fotos (Textur-Normierung). Eine gerade durchgehende Kante gibt einen hohen
    Betrag, Mauerwerk/Ziegel mitteln sich weg. Ein Foto legt nur einen Sehstrahl in der (a, z)-Ebene fest; erst Fotos aus verschiedenen Hoehenwinkeln
    schneiden sich im Punkt der Kante (Triangulation) - Spitze der Summenkarte = 3D-Kante.
 3. WANDANSCHLUSS (a_wand, z_wand) = staerkste Kante nahe der Wandebene; AUSSENKANTE (a_aussen, z_oben) = staerkste Kante mind. 0,2 m davor und 0,15 m
    darueber (Traufkante gegen Himmel/Dach). Gueltig nur, wenn beide Kanten (a) mind. STARK x Median der Karte und (b) in BEIDEN Haelften der Fotos (nach
    Hoehenwinkel geteilt, je mind. MIN_HALB Fotos) an derselben Stelle (+-TOL_A / TOL_Z) wiederkehren = Formfamilie aus vielen Fotos, kein Einzelfoto.
 4. STIRN-UNTERKANTE: Spalte a_aussen, flache Fotos (Hoehenwinkel < EL_STIRN, dort sieht man die Stirnflaeche von vorn), Spitze zwischen Wandanschluss
    und Aussenkante, ebenfalls in beiden Haelften. Nicht gefunden -> z_unten = None (ehrlich: nicht aufgeloest), Bau: Untersicht als Ebene vom Wandanschluss
    zur Aussenkante, Stirn nur Druckmindestmass (ANNAHME im Beleg).
 5. (24.11.2026) ohne Unterkante aus 4.: STIRN-UNTERKANTE aus den triangulierten 3D-Kanten der Kantenstufe (sweep.npz, Traufzone bis Dachfuss + 1 m;
    stirn_aus_kanten: Spitze in der Spalte a_aussen, waagrechte Linie ueber die Seite, >= 3 Referenzfotos). Erst wenn auch das fehlt: ANNAHME wie bisher.
 Ungesehene Seiten (zu wenige Fotos/keine bestaetigte Kante) bleiben ungueltig: dort baut dach_aus_profil weiter aus Wolke/DOM1 und vermerkt das.
Ausgabe: Block 'traufe_foto' in audit/dach_profil.json {seiten: {"+n": {gueltig, a_wand, z_wand, a_aussen, z_oben, z_unten, ueberstand, stirn_m, untersicht_grad,
fotos, staerke, grund}}, gueltige_seiten, quelle, annahmen}; Bild audit/traufe_foto.jpg (Summenkarte je Seite + Fotoausschnitte mit den gemessenen Kanten).
-> bauteile.traufkasten / dach_aus_profil (Traufkasten mit Stirn + Untersicht je gemessener Seite), hand_vergleich: zeltdach_ueberstand "aus Fotos".
Aufruf: traufe_aus_fotos.py <objekt.json> [--profil audit/dach_profil.json] [--aus DATEI] [--bild DATEI] [--max-fotos 120] [--seiten +n,-d] [--nur-messen]
rc 0 = mind. eine Seite gueltig eingetragen, rc 3 = kein Dachprofil, rc 4 = keine Seite gueltig (Block mit gueltig=false eingetragen).
"""
import sys, os, json, argparse, math, numpy as np

H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)

# ---- Schwellen (Grund je Zeile; nicht an einem Bauwerk eingestellt) ---------------------------------------------------------------------------
EL_MIN, EL_MAX = 5.0, 88.0   # Hoehenwinkel zur Traufe: < 5 Grad liegt die Kante streifend (Strahlen parallel), > 88 Grad senkrecht unter der Wand
VOR_MIN_M = 3.0              # Kamera mind. 3 m vor der Wandebene (sonst sieht sie die Seite streifend/von hinten)
ANTEIL = 0.6                 # mittlere 60 % der Seitenlaenge (Grate, Eckquader und Nachbardaecher an den Enden fallen weg)
A_BEREICH = (-1.6, 2.4)      # Suchbereich vor der Wandebene (m): Wand des Dachprofils kann +-1 m daneben liegen, Ueberstaende ueber 2,4 m gibt es an Tuermen nicht
Z_BEREICH = (-3.0, 2.0)      # um z0 des Dachprofils (Dachbeginn der Wolke)
RASTER = 0.04                # 4 cm: 1 px bei 25 m Abstand und 1600-px-Bild
DECKUNG = 0.7                # eine Hypothese zaehlt im Foto nur, wenn 70 % ihrer Linienpunkte im Bild liegen
STARK = 2.0                  # Kante = mind. 2 x Median der Summenkarte (Kanten-Rauschen der Ziegel/Mauern ~ Median)
MIN_FOTOS = 30               # Formfamilie: >= 30 Fotos mit voller Deckung (Schwabentor -d: 25 Fotos gaben eine Scheintraufe 0,5 m zu hoch mit 2,1-2,9 x Median, 54 Fotos derselben Seite keine)
MIN_HALB = 3
TOL_A, TOL_Z = 0.25, 0.16    # Haelften-Bestaetigung: flache Fotos loesen a schlechter auf als z (Strahlen flach), darum TOL_A > TOL_Z
KAMM = 0.6                   # Kamm einer Haelfte am Punkt mind. 60 % seines Maximums in der Umgebung (sonst gehoert die Spitze zu einer anderen Kante)
EL_SPANNE = 12.0             # Triangulation braucht verschiedene Hoehenwinkel: Mediane der beiden Fotohaelften mind. 12 Grad auseinander (sonst nur ein Sehstrahl)
AUSSEN_MIN_A, AUSSEN_MIN_Z = 0.2, 0.15   # Aussenkante mind. 20 cm vor und 15 cm ueber dem Wandanschluss (sonst ist es dieselbe Kante/ein Sehstrahl-Abbild)
EL_STIRN = 50.0              # Stirn-Unterkante nur aus Fotos flacher als 50 Grad (steiler sieht man die Untersicht, die Stirn verkuerzt)
STIRN_STARK = 1.8            # Spitze in der Stirnspalte mind. 1,8 x Spaltenmedian
STIRN_MIN_M = 0.08           # ohne gemessene Unterkante: Stirn nur Druckmindestmass (0,92 mm bei 1:87), keine erfundene Brettbreite
SEITEN = ("-d", "+d", "-n", "+n")


def rahmen(D, seite):
    """Seite -> (e Normale nach aussen, t entlang der Seite, h Abstand Achse-Wandebene, hl halbe Seitenlaenge) im Rahmen des Dachprofils."""
    d = np.asarray(D["d"], float); n = np.asarray(D["n"], float); wh = D["wand_halb"]
    e = {"-d": -d, "+d": d, "-n": -n, "+n": n}[seite]; t = np.array([-e[1], e[0]])
    return e, t, float(wh[0] if "d" in seite else wh[1]), float(wh[1] if "d" in seite else wh[0])


def gitter(z0):
    A = np.round(np.arange(A_BEREICH[0], A_BEREICH[1] + 1e-9, RASTER), 3); Z = np.round(np.arange(z0 + Z_BEREICH[0], z0 + Z_BEREICH[1] + 1e-9, RASTER), 3); return A, Z


def foto_karte(grau, proj, o, e, t, h, hl, A, Z, ns=60):
    """Ein Foto: (m, sg) je Hypothese (a, z) - m = |mittlerer Quergradient| / Texturmass, sg = mit Vorzeichen (negativ = oben dunkler); None ohne Deckung.
    grau: Grauwertbild; proj(X) -> (pixel (n,2) im Bild, tiefe)."""
    import cv2
    from scipy.ndimage import map_coordinates
    g = cv2.GaussianBlur(grau.astype(np.float32), (0, 0), 1.2); gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    S = np.linspace(-ANTEIL * hl, ANTEIL * hl, ns); AA, ZZ = np.meshgrid(A, Z, indexing="ij")
    P = (o + (h + AA[..., None]) * e)[..., None, :] + S[None, None, :, None] * t
    X = np.concatenate([P, np.broadcast_to(ZZ[..., None, None], P.shape[:-1] + (1,))], -1).reshape(-1, 3)
    q, zc = proj(X); Xo = X.copy(); Xo[:, 2] += 0.05; qo, _ = proj(Xo)
    if (zc <= 0.3).any(): return None
    nv = qo - q; nv /= np.maximum(np.linalg.norm(nv, axis=1, keepdims=True), 1e-9)
    H, W = grau.shape[:2]; ins = (q[:, 0] > 2) & (q[:, 0] < W - 3) & (q[:, 1] > 2) & (q[:, 1] < H - 3)
    cc = [q[:, 1], q[:, 0]]; vx = map_coordinates(gx, cc, order=1, mode="nearest"); vy = map_coordinates(gy, cc, order=1, mode="nearest")
    r = ((vx * nv[:, 0] + vy * nv[:, 1]) * ins).reshape(len(A), len(Z), ns); mag = np.hypot(vx, vy)[ins]; ins = ins.reshape(r.shape)
    dk = ins.mean(-1) >= DECKUNG
    if not dk.any() or mag.size == 0: return None
    sg = r.sum(-1) / np.maximum(ins.sum(-1), 1) / (float(mag.mean()) + 1e-6); sg[~dk] = 0.0
    return np.abs(sg).astype(np.float32), sg.astype(np.float32)


def _summe(M, k):
    anz = (M[k] > 0).sum(0); S = M[k].sum(0) / np.maximum(anz, 1); return S * (anz >= max(MIN_HALB, 0.3 * max(int(anz.max()), 1)))


def _spitze(S, A, Z, ma, mz):
    """Staerkster Punkt in der Maske (Achsen a, z) -> (i, j, wert) oder None."""
    W = np.where(np.outer(ma, mz), S, -1.0); i, j = np.unravel_index(int(np.argmax(W)), W.shape)
    return (int(i), int(j), float(W[i, j])) if W[i, j] > 0 else None


def _bestaetigt(M, k, A, Z, a0, z0):
    """Sieht die Fotoauswahl k (eine Hoehenwinkel-Haelfte) die Kante (a0, z0)? Eine Haelfte allein legt nur einen Sehstrahl-Kamm fest (Spitze laeuft entlang des
    Kamms, synthetisch bis 0,4 m) - verlangt wird darum: der Kamm geht durch den Punkt (Maximum im Fenster +-TOL >= STARK x Median der Teilkarte und >= KAMM x
    Maximum im Fenster +-2 TOL). Der Punkt selbst kommt aus der Summenkarte = Schnitt der Kaemme beider Haelften (Triangulation)."""
    if k.sum() < MIN_HALB: return False, None
    S = _summe(M, k); v = S[S > 0]
    if v.size == 0: return False, None
    p = _spitze(S, A, Z, np.abs(A - a0) <= TOL_A, np.abs(Z - z0) <= TOL_Z); g = _spitze(S, A, Z, np.abs(A - a0) <= 2 * TOL_A, np.abs(Z - z0) <= 2 * TOL_Z)
    if p is None or g is None: return False, None
    ok = p[2] >= STARK * float(np.median(v)) and p[2] >= KAMM * g[2]
    return bool(ok), [round(float(A[p[0]]), 2), round(float(Z[p[1]]), 2), round(p[2] / float(np.median(v)), 2), round(p[2] / g[2], 2)]


def auswerten(A, Z, M, SG, EL, min_fotos=MIN_FOTOS):
    """Reine Auswertung (fuer den Test): M, SG (fotos, na, nz), EL Hoehenwinkel je Foto -> dict Ergebnis der Seite."""
    M = np.asarray(M, float); SG = np.asarray(SG, float); EL = np.asarray(EL, float); A = np.asarray(A, float); Z = np.asarray(Z, float)
    erg = dict(fotos=int(len(EL)), gueltig=False)
    if len(EL) < min_fotos: erg["grund"] = f"nur {len(EL)} Fotos mit Deckung (verlangt {min_fotos})"; return erg
    alle = np.ones(len(EL), bool); S = _summe(M, alle); v = S[S > 0]
    if v.size == 0: erg["grund"] = "keine Hypothese in genug Fotos"; return erg
    med = float(np.median(v)); lo = EL <= np.median(EL); hi = ~lo
    if hi.sum() < MIN_HALB or float(np.median(EL[hi]) - np.median(EL[lo])) < EL_SPANNE:
        erg["grund"] = f"Hoehenwinkel zu einheitlich ({np.median(EL[lo]):.0f} / {np.median(EL[hi]) if hi.any() else 0:.0f} Grad, verlangt {EL_SPANNE:.0f} Grad Abstand) - keine Triangulation"; return erg
    w = _spitze(S, A, Z, A <= 0.8, np.ones(len(Z), bool))
    if w is None or w[2] < STARK * med: erg["grund"] = f"kein Wandanschluss (staerkste Kante {0 if w is None else w[2] / med:.1f} x Median, verlangt {STARK})"; return erg
    a_w, z_w = float(A[w[0]]), float(Z[w[1]])
    # Kandidaten vor dem Wandanschluss: lokale Spitzen (Fenster +-TOL_A / +-TOL_Z), >= STARK x Median. AUSSENKANTE = die HOECHSTE davon, die in beiden Fotohaelften
    # wiederkehrt (die Traufkante ist die oberste waagrechte Kante vor der Wand; die staerkste ist oft die Stirn-Unterkante, synthetisch Stirn hell / Untersicht dunkel).
    from scipy.ndimage import maximum_filter
    ma = A >= a_w + AUSSEN_MIN_A; mzr = (Z >= z_w + AUSSEN_MIN_Z) & (Z <= z_w + 3.0)
    Sr = np.where(np.outer(ma, mzr), S, 0.0); fen = (2 * int(round(TOL_A / RASTER)) + 1, 2 * int(round(TOL_Z / RASTER)) + 1)
    kand = sorted([(float(Z[j]), int(i), int(j)) for i, j in zip(*np.nonzero((Sr == maximum_filter(Sr, size=fen)) & (Sr >= STARK * med)))], reverse=True)
    bw = [_bestaetigt(M, k, A, Z, a_w, z_w) for k in (lo, hi)]
    erg.update(a_wand=round(a_w, 2), z_wand=round(z_w, 2), el_bereich=[round(float(EL.min())), round(float(EL.max()))], kandidaten=[[round(float(A[i]), 2), round(z, 2), round(float(S[i, j]) / med, 2)] for z, i, j in kand[:8]])
    if not all(b[0] for b in bw): erg["grund"] = f"Wandanschluss nicht in beiden Fotohaelften (flach/steil) an derselben Stelle ({[b[1] for b in bw]})"; return erg
    au = None; bo = None
    for z, i, j in kand:
        b_ = [_bestaetigt(M, k, A, Z, float(A[i]), z) for k in (lo, hi)]
        if all(b[0] for b in b_): au, bo = (i, j, float(S[i, j])), b_; break
    if au is None: erg["grund"] = f"keine in beiden Fotohaelften bestaetigte Aussenkante vor dem Wandanschluss ({len(kand)} Kandidaten >= {STARK} x Median)"; return erg
    a_o, z_o = float(A[au[0]]), float(Z[au[1]])
    erg.update(a_aussen=round(a_o, 2), z_oben=round(z_o, 2), staerke=dict(wand=round(w[2] / med, 2), aussen=round(au[2] / med, 2)), haelften=dict(wand=[b[1] for b in bw], aussen=[b[1] for b in bo]),
               zeichen=dict(wand=round(float(np.mean(SG[:, w[0], w[1]][M[:, w[0], w[1]] > 0])), 2), aussen=round(float(np.mean(SG[:, au[0], au[1]][M[:, au[0], au[1]] > 0])), 2)))
    # Stirn-Unterkante: (1) bestaetigter Kandidat unter der Aussenkante in derselben Spalte (+-TOL_A); (2) sonst Spalte a_o in den flachen Fotos (Stirn von vorn gesehen)
    z_u = None; st = None
    for z, i, j in kand:
        if z < z_o - 0.1 and abs(float(A[i]) - a_o) <= TOL_A and all(_bestaetigt(M, k, A, Z, float(A[i]), z)[0] for k in (lo, hi)): z_u = z; st = dict(z=round(z, 2), aus="Kandidat 2D", staerke=round(float(S[i, j]) / med, 2)); break
    fl = EL < EL_STIRN; ia = np.abs(A - a_o) <= RASTER * 1.01; mz = (Z > z_w + AUSSEN_MIN_Z) & (Z < z_o - 0.1)
    if z_u is None and fl.sum() >= 2 * MIN_HALB and mz.sum() >= 3:
        Sf = _summe(M, fl); col = Sf[ia][:, mz].max(0)
        if (col > 0).all():
            j = int(np.argmax(col)); r = col[j] / float(np.median(col)); zc = float(Z[mz][j]); st = dict(z=round(zc, 2), aus="Spalte flache Fotos", staerke=round(r, 2))
            if 0 < j < len(col) - 1 and r >= STIRN_STARK:
                fm = np.median(EL[fl]); hb = [_bestaetigt(M[:, ia], k, A[ia], Z, a_o, zc)[0] for k in (fl & (EL <= fm), fl & (EL > fm))]
                st["haelften"] = hb
                if all(hb): z_u = zc
    erg["stirn_suche"] = st
    z_ue = z_u if z_u is not None else z_o - STIRN_MIN_M
    erg.update(gueltig=True, grund=None, z_unten=None if z_u is None else round(z_u, 2), z_unten_bau=round(z_ue, 2), ueberstand=round(a_o - a_w, 2), stirn_m=None if z_u is None else round(z_o - z_u, 2),
               untersicht_grad=round(math.degrees(math.atan2(z_ue - z_w, a_o - a_w)), 1), stirn_gemessen=z_u is not None)
    return erg


def kameras_seite(cams, o, e, h, z0, t=None, hl=None):
    """Kameras vor der Seite im Hoehenwinkelbereich; mit t/hl nur solche, in deren Bild die Enden der Messlinie (Wandebene, z0 und z0+1,5) liegen
    (vorher fielen am Schwabentor 75 von 120 geladenen Fotos erst nach dem Laden mangels Deckung weg)."""
    import flaeche_ortho as FO
    out = []
    for nr, (c, pf) in sorted(cams.items()):
        _, _, C = FO.projektion(np.array([[o[0], o[1], z0]]), c); vor = float((C[:2] - o) @ e) - h
        if vor < VOR_MIN_M: continue
        el = math.degrees(math.atan2(z0 - float(C[2]), vor))
        if not EL_MIN < el < EL_MAX: continue
        if t is not None:
            W0, H0 = (c["bild"] if c.get("bild") else (c["cx"] * 2, c["cy"] * 2))
            X = np.array([[*(o + h * e + s * ANTEIL * hl * t), z] for s in (-1, 1) for z in (z0, z0 + 1.5)]); q, zc, _ = FO.projektion(X, c)
            if (zc <= 0.3).any() or (q[:, 0] < 0).any() or (q[:, 0] > W0).any() or (q[:, 1] < 0).any() or (q[:, 1] > H0).any(): continue
        out.append((nr, c, pf, vor, el))
    return out


KANTE_MIN_PUNKTE = 20        # Stirn-Unterkante aus der Kantenstufe: Spitze mind. 20 triangulierte Punkte (Einzelstrahlen/Rauschen geben 1-5 je 4-cm-Scheibe)
KANTE_DECKUNG = 0.5          # ... ueber mind. 50 % der 0,5-m-Abschnitte der mittleren Seite verteilt (waagrechte LINIE, kein Haufen an einer Stelle)
KANTE_REFS = 3               # ... aus mind. 3 Referenzfotos (Formfamilie)


def stirn_aus_kanten(P, ref, D, seite, E, scheibe=RASTER):
    """STIRN-UNTERKANTE aus den triangulierten 3D-Kanten der Kantenstufe (24.11.2026, Befund Hoehen-Angleich 1122 Nord: ohne aufgeloeste Unterkante ANNAHME
    'Untersicht in Raehmhoehe', Modell-Stirn 36,7-38,1 m gegen Wolke 37,55-38,15). Seit der Traufzone der Kantenstufe (sweep.npz reicht bis Dachfuss + 1 m)
    gibt es dort Kanten: Spalte a_aussen +-TOL_A, mittlere ANTEIL der Seite, z zwischen Wandanschluss + AUSSEN_MIN_Z und Aussenkante - 0,1 m.
    Spitze des z-Histogramms (4-cm-Scheiben, +-1 Nachbar) gilt, wenn sie (a) >= KANTE_MIN_PUNKTE und >= STARK x mittlere Scheibe der Spalte, (b) als LINIE ueber
    >= KANTE_DECKUNG der 0,5-m-Abschnitte und (c) aus >= KANTE_REFS tragenden Referenzfotos (je >= 3 Punkte und >= 5 % der Spitze; Linie/Deckung nur aus diesen). Liefert (z oder None, Beleg-dict)."""
    if not E.get("gueltig") or E.get("a_aussen") is None or P is None or not len(P): return None, dict(grund="keine Kantenpunkte/keine gueltige Aussenkante")
    o = np.asarray(D["o"], float); e, t, h, hl = rahmen(D, seite); q = P[:, :2] - o; a = q @ e - h; s = q @ t
    z_lo, z_hi = float(E["z_wand"]) + AUSSEN_MIN_Z, float(E["z_oben"]) - 0.1
    k = (np.abs(a - float(E["a_aussen"])) <= TOL_A) & (np.abs(s) <= ANTEIL * hl) & (P[:, 2] > z_lo) & (P[:, 2] < z_hi)
    b = dict(spalte_punkte=int(k.sum()), z_bereich=[round(z_lo, 2), round(z_hi, 2)])
    if z_hi - z_lo < 3 * scheibe or k.sum() < KANTE_MIN_PUNKTE: return None, dict(b, grund=f"zu wenig Kantenpunkte in der Stirnspalte ({int(k.sum())})")
    zk = P[k, 2]; sk = s[k]; rk = np.asarray(ref)[k]; kanten_ = np.arange(z_lo, z_hi + scheibe, scheibe); hz, _ = np.histogram(zk, bins=kanten_)
    h3 = np.convolve(hz, np.ones(3, int), "same"); j = int(np.argmax(h3)); zc = float(kanten_[j] + 0.5 * scheibe); mittel = 3.0 * float(hz.mean())
    w = np.abs(zk - zc) <= 1.5 * scheibe; ur, uc = np.unique(rk[w], return_counts=True); trag = ur[uc >= max(3, 0.05 * w.sum())]   # tragende Referenzen (Einzelpunkte = Rauschen)
    w &= np.isin(rk, trag); ab = np.arange(-ANTEIL * hl, ANTEIL * hl + 1e-9, 0.5); nb_ = max(len(ab) - 1, 1)
    hb, _ = np.histogram(sk[w], bins=ab); deck = float((hb >= max(2, 0.2 * w.sum() / nb_)).sum()) / nb_          # Abschnitt zaehlt ab 20 % der Gleichverteilung (Streupunkte nicht)
    nref = len(trag); b.update(z=round(zc, 2), punkte=int(h3[j]), staerke=round(float(h3[j]) / max(mittel, 1e-9), 2), deckung=round(min(deck, 1.0), 2), refs=nref)
    if h3[j] < KANTE_MIN_PUNKTE or h3[j] < STARK * mittel: return None, dict(b, grund=f"keine ausgepraegte Spitze ({int(h3[j])} Punkte, {b['staerke']} x Mittel, verlangt {KANTE_MIN_PUNKTE} / {STARK})")
    if deck < KANTE_DECKUNG: return None, dict(b, grund=f"Spitze ist keine Linie entlang der Seite (Deckung {deck:.2f} < {KANTE_DECKUNG})")
    if nref < KANTE_REFS: return None, dict(b, grund=f"nur {nref} Referenzfotos (verlangt {KANTE_REFS})")
    return zc, b


def stirn_einsetzen(E, z_u, beleg):
    """Gemessene Stirn-Unterkante (aus stirn_aus_kanten) in das Seitenergebnis uebernehmen - nur wenn die 2D-Suche keine hatte."""
    if z_u is None or E.get("z_unten") is not None: return E
    E = dict(E, z_unten=round(z_u, 2), z_unten_bau=round(z_u, 2), stirn_m=round(float(E["z_oben"]) - z_u, 2), stirn_gemessen=True,
             untersicht_grad=round(math.degrees(math.atan2(z_u - float(E["z_wand"]), float(E["a_aussen"]) - float(E["a_wand"]))), 1),
             unterkante_quelle=f"Fotokanten der Kantenstufe (sweep.npz, Traufzone): {beleg.get('punkte')} Punkte, {beleg.get('refs')} Referenzfotos, Deckung {beleg.get('deckung')}")
    return E


def kanten_laden(pfad):
    """sweep.npz der Kantenstufe -> (P, ref) oder (None, None)."""
    try: Z = np.load(pfad); return Z["P"].astype(float), Z["ref"]
    except Exception: return None, None


def umgang_anpassen(E, U):
    """Offener Umgang unter der Traufe (audit/umgang_auto.json, tools/umgang_aus_fotos.py: Zone aus Zeilenkanten der entzerrten Fotos): der Traufkasten darf den
    Laufgang nicht fuellen. Der helle->dunkle Wandanschluss der Traufmessung ist dann die UNTERKANTE DES UMGANGS (Schwabentor: Kante z 36,18, Umgang 35,92..36,97),
    die Untersicht beginnt an der Wand erst ueber dem Raehm (z1). Ohne gemessene Stirn-Unterkante: Untersicht waagrecht in Raehmhoehe (ANNAHME, im Block)."""
    if not E.get("gueltig") or not (U or {}).get("gefunden") or U.get("z1") is None: return E
    z1 = float(U["z1"])
    if not (E["z_wand"] - 0.4 <= z1 <= E["z_oben"] - STIRN_MIN_M): return E                  # Umgang nicht unter dieser Traufe
    E = dict(E, z_wand_bau=round(max(E["z_wand"], z1), 2), umgang_z1=round(z1, 2))
    if E.get("z_unten") is None:
        E.update(z_unten_bau=E["z_wand_bau"], untersicht_grad=0.0, unterkante_quelle=f"ANNAHME: Stirn-Unterkante nicht aus Kanten aufgeloest - Untersicht waagrecht in Raehmhoehe des Umgangs (z1 {z1:.2f}, audit/umgang_auto.json)")
    return E


def seite_messen(D, seite, cams, max_fotos, log=print):
    import cv2, flaeche_ortho as FO
    o = np.asarray(D["o"], float); z0 = float(D["z0"]); e, t, h, hl = rahmen(D, seite); A, Z = gitter(z0)
    kw = sorted(kameras_seite(cams, o, e, h, z0, t, hl), key=lambda x: x[4])
    if len(kw) > max_fotos: kw = [kw[int(i)] for i in np.round(np.linspace(0, len(kw) - 1, max_fotos))]
    Ms, SGs, EL, NR = [], [], [], []
    for nr, c, pf, vor, el in kw:
        im = cv2.imread(pf, cv2.IMREAD_REDUCED_GRAYSCALE_2)
        if im is None: continue
        W0, H0 = (c["bild"] if c.get("bild") else (c["cx"] * 2, c["cy"] * 2)); sx, sy = im.shape[1] / W0, im.shape[0] / H0
        def proj(X, c=c, sx=sx, sy=sy):
            q, zc, _ = FO.projektion(X, c); return q * [sx, sy], zc
        r = foto_karte(im, proj, o, e, t, h, hl, A, Z)
        if r is None: continue
        Ms.append(r[0]); SGs.append(r[1]); EL.append(el); NR.append(nr)
    log(f"  {seite}: {len(kw)} Kameras vor der Seite, {len(Ms)} mit Deckung")
    if not Ms: return dict(fotos=0, gueltig=False, grund="keine Kamera sieht die Traufe dieser Seite"), None
    E = auswerten(A, Z, np.array(Ms), np.array(SGs), np.array(EL)); E["einzel"] = NR[:400]
    return E, dict(A=A, Z=Z, S=_summe(np.array(Ms, float), np.ones(len(Ms), bool)), NR=NR, EL=EL)


def bild(aus, D, karten, ergebnisse, cams):
    """Pruefbild: je Seite die Summenkarte (a nach rechts, z nach oben; rot Wandanschluss, gruen Aussenkante, blau Stirn-Unterkante) und zwei Fotoausschnitte
    (flachstes und steilstes Foto mit Deckung) mit den gemessenen Kanten als Linien."""
    import cv2, flaeche_ortho as FO
    zeilen = []
    for seite, K in karten.items():
        E = ergebnisse[seite]; S = K["S"]; A, Z = K["A"], K["Z"]
        im = (255 * S / max(float(S.max()), 1e-6)).astype(np.uint8).T[::-1]; im = cv2.resize(cv2.applyColorMap(im, cv2.COLORMAP_JET), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        P_ = lambda a, z: (int((a - A[0]) / RASTER * 3 + 1), int((Z[-1] - z) / RASTER * 3 + 1))
        for k_, col in ((("a_wand", "z_wand"), (0, 0, 255)), (("a_aussen", "z_oben"), (0, 255, 0)), (("a_aussen", "z_unten"), (255, 0, 0)), (("a_aussen", "z_unten_bau" if E.get("z_unten") is None else "_"), (0, 165, 255))):
            if E.get(k_[0]) is not None and E.get(k_[1]) is not None: cv2.circle(im, P_(E[k_[0]], E[k_[1]]), 7, col, 2)
        cv2.putText(im, f"{seite} {'GUELTIG' if E.get('gueltig') else 'ungueltig'} n{E.get('fotos')}", (4, 16), 0, 0.5, (255, 255, 255), 1)
        kach = [im]; o = np.asarray(D["o"], float); e, t, h, hl = rahmen(D, seite)
        for nr in ([K["NR"][int(np.argmin(K["EL"]))], K["NR"][int(np.argmax(K["EL"]))]] if K["NR"] else []):
            c, pf = cams[nr]; f = cv2.imread(pf)
            if f is None: continue
            W0 = c["bild"][0] if c.get("bild") else c["cx"] * 2; s = f.shape[1] / W0; pts = []
            Ss = np.linspace(-hl, hl, 40)
            for k_, col in ((("a_wand", "z_wand"), (0, 0, 255)), (("a_aussen", "z_oben"), (0, 255, 0)), (("a_aussen", "z_unten"), (255, 0, 0)), (("a_aussen", "z_unten_bau" if E.get("z_unten") is None else "_"), (0, 165, 255))):
                if E.get(k_[0]) is None or E.get(k_[1]) is None: continue
                X = np.c_[o + (h + E[k_[0]]) * e + Ss[:, None] * t, np.full(len(Ss), E[k_[1]])]; q = FO.projektion(X, c)[0] * s; pts += list(q)
                cv2.polylines(f, [q.astype(np.int32)], False, col, max(2, f.shape[1] // 900))
            if not pts: continue
            P = np.array(pts); r = max(80, int(0.6 * np.ptp(P[:, 1]) + 60)); x0, y0 = np.maximum(P.min(0) - r, 0).astype(int); x1, y1 = (P.max(0) + r).astype(int)
            cr = f[y0:min(y1, f.shape[0]), x0:min(x1, f.shape[1])]
            if cr.size == 0: continue
            cr = cv2.resize(cr, (max(1, int(cr.shape[1] * im.shape[0] / cr.shape[0])), im.shape[0])); cv2.putText(cr, nr[-22:], (4, 16), 0, 0.5, (255, 255, 0), 1); kach.append(cr)
        z_ = np.hstack(kach); zeilen.append(z_)
    if not zeilen: return
    b = max(z.shape[1] for z in zeilen); out = np.vstack([np.pad(z, ((0, 0), (0, b - z.shape[1]), (0, 0)), constant_values=255) for z in zeilen])
    if out.shape[1] > 2400: out = cv2.resize(out, None, fx=2400 / out.shape[1], fy=2400 / out.shape[1])
    cv2.imwrite(aus, out, [cv2.IMWRITE_JPEG_QUALITY, 85]); print("Bild:", aus)


def main(argv=None):
    import flaeche_ortho as FO
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--profil"); ap.add_argument("--aus"); ap.add_argument("--bild"); ap.add_argument("--max-fotos", type=int, default=120)
    ap.add_argument("--seiten", default=",".join(SEITEN)); ap.add_argument("--nur-messen", action="store_true"); ap.add_argument("--root", help="Projektwurzel fuer fotos_dir (Standard: Repo)")
    ap.add_argument("--kanten", help="sweep.npz der Kantenstufe (Standard <daten>/<objekt>/kanten/sweep.npz) fuer die Stirn-Unterkante")
    a = ap.parse_args(argv)
    od = os.path.dirname(os.path.abspath(a.objekt)); Au = os.path.join(od, "audit"); pp = a.profil or os.path.join(Au, "dach_profil.json")
    try: D = json.load(open(pp))
    except Exception: print("kein Dachprofil", pp); return 3
    if not all(k in D for k in ("o", "d", "n", "wand_halb", "z0")): print("Dachprofil ohne Rahmen"); return 3
    if a.root: FO.ROOT = a.root
    obj, cams = FO.kameras_laden(a.objekt); print(f"{len(cams)} Kameras; Rahmen z0 {D['z0']:.2f}, Wand halb {D['wand_halb'][0]:.2f} x {D['wand_halb'][1]:.2f}")
    erg, karten = {}, {}
    try: U = json.load(open(os.path.join(Au, "umgang_auto.json")))
    except Exception: U = None
    kp = a.kanten
    if not kp:
        import pfade; kp = os.path.join(pfade.DATEN, os.path.basename(od), "kanten", "sweep.npz")
    KP, KR = kanten_laden(kp); print(f"Kantenstufe: {kp} ({'keine' if KP is None else len(KP)} Punkte)")
    for s in a.seiten.split(","):
        E, K = seite_messen(D, s, cams, a.max_fotos)
        if E.get("gueltig") and E.get("z_unten") is None:                       # 24.11.2026: Stirn-Unterkante aus den 3D-Kanten der Traufzone statt ANNAHME
            zk, bk = stirn_aus_kanten(KP, KR, D, s, E); E["stirn_kanten"] = bk; E = stirn_einsetzen(E, zk, bk)
        E = umgang_anpassen(E, U); erg[s] = E
        if K: karten[s] = K
        print(f"  {s}: " + (f"GUELTIG Wandanschluss a {E['a_wand']:+.2f} z {E['z_wand']:.2f}, Aussenkante a {E['a_aussen']:+.2f} z {E['z_oben']:.2f} -> Ueberstand {E['ueberstand']:.2f} m, "
                             f"Stirn {'%.2f m' % E['stirn_m'] if E.get('stirn_m') else 'Unterkante nicht aufgeloest'}, Untersicht {E['untersicht_grad']} Grad (Staerke {E['staerke']})"
                             + (f"; Umgang darunter (z1 {E['umgang_z1']}): Kasten ab z {E['z_wand_bau']}" if E.get("umgang_z1") is not None else "") if E.get("gueltig") else f"ungueltig: {E.get('grund')}"))
    gs = [s for s, E in erg.items() if E.get("gueltig")]
    B = dict(quelle="tools/traufe_aus_fotos.py: Kanten-Tiefen-Sweep waagrechter Traufkanten in den kalibrierten Fotos (Rahmen/Wandebene aus dach_profil.json)", seiten=erg, gueltige_seiten=gs,
             gueltig=bool(gs), a_bezug="a = Abstand vor der Wandebene wand_halb des Dachprofils (m); ueberstand = Aussenkante - Wandanschluss (beide aus Fotos)",
             annahmen=["Traufkanten waagrecht und parallel zur Seite (Zeltdach)", "Stirn senkrecht unter der Aussenkante", "ohne gemessene Stirn-Unterkante: Untersicht = Ebene Wandanschluss -> Aussenkante, Stirn nur Druckmindestmass "
                       f"{STIRN_MIN_M} m", "mit offenem Umgang darunter (audit/umgang_auto.json): Kasten erst ueber dem Raehm (z1), ohne gemessene Stirn-Unterkante Untersicht waagrecht in Raehmhoehe", "Seiten ohne gueltige Fotomessung: Traufe weiter aus Wolke/DOM1 (nicht gespiegelt, nicht erfunden)"])
    try: bild(a.bild or os.path.join(Au, "traufe_foto.jpg"), D, karten, erg, cams)
    except Exception as ex: print("Bild fehlgeschlagen:", ex)
    if not a.nur_messen:
        D["traufe_foto"] = B; ap_ = a.aus or pp; json.dump(D, open(ap_, "w"), indent=1); print("->", ap_, "(Block traufe_foto)")
    print(f"gueltige Seiten: {gs or 'keine'}")
    return 0 if gs else 4


if __name__ == "__main__": sys.exit(main())
