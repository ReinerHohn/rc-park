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
rc 0 = mindestens ein Paar eingetragen, 3 = keins (nichts geaendert).
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
        st = {}
        for f in FORMEN:
            if f == "gerade": kand = [zt]
            elif f == "rund": kand = [zt - a] if zt - a > zs + 0.05 else []
            elif f == "stich": kand = list(np.arange(max(zs + 0.05, zt - a + 0.02), zt - 0.04, 0.02))
            elif f == "korb": kand = [z_ for z_ in np.arange(max(zs + 0.05, zt - 1.5 * a), zt - 0.04, 0.02) if abs(zt - z_ - a) > 0.01]   # Ellipse gedrueckt ODER ueberhoeht (senkrechter Ansatz)
            else: kand = list(np.arange(max(zs + 0.05, zt - 1.5 * a), zt - a - 0.02, 0.02))     # spitz: Pfeil bis 1,5 x halbe Breite
            for zk in kand:
                P_ = _ohne_innen(umriss(f, uL, uR, zs, zk, zt, schritt=0.02), innen); s_ = stuetze(B, P_, thr)
                if s_ > st.get(f, ((-1, -1), 0, 0))[0]: st[f] = (s_, float(zk), len(P_))
        if not st: continue
        top = max(v[0] for v in st.values())
        if best is None or top > best[0]: best = (top, zt, st)
    if best is None: return dict(fehler="keine Scheitelkante / keine Formfamilie passt")
    top, zt, st = best; p_ = top[0]; n_ = max(v[2] for v in st.values())
    tol = max(GLEICH * p_, 2.0 * np.sqrt(p_ * (1 - p_) / max(n_, 1)))     # Gleichstand = innerhalb 2 Standardfehlern des Anteils: die reichere Form (freier Kaempfer) muss klar mehr tragen
    form = next(f for f in ("rund", "gerade", "stich", "korb", "spitz") if f in st and st[f][0][0] >= p_ - tol)   # einfachste Form im Gleichstand
    zk = st[form][1]; an = st[form][0][0]
    r = dict(u0=round(uL, 3), u1=round(uR, 3), z0=round(zs, 3), z1=round(zt, 3), bogen=dict(form=form, kaempfer=round(zk, 3), scheitel=round(zt, 3)),
             anteil=round(an, 2), stuetzen={f: round(v[0][0], 2) for f, v in st.items()}, kante_schwelle=round(thr, 2))
    if an < anteil_min: r["fehler"] = f"nur {an:.0%} des Umrisses auf Bildkanten (< {anteil_min:.0%})"
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


def tiefen(npz, nische, fenster, ring=(0.1, 0.4), min_gut=0.3):
    """Nischentiefe (Nischenring gegen Wandring) und Fenstertiefe (Fenster gegen Nischengrund) aus dem Sweep (negativ = hinter). Werte None = nicht messbar."""
    w, g = npz["w"], npz["gut"].astype(bool); R = (float(npz["u0"]), float(npz["z1"]), float(npz["zelle"]), *w.shape)
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
def fassade_auswerten(B, kaesten, npz, a, vorbauten=()):
    """Je Paar Nische + Fenster vermessen. Liefert (eintraege, bericht)."""
    E, br = [], []
    for A, I in paare(zonen(kaesten), a.flaeche_max_anteil):
        r = dict(zone_aussen=[round(x, 2) for x in A[:4]], zone_innen=[round(x, 2) for x in I[:4]], stimmen=[A[4], I[4]])
        if any(min(A[1], v["u1"]) > max(A[0], v["u0"]) and min(A[3], v["z1"]) > max(A[2], v["z0"]) for v in vorbauten): r["urteil"] = "uebersprungen: hinter einem Vorbau"; br.append(r); continue
        f = form_aus_kanten(B, I[:4], anteil_min=a.anteil_min, kante=a.kante); r["fenster"] = f
        if "fehler" in f: r["urteil"] = "kein Fenster: " + f["fehler"]; br.append(r); continue
        n = form_aus_kanten(B, A[:4], innen=(f["u0"], f["u1"], f["z0"], f["z1"]), anteil_min=a.anteil_min, kante=a.kante); r["nische"] = n
        t = tiefen(npz, n, f) if (npz is not None and "fehler" not in n) else dict(nische=None, fenster=None); r["tiefe"] = t
        e = dict(u0=f["u0"], u1=f["u1"], z0=f["z0"], z1=f["z1"], teiler=[], kaempfer=None, scheiben=1, stimmen_min=int(I[4]), sprossen=[], bogen=f["bogen"],
                 tiefe=-t["fenster"] if t.get("fenster") is not None else a.fenster_tiefe,      # Sweep: negativ = hinter; im Eintrag positive Tiefe ab Nischengrund
                 tiefe_quelle="Ebenen-Sweep (Fenster gegen Nischengrund)" if t.get("fenster") is not None else f"ANNAHME {a.fenster_tiefe} m (Sweep im Fenster ohne Textur: {t.get('fenster_roh')})",
                 quelle="nischen_fenster: Erkennerzone -> Umriss aus Kanten des 1-cm-Wandbilds -> Tiefe aus dem Ebenen-Sweep")
        if "fehler" in n: r["urteil"] = "Fenster ohne Nische: " + n["fehler"]
        elif t["nische"] is None: r["urteil"] = "Fenster ohne Nische: Nischentiefe nicht messbar (zu wenig sichere Sweep-Zellen)"
        elif t["nische"] > -a.nische_min: r["urteil"] = f"Fenster ohne Nische: Nischenflaeche nur {t['nische']:+.2f} m gegen die Wand (flach, < {a.nische_min} m)"
        else:
            e["nische"] = dict(u0=n["u0"], u1=n["u1"], z0=n["z0"], z1=n["z1"], bogen=n["bogen"], tiefe=round(-t["nische"], 3), tiefe_quelle="Ebenen-Sweep (Nischenring gegen Wandring)")
            if abs(e["z0"] - n["z0"]) < 0.03: e["z0"] = n["z0"]                # gleiche Sohlbank: Fenster sitzt auf dem Nischengrund (Kanten liegen <= 3 cm auseinander)
            r["urteil"] = f"NISCHE {n['u1'] - n['u0']:.2f} m ({n['bogen']['form']}, {-t['nische']:.2f} tief) + FENSTER {f['u1'] - f['u0']:.2f} m ({f['bogen']['form']})"
        E.append(e); br.append(r)
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
        neu, br = fassade_auswerten(B, k, npz, a, VB.get(fid, ()))
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
    print(f"-> {ziel}: {n_paare} Fenster mit Nische"); return 0 if n_paare else 3


if __name__ == "__main__": sys.exit(main())
