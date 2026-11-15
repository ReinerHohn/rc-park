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
    def halbraum_innen(self, koerper):
        """Koerper an der Wandebene abschneiden (alles VOR der Ebene faellt weg)."""
        return koerper.trim_by_plane((-self.n[0], -self.n[1], 0.0), float(-(self.n @ self.a)))


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
