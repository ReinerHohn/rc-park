#!/usr/bin/env python3
"""drahtmaske.py - DETEKTOR fuer Oberleitungen/Spanndraehte in EINEM Foto (nur cv2 + numpy, CPU, ~1 s je 12-MP-Foto). Rueckgabe: Maske 255 = Draht.

ANLASS 24.11.2026 (Kette schwabentor 1122x): Strassenbahn-Oberleitung und Spanndraehte vor dem Schwabentor landen in der dichten Wolke als schraege 'Fahnen'
(0,8 x 4 m, entlang der Sichtstrahlen verschmiert); der Wolken-Nachfilter (wolke_draehte.py) trennt nah an der Wand nicht. Ursache sitzt in den FOTOS: duenne
dunkle Linien vor Himmel und Wand werden in PatchMatch gematcht, erscheinen im Wandbild als Striche und stoeren die Kantenstufe.
Verbraucher (tools/drahtmasken.py): Fusion der dichten Wolke (mask_path), fassade_ortho (Pixel tragen nicht bei), stabil_alle (Kanten auf Drahtpixeln weg).

ERKENNUNG (generisch, keine Objektwerte; Arbeitsmassstab lange Seite <= 2000 px):
  1. DUENN + DUNKEL: Black-Hat (Schliessen - Bild) mit Kern 9 px misst Linien bis ~7 px Breite voll, Kern 21 px auch breitere. Duenn = Antwort(9) >= 0,7 x Antwort(21)
     - Fachwerkbalken, Fensterrahmen-Schatten, Dachrinnen ab ~8 px fallen hier heraus; Stufenkanten (Gesims, Dachkante, Fensterkante) geben keine Black-Hat-Antwort.
  2. LANGE SEGMENTE: HoughLinesP auf den starken Duennpixeln, dann je Segment die Kurve verfolgen (Polynom Grad 1-2 in Laufrichtung = gerade oder leicht
     durchhaengend, Reste <= 2,5 px), schrittweise verlaengern, Ende nach einer Luecke > 4 % der kurzen Bildseite.
  3. ANNAHME nur, wenn (a) belegte Laenge >= 15 % der kurzen Bildseite, (b) >= 8 % der kurzen Seite davon VOR HIMMEL liegen - Himmel auf BEIDEN Seiten der Linie
     (Himmel = hell, glatt im geschlossenen Bild, Flaeche am Bildrand), (c) die Himmelsstrecke zu >= 75 % lueckenlos belegt ist (Zweige/Antennen sind kurz und krumm).
     ROT-PROBE (tests/test_drahtmaske.py): Fugen, Gesims, Fensterkanten, Dachkanten enden an der Gebaeudeflaeche und laufen nie beidseitig im Himmel.
  4. Maske = angenommene Kurve ueber die ganze belegte Strecke, auch ueber die Wand (dort schwaechere Antwort genuegt), Breite +- 3 px (Arbeitsmassstab).
GRENZE: Draehte, die im Foto nur vor der Wand verlaufen (kein Himmel im Bild), werden nicht erkannt (Rot-Probe geht vor). Helle Draehte vor dunkler Wand ebenso.
Lizenz: nur OpenCV (Apache-2.0) + numpy (BSD)."""
import numpy as np, cv2

