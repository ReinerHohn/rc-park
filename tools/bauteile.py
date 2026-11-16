#!/usr/bin/env python3
"""bauteile.py - gemeinsame Bausteine fuer Generatoren (herausgezogen aus modelle/schwab_v3_gen.py, 15.11.2026, Nutzer: "so gut muss der Rest auch werden").

Alle Bauteile werden in WANDKOORDINATEN gebaut: u = waagerecht entlang der Wand ab Ecke a Richtung b, z = Hoehe, w = Abstand VOR der Wandebene (nach aussen).
Die Wand selbst (Ebene durch zwei am Foto gepeilte Ecken) liefert Wand(a, b, aussen). Masse kommen aus foto_mass.py-Protokollen; Picks bequem ueber
tools/wand_ortho.py. Reihenfolge im Generator: Relief (relief_einsatz.koerper) zur Wand addieren -> Oeffnungen abziehen -> Anbauten addieren.
  from bauteile import Wand, spitzbogen, rundbogen
  W = Wand((3.72, 9.22), (3.54, 21.38), aussen=(10, 15))
  rumpf = rumpf - W.prisma(spitzbogen(2.3, 4.3, 6.9), u=6.1, w0=-15, w1=1)          # Tordurchfahrt
  rumpf = rumpf - W.prisma(rundbogen(2.1, 24.2, 26.7), u=4.0, w0=-0.15, w1=0.6)      # Blendnische
  rumpf = rumpf + W.kasten(1.9, 10.5, 10.95, 11.3, -0.05, 1.55)                      # Galerieboden
"""
import numpy as np
from manifold3d import Manifold as M, CrossSection


def spitzbogen(halb, kaempfer, scheitel, unten=-0.6, nseg=24, tief=0.3):
    """Querschnitt (quer, hoch) eines Spitzbogens aus zwei Kreisboegen: halbe lichte Breite, Kaempferhoehe, Scheitelhoehe; Pfeiler bis 'unten'."""
    h = scheitel - kaempfer
    if h < halb:                                                          # GEDRUECKTER Spitzbogen: zwei Kreisboegen, Mittelpunkte UNTER der Kaempferlinie (tief = 0,3 x halbe Breite, ANNAHME) -
        d = tief * halb; c = (h * h + 2 * h * d - halb * halb) / (2 * halb); r = float(np.hypot(halb + c, d)); w_a = np.arctan2(d, halb + c); w_b = np.arctan2(h + d, c)      # 16.11.2026: erst waagerechter Sturz (falsch), dann Vier-Zentren-Bogen
        re = [[-c + r * np.cos(w), kaempfer - d + r * np.sin(w)] for w in np.linspace(w_a, w_b, nseg)]                                                                      # (Nutzerbild: "spitzes Fehlerding" - Schultern zu flach, Spitze aufgesetzt); Foto zeigt glatte Boegen bis zur Spitze
        return CrossSection([[[-halb, unten], [halb, unten]] + re[:-1] + [[-x, z] for x, z in re[::-1]]])
    r = (halb * halb + h * h) / (2 * halb); w0 = np.arcsin(h / r)
    re = [[-(r - halb) + r * np.cos(w), kaempfer + r * np.sin(w)] for w in np.linspace(0, w0, nseg)]
    return CrossSection([[[-halb, unten], [halb, unten]] + re[:-1] + [[-x, z] for x, z in re[::-1]]])


def rundbogen(breite, unten, scheitel, nseg=20):
    """Querschnitt (quer, hoch) einer Rundbogenoeffnung: Breite, Unterkante, Scheitel (Halbkreis oben)."""
    r = breite / 2; return CrossSection([[[-r, unten], [r, unten]] + [[r * np.cos(w), scheitel - r + r * np.sin(w)] for w in np.linspace(0, np.pi, nseg)]])


