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
 2. PFOSTEN (offene Zone je Foto aus der Silhouette: Zeilen mit Himmel zwischen den Pfosten, unter Glocke/Krempe, ueber dem First): ein regelmaessiges n-Eck mit Umkreis R und Lage phase zeigt
    seine Pfosten bei x = c + R sin(az - alpha_k) (vorne UND hinten sichtbar, weil offen). Bewertung je (n, phase, R): mittlere Dunkelheit an den Pfosten minus
    mittlere Dunkelheit an den Kantenmitten (dort muss Himmel sein). Ein Achteck bei einem Quadrat verliert, weil seine Zwischenpfosten im Himmel liegen.
 3. HAUBE (geschlossen): Facettenkanten sind Helligkeitsstufen (Flaechen verschiedener Neigung zum Licht), Blechnaehte nur duenne Linien -> Stufensignal
    |mean I(x+w) - mean I(x-w)|. Vorhersage nur fuer vordere Ecken, normiert auf die Silhouette: u_k = sin(az - alpha_k) / max|sin|. Gleiche Kontrastbewertung.
 4. Breitenprofil in voller Aufloesung (aeussere Ausdehnung der Dunkelheit) ueber alle Fotos -> Median je Hoehe; Zonen: Pfosten (bis Krempe), Krempe (Breitensprung),
    Haube (Taille -> Bauch -> Hals), Knauf (Maximum ueber dem Hals), Nadel (schmal bis zum obersten dunklen Pixel). Umkreis = Silhouette / mittleres max|sin|.
 5. Formfamilie der Haube je Foto (zwiebel / geschweift / gerade aus dem Breitenprofil); gilt nur, wenn >= MIN_FAMILIE Fotos einig sind.
 6. (23.11.2026) HAUBE ALS DREHKOERPER: Farbsilhouette je Foto (Farbabstand zum Himmel), Seiten- und Hoehenversatz je Foto registriert, Sehstrahl-Huelle ueber der
    Pfostenoberkante (Krempe, Taille, Bauch, Hals, Knauf) = Profil r(z) + Zonen; Querschnitt rund/n-Eck durch Synthese (haube_huelle, querschnitt_haube).
    Familie aus der Huelle schlaegt die Einzelprofile (die Krempe verdeckt von unten die Taille).
Ausgabe: Block 'laterne_foto' in audit/dach_profil.json (oder --aus); bauteile.laterne baut daraus (bauteile.dach_aus_profil nimmt ihn, wenn gueltig).
Aufruf: laterne_aus_fotos.py <objekt.json> [--profil audit/dach_profil.json] [--aus datei.json] [--bild datei.jpg] [--min-ppm 25]
rc 0 = gueltig, rc 3 = kein spitze_foto-Block, rc 4 = zu wenig Fotos/keine eindeutige Eckenzahl (Block mit gueltig=false).
"""
import sys, os, json, argparse, math, numpy as np

H_ = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H_)

# ---- Schwellen (Grund je Zeile; nicht an einem Bauwerk eingestellt) ---------------------------------------------------------------------------
N_KAND = (3, 4, 5, 6, 8, 10, 12, 16)  # gepruefte Eckenzahlen (regelmaessige Vielecke der Laternen/Hauben; Kreis = keine Zahl gewinnt)
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
# 23.11.2026 (Kette 1122q, Befund 'Laterne geschlossen statt offen', laterne_foto: 'Pfosten None'): das feste Band (30-45 % der Pfostenhoehe) lag in den Fotos
# von unten am Dachfirst; die hellgruenen Pfosten erreichten gegen die tiefschwarze Krempen-Untersicht (lo = 3-%-Wert der ganzen Laterne) die Schwelle DUNKEL nicht.
# Jetzt je Foto die OFFENE ZONE aus der Silhouette (Zeilen mit Himmel zwischen den Pfosten), Dunkelheit je Zeile normiert, und Fotos aus allen Blickrichtungen.
OFFEN_REL = 0.85       # offene Zeilen: Himmelsanteil >= 85 % des offensten Werts dieses Fotos (darunter Dachfirst/Glocke zwischen den Pfosten)
BREITE_REL = 0.15      # ... und Silhouetten-Halbbreite auf 15 % wie der Median der offenen Zeilen (Dachflaeche/Krempe sind breiter)
MIN_ZEILEN = 3         # offene Zone mind. 3 Zeilen (0,15 m bei 5 cm Schritt), sonst Foto fuer die Pfosten nicht verwendbar
ZEILE_LO_ANTEIL = 0.3  # Zeilen-Normierung: Nenner mind. 30 % des Foto-Kontrasts (reine Himmelszeile bleibt hell, Rauschen wird nicht zu 'dunkel')
MIN_HIMMEL = 0.8       # Fotoauswahl: >= 80 % der Randpunkte neben der Laterne (Krempe .. Spitze) sind in der Himmelsmaske Himmel (Laterne frei vor Himmel)
SEKTOR_GRAD = 45.0     # Fotoauswahl je Blickrichtungs-Sektor ...
MAX_JE_SEKTOR = 8      # ... hoechstens 8 Fotos (die mit den meisten px/m) - sonst bestimmen 10 Fotos aus 16 Grad die Eckenzahl allein
MAX_FOTOS = 40         # Speicher: 40 Fotos x 12 MP Graustufen ~ 0,5 GB


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
    -> dict(n -> dict(kontrast [Korrelation], phase, R_anteil)), bestes n, Abstand zum zweiten.
    23.11.2026: offen - Umkreis R in METERN fuer alle Fotos gleich, je (n, phase) aus den Silhouetten bestimmt (aeussere Pfostenkante = Ausdehnung:
    R_F = (h_F - breite/2) / halbe Spannweite der Ecken; R = Median) statt R = Anteil x h je Foto (ein Vieleck ist je Blickrichtung verschieden breit; das freie R
    liess die Pfosten nach innen rutschen - Kette 1122: Marken bei R 0,55 m zwischen Pfosten bei 0,75 m). Bewertet nur im Silhouettenbereich (|x - c| <= h + breite).
    Je Foto die beste Eckenzahl -> 'stimmen' (Formfamilie aus >= 3 Fotos, main prueft)."""
    if offen and breite is None:
        bb = [b for B in beob for b in aussen_breite(B)]; breite = float(np.median(bb)) if bb else 0.1
    erg = {}
    for n in n_kand:
        best = (-np.inf, 0.0, 1.0)
        for ph in np.arange(0.0, 360.0 / n, phase_schritt):
            if offen:
                X_ = [ecken_x(n, ph, B["az"])[0] for B in beob]
                R_ = float(np.median([(B["h"] - breite / 2) / max((x_.max() - x_.min()) / 2, 1e-3) for B, x_ in zip(beob, X_)]))
            for ra in ([R_] if offen else [1.0]):
                ks = []
                for i, B in enumerate(beob):
                    x, s = B["x"], B["s"]; xe, ve = ecken_x(n, ph, B["az"])
                    if offen:
                        m = np.zeros_like(x); reg = np.abs(x - B["c"]) <= B["h"] + breite; c_ = B["c"] - ra * (xe.max() + xe.min()) / 2     # Mitte der Eckenspannweite = Mitte der Ausdehnung
                        for p in c_ + ra * xe: m = np.maximum(m, (np.abs(x - p) <= breite / 2).astype(float))
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
        if offen: erg[n].update(R=round(best[2], 3), R_anteil=round(best[2] / max(float(np.median([B["h"] for B in beob])), 1e-6), 3), breite=round(breite, 3))
    o = sorted(erg, key=lambda n: -erg[n]["kontrast"])
    # Stimmen: je Foto die Eckenzahl mit der hoechsten Einzel-Korrelation (Formfamilie erst aus >= MIN_FAMILIE Fotos)
    ein = {n: erg[n]["einzel"] for n in erg if len(erg[n]["einzel"]) == len(beob)}
    if ein:
        st = {}
        for i in range(len(beob)):
            nb = max(ein, key=lambda n: ein[n][i]); st[nb] = st.get(nb, 0) + 1
        erg[o[0]]["stimmen"] = {str(k): v for k, v in sorted(st.items())}
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


