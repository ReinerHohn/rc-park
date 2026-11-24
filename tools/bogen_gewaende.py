#!/usr/bin/env python3
"""bogen_gewaende.py - GEWAENDE (Werkstein-Rahmenband) um gebaute Tor-/Bogenoeffnungen aus dem feinen Wandbild (24.11.2026, Kettenstufe 'bauplan' nach oeffnungen_aus_kanten).

Anlass (Kettenlauf 1122w, Schwabentor, audit/neben_detail_oeffnung_bogen_f00/_f01.jpg, neben_sued_w): beide Torboegen haben im Foto ein deutlich abgesetztes
Sandstein-Gewaende (Bogensteine als Ring um den Spitzbogen, glatter als die Bruchsteinquader), im Modell nur ein glattes Loch. Ursache: bauteile.oeffnungen_aus_json
schneidet nur das Loch; das 'gewaende' aus oeffnungen_aus_kanten ist nur der Abstand Aussen-/Innenkante (Fase, 0,12-0,15 m) und wird nicht gebaut;
loch_gewaende.py behandelt nur Fenster/geschlossene Tueren (dunkles Loch), nie gebaute Durchblicke.
Methode (WANDBILD = BAUPLAN, keine Musterteile, keine generierten Bogensteine): je gebauter Oeffnung in audit/oeffnungen_auto.json
  1. ABROLLEN: der lichte Umriss (bogen_querschnitt wie im Bau) wird in 1-cm-Schritten abgegangen, je Punkt die Aussennormale; das Wandbild wird entlang der Normalen
     0..dmax m abgetastet -> Streifen S[d, s] (Zeile = Abstand vom Loch, Spalte = Weg entlang des Umrisses).
  2. BAND im Bogen/Sturz (Umrissteil ueber dem Kaempfer): die Bogensteine laufen RADIAL ueber die ganze Bandbreite - jede Streifenzeile im Band zeigt dieselben
     Stossfugen (Zeilenkorrelation hoch), ausserhalb liegen die Lagerfugen des Mauerwerks quer dazu (Korrelation ~0). Kernzeile r0 = Zeile mit der hoechsten
     Korrelation zu ihren +-10-cm-Nachbarn; Band = zusammenhaengende Zeilen mit Korrelation zur Kernzeile >= --schwelle; Aussenkante b = erste Zeile darunter.
     GUARD: Kontrast (Band gegen 5-30 cm ausserhalb) >= --kontrast, Bandbreite >= 0,08 m, b <= dmax - 0,3; sonst kein Band (Grund im Bericht).
  3. PFOSTEN: die Pfostensteine sind mit dem Mauerwerk verzahnt (Lagerfugen laufen durch) - im Wandbild nicht trennbar (gemessen 1122w: Kante je Spalte streut
     0,1-0,7 m). Breite = Bogenband (ANNAHME im Eintrag).
  4. VORSPRUNG: Tiefe je Zelle (fassade/tiefe_<fid>.npz, w positiv = vor der Wand): Median im Band gegen Median im Wandring b+0,1..b+0,4; plausibel 0,01-0,30 m,
     sonst ANNAHME Druckmindestmass (MINMM x SCALE).
  5. FUGEN (24.11.2026, Nutzer: Fugen zwischen den Bogensteinen sehen; Regel 15.11. bleibt: Bogensteine NIE generieren): je Einzelfoto-Ortho (ortho_<fid>_einzeln,
     auf das Wandbild ausgerichtet: Ring-NCC, dann Restversatz entlang des Bogens) im Band innen..aussen schmale RADIALE Linien (hell = Kalkmoertel oder dunkel,
     beide Seiten anders als die Mitte - keine Stufenkante, >= 60 % der Bandzeilen). Fuge gilt nur mit Mehrfoto-Beleg (>= 3 Fotos und >= 40 % der sehenden, +- 3 cm),
     Kopien desselben Bilds (Download + Original, Serienbild, Streifen-Korrelation >= 0,85) zaehlen einmal. Keine Teilung, kein Mittelwert: jede Fuge an ihrer
     gemessenen Stelle, unbelegte Abschnitte bleiben glatt. 1122 Schwabentor: f00 21, f01 22 Fugen aus 20/29 Fotos; Sichtzaehlung am Foto je ~19-20 Steine.
Ausgabe: oeffnungen_auto.json bekommt je gebauter Oeffnung 'gewaende_band' {aussen (m vom lichten Umriss), innen, vorsprung, *_quelle, kontrast, ...} und, wenn
  belegt, 'gewaende_fugen' {fugen: [{s, winkel_grad, q, n, fotos, sehen, breite_foto}], quelle, fotos_benutzt, doppel}; Bericht bogen_gewaende.json und Bild
  bogen_gewaende_<fid>.jpg (rot = lichter Umriss, gelb = Aussenkante des Bands, gruen = gemessene Fuge mit Fotozahl; ANSEHEN). Bau: bauteile.bogen_gewaende_spaet
  (auf der echten Oberflaeche nach allen Anbauten, Generator-Vorlage objekt_anlegen.py) mit Rillen aus bauteile.bogen_fugen_rillen (Breite >= Druckmindestmass,
  Tiefe ANNAHME FUGE_TIEFE_MM 0,5 mm H0, zu enge Nachbarfuge entfaellt mit Vermerk).
Aufruf:  bogen_gewaende.py <audit/oeffnungen_auto.json> <fassade_fein-ordner> [--fassade <fassade-ordner mit tiefe_fNN.npz>] [--aus ordner] [--nur f00 f01] [--ohne_fugen]
rc 0 = mindestens ein Band vermessen, 3 = nichts geaendert.
"""
import sys, os, json, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCHRITT = 0.01


