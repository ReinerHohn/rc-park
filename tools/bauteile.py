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
Kein Kommandozeilenwerkzeug: Bibliothek, nur per import (Generator laeuft mit ~/.venvs/rcpark, braucht manifold3d/trimesh).
Neue Bauteile nur hier als generische Funktion (Katalog in modelle/PIPELINE_FASSADEN.md); am Generatorende bauteile.aushoehlen (Fenster = Loecher).
"""
import json, math, os, random
import numpy as np
from manifold3d import Manifold as M, CrossSection, OpType, JoinType

# Seitenkonvention des Modellrahmens (+x Sued, +y Ost, z oben): je Fassadenseite die Tiefenachse, ihr Vorzeichen nach aussen und die Querachse.
# (18.11.2026 wieder eingefuegt: bei der Umstellung auf die Bibliothek 497af805 verloren gegangen -> regression.py martinstor, foto_silhouette_profil, masse_aus_profilen, wolke_baender brachen)
SEITEN = {"nord": ("x", -1.0, "y"), "sued": ("x", 1.0, "y"), "ost": ("y", 1.0, "x"), "west": ("y", -1.0, "x")}
def seite_achsen(seite):
    """(tief, sgn, quer) einer Fassadenseite: Punkte der Seite liegen bei sgn * koordinate[tief] > 0; quer laeuft in der Fassadenebene."""
    return SEITEN[seite.lower()]


def lade_masse(pfad):
    """Masse eines Bauwerks aus JSON laden: {"masse": {"NAME": {"wert": 9.8 | "DB / 2 - 0.8", "quelle": ...}}}.
    Zahlen direkt, Text als Formel ueber die bereits geladenen Namen (Reihenfolge der Datei). Rueckgabe: dict NAME -> float."""
    roh = json.load(open(pfad))["masse"]; w = {}
    for name, eintrag in roh.items():
        v = eintrag["wert"]
        w[name] = float(v) if not isinstance(v, str) else float(eval(v, {"__builtins__": {}}, dict(w)))
    return w


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


def wandversatz_fassade(korrekturen_json, o, n, winkel=5.0, abstand=0.3, z=None):
    """Gesetzte Wandlage (m, + = aussen) der Fassade mit Bezugspunkt o / Normale n aus audit/schleife_korrekturen.json (Eintraege art 'wandversatz', angenommen != false:
    tools/wandlage_fotokanten.py, tools/ebenen_schleife.py), zugeordnet ueber Normale (< winkel Grad) und Ebenenabstand (< abstand m) wie fassade_ortho.wandversatz.
    Mehrere Eintraege: der tiefste (wie korrekturen_aus_json: die Wand steht dort, wo die tiefste Korrektur sie hinsetzt). Ohne Eintrag 0.
    z = (z_unten, z_oben) (24.11.2026): nur Eintraege, deren Scheibe z0..z1 diesen Hoehenbereich ueberlappt (Umgang ueber der Fassaden-Oberkante bleibt auf der alten Wand)."""
    import json, os
    if not korrekturen_json or not os.path.exists(korrekturen_json): return 0.0
    try: KK = json.load(open(korrekturen_json)).get("korrekturen", [])
    except Exception: return 0.0
    n = np.asarray(n, float)[:2]; o = np.asarray(o, float)[:2]; ws = []
    for K in KK:
        if K.get("art") != "wandversatz" or K.get("angenommen") is False or "w_soll" not in K: continue
        try: nk = np.asarray(K["n"], float)[:2]; ok_ = np.asarray(K["o"], float)[:2]
        except Exception: continue
        if z is not None and K.get("z0") is not None and K.get("z1") is not None and not (float(K["z0"]) < z[1] and z[0] < float(K["z1"])): continue
        if nk @ n > np.cos(np.radians(winkel)) and abs((ok_ - o) @ n) < abstand: ws.append(float(K["w_soll"]) + float((ok_ - o) @ n))
    return min(ws) if ws else 0.0


def wand_gesetzt(korrekturen_json, F, z=None):
    """Bezugspunkt einer Fassade F (o, n aus einer Bauteil-JSON, LoD2-Ebene) auf die GESETZTE Wandlage verschoben (wandversatz_fassade) -> (o_neu, wv).
    Fuer alle Bauteile, die an einer Fassade haengen oder in sie schneiden (Oeffnungen, Laube, Wandbild-Oeffnungen): Tiefen gelten ab der gebauten Wand, nicht ab LoD2."""
    o = np.array(F["o"], float); wv = wandversatz_fassade(korrekturen_json, o, F["n"], z=z)
    return o + wv * np.array(F["n"], float)[:len(o)], wv


def fenster_aus_json(koerper, datei, tiefe=0.12, min_stimmen=3):
    """Automatisch erkannte Fenster (tools/fenster_aus_parsing.py: je Fassade o, d, n und Rechtecke mit Pfosten/Kaempfer) in den Koerper schneiden.
    Fenster, vor denen im Modell schon etwas steht (Sonde 3-8 cm vor der Flaeche zu > 20 % gefuellt), werden ausgelassen. Liefert (koerper, belege).
    24.11.2026: Bezugsebene = GESETZTE Wandlage (wandversatz_fassade: Koerperwand auf die Fotokanten-Ebene zurueckgesetzt, tools/wandlage_fotokanten.py), sonst schnitte
    eine 0,12-m-Laibung 0,32 m vor der Wand ins Leere (Schwabentor f00) und die Sonde laege in der Wand."""
    import json, os
    if not os.path.exists(datei): return koerper, []
    belege = []; DRUCK_MIN = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0     # 0,8 mm bei 1:87 = 0,07 m
    kp_ = os.path.join(os.path.dirname(os.path.abspath(datei)), "schleife_korrekturen.json")
    for fid, F in json.load(open(datei)).items():
        o = np.array(F["o"], float); wv_ = wandversatz_fassade(kp_, o, F["n"]); o = o + wv_ * np.array(F["n"], float)[:len(o)]
        W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float)); n_ = 0; ann = []; formen = {}
        if wv_: belege.append(dict(seite="wand", element=f"Fenster Fassade {fid}: Bezugsebene {wv_:+.2f} m (gesetzte Wandlage)", quelle="bauteile.wandversatz_fassade (audit/schleife_korrekturen.json)"))
        for f in F["fenster"]:
            if f.get("stimmen_min", 0) < min(min_stimmen, 2): continue          # Stimmen prueft schon fenster_aus_parsing.py (anteilig); hier nur noch Einzelstimmen aussieben
            N = f.get("nische"); A_ = N or f
            sonde = W.kasten(A_["u0"], A_["u1"], A_["z0"], A_["z1"], 0.03, 0.08)
            if (koerper ^ sonde).volume() > 0.2 * sonde.volume(): continue
            # 23.11.2026 tools/loch_gewaende.py (1122o: Fenster/Tuer = Erkennerkasten um Loch UND Gewaende): Gewaende als Relief aus dem Wandbild-Umriss VOR dem Lochschnitt,
            # Loch = dunkle Komponente (u0..z1 des Eintrags) mit Laibungstiefe 'tiefe'. Hoehe mindestens Druckmindestmass (sonst im Druck unsichtbar).
            G = f.get("gewaende") or {}; w_vor = 0.05
            if len(G.get("umriss") or []) >= 3:
                h_ = max(float(G.get("hoehe") or 0.0), DRUCK_MIN); s_ = -1.0 if W.spiegel else 1.0; P = [[s_ * u, z] for u, z in G["umriss"]]
                if sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P))) < 0: P = P[::-1]
                rel = M.extrude(CrossSection([P]), h_ + 0.2).translate((0, 0, -0.2)).transform(W.matrix(0))     # 0,2 m eingebunden (gekruemmte Wand hinter der Fassadenebene)
                if rel.volume() > 1e-6:
                    koerper = koerper + rel; w_vor = h_ + 0.03; formen["Gewaende-Relief"] = formen.get("Gewaende-Relief", 0) + 1
                    if "ANNAHME" in str(G.get("hoehe_quelle", "")): ann.append(f"Gewaende {fid} u {f['u0']:.2f}: Relief {h_:.3f} m (Druckmindestmass, nicht gemessen)")
            if f.get("loch") and not f.get("bogen"): f = dict(f, bogen=dict(form="gerade", kaempfer=f["z1"], scheitel=f["z1"]))     # Loch: immer Umriss-Schnitt mit gemessener Laibungstiefe
            if N or f.get("bogen"):                                           # 21.11.2026 tools/nischen_fenster.py: Nische und Fensteroeffnung als ZWEI Ebenen, Umriss je Ebene aus den Bildkanten
                t0 = float(N["tiefe"]) if N else 0.0; tf = float(f.get("tiefe") or tiefe)
                # 21.11.2026 spaet (Nutzer: 'zwei flache Rechtecke'): jede Stufe mindestens Druckmindestmass (MINMM im Massstab SCALE, Generatoraufruf), sonst ist
                # eine gemessene 5-cm-Nische im Druck 0,57 mm = unsichtbar. ANNAHME (Druckbarkeit, CLAUDE.md 'Mindestmass 0,8 mm'), je Fenster im Beleg vermerkt.
                if tf < DRUCK_MIN: ann.append(f"Fenster {fid} u {f['u0']:.2f}: {tf:.2f} -> {DRUCK_MIN:.3f} m"); tf = DRUCK_MIN
                if N:                                                         # 24.11.2026: Mindestmass + nicht tiefer als die massive Wand (nische_tiefe_guard)
                    t0, tf, v_ = nische_tiefe_guard(koerper, W, N, t0, tf, DRUCK_MIN); ann += [f"{fid}: {x}" for x in v_]
                    if "ANNAHME" in str(N.get("tiefe_quelle", "")): ann.append(f"Nische {fid} u {N['u0']:.2f}: Tiefe {t0:.3f} m - {str(N['tiefe_quelle'])[:90]}")
                if "ANNAHME" in str(f.get("tiefe_quelle", "")): ann.append(f"Laibung {fid} u {f['u0']:.2f}: {tf:.2f} m nicht gemessen")
                if N: koerper = koerper - _umriss_prisma(W, N, N["z0"], -t0, 0.05)
                z0_ = max(f["z0"], N["z0"]) if N else f["z0"]                  # Fenster unter der Nischensohle wuerde einen geschlossenen Hohlraum hinter der Wand schneiden
                koerper = koerper - _umriss_prisma(W, f, z0_, -(t0 + tf), w_vor); n_ += 1
                k_ = (f.get("art") + " " if f.get("art") else "") + (f.get("bogen") or {}).get("form", "gerade") + (" in Nische" if N else "") + (" (Loch aus Wandbild)" if f.get("loch") else ""); formen[k_] = formen.get(k_, 0) + 1
                b_ = f.get("bogen") or {}; DURCH.append((W, f["u0"], f["u1"], z0_, b_.get("kaempfer", f["z1"]) if b_.get("form", "gerade") != "gerade" else f["z1"], -(t0 + tf), dict(tiefe=t0 + tf)))   # 7. Feld: Laibungstiefe dieses Fensters fuer rueckwaende()
                continue
            ab, zu = W.fenster(f["u0"], f["u1"], f["z0"], f["z1"], 0.0, tiefe=tiefe, teiler=f.get("teiler", ()), kaempfer=f.get("kaempfer"), sprossen=f.get("sprossen", ())); koerper = koerper - ab + zu; n_ += 1
            formen["rechteck (Form nicht gemessen)"] = formen.get("rechteck (Form nicht gemessen)", 0) + 1
        # 21.11.2026 spaet (Schwabentor f00: Leiste unter den Rundbogennischen fehlte): gemessene Sohlbaenke (tools/sohlbank_aus_fotos.py) NACH allen Schnitten anbauen
        sb_ = [f["sohlbank"] for f in F["fenster"] if f.get("sohlbank") and f.get("stimmen_min", 0) >= min(min_stimmen, 2)]; n_sb = 0
        for S_ in sb_:
            k_neu, v_ = sohlbank(koerper, W, S_, DRUCK_MIN); ann += v_
            if "ANNAHME" in str(S_.get("auskragung_quelle", "")): ann.append(f"Sohlbank {fid} u {S_['u0']:.2f}: {str(S_['auskragung_quelle'])[:110]}")     # 24.11.2026
            if k_neu is not koerper: koerper = k_neu; n_sb += 1
        if n_sb: belege.append(dict(seite="wand", element=f"{n_sb} Sohlbank/Sohlbaenke Fassade {fid} (aus Fotos gemessen)", quelle="tools/sohlbank_aus_fotos.py: " + "; ".join(str(S_.get("quelle", "")) for S_ in sb_[:2]),
                                    masse=[{k: S_.get(k) for k in ("u0", "u1", "z0", "z1", "auskragung", "auskragung_streuung", "fotos")} for S_ in sb_], hinweis="Rueckseite in der gemessenen Koerperflaeche (bauteile.sohlbank)"))
        if n_: belege.append(dict(seite="wand", element=f"{n_} Fenster Fassade {fid} (automatisch erkannt)", formen=formen, **({"annahmen": "ANNAHME: " + "; ".join(ann)} if ann else {}), quelle="OWLv2 auf dem Mehrfoto-Ortho (fassade_ortho.py -> fassade_parsing.py -> fenster_aus_parsing.py), Fotos " + ", ".join(F.get("fotos", [])[:3]),
                                  hinweis="ERKENNUNG, am Bild fenster_<id>.jpg pruefen; Nischentiefe und Rahmenbreiten ANNAHME"))
    return koerper, belege


_OW_CACHE = [None, None]


def _oberflaeche_w_leeren(): _OW_CACHE[:] = [None, None]


def _oberflaeche_w(koerper, W, punkte, w_von=3.0, w_bis=-1.5, radius=4.0):
    """Aeusserste Koerperflaeche vor der Wandebene W an den Stellen [(u, z), ...]: Strahl von w_von gegen -n, erster Treffer -> w (None = kein Treffer).
    Nur Dreiecke im Umkreis 'radius' um die Punkte (schnell auch bei 1 Mio. Dreiecken).
    24.11.2026: Netz + Dreiecksmitten des zuletzt befragten Koerpers zwischengespeichert (Manifold ist unveraenderlich: gleicher Koerper = gleiches Netz) -
    loch_gewaende_spaet/ortsteine_bauen fragen denselben Koerper je Fenster/Kante neu (16 Aufrufe, 45 s je Bau). _oberflaeche_w_leeren() gibt den Speicher frei."""
    if _OW_CACHE[0] is koerper and os.environ.get("RCPARK_BAU_SERIELL") != "1": V, F, C = _OW_CACHE[1]
    else:
        me = koerper.to_mesh(); V = np.asarray(me.vert_properties)[:, :3].astype(float); F = np.asarray(me.tri_verts); C = V[F].mean(1)
        _OW_CACHE[:] = [koerper, (V, F, C)]
    P = np.array([W.punkt(u, z, 0.0) for u, z in punkte], float); m = P.mean(0)
    sel = np.linalg.norm(C - m, axis=1) < radius + float(np.max(np.linalg.norm(P - m, axis=1)))
    if not sel.any(): return [None] * len(punkte)
    A, B, Cc = V[F[sel, 0]], V[F[sel, 1]], V[F[sel, 2]]; e1, e2 = B - A, Cc - A; n3 = np.array([W.n[0], W.n[1], 0.0]); d = -n3
    pv = np.cross(d, e2); det = np.einsum("ij,ij->i", e1, pv); ok = np.abs(det) > 1e-12; inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    out = []
    for p in P:                                                          # Moeller-Trumbore je Strahl (ohne rtree/embree)
        o = p + w_von * n3; tv = o - A; uu = np.einsum("ij,ij->i", tv, pv) * inv; qv = np.cross(tv, e1); vv = (qv @ d) * inv; t = np.einsum("ij,ij->i", e2, qv) * inv
        hit = ok & (uu >= 0) & (vv >= 0) & (uu + vv <= 1) & (t > 0)
        w = w_von - t[hit]; w = w[(w >= w_bis) & (w <= w_von)]
        out.append(float(w.max()) if w.size else None)
    return out


def loch_gewaende_spaet(koerper, datei, einbinden=0.3, min_vor=0.005, abtrag=0.3):
    """23.11.2026 (1122o, Tuer f04 im Treppenturm, Fenster f03): Loch + Gewaende (tools/loch_gewaende.py) auf der ECHTEN Oberflaeche NACH allen Anbauten nachziehen.
    fenster_aus_json schneidet in die LoD2-Fassadenebene; Rundkoerper/Vorbauten (wolkenrest_koerper, vorbauten_aus_json) kommen erst danach und decken das Loch zu
    (Schwabentor: Turmzylinder 0,98 m VOR der Facette f04 -> Tuer unsichtbar). Je Eintrag mit 'loch': Oberflaeche w_s = Median der Strahltreffer auf einem Ring 0,1 m um
    das Gewaende (bzw. das Loch). Liegt sie > min_vor vor der Ebene (Reliefplatte, Rundkoerper: das Gewaende muss ueber DIESER Flaeche Druckmindestmass zeigen) ODER ist das Loch zu (Treffer im Loch vor -tiefe/2), werden Gewaende-Relief (w_s - einbinden .. w_s + h)
    und Loch (bis w_s - tiefe) dort neu gebaut. Immer (24.11.2026, 1122w Sued f01 Beulen): Relief VOR dem Gewaende (ab w_s + h, 'abtrag' m) wird im Gewaende-Umriss abgetragen. GUARD: < 3 Ringtreffer oder Streuung > 0,5 m (kein ebenes Stueck Oberflaeche) -> nichts. Liefert (koerper, belege)."""
    import json, os
    if not datei or not os.path.exists(datei): return koerper, []
    DRUCK_MIN = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    belege = []; neu = []; aus = []
    for fid, F in json.load(open(datei)).items():
        if not isinstance(F, dict) or not F.get("fenster") or F.get("o") is None: continue
        o = np.array(F["o"], float); W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float))
        for f in F["fenster"]:
            if not f.get("loch") or f.get("nische"): continue
            G = f.get("gewaende") or {}; um = G.get("umriss") if len(G.get("umriss") or []) >= 3 else [[f["u0"], f["z0"]], [f["u1"], f["z0"]], [f["u1"], f["z1"]], [f["u0"], f["z1"]]]
            uu = [p[0] for p in um]; zz = [p[1] for p in um]; a0, a1, b0, b1 = min(uu) - 0.1, max(uu) + 0.1, min(zz) - 0.1, max(zz) + 0.1
            ring = [(a0, b0), (a1, b0), (a0, b1), (a1, b1), ((a0 + a1) / 2, b0), ((a0 + a1) / 2, b1), (a0, (b0 + b1) / 2), (a1, (b0 + b1) / 2)]
            mitte = ((f["u0"] + f["u1"]) / 2, (f["z0"] + f["z1"]) / 2)
            w = _oberflaeche_w(koerper, W, ring + [mitte]); wr = [x for x in w[:-1] if x is not None]; tf = max(float(f.get("tiefe") or 0.12), DRUCK_MIN)
            if len(wr) < 3 or float(np.max(wr) - np.min(wr)) > 0.5: aus.append(f"{fid} u {f['u0']:.2f}: Oberflaeche um das Loch nicht eben/nicht getroffen ({len(wr)} Treffer)"); continue
            ws = float(np.median(wr)); wl = w[-1]
            zu = wl is not None and wl > ws - 0.5 * tf
            h_ = max(float(G.get("hoehe") or 0.0), DRUCK_MIN) if G.get("umriss") else 0.0
            if h_ > 0:
                s_ = -1.0 if W.spiegel else 1.0; P = [[s_ * u, z] for u, z in um]
                if sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P))) < 0: P = P[::-1]
                # 24.11.2026 (1122w Sued f01: Beulen am Fenster): Netzrelief/Kruemel VOR dem Gewaende abtragen - das Gewaende ist die gemessene Gestalt dort (wie bogen_gewaende_spaet)
                # nie unter max(w_s, 0) + h: das Gewaende von fenster_aus_json (Ebene 0 .. h) bleibt, auch wenn der Ring auf einer zurueckspringenden Nachbarflaeche liegt
                koerper = koerper - M.extrude(CrossSection([P]), abtrag).translate((0, 0, max(ws, 0.0) + h_)).transform(W.matrix(0))
            if ws <= min_vor and not zu: continue                              # schon richtig gebaut (fenster_aus_json auf der Ebene)
            if h_ > 0:
                koerper = koerper + M.extrude(CrossSection([P]), h_ + einbinden).translate((0, 0, ws - einbinden)).transform(W.matrix(0))
            b_ = f.get("bogen") or dict(form="gerade", kaempfer=f["z1"], scheitel=f["z1"])
            if ws > min_vor:                                                  # den frueheren Schnitt in der Ebene (jetzt eingeschlossener Hohlraum hinter dem Anbau) erst fuellen
                koerper = koerper + _umriss_prisma(W, dict(f, bogen=b_), f["z0"], -(tf + 0.05), ws)
            koerper = koerper - _umriss_prisma(W, dict(f, bogen=b_), f["z0"], ws - tf, ws + h_ + 0.03)
            neu.append(dict(fassade=fid, u0=f["u0"], u1=f["u1"], z0=f["z0"], z1=f["z1"], art=f.get("art", "fenster"), oberflaeche_w=round(ws, 3), war_zu=bool(zu), gewaende_h=round(h_, 3), tiefe=round(tf, 3)))
    if neu or aus:
        belege.append(dict(seite="wand", element=f"{len(neu)} Loch/Gewaende auf der echten Oberflaeche nachgezogen (nach allen Anbauten)", quelle="bauteile.loch_gewaende_spaet: Strahltreffer um das Gewaende; Loch/Gewaende aus tools/loch_gewaende.py",
                           masse=neu, **({"hinweis": "; ".join(aus)} if aus else {})))
    _oberflaeche_w_leeren()
    return koerper, belege


def bogen_gewaende_band(form, breite, kaempfer, scheitel, unten, aussen):
    """Querschnitt (quer um die Oeffnungsmitte, hoch = z) des GEWAENDE-Bands um eine Bogen-/Toroeffnung: lichter Umriss (bogen_querschnitt) um 'aussen' m
    nach aussen versetzt (rund), unten an der Schwelle abgeschnitten, ohne das Loch selbst. Pfosten = gleiche Breite wie der Bogen."""
    innen = bogen_querschnitt(form, breite, kaempfer, scheitel, unten - 0.5)
    huelle = bogen_querschnitt(form, breite, kaempfer, scheitel, unten).offset(float(aussen), JoinType.Round, circular_segments=48)
    x0, _, x1, z1 = huelle.bounds()
    ueber = CrossSection.square((x1 - x0 + 2.0, z1 - unten + 1.0)).translate((x0 - 1.0, unten))
    return (huelle ^ ueber) - innen


def bogen_fugen_rillen(fugen, innen, aussen, breite_min, steg_min=None):
    """RILLEN fuer GEMESSENE Fugen im Gewaende-Band (24.11.2026; Fugen aus tools/bogen_gewaende.py, je Fuge Umrisspunkt q (quer, z) und Aussennormale n).
    Je Fuge ein Streifen quer zum lichten Umriss von innen bis aussen (m vom Umriss), Breite max(gemessene Breite, breite_min = Druckmindestmass). Keine Teilung,
    keine erfundene Fuge: nur die uebergebenen Stellen. DRUCKBAR: verbleibender Steg zwischen zwei Rillen (an der engsten Stelle, Innenkante) >= steg_min (Standard
    breite_min); sonst entfaellt die schwaecher belegte Fuge (Vermerk). Liefert (CrossSection, gebaut [fuge], weg [text])."""
    steg_min = breite_min if steg_min is None else steg_min
    gebaut, weg = [], []
    for f in sorted(fugen, key=lambda f: -int(f.get("fotos", 0))):
        b = max(float(f.get("breite_foto") or 0.0), float(breite_min)); q = np.array(f["q"], float); n = np.array(f["n"], float); n = n / (np.linalg.norm(n) + 1e-12)
        p_in = q + innen * n; zu_nah = None
        for g in gebaut:
            d = float(np.linalg.norm(p_in - (np.array(g["q"], float) + innen * np.array(g["n"], float))))
            if d - 0.5 * (b + g["_b"]) < steg_min: zu_nah = g; break
        if zu_nah is not None:
            weg.append(f"Fuge s {f.get('s', '?')} ({f.get('fotos')} Fotos): Steg zur Fuge s {zu_nah.get('s', '?')} < {steg_min:.3f} m - nicht druckbar, nicht gebaut"); continue
        gebaut.append(dict(f, _b=b))
    cs = CrossSection()
    for g in gebaut:
        q = np.array(g["q"], float); n = np.array(g["n"], float); n = n / (np.linalg.norm(n) + 1e-12); m = q + 0.5 * (innen + aussen) * n
        cs = cs + CrossSection.square((aussen - innen, g["_b"]), center=True).rotate(float(np.degrees(np.arctan2(n[1], n[0])))).translate((float(m[0]), float(m[1])))
    return cs, [{k: v for k, v in g.items() if k != "_b"} | {"breite_gebaut": round(g["_b"], 3)} for g in sorted(gebaut, key=lambda g: g.get("s", 0))], weg


def hoehen_aus_json(koerper, datei):
    """24.11.2026 (Hoehensitz-Befund 1122: waagerechte Bauteile sitzen kaum ueber Zufall): HOEHEN-ANGLEICH als LETZTER Bauschritt - monotone Hoehenabbildung je Seite
    aus tools/hoehen_angleich.py (audit/hoehen_angleich.json; nur Korrekturen mit angenommen=true, d. h. Wolken-Linie UND triangulierte Fotokanten einig).
    Manifold.warp_batch verschiebt nur z (Steigung >= FALT_MIN, keine Faltung -> gueltige Huelle). Liefert (koerper, belege); Beleg-Name 'Hoehenangleich'."""
    if not os.path.exists(datei): return koerper, []
    J = json.load(open(datei)); K_ = [q for q in J.get("korrekturen", []) if q.get("angenommen")]
    if not K_: return koerper, []
    import hoehen_angleich as HA_
    neu = koerper.warp_batch(lambda V: HA_.verschoben(V, J))
    if neu.is_empty() or neu.volume() < 0.5 * koerper.volume():                # Gueltigkeits-Guard: Abbildung darf den Koerper nicht zerstoeren
        return koerper, [dict(seite="wand", element=f"{HA_.ELEMENT_BELEG} NICHT angewendet (Koerper nach Abbildung ungueltig)", quelle="bauteile.hoehen_aus_json (Guard)")]
    bel = [dict(seite=q["achse"], element=f"{HA_.ELEMENT_BELEG}: Linie z {q['z']:.2f} t {q['t0']:.1f}..{q['t1']:.1f} um {q['dz']:+.2f} m", quelle="tools/hoehen_angleich.py: " + q.get("grund", ""),
                bauteile=q.get("bauteile", []), z_vorher=q["z"], dz=q["dz"]) for q in K_]
    return neu, bel


def bogen_gewaende_spaet(koerper, datei, einbinden=0.15, abtrag=0.3, ring=0.15):
    """24.11.2026 (1122w, Schwabentor Nord f00 / Sued f01: Torboegen nur glattes Loch, Foto zeigt Sandstein-Gewaende aus Bogensteinen): GEWAENDE-Band um gebaute
    Tor-/Bogenoeffnungen (audit/oeffnungen_auto.json, Eintrag 'gewaende_band' von tools/bogen_gewaende.py: Aussenkante 'aussen' m vom lichten Umriss, 'vorsprung')
    auf der ECHTEN Oberflaeche nach allen Anbauten. Oberflaeche w_s = Median der Strahltreffer auf einem Ring 'ring' m ausserhalb des Bands; im Band wird Relief
    vor w_s + vorsprung bis 'abtrag' abgetragen (glatte Werksteine statt Bruchsteinrelief) und das Band von w_s - einbinden bis w_s + vorsprung gebaut
    (vorsprung mindestens Druckmindestmass). Das Loch bleibt frei (Band ohne lichten Umriss). GUARD: < 3 Ringtreffer oder Streuung (P10-P90) > 0,5 m -> nichts.
    Liefert (koerper, belege)."""
    import json, os
    if not datei or not os.path.exists(datei): return koerper, []
    DRUCK_MIN = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    belege = []; neu = []; aus = []
    for fid, F in json.load(open(datei)).items():
        if not isinstance(F, dict) or F.get("o") is None: continue
        o = np.array(F["o"], float); W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float)); s_ = -1.0 if W.spiegel else 1.0
        for x in F.get("oeffnungen", []):
            G = x.get("gewaende_band")
            if not x.get("gebaut") or not G or not G.get("aussen"): continue
            b_ = float(G["aussen"]); h_ = max(float(G.get("vorsprung") or 0.0), DRUCK_MIN); T_ = float(x.get("tiefe_m") or 0.6); un = float(x.get("unten", 0.0))
            band = bogen_gewaende_band(x["form"], float(x["breite"]), float(x["kaempfer"]), float(x["scheitel"]), un, b_)
            if band.is_empty(): aus.append(f"{fid} u {x['u']:.2f}: Band leer"); continue
            rp = [p for poly in bogen_querschnitt(x["form"], float(x["breite"]), float(x["kaempfer"]), float(x["scheitel"]), un).offset(b_ + ring, JoinType.Round).to_polygons() for p in poly]
            rp = [p for p in rp if p[1] > un + 0.5]
            rp = rp[:: max(1, len(rp) // 16)]
            w = _oberflaeche_w(koerper, W, [(float(x["u"]) + s_ * float(p[0]), float(p[1])) for p in rp]); wr = [v for v in w if v is not None]
            if len(wr) < 3 or float(np.percentile(wr, 90) - np.percentile(wr, 10)) > 0.5:
                aus.append(f"{fid} u {x['u']:.2f}: Oberflaeche um das Gewaende nicht eben/nicht getroffen ({len(wr)} Treffer)"); continue
            ws = float(np.median(wr)); w_lo = max(ws - einbinden, -T_ + 0.02)
            koerper = koerper - W.prisma(band, u=float(x["u"]), w0=ws + h_, w1=ws + h_ + abtrag)
            koerper = koerper + W.prisma(band, u=float(x["u"]), w0=w_lo, w1=ws + h_)
            e_ = dict(fassade=fid, u=x["u"], form=x["form"], lichte_breite=x["breite"], band_aussen=round(b_, 3), vorsprung=round(h_, 3), oberflaeche_w=round(ws, 3),
                      vorsprung_quelle=G.get("vorsprung_quelle", ""), pfosten_quelle=G.get("pfosten_quelle", ""))
            FG = (x.get("gewaende_fugen") or {}).get("fugen")
            if FG:                                                            # 24.11.2026: nur GEMESSENE Fugen (Mehrfoto-Beleg), nie eine Teilung
                tf = min(float(os.environ.get("FUGE_TIEFE_MM", "0.5")) * float(os.environ.get("SCALE", "87")) / 1000.0, h_ + einbinden - 0.01)
                rl, geb, weg = bogen_fugen_rillen(FG, float(G.get("innen") or 0.0), b_, DRUCK_MIN)
                rl = rl ^ band
                if not rl.is_empty(): koerper = koerper - W.prisma(rl, u=float(x["u"]), w0=ws + h_ - tf, w1=ws + h_ + abtrag)
                e_.update(fugen_gebaut=len(geb), fugen_gemessen=len(FG), fugen_winkel_grad=[g.get("winkel_grad") for g in geb],
                          fugen_breite=round(DRUCK_MIN, 3), fugen_tiefe=round(tf, 3),
                          fugen_quelle="tools/bogen_gewaende.py: radiale Fugenlinien je Einzelfoto, Mehrfoto-Beleg; Breite >= Druckmindestmass (MINMM x SCALE)",
                          fugen_tiefe_quelle="ANNAHME: Rillentiefe FUGE_TIEFE_MM (0,5 mm H0) - Fugentiefe im Wandbild nicht messbar")
                if weg: aus += [f"{fid} u {x['u']:.2f}: {t}" for t in weg]
            neu.append(e_)
    if neu or aus:
        belege.append(dict(seite="wand", element=f"{len(neu)} Gewaende-Band um Tor-/Bogenoeffnungen (Werkstein-Rahmen)", quelle="bauteile.bogen_gewaende_spaet: Band aus tools/bogen_gewaende.py "
                           "(radiale Fugen-Kohaerenz im feinen Wandbild), auf der echten Oberflaeche nach allen Anbauten", masse=neu, **({"hinweis": "; ".join(aus)} if aus else {})))
    return koerper, belege


def flaeche_w(koerper, W, u, z, w_aussen=1.0, w_innen=-1.0, schritt=0.002, halb=0.05):
    """Lage der Koerperflaeche vor der Wandebene W an (u, z): aeusserste Tiefe w, bei der ein Stab (2*halb breit/hoch) von w bis w_aussen den Koerper trifft
    (Halbierung, wie fassaden_kette.koerper_flaeche). None, wenn bis w_innen nichts getroffen wird (Loch, Oeffnung)."""
    def trifft(w): return (koerper ^ W.kasten(u - halb, u + halb, z - halb, z + halb, w, w_aussen)).volume() > 1e-7
    if trifft(w_aussen - schritt) or not trifft(w_innen): return None
    lo, hi = w_innen, w_aussen
    while hi - lo > schritt:
        m_ = 0.5 * (lo + hi)
        if trifft(m_): lo = m_
        else: hi = m_
    return lo


def wand_dicke(koerper, W, u, z, w_vorn=0.0, w_max=3.0, schritt=0.01, halb=0.05):
    """Massive Tiefe des Koerpers hinter der Wandebene W an (u, z): groesstes t (<= w_max), bei dem der Stab w_vorn - t .. w_vorn (2*halb breit/hoch) zu >= 99 % im
    Koerper liegt (Halbierung). 0, wenn schon vorn kein Koerper ist. Fuer Guards 'Nische/Oeffnung nicht tiefer als die Wand' (24.11.2026)."""
    def voll(t):
        s_ = W.kasten(u - halb, u + halb, z - halb, z + halb, w_vorn - t, w_vorn); v = s_.volume()
        return v > 0 and (koerper ^ s_).volume() >= 0.99 * v
    if not voll(schritt): return 0.0
    if voll(w_max): return w_max
    lo, hi = schritt, w_max
    while hi - lo > schritt:
        m_ = 0.5 * (lo + hi)
        if voll(m_): lo = m_
        else: hi = m_
    return lo


def nische_tiefe_guard(koerper, W, N, t0, tf, druck_min):
    """Guard fuer eine Nische mit Fensteroeffnung (tools/nischen_fenster.py, 24.11.2026 Nutzerplan 'belegte Form bauen, Mass als ANNAHME'): Nischentiefe t0 mindestens
    Druckmindestmass, und Nische + Oeffnung (t0 + tf) nicht tiefer als die massive Wand an der Nischenmitte minus Druckmindestmass (Rueckwand bleibt druckbar).
    Liefert (t0, tf, vermerke)."""
    v = []
    if t0 < druck_min - 1e-6: v.append(f"Nische u {N['u0']:.2f}: {t0:.3f} -> {druck_min:.3f} m (Druckmindestmass)"); t0 = druck_min
    d_ = wand_dicke(koerper, W, 0.5 * (N["u0"] + N["u1"]), N["z0"] + 0.25 * (N["z1"] - N["z0"]), w_vorn=0.0, w_max=t0 + tf + 2 * druck_min)
    grenze = d_ - druck_min
    if t0 + tf > grenze:
        if grenze > 0.01:                                                    # Rueckwand bleibt: Oeffnung zuerst auf Druckmindestmass, dann die Nische flacher
            tf_n = min(tf, max(grenze - t0, druck_min)); t0_n = max(0.0, min(t0, grenze - tf_n))
            v.append(f"Nische u {N['u0']:.2f}: Wand nur {d_:.2f} m massiv -> Nische {t0:.3f}->{t0_n:.3f}, Oeffnung {tf:.3f}->{tf_n:.3f} m"
                     + (" (Nische unter Druckmindestmass)" if t0_n < druck_min else "")); t0, tf = t0_n, tf_n
        else: v.append(f"Nische u {N['u0']:.2f}: Wand nur {d_:.2f} m massiv (kein Platz fuer Rueckwand) - Tiefen unveraendert")
    return t0, tf, v


def sohlbank(koerper, W, sb, druck_min=None, einbinden=0.10):
    """SOHLBANK (vorspringende Leiste unter Fenster/Nische, 21.11.2026; Masse aus tools/sohlbank_aus_fotos.py: u0, u1, z0, z1, auskragung).
    Die Rueckseite sitzt 'einbinden' m IN der gemessenen Koerperflaeche (Stab-Sonde je 3 Stellen 0,15 m unter der Sohlbank - das Relief liegt nicht immer in der
    Fassadenebene), die Vorderkante 'auskragung' davor. Hoehe und Auskragung mindestens Druckmindestmass (MINMM x SCALE), sonst ANNAHME-Vermerk.
    Liefert (koerper, vermerke); ohne getroffene Flaeche unveraendert (nichts schwebend anbauen)."""
    if druck_min is None: druck_min = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    u0, u1, z0, z1, d = float(sb["u0"]), float(sb["u1"]), float(sb["z0"]), float(sb["z1"]), float(sb["auskragung"]); ann = []
    if u1 - u0 < druck_min or d <= 0: return koerper, [f"Sohlbank u {u0:.2f}: unbrauchbar (Laenge {u1 - u0:.2f}, Auskragung {d:.3f})"]
    ws = [w for w in (flaeche_w(koerper, W, u0 + f * (u1 - u0), z0 - 0.15) for f in (0.2, 0.5, 0.8)) if w is not None]
    if not ws: return koerper, [f"Sohlbank u {u0:.2f}..{u1:.2f}: keine Wandflaeche unter der Sohlbank getroffen - nicht gebaut"]
    wf = float(np.median(ws))
    if d < druck_min: ann.append(f"Sohlbank u {u0:.2f}: Auskragung {d:.3f} -> {druck_min:.3f} m (Druckmindestmass)"); d = druck_min
    if z1 - z0 < druck_min: ann.append(f"Sohlbank u {u0:.2f}: Hoehe {z1 - z0:.3f} -> {druck_min:.3f} m (Druckmindestmass, nach unten)"); z0 = z1 - druck_min
    return koerper + W.kasten(u0, u1, z0, z1, wf - einbinden, wf + d), ann


def linien_profil(W, u0, u1, profil, wf, einbinden=0.10, druck_min=None):
    """WAAGERECHTES LINIEN-BAUTEIL (Gesims/Band/Verdachung, 24.11.2026) als Prisma ueber u0..u1: Querschnitt = konvexe Huelle der gemessenen Kantenpunkte
    (z, Ausladung a ab der Koerperflaeche wf) + Rueckseite 'einbinden' m IN der Flaeche. Ausladung/Hoehe unter Druckmindestmass werden angehoben (Vermerk).
    Liefert (koerper_teil, vermerke) oder (None, vermerke) bei unbrauchbarem Profil."""
    if druck_min is None: druck_min = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    pr = sorted((float(z), float(a)) for z, a in profil); ann = []
    if u1 - u0 < druck_min or not pr or max(a for _, a in pr) <= 0: return None, [f"Linienbauteil u {u0:.2f}..{u1:.2f}: unbrauchbar (Laenge {u1 - u0:.2f}, Profil {pr})"]
    if max(a for _, a in pr) < druck_min: ann.append(f"Ausladung {max(a for _, a in pr):.3f} -> {druck_min:.3f} m (Druckmindestmass)"); pr = [(z, druck_min if a > 0 else a) for z, a in pr]
    if pr[-1][0] - pr[0][0] < druck_min: ann.append(f"Hoehe {pr[-1][0] - pr[0][0]:.3f} -> {druck_min:.3f} m (Druckmindestmass, nach oben)"); pr.append((pr[0][0] + druck_min, pr[-1][1]))
    pts = [(u, z, wf + a) for u in (u0, u1) for z, a in pr] + [(u, z, wf - einbinden) for u in (u0, u1) for z in (pr[0][0], pr[-1][0])]
    return W.huelle(pts), ann


def linien_aus_json(koerper, datei, einbinden=0.10):
    """Gesimse, Baender, Verdachungen und Balkenkopf-Reihen aus tools/linien_bauteile.py (audit/linien_auto.json, Kettenstufe 'bauplan_linien', 24.11.2026).
    Lage der Koerperflaeche je Bauteil per Stab-Sonde (flaeche_w, 3 Stellen 0,15 m unter dem Profil, sonst darueber) - das Bauteil haengt an der GEBAUTEN Wand
    (Relief/Wandversatz), nicht an der Messebene. Masse (Hoehe je Kante, Ausladung, Stueckzahl, Teilung) aus den Fotos; ANNAHMEN stehen im JSON und im Beleg.
    Ohne getroffene Flaeche wird nichts gebaut (nichts schwebend). Liefert (koerper, belege)."""
    if not os.path.exists(datei): return koerper, []
    try: J = json.load(open(datei))
    except Exception as e: return koerper, [dict(seite="wand", element="Linien-Bauteile NICHT gebaut", quelle=datei, hinweis=f"JSON nicht lesbar: {e}")]
    belege = []; teile = []
    for fid, F in (J.get("fassaden") or {}).items():
        o = np.array(F["o"], float); W_ = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float))
        def wand_bei(us, z_unten, z_oben):
            ws = [w for w in (flaeche_w(koerper, W_, u_, z_unten - 0.15) for u_ in us) if w is not None]
            if not ws: ws = [w for w in (flaeche_w(koerper, W_, u_, z_oben + 0.15) for u_ in us) if w is not None]
            return float(np.median(ws)) if ws else None
        for B in F.get("bauteile", []):
            u0, u1 = float(B["u0"]), float(B["u1"]); wf = wand_bei([u0 + f * (u1 - u0) for f in (0.2, 0.5, 0.8)], float(B["z0"]), float(B["z1"]))
            if wf is None: belege.append(dict(seite="wand", element=f"{B['typ']} {fid} z {B['z0']:.2f}: NICHT gebaut", quelle="tools/linien_bauteile.py", hinweis="keine Koerperflaeche an der Stelle getroffen")); continue
            t_, ann = linien_profil(W_, u0, u1, B["profil"], wf, einbinden)
            if t_ is None: belege.append(dict(seite="wand", element=f"{B['typ']} {fid}: NICHT gebaut", quelle="tools/linien_bauteile.py", hinweis="; ".join(ann))); continue
            teile.append(t_)
            belege.append(dict(seite="wand", element=f"{B['typ'].capitalize()} {fid} z {B['z0']:.2f}-{B['z1']:.2f} m, u {u0:.2f}..{u1:.2f}, Ausladung {B['ausladung']:.2f} m",
                               quelle="tools/linien_bauteile.py: waagerechte Fotokanten (Ebenen-Sweep, " + str(B.get("fotos")) + " Fotos)" + (f", Profil von Wand {B['uebertragen']}" if B.get("uebertragen") else ""),
                               z0=B["z0"], z1=B["z1"], u0=u0, u1=u1, ausladung=B["ausladung"], profil=B["profil"], wand_w=round(wf, 3), fehlende_kanten_haufen=len(B.get("haufen") or []),
                               hinweis="; ".join((B.get("annahmen") or []) + ann + [f"Ausladung aus {', '.join(sorted(set(k.get('aus', '?') for k in B.get('kanten', []))))}"])))
        for R in F.get("balkenkoepfe", []):
            b, a, z0, z1 = float(R["b"]), float(R["ausladung"]), float(R["z0"]), float(R["z1"]); n_ok = 0
            for u_ in R["u"]:
                wf = wand_bei([u_], z0, z1)
                if wf is None: continue
                t_, ann = linien_profil(W_, u_ - b / 2, u_ + b / 2, [(z0, a), (z1, a)], wf, einbinden)
                if t_ is not None: teile.append(t_); n_ok += 1
            belege.append(dict(seite="wand", element=f"Balkenkopf-Reihe {fid}: {n_ok} von {R['n']} gebaut, z {z0:.2f}-{z1:.2f}, Breite {b:.2f}, Ausladung {a:.2f} m",
                               quelle="tools/linien_bauteile.py: kompakte vorstehende Kantenhaufen (Ebenen-Sweep, >= 3 Fotos je Kopf)", u=R["u"], teilung=R.get("teilung"),
                               hinweis=R.get("ausladung_aus", "") + "; Groesse = Ausdehnung der Kantenhaufen"))
    if teile: koerper = koerper + M.batch_boolean(teile, OpType.Add) if len(teile) > 1 else koerper + teile[0]
    return koerper, belege


def _umriss_prisma(W, o, unten, w0, w1):
    """Schnittkoerper eines Umrisses aus tools/nischen_fenster.py (u0, u1, z1, bogen{form, kaempfer, scheitel}) von Hoehe 'unten' an, Tiefe w0..w1."""
    b = o.get("bogen") or {}; br = o["u1"] - o["u0"]; m = (o["u0"] + o["u1"]) / 2
    if b.get("form", "gerade") == "gerade": return W.kasten(o["u0"], o["u1"], unten, o["z1"], w0, w1)
    return W.prisma(bogen_querschnitt(b["form"], br, b["kaempfer"], b["scheitel"], unten), u=m, w0=w0, w1=w1)


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
        o, _ = wand_gesetzt(os.path.join(os.path.dirname(os.path.abspath(datei)), "schleife_korrekturen.json"), F)     # 24.11.2026: Nischentiefe ab der GESETZTEN Wand (wandlage_fotokanten)
        W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float)); s = -1.0 if W.spiegel else 1.0
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


def korrekturen_aus_json(koerper, datei, art=None, ohne=None):
    """Korrekturen der Abweichungsschleife (tools/ebenen_schleife.py, audit/schleife_korrekturen.json, 21.11.2026; Methode modelle/METHODE_EBENEN_BAUPLAN.md).
    Jede Korrektur setzt ein Rechteck einer Ebene auf die dort aus Fotokanten gemessene Tiefe: {fassade, o, d, n, u0, u1, z0, z1, w_ist, w_soll, grund}.
    w_soll > w_ist: Kasten von w_ist - 0,05 bis w_soll anfuegen; w_soll < w_ist: von w_soll bis w_ist + 0,05 abtragen. Nur Eintraege mit angenommen != false. Liefert (koerper, belege)."""
    if not os.path.exists(datei): return koerper, []
    plus, minus, belege = [], [], []; KL = json.load(open(datei)).get("korrekturen", [])
    # 21.11.2026: ein Zusatzkasten reicht bis hinter die GEMESSENE Wand seiner Fassade (Wandversatz), nicht nur bis w_ist - 0,05: w_ist war die Lage des damaligen Reliefs
    # (Putzwand 0,11 m vor der Ebene); seit das Relief auf der Koerperflaeche sitzt, schwebten die Kaesten (schwabentor-1120 f03: 2 freie Stuecke).
    wv_ = {}
    for K in KL:
        if K.get("art") == "wandversatz" and K.get("angenommen") is not False: wv_[K.get("fassade")] = min(wv_.get(K.get("fassade"), 0.0), float(K["w_soll"]))
    for K in KL:
        if K.get("angenommen") is False or (art and K.get("art") != art) or (ohne and K.get("art") == ohne): continue      # art='wandversatz': am GRUNDKOERPER vor dem Relief (1. Fassung trug das Relief mit ab: Modellkanten 208 000 -> 38 000)
        o = np.array(K["o"], float); d = np.array(K["d"], float); n = np.array(K["n"], float)
        P = lambda u, z, w: [o[0] + u * d[0] + w * n[0], o[1] + u * d[1] + w * n[1], z]
        wa, wb = (min(K["w_ist"], wv_.get(K.get("fassade"), 0.0)) - 0.05, K["w_soll"]) if K["w_soll"] > K["w_ist"] else (K["w_soll"], K["w_ist"] + 0.05)
        (plus if K["w_soll"] > K["w_ist"] else minus).append(M.hull_points([P(u, z, w) for u in (K["u0"], K["u1"]) for z in (K["z0"], K["z1"]) for w in (wa, wb)]))
        belege.append(dict(seite="wand", element=f"Korrektur {K.get('id', '')} {K.get('fassade', '')}: u {K['u0']:.2f}..{K['u1']:.2f} z {K['z0']:.2f}..{K['z1']:.2f} von {K['w_ist']:+.2f} auf {K['w_soll']:+.2f} m",
                           quelle="Abweichungsschleife tools/ebenen_schleife.py: " + K.get("grund", ""), kennzahl_vorher=K.get("vorher"), kennzahl_nachher=K.get("nachher")))
    if minus: koerper = koerper - M.batch_boolean(minus, OpType.Add)
    if plus: koerper = koerper + M.batch_boolean(plus, OpType.Add)
    return koerper, belege


def drehkoerper_aus_wolkenrest(koerper, datei, nseg=48):
    """Runde Anbauten (Treppenturm, Rundturm, Saeule) aus tools/wolke_rest.py (--uebernehmen -> audit/koerper_auto.json, 21.11.2026): Haufen der dichten Wolke, der NICHT am Modell liegt, Form 'rund'.
    Achse = Kreisausgleich im Grundriss, Gestalt = gemessenes DREHPROFIL r(z) in 0,25-m-Scheiben (Schaft, Gesims) - kein Musterteil. Unter der ersten Scheibe bis z 0 mit deren Radius
    (Boden von der Wolke abgeschnitten); oben endet der Koerper, wo die Wolke endet (Haube/Dach nur, wenn die Wolke sie zeigt - sonst im Beleg als FEHLT). Nur Haufen mit angenommen != false."""
    if not os.path.exists(datei): return koerper, []
    belege = []
    for H in json.load(open(datei)).get("haufen", []):
        P = H.get("profil") or []
        if H.get("form") != "rund" or len(P) < 4 or H.get("angenommen") is False: continue
        x, y = H["kreis"]["x"], H["kreis"]["y"]; dz = P[1][0] - P[0][0]; weg = []
        # 24.11.2026 GLATTER PUTZ-SCHAFT (Befund 1122zb f04, Treppenturm: Foto glatter weisser Putz bis zum Gesims, Modell 0,7-m-Kerbe z 10,5-12,2 und 48-Eck mit 0,2-m-Facetten):
        # (a) Profilhoehen am Suchrand der Umrissmessung sind kein Messwert (rund_aus_umriss.profil_bereinigen; Daten vor diesem Fix tragen sie noch);
        # (b) Facette <= Druckmindestmass (MINMM x SCALE, 0,07 m in H0): Segmentzahl aus dem groessten Radius statt fest 48 - glatter Putz ist rund, nicht 7,5-Grad-Knicke.
        r0_ = (H.get("umriss") or {}).get("start_wolke", {}).get("r") or (H.get("kreis_wolke") or {}).get("r")
        if H.get("mass_quelle") == "foto_umriss" and r0_:
            from rund_aus_umriss import profil_bereinigen
            P, weg = profil_bereinigen(P, r0_)
        dmin_ = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
        r_max_ = max([p[1] for p in P] + [float((H.get("dach") or {}).get("r_traufe") or 0.0)])
        nseg = max(int(nseg), int(np.ceil(2 * np.pi * r_max_ / max(dmin_, 1e-3))))
        if weg: belege.append(dict(seite="wand", element=f"Rundkoerper {H.get('id', '')}: {len(weg)} Profilhoehen am Suchrand verworfen (z {weg})", quelle="rund_aus_umriss.profil_bereinigen",
                                   hinweis="Radius am Rand des Suchbereichs = kein Umriss gefunden; Hoehe traegt den Radius der gemessenen Hoehe darunter"))
        kd, bel_k = kegeldach_teile(H.get("dach"), x, y, P, nseg)                   # 23.11.2026: Kegeldach aus den Foto-Umrissen (rund_aus_umriss.kegeldach), sonst flach wie bisher
        if kd: P = [p for p in P if p[0] < kd[0] - 1e-6]
        teile = [M.cylinder(P[0][0] + 0.01, P[0][1], P[0][1], nseg).translate((x, y, 0.0))]
        for (z0, r0, _), (z1, r1, _) in zip(P[:-1], P[1:]): teile.append(M.cylinder(z1 - z0 + 0.005, r0, r1, nseg).translate((x, y, z0)))
        teile.append(M.cylinder((kd[0] - P[-1][0] + 0.005) if kd else dz / 2, P[-1][1], P[-1][1], nseg).translate((x, y, P[-1][0])))
        if kd: teile += kd[1]
        koerper = koerper + M.batch_boolean(teile, OpType.Add); belege += bel_k
        belege.append(dict(seite="wand", element=f"Rundkoerper {H.get('id', '')} bei x {x:.2f} y {y:.2f}: Schaft r {float(np.median([p[1] for p in P])):.2f} m, z 0..{P[-1][0] + dz / 2:.2f} m, groesster Radius {max(p[1] for p in P):.2f} m",
                           quelle=(f"FOTO-UMRISS (tools/rund_aus_umriss.py): {H.get('umriss', {}).get('fotos')} Fotos, {H.get('umriss', {}).get('beobachtungen')} Umrissbeobachtungen, Drehprofil in {len(P)} Hoehen, Traufe {H.get('traufe')}; Lage aus der dichten Wolke (Wolkenradius {H.get('kreis_wolke', {}).get('r')} m nur Startwert)"
                                   if H.get("mass_quelle") == "foto_umriss" else f"dichte Wolke: Rest am Modell ({H['punkte']} Punkte), Kreisausgleich Rest {H['kreis']['rest']} m, Drehprofil in {len(P)} Scheiben (tools/wolke_rest.py) - VORLAEUFIG, kein Fotomass"),
                           hinweis="ANNAHME: voll (nicht hohl), " + ("Kegeldach siehe eigener Beleg" if kd else "oben flach abgeschlossen, wo die Wolke endet - Haube/Dach FEHLT") + "; Oeffnungen fehlen (Abwicklung noch nicht in der Kette)"))
    return koerper, belege


def kegeldach_teile(KD, x, y, P, nseg=48):
    """KEGELDACH eines Rundkoerpers (23.11.2026) aus dem Block 'dach' (tools/rund_aus_umriss.kegeldach: Traufe z/r und Spitze aus den Umriss-Mantellinien der Fotos).
    Formfamilie gerade (ein Kegel) oder geschweift/gebaucht (Block "profil": Traufe -> Knick -> Spitze, je Stueck ein Kegelstumpf; Guard: z steigend, r nicht wachsend).
    -> ((z_traufe, [Teile]) | None, Belege). Gueltigkeits-Guard: Block gueltig, Spitze >= 0,2 m ueber der Traufe, Traufradius 0,5..2 x Schaft, mind. 2 Profilhoehen unter der Traufe;
    sonst None (Rundkoerper bleibt oben flach, Beleg nennt den Grund). Druckbar: Traufbrett mind. MINMM x SCALE dick (0,8 mm in H0 = 7 cm), Spitze als Kegelstumpf mit
    Radius MINMM/2 x SCALE (keine Nadelspitze unter dem Druckmass)."""
    if not KD: return None, []
    if not KD.get("gueltig"): return None, [dict(seite="dach", element=f"Kegeldach Rundkoerper bei x {x:.2f} y {y:.2f} NICHT gebaut", quelle="tools/rund_aus_umriss.kegeldach", hinweis=str(KD.get("grund")))]
    dmin = float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    z_t, r_e, z_s = float(KD["z_traufe"]), float(KD["r_traufe"]), float(KD["z_spitze"]); r_s = float(np.median([p[1] for p in P if p[0] < z_t] or [p[1] for p in P]))
    unter = [p for p in P if p[0] < z_t - 1e-6]
    if z_s < z_t + 0.2 or not 0.5 * r_s <= r_e <= 2.0 * r_s or len(unter) < 2:
        return None, [dict(seite="dach", element=f"Kegeldach Rundkoerper bei x {x:.2f} y {y:.2f} NICHT gebaut (Guard)", quelle="bauteile.kegeldach_teile", hinweis=f"Traufe z {z_t} r {r_e}, Spitze z {z_s}, Schaft r {r_s:.2f}, Profilhoehen unter der Traufe {len(unter)}")]
    r_top = max(0.5 * dmin, 0.01); brett = dmin
    # 23.11.2026 geschweiftes/gebauchtes Dach: Profil (Traufe -> Knick -> Spitze) aus rund_aus_umriss.kegeldach, je Stueck ein Kegelstumpf; gerade = ein Stumpf
    PR = [[float(z), float(r)] for z, r in (KD.get("profil") or [[z_t, r_e], [z_s, 0.0]])]
    if any(z1 <= z0 + 1e-3 or r1 > r0 + 1e-6 for (z0, r0), (z1, r1) in zip(PR[:-1], PR[1:])) or abs(PR[0][0] - z_t) > 1e-3 or abs(PR[-1][0] - z_s) > 1e-3:
        return None, [dict(seite="dach", element=f"Kegeldach Rundkoerper bei x {x:.2f} y {y:.2f} NICHT gebaut (Guard Profil)", quelle="bauteile.kegeldach_teile", hinweis=f"Profil {PR} nicht steigend/verjuengend")]
    z_o, r_o = PR[-2]; PR[-1] = [z_s - (z_s - z_o) * r_top / max(r_o, 1e-9), r_top]                 # Spitze als Stumpf mit Druckradius (auf der Mantellinie des obersten Stuecks)
    teile = [M.cylinder(brett + 0.005, r_e, r_e, nseg).translate((x, y, z_t - brett))]                 # Traufbrett (sonst Messerkante am Ueberstand)
    for (z0, r0), (z1, r1) in zip(PR[:-1], PR[1:]):
        teile.append(M.cylinder(z1 - z0 + (0.005 if (z1, r1) != tuple(PR[-1]) else 0.0), r0, max(r1, r_top), nseg).translate((x, y, z0)))
    fam = KD.get("familie") or "kegel"; kn = KD.get("knick")
    return (z_t - brett, teile), [dict(seite="dach", element=f"Kegeldach ({fam}) Rundkoerper bei x {x:.2f} y {y:.2f}: Traufe z {z_t:.2f} r {r_e:.2f} (Schaft {r_s:.2f}), "
                                       + (f"Knick z {kn['z']:.2f} r {kn['r']:.2f} (unten {KD.get('neigung_unten_grad')} / oben {KD.get('neigung_oben_grad')} Grad), " if kn else f"Neigung {KD.get('neigung_grad')} Grad, ")
                                       + f"Spitze z {z_s:.2f}",
                                       quelle=f"tools/rund_aus_umriss.kegeldach: Umriss-Mantellinien in {KD.get('fotos')} kalibrierten Fotos, {KD.get('einig')} einig ueber die Spitze, Stuetze {KD.get('stuetze')}"
                                       + (f"; Formwahl {KD.get('formwahl')}" if KD.get("formwahl") else ""),
                                       hinweis=f"ANNAHME: Traufhoehe = Traufe/Oberkante des Drehprofils (Mantellinie koppelt z und r); Profil aus geraden Kegelstuempfen (Knick statt stetiger Schweifung); Traufbrett {brett:.2f} m und Spitzenradius {r_top:.3f} m = Druckmindestmass, nicht gemessen; Knauf/Wetterfahne nicht gebaut")]


def dach_aus_profil(koerper, datei):
    """Dach als SCHICHTKOERPER aus tools/dach_profil_wolke.py (audit/dach_profil.json, 21.11.2026): je Hoehenscheibe das Rechteck der dichten Wolke im Fassadenrahmen (Ueberstand, Neigung,
    Laternenkoerper ohne Musterteil). Das bisherige Modell wird ueber z0 abgetragen, die Scheiben werden als Huellen aufeinanderfolgender Rechtecke aufgesetzt; oben flach, wo die Wolke endet.
    Seiten ohne Wolke sind im Profil an der gemessenen Achse gespiegelt (ANNAHME, im Beleg)."""
    if not os.path.exists(datei): return koerper, []
    D = json.load(open(datei)); P = D.get("scheiben") or []
    if len(P) < 4 or D.get("angenommen") is False: return koerper, []
    o = np.array(D["o"], float); d = np.array(D["d"], float); n = np.array(D["n"], float); dz = float(D.get("schritt", 0.5)); z0 = float(D["z0"])
    R = lambda p, z: [[o[0] + u * d[0] + v * n[0], o[1] + u * d[1] + v * n[1], z] for u in (p[1], p[2]) for v in (p[3], p[4])]
    lo, hi = koerper.bounding_box()[:3], koerper.bounding_box()[3:]; koerper = koerper - M.cube((hi[0] - lo[0] + 20, hi[1] - lo[1] + 20, hi[2] - z0 + 40)).translate((lo[0] - 10, lo[1] - 10, z0))
    SF = D.get("spitze_foto") or {}; ab = spitze_ab(SF); bel_sp = []
    if ab is not None: P = [p for p in P if p[0] + dz <= ab + 1e-6] or P[:1]       # 21.11.2026: ueber 'ab' kommt die Laterne/Spitze aus den Foto-Silhouetten (tools/spitze_aus_umriss.py), die Wolke ist dort duenn
    # 21.11.2026 (Nutzer "noch nicht gut", neben_eigen__IMG_20261106_113231.jpg: dicke dunkle Traufe im Foto, duenne 2-cm-Scheibe im Modell): Traufe der Seiten mit
    # Fotomessung (tools/traufe_aus_fotos.py, Block 'traufe_foto') als Traufkasten mit Untersicht + Stirn; Scheiben dort auf die Aussenkante begrenzt, Traufring eingefuegt.
    P, kaesten_tr, bel_tr = traufe_einbauen(P, D)
    # 22.11.2026 (Koordinator, Kontrollbild IMG_113056: Foto gerade Pyramide, Modell glockig gestuft + breiter Absatz unter dem Aufsatz): DACHFLAECHE aus den Foto-
    # Silhouetten (tools/dachflaeche_aus_umriss.py, Block 'flaeche_foto': Profil g(t; c) von der Foto-Traufkante bis zum Fuss des Aufsatzes) statt Wolkenscheiben.
    fl_, bel_fl = flaeche_aus_foto(P, D)
    if fl_ is not None:
        P = P[:fl_[0] + 1]; oben = [list(map(float, q)) for q in fl_[1][-1]]
        teile = [M.hull_points(R(a_, a_[0]) + R(b_, b_[0])) for a_, b_ in zip(P[:-1], P[1:])] + [M.hull_points(R(P[0], z0 - 0.02) + R(P[0], P[0][0]))]
        teile += [M.hull_points(np.vstack([a_, b_]).tolist()) for a_, b_ in zip(fl_[1][:-1], fl_[1][1:])]
        ab = float(fl_[2]) if SF.get("gueltig") and SF.get("profil") and SF.get("angenommen") is not False else None
    else:
        oben = R(P[-1], P[-1][0] + dz)
        teile = [M.hull_points(R(a_, a_[0]) + R(b_, b_[0])) for a_, b_ in zip(P[:-1], P[1:])] + [M.hull_points(R(P[-1], P[-1][0]) + R(P[-1], P[-1][0] + dz))] + [M.hull_points(R(P[0], z0 - 0.02) + R(P[0], P[0][0]))]
    # 22.11.2026 (Koordinator, Foto IMG_113231/113056: offene Laterne mit Pfosten, Krempe, Haube, Knauf, Nadel - Modell runde Zwiebel): LATERNE aus den Kanten im Inneren
    # der Silhouette (tools/laterne_aus_fotos.py, Block 'laterne_foto') als bauteile.laterne; ohne gueltigen Block wie bisher die Drehringe aus spitze_foto.
    LB = laterne_aus_block(D.get("laterne_foto"), SF) if ab is not None else None
    if LB is not None:
        lp, hq = LB; z_dach = min(p[2] for p in oben); lp = dict(lp, z_fuss=max(min(lp["z_fuss"], z_dach + 0.3), z_dach + 0.05))   # Pfosten stehen im Dach (mind. 0,25 m eingebunden)
        lk, lh = laterne(**lp); teile.append(lk); LF = D["laterne_foto"]
        bel_sp = [dict(seite="dach", element=f"Laterne aus Fotokanten: {lp['n']} Pfosten (b {lp['b_pfosten']:.2f} m, Umkreis {lp['r_pfosten']:.2f} m) z {lp['z_fuss']:.2f}..{lp['z_pfosten_oben']:.2f}, "
                                              f"Krempe z {lp['krempe']['z_kante']:.2f} (r {lp['krempe']['r_kante']:.2f}), Haube {LF.get('familie')} {lp['n_haube']}-Eck bis Hals z {lp['haube'][-1][0]:.2f}, "
                                              f"Knauf {lp['knauf']}, Nadel bis z {lp['nadel'][0] if lp['nadel'] else None}",
                       quelle=f"tools/laterne_aus_fotos.py: {len(LF.get('fotos', [])) - len(LF.get('ausreisser', []))} Fotos (az {LF.get('az_bereich')}), Pfosten-Kontrastabstand {LF['pfosten'].get('abstand')}; bauteile.laterne",
                       hinweis="; ".join([hq] + lh + list(LF.get("annahmen", [])) + ([LF["nadel_grund"]] if LF.get("nadel_grund") else []) + ["ANNAHME: Nadelradius 0,03 m (nicht gemessen)"]))]
        ab = None
    if ab is not None:
        A = SF["achse"]; FP = [p for p in SF["profil"] if p[0] >= ab - 1e-6] or SF["profil"][-1:]
        def ring(p, z):
            if len(p) > 6 and p[4] == "eckig":
                t = math.radians(p[5]); a = p[6]; return [[A[0] + a * (sx * math.cos(t) - sy * math.sin(t)), A[1] + a * (sx * math.sin(t) + sy * math.cos(t)), z] for sx in (-1, 1) for sy in (-1, 1)]
            r = p[6] if len(p) > 6 else p[1]; return [[A[0] + r * math.cos(w), A[1] + r * math.sin(w), z] for w in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        teile.append(M.hull_points(list(oben) + ring(FP[0], FP[0][0])))                 # Anschluss Dach (Wolke bzw. Fotoflaeche) -> erste Fotohoehe des Aufsatzes
        teile += [M.hull_points(ring(a_, a_[0]) + ring(b_, b_[0])) for a_, b_ in zip(FP[:-1], FP[1:])]
        teile.append(M.hull_points(ring(FP[-1], FP[-1][0]) + [[A[0], A[1], float(SF["spitze_z"])]]))    # letzte Hoehe -> Spitze (Knauf/Nadel als Kegel, Durchmesser unter der Druckgrenze faellt beim Druck weg)
        nr_ = sum(1 for p in FP if len(p) > 6 and p[4] == "eckig")
        bel_sp = [dict(seite="dach", element=f"Laterne/Spitze aus Foto-Silhouetten ab z {ab:.2f} bis Spitze z {SF['spitze_z']:.2f} m" + (f", Krempe z {SF['krempe_z']:.2f} (Hals z {SF['hals_z']:.2f})" if SF.get("krempe_z") else ""),
                       quelle=f"tools/spitze_aus_umriss.py: Himmelskante in {SF.get('fotos')} kalibrierten Fotos aus Sektoren {SF.get('sektoren')}, Spitze Median (Streuung {SF.get('spitze_streuung')} m)",
                       hinweis=f"ANNAHME: Querschnitt {nr_} von {len(FP)} Hoehen eckig, Rest rund (Blickrichtungs-Abhaengigkeit der Halbbreite); Laterne voll gebaut (offene Pfosten nicht aufgeloest); Spitze auf der Dachachse")]
    teile += kaesten_tr
    koerper = koerper + M.batch_boolean(teile, OpType.Add); ann = sum(len(p[6]) for p in P if len(p) > 6 and isinstance(p[6], list))
    return koerper, [dict(seite="dach", element=f"Dach als Schichtprofil ab z {z0:.1f} m: Traufe halb {(P[0][2] - P[0][1]) / 2:.2f} x {(P[0][4] - P[0][3]) / 2:.2f} m (Wand {D['wand_halb'][0]:.2f} x {D['wand_halb'][1]:.2f}), Neigung ~{D.get('neigung_grad')} Grad, bis z {P[-1][0] + dz:.1f} m",
                          quelle=f"dichte Wolke, {len(P)} Scheiben je {dz} m (tools/dach_profil_wolke.py); ersetzt das LoD2/Laser-Dach (bis {D.get('modell_hoehe_vorher', 0):.1f} m)",
                          hinweis=f"ANNAHME: {ann} von {4 * len(P)} Scheibenseiten ohne Wolke an der gemessenen Achse gespiegelt (Dachflaeche von keinem Foto gesehen); Stufen von {dz} m statt glatter Flaeche; "
                                  + ("Laterne/Spitze darueber aus Fotos" if bel_sp else "Spitze/Knauf ueber dem Wolkenende FEHLT") + "; Dach voll" + ("; ueber der Traufe Dachflaeche aus Fotos (siehe Beleg)" if fl_ else ""))] + bel_sp + bel_tr + bel_fl


def flaeche_aus_foto(P, D, n=12):
    """Dachflaeche aus 'flaeche_foto' (tools/dachflaeche_aus_umriss.py): Ringe von der Traufe (Traufring aus traufe_einbauen, sonst oberste Scheibe unter der Traufe)
    bis zum Fuss des Aufsatzes mit dem gemessenen Profil c. -> ((Index der Anschlussscheibe, Ringe, z_fuss) | None, Belege). Gueltigkeits-Guard: Fuss ueber der Traufe,
    Fuss schmaler als die Traufe."""
    FF = D.get("flaeche_foto") or {}
    if not FF.get("gueltig") or FF.get("angenommen") is False or not FF.get("z_fuss") or not FF.get("fuss") or not P: return None, []
    ir = next((k for k, p in enumerate(P) if len(p) > 6 and p[6] == "traufe_foto"), None)
    if ir is None: ir = max([k for k, p in enumerate(P) if p[0] <= float(FF.get("z_traufe", P[0][0])) + 1e-6] or [0])
    r_ = P[ir]; z_t, z_f = float(r_[0]), float(FF["z_fuss"]); a_f = float(FF["fuss"]["halb"])
    if z_f < z_t + 1.0 or a_f >= 0.9 * min(r_[2] - r_[1], r_[4] - r_[3]) / 2: return None, [dict(seite="dach", element="Dachflaeche aus Fotos NICHT gebaut (Guard)", quelle="bauteile.flaeche_aus_foto", hinweis=f"Fuss z {z_f} / halb {a_f} gegen Traufe z {z_t}")]
    from dachflaeche_aus_umriss import ringe as _ringe, ringe_dom1_veto as _veto
    A = np.array(FF.get("achse") or D["o"], float); c_ = 0.0 if FF.get("familie") == "gerade" else float(FF.get("c", 0.0))   # Familie 'gerade' -> Ebenen (Koordinator 22.11.), c innerhalb der Familie = Messrauschen
    # 23.11.2026 (Schwabentor-1122p HOEHEN-TOR +1,73 m): DOM1-Veto der Fotoflaeche (Block flaeche_foto.dom1_veto aus tools/dachflaeche_aus_umriss.py) - feinere Ringe (0,3 m),
    # damit die Flaeche dem Laser-Knick an der Traufe folgen kann; Seiten > tol ausserhalb der Isolinie auf die Isolinie
    V = FF.get("dom1_veto") or {}; iso = {round(float(q[0]), 2): q[1:5] for q in V.get("isolinien") or []} if V.get("aktiv") else {}
    if iso: n = max(n, int(math.ceil((z_f - z_t) / 0.3)))
    rs = _ringe((np.array(D["o"], float), np.array(D["d"], float), np.array(D["n"], float), r_[1], r_[2], r_[3], r_[4]), (A, a_f, None if FF["fuss"].get("theta") is None else float(FF["fuss"]["theta"])), z_t, z_f, c_, n=n)
    vt = ""
    if iso:
        rs, ein_ = _veto(rs, D["o"], D["d"], D["n"], iso, tol=float(V.get("tol_m", 0.3)))
        vt = (f"; DOM1-VETO: {len(ein_)} Ringseiten auf die Laser-Isolinie gesetzt (Foto bis {max(e['foto_m'] - e['laser_m'] for e in ein_):.2f} m weiter draussen)" if ein_ else "; DOM1-Veto: Fotoflaeche innerhalb der Laser-Isolinie")
    return (ir, rs, z_f), [dict(seite="dach", element=f"Dachflaeche aus Foto-Silhouetten: {FF.get('familie')} (gemessen c {FF.get('c')}, gebaut c {c_}) von der Traufe z {z_t:.2f} bis zum Fuss des Aufsatzes z {z_f:.2f} (halb {a_f:.2f} m)",
                                quelle=f"tools/dachflaeche_aus_umriss.py: Himmelskante in {FF.get('fotos_gut')} guten Fotos gegen gerenderte Profil-Hypothesen, Konsens {FF.get('konsens')}, Restfehler {FF.get('fehler_median')} m (gerade {FF.get('fehler_gerade_median')} m)",
                                hinweis="ersetzt die Wolkenscheiben ueber der Traufe (Wolke/DOM1 dort glockig gestuft); ANNAHME: Fussquerschnitt " + str(FF["fuss"].get("quelle")) + ", Ecken der Traufe laufen gerade zu den Fussecken (Grate)" + vt)]


TRAUF_SEITEN = {"-d": (1, -1), "+d": (2, 1), "-n": (3, -1), "+n": (4, 1)}      # Seite -> (Index in der Scheibe [z, u_lo, u_hi, v_lo, v_hi], Vorzeichen)


def traufkasten(o, e, t, w_innen, w_wand, z_wand, w_aussen, z_unten, z_oben, s0, s1):
    """TRAUFKASTEN (GENERISCH, 21.11.2026): Prisma entlang einer Dachseite mit Querschnitt Einbindung -> Wandanschluss (w_wand, z_wand) -> Untersicht -> Stirn-Unterkante
    (w_aussen, z_unten) -> Stirn -> Aussenkante (w_aussen, z_oben) -> waagrecht zurueck bis w_innen. w = Abstand von o entlang der Aussennormalen e (2D), s0..s1 entlang t.
    Gestalt nur aus den uebergebenen Massen (tools/traufe_aus_fotos.py), kein Musterteil. Konvexer Querschnitt (z_wand <= z_unten <= z_oben, w_innen < w_wand < w_aussen)."""
    o = np.asarray(o, float); e = np.asarray(e, float); t = np.asarray(t, float)
    q = [(w_innen, z_wand), (w_wand, z_wand), (w_aussen, z_unten), (w_aussen, z_oben), (w_innen, z_oben)]
    return M.hull_points([[*(o + w * e + s * t), z] for w, z in q for s in (s0, s1)])


def traufe_einbauen(P, D, einbinden=0.3):
    """Traufe der FOTO-gemessenen Seiten (dach_profil.json 'traufe_foto', tools/traufe_aus_fotos.py) in das Scheibenprofil einbauen -> (P neu, Traufkaesten, Belege).
    Je gueltiger Seite: alle Scheiben auf die Aussenkante begrenzt (das Dach steht nirgends weiter hinaus als die gemessene Traufe), ein Traufring in Hoehe der
    Aussenkante eingefuegt (die Dachflaeche beginnt an der Traufkante) und ein Traufkasten (Untersicht + Stirn) von der Wand bis zur Aussenkante, entlang der Seite
    bis zur Traufe der Nachbarseiten (Ecke). Seiten ohne gueltige Fotomessung bleiben wie die Wolke/DOM1 sie liefern (Beleg nennt sie und den Grund)."""
    TF = D.get("traufe_foto") or {}
    if not TF.get("gueltig") or TF.get("angenommen") is False or not P: return P, [], []
    o = np.array(D["o"], float); d = np.array(D["d"], float); n = np.array(D["n"], float); wh = D["wand_halb"]
    gut = {}
    for s, E in (TF.get("seiten") or {}).items():
        if s not in TRAUF_SEITEN or not E.get("gueltig"): continue
        zu = E.get("z_unten") if E.get("z_unten") is not None else E.get("z_unten_bau", E["z_oben"] - 0.08); zw = E.get("z_wand_bau", E["z_wand"])   # z_wand_bau: ueber einem offenen Umgang
        if not (E["a_wand"] < E["a_aussen"] and zw <= zu <= E["z_oben"] and E["a_aussen"] - E["a_wand"] <= 2.5 and E["z_oben"] - zw <= 3.0): continue   # Gueltigkeits-Guard
        gut[s] = dict(E, _zu=zu, _zw=zw, _h=float(wh[0] if "d" in s else wh[1]))
    if not gut: return P, [], []
    P = [list(p) for p in P]
    for s, E in gut.items():                                                       # Dach nirgends weiter hinaus als die Traufkante dieser Seite
        i, sg = TRAUF_SEITEN[s]; ext = E["_h"] + E["a_aussen"]
        for p in P: p[i] = sg * min(sg * p[i], ext)
    zr = float(np.median([E["z_oben"] for E in gut.values()]))
    def lage(z):                                                                   # Scheibe bei z (linear zwischen den Nachbarn, ausserhalb die Randscheibe)
        zs = [p[0] for p in P]
        if z <= zs[0]: return list(P[0][1:5])
        if z >= zs[-1]: return list(P[-1][1:5])
        k = next(k for k in range(1, len(P)) if zs[k] >= z); f = (z - zs[k - 1]) / max(zs[k] - zs[k - 1], 1e-9)
        return [P[k - 1][j] + f * (P[k][j] - P[k - 1][j]) for j in range(1, 5)]
    ring = [round(zr, 3)] + lage(zr) + [0, "traufe_foto"]
    for s, E in gut.items(): i, sg = TRAUF_SEITEN[s]; ring[i] = sg * (E["_h"] + E["a_aussen"])
    P = sorted([p for p in P if abs(p[0] - zr) > 0.05] + [ring], key=lambda p: p[0])
    kaesten = []; bel = []
    for s, E in gut.items():
        e = {"-d": -d, "+d": d, "-n": -n, "+n": n}[s]; t = n if "d" in s else d
        s0, s1 = (ring[3], ring[4]) if "d" in s else (ring[1], ring[2])
        h = E["_h"]; kaesten.append(traufkasten(o, e, t, h + E["a_wand"] - einbinden, h + E["a_wand"], E["_zw"], h + E["a_aussen"], E["_zu"], E["z_oben"], s0, s1))
        st = (f"Stirn {E['z_oben'] - E['z_unten']:.2f} m (Unterkante z {E['z_unten']:.2f} gemessen)" if E.get("z_unten") is not None
              else (E.get("unterkante_quelle") or "ANNAHME: Stirn-Unterkante in den Fotos nicht aufgeloest -> Untersicht als Ebene Wandanschluss -> Aussenkante") + f" (Untersicht {E.get('untersicht_grad')} Grad, Stirn {E['z_oben'] - E['_zu']:.2f} m)")
        if E.get("umgang_z1") is not None: st += f"; offener Umgang darunter (Raehm z {E['umgang_z1']:.2f}): Kasten erst ab z {E['_zw']:.2f}, Laufgang bleibt offen"
        bel.append(dict(seite="dach", element=f"Traufkasten {s} aus Fotos: Ueberstand {E['ueberstand']:.2f} m vor dem Wandanschluss, Aussenkante z {E['z_oben']:.2f} m, Wandanschluss z {E['z_wand']:.2f} m",
                        quelle=f"tools/traufe_aus_fotos.py: Kanten-Sweep waagrechter Traufkanten in {E.get('fotos')} kalibrierten Fotos (Hoehenwinkel {E.get('el_bereich')}), in beiden Fotohaelften bestaetigt; bauteile.traufkasten",
                        ueberstand=E["ueberstand"], a_wand=E["a_wand"], a_aussen=E["a_aussen"], z_wand=E["z_wand"], z_oben=E["z_oben"], z_unten=E.get("z_unten"),
                        hinweis=st + f"; Wandanschluss {E['a_wand']:+.2f} m gegen die Profilwand (wand_halb) - die Modellwand darunter wird hier nicht verschoben"))
    rest = [s for s in TRAUF_SEITEN if s not in gut]
    if rest: bel.append(dict(seite="dach", element=f"Traufe {', '.join(rest)} NICHT aus Fotos: weiter aus Wolke/DOM1-Scheiben (vorlaeufig)",
                             quelle="tools/traufe_aus_fotos.py", hinweis="; ".join(f"{s}: {((TF.get('seiten') or {}).get(s) or {}).get('grund') or 'nicht gemessen'}" for s in rest)))
    return P, kaesten, bel


def spitze_ab(SF):
    """Ab welcher Hoehe die Foto-Silhouette (dach_profil.json 'spitze_foto', tools/spitze_aus_umriss.py) das Wolkendach ersetzt: Beginn des Laternenhalses (erste Fotohoehe,
    deren Halbbreite hoechstens 10 % ueber dem Hals liegt - darunter misst die Wolke die Dachflaeche gut und der Querschnitt ist ein Rechteck), ohne Hals das Wolkenende.
    None = kein gueltiger Fotoblock (Generator baut nur das Wolkendach)."""
    if not SF.get("gueltig") or not SF.get("profil") or SF.get("angenommen") is False: return None
    if SF.get("hals_halb"):
        z = next((p[0] for p in SF["profil"] if p[1] <= 1.1 * SF["hals_halb"]), None)
        if z is not None: return float(z)
    z = next((p[0] for p in SF["profil"] if p[0] >= float(SF.get("wolke_ende_z", 1e9)) - 1e-6), None)
    return None if z is None else float(z)


def _ring_n(achse, n, phase_grad, r, z):
    """Ecken eines regelmaessigen n-Ecks (Umkreis r, Ecke 0 bei Weltwinkel phase_grad) in Hoehe z."""
    return [[achse[0] + r * math.cos(math.radians(phase_grad + k * 360.0 / n)), achse[1] + r * math.sin(math.radians(phase_grad + k * 360.0 / n)), z] for k in range(n)]


def laterne(achse, n, phase_grad, r_pfosten, b_pfosten, z_fuss, z_pfosten_oben, krempe, haube, knauf=None, nadel=None, n_haube=None, phase_haube=None,
            massstab=87.0, min_mm=0.8, deck=None):
    """OFFENE n-ECK-LATERNE (Dachreiter) mit Pfosten, Krempe, Haube, Knauf, Nadel (GENERISCH, 22.11.2026; Masse aus tools/laterne_aus_fotos.py, kein Musterteil).
    achse (x, y); n Pfosten an den Ecken eines regelmaessigen n-Ecks (Umkreis r_pfosten der Pfostenmitten, Ecke 0 bei phase_grad), Querschnitt b_pfosten x b_pfosten,
    von z_fuss bis z_pfosten_oben (Pfosten reichen 0,3 m unter z_fuss ins Dach).
    deck: Dicke des Rahmens auf den Pfosten (Standard = b_pfosten), Umkreis r_pfosten + b_pfosten.
    krempe: dict(z_kante, r_kante, dicke) - Untersicht vom Rahmen schraeg bis zur Kante (n-Eck wie die Pfosten), Oberseite von der Kante bis zum Haubenfuss.
    haube: Liste (z, r_umkreis) aufsteigend (Haubenfuss .. Hals) - n_haube-Eck (Standard n) mit phase_haube (Standard phase_grad), Huellen je Ringpaar (geschweift/Zwiebel).
    knauf: (z_mitte, r) Kugel; nadel: (z_oben, r) Stange vom Knauf bis z_oben.
    DRUCKBAR (H0 1:massstab): Mindestmass min_mm -> d_min = min_mm * massstab / 1000 m (0,8 mm -> 7 cm). Pfosten schmaler als d_min: geschlossener n-Eck-Koerper
    (Umkreis r_pfosten + b/2) mit flachen Nischen zwischen den Pfosten (Andeutung, ANNAHME im Beleg). Nadel/Hals duenner als d_min werden auf d_min verdickt (ANNAHME).
    -> (Manifold, Liste Hinweise)."""
    d_min = min_mm * massstab / 1000.0; hin = []; teile = []; A = [float(achse[0]), float(achse[1])]
    nh = int(n_haube or n); ph_h = float(phase_grad if phase_haube is None else phase_haube); deck = float(deck if deck is not None else b_pfosten)
    z_u = z_fuss - 0.3; r_aussen = r_pfosten + b_pfosten / 2
    if b_pfosten >= d_min:
        for k in range(n):
            w = math.radians(phase_grad + k * 360.0 / n); c = (A[0] + r_pfosten * math.cos(w), A[1] + r_pfosten * math.sin(w)); h = b_pfosten / 2
            e = (math.cos(w), math.sin(w)); t = (-e[1], e[0])                                       # Pfosten radial ausgerichtet (Seite zur Achse)
            teile.append(M.hull_points([[c[0] + su * h * e[0] + sv * h * t[0], c[1] + su * h * e[1] + sv * h * t[1], z] for su in (-1, 1) for sv in (-1, 1) for z in (z_u, z_pfosten_oben)]))
        hin.append(f"{n} Pfosten {b_pfosten:.2f} m ({b_pfosten * 1000 / massstab:.1f} mm bei 1:{massstab:g}) offen")
    else:
        k_ = M.hull_points(_ring_n(A, n, phase_grad, r_aussen, z_u) + _ring_n(A, n, phase_grad, r_aussen, z_pfosten_oben)); t_ = min(0.5 * d_min, 0.3 * r_pfosten)
        for k in range(n):                                                                           # Nische je Seite zwischen zwei Pfosten (Andeutung der Oeffnung)
            w0 = math.radians(phase_grad + k * 360.0 / n); w1 = math.radians(phase_grad + (k + 1) * 360.0 / n); zb = (z_fuss + 0.15, z_pfosten_oben - 0.1)
            p0 = np.array([math.cos(w0), math.sin(w0)]) * r_aussen; p1 = np.array([math.cos(w1), math.sin(w1)]) * r_aussen; m_ = (p0 + p1) / 2; nm = m_ / max(np.linalg.norm(m_), 1e-9)
            q0 = p0 + (p1 - p0) * (b_pfosten + d_min) / max(np.linalg.norm(p1 - p0), 1e-9) * 0.5; q1 = p1 - (p1 - p0) * (b_pfosten + d_min) / max(np.linalg.norm(p1 - p0), 1e-9) * 0.5
            if np.dot(q1 - q0, p1 - p0) <= 0 or zb[1] <= zb[0]: continue
            pts = [[A[0] + q[0] + s * nm[0], A[1] + q[1] + s * nm[1], z] for q in (q0, q1) for s in (-t_, 0.3) for z in zb]
            k_ = k_ - M.hull_points(pts)
        teile.append(k_); hin.append(f"ANNAHME: Pfosten {b_pfosten:.2f} m unter dem Druckmindestmass {d_min:.3f} m -> geschlossener {n}-Eck-Koerper mit Nischen {t_:.3f} m (Andeutung der offenen Laterne)")
    zr0 = z_pfosten_oben; zr1 = zr0 + deck
    teile.append(M.hull_points(_ring_n(A, n, phase_grad, r_aussen, zr0 - 0.01) + _ring_n(A, n, phase_grad, r_aussen, zr1)))        # Rahmen auf den Pfosten
    zk, rk, dk = float(krempe["z_kante"]), float(krempe["r_kante"]), float(krempe.get("dicke") or d_min)
    hz0, hr0 = haube[0]
    teile.append(M.hull_points(_ring_n(A, n, phase_grad, r_aussen, zr1 - 0.01) + _ring_n(A, n, phase_grad, rk, zk) + _ring_n(A, n, phase_grad, rk, zk + dk)
                               + _ring_n(A, nh, ph_h, max(hr0, d_min / 2), max(hz0, zk + dk))))
    hb = [(float(z), max(float(r), d_min / 2)) for z, r in haube]
    if any(r < d_min / 2 for _, r in haube): hin.append(f"ANNAHME: Haubenhals unter {d_min / 2:.3f} m Radius auf das Druckmindestmass verdickt")
    for (za, ra), (zb_, rb) in zip(hb[:-1], hb[1:]):
        teile.append(M.hull_points(_ring_n(A, nh, ph_h, ra, za) + _ring_n(A, nh, ph_h, rb, zb_ + 1e-4)))
    z_ob = hb[-1][0]
    if knauf:
        zk_, rk_ = float(knauf[0]), max(float(knauf[1]), d_min / 2)
        teile.append(M.sphere(rk_, 32).translate((A[0], A[1], zk_)))
        teile.append(M.cylinder(max(zk_ - z_ob, 0.01) + 0.02, max(hb[-1][1], d_min / 2), max(hb[-1][1], d_min / 2), 24).translate((A[0], A[1], z_ob - 0.01)))   # Hals bis zur Knaufmitte
        z_ob = zk_ + rk_ * 0.8
    if nadel:
        zn, rn = float(nadel[0]), float(nadel[1])
        if rn < d_min / 2: hin.append(f"ANNAHME: Nadel r {rn:.3f} m auf {d_min / 2:.3f} m verdickt (druckbar)")
        rn = max(rn, d_min / 2)
        if zn > z_ob: teile.append(M.cylinder(zn - z_ob + 0.02, rn, rn * 0.6, 16).translate((A[0], A[1], z_ob - 0.02)))
    return M.batch_boolean(teile, OpType.Add), hin


N_RUND = 48             # Haube 'rund': 48-Eck (Sehne 3 mm bei r 1,1 m in H0 << Druckaufloesung)


def laterne_aus_block(LF, SF=None, massstab=87.0):
    """Block 'laterne_foto' (tools/laterne_aus_fotos.py) -> Parameter fuer laterne(); None, wenn ungueltig/abgelehnt. Haube: eigene Eckenzahl nur wenn eindeutig,
    sonst die der Pfosten (ANNAHME im Beleg). Radien = Silhouetten-Halbbreite / Silhouettenfaktor des Vielecks. Nadel: eigene Messung, sonst spitze_foto.spitze_z."""
    if not LF or not LF.get("gueltig") or LF.get("angenommen") is False: return None
    Pf, Z, H = LF["pfosten"], LF["zonen"], LF.get("haube") or {}
    if H.get("eindeutig"): nh, phh, fh, hq = int(H["n"]), float(H["phase"]), float(H.get("silh_faktor") or 1.0), f"Haube {H['n']}-Eck aus Facettenstufen (Abstand {H.get('abstand')})"
    else: nh, phh, fh, hq = int(Pf["n"]), float(Pf["phase"]), float(Pf.get("silh_faktor") or 1.0), f"ANNAHME: Haube {Pf['n']}-Eck wie die Pfosten (Facettenprobe unentschieden: bestes {H.get('n')}-Eck, Abstand {H.get('abstand')})"
    fp = float(Pf.get("silh_faktor") or 1.0)
    hb = [(p[0], p[1] / fh) for p in LF["profil"] if Z["z_taille"] - 1e-6 <= p[0] <= Z["z_hals"] + 1e-6]
    # 23.11.2026 (Kette 1122r: Haube als Kasten statt Zwiebel): Haube als DREHKOERPER aus der Sehstrahl-Huelle (laterne_aus_fotos.haube_huelle: registrierte Farbsilhouetten,
    # Umkreis je Hoehe), Querschnitt rund/n-Eck nach Fotobeleg bzw. benannter ANNAHME (querschnitt_haube); ohne Huelle wie bisher Median-Halbbreite / Silhouettenfaktor.
    HH = LF.get("haube_huelle") or {}; Q = HH.get("querschnitt") or {}
    hh = [(float(p[0]), float(p[1])) for p in HH.get("profil") or [] if Z["z_taille"] - 1e-6 <= p[0] <= Z["z_hals"] + 1e-6]
    if Q.get("art") in ("rund", "n-eck") and len(hh) >= 3 and (Q["art"] == "rund" or Q.get("n")):
        hb = hh
        if Q["art"] == "rund": nh, phh, hq = N_RUND, 0.0, Q.get("annahme") or f"Haube rund ({Q.get('quelle')})"
        else: nh, phh, hq = int(Q["n"]), float(Q.get("phase") or 0.0), Q.get("annahme") or f"Haube {Q['n']}-Eck ({Q.get('quelle')})"
        hq += f"; Profil Sehstrahl-Huelle aus {len(HH.get('bindende_fotos') or [])} bindenden Fotos, Familie {HH.get('familie')}"
    if len(hb) < 3: return None
    nz = LF.get("nadel_z") or (SF or {}).get("spitze_z")
    return dict(achse=LF["achse"], n=int(Pf["n"]), phase_grad=float(Pf["phase"]), r_pfosten=float(Pf["R"]), b_pfosten=float(Pf["breite"]), z_fuss=float(Z.get("z_pfosten_unten", LF["z_fuss"])),
                z_pfosten_oben=float(Z["z_pfosten_oben"]), krempe=dict(z_kante=float(Z["z_krempe"]), r_kante=float(Z["r_krempe"]) / fp), haube=hb,
                knauf=(float(Z["z_knauf"]), float(Z["r_knauf"])) if Z.get("r_knauf", 0) > 1.05 * Z.get("r_hals", 0) else None,
                nadel=(float(nz), 0.03) if nz else None, n_haube=nh, phase_haube=phh, massstab=massstab), hq


def uhren_aus_json(koerper, datei, w_ring=0.10, w_feld=0.06, details=False):      # 21.11.2026: Katalog-Ziffern/Zeiger aus (Nutzer: kein Baukasten) - nur die gemessenen Kreise
    """Turmuhren aus tools/uhren_wandbild.py (audit/uhren_auto.json, Kettenstufe 'bauplan', 21.11.2026; vorher nur Hand-Generator schwab_v3/martinstor_v4).
    Gemessen: Mitte, Aussen- und (falls belegt) Innendurchmesser im feinen Wandbild. Ring bis w_ring vor der Wandebene, Innenfeld bis w_feld (ANNAHME 10 / 6 cm wie schwab_v3);
    details=True: Wand.zifferblatt (Wulste, 12 Ziffern, Zeiger) - Ziffernform/Zeit = ANNAHME. Ohne Innenkreis: Innenfeld = 0,66 x Aussen (ANNAHME, schwab_v3 3,52/5,36)."""
    if not os.path.exists(datei): return koerper, []
    belege = []
    # 21.11.2026 (Kettenlauf 1121m: Abnahme 'Anzahl getrennte Koerper' = 2): die Schleife hatte die Wand um -0,15 m zurueckgesetzt (Korrektur 'wandversatz'), der Uhrring reichte
    # nur bis -0,05 m hinter die ALTE Wandebene und schwebte 10 cm vor der Wand. Der Ring reicht jetzt bis hinter die gemessene Wandlage dieser Fassade.
    wv_ = {}; kp_ = os.path.join(os.path.dirname(datei), "schleife_korrekturen.json")
    if os.path.exists(kp_):
        for K_ in json.load(open(kp_)).get("korrekturen", []):
            if K_.get("art") == "wandversatz" and K_.get("angenommen") is not False: wv_[K_.get("fassade")] = min(wv_.get(K_.get("fassade"), 0.0), float(K_["w_soll"]))
    for fid, F in json.load(open(datei)).items():
        o = np.array(F["o"], float); W_ = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float))
        for U in F.get("uhren", []):
            da = float(U["d_aussen"]); di = float(U["d_innen"]) if U.get("d_innen") else 0.66 * da
            zb_ = os.path.join(os.path.dirname(datei), U["zifferblatt"]) if U.get("zifferblatt") else ""
            if zb_ and os.path.exists(zb_) and os.environ.get("OHNE_ZIFFERBLATT") != "1":
                # 21.11.2026 (Nutzerbild: Uhr nur flacher Kreis): Zifferblatt-RELIEF aus dem Wandbild (tools/uhren_wandbild.zifferblatt_aus_fotos: Goldteile, Mehrheit der Einzelfotos,
                # Striche auf >= 0,8 mm verbreitert). Hoehen ueber der GEMESSENEN Wandflaeche (Wandversatz der Abweichungsschleife), nicht ueber der alten Fassadenebene.
                import sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from relief_einsatz import koerper as _rk
                b_ = wv_.get(fid, 0.0); t_ = 0.05 - b_
                koerper = koerper + (_rk(zb_, tiefe=t_, flaeche=b_, rand_auslauf=False) ^ W_.scheibe(U["u"], U["z"], da, -t_ - 0.01, 1.0))
                Zz_ = np.load(zb_)
                belege.append(dict(seite="wand", element=f"Uhr {fid} (Durchmesser {da:.2f} m): Zifferblatt-Relief aus dem Wandbild", quelle="tools/uhren_wandbild.py (Kreis im 1-cm-Wandbild) + zifferblatt_aus_fotos (Goldteile aus " + str(len(U.get("zifferblatt_fotos", []))) + " Einzelfotos, Mehrheit)",
                                   mitte_u=U["u"], mitte_z=U["z"], d_aussen=da, d_innen=di, gold_anteil=float(Zz_["gold_anteil"]), wand_w=b_, zeiger_foto=U.get("zeiger_foto"),
                                   hinweis="Gestalt (Ziffernfelder, Randwulst, Zeiger) aus dem Wandbild; Zeiger aus dem schaerfsten Einzelfoto (Uhrzeit dieses Fotos); ANNAHME Hoehen: Feld 6 cm, Ring 10 cm, Gold +7 cm (0,8 mm); Striche auf 0,8 mm verbreitert; audit/" + U["zifferblatt"][:-4] + ".jpg ansehen"))
                continue
            ring = W_.scheibe(U["u"], U["z"], da, min(-0.05, wv_.get(fid, 0.0) - 0.05), w_ring) - W_.scheibe(U["u"], U["z"], di, w_feld, w_ring + 0.05)
            koerper = koerper + ring
            if details: koerper = koerper + W_.zifferblatt(U["u"], U["z"], da, di)
            belege.append(dict(seite="wand", element=f"Uhr {fid} (Durchmesser {da:.2f} m)", quelle=U.get("quelle", "tools/uhren_wandbild.py"), mitte_u=U["u"], mitte_z=U["z"], d_aussen=da, d_innen=di,
                               hinweis="ANNAHME: Ringtiefe 10 cm, Feld 6 cm" + ("" if U.get("d_innen") else ", Innendurchmesser 0,66 x Aussen (nicht gemessen)") + ("; Ziffern/Zeiger/Zeit generisch (Wand.zifferblatt)" if details else "")))
    return koerper, belege


def vordach_profil_z(s, c):
    """Profil eines Vordachs 0..1 (s = 0 Traufe, s = 1 Wandanschluss): c = 0 gerade, c > 0 geschweift (flach an der Traufe, steil an der Wand), c < 0 gewoelbt."""
    s = np.asarray(s, float)
    return s if abs(c) < 1e-6 else (np.exp(c * s) - 1.0) / (np.exp(c) - 1.0)


def vordach_walm(W, u0, u1, w_wand, w_t, z_t, z_a, c=0.0, As=0.0, dk=0.15, einbinden=0.10, n=16):
    """WALM-VORDACH mit gemessenem Profil (GENERISCH, 21.11.2026; Masse aus tools/vordach_profil.py -> audit/vordach_profil.json).
    Front z = z_t + (z_a - z_t) * g(a / (w_t - w_wand)), Seiten dasselbe Profil auf den Walm-Ruecksprung As skaliert (As = 0: senkrechte Giebelseiten).
    Gebaut als Stapel von Huellen zwischen aufeinanderfolgenden Hoehenrechtecken (u0 + t As .. u1 - t As, w_wand - einbinden .. w_t - t A) - ein krummes Profil wird
    so stueckweise eben (n Stufen); Unterseite flach dk unter der Traufe (Traufkasten/Galeriedecke). Ziegel nicht modelliert (glatt)."""
    A = w_t - w_wand; wi = w_wand - einbinden
    if A <= 0.05 or u1 - u0 <= 2 * As + 0.1: return M()
    t = np.linspace(0.0, 1.0, n + 1); z = z_t + (z_a - z_t) * vordach_profil_z(t, c)
    def rect(tk, zk): return [(u, zk, w) for u in (u0 + tk * As, u1 - tk * As) for w in (wi, max(w_t - tk * A, wi + 0.02))]
    teile = [W.huelle(rect(0.0, z_t - dk) + rect(0.0, z_t))] + [W.huelle(rect(a_, za) + rect(b_, zb)) for a_, b_, za, zb in zip(t[:-1], t[1:], z[:-1], z[1:])]
    return M.batch_boolean(teile, OpType.Add)


def vorbau_kasten_ersatz(g, min_aus=0.15):
    """ERSATZ-KANTENMASS fuer einen Vorbau ohne Kantenkasten (24.11.2026, Rueckfall Treppenkloetze 1122z-zc). Liefert ein dict im Format von ebenen_masse 'kanten_mass'
    (kasten, ausladung, konsolen, streben), damit vorbauten_aus_json denselben Kasten-Zweig baut - nie das Hoehenfeld. Quellen in Rangfolge (alle aus den Fotos):
      1. galerie (vorbauten_bauplan.galerie_messen: Bruestungsband z_boden..z_holm, u0..u1, Ausladung w, Streben im feinen Wandbild gezaehlt, Strebenfuss)
      2. koerper (Grobband des Ebenen-Sweeps: u0..u1, z0..z1, w_median) = ein Kasten.
    GUARD: Breite 0,5..30 m, Hoehe 0,3..8 m, Ausladung min_aus..3 m, sonst naechste Quelle / None (nichts bauen)."""
    def ok(u0, u1, z0, z1, a):
        return all(np.isfinite([u0, u1, z0, z1, a])) and 0.5 <= u1 - u0 <= 30 and 0.3 <= z1 - z0 <= 8 and min_aus <= a <= 3.0
    G = g.get("galerie") or {}
    try:
        u0, u1, zb, zh, a = (float(G[k]) for k in ("u0", "u1", "z_boden", "z_holm", "w"))
        if ok(u0, u1, zb, zh, a):
            km = dict(ausladung=a, kasten=dict(z_unten=zb, z_oben=zh, u0=u0, u1=u1, breite=round(u1 - u0, 2)), ersatz="Galerie (Ebenen-Sweep + Wandbild)",
                      quelle="vorbauten_bauplan.galerie_messen (Ersatz, Kanten zu duenn)", ersatz_annahme="ERSATZ Galerie-Messung: Kasten = Bruestungsband, Ausladung Sweep (kein Kantenkasten)")
            # Konsolen/Streben NICHT im Ersatz: ihre Querschnitte waeren feste Zahlen (Nutzer 24.11.: "Alle Masse muessen aus Fotos kommen") - Beleg nennt die Luecke
            if G.get("streben_u"): km["ersatz_annahme"] += "; %d Streben im Wandbild gezaehlt, aber ohne gemessenen Querschnitt NICHT gebaut" % len(G["streben_u"])
            return km
    except (KeyError, TypeError, ValueError): pass
    k = g.get("koerper") or {}
    try:
        u0, u1, z0, z1, a = (float(k[x]) for x in ("u0", "u1", "z0", "z1", "w_median"))
        if ok(u0, u1, z0, z1, a):
            return dict(ausladung=a, kasten=dict(z_unten=z0, z_oben=z1, u0=u0, u1=u1, breite=round(u1 - u0, 2)), ersatz="Grobkoerper (Ebenen-Sweep)",
                        quelle="vorbauten_bauplan koerper (Ersatz, Kanten zu duenn)", ersatz_annahme="ERSATZ Grobkoerper: ein Kasten (Band + Median-Ausladung), keine Konsolen")
    except (KeyError, TypeError, ValueError): pass
    return None


def treppen_anteil(mesh, o, d, n, u0, u1, z0, z1, w_min=0.1, zelle=0.1, klein=(0.03, 0.4)):
    """TREPPEN-MASS einer Vorbau-Gestalt (24.11.2026, Guard gegen den Hoehenfeld-Rueckfall): Tiefenkarte der Front (Strahlen von vorn, Raster 'zelle') im Bereich u0..u1 x z0..z1,
    Tiefe w gegen die Ebene (o, d, n). Gezaehlt werden waagrecht benachbarte Zellen, die beide Vorbau sind (w > w_min): Anteil mit KLEINEM Tiefensprung (klein[0]..klein[1] m).
    Kasten/Galerie/Vordach: gleiche Tiefe entlang u, Spruenge nur an Kanten zur Wand (gross) -> ~0. Hoehenfeld: Laeufe verschiedener Tiefe je Zeile -> deutlich > 0.
    mesh: trimesh.Trimesh. Liefert (anteil, paare)."""
    import trimesh
    o = np.asarray(o, float); d = np.asarray(d, float); n = np.asarray(n, float)
    uu = np.arange(u0 + zelle / 2, u1, zelle); zz = np.arange(z0 + zelle / 2, z1, zelle); U, Z = np.meshgrid(uu, zz)
    w_vor = 6.0; ori = np.c_[o[0] + U.ravel() * d[0] + w_vor * n[0], o[1] + U.ravel() * d[1] + w_vor * n[1], Z.ravel()]
    dirs = np.tile([-n[0], -n[1], 0.0], (len(ori), 1))
    loc, idx, _ = mesh.ray.intersects_location(ori, dirs, multiple_hits=False)
    W = np.full(len(ori), -9.0)
    if len(idx): W[idx] = (loc[:, :2] - o[:2]) @ n[:2]
    W = W.reshape(U.shape); A = (W[:, 1:] > w_min) & (W[:, :-1] > w_min); dW = np.abs(np.diff(W, axis=1))
    paare = int(A.sum()); kl = int((A & (dW >= klein[0]) & (dW <= klein[1])).sum())
    return (kl / paare if paare else 0.0), paare


def vorbauten_aus_json(koerper, datei, stufe=0.05, min_w=0.15, einbinden=0.10):
    """Vorbauten (Erker, Galerie, Vordach, Balkon) aus dem Ebenen-Sweep an die Wand bauen (20.11.2026, GENERISCH; Liste: tools/vorbauten_bauplan.py
    -> audit/vorbauten_auto.json, Kettenstufe 'bauplan'). Je Gruppe ein Hoehenfeld w[zeile][spalte] (m vor der gemessenen Wand, Raster 'raster', Zeile 0 = oben):
    zeilenweise gleich tiefe Laeufe (auf 'stufe' gerundet) werden Kaesten von 'einbinden' m in der Wand bis zur Front. Gestalt = gemessene Tiefe je Zelle, kein Musterteil.
    24.11.2026: das Hoehenfeld wird NICHT mehr als Gestalt gebaut (Treppenkloetze, Rueckfall 1122z-zc) - ohne kanten_mass.kasten baut der Kasten-Zweig aus
    vorbau_kasten_ersatz (Galerie-Messung / Grobkoerper); MIT_HOEHENFELD=1 nur fuer Vergleich und rote Probe (tools/test_vorbau_keine_treppe.py).
    Liefert (koerper, belege); ohne Datei unveraendert."""
    if not os.path.exists(datei): return koerper, []
    J = json.load(open(datei)); teile = []; belege = []; VPJ = {}
    vpd = os.path.join(os.path.dirname(os.path.abspath(datei)), "vordach_profil.json")       # tools/vordach_profil.py (Kettenstufe 'bauplan'); OHNE_VORDACH_PROFIL=1 = ebene Platte wie bisher
    if os.path.exists(vpd) and os.environ.get("OHNE_VORDACH_PROFIL") != "1":
        try: VPJ = {(e.get("id"), e.get("gruppe", 0)): e for e in json.load(open(vpd)).get("fassaden", []) if e.get("profil")}
        except Exception: VPJ = {}
    for F in J.get("fassaden", []):
        o = np.array(F["o"], float); d = np.array(F["d"], float); n = np.array(F["n"], float); ww = float(F.get("w_wand", 0.0))
        # 24.11.2026 (Risiko b, wandlage_fotokanten): Einbindung bis hinter die GESETZTE Wand (Front bleibt gemessen ww + Ausladung) - sonst Spalt, wenn die Wand hinter w_wand liegt
        wv_ = wandversatz_fassade(os.path.join(os.path.dirname(os.path.abspath(datei)), "schleife_korrekturen.json"), o, n); w0 = min(0.0, ww, wv_) - einbinden
        P = lambda u, z, w: [o[0] + u * d[0] + w * n[0], o[1] + u * d[1] + w * n[1], z]
        for gi_, g in enumerate(F["gruppen"]):
            if g.get("verworfen"): continue      # 23.11.2026: Beleg-/Fototor (tools/vorbau_fototor.py) hat die Gruppe verworfen (Phantom f03 1122t) - Index gi_ bleibt fuer vordach_profil gleich
            KM_ = g.get("kanten_mass"); G_ = g.get("galerie")
            if not (KM_ and KM_.get("kasten")) and os.environ.get("MIT_HOEHENFELD") != "1" and not (G_ and os.environ.get("MIT_KATALOG_GALERIE") == "1"):
                # 24.11.2026 RUECKFALL 1122z/zb/zc (Nutzer: "wir hatten mal so einen geilen Stand und du machst KI-Muell"): ohne Kantenkasten fiel der Bau STILL auf das
                # Hoehenfeld je 0,2-m-Zelle zurueck = Treppenkloetze (bekannte Sackgasse 21.11., METHODE_EBENEN_BAUPLAN). Jetzt nie mehr Hoehenfeld als Gestalt: Ersatz-Kasten aus
                # den uebrigen Fotomessungen derselben Gruppe (Galerie-Messung, sonst Grobkoerper) im SELBEN Kasten-Zweig; ohne gueltigen Ersatz wird nichts gebaut (Beleg).
                KM_ = vorbau_kasten_ersatz(g)
                if not KM_:
                    belege.append(dict(seite="wand", element=f"Vorbau {F.get('id', '')} u {g['u0']:.2f}..{g['u1']:.2f} NICHT gebaut", quelle="bauteile.vorbau_kasten_ersatz",
                                       hinweis="kein Kantenkasten und keine gueltige Ersatzmessung (Galerie/Grobkoerper) - Hoehenfeld als Gestalt ist verworfen (Treppenkloetze)"))
                    continue
            if KM_ and KM_.get("kasten") and os.environ.get("OHNE_KANTENMASS") != "1":
                # 21.11.2026 (Nutzer: "so wenig allgemeine Bauteile wie moeglich ... was nicht moeglich ist, wird aus allgemeinen Bauteilen gebaut"): Vorbau aus den dichten triangulierten
                # Fotokanten seiner Ebene (tools/ebenen_bauplan.py -> tools/ebenen_masse.py). Aus Kanten: Kasten (Unter-/Oberkante, Breite, Ausladung), Konsolen (Zahl, Lage, Unterkante),
                # Strebenfuss, Pfostenlage. Nicht aus Kanten (ANNAHME, im Beleg): Pfostenquerschnitt, Strebe gerade, Raehm, Dachflaeche (nur Traufe/Anschluss gemessen).
                WG = Wand(o, o + d, aussen=o + n); Kb = KM_["kasten"]; wf = ww + float(KM_["ausladung"]); wi = min(ww, wv_) - einbinden; KK = WG.kasten; ann = []
                Br_ = KM_.get("bruestung") or {}; z_p0 = Kb["z_oben"] - 0.02          # z_p0: Pfostenfuss
                if Br_.get("offen") and os.environ.get("OHNE_BRUESTUNG_OFFEN") != "1":
                    # 24.11.2026 (1122w, Foto 113130: Schwelle, vorstehender Holm, dazwischen offen mit Knaggen an den Pfosten, Gemaelde dahinter sichtbar; Kette baute einen
                    # vollen Kasten): Riegel und Knaggen aus den Kantenpunkten (ebenen_masse.bruestung), Feld offen. Schwelle traegt Boden und Pfosten.
                    so_ = Br_.get("schwelle_oben") or (Kb["z_unten"] + 0.3); hu_ = Br_["holm_unten"]
                    hf_ = max(ww + float(Br_["holm_front"]), wf); hh_ = ww + float(Br_["holm_hinten"]) if Br_.get("holm_hinten") is not None else wf - 0.2
                    hh_ = min(hh_, wf - 0.12)
                    teile.append(KK(Kb["u0"], Kb["u1"], Kb["z_unten"], so_, wi, wf))                                   # Schwelle + Boden
                    teile.append(KK(Kb["u0"] - 0.05, Kb["u1"] + 0.05, hu_, Kb["z_oben"], hh_, hf_))                     # Holm (steht vor)
                    for k_ in Br_.get("knaggen") or []:                                                                 # Knaggen: Trapez, unten Haufenbreite, oben Pfostenbreite
                        um_ = 0.5 * (k_["u0"] + k_["u1"]); hb_ = max(0.5 * (k_["u1"] - k_["u0"]), 0.15)
                        teile.append(WG.huelle([(um_ + s_ * hb_, so_ - 0.02, w_) for s_ in (-1, 1) for w_ in (wf - 0.12, wf)] + [(um_ + s_ * 0.11, hu_ + 0.02, w_) for s_ in (-1, 1) for w_ in (wf - 0.12, wf)]))
                    z_p0 = so_ - 0.02
                    ann.append("Bruestung offen (Kanten): Schwelle z %.2f-%.2f%s, Holm z %.2f-%.2f vor bis w %.2f, %d Knaggen (Trapez, 0,12 m stark = ANNAHME)"
                               % (Kb["z_unten"], so_, "" if Br_.get("schwelle_oben") else " (Oberkante ANNAHME +0,3 m)", hu_, Kb["z_oben"], hf_ - ww, len(Br_.get("knaggen") or [])))
                else: teile.append(KK(Kb["u0"], Kb["u1"], Kb["z_unten"], Kb["z_oben"], wi, wf))
                Ko = KM_.get("konsolen"); St = KM_.get("streben")
                if Ko:
                    for a_, b_ in Ko["lage"]:
                        teile.append(KK(a_, b_, Ko["z_unten"], Kb["z_unten"] + 0.02, wi, wf))
                        if St and St["z_fuss"] < Ko["z_unten"] - 0.3:
                            teile.append(WG.huelle([(u_, z_, w_) for u_ in (a_, b_) for z_, w_ in ((St["z_fuss"], wi), (St["z_fuss"] + 0.3, wi), (Ko["z_unten"] + 0.02, wf - 0.3), (Ko["z_unten"] + 0.02, wf - 0.05))]))
                    ann.append("Konsolen als Balken von der Wand bis zur Front" + ("; Streben gerade vom Wandfuss zur Konsole" if St else ""))
                z_d = (G_ or {}).get("z_dach"); V_ = (G_ or {}).get("vordach"); Pf = KM_.get("pfosten") or []
                if 0 < len(Pf) < 2 and z_d and len((G_ or {}).get("pfosten") or []) >= 2 and os.environ.get("OHNE_SWEEP_PFOSTEN_ERGAENZEN") != "1":   # ein Schalter fuer beide Ergaenzungen (Merge 24.11.)
                    # 24.11.2026 (1122zc, duenne Kanten: nur 1 Pfosten aus einer Knagge) - Vordach auf einem Pfosten; Sweep-Pfostenspalten ergaenzen, die nicht schon belegt sind
                    Pf = sorted(list(Pf) + [dict(u=float(u_), breite=None) for u_ in G_["pfosten"] if all(abs(float(u_) - float(p_["u"])) >= 0.6 for p_ in Pf)], key=lambda p_: float(p_["u"]))
                    ann.append("Pfosten aus Kanten ergaenzt um Sweep-Pfostenspalten (nur %d aus Kanten)" % 1)
                if not Pf and z_d and len((G_ or {}).get("pfosten") or []) >= 2:
                    # 24.11.2026 (1122w, Nutzer: "Bild-Vorbau hatten wir mal fast perfekt"): ohne Kanten-Pfosten stand das Vordach ohne Stuetze ueber der Galerie (getrennter Koerper,
                    # offene Galerie fehlte). Ersatz = Pfostenspalten des Ebenen-Sweeps (vorbauten_bauplan.galerie_messen, ebenfalls aus den Fotos), Querschnitt Standard.
                    Pf = [dict(u=float(u_), breite=None) for u_ in G_["pfosten"]]; ann.append("Pfostenlage aus den Sweep-Pfostenspalten (Kanten ohne Pfosten)")
                elif Pf and z_d and os.environ.get("OHNE_SWEEP_PFOSTEN_ERGAENZEN") != "1":
                    # 24.11.2026 (Nutzer: Handstand schwab_v3 besser; Foto 113029 Galerie mit Pfosten an BEIDEN Enden, Kette 1122zc nur 1 Pfosten aus einer Knagge):
                    # Kanten-Pfosten und Sweep-Pfostenspalten sind beide Fotomessungen - Sweep-Pfosten ohne Kanten-Pfosten in 0,6 m werden ergaenzt (nicht ersetzt).
                    neu_ = [float(u_) for u_ in (G_ or {}).get("pfosten") or [] if not any(abs(float(u_) - float(p_["u"])) < 0.6 for p_ in Pf)]
                    if neu_: Pf = sorted(Pf + [dict(u=u_, breite=None) for u_ in neu_], key=lambda p_: p_["u"]); ann.append("Sweep-Pfosten ergaenzt bei u %s" % ", ".join("%.2f" % u_ for u_ in neu_))
                if z_d and z_d > Kb["z_oben"] + 0.5:
                    for p_ in Pf:
                        # 24.11.2026 (Kette 1122u: Abnahme "2 getrennte Koerper" = Pfosten f00 bei u 4,25 neben dem Kasten u -3,81..4,09 - stand frei zwischen Kasten und Raehm):
                        # Pfosten traegt Raehm und steht auf dem Kasten -> Mitte in dessen u-Bereich ziehen (Kanten-Pfostenlage und Kastenende uneinig = Messunschaerfe am Rand)
                        bp = p_["breite"] or 0.22; up = min(max(float(p_["u"]), Kb["u0"] + bp / 2), Kb["u1"] - bp / 2)
                        if abs(up - float(p_["u"])) > 1e-6: ann.append("Pfosten u %.2f lag neben dem Kasten (u %.2f..%.2f) -> auf %.2f an dessen Ende gerueckt" % (p_["u"], Kb["u0"], Kb["u1"], up))
                        teile.append(KK(up - bp / 2, up + bp / 2, z_p0, z_d + 0.02, wf - bp, wf))
                    if Pf: ann.append("Pfostenquerschnitt %s" % ", ".join(("%.2f m gemessen" % p_["breite"]) if p_["breite"] else "0,22 m Standard" for p_ in Pf))
                    zt = V_["z_traufe"] if V_ else z_d + 0.3
                    VP_ = VPJ.get((F.get("id"), gi_))
                    if V_ and not VP_:              # 24.11.2026: ebene Platte steigt zur Wand an - an der Raehmflucht w = wf liegt ihre Unterseite ueber der Traufe; Raehm bis dorthin (+5 cm), sonst schwebt die Platte
                        wt_ = wf + 0.25; zt = V_["z_traufe"] + (V_["z_anschluss"] - 0.15 - V_["z_traufe"]) * (wt_ - wf) / max(wt_ - wi, 0.1) + 0.05
                    teile.append(KK(Kb["u0"], Kb["u1"], z_d, zt, wf - 0.25, wf)); teile.append(KK(Kb["u0"], Kb["u0"] + 0.25, z_d, zt, wi, wf)); teile.append(KK(Kb["u1"] - 0.25, Kb["u1"], z_d, zt, wi, wf)); ann.append("Raehm 0,25 m stark (Hoehe aus dem Sweep-Band)")
                    if V_ and VP_:                  # 21.11.2026 (Nutzer: Vordach im Foto geschweiftes Walmdach, Modell ebene Platte): Profil + Walm aus Foto-Silhouetten (tools/vordach_profil.py)
                        teile.append(vordach_walm(WG, VP_["u0"], VP_["u1"], ww, VP_["w_t"], VP_["z_t"], VP_["z_a"], c=VP_["c"], As=VP_["As"], einbinden=einbinden + max(0.0, ww - wv_)))
                        ann.append(f"Vordach {VP_['familie']} (c {VP_['c']:+.1f}, Walm-Ruecksprung {VP_['As']:.2f} m, Traufe w {VP_['w_t']:.2f} z {VP_['z_t']:.2f}, Anschluss z {VP_['z_a']:.2f}) aus "
                                   f"{len(VP_.get('fotos', []))} Foto-Silhouetten ({VP_.get('fotos_familie')} Fotos einzeln gleiche Familie); {VP_.get('annahme', '')}")
                    elif V_:
                        ua, ub, dk, wt = Kb["u0"] - 0.15, Kb["u1"] + 0.15, 0.15, wf + 0.25
                        teile.append(WG.huelle([(u_, z_, w_) for u_ in (ua, ub) for z_, w_ in ((V_["z_anschluss"], wi), (V_["z_anschluss"] - dk, wi), (V_["z_traufe"] + dk, wt), (V_["z_traufe"], wt))]))
                        ann.append("Vordach = ebene Platte (allgemeines Bauteil): Traufe und Wandanschluss gemessen, Ueberstand 0,25 m und Dachhaut 0,15 m Standard")
                if KM_.get("ersatz"): ann.append(KM_["ersatz_annahme"])
                belege.append(dict(seite="wand", element=f"Vorbau {F.get('id', '')} aus {'Fotokanten' if not KM_.get('ersatz') else 'Ersatzmessung ' + KM_['ersatz']}: Kasten z {Kb['z_unten']:.2f}-{Kb['z_oben']:.2f}, Breite {Kb['breite']:.2f}, Ausladung {KM_['ausladung']:.2f} m"
                                   + (f", {Ko['anzahl']} Konsolen" if Ko else "") + (f", {len(Pf)} Pfosten" if Pf and z_d else "") + (", Vordach" if V_ and z_d else ""),
                                   quelle=KM_.get("quelle", "tools/ebenen_masse.py"), kasten=Kb, konsolen=(Ko or {}).get("anzahl"), konsolen_abstand=(Ko or {}).get("abstand"), strebenfuss=(St or {}).get("z_fuss"),
                                   pfosten_u=[p_["u"] for p_ in Pf], traufe=(V_ or {}).get("z_traufe"), anschluss=(V_ or {}).get("z_anschluss"), hinweis="ANNAHME: " + "; ".join(ann) if ann else ""))
                continue
            if G_ and os.environ.get("MIT_KATALOG_GALERIE") == "1":      # Katalog-Galerie (Wand.galerie) nur noch auf Wunsch - Nutzer 21.11.: "nicht aus dem Baukasten"      # 21.11.2026: Masse gemessen (vorbauten_bauplan.galerie_messen), Gestalt = bewaehrtes Bauteil Wand.galerie wie schwab_v3
                WG = Wand(o, o + d, aussen=o + n); pf_ = G_["pfosten"]; z_fu = G_.get("z_fuss")
                teile.append(WG.galerie(G_["u0"], G_["u1"], G_["z_boden"], G_["z_holm"], G_["z_dach"] + 0.1, G_["w"], pfosten=pf_ if len(pf_) >= 2 else 3, streben=int(G_.get("streben") or 0),
                                        z_fuss=z_fu, tafeln=False, w_wand=G_["w_wand"]))
                V_ = G_.get("vordach")
                if V_:
                    ua, ub, dk = G_["u0"] - 0.1, G_["u1"] + 0.1, 0.15
                    teile.append(WG.huelle([(u, z, w) for u in (ua, ub) for z, w in ((V_["z_anschluss"], G_["w_wand"]), (V_["z_anschluss"] - dk, G_["w_wand"]), (V_["z_traufe"] + dk, V_["w_traufe"]), (V_["z_traufe"], V_["w_traufe"]))]))
                belege.append(dict(seite="wand", element=f"Galerie {F.get('id', '')} u {G_['u0']:.2f}..{G_['u1']:.2f} (Bruestung {G_['z_boden']:.2f}-{G_['z_holm']:.2f} m, {len(pf_)} Pfosten, {G_.get('streben')} Streben)" + (" mit Vordach" if V_ else ""),
                                   quelle="Masse aus Ebenen-Sweep + feinem Wandbild (tools/vorbauten_bauplan.py galerie_messen), Gestalt bauteile.Wand.galerie", ausladung=G_["w"], traufe=(V_ or {}).get("z_traufe"),
                                   streben_quelle=G_.get("streben_quelle"), hinweis="ANNAHME: Querschnitte (Pfosten/Riegel 0,22 m), Knaggen, Bodenplatte 0,35 m (Bauteil-Standard); " + ((V_ or {}).get("annahme") or "")))
                continue
            # NUR NOCH MIT_HOEHENFELD=1 (Vergleich/Rote Probe): Hoehenfeld als Gestalt = Treppenkloetze, verworfen 21.11. und 24.11. (Rueckfall 1122z-zc)
            W_ = np.round(np.array(g["w"], float) / stufe) * stufe; r_ = float(g["raster"]); nk = 0
            # 24.11.2026 (Nutzer: Handstand schwab_v3 war besser - Vordach dort GENEIGT, Kette 1122w-zc baute das Vordach als Hoehenfeld-Stufen/flachen Kasten):
            # hat die Gruppe ein Foto-Profil (tools/vordach_profil.py, jetzt auch ohne Kanten-Kasten gemessen), ersetzt das geneigte Walm-Vordach die Hoehenfeld-Zellen
            # oberhalb seiner Unterkante (z_t - Dachhaut); darunter (Galerie, Raehm) bleibt das gemessene Hoehenfeld. Ohne Profil: unveraendert (Guard).
            VPh_ = VPJ.get((F.get("id"), gi_)); z_vd = None
            if VPh_ and (G_ or {}).get("vordach") and VPh_["z_a"] > VPh_["z_t"] + 0.3 and VPh_["w_t"] > ww + 0.2:
                z_vd = float(VPh_["z_t"]) - 0.15
                teile.append(vordach_walm(Wand(o, o + d, aussen=o + n), VPh_["u0"], VPh_["u1"], ww, VPh_["w_t"], VPh_["z_t"], VPh_["z_a"], c=VPh_["c"], As=VPh_["As"], einbinden=einbinden + max(0.0, ww - wv_)))
                belege.append(dict(seite="wand", element=f"Vordach {F.get('id', '')} {VPh_['familie']} (c {VPh_['c']:+.1f}, Walm {VPh_['As']:.2f} m, Traufe w {VPh_['w_t']:.2f} z {VPh_['z_t']:.2f}, Anschluss z {VPh_['z_a']:.2f})",
                                   quelle=f"tools/vordach_profil.py: {len(VPh_.get('fotos', []))} Foto-Silhouetten; Grenzen {VPh_.get('kasten_quelle', 'kanten_mass.kasten')}",
                                   hinweis="ANNAHME: " + (VPh_.get("annahme") or "") + "; Hoehenfeld-Zellen ueber z %.2f durch das Walm-Vordach ersetzt" % z_vd))
            for r in range(W_.shape[0]):
                za, zb = g["z1"] - (r + 1) * r_, g["z1"] - r * r_; s = 0
                if z_vd is not None:
                    if za >= z_vd: continue
                    zb = min(zb, z_vd + 0.02)
                while s < W_.shape[1]:
                    e = s
                    while e + 1 < W_.shape[1] and W_[r, e + 1] == W_[r, s]: e += 1
                    if W_[r, s] >= min_w:
                        ua, ub = g["u0"] + s * r_, g["u0"] + (e + 1) * r_; wf = ww + float(W_[r, s])
                        teile.append(M.hull_points([P(u, z, w) for u in (ua, ub) for z in (za, zb) for w in (w0, wf)])); nk += 1
                    s = e + 1
            k_ = g["koerper"]; d_ = g.get("dach")
            belege.append(dict(seite="wand", element=f"Vorbau {F.get('id', '')} u {g['u0']:.2f}..{g['u1']:.2f} z {g['z0']:.2f}..{g['z1']:.2f}",
                               quelle="Ebenen-Sweep tools/fassade_tiefe.py -> tools/vorbauten_bauplan.py (Hoehenfeld je Zelle)", breite=round(g["u1"] - g["u0"], 2),
                               ausladung_front=k_["w_median"], dach_ausladung=d_["w_median"] if d_ else None, kaesten=nk,
                               hinweis="Gestalt = gemessene Tiefe je %.2f-m-Zelle (3x3-Median); Unterseite geschlossen (Konsolen/Streben nicht einzeln) = ANNAHME" % r_))
    if teile: koerper = koerper + M.batch_boolean(teile, OpType.Add)
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
    belege = []; z_massiv = None; kp_ = os.path.join(os.path.dirname(os.path.abspath(datei)), "schleife_korrekturen.json")
    for fid, F in json.load(open(datei)).items():
        for x in F.get("oeffnungen", []):
            if not x.get("gebaut"): continue
            # 24.11.2026 (Risiko a, wandlage_fotokanten): Tiefe tiefe_m ab der GESETZTEN Wand - sonst schnitt das f00-Tor (0,6 m) bei Wand -0,32 nur noch 0,28 m ins Mauerwerk
            o, wv_ = wand_gesetzt(kp_, F, z=(x.get("unten", 0.0), x["scheitel"])); W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float))
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
                               lichte_breite=x["breite"], kaempfer=x["kaempfer"], scheitel=x["scheitel"], tiefe=x["tiefe_m"], wandlage=round(wv_, 3),
                               hinweis="ERKENNUNG, am Bild oeffnungen_<id>.jpg pruefen; " + "; ".join(x.get("annahmen", [])) + (f"; Tiefe ab gesetzter Wand {wv_:+.2f} m" if wv_ else "")))
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
    dazwischen ist die Wand um 'tiefe' zurueckgesetzt und zwischen 'pfosten' Pfosten je Seite (Eckpfosten mitgezaehlt) offen; 'pfosten' als Liste = Zahl je Kante
    (Kante k = ecken[k] -> ecken[k+1], 24.11.2026: je Wand gezaehlt statt Mehrheit).
    Zu messen: z0, z1, Pfostenzahl (am Foto zaehlen); tiefe, Querschnitte = ANNAHME. Liefert den neuen Koerper."""
    m = np.mean(np.asarray(ecken, float), axis=0); zus = None; ab = None
    pl = list(pfosten) if isinstance(pfosten, (list, tuple)) and len(pfosten) == len(ecken) else [int(pfosten if np.isscalar(pfosten) else max(pfosten))] * len(ecken)
    for ki, (a_, b_) in enumerate(zip(ecken, list(ecken[1:]) + [ecken[0]])):
        pfosten_k = max(2, int(pl[ki]))
        mi = 0.5 * (np.asarray(a_, float) + np.asarray(b_, float)); W = Wand(a_, b_, aussen=tuple(2 * mi - m)); L = W.laenge
        c_ = W.kasten(-0.05, L + 0.05, z0 + riegel, z1 - riegel, -tiefe, vor + 0.3); ab = c_ if ab is None else ab + c_
        t_ = W.kasten(-vor, L + vor, z0, z0 + riegel, -0.3, vor) + W.kasten(-vor, L + vor, z1 - riegel, z1, -0.3, vor)
        for k_ in range(pfosten_k): u_ = k_ * (L - b) / (pfosten_k - 1); t_ = t_ + W.kasten(u_, u_ + b, z0 + riegel - 0.02, z1 - riegel + 0.02, -0.3, vor - 0.01)
        zus = t_ if zus is None else zus + t_
    return koerper - ab + zus


