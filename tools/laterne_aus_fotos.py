#!/usr/bin/env python3
"""laterne_aus_fotos.py - LATERNE (Dachreiter) auf der Dachspitze aus den Fotos: Eckenzahl der Pfosten und der Haube, Pfostenbreite, Zonenhoehen,
Haubenform, Knauf, Nadel (22.11.2026, Schwabentor-1120).

Anlass: spitze_aus_umriss.py baute die Laterne als runde Zwiebel ("rund" in allen Hoehen); im Foto (eigen__IMG_20261106_113231/113056, eigen__033) steht eine OFFENE
Laterne mit Pfosten, Krempe, facettierter Haube, Knauf und Nadel. URSACHE dort: (1) querschnitt() kennt nur Quadrat gegen Kreis - ein Achteck schwankt in der
sichtbaren Halbbreite nur um 8 % (Quadrat 41 %), unter der Masken-Aufloesung (1600 px, ~20 px/m: 6 cm = 1,3 px); (2) 16 der 17 Fotos sehen die Spitze aus 25 Grad
Blickrichtung (az -23..+1) - die Breite ueber dem Blickwinkel ist dort nicht periodisch messbar (Periode 45 Grad beim Achteck); (3) die Himmelsmaske sieht die
Laterne nur als Umriss - die offenen Pfosten und die Facetten der Haube liegen INNEN.
Darum hier die KANTEN IM INNERN der Silhouette in voller Fotoaufloesung (KERNMETHODE: Form aus Fotokanten mit den SfM-Kameras):

 1. Je Foto (Kameras aus messprotokoll, Achse aus dach_profil.json 'spitze_foto') wird die Zeile quer zur Blickrichtung an der Achse in voller Aufloesung
    abgetastet (Median ueber ein Hoehenband): Helligkeit I(x), Dunkelheit gegen den Himmel s(x) in 0..1, x in Metern quer zur Blickrichtung.
 2. PFOSTEN (offene Zone, Band PF_BAND der Pfostenhoehe - unter der Glocke, ueber dem First): ein regelmaessiges n-Eck mit Umkreis R und Lage phase zeigt
    seine Pfosten bei x = c + R sin(az - alpha_k) (vorne UND hinten sichtbar, weil offen). Bewertung je (n, phase, R): mittlere Dunkelheit an den Pfosten minus
    mittlere Dunkelheit an den Kantenmitten (dort muss Himmel sein). Ein Achteck bei einem Quadrat verliert, weil seine Zwischenpfosten im Himmel liegen.
 3. HAUBE (geschlossen): Facettenkanten sind Helligkeitsstufen (Flaechen verschiedener Neigung zum Licht), Blechnaehte nur duenne Linien -> Stufensignal
    |mean I(x+w) - mean I(x-w)|. Vorhersage nur fuer vordere Ecken, normiert auf die Silhouette: u_k = sin(az - alpha_k) / max|sin|. Gleiche Kontrastbewertung.
 4. Breitenprofil in voller Aufloesung (aeussere Ausdehnung der Dunkelheit) ueber alle Fotos -> Median je Hoehe; Zonen: Pfosten (bis Krempe), Krempe (Breitensprung),
    Haube (Taille -> Bauch -> Hals), Knauf (Maximum ueber dem Hals), Nadel (schmal bis zum obersten dunklen Pixel). Umkreis = Silhouette / mittleres max|sin|.
 5. Formfamilie der Haube je Foto (zwiebel / geschweift / gerade aus dem Breitenprofil); gilt nur, wenn >= MIN_FAMILIE Fotos einig sind.
Ausgabe: Block 'laterne_foto' in audit/dach_profil.json (oder --aus); bauteile.laterne baut daraus (bauteile.dach_aus_profil nimmt ihn, wenn gueltig).
Aufruf: laterne_aus_fotos.py <objekt.json> [--profil audit/dach_profil.json] [--aus datei.json] [--bild datei.jpg] [--min-ppm 25]
rc 0 = gueltig, rc 3 = kein spitze_foto-Block, rc 4 = zu wenig Fotos/keine eindeutige Eckenzahl (Block mit gueltig=false).
"""
import sys, os, json, argparse, math, numpy as np

H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)

# ---- Schwellen (Grund je Zeile; nicht an einem Bauwerk eingestellt) ---------------------------------------------------------------------------
N_KAND = (3, 4, 5, 6, 8, 10, 12, 16)  # gepruefte Eckenzahlen (regelmaessige Vielecke der Laternen/Hauben; Kreis = keine Zahl gewinnt)
PF_BAND = (0.30, 0.45)  # Pfostenband als Anteil der Pfostenhoehe: ueber dem Dachfirst (der steht in der Mitte bis ~25 % hinauf), unter Glocke/Krempen-Untersicht
HB_BAND = (0.1, 0.4)    # Facettenband der Haube als Anteil Bauch -> Hals: obere, vom Himmel beleuchtete Haelfte (unter dem Bauch liegt die Haube im eigenen
                        # Schatten - die Licht/Schatten-Grenze ist eine waagrecht gekruemmte Stufe und taeuschte im ersten Lauf Kanten vor)