def dunkel_zeile(I, hi, lo_foto):
    """Dunkelheit einer Zeile gegen den Himmel (hi), normiert auf das Dunkelste DIESER Zeile (1-%-Wert): helle Pfosten vor Himmel werden ~1, auch wenn die Krempen-Untersicht
    im selben Foto viel dunkler ist; Nenner mind. ZEILE_LO_ANTEIL des Foto-Kontrasts (reine Himmelszeile bleibt ~0)."""
    lo = float(np.nanpercentile(I, 1)) if np.isfinite(I).any() else hi
    return np.clip((hi - I) / max(hi - lo, ZEILE_LO_ANTEIL * (hi - lo_foto), 1e-6), 0, 1)


def offene_zone(S, zs, x):
    """Offene Zone der Pfosten in EINEM Foto aus der Silhouette: S [Zeilen, x] Dunkelheit je Hoehe zs (Fuss .. Pfostenoberkante). Je Zeile aeussere Ausdehnung (> DUNKEL)
    und Himmelsanteil dazwischen. Offen = Himmelsanteil >= MIN_OFFEN und >= OFFEN_REL x offenster Wert, Halbbreite auf BREITE_REL wie der Median der offenen Zeilen
    (Dachfirst, Glocke hinter den Pfosten, Krempe fallen heraus). -> dict(s [Median der offenen Zeilen], z0, z1, zeilen, offen, c, h) oder (None, Grund)."""
    hf, of, ce = [], [], []
    for s in S:
        e_ = ausdehnung(np.nan_to_num(s, nan=0.0), x)
        if not e_: hf.append(np.nan); of.append(0.0); ce.append(np.nan); continue
        inn = (x > e_[0]) & (x < e_[1]); hf.append((e_[1] - e_[0]) / 2); ce.append((e_[0] + e_[1]) / 2)
        of.append(float(np.mean(s[inn] < 1 - DUNKEL)) if inn.any() else 0.0)
    hf, of, ce = np.array(hf), np.array(of), np.array(ce)
    k = of >= MIN_OFFEN
    if not k.any(): return None, f"kein Himmel zwischen den Pfosten (offen max {of.max():.2f})"
    k &= of >= OFFEN_REL * of[k].max(); hm = float(np.median(hf[k])); k &= np.abs(hf - hm) <= BREITE_REL * hm
    if k.sum() < MIN_ZEILEN: return None, f"offene Zone nur {int(k.sum())} Zeilen"
    s = np.median(np.asarray(S)[k], 0)
    e_ = ausdehnung(s, x)
    if not e_: return None, "Pfosten im Median der offenen Zeilen nicht dunkel"
    return dict(s=s, z0=float(zs[k].min()), z1=float(zs[k].max()), zeilen=int(k.sum()), offen=round(float(np.median(of[k])), 3), c=(e_[0] + e_[1]) / 2, h=(e_[1] - e_[0]) / 2), None


def himmel_anteil(maske, proj, A, q, zs, xr):
    """Anteil Himmel (maske True) an den Randpunkten A + x q (x = +-xr) in den Hoehen zs; Punkte ausserhalb des Bilds zaehlen als nicht Himmel."""
    H, W = maske.shape; n = 0; h = 0
    for z in zs:
        for x in xr:
            p = proj(np.array([[A[0] + x * q[0], A[1] + x * q[1], z]]))[0][0]; n += 1
            xi, yi = int(round(p[0])), int(round(p[1]))
            if 0 <= xi < W and 0 <= yi < H and maske[yi, xi]: h += 1
    return h / max(n, 1)


def fotos_streuen(kand, sektor=SEKTOR_GRAD, je=MAX_JE_SEKTOR, gesamt=MAX_FOTOS):
    """Fotoauswahl ueber die Blickrichtungen: kand = [(ppm, az, nr, ...)]; je Sektor die je besten (ppm), dann insgesamt hoechstens 'gesamt' (beste ppm). -> Liste."""
    sek = {}
    for k in sorted(kand, key=lambda k: -k[0]): sek.setdefault(int((k[1] % 360.0) // sektor), []).append(k)
    aus = [k for v in sek.values() for k in v[:je]]
    return sorted(aus, key=lambda k: -k[0])[:gesamt]


def profil_abweichung(halb, pm, k_grenze=1.45):
    """Abweichung eines Foto-Breitenprofils vom Median-Profil MIT freiem Massstab k (Vieleck: je Blickrichtung bis sqrt(2) breiter/schmaler - ohne k flogen am
    Schwabentor genau die Fotos aus anderen Richtungen als 'Ausreisser' raus). halb {z: (l, r)}, pm {z: halb}. -> (Median |h - k pm|, k)."""
    zz = [z for z in halb if z in pm]
    if not zz: return np.inf, 1.0
    h = np.array([(halb[z][1] - halb[z][0]) / 2 for z in zz]); p = np.array([pm[z] for z in zz])
    best = (np.inf, 1.0)
    for k in np.exp(np.linspace(-math.log(k_grenze), math.log(k_grenze), 41)):
        d = float(np.median(np.abs(h - k * p)))
        if d < best[0]: best = (d, float(k))
    return best


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
    zk = zonen_ab_krempe(z, r, jk); zk["i"] = (j,) + zk["i"]
    return dict(z_pfosten_unten=float(z[j0]), z_pfosten_oben=float(z[j]), r_pfosten_silh=r_pf, **zk)


def zonen_ab_krempe(z, r, jk):
    """Haubenzonen ab der Krempe (Index jk) im Profil z/r: Taille = schmalste Stelle in 1 m darueber, Bauch = groesste darueber, Hals = schmalste ueber dem Bauch,
    Knauf = groesste in 1 m ueber dem Hals."""
    jt = jk + int(np.argmin(r[jk:][z[jk:] <= z[jk] + 1.0]))
    jb = jt + int(np.argmax(r[jt:]))
    # Hals: erste Hoehe ueber dem Bauch unter 35 % der Bauchbreite, dann weiter bis zum oertlichen Minimum (nicht das Nadelende: dort wird es wieder schmaler)
    jh = next((i for i in range(jb, len(r)) if r[i] < 0.35 * r[jb]), len(r) - 1)
    while jh + 1 < len(r) and r[jh + 1] <= r[jh] + 1e-9: jh += 1
    jn = jh + int(np.argmax(r[jh:][z[jh:] <= z[jh] + 1.0]))
    return dict(z_krempe=float(z[jk]), r_krempe=float(r[jk]), z_taille=float(z[jt]), r_taille=float(r[jt]),
                z_bauch=float(z[jb]), r_bauch=float(r[jb]), z_hals=float(z[jh]), r_hals=float(r[jh]), z_knauf=float(z[jn]), r_knauf=float(r[jn]), i=(jk, jt, jb, jh, jn))


# ---- Haube als DREHKOERPER aus den Silhouetten (23.11.2026) ----------------------------------------------------------------------------------------
# Anlass (Kette 1122r, neben_detail_laterne: Foto Zwiebel mit Einschnuerung, Knauf, Nadel - Modell Kasten): das Median-Breitenprofil je Hoehe war von der Taille bis
# zum Bauch flach (1,17..1,22 m), weil in Fotos von schraeg unten (bis -49 Grad) die breite Krempe als Ellipse bis 0,9 m ueber ihre eigene Hoehe in die Taillen-Zeilen
# ragt (Rueckkante hoeher abgebildet) - die Taille verschwand, Familie 'geschweift' 8:5. Jetzt SEHSTRAHL-HUELLE (visual hull): je Foto und Hoehe der groesste Querschnitt
# (Kreis bzw. n-Eck), dessen Abbild ganz in der Silhouette DIESES Fotos liegt; Radius je Hoehe = K_HUELLE-kleinster Wert ueber die Fotos (Fotos von unten begrenzen die
# Taille nicht, waagrechte Fotos schon). Querschnitt rund/n-Eck durch Synthese: Huelle je Hypothese, Silhouetten neu abgebildet, Restfehler je Foto verglichen.
K_HUELLE = 3            # Radius = drittkleinster Fotowert: bis zu 2 Fotos mit zu schmaler Silhouette (helles Blech vor hellem Himmel, Kamera-Restfehler) schnueren die Haube nicht ein;
                        # am Schwabentor schnitten 195 (Haube oben hell) und ein zweites Foto mit k = 2 den Bauch auf 1,0 m (Fotos 1,25 m)
QS_PUNKTE = 96          # Punkte je Querschnitt (Kreis/n-Eck-Kanten) fuer die Abbildung
RUND_TOL = 0.10         # Silhouette RICHTUNGSUNABHAENGIG: Kreis-Huelle erklaert die Fotos hoechstens 10 % schlechter als das beste n-Eck (kein richtungsabhaengiger Anteil) ...
EGAL_TOL = 0.20         # ... UND die Ersatz-Eckenzahl (Pfosten) ist mind. 20 % schlechter als der Kreis (Fotos widersprechen ihr). Von schraeg unten (45-55 Grad) zeigt die
                        # Silhouette den Querschnitt selbst (Ellipse/Raute der Ringe), darum trennt das auch bei engem Azimut-Bereich (Schwabentor: Quadrat 0,146 m, Kreis 0,088 m).
                        # Achteck -> Kreis-Naeherung weicht <= 4 % ab (unter der Profilstreuung)


def querschnitt_einheit(n=None, phase=0.0, m=QS_PUNKTE):
    """Einheits-Querschnitt (Umkreis 1) als Punkte (m x 2): Kreis (n None) oder regelmaessiges n-Eck (Punkte gleichmaessig auf den Kanten, Ecke 0 bei Weltwinkel phase)."""
    if not n: w = np.linspace(0, 2 * math.pi, m, endpoint=False); return np.c_[np.cos(w), np.sin(w)]
    e = np.array([[math.cos(math.radians(phase + k * 360.0 / n)), math.sin(math.radians(phase + k * 360.0 / n))] for k in range(n + 1)]); j = max(1, m // n)
    return np.vstack([e[k] + (e[k + 1] - e[k]) * t for k in range(n) for t in np.arange(j) / j])


def ebene_abbilden(P, C, A, az):
    """3D-Punkte P (k x 3) -> (x', z') in der Fotoebene eines Fotos: Ebene durch die Achse A senkrecht zur waagrechten Blickrichtung az (wie zeile()), Schnitt des
    Sehstrahls Kamera C -> P mit der Ebene. Gleiches Pixel wie P - so vergleicht man Punkte ausserhalb der Ebene (Krempe, Haubenrueckseite) mit dem gemessenen Profil."""
    u = np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), 0.0]); q = np.array([u[1], -u[0], 0.0]); A3 = np.array([A[0], A[1], 0.0])
    d = P - C; t = ((A3 - C) @ u) / np.where(np.abs(d @ u) < 1e-9, -1e-9, d @ u); X = C + t[:, None] * d
    return (X - A3) @ q, X[:, 2]


