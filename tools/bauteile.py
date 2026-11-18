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
from manifold3d import Manifold as M, CrossSection, OpType, JoinType


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
    def versetzt(self, d):
        """Parallele Wand, um d nach aussen (d < 0 = nach innen) verschoben; u-Ursprung und Richtung bleiben (u-Werte der alten Wand gelten weiter)."""
        a = self.a + d * self.n; return Wand(a, a + self.laenge * self.t, aussen=a + self.n)


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


def stichbogen(breite, unten, kaempfer, scheitel, nseg=24):
    """Querschnitt (quer, hoch) einer Stichbogenoeffnung (Segmentbogen): Pfeiler von 'unten' bis zum Kaempfer, darueber ein Kreissegment mit Pfeilhoehe scheitel - kaempfer (< halbe Breite)."""
    a = breite / 2; h = scheitel - kaempfer; R = (a * a + h * h) / (2 * h); zc = scheitel - R; w0 = np.arcsin(min(a / R, 1.0))
    return CrossSection([[[-a, unten], [a, unten]] + [[R * np.sin(w), zc + R * np.cos(w)] for w in np.linspace(w0, -w0, nseg)]])


def korbbogen(breite, unten, kaempfer, scheitel, nseg=24):
    """Querschnitt (quer, hoch) einer Korbbogen-/Ellipsenbogenoeffnung: Pfeiler bis zum Kaempfer, darueber eine halbe Ellipse (Halbachsen breite/2 und scheitel - kaempfer).
    17.11.2026 Kaufhaus-Laube: die Boegen setzen am Kaempfer SENKRECHT an (kein Knick wie beim Stichbogen), sind aber flacher als ein Halbkreis (Pfeil 1,45 m bei 1,8 m halber Breite)."""
    a = breite / 2; h = scheitel - kaempfer
    return CrossSection([[[-a, unten], [a, unten]] + [[a * np.cos(w), kaempfer + h * np.sin(w)] for w in np.linspace(0, np.pi, nseg)][:-1] + [[-a, kaempfer]]])


def bogen_querschnitt(form, breite, kaempfer, scheitel, unten):
    """Querschnitt einer Bogenoeffnung nach Formfamilie (wie tools/element_einpassen.py / oeffnungen_bogen.py): 'rund' (Halbkreis ueber dem Kaempfer), 'stich' (Segmentbogen), 'spitz' (zwei Kreisboegen),
    'korb' (halbe Ellipse, senkrechter Ansatz am Kaempfer)."""
    if form == "korb": return korbbogen(breite, unten, kaempfer, scheitel)
    if form == "spitz": return spitzbogen(breite / 2, kaempfer, scheitel, unten=unten)
    if form == "stich" and scheitel - kaempfer < breite / 2 - 1e-3: return stichbogen(breite, unten, kaempfer, scheitel)
    return rundbogen(breite, unten, kaempfer + breite / 2)


def oeffnungen_aus_wandbild(koerper, datei, ncc_min=0.2, ersatz=None, steg_tiefe=0.05, vor=0.05, nur=None, nur_frei=False, frei_tiefe=0.3, frei_anteil=0.5):
    """OEFFNUNGEN AUS DEM WANDBILD bauen (18.11.2026, Rueckwand/Laube; Datei von tools/oeffnungen_wandbild.py): je Oeffnung der Bildumriss als Nische bis zur
    gemessenen Tiefe (Parallaxe der Einzelfoto-Orthos) - der flache Nischengrund IST die Rueckwand nach Regel A (Glas/Torblatt in Leibungstiefe). Bei Fenstern
    die Stege (Pfosten/Kaempfer/Rahmen = Zellen in Wandfarbe innerhalb des Umrisses) steg_tiefe dick vor dem Grund. 'flach' (Tafel, Bild) wird nicht gebaut.
    Tiefe unsicher (NCC innen < ncc_min): ersatz[klasse] = (tiefe, quelle) aus objekt.json (benannte Quelle), sonst Tiefe der sichersten Oeffnung derselben Klasse auf derselben Wand (ANNAHME), sonst nicht gebaut.
    VOR aushoehlen aufrufen: die Hohlraumschale folgt dann der Nische (kein Durchblick ins Innere). nur = Liste von Fassaden-ids. Liefert (koerper, belege).
    nur_frei (18.11.2026, Generator-Vorlage der Kette): eine Oeffnung wird nur gebaut, wenn vor ihr Luft ist (Sonde frei_tiefe vor der Wandebene ueber dem Umriss zu
    < frei_anteil gefuellt) - im Kettenmodell ist eine Innenwand ohne freilegendes Bauteil (Laube) noch im Vollkoerper; dort geschnitten gaebe es eingeschlossene Hohlraeume (Luftinseln)."""
    import json, os
    if not os.path.exists(datei): return koerper, []
    belege = []; ersatz = ersatz or {}
    for fid, F in json.load(open(datei)).items():
        if nur and fid not in nur: continue
        o = np.array(F["o"], float); W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float)); s = -1.0 if W.spiegel else 1.0
        sicher = {}
        for e in F["oeffnungen"]:
            if e.get("tiefe") is not None and not e.get("flach") and e.get("ncc_innen", 0) >= ncc_min and e.get("ncc_innen", 0) > sicher.get(e["klasse"], (0, 0))[1]: sicher[e["klasse"]] = (e["tiefe"], e["ncc_innen"], e["zone"])
        ab = None; zu = None; liste = []; verdeckt = []
        for e in F["oeffnungen"]:
            if e.get("flach") or not e.get("umriss"): continue
            if e.get("tiefe") is not None and e.get("ncc_innen", 0) >= ncc_min: T, q = e["tiefe"], "gemessen (Parallaxe, NCC %.2f)" % e["ncc_innen"]
            elif e["klasse"] in ersatz: T, q = ersatz[e["klasse"]][0], "Ersatzquelle: " + ersatz[e["klasse"]][1] + " (eigene Messung %s, NCC %.2f zu schwach)" % (e.get("tiefe"), e.get("ncc_innen", 0))
            elif e["klasse"] in sicher: T, q = sicher[e["klasse"]][0], "ANNAHME: wie %s u %.2f..%.2f (eigene Messung %s, NCC %.2f zu schwach)" % (e["klasse"], sicher[e["klasse"]][2][0], sicher[e["klasse"]][2][1], e.get("tiefe"), e.get("ncc_innen", 0))
            else: continue
            P = [[s * u, z] for u, z in e["umriss"]]
            if sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P))) < 0: P = P[::-1]
            if nur_frei:
                u_ = [p_[0] for p_ in e["umriss"]]; z_ = [p_[1] for p_ in e["umriss"]]; so = W.kasten(min(u_), max(u_), min(z_), max(z_), 0.02, frei_tiefe)
                if (koerper ^ so).volume() > frei_anteil * so.volume(): verdeckt.append("%s u %.2f..%.2f" % (e["klasse"], min(u_), max(u_))); continue
            k = M.extrude(CrossSection([P]), T + vor).translate((0, 0, -T)).transform(W.matrix(0)); ab = k if ab is None else ab + k
            if e["klasse"] == "fenster":
                for st in e.get("stege", []):
                    S = [[s * u, z] for u, z in st]
                    if sum(S[i][0] * S[(i + 1) % len(S)][1] - S[(i + 1) % len(S)][0] * S[i][1] for i in range(len(S))) < 0: S = S[::-1]
                    k2 = M.extrude(CrossSection([S]), steg_tiefe + 0.01).translate((0, 0, -T - 0.01)).transform(W.matrix(0)); zu = k2 if zu is None else zu + k2
            liste.append(dict(klasse=e["klasse"], zone=e["zone"], tiefe=round(float(T), 3), tiefe_quelle=q))
        if ab is not None: koerper = koerper - ab
        if zu is not None: koerper = koerper + zu
        if verdeckt: belege.append(dict(seite="wand", element="Wand %s: %d Oeffnungen NICHT gebaut (Wand liegt im Vollkoerper, kein Bauteil legt sie frei)" % (fid, len(verdeckt)), quelle="bauteile.oeffnungen_aus_wandbild nur_frei; " + os.path.basename(datei), hinweis="; ".join(verdeckt) + " - Freilegung (Laube/Halle) fehlt im Generator (ZIEL_PIPELINE_H0 L3)"))
        if liste:
            belege.append(dict(seite="wand", element="Wand %s: %d Oeffnungen aus dem Wandbild (%s)" % (fid, len(liste), ", ".join("%s %.2f m tief" % (x["klasse"], x["tiefe"]) for x in liste)),
                               quelle="tools/oeffnungen_wandbild.py: Zone OWLv2, Umriss aus dem feinen Wandbild (Helligkeit + Farbabstand zur Wand), Tiefe Parallaxen-Sweep der Einzelfoto-Orthos; " + os.path.basename(datei),
                               hinweis="; ".join("%s u %.2f..%.2f: %s" % (x["klasse"], x["zone"][0], x["zone"][1], x["tiefe_quelle"]) for x in liste) + "; Stege 5 cm vor dem Grund = ANNAHME", oeffnungen=liste))
    return koerper, belege