MIN_FOTOS = 3           # Formfamilie/Eckenzahl aus >= 3 Fotos (CLAUDE.md)
MIN_FAMILIE = 3
BAUCH_ANTEIL = 0.04     # Zwiebel: Bauch mind. 4 % breiter als die Taille (Breitenstreuung je Foto 2-3 %; 1,1 x war am Schwabentor mit Bauch/Taille 1,095 zu streng)
# gewinnende Eckenzahl: gepaarter t-Wert (Korrelation bestes - zweites n je Foto) ueber dem einseitigen 97,5-%-Quantil der t-Verteilung (Freiheitsgrade = Fotos - 1),
# sonst 'unentschieden' (Fotostreuung statt fester Schwelle)
T975 = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23}
def t_grenze(n_fotos): return T975.get(max(1, n_fotos - 1), 2.2 if n_fotos <= 21 else 2.05 if n_fotos <= 31 else 1.96)
MIN_T = t_grenze(8)     # nur fuer Tests/Anzeige; im Lauf je Fotozahl
STUFE_W_M = 0.10        # Fensterbreite des Stufensignals (Facette ~0,5 m breit, Blechnaht ~1-2 cm -> Naht gibt kaum Stufe)
DUNKEL = 0.5            # Dunkelheit > 0,5 = Bauwerk (halber Weg Himmel -> dunkelster Wert)
NADEL_DUNKEL = 0.3      # duenne Nadel (2-3 px) ist im Foto nur halb dunkel (Mischpixel)
ABW_M = 0.15            # Foto-Ausreisser: Halbbreiten im Median > 15 cm neben dem Median aller Fotos (Profilstreuung guter Fotos 2-5 cm)
NADEL_STREUUNG_M = 0.3  # Nadelende nur gueltig, wenn die Fotos auf 30 cm einig sind (sonst Mischpixel/Ueberbelichtung - Fallback Himmelsmasken-Spitze)
NADEL_FENSTER_M = 0.12  # Nadel/Kreuzstange: Fenster quer um die Knaufmitte (Stange 3-10 cm, Achse/Knaufmitte auf ~5 cm)
MIN_OFFEN = 0.2        # Pfostenband nur verwendbar, wenn >= 20 % zwischen den aeusseren Pfosten Himmel ist (offene Laterne gesehen, nicht verdeckt)


def ecken_x(n, phase, az, R=1.0):
    """Seitliche Lage der Ecken eines regelmaessigen n-Ecks (Umkreis R, Ecke 0 bei Weltwinkel phase, Grad) fuer eine Kamera in Richtung az (Grad, von der Achse aus).
    -> (x [n], vorne [n] bool). x quer zur Blickrichtung (wie spitze_aus_umriss: q = (sin az, -cos az))."""
    a = np.radians(phase + np.arange(n) * 360.0 / n); b = math.radians(az)
    return R * np.sin(b - a), np.cos(a - b) > 1e-6


def kanten_mitten_x(n, phase, az, R=1.0):
    """Mitten der Vieleckseiten (Abstand R cos(pi/n)) - dort darf kein Pfosten/keine Facettenkante sein."""
    a = np.radians(phase + (np.arange(n) + 0.5) * 360.0 / n); b = math.radians(az); r = R * math.cos(math.pi / n)
    return r * np.sin(b - a), np.cos(a - b) > 1e-6


def ecken_bewerten_beide(beob, offen, **kw):
    """ecken_bewerten im Drehsinn der Kameras UND gespiegelt (x -> -x je Foto, gleichwertig az -> -az). Der Drehsinn ist nur bei geschlossenen Koerpern (vordere
    Kanten) messbar; gewinnt der gespiegelte deutlich, stimmt der Drehsinn der Kamera-Azimute nicht mit dem Bild (Seitenverwechslung/Spiegelung - im Ergebnis gemeldet).
    -> (erg, n, abstand, drehsinn 'kameras'|'gespiegelt')."""
    e1 = ecken_bewerten(beob, offen, **kw)
    sp = [dict(B, x=-B["x"][::-1], s=B["s"][::-1], c=-B["c"]) for B in beob]
    e2 = ecken_bewerten(sp, offen, **kw)
    return (*e1, "kameras") if e1[0][e1[1]]["kontrast"] >= e2[0][e2[1]]["kontrast"] else (*e2, "gespiegelt")


