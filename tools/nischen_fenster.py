#!/usr/bin/env python3
"""nischen_fenster.py - FENSTER IN NISCHEN als zwei Ebenen aus dem feinen Wandbild + Ebenen-Sweep (21.11.2026, Kettenstufe 'bauplan' nach fenster_tiefe_tor.py).

Anlass (Schwabentor von null, Stadtseite f00): zwei Rundbogenfenster sitzen je in einer flachen Rundbogennische. Der Erkenner (fassade_parsing, OWLv2) meldet beides als
Kasten - die Nische (~2 m breit, 3 Stimmen) und das innere Fenster (~0,6 m, 3-5 Stimmen). Die Kette hatte daraus nur EIN Rechteckfenster gemacht:
  - fenster_aus_parsing nahm keinen der Kaesten (Stimmenschwelle), fenster_tiefe_tor ergaenzte nur innere Kaesten und urteilte ueber den 0,5-m-Ring um das kleine Fenster -
    der liegt aber zum grossen Teil IN der Nische und an ihren unsicheren Laibungskanten (Ring 0,68 < 0,70 links -> nicht ergaenzt, 0,71 rechts -> ergaenzt);
  - die Nische (aeussere Ebene) kam nirgends vor, darum hiess die 0,59 m breite Fensteroeffnung im Handvergleich 'Nische'; Bogenform gab es nicht (Rechteck).
Methode (KERNMETHODE, WANDBILD = BAUPLAN; Erkennen = nur Zone):
 1. ZONEN: Erkennerkaesten 'fenster'/'bogen' (>= --min_stimmen) und die schon gelisteten Fenster; Kaesten mit IoU > 0,5 werden eine Zone.
    PAAR = aeussere Zone, die genau EINE innere Zone enthaelt (innere Mitte drin, >= 90 % ihrer Flaeche drin, Flaeche <= --flaeche_max_anteil der aeusseren).
 2. FORM je Ebene aus den Kanten des 1-cm-Wandbilds (fassade_fein/ortho_fNN.png): Kandidaten = staerkste Spitzen der MEDIAN-Gradientenprofile (Laibungen |d/du|,
    Sohlbank und Scheitel |d/dz|), gesucht je +-25 % der Zonengroesse um die Kastenkante (die Zone sagt nur WO). Mass = Anteil des Umrisses auf Bildkanten
    (Normalengradient > --kante x Rauschen der Zone). Stufe 1 Laibungen + Sohlbank, Stufe 2 Scheitel + Formfamilie (gerade, rund, stich, korb gedrueckt/ueberhoeht,
    spitz; Kaempfer im 2-cm-Raster); die reichere Form gewinnt nur mit > 2 Standardfehlern mehr Anteil. Unter --anteil_min keine Form (kein Urteil ohne Kante).
 3. TIEFE je Ebene aus dem Ebenen-Sweep (fassade/tiefe_fNN.npz, nur sichere Zellen): Nische = Median im Nischenring (Nische ohne Fenster) gegen den Wandring aussen
    (0,1-0,4 m um die Nische); sie gilt nur, wenn sie mindestens --nische_min HINTER der Wand liegt. Fenster = Median im Fenster gegen den Nischengrund; liefert
    der Sweep dort nichts Plausibles (zu wenig sichere Zellen, Glas/Laden ohne Textur: Wert vor der Wand oder > 1 m), steht 'tiefe_quelle': 'ANNAHME ...'.
Ausgabe: fenster_auto.json neu (Eingang als fenster_auto_vor_nischen.json daneben): je Paar EIN Eintrag = Fensteroeffnung (u0,u1,z0,z1, bogen{form,kaempfer,scheitel},
  tiefe) mit 'nische' {u0,u1,z0,z1,bogen,tiefe}; ueberlappende alte Eintraege derselben Fassade fallen weg. Bericht nischen_fenster.json, Bild nischen_fenster_<fid>.jpg.
Aufruf:  nischen_fenster.py <fenster_auto.json> <fassade-ordner (elemente.json, tiefe_fNN.npz, vorbauten_fNN.json)> <fassade_fein-ordner> [--nur f00] [--aus ordner]
rc 0 = mindestens ein Paar oder ein Einzelfenster vermessen, 3 = nichts (nichts geaendert).
NACHTRAG 21.11.2026 spaet (Nutzer "Das ist noch nicht gut", neben_eigen__IMG_20261106_113231: im Modell zwei flache Rechtecke statt Rundbogenfenster):
 Lauf 1121s fand nur EIN Paar - der Erkenner hatte fuer die LINKE Nische keinen Kasten, das linke Fenster (fenster_tiefe_tor) blieb ein Rechteck ohne Nische.
 4. EINZELFENSTER: jedes gelistete Fenster ohne Paar bekommt seinen Umriss/Formfamilie ebenfalls aus den Bildkanten; hat dieselbe Wand ein vermessenes GESCHWISTER
    (Breite, Hoehe, Sohlbank je +-25 %), ist dessen Nische - verschoben - die SUCHZONE fuer eine Nische hier (Umriss und Tiefe nur aus Kanten/Sweep an dieser Stelle).
 5. FORMFAMILIE AUS >= 3 FOTOS: jeder Umriss wird bei fester Lage an den Einzelfoto-Orthos (fassade_fein/ortho_fNN_einzeln/, fassade_ortho --einzeln) geprueft;
    je Foto eine Stimme (einfachste Familie im Gleichstand, nur bei >= --anteil_min Kantenstuetze). Gilt die Familie mit den meisten Stimmen, wenn >= 3; sonst
    bleibt die Wandbild-Form mit 'form_unsicher'. Pruefung des GEBAUTEN: tools/fenster_form_tor.py.
"""
import sys, os, json, argparse, shutil, numpy as np

SUCH = 0.25          # Suchspanne um eine Kastenkante, Anteil der Zonengroesse (der Erkennerkasten trifft die Kante nur ungefaehr: Schwabentor 5-20 %)
GLEICH = 0.03        # Formfamilien mit < 3 % weniger Kantenstuetze gelten als gleich gut -> die einfachere bleibt (rund vor stich/korb/spitz)
FORMEN = ("gerade", "rund", "stich", "korb", "spitz")