def oeffnungen_aus_json(koerper, datei, vor=0.8, gewoelbe=0.5, innenwaende=None):
    """Automatisch erkannte Bogenoeffnungen / Tordurchfahrten (tools/oeffnungen_bogen.py: je Fassade o, d, n und 'oeffnungen' mit form, u, breite, kaempfer, scheitel, unten, tiefe_m)
    in den Koerper schneiden. Nur Eintraege mit gebaut = true (Durchblick im Ebenen-Sweep belegt, Form gegengeprueft). Der Schnitt reicht von 'vor' m vor der Fassadenebene
    (Reliefs, Vorsprung der LoD2-Wand) bis tiefe_m dahinter. Liefert (koerper, belege, z_massiv): z_massiv = hoechster Scheitel einer DURCHFAHRT + gewoelbe (ANNAHME 0,5 m Gewoelbestaerke)
    fuer aushoehlen(z_min=...) - das Torgeschoss bleibt massiv, die Durchfahrt oeffnet sich nicht in den Hohlraum; None, wenn keine Durchfahrt gebaut wurde.
    innenwaende (objekt.json, Kettenstufe 'bauplan', 18.11.2026): liegt eine gebaute Nicht-Durchfahrt im u-Bereich einer Innenwand derselben Fassadenrichtung, reicht ihr
    Schnitt bis auf die Innenwandebene (gemessene Tiefe statt der Nischen-ANNAHME) - die Innenwand liegt dann im Bogen frei."""
    import json, os
    if not os.path.exists(datei): return koerper, [], None
    belege = []; z_massiv = None
    for fid, F in json.load(open(datei)).items():
        o = np.array(F["o"], float); W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float))
        for x in F.get("oeffnungen", []):
            if not x.get("gebaut"): continue
            T_ = float(x["tiefe_m"]); iw_ = None
            for iw in (innenwaende or []) if not x.get("durchfahrt") else []:
                A_ = np.asarray(iw["a"], float); t_ = np.asarray(iw["b"], float) - A_; t_ /= np.linalg.norm(t_); n_ = np.asarray(iw["aussen"], float) - A_; n_ = n_ - (n_ @ t_) * t_; n_ /= np.linalg.norm(n_)
                if n_ @ W.n < 0.98: continue
                P_ = o + x["u"] * W.t; uu_ = sorted(float(iw_u) for iw_u in iw["u"]); ux_ = float((P_ - A_) @ t_)
                if uu_[0] <= ux_ <= uu_[1]: T_ = max(T_, float((o - (A_ + float(iw["versatz"]) * n_)) @ n_)); iw_ = iw.get("name")
            koerper = koerper - W.prisma(bogen_querschnitt(x["form"], x["breite"], x["kaempfer"], x["scheitel"], x.get("unten", 0.0) - 0.5), u=x["u"], w0=-T_, w1=vor)
            if iw_: x = dict(x, tiefe_m=round(T_, 3), annahmen=list(x.get("annahmen", [])) + [f"Tiefe bis Innenwand {iw_} (gemessen, Stufe bauplan)"])
            if x.get("durchfahrt"): z_massiv = max(z_massiv or -1e9, x["scheitel"] + gewoelbe)
            belege.append(dict(seite="wand", element=("Tordurchfahrt" if x.get("durchfahrt") else "Bogenoeffnung") + f" Fassade {fid} ({x['form']}, automatisch erkannt)",
                               quelle="OWLv2-Bogenkasten als Suchfenster (fassade_parsing.py) -> Ebenen-Sweep ueber die Fotos (fassade_tiefe.py: Durchblick = Fotos in der Wandtiefe nicht deckungsgleich) -> Formfamilie eingepasst (tools/oeffnungen_bogen.py), Fotos " + ", ".join(F.get("fotos", [])[:3]),
                               lichte_breite=x["breite"], kaempfer=x["kaempfer"], scheitel=x["scheitel"], tiefe=x["tiefe_m"], hinweis="ERKENNUNG, am Bild oeffnungen_<id>.jpg pruefen; " + "; ".join(x.get("annahmen", []))))
    return koerper, belege, z_massiv


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


def laube(koerper, W, boegen, tiefe, decke, pfeiler_tiefe=0.8, u0=None, u1=None, vor=0.8, unten=-0.5, stirn=(), frei=None):
    """OFFENE LAUBE / ARKADENHALLE hinter einer Bogenreihe (GENERISCH, 17.11.2026 Kaufhaus: "Arkaden nur 10 cm Ruecksprung").
    W: Wand der Bogenreihe (Aussenflaeche w = 0). boegen: Liste dict(u, breite, kaempfer, scheitel, form) mit LICHTEN Massen der Oeffnungen (form 'rund'|'stich'|'spitz'|'korb');
    jede Oeffnung wird von 'vor' m vor der Wand (Reliefplatten davor fallen mit) bis knapp hinter die Pfeilerflucht (pfeiler_tiefe) geschnitten.
    Halle: Quader u0..u1 (Standard: aeusserste Bogenkanten), w = -tiefe .. -pfeiler_tiefe, z = unten .. decke (flache Decke = ANNAHME statt Gewoelbe).
    stirn: Bogenoeffnungen in Stirnwaenden, je (Wand2, dict wie boegen + 'durch' = Schnitttiefe hinter Wand2, Standard 1,5 m).
    Zu messen: Bogenlagen und -masse (entzerrtes Frontfoto, tools/wand_ortho.py, 2 Fotos deckungsgleich), Zahl am Foto (foto_zaehlung.py), Hallentiefe (Ebenen-Sweep durch die Boegen).
    ANNAHME meist: pfeiler_tiefe, decke. Liefert (koerper, schnittkoerper).
    frei = (u0, u1, z1[, w_hinten]) oder Liste davon: Pfeilerzone u0..u1 unterhalb z1 (Kaempfer) freiraeumen (bis w_hinten, Standard ganz), von vor bis hinter die Pfeilerflucht - fuer freistehende Saeulen statt Wandpfeiler
    (17.11.2026 Runde 2: Foto zeigt runde Saeulen; die Saeulen selbst mit saeule() NACH aushoehlen addieren)."""
    sch = None
    for b in boegen:
        k = W.prisma(bogen_querschnitt(b.get("form", "rund"), b["breite"], b["kaempfer"], b["scheitel"], unten), u=b["u"], w0=-pfeiler_tiefe - 0.05, w1=vor); sch = k if sch is None else sch + k
    u0 = min(b["u"] - b["breite"] / 2 for b in boegen) if u0 is None else u0; u1 = max(b["u"] + b["breite"] / 2 for b in boegen) if u1 is None else u1
    sch = sch + W.kasten(u0, u1, unten, decke, -tiefe, -pfeiler_tiefe)
    for W2, b in stirn:
        sch = sch + W2.prisma(bogen_querschnitt(b.get("form", "rund"), b["breite"], b["kaempfer"], b["scheitel"], unten), u=b["u"], w0=-float(b.get("durch", 1.5)), w1=vor)
    for f_ in ([frei] if frei and np.isscalar(frei[0]) else (frei or ())):     # je Kasten (u0, u1, z1[, w_hinten]); w_hinten Standard = hinter der Pfeilerflucht
        sch = sch + W.kasten(f_[0], f_[1], unten, f_[2], f_[3] if len(f_) > 3 else -pfeiler_tiefe - 0.05, vor)
    return koerper - sch, sch