def farb_halb(zeile_fn, xs, zs, x_himmel, z_ref, schwelle_fn):
    """Silhouette je Hoehe aus dem FARBABSTAND zum Himmel: zeile_fn(z0, z1, nz) -> Farbzeile (N x 3) auf xs. Himmelsfarbe = Median der Pixel mit |x| >= x_himmel im
    Referenzband z_ref (neben der Laterne, Foto frei vor Himmel); Abstand normiert auf seinen 97-%-Wert im Band; Bauwerk = Abstand > schwelle_fn(z). -> {z: (l, r)}."""
    ref = np.asarray(zeile_fn(z_ref[0], z_ref[1], 25), float); au = np.abs(xs) >= x_himmel
    if ref.ndim != 2 or not np.isfinite(ref[au]).all(1).any(): return {}
    sky = np.nanmedian(ref[au], 0); d97 = float(np.nanpercentile(np.linalg.norm(ref - sky, axis=1), 97)); out = {}
    if not d97 > 1e-6: return {}
    for z in zs:
        d = np.nan_to_num(np.linalg.norm(np.asarray(zeile_fn(z, z, 1), float) - sky, axis=1) / d97, nan=0.0); e_ = ausdehnung(d, xs, schwelle=schwelle_fn(float(z)))
        if e_: out[float(z)] = (e_[0], e_[1])
    return out


def profil_raster(halb, dz=0.05):
    """Gemessenes Foto-Profil {z: (l, r)} (x quer in der Fotoebene) -> (zg, l, r) auf dem z-Gitter; fehlende Zeilen = NaN (dort ist Himmel)."""
    zz = sorted(halb); zg = np.round(np.arange(zz[0], zz[-1] + dz / 2, dz), 3); l = np.full(len(zg), np.nan); r = np.full(len(zg), np.nan); k = {round(z, 3): v for z, v in halb.items()}
    for i, z in enumerate(zg):
        v = k.get(round(float(z), 3))
        if v is not None: l[i], r[i] = v[0], v[1]
    return zg, l, r


def _zeilen(zp, zg):
    dz = float(zg[1] - zg[0]) if len(zg) > 1 else 0.05; i = np.round((zp - zg[0]) / dz).astype(int); return i, (i >= 0) & (i < len(zg))


def _in_silhouette(xp, zp, B):
    """Liegen die abgebildeten Punkte (x', z') in der Silhouette von Foto B (l <= x' <= r der naechsten Gitterzeile)? Ausserhalb des Gitters/Himmelszeile = nein."""
    i, ok = _zeilen(zp, B["zg"]); i = np.clip(i, 0, len(B["zg"]) - 1); l, r = B["l"][i], B["r"][i]
    return ok & np.isfinite(l) & (xp >= l - 1e-9) & (xp <= r + 1e-9)


def _ringe(A, zs, s, quer):
    m = len(quer); return np.c_[A[0] + (s[:, None] * quer[None, :, 0]).ravel(), A[1] + (s[:, None] * quer[None, :, 1]).ravel(), np.repeat(zs, m)]


def huelle_foto(B, A, zs, quer, s_max=3.0, iters=14):
    """Je Hoehe z (zs) der groesste Massstab s (Umkreis), bei dem der Querschnitt s * quer um die Achse A in Hoehe z ganz in der Silhouette von Foto B liegt (Bisektion).
    B: dict(C [3], az, A0 [Ebene der Messung], zg, l, r). -> Array s je Hoehe."""
    lo = np.zeros(len(zs)); hi = np.full(len(zs), s_max); m = len(quer); A0 = B.get("A0", A)
    for _ in range(iters):
        s = (lo + hi) / 2; xp, zp = ebene_abbilden(_ringe(A, zs, s, quer), np.asarray(B["C"], float), A0, B["az"])
        ok = _in_silhouette(xp, zp, B).reshape(len(zs), m).all(1); lo = np.where(ok, s, lo); hi = np.where(ok, hi, s)
    return lo


def silhouette_vorhersage(B, A, zs, rs, quer, dz=0.025):
    """Ausdehnung (l, r) des Drehkoerpers (Profil zs/rs um die Achse A, Querschnitt quer) im Foto B auf dessen Gitter zg (NaN = nichts): alle Querschnitte fein in z abgebildet."""
    zf = np.arange(zs[0], zs[-1] + 1e-9, dz); rf = np.interp(zf, zs, rs); xp, zp = ebene_abbilden(_ringe(A, zf, rf, quer), np.asarray(B["C"], float), B.get("A0", A), B["az"])
    i, k = _zeilen(zp, B["zg"]); n = len(B["zg"]); l = np.full(n, np.inf); r = np.full(n, -np.inf)
    np.minimum.at(l, i[k], xp[k]); np.maximum.at(r, i[k], xp[k]); l[~np.isfinite(l)] = np.nan; r[~np.isfinite(r)] = np.nan; return l, r


def drehprofil(beob, A, zs, n=None, phase=0.0, k=K_HUELLE):
    """Sehstrahl-Huelle eines Drehkoerpers mit Querschnitt (Kreis oder n-Eck/phase) um die Achse A aus mehreren Fotos. -> (r je Hoehe [Umkreis], S [Fotos x Hoehen],
    bindend [Anzahl Fotos je Hoehe innerhalb 5 % des Ergebnisses])."""
    quer = querschnitt_einheit(n, phase); S = np.array([huelle_foto(B, A, zs, quer) for B in beob])
    r = np.sort(S, 0)[min(k, len(beob)) - 1]
    return r, S, (S <= 1.05 * r[None, :] + 1e-3).sum(0)