class Wand:
    """Senkrechte Wandebene durch die Ecken a, b (Grundriss, Modellrahmen); 'aussen' = irgendein Punkt vor der Wand."""
    def __init__(self, a, b, aussen):
        self.a = np.array(a, float); b = np.array(b, float); self.t = (b - self.a) / np.linalg.norm(b - self.a); n = np.array([self.t[1], -self.t[0]])
        self.n = n if (np.array(aussen, float) - self.a) @ n > 0 else -n; self.laenge = float(np.linalg.norm(b - self.a))
        self.spiegel = (self.t[0] * self.n[1] - self.t[1] * self.n[0]) > 0          # (t, z, n) linkshaendig -> Querschnitte in u spiegeln, damit die Matrix eine Drehung bleibt
    def matrix(self, u0=0.0):
        s = -1.0 if self.spiegel else 1.0; o = self.a + u0 * self.t
        return [[s * self.t[0], 0.0, self.n[0], o[0]], [s * self.t[1], 0.0, self.n[1], o[1]], [0.0, 1.0, 0.0, 0.0]]
    def punkt(self, u, z, w=0.0): return [self.a[0] + u * self.t[0] + w * self.n[0], self.a[1] + u * self.t[1] + w * self.n[1], z]
    def prisma(self, querschnitt, u, w0, w1):
        """Querschnitt (quer um u, hoch = z) von w0 bis w1 durch die Wand ziehen (w0 < 0 = in die Wand hinein)."""
        return M.extrude(querschnitt, w1 - w0).translate((0, 0, w0)).transform(self.matrix(u))
    def kasten(self, u0, u1, z0, z1, w0, w1): return M.hull_points([self.punkt(u, z, w) for u in (u0, u1) for z in (z0, z1) for w in (w0, w1)])
    def huelle(self, pts): return M.hull_points([self.punkt(u, z, w) for u, z, w in pts])
    def scheibe(self, u, z, durchmesser, w0, w1, nseg=64): return M.cylinder(w1 - w0, durchmesser / 2, durchmesser / 2, nseg).translate((0, 0, w0)).transform(self.matrix(u)).translate((0, 0, z))
    def fenster(self, u0, u1, z0, z1, w, tiefe=0.12, teiler=(), kaempfer=None, b=0.07, rahmen=0.05, sprossen=(), b_sprosse=0.03):
        """Rechteckfenster in einer Wandflaeche bei w: liefert (abzug, zusatz). Nische 'tiefe' tief; Rahmen, Pfosten (teiler = u-Lagen) und Kaempfer (z) 'b' breit,
        5 cm hinter der Wandflaeche (so misst pruefstand.ebene_oeffnungen mit tiefe 0,03 die volle Nischenbreite). koerper = koerper - abzug + zusatz."""
        v0, v1 = w - tiefe - 0.01, w - 0.05; K_ = self.kasten; e = 0.005          # e: Rahmen greifen 5 mm in die Laibung (deckungsgleiche Flaechen gaben Splitterkoerper)
        zus = K_(u0 - e, u0 + rahmen, z0 - e, z1 + e, v0, v1) + K_(u1 - rahmen, u1 + e, z0 - e, z1 + e, v0, v1) + K_(u0 - e, u1 + e, z0 - e, z0 + rahmen, v0, v1) + K_(u0 - e, u1 + e, z1 - rahmen, z1 + e, v0, v1)
        for t_ in teiler: zus = zus + K_(t_ - b / 2, t_ + b / 2, z0 - e, z1 + e, v0, v1)
        if kaempfer: zus = zus + K_(u0 - e, u1 + e, kaempfer - b / 2, kaempfer + b / 2, v0, v1)
        for a0, c0, a1, c1 in sprossen: zus = zus + self.stab((a0, c0), (a1, c1), b_sprosse, v0, v1 - 0.01)      # Sprossen (u0, z0, u1, z1) aus fenster_aus_parsing.py, 1 cm hinter den Pfosten
        DURCH.append((self, u0, u1, z0, z1, w - tiefe))                    # fuer aushoehlen(): Fenster = echtes Loch (Nutzer 16.11.2026)
        return K_(u0, u1, z0, z1, w - tiefe, w + 0.02), zus
    def stab(self, p, q, b, w0, w1):
        """Gerader Stab von p = (u, z) nach q = (u, z), Breite b, von w0 bis w1 vor der Wand (Zeiger, Ziffernstriche, Leisten)."""
        p = np.array(p, float); q = np.array(q, float); d = q - p; d = d / np.linalg.norm(d); s = np.array([-d[1], d[0]]) * b / 2
        return self.huelle([(c[0], c[1], w_) for c in (p + s, p - s, q + s, q - s) for w_ in (w0, w1)])
    def galerie(self, u0, u1, z_boden, z_holm, z_dach, w, pfosten=3, streben=6, z_fuss=None, boden=0.35, b=0.22, tafeln=True, knaggen=True, w_wand=-0.05):
        """Auskragende Holzgalerie / Holzerker vor einer Wand (GENERISCH, Nutzer 16.11.2026: "lerne daraus und baue generische Tools").
        u0..u1 Breite, z_boden Unterkante Schwelle, z_holm Oberkante Bruestung, z_dach Oberkante der Pfosten (Anschluss Vordach), w Ausladung.
        Teile: Bodenplatte, Schwelle und Holm als vorstehende Riegel, geschlossene Bruestung, 'pfosten' Pfosten (Zahl oder Liste von u-Lagen),
        tafeln=True: Fuellung zwischen den Pfosten oberhalb des Holms (bemalte Tafeln, verglaste oder verbretterte Felder), 7 cm hinter der Pfostenflucht;
        knaggen=True: dreieckige Knaggen beidseits jedes Pfostens im Bruestungsband; 'streben' Kopfstreben vom Wandfuss z_fuss unter den Boden (0 = keine).
        Gemessen werden muessen nur u0, u1, z_boden, z_holm, z_dach, w und die Zahlen (am Foto zaehlen); Querschnitte sind Standardwerte = ANNAHME."""
        K = self.kasten; ups = list(np.linspace(u0 + b / 2, u1 - b / 2, pfosten)) if np.isscalar(pfosten) else list(pfosten)
        g = K(u0, u1, z_boden, z_boden + boden, w_wand, w) + K(u0, u1, z_boden, z_holm, w - 0.15, w) + K(u0, u0 + 0.15, z_boden, z_holm, w_wand, w) + K(u1 - 0.15, u1, z_boden, z_holm, w_wand, w)
        g = g + K(u0 - 0.05, u1 + 0.05, z_holm - 0.20, z_holm + 0.08, w - b, w + 0.06) + K(u0 - 0.05, u1 + 0.05, z_boden, z_boden + 0.22, w - b, w + 0.05)       # Holm und Schwelle stehen vor
        for up in ups:
            g = g + K(up - b / 2, up + b / 2, z_boden, z_dach, w - b, w + 0.02)
            if knaggen:
                for sg in (-1.0, 1.0):
                    if u0 + 0.3 < up + sg * 0.5 < u1 - 0.3: g = g + self.huelle([(up + sg * b / 2, z_holm - 0.2, w_) for w_ in (w - 0.02, w + 0.04)] + [(up + sg * (b / 2 + 0.38), z_holm - 0.2, w_) for w_ in (w - 0.02, w + 0.04)] + [(up + sg * b / 2, z_holm - 0.62, w_) for w_ in (w - 0.02, w + 0.04)])
        if tafeln:
            for ua, ub in zip(ups[:-1], ups[1:]): g = g + K(ua + b / 2 - 0.01, ub - b / 2 + 0.01, z_holm, z_dach, w - 0.17, w - 0.07)
            g = g + K(u0, u0 + 0.1, z_holm, z_dach, w_wand, w - 0.05) + K(u1 - 0.1, u1, z_holm, z_dach, w_wand, w - 0.05)                                      # Seiten geschlossen
        if streben and z_fuss is not None:
            for us in np.linspace(u0 + 0.3, u1 - 0.3, streben):
                g = g + self.huelle([(us + du, z_boden, w_) for du in (-0.1, 0.1) for w_ in (w - 0.3, w - 0.05)] + [(us + du, z_, w_wand) for du in (-0.1, 0.1) for z_ in (z_fuss, z_fuss + 0.35)])
        return g
    def ortgang_quader(self, first_u, first_z, steigung, bloecke, w, laenge=(0.65, 0.42), schicht=0.30, staerke=0.04, rand=0.25):
        """Stufenquader entlang der Ortgaenge eines Steilgiebels (GENERISCH): je Block (seite +1/-1 = Richtung +u/-u vom First, z_oben, z_unten) liegen Quader am Ortgang
        und greifen abwechselnd lang/kurz in die Giebelflaeche (Schichthoehe ~'schicht'). Platte 'staerke' vor der Wandflaeche w. rand = Abstand der Quaderaussenkante
        von der Ortganglinie (Dachueberstand/Ortgangbrett). Zu messen: First (u, z), Neigung dz/du, je Block z_oben/z_unten; Laengen = Standard (am Foto pruefen)."""
        k = None
        for seite, zo, zu in bloecke:
            n = max(1, int(round((zo - zu) / schicht))); h = (zo - zu) / n
            for i in range(n):
                z1 = zo - i * h; z0 = z1 - h; ua = first_u + seite * ((first_z - z0) / steigung - rand); L = laenge[i % 2]       # Aussenkante am unteren Blockrand auf der Ortganglinie
                q = self.huelle([(u_, z_, w_) for w_ in (w - 0.01, w + staerke) for u_, z_ in ((ua, z0), (ua - seite * L, z0), (ua - seite * L, z1 - 0.01), (ua - seite * h / steigung, z1 - 0.01))])
                k = q if k is None else k + q
        return k
    def linienzug(self, pts, b, w0, w1):
        """Stab entlang eines Linienzugs (u, z)-Punkte (Masswerk, Ranken, geschwungene Leisten)."""
        k = None
        for p, q in zip(pts[:-1], pts[1:]):
            if np.hypot(q[0] - p[0], q[1] - p[1]) < 1e-4: continue
            s_ = self.stab(p, q, b, w0, w1); k = s_ if k is None else k + s_
        return k
    def masswerk_fischblase(self, u0, u1, z0, z1, w0, w1, b=0.07, n=14):
        """Vereinfachtes Fischblasen-Masswerk fuer ein Bruestungsfeld (spaetgotisch): Ring in der Mitte mit S-Schwung (zwei Blasen), links und rechts je zwei
        spitz zulaufende Blasen (Bogenstaebe zur Feldmitte der Schmalseite) und eine Mittelrippe. Form nach Foto 113529 (Loggia Schwabentor-Nachbarhaus), Einzelkurven ANNAHME.
        Liefert die Staebe; das Feld vorher ausschneiden: koerper - kasten(u0, u1, z0, z1, ...) + masswerk."""
        cu, cz = 0.5 * (u0 + u1), 0.5 * (z0 + z1); h = 0.5 * (z1 - z0); L = 0.5 * (u1 - u0); R = min(h - b / 2, 0.45 * L); t = np.linspace(0, 1, n)
        ring = [(cu + R * np.cos(a_), cz + R * np.sin(a_)) for a_ in np.linspace(0, 2 * np.pi, 33)]
        s_kurve = [(cu + 0.5 * R * np.sin(a_), cz + 0.5 * R + 0.5 * R * np.cos(a_)) for a_ in np.linspace(0, np.pi, n)] + [(cu - 0.5 * R * np.sin(a_), cz - 0.5 * R + 0.5 * R * np.cos(a_)) for a_ in np.linspace(0, np.pi, n)]
        k = self.linienzug(ring, b, w0, w1) + self.linienzug(s_kurve, b, w0, w1)
        def bez(p0, p1, p2): return [((1 - x) ** 2 * p0[0] + 2 * x * (1 - x) * p1[0] + x * x * p2[0], (1 - x) ** 2 * p0[1] + 2 * x * (1 - x) * p1[1] + x * x * p2[1]) for x in t]
        for sg in (-1.0, 1.0):
            e = cu + sg * (L + 0.01); a0 = cu + sg * R * 0.8
            for sz in (-1.0, 1.0):
                k = k + self.linienzug(bez((a0, cz + sz * R * 0.6), (cu + sg * 0.5 * (R + L), cz + sz * (h + 0.25 * h)), (e, cz + sz * 0.15 * h)), b, w0, w1)       # aeusserer Blasenbogen
                k = k + self.linienzug(bez((cu + sg * R, cz), (cu + sg * 0.5 * (R + L), cz + sz * 0.55 * h), (e, cz + sz * 0.9 * h)), b, w0, w1)                 # innerer Gegenschwung zur Feldecke
        return k ^ self.kasten(u0 - 0.01, u1 + 0.01, z0 - 0.01, z1 + 0.01, w0 - 0.01, w1 + 0.01)
    def blendfeld_mandel(self, u0, u1, z0, z1, w, tiefe=0.04, b=0.05, n=16):
        """Blendmasswerk-Feld (NICHT durchbrochen): vertieftes Feld mit stehender Mandel (zwei Spitzboegen) und S-Schwung darin - Bruestungsfelder spaetgotischer Erker.
        Liefert (abzug, zusatz) wie fenster(): koerper = koerper - abzug + zusatz. Zu messen: Feldrechteck; Kurven nach Foto 113857 vereinfacht (ANNAHME)."""
        cu, cz = 0.5 * (u0 + u1), 0.5 * (z0 + z1); h = 0.5 * (z1 - z0) - b; L = min(0.5 * (u1 - u0) - b, 0.55 * h); t = np.linspace(0, 1, n); w0, w1 = w - tiefe - 0.01, w
        def bez(p0, p1, p2): return [((1 - x) ** 2 * p0[0] + 2 * x * (1 - x) * p1[0] + x * x * p2[0], (1 - x) ** 2 * p0[1] + 2 * x * (1 - x) * p1[1] + x * x * p2[1]) for x in t]
        k = None
        for sg in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                s_ = self.linienzug(bez((cu + sg * L, cz), (cu + sg * L, cz + sz * 0.65 * h), (cu, cz + sz * h)), b, w0, w1); k = s_ if k is None else k + s_
        k = k + self.linienzug(bez((cu, cz + h), (cu + 0.9 * L, cz + 0.45 * h), (cu, cz)) + bez((cu, cz), (cu - 0.9 * L, cz - 0.45 * h), (cu, cz - h)), b, w0, w1)
        return self.kasten(u0, u1, z0, z1, w - tiefe, w + 0.02), k ^ self.kasten(u0 - 0.005, u1 + 0.005, z0 - 0.005, z1 + 0.005, w0, w1)
    def zifferblatt(self, u, z, d_aussen, d_innen, zeit=(2, 5), k=1.0, w_ring=0.10, w_feld=0.06):
        """Turmuhr-Details AUF einer vorhandenen Ringscheibe (Ring bis w_ring, Innenfeld bis w_feld vor der Wand): Wulst aussen und innen, 12 roemische Ziffern
        (radial, Fuss zur Mitte, IIII statt IV wie an Turmuhren ueblich), Nabe, Stundenzeiger mit Sonne und Mondsichel am Gegenende, Minutenzeiger mit Pfeil.
        Masse relativ zum Durchmesser (Ablesung Schwabentor Sued, entzerrtes Foto commons 127); k = Laengenfaktor fuer Tiefen/Breiten (Rohrahmen). Zeit = ANNAHME."""
        ra, ri = d_aussen / 2, d_innen / 2; sr = 1.0 if self.t @ np.array([-self.n[1], self.n[0]]) > 0 else -1.0; S = self.scheibe; e = 0.01 * k
        def P(r, phi, dx=0.0, dy=0.0):                                     # Uhrwinkel phi im Uhrzeigersinn ab 12; dx entlang des Uhrzeigersinns, dy nach aussen
            return (u + sr * (r * np.sin(phi) + dx * np.cos(phi) + dy * np.sin(phi)), z + r * np.cos(phi) - dx * np.sin(phi) + dy * np.cos(phi))
        t = (S(u, z, d_aussen, w_ring - e, w_ring + 0.04 * k) - S(u, z, d_aussen - 0.14 * k, w_ring - 2 * e, w_ring + 0.1 * k)) + (S(u, z, d_innen + 0.13 * k, w_feld - e, w_ring + 0.04 * k) - S(u, z, d_innen, w_feld - 2 * e, w_ring + 0.1 * k))
        rm = (ri + ra) / 2; h = 0.70 * (ra - ri) ; b = 0.075 * k; a_ = 0.13 * h / 0.63; w0, w1 = w_ring - e, w_ring + 0.03 * k
        for n_, txt in enumerate(("I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"), 1):
            phi = np.radians(30.0 * n_); br = [0.11 * h / 0.63 if c == "I" else 2 * a_ + 0.06 * h for c in txt]; x = -sum(br) / 2
            for c, bw in zip(txt, br):
                xm = x + bw / 2; x += bw
                if c == "I": t = t + self.stab(P(rm, phi, xm, -h / 2), P(rm, phi, xm, h / 2), b, w0, w1)
                elif c == "V": t = t + self.stab(P(rm, phi, xm - a_, h / 2), P(rm, phi, xm, -h / 2), b, w0, w1) + self.stab(P(rm, phi, xm + a_, h / 2), P(rm, phi, xm, -h / 2), b * 0.6, w0, w1)
                else: t = t + self.stab(P(rm, phi, xm - a_, h / 2), P(rm, phi, xm + a_, -h / 2), b, w0, w1) + self.stab(P(rm, phi, xm - a_, -h / 2), P(rm, phi, xm + a_, h / 2), b * 0.6, w0, w1)
        ph = np.radians(30.0 * (zeit[0] % 12) + 0.5 * zeit[1]); pm = np.radians(6.0 * zeit[1]); v0, v1, v2 = w_feld - e, w_feld + 0.10 * k, w_feld + 0.16 * k
        t = t + S(u, z, 0.30 * k, v0, v2 + 0.03 * k)                                                                            # Nabe traegt beide Zeiger
        t = t + self.stab(P(0.74 * ri, ph + np.pi), P(0.80 * ri, ph), 0.07 * k, v1 - 0.03 * k, v1) + S(*P(0.80 * ri, ph), 0.36 * ri, v1 - 0.03 * k, v1 + 0.02 * k)      # Stundenzeiger + Sonne
        mo = P(0.62 * ri, ph + np.pi); mi = P(0.62 * ri - 0.07 * ri, ph + np.pi, 0.05 * ri)
        t = t + (S(*mo, 0.34 * ri, v1 - 0.03 * k, v1) - S(*mi, 0.28 * ri, v1 - 0.05 * k, v1 + 0.02 * k))                         # Mondsichel am Gegenende
        t = t + self.stab(P(0.62 * ri, pm + np.pi), P(ra - 0.30 * (ra - ri), pm), 0.05 * k, v2 - 0.03 * k, v2)                   # Minutenzeiger bis in den Ziffernring
        sp = ra - 0.30 * (ra - ri); t = t + self.huelle([(c[0], c[1], w_) for c in (P(sp + 0.22 * ri, pm), P(sp - 0.10 * ri, pm, 0.07 * ri), P(sp - 0.10 * ri, pm, -0.07 * ri)) for w_ in (v2 - 0.03 * k, v2)])
        return t
    def halbraum_innen(self, koerper):
        """Koerper an der Wandebene abschneiden (alles VOR der Ebene faellt weg)."""
        return koerper.trim_by_plane((-self.n[0], -self.n[1], 0.0), float(-(self.n @ self.a)))