def laube_aus_wandbild(koerper, innenwaende, datei, pfeiler_tiefe=0.8, vor=0.8, klassen=("bogen", "tor", "tuer"), min_b=1.0, min_h=1.8, boden=1.0):
    """LAUBE / HALLE AUS DEM WANDBILD FREILEGEN (18.11.2026, Ziel H0 von null L2; Grundsatz WANDBILD = BAUPLAN). Kette: innenwaende (objekt.json, tools/innenwaende_finden.py:
    Ebenen-Sweep sieht durch grosse bodennahe Oeffnungen eine Flaeche 'versatz' m hinter der Aussenwand) + Oeffnungen der AUSSENWAND aus dem feinen Wandbild
    (datei = audit/oeffnungen_aussen.json von tools/oeffnungen_wandbild.py: Umriss je Oeffnung aus Bildkanten). Je Innenwand:
      Bogenoeffnungen = Bildumriss jeder grossen, bodennahen Oeffnung (klassen, >= min_b x min_h m, Unterkante <= Innenwand-z0 + boden) mit Mitte im u-Bereich der Innenwand,
      als Prisma von 'vor' m vor der Wand (Reliefplatten fallen mit) bis hinter die Pfeilerflucht; Gestalt NUR aus dem Bild, kein Katalogbogen;
      Halle = Quader u = Huelle der Umrisse, z = tiefste Umriss-Unterkante (ANNAHME ebener Boden) .. max(Innenwand-z1, hoechster Scheitel + 5 cm) (ANNAHME flache Decke),
      w = Innenwandebene (gemessen) .. -pfeiler_tiefe (ANNAHME 0,8 m wie laube(); hoechstens halbe Hallentiefe).
    VOR oeffnungen_aus_wandbild(nur_frei) der Innenwand-Oeffnungen und VOR aushoehlen aufrufen (die Innenwand liegt dann frei, die Hohlraumschale folgt der Halle).
    Liefert (koerper, belege). Ohne passende Oeffnung bleibt die Innenwand verdeckt (Beleg mit Grund)."""
    import json, os
    if not innenwaende or not os.path.exists(datei): return koerper, []
    FA = json.load(open(datei)); belege = []
    for iw in innenwaende:
        F = FA.get(iw.get("fassade"))
        if not F: belege.append(dict(seite="wand", element="Innenwand %s: Laube NICHT freigelegt" % iw.get("name"), quelle="bauteile.laube_aus_wandbild", hinweis="Fassade %s fehlt in %s" % (iw.get("fassade"), os.path.basename(datei)))); continue
        o = np.array(F["o"], float); W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float)); s = -1.0 if W.spiegel else 1.0
        A_ = np.asarray(iw["a"], float); t_ = np.asarray(iw["b"], float) - A_; t_ /= np.linalg.norm(t_)
        n_ = np.asarray(iw["aussen"], float) - A_; n_ = n_ - (n_ @ t_) * t_; n_ /= np.linalg.norm(n_)
        if n_ @ W.n < 0.98: belege.append(dict(seite="wand", element="Innenwand %s: Laube NICHT freigelegt" % iw.get("name"), quelle="bauteile.laube_aus_wandbild", hinweis="Innenwand nicht parallel zur Fassade")); continue
        w_iw = float(((A_ + float(iw["versatz"]) * n_) - o) @ W.n); du = float((A_ - o) @ W.t)      # Innenwandebene und u-Versatz im Fassadenrahmen
        iu = sorted(float(x) + du for x in iw["u"]); iz = [float(x) for x in iw["z"]]
        pt = min(pfeiler_tiefe, 0.5 * abs(w_iw)); sch = None; gew = []
        for e in F.get("oeffnungen", []):
            if e.get("flach") or not e.get("umriss") or e["klasse"] not in klassen: continue
            U = [p_[0] for p_ in e["umriss"]]; Z_ = [p_[1] for p_ in e["umriss"]]
            if max(U) - min(U) < min_b or max(Z_) - min(Z_) < min_h or min(Z_) > iz[0] + boden: continue
            if not iu[0] <= 0.5 * (min(U) + max(U)) <= iu[1]:
                # 18.11.2026 (Kaufhaus gk2: 4. Laubenbogen u 4,96..8,90 offen 5,2 m tief, Innenwand-Kern endete bei u 4,73): angrenzendes Joch mitnehmen, wenn die Sweep-Tiefe passt
                luecke = max(iu[0] - max(U), min(U) - iu[1])
                if not (e["klasse"] == "bogen" and e.get("tiefe") is not None and luecke <= 1.5 and float(e["tiefe"]) >= 0.8 * abs(w_iw)): continue
                e = dict(e, angrenzend=True)
            P = [[s * u, z] for u, z in e["umriss"]]
            if sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P))) < 0: P = P[::-1]
            k = M.extrude(CrossSection([P]), pt + 0.05 + vor).translate((0, 0, -pt - 0.05)).transform(W.matrix(0)); sch = k if sch is None else sch + k
            gew.append((e["klasse"] + (" (ANNAHME angrenzendes Joch, Tiefe %.1f m aus Sweep-Karte)" % float(e["tiefe"]) if e.get("angrenzend") else ""), min(U), max(U), min(Z_), max(Z_)))
        if not gew:
            belege.append(dict(seite="wand", element="Innenwand %s: Laube NICHT freigelegt" % iw.get("name"), quelle="bauteile.laube_aus_wandbild; " + os.path.basename(datei), hinweis="keine grosse bodennahe Oeffnung mit Bildumriss im u-Bereich %.2f..%.2f" % tuple(iu))); continue
        ua, ub = min(g[1] for g in gew), max(g[2] for g in gew); za = min(g[3] for g in gew); zb = max(iz[1], max(g[4] for g in gew) + 0.05)
        sch = sch + W.kasten(ua, ub, za, zb, w_iw, -pt); koerper = koerper - sch
        belege.append(dict(seite="wand", element="Laube vor Innenwand %s: %d Oeffnungen aus dem Wandbild + Halle %.2f m tief" % (iw.get("name"), len(gew), -w_iw),
                           quelle="bauteile.laube_aus_wandbild: Umrisse aus dem feinen Wandbild der Fassade %s (%s), Hallentiefe = Innenwand %s (%s)" % (iw["fassade"], os.path.basename(datei), iw.get("name"), str(iw.get("quelle", ""))[:120]),
                           hinweis="ANNAHME: Pfeilertiefe %.2f m, ebener Boden z %.2f, flache Decke z %.2f; Oeffnungen " % (pt, za, zb) + "; ".join("%s u %.2f..%.2f z %.2f..%.2f" % g for g in gew)))
    return koerper, belege


def saeule(W, u, w, z0, z1, d, basis=None, kapitell=None, nseg=40):
    """RUNDE SAEULE mit Basis und Kapitell (GENERISCH, 17.11.2026 Kaufhaus-Laube Runde 2). Achse bei Wandkoordinaten (u, w) der Wand W, Schaft z0..z1, Durchmesser d.
    basis = dict(z1, breite, form='quadrat'|'rund', wulst=0.06): Plinthe z0..z1 (quadratisch = Kanten parallel zur Wand), darauf ein Wulst (Ring halbe Hoehe 'wulst',
    Durchmesser zwischen Schaft und Plinthe) als Uebergang. kapitell = dict(z0, z1, d_oben): Aufweitung (Kegelstumpf) vom Schaft auf d_oben - an der Laube laufen dort
    die Bogenprofile aus. Zu messen: Achse (Triangulation der Silhouettenmitte in >= 2 Fotos, foto_mass --tri2d), d (Silhouette am entzerrten Bild in der Achsebene),
    Plinthe Breite/Hoehe, Beginn der Aufweitung; Zahl am Foto. Liefert den Saeulenkoerper (z0 nicht unter die Modellunterkante legen: der Pruefstand setzt z = 0 dort)."""
    x, y, _ = W.punkt(u, 0.0, w); zs = (basis or {}).get("z1", z0); k = M.cylinder(z1 - zs + 0.02, d / 2, d / 2, nseg).translate((x, y, zs - 0.01))
    if basis:
        b = basis["breite"]
        k = k + (W.kasten(u - b / 2, u + b / 2, z0, basis["z1"], w - b / 2, w + b / 2) if basis.get("form", "quadrat") == "quadrat"
                 else M.cylinder(basis["z1"] - z0, b / 2, b / 2, nseg).translate((x, y, z0)))
        hw = basis.get("wulst", 0.06); dw = 0.5 * (d + min(b, d + 0.16))
        if hw > 0: k = k + M.cylinder(hw, dw / 2, d / 2, nseg).translate((x, y, basis["z1"] - 0.005))
    if kapitell:
        k = k + M.cylinder(kapitell["z1"] - kapitell["z0"], d / 2, kapitell["d_oben"] / 2, nseg).translate((x, y, kapitell["z0"]))
    return k