def huelle_restfehler(beob, A, zs, r, n=None, phase=0.0, zband=None):
    """Restfehler je Foto: Median der Kantenabweichung (|l - l_vorh| + |r - r_vorh|) / 2 in den Zeilen des Bands zband (z0, z1); Zeile nur in einem von beiden (Messung
    oder Vorhersage) zaehlt als Halbbreite daneben."""
    quer = querschnitt_einheit(n, phase); z0, z1 = zband or (zs[0], zs[-1]); out = []
    for B in beob:
        lp, rp = silhouette_vorhersage(B, A, zs, r, quer); sel = (B["zg"] >= z0) & (B["zg"] <= z1); gm = np.isfinite(B["l"]) & sel; gp = np.isfinite(lp) & sel
        if not (gm | gp).any(): out.append(np.nan); continue
        e = np.where(gm & gp, (np.abs(B["l"] - lp) + np.abs(B["r"] - rp)) / 2, np.where(gm, (B["r"] - B["l"]) / 2, (rp - lp) / 2))
        out.append(float(np.median(e[gm | gp])))
    return np.array(out)


DZ_MAX = 0.8            # Registrierung: Hoehenversatz je Foto hoechstens +-0,8 m (Schwabentor-1122: Knauf je Foto 51,6..52,4 m, Krempensprung passend zum Hoehenwinkel
DZ_SCHRITT = 0.05       # versetzt - Kameralage an der Laternenspitze einige dm unsicher; Nadelende je Foto streute 2 m)
REST_AUSREISSER = 2.0   # Foto mit Restfehler > 2 x Median aller nach der Registrierung = Silhouette unvollstaendig (helles Blech vor hellem Himmel) -> raus aus der Huelle


def zentrieren(beob, band):
    """Seitlicher Versatz je Foto: Silhouettenmitte im Band (Median von (l + r) / 2) auf 0 - die Achse liegt quer zur Blickrichtung je Foto einige dm daneben
    (Kameralage/Achse aus der Wolke); Drehkoerper sind in der Fotoebene symmetrisch zur Achse (Kamera liegt in der Symmetrieebene). Mitte nur aus dem Koerper
    (Zeilen mit > 50 % der groessten Breite; Knauf/Nadel sind wenige Pixel breit). Danach SYMMETRISCH auf die schmalere Seite: ein Fremdkoerper neben einer Seite
    (Nachbardach/Turm hinter der Haube, commons_orig2__084) verbreitert nur eine Seite und darf die Huelle nicht tragen. Setzt B['mitte'], l = -w, r = w."""
    for B in beob:
        sel = (B["zg"] >= band[0]) & (B["zg"] <= band[1]) & np.isfinite(B["l"])
        if sel.any():
            wb = (B["r"] - B["l"]) / 2; sel &= wb >= 0.5 * np.nanmax(np.where(sel, wb, np.nan))
        c = float(np.median((B["l"][sel] + B["r"][sel]) / 2)) if sel.any() else 0.0
        w = np.minimum(c - B["l"], B["r"] - c); w = np.where(w > 0, w, np.nan)
        B["mitte"] = c; B["l"] = -w; B["r"] = w
    return beob


def registrieren(beob, A, zs, band, iters=3, k=K_HUELLE):
    """HOEHENVERSATZ je Foto (Kameralage-Fehler) durch Synthese: je Foto der Versatz dz (+-DZ_MAX), bei dem seine Silhouette am besten zur Huelle der ANDEREN Fotos passt
    (Runde 1 Median der Einzel-Huellen, danach k-kleinster Wert); Versatz-Median = 0. Danach Fotos mit Restfehler > REST_AUSREISSER x Median raus.
    Setzt B['dz'] und verschiebt zg. -> (beob [nur passende], weg {nr: Grund})."""
    quer = querschnitt_einheit()
    for B in beob: B.setdefault("zg0", B["zg"].copy()); B["dz"] = 0.0
    def setz(B, dz): B["zg"] = B["zg0"] + dz
    for it in range(iters):
        for B in beob: setz(B, B["dz"])
        S = np.array([huelle_foto(B, A, zs, quer) for B in beob]); neu = []
        for i, B in enumerate(beob):
            an = np.delete(S, i, 0); r = np.median(an, 0) if it == 0 else np.sort(an, 0)[min(k, len(an)) - 1]; best = (np.inf, 0.0)
            for d in np.arange(-DZ_MAX, DZ_MAX + 1e-9, DZ_SCHRITT):
                if abs(B["dz"] + d) > DZ_MAX + 1e-9: continue
                setz(B, B["dz"] + d); e = huelle_restfehler([B], A, zs, r, zband=band)[0]
                if e < best[0] - 1e-9: best = (e, d)
            setz(B, B["dz"]); neu.append(B["dz"] + best[1])
        m_ = float(np.median(neu))
        for B, d in zip(beob, neu): B["dz"] = round(d - m_, 3)
    for B in beob: setz(B, B["dz"])
    r, _, _ = drehprofil(beob, A, zs, k=k); e = huelle_restfehler(beob, A, zs, r, zband=band); me = float(np.nanmedian(e)); weg = {}
    for B, e_ in zip(beob, e):
        B["rest"] = round(float(e_), 3)
        if not np.isfinite(e_) or e_ > REST_AUSREISSER * me: weg[B["nr"]] = f"Restfehler {e_:.2f} m > {REST_AUSREISSER} x Median {me:.2f} (Silhouette unvollstaendig/Fremdkoerper)"
    gut = [B for B in beob if B["nr"] not in weg]
    if weg and len(gut) >= MIN_FOTOS: g2, w2 = registrieren(gut, A, zs, band, iters, k); return g2, {**weg, **w2}
    return beob, {}