def eckquader_aus_relief(rel, px, z0, putz_niveau, ecke_links, ecke_rechts, streifen=1.5, innen_ab=2.0, schwelle=0.01, min_hoehe=3.0):
    """ECKQUADERUNG im gebauten Steinrelief erkennen (GENERISCH, 21.11.2026; Grundsatz WANDBILD = BAUPLAN - die Quader SIND schon das Fotorelief von steine_aus_foto.py,
    hier wird nur benannt, was davon an einer Gebaeudeecke steht). rel: Reliefbild (Zeile 0 = oben, Spalte 0 = Wandanfang), px m/Zelle, z0 = Unterkante,
    putz_niveau = Hoehe des glatten Putzes. Stein = |rel - putz_niveau| > schwelle, Anteil je Zelle im 0,5-m-Fenster gemittelt.
    Je Wandende, das eine Gebaeudeecke ist (ecke_links/ecke_rechts): Zeilen, in denen der Randstreifen (streifen m) ueberwiegend Stein ist (>= 50 %) und das
    Wandinnere (ab innen_ab m vom Rand) ueberwiegend Putz (<= 25 %) = Eckquaderzone. Verzahnung: Steinbreite ab der Ecke je Zeile, Wechsel lang/kurz = Quaderlagen.
    Liefert Liste dict(ende, z0, z1, hoehe, lagen, breite_lang, breite_kurz) - nur Zonen >= min_hoehe m."""
    def blur(a, ky, kx):                                     # Mittelwertfenster ky x kx (nur numpy: im Generator-venv ist OpenCV nicht ladbar)
        a = np.asarray(a, np.float64)
        for ax, k_ in ((0, ky), (1, kx)):
            if k_ <= 1: continue
            p_ = np.pad(a, [(k_ // 2, k_ - 1 - k_ // 2) if q == ax else (0, 0) for q in range(2)], mode='edge'); c_ = np.cumsum(p_, axis=ax)
            c_ = np.concatenate([np.zeros_like(np.take(c_, [0], axis=ax)), c_], axis=ax); a = (np.take(c_, range(k_, c_.shape[ax]), axis=ax) - np.take(c_, range(0, c_.shape[ax] - k_), axis=ax)) / k_
        return a
    rel = np.asarray(rel, np.float32); h, w = rel.shape
    if w * px < innen_ab + 0.5: return []
    st = (np.abs(rel - putz_niveau) > schwelle).astype(np.float32)
    k = max(3, int(0.5 / px) | 1); stg = blur(st, k, k)
    ns, ni = int(streifen / px), int(innen_ab / px); erg = []
    for ende, ok in (("anfang", ecke_links), ("ende", ecke_rechts)):
        if not ok: continue
        s_ = stg[:, :ns] if ende == "anfang" else stg[:, w - ns:][:, ::-1]          # Spalte 0 = Ecke
        i_ = stg[:, ni:] if ende == "anfang" else stg[:, :w - ni]
        zeile = (s_.mean(1) >= 0.5) & (i_.mean(1) <= 0.25)
        lz = int(1.0 / px); zi = np.flatnonzero(zeile)
        for a_, b_ in zip(zi[:-1], zi[1:]):                          # Luecken < 1 m schliessen
            if 1 < b_ - a_ <= lz: zeile[a_:b_] = True
        j = 0
        while j < h:
            if not zeile[j]: j += 1; continue
            e = j
            while e < h and zeile[e]: e += 1
            if (e - j) * px >= min_hoehe:
                roh = st[j:e, :ns * 2] if ende == "anfang" else st[j:e, w - 2 * ns:][:, ::-1]
                roh = blur(roh, max(3, int(0.3 / px) | 1), max(3, int(0.3 / px) | 1))
                breite = np.array([(np.argmin(r_ >= 0.5) if (r_ < 0.5).any() else len(r_)) * px for r_ in roh])     # Steinbreite ab der Ecke je Zeile
                b_lang, b_kurz = float(np.percentile(breite, 80)), float(np.percentile(breite, 20)); mitte = 0.5 * (b_lang + b_kurz)
                lagen = int(np.count_nonzero(np.diff((breite > mitte).astype(int)) != 0)) + 1 if b_lang - b_kurz >= 0.15 else 0
                erg.append(dict(ende=ende, z0=round(z0 + (h - e) * px, 2), z1=round(z0 + (h - j) * px, 2), hoehe=round((e - j) * px, 2), lagen=lagen,
                                breite_lang=round(b_lang, 2), breite_kurz=round(b_kurz, 2)))
            j = e
    return erg


def ecken_gesetzt(ecken, korrekturen_json, z=None):
    """Umlauf-Ecken (x, y) eines Bauteils rund um den Koerper (Umgang) auf die GESETZTEN Wandlagen (wandversatz_fassade je Kante, im Hoehenbereich z) verschieben:
    jede Kante parallel um ihren Versatz, neue Ecke = Schnitt der Nachbarkanten (parallele Nachbarn: verschobener Punkt). 24.11.2026 (Risiko b, wandlage_fotokanten:
    Umgang stand 0,32 m vor der zurueckgesetzten Wand). Liefert (ecken_neu, versatz je Kante)."""
    E = np.asarray(ecken, float)[:, :2]; m = E.mean(0); L = []; wvs = []
    for i in range(len(E)):
        a_, b_ = E[i], E[(i + 1) % len(E)]; t_ = (b_ - a_) / np.linalg.norm(b_ - a_); n_ = np.array([t_[1], -t_[0]])
        if (0.5 * (a_ + b_) - m) @ n_ < 0: n_ = -n_
        wv = wandversatz_fassade(korrekturen_json, 0.5 * (a_ + b_), n_, z=z); wvs.append(round(wv, 3)); L.append((a_ + wv * n_, t_))
    neu = []
    for i in range(len(E)):
        (p1, t1), (p2, t2) = L[i - 1], L[i]; A_ = np.array([t1, -t2]).T
        if abs(np.linalg.det(A_)) < 1e-6: neu.append(p2); continue
        s_ = np.linalg.solve(A_, p2 - p1)[0]; neu.append(p1 + s_ * t1)
    return [tuple(float(c) for c in q) for q in neu], wvs


def umgang_aus_json(koerper, datei, tiefe=0.9):
    """Offener Umgang aus der Kettenstufe 'bauplan' (tools/umgang_aus_fotos.py -> audit/umgang_auto.json: z0, z1, pfosten_je_seite, ecken). Baut nur bei gefunden=true.
    Schwelle/Raehm hoechstens 1/5 der Zonenhoehe (ANNAHME Querschnitt), Ruecksprung 'tiefe' = ANNAHME. VOR aushoehlen aufrufen (die Hohlraumschale folgt dem Ruecksprung).
    Liefert (koerper, belege)."""
    import json, os
    if not os.path.exists(datei): return koerper, []
    J = json.load(open(datei))
    if not J.get("gefunden"):
        return koerper, [dict(seite="wand", element="Laufgang unter der Traufe NICHT gebaut", quelle="bauteile.umgang_aus_json; " + os.path.basename(datei), hinweis=str(J.get("grund", ""))[:200])]
    z0, z1, p = float(J["z0"]), float(J["z1"]), int(J["pfosten_je_seite"]); h = z1 - z0
    if h < 0.5 or p < 2 or len(J.get("ecken") or []) < 3:
        return koerper, [dict(seite="wand", element="Laufgang unter der Traufe NICHT gebaut", quelle="bauteile.umgang_aus_json", hinweis="Zone %.2f m / %d Pfosten / Ecken ungueltig" % (h, p))]
    ri = min(0.25, 0.2 * h)
    ecken, wvs = ecken_gesetzt(J["ecken"], os.path.join(os.path.dirname(os.path.abspath(datei)), "schleife_korrekturen.json"), z=(z0, z1))
    pk = J.get("pfosten_kanten"); pk = [int(x) for x in pk] if isinstance(pk, list) and len(pk) == len(ecken) and all(int(x) >= 2 for x in pk) else p   # je Kante (24.11.2026), alt: Mehrheit
    koerper = umgang(koerper, [tuple(e) for e in ecken], z0, z1, tiefe=tiefe, pfosten=pk, riegel=ri)
    if any(wvs): J.setdefault("annahmen", []).append("Ecken auf gesetzte Wandlage verschoben (Kanten %s m, bauteile.ecken_gesetzt)" % ", ".join("%+.2f" % w_ for w_ in wvs))
    wz = "; ".join("%s: %s Pfosten, innen u %s (%d Fotos)" % (w["id"], w["pfosten"], w.get("pfosten_u_konsens"), w.get("pfosten_fotos", 0)) for w in J.get("waende", []) if w.get("pfosten"))
    return koerper, [dict(seite="wand", element="Umgang unter der Traufe (offener Laufgang, Pfosten je Seite %s)" % (pk if isinstance(pk, list) else p), quelle="Kettenstufe bauplan: tools/umgang_aus_fotos.py (%d Fotos, Zone aus Bildkanten, Pfosten gezaehlt) -> bauteile.umgang" % J.get("fotos_gut", 0),
                          umgang_z0=z0, umgang_z1=z1, pfosten_je_seite=p, hinweis="ANNAHME: Ruecksprung %.2f m, Schwelle/Raehm %.2f m, Pfosten 0,24 m; %s; " % (tiefe, ri, wz) + "; ".join(J.get("annahmen", [])))]


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
        # 24.11.2026 (Risiko b, wandlage_fotokanten): Pfeilertiefe ab der GESETZTEN Aussenwand; die Innenwandebene w_iw bleibt absolut (gemessen) und wird gegen die neue Wand gerechnet
        o, _ = wand_gesetzt(os.path.join(os.path.dirname(os.path.abspath(datei)), "schleife_korrekturen.json"), F, z=tuple(float(x) for x in iw["z"]) if iw.get("z") else None)
        W = Wand(o, o + np.array(F["d"], float), aussen=o + np.array(F["n"], float)); s = -1.0 if W.spiegel else 1.0
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


def _zahl(v):
    """float oder None (fehlend, nicht endlich, kein Zahlwert)."""
    try: v = float(v)
    except (TypeError, ValueError): return None
    return v if math.isfinite(v) else None


def _cs(pts):
    """CrossSection aus einem einfachen Polygon, Umlaufsinn egal (gegen den Uhrzeigersinn gedreht, sonst waere es unter FillRule Positive leer)."""
    p = np.asarray(pts, float); fl = 0.5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1])
    return CrossSection([(p if fl > 0 else p[::-1]).tolist()])


def _laengs(cs, x0, x1):
    """Querschnitt (y, z) von x0 bis x1 entlang +x ziehen (Drehmatrix, det +1)."""
    return M.extrude(cs, x1 - x0).transform([[0.0, 0.0, 1.0, x0], [1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]])


def _quer(cs, breite):
    """Profil (x, z) quer ueber die Breite ziehen, mittig um y = 0 (Drehmatrix, det +1)."""
    return M.extrude(cs, breite).transform([[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, breite / 2], [0.0, 1.0, 0.0, 0.0]])


def treppen_profil(x0, z0, n, s, a, platte, richtung=1.0, rampe=False, hinten=0.02, podest=None, unterlage=0.02, anker="fuss", fuge=0.0):
    """Treppenlauf-Profil (x, z) als CrossSection (GENERISCH, 26.11.2026): n Stufen, Steigung s, Auftritt a, steigend in Richtung richtung (+1 = +x, -1 = -x).
    anker "fuss": (x0, z0) = Fuss des Laufs (Antritt); "kopf": (x0, z0) = Austritt oben (Oberkante der obersten Stufe, exakt z0 - kein Rundungsversatz
    gegen einen Anschlussboden auf z0). Freier Lauf (podest None): Unterseite eine Gerade parallel zum Lauf, senkrecht 'platte' dick; die oberste Stufe reicht
    'hinten' ueber das Laufende (Ueberlappung in den Anschluss, nie nur flaechengleich). Mit podest: aufliegender Lauf (Innentreppe) - Unterseite waagrecht
    'unterlage' unter dem Fuss (greift in den Boden), oben ein Boden der Laenge 'podest' auf Fuss + n s. rampe=True: schiefe Ebene statt Stufen.
    fuge > 0 (freier Lauf): die Ueberlappung 'hinten' liegt 'fuge' tiefer und beginnt 'fuge' vor dem Laufende - eine oberste Stufe flaechengleich mit einem
    Anschlussboden, die die Anschlussflaeche kreuzt, gab doppelte Eckpunkte (trimesh nicht wasserdicht, Test 26.11.); 5 mm = 0,06 mm im Druck, unter der Duese."""
    H = n * s; lauf = n * a; dv = platte / math.cos(math.atan2(s, a))
    oben = [(0.0, 0.0)]
    if rampe: oben.append((lauf, H))
    else:
        for i in range(n): oben += [(i * a, (i + 1) * s), ((i + 1) * a, (i + 1) * s)]
    ende = lauf + (podest if podest is not None else hinten)
    oben += [(lauf - fuge, H), (lauf - fuge, H - fuge), (ende, H - fuge)] if (fuge > 0 and podest is None) else [(ende, H)]
    unten = [(ende, -unterlage), (0.0, -unterlage)] if podest is not None else [(ende, H - dv + (ende - lauf) * s / a), (0.0, -dv)]
    q = []
    for x, z in oben + unten:
        if not q or abs(x - q[-1][0]) > 1e-12 or abs(z - q[-1][1]) > 1e-12: q.append((x, z))
    if abs(q[0][0] - q[-1][0]) < 1e-12 and abs(q[0][1] - q[-1][1]) < 1e-12: q.pop()
    if anker == "kopf": return _cs([(x0 + richtung * (x - lauf), z0 + (z - H)) for x, z in q])
    return _cs([(x0 + richtung * x, z0 + z) for x, z in q])


def ueberdachter_gang(P, massstab=None, min_mm=None):
    """UEBERDACHTER GANG MIT TREPPE (Bruecke ueber eine Strasse zwischen zwei Baukoerpern; GENERISCH, 26.11.2026, SPEC_SCHWABENTOR_DEMONSTRATOR Anf. 4).
    Alle Masse aus dem dict P (JSON, Meter, Modellmassstab 1:1) - keine Objektmasse im Code:
      spannweite            lichter Abstand der beiden Anschlussfassaden (oder achse {a: [x, y], b: [x, y]} im Modellrahmen; beide angegeben -> muessen
                            auf 'toleranz' (Vorgabe 0,05 m) uebereinstimmen, sonst NICHT gebaut - Quellen nicht mitteln)
      breite                Aussenbreite der Seitenwaende;  z_boden  Oberkante Laufboden am Ende a (bzw. am Fuss einer Innentreppe);  hoehe  lichte Hoehe Boden -> Traufe innen
      boden_dicke, wand_dicke   (Vorgabe = Druck-Mindestmass);  einbinden  Ueberlappung in die Baukoerper je Ende (Vorgabe 0,10 m, ANNAHME)
      dach    {form: flach|pult|sattel, neigung_grad, ueberstand (seitlich), dicke}; sattel = First laengs ueber der Gangmitte, pult = hohe Seite auf +y (links der Achse a->b)
      seiten  {art: geschlossen|offen, bruestung, pfosten (Anzahl inkl. Endpfosten), pfosten_breite, riegel (Wandband unter dem Dach)}
      treppe  {lage: innen|aussen, ende: a|b, stufen, steigung (oder hub), auftritt und/oder lauflaenge, breite, platte}
              innen: Lauf steigt vom Ende aus in den Gang, danach Boden auf z_boden + stufen x steigung (zwei Baukoerper mit verschiedener Geschosshoehe);
              aussen: Lauf vor dem Gangende, abwaerts weg vom Gang bis z_boden - stufen x steigung (Abgang zur Strasse).
    Lokaler Rahmen: x laengs (0 = Fassade a, spannweite = Fassade b), y quer (Mitte 0), z absolut; mit achse in den Modellrahmen gedreht/verschoben.
    GUARD (parametrisch gueltig, nie degeneriert): Dicken < MINMM x SCALE (0,8 mm bei 1:87) -> angehoben (Beleg); unbekannte Dachform / Neigung ausserhalb 0..75 Grad
    -> Flachdach; Treppe widerspruechlich, laenger als der Gang oder bis ans Dach -> Gang ohne Treppe; Stufe unter dem Mindestmass -> Rampe; kein Laufraum
    (breite < 2 wand + Mindestmass) -> massiver Steg; Endkontrolle ein Koerper, sonst Fallback (erst ohne Oeffnungen, dann ohne Treppe).
    Liefert (Manifold oder None, belege, masse) - masse = tatsaechlich gebaute Werte (fuer Tests/Abnahme)."""
    massstab = float(massstab if massstab is not None else os.environ.get("SCALE", "87")); min_mm = float(min_mm if min_mm is not None else os.environ.get("MINMM", "0.8"))
    dmin = min_mm * massstab / 1000.0; quelle = "bauteile.ueberdachter_gang; " + str(P.get("quelle", "JSON-Parameter"))
    def nicht(grund):
        return None, [dict(seite="bruecke", element="Ueberdachter Gang nicht gebaut", quelle=quelle, hinweis=grund)], dict(art="nicht gebaut", grund=grund, rot=[dict(bauteil="bruecke", grund=grund)])
    # ---- Spannweite / Achse
    L = _zahl(P.get("spannweite")); A = P.get("achse"); T = None
    if A:
        try: pa = np.array(A["a"][:2], float); pb = np.array(A["b"][:2], float)
        except (KeyError, TypeError, ValueError): return nicht("achse unlesbar (erwartet {a: [x, y], b: [x, y]})")
        La = float(np.linalg.norm(pb - pa))
        if not math.isfinite(La) or La <= dmin: return nicht(f"achse a->b zu kurz ({La:.3f} m)")
        tol = _zahl(P.get("toleranz")); tol = 0.05 if tol is None else tol
        if L is not None and abs(L - La) > tol: return nicht(f"spannweite {L:.3f} m widerspricht der Achse a->b {La:.3f} m (> {tol} m) - Quellen nicht mitteln, Mass klaeren")
        L = La; c, s_ = (pb - pa) / La; T = [[c, -s_, 0.0, pa[0]], [s_, c, 0.0, pa[1]], [0.0, 0.0, 1.0, 0.0]]
    if L is None: return nicht("spannweite fehlt (weder 'spannweite' noch 'achse')")
    B, zb, h = _zahl(P.get("breite")), _zahl(P.get("z_boden")), _zahl(P.get("hoehe"))
    if None in (B, zb, h) or L <= dmin or B <= dmin or h <= 0: return nicht(f"Grundmass fehlt/ungueltig: spannweite {L}, breite {B}, z_boden {zb}, hoehe {h}")
    hinw = []; rot = []                       # rot: (bauteil, grund) fuer jede Ersatzform/fehlende Messung -> Bestand-Tor ROT (bruecke_tor)
    def ersatz(bauteil, grund): hinw.append(grund); rot.append(dict(bauteil=bauteil, grund=grund))
    for f_ in P.get("fehlt", []) or []: rot.append(dict(bauteil=str(f_.get("bauteil", f_)) if isinstance(f_, dict) else str(f_), grund=str(f_.get("grund", "Messung fehlt")) if isinstance(f_, dict) else "Messung fehlt"))
    def mind(name, v):
        v = dmin if v is None else v
        if v < dmin - 1e-12:
            hinw.append(f"{name} {v:.3f} m < Druck-Mindestmass {dmin:.4f} m ({min_mm:g} mm bei 1:{massstab:g}) -> angehoben"); return dmin
        return v
    t = mind("wand_dicke", _zahl(P.get("wand_dicke"))); db = mind("boden_dicke", _zahl(P.get("boden_dicke")))
    e = _zahl(P.get("einbinden")); e = 0.10 if e is None or e < 0 else e
    # ---- Dach
    D = P.get("dach") or {}; form = str(D.get("form", "flach")).lower(); al = _zahl(D.get("neigung_grad")); u = max(_zahl(D.get("ueberstand")) or 0.0, 0.0)
    dd = mind("dach.dicke", _zahl(D.get("dicke")))
    if form not in ("flach", "pult", "sattel"): ersatz("dach", f"Dachform '{form}' unbekannt -> Flachdach (Fallback)"); form = "flach"
    if form != "flach" and (al is None or not 0.0 < al < 75.0): ersatz("dach", f"Dachneigung {al} Grad ungueltig (0..75) -> Flachdach (Fallback)"); form = "flach"
    ta = math.tan(math.radians(al)) if form != "flach" else 0.0; dv = dd / math.cos(math.atan(ta))
    massiv = B < 2 * t + dmin or h < dmin; art = "massiver Steg" if massiv else "gang"
    if massiv: ersatz("gang", f"kein Laufraum (breite {B:.3f} < 2 x wand {t:.3f} + {dmin:.3f} oder hoehe {h:.3f} < {dmin:.3f}) -> massiver Steg (Fallback)")
    zt = zb + h; yi = B / 2 if massiv else B / 2 - t; Y = B / 2 + u; zbot = zb - db
    unter = {"flach": lambda y: zt, "sattel": lambda y: zt + (yi - abs(y)) * ta, "pult": lambda y: zt + (y + yi) * ta}[form]
    ys = [-Y, 0.0, Y] if form == "sattel" else [-Y, Y]
    dach = _cs([(y, unter(y)) for y in ys] + [(y, unter(y) + dv) for y in ys[::-1]])
    yb = [-B / 2, 0.0, B / 2] if form == "sattel" else [-B / 2, B / 2]
    unter_dach = _cs([(-B / 2, zbot), (B / 2, zbot)] + [(y, unter(y) + dv / 2) for y in yb[::-1]])     # Wandkopf in Dachmitte: nie auf der Dachkante (doppelte Eckpunkte)
    hoch = zt + B * (ta + 1.0) + dv + 1.0
    if massiv: kern = CrossSection.square([B, hoch - zbot]).translate((-B / 2, zbot)) ^ unter_dach
    else:
        waende = CrossSection.square([t, hoch - zbot]).translate((-B / 2, zbot)) + CrossSection.square([t, hoch - zbot]).translate((B / 2 - t, zbot))
        kern = (waende ^ unter_dach) + CrossSection.square([B, db]).translate((-B / 2, zbot))
    rumpf = _laengs(kern + dach, -e, L + e)
    ms = dict(art=art, spannweite=L, breite=B, hoehe=h, wand_dicke=t, boden_dicke=db, dach=form, dach_dicke=dd, einbinden=e, treppe="keine", oeffnungen=0, fallback=[], rot=rot)
    # ---- Treppe
    TP = P.get("treppe"); treppe = None; boden_bei = lambda x: zb; tbeleg = None
    if TP:
        lage = str(TP.get("lage", "")).lower(); ende = str(TP.get("ende", "a")).lower(); n_ = _zahl(TP.get("stufen"))
        s, a, lauf, hub = _zahl(TP.get("steigung")), _zahl(TP.get("auftritt")), _zahl(TP.get("lauflaenge")), _zahl(TP.get("hub"))
        grund = None
        if lage not in ("innen", "aussen") or ende not in ("a", "b"): grund = f"lage '{lage}' / ende '{ende}' ungueltig (innen|aussen, a|b)"
        elif n_ is None or n_ < 1 or abs(n_ - round(n_)) > 1e-9: grund = f"stufen {TP.get('stufen')} ist keine ganze Zahl >= 1"
        else:
            n = int(round(n_))
            if s is not None and hub is not None and abs(n * s - hub) > 0.01: grund = f"steigung x stufen {n * s:.3f} m widerspricht hub {hub:.3f} m"
            elif a is not None and lauf is not None and abs(n * a - lauf) > 0.01: grund = f"auftritt x stufen {n * a:.3f} m widerspricht lauflaenge {lauf:.3f} m"
            s = s if s is not None else (hub / n if hub is not None else None); a = a if a is not None else (lauf / n if lauf is not None else None)
            if grund is None and (s is None or a is None): grund = "steigung (oder hub) und auftritt (oder lauflaenge) noetig"
            elif grund is None and (s <= 0 or a <= 0): grund = f"steigung {s} / auftritt {a} muessen > 0 sein"
        if grund is None:
            H = n * s; lauf = n * a; platte = mind("treppe.platte", _zahl(TP.get("platte")))
            rampe = min(s, a) < dmin
            if rampe: ersatz("treppe", f"Stufe {s:.3f} x {a:.3f} m unter dem Druck-Mindestmass {dmin:.4f} m -> Rampe statt Stufen (Fallback)")
            wb = _zahl(TP.get("breite"))
            if lage == "innen":
                if massiv: grund = "kein Laufraum (massiver Steg) - Innentreppe nicht moeglich"
                elif lauf + max(0.01 - e, 0.0) > L + e - 0.01 + 1e-9: grund = f"Lauf {lauf:.3f} m laenger als der Gang {L:.3f} m"
                elif zb + H + dmin > zt: grund = f"Treppe stoesst ans Dach: oberer Boden z {zb + H:.3f} + {dmin:.3f} > Traufe innen z {zt:.3f}"
                else:
                    wi = B - 2 * t; wb = wi if wb is None or wb > wi else max(wb, dmin); wb = wb + (0.04 if wb >= wi else 0.0)   # volle Breite greift 2 cm in die Waende
                    # Antritt an der Fassade; ohne Einbinden 1 cm nach innen (Antritt flaechengleich mit dem Gangende gab doppelte Eckpunkte, Zufallsprobe 26.11.)
                    ve = max(0.01 - e, 0.0); r = 1.0 if ende == "a" else -1.0; x0 = ve if ende == "a" else L - ve
                    # oberer Boden endet 1 cm vor dem Gangende: buendige Endflaeche gab doppelte Eckpunkte (trimesh nicht wasserdicht, Test 26.11.)
                    treppe = _quer(treppen_profil(x0, zb, n, s, a, platte, r, rampe, podest=max(L + e - 0.01 - ve - lauf, 0.0)), wb)
                    def boden_bei(x, r=r, x0=x0):
                        d_ = (x - x0) * r
                        if d_ <= 0: return zb
                        if d_ >= lauf: return zb + H
                        return zb + (H * d_ / lauf if rampe else s * (math.floor(d_ / a) + 1))
            else:
                wb = B - 0.02 if wb is None or wb > B - 0.02 else max(wb, dmin); r = 1.0 if ende == "a" else -1.0; x0 = -e if ende == "a" else L + e   # Breite 1 cm innerhalb der Wandflucht (nie flaechengleich)
                treppe = _quer(treppen_profil(x0, zb, n, s, a, platte, r, rampe, hinten=0.02, anker="kopf", fuge=0.005), wb)
        if grund is None:
            ms.update(treppe="rampe" if rampe else "gebaut", stufen=n, steigung=s, auftritt=a, lauflaenge=lauf, hub=H, treppe_lage=lage, treppe_ende=ende,
                      kopfhoehe=(zt - zb - H) if lage == "innen" else None)
            tbeleg = dict(seite="bruecke", element=f"Treppe {lage} am Ende {ende}: {n} Stufen {s:.3f} x {a:.3f} m, Lauf {lauf:.3f} m, Hub {H:.3f} m" + (" (als Rampe)" if rampe else ""),
                          quelle=quelle, hinweis=f"Schrittmass 2 s + a = {2 * s + a:.3f} m; Laufplatte {platte:.3f} m")
        else:
            ms.update(treppe="nicht gebaut", treppe_grund=grund); ersatz("treppe", "Treppe NICHT gebaut: " + grund)
    # ---- Seiten offen: Felder zwischen Pfosten
    S = P.get("seiten") or {}; felder = []
    if str(S.get("art", "geschlossen")).lower() == "offen" and not massiv:
        np_, br = _zahl(S.get("pfosten")), _zahl(S.get("bruestung"))
        if np_ is None or np_ < 2 or abs(np_ - round(np_)) > 1e-9 or br is None or br < 0: ersatz("seiten", f"seiten offen ungueltig (pfosten {S.get('pfosten')}, bruestung {S.get('bruestung')}) -> geschlossen (Fallback)")
        else:
            bp = mind("seiten.pfosten_breite", _zahl(S.get("pfosten_breite"))); ri = mind("seiten.riegel", _zahl(S.get("riegel")))
            z1 = min(unter(-B / 2), unter(B / 2)) - ri; cs_ = np.linspace(bp / 2, L - bp / 2, int(round(np_)))
            pl = S.get("pfosten_lagen")                                   # gemessene Lagen laengs (m ab Ende a), sonst gleichmaessig zwischen den Enden
            if pl:
                pl = np.clip(np.sort(np.asarray(pl, float)), bp / 2, L - bp / 2)
                if len(pl) != int(round(np_)): ersatz("seiten", f"pfosten_lagen ({len(pl)}) widerspricht pfosten ({int(round(np_))}) - gleichmaessig verteilt")
                else: cs_ = pl
            for c0, c1 in zip(cs_[:-1], cs_[1:]):
                xa, xb = c0 + bp / 2, c1 - bp / 2; z0 = max(boden_bei(xa), boden_bei(xb)) + br
                if xb - xa >= dmin and z1 - z0 >= dmin: felder.append(M.cube([xb - xa, B + 0.02, z1 - z0]).translate((xa, -B / 2 - 0.01, z0)))
            if len(felder) < len(cs_) - 1: ersatz("seiten", f"{len(cs_) - 1 - len(felder)} Seitenfeld(er) kleiner als das Mindestmass - geschlossen gelassen")
    # ---- Stuetzen unter dem Boden (27.11.2026): stuetzen {lagen: [[x, y], ...] im lokalen Rahmen, breite, z_fuss}; jede reicht 1 cm in den Boden
    ST = P.get("stuetzen")
    if ST and ST.get("keine"): ms["stuetzen_keine_belegt"] = bool(ST.get("beleg"))      # "keine Stuetzen" nur mit Fotobeleg (Zaehlprotokoll) gruen
    elif ST:
        bs, zf = _zahl(ST.get("breite")), _zahl(ST.get("z_fuss")); lg = ST.get("lagen") or []
        if bs is None or zf is None or not lg or zf >= zbot - dmin: ersatz("stuetzen", f"stuetzen ungueltig (breite {bs}, z_fuss {zf}, {len(lg)} Lagen, Boden-Unterkante {zbot:.3f}) - nicht gebaut")
        else:
            bs = mind("stuetzen.breite", bs); sts = [M.cube([bs, bs, zbot + 0.01 - zf]).translate((float(x) - bs / 2, float(y) - bs / 2, zf)) for x, y in lg]
            rumpf = rumpf + M.batch_boolean(sts, OpType.Add); ms.update(stuetzen=len(sts))
    # ---- Zusammenbau mit Endkontrolle (ein Koerper, wasserdicht) und Fallback
    def gut(m): return (m is not None and not m.is_empty() and str(m.status()).endswith("NoError") and m.volume() > 0 and len(m.decompose()) == 1
                        and als_trimesh(m).is_watertight)          # STL-Export: auch nach dem Verschmelzen gleicher Eckpunkte wasserdicht
    def bauen(mit_treppe, mit_feldern):
        m = rumpf + treppe if (mit_treppe and treppe is not None) else rumpf
        if mit_feldern and felder: m = m - M.batch_boolean(felder, OpType.Add)
        return m
    g = None
    for mt, mf, fb in ((True, True, None), (True, False, "ohne Seitenfelder"), (False, False, "ohne Treppe und Seitenfelder")):
        g = bauen(mt, mf)
        if gut(g):
            if fb: ms["fallback"].append(fb); ersatz("seiten" if mt else "treppe", f"Endkontrolle: erst {fb} ein Koerper (Fallback)")
            if not mt and treppe is not None: ms.update(treppe="nicht gebaut", treppe_grund="Endkontrolle"); tbeleg = None
            if mf: ms["oeffnungen"] = len(felder)
            break
        g = None
    if g is None: return nicht("Endkontrolle: kein einzelner wasserdichter Koerper (auch Fallback nicht)")
    if T is not None: g = g.transform(T)
    belege = [dict(seite="bruecke", element=f"Ueberdachter Gang ({art}): Spannweite {L:.3f} m, Breite {B:.3f} m, lichte Hoehe {h:.3f} m, Dach {form}"
                   + (f" {al:g} Grad" if form != "flach" else "") + (f", {len(felder)} offene Seitenfelder" if ms["oeffnungen"] else ""),
                   quelle=quelle, hinweis="; ".join(hinw) if hinw else "alle Masse aus den Parametern")]
    if tbeleg: belege.append(tbeleg)
    return g, belege, ms


def ueberdachter_gang_aus_json(koerper, datei, massstab=None, min_mm=None):
    """Gang(e) aus einer JSON-Datei: {"gang": {...}} oder {"gaenge": [{...}, ...]} oder direkt das Parameter-dict (Schluessel siehe ueberdachter_gang).
    koerper None -> nur die Gaenge. Liefert (koerper, belege)."""
    J = json.load(open(datei)); liste = J.get("gaenge") or ([J["gang"]] if "gang" in J else [J]); belege = []
    for P in liste:
        g, b, _ = ueberdachter_gang(P, massstab, min_mm); belege += b
        if g is not None: koerper = g if koerper is None else koerper + g
    return koerper, belege


def bruecke_tor(masse, pflicht=("dach", "seiten", "treppe", "stuetzen")):
    """Tor fuer den Brueckenbaustein (27.11.2026, PLAN_HANDMODELL_IN_KETTE §3 'kein stiller Kasten-Fallback'): ROT, sobald ein Bauteil per Ersatzform gebaut,
    nicht gebaut oder in der Massliste als 'fehlt' markiert ist; jeder Eintrag nennt den Bauteilnamen. pflicht: Bauteile, deren Fehlen ROT ist, auch wenn der
    Parameterblock ganz fehlt (fehlt 'treppe' im JSON -> ROT 'treppe: kein Parameterblock'). Liefert dict(status, rot=[...])."""
    rot = list(masse.get("rot", []))
    if masse.get("art") == "nicht gebaut" and not any(r["bauteil"] == "bruecke" for r in rot): rot.append(dict(bauteil="bruecke", grund=masse.get("grund", "nicht gebaut")))
    if masse.get("art") == "massiver Steg" and not any(r["bauteil"] == "gang" for r in rot): rot.append(dict(bauteil="gang", grund="massiver Steg (Ersatzform)"))
    if "treppe" in pflicht and masse.get("treppe") in ("keine", None) and not any(r["bauteil"] == "treppe" for r in rot) and masse.get("art") != "nicht gebaut":
        rot.append(dict(bauteil="treppe", grund="kein Parameterblock 'treppe' (Treppe nicht gemessen)"))
    if "stuetzen" in pflicht and not masse.get("stuetzen") and not any(r["bauteil"] == "stuetzen" for r in rot) and masse.get("art") != "nicht gebaut" and not masse.get("stuetzen_keine_belegt"):
        rot.append(dict(bauteil="stuetzen", grund="keine Stuetzen gebaut und 'keine Stuetzen' nicht am Foto belegt"))
    return dict(status="ROT" if rot else "GRUEN", rot=rot)


def als_trimesh(m):
    """Manifold -> trimesh.Trimesh (Export/Abnahme)."""
    import trimesh
    me = m.to_mesh(); return trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts), process=True)


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
    cuts = [W.kasten(u0, u1, z0, z1, wr - d - 0.25, wr + 0.002) for W, u0, u1, z0, z1, wr, *_ in fenster] + list(schnitte)
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
        t_f = float(f[6].get("tiefe", 0.0)) if len(f) > 6 and isinstance(f[6], dict) else None   # 21.11.2026: Laibung dieses Fensters AB WANDEBENE w = 0 (fenster_aus_json: Nische + Fenster)
        t_ = max(tiefe, t_f or 0.0)
        w0 = min(w_bereich[0], -(t_ + d + 0.3))                           # gemessene Laibung 0,85 m (Schwabentor f00): Profil muss bis hinter die Rueckwandplatte reichen
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
        ziel = vorn - tiefe if t_f is None else min(vorn - tiefe, -t_f)       # gemessene Laibung absolut (vorn liegt bei einer Nische schon auf deren Grund - nicht doppelt zaehlen)
        wp = ziel if tiefst is None else min(ziel, tiefst - schritt / 2 - 0.01)
        ring = Q.offset(d, JoinType.Miter) - Q; h_ = 0.5 * (sv + sh) - (wp - d)
        if not h_ > 0: info.append(dict(e, fehlt="Kragenhoehe %.3f <= 0 (Platte vor der Wandschale: vorn %.2f, Schale %.2f..%.2f, Platte %.2f)" % (h_, vorn, sh, sv, wp))); continue   # 24.11.2026 (1122u): sonst InvalidConstruction -> ganzer Koerper leer
        k_ = M.extrude(ring, h_).translate((0, 0, wp - d)) + M.extrude(Q, d).translate((0, 0, wp - d))
        k_ = k_.transform(W.matrix(0))
        if k_.status() != k_.status().__class__.NoError or k_.num_tri() == 0: info.append(dict(e, fehlt="Rueckwand ungueltig (%s)" % k_.status())); continue
        zus = k_ if zus is None else zus + k_
        info.append(dict(e, vorn=round(vorn, 3), schale=[round(sh, 3), round(sv, 3)], tiefe_ist=round(vorn - wp, 3), flaeche_m2=round(float(Q.area()), 3), erkannt=k, nur_feld=bool(nur)))
    if zus is None: return koerper, info
    neu = koerper + zus
    if neu.num_tri() == 0 or neu.status() != neu.status().__class__.NoError:   # 24.11.2026: nie einen leeren Koerper zurueckgeben (1122u: STL 84 Byte, Kette meldete rc 0)
        print("rueckwaende: Vereinigung ungueltig (%s) - Rueckwaende weggelassen" % neu.status()); info.append(dict(fehlt="Vereinigung ungueltig (%s), alle Rueckwaende weggelassen" % neu.status())); return koerper, info
    return neu, info


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