def balkon(W, u0, u1, z_boden, w_vorne, z_handlauf, docken, pfosten, konsolen=(), platte=0.11, ueber=0.05, d_docke=0.09, b_pfosten=0.16, schwelle=0.07,
           handlauf=(0.10, 0.18), konsole=(0.25, 0.62, 0.30), seiten_docken=3, w_wand=-0.05):
    """AUSKRAGENDER BALKON mit Docken-Gelaender (GENERISCH, 17.11.2026 Kaufhaus Runde 2) vor der Wand W (Aussenflaeche w = 0).
    u0..u1: Laenge (Aussenkanten der Eckpfosten), z_boden: Unterkante Bodenplatte, w_vorne: Vorderflucht des Gelaenders (Handlauf), z_handlauf: Oberkante Handlauf.
    docken: u-Lagen der Docken (Baluster, je Segment am Foto gezaehlt und abgelesen); pfosten: u-Lagen der Pfosten (inkl. Eckpfosten); konsolen: u-Lagen der Konsolen.
    Teile: Bodenplatte (platte hoch, 'ueber' vor der Gelaenderflucht), Schwelle, Handlauf (hoch, tief), Pfosten (b_pfosten quadratisch), Docken (Zylinder d_docke mit Fuss- und
    Kopfklotz), Seitenruecklaeufe mit 'seiten_docken' Docken je Seite, Konsolen (breite, hoehe, unten_tief): oben bis unter die Vorderkante, unten 'unten_tief' tief (Keil statt Volute).
    Zu messen: Vorderecke (Triangulation, foto_mass --tri), Hoehen am entzerrten Bild der Gelaenderebene, Zahlen am Foto. Querschnitte = ANNAHME. Liefert den Balkonkoerper."""
    K = W.kasten; zb1 = z_boden + platte; zs1 = zb1 + schwelle; hh, ht = handlauf; zh0 = z_handlauf - hh; wv = w_vorne; wm = wv - ht / 2
    g = K(u0 - ueber, u1 + ueber, z_boden, zb1, w_wand, wv + ueber)                                                  # Bodenplatte
    g = g + K(u0, u1, zb1 - 0.01, zs1, wv - ht + 0.02, wv - 0.02)                                                    # Schwelle (vorn)
    g = g + K(u0 - 0.03, u1 + 0.03, zh0, z_handlauf, wv - ht, wv + 0.02)                                            # Handlauf (vorn)
    for s_ in (u0 + b_pfosten / 2, u1 - b_pfosten / 2):                                                             # Seitenruecklaeufe: Schwelle, Handlauf, Docken
        g = g + K(s_ - b_pfosten / 2, s_ + b_pfosten / 2, zb1 - 0.01, zs1, w_wand, wv - 0.02) + K(s_ - b_pfosten / 2 - 0.01, s_ + b_pfosten / 2 + 0.01, zh0, z_handlauf, w_wand, wv)
        for i in range(seiten_docken):
            wd = (i + 1) * (wv - ht) / (seiten_docken + 1); g = g + M.cylinder(zh0 - zs1 + 0.02, d_docke / 2, d_docke / 2, 16).translate((*W.punkt(s_, 0.0, wd)[:2], zs1 - 0.01))
    for up in pfosten: g = g + K(up - b_pfosten / 2, up + b_pfosten / 2, zb1 - 0.01, zh0 + 0.01, wm - b_pfosten / 2, wm + b_pfosten / 2)
    kl = 0.06; kb = d_docke + 0.03
    for ud in docken:
        x, y, _ = W.punkt(ud, 0.0, wm)
        g = g + M.cylinder(zh0 - zs1 + 0.02, d_docke / 2, d_docke / 2, 16).translate((x, y, zs1 - 0.01)) + K(ud - kb / 2, ud + kb / 2, zs1 - 0.01, zs1 + kl, wm - kb / 2, wm + kb / 2) \
            + K(ud - kb / 2, ud + kb / 2, zh0 - kl, zh0 + 0.01, wm - kb / 2, wm + kb / 2)
    kb_, kh, kt = konsole
    for uk in konsolen:
        g = g + W.huelle([(uk + s * kb_ / 2, z_, w_) for s in (-1.0, 1.0) for z_, w_ in ((z_boden + 0.01, w_wand), (z_boden + 0.01, wv - 0.05), (z_boden - kh, w_wand), (z_boden - kh, kt))])
    return g


def vorhangbogen(breite, unten, schulter, spitze, mitte, feld, exponent=1.9, nseg=14):
    """Querschnitt (quer, hoch) einer VORHANGBOGEN-Oeffnung (spaetgotischer Fensterkopf, GENERISCH, 17.11.2026 Kaufhaus Runde 2): senkrechte Seiten bis zur Schulter,
    aussen je ein hohl geschwungener Bogen (z = schulter + (spitze - schulter) * s^exponent, s = 0 an der Seite .. 1 an der Spitze) bis zu den Spitzen bei +-feld/2,
    dazwischen ein haengender Bogen (Parabel) mit dem tiefsten Punkt 'mitte'. Zu messen: Breite, Schulter, Spitzen (Hoehe, Abstand = Breite des Mittelfeldes),
    Scheitel des Mittelfeldes, 3-5 Punkte eines Aussenbogens fuer den Exponenten (entzerrtes Bild, 2 Fotos)."""
    a = breite / 2; f = feld / 2; s = np.linspace(0, 1, nseg)
    re = [(a - si * (a - f), schulter + (spitze - schulter) * si ** exponent) for si in s]                       # rechts: Seite -> Spitze
    mi = [(x, mitte + (spitze - mitte) * (x / f) ** 2) for x in np.linspace(f, -f, nseg)][1:-1]                   # haengend, rechts -> links
    li = [(-x, z) for x, z in re[::-1]]                                                                        # links: Spitze -> Seite
    return CrossSection([[[-a, unten], [a, unten]] + [list(p) for p in re + mi + li]])


def vorhangbogen_fenster(W, u0, u1, z0, z1, schulter, spitze, mitte, feld, exponent=1.9, w_fuell=(-0.11, -0.005), schnitt=(-0.3, 0.4),
                         pfosten_b=0.07, rahmen=(-0.13, -0.05), kaempfer=None):
    """Rechteckiges Fenster (u0..u1, z0..z1, schon als Nische/Loch gebaut, z. B. fenster_aus_json + aushoehlen) zum VORHANGBOGEN-Fenster umbauen (GENERISCH, 17.11.2026):
    oberhalb der Schulter Wand zurueck (Fuellung w_fuell), dann die Vorhangbogenform durch die Wand schneiden (schnitt = w-Bereich, auch durch Reliefplatten davor) -
    die Spitzen duerfen hoeher als z1 liegen. Pfosten unter den beiden Spitzen (z0 bis Spitze) und Kaempfer = (z in den Seitenfeldern, z im Mittelfeld) in der Rahmenebene.
    NACH aushoehlen aufrufen. Liefert (zusatz, abzug, pfosten): koerper = (koerper + zusatz - abzug) + pfosten."""
    um = 0.5 * (u0 + u1); B = u1 - u0
    zus = W.kasten(u0 - 0.02, u1 + 0.02, schulter - 0.02, z1 + 0.03, w_fuell[0], w_fuell[1])
    ab = W.prisma(vorhangbogen(B, schulter - 0.3, schulter, spitze, mitte, feld, exponent), u=um, w0=schnitt[0], w1=schnitt[1])
    pf = None
    for uc in (um - feld / 2, um + feld / 2):
        q = W.kasten(uc - pfosten_b / 2, uc + pfosten_b / 2, z0 - 0.01, spitze + 0.04, rahmen[0], rahmen[1]); pf = q if pf is None else pf + q
    if kaempfer:
        zs_, zm_ = kaempfer; ul, ur = um - feld / 2, um + feld / 2
        for zk, ua, ub in ((zs_, u0 - 0.01, ul), (zs_, ur, u1 + 0.01), (zm_, ul, ur)): pf = pf + W.kasten(ua, ub, zk - 0.03, zk + 0.03, rahmen[0], rahmen[1])
    return zus, ab, pf