def querschnitt_haube(beob, A, zs, zband, r_ref, n_kand=N_KAND, phase_schritt=5.0, facetten=None, n_fallback=None, phase_fallback=0.0):
    """Querschnitt der Haube durch SYNTHESE: je Hypothese (Kreis, n-Eck x Lage) Sehstrahl-Huelle, Silhouetten neu abgebildet, Restfehler je Foto im Haubenband.
    Entscheidung (Formfamilie nur aus >= MIN_FAMILIE Fotos, CLAUDE.md):
     1. ein n-Eck ist in >= MIN_FAMILIE Fotos besser als der Kreis UND gepaarter t-Wert ueber t_grenze -> n-Eck (Fotobeleg Silhouette);
     2. sonst Facettenprobe eindeutig (facetten = dict(n, phase, eindeutig)) -> deren n-Eck (Fotobeleg Facettenstufen);
     3. sonst Kreis, wenn die Silhouette richtungsunabhaengig ist: Kreis-Restfehler <= (1 + RUND_TOL) x bestes n-Eck UND Ersatz-Eckenzahl n_fallback
        >= (1 + EGAL_TOL) x Kreis -> 'rund' als benannte ANNAHME;
     4. sonst n_fallback (Eckenzahl der Pfosten) als ANNAHME.
    -> dict(art 'rund'|'n-eck', n, phase, quelle, annahme, rest_kreis, rest_best, t, besser_fotos, kandidaten)."""
    rk, _, _ = drehprofil(beob, A, zs); ek = huelle_restfehler(beob, A, zs, rk, zband=zband); kand = {"kreis": round(float(np.nanmedian(ek)), 4)}; best = None
    for n in n_kand:
        for ph in np.arange(0.0, 360.0 / n, phase_schritt):
            r, _, _ = drehprofil(beob, A, zs, n, ph); e = huelle_restfehler(beob, A, zs, r, n, ph, zband=zband); m_ = float(np.nanmedian(e))
            if best is None or m_ < best[0]: best = (m_, n, float(ph), e)
            kand[str(n)] = round(min(kand.get(str(n), 9.0), m_), 4)
    d_ = ek - best[3]; d_ = d_[np.isfinite(d_)]; besser = int((d_ > 0).sum())
    t = float(d_.mean() / max(d_.std(ddof=1), 1e-6) * math.sqrt(len(d_))) if len(d_) > 1 else 0.0
    erg = dict(rest_kreis=kand["kreis"], rest_best=round(best[0], 4), n_best=best[1], phase_best=best[2], t=round(t, 2), t_grenze=t_grenze(len(d_)), besser_fotos=besser, kandidaten=kand,
               rest_kreis_rel=round(kand["kreis"] / max(r_ref, 1e-6), 3))
    if besser >= MIN_FAMILIE and t >= t_grenze(len(d_)):
        return dict(erg, art="n-eck", n=best[1], phase=best[2], annahme=None, quelle=f"Silhouetten-Synthese: {best[1]}-Eck in {besser} Fotos besser als Kreis (t {t:.2f})")
    if facetten and facetten.get("eindeutig"):
        return dict(erg, art="n-eck", n=int(facetten["n"]), phase=float(facetten["phase"]), annahme=None, quelle=f"Facettenstufen: {facetten['n']}-Eck eindeutig")
    r_fb = kand.get(str(n_fallback)) if n_fallback else None
    if kand["kreis"] <= (1 + RUND_TOL) * best[0] and (r_fb is None or r_fb >= (1 + EGAL_TOL) * kand["kreis"]):
        return dict(erg, art="rund", n=None, phase=0.0, quelle="Silhouette richtungsunabhaengig",
                    annahme=f"ANNAHME: Haube rund - Silhouette richtungsunabhaengig (Kreis-Restfehler {kand['kreis']:.3f} m, bestes {best[1]}-Eck {best[0]:.3f} m, Pfosten-{n_fallback}-Eck "
                            f"{r_fb if r_fb is None else round(r_fb, 3)} m); Facetten/Rippen nicht belegt (kein n-Eck in >= {MIN_FAMILIE} Fotos signifikant besser, t {t:.2f})")
    return dict(erg, art="n-eck", n=n_fallback, phase=phase_fallback, quelle="Pfosten",
                annahme=f"ANNAHME: Haube {n_fallback}-Eck wie die Pfosten (kein n-Eck belegt, Kreis nicht richtungsunabhaengig: Kreis {kand['kreis']:.3f} m, bestes {best[1]}-Eck {best[0]:.3f} m)")


GLATT_ZEILEN = 5        # Huellenprofil: gleitender Median ueber 5 Zeilen (0,25 m) - einzelne Zeilen mit Rauschen (Blechnaht, Mischpixel) kerben sonst die Haube;
                        # Knauf (0,4 m hoch) bleibt erhalten


KNAUF_FENSTER_M = 0.1   # Knaufradius: Halbbreiten +-0,1 m um die Knaufmitte (Restversatz der Registrierung ~5 cm)
KNAUF_MAX = 1.5


def glaetten(r, k=GLATT_ZEILEN):
    """Gleitender Median (ungerade Fensterlaenge k) mit Randwiederholung."""
    r = np.asarray(r, float); h = k // 2
    if len(r) < k: return r
    p = np.r_[np.full(h, r[0]), r, np.full(h, r[-1])]; return np.array([np.median(p[i:i + k]) for i in range(len(r))])