ARBEIT_PX = 2000          # lange Seite fuer die Erkennung
K_DUENN, K_BREIT = 9, 21  # Black-Hat-Kerne (Arbeitspixel)
DUENN_VERH = 0.7
STARK, SCHWACH = 22.0, 9.0  # Grauwert-Kontrast (Black-Hat) fuer Saat- und Folgepixel
MIN_LAENGE = 0.15         # Anteil der kurzen Bildseite
MIN_HIMMEL = 0.08
HIMMEL_DICHTE = 0.75
LUECKE = 0.04
RES_PX = 2.5
BIN_PX = 4
# Abstand der Himmels-Fusionsmaske zur Silhouette (Arbeitspixel). himmel() selbst endet schon ~7 px vor jeder starken Kante (Streuung im 15-px-Fenster < 7 bei
# Kontrast >= 60 erst ab ~7 px Abstand), also ausserhalb des PatchMatch-Fensters (COLMAP window_radius 5); 2 px mehr gegen weiche/unscharfe Kanten (JPEG, Dunst).
HIMMEL_RAND_PX = 2
# Wachsen in den Saum (himmelmaske): Farbabstand zur lokalen Himmelsfarbe, Kantensperre, Reichweite (Arbeitspixel). Saum am Beleg 1122z 8-25 px breit.
HIMMEL_TOL, HIMMEL_GRAD, HIMMEL_WACHS = 22.0, 14.0, 40
HIMMEL_BREIT = 41         # Kern = Himmel, in den ein Kreis von 41 Arbeitspixeln passt (~2 % der langen Seite); schmalere helle Baender nur ueber das begrenzte Wachsen


def _kern(k): return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))