def aussen_breite(B, schwelle=None):
    """Breite der aeussersten dunklen Laeufe links und rechts (Pfostenbreite) eines Pfostenbands -> Liste (m)."""
    schwelle = DUNKEL if schwelle is None else schwelle; x, s = B["x"], B["s"]; j = np.where(s > schwelle)[0]; out = []
    if not len(j): return out
    for k0, sg in ((j[0], 1), (j[-1], -1)):
        k = k0
        while 0 <= k + sg < len(x) and s[k + sg] > schwelle: k += sg
        out.append(abs(float(x[k] - x[k0])) + float(x[1] - x[0]))
    return out


def ecken_bewerten(beob, offen, n_kand=N_KAND, phase_schritt=1.0, r_anteile=np.linspace(0.3, 1.0, 36), breite=None):
    """Eckenzahl aus Kantenlagen in mehreren Fotos (ANALYSE DURCH SYNTHESE). beob: Liste dict(az, x [m, Gitter], s [Signal], c [Mitte m], h [Silhouetten-Halbbreite m]).
    Je Hypothese (n, phase[, R]) wird das Signal vorhergesagt und mit dem gemessenen korreliert (Pearson, Mittel ueber die Fotos):
    offen=True (Pfosten): Dunkelheit = Kaesten der Breite 'breite' (Standard: Median der aeusseren Laufbreiten) an x = c + R sin(az - alpha), vorne UND hinten; R frei (Anteil von h).
      Ein Achteck-Modell bei einem Quadrat sagt Pfosten in den Himmel voraus, ein Quadrat-Modell beim Achteck laesst Pfosten aus - beides senkt die Korrelation.
    offen=False (Haube): Stufensignal = Dreiecke (Halbbreite STUFE_W_M) an den vorderen Ecken, normiert u = sin(...)/max|sin| auf die Silhouette (c, h); nur im Inneren
      (|x - c| < 0,92 h; die Silhouette selbst ist keine Facettenkante).
    -> dict(n -> dict(kontrast [Korrelation], phase, R_anteil)), bestes n, Abstand zum zweiten."""
    if offen and breite is None:
        bb = [b for B in beob for b in aussen_breite(B)]; breite = float(np.median(bb)) if bb else 0.1
    erg = {}
    for n in n_kand:
        best = (-np.inf, 0.0, 1.0)
        for ph in np.arange(0.0, 360.0 / n, phase_schritt):
            for ra in (r_anteile if offen else [1.0]):
                ks = []
                for B in beob:
                    x, s = B["x"], B["s"]; xe, ve = ecken_x(n, ph, B["az"])
                    if offen:
                        m = np.zeros_like(x); reg = np.ones(len(x), bool)
                        for p in B["c"] + ra * B["h"] * xe: m = np.maximum(m, (np.abs(x - p) <= breite / 2).astype(float))
                    else:
                        lo, hi = xe.min(), xe.max(); m_ = (lo + hi) / 2; hh = max((hi - lo) / 2, 1e-9); ue = (xe - m_) / hh
                        reg = np.abs(x - B["c"]) < 0.92 * B["h"]; m = np.zeros_like(x)
                        for u in ue[ve & (np.abs(ue) < 0.92)]: m = np.maximum(m, np.clip(1 - np.abs(x - (B["c"] + B["h"] * u)) / STUFE_W_M, 0, 1))
                    a_, b_ = m[reg], s[reg]
                    if a_.std() < 1e-9 or b_.std() < 1e-9: ks.append(0.0); continue
                    ks.append(float(np.corrcoef(a_, b_)[0, 1]))
                k = float(np.mean(ks)) if ks else -np.inf
                if k > best[0]: best = (k, float(ph), float(ra), ks)
        erg[n] = dict(kontrast=round(best[0], 3), phase=round(best[1], 1), R_anteil=round(best[2], 3), einzel=[round(v, 3) for v in (best[3] if len(best) > 3 else [])])
    o = sorted(erg, key=lambda n: -erg[n]["kontrast"])
    # Sicherheit: gepaarter t-Wert der Korrelations-Differenz bestes - zweites n ueber die Fotos (Streuung der Fotos statt fester Schwelle)
    d_ = np.array(erg[o[0]]["einzel"]) - np.array(erg[o[1]]["einzel"]) if len(erg[o[0]]["einzel"]) == len(erg[o[1]]["einzel"]) and len(erg[o[0]]["einzel"]) > 1 else np.array([0.0])
    erg[o[0]]["t"] = round(float(d_.mean() / max(d_.std(ddof=1) if len(d_) > 1 else 1.0, 1e-6) * math.sqrt(len(d_))), 2)
    return erg, o[0], round(erg[o[0]]["kontrast"] - erg[o[1]]["kontrast"], 3)