def staffelgiebel(W, mitte_u, spitze_breite, spitze_z, flanken, dicke=0.63, fuss_z=None, kappe=0.22, sims=0.08, ueber=0.08):
    """TREPPENGIEBEL / STAFFELGIEBEL (GENERISCH, 17.11.2026): Spitzblock + Stufenbloecke je Flanke in der Giebelebene W (Aussenflaeche w = 0, Dicke nach innen).
    flanken: Liste (seite, [(u_aussen, z_oben), ...] von oben nach unten); seite +1 = Stufen laufen Richtung +u, -1 Richtung -u. u_aussen = Aussenkante der Stufe,
    z_oben = Stufenoberkante unter der Abdeckung. Jede Stufe reicht waagerecht von der Aussenkante der naechsthoeheren Stufe (bzw. des Spitzblocks) bis zur eigenen,
    senkrecht hinab bis fuss_z (unter die Dachflaeche, im Rumpf versenkt). Abdeckung je Block: Gesimsplatte 'sims' hoch, 'ueber' ringsum vorstehend, darauf ein Satteldaechlein
    'kappe' hoch (First quer zur Wand, faellt nach beiden u-Seiten) - so am Kaufhaus (Fotos 022/050/024/110).
    Zu messen: Ebene (Sweep), Spitzblock (Mitte, Breite, Oberkante), je Stufe Aussenkante + Oberkante (entzerrtes Foto der Giebelebene, 2 Fotos deckungsgleich), Stufenzahl am Foto.
    ANNAHME: Dicke, Abdeckungsprofil. Liefert den Giebelkoerper (zum Rumpf addieren; Dach jenseits der Giebelflaeche vorher mit W.halbraum_innen abschneiden)."""
    zs = [spitze_z] + [z for _, st in flanken for _, z in st]; fuss_z = (min(zs) - 3.0) if fuss_z is None else fuss_z

    def block(ua, ub, zo):
        lo, hi = min(ua, ub), max(ua, ub); m = 0.5 * (lo + hi)
        k = W.kasten(lo, hi, fuss_z, zo, -dicke, 0.0) + W.kasten(lo - ueber, hi + ueber, zo - 0.01, zo + sims, -dicke - ueber, ueber)
        return k + W.huelle([(u_, zo + sims - 0.01, w_) for u_ in (lo - ueber, hi + ueber) for w_ in (-dicke - ueber, ueber)] + [(m, zo + sims + kappe, w_) for w_ in (-dicke - ueber, ueber)])
    g = block(mitte_u - spitze_breite / 2, mitte_u + spitze_breite / 2, spitze_z)
    for seite, stufen in flanken:
        prev = mitte_u + seite * spitze_breite / 2
        for ua, zo in stufen: g = g + block(prev, ua, zo); prev = ua
    return g


def schleppgaube(W, u, w_front, z_fuss, breite, hoehe, neigung, dach_z0, dach_s, dach_breite=None, ueberstand=0.15, platte=0.10, fenster=(0.5, 0.10, 0.43), tief=1.5):
    """SCHLEPPGAUBE auf einem geneigten Dach (GENERISCH, 17.11.2026 Kaufhaus). Wandkoordinaten der Traufwand W: Front senkrecht bei w = w_front (< 0 = hinter der Wand),
    Breite 'breite', Unterkante z_fuss (auf der Dachflaeche), Oberkante z_fuss + hoehe = Traufe der Gaube. Das Gaubendach steigt mit 'neigung' (dz/dm) nach hinten, bis es die
    Hauptdachflaeche z = dach_z0 + dach_s * (-w) trifft; Wangen dreieckig. Dachplatte 'platte' dick, 'ueberstand' vor der Front, seitlich bis dach_breite.
    fenster = (breite, Bruestung ueber z_fuss, Scheitel ueber z_fuss): Rundbogen-Nische 0,12 m tief (kein Durchbruch).
    Zu messen: u, w_front, Hoehen und Breiten (Frontfoto + Triangulation), neigung (Seitenfoto oder aus dem Frontfoto abgeleitet), Zahl je Reihe am Foto.
    Liefert (zusatz, abzug): koerper = koerper + zusatz - abzug."""
    zt = z_fuss + hoehe; wi = (dach_z0 - zt - neigung * w_front) / (dach_s - neigung)        # Schnitt Gaubendach / Hauptdach
    wb = min(wi, w_front - 0.2) - 0.3; zb = zt + neigung * (w_front - wb); zu = z_fuss - tief; b2 = breite / 2; db = (dach_breite or breite + 0.3) / 2
    k = W.huelle([(u + s * b2, z_, w_) for s in (-1.0, 1.0) for z_, w_ in ((zu, w_front), (zt, w_front), (zb, wb), (zu, wb))])
    wf = w_front + ueberstand; zf = zt - neigung * ueberstand
    k = k + W.huelle([(u + s * db, z_ + dz, w_) for s in (-1.0, 1.0) for z_, w_ in ((zf, wf), (zb, wb)) for dz in (0.0, platte)])
    ab = None
    if fenster: ab = W.prisma(rundbogen(fenster[0], z_fuss + fenster[1], z_fuss + fenster[2]), u=u, w0=w_front - 0.12, w1=w_front + 0.05)
    return k, ab


def _ngon(achse, phase, apothem, z, n):
    R = apothem / np.cos(np.pi / n); return [(achse[0] + R * np.cos(phase + (i + 0.5) * 2 * np.pi / n), achse[1] + R * np.sin(phase + (i + 0.5) * 2 * np.pi / n), z) for i in range(n)]