def haube_huelle(fotos, A, zs, P, Z):
    """Kreis-Huelle ueber der Krempe (Haube, Hals, Knauf, Nadelfuss) aus allen Fotos (dict mit C, az, halb) und Zonen neu: Profil = Median-Profil bis zur Krempe
    (Pfosten/Krempe wie bisher) + Huelle darueber. -> (dict(beob, zh, r, bindend), Zonen | None [Huelle ohne Taille/Bauch/Hals -> alte Zonen bleiben])."""
    beob = []
    for F in fotos:
        if len(F.get("halb_f") or F["halb"]) < 5 or F.get("C") is None: continue
        zg, l, r = profil_raster(F.get("halb_f") or F["halb"]); beob.append(dict(C=F["C"], az=F["az"], A0=np.asarray(A, float), zg=zg, l=l, r=r, nr=F["nr"]))
    if len(beob) < MIN_FOTOS: return None, None
    zh = zs[zs >= Z["z_pfosten_oben"] - 1e-6]                                    # ab der Pfostenoberkante: Krempe selbst gehoert in die Huelle (im Median zu tief verschmiert)
    if len(zh) < 10: return None, None
    band = (float(zh[0]), float(zh[-1])); zentrieren(beob, band); alle = list(beob)
    beob, weg = registrieren(beob, A, zh, band)
    if len(beob) < MIN_FOTOS: return None, None
    r, S, bd = drehprofil(beob, A, zh); r = glaetten(r)
    P2 = [list(p) for p in P if p[0] < Z["z_pfosten_oben"] - 1e-6] + [[float(z), float(v), int(b)] for z, v, b in zip(zh, r, bd) if v > 0]
    HB = dict(beob=beob, zh=zh, r=r, S=S, bindend=bd, profil=P2, weg=weg, alle=alle)
    # Krempe = breiteste Stelle der Huelle bis 1,2 m ueber der (Median-)Pfostenoberkante (im Median liegt sie wegen der Verschmierung von unten zu tief)
    w_ = zh <= Z["z_pfosten_oben"] + 1.2
    if not w_.any(): return HB, None
    Z2 = zonen_ab_krempe(zh, r, int(np.argmax(np.where(w_, r, -1.0))))
    if not Z2["z_krempe"] < Z2["z_taille"] < Z2["z_bauch"] < Z2["z_hals"]: return HB, None
    # Pfostenzone und Krempenbreite bleiben aus dem Median (offene Pfosten sind kein Drehkoerper; Krempe meist n-Eck wie die Pfosten - Kreis-Huelle gaebe den Innenkreis)
    Z3 = dict(Z2, z_pfosten_unten=Z["z_pfosten_unten"], z_pfosten_oben=Z["z_pfosten_oben"], r_pfosten_silh=Z["r_pfosten_silh"], r_krempe=max(Z["r_krempe"], Z2["r_krempe"]), i=None)
    Z3["z_krempe"] = max(Z2["z_krempe"], Z["z_pfosten_oben"])
    # KNAUF: kleine Kugel - die k-kleinste Huelle frisst sie bei Restversatz von wenigen cm an (Schwabentor 0,19 m, Fotos 0,22-0,27 m). Radius = Median der
    # gemessenen Halbbreiten der registrierten Fotos um die Knaufhoehe (+-KNAUF_FENSTER_M), hoechstens KNAUF_MAX x Huelle (Haubenrand von unten in den Knaufzeilen)
    kw = [float(np.nanmax(B["r"][np.abs(B["zg"] - Z3["z_knauf"]) <= KNAUF_FENSTER_M])) for B in beob if np.isfinite(B["r"][np.abs(B["zg"] - Z3["z_knauf"]) <= KNAUF_FENSTER_M]).any()]
    if len(kw) >= MIN_FOTOS and Z3["r_knauf"] > Z3["r_hals"]:
        Z3["r_knauf_huelle"] = Z3["r_knauf"]; Z3["r_knauf"] = float(max(Z3["r_knauf"], min(np.median(kw), KNAUF_MAX * Z3["r_knauf"])))
    return HB, Z3


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
    ap.add_argument("--cache", help="Himmelsmasken-Cache (Standard audit/himmel_cache; nur lesen)")
    ap.add_argument("--roh", help="Foto-Profile (Kamera, Blickrichtung, Halbbreiten) als JSON fuer Nachrechnungen/Tests")
    a = ap.parse_args(argv)
    if a.root: FO.ROOT = a.root
    od = os.path.dirname(os.path.abspath(a.objekt)); Au = os.path.join(od, "audit"); pp = a.profil or os.path.join(Au, "dach_profil.json")
    try: D = json.load(open(pp))
    except Exception: print("kein Dachprofil", pp); return 3
    SF = D.get("spitze_foto") or {}
    if not SF.get("gueltig") or not SF.get("einzel"): print("kein gueltiger Block spitze_foto (tools/spitze_aus_umriss.py)"); return 3
    from bauteile import spitze_ab
    A = np.array(SF["achse"], float); z_fuss = spitze_ab(SF) or float(SF["profil"][0][0]); z_top = float(SF["spitze_z"]) + 1.5
    # 23.11.2026 FOTOAUSWAHL ueber ALLE Kameras (vorher nur spitze_foto.einzel: am Schwabentor 10 Fotos aus 16 Grad Blickrichtung): Laterne ganz im Bild, gross genug
    # (--min-ppm) und FREI VOR HIMMEL (Himmelsmaske aus dem Cache von spitze_aus_umriss/dach_aus_fotos: Randpunkte neben der Laterne von der Krempe bis zur Spitze);
    # Fotos ohne Maske nur, wenn spitze_aus_umriss sie schon vor dem Himmel gemessen hat (einzel). Je 45-Grad-Sektor die besten, damit viele Richtungen zaehlen.
    import dach_aus_fotos as DA
    _, cams = FO.kameras_laden(a.objekt); sf_ein = {e[0] for e in SF["einzel"]}; cache = a.cache or os.path.join(Au, "himmel_cache")
    r_max = max([float(p[1]) for p in SF["profil"] if p[0] >= z_fuss - 1e-6] or [1.5]); xr_ = (1.25 * r_max + 0.2, 1.25 * r_max + 0.5)
    z_rand = np.linspace(float(SF.get("krempe_roh_z") or SF.get("krempe_z") or z_fuss + 1.0), float(SF["spitze_z"]), 8)
    kand = []; gruende = {}
    def grund(g): gruende[g] = gruende.get(g, 0) + 1
    for nr, (c, pf) in sorted(cams.items()):
        W0, H0 = c.get("bild") or (c["cx"] * 2, c["cy"] * 2)
        C = FO.projektion(np.array([[A[0], A[1], 0.0]]), c)[2]; az = math.degrees(math.atan2(C[1] - A[1], C[0] - A[0])); q = np.array([math.sin(math.radians(az)), -math.cos(math.radians(az))])
        ecken = np.array([[A[0] + x * q[0], A[1] + x * q[1], z] for x in (-xr_[1], xr_[1]) for z in (z_fuss, z_top)])
        pe, ze, _ = FO.projektion(ecken, c)
        if (ze <= 0).any() or (pe[:, 0] < 0).any() or (pe[:, 1] < 0).any() or (pe[:, 0] > W0 - 1).any() or (pe[:, 1] > H0 - 1).any(): grund("Laterne nicht ganz im Bild"); continue
        p0 = FO.projektion(np.array([[A[0], A[1], z_fuss + 2]]), c)[0]; p1 = FO.projektion(np.array([[A[0] + q[0], A[1] + q[1], z_fuss + 2]]), c)[0]; ppm0 = float(np.linalg.norm(p1 - p0))
        if ppm0 < a.min_ppm: grund("zu klein (px/m)"); continue
        M_, s_ = DA.himmel_laden(dict(name=nr, W0=int(round(W0)), H0=int(round(H0)), foto=pf), cache, nur_cache=True)
        if M_ is None:
            if nr not in sf_ein: grund("keine Himmelsmaske"); continue
            ha = None
        else:
            sm = M_.shape[1] / float(W0); ha = himmel_anteil(M_, lambda X: (FO.projektion(X, c)[0] * sm,), A, q, z_rand, (-xr_[1], -xr_[0], xr_[0], xr_[1]))
            if ha < MIN_HIMMEL: grund("nicht frei vor Himmel"); continue
        kand.append((ppm0, az, nr, c, pf, ha))
    kand = fotos_streuen(kand)
    print(f"Fotoauswahl: {len(kand)} Fotos aus Sektoren {sorted({int((k[1] % 360) // SEKTOR_GRAD) for k in kand})}; verworfen {gruende}")
    zs = np.round(np.arange(z_fuss, z_top, 0.05), 2); fotos = []
    for ppm0, az, nr, c, pf, ha in kand:
        im = cv2.imread(pf, cv2.IMREAD_GRAYSCALE)
        if im is None: continue
        sb = im.shape[1] / (c["cx"] * 2)                                                          # uint8 behalten (17 Fotos x 12 MP; float waeren 0,8 GB)
        q = np.array([math.sin(math.radians(az)), -math.cos(math.radians(az))]); ppm = ppm0 * sb
        if ppm < a.min_ppm: continue
        xs = np.arange(-max(2.5, xr_[1]), max(2.5, xr_[1]), 0.5 / ppm)
        # Breitenprofil in voller Aufloesung (aeussere Ausdehnung der Dunkelheit je Hoehe; Himmel/Dunkel je Foto aus einem Referenzband ueber die ganze Laterne)
        ref = zeile(im, c, sb, A, q, z_fuss, z_top - 1.0, xs, nz=25); hi = np.nanpercentile(ref, 97); lo = np.nanpercentile(ref, 3)
        dk = lambda I: np.clip((hi - I) / max(hi - lo, 1e-6), 0, 1)
        halb = {}
        for z in zs:
            s = dk(np.nan_to_num(zeile(im, c, sb, A, q, z, z, xs, nz=1), nan=hi)); e_ = ausdehnung(s, xs, schwelle=NADEL_DUNKEL if z > SF.get("krempe_z", z_fuss) + 3 else DUNKEL)
            if e_: halb[float(z)] = (e_[0], e_[1])
        # 23.11.2026 FARB-SILHOUETTE fuer die Haube (Huelle): Grauwert-Dunkelheit versagt vor tiefblauem Himmel (Himmel dunkler als das helle Kupfergruen - commons_orig2__190/191,
        # Haube 'endete' 1 m zu tief); Farbabstand zum Himmel (Median der Randpixel neben der Laterne, frei vor Himmel geprueft) trennt beides.
        imc = cv2.imread(pf)
        halb_f = farb_halb(lambda z0, z1, nz: zeile(imc, c, sb, A, q, z0, z1, xs, nz=nz), xs, zs, xr_[0], (z_fuss, z_top - 1.0),
                           lambda z: NADEL_DUNKEL if z > SF.get("krempe_z", z_fuss) + 3 else DUNKEL) if imc is not None else {}
        imc = None                                                                  # Farbbild freigeben (Speicher)
        C_ = FO.projektion(np.array([[A[0], A[1], 0.0]]), c)[2]; el = math.degrees(math.atan2(float(z_fuss + 3.0 - C_[2]), float(np.hypot(C_[0] - A[0], C_[1] - A[1]))))
        fotos.append(dict(nr=nr, az=az, ppm=ppm, c=c, sb=sb, q=q, xs=xs, dk=dk, hi=hi, lo=lo, halb=halb, im=im, pf=pf, himmel=ha, C=[float(v) for v in C_], el=el, halb_f=halb_f))
        print(f"{nr}: az {az:6.1f} Hoehenwinkel {el:5.1f} ppm {ppm:.0f} Hoehen {len(halb)}")
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
        d_, F["k_profil"] = profil_abweichung(F["halb"], pm)                     # freier Massstab: Vieleck je Blickrichtung verschieden breit
        if d_ > ABW_M: weg.append(F["nr"])
    fotos_alle = list(fotos)                                                      # Huelle der Haube: eigene Registrierung + Ausreisserprobe (Hoehenversatz, Farbsilhouette)
    if weg:
        fotos = [F for F in fotos if F["nr"] not in weg]; print("Ausreisser-Fotos (Breitenprofil):", weg)
        if len(fotos) < MIN_FOTOS: return schreiben(D, pp, a, dict(gueltig=False, grund=f"nach Ausreissern nur {len(fotos)} Fotos", ausreisser=weg), 4)
        P = median_profil(fotos)
    Z = zonen_aus_profil(P)
    if Z is None: return schreiben(D, pp, a, dict(gueltig=False, grund="Zonen (Pfosten/Krempe/Haube/Hals) im Breitenprofil nicht gefunden", profil=P), 4)
    # 23.11.2026 HAUBE ALS DREHKOERPER: ueber der Krempe Sehstrahl-Huelle (Kreis) statt Median der Halbbreiten (Krempe von unten ragt in die Taillen-Zeilen), Zonen neu
    HB, HZ = haube_huelle(fotos_alle, A, zs, P, Z)
    if HZ is not None: Z = HZ
    if a.roh and HB is not None:
        json.dump(dict(achse=[float(A[0]), float(A[1])], zh=[float(z) for z in HB["zh"]], P=P, Z0={k: v for k, v in zonen_aus_profil(P).items() if k != "i"},
                       beob=[dict(nr=B["nr"], C=B["C"], az=B["az"], A0=[float(v) for v in B["A0"]], zg=[float(z) for z in B["zg"]], dz=B.get("dz"), mitte=B.get("mitte"), rest=B.get("rest"), l=[None if not np.isfinite(v) else round(float(v), 4) for v in B["l"]],
                                  r=[None if not np.isfinite(v) else round(float(v), 4) for v in B["r"]]) for B in HB["alle"]], gut=[B["nr"] for B in HB["beob"]]), open(a.roh, "w"))
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
    # Pfosten: OFFENE ZONE je Foto aus der Silhouette (23.11.2026; vorher festes Band PF_BAND der Pfostenhoehe - lag in Fotos von unten am Dachfirst):
    # Zeilen vom Laternenfuss bis zur Pfostenoberkante, Dunkelheit je Zeile normiert (helle Pfosten vor Himmel), offene Zeilen = Himmel zwischen den Pfosten.
    zpf = zs[(zs >= zs[0]) & (zs <= Z["z_pfosten_oben"] + 1e-6)]
    bp, bh = [], []; zu_offen = {}
    for F in fotos:
        S = np.array([dunkel_zeile(zeile(F["im"], F["c"], F["sb"], A, F["q"], z, z, F["xs"], nz=1), F["hi"], F["lo"]) for z in zpf])
        oz, g_ = offene_zone(S, zpf, F["xs"]) if len(zpf) >= MIN_ZEILEN else (None, "Pfostenzone zu kurz")
        if oz: bp.append(dict(az=F["az"], x=F["xs"], s=oz["s"], c=oz["c"], h=oz["h"], nr=F["nr"], band=[round(oz["z0"], 2), round(oz["z1"], 2)], offen=oz["offen"]))
        else: zu_offen[F["nr"]] = g_                  # kein Himmel zwischen den Pfosten (Glocke/Dach dahinter/verdeckt) -> fuer die Pfostenzahl nicht verwendbar
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
        b = float(np.median(br)) if br else None; R = E[n]["R"]
        st_ = E[n].get("stimmen") or {}; sn = int(st_.get(str(n), 0))      # Formfamilie: die Eckenzahl muss in >= MIN_FAMILIE Fotos einzeln gewinnen
        fpf = float(np.median([np.max(np.abs(ecken_x(n, E[n]["phase"], B["az"])[0])) for B in bp]))      # Silhouette eines n-Ecks in dieser Lage = Umkreis x max|sin|
        erg["pfosten"] = dict(n=n, phase=E[n]["phase"], R=round(R, 3), silh_faktor=round(fpf, 3), breite=None if b is None else round(b, 3), abstand=ab, fotos=len(bp),
                              band=[round(float(np.median([B["band"][0] for B in bp])), 2), round(float(np.median([B["band"][1] for B in bp])), 2)],
                              baender={B["nr"]: B["band"] for B in bp}, mitten={B["nr"]: round(float(B["c"]), 3) for B in bp}, offen={B["nr"]: B["offen"] for B in bp}, az_bereich=[round(min(B["az"] for B in bp), 1), round(max(B["az"] for B in bp), 1)],
                              kandidaten={str(k): v for k, v in E.items()}, t=E[n].get("t"), t_grenze=t_grenze(len(bp)), stimmen=st_,
                              eindeutig=bool(E[n].get("t", 0) >= t_grenze(len(bp)) and sn >= MIN_FAMILIE))
    else: erg["pfosten_grund"] = f"nur {len(bp)} Fotos mit offener Pfostenzone (verlangt {MIN_FOTOS}) - keine Pfostenzahl, kein offener Bau"
    if len(bh) >= MIN_FOTOS:
        E, n, ab, ds = ecken_bewerten_beide(bh, offen=False)
        sg = 1 if ds == "kameras" else -1
        f = float(np.median([np.max(np.abs(ecken_x(n, E[n]["phase"], sg * B["az"])[0])) for B in bh]))      # Silhouette = Umkreis x max|sin|
        erg["haube"] = dict(n=n, phase=sg * E[n]["phase"], silh_faktor=round(f, 3), abstand=ab, fotos=len(bh), drehsinn=ds, kandidaten={str(k): v for k, v in E.items()},
                            band=[round(zb0, 2), round(zb1, 2)], t=E[n].get("t"), t_grenze=t_grenze(len(bh)), eindeutig=bool(E[n].get("t", 0) >= t_grenze(len(bh))))
    # 23.11.2026 QUERSCHNITT + PROFIL DER HAUBE aus der Sehstrahl-Huelle (Kreis/n-Eck durch Synthese, Fotobeleg >= MIN_FAMILIE Fotos), Familie aus dem Huellenprofil
    fam_h = None
    if HB is not None and HZ is not None:
        zb_ = (Z["z_taille"], Z["z_hals"]); Pf_q = erg.get("pfosten") or {}
        Q = querschnitt_haube(HB["beob"], A, HB["zh"], zb_, Z["r_bauch"], facetten=erg.get("haube"), n_fallback=Pf_q.get("n"), phase_fallback=float(Pf_q.get("phase") or 0.0))
        rq, Sq, bq = (HB["r"], HB["S"], HB["bindend"]) if Q["art"] == "rund" else drehprofil(HB["beob"], A, HB["zh"], Q["n"], Q["phase"])
        if Q["art"] != "rund": rq = glaetten(rq)
        sel = (HB["zh"] >= zb_[0] - 1e-6) & (HB["zh"] <= zb_[1] + 1e-6)
        bind_f = sorted({HB["beob"][i]["nr"] for i in range(len(HB["beob"])) for j in np.where(sel)[0] if Sq[i, j] <= 1.05 * rq[j] + 1e-3})
        fam_h = familie_aus_profil([(float(z), float(v)) for z, v in zip(HB["zh"][sel], rq[sel])])
        oben = HB["zh"] <= Z["z_knauf"] + 0.5
        erg["haube_huelle"] = dict(querschnitt=Q, profil=[[round(float(z), 2), round(float(v), 3), int(b)] for z, v, b in zip(HB["zh"][oben], rq[oben], bq[oben])],
                                   familie=fam_h if len(bind_f) >= MIN_FAMILIE else None, bindende_fotos=bind_f, k_huelle=K_HUELLE,
                                   registrierung=dict(dz={B["nr"]: B["dz"] for B in HB["beob"]}, mitte={B["nr"]: round(B["mitte"], 3) for B in HB["beob"]},
                                                      rest={B["nr"]: B.get("rest") for B in HB["beob"]}, weg=HB["weg"]),
                                   quelle="Sehstrahl-Huelle ueber der Krempe: je Foto groesster Querschnitt ganz in der Silhouette, Radius = " + f"{K_HUELLE}.-kleinster Fotowert")
        print(f"Haube Huelle: Querschnitt {Q['art']} {Q.get('n')} ({Q['quelle']}; Kreis-Rest {Q['rest_kreis']} m, bestes {Q['n_best']}-Eck {Q['rest_best']} m, t {Q['t']}, besser {Q['besser_fotos']}), "
              f"Familie {fam_h}, bindend {len(bind_f)} Fotos, raus {list(HB['weg'])}, dz {[B['dz'] for B in HB['beob']]}; Taille z {Z['z_taille']:.2f} r {Z['r_taille']:.2f}, Bauch z {Z['z_bauch']:.2f} r {Z['r_bauch']:.2f}, Hals z {Z['z_hals']:.2f} r {Z['r_hals']:.2f}, Knauf z {Z['z_knauf']:.2f} r {Z['r_knauf']:.2f}")
    # Formfamilie der Haube je Foto (Taille .. Hals)
    fam = {}
    for F in fotos:
        zr = [(z, (e_[1] - e_[0]) / 2) for z, e_ in sorted(F["halb"].items()) if Z["z_taille"] - 1e-6 <= z <= Z["z_hals"] + 1e-6]
        f_ = familie_aus_profil(zr)
        if f_: fam[f_] = fam.get(f_, 0) + 1
    fa = max(fam, key=fam.get) if fam else None
    einig = fa is not None and fam[fa] >= MIN_FAMILIE and all(v < fam[fa] for k, v in fam.items() if k != fa)     # Mehrheit, kein Gleichstand
    if (erg.get("haube_huelle") or {}).get("familie"): fa, einig = erg["haube_huelle"]["familie"], True        # Huelle aus >= MIN_FAMILIE bindenden Fotos schlaegt Einzelprofile
    erg.update(familie=fa if einig else None, familie_stimmen=fam, nadel_einzel=nadel_einzel, nadel_z=round(float(np.median(spitzen)), 2) if len(spitzen) >= MIN_FOTOS else None,
               nadel_streuung=round(float(np.median(np.abs(np.array(spitzen) - np.median(spitzen)))), 2) if len(spitzen) >= MIN_FOTOS else None)
    if erg["nadel_z"] is not None and erg["nadel_streuung"] > NADEL_STREUUNG_M:
        erg.update(nadel_grund=f"Nadelende streut {erg['nadel_streuung']} m (> {NADEL_STREUUNG_M}) - Bauteil nimmt spitze_foto.spitze_z", nadel_z_roh=erg["nadel_z"], nadel_z=None)
    ok_ = erg.get("pfosten", {}).get("eindeutig") and erg.get("haube") is not None and erg["familie"] is not None
    Pf_ = erg.get("pfosten") or {}
    g_ = [] if ok_ else ([erg.get("pfosten_grund")] if not Pf_ else [] if Pf_.get("eindeutig") else
                         [f"Pfosten-Eckenzahl {Pf_.get('n')} nicht eindeutig (t {Pf_.get('t')} / Grenze {Pf_.get('t_grenze')}, Stimmen {Pf_.get('stimmen')}, verlangt >= {MIN_FAMILIE})"])
    g_ += [] if ok_ or erg.get("haube") is not None else [f"Haube ohne >= {MIN_FOTOS} Fotos"]
    g_ += [] if ok_ or erg["familie"] is not None else [f"Haubenfamilie ohne >= {MIN_FAMILIE} einige Fotos"]
    erg.update(gueltig=bool(ok_), grund=None if ok_ else "; ".join(g_),
               annahmen=["ANNAHME: regelmaessiges n-Eck um die Dachachse (Lage aus dach_profil.json)",
                         "ANNAHME: Krempe hat die Eckenzahl und Lage der Pfosten (Dach ueber dem Pfostenviereck); Haube: Querschnitt siehe haube_huelle.querschnitt (Fotobeleg oder benannte ANNAHME)",
                         "Pfostenbreite = Breite der Dunkelheit um die aeusseren Pfosten (Unschaerfe macht sie etwas breiter)", "Glocke/Zifferblaetter im Inneren nicht gebaut"])
    if not ok_: print("UNGUELTIG:", erg["grund"])
    print(f"Pfosten {erg.get('pfosten', {}).get('n')} (Stimmen {erg.get('pfosten', {}).get('stimmen')}, t {erg.get('pfosten', {}).get('t')}, Band {erg.get('pfosten', {}).get('band')}, Abstand {erg.get('pfosten', {}).get('abstand')}, R {erg.get('pfosten', {}).get('R')}, Breite {erg.get('pfosten', {}).get('breite')}); "
          f"Haube {erg.get('haube', {}).get('n')} (Abstand {erg.get('haube', {}).get('abstand')}); Familie {erg['familie']} {fam}; Nadel z {erg['nadel_z']}")
    if a.bild:
        try: bild(fotos, A, erg, a.bild)
        except Exception as e: print("Bild fehlgeschlagen:", e)
    return schreiben(D, pp, a, erg, 0 if ok_ else 4)