# ---------------------------------------------------------------- Bildgradienten im Wandraster
class Bild:
    """Grauwertbild einer Wand (1 Pixel = zelle m; Spalte = (u - u0)/zelle, Zeile = (z1 - z)/zelle) mit Gradient d/du und d/dz."""
    def __init__(self, grau, u0, z1, zelle, glatt=1.5):
        from scipy import ndimage as ndi
        g = ndi.gaussian_filter(np.asarray(grau, np.float32), glatt)
        self.gu = ndi.sobel(g, axis=1) / 8.0; self.gz = -ndi.sobel(g, axis=0) / 8.0      # Zeile waechst nach unten -> d/dz = -d/dZeile
        self.u0, self.z1, self.c = float(u0), float(z1), float(zelle); self.H, self.W = g.shape
        self.belegt = ndi.binary_erosion(np.asarray(grau) > 0, iterations=3)       # 0 = keine Fotozelle (fassade_fein) - dort keine Kanten werten
        G = np.hypot(self.gu, self.gz)[self.belegt]; self.g_med = float(np.median(G)) if G.size else 0.0      # Gradientenmass der GANZEN Wand (Kontrast-Bezug)

    def ij(self, u, z): return (self.z1 - np.asarray(z, float)) / self.c, (np.asarray(u, float) - self.u0) / self.c

    def profil(self, A, u0, u1, z0, z1, achse):
        """MEDIAN von |A| im Kasten je Spalte (achse 'u') oder je Zeile ('z') und die Koordinaten dazu. Median statt Mittel: eine echte Laibung/Sohlbank
        laeuft durch fast alle Zeilen/Spalten, eine schraege Stoerlinie (Mast, Kabel, Ortho-Naht; Schwabentor f00) nur durch wenige."""
        i0, j0 = self.ij(u0, z1); i1, j1 = self.ij(u1, z0)
        i0, i1 = int(np.clip(round(i0), 0, self.H)), int(np.clip(round(i1), 0, self.H)); j0, j1 = int(np.clip(round(j0), 0, self.W)), int(np.clip(round(j1), 0, self.W))
        S = np.abs(A[i0:i1, j0:j1])
        if S.size == 0: return np.zeros(0), np.zeros(0)
        if achse == "u": return np.median(S, axis=0), self.u0 + self.c * np.arange(j0, j1)
        return np.median(S, axis=1), self.z1 - self.c * np.arange(i0, i1)

    def rauschen(self, u0, u1, z0, z1):
        """Median-Gradient der belegten Pixel im Kasten (Bezug fuer 'Kante': glatter Putz ~0,3, Bruchstein mehr)."""
        i0, j0 = self.ij(u0, z1); i1, j1 = self.ij(u1, z0)
        i0, i1 = int(np.clip(round(i0), 0, self.H)), int(np.clip(round(i1), 0, self.H)); j0, j1 = int(np.clip(round(j0), 0, self.W)), int(np.clip(round(j1), 0, self.W))
        m = self.belegt[i0:i1, j0:j1]; G = np.hypot(self.gu[i0:i1, j0:j1], self.gz[i0:i1, j0:j1])[m]
        return float(np.median(G)) if G.size > 0.5 * m.size and G.size else None

    def probe(self, A, u, z):
        from scipy.ndimage import map_coordinates
        i, j = self.ij(u, z); return map_coordinates(A, [np.atleast_1d(i), np.atleast_1d(j)], order=1, mode="nearest")

    def ausschnitt(self, A, u0, u1, z0, z1):
        i0, j0 = self.ij(u0, z1); i1, j1 = self.ij(u1, z0)
        i0, i1 = int(np.clip(i0, 0, self.H)), int(np.clip(i1, 0, self.H)); j0, j1 = int(np.clip(j0, 0, self.W)), int(np.clip(j1, 0, self.W))
        return A[i0:i1, j0:j1]