def erker_polygon(achse, front_n, apothem, zonen, konsole=None, fenster=None, helm=None, knauf=None, stange=None, n=8, felder=None, wirt=None, konsole_rippen=None):
    """POLYGONALER ERKER mit Konsole und Helm (GENERISCH, 17.11.2026 Kaufhaus-Eckerker; Nutzer: nicht wieder 'besserer Kasten').
    Grundriss: regelmaessiges n-Eck um achse (x, y), eine Flaeche mit der Normalen front_n (Plan), Abstand der Flaechen von der Achse = apothem.
    zonen: Liste (z0, z1, apothem) - Prismen gleicher Ausrichtung (Gesimse = groesserer Abstand, Bruestung, Fensterband ...).
    konsole: (z_spitze, apothem_spitze, z_oben, apothem_oben) - nach unten spitz zulaufender Unterbau (Pyramidenstumpf).
    fenster: dict(z0, z1, je_flaeche, pfosten=0.08, tiefe=0.08, flaechen=None) - Lichter als Nischen je Flaeche (flaechen = Indizes ab der Frontflaeche, gegen den Uhrzeigersinn; None = alle).
    felder: dict(z0, z1, tiefe=0.04, rand=0.12) - ein vertieftes Feld je Flaeche (Wappen-/Bruestungsfelder).
    wirt: Rumpf, an dem der Erker sitzt - Flaechen, die ihn beruehren (halb in der Wand), bekommen keine Nischen (sonst Null-Volumen-Splitter).
    helm: Liste (z, apothem) von unten nach oben - geschweifter n-eckiger Helm aus Stumpfstuecken; knauf: (z_mitte, radius); stange: (z_oben, radius).
    Zu messen: Achse (Triangulation der Helmspitze/des Knaufs in >= 3 Fotos), apothem (n-Eck in die Fotos projizieren, Pfosten treffen), Zonengrenzen (entzerrtes Frontfoto),
    Helmprofil r(z) (Silhouette), Lichter je Flaeche am Foto zaehlen. Liefert den Erkerkoerper (zum Rumpf addieren; Flaechen im Rumpf verschwinden dort).
    17.11.2026 Runde 3 (Masswerk/Rippen, alle Schluessel optional, ohne sie bitgleich wie vorher):
      fenster.kaempfer = (z, b): waagerechter Kaempferriegel (Querholz) durch alle Lichter; fenster.kopf = h: Lichtkopf spitz (Kielbogen-Huelle, Seiten bis z1 - h, Spitze z1).
      felder.medaillon = (r, w_front): runde Wappenscheibe je Feld (Mitte des Feldes, Front w_front vor der Flaeche, meist knapp dahinter, z. B. -0,01).
      konsole_rippen = dict(b, vor, grate=True, kreuz=True, n=10, kreuz_form=(s_ctrl, v_ctrl, s_ende)): Rippennetz auf dem Pyramiden-Unterbau - Grate (Kantenlinien)
        und je Flaeche zwei sich kreuzende gekruemmte Rippen von den oberen Ecken zur Spitze (Bezier, Flaechenparameter s quer 0..1, v nach unten 0..1).
        Vorlage: kaufhaus_grob3 erker_polygon unterbau.rippen/rippen_bogen (dort Pfade gemessen; hier generische Form, ANNAHME bis gemessen)."""
    ph = float(np.arctan2(front_n[1], front_n[0])); P = lambda a, z: _ngon(achse, ph, a, z, n)
    k = None
    for z0, z1, a in zonen:
        q = M.hull_points(P(a, z0) + P(a, z1)); k = q if k is None else k + q
    if konsole:
        zs, a_s, zo, a_o = konsole; k = k + M.hull_points(P(a_s, zs) + P(a_o, zo + 0.01))
    for spec, ist_fenster in ((fenster, True), (felder, False)):
        if not spec: continue
        s_ = 2 * apothem * np.tan(np.pi / n); z0, z1 = spec["z0"], spec["z1"]; ab = None; zus = []
        for i in (spec.get("flaechen") or range(n)):
            phi = ph + i * 2 * np.pi / n; e = np.array([np.cos(phi), np.sin(phi)]); t = np.array([-e[1], e[0]]); c = np.array(achse, float) + apothem * e
            if wirt is not None and not (wirt ^ M.hull_points([tuple(c + sg * s_ / 2 * t + w_ * e) + (z_,) for sg in (-1, 1) for w_ in (-0.02, 0.15) for z_ in (z0, z1)])).is_empty(): continue
            if ist_fenster:
                kk = int(spec["je_flaeche"]); pf = spec.get("pfosten", 0.08); lw = (s_ - (kk + 1) * pf) / kk; offs = [-s_ / 2 + pf + lw / 2 + j * (lw + pf) for j in range(kk)]; tf = spec.get("tiefe", 0.08)
            else:
                lw = s_ - 2 * spec.get("rand", 0.12); offs = [0.0]; tf = spec.get("tiefe", 0.04)
            kopf = float(spec.get("kopf") or 0.0) if ist_fenster else 0.0; kae = spec.get("kaempfer") if ist_fenster else None
            baender = [(z0, kae[0] - kae[1] / 2, 0.0), (kae[0] + kae[1] / 2, z1, kopf)] if kae else [(z0, z1, kopf)]
            for o in offs:
                for za, zb, hk in baender:
                    pts = [tuple(c + (o + sg * lw / 2) * t + w_ * e) + (z_,) for sg in (-1, 1) for w_ in (-tf, 0.3) for z_ in (za, zb - hk)]
                    if hk > 0: pts += [tuple(c + o * t + w_ * e) + (zb,) for w_ in (-tf, 0.3)]
                    q = M.hull_points(pts); ab = q if ab is None else ab + q
                if not ist_fenster and spec.get("medaillon"):
                    r_m, wf = spec["medaillon"]; zm = 0.5 * (z0 + z1); cc = c + o * t
                    zus.append(M.cylinder(wf + tf + 0.01, r_m, r_m, 32).transform([[t[0], 0, e[0], cc[0] - (tf + 0.01) * e[0]], [t[1], 0, e[1], cc[1] - (tf + 0.01) * e[1]], [0, 1, 0, zm]]))
        if ab is not None: k = k - ab
        for q in zus: k = k + q
    if konsole and konsole_rippen:
        zs, a_s, zo, a_o = konsole; R_ = konsole_rippen; b_, v_ = float(R_["b"]), float(R_["vor"]); nn_ = int(R_.get("n", 10)); sc, vc, se = R_.get("kreuz_form", (0.15, 0.75, 0.7))
        To = P(a_o, zo); Bu = P(a_s, zs); rip = []
        for i in range(n):
            phi = ph + i * 2 * np.pi / n; e = np.array([np.cos(phi), np.sin(phi)]); t = np.array([-e[1], e[0]])
            nf = np.r_[e * (zo - zs), -(a_o - a_s)]; nf /= np.linalg.norm(nf)                 # wahre Flaechennormale der Pyramidenflaeche (nach aussen-unten): Rippen stehen senkrecht darauf
            L_, R2 = (i - 1) % n, i                                                        # Flaeche i liegt zwischen den Ecken i-1 und i (_ngon: Ecken bei (j + 0,5) Teilung)
            def Q(s, v): return (1 - v) * ((1 - s) * np.array(To[L_]) + s * np.array(To[R2])) + v * ((1 - s) * np.array(Bu[L_]) + s * np.array(Bu[R2]))
            def rippe(pts):                                                                 # Abschnittshuellen: +-b/2 quer (t), -0,03..vor entlang der Flaechennormalen
                return M.batch_boolean([M.hull_points([tuple(np.asarray(x, float) + np.r_[sg * b_ / 2 * t, 0.0] + d * nf) for x in (p_, q_) for sg in (-1, 1) for d in (-0.03, v_)])
                                        for p_, q_ in zip(pts[:-1], pts[1:])], OpType.Add)
            if R_.get("grate", True): rip.append(rippe([Q(0.0, v) for v in np.linspace(0, 1, 3)]))
            if R_.get("kreuz", True):
                for s0, s1, s2 in ((0.0, sc, se), (1.0, 1 - sc, 1 - se)):
                    x = np.linspace(0, 1, nn_); S_ = (1 - x) ** 2 * s0 + 2 * x * (1 - x) * s1 + x * x * s2; V_ = 2 * x * (1 - x) * vc + x * x * 1.0
                    rip.append(rippe([Q(a_, b2) for a_, b2 in zip(S_, V_)]))
        k = k + M.batch_boolean(rip, OpType.Add)
    if helm:
        for (za, aa), (zb, ab_) in zip(helm[:-1], helm[1:]): k = k + M.hull_points(P(aa, za) + P(max(ab_, 0.01), zb))
    if knauf: k = k + M.sphere(knauf[1], 24).translate((achse[0], achse[1], knauf[0]))
    if stange: zt = helm[-1][0] - 0.05 if helm else knauf[0]; k = k + M.cylinder(stange[0] - zt, stange[1], stange[1], 12).translate((achse[0], achse[1], zt))
    return k


def dachflaechen(koerper, nz_min=0.3, nz_max=0.97, z_min=None, tol=0.05, min_m2=2.0):
    """Ebene Dachflaechen eines Koerpers: Dreiecke mit Normalen-z in [nz_min, nz_max] (geneigt, nicht flach), gruppiert nach Ebene (|n.n_g| > 0,999, Abstand < tol).
    Rueckgabe Liste (n, Dreiecke [k, 3, 3], Flaeche m2), groesste zuerst; Gruppen unter min_m2 fallen weg (Gaubendaechlein, Splitter)."""
    me = koerper.to_mesh(); V = np.asarray(me.vert_properties)[:, :3].astype(float); T = V[np.asarray(me.tri_verts)]
    N = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]); A = np.linalg.norm(N, axis=1); ok = A > 1e-9; N[ok] /= A[ok, None]
    sel = ok & (N[:, 2] >= nz_min) & (N[:, 2] <= nz_max)
    if z_min is not None: sel &= T[:, :, 2].min(1) >= z_min
    G = []
    for i in np.flatnonzero(sel)[np.argsort(-A[sel])]:
        d = float(N[i] @ T[i, 0])
        for g in G:
            if g[0] @ N[i] > 0.999 and abs(d - g[1]) < tol: g[2].append(i); break
        else: G.append([N[i].copy(), d, [i]])
    return [(g[0], T[g[2]], float(A[g[2]].sum() / 2)) for g in G if A[g[2]].sum() / 2 >= min_m2]