def himmel(g, geschlossen, linien, farbe=None):
    """Himmel-Maske im Arbeitsmassstab: hell, glatt (lokale Streuung im geschlossenen Bild klein), WENIG duenne Linien in der Umgebung (Pflaster, Mauerfugen und
    Zweiggewirr sind nach dem Schliessen auch hell und glatt, haben aber dichte Linien; ein Draht belegt im 61-px-Fenster nur ~5 %), am Bildrand, Flaeche >= 0,5 %. Fenster 121 px statt 61: zwei parallele Fahrdraehte gaben im 61er-Fenster 0,13 und loeschten ihren eigenen Himmel."""
    c = geschlossen.astype(np.float32); m = cv2.blur(c, (15, 15)); s = np.sqrt(np.maximum(cv2.blur(c * c, (15, 15)) - m * m, 0))
    dichte = cv2.blur(linien.astype(np.float32), (121, 121))             # gemessen 24.11. (2000 px): Draehte am Himmel 0,03-0,07 (zwei parallele bis 0,13), Pflaster 0,24-0,30, Zweige 0,13-0,43
    kand = ((c > 110) & (s < 7.0) & (dichte < 0.17)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(kand, 8)
    H, W = g.shape; rand = np.zeros(n, bool); oben = np.zeros(n, bool); oben[np.unique(lab[0])] = True
    for r in (lab[0], lab[-1], lab[:, 0], lab[:, -1]): rand[np.unique(r)] = True
    gross = st[:, cv2.CC_STAT_AREA] >= 0.005 * H * W; gross[0] = False
    # OBEREN Bildrand beruehren (24.11. 153641: Quadermauer + Pflaster ohne Himmel - helle Moertelfugen nach dem Schliessen = 'Himmel' am unteren/seitlichen Rand,
    # zwei Fugen-/Pflasterlinien quer durchs Bild) und im UNGESCHLOSSENEN Bild hell (grau >= 170, Bedeckt 200-240; blau >= 120 an jedem Rand)
    cnt = np.maximum(np.bincount(lab.ravel(), minlength=n), 1); roh = np.bincount(lab.ravel(), weights=g.astype(np.float32).ravel(), minlength=n) / cnt
    gut = oben & gross & (roh >= 170)
    if farbe is not None:                                                 # grauer Himmel ist nie roetlich (153641: rosa Sandstein-Pilaster oben am Rand, B-R ~ -30)
        br = np.bincount(lab.ravel(), weights=(farbe[..., 0].astype(np.float32) - farbe[..., 2]).ravel(), minlength=n) / cnt
        gut &= br >= -10
    if gut.any():                                                         # Himmel = die HELLSTEN glatten Flaechen (>= 85 % der hellsten) oder blau; eine glatte Wand
        hell = np.bincount(lab.ravel(), weights=c.ravel(), minlength=n) / cnt   # (Quader/Putz im Schatten) ist dunkler und zaehlt nicht
        gut &= hell >= 0.85 * hell[gut].max()
    if farbe is not None:                                                 # blauer Himmel darf an jedem Rand liegen (Foto gedreht gelesen, IMREAD_IGNORE_ORIENTATION)
        gut |= rand & gross & (br > 20) & (roh >= 120)
    return gut[lab]


def _vorstufe(bild, mit_farbe=False):
    """Gemeinsame Vorstufe von drahtmaske() und himmelmaske(): Arbeitsmassstab s, Grau g, Black-Hat bh1, Duenn-Linien stark/schwach, Himmel (alles Arbeitsmassstab)."""
    H0, W0 = bild.shape[:2]; s = min(1.0, ARBEIT_PX / max(H0, W0))
    g = bild if bild.ndim == 2 else cv2.cvtColor(bild, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (int(round(W0 * s)), int(round(H0 * s))), interpolation=cv2.INTER_AREA) if s < 1 else g.copy()
    H, W = g.shape
    cl1 = cv2.morphologyEx(g, cv2.MORPH_CLOSE, _kern(K_DUENN)); cl2 = cv2.morphologyEx(g, cv2.MORPH_CLOSE, _kern(K_BREIT))
    bh1 = cl1.astype(np.float32) - g; bh2 = cl2.astype(np.float32) - g
    duenn = bh1 >= DUENN_VERH * np.maximum(bh2, 1.0)
    duenn[:4] = duenn[-4:] = False; duenn[:, :4] = duenn[:, -4:] = False   # Bildrand (Randabfall/Vignette gab eine 'Linie' entlang der Kante, 153319)
    stark = (duenn & (bh1 > STARK)).astype(np.uint8); schwach = duenn & (bh1 > SCHWACH)
    fb = None if bild.ndim == 2 else (cv2.resize(bild, (W, H), interpolation=cv2.INTER_AREA) if bild.shape[:2] != (H, W) else bild)
    sky = himmel(g, cl2, schwach, fb)
    return (s, g, bh1, stark, schwach, sky, fb) if mit_farbe else (s, g, bh1, stark, schwach, sky)


def _poly(T, D, grad):
    if len(T) < 6 or np.ptp(T) < 10: return None
    return np.polyfit(T, D, grad)


def drahtmaske(bild, rand_px=0, info=None):
    """bild: BGR- oder Grau-Array beliebiger Groesse. -> uint8-Maske gleicher Groesse (255 = Draht). rand_px = zusaetzliche Aufweitung in Bildpixeln.
    info (dict, optional) bekommt Kandidaten/angenommen/verworfen mit Gruenden (fuer Test und Overlay)."""
    H0, W0 = bild.shape[:2]
    s, g, bh1, stark, schwach, sky = _vorstufe(bild); H, W = g.shape; kurz = min(H, W)
    hs = cv2.dilate((stark.astype(bool) & sky).astype(np.uint8), _kern(11)).astype(bool)
    out = np.zeros((H, W), np.uint8); I = info if info is not None else {}; I.update(kandidaten=0, angenommen=[], verworfen=[])
    segs = cv2.HoughLinesP(stark * 255, 1, np.pi / 360, threshold=max(20, int(0.03 * kurz)), minLineLength=int(0.05 * kurz), maxLineGap=int(0.01 * kurz) + 2)
    if segs is None: return _hoch(out, H0, W0, rand_px)
    segs = np.asarray(segs).reshape(-1, 4).astype(np.float32); segs = segs[np.argsort(-np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1]))][:300]
    yy, xx = np.nonzero(schwach); P = np.stack([xx, yy], 1).astype(np.float32); frei = np.ones(len(P), bool)
    luecke = LUECKE * kurz
    for x1, y1, x2, y2 in segs:
        mx, my = int((x1 + x2) / 2), int((y1 + y2) / 2)
        if out[min(my, H - 1), min(mx, W - 1)]: continue                  # schon von einem angenommenen Draht abgedeckt
        I["kandidaten"] += 1
        d = np.array([x2 - x1, y2 - y1], np.float32); L = float(np.linalg.norm(d)); d /= L; nv = np.array([-d[1], d[0]], np.float32); o = np.array([mx, my], np.float32)
        tt = np.arange(-2 * (H + W), 2 * (H + W), 2.0); xy = o + np.outer(tt, d); inn = (xy[:, 0] >= 0) & (xy[:, 0] < W) & (xy[:, 1] >= 0) & (xy[:, 1] < H)   # Vorprobe (Tempo):
        if hs[xy[inn, 1].astype(int), xy[inn, 0].astype(int)].sum() * 2 < 0.5 * MIN_HIMMEL * kurz:                                   # Gerade trifft kaum Saatpixel im Himmel
            I["verworfen"].append(dict(grund="kaum vor Himmel (endet an Gebaeudeflaeche)", vorprobe=True, mitte_px=[round(mx / s), round(my / s)])); continue
        fi = np.where(frei)[0]; Q = P[fi]; D = (Q - o) @ nv; band = np.abs(D) < 0.08 * kurz + 6      # nur ein Band um die Gerade weiterrechnen (Tempo)
        fi, Q, D = fi[band], Q[band], D[band]; T = (Q - o) @ d
        lo, hi = -L / 2, L / 2; sel = (T >= lo) & (T <= hi) & (np.abs(D) < 3)
        c = _poly(T[sel], D[sel], 1)
        if c is None: continue
        def quer(karte, c_, bins, off):                                  # Karte an den Bins, quer zur Kurve um off px versetzt (Durchhang klein: Querrichtung = nv)
            tb = (bins + 0.5) * BIN_PX; xy = o + np.outer(tb, d) + np.outer(np.polyval(c_, tb) + off, nv)
            inn = (xy[:, 0] >= 0) & (xy[:, 0] < W - 0.5) & (xy[:, 1] >= 0) & (xy[:, 1] < H - 0.5)
            xi = np.clip(np.round(xy[:, 0]).astype(int), 0, W - 1); yi = np.clip(np.round(xy[:, 1]).astype(int), 0, H - 1); return karte[yi, xi] & inn, inn
        def belegt(c_, ok_):
            """Bins mit Linienpixel, deren Umgebung quer (+-5, +-9 px) frei ist (>= 3 von 4): eine EINZELNE Linie. Zweiggewirr, Pflaster, Mauerfugen-Netz fallen heraus."""
            b_ = np.unique(np.floor(T[ok_] / BIN_PX).astype(int))
            if not len(b_): return b_
            frei_ = sum((~quer(schwach, c_, b_, off)[0]).astype(int) for off in (-9, -5, 5, 9)); return b_[frei_ >= 3]
        for _ in range(12):                                               # Kurve schrittweise verlaengern (gerade -> leicht durchhaengend)
            ext = 0.08 * kurz; sel = (T >= lo - ext) & (T <= hi + ext) & (np.abs(D - np.polyval(c, T)) < RES_PX + 1)
            c2 = _poly(T[sel], D[sel], 2 if (hi - lo) > 0.25 * kurz else 1)
            if c2 is None: break
            if len(c2) == 3 and abs(c2[0]) * (0.5 * (hi - lo + 2 * ext)) ** 2 > 0.08 * kurz: c2 = _poly(T[sel], D[sel], 1)   # Durchhang unplausibel gross -> gerade
            c = c2; b = belegt(c, sel & (np.abs(D - np.polyval(c, T)) < RES_PX))
            if not len(b): break
            nlo, nhi = _strecke(b, luecke / BIN_PX)
            nlo, nhi = nlo * BIN_PX, (nhi + 1) * BIN_PX
            if nlo >= lo - 1 and nhi <= hi + 1: lo, hi = min(lo, nlo), max(hi, nhi); break
            lo, hi = min(lo, nlo), max(hi, nhi)
        ok = (T >= lo) & (T <= hi) & (np.abs(D - np.polyval(c, T)) < RES_PX)
        b = belegt(c, ok); beleg = len(b) * BIN_PX
        if not len(b): continue
        # Himmelsprobe je belegtem Abschnitt: beidseitig (+-7 px quer) Himmel
        hb = quer(sky, c, b, 7)[0] & quer(sky, c, b, -7)[0]; n_h = int(hb.sum()) * BIN_PX
        if hb.any():                                                     # Dichte auf der Himmelsstrecke: Anteil belegter Bins unter allen Himmels-Bins zwischen erstem und letztem Beleg
            alle = np.arange(b.min(), b.max() + 1); imb = quer(sky, c, alle, 0)[0]
            dichte = float(np.isin(alle[imb], b).mean()) if imb.any() else 0.0
        else: dichte = 0.0
        rec = dict(laenge=round(beleg / kurz, 3), himmel=round(n_h / kurz, 3), dichte=round(dichte, 2), mitte_px=[round(mx / s), round(my / s)])
        grund = ("zu kurz" if beleg < MIN_LAENGE * kurz else "kaum vor Himmel (endet an Gebaeudeflaeche)" if n_h < MIN_HIMMEL * kurz
                 else "luckenhaft vor Himmel" if dichte < HIMMEL_DICHTE else None)
        if grund: rec["grund"] = grund; I["verworfen"].append(rec); continue
        I["angenommen"].append(rec)
        # Zeichnen: belegte Strecke mit Luecken <= luecke ueberbrueckt
        for a_, e_ in _abschnitte(b, luecke / BIN_PX):
            ta = np.arange(a_ * BIN_PX, (e_ + 1) * BIN_PX + 1, 2.0); da = np.polyval(c, ta); xy = o + np.outer(ta, d) + np.outer(da, nv)
            cv2.polylines(out, [np.round(xy).astype(np.int32).reshape(-1, 1, 2)], False, 255, thickness=7)
        frei[fi[ok]] = False
    return _hoch(out, H0, W0, rand_px)


