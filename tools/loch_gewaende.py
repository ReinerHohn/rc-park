#!/usr/bin/env python3
"""loch_gewaende.py - LOCH UND GEWAENDE eines Fensters/einer Tuer aus dem feinen Wandbild (23.11.2026, Kettenstufe 'bauplan' nach nischen_fenster.py).

Anlass (Kettenlauf 1122o, Schwabentor von null, audit/neben_detail_*.jpg):
  fenster_f03    Foto: kleines vergittertes Rechteckfenster in verzahntem Sandsteingewaende. Kette: 2,8 x 3,1 m Rechteck (= Erkennerkasten um das GANZE Gewaende,
                 nischen_fenster 'Zone ohne Fotozellen', weil das Wandbild oben angeschnitten ist), 0,12 m ANNAHME-Tiefe, kein Gewaende.
  fenster_f03_2  Foto: schmaler Lichtschlitz (~0,2 m) in einem Sandsteinfeld. Kette: 1,28 m Rundbogenfenster - der Erkennerkasten und die Bildkanten folgen dem
                 FARBFELD (Sandstein gegen weissen Putz), nicht dem Loch.
  oeffnung f04   Foto: Rechtecktuer (dunkles Tuerblatt) in profiliertem Sandsteinportal. Kette: nichts gebaut (oeffnungen_bogen: kein Durchblick -> verworfen,
                 oeffnungen_wandbild: 'tuer', flach) - eine geschlossene Aussentuer kam in keinem Bauteil an.
Gemeinsame Ursache: der Erkennerkasten umfasst Loch UND Gewaende; die Kette hatte nur 'Kasten = Oeffnung'. Im Wandbild sind es drei Klassen:
  WAND     = Farbe des Wandrings um die Zone (Lab-Median der belegten Zellen 0,15-0,45 m ausserhalb),
  GEWAENDE = deutlich andere Farbe als die Wand, aber NICHT dunkel (Sandstein, Putzfaschen),
  LOCH     = dunkel gegen Wand UND Gewaende (Glas, Gitter im Schatten, Tuerblatt, Schlitz) - Otsu auf der Helligkeit der Nicht-Wand-Zellen (hoechstens
             --dunkel x Wand-L); ist das Gewaende farbig (Sandstein), zaehlen dunkle Zellen mit seinem Farbton nicht (beschattete Laibung ist kein Loch).
Methode (KERNMETHODE, WANDBILD = BAUPLAN; Erkennen = nur Zone): je Eintrag der Fensterliste OHNE Nische (Paare aus nischen_fenster bleiben unberuehrt) und je
geschlossener Tuer aus oeffnungen_aussen.json (klasse 'tuer', flach, keine gebaute Oeffnung an der Stelle):
  1. Loch = groesste dunkle Komponente nahe der Zonenmitte (Schliessen 4 cm gegen Gitterstaebe), Kasten = 2-/98-%-Werte ihrer Zellen.
     Gueltig nur: >= 0,1 m in beiden Richtungen, >= 40 % Fuellung des Kastens, Mitte in der Zone, Loch deutlich dunkler (L <= --dunkel x Wand-L).
     Beruehrt das Loch den Rand der belegten Zellen (Wandbild angeschnitten), gilt fuer diese Seite der kleinste Erkennerkasten, der das Loch enthaelt (sonst bleibt
     die Seite mit 'angeschnitten' im Eintrag).
  2. Gewaende = Nicht-Wand-Zellen, die das Loch beruehren (Komponente am um 10 cm gewachsenen Loch), ohne Loch; Umriss (2 cm vereinfacht) in u/z.
     Gilt nur mit >= 15 % der Lochflaeche. Fuellt das Gewaende den Wandring (wandfarbe: Ring + Band bis RING_WEIT zweifarbig, aussen andere Mehrheit;
     1122w Sued f01), ist die Wand die Farbe aussen und das Gewaende darf bis zur Lochbreite reichen, dort nur in seiner Farbe am Loch. Relief-Hoehe: Ebenen-Sweep (Gewaendezellen gegen Wandring, nur 0,02-0,30 m vor der Wand plausibel), sonst
     ANNAHME Druckmindestmass (MINMM x SCALE) - im Eintrag vermerkt.
  3. Form: Eintrag ohne Bogen -> Bogen aus der Oberkante des Lochs (bogen_aus_loch: Stich/Rund), wenn messbar. Der Eintrag behaelt seine Bogenform nur, wenn das Loch dieselbe Groesse hat (Breite und Hoehe je +-25 %); sonst war die Form die des Gewaendes -> Rechteck
     (form_quelle nennt den Grund). Tiefe: Sweep im Loch gegen den Wandring (nischen_fenster.tiefe_einzeln); sonst bleibt eine gemessene Tiefe, sonst ANNAHME.
  GUARD + FALLBACK: kein gueltiges Loch -> Eintrag unveraendert (Grund im Bericht). Ein Loch, das > 90 % der Zone fuellt, aendert nichts (Zone war schon das Loch).
Ausgabe: fenster_auto.json neu (Eingang als fenster_auto_vor_loch.json daneben); Eintraege bekommen 'loch' (Mass + Quelle) und ggf. 'gewaende'
  {umriss [[u, z]..], hoehe, hoehe_quelle}; Tueren kommen als Eintrag mit art 'tuer' dazu. Bericht loch_gewaende.json, Bild loch_gewaende_<fid>.jpg (ANSEHEN:
  rot = Loch, gelb = Gewaende, grau = Zone). Gebaut von bauteile.fenster_aus_json (Gewaende als Relief vor der Wand, dann das Loch geschnitten).
Aufruf:  loch_gewaende.py <fenster_auto.json> <fassade-ordner (elemente.json, tiefe_fNN.npz)> <fassade_fein-ordner> [--oeffnungen audit/oeffnungen_aussen.json]
         [--oeffnungen_auto audit/oeffnungen_auto.json] [--nur f03] [--aus ordner]
rc 0 = mindestens ein Loch vermessen, 3 = nichts geaendert.
"""
import sys, os, json, argparse, shutil
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RING = (0.15, 0.45)        # Wandring um die Zone (m)
RING_WEIT = 1.0            # aeusseres Band (RING[1] .. RING_WEIT) fuer die Wandfarbe, wenn ein breites Gewaende den Wandring fuellt (1122w Sued f01)
RAND = 0.25                # Suchbereich um die Zone (Anteil der Zonengroesse; das Gewaende ragt oft ueber den Erkennerkasten)