def schreiben(D, pp, a, erg, rc):
    if a.aus: json.dump(erg, open(a.aus, "w"), indent=1); print("->", a.aus)
    else: D["laterne_foto"] = erg; json.dump(D, open(pp, "w"), indent=1); print("->", pp, "(Block laterne_foto)")
    return rc


def bild_auswahl(fotos, k=4, min_abstand=20.0):
    """Bis k Fotos fuer das Pruefbild: zuerst verschiedene Blickrichtungen (>= min_abstand Grad auseinander, je die meisten px/m), dann nach px/m auffuellen."""
    o = sorted(fotos, key=lambda F: -F["ppm"]); aus = []
    for F in o:
        if len(aus) < k and all(abs((F["az"] - G["az"] + 180) % 360 - 180) >= min_abstand for G in aus): aus.append(F)
    for F in o:
        if len(aus) < k and F not in aus: aus.append(F)
    return aus


def bild(fotos, A, erg, aus):
    """Pruefbild: bis 4 Fotos aus verschiedenen Blickrichtungen (Ausschnitt um die Laterne) mit den vorhergesagten Pfosten (gruen, in der offenen Zone DIESES Fotos,
    Zonengrenzen als kurze Querstriche) und Haubenkanten (magenta, im Bauchband)."""
    import cv2, flaeche_ortho as FO
    Z = erg["zonen"]; kach = []; Pf = erg.get("pfosten") or {}
    mit_pf = [F for F in fotos if F["nr"] in (Pf.get("baender") or {})]
    for F in bild_auswahl(mit_pf if len(mit_pf) >= 4 else fotos):                  # gezeigt werden die Fotos, die die Pfosten tragen (offene Zone gefunden)
        im = cv2.imread(F["pf"]) if F.get("pf") else cv2.cvtColor(F["im"], cv2.COLOR_GRAY2BGR); c, sb, q = F["c"], F["sb"], F["q"]
        P_ = lambda x, z: tuple(int(v) for v in (FO.projektion(np.array([[A[0] + x * q[0], A[1] + x * q[1], z]]), c)[0] * sb)[0])
        if Pf and F["nr"] in (Pf.get("baender") or {}):
            xe = ecken_x(Pf["n"], Pf["phase"], F["az"], Pf["R"])[0]; zb = Pf.get("baender", {}).get(F["nr"]) or Pf["band"]
            xe = xe + Pf.get("mitten", {}).get(F["nr"], 0.0) - (xe.max() + xe.min()) / 2          # wie ecken_bewerten: Mitte der Eckenspannweite = Mitte der Ausdehnung
            for x in xe: cv2.line(im, P_(x, zb[0]), P_(x, zb[1]), (0, 200, 0), 2)
            for zz in zb: cv2.line(im, P_(xe.min() - 0.35, zz), P_(xe.min() - 0.1, zz), (0, 200, 0), 2)     # Grenzen der offenen Zone
        E = erg.get("haube")
        if E:
            xe, sel = ecken_x(E["n"], E["phase"], F["az"], Z["r_bauch"] / E["silh_faktor"])
            for x in xe[sel]: cv2.line(im, P_(x, Z["z_bauch"] - 0.3), P_(x, Z["z_bauch"] + 0.3), (255, 0, 255), 2)
        a0 = P_(0, erg["z_fuss"] - 0.5); a1 = P_(0, (erg.get("nadel_z") or Z["z_knauf"]) + 0.5); h = abs(a0[1] - a1[1])
        k = im[max(0, a1[1]):a0[1], max(0, a0[0] - int(0.45 * h)):a0[0] + int(0.45 * h)]
        if k.size == 0: continue
        k = cv2.resize(k, (int(k.shape[1] * 500 / k.shape[0]), 500))
        cv2.putText(k, f"{F['nr'][-14:]} az {F['az']:.0f}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1); kach.append(k)
    if kach: cv2.imwrite(aus, np.hstack(kach), [cv2.IMWRITE_JPEG_QUALITY, 88]); print("Bild:", aus)


if __name__ == "__main__": sys.exit(main())