def unique_zeilen(A, inverse=False, counts=False, stellen=None):
    """Wie np.unique(A, axis=0, return_inverse=..., return_counts=...) (gleiche Zeilen, gleiche lexikografische Reihenfolge, gleiche Zuordnung), aber per lexsort
    statt Strukturtyp-Sortierung: 24.11.2026 Profil Schwabentor-1122 - np.unique(axis=0) auf 2-4 Mio. Ecken/Kanten kostete in kneifkanten_schliessen + stl_schreiben
    ~100 s je Bau. Ganzzahlen bzw. auf 'stellen' Nachkommastellen gerundete Werte: Zeile als ein int64-Schluessel (wenn <= 62 Bit), sonst lexsort.
    RCPARK_BAU_SERIELL=1 = alter Weg (np.unique)."""
    A = np.asarray(A)
    if os.environ.get("RCPARK_BAU_SERIELL") == "1" or A.ndim != 2 or len(A) == 0:
        r = np.unique(A, axis=0, return_inverse=inverse, return_counts=counts)
        if not (inverse or counts): return r
        r = list(r)
        if inverse: r[1] = r[1].ravel()
        return tuple(r)
    K = None
    if np.issubdtype(A.dtype, np.integer): K = A.astype(np.int64)
    elif stellen is not None: K = np.rint(A * 10.0 ** stellen).astype(np.int64)   # A ist schon auf 'stellen' gerundet: k = A * 10^stellen ist eindeutig und ordnungstreu
    if K is not None:
        K = K - K.min(0); bits = [int(r).bit_length() for r in K.max(0)]
        if sum(bits) <= 62:                                              # Zeile -> ein int64-Schluessel (lexikografisch = numerisch), dann 1-D-unique (schnell)
            key = np.zeros(len(K), np.int64)
            for j, b in enumerate(bits): key = (key << b) | K[:, j]
            o = np.argsort(key); ks = key[o]; neu = np.empty(len(A), bool); neu[0] = True; neu[1:] = ks[1:] != ks[:-1]
        else: K = None
    if K is None:
        o = np.lexsort(A.T[::-1]); As = A[o]
        neu = np.empty(len(A), bool); neu[0] = True; neu[1:] = (As[1:] != As[:-1]).any(1)
    u = A[o[neu]]; erg = [u]                                             # gleicher Schluessel = gleiche Werte (gerundet), welcher Vertreter ist egal
    if inverse: inv = np.empty(len(A), np.intp); inv[o] = np.cumsum(neu) - 1; erg.append(inv)
    if counts: erg.append(np.diff(np.r_[np.flatnonzero(neu), len(A)]))
    return erg[0] if len(erg) == 1 else tuple(erg)