def druck_min():
    return float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0


def umriss_pfad(x, schritt=SCHRITT):
    """Lichter Umriss der Oeffnung x (form, breite, kaempfer, scheitel, unten; u-Mitte = 0) ohne die Unterkante, gleichmaessig abgetastet.
    Liefert (Q [n,2] in (quer, z), N [n,2] Aussennormalen, teil [n] 'oben'/'links'/'rechts')."""
    import cv2
    from bauteile import bogen_querschnitt
    un = float(x.get("unten", 0.0))
    P = np.array(bogen_querschnitt(x["form"], float(x["breite"]), float(x["kaempfer"]), float(x["scheitel"]), un).to_polygons()[0], float)
    n = len(P); boden = [i for i in range(n) if P[i, 1] <= un + 1e-6 and P[(i + 1) % n, 1] <= un + 1e-6]
    if boden: P = np.roll(P, -(boden[0] + 1), axis=0)                  # Pfad beginnt an einer Unterecke und endet an der anderen
    Q = []
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]; L = float(np.hypot(*(b - a))); k = max(1, int(np.ceil(L / schritt)))
        Q += [a + (b - a) * t for t in np.arange(k) / k]
    Q.append(P[-1]); Q = np.array(Q)
    T = np.gradient(Q, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    N = np.stack([T[:, 1], -T[:, 0]], 1)
    kont = P.astype(np.float32).reshape(-1, 1, 2)
    mitte = len(Q) // 2
    if cv2.pointPolygonTest(kont, (float(Q[mitte, 0] + 0.05 * N[mitte, 0]), float(Q[mitte, 1] + 0.05 * N[mitte, 1])), False) > 0: N = -N
    senk = np.abs(T[:, 1]) > 0.97
    teil = np.where(senk & (Q[:, 1] < float(x["kaempfer"]) + 0.02), np.where(Q[:, 0] < 0, "links", "rechts"), "oben")
    return Q, N, teil


def abrollen(bgr, raster, x, dmax=1.0, schritt=SCHRITT):
    """Wandbild entlang der Aussennormalen des lichten Umrisses abtasten. raster = {u0, z1, zelle} des Wandbilds. Liefert (S [D, n, 3] BGR, bel [D, n] bool, Q, N, teil, D)."""
    import cv2
    Q, N, teil = umriss_pfad(x, schritt)
    D = np.arange(0.0, dmax, schritt)
    UU = float(x["u"]) + Q[None, :, 0] + D[:, None] * N[None, :, 0]; ZZ = Q[None, :, 1] + D[:, None] * N[None, :, 1]
    c = float(raster["zelle"])
    mx = ((UU - float(raster["u0"])) / c).astype(np.float32); my = ((float(raster["z1"]) - ZZ) / c).astype(np.float32)
    S = cv2.remap(np.ascontiguousarray(bgr), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    bel = cv2.remap((bgr.sum(2) > 0).astype(np.uint8), mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    return S, bel, Q, N, teil, D


def band_radial(L, schritt=SCHRITT, schwelle=0.45, kontrast_min=0.25, min_spalten=50, min_band=0.08, rand_aussen=0.3, kern=(0.08, 0.5)):
    """Rahmenband im abgerollten Helligkeitsstreifen L [D, n] (nur belegte Spalten): radiale Kohaerenz der Steinfugen.
    Liefert dict(aussen, innen, kern, kontrast, profil) oder dict(fehler=...)."""
    import cv2
    D, n = L.shape
    if n < min_spalten: return dict(fehler=f"nur {n} belegte Spalten ueber dem Kaempfer (< {min_spalten})")
    A = L.astype(np.float32)
    hp = A - cv2.GaussianBlur(A, (0, 0), sigmaX=0.15 / schritt, sigmaY=0.1)         # Helligkeitsverlauf entlang des Umrisses weg (Schatten, Licht)
    hp = (hp - hp.mean(1, keepdims=True)) / (hp.std(1, keepdims=True) + 1e-6)
    C = hp @ hp.T / n
    k10 = int(round(0.10 / schritt)); r_lo, r_hi = int(kern[0] / schritt), min(int(kern[1] / schritt), D - k10 - 1)
    if r_hi <= r_lo: return dict(fehler="Streifen zu kurz")
    wert = [float(np.mean(C[r, max(0, r - k10): r + k10 + 1])) for r in range(r_lo, r_hi)]
    r0 = r_lo + int(np.argmax(wert))
    k3 = int(round(0.03 / schritt))
    rho = C[max(0, r0 - k3): r0 + k3 + 1].mean(0)
    rho = np.convolve(rho, np.ones(3) / 3, mode="same")
    b = r0
    while b + 1 < D and rho[b + 1] >= schwelle: b += 1
    a = r0
    while a - 1 >= 0 and rho[a - 1] >= schwelle: a -= 1
    b += 1                                                                # erste Zeile ausserhalb
    aussen, innen = b * schritt, a * schritt
    prof = [round(float(v), 2) for v in rho[::3]]
    if aussen > D * schritt - rand_aussen: return dict(fehler=f"Band reicht bis {aussen:.2f} m - keine Aussenkante im Suchbereich", profil=prof)
    if aussen - innen < min_band: return dict(fehler=f"Band nur {aussen - innen:.2f} m breit", profil=prof)
    o0, o1 = b + int(0.05 / schritt), min(D, b + int(rand_aussen / schritt))
    kontrast = float(np.mean(rho[a:b]) - np.mean(rho[o0:o1]))
    if kontrast < kontrast_min: return dict(fehler=f"Band nicht vom Mauerwerk abgesetzt (Kontrast {kontrast:.2f} < {kontrast_min})", profil=prof)
    return dict(aussen=round(aussen, 3), innen=round(innen, 3), kern=round(r0 * schritt, 3), kontrast=round(kontrast, 2), profil=prof)


def farbe(lab, bel, d0, d1, schritt=SCHRITT):
    """Lab-Median der belegten Zellen in den Zeilen d0..d1 (m)."""
    a, b = int(d0 / schritt), int(d1 / schritt); m = bel[a:b]
    return [round(float(v), 1) for v in np.median(lab[a:b][m], axis=0)] if m.sum() >= 20 else None


def vorsprung_messen(npz, x, innen, aussen, ring=(0.1, 0.4)):
    """Vorsprung des Bands aus der Tiefe je Zelle (w positiv = vor der Wand): Median im Band (innen..aussen vom lichten Umriss) gegen Wandring
    aussen+ring. None, wenn zu wenig sichere Zellen oder unplausibel (< 0,01 oder > 0,30 m)."""
    import cv2
    from bauteile import bogen_querschnitt
    if npz is None: return None
    w, gut = np.asarray(npz["w"], float), np.asarray(npz["gut"]).astype(bool); c = float(npz["zelle"]); u0, z1 = float(npz["u0"]), float(npz["z1"])
    P = np.array(bogen_querschnitt(x["form"], float(x["breite"]), float(x["kaempfer"]), float(x["scheitel"]), float(x.get("unten", 0.0))).to_polygons()[0], float)
    pts = np.stack([(float(x["u"]) + P[:, 0] - u0) / c, (z1 - P[:, 1]) / c], 1).round().astype(np.int32)
    m = np.zeros(w.shape, np.uint8); cv2.fillPoly(m, [pts], 1)
    d = cv2.distanceTransform((1 - m).astype(np.uint8), cv2.DIST_L2, 5) * c
    H, _ = w.shape; z = z1 - np.arange(H)[:, None] * c + 0 * d
    ueber = z > float(x.get("unten", 0.0)) + 0.3
    band = (d > max(innen, c)) & (d <= aussen) & gut & ueber & np.isfinite(w)
    wand = (d >= aussen + ring[0]) & (d <= aussen + ring[1]) & gut & ueber & np.isfinite(w)
    if band.sum() < 10 or wand.sum() < 10: return None
    v = float(np.median(w[band]) - np.median(w[wand]))
    return round(v, 3) if 0.01 <= v <= 0.30 else None


def oeffnung_messen(bgr, raster, x, npz=None, dmax=1.0, schwelle=0.45, kontrast_min=0.25):
    """Gewaende-Band einer gebauten Oeffnung x. Liefert (gewaende_band dict | None, bericht dict, abrollung)."""
    import cv2
    S, bel, Q, N, teil, D = abrollen(bgr, raster, x, dmax)
    lab = cv2.cvtColor(S, cv2.COLOR_BGR2LAB).astype(np.float32); lab[..., 0] *= 100.0 / 255.0; lab[..., 1:] -= 128.0
    un = float(x.get("unten", 0.0))
    sp = (teil == "oben") & (Q[:, 1] > un + 0.3) & (bel.mean(0) >= 0.9)
    erg = band_radial(lab[:, sp, 0], kontrast_min=kontrast_min, schwelle=schwelle) if sp.any() else dict(fehler="kein Bogen/Sturz ueber dem Kaempfer im Wandbild")
    ber = dict(u=x["u"], breite=x["breite"], form=x["form"], spalten_oben=int(sp.sum()), **erg)
    if "fehler" in erg: return None, ber, (S, Q, N, D)
    fb = farbe(lab[:, sp], bel[:, sp], erg["innen"], erg["aussen"]); fw = farbe(lab[:, sp], bel[:, sp], erg["aussen"] + 0.05, erg["aussen"] + 0.3)
    v = vorsprung_messen(npz, x, erg["innen"], erg["aussen"])
    G = dict(aussen=erg["aussen"], innen=erg["innen"], kontrast=erg["kontrast"],
             quelle="bogen_gewaende: radiale Fugen-Kohaerenz im abgerollten feinen Wandbild (Bogen/Sturz ueber dem Kaempfer)",
             pfosten_quelle="ANNAHME: Pfosten so breit wie das Bogenband (Pfostensteine mit dem Mauerwerk verzahnt, im Wandbild nicht trennbar)",
             vorsprung=v if v is not None else round(druck_min(), 3),
             vorsprung_quelle="Tiefe je Zelle (fassade/tiefe_<fid>.npz): Band gegen Wandring" if v is not None else
             "ANNAHME Druckmindestmass (MINMM x SCALE) - Tiefe je Zelle misst das Band nicht (0,01-0,30 m)",
             farbe_band=fb, farbe_wand=fw)
    if fb and fw: G["farbabstand"] = round(float(np.linalg.norm(np.subtract(fb, fw))), 1)
    return G, ber, (S, Q, N, D)


# ---- FUGEN zwischen den Bogensteinen (24.11.2026, Nutzer: Fugen sehen; Regel 15.11.: Bogensteine NIE generieren) -----------------------------------------------
# Nur GEMESSENE Fugen: je Einzelfoto-Ortho (fassade_ortho --einzeln, gleiches Raster) wird das Bogenband abgerollt; eine Fuge ist eine dunkle Linie quer zum Umriss,
# die ueber die ganze Bandbreite laeuft (radial). Gilt erst, wenn sie in >= FUGE_FOTOS_MIN Fotos (und >= FUGE_ANTEIL der Fotos, die die Stelle sehen) an derselben
# Stelle (+- FUGE_TOL m entlang des Umrisses) liegt. Keine Teilung, kein Mittelwert ueber Abstaende: jede Fuge an ihrer gemessenen Stelle; unbelegt = glatt.
FUGE_FOTOS_MIN, FUGE_ANTEIL, FUGE_TOL = 3, 0.4, 0.03       # >= 3 Fotos (Kernmethode: Formfamilie aus >= 3 Fotos)
FUGE_SEITE = (0.03, 0.06)            # Liniendetektor: Mitte +-1 cm gegen beide Seiten 3-6 cm daneben
FUGE_TRENN = 2 * FUGE_SEITE[1]       # Fussbreite des Detektors (12 cm): naeher beieinander = dieselbe Antwort, die staerker belegte Stelle gilt
FUGE_STAERKE, FUGE_RADIAL = float(os.environ.get("FUGE_STAERKE", "1.0")), float(os.environ.get("FUGE_RADIAL", "0.6"))   # Linie je Foto: Median-Antwort in Bildstreuungen, Anteil der Bandzeilen


def _hochpass(g, sigma):
    import cv2
    g = g.astype(np.float32); return g - cv2.GaussianBlur(g, (0, 0), sigma)


def einzelbilder(fein, fid):
    """Einzelfoto-Orthos ortho_<fid>_einzeln/*.png (fassade_ortho --einzeln, gleiches Raster wie das Wandbild). Liste (name, pfad) - geladen wird erst beim Messen,
    eins nach dem anderen (38 Bilder x 15 MB)."""
    import glob
    return [(os.path.basename(q)[:-4], q) for q in sorted(glob.glob(os.path.join(fein, f"ortho_{fid}_einzeln", "*.png")))]


def ausrichten(ref, im, raster, x, aussen, max_m=0.25, schritt=SCHRITT):
    """Ganzzahliger Versatz (di, dj) des Einzelorthos 'im' gegen das Wandbild 'ref' im Bogenbereich (Einzelorthos liegen 0,1-1 m gegeneinander, fassade_fein):
    normierte Kreuzkorrelation der bandpassgefilterten Helligkeit (DoG 1,5/8 Zellen: Steinkanten, nicht Licht/Aufloesung) auf dem RING um den lichten Umriss
    (0..aussen+0,3 m, ohne den Durchblick, der je Standort anderes zeigt), Suche +- max_m. Liefert (di, dj, ncc) oder None (zu wenig gesehen)."""
    import cv2
    from bauteile import bogen_querschnitt
    c = float(raster["zelle"]); r = int(round(max_m / c)); a_ = float(aussen) + 0.3
    j0 = int((float(x["u"]) - float(x["breite"]) / 2 - a_ - float(raster["u0"])) / c); j1 = int((float(x["u"]) + float(x["breite"]) / 2 + a_ - float(raster["u0"])) / c)
    i0 = int((float(raster["z1"]) - float(x["scheitel"]) - a_) / c); i1 = int((float(raster["z1"]) - float(x["kaempfer"]) + 0.5) / c)
    H, W = ref.shape[:2]; i0, j0 = max(r, i0), max(r, j0); i1, j1 = min(H - r, i1), min(W - r, j1)
    if i1 - i0 < 20 or j1 - j0 < 20: return None
    P = np.array(bogen_querschnitt(x["form"], float(x["breite"]), float(x["kaempfer"]), float(x["scheitel"]), float(x.get("unten", 0.0))).to_polygons()[0], float)
    pts = np.stack([(float(x["u"]) + P[:, 0] - float(raster["u0"])) / c - j0, (float(raster["z1"]) - P[:, 1]) / c - i0], 1).round().astype(np.int32)
    loch = np.zeros((i1 - i0, j1 - j0), np.uint8); cv2.fillPoly(loch, [pts], 1)
    ring = (loch == 0) & (cv2.distanceTransform((1 - loch).astype(np.uint8), cv2.DIST_L2, 5) * c <= a_)
    g = lambda b: cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    dog = lambda a: cv2.GaussianBlur(a, (0, 0), 1.5) - cv2.GaussianBlur(a, (0, 0), 8.0)
    ok_i = (im[i0:i1, j0:j1].sum(2) > 0) & ring
    if ok_i.sum() < 0.5 * ring.sum(): return None
    T = dog(g(im[i0:i1, j0:j1])) * cv2.erode(ok_i.astype(np.uint8), np.ones((9, 9), np.uint8))
    Rr = ref[i0 - r:i1 + r, j0 - r:j1 + r]; Rg = dog(g(Rr)) * cv2.erode((Rr.sum(2) > 0).astype(np.uint8), np.ones((9, 9), np.uint8))
    M = cv2.matchTemplate(Rg, T, cv2.TM_CCORR_NORMED); _, v, _, p = cv2.minMaxLoc(M)
    return p[1] - r, p[0] - r, float(v)


def linien_antwort(B, schritt=SCHRITT, kern=0.01, seite=FUGE_SEITE):
    """Linien-Antwort je Zelle entlang s (Spalten) eines Streifens B [Zeilen, n]: Mitte (+-kern) gegen BEIDE Seiten (seite[0]..seite[1] links und rechts).
    dunkel = min(links, rechts) - Mitte, hell = Mitte - max(links, rechts): eine Stufenkante (eine Seite hell, eine dunkel) gibt ~0, nur eine LINIE antwortet."""
    import cv2
    k = max(1, int(round(kern / schritt))); s0, s1 = max(k + 1, int(round(seite[0] / schritt))), max(k + 2, int(round(seite[1] / schritt)))
    mitte = cv2.blur(B, (2 * k + 1, 1), borderType=cv2.BORDER_REPLICATE)
    w = s1 - s0 + 1; box = cv2.blur(B, (w, 1), borderType=cv2.BORDER_REPLICATE); o = (s0 + s1) // 2
    li = np.empty_like(B); re = np.empty_like(B)
    li[:, o:] = box[:, :-o]; li[:, :o] = box[:, :1]; re[:, :-o] = box[:, o:]; re[:, -o:] = box[:, -1:]
    return np.minimum(li, re) - mitte, mitte - np.maximum(li, re)


def fugen_kandidaten(L, bel, innen, aussen, schritt=SCHRITT, staerke_min=FUGE_STAERKE, radial_min=FUGE_RADIAL, rand=0.03, breite_max=0.07):
    """RADIALE Fugenlinien in einem abgerollten Helligkeitsstreifen L [D, n] (Zeile = Abstand vom Loch, Spalte = Weg s entlang des Umrisses), Bandzeilen innen..aussen.
    Fuge = schmale Linie quer zum Umriss, DUNKEL (Schattenfuge) oder HELL (Kalkmoertel, 1122w Sued: helle Fugen zwischen dunklen Bogensteinen), die ueber die
    Bandbreite laeuft: Linien-Antwort (linien_antwort, keine Stufenkanten) je Bandzeile; je Spalte Median ueber die Zeilen in Einheiten der Bildstreuung >= staerke_min
    und in >= radial_min der Zeilen positiv (kein Fleck), oertliches Maximum +-4 cm, Halbwertsbreite <= breite_max.
    Liefert (liste dict(s_idx, art, staerke, radial, breite), gesehen[n])."""
    import cv2
    a, b = int(round((innen + rand) / schritt)), int(round((aussen - rand) / schritt))
    if b - a < 3: return [], np.zeros(L.shape[1], bool)
    B = L[a:b].astype(np.float32); m = bel[a:b]
    gesehen = m.mean(0) >= 0.8
    if gesehen.sum() < 20: return [], gesehen
    B = np.where(m, B, np.median(B[m]))
    B = cv2.GaussianBlur(B, (0, 0), sigmaX=0.5, sigmaY=1.0)
    hp = B - cv2.GaussianBlur(B, (0, 0), sigmaX=0.05 / schritt, sigmaY=0.1)
    sd = 1.4826 * float(np.median(np.abs(hp[m] - np.median(hp[m])))) + 1e-6
    aus = []; k = int(round(0.04 / schritt))
    for art, R in zip(("dunkel", "hell"), linien_antwort(B, schritt)):
        R = R / sd; p = np.median(R, axis=0)
        frac = ((R > 0.3) & m).sum(0) / np.maximum(m.sum(0), 1)
        for s in range(k, len(p) - k):
            if not gesehen[s] or p[s] < staerke_min or p[s] != p[s - k: s + k + 1].max() or frac[s] < radial_min: continue
            h = p[s] / 2; l = s; r = s
            while l > 0 and p[l - 1] > h: l -= 1
            while r < len(p) - 1 and p[r + 1] > h: r += 1
            br = (r - l + 1) * schritt
            if br > breite_max: continue
            aus.append(dict(s_idx=s, art=art, staerke=round(float(p[s]), 2), radial=round(float(frac[s]), 2), breite=round(br, 3)))
    aus.sort(key=lambda c: -c["staerke"]); frei = []                       # dunkle und helle Antwort an derselben Stelle: die staerkere gilt
    for c in aus:
        if all(abs(c["s_idx"] - f["s_idx"]) > k for f in frei): frei.append(c)
    return sorted(frei, key=lambda c: c["s_idx"]), gesehen


def fugen_abstimmen(kand, gesehen, schritt=SCHRITT, tol=None, n_min=None, anteil=None):
    """Mehrfoto-Beleg: kand = je Foto Liste von s-Indizes, gesehen = je Foto bool[n]. Gierig: Stelle mit den meisten Fotos (Kandidat +- tol) nehmen, belegende Kandidaten
    verbrauchen, bis keine Stelle mehr >= max(n_min, anteil x sehende Fotos) Stimmen hat. Lage = Median der belegenden Kandidaten. Liefert Liste dict(s_idx, fotos, sehen)."""
    tol = FUGE_TOL if tol is None else tol; n_min = FUGE_FOTOS_MIN if n_min is None else n_min; anteil = FUGE_ANTEIL if anteil is None else anteil
    t = int(round(tol / schritt)); frei = [list(k) for k in kand]; aus = []
    if not kand: return aus
    n = len(gesehen[0])
    while True:
        S = np.zeros(n, int)
        for k in frei:
            v = np.zeros(n, bool)
            for s in k: v[max(0, s - t): s + t + 1] = True
            S += v
        if not S.any(): break
        sehen = np.sum([g for g in gesehen], 0)
        ok = (S >= n_min) & (S >= np.ceil(anteil * sehen))
        if not ok.any(): break
        s0 = int(np.argmax(np.where(ok, S, -1))); tr = []
        for k in frei:
            nah = [s for s in k if abs(s - s0) <= t]
            if nah: q = min(nah, key=lambda s: abs(s - s0)); tr.append(q); k.remove(q)
        aus.append(dict(s_idx=int(round(np.median(tr))), fotos=len(tr), sehen=max(len(tr), int(sehen[s0]))))
    trenn = int(round(FUGE_TRENN / schritt)); gilt = []                   # AUFLOESUNG: zwei Stellen innerhalb der Fussbreite des Liniendetektors sind nicht unabhaengig
    for f in sorted(aus, key=lambda f: -f["fotos"]):
        if all(abs(f["s_idx"] - g["s_idx"]) >= trenn for g in gilt): gilt.append(f)
    return sorted(gilt, key=lambda f: f["s_idx"])


def feinversatz(hp, ok, hp_ref, ok_ref, schritt=SCHRITT, fenster=0.8, takt=0.2, max_m=0.08, ncc_min=0.2):
    """Restversatz entlang des Bogenwegs je Spalte: Fenster (fenster m, alle takt m) des Fotostreifens gegen den Bezugsstreifen (Wandbild) um +- max_m verschoben,
    beste normierte Korrelation (>= ncc_min, sonst Fenster unbelegt). Foto-Spalte s entspricht Bezug-Spalte s + v[s]. Liefert (v int[n], belegt bool[n])."""
    n = hp.shape[1]; h = int(round(fenster / schritt / 2)); T = int(round(max_m / schritt)); st = max(1, int(round(takt / schritt)))
    mitten, werte = [], []
    for m0 in range(h, max(h + 1, n - h), st):
        a, b = m0 - h, min(n, m0 + h); best = None
        for t in range(-T, T + 1):
            if a + t < 0 or b + t > n: continue
            m = ok[a:b] & ok_ref[a + t:b + t]
            if m.sum() < 0.6 * (b - a): continue
            A_, B_ = hp[:, a:b][:, m].ravel(), hp_ref[:, a + t:b + t][:, m].ravel()
            r_ = float(np.dot(A_ - A_.mean(), B_ - B_.mean()) / (np.linalg.norm(A_ - A_.mean()) * np.linalg.norm(B_ - B_.mean()) + 1e-9))
            if best is None or r_ > best[0]: best = (r_, t)
        if best and best[0] >= ncc_min and abs(best[1]) < T: mitten.append(m0); werte.append(best[1])
    v = np.zeros(n, int); bel = np.zeros(n, bool)
    if not mitten: return v, bel
    v = np.round(np.interp(np.arange(n), mitten, werte)).astype(int)
    for m0 in mitten: bel[max(0, m0 - h):min(n, m0 + h)] = True
    return v, bel & ok


def fugen_messen(ref, einzeln, raster, x, G, dmax=1.0, schritt=SCHRITT, ncc_min=0.1, doppel_r=0.85):
    """Gemessene Fugen im Bogenband (Teil 'oben' des Umrisses) der Oeffnung x mit Band G. ref = Wandbild (Ausrichtung), einzeln = [(name, bgr)].
    Liefert (fugen [dict(s, winkel_grad, q, n, fotos, sehen, breite)], bericht dict)."""
    import cv2
    ber = dict(fotos_gesamt=len(einzeln))
    if len(einzeln) < FUGE_FOTOS_MIN: ber["fehler"] = f"nur {len(einzeln)} Einzelfotos - Mehrfoto-Beleg unmoeglich, Band bleibt glatt"; return [], ber
    un = float(x.get("unten", 0.0)); Q, N, teil = umriss_pfad(x, schritt)
    oben = (teil == "oben") & (Q[:, 1] > un + 0.3)
    kand, ges, benutzt, brei, streifen = [], [], [], {}, []
    a_, b_ = int(round((float(G.get("innen", 0.0)) + 0.03) / schritt)), int(round((float(G["aussen"]) - 0.03) / schritt)); c = float(raster["zelle"])
    S0, bel0, _, _, _, _ = abrollen(ref, raster, x, dmax, schritt)
    hp_ref = _hochpass(cv2.cvtColor(S0, cv2.COLOR_BGR2GRAY)[:, oben][a_:b_], 3.0); ok_ref = bel0[:, oben][a_:b_].mean(0) >= 0.8
    for name, im in einzeln:
        if isinstance(im, str): im = cv2.imread(im, cv2.IMREAD_COLOR)
        if im is None or im.shape[:2] != ref.shape[:2]: continue
        v = ausrichten(ref, im, raster, x, G["aussen"])
        if v is None or v[2] < ncc_min: continue
        di, dj, ncc = v
        rs = dict(raster, u0=float(raster["u0"]) + dj * c, z1=float(raster["z1"]) - di * c)   # Einzelpixel (i, j) = Wandbild (i + di, j + dj)
        S, bel, _, _, _, _ = abrollen(im, rs, x, dmax, schritt)
        L = cv2.cvtColor(S, cv2.COLOR_BGR2GRAY)[:, oben]; bo = bel[:, oben]
        hp = _hochpass(L[a_:b_], 3.0); ok = bo[a_:b_].mean(0) >= 0.8
        doppel = None                                                      # DOPPEL: dasselbe Bild zweimal im Bestand (Download + Original) ist KEIN zweiter Beleg
        for k_s, (h2, ok2, _) in enumerate(streifen):
            m = ok & ok2
            if m.sum() >= 50:
                A_, B_ = hp[:, m].ravel(), h2[:, m].ravel(); r_ = float(np.corrcoef(A_, B_)[0, 1])
                if r_ >= doppel_r: doppel = (k_s, r_); break
        eintrag = dict(foto=name, versatz_m=[round(dj * c, 2), round(-di * c, 2)], ncc=round(ncc, 2))
        if doppel is not None: eintrag["doppel_von"] = benutzt[doppel[0]]["foto"]; eintrag["r"] = round(doppel[1], 2); ber.setdefault("doppel", []).append(eintrag); continue
        streifen.append((hp, ok, name))
        vs, v_ok = feinversatz(hp, ok, hp_ref, ok_ref, schritt)          # Restversatz entlang des Bogens (schraege Fotos: Translation reicht nicht ueberall)
        k_, g_ = fugen_kandidaten(L, bo, G.get("innen", 0.0), G["aussen"], schritt)
        idx = np.where(oben)[0]; n_o = len(idx)
        k_ = [dict(k, s_ref=int(k["s_idx"] + vs[k["s_idx"]])) for k in k_ if v_ok[k["s_idx"]] and 0 <= k["s_idx"] + vs[k["s_idx"]] < n_o]
        kand.append([int(idx[k["s_ref"]]) for k in k_]); gg = np.zeros(len(Q), bool); gg[idx] = g_ & v_ok; ges.append(gg)
        for k in k_: brei.setdefault(int(idx[k["s_ref"]]), []).append(k["breite"])
        eintrag["kandidaten"] = len(k_); eintrag["feinversatz_m"] = [round(float(np.min(vs[v_ok])) * schritt, 2), round(float(np.max(vs[v_ok])) * schritt, 2)] if v_ok.any() else None
        benutzt.append(eintrag)
    ber["fotos_benutzt"] = benutzt
    if len(kand) < FUGE_FOTOS_MIN: ber["fehler"] = f"nur {len(kand)} Einzelfotos sehen das Bogenband ausgerichtet - Band bleibt glatt"; return [], ber
    F = fugen_abstimmen(kand, ges, schritt)
    s_weg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    aus = []
    for f in F:
        i = f["s_idx"]; bb = [b for s_, l_ in brei.items() if abs(s_ - i) <= int(round(FUGE_TOL / schritt)) for b in l_]
        aus.append(dict(s=round(float(s_weg[i]), 3), winkel_grad=round(float(np.degrees(np.arctan2(N[i, 1], N[i, 0]))), 1), q=[round(float(Q[i, 0]), 3), round(float(Q[i, 1]), 3)],
                        n=[round(float(N[i, 0]), 4), round(float(N[i, 1]), 4)], fotos=f["fotos"], sehen=f["sehen"], breite_foto=round(float(np.median(bb)), 3) if bb else None))
    ber["fugen"] = len(aus); ber["bogen_weg_m"] = [round(float(s_weg[np.where(oben)[0][0]]), 2), round(float(s_weg[np.where(oben)[0][-1]]), 2)] if oben.any() else None
    return aus, ber


def kontrollbild(bgr, raster, eintraege, pfad, rand=1.2):
    """rot = lichter Umriss, gelb = Aussenkante des Bands (gemessen), grau = kein Band, gruen = gemessene Fuge (Zahl = belegende Fotos)."""
    import cv2
    if not eintraege: return
    c = float(raster["zelle"]); P = lambda u, z: (int(round((u - float(raster["u0"])) / c)), int(round((float(raster["z1"]) - z) / c)))
    us = [x["u"] + s * (x["breite"] / 2 + rand) for x, _ in eintraege for s in (-1, 1)]; zs = [float(x.get("unten", 0.0)) for x, _ in eintraege] + [x["scheitel"] + rand for x, _ in eintraege]
    (j0, i0), (j1, i1) = P(min(us), max(zs)), P(max(us), min(zs))
    i0, j0 = max(0, i0), max(0, j0); i1, j1 = min(bgr.shape[0], i1), min(bgr.shape[1], j1)
    im = np.ascontiguousarray(bgr[i0:i1, j0:j1]).copy()
    for x, G in eintraege:
        Q, N, _ = umriss_pfad(x)
        innen = np.array([P(x["u"] + q[0], q[1]) for q in Q], np.int32) - [j0, i0]
        cv2.polylines(im, [innen], False, (0, 0, 255), 2)
        if G:
            au = np.array([P(x["u"] + q[0] + G["aussen"] * n_[0], q[1] + G["aussen"] * n_[1]) for q, n_ in zip(Q, N)], np.int32) - [j0, i0]
            cv2.polylines(im, [au], False, (0, 230, 255), 2)
            for f in G.get("fugen") or []:                                  # gemessene Fuge: Strich ueber die Bandbreite, Zahl = belegende Fotos
                q, n_ = np.array(f["q"]), np.array(f["n"]); a_, b_ = P(x["u"] + q[0], q[1]), P(x["u"] + q[0] + G["aussen"] * n_[0], q[1] + G["aussen"] * n_[1])
                cv2.line(im, (a_[0] - j0, a_[1] - i0), (b_[0] - j0, b_[1] - i0), (0, 255, 0), 2)
                cv2.putText(im, str(f["fotos"]), (b_[0] - j0 + 2, b_[1] - i0), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
            nf = len(G.get("fugen") or [])
            cv2.putText(im, f"Band {G['aussen']:.2f} m, vor {G['vorsprung']:.3f}" + (f", {nf} Fugen gemessen" if "fugen" in G else ""), (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 255), 2)
    s = 900.0 / max(im.shape[:2]); im = cv2.resize(im, None, fx=s, fy=s) if s < 1 else im
    cv2.imwrite(pfad, im)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("oeffnungen"); ap.add_argument("fein")
    ap.add_argument("--fassade", help="Ordner mit tiefe_<fid>.npz (Vorsprung)"); ap.add_argument("--aus"); ap.add_argument("--nur", nargs="*")
    ap.add_argument("--dmax", type=float, default=1.0); ap.add_argument("--schwelle", type=float, default=0.45); ap.add_argument("--kontrast", type=float, default=0.25)
    ap.add_argument("--ohne_fugen", action="store_true", help="nur das Band, keine Fugenmessung")
    a = ap.parse_args(argv)
    import cv2
    from loch_gewaende import wandbild
    aus = a.aus or os.path.dirname(os.path.abspath(a.oeffnungen)); os.makedirs(aus, exist_ok=True)
    J = json.load(open(a.oeffnungen))
    FF = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    bericht = {}; n_ok = 0; alt_weg = 0
    for fid, F in J.items():
        if not isinstance(F, dict) or (a.nur and fid not in a.nur): continue
        geb = [x for x in F.get("oeffnungen", []) if x.get("gebaut")]
        if not geb: continue
        bgr = wandbild(a.fein, fid)
        if fid not in FF or bgr is None: bericht[fid] = "kein feines Wandbild"; continue
        rs = FF[fid]["raster"]
        nz = os.path.join(a.fassade, f"tiefe_{fid}.npz") if a.fassade else None; npz = dict(np.load(nz)) if nz and os.path.exists(nz) else None
        br = []; bild = []; einz = None
        for x in geb:
            if x.pop("gewaende_band", None) is not None: alt_weg += 1     # zweiter Lauf: nur die neue Messung gilt
            if x.pop("gewaende_fugen", None) is not None: alt_weg += 1   # alte Fugen gelten nie weiter (auch wenn jetzt kein Band gemessen wird)
            G, ber, _ = oeffnung_messen(bgr, rs, x, npz, a.dmax, a.schwelle, a.kontrast)
            if G: x["gewaende_band"] = G; n_ok += 1
            if G and not a.ohne_fugen:                                      # 24.11.2026: Fugen nur GEMESSEN (Mehrfoto-Beleg), sonst bleibt das Band glatt
                if einz is None: einz = einzelbilder(a.fein, fid)
                fu, fb = fugen_messen(bgr, einz, rs, x, G, a.dmax)
                ber["fugen"] = {k: v for k, v in fb.items() if k != "fotos_benutzt"} | {"fotos_benutzt": len(fb.get("fotos_benutzt", []))}
                if fu:
                    x["gewaende_fugen"] = dict(fugen=fu, quelle="bogen_gewaende.fugen_messen: radiale Fugenlinie (hell oder dunkel, keine Stufenkante) ueber die Bandbreite je "
                                               f"Einzelfoto-Ortho, Mehrfoto-Beleg >= {FUGE_FOTOS_MIN} Fotos und >= {FUGE_ANTEIL:.0%} der sehenden; keine Teilung, unbelegt = glatt",
                                               winkel="winkel_grad = Richtung der Aussennormale des lichten Umrisses an der Fuge (0 = waagerecht nach rechts, 90 = senkrecht nach oben)",
                                               fotos_benutzt=fb.get("fotos_benutzt", []), doppel=fb.get("doppel", []))
                print(f"   Fugen: {len(fu)} gemessen aus {len(fb.get('fotos_benutzt', []))} Einzelfotos" + (f" ({fb['fehler']})" if fb.get("fehler") else ""))
            br.append(ber); bild.append((x, dict(G, fugen=(x.get("gewaende_fugen") or {}).get("fugen", [])) if G else G))
            print(f"{fid} Oeffnung u {x['u']:.2f} ({x['form']}, {x['breite']:.2f} m): " + (f"Band {G['aussen']:.2f} m (innen {G['innen']:.2f}, Kontrast {G['kontrast']:.2f}), "
                  f"Vorsprung {G['vorsprung']:.3f} m" + (" ANNAHME" if "ANNAHME" in G["vorsprung_quelle"] else " gemessen") if G else "kein Band: " + ber["fehler"]))
        bericht[fid] = br; kontrollbild(bgr, rs, bild, os.path.join(aus, f"bogen_gewaende_{fid}.jpg"))
    json.dump(bericht, open(os.path.join(aus, "bogen_gewaende.json"), "w"), indent=1, ensure_ascii=False)
    if not n_ok:
        if alt_weg: json.dump(J, open(a.oeffnungen, "w"), indent=1, ensure_ascii=False); print(f"{alt_weg} alte(s) Gewaende-Band/Fugen entfernt (neue Messung ohne Band)")
        print("kein Gewaende-Band vermessen"); return 3
    json.dump(J, open(a.oeffnungen, "w"), indent=1, ensure_ascii=False)
    print(f"-> {a.oeffnungen}: {n_ok} Gewaende-Band/Baender vermessen"); return 0


if __name__ == "__main__": sys.exit(main())