def fenster_aus_json(koerper, datei, tiefe=0.12, min_stimmen=3):
    """Automatisch erkannte Fenster (tools/fenster_aus_parsing.py: je Fassade o, d, n und Rechtecke mit Pfosten/Kaempfer) in den Koerper schneiden.
    Fenster, vor denen im Modell schon etwas steht (Sonde 3-8 cm vor der Flaeche zu > 20 % gefuellt), werden ausgelassen. Liefert (koerper, belege)."""
    import json, os
    if not os.path.exists(datei): return koerper, []
    belege = []
    for fid, F in json.load(open(datei)).items():
        o = np.array(F["o"], float); W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float)); n_ = 0
        for f in F["fenster"]:
            if f.get("stimmen_min", 0) < min(min_stimmen, 2): continue          # Stimmen prueft schon fenster_aus_parsing.py (anteilig); hier nur noch Einzelstimmen aussieben
            sonde = W.kasten(f["u0"], f["u1"], f["z0"], f["z1"], 0.03, 0.08)
            if (koerper ^ sonde).volume() > 0.2 * sonde.volume(): continue
            ab, zu = W.fenster(f["u0"], f["u1"], f["z0"], f["z1"], 0.0, tiefe=tiefe, teiler=f.get("teiler", ()), kaempfer=f.get("kaempfer"), sprossen=f.get("sprossen", ())); koerper = koerper - ab + zu; n_ += 1
        if n_: belege.append(dict(seite="wand", element=f"{n_} Fenster Fassade {fid} (automatisch erkannt)", quelle="OWLv2 auf dem Mehrfoto-Ortho (fassade_ortho.py -> fassade_parsing.py -> fenster_aus_parsing.py), Fotos " + ", ".join(F.get("fotos", [])[:3]),
                                  hinweis="ERKENNUNG, am Bild fenster_<id>.jpg pruefen; Nischentiefe und Rahmenbreiten ANNAHME"))
    return koerper, belege