def himmelmaske(bild, rand_px=HIMMEL_RAND_PX, info=None):
    """HIMMEL fuer die Fusion (24.11.2026, blaues Geisterblatt 1122z): 255 = Himmel in Bildgroesse, bis rand_px Arbeitspixel an die Silhouette heran.
    BELEG (/media/oem/scan/rc-park_tmp/himmel_maske/blatt_kontrolle_*.jpg): die Quellpixel des Blatts liegen im SAUM zwischen himmel() und Turmkante
    (himmel() endet 7-25 px vor jeder Kante: Streuungsfenster + Liniendichte) - PatchMatch gibt diesen Himmelspixeln die Tiefe der Kante (Fenster-Verschleppung),
    in vielen Videobildern gleich -> mehrsichtig 'bestaetigtes' Blatt entlang der Sehstrahlen. Daher:
      1. Kern = himmel() NUR mit Himmelsfarbe: himmel() arbeitet im geschlossenen Bild und nimmt duenne dunkle Dinge (< 21 px: Turmspitze, Blitzableiter, Draht,
         Zweig) mit - die bleiben frei (Draehte maskiert die Drahtmaske).
      1b. Kern geoeffnet (HIMMEL_BREIT): nur flaechiger Himmel; helle glatte Baender (Gesims mit seitlichem Himmelsanschluss) fallen heraus.
      2. WACHSEN in den Saum: Pixel mit Himmelsfarbe (Abstand zur lokalen Himmelsfarbe, 41-px-Mittel nur ueber Himmel, < HIMMEL_TOL) und ohne Kante (morphologischer
         Gradient < HIMMEL_GRAD), mit dem Kern verbunden, hoechstens HIMMEL_WACHS px weit. Die Kante selbst (Gradient hoch) ist die Sperre -> weisse Wand neben
         weissem Himmel waechst nur bis zur Kontur.
      3. rand_px Abstand zu allem Nicht-Himmel: die Silhouette (Dachkante, Turmspitze, Laterne) und die ersten Pixel davor bleiben."""
    H0, W0 = bild.shape[:2]
    s, g, bh1, stark, schwach, sky, fb = _vorstufe(bild, mit_farbe=True)
    f = (fb if fb is not None else g[..., None]).astype(np.float32); grad = cv2.morphologyEx(g, cv2.MORPH_GRADIENT, _kern(3)).astype(np.float32)
    kern = sky.astype(np.uint8); m = kern
    for _ in range(2):                                                    # lokale Himmelsfarbe (41-px-Mittel nur ueber Himmel); 2. Runde ohne die dunklen Pixel,
        kw = kern.astype(np.float32); w = cv2.blur(kw, (41, 41))          # die himmel() im GESCHLOSSENEN Bild mitnimmt (Turmspitze/Draht/Zweig < 21 px)
        ref = cv2.blur(f * kw[..., None], (41, 41)).reshape(f.shape) / np.maximum(w, 1e-6)[..., None]
        farbe = (w > 0.02) & (np.abs(f - ref).max(axis=2) < HIMMEL_TOL); kern = (sky & farbe).astype(np.uint8)
    kern = cv2.morphologyEx(kern, cv2.MORPH_OPEN, _kern(HIMMEL_BREIT))     # nur FLAECHIGER Himmel als Kern: helle glatte Baender (Gesims, Fries), die himmel() ueber
    if kern.any():                                                        # einen seitlichen Himmelsanschluss mitnimmt, sind schmaler (Rot-Probe)
        nah = cv2.dilate(kern, _kern(2 * HIMMEL_WACHS + 1)) > 0
        kand = (farbe & (grad < HIMMEL_GRAD) & nah).astype(np.uint8) | kern
        n, lab = cv2.connectedComponents(kand, connectivity=4)                  # nur mit dem Kern verbundene Saumpixel
        mit = np.zeros(n, bool); mit[np.unique(lab[kern > 0])] = True; mit[0] = False; m = mit[lab].astype(np.uint8)
    if info is not None: info.update(kern=float(kern.mean()), gewachsen=float(m.mean()))
    if rand_px > 0: m = cv2.erode(m, _kern(2 * int(rand_px) + 1))
    return _hoch(m * 255, H0, W0, 0)


