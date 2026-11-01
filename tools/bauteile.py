#!/usr/bin/env python3
"""bauteile.py - Bibliothek der Bauteil-Generatoren (manifold3d), objektunabhaengig.

Diese Funktionen lagen bis 2026-11-01 in `modelle/martinstor_v4_gen.py` und waren damit an ein Bauwerk gebunden, obwohl sie
nichts Bauwerksspezifisches enthalten. Ein Generator soll nur noch sagen WELCHES Teil mit WELCHEN Massen - nicht wie ein
Quader an einer Fassade entsteht.

Zwei Arten:
- freie Funktionen (box, fbox, fcyl, frustum, prism, frei_box): geben ein Manifold zurueck, kennen keinen Zustand
- Klasse `Bau`: haelt die Listen adds/cuts/late, den Massstab (K, MINMM) und die Standard-Halbmasse (hx, hy) und bietet
  die Teile, die mehrere Koerper gleichzeitig hinzufuegen und abziehen (window, quoins, clock)

Alle Masse in Metern; `rel(m)` rechnet eine Relieftiefe so um, dass sie im Druck nicht unter MINMM faellt.
"""
import math, random, json, os
from manifold3d import Manifold as M


def lade_masse(pfad):
    """Masse eines Bauwerks aus JSON laden: {"masse": {"NAME": {"wert": 9.8 | "DB / 2 - 0.8", "quelle": ...}}}.
    Zahlen direkt, Text als Formel ueber die bereits geladenen Namen (Reihenfolge der Datei). Rueckgabe: dict NAME -> float.
    So stehen die Masse als DATEN mit Quelle neben der Masstabelle, statt als Zahlen im Code verstreut zu sein."""
    roh = json.load(open(pfad))["masse"]; w = {}
    for name, eintrag in roh.items():
        v = eintrag["wert"]
        w[name] = float(v) if not isinstance(v, str) else float(eval(v, {"__builtins__": {}}, dict(w)))
    return w


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