def kneifkanten_schliessen(koerper, r=0.02, runden=6, stellen=4):
    """Kanten, an denen sich der Koerper nur beruehrt (4 Flaechen an einer Kante, z. B. Hohlraum tippt an eine Nische): im STL 'nicht wasserdicht'.
    Um jede solche Kante einen kleinen Klotz (r) auffuellen - schliesst die Beruehrung, oeffnet nie ein Loch."""
    for runde in range(runden):
        me = koerper.to_mesh(); V = np.array(me.vert_properties)[:, :3].astype(np.float64); F = np.asarray(me.tri_verts)
        vq, inv = unique_zeilen(np.round(V, stellen), inverse=True, stellen=stellen); F = inv[F]; F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
        e = np.sort(np.r_[F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], axis=1); u, cnt = unique_zeilen(e, counts=True); bad = u[cnt > 2]
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
    if model.num_tri() == 0 or model.status() != model.status().__class__.NoError:   # 24.11.2026 (1122u): leeres Modell nie als STL schreiben - Generator bricht ab statt still Erfolg zu melden
        raise SystemExit("stl_schreiben: Modell LEER oder ungueltig (%s, %d Dreiecke) - kein STL geschrieben: %s" % (model.status(), model.num_tri(), pfad))
    model = kneifkanten_schliessen(model, r=0.25, stellen=3)           # im Druckmassstab (mm): Beruehrkanten, die erst nach dem Skalieren zusammenfallen (16.11.2026 Blendmasswerk)
    mesh = model.to_mesh(); V = np.array(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
    vq, inv = unique_zeilen(np.round(V.astype(np.float64), 3), inverse=True, stellen=3); F = inv[F]; V = vq.astype(np.float32)
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    fs = np.sort(F, axis=1); _u, inv2, cnt = unique_zeilen(fs, inverse=True, counts=True); F = F[cnt[inv2] == 1]      # Flaechenpaare mit denselben drei Ecken (Lappen ohne Dicke) entfernen
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


# ===== Generator-Bausteine (box, fbox, fcyl, frustum, prism, Bau, ...) =====
# 18.11.2026 wiederhergestellt aus Commit 711a82c1: der Umbau 497af805 (15.11.) hat sie versehentlich aus dieser Datei entfernt,
# die Martinstor-/Kaufhaus-Generatoren importieren sie weiter (martinstor_v4_gen, martinstor_gk_gen, ...). Unveraendert uebernommen.
def box(x0, x1, y0, y1, z0, z1):
    return M.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def fbox(face, u0, u1, z0, z1, n0, n1, c=(0.0, 0.0), h=(0.0, 0.0)):
    """Box an einer Fassade: u = waagrecht entlang Fassade, n = Abstand nach aussen, h = Halbmasse des Koerpers."""
    cx, cy = c; hx, hy = h
    if face == "+x": return box(cx + hx + n0, cx + hx + n1, cy + u0, cy + u1, z0, z1)
    if face == "-x": return box(cx - hx - n1, cx - hx - n0, cy - u1, cy - u0, z0, z1)
    if face == "+y": return box(cx - u1, cx - u0, cy + hy + n0, cy + hy + n1, z0, z1)
    return box(cx + u0, cx + u1, cy - hy - n1, cy - hy - n0, z0, z1)


def fcyl(face, u, z, r, n0, n1, c=(0.0, 0.0), h=(0.0, 0.0), seg=48):
    """Zylinder mit Achse senkrecht zur Fassade."""
    cx, cy = c; hx, hy = h
    cyl = M.cylinder(n1 - n0, r, circular_segments=seg)
    if face in ("+x", "-x"):
        s = 1 if face == "+x" else -1
        cyl = cyl.rotate((0, 90, 0))
        x0 = cx + hx + n0 if s > 0 else cx - hx - n1
        return cyl.translate((x0, cy + s * u, z))
    s = 1 if face == "+y" else -1
    cyl = cyl.rotate((-90, 0, 0))
    y0 = cy + hy + n0 if s > 0 else cy - hy - n1
    return cyl.translate((cx - s * u, y0, z))


def frustum(x0, y0, z0, sx0, sy0, z1, sx1, sy1):
    """Pyramidenstumpf/Walm: Rechteck (sx0,sy0) bei z0 -> (sx1,sy1) bei z1, zentriert."""
    pts = []
    for z, sx, sy in ((z0, sx0, sy0), (z1, sx1, sy1)):
        for a in (-1, 1):
            for b in (-1, 1):
                pts.append((x0 + a * sx / 2, y0 + b * sy / 2, z))
    return M.hull_points(pts)


def prism(face, pts, n0, n1, h):
    """Prisma (Polygon in u,z) an einer Fassade, Dicke n0..n1 nach aussen."""
    hx, hy = h
    P = [(n, u, z) for n in (n0, n1) for (u, z) in pts]
    m = M.hull_points(P)
    if face == "+x": return m.translate((hx, 0, 0))
    if face == "-x": return m.rotate((0, 0, 180)).translate((-hx, 0, 0))
    if face == "+y": return m.rotate((0, 0, 90)).translate((0, hy, 0))
    return m.rotate((0, 0, -90)).translate((0, -hy, 0))


class Bau:
    """Sammelstelle fuer einen Bau: Koerper (adds), Abzuege (cuts), Nachzuege (late) und der Massstab.

    `hx, hy` sind die Standard-Halbmasse des Rumpfs - Teile, die ohne eigenes `h` angelegt werden, sitzen auf dieser Flucht.
    `belegen()` fuehrt das Beleg-Register (jedes sichtbare Element mit Quelle), das der Pruefstand einfordert.
    """

    def __init__(self, k, minmm, hx=0.0, hy=0.0, seg=48, rng=None):
        self.adds, self.cuts, self.late, self.elemente = [], [], [], []
        self.k, self.minmm, self.hx, self.hy, self.seg = k, minmm, hx, hy, seg
        # WICHTIG: denselben Zufallsgenerator wie der Generator verwenden - Muster haengen von der REIHENFOLGE
        # der Aufrufe ab; zwei getrennte Generatoren wuerden Mauerwerk und Eckquader veraendern.
        self.rng = rng if rng is not None else random.Random(1900)

    def rel(self, m):
        """Relieftiefe in Metern, mindestens MINMM im Druck."""
        return max(m, self.minmm / self.k)

    def belegen(self, seite, element, quelle, **masse):
        self.elemente.append(dict(seite=seite, element=element, quelle=quelle, **masse))

    def _h(self, h):
        return (self.hx, self.hy) if h is None else h

    def fassade(self, gruppen, seite, hxy):
        """Oeffnungen einer Seite aus der Fassadenliste (JSON) bauen. Gibt den Beleg-Eintrag zurueck, damit der Aufrufer
        ihn registriert. Reihenfolge der Liste = Reihenfolge im CSG - wichtig, sonst aendert sich das Ergebnis."""
        for g in gruppen:
            if seite not in g["seiten"]: continue
            for o in g["oeffnungen"]:
                if o["typ"] == "fenster":
                    self.window(seite, o["u"], o["z"], o["breite"], o["hoehe"], hh=hxy(o["z"]))
            return g.get("beleg")
        return None

    def window(self, face, u, z, w, h, c=(0.0, 0.0), hh=None, deep=0.35):
        hh = self._h(hh)
        fr, sill = self.rel(0.08), self.rel(0.14)
        self.adds.append(fbox(face, u - w / 2 - 0.25, u + w / 2 + 0.25, z - 0.25, z + h + 0.25, -0.05, fr, c, hh))  # Gewaende
        self.adds.append(fbox(face, u - w / 2 - 0.4, u + w / 2 + 0.4, z - 0.42, z - 0.22, -0.05, sill, c, hh))      # Sohlbank
        self.adds.append(fbox(face, u - w / 2 - 0.35, u + w / 2 + 0.35, z + h + 0.25, z + h + 0.4, -0.05, sill, c, hh))  # Sturzgesims
        self.cuts.append(fbox(face, u - w / 2, u + w / 2, z, z + h, -deep, 0.5, c, hh))
        self.cuts.append(fbox(face, u - 0.05, u + 0.05, z, z + h, -deep - 0.1, 0.5, c, hh) if w > 0.8 else M())  # Fensterkreuz-Spalt -> Mittelpfosten
        if w > 0.8:  # Mittelpfosten + Kaempfer bleiben stehen
            self.adds.append(fbox(face, u - 0.07, u + 0.07, z, z + h, -deep, -0.02, c, hh))
            self.adds.append(fbox(face, u - w / 2, u + w / 2, z + h * 0.62, z + h * 0.62 + 0.12, -deep, -0.02, c, hh))
    
    def quoins(self, c, hx, hy, z0, z1, a=1.3, b=0.75, course=0.72, joint=0.07, pr=None):
        """Eckquader an allen 4 Kanten eines Rechteck-Koerpers (Mitte c, halbe Masse hx, hy)."""
        pr = pr or self.rel(0.12)
        cx, cy = c
        n = int((z1 - z0) / course)
        for sx in (-1, 1):
            for sy in (-1, 1):
                X, Y = cx + sx * hx, cy + sy * hy
                for i in range(n):
                    za, zb = z0 + i * course, z0 + (i + 1) * course - joint
                    lx, ly = (a, b) if i % 2 == 0 else (b, a)
                    xa, xb = sorted((X - sx * lx, X + sx * pr))
                    ya, yb = sorted((Y - sy * ly, Y + sy * pr))
                    self.adds.append(box(xa, xb, ya, yb, za, zb))

    # --- aus dem Martinstor-Generator uebernommen (2026-11-01), Objektgroessen jetzt als Parameter ---
    def clock(self, face, z, r=1.35):
        pr = self.rel(0.1)
        self.adds.append(fbox(face, -r - 0.65, r + 0.65, z - r - 0.65, z + r + 0.65, -0.05, pr))   # Sandstein-Rahmen
        self.cuts.append(fcyl(face, 0, z, r + 0.12, -0.15, 0.6))                                   # Nische
        self.adds.append(fcyl(face, 0, z, r, -0.2, -0.15 + self.rel(0.06)))                             # Zifferblatt
        self.adds.append(fcyl(face, 0, z, 0.18, -0.2, -0.15 + self.rel(0.16)))                          # Nabe
        for i in range(12):  # Stundenmarken
            ang = math.radians(i * 30)
            u, zz = math.sin(ang) * r * 0.82, z + math.cos(ang) * r * 0.82
            s = 0.16 if i % 3 == 0 else 0.1
            self.adds.append(fbox(face, u - s, u + s, zz - s, zz + s, -0.2, -0.15 + self.rel(0.12)))
        for ang, ln, wd in ((math.radians(300), 0.75, 0.09), (math.radians(60), 1.1, 0.06)):  # Zeiger 10:10
            steps = 6
            for k in range(steps):
                t = (k + 0.5) / steps * ln
                u, zz = math.sin(ang) * t, z + math.cos(ang) * t
                self.adds.append(fbox(face, u - wd, u + wd, zz - wd, zz + wd, -0.2, -0.15 + self.rel(0.14)))
    def clock3(self, face, z, r, hh):
        pr = self.rel(0.1)
        self.adds.append(fbox(face, -r - 0.9, r + 0.9, z - r - 0.9, z + r + 0.9, -0.05, pr, h=hh))   # Sandsteinrahmen
        self.cuts.append(fcyl(face, 0, z, r + 0.12, -0.15, 0.6, h=hh))
        self.late.append(fcyl(face, 0, z, r, -0.2, -0.15 + self.rel(0.06), h=hh))
        self.late.append(fcyl(face, 0, z, 0.2, -0.2, -0.15 + 3.2 * self.rel(0.06), h=hh))
        for i in range(12):
            ang = math.radians(i * 30)
            u, zz = math.sin(ang) * r * 0.82, z + math.cos(ang) * r * 0.82
            sz = 0.17 if i % 3 == 0 else 0.1
            self.late.append(fbox(face, u - sz, u + sz, zz - sz, zz + sz, -0.2, -0.15 + 2.2 * self.rel(0.06), h=hh))
        for ang, ln, wd in ((math.radians(300), 0.8, 0.09), (math.radians(60), 1.2, 0.06)):
            for k in range(6):
                t = (k + 0.5) / 6 * ln
                u, zz = math.sin(ang) * t, z + math.cos(ang) * t
                self.late.append(fbox(face, u - wd, u + wd, zz - wd, zz + wd, -0.2, -0.15 + 2.6 * self.rel(0.06), h=hh))
    def bruchstein(self, zb_, f, L, hh, frei):
        """Unregelmaessige Bruchstein-Quader auf einer Sockelseite (Foto: grobe Findlinge mit tiefen Fugen).
        frei(u0,u1,z0,z1) -> True, wenn dort schon etwas anderes sitzt (Tor, Tafel, Fenster)."""
        z = 0.95
        while z < zb_ - 0.3:
            hgt = self.rng.uniform(0.48, 0.78)
            z1 = min(z + hgt, zb_ - 0.02)
            u = -L / 2 + 0.35
            while u < L / 2 - 0.35:
                w = self.rng.uniform(0.7, 1.7)
                u1 = min(u + w, L / 2 - 0.35)
                if u1 - u > 0.3 and not frei(u, u1, z, z1):
                    pr = self.rel(self.rng.uniform(0.05, 0.22))
                    self.adds.append(fbox(f, u + 0.03, u1 - 0.03, z + 0.03, z1 - 0.03, -0.05, pr, h=hh))
                u = u1
            z = z1
    def falze(self, rz0, rz1, face, hb, ht, ub, ut):
        dz = rz1 - rz0
        th = math.degrees(math.atan2(hb - ht, dz))
        nseam = int(2 * ub / 0.62)
        for k in range(nseam):
            u = -ub + (k + 0.5) * 2 * ub / nseam
            t1 = min(1.0, (ub - abs(u) - 0.2) / (ub - ut))
            if t1 <= 0.15: continue
            t0 = 0.04
            L = (t1 - t0) * dz / math.cos(math.radians(th))
            zc = rz0 + (t0 + t1) / 2 * dz
            xc = hb - (hb - ht) * (t0 + t1) / 2
            cut = M.cube((0.16, 0.06, L)).translate((-0.08, -0.03, -L / 2)).rotate((0, -th, 0)).translate((xc, u, zc))
            if face == "-x": cut = cut.rotate((0, 0, 180))
            elif face == "+y": cut = cut.rotate((0, 0, 90))
            elif face == "-y": cut = cut.rotate((0, 0, -90))
            self.cuts.append(cut)


def okt_prisma(c, r, z0, z1):
    """Achteck mit Schluesselweite 2r (Flaechen zeigen nach +-x/+-y, wie Schnitt- und Strahlmessungen), von z0 bis z1."""
    R = r / math.cos(math.radians(22.5)); return M.cylinder(z1 - z0, R, R, 8).rotate((0, 0, 22.5)).translate((c[0], c[1], z0))

def okt_kegel(c, r0, z0, r1, z1):
    R0, R1 = r0 / math.cos(math.radians(22.5)), r1 / math.cos(math.radians(22.5)); return M.cylinder(z1 - z0, R0, max(R1, 0.03), 8).rotate((0, 0, 22.5)).translate((c[0], c[1], z0))

def baender_rundkoerper(c, baender, kegel, spitze, rel, nach_innen, adds, cuts, n_oeffnungen=2, knauf=True, oeffnungen=None, hohl={"wand": 0.2, "innen": 0.5}):
    """Rundkoerper (Erker/Tuermchen/Laterne) aus gemessenen Hoehenbaendern (tools/wolke_baender.py): je Band {z0, z1, r, klasse}.
    gesims/traufe = Kragplatte (Achteck r); hell = Bruestung mit Leisten und X-Schlitzen; offen = Band mit n_oeffnungen Rundbogenoeffnungen
    je Aussenflaeche; traufe zusaetzlich 8 Konsolen darunter; kegel {r0, z0} = Achteckkegel bis spitze - 0,5 + Knauf/Nadel.
    oeffnungen = {je_flaeche, breite_anteil} (am FOTO gezaehlt/gemessen, tools/foto_zaehlung.py) hat VORRANG vor den Wolken-Laeufen in b['oeffnungen']
    (Register CB: Wolken-Dunkellaeufe lieferten 2 Boegen + Zwischenpfeiler, am Bauwerk steht je Flaeche EIN Bogen); breite_anteil = Oeffnungsbreite / Flaechenbreite.
    stein-Baender baut der Aufrufer (Schaft mit Quadern/Fenstern ist bauwerksspezifisch). nach_innen(k) sagt, ob Flaeche k (Normale k*45 Grad)
    zum Hauptkoerper zeigt - dort keine Oeffnungen (sonst Hohlraeume). rel(m) = Relieftiefe mit Druck-Untergrenze. Fuegt in adds/cuts ein."""
    for b in baender:
        z0, z1, r, kl = b["z0"], b["z1"], b["r"], b["klasse"]
        if kl == "gesims":
            adds.append(okt_prisma(c, r, z0 - 0.02, z1))
        elif kl in ("hell", "fachwerk"):
            adds.append(okt_prisma(c, r, z0 - 0.02, z1))
            for zz in (z0, z1 - 0.12): adds.append(okt_prisma(c, r + rel(0.12), zz, zz + 0.12))
            for k in range(8):
                if nach_innen(k): continue
                for sg in (-1, 1):
                    hs = max(z1 - z0 - 0.3, 0.15)                                          # Schlitzhoehe nie <= 0 (sehr flache Baender)
                    cut = M.cube((0.4, 0.08, hs)).translate((-0.2 + r + 0.02, -0.04, -hs / 2)).rotate((sg * 38, 0, 0))
                    cuts.append(cut.translate((0, 0, (z0 + z1) / 2)).rotate((0, 0, k * 45)).translate((c[0], c[1], 0)))
        elif kl == "offen":
            # Koerper bis an die naechste AUSKRAGENDE Platte (r >= r + 0,2): Baender dazwischen (z. B. Nullstart 'stein' 34,5-35,0) baut sonst niemand -> Luecke unter dem Dach (Register CG)
            deck = [b2["z0"] for b2 in baender if b2["z0"] >= z1 - 1e-6 and b2["r"] >= r + 0.2]; z_deck = min(deck) if deck else z1
            adds.append(okt_prisma(c, r, z0 - 0.02, z_deck))
            fb = 2 * r * math.tan(math.radians(22.5))
            oe_d = b.get("oeffnungen") or {}                                                      # Wolke (wolke_baender): nur Hoehe/Rueckfall; Zahl und Breite haben Foto-Vorrang (oeffnungen=)
            n_o = int((oeffnungen or {}).get("je_flaeche") or oe_d.get("je_flaeche") or n_oeffnungen) or 1
            pf = 0.12                                                                             # Mindestpfeiler zwischen/neben den Oeffnungen
            b_ziel = (oeffnungen or {}).get("breite_anteil", 0) * fb / n_o if (oeffnungen or {}).get("breite_anteil") else float(oe_d.get("breite_median") or 0.36)
            bw = min(b_ziel, (fb - (n_o + 1) * pf) / n_o)
            # Oeffnungshoehe ROBUST (Register CG): Oberkante = Unterseite der naechsten AUSKRAGENDEN Platte (r >= r + 0,2) minus Sturz 0,08 m (ANNAHME, Foto 030:
            # Bogen fast an der Platte). Die Bandgrenze der Wolke springt von Lauf zu Lauf (Ref offen bis 35,0, Nullstart 34,5 + 'stein'); die Plattenunterkante nicht (beide 35,0).
            zu = (max(oe_d["hoehe"][0], z0 + 0.1) if oe_d.get("hoehe") else z0 + 0.1); zo = z_deck - 0.08; bh = max(zo - zu, bw)
            for k in range(8):
                if nach_innen(k): continue
                for j in range(n_o):
                    u = (j - (n_o - 1) / 2) * (bw + pf)
                    st_a = (oeffnungen or {}).get("stich_anteil")                                     # Bogenstich/Breite (Foto); None = Halbkreis (alt)
                    s_ = bw / 2 if not st_a else min(bw / 2, max(0.03, st_a * bw)); R_ = (bw * bw / 4 + s_ * s_) / (2 * s_); zt_ = zu + bh
                    oe = M.cube((0.45, bw, bh - s_ + 0.01)).translate((r - 0.35, u - bw / 2, zu))
                    bogen = M.cylinder(0.45, R_, R_, 64).rotate((0, 90, 0)).translate((r - 0.35, u, zt_ - R_))
                    oe = oe + (bogen ^ M.cube((0.45, bw, s_ + 0.01)).translate((r - 0.35, u - bw / 2, zt_ - s_)))   # Segmentbogen (Register CF)
                    cuts.append(oe.rotate((0, 0, k * 45)).translate((c[0], c[1], 0)))
            # Band 'offen' (Wolke: dunkler Anteil hoch = Durchblick) ist ein HOHLRAUM, keine Nischenreihe: sonst zeichnet die Nischenrueckwand jeden Bogen ein
            # zweites Mal kleiner/versetzt (Register CD). Innenraum = Achteck r - wand von Sohle bis Bandoberkante; zur Turmseite (Ursprung) hin nur bis
            # hohl_innen hinter die Achse, damit der Hauptkoerper nicht angeschnitten wird. ANNAHME wand 0,2 m (schlanke Pfosten, Foto 043), hohl_innen 0,5 m.
            if hohl:
                wand, hi = hohl.get("wand", 0.2), hohl.get("innen", 0.5)
                h = okt_prisma(c, r - wand, zu, z_deck - 0.01)
                sx = 0 if abs(c[0]) < 1e-6 else math.copysign(1, c[0]); sy = 0 if abs(c[1]) < 1e-6 else math.copysign(1, c[1]); L = 2 * r + 1
                bx0, bx1 = (c[0] - L, c[0] + L) if sx == 0 else ((c[0] - hi, c[0] + L) if sx > 0 else (c[0] - L, c[0] + hi))
                by0, by1 = (c[1] - L, c[1] + L) if sy == 0 else ((c[1] - hi, c[1] + L) if sy > 0 else (c[1] - L, c[1] + hi))
                cuts.append(h ^ M.cube((bx1 - bx0, by1 - by0, z_deck - zu + 1)).translate((bx0, by0, zu - 0.5)))
        elif kl == "traufe":
            adds.append(okt_prisma(c, r, z0, z1))
            for k in range(8):
                ang = math.radians(k * 45 + 22.5); rr = r - 0.22
                adds.append(M.cube((0.2, 0.2, 0.3)).translate((-0.1, -0.1, 0)).rotate((0, 0, k * 45 + 22.5)).translate((c[0] + rr * math.cos(ang), c[1] + rr * math.sin(ang), z0 - 0.28)))
    if kegel: adds.append(okt_kegel(c, kegel["r0"], kegel["z0"] - 0.02, 0.05, spitze - 0.5))
    if knauf: adds.append(M.sphere(0.2, 20).translate((c[0], c[1], spitze - 0.35))); adds.append(M.cylinder(0.35, 0.05, 0.015, 8).translate((c[0], c[1], spitze - 0.35)))


def segmentbogen_reihe(laeufe, n_soll, z_oben, hoehe, stich_anteil):
    """Oeffnungsreihe (Schallarkaden, Lauben ...) GENERISCH aus Wolken-Dunkellaeufen [[start, breite], ...] (wolke_baender.py, Register CD):
    Lage/Breite je Oeffnung aus der Wolke, ANZAHL n_soll aus der Foto-Zaehlung (Register CB). Stimmt die Laufzahl nicht, werden n_soll gleiche
    Oeffnungen ueber die Wolkenspanne verteilt (Pfeiler 0,3 m) und das gemeldet. Rueckgabe je Oeffnung dict(u0, u1, uc, zu, zk, zt, R) fuer einen
    Segmentbogen: Sohle zu, Kaempfer zk, Scheitel zt = z_oben, Kreisradius R (Mittelpunkt bei zt - R)."""
    L = [(float(a), float(a) + float(b)) for a, b in laeufe]
    hinweis = ""
    if len(L) != n_soll:
        a0, a1 = min(x for x, _ in L), max(y for _, y in L); pf = 0.3; w = (a1 - a0 - (n_soll - 1) * pf) / n_soll
        L = [(a0 + i * (w + pf), a0 + i * (w + pf) + w) for i in range(n_soll)]; hinweis = f"Wolke {len(laeufe)} Laeufe != Foto {n_soll}: gleich verteilt"
    out = []
    for u0, u1 in L:
        w = u1 - u0; s = max(0.05, stich_anteil * w); R = (w * w / 4 + s * s) / (2 * s)
        out.append(dict(u0=u0, u1=u1, uc=(u0 + u1) / 2, zu=z_oben - hoehe, zk=z_oben - s, zt=z_oben, R=R, hinweis=hinweis))
    return out


def mauerwerk_aus_protokollen(objekt_dir, bauteil, rueckfall):
    """Mauerwerksmasse eines Bauteils (z. B. 'Eckband') aus Foto-Messprotokollen (Register CI), GENERISCH fuer jedes Objekt.
    Liest messprotokoll/M-*.json mit name 'Mauerwerk_<bauteil>_Schichthoehe*' | '_Stein_lang*' | '_Stein_kurz*' (tools/foto_mass.py --kamera).
    Rueckgabe dict(kurs=f(z) -> Schichthoehe (lineare Interpolation ueber die Protokollhoehen, aussen konstant), lang, kurz, quelle, protokolle);
    fehlt eine Groesse in den Protokollen, gilt rueckfall[...] (Werte aus masse.json, Quelle dort)."""
    import glob, json, os
    sch, lang, kurz, ids = [], [], [], []
    for p in sorted(glob.glob(os.path.join(objekt_dir, "messprotokoll", "M-*.json"))):
        r = json.load(open(p)); n = str(r.get("name", ""))
        if not n.startswith(f"Mauerwerk_{bauteil}_"): continue
        rest = n[len(f"Mauerwerk_{bauteil}_"):]; ids.append(r["id"])
        if rest.startswith("Schichthoehe"): sch.append(((r["z1"] + r["z2"]) / 2, abs(r["dz"]) if abs(r["dz"]) > 0.5 * r["abstand"] else r["abstand"]))
        elif rest.startswith("Stein_lang"): lang.append(r["abstand"])
        elif rest.startswith("Stein_kurz"): kurz.append(r["abstand"])
    sch.sort()
    def kurs(z):
        if not sch: return rueckfall["kurs"](z)
        if z <= sch[0][0]: return sch[0][1]
        if z >= sch[-1][0]: return sch[-1][1]
        for (za, ka), (zb, kb) in zip(sch, sch[1:]):
            if za <= z <= zb: return ka + (kb - ka) * (z - za) / max(zb - za, 1e-9)
    med = lambda v: sorted(v)[len(v) // 2] if len(v) % 2 else (sorted(v)[len(v) // 2 - 1] + sorted(v)[len(v) // 2]) / 2
    return dict(kurs=kurs, lang=med(lang) if lang else rueckfall["lang"], kurz=med(kurz) if kurz else rueckfall["kurz"],
                quelle=("Foto-Messprotokolle " + ", ".join(ids)) if ids else "Rueckfall masse.json", protokolle=ids,
                n=dict(schicht=len(sch), lang=len(lang), kurz=len(kurz)))


def tuermchen_achse_je_quadrant(ta, seite, sx, sy):
    """Achse (x, y) eines Eck-/Abseitskoerpers aus wolke_profile.py['tuerm_achsen'] (Register CH), generisch fuer jede Seite.
    ta['je'] = {'quer+'|'quer-': {tief, quer_rel}}: quer RELATIV zur Zentralmitte (Wolkenverschiebung herausgerechnet), tief = Betrag.
    Quadranten auf der Rueckseite (von dieser Seite nicht gesehen) = Spiegelung des Quadranten mit gleichem quer-Vorzeichen (ANNAHME)."""
    tief, sgn, quer = seite_achsen(seite)
    s_tief, s_quer = (sx, sy) if tief == "x" else (sy, sx)
    q = ta["je"]["quer+" if s_quer > 0 else "quer-"]
    vt, vq = s_tief * q["tief"], s_quer * abs(q["quer_rel"])
    return (vt, vq) if tief == "x" else (vq, vt)


def oeffnungsreihe_aus_profil(profil_pfad, z_min, n_soll, hoehe, stich_anteil, traufabstand=None, rueckfall=None, aktiv=True):
    """GENERISCH (jedes Objekt): Oeffnungsreihe einer Fassade aus einem Wolken-Baenderprofil (wolke_baender.py) - Register CE/CG.
    Band = erstes 'offen' mit Dunkellaeufen oberhalb z_min. Lage/Breite je Oeffnung = Wolkenlaeufe; ANZAHL n_soll = Foto-Zaehlung (Register CB);
    hoehe = Foto-Mass; Scheitel ROBUST = Unterkante des naechsten 'traufe'-Bandes - traufabstand (Foto-Mass), sonst Oberkante des Dunkellaufs.
    Ohne Profil (erster Generatorlauf im Nullstart) -> rueckfall = dict(breite, pfeiler, scheitel) aus Fotomassen.
    Rueckgabe (liste segmentbogen_reihe, quelle 'wolke' | 'foto_rueckfall')."""
    import os as _os, json as _json
    ob, tr = None, []
    if aktiv and profil_pfad and _os.path.exists(profil_pfad):
        B = _json.load(open(profil_pfad))["baender"]
        ob = ([b["oeffnungen"] for b in B if b["klasse"] == "offen" and b.get("oeffnungen") and b["z0"] > z_min] or [None])[0]
        tr = [b["z0"] for b in B if b["klasse"] == "traufe" and b["z0"] > z_min]
    if ob:
        lf = ob["details"][0]["laeufe"]; zo = (min(tr) - traufabstand) if (tr and traufabstand is not None) else ob["hoehe"][1]; q = "wolke"
    else:
        if not rueckfall: return [], "keine"
        sp = n_soll * rueckfall["breite"] + (n_soll - 1) * rueckfall["pfeiler"]
        lf = [[-sp / 2 + i * (rueckfall["breite"] + rueckfall["pfeiler"]), rueckfall["breite"]] for i in range(n_soll)]; zo = rueckfall["scheitel"]; q = "foto_rueckfall"
    return segmentbogen_reihe(lf, n_soll, zo, hoehe, stich_anteil), q


# ------------------------------------------------------------------ Netz-Neuvernetzung (S4, 2026-11-05)
def netz_druckbar(V, F, zelle_m, vol_min=0.90, vol_max=1.00, sigma=0.5, max_unsicher=0.01, simpl=0.02):
    """Bild-zu-3D-Netz (TripoSR u. a.) auf Druckaufloesung neu vernetzen. V (n,3) Meter, F (m,3) Indizes; zelle_m = Duese x Massstab / 1000 (Zelle des Innen-Gitters).
    Warum (versuche.jsonl 'figuren-druckbar-ursache'): die Netze sind mannigfaltig, aber ihre Feinstruktur unter Druckaufloesung wird beim Export (simplify, float32-STL) zu
    Beruehrkanten (123-155 Koerper). Verfahren: Innen-Test = Paritaet entlang z-Strahlen (je Gitterzelle), Besetzung -> groesste zusammenhaengende Komponente ->
    Gauss-Glaettung (sigma Zellen) -> Oberflaeche bei Level l per manifold3d.level_set (Marching Tetrahedra, garantiert mannigfaltig; skimage-Marching-Cubes fehlt in der
    Generator-Umgebung). Der Level l wird aus 0,5/0,48/... (nach aussen wachsend) so gewaehlt, dass das Volumen in [vol_min, vol_max] des Originals liegt (Spec 90-100 %); sonst Verwerfen.
    Schwellen als Argumente: vol_min/vol_max aus Spec S4; sigma 0,5 (bei Nichtgelingen werden 0,4 und 0,6 probiert; gemessen an 4 TripoSR-Figuren: sigma 0,8 zerlegt das Netz in Teile, Hauptteil nur 42-57 % des Volumens; 0,4-0,5: 1 Koerper, 90-97 % bei Level 0,5); simpl = Kantenlaenge (Anteil der Zelle) unter der Level-Set-Dreiecke zusammengezogen werden (0,02: nur Entartete; mit trimesh process=True gemessen: ohne diesen Schritt 1 von 4 Netzen mit Nullflaechen-Dreiecken -> 4 Koerper/Loecher); max_unsicher = Anteil Strahlen mit
    ungerader Trefferzahl (Netz nicht geschlossen), darueber Verwerfen.
    Rueckgabe: (V2, F2, info) mit info = dict(ok, grund, zelle_m, vol_orig, vol_neu, anteil, level, dreiecke_alt, dreiecke_neu, unsicher); bei ok=False sind V2/F2 None."""
    import numpy as np
    from scipy import ndimage
    V = np.asarray(V, float); F = np.asarray(F, int); info = dict(ok=False, zelle_m=float(zelle_m), dreiecke_alt=int(len(F)))
    T = V[F]; vol0 = abs(float(np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum() / 6.0)); info["vol_orig"] = vol0
    if vol0 <= 0 or M is None: info["grund"] = "Volumen 0 oder manifold3d fehlt"; return None, None, info
    lo = V.min(0) - 3 * zelle_m; hi = V.max(0) + 3 * zelle_m; n = np.ceil((hi - lo) / zelle_m).astype(int); n = np.maximum(n, 4); hi = lo + n * zelle_m
    eps = np.array([0.4142135, 0.7320508]) * 1e-6 * zelle_m                                           # Strahlen leicht versetzt: keine Treffer genau auf Dreieckskanten
    p = T[:, :, :2]; a, b, c = p[:, 0], p[:, 1], p[:, 2]; d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok_t = np.abs(d) > 1e-18                                                                          # senkrechte Dreiecke (Projektionsflaeche 0) treffen keinen z-Strahl
    i0 = np.floor((p[:, :, 0].min(1) - lo[0]) / zelle_m - 0.5).astype(int) + 1; i1 = np.floor((p[:, :, 0].max(1) - lo[0]) / zelle_m - 0.5).astype(int) + 1
    j0 = np.floor((p[:, :, 1].min(1) - lo[1]) / zelle_m - 0.5).astype(int) + 1; j1 = np.floor((p[:, :, 1].max(1) - lo[1]) / zelle_m - 0.5).astype(int) + 1
    hits = []                                                                                         # (ray = i*ny + j, z)
    def treffer(idx, di, dj):
        i = i0[idx] + di; j = j0[idx] + dj; ok = ok_t[idx] & (i <= i1[idx]) & (j <= j1[idx]) & (i >= 0) & (j >= 0) & (i < n[0]) & (j < n[1]); idx, i, j = idx[ok], i[ok], j[ok]
        x = lo[0] + (i + 0.5) * zelle_m + eps[0]; y = lo[1] + (j + 0.5) * zelle_m + eps[1]
        l1 = ((b[idx, 1] - c[idx, 1]) * (x - c[idx, 0]) + (c[idx, 0] - b[idx, 0]) * (y - c[idx, 1])) / d[idx]; l2 = ((c[idx, 1] - a[idx, 1]) * (x - c[idx, 0]) + (a[idx, 0] - c[idx, 0]) * (y - c[idx, 1])) / d[idx]; l3 = 1 - l1 - l2
        im = (l1 >= 0) & (l2 >= 0) & (l3 >= 0); idx, i, j, l1, l2, l3 = idx[im], i[im], j[im], l1[im], l2[im], l3[im]
        hits.append((i * n[1] + j, l1 * T[idx, 0, 2] + l2 * T[idx, 1, 2] + l3 * T[idx, 2, 2]))
    span = np.maximum(i1 - i0, j1 - j0); klein = np.where(span <= 3)[0]; gross = np.where(span > 3)[0]
    for di in range(4):
        for dj in range(4): treffer(klein, di, dj)
    for t in gross:                                                                                   # wenige grosse Dreiecke (Deckel/Boden): einzeln
        for di in range(i1[t] - i0[t] + 1):
            for dj in range(j1[t] - j0[t] + 1): treffer(np.array([t]), di, dj)
    ray = np.concatenate([h[0] for h in hits]); zz = np.concatenate([h[1] for h in hits]); o = np.lexsort((zz, ray)); ray, zz = ray[o], zz[o]
    occ = np.zeros(tuple(n), bool); start = np.r_[0, np.where(np.diff(ray))[0] + 1, len(ray)]; ungerade = 0
    for s0, s1 in zip(start[:-1], start[1:]):
        if (s1 - s0) % 2: ungerade += 1; continue
        i, j = divmod(int(ray[s0]), int(n[1]))
        for q in range(s0, s1, 2):
            k0 = int(np.ceil((zz[q] - lo[2]) / zelle_m - 0.5)); k1 = int(np.ceil((zz[q + 1] - lo[2]) / zelle_m - 0.5)); occ[i, j, max(k0, 0):max(k1, 0)] = True
    info["unsicher"] = round(ungerade / max(1, len(start) - 1), 4)
    if info["unsicher"] > max_unsicher: info["grund"] = f"Netz nicht geschlossen ({info['unsicher']:.1%} Strahlen mit ungerader Trefferzahl)"; return None, None, info
    lab, nl = ndimage.label(occ)
    if nl == 0: info["grund"] = "Netz unter Druckaufloesung (keine besetzte Zelle)"; return None, None, info
    occ = lab == (1 + int(np.argmax(ndimage.sum(occ, lab, range(1, nl + 1)))))                        # groesste Komponente
    f = lambda x, y, z: float(ndimage.map_coordinates(gl, [[(x - lo[0]) / zelle_m - 0.5], [(y - lo[1]) / zelle_m - 0.5], [(z - lo[2]) / zelle_m - 0.5]], order=1, mode="constant")[0]) - lvl
    import trimesh as _tm
    gl = None; sg_alt = None; lvl = 0.5
    for ver, sg, lvl in [(v_, sg_, l_) for v_ in (0.0, 0.37, 0.71) for sg_ in (sigma, sigma - 0.1, sigma + 0.1) for l_ in (0.5, 0.49, 0.48, 0.47, 0.46, 0.45, 0.44, 0.42)]:   # ver = Versatz des Level-Set-Gitters in Zellen (anderes Schnappen der Punkte)
        if sg != sg_alt: gl = ndimage.gaussian_filter(occ.astype(float), sg, mode="constant"); sg_alt = sg
        m = M.level_set(f, list(lo + ver * zelle_m) + list(hi + ver * zelle_m), zelle_m)
        if m.is_empty(): continue
        parts = m.decompose(); m = max(parts, key=lambda q: q.volume()).simplify(simpl * zelle_m); r = m.volume() / vol0      # simplify: entartete Dreiecke aus dem Level-Set-Schnappen (Flaeche 0) entfernen
        mm = m.to_mesh(); t = _tm.Trimesh(np.asarray(mm.vert_properties)[:, :3].astype(np.float32).astype(float), np.asarray(mm.tri_verts), process=True)   # wie der STL-Export: float32 + Punkte verschweissen
        if not (t.is_watertight and len(t.split(only_watertight=False)) == 1): info["anteil"] = round(float(r), 4); info["grund"] = "Level-Set-Netz nach Verschweissen nicht wasserdicht"; continue   # Beruehrstellen (Level-Set erzeugt doppelte Punkte) -> naechster Level
        if vol_min <= r <= vol_max:
            info.update(ok=True, grund="", vol_neu=float(m.volume()), anteil=round(float(r), 4), level=lvl, dreiecke_neu=int(len(t.faces)), komponenten=sum(1 for q in parts if q.volume() > 0.01 * vol0))
            return np.asarray(t.vertices, float), np.asarray(t.faces, int), info
        info["anteil"] = round(float(r), 4)
    info["grund"] = f"Netz unter Druckaufloesung (letzter Versuch: Volumen {info.get('anteil', 0):.0%} ausserhalb {vol_min:.0%}-{vol_max:.0%} oder nicht wasserdicht nach Verschweissen: {info.get('grund', '')})"; return None, None, info


# --- 21.11.2026: Koerper aus dem Rest der dichten Wolke (tools/wolke_rest.py -> audit/koerper_auto.json, Annahme je Kandidat durch tools/koerper_schleife.py) ---------------------------------
def _wolkenrest_haufen(datei, formen):
    """Eintraege der Formen aus koerper_auto.json, ohne verworfene (angenommen == false) und ohne solche ohne Masse."""
    if not os.path.exists(datei): return []
    return [H for H in json.load(open(datei)).get("haufen", []) if H.get("form") in formen and H.get("angenommen") is not False and H.get("mass")]


def kastenkoerper_aus_wolkenrest(koerper, datei):
    """Quader an einer Wand (Anbau, Erker, Risalit) aus tools/wolke_rest.py, Form 'kasten': Wandrahmen o/d/n aus der Normale der naechsten Modellflaeche, Aussenflaechen = Ebenen-Fit der
    Wolkenpunkte (u0/u1 Seiten, w1 Front, z0/z1). Gebaut wird von 5 cm hinter der Wandflaeche (w0) bis zur Front; 'bis_boden': bis z 0 (Wolke am Boden abgeschnitten). Kein Musterteil:
    nur der gemessene Quader - Dach, Gliederung, Oeffnungen kommen aus Fotokanten auf seinen Ebenen. Guard: jede Kante >= 0,2 m, sonst nicht gebaut (Beleg)."""
    belege = []
    for H in _wolkenrest_haufen(datei, ("kasten",)):
        m = H["mass"]; o = np.array(m["o"], float); d = np.array(m["d"], float); n = np.array(m["n"], float); z0 = 0.0 if m.get("bis_boden") else float(m["z0"]); w0 = float(m["w0"]) - 0.05
        if min(m["u1"] - m["u0"], m["w1"] - w0, m["z1"] - z0) < 0.2:
            belege.append(dict(seite="wand", element=f"Kasten {H.get('id', '')} NICHT gebaut (Kante < 0,2 m)", quelle="tools/wolke_rest.py; Gueltigkeits-Guard bauteile.kastenkoerper_aus_wolkenrest")); continue
        koerper = koerper + M.hull_points([[o[0] + u * d[0] + w * n[0], o[1] + u * d[1] + w * n[1], z] for u in (m["u0"], m["u1"]) for w in (w0, m["w1"]) for z in (z0, m["z1"])])
        ohne = [k for k, v in (m.get("flaechen") or {}).items() if v < 0.03]
        belege.append(dict(seite="wand", element=f"Kasten {H.get('id', '')}: breit {m['u1'] - m['u0']:.2f} m, {m['w1'] - m['w0']:.2f} m vor der Wand, z {z0:.2f}..{m['z1']:.2f} m (Mitte x {o[0] + 0.5 * (m['u0'] + m['u1']) * d[0]:.2f} y {o[1] + 0.5 * (m['u0'] + m['u1']) * d[1]:.2f})",
                           quelle=f"dichte Wolke: Rest am Modell ({H['punkte']} Punkte), Punkte liegen im Median {m['rest']} m an den Aussenflaechen des Quaders, Front {m.get('winkel_front')} Grad zur Wand (tools/wolke_rest.py)",
                           hinweis="ANNAHME: Quader (oben flach, keine Gliederung, voll)" + (", bis zum Boden verlaengert (Wolke unter 1 m abgeschnitten)" if m.get("bis_boden") else "") + (f"; Flaechen ohne Wolkenpunkte: {', '.join(ohne)} (Lage aus dem Rand der uebrigen Punkte)" if ohne else "") + "; Masse aus Fotokanten nachmessen (offen)"))
    return koerper, belege


def ringkoerper_aus_wolkenrest(koerper, datei):
    """Umlaufende oder einseitige Auskragung auf einer Hoehe (Gesims, Umgang, Dachueberstand) aus tools/wolke_rest.py, Formen 'ring' / 'band': der QUERSCHNITT DES MODELLS in der Hoehenmitte
    des Haufens wird um die gemessene Ausladung nach aussen versetzt und von z0 bis z1 ausgezogen (folgt jedem Grundriss, kein Musterprofil). Gebaut wird nur, wo die Wolke den Koerper zeigt:
    'ring' in den belegten 15-Grad-Sektoren (+ je ein Nachbarsektor), 'band' im Grundriss-Rechteck des Haufens (+ 0,1 m). Fensternischen im Querschnitt werden mit 0,5 m geschlossen
    (sonst folgte der Ring jeder Nische). Guard: leerer Querschnitt oder Ausladung < 5 cm -> nicht gebaut (Beleg)."""
    belege = []
    for H in _wolkenrest_haufen(datei, ("ring", "band")):
        m = H["mass"]; z0, z1, a_ = float(m["z0"]), float(m["z1"]), float(m["ausladung"]); cs = koerper.slice(0.5 * (z0 + z1)); name = "Ring" if H["form"] == "ring" else "Band"
        if not cs.is_empty(): cs = CrossSection([p for p in cs.to_polygons() if len(p) >= 3 and CrossSection([p]).area() > 0.01])      # nur Aussenumrisse (Hohlraeume der Schale zaehlen nicht)
        if cs.is_empty() or a_ < 0.05 or z1 - z0 < 0.05:
            belege.append(dict(seite="wand", element=f"{name} {H.get('id', '')} NICHT gebaut (kein Modellquerschnitt bei z {0.5 * (z0 + z1):.2f} m oder Ausladung/Hoehe < 5 cm)", quelle="tools/wolke_rest.py; Gueltigkeits-Guard bauteile.ringkoerper_aus_wolkenrest")); continue
        cs = cs.offset(0.5, JoinType.Miter, 2.0).offset(-0.5, JoinType.Miter, 2.0); ring = cs.offset(a_, JoinType.Miter, 2.0) - cs.offset(-0.05, JoinType.Miter, 2.0); c = np.array(m["c"], float)
        if H["form"] == "band" or not m.get("sektoren"):
            g = m.get("grenzen") or [c[0] - 1e3, c[1] - 1e3, c[0] + 1e3, c[1] + 1e3]; ring = ring ^ CrossSection([[[g[0] - 0.1, g[1] - 0.1], [g[2] + 0.1, g[1] - 0.1], [g[2] + 0.1, g[3] + 0.1], [g[0] - 0.1, g[3] + 0.1]]]); wo = f"im Rechteck x {g[0]:.1f}..{g[2]:.1f} y {g[1]:.1f}..{g[3]:.1f}"
        else:
            S_ = m["sektoren"]; ns = len(S_); an = [bool(S_[i] or S_[(i - 1) % ns] or S_[(i + 1) % ns]) for i in range(ns)]; b = koerper.bounding_box(); R_ = float(np.hypot(b[3] - b[0], b[4] - b[1])) + a_ + 5.0
            if not all(an):
                keile = [CrossSection([[[c[0], c[1]]] + [[c[0] + R_ * math.cos(w), c[1] + R_ * math.sin(w)] for w in np.linspace(-math.pi + i * 2 * math.pi / ns - 0.01, -math.pi + (i + 1) * 2 * math.pi / ns + 0.01, 4)]]) for i in range(ns) if an[i]]
                ring = ring ^ CrossSection.batch_boolean(keile, OpType.Add)
            wo = f"{sum(S_)} von {ns} Sektoren belegt, {sum(an)} gebaut"
        if ring.is_empty():
            belege.append(dict(seite="wand", element=f"{name} {H.get('id', '')} NICHT gebaut (leer nach Beschnitt)", quelle="tools/wolke_rest.py; Gueltigkeits-Guard bauteile.ringkoerper_aus_wolkenrest")); continue
        koerper = koerper + M.extrude(ring, z1 - z0).translate((0, 0, z0))
        belege.append(dict(seite="wand", element=f"{name} {H.get('id', '')}: z {z0:.2f}..{z1:.2f} m, Ausladung {a_:.2f} m vor dem Modellquerschnitt, {wo}",
                           quelle=f"dichte Wolke: Rest am Modell ({H['punkte']} Punkte), Ausladung = Median der aeusseren Punkte je Sektor, Streuung {m['rest']} m (tools/wolke_rest.py)",
                           hinweis="ANNAHME: Rechteckprofil (kein Gesimsprofil, Unterseite waagrecht), voll; nur gebaut, wo die Wolke Punkte hat - uebrige Seiten FEHLEN (nicht gespiegelt); Profil/Hoehen aus Fotokanten nachmessen (offen)"))
    return koerper, belege


def stabkoerper_aus_wolkenrest(koerper, datei, nseg=16):
    """Schlanker hoher Koerper (Stange, Fiale, Schornstein, Helmstange) aus tools/wolke_rest.py, Form 'stab': lotrechte Achse (x, y), gemessenes Radiusprofil r(z) in 0,25-m-Scheiben
    als Kegelstuempfe. Unten um 0,4 m bis an das Modell verlaengert (Wolke naeher als 0,35 m am Modell zaehlt nicht zum Rest). Guard: Radius mindestens das halbe Druck-Mindestmass
    (MINMM x SCALE, Vorgabe 0,8 mm x 87 = 3,5 cm) - duennere Staebe waeren nicht druckbar (im Beleg)."""
    belege = []; rmin = 0.5 * float(os.environ.get("MINMM", "0.8")) * float(os.environ.get("SCALE", "87")) / 1000.0
    for H in _wolkenrest_haufen(datei, ("stab",)):
        m = H["mass"]; P = [[float(z), max(float(r), rmin)] for z, r, _ in (m.get("profil") or [])]; x, y = float(m["x"]), float(m["y"])
        if len(P) < 2: P = [[float(m["z0"]), max(float(m["r"]), rmin)], [float(m["z1"]), max(float(m["r"]), rmin)]]
        z_u = max(float(m["z0"]) - 0.4, 0.0); teile = [M.cylinder(P[0][0] - z_u + 0.005, P[0][1], P[0][1], nseg).translate((x, y, z_u))]
        for (za, ra), (zb, rb) in zip(P[:-1], P[1:]): teile.append(M.cylinder(zb - za + 0.005, ra, rb, nseg).translate((x, y, za)))
        teile.append(M.cylinder(max(float(m["z1"]) - P[-1][0], 0.02), P[-1][1], P[-1][1], nseg).translate((x, y, P[-1][0]))); koerper = koerper + M.batch_boolean(teile, OpType.Add)
        belege.append(dict(seite="wand", element=f"Stab {H.get('id', '')} bei x {x:.2f} y {y:.2f}: z {z_u:.2f}..{float(m['z1']):.2f} m, Radius {float(np.median([p[1] for p in P])):.2f} m",
                           quelle=f"dichte Wolke: Rest am Modell ({H['punkte']} Punkte), Achse = Ausgleichsgerade, Radius = mittlerer Achsabstand je 0,25-m-Scheibe, Streuung {m['rest']} m, Neigung {m.get('neigung_grad')} Grad (tools/wolke_rest.py)",
                           hinweis="ANNAHME: runder Querschnitt, lotrecht, voll, unten 0,4 m bis an das Modell verlaengert" + (f"; Radius auf Druck-Mindestmass {rmin:.3f} m angehoben (gemessen {m['r']} m)" if float(m["r"]) < rmin else "") + "; Kopf/Knauf nur, soweit die Wolke ihn zeigt"))
    return koerper, belege


def wolkenrest_koerper(koerper, datei, nseg=48):
    """SAMMELAUFRUF fuer den Generator (eine Zeile): alle Koerper aus audit/koerper_auto.json (tools/wolke_rest.py, angenommen/verworfen durch tools/koerper_schleife.py) -
    Ring/Band zuerst (Querschnitt des Modells OHNE die uebrigen Wolkenkoerper), dann rund (drehkoerper_aus_wolkenrest), Kasten, Stab. Liefert (koerper, belege)."""
    belege = []
    for f in (ringkoerper_aus_wolkenrest, lambda k, d: drehkoerper_aus_wolkenrest(k, d, nseg), kastenkoerper_aus_wolkenrest, stabkoerper_aus_wolkenrest):
        koerper, b = f(koerper, datei); belege += b
    return koerper, belege