def fusionsmaske(bild, rand_px=0):
    """Maske fuer die Fusion der dichten Wolke: Draht (drahtmaske, + rand_px) ODER sicherer Himmel (himmelmaske). 255 = nicht fusionieren."""
    return np.maximum(drahtmaske(bild, rand_px), himmelmaske(bild))


def _abschnitte(b, gap):
    """sortierte Bin-Nummern -> zusammenhaengende Abschnitte (Luecken <= gap ueberbrueckt)."""
    b = np.sort(b); br = np.where(np.diff(b) > gap)[0]; st = np.r_[0, br + 1]; en = np.r_[br, len(b) - 1]
    return [(int(b[i]), int(b[j])) for i, j in zip(st, en)]


def _strecke(b, gap):
    """laengster Abschnitt (Luecken <= gap) -> (erste, letzte Bin-Nummer)."""
    A = _abschnitte(b, gap); a, e = max(A, key=lambda x: x[1] - x[0]); return a, e


def _hoch(m, H0, W0, rand_px):
    if m.shape != (H0, W0): m = cv2.resize(m, (W0, H0), interpolation=cv2.INTER_NEAREST)
    if rand_px > 0: m = cv2.dilate(m, _kern(2 * int(rand_px) + 1))
    return m


def overlay(bild, maske, breite=1500):
    """Kontrollbild: Draht-Maske rot ueber dem Foto (verkleinert)."""
    s = min(1.0, breite / bild.shape[1]); b = cv2.resize(bild, None, fx=s, fy=s, interpolation=cv2.INTER_AREA); m = cv2.resize(maske, (b.shape[1], b.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
    o = b.copy(); o[m] = (0.35 * o[m] + 0.65 * np.array([0, 0, 255])).astype(np.uint8); return o