def zylinder_oeffnungen(datei, tiefe=0.7, innen=0.45, nur=None):
    """Schnittkoerper fuer die Oeffnungen eines runden Bauteils aus tools/fassade_zylinder.py (<aus>.json: achse, radius, oeffnungen mit azimut/z0/z1/breite).
    Jeder Schnitt ist ein Quader radial durch den Mantel (von radius - innen bis radius - innen + tiefe). koerper = koerper - zylinder_oeffnungen(...). nur = Liste von Indizes."""
    import json
    J = json.load(open(datei)); ax = J["achse"]; r = J["radius"]; k = None
    for i, o in enumerate(J.get("oeffnungen", [])):
        if nur is not None and i not in nur: continue
        q = M.cube((tiefe, o["breite"], o["z1"] - o["z0"])).translate((r - innen, -o["breite"] / 2, o["z0"])).rotate((0, 0, o["azimut"])).translate((ax[0], ax[1], 0.0)); k = q if k is None else k + q
    return k


def umgang(koerper, ecken, z0, z1, tiefe=0.9, pfosten=4, b=0.24, riegel=0.25, vor=0.08):
    """Offener Umgang / Laufgang unter der Traufe eines Turms (GENERISCH): rundum zurueckgesetzte Wand hinter einer Pfostenreihe.
    ecken: Wandecken (x, y) im Umlauf auf Hoehe des Umgangs; z0..z1: Schwelle unten bis Raehm oben (beide 'riegel' hoch, stehen 'vor' vor der Wand);
    dazwischen ist die Wand um 'tiefe' zurueckgesetzt und zwischen 'pfosten' Pfosten je Seite (Eckpfosten mitgezaehlt) offen.
    Zu messen: z0, z1, Pfostenzahl (am Foto zaehlen); tiefe, Querschnitte = ANNAHME. Liefert den neuen Koerper."""
    m = np.mean(np.asarray(ecken, float), axis=0); zus = None; ab = None
    for a_, b_ in zip(ecken, list(ecken[1:]) + [ecken[0]]):
        mi = 0.5 * (np.asarray(a_, float) + np.asarray(b_, float)); W = Wand(a_, b_, aussen=tuple(2 * mi - m)); L = W.laenge
        c_ = W.kasten(-0.05, L + 0.05, z0 + riegel, z1 - riegel, -tiefe, vor + 0.3); ab = c_ if ab is None else ab + c_
        t_ = W.kasten(-vor, L + vor, z0, z0 + riegel, -0.3, vor) + W.kasten(-vor, L + vor, z1 - riegel, z1, -0.3, vor)
        for k_ in range(pfosten): u_ = k_ * (L - b) / (pfosten - 1); t_ = t_ + W.kasten(u_, u_ + b, z0 + riegel - 0.02, z1 - riegel + 0.02, -0.3, vor - 0.01)
        zus = t_ if zus is None else zus + t_
    return koerper - ab + zus


