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
try:
    from manifold3d import Manifold as M
except ImportError:                       # Analyse-Umgebungen ohne manifold3d duerfen lade_masse/seite_achsen trotzdem nutzen
    M = None

# Seitenkonvention des Modellrahmens (+x Sued, +y Ost, z oben): je Fassadenseite die Tiefenachse, ihr Vorzeichen nach aussen und die Querachse.
SEITEN = {"nord": ("x", -1.0, "y"), "sued": ("x", 1.0, "y"), "ost": ("y", 1.0, "x"), "west": ("y", -1.0, "x")}
def seite_achsen(seite):
    """(tief, sgn, quer) einer Fassadenseite: Punkte der Seite liegen bei sgn * koordinate[tief] > 0; quer laeuft in der Fassadenebene."""
    return SEITEN[seite.lower()]


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