def schindeln(koerper, abstand, tiefe, nz_min=0.3, nz_max=0.97, z_min=None, min_m2=2.0, rand=0.0):
    """DACHDECKUNG ALS STUFENRELIEF (Biberschwanz-/Ziegelreihen, GENERISCH, 17.11.2026 Runde 3; Vorlage kaufhaus_grob3 satteldach ziegel_abstand/ziegel_tiefe).
    Je ebener Dachflaeche (dachflaechen) eine Saegezahn-Schicht: Reihe k = Keil zwischen zwei Reihenlinien (waagerecht in der Flaeche), am unteren Rand 'tiefe' ueber
    der Flaeche, am oberen Rand 0 (jede Reihe liegt ueber der naechsthoeheren wie die Ziegel). Reihen ab der Traufe (tiefste Kante der Flaeche) nach oben im Abstand
    'abstand' (entlang des Hangs). Begrenzt auf die Flaeche (Dreiecke entlang der Normalen extrudiert, rand m eingerueckt nicht noetig).
    Zu messen: abstand am Foto (Hang entzerrt, Autokorrelation: tools/foto_dachreihen.py bzw. messprotokoll ZR-dachreihen); tiefe ist im Foto nicht messbar
    (ANNAHME, im Druck >= 0,3 mm: tiefe >= 0,3 x Massstab/1000 m, H0 >= 0,026 m). Rueckgabe (Schicht, Anzahl Flaechen, Reihen gesamt). Zum Koerper ADDIEREN."""
    teile = []; n_r = 0; fl = dachflaechen(koerper, nz_min, nz_max, z_min, min_m2=min_m2)
    for n, T, _ in fl:
        dn = np.array([0.0, 0.0, -1.0]) - n * (-n[2]); dn /= np.linalg.norm(dn); e = np.cross(dn, n); e /= np.linalg.norm(e)
        X = T.reshape(-1, 3); s = X @ dn; q = X @ e; h0 = float(np.median(X @ n))
        s_hi = float(s.max()); s_lo = float(s.min()); q0, q1 = float(q.min()) - 0.1, float(q.max()) + 0.1
        P = lambda s_, q_, h_: (s_ * dn + q_ * e + (h0 + h_) * n).tolist()
        kz = []; k = 0
        while s_hi - k * abstand > s_lo - abstand:
            a_, b_ = s_hi - k * abstand, s_hi - (k + 1) * abstand                       # a_ = untere (traufseitige) Reihenkante, b_ = obere
            kz.append(M.hull_points([P(a_, qq, -0.01) for qq in (q0, q1)] + [P(a_, qq, tiefe) for qq in (q0, q1)] + [P(b_, qq, -0.01) for qq in (q0, q1)] + [P(b_, qq, 0.002) for qq in (q0, q1)]))
            k += 1
        clip = M.batch_boolean([M.hull_points([tuple(v + o * n) for v in tri for o in (-0.02, tiefe + 0.03)]) for tri in T], OpType.Add)
        teile.append(M.batch_boolean(kz, OpType.Add) ^ clip); n_r += k
    return (M.batch_boolean(teile, OpType.Add) if teile else M()), len(fl), n_r


def figur(W, u, w, konsole, koerper, nseg=16):
    """FREISTEHENDE FIGUR AUF RUNDKONSOLE vor einer Wand (GENERISCH, 17.11.2026; Vorlage kaufhaus_grob3 figurenreihe).
    konsole [[z, r], ...] = Rotationsprofil (Kreisringe), koerper [[z, breite_u, tiefe_w], ...] = Ellipsenringe um die senkrechte Achse bei (u, w);
    Teilkoerper = Huelle je zwei benachbarter Ringe. Arme/Attribute nicht modelliert (Huellkoerper, H0). KLIPSTEIL-KANDIDAT (tools/druck_klips.py): Figur getrennt drucken."""
    th = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    def ring(z, b, d): return [W.punkt(u + 0.5 * b * np.cos(t), z, w + 0.5 * d * np.sin(t)) for t in th]
    rs = [ring(z, 2 * r, 2 * r) for z, r in sorted(konsole)]; rk = [ring(z, b, d) for z, b, d in sorted(koerper)]
    return M.batch_boolean([M.hull_points(a + b) for R_ in (rs, rk) for a, b in zip(R_[:-1], R_[1:])], OpType.Add)


def baldachin(W, u, w_wand, z_spitze, stufen, fialen, einbindung=0.1, kegel_h=0.18, nseg=8):
    """WANDBALDACHIN (Wimperg-Haube mit Fialenkrone) ueber einer Figur (GENERISCH, 17.11.2026; Vorlage kaufhaus_grob3 baldachinreihe).
    stufen [[z0_rel, z1_rel, halbbreite, tiefe0, tiefe1(, wangendicke)]] relativ zur Fialenspitze z_spitze (negativ = darunter), Tiefen vor w_wand; wangendicke > 0 = hohle Haube
    (nur zwei Seitenwangen). fialen [[du, tiefe, radius, z_unten_rel, z_spitze_rel]]: Achteck-Schaft + Spitzkegel (kegel_h). KLIPSTEIL-KANDIDAT."""
    teile = []
    for st in stufen:
        z0, z1, hb, t0, t1 = st[:5]; dk = float(st[5]) if len(st) > 5 else 0.0
        for lo_, hi_ in ([(-hb, hb)] if dk <= 0 else [(-hb, -hb + dk), (hb - dk, hb)]):
            teile.append(W.huelle([(u + a, z_spitze + (z0 if zi == 0 else z1), w_wand - einbindung if c == 0 else w_wand + (t0 if zi == 0 else t1)) for zi in (0, 1) for a in (lo_, hi_) for c in (0, 1)]))
    for du, t, r, zu, zs in fialen:
        ztop = z_spitze + zs; zb = z_spitze + zu; zk = max(zb + 0.02, ztop - kegel_h); p = W.punkt(u + du, 0.0, w_wand + t)
        teile.append(M.cylinder(zk - zb, r, r, nseg).translate((p[0], p[1], zb))); teile.append(M.cylinder(ztop - zk, r, 0.012, nseg).translate((p[0], p[1], zk)))
    return M.batch_boolean(teile, OpType.Add)


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


def _wand_inv(W):
    """Welt -> Wandkoordinaten (x = s*u wie in Wand.matrix, y = z, z = w) als 3x4-Matrix fuer Manifold.transform."""
    s = -1.0 if W.spiegel else 1.0
    return [[s * W.t[0], s * W.t[1], 0.0, -s * float(W.t @ W.a)], [0.0, 0.0, 1.0, 0.0], [float(W.n[0]), float(W.n[1]), 0.0, -float(W.n @ W.a)]]


def rueckwaende(koerper, felder, tiefe, d, rand=0.6, schliessen=0.05, schritt=0.01, w_bereich=(-1.0, 1.0), voll_ab=0.8, max_faktor=3.0):
    """REGEL A (Rueckwand/Laube 18.11.2026; Nutzer: im Render sah man durch die Obergeschossfenster in den Hohlraum mit diagonalen Innenkanten):
    hinter JEDER durchgebrochenen Oeffnung sitzt in Leibungstiefe eine ebene Rueckwand (Platte d dick), ein Kragen (Ring d breit um den Oeffnungsumriss,
    von der Wandschale bis zur Platte) schliesst den Hohlraum seitlich ab - durch kein Fenster sieht man ins Hohlinnere oder auf Innenkanten.
    Die Oeffnung selbst bleibt unberuehrt (Gewaende, Pfosten, Kaempfer, Masswerk in ihr bleiben); sie ist danach eine tiefe Nische, kein Durchblick mehr.
    Alles wird am GEBAUTEN Koerper je Feld gemessen (daher NACH allen Oeffnungsschnitten aufrufen, auch nach Umformungen wie vorhangbogen_fenster):
      1. Tiefenprofil im Umfeld (Feld + rand ohne das Feld): Belegung je w-Ebene (Manifold.slice in Wandkoordinaten). Wandflaeche 'vorn' = vorderste Ebene
         mit >= 50 % Belegung (Relief darf vor der Wandebene w = 0 liegen), Wandschale = zusammenhaengende Ebenen mit >= voll_ab Belegung ab dort.
      2. Umriss = leere Zellen in der Schale (Projektion), Pfosten/Kaempfer schmaler als 2*schliessen ueberbrueckt, nur Stuecke am Feld, vereinigt mit dem Feld.
      3. Rueckwand bei vorn - tiefe; liegt etwas IN der Oeffnung tiefer (Rahmen, Pfosten), dann 1 cm dahinter (gemeldet als tiefe_ist).
    tiefe = Leibungstiefe ab Wandflaeche (Fotomass oder ANNAHME im Beleg). felder: [(Wand, u0, u1, z0, z1, ...)] - im Generator bauteile.DURCH + eigene Felder.
    Liefert (koerper, info je Feld: u0, u1, z0, z1, vorn, schale, tiefe_ist, flaeche_m2, erkannt, nur_feld | fehlt)."""
    zus = None; info = []; w0, w1 = w_bereich
    for f in felder:
        W, u0, u1, z0, z1 = f[:5]; s = -1.0 if W.spiegel else 1.0
        xa, xb = sorted((s * (u0 - rand), s * (u1 + rand))); fa, fb = sorted((s * u0, s * u1)); ya, yb = z0 - rand, z1 + rand
        box = lambda q0, q1: M.cube((xb - xa, yb - ya, q1 - q0)).translate((xa, ya, q0))
        st = (koerper ^ box(w0, w1).transform(W.matrix(0))).transform(_wand_inv(W))
        feld = CrossSection.square((fb - fa, z1 - z0)).translate((fa, z0)); gross = CrossSection.square((xb - xa, yb - ya)).translate((xa, ya))
        umfeld = gross - feld.offset(0.05, JoinType.Miter); A_r = umfeld.area(); kern = None
        ws = np.arange(w1 - schritt / 2, w0, -schritt); SL = [st.slice(float(w)) for w in ws]; occ = np.array([(S ^ umfeld).area() / A_r for S in SL])
        e = dict(u0=round(float(u0), 3), u1=round(float(u1), 3), z0=round(float(z0), 3), z1=round(float(z1), 3))
        if not (occ >= voll_ab).any(): info.append(dict(e, fehlt="keine Wandschale im Umfeld")); continue
        vorn = float(ws[np.where(occ >= 0.5)[0][0]]); i0 = int(np.where(occ >= voll_ab)[0][0]); i1 = i0
        while i1 + 1 < len(ws) and occ[i1 + 1] >= voll_ab: i1 += 1
        sv, sh = float(ws[i0]) + schritt / 2, float(ws[i1]) - schritt / 2
        voll = (st ^ box(sh, sv)).project()
        offen = (gross - voll).offset(schliessen, JoinType.Miter).offset(-schliessen, JoinType.Miter); Q = feld; k = 0
        for p in offen.decompose():
            if p.area() >= 0.01 and (p ^ feld).area() > 1e-4: Q = Q + p; k += 1
        nur = Q.area() > max_faktor * feld.area()
        if nur: Q = feld; print("rueckwaende: Umriss bei u %.2f-%.2f zu gross -> nur Feld" % (u0, u1))
        innen = Q.offset(-0.03, JoinType.Miter); tiefst = None
        for w, S in zip(ws, SL):
            if vorn - 0.6 < w < sv and (S ^ innen).area() > 1e-4: tiefst = float(w)
        wp = vorn - tiefe if tiefst is None else min(vorn - tiefe, tiefst - schritt / 2 - 0.01)
        ring = Q.offset(d, JoinType.Miter) - Q
        k_ = M.extrude(ring, 0.5 * (sv + sh) - (wp - d)).translate((0, 0, wp - d)) + M.extrude(Q, d).translate((0, 0, wp - d))
        k_ = k_.transform(W.matrix(0)); zus = k_ if zus is None else zus + k_
        info.append(dict(e, vorn=round(vorn, 3), schale=[round(sh, 3), round(sv, 3)], tiefe_ist=round(vorn - wp, 3), flaeche_m2=round(float(Q.area()), 3), erkannt=k, nur_feld=bool(nur)))
    return (koerper if zus is None else koerper + zus), info