DURCH = []   # von Wand.fenster gesammelte Oeffnungen (Wand, u0, u1, z0, z1, w der Nischenrueckwand)


def hohlraum(koerper, d, decke=None, boden=None):
    """Innenraum = Koerper, um die Wandstaerke d nach innen geschrumpft (Schnitt von 8 waagerecht und 2 senkrecht verschobenen Kopien = Erosion)."""
    v = koerper; r = d * 0.7071
    for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d), (r, r), (r, -r), (-r, r), (-r, -r)): v = v ^ koerper.translate((dx, dy, 0.0))
    v = v ^ koerper.translate((0.0, 0.0, -(decke or d))) ^ koerper.translate((0.0, 0.0, boden or d))
    for dx, dy in ((d, 0), (-d, 0), (0, d), (0, -d)):                    # schraeg nach oben/unten: sonst beruehrt der Raum waagerechte Aussenflaechen (Auskragungen) entlang einer Kante (4 Flaechen an einer Kante = nicht wasserdicht)
        for dz in (-0.5 * d, 0.5 * d): v = v ^ koerper.translate((0.7 * dx, 0.7 * dy, dz))
    return v


def aushoehlen(koerper, d=0.3, schnitte=(), fenster=None, min_m3=0.5, decke=None, boden=None, z_min=None):
    """Nutzer 16.11.2026: "alles, was in Wirklichkeit ein Loch ist (Fenster ...), muss ein Loch werden". Gebaeude hohl (Wandstaerke d = ANNAHME), Fenster durchgebrochen.
    fenster: Liste wie DURCH (Standard: alle bisher mit Wand.fenster gebauten); schnitte: weitere Durchbruchkoerper (Rundfenster, Schlitze).
    Nur Hohlraumteile, die von einem Durchbruch erreicht werden, bleiben (sonst geschlossene Blasen = Extrakoerper im STL). Liefert (koerper, anzahl_offen, hohlraum_m3)."""
    fenster = DURCH if fenster is None else fenster
    cuts = [W.kasten(u0, u1, z0, z1, wr - d - 0.25, wr + 0.002) for W, u0, u1, z0, z1, wr in fenster] + list(schnitte)
    if not cuts: return koerper, 0, 0.0
    alle = cuts[0]
    for c in cuts[1:]: alle = alle + c
    raum = None; vol = 0.0
    roh = hohlraum(koerper, d, decke, boden)
    if z_min is not None: roh = roh.trim_by_plane((0.0, 0.0, 1.0), z_min)      # darunter massiv (Torgeschoss eines Turms: Pfeiler neben der Durchfahrt)
    for t in roh.decompose():
        if t.volume() >= min_m3 and (t ^ alle).volume() > 1e-4: raum = t if raum is None else raum + t; vol += t.volume()
    offen = sum(1 for c in cuts if raum is not None and (c ^ raum).volume() > 1e-5)
    erg = (koerper - raum if raum is not None else koerper) - alle
    teile = erg.decompose()                                               # Spaene zwischen Hohlraum und Boegen/Nischen schweben frei (5 Extrakoerper am Nachbarhaus) -> weg
    if len(teile) > 1:
        gross = [t for t in teile if t.volume() >= 0.05]; erg = gross[0]
        for t in gross[1:]: erg = erg + t
    return kneifkanten_schliessen(erg), offen, vol