def umriss(form, uL, uR, zs, zk, zt, schritt=0.01, nur_oben_ab=None):
    """Punkte (u, z) und Normalen (nu, nz) des Umrisses einer Oeffnung: Laibung links/rechts von zs bis Kaempfer zk, oberer Abschluss bis Scheitel zt, Sohlbank bei zs.
    nur_oben_ab: nur der Teil oberhalb dieser Hoehe (Formvergleich)."""
    a = (uR - uL) / 2; m = (uL + uR) / 2; h = zt - zk; P = []
    if form == "gerade": oben = [(uL, zt), (uR, zt)]; zk = zt
    else:
        t = np.linspace(np.pi, 0, max(9, int(np.pi * max(a, h) / schritt)))
        if form == "rund": oben = [(m + a * np.cos(x), zk + a * np.sin(x)) for x in t]
        elif form == "korb": oben = [(m + a * np.cos(x), zk + h * np.sin(x)) for x in t]
        elif form == "stich":
            R = (a * a + h * h) / (2 * h); zc = zt - R; w0 = np.arcsin(min(a / R, 1.0))
            oben = [(m + R * np.sin(x), zc + R * np.cos(x)) for x in np.linspace(-w0, w0, len(t))]
        elif form == "spitz":                                              # zwei Kreisboegen, Mittelpunkte auf Kaempferhoehe (lanzett/gleichseitig je nach h)
            r = (a * a + h * h) / (2 * a); x0 = uL + r; x1 = uR - r; wl = np.arcsin(min(h / r, 1.0))
            oben = [(x0 - r * np.cos(x), zk + r * np.sin(x)) for x in np.linspace(0, wl, len(t) // 2)] + [(x1 + r * np.cos(x), zk + r * np.sin(x)) for x in np.linspace(wl, 0, len(t) // 2)]
        else: raise ValueError(form)
    zug = [(uL, zs), (uL, zk)] + oben + [(uR, zk), (uR, zs), (uL, zs)]
    for (p, q) in zip(zug[:-1], zug[1:]):                               # dicht abtasten, Normale = Tangente gedreht
        p, q = np.array(p), np.array(q); L = np.linalg.norm(q - p)
        if L < 1e-6: continue
        n = max(1, int(L / schritt)); s = np.linspace(0, 1, n, endpoint=False)[:, None]; T = (q - p) / L
        for x in p + s * (q - p): P.append((x[0], x[1], T[1], -T[0]))
    P = np.array(P)
    if nur_oben_ab is not None: P = P[P[:, 1] >= nur_oben_ab - 1e-9]
    return P


def spitzen(prof, achse, lo, hi, k=3, abstand=0.03):
    """Lagen der k staerksten Spitzen eines Profils im Bereich [lo, hi] (Mindestabstand 'abstand' m; achse = Koordinate je Profilwert)."""
    m = np.flatnonzero((achse >= lo) & (achse <= hi)); out = []
    for i in m[np.argsort(-prof[m])]:
        if all(abs(achse[i] - x) >= abstand for x in out): out.append(float(achse[i]))
        if len(out) == k: break
    return out


def stuetze(B, P, schwelle):
    """Kantenstuetze eines Umrisses: (Anteil der Umrisspunkte P (u, z, nu, nz) mit Normalengradient > schwelle, Mittel des Normalengradienten)."""
    if len(P) == 0: return 0.0, 0.0
    v = np.abs(B.probe(B.gu, P[:, 0], P[:, 1]) * P[:, 2] + B.probe(B.gz, P[:, 0], P[:, 1]) * P[:, 3]); ok = B.probe(B.belegt.astype(np.float32), P[:, 0], P[:, 1]) > 0.5
    if ok.mean() < 0.8: return 0.0, 0.0                                   # Umriss liegt zu > 20 % ausserhalb der Fotozellen - kein Urteil
    return float((v[ok] > schwelle).mean()), float(v[ok].mean())


def _ohne_innen(P, innen):
    """Umrisspunkte ohne das Stueck vor/an einem inneren Fenster (dessen Kanten gehoeren nicht zur Nische)."""
    if innen is None: return P
    return P[~((P[:, 0] > innen[0] - 0.04) & (P[:, 0] < innen[1] + 0.04) & (P[:, 1] < innen[3] + 0.04))]


def form_aus_kanten(B, kasten, innen=None, anteil_min=0.5, kante=4.0, k=5):
    """Gestalt einer Oeffnung/Nische aus den Bildkanten in der Zone 'kasten' (u0, u1, z0, z1); die Zone sagt nur WO.
    Kandidaten je Kante: die k staerksten Spitzen der Median-Gradientenprofile im Suchbereich (Laibungen |d/du| im unteren Teil, Sohlbank |d/dz| quer,
    Scheitel |d/dz| in der Mitte). Gewertet wird immer der Anteil des Umrisses auf Bildkanten (Normalengradient > kante x Rauschen der Zone) - eine
    Stoerlinie traegt so nur ihre Kreuzungspunkte bei. Stufe 1: Laibungen + Sohlbank am unteren, geraden Teil; Stufe 2: Scheitel, Formfamilie, Kaempfer am
    ganzen Umriss. innen = Kasten eines inneren Fensters: Suchbereiche und Umriss sparen ihn aus.
    Liefert dict(u0, u1, z0, z1, bogen{form, kaempfer, scheitel}, anteil, stuetzen{form: anteil}) und 'fehler', wenn anteil < anteil_min."""
    u0, u1, z0, z1 = kasten; w, h = u1 - u0, z1 - z0
    rs = B.rauschen(u0 - SUCH * w, u1 + SUCH * w, z0 - SUCH * h, z1 + SUCH * h)
    if rs is None: return dict(fehler="Zone ohne Fotozellen im Wandbild")
    thr = kante * max(rs, 0.05)
    pu, au = B.profil(B.gu, u0 - SUCH * w, u1 + SUCH * w, z0 + 0.1 * h, z0 + 0.5 * h, "u")
    li_hi, re_lo = u0 + SUCH * w, u1 - SUCH * w
    if innen is not None: li_hi = min(li_hi, innen[0] - 0.08); re_lo = max(re_lo, innen[1] + 0.08)     # > Aussparung 4 cm + Glaettung: sonst faellt eine Laibung in die Aussparung und zaehlt nicht mit
    UL = spitzen(pu, au, u0 - SUCH * w, li_hi, k); UR = spitzen(pu, au, re_lo, u1 + SUCH * w, k)
    if not UL or not UR: return dict(fehler="keine Laibungskanten")
    if innen is None: pz, az = B.profil(B.gz, u0 + 0.15 * w, u1 - 0.15 * w, z0 - SUCH * h, z1 + SUCH * h, "z")
    else:                                                                 # Sohlbank der Nische neben dem Fenster
        pa, az = B.profil(B.gz, u0 + 0.05 * w, innen[0] - 0.04, z0 - SUCH * h, z1 + SUCH * h, "z"); pb, _ = B.profil(B.gz, innen[1] + 0.04, u1 - 0.05 * w, z0 - SUCH * h, z1 + SUCH * h, "z")
        pz = np.maximum(pa, pb) if pa.size and pb.size and len(pa) == len(pb) else (pa if pa.size else pb)
    ZS = spitzen(pz, az, z0 - SUCH * h, z0 + SUCH * h, k)
    if not ZS: return dict(fehler="keine Sohlbankkante")
    zh = z0 + 0.5 * h; best = None                                         # Stufe 1: Rechteck-Unterteil (Laibungen bis zur Kastenmitte + Sohlbank)
    for uL in UL:
        for uR in UR:
            if uR - uL < 0.1: continue
            for zs in ZS:
                if zh - zs < 0.1: continue
                P = umriss("gerade", uL, uR, zs, zh, zh, schritt=0.02); s_ = stuetze(B, _ohne_innen(P[P[:, 1] < zh - 0.005], innen), thr)
                if best is None or s_ > best[0]: best = (s_, uL, uR, zs)
    if best is None: return dict(fehler="keine Laibungen/Sohlbank")
    _, uL, uR, zs = best; a = (uR - uL) / 2; mitte = (uL + uR) / 2
    pm, am = B.profil(B.gz, mitte - 0.15 * a, mitte + 0.15 * a, z0 - SUCH * h, z1 + SUCH * h, "z")
    ZT = spitzen(pm, am, z1 - SUCH * h if innen is None else max(z1 - SUCH * h, innen[3] + 0.05), z1 + SUCH * h, k)
    best = None                                                            # Stufe 2: Scheitel + Formfamilie + Kaempfer am ganzen Umriss
    for zt in ZT:
        if zt - zs < 0.2: continue
        st = familien(B, uL, uR, zs, zt, thr, innen)
        if not st: continue
        top = max(v[0] for v in st.values())
        if best is None or top > best[0]: best = (top, zt, st)
    if best is None: return dict(fehler="keine Scheitelkante / keine Formfamilie passt")
    top, zt, st = best; form = waehle(st); zk = st[form][1]; an = st[form][0][0]
    r = dict(u0=round(uL, 3), u1=round(uR, 3), z0=round(zs, 3), z1=round(zt, 3), bogen=dict(form=form, kaempfer=round(zk, 3), scheitel=round(zt, 3)),
             anteil=round(an, 2), stuetzen={f: round(v[0][0], 2) for f, v in st.items()}, kaempfer_je_form={f: round(v[1], 3) for f, v in st.items()}, kante_schwelle=round(thr, 2))
    if an < anteil_min: r["fehler"] = f"nur {an:.0%} des Umrisses auf Bildkanten (< {anteil_min:.0%})"
    return r


def familien(B, uL, uR, zs, zt, thr, innen=None):
    """Bei FESTEN Laibungen uL/uR, Sohlbank zs und Scheitel zt je Formfamilie den Kaempfer mit der hoechsten Kantenstuetze: {form: ((anteil, mittel), kaempfer, n_punkte)}."""
    a = (uR - uL) / 2; st = {}
    for f in FORMEN:
        if f == "gerade": kand = [zt]
        elif f == "rund": kand = [zt - a] if zt - a > zs + 0.05 else []
        elif f == "stich": kand = list(np.arange(max(zs + 0.05, zt - a + 0.02), zt - 0.04, 0.02))
        elif f == "korb": kand = [z_ for z_ in np.arange(max(zs + 0.05, zt - 1.5 * a), zt - 0.04, 0.02) if abs(zt - z_ - a) > 0.01]   # Ellipse gedrueckt ODER ueberhoeht (senkrechter Ansatz)
        else: kand = list(np.arange(max(zs + 0.05, zt - 1.5 * a), zt - a - 0.02, 0.02))     # spitz: Pfeil bis 1,5 x halbe Breite
        for zk in kand:
            P_ = _ohne_innen(umriss(f, uL, uR, zs, zk, zt, schritt=0.02), innen); s_ = stuetze(B, P_, thr)
            if s_ > st.get(f, ((-1, -1), 0, 0))[0]: st[f] = (s_, float(zk), len(P_))
    return st


def waehle(st):
    """Einfachste Formfamilie im Gleichstand mit der besten (Gleichstand = innerhalb 2 Standardfehlern des Anteils: die reichere Form mit freiem Kaempfer muss klar mehr tragen)."""
    p_ = max(v[0] for v in st.values())[0]; n_ = max(v[2] for v in st.values())
    tol = max(GLEICH * p_, 2.0 * np.sqrt(p_ * (1 - p_) / max(n_, 1)))
    return next(f for f in ("rund", "gerade", "stich", "korb", "spitz") if f in st and st[f][0][0] >= p_ - tol)


# ---------------------------------------------------------------- Formfamilie aus >= 3 Einzelfotos (KERNMETHODE: Formfamilie nie aus einem Bild)
MIN_FOTOS = 3


def einzelbilder(ordner, fid, rast, kasten, rand=1.0):
    """Einzelfoto-Orthos derselben Wand (fassade_ortho.py --einzeln: ortho_<fid>_einzeln/<foto>.png, gleiches Raster wie das Wandbild), auf 'kasten' (u0,u1,z0,z1) + rand
    zugeschnitten (Speicher: 40 Fotos x 5 Mio. Pixel passen sonst nicht). Liefert [(foto, Bild)]."""
    import cv2, glob
    d = os.path.join(ordner, f"ortho_{fid}_einzeln"); out = []
    if not os.path.isdir(d): return out
    u0, z1, c = rast; U0, U1, Z0, Z1 = kasten[0] - rand, kasten[1] + rand, kasten[2] - rand, kasten[3] + rand
    for p in sorted(glob.glob(os.path.join(d, "*.png"))):
        g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if g is None: continue
        i0, i1 = int(max(0, (z1 - Z1) / c)), int(min(g.shape[0], (z1 - Z0) / c)); j0, j1 = int(max(0, (U0 - u0) / c)), int(min(g.shape[1], (U1 - u0) / c))
        if i1 - i0 < 10 or j1 - j0 < 10 or not (g[i0:i1, j0:j1] > 0).any(): continue
        out.append((os.path.basename(p)[:-4], Bild(g[i0:i1, j0:j1].copy(), u0 + j0 * c, z1 - i0 * c, c)))
    return out


def form_fotos(bilder, zone, innen=None, kante=4.0, anteil_min=0.5):
    """FORMFAMILIE JE EINZELFOTO: in jedem Einzelfoto-Ortho eigene Umrisssuche in derselben Zone (form_aus_kanten: Laibungen, Sohlbank, Scheitel, Familie);
    eine Stimme nur, wenn der Umriss zu >= anteil_min auf Kanten DIESES Fotos liegt (sonst: Foto zu schraeg, verdeckt, unscharf). Lage je Foto frei - bei fester
    Lage machten 5-10 cm Kastenfehler am 0,6-m-Fenster aus Rund 'gerade' (Schwabentor f00, gemessen). zone = Suchzone (u0,u1,z0,z1) oder Umriss-dict.
    Liefert {form: stimmen}, {foto: form}."""
    K = tuple(zone[k] for k in ("u0", "u1", "z0", "z1")) if isinstance(zone, dict) else tuple(zone[:4]); st_ = {}; je = {}
    for name, B in bilder:
        x = form_aus_kanten(B, K, innen=innen, anteil_min=anteil_min, kante=kante)
        if "fehler" in x: continue
        f = x["bogen"]["form"]; je[name] = f; st_[f] = st_.get(f, 0) + 1
    return st_, je


def form_bestaetigen(r, bilder, zone, innen=None, kante=4.0, anteil_min=0.5):
    """Formfamilie des Wandbild-Umrisses r an den Einzelfotos pruefen (in place). Gilt: die Familie mit den meisten Stimmen, wenn sie >= MIN_FOTOS hat; sonst bleibt die
    Wandbild-Form mit 'form_unsicher' (zu wenige Fotos). Ohne Einzelfotos (alte Laeufe, kein --einzeln) nur Vermerk 'form_fotos': None."""
    if not bilder: r["form_fotos"] = None; return r
    st, je = form_fotos(bilder, zone, innen, kante, anteil_min); r["form_fotos"] = st; r["form_fotos_je"] = je
    if not st: r["form_unsicher"] = "kein Einzelfoto traegt den Umriss"; return r
    alt = r["bogen"]["form"]; best = max(st, key=lambda f: (st[f], f == alt))
    if st[best] < MIN_FOTOS: r["form_unsicher"] = f"Formfamilie nur aus {st[best]} Einzelfoto(s) (< {MIN_FOTOS})"; return r
    if best != alt:
        zk = (r.get("kaempfer_je_form") or {}).get(best)
        if zk is None: r["form_unsicher"] = f"Einzelfotos sagen {best}, im Wandbild kein Kaempfer dafuer"; return r
        r["bogen"] = dict(form=best, kaempfer=zk, scheitel=r["bogen"]["scheitel"]); r["form_wandbild"] = alt
    r["form_quelle"] = f"{st[best]} von {sum(st.values())} Einzelfotos"
    return r


# ---------------------------------------------------------------- Tiefe aus dem Ebenen-Sweep
def maske(npz_raster, o, wachs=0.0):
    """Zellmaske im Sweep-Raster (u0, z1, zelle, Form H x W) fuer einen Umriss o (u0,u1,z0,bogen), um 'wachs' m vergroessert."""
    import cv2
    u0, z1, c, H, W = npz_raster; P = umriss(o["bogen"]["form"], o["u0"], o["u1"], o["z0"], o["bogen"]["kaempfer"], o["bogen"]["scheitel"], schritt=c / 2)
    poly = np.stack([(P[:, 0] - u0) / c, (z1 - P[:, 1]) / c], 1).round().astype(np.int32)
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [poly], 1)
    if wachs > 0: k = 2 * int(round(wachs / c)) + 1; m = cv2.dilate(m, np.ones((k, k), np.uint8))
    return m.astype(bool)


def plausibel(w, g, ring, vor_max=0.2):
    """21.11.2026 spaet (Ursache Nischentiefe rechts 0,05 / links 0,15 bei gleichen Nischen, Schwabentor f00): auf glattem weissem Putz liefert der Sweep viele 'gute'
    Zellen 0,4-2,4 m VOR der Wand (Mehrdeutigkeit ohne Textur; rechte Nische 20 %, linke 13 %), der Median kippt damit nach vorn. Eine Wand mit Nischen hat nichts vor
    der Wandflaeche: Zellen mehr als vor_max vor dem MODALWERT des Wandrings (5-cm-Klassen) zaehlen nicht."""
    v = w[ring & g]
    if v.size < 20: return np.ones_like(g)
    werte, n_ = np.unique(np.round(v / 0.05) * 0.05, return_counts=True); modal = float(werte[np.argmax(n_)])
    return w <= modal + vor_max


def tiefen(npz, nische, fenster, ring=(0.1, 0.4), min_gut=0.3):
    """Nischentiefe (Nischenring gegen Wandring) und Fenstertiefe (Fenster gegen Nischengrund) aus dem Sweep (negativ = hinter). Werte None = nicht messbar."""
    w, g = npz["w"], npz["gut"].astype(bool); R = (float(npz["u0"]), float(npz["z1"]), float(npz["zelle"]), *w.shape)
    g = g & plausibel(w, g, maske(R, nische, ring[1]) & ~maske(R, nische, ring[0]))
    mn = maske(R, nische); mf = maske(R, fenster, wachs=float(npz["zelle"]))
    an = mn & ~mf; wr = maske(R, nische, ring[1]) & ~maske(R, nische, ring[0]); fi = maske(R, fenster)
    q = {k: (float(g[m].mean()) if m.any() else 0.0) for k, m in (("nische", an), ("wand", wr), ("fenster", fi))}
    med = lambda m: float(np.median(w[m & g])) if (m & g).any() else None
    out = dict(sicher=q)
    if q["nische"] >= min_gut and q["wand"] >= min_gut: out["wand_w"] = med(wr); out["nische_w"] = med(an); out["nische"] = round(out["nische_w"] - out["wand_w"], 3)
    else: out["nische"] = None
    if out.get("nische_w") is not None and q["fenster"] >= min_gut:
        d = med(fi) - out["nische_w"]; out["fenster_roh"] = round(d, 3)
        out["fenster"] = round(d, 3) if -1.0 < d < -0.02 else None           # vor dem Nischengrund oder > 1 m dahinter: Sweep ohne Textur (Glas, Laden) - nicht messbar
    else: out["fenster"] = None
    return out


# ---------------------------------------------------------------- Zonen und Paare
def iou(a, b):
    i = max(0.0, min(a[1], b[1]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[2], b[2])); fa = (a[1] - a[0]) * (a[3] - a[2]); fb = (b[1] - b[0]) * (b[3] - b[2])
    return i / max(fa + fb - i, 1e-9)


def zonen(kaesten, iou_min=0.5):
    """Kaesten [(u0,u1,z0,z1,stimmen)] mit IoU > iou_min zu Zonen (Median der Kanten, Stimmen = Maximum) zusammenfassen."""
    Z = []
    for k in sorted(kaesten, key=lambda k: -k[4]):
        for z in Z:
            if iou(z["kaesten"][0], k) > iou_min: z["kaesten"].append(k); break
        else: Z.append(dict(kaesten=[k]))
    return [(*[float(np.median([k[i] for k in z["kaesten"]])) for i in range(4)], max(k[4] for k in z["kaesten"])) for z in Z]


def paare(Z, flaeche_max_anteil=0.5, enthalten=0.9):
    """(aussen, innen) je aeusserer Zone, die genau EINE Gruppe innerer Zonen enthaelt (innere Kaesten, die sich ueberlappen = ein Fenster,
    z. B. Erkennerkasten + alter Listeneintrag mit IoU < 0,5; die Gruppe wird zum Median-Kasten)."""
    fl = lambda b: (b[1] - b[0]) * (b[3] - b[2]); P = []; ueber = lambda a, b: min(a[1], b[1]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[2], b[2])
    for A in Z:
        drin = [B for B in Z if B is not A and fl(B) <= flaeche_max_anteil * fl(A) and A[0] < (B[0] + B[1]) / 2 < A[1] and A[2] < (B[2] + B[3]) / 2 < A[3]
                and max(0, min(A[1], B[1]) - max(A[0], B[0])) * max(0, min(A[3], B[3]) - max(A[2], B[2])) >= enthalten * fl(B)]
        gr = []
        for B in drin:
            g_ = [g for g in gr if any(ueber(B, x) for x in g)]
            for g in g_: gr.remove(g)
            gr.append(sum(g_, []) + [B])
        if len(gr) == 1: P.append((A, gr[0]))
    innere = [id(x) for p in P for x in p[1]]                             # eine Zone, die selbst innen liegt, ist keine Nische (verschachtelte Rahmen)
    return [(A, (*[float(np.median([x[i] for x in G])) for i in range(4)], max(x[4] for x in G))) for A, G in P if id(A) not in innere]


# ---------------------------------------------------------------- Hauptablauf
def _eintrag(f, n, t, stimmen, a, quelle, r):
    """Eintrag fuer fenster_auto.json aus Fensterumriss f, Nischenumriss n (oder None), Tiefen t; setzt r['urteil']."""
    e = dict(u0=f["u0"], u1=f["u1"], z0=f["z0"], z1=f["z1"], teiler=[], kaempfer=None, scheiben=1, stimmen_min=int(stimmen), sprossen=[], bogen=f["bogen"],
             tiefe=-t["fenster"] if t.get("fenster") is not None else a.fenster_tiefe,      # Sweep: negativ = hinter; im Eintrag positive Tiefe ab Nischengrund (bzw. Wand)
             tiefe_quelle=("Ebenen-Sweep (Fenster gegen " + ("Nischengrund)" if n is not None else "Wandring)")) if t.get("fenster") is not None
             else f"ANNAHME {a.fenster_tiefe} m (Sweep im Fenster ohne Textur: {t.get('fenster_roh')}); Bau mindestens Druckmindestmass (bauteile.fenster_aus_json)",
             form_quelle=f.get("form_quelle") or ("ANNAHME: " + f["form_unsicher"] if f.get("form_unsicher") else "nur fusioniertes Wandbild (keine Einzelfoto-Orthos)"),
             quelle=quelle)
    if f.get("form_unsicher"): e["form_unsicher"] = f["form_unsicher"]
    tx = f"FENSTER {f['u1'] - f['u0']:.2f} m ({f['bogen']['form']}, {f.get('form_quelle') or f.get('form_unsicher') or 'Wandbild'})"
    if n is None: r["urteil"] = tx if r.get("urteil") is None else r["urteil"] + "; " + tx; return e
    if "fehler" in n: r["urteil"] = "Fenster ohne Nische: " + n["fehler"] + "; " + tx
    elif t.get("nische") is None: r["urteil"] = "Fenster ohne Nische: Nischentiefe nicht messbar (zu wenig sichere Sweep-Zellen); " + tx
    elif t["nische"] > -a.nische_min: r["urteil"] = f"Fenster ohne Nische: Nischenflaeche nur {t['nische']:+.2f} m gegen die Wand (flach, < {a.nische_min} m); " + tx
    else:
        e["nische"] = dict(u0=n["u0"], u1=n["u1"], z0=n["z0"], z1=n["z1"], bogen=n["bogen"], tiefe=round(-t["nische"], 3), tiefe_quelle="Ebenen-Sweep (Nischenring gegen Wandring)",
                           form_quelle=n.get("form_quelle") or ("ANNAHME: " + n["form_unsicher"] if n.get("form_unsicher") else "nur fusioniertes Wandbild"))
        if abs(e["z0"] - n["z0"]) < 0.03: e["z0"] = n["z0"]                # gleiche Sohlbank: Fenster sitzt auf dem Nischengrund (Kanten liegen <= 3 cm auseinander)
        r["urteil"] = f"NISCHE {n['u1'] - n['u0']:.2f} m ({n['bogen']['form']}, {-t['nische']:.2f} tief) + " + tx
    return e


def tiefe_einzeln(npz, f, ring=(0.1, 0.4), min_gut=0.3):
    """Fenster ohne Nische: Median im Fenster gegen den Wandring (Sweep, negativ = hinter). None = nicht messbar (wie tiefen())."""
    w, g = npz["w"], npz["gut"].astype(bool); R = (float(npz["u0"]), float(npz["z1"]), float(npz["zelle"]), *w.shape)
    fi = maske(R, f); wr = maske(R, f, ring[1]) & ~maske(R, f, ring[0]); g = g & plausibel(w, g, wr)
    if not fi.any() or not wr.any() or g[fi].mean() < min_gut or g[wr].mean() < min_gut: return dict(fenster=None)
    d = float(np.median(w[fi & g]) - np.median(w[wr & g])); return dict(fenster_roh=round(d, 3), fenster=round(d, 3) if -1.0 < d < -0.02 else None)


def _ueber(a, b): return min(a[1], b[1]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[2], b[2])


def fassade_auswerten(B, kaesten, npz, a, vorbauten=(), bilder=None, liste=()):
    """Je Paar Nische + Fenster vermessen; danach jedes schon gelistete Fenster ('liste', fenster_auto.json) ohne Paar: Form aus den Bildkanten, Nische an der Stelle
    eines vermessenen GESCHWISTERS (gleiche Breite/Sohlbank derselben Wand; die Zone kommt vom Geschwister, der Umriss nur aus den Kanten hier). Formfamilie je
    Umriss an den Einzelfotos bestaetigt (form_bestaetigen, >= 3 Fotos). Liefert (eintraege, bericht)."""
    E, br = [], []; kw = dict(kante=a.kante, anteil_min=a.anteil_min); vor = lambda A: any(_ueber(A, (v["u0"], v["u1"], v["z0"], v["z1"])) for v in vorbauten)
    lade = bilder if callable(bilder) else (lambda kasten: list(bilder or ()))     # bilder: Liste [(foto, Bild)] oder Lader(kasten) -> Liste
    for A, I in paare(zonen(kaesten), a.flaeche_max_anteil):
        r = dict(zone_aussen=[round(x, 2) for x in A[:4]], zone_innen=[round(x, 2) for x in I[:4]], stimmen=[A[4], I[4]], art="paar")
        if vor(A): r["urteil"] = "uebersprungen: hinter einem Vorbau"; br.append(r); continue
        f = form_aus_kanten(B, I[:4], anteil_min=a.anteil_min, kante=a.kante); r["fenster"] = f
        if "fehler" in f: r["urteil"] = "kein Fenster: " + f["fehler"]; br.append(r); continue
        bil = lade(A[:4]); form_bestaetigen(f, bil, I[:4], **kw); fi = (f["u0"], f["u1"], f["z0"], f["z1"])
        n = form_aus_kanten(B, A[:4], innen=fi, anteil_min=a.anteil_min, kante=a.kante); r["nische"] = n
        if "fehler" not in n: form_bestaetigen(n, bil, A[:4], innen=fi, **kw)
        t = tiefen(npz, n, f) if (npz is not None and "fehler" not in n) else dict(nische=None, fenster=None); r["tiefe"] = t
        E.append(_eintrag(f, n, t, I[4], a, "nischen_fenster: Erkennerzone -> Umriss aus Kanten des 1-cm-Wandbilds -> Tiefe aus dem Ebenen-Sweep", r)); br.append(r)
    # 21.11.2026 (Nutzer 'Das ist noch nicht gut', Schwabentor f00 Lauf 1121s): das LINKE Rundbogenfenster hatte keinen Nischenkasten im Erkenner -> kein Paar -> blieb Rechteck.
    for q in liste:
        Q = (q["u0"], q["u1"], q["z0"], q["z1"])
        if q.get("bogen") or q.get("nische") or any(_ueber(Q, (x["u0"], x["u1"], x["z0"], x["z1"])) or (x.get("nische") and _ueber(Q, (x["nische"]["u0"], x["nische"]["u1"], x["nische"]["z0"], x["nische"]["z1"]))) for x in E): continue
        r = dict(zone_aussen=[round(x, 2) for x in Q], zone_innen=[round(x, 2) for x in Q], stimmen=[q.get("stimmen_min", 0)] * 2, art="einzeln")
        if vor(Q): r["urteil"] = "einzeln uebersprungen: hinter einem Vorbau"; br.append(r); continue
        f = form_aus_kanten(B, Q, anteil_min=a.anteil_min, kante=a.kante); r["fenster"] = f
        if "fehler" in f: r["urteil"] = "einzeln: Form nicht messbar (bleibt Rechteck): " + f["fehler"]; br.append(r); continue
        fi = (f["u0"], f["u1"], f["z0"], f["z1"]); bf, hf = fi[1] - fi[0], fi[3] - fi[2]; n = None
        gs = [x for x in E if x.get("nische") and abs((x["u1"] - x["u0"]) - bf) <= 0.25 * bf and abs((x["z1"] - x["z0"]) - hf) <= 0.25 * hf and abs(x["z0"] - fi[2]) <= 0.25 * hf]
        if gs:                                                             # Geschwister: dessen Nische, um den Fenstermittelpunkt/die Sohlbank verschoben, ist nur die SUCHZONE
            x = min(gs, key=lambda x: abs(x["z0"] - fi[2])); N = x["nische"]; du = (fi[0] + fi[1] - x["u0"] - x["u1"]) / 2; dz = fi[2] - x["z0"]
            Z_ = (N["u0"] + du, N["u1"] + du, N["z0"] + dz, N["z1"] + dz); r["zone_aussen"] = [round(v, 2) for v in Z_]; r["geschwister"] = [x["u0"], x["u1"], x["z0"], x["z1"]]
            n = form_aus_kanten(B, Z_, innen=fi, anteil_min=a.anteil_min, kante=a.kante); r["nische"] = n
        bil = lade(r["zone_aussen"]); form_bestaetigen(f, bil, Q, **kw)
        if n is not None and "fehler" not in n: form_bestaetigen(n, bil, r["zone_aussen"], innen=fi, **kw)
        if n is not None and "fehler" not in n: t = tiefen(npz, n, f) if npz is not None else dict(nische=None, fenster=None)
        else: t = tiefe_einzeln(npz, f) if npz is not None else dict(fenster=None); t.setdefault("nische", None)
        r["tiefe"] = t
        E.append(_eintrag(f, n, t, q.get("stimmen_min", 0), a, "nischen_fenster (einzeln" + (", Nischenzone vom Geschwister" if n is not None else "") + "): Listenfenster -> Umriss aus Kanten des 1-cm-Wandbilds -> Tiefe aus dem Ebenen-Sweep", r)); br.append(r)
    return E, br


def kontrollbild(grau, rast, br, pfad, rand=1.0):
    import cv2
    if not br: return
    U0 = min(r["zone_aussen"][0] for r in br) - rand; U1 = max(r["zone_aussen"][1] for r in br) + rand; Z0 = min(r["zone_aussen"][2] for r in br) - rand; Z1 = max(r["zone_aussen"][3] for r in br) + rand
    u0, z1, c = rast; j0, j1 = int(max(0, (U0 - u0) / c)), int(min(grau.shape[1], (U1 - u0) / c)); i0, i1 = int(max(0, (z1 - Z1) / c)), int(min(grau.shape[0], (z1 - Z0) / c))
    im = cv2.cvtColor(np.ascontiguousarray(grau[i0:i1, j0:j1]).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    def zeichne(o, farbe):
        P = umriss(o["bogen"]["form"], o["u0"], o["u1"], o["z0"], o["bogen"]["kaempfer"], o["bogen"]["scheitel"])
        pts = np.stack([(P[:, 0] - u0) / c - j0, (z1 - P[:, 1]) / c - i0], 1).round().astype(np.int32); cv2.polylines(im, [pts], False, farbe, 2)
    for r in br:
        a_ = r["zone_aussen"]; cv2.rectangle(im, (int((a_[0] - u0) / c) - j0, int((z1 - a_[3]) / c) - i0), (int((a_[1] - u0) / c) - j0, int((z1 - a_[2]) / c) - i0), (160, 160, 160), 1)
        if "fehler" not in (r.get("nische") or {"fehler": 1}): zeichne(r["nische"], (0, 200, 255))
        if "fehler" not in (r.get("fenster") or {"fehler": 1}): zeichne(r["fenster"], (0, 0, 255))
        cv2.putText(im, r["urteil"][:60], (int((a_[0] - u0) / c) - j0, max(15, int((z1 - a_[3]) / c) - i0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 120, 0), 1)
    cv2.imwrite(pfad, im)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("fenster"); ap.add_argument("ordner"); ap.add_argument("fein")
    ap.add_argument("--nur", nargs="*"); ap.add_argument("--aus", help="Ausgabeordner (Standard: neben fenster_auto.json, Datei wird ersetzt)")
    ap.add_argument("--min_stimmen", type=int, default=2, help="Erkennerkaesten ab so vielen Stimmen sind ZONE (die Form entscheiden Kanten + Tiefe)")
    ap.add_argument("--anteil_min", type=float, default=0.5, help="ANNAHME: mindestens die Haelfte des Umrisses liegt auf einer Bildkante")
    ap.add_argument("--kante", type=float, default=4.0, help="ANNAHME: Kante = Normalengradient > 4 x Median-Gradient (Rauschen) der Zone")
    ap.add_argument("--nische_min", type=float, default=0.05, help="Nische gilt ab so viel m hinter der Wand (= ein Sweep-Schritt 5 cm)")
    ap.add_argument("--flaeche_max_anteil", type=float, default=0.5); ap.add_argument("--fenster_tiefe", type=float, default=0.12, help="ANNAHME, wenn der Sweep im Fenster nichts misst (wie bauteile.fenster_aus_json)")
    a = ap.parse_args()
    import cv2
    aus = a.aus or os.path.dirname(os.path.abspath(a.fenster)); os.makedirs(aus, exist_ok=True)
    J = json.load(open(a.fenster)); E = json.load(open(os.path.join(a.ordner, "elemente.json")))["fassaden"]
    FF = {F["id"]: F for F in json.load(open(os.path.join(a.fein, "fassaden.json")))["fassaden"]}
    VB = {}; vj_ = os.path.join(os.path.dirname(os.path.abspath(a.fenster)), "vorbauten_auto.json")
    if os.path.exists(vj_):
        for F_ in json.load(open(vj_)).get("fassaden", []):
            VB[F_["id"]] = [dict(u0=g_["u0"], u1=g_["u1"], z0=min(g_["z0"], (g_.get("galerie") or {}).get("z_fuss") or g_["z0"]), z1=g_["z1"]) for g_ in F_["gruppen"]]
    bericht = {}; n_paare = 0
    for fid, F in J.items():
        if not isinstance(F, dict) or "fenster" not in F or (a.nur and fid not in a.nur): continue
        png = os.path.join(a.fein, f"ortho_{fid}.png")
        if fid not in FF or not os.path.exists(png): bericht[fid] = "kein feines Wandbild"; continue
        rs = FF[fid]["raster"]; grau = cv2.imread(png, cv2.IMREAD_GRAYSCALE); B = Bild(grau, rs["u0"], rs["z1"], rs["zelle"])
        nz = os.path.join(a.ordner, f"tiefe_{fid}.npz"); npz = dict(np.load(nz)) if os.path.exists(nz) else None
        k = [(e["u0"], e["u1"], e["z0"], e["z1"], e.get("stimmen", 0)) for e in (E.get(fid) or {}).get("elemente", []) if e.get("klasse") in ("fenster", "bogen") and e.get("stimmen", 0) >= a.min_stimmen]
        k += [(q["u0"], q["u1"], q["z0"], q["z1"], q.get("stimmen_min", a.min_stimmen)) for q in F["fenster"]]
        bil = lambda kasten, fid=fid, rs=rs: einzelbilder(a.fein, fid, (rs["u0"], rs["z1"], rs["zelle"]), kasten)     # je Zone zugeschnitten laden (Speicher)
        neu, br = fassade_auswerten(B, k, npz, a, VB.get(fid, ()), bil, list(F["fenster"]))
        bericht[fid] = br
        if not neu: continue
        ub = lambda q: (q.get("nische") or q)
        F["fenster"] = [q for q in F["fenster"] if not any(min(q["u1"], ub(x)["u1"]) > max(q["u0"], ub(x)["u0"]) and min(q["z1"], ub(x)["z1"]) > max(q["z0"], ub(x)["z0"]) for x in neu)] + neu
        n_paare += sum(1 for x in neu if x.get("nische")); kontrollbild(grau, (rs["u0"], rs["z1"], rs["zelle"]), br, os.path.join(aus, f"nischen_fenster_{fid}.jpg"))
        for r in br: print(f"{fid}: {r['urteil']}")
    if not any(isinstance(v, list) and v for v in bericht.values()): print("keine Nischen-/Fensterpaare"); json.dump(bericht, open(os.path.join(aus, "nischen_fenster.json"), "w"), indent=1); return 3
    ziel = os.path.join(aus, os.path.basename(a.fenster))
    if os.path.abspath(ziel) == os.path.abspath(a.fenster): shutil.copy(a.fenster, a.fenster[:-5] + "_vor_nischen.json")
    json.dump(J, open(ziel, "w"), indent=1); json.dump(bericht, open(os.path.join(aus, "nischen_fenster.json"), "w"), indent=1)
    n_neu = sum(len(v) for v in bericht.values() if isinstance(v, list) and any("fenster" in r and "fehler" not in r["fenster"] for r in v))
    print(f"-> {ziel}: {n_paare} Fenster mit Nische"); return 0 if (n_paare or n_neu) else 3


if __name__ == "__main__": sys.exit(main())