def stufe(I, x, w):
    """Stufensignal |mittel(I, x..x+w) - mittel(I, x-w..x)| auf dem Gitter x (Facettenkante = Stufe, duenne Naht ~ 0)."""
    dx = float(x[1] - x[0]); k = max(1, int(round(w / dx))); c = np.r_[0.0, np.cumsum(I)]; n = len(I); s = np.zeros(n)
    for i in range(k, n - k): s[i] = abs((c[i + k] - c[i]) - (c[i] - c[i - k])) / k
    return s


def dunkelheit(I):
    """Helligkeit -> Dunkelheit 0 (Himmel) .. 1 (dunkelster Teil); Himmel = 95-%-Wert, dunkel = 5-%-Wert der Zeile."""
    hi, lo = np.percentile(I, 95), np.percentile(I, 5)
    return np.clip((hi - I) / max(hi - lo, 1e-6), 0, 1)


def ausdehnung(s, x, c0=0.0, schwelle=DUNKEL):
    """Aeussere Ausdehnung der Dunkelheit (erste/letzte Stelle > schwelle) -> (links, rechts) oder None."""
    j = np.where(s > schwelle)[0]
    return None if len(j) == 0 else (float(x[j[0]]), float(x[j[-1]]))


def familie_aus_profil(zr):
    """Haubenform aus dem Breitenprofil [(z, halb)] von der Taille (Fuss der Haube) bis zum Hals: 'zwiebel' (Bauch um > BAUCH_ANTEIL breiter als der Fuss, darueber eingezogen),
    'gerade' (monoton fallend, Rest einer Geraden < 4 % der Fussbreite), sonst 'geschweift'. None bei < 5 Hoehen."""
    if len(zr) < 5: return None
    z = np.array([p[0] for p in zr], float); r = np.array([p[1] for p in zr], float); i = int(np.argmax(r))
    if r[i] - r[0] > BAUCH_ANTEIL * r[i] and 0 < i < len(r) - 2 and r[-1] < 0.6 * r[i]: return "zwiebel"
    A = np.c_[z, np.ones_like(z)]; c = np.linalg.lstsq(A, r, rcond=None)[0]; rest = float(np.max(np.abs(A @ c - r)))
    return "gerade" if rest < 0.04 * max(r[0], 1e-6) and np.all(np.diff(r) <= 0.02 * r[0]) else "geschweift"