def kneifkanten_schliessen(koerper, r=0.02, runden=6, stellen=4):
    """Kanten, an denen sich der Koerper nur beruehrt (4 Flaechen an einer Kante, z. B. Hohlraum tippt an eine Nische): im STL 'nicht wasserdicht'.
    Um jede solche Kante einen kleinen Klotz (r) auffuellen - schliesst die Beruehrung, oeffnet nie ein Loch."""
    for runde in range(runden):
        me = koerper.to_mesh(); V = np.array(me.vert_properties)[:, :3].astype(np.float64); F = np.asarray(me.tri_verts)
        vq, inv = np.unique(np.round(V, stellen), axis=0, return_inverse=True); F = inv.ravel()[F]; F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
        e = np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1); u, cnt = np.unique(e, axis=0, return_counts=True); bad = u[cnt > 2]
        if not len(bad): break
        r = r * (1.5 if runde else 1.0)                                  # an gekruemmten Flaechen (Bogenlaibung) wandert die Beruehrung sonst nur weiter
        o = np.array([[sx, sy, sz] for sx in (-r, r) for sy in (-r, r) for sz in (-r, r)])
        for a_, b_ in vq[bad]: koerper = koerper + M.hull_points(np.r_[a_ + o, b_ + o].tolist())
        print("kneifkanten geschlossen:", len(bad))
    return koerper


