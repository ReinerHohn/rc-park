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


def spitzbogen(halb, kaempfer, scheitel, unten=-0.6, nseg=24):
    """Querschnitt (quer, hoch) eines Spitzbogens aus zwei Kreisboegen: halbe lichte Breite, Kaempferhoehe, Scheitelhoehe; Pfeiler bis 'unten'."""
    h = scheitel - kaempfer; r = (halb * halb + h * h) / (2 * halb); w0 = np.arcsin(h / r)
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
    def fenster(self, u0, u1, z0, z1, w, tiefe=0.12, teiler=(), kaempfer=None, b=0.07, rahmen=0.05):
        """Rechteckfenster in einer Wandflaeche bei w: liefert (abzug, zusatz). Nische 'tiefe' tief; Rahmen, Pfosten (teiler = u-Lagen) und Kaempfer (z) 'b' breit,
        5 cm hinter der Wandflaeche (so misst pruefstand.ebene_oeffnungen mit tiefe 0,03 die volle Nischenbreite). koerper = koerper - abzug + zusatz."""
        v0, v1 = w - tiefe - 0.01, w - 0.05; K_ = self.kasten; e = 0.005          # e: Rahmen greifen 5 mm in die Laibung (deckungsgleiche Flaechen gaben Splitterkoerper)
        zus = K_(u0 - e, u0 + rahmen, z0 - e, z1 + e, v0, v1) + K_(u1 - rahmen, u1 + e, z0 - e, z1 + e, v0, v1) + K_(u0 - e, u1 + e, z0 - e, z0 + rahmen, v0, v1) + K_(u0 - e, u1 + e, z1 - rahmen, z1 + e, v0, v1)
        for t_ in teiler: zus = zus + K_(t_ - b / 2, t_ + b / 2, z0 - e, z1 + e, v0, v1)
        if kaempfer: zus = zus + K_(u0 - e, u1 + e, kaempfer - b / 2, kaempfer + b / 2, v0, v1)
        return K_(u0, u1, z0, z1, w - tiefe, w + 0.02), zus
    def stab(self, p, q, b, w0, w1):
        """Gerader Stab von p = (u, z) nach q = (u, z), Breite b, von w0 bis w1 vor der Wand (Zeiger, Ziffernstriche, Leisten)."""
        p = np.array(p, float); q = np.array(q, float); d = q - p; d = d / np.linalg.norm(d); s = np.array([-d[1], d[0]]) * b / 2
        return self.huelle([(c[0], c[1], w_) for c in (p + s, p - s, q + s, q - s) for w_ in (w0, w1)])
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
            if f.get("stimmen_min", 0) < min_stimmen: continue
            sonde = W.kasten(f["u0"], f["u1"], f["z0"], f["z1"], 0.03, 0.08)
            if (koerper ^ sonde).volume() > 0.2 * sonde.volume(): continue
            ab, zu = W.fenster(f["u0"], f["u1"], f["z0"], f["z1"], 0.0, tiefe=tiefe, teiler=f.get("teiler", ()), kaempfer=f.get("kaempfer")); koerper = koerper - ab + zu; n_ += 1
        if n_: belege.append(dict(seite="wand", element=f"{n_} Fenster Fassade {fid} (automatisch erkannt)", quelle="OWLv2 auf dem Mehrfoto-Ortho (fassade_ortho.py -> fassade_parsing.py -> fenster_aus_parsing.py), Fotos " + ", ".join(F.get("fotos", [])[:3]),
                                  hinweis="ERKENNUNG, am Bild fenster_<id>.jpg pruefen; Nischentiefe und Rahmenbreiten ANNAHME"))
    return koerper, belege


def massstab(koerper, faktor, drehpunkt): return koerper.translate((-drehpunkt[0], -drehpunkt[1], -drehpunkt[2])).scale((faktor, faktor, faktor)).translate(drehpunkt)


def stl_schreiben(model, pfad, kopf=b"rcpark"):
    """Binaeres STL; Ecken auf 1 Mikrometer verschweisst, entartete Dreiecke entfernt (sonst fallen Splitter als Einzelkoerper heraus)."""
    import os
    mesh = model.to_mesh(); V = np.array(mesh.vert_properties)[:, :3]; F = np.asarray(mesh.tri_verts)
    vq, inv = np.unique(np.round(V.astype(np.float64), 3), axis=0, return_inverse=True); F = inv.ravel()[F]; V = vq.astype(np.float32)
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]; tri = V[F]; nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]); nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    rec = np.zeros(len(F), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]); rec["n"], rec["v"] = nrm, tri; os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "wb") as f: f.write(kopf.ljust(80, b" ")); f.write(np.uint32(len(F)).tobytes()); f.write(rec.tobytes())
    return len(F)