def wandfarbe(lab, d, bel, trennung=15.0, it=12):
    """WANDFARBE um eine Zone (24.11.2026, Befund 1122w Sued-Fenster f01: breites Sandstein-Gewaende mit Keilsteinfaecher fuellt den Wandring 0,15-0,45 m -> der
    Ring-Median WAR der Sandstein, das Gewaende galt als Wand und fehlte im Modell). Liefert (wand_lab, rausch, weit):
    Standard wie bisher: Median des Wandrings, rausch = 2 x Median-Abstand im Ring. Ist der Ring + das aeussere Band (bis RING_WEIT) ZWEIFARBIG (2-Mittel, Abstand
    der Mitten >= trennung) und ist die Mehrheitsfarbe des AEUSSEREN Bands nicht die des Rings, dann ist die Wand das Material, das nach aussen weiterlaeuft:
    wand = Median dieser Klasse, rausch nur aus ihren Zellen, weit = True (das Gewaende reicht ueber den Ring hinaus)."""
    nah = (d >= RING[0]) & (d <= RING[1]) & bel; fern = (d > RING[1]) & (d <= RING_WEIT) & bel
    w0 = np.median(lab[nah], axis=0); r0 = 2.0 * float(np.percentile(np.linalg.norm(lab[nah] - w0, axis=1), 50))
    if fern.sum() < 50: return w0, r0, False
    alle = nah | fern; X = lab[alle]; Xs = X[:: max(1, len(X) // 20000)]
    c = np.stack([w0, np.median(lab[fern], axis=0)])
    if np.linalg.norm(c[0] - c[1]) < 1e-3: c[1] = Xs[np.argmax(np.linalg.norm(Xs - w0, axis=1))]
    for _ in range(it):                                                    # 2-Mittel (Lab), Start: Ring-Median und Band-Median
        k = np.linalg.norm(Xs[:, None, :] - c[None], axis=2).argmin(1)
        if (k == 0).sum() < 10 or (k == 1).sum() < 10: return w0, r0, False
        c = np.stack([np.median(Xs[k == 0], axis=0), np.median(Xs[k == 1], axis=0)])
    if np.linalg.norm(c[0] - c[1]) < trennung: return w0, r0, False       # einfarbig: wie bisher
    kf = np.linalg.norm(lab[fern][:, None, :] - c[None], axis=2).argmin(1); kw = int(np.bincount(kf, minlength=2).argmax())
    if (kf == kw).mean() < 0.5: return w0, r0, False
    if np.linalg.norm(w0 - c[kw]) < 0.5 * np.linalg.norm(c[0] - c[1]): return w0, r0, False     # Ring-Median ist schon die Wand (Normalfall)
    ka = np.linalg.norm(X[:, None, :] - c[None], axis=2).argmin(1); Xw = X[ka == kw]
    w = np.median(Xw, axis=0); return w, 2.0 * float(np.percentile(np.linalg.norm(Xw - w, axis=1), 50)), True


def bogen_aus_loch(m, U, Z, lu0, lu1, lz1, c, rest_max=0.025):
    """OBERKANTE DES LOCHS -> Bogenform (24.11.2026, 1122w Sued f01: Bogen kam als Stich 9 cm aus dem Erkennerumriss, das Wandbild zeigt den Bogen des Lochs selbst).
    Je Spalte die oberste Lochzelle; Modelle (Breite b = lu1 - lu0, a = b/2, Scheitel = lz1): gerade (Pfeil 0), Stich (Kreissegment, Pfeil h < a), Rund (h = a).
    Scheitel = P90 der Mittelspalten. Gewinner = kleinster Median-Rest; gilt nur mit Rest <= rest_max und >= 5 Spalten. None = kein Bogen messbar (Pfeil < max(3 cm, 3 Zellen)) -> Kasten bleibt."""
    sp = np.nonzero(m.any(0))[0]
    if len(sp) < 5: return None
    top = np.array([Z[:, j][m[:, j]].max() for j in sp]) + c / 2; uj = U[0, sp]
    a = (lu1 - lu0) / 2; mu = (lu0 + lu1) / 2; x = uj - mu; s = (np.abs(x) <= 0.95 * a)
    if s.sum() < 5 or a < 0.05: return None
    x, top = x[s], top[s]; best = None
    mi = np.abs(x) <= 0.2 * a
    sz = float(np.percentile(top[mi], 90)) if mi.sum() >= 2 else lz1      # Scheitel = Oberkante der Mittelspalten (P98 aller Lochzellen liegt beim Bogen tiefer)
    rest = {}
    for h in list(np.arange(0.0, a, max(c, 0.005))) + [a]:
        if h < 1e-6: pred = np.full_like(x, sz)
        else:
            R = (a * a + h * h) / (2 * h); pred = sz - R + np.sqrt(np.maximum(R * R - x * x, 0.0))
        r = float(np.median(np.abs(top - pred))); rest[h] = r
        if best is None or r < best[0] - 1e-9: best = (r, h)
    r, h = best
    if r > rest_max: return None
    if h < max(0.03, 3 * c): return None                                   # kein messbarer Bogen: Kasten der Komponente bleibt (gerade)
    if h >= 0.9 * a or rest[a] <= r + max(c, 0.005):                       # Halbkreis gleich gut (Randspalten steil, Pfeil dort unscharf) -> Formfamilie rund
        return dict(form="rund", kaempfer=round(float(sz - a), 3), scheitel=round(sz, 3), rest_m=round(rest[a], 3))
    return dict(form="stich", kaempfer=round(float(sz - h), 3), scheitel=round(sz, 3), rest_m=round(r, 3))


def _lab(bgr):
    import cv2
    L = cv2.cvtColor(np.ascontiguousarray(bgr, np.uint8), cv2.COLOR_BGR2LAB).astype(np.float32)
    L[..., 0] *= 100.0 / 255.0; L[..., 1:] -= 128.0
    return L


def _otsu(v):
    """Otsu-Schwelle einer 1-D-Werteliste (float)."""
    v = np.asarray(v, float)
    if v.size < 10 or v.max() - v.min() < 1e-6: return None
    h, e = np.histogram(v, 128); m = 0.5 * (e[1:] + e[:-1]); w0 = np.cumsum(h); w1 = w0[-1] - w0
    s0 = np.cumsum(h * m); mu0 = s0 / np.maximum(w0, 1); mu1 = (s0[-1] - s0) / np.maximum(w1, 1)
    k = int(np.argmax(w0 * w1 * (mu0 - mu1) ** 2)); return float(e[k + 1])


class Raster:
    """Wandbild-Ausschnitt: Pixel (i, j) <-> (u, z); u0, z1 = linke obere Ecke des GANZEN Bildes, c = Zellgroesse (m)."""
    def __init__(self, u0, z1, c, H, W): self.u0, self.z1, self.c, self.H, self.W = float(u0), float(z1), float(c), int(H), int(W)
    def ij(self, u, z): return int(round((self.z1 - z) / self.c)), int(round((u - self.u0) / self.c))
    def fenster(self, u0, u1, z0, z1):
        i0, j0 = self.ij(u0, z1); i1, j1 = self.ij(u1, z0)
        return max(0, i0), min(self.H, i1), max(0, j0), min(self.W, j1)


def loch_messen(bgr, R, zone, kleine_kaesten=(), dunkel=0.6, min_m=0.1, fuell_min=0.4, gewaende_min=0.15, gewaende_rand=0.10):
    """Loch und Gewaende in der Zone [u0, u1, z0, z1] eines Wandbilds (bgr, 0 = keine Fotozelle). Liefert dict mit 'loch' {u0,u1,z0,z1,...} und ggf.
    'gewaende' {umriss, flaeche_m2} oder 'fehler'."""
    import cv2
    u0, u1, z0, z1 = map(float, zone); bu, bz = u1 - u0, z1 - z0
    ru, rz = max(RAND * bu, RING[1] + 0.05), max(RAND * bz, RING[1] + 0.05); rw = RING_WEIT + 0.05
    i0, i1, j0, j1 = R.fenster(u0 - max(ru, rw), u1 + max(ru, rw), z0 - max(rz, rw), z1 + max(rz, rw))
    if i1 - i0 < 5 or j1 - j0 < 5: return dict(fehler="Zone ausserhalb des Wandbilds")
    A = np.asarray(bgr[i0:i1, j0:j1]); bel = A.reshape(-1, 3).sum(1).reshape(A.shape[:2]) > 0
    c = R.c; II, JJ = np.mgrid[i0:i1, j0:j1]; U = R.u0 + JJ * c; Z = R.z1 - II * c
    du = np.maximum(np.maximum(u0 - U, U - u1), 0.0); dz = np.maximum(np.maximum(z0 - Z, Z - z1), 0.0); d = np.hypot(du, dz)
    inn = (d == 0) & bel; ring = (d >= RING[0]) & (d <= RING[1]) & bel
    if inn.sum() < 50: return dict(fehler="Zone ohne Fotozellen im Wandbild")
    if ring.sum() < 50: return dict(fehler="kein Wandring mit Fotozellen um die Zone")
    lab = _lab(A)
    # Median statt P90: im Ring liegen oft Nachbarbauteile (Bossenquader, Schilder) - die Wand ist die Mehrheit; fuellt ein breites Gewaende den Ring: wandfarbe()
    wand, rausch, weit = wandfarbe(lab, d, bel); dist = np.linalg.norm(lab - wand, axis=2)
    schwelle = max(1.5 * rausch, 10.0)      # KEIN Otsu ueber die Zone: der trennt dann Tuerblatt gegen Sandstein statt Nicht-Wand gegen Wand (f04-Portal fiel weg)
    fremd = (dist > schwelle) & bel & (d <= (RING_WEIT if weit else max(ru, rz)))
    Lw = float(wand[0]); Lf = lab[..., 0]
    kand = fremd & (d == 0)
    if kand.sum() < 20: return dict(fehler=f"in der Zone kaum Nicht-Wand-Farbe (Schwelle {schwelle:.1f})", wand_L=round(Lw, 1))
    tL = _otsu(Lf[kand]); tL = min(tL if tL is not None else Lw, dunkel * Lw)
    dk = (Lf <= tL) & bel & (d <= 0.05 + 2 * c)
    # Farbton des Gewaendes (helle Nicht-Wand-Zellen): beschattete Gewaendeflaechen (Laibung im Schatten) sind dunkel, behalten aber den Farbton -
    # ist das Gewaende deutlich farbig (|a,b| > 8), zaehlen dunkle Zellen mit >= halbem Gewaende-Farbanteil nicht zum Loch (f04: Portal-Laibung im Schatten)
    hell = kand & (Lf > tL); gab = np.median(lab[hell][:, 1:], axis=0) if hell.sum() >= 20 else np.zeros(2); gn = float(np.hypot(*gab))
    if gn > 8.0:
        proj = (lab[..., 1] * gab[0] + lab[..., 2] * gab[1]) / gn; dk &= proj < 0.5 * gn
    k = max(3, 2 * int(round(0.02 / c)) + 1); dk = cv2.morphologyEx(dk.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    dk = cv2.morphologyEx(dk, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab_k, st, _ = cv2.connectedComponentsWithStats(dk, 8)
    if n <= 1: return dict(fehler="kein dunkles Loch in der Zone", wand_L=round(Lw, 1), schwelle_L=round(tL, 1))
    mu, mz = (u0 + u1) / 2, (z0 + z1) / 2; best = None
    for q in range(1, n):
        m = lab_k == q; fl = float(m.sum()) * c * c
        if fl < (min_m * min_m) * 0.5: continue
        cu, cz = float(U[m].mean()), float(Z[m].mean())
        if not (u0 <= cu <= u1 and z0 <= cz <= z1): continue
        wert = fl / (1.0 + np.hypot((cu - mu) / bu, (cz - mz) / bz))
        if best is None or wert > best[0]: best = (wert, q)
    if best is None: return dict(fehler="kein dunkles Loch (>= %.2f m) mit Mitte in der Zone" % min_m, wand_L=round(Lw, 1), schwelle_L=round(tL, 1))
    m = lab_k == best[1]
    lu0, lu1 = (float(np.percentile(U[m], p)) for p in (2, 98)); lz0, lz1 = (float(np.percentile(Z[m], p)) for p in (2, 98))
    lu0 -= c / 2; lu1 += c / 2; lz0 -= c / 2; lz1 += c / 2
    Lloch = float(np.median(Lf[m])); fuell = float(m.sum()) * c * c / max((lu1 - lu0) * (lz1 - lz0), 1e-9)
    if Lloch > dunkel * Lw: return dict(fehler=f"Loch nicht dunkel genug (L {Lloch:.0f} gegen Wand {Lw:.0f})")
    if lu1 - lu0 < min_m or lz1 - lz0 < min_m: return dict(fehler=f"Loch zu klein ({lu1 - lu0:.2f} x {lz1 - lz0:.2f} m)")
    if fuell < fuell_min: return dict(fehler=f"Loch fuellt seinen Kasten nur zu {fuell * 100:.0f} % (kein Rechteck/Bogen, eher Schatten/Fleck)")
    # angeschnitten: Lochrand neben Zellen ohne Foto -> Seite aus dem kleinsten Erkennerkasten, der das Loch enthaelt
    leer = cv2.dilate((~bel).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & m
    an = []
    if leer.any():
        for s_, wert, ach in (("oben", lz1, Z), ("unten", lz0, Z), ("links", lu0, U), ("rechts", lu1, U)):
            if np.any(np.abs(ach[leer] - wert) < 3 * c): an.append(s_)
    loch = dict(u0=round(lu0, 3), u1=round(lu1, 3), z0=round(lz0, 3), z1=round(lz1, 3), L=round(Lloch, 1), wand_L=round(Lw, 1), fuellung=round(fuell, 2))
    if an:
        kk = [k_ for k_ in kleine_kaesten if k_[0] <= (lu0 + lu1) / 2 <= k_[1] and k_[2] <= (lz0 + lz1) / 2 <= k_[3]]
        kk = [k_ for k_ in kk if (k_[1] - k_[0]) * (k_[3] - k_[2]) < bu * bz * 0.9]
        if kk:
            k_ = min(kk, key=lambda k_: (k_[1] - k_[0]) * (k_[3] - k_[2])); ersetzt = []
            for s_, idx, key in (("oben", 3, "z1"), ("unten", 2, "z0"), ("links", 0, "u0"), ("rechts", 1, "u1")):
                if s_ in an: loch[key] = round(max(loch[key], k_[idx]) if s_ in ("oben", "rechts") else min(loch[key], k_[idx]), 3); ersetzt.append(s_)
            loch["angeschnitten"] = an; loch["ersatz"] = f"Seiten {', '.join(ersetzt)} aus dem kleinsten Erkennerkasten {[round(x, 2) for x in k_[:4]]} (Wandbild dort ohne Fotozellen)"
        else: loch["angeschnitten"] = an
    if "oben" not in an:                                                  # Oberkante im Bild -> Bogenform aus dem Loch selbst (nicht aus dem Erkennerumriss)
        bg = bogen_aus_loch(m, U, Z, lu0, lu1, lz1, c)
        if bg: loch["bogen"] = bg                                         # Scheitel = Bogenoberkante; loch z1 bleibt der 98-%-Wert (Zonenvergleich wie bisher)
    out = dict(loch=loch, schwelle_farbe=round(schwelle, 1), schwelle_L=round(tL, 1))
    # Gewaende: Nicht-Wand-Zellen, die das Loch beruehren
    kw = 2 * int(round(0.10 / c)) + 1; mw = cv2.dilate(m.astype(np.uint8), np.ones((kw, kw), np.uint8)).astype(bool)
    fr = cv2.morphologyEx(fremd.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    n2, l2, _, _ = cv2.connectedComponentsWithStats(fr, 8); ids = set(np.unique(l2[mw & (fr > 0)])) - {0}
    g = np.isin(l2, list(ids)) & ~cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) if ids else np.zeros_like(m)
    nahe_g = g & (d <= gewaende_rand)
    if weit and nahe_g.sum() >= 20:
        # 24.11.2026 (1122w Sued f01): das Gewaende fuellt den Wandring -> es reicht ueber 'gewaende_rand' hinaus (Keilsteinfaecher 0,8 m). Weiter als der Rand nur
        # bis zur Lochbreite/-hoehe UND nur in der Farbe des Gewaendes am Loch (Median der Gewaendezellen am Rand): Schild/Bruchstein-Eckquader neben einem
        # Portal (Schwabentor f04) haben eine andere Farbe und bleiben draussen; danach nur, was mit dem Loch zusammenhaengt.
        out["wand_weit"] = True; weit_rand = min(RING_WEIT, max(gewaende_rand, min(lu1 - lu0, lz1 - lz0)))
        gc = np.median(lab[nahe_g], axis=0); dg = np.linalg.norm(lab - gc, axis=2); tg = max(12.0, 2.5 * float(np.median(dg[nahe_g])))
        g2 = (g & (d <= weit_rand) & (dg <= tg)) | nahe_g
        g2 = cv2.morphologyEx(g2.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2 * int(round(0.03 / c)) + 1,) * 2, np.uint8))
        n3, l3, _, _ = cv2.connectedComponentsWithStats(g2, 8); ids3 = set(np.unique(l3[mw & (g2 > 0)])) - {0}
        g = np.isin(l3, list(ids3)) if ids3 else nahe_g
        out["gewaende_farbe_lab"] = [round(float(x), 1) for x in gc]
    else: g = nahe_g                                                      # nur Zone + Rand: angrenzende fremde Bauteile (Eckquader des Turms, Schilder) sind kein Gewaende
    ko = 2 * int(round(0.03 / c)) + 1; g = cv2.morphologyEx(g.astype(np.uint8), cv2.MORPH_OPEN, np.ones((ko, ko), np.uint8)).astype(bool)   # Fransen < 3 cm weg (druckbar)
    gfl = float(g.sum()) * c * c
    if gfl >= gewaende_min * float(m.sum()) * c * c:
        voll = (g | cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)).astype(np.uint8)    # Loch + Gewaende EIN Umriss (g spart 1 px um das Loch aus)
        cs, _ = cv2.findContours(voll, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cs = sorted(cs, key=cv2.contourArea, reverse=True)[:1]
        if cs:
            P = cv2.approxPolyDP(cs[0], max(1.0, 0.02 / c), True)[:, 0, :]
            um = [[round(R.u0 + (j0 + p[0]) * c, 3), round(R.z1 - (i0 + p[1]) * c, 3)] for p in P]
            if len(um) >= 3:
                out["gewaende"] = dict(umriss=um, flaeche_m2=round(gfl, 3))
    out["_masken"] = (i0, j0, m, g)
    return out


def sweep_werte(npz, umriss, loch, ring=RING, min_gut=0.3):
    """Tiefe je Zelle (Ebenen-Sweep, w positiv = vor der Wand) gegen den WANDRING AUSSERHALB des Gewaendes (0,15-0,45 m um Gewaende + Loch):
    (hoehe, tiefe) = (Gewaende-Median - Wand, Wand - Loch-Median). hoehe nur 0,02-0,30 m plausibel, tiefe nur 0,02-1,0 m (sonst None: Glas/Tuerblatt ohne Textur,
    Mehrdeutigkeit auf glattem Putz - nischen_fenster.plausibel gilt auch hier). Ohne Gewaende-Umriss: Ring um das Loch."""
    import cv2
    if npz is None: return None, None
    import nischen_fenster as NF
    w, gut = npz["w"], npz["gut"].astype(bool); c = float(npz["zelle"]); u0, z1 = float(npz["u0"]), float(npz["z1"]); H, W = w.shape
    a_ = lambda u, z: (int(round((u - u0) / c)), int(round((z1 - z) / c)))
    li = np.zeros((H, W), np.uint8); cv2.rectangle(li, a_(loch["u0"], loch["z1"]), a_(loch["u1"], loch["z0"]), 1, -1); li = li.astype(bool)
    voll = li.astype(np.uint8).copy()
    if umriss:
        P = np.array([[(u - u0) / c, (z1 - z) / c] for u, z in umriss]).round().astype(np.int32); cv2.fillPoly(voll, [P], 1)
    g = voll.astype(bool) & ~li
    k1, k0 = 2 * int(round(ring[1] / c)) + 1, 2 * int(round(ring[0] / c)) + 1
    r = cv2.dilate(voll, np.ones((k1, k1), np.uint8)).astype(bool) & ~cv2.dilate(voll, np.ones((k0, k0), np.uint8)).astype(bool)
    if not r.any() or gut[r].mean() < min_gut: return None, None
    gut = gut & NF.plausibel(w, gut, r); wand = float(np.median(w[r & gut]))
    h = t = None
    if umriss and (g & gut).sum() >= 5: d = float(np.median(w[g & gut])) - wand; h = round(d, 3) if 0.02 <= d <= 0.30 else None
    if li.any() and gut[li].mean() >= min_gut: d = wand - float(np.median(w[li & gut])); t = round(d, 3) if 0.02 <= d <= 1.0 else None
    return h, t


def druck_min():
    return float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0


def eintrag_anpassen(e, erg, npz, fenster_tiefe=0.12):
    """Fensterlisten-Eintrag e mit dem Messergebnis erg (loch_messen) anpassen. Liefert Urteilstext."""
    L = erg["loch"]; bu, bz = e["u1"] - e["u0"], e["z1"] - e["z0"]; lb, lh = L["u1"] - L["u0"], L["z1"] - L["z0"]
    if lb * lh > 0.9 * bu * bz:
        e["loch"] = dict(L, quelle="loch_gewaende: Zone war schon das Loch")
        tx = "Zone = Loch (unveraendert)"
        if L.get("bogen") and (e.get("bogen") or {}).get("form", "gerade") == "gerade":                # Bogen am Loch gemessen, Eintrag ohne Bogen (s. u.)
            e.update(u0=L["u0"], u1=L["u1"]); tx = "Zone = Loch (Seiten aus dem Loch)"
    else:
        gleich = abs(lb - bu) <= 0.25 * bu and abs(lh - bz) <= 0.25 * bz
        alt = dict(u0=e["u0"], u1=e["u1"], z0=e["z0"], z1=e["z1"])
        e.update(u0=L["u0"], u1=L["u1"], z0=L["z0"], z1=L["z1"]); e["loch"] = dict(L, zone_vorher=alt, quelle="loch_gewaende: dunkle Komponente im feinen Wandbild")
        b_ = e.get("bogen")
        if b_ and b_.get("form", "gerade") != "gerade":
            if gleich:
                # 24.11.2026 (Schwabentor-1122 Sued, Stichbogen k 24,46 / s 24,61, Loch oben 24,21): min(kaempfer, z1) gab kaempfer = scheitel -> Stich 0 -> Generator
                # ZeroDivisionError in bauteile.stichbogen. Jetzt: gemessene Bogenhoehe (scheitel - kaempfer) am neuen Scheitel behalten, hoechstens bis z0.
                k_, s_ = b_.get("kaempfer"), b_.get("scheitel"); h_ = (s_ - k_) if (k_ is not None and s_ is not None) else 0.0
                h_ = min(max(h_, 0.0), e["z1"] - e["z0"])
                e["bogen"] = dict(b_, scheitel=e["z1"], kaempfer=round(e["z1"] - h_, 3)) if h_ > 1e-3 else dict(form="gerade", kaempfer=e["z1"], scheitel=e["z1"])
            else:
                e["form_vorher"] = b_; e["bogen"] = dict(form="gerade", kaempfer=e["z1"], scheitel=e["z1"])
                e["form_quelle"] = f"loch_gewaende: Bogen '{b_.get('form')}' war die Form des Gewaendes/Farbfelds ({bu:.2f} m), Loch {lb:.2f} x {lh:.2f} m -> Rechteck"
        if not e.get("bogen"): e["bogen"] = dict(form="gerade", kaempfer=e["z1"], scheitel=e["z1"]); e.setdefault("form_quelle", "loch_gewaende: Kasten der dunklen Komponente (Rechteck)")
        e["scheiben"] = 1; e["teiler"] = []; e["sprossen"] = []
        tx = f"LOCH {lb:.2f} x {lh:.2f} m statt Zone {bu:.2f} x {bz:.2f} m"
    gb = L.get("bogen")
    if gb and gb.get("scheitel") is not None:
        # 24.11.2026 (1122w Sued f01): gemessene Oberkante des Lochs schlaegt die geerbte Form (Erkennerumriss / Stichhoehe vom Gewaende)
        # Nur wenn der Eintrag KEINEN Bogen hat (gerade / verworfen): ein Bogen aus nischen_fenster (Kanten in >= 3 Einzelfotos) bleibt - die Oberkante EINER dunklen
        # Komponente ist bei Gitter/Schatten im Bogenfeld unsicherer (Schwabentor Nord f00: rund aus den Kanten, Komponente nur Stich 8 cm).
        b_ = e.get("bogen") or {}
        if b_.get("form", "gerade") == "gerade" and (b_.get("form"), b_.get("kaempfer")) != (gb["form"], gb["kaempfer"]):
            e.setdefault("form_vorher", b_); e["z1"] = gb["scheitel"]; e["bogen"] = dict(form=gb["form"], kaempfer=gb["kaempfer"], scheitel=gb["scheitel"])
            e["form_quelle"] = f"loch_gewaende: Oberkante der dunklen Komponente im Wandbild ({gb['form']}, Pfeil {gb['scheitel'] - gb['kaempfer']:.2f} m, Rest {gb['rest_m']:.3f} m)"
            tx += f", Bogen {gb['form']} aus dem Loch"
    G = erg.get("gewaende")
    h, t = sweep_werte(npz, (G or {}).get("umriss"), e)
    if t is not None:
        e["tiefe"] = t; e["tiefe_quelle"] = "Ebenen-Sweep: Loch gegen den Wandring ausserhalb des Gewaendes (loch_gewaende, Tiefe je Zelle)"
        tx += f", Laibung {t:.2f} m (Sweep)"
    elif e.get("tiefe") is None or "ANNAHME" in str(e.get("tiefe_quelle", "")):
        e["tiefe"] = e.get("tiefe") or fenster_tiefe; e["tiefe_quelle"] = f"ANNAHME {e['tiefe']} m (Sweep im Loch nicht messbar); Bau mindestens Druckmindestmass"
    if G:
        e["gewaende"] = dict(umriss=G["umriss"], flaeche_m2=G["flaeche_m2"], hoehe=h if h is not None else round(druck_min(), 3),
                             hoehe_quelle="Ebenen-Sweep (Gewaende gegen Wandring)" if h is not None else
                             "ANNAHME Druckmindestmass (MINMM x SCALE) - Sweep misst das Gewaende nicht (0,02-0,30 m vor der Wand)",
                             quelle="loch_gewaende: Nicht-Wand-Farbe am Loch im feinen Wandbild (Lab-Abstand zum Wandring > 3 x Median-Abstand im Ring, mind. 10)")
        tx += f", Gewaende {G['flaeche_m2']:.2f} m2 ({len(G['umriss'])} Ecken)"
    return tx


def tueren(oeff, oeff_auto, fenster):
    """Geschlossene Tueren aus oeffnungen_aussen.json: klasse 'tuer', flach (kein Durchblick), keine gebaute Oeffnung und kein Fenster an der Stelle."""
    out = {}
    ueber = lambda a, b: min(a[1], b[1]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[2], b[2])
    for fid, F in (oeff or {}).items():
        if not isinstance(F, dict): continue
        geb = [x.get("kasten") for x in ((oeff_auto or {}).get(fid) or {}).get("oeffnungen", []) if x.get("gebaut") and x.get("kasten")]
        fe = [(q["u0"], q["u1"], q["z0"], q["z1"]) for q in ((fenster or {}).get(fid) or {}).get("fenster", [])]
        for e in F.get("oeffnungen", []):
            if e.get("klasse") != "tuer" or not e.get("flach") or not e.get("zone"): continue
            z = e["zone"]
            if any(ueber(z, g) for g in geb) or any(ueber(z, q) for q in fe): continue
            st = max([x.get("stimmen", 0) for x in ((oeff_auto or {}).get(fid) or {}).get("oeffnungen", []) if x.get("kasten") and ueber(z, x["kasten"])] + [2])
            out.setdefault(fid, []).append(dict(u0=z[0], u1=z[1], z0=z[2], z1=z[3], teiler=[], kaempfer=None, scheiben=1, stimmen_min=int(st), sprossen=[], art="tuer",
                                                quelle="loch_gewaende: geschlossene Tuer aus oeffnungen_aussen.json (klasse tuer, kein Durchblick) -> Loch/Gewaende aus dem Wandbild"))
    return out


def wandbild(fein, fid):
    """Feines Wandbild wie oeffnungen_wandbild/uhren_wandbild: ortho_<id>_fein.png (fassade_fein, Mehrfoto-Median ausgerichtet); wo es leer ist, ortho_<id>.png
    auf demselben Raster. None = keins da."""
    import cv2
    p1, p0 = os.path.join(fein, f"ortho_{fid}_fein.png"), os.path.join(fein, f"ortho_{fid}.png")
    a = cv2.imread(p1, cv2.IMREAD_COLOR) if os.path.exists(p1) else None; b = cv2.imread(p0, cv2.IMREAD_COLOR) if os.path.exists(p0) else None
    if a is None: return b
    if b is not None and b.shape == a.shape:
        leer = a.sum(2) == 0; a[leer] = b[leer]
    return a


def kontrollbild(bgr, R, eintraege, pfad, rand=0.8):
    import cv2
    if not eintraege: return
    Zs = [x["zone"] for x in eintraege]
    i0, i1, j0, j1 = R.fenster(min(z[0] for z in Zs) - rand, max(z[1] for z in Zs) + rand, min(z[2] for z in Zs) - rand, max(z[3] for z in Zs) + rand)
    im = np.ascontiguousarray(bgr[i0:i1, j0:j1]).copy()
    P = lambda u, z: (int(round((u - R.u0) / R.c)) - j0, int(round((R.z1 - z) / R.c)) - i0)
    for x in eintraege:
        z = x["zone"]; cv2.rectangle(im, P(z[0], z[3]), P(z[1], z[2]), (160, 160, 160), 1)
        if x.get("gewaende"):
            cv2.polylines(im, [np.array([P(u, zz) for u, zz in x["gewaende"]["umriss"]], np.int32)], True, (0, 220, 255), 2)
        if x.get("loch"):
            L = x["loch"]; cv2.rectangle(im, P(L["u0"], L["z1"]), P(L["u1"], L["z0"]), (0, 0, 255), 2)
        cv2.putText(im, x["urteil"][:50], (P(z[0], z[3])[0], max(12, P(z[0], z[3])[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 120, 0), 1)
    s = 900.0 / max(im.shape[:2]); im = cv2.resize(im, None, fx=s, fy=s) if s < 1 else im
    cv2.imwrite(pfad, im)


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("fenster"); ap.add_argument("ordner"); ap.add_argument("fein")
    ap.add_argument("--oeffnungen", help="audit/oeffnungen_aussen.json (geschlossene Tueren)"); ap.add_argument("--oeffnungen_auto", help="audit/oeffnungen_auto.json (gebaute Oeffnungen)")
    ap.add_argument("--nur", nargs="*"); ap.add_argument("--aus"); ap.add_argument("--dunkel", type=float, default=0.6, help="Loch-Helligkeit hoechstens so viel x Wand-L")
    ap.add_argument("--fenster_tiefe", type=float, default=0.12, help="ANNAHME wie nischen_fenster/bauteile.fenster_aus_json")
    a = ap.parse_args(argv)
    import cv2
    aus = a.aus or os.path.dirname(os.path.abspath(a.fenster)); os.makedirs(aus, exist_ok=True)
    J = json.load(open(a.fenster)); FF = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    try: E = json.load(open(os.path.join(a.ordner, "elemente.json")))["fassaden"]
    except Exception: E = {}
    lies = lambda p: json.load(open(p)) if p and os.path.exists(p) else None
    T = tueren(lies(a.oeffnungen), lies(a.oeffnungen_auto), J)
    bericht = {}; n_ok = 0
    for fid in sorted(set(k for k, v in J.items() if isinstance(v, dict) and "fenster" in v) | set(T)):
        if a.nur and fid not in a.nur: continue
        if fid not in J:
            F0 = (lies(a.oeffnungen) or {}).get(fid) or {}; J[fid] = dict(o=F0.get("o"), d=F0.get("d"), n=F0.get("n"), fenster=[])
        F = J[fid]; bgr = wandbild(a.fein, fid)
        if fid not in FF or bgr is None: bericht[fid] = "kein feines Wandbild"; continue
        rs = FF[fid]["raster"]; R = Raster(rs["u0"], rs["z1"], rs["zelle"], *bgr.shape[:2])
        nz = os.path.join(a.ordner, f"tiefe_{fid}.npz"); npz = dict(np.load(nz)) if os.path.exists(nz) else None
        kl = [(e["u0"], e["u1"], e["z0"], e["z1"]) for e in (E.get(fid) or {}).get("elemente", []) if e.get("klasse") in ("fenster", "tuer", "bogen")]
        br = []; neu_tueren = []
        for e in list(F["fenster"]) + T.get(fid, []):
            r = dict(zone=[round(e[k], 3) for k in ("u0", "u1", "z0", "z1")], art=e.get("art", "fenster"))
            if e.get("nische"): r["urteil"] = "uebersprungen: Fenster in Nische (nischen_fenster, zwei Ebenen)"; br.append(r); continue
            if e.get("loch"): r["urteil"] = "uebersprungen: schon vermessen (zweiter Lauf auf derselben Liste)"; br.append(r); continue
            erg = loch_messen(bgr, R, r["zone"], kl, dunkel=a.dunkel)
            if "fehler" in erg:
                r["urteil"] = "unveraendert: " + erg["fehler"]; br.append(r); continue
            erg.pop("_masken", None)
            r["urteil"] = eintrag_anpassen(e, erg, npz, a.fenster_tiefe); r["loch"] = e.get("loch"); r["gewaende"] = e.get("gewaende"); n_ok += 1; br.append(r)
            if e.get("art") == "tuer": neu_tueren.append(e)
        F["fenster"] = F["fenster"] + neu_tueren
        bericht[fid] = br; kontrollbild(bgr, R, br, os.path.join(aus, f"loch_gewaende_{fid}.jpg"))
        for r in br: print(f"{fid} {r['art']} {r['zone']}: {r['urteil']}")
    json.dump(bericht, open(os.path.join(aus, "loch_gewaende.json"), "w"), indent=1, ensure_ascii=False)
    if not n_ok: print("kein Loch vermessen - Fensterliste unveraendert"); return 3
    ziel = os.path.join(aus, os.path.basename(a.fenster))
    if os.path.abspath(ziel) == os.path.abspath(a.fenster): shutil.copy(a.fenster, a.fenster[:-5] + "_vor_loch.json")
    json.dump(J, open(ziel, "w"), indent=1, ensure_ascii=False)
    print(f"-> {ziel}: {n_ok} Loch/Loecher vermessen"); return 0


if __name__ == "__main__": sys.exit(main())