def massstab(koerper, faktor, drehpunkt): return koerper.translate((-drehpunkt[0], -drehpunkt[1], -drehpunkt[2])).scale((faktor, faktor, faktor)).translate(drehpunkt)


def zwischenstand(koerper, name, muster=("relief/*.npz", "dach.json", "objekt.json", "audit/zyl_*.json", "audit/fenster_auto.json"), extra=()):
    """ZWISCHENSPEICHER im Generator (Aufgabenliste 1b, 16.11.2026): koerper = zwischenstand(koerper, "nord") an festen Stellen des Generators.
    Schluessel = Generatortext BIS zu dieser Zeile + Inhalt von bauteile.py/relief_einsatz.py/dach_bauen.py + Groesse/Zeit der Eingabedateien (muster, relativ zu modelle/<objekt>/)
    + Umgebungsvariablen (SCALE, WAND_MM, MINMM, OHNE_*) + extra. Treffer: der gespeicherte Koerper wird geladen, der bis hierher aufgebaute (noch nicht ausgerechnete) Baum verworfen -
    manifold3d rechnet erst bei der Ausgabe, deshalb kostet der Code davor dann fast nichts. Kein Treffer: ausrechnen, speichern, den GESPEICHERTEN Stand weitergeben (kalter und warmer Lauf sind so gleich).
    Wer am Generator Zeile N aendert, rechnet nur ab dem letzten Zwischenstand davor neu. OHNE_CACHE=1 schaltet ab. Ablage: /media/oem/scan/rc-park_daten/gen_cache/<objekt>/ (je Name nur der neueste Stand).
    Grenze: Dateien, die der Generator ausserhalb von `muster` liest, muessen ueber muster/extra gemeldet werden - sonst alter Stand trotz neuer Eingabe."""
    import inspect, hashlib, glob, os, time
    if os.environ.get("OHNE_CACHE") == "1": return koerper
    from manifold3d import Mesh64
    fr = inspect.stack()[1]; gen = os.path.abspath(fr.filename); h = hashlib.sha1("\n".join(open(gen).read().split("\n")[:fr.lineno]).encode()); td = os.path.dirname(os.path.abspath(__file__))
    for t_ in ("bauteile.py", "relief_einsatz.py", "dach_bauen.py"): h.update(open(os.path.join(td, t_), "rb").read())
    od = gen[:-len("_gen.py")] if gen.endswith("_gen.py") else os.path.splitext(gen)[0]
    for mu in muster:
        for f in sorted(glob.glob(os.path.join(od, mu))): st = os.stat(f); h.update(f"{os.path.relpath(f, od)}|{st.st_size}|{st.st_mtime_ns}".encode())
    h.update(repr(sorted((k, v) for k, v in os.environ.items() if k in ("SCALE", "WAND_MM", "MINMM") or k.startswith("OHNE_"))).encode()); h.update(repr(extra).encode())
    cd = os.path.join("/media/oem/scan/rc-park_daten/gen_cache", os.path.basename(od)); cf = os.path.join(cd, f"{name}_{h.hexdigest()[:16]}.npz"); t0 = time.time()

    def laden():
        Z = np.load(cf); m = M(Mesh64(vert_properties=Z["V"], tri_verts=Z["F"], merge_from_vert=Z["mf"], merge_to_vert=Z["mt"]))
        return m if m.status().name == "NoError" and not m.is_empty() else None
    if os.path.exists(cf):
        try:
            m = laden()
            if m is not None: print(f"zwischenstand {name}: geladen ({time.time() - t0:.1f} s)", flush=True); return m
        except Exception as e: print(f"zwischenstand {name}: Datei unbrauchbar ({str(e)[:60]}) - rechne neu", flush=True)
    try:
        me = koerper.to_mesh64(); os.makedirs(cd, exist_ok=True)
        for alt in glob.glob(os.path.join(cd, f"{name}_*.npz")): os.remove(alt)
        np.savez(cf, V=np.asarray(me.vert_properties)[:, :3], F=np.asarray(me.tri_verts), mf=np.asarray(me.merge_from_vert), mt=np.asarray(me.merge_to_vert)); m = laden()
        if m is None: os.remove(cf); print(f"zwischenstand {name}: gespeicherter Stand nicht ladbar - ohne Zwischenspeicher weiter", flush=True); return koerper
        print(f"zwischenstand {name}: gerechnet und gespeichert ({time.time() - t0:.1f} s, {len(Z_F(me)) // 1000}k Dreiecke)", flush=True); return m
    except Exception as e: print(f"zwischenstand {name}: nicht gespeichert ({type(e).__name__}: {str(e)[:80]})", flush=True); return koerper