def entlueften(koerper, breite=0.3, schritt=0.3):
    """GESCHLOSSENER HOHLRAUM -> Bodenoeffnung (18.11.2026, Ziel H0 L2; Kettenmodell schwab_l2): nach rueckwaende (Regel A) ist der Hohlraum von aushoehlen ringsum zu
    (jede Oeffnung hat Rueckwand + Kragen) - im STL zwei Flaechenkoerper (aussen + Hohlraumhaut), die Abnahme zaehlt 2 Koerper, im Druck eine eingeschlossene Luftblase.
    Abhilfe: je eingeschlossenem Hohlraum ein senkrechter Schacht breite x breite von der Unterseite des Modells bis in den Hohlraumboden, an einer Stelle, unter der
    das Modell VOLL ist (nie durch eine Durchfahrt/Oeffnung - nur die Standflaeche bekommt ein Loch, unsichtbar). Liefert (koerper, belege)."""
    import trimesh
    me = koerper.to_mesh(); tm = trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts), process=True); teile = tm.split(only_watertight=False)
    if len(teile) <= 1: return koerper, []
    bb = koerper.bounding_box(); zb = bb[2]; aussen = max(teile, key=lambda t: np.prod(t.extents)); belege = []
    for t in teile:
        if t is aussen or not t.is_watertight or t.volume > -1e-4: continue         # nur Hohlraumhaeute (geschlossen, Normalen nach innen = negatives Volumen); Rest = Flaechenstuecke, die nur an Kanten haengen
        (x0, y0, zf), (x1, y1, _) = t.bounds; c = t.vertices[t.vertices[:, 2] < zf + 0.05].mean(0); kand = []
        for x in np.arange(x0 + breite, x1 - breite + 1e-9, schritt):
            for y in np.arange(y0 + breite, y1 - breite + 1e-9, schritt): kand.append((np.hypot(x - c[0], y - c[1]), x, y))
        for _, x, y in sorted(kand):
            luft = M.cube((breite, breite, 0.04)).translate((x - breite / 2, y - breite / 2, zf + 0.02))
            if (luft ^ koerper).volume() > 1e-7: continue                       # Punkt nicht im Hohlraum
            if zf - zb < 0.05: continue
            saeule = M.cube((breite, breite, zf - zb - 0.03)).translate((x - breite / 2, y - breite / 2, zb))
            if (saeule ^ koerper).volume() < 0.98 * saeule.volume(): continue  # darunter Luft (Durchfahrt, Oeffnung) - nicht hier
            koerper = koerper - M.cube((breite, breite, zf - zb + 0.15)).translate((x - breite / 2, y - breite / 2, zb - 0.1))
            belege.append(dict(seite="dach", element="Entlueftung: Hohlraum (Boden z %.2f) per Schacht %.2f x %.2f m zur Standflaeche geoeffnet" % (zf, breite, breite), quelle="bauteile.entlueften (geschlossener Hohlraum nach rueckwaende)",
                               hinweis="Druckhilfe, keine Bauwerksgeometrie; Loch nur in der Standflaeche bei x %.2f y %.2f, Schacht durch vollen Koerper" % (x, y))); break
        else: belege.append(dict(seite="dach", element="Hohlraum (Boden z %.2f) bleibt geschlossen - keine Schachtstelle mit vollem Koerper darunter" % zf, quelle="bauteile.entlueften", hinweis="Luftinsel im Druck: von Hand entlueften"))
    return koerper, belege


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

    import json as _js; fn = koerper if callable(koerper) else None      # TEURE SCHRITTE (aushoehlen: 80 s am Turm): koerper, info = zwischenstand(lambda: (aushoehlen(...), dict(...)), "hohl") - die Funktion laeuft nur ohne Treffer

    def laden():
        Z = np.load(cf); m = M(Mesh64(vert_properties=Z["V"], tri_verts=Z["F"], merge_from_vert=Z["mf"], merge_to_vert=Z["mt"]))
        return (m, _js.loads(str(Z["info"]))) if m.status().name == "NoError" and not m.is_empty() else None
    if os.path.exists(cf):
        try:
            m = laden()
            if m is not None: print(f"zwischenstand {name}: geladen ({time.time() - t0:.1f} s)", flush=True); return m if fn else m[0]
        except Exception as e: print(f"zwischenstand {name}: Datei unbrauchbar ({str(e)[:60]}) - rechne neu", flush=True)
    info = {}
    if fn: koerper, info = fn()
    try:
        me = koerper.to_mesh64(); os.makedirs(cd, exist_ok=True)
        for alt in glob.glob(os.path.join(cd, f"{name}_*.npz")): os.remove(alt)
        np.savez(cf[:-4] + ".tmp.npz", V=np.asarray(me.vert_properties)[:, :3], F=np.asarray(me.tri_verts), mf=np.asarray(me.merge_from_vert), mt=np.asarray(me.merge_to_vert), info=_js.dumps(info)); os.replace(cf[:-4] + ".tmp.npz", cf); m = laden()      # 16.11.2026: erst fertig schreiben, dann umbenennen (abgebrochener Lauf hinterlaesst keinen halben Stand)
        if m is None: os.remove(cf); print(f"zwischenstand {name}: gespeicherter Stand nicht ladbar - ohne Zwischenspeicher weiter", flush=True); return (koerper, info) if fn else koerper
        print(f"zwischenstand {name}: gerechnet und gespeichert ({time.time() - t0:.1f} s, {len(Z_F(me)) // 1000}k Dreiecke)", flush=True); return m if fn else m[0]
    except Exception as e: print(f"zwischenstand {name}: nicht gespeichert ({type(e).__name__}: {str(e)[:80]})", flush=True); return (koerper, info) if fn else koerper


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
    pfad = os.path.realpath(pfad)                  # modelle/stl/*.stl sind Verknuepfungen auf die Datenplatte - die Verknuepfung darf nicht durch eine Datei auf der Systemplatte ersetzt werden
    with open(pfad + ".teil", "wb") as f: f.write(kopf.ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
    os.replace(pfad + ".teil", pfad)      # 16.11.2026: ein abgebrochener Bau (Speicher, Platte) liess sonst ein halbes STL liegen, das die naechste Stufe als frisch las
    return len(F)