def zonen_aus_profil(P):
    """Zonen aus dem Median-Breitenprofil [(z, halb)] (aufsteigend, ab dem Fuss der Laterne): Pfosten bis zum Breitensprung (> 1,3 x Pfostenbreite = Krempe),
    Krempe = groesste Breite in 0,5 m ueber dem Sprung, Haubenfuss = schmalste Stelle darueber, Bauch = groesste darueber, Hals = schmalste ueber dem Bauch,
    Knauf = groesste ueber dem Hals, Nadel bis zum Ende. -> dict oder None."""
    if len(P) < 10: return None
    z = np.array([p[0] for p in P], float); r = np.array([p[1] for p in P], float)
    r_pf = float(np.percentile(r[:max(3, len(r) // 3)], 20))                     # Pfostenplateau: unten steht noch der Dachfirst (breiter) im Profil
    j0 = next((i for i in range(len(r)) if r[i] <= 1.1 * r_pf), 0)
    j = next((i for i in range(j0, len(r)) if r[i] > 1.3 * r_pf), None)
    if j is None: return None
    jk = j + int(np.argmax(r[j:][z[j:] <= z[j] + 0.5]))
    jt = jk + int(np.argmin(r[jk:][z[jk:] <= z[jk] + 1.0]))
    jb = jt + int(np.argmax(r[jt:]))
    # Hals: erste Hoehe ueber dem Bauch unter 35 % der Bauchbreite, dann weiter bis zum oertlichen Minimum (nicht das Nadelende: dort wird es wieder schmaler)
    jh = next((i for i in range(jb, len(r)) if r[i] < 0.35 * r[jb]), len(r) - 1)
    while jh + 1 < len(r) and r[jh + 1] <= r[jh] + 1e-9: jh += 1
    jn = jh + int(np.argmax(r[jh:][z[jh:] <= z[jh] + 1.0]))
    return dict(z_pfosten_unten=float(z[j0]), z_pfosten_oben=float(z[j]), r_pfosten_silh=r_pf, z_krempe=float(z[jk]), r_krempe=float(r[jk]), z_taille=float(z[jt]), r_taille=float(r[jt]),
                z_bauch=float(z[jb]), r_bauch=float(r[jb]), z_hals=float(z[jh]), r_hals=float(r[jh]), z_knauf=float(z[jn]), r_knauf=float(r[jn]), i=(j, jk, jt, jb, jh, jn))


# ---- Fotos ---------------------------------------------------------------------------------------------------------------------------------------
def zeile(im, c, sb, A, q, z0, z1, xs, nz=7):
    """Helligkeit quer zur Blickrichtung (x-Gitter xs in m) als Median ueber nz Hoehen zwischen z0 und z1 (volle Fotoaufloesung, bilinear)."""
    import cv2, flaeche_ortho as FO
    rows = []
    for z in np.linspace(z0, z1, nz):
        X = np.c_[A[0] + xs * q[0], A[1] + xs * q[1], np.full(len(xs), z)]; p = FO.projektion(X, c)[0] * sb
        v = cv2.remap(im, p[:, 0].astype(np.float32).reshape(1, -1), p[:, 1].astype(np.float32).reshape(1, -1), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)[0].astype(float)
        aussen = (p[:, 0] < 0) | (p[:, 1] < 0) | (p[:, 0] > im.shape[1] - 1) | (p[:, 1] > im.shape[0] - 1); v[aussen] = np.nan
        rows.append(v)
    R = np.array(rows, float)
    return np.nanmedian(R, 0)


def main(argv=None):
    import cv2, flaeche_ortho as FO
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--profil"); ap.add_argument("--aus"); ap.add_argument("--bild"); ap.add_argument("--min-ppm", type=float, default=25.0)
    ap.add_argument("--root", help="Wurzel fuer fotos_dir (Standard wie flaeche_ortho)")
    a = ap.parse_args(argv)
    if a.root: FO.ROOT = a.root
    od = os.path.dirname(os.path.abspath(a.objekt)); Au = os.path.join(od, "audit"); pp = a.profil or os.path.join(Au, "dach_profil.json")
    try: D = json.load(open(pp))
    except Exception: print("kein Dachprofil", pp); return 3
    SF = D.get("spitze_foto") or {}
    if not SF.get("gueltig") or not SF.get("einzel"): print("kein gueltiger Block spitze_foto (tools/spitze_aus_umriss.py)"); return 3
    from bauteile import spitze_ab
    A = np.array(SF["achse"], float); z_fuss = spitze_ab(SF) or float(SF["profil"][0][0]); z_top = float(SF["spitze_z"]) + 1.5
    _, cams = FO.kameras_laden(a.objekt, fotos={e[0] for e in SF["einzel"]})
    zs = np.round(np.arange(z_fuss, z_top, 0.05), 2); fotos = []
    for nr, (c, pf) in sorted(cams.items()):
        im = cv2.imread(pf, cv2.IMREAD_GRAYSCALE)
        if im is None: continue
        sb = im.shape[1] / (c["cx"] * 2)                                                          # uint8 behalten (17 Fotos x 12 MP; float waeren 0,8 GB)
        C = FO.projektion(np.array([[A[0], A[1], 0.0]]), c)[2]; az = math.degrees(math.atan2(C[1] - A[1], C[0] - A[0])); q = np.array([math.sin(math.radians(az)), -math.cos(math.radians(az))])
        p0 = FO.projektion(np.array([[A[0], A[1], z_fuss + 2]]), c)[0] * sb; p1 = FO.projektion(np.array([[A[0] + q[0], A[1] + q[1], z_fuss + 2]]), c)[0] * sb; ppm = float(np.linalg.norm(p1 - p0))
        if ppm < a.min_ppm: continue
        xs = np.arange(-2.5, 2.5, 0.5 / ppm)
        # Breitenprofil in voller Aufloesung (aeussere Ausdehnung der Dunkelheit je Hoehe; Himmel/Dunkel je Foto aus einem Referenzband ueber die ganze Laterne)
        ref = zeile(im, c, sb, A, q, z_fuss, z_top - 1.0, xs, nz=25); hi = np.nanpercentile(ref, 97); lo = np.nanpercentile(ref, 3)
        dk = lambda I: np.clip((hi - I) / max(hi - lo, 1e-6), 0, 1)
        halb = {}
        for z in zs:
            s = dk(np.nan_to_num(zeile(im, c, sb, A, q, z, z, xs, nz=1), nan=hi)); e_ = ausdehnung(s, xs, schwelle=NADEL_DUNKEL if z > SF.get("krempe_z", z_fuss) + 3 else DUNKEL)
            if e_: halb[float(z)] = (e_[0], e_[1])
        fotos.append(dict(nr=nr, az=az, ppm=ppm, c=c, sb=sb, q=q, xs=xs, dk=dk, halb=halb, im=im, pf=pf))
        print(f"{nr}: az {az:6.1f} ppm {ppm:.0f} Hoehen {len(halb)}")
    if len(fotos) < MIN_FOTOS: return schreiben(D, pp, a, dict(gueltig=False, grund=f"nur {len(fotos)} Fotos mit >= {a.min_ppm} px/m"), 4)
    # Median-Breitenprofil (Halbbreite = halbe Ausdehnung, Mitte = Mitte der Ausdehnung)
    def median_profil(fs):
        P_ = []
        for z in zs:
            v = [(F["halb"][float(z)][1] - F["halb"][float(z)][0]) / 2 for F in fs if float(z) in F["halb"]]
            if len(v) >= MIN_FOTOS: P_.append([float(z), float(np.median(v)), len(v)])
        return P_
    P = median_profil(fotos)
    # Ausreisser-Fotos (falsche Kamera, Laterne hinter Traufe/Giebel, Fremdkoerper): Halbbreiten weichen im Median > ABW_M vom Median aller ab -> raus
    pm = {p[0]: p[1] for p in P}; weg = []
    for F in fotos:
        d_ = [abs((e_[1] - e_[0]) / 2 - pm[z]) for z, e_ in F["halb"].items() if z in pm]
        if not d_ or float(np.median(d_)) > ABW_M: weg.append(F["nr"])
    if weg:
        fotos = [F for F in fotos if F["nr"] not in weg]; print("Ausreisser-Fotos (Breitenprofil):", weg)
        if len(fotos) < MIN_FOTOS: return schreiben(D, pp, a, dict(gueltig=False, grund=f"nach Ausreissern nur {len(fotos)} Fotos", ausreisser=weg), 4)
        P = median_profil(fotos)
    Z = zonen_aus_profil(P)
    if Z is None: return schreiben(D, pp, a, dict(gueltig=False, grund="Zonen (Pfosten/Krempe/Haube/Hals) im Breitenprofil nicht gefunden", profil=P), 4)
    # Nadel: ueber dem Knauf die oberste Hoehe, die durchgehend (Luecken <= 0,15 m) im schmalen Fenster an der Knaufmitte dunkel ist (Mischpixel: NADEL_DUNKEL);
    # nur das Fenster +-NADEL_FENSTER_M, damit Oberleitungen/Draehte weiter seitlich nicht zaehlen. Je Foto, dann Median.
    spitzen = []; nadel_einzel = {}
    for F in fotos:
        e_k = F["halb"].get(round(min(F["halb"], key=lambda z: abs(z - Z["z_knauf"])), 2)) if F["halb"] else None
        if not e_k: continue
        ck = (e_k[0] + e_k[1]) / 2; xw = ck + np.arange(-NADEL_FENSTER_M, NADEL_FENSTER_M, 0.25 / F["ppm"]); top = None; leer = 0
        for z in zs[zs >= Z["z_knauf"]]:
            if float(np.max(F["dk"](np.nan_to_num(zeile(F["im"], F["c"], F["sb"], A, F["q"], z, z, xw, nz=1), nan=255.0)))) > NADEL_DUNKEL: top = float(z); leer = 0
            elif top is not None:
                leer += 1
                if leer > 3: break
        if top is None: continue
        nadel_einzel[F["nr"]] = top
        if Z["z_knauf"] + 0.3 <= top <= zs[-1] - 0.2: spitzen.append(top)     # Nadel ueberhaupt gesehen (nicht nur der Knauf) und Himmel darueber (nicht Suchende)
    # Pfosten: Band PF_BAND der Pfostenzone
    zu_ = Z["z_pfosten_unten"]; zp0 = zu_ + PF_BAND[0] * (Z["z_pfosten_oben"] - zu_); zp1 = zu_ + PF_BAND[1] * (Z["z_pfosten_oben"] - zu_)
    bp, bh = [], []; zu_offen = []
    for F in fotos:
        s = F["dk"](np.nan_to_num(zeile(F["im"], F["c"], F["sb"], A, F["q"], zp0, zp1, F["xs"]), nan=0.0)); e_ = ausdehnung(s, F["xs"])
        if e_:
            inn = (F["xs"] > e_[0]) & (F["xs"] < e_[1]); hell = float(np.mean(s[inn] < 1 - DUNKEL)) if inn.any() else 0.0
            if hell >= MIN_OFFEN: bp.append(dict(az=F["az"], x=F["xs"], s=s, c=(e_[0] + e_[1]) / 2, h=(e_[1] - e_[0]) / 2, nr=F["nr"]))
            else: zu_offen.append(F["nr"])           # kein Himmel zwischen den Pfosten (Glocke/Dach dahinter/verdeckt) -> fuer die Pfostenzahl nicht verwendbar
        zb0, zb1 = Z["z_bauch"] + HB_BAND[0] * (Z["z_hals"] - Z["z_bauch"]), Z["z_bauch"] + HB_BAND[1] * (Z["z_hals"] - Z["z_bauch"])
        I = np.nan_to_num(zeile(F["im"], F["c"], F["sb"], A, F["q"], zb0, zb1, F["xs"]), nan=255.0)
        sd = F["dk"](I); e_ = ausdehnung(sd, F["xs"])
        if e_:
            st = stufe(I, F["xs"], STUFE_W_M); inn = (F["xs"] > e_[0] + STUFE_W_M) & (F["xs"] < e_[1] - STUFE_W_M)
            if inn.sum() > 10:
                st = np.where(inn, (st - st[inn].mean()) / max(st[inn].std(), 1e-6), 0.0) / 10.0
                bh.append(dict(az=F["az"], x=F["xs"], s=st, c=(e_[0] + e_[1]) / 2, h=(e_[1] - e_[0]) / 2, nr=F["nr"]))
    erg = dict(quelle="tools/laterne_aus_fotos.py: Kanten im Inneren der Silhouette in voller Fotoaufloesung (Pfosten gegen Himmel, Facettenstufen der Haube) mit den SfM-Kameras",
               achse=[round(float(A[0]), 3), round(float(A[1]), 3)], z_fuss=round(z_fuss, 2), fotos=[F["nr"] for F in fotos],
               az_bereich=[round(min(F["az"] for F in fotos), 1), round(max(F["az"] for F in fotos), 1)], ausreisser=weg, pfosten_verdeckt=zu_offen,
               profil=[[round(p[0], 2), round(p[1], 3), p[2]] for p in P], zonen={k: round(v, 3) for k, v in Z.items() if k != "i"})
    if len(bp) >= MIN_FOTOS:
        E, n, ab = ecken_bewerten(bp, offen=True); hm = float(np.median([B["h"] for B in bp]))
        # Pfostenbreite: Breite der Dunkelheit (> DUNKEL) um die beiden aeussersten Pfosten je Foto
        br = []
        for B in bp:
            for sg in (-1, 1):
                j = np.where(B["s"] > DUNKEL)[0]; j = j[(B["x"][j] - B["c"]) * sg > 0]
                if not len(j): continue
                k0 = j[-1] if sg > 0 else j[0]; k = k0
                while 0 < k < len(B["x"]) - 1 and B["s"][k - sg] > DUNKEL: k -= sg
                br.append(abs(B["x"][k0] - B["x"][k]))
        b = float(np.median(br)) if br else None; R = E[n]["R_anteil"] * hm
        fpf = float(np.median([np.max(np.abs(ecken_x(n, E[n]["phase"], B["az"])[0])) for B in bp]))      # Silhouette eines n-Ecks in dieser Lage = Umkreis x max|sin|
        erg["pfosten"] = dict(n=n, phase=E[n]["phase"], R=round(R, 3), silh_faktor=round(fpf, 3), breite=None if b is None else round(b, 3), abstand=ab, fotos=len(bp), band=[round(zp0, 2), round(zp1, 2)],
                              kandidaten={str(k): v for k, v in E.items()}, t=E[n].get("t"), t_grenze=t_grenze(len(bp)), eindeutig=bool(E[n].get("t", 0) >= t_grenze(len(bp))))
    if len(bh) >= MIN_FOTOS:
        E, n, ab, ds = ecken_bewerten_beide(bh, offen=False)
        sg = 1 if ds == "kameras" else -1
        f = float(np.median([np.max(np.abs(ecken_x(n, E[n]["phase"], sg * B["az"])[0])) for B in bh]))      # Silhouette = Umkreis x max|sin|
        erg["haube"] = dict(n=n, phase=sg * E[n]["phase"], silh_faktor=round(f, 3), abstand=ab, fotos=len(bh), drehsinn=ds, kandidaten={str(k): v for k, v in E.items()},
                            band=[round(zb0, 2), round(zb1, 2)], t=E[n].get("t"), t_grenze=t_grenze(len(bh)), eindeutig=bool(E[n].get("t", 0) >= t_grenze(len(bh))))
    # Formfamilie der Haube je Foto (Taille .. Hals)
    fam = {}
    for F in fotos:
        zr = [(z, (e_[1] - e_[0]) / 2) for z, e_ in sorted(F["halb"].items()) if Z["z_taille"] - 1e-6 <= z <= Z["z_hals"] + 1e-6]
        f_ = familie_aus_profil(zr)
        if f_: fam[f_] = fam.get(f_, 0) + 1
    fa = max(fam, key=fam.get) if fam else None
    einig = fa is not None and fam[fa] >= MIN_FAMILIE and all(v < fam[fa] for k, v in fam.items() if k != fa)     # Mehrheit, kein Gleichstand
    erg.update(familie=fa if einig else None, familie_stimmen=fam, nadel_einzel=nadel_einzel, nadel_z=round(float(np.median(spitzen)), 2) if len(spitzen) >= MIN_FOTOS else None,
               nadel_streuung=round(float(np.median(np.abs(np.array(spitzen) - np.median(spitzen)))), 2) if len(spitzen) >= MIN_FOTOS else None)
    if erg["nadel_z"] is not None and erg["nadel_streuung"] > NADEL_STREUUNG_M:
        erg.update(nadel_grund=f"Nadelende streut {erg['nadel_streuung']} m (> {NADEL_STREUUNG_M}) - Bauteil nimmt spitze_foto.spitze_z", nadel_z_roh=erg["nadel_z"], nadel_z=None)
    ok_ = erg.get("pfosten", {}).get("eindeutig") and erg.get("haube") is not None and erg["familie"] is not None
    erg.update(gueltig=bool(ok_), grund=None if ok_ else "Pfosten-Eckenzahl nicht eindeutig / Haube oder Familie ohne >= 3 Fotos",
               annahmen=["ANNAHME: regelmaessiges n-Eck um die Dachachse (Lage aus dach_profil.json)",
                         "ANNAHME: Krempe hat die Eckenzahl und Lage der Pfosten (Dach ueber dem Pfostenviereck), Haube eigene Eckenzahl aus den Facettenstufen",
                         "Pfostenbreite = Breite der Dunkelheit um die aeusseren Pfosten (Unschaerfe macht sie etwas breiter)", "Glocke/Zifferblaetter im Inneren nicht gebaut"])
    print(f"Pfosten {erg.get('pfosten', {}).get('n')} (Abstand {erg.get('pfosten', {}).get('abstand')}, R {erg.get('pfosten', {}).get('R')}, Breite {erg.get('pfosten', {}).get('breite')}); "
          f"Haube {erg.get('haube', {}).get('n')} (Abstand {erg.get('haube', {}).get('abstand')}); Familie {erg['familie']} {fam}; Nadel z {erg['nadel_z']}")
    if a.bild:
        try: bild(fotos, A, erg, a.bild)
        except Exception as e: print("Bild fehlgeschlagen:", e)
    return schreiben(D, pp, a, erg, 0 if ok_ else 4)


def schreiben(D, pp, a, erg, rc):
    if a.aus: json.dump(erg, open(a.aus, "w"), indent=1); print("->", a.aus)
    else: D["laterne_foto"] = erg; json.dump(D, open(pp, "w"), indent=1); print("->", pp, "(Block laterne_foto)")
    return rc


def bild(fotos, A, erg, aus):
    """Pruefbild: bis 4 Fotos (Ausschnitt um die Laterne) mit den vorhergesagten Pfosten (gruen, im Pfostenband) und Haubenkanten (magenta, im Bauchband)."""
    import cv2, flaeche_ortho as FO
    Z = erg["zonen"]; kach = []
    for F in sorted(fotos, key=lambda F: -F["ppm"])[:4]:
        im = cv2.imread(F["pf"]) if F.get("pf") else cv2.cvtColor(F["im"], cv2.COLOR_GRAY2BGR); c, sb, q = F["c"], F["sb"], F["q"]
        P_ = lambda x, z: tuple(int(v) for v in (FO.projektion(np.array([[A[0] + x * q[0], A[1] + x * q[1], z]]), c)[0] * sb)[0])
        for key, zb, col in (("pfosten", sum(erg["pfosten"]["band"]) / 2 if erg.get("pfosten") else None, (0, 200, 0)), ("haube", Z["z_bauch"], (255, 0, 255))):
            E = erg.get(key)
            if not E or zb is None: continue
            if key == "pfosten": xe = ecken_x(E["n"], E["phase"], F["az"], E["R"])[0]; sel = np.ones(len(xe), bool)
            else: xe, sel = ecken_x(E["n"], E["phase"], F["az"], Z["r_bauch"] / E["silh_faktor"])
            for x in xe[sel]: cv2.line(im, P_(x, zb - 0.3), P_(x, zb + 0.3), col, 2)
        a0 = P_(0, erg["z_fuss"] - 0.5); a1 = P_(0, (erg.get("nadel_z") or Z["z_knauf"]) + 0.5); h = abs(a0[1] - a1[1])
        k = im[max(0, a1[1]):a0[1], max(0, a0[0] - int(0.45 * h)):a0[0] + int(0.45 * h)]
        if k.size == 0: continue
        k = cv2.resize(k, (int(k.shape[1] * 500 / k.shape[0]), 500)); cv2.putText(k, F["nr"][-14:], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1); kach.append(k)
    if kach: cv2.imwrite(aus, np.hstack(kach), [cv2.IMWRITE_JPEG_QUALITY, 88]); print("Bild:", aus)


if __name__ == "__main__": sys.exit(main())