def Z_F(me): return np.asarray(me.tri_verts)


def stl_schreiben(model, pfad, kopf=b"rcpark"):
    """Binaeres STL; Ecken auf 1 Mikrometer verschweisst, entartete Dreiecke entfernt (sonst fallen Splitter als Einzelkoerper heraus)."""
    import os
    model = kneifkanten_schliessen(model, r=0.25, stellen=3)            # im Druckmassstab (mm): Beruehrkanten, die erst nach dem Skalieren zusammenfallen (16.11.2026 Blendmasswerk)
    mesh = model.to_mesh(); V = np.array(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
    vq, inv = np.unique(np.round(V.astype(np.float64), 3), axis=0, return_inverse=True); F = inv.ravel()[F]; V = vq.astype(np.float32)
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    fs = np.sort(F, axis=1); _u, inv2, cnt = np.unique(fs, axis=0, return_inverse=True, return_counts=True); F = F[cnt[inv2.ravel()] == 1]      # Flaechenpaare mit denselben drei Ecken (Lappen ohne Dicke) entfernen
    try:                                                                 # 16.11.2026: Kruemel (<= 8 Dreiecke, z. B. 2-cm-Tetraeder nach dem Aushoehlen) fallen sonst als Einzelkoerper heraus
        from scipy.sparse import coo_matrix; from scipy.sparse.csgraph import connected_components
        e_ = np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1); fi_ = np.tile(np.arange(len(F)), 3); o_ = np.lexsort((e_[:, 1], e_[:, 0])); e_, fi_ = e_[o_], fi_[o_]; g_ = np.flatnonzero((e_[1:] == e_[:-1]).all(1))      # Nachbarschaft ueber gemeinsame KANTEN (wie trimesh.split)
        nk_, fl_ = connected_components(coo_matrix((np.ones(len(g_)), (fi_[g_], fi_[g_ + 1])), shape=(len(F), len(F))), directed=False); F = F[np.bincount(fl_, minlength=nk_)[fl_] > 8]
    except ImportError: pass
    tri = V[F]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri; os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "wb") as f: f.write(kopf.ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
    return len(F)
