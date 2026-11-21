#!/usr/bin/env python3
"""oeffnungen_aus_kanten.py - OEFFNUNGEN einer Wand (Tor, Rundbogen-, Spitzbogen-, Rechteckfenster) finden und vermessen, ohne Vorwissen (21.11.2026).

Luecke aus modelle/ANALYSE_SACKGASSEN_2026-11-21.md ("Oeffnungen ... Kette findet 1 von 2 Fenstern, Tor mit falschen Massen. LUECKE: Bogenform und Masse aus Kanten").
Eingang: <ebenen>/ebenen.json (tools/ebenen_bauplan.py; je WAND-Ebene o, d, n, w, zone, sweep.npz mit P = triangulierte Fotokanten), wahlweise --wolke (dichte Wolke, npy N x 3+).
Ebenenkoordinaten: u = (X_xy - o) . d, z = X_z, Tiefe = (X_xy - o) . n - w (negativ = hinter der Wand).

Je Wandebene:
 1. KANDIDATEN (Raster in der Wandebene):
    mit --wolke : Zelle 'hinten' = Belag der Wolke liegt tiefer als die oertliche Wandtiefe (Median im Umkreis), 'leer' = keine Wolkenpunkte (Durchblick),
                  'verdeckt' = nur Punkte VOR der Wand (Vorbau) -> keine Aussage. Zusammenhaengende Flecken hinten/leer, die ringsum von Wand umschlossen sind
                  (unten darf der Boden sein). Eine zweite Stufe sucht IM Fleck eine noch tiefere Zone (Fenster in der Nische).
    ohne --wolke: geschlossene Kantenzuege - Kantenpunkte zu einem Band verdickt (schliesst fehlende Stuecke), eingeschlossene freie Flaeche = Kandidat;
                  er gilt nur, wenn Kantenpunkte an seinem Rand HINTER der Wand liegen (hintere Laibungskante), sonst 'ohne_tiefe' (nur gezaehlt).
 2. FORM des oberen Abschlusses per Ausgleich des ganzen Umrisses (Laibung links, rechts, Abschluss; Nelder-Mead auf Huber-Abstand):
    sturz (gerade), rundbogen (Halbkreis), segmentbogen (Kreis, Stich < halbe Breite), spitzbogen (zwei Kreisboegen, Mittelpunkte auf Kaempferhoehe).
    Zuerst am Rand des Flecks (Wolkenrand bzw. Kantenband), dann - wenn genug Kantenpunkte den Umriss belegen - nur an den KANTENPUNKTEN ('form_quelle').
    Die einfachere Form bleibt, wenn die reichere den Rest nicht klar senkt; ohne klaren Sieger 'unbestimmt'.
 3. MASSE: Breite, Kaempfer, Scheitel, Sohlbank/Schwelle, Laibungstiefe - je mit tragenden Punkten und Rest; Annahmen stehen in 'annahmen'.
 4. WANDBILD-STUFE (21.11.2026 abends; Befund Schwabentor f00: Wolkenrand sagte 'rundbogen 5,37 m', das Bild zeigt einen Spitzbogen mit Fase): wenn fassade_fein da ist
    (--wandbild, Standard <ebenen>/../fassade_fein), je Oeffnung im FEINEN entzerrten Wandbild + Mittelbild (ortho_<fid>_fein.png, ortho_<fid>.png):
    a) Laibungskanten: durchgehende senkrechte Kanten (Zeilenmedian des Gradienten) in jedem Einzelfoto-Ortho; Hough ueber (Lage u0, Tiefe L) mit u_k = u0 + L * ru_k
       (Parallaxe; die Orthos sind aufs Relief projiziert -> relief_<fid>.png wird herausgerechnet) -> Kanten mit Lage, Tiefe, Fotozahl, Rest.
    b) Umriss je Form an die Bildkanten (Canny, nur gleichgerichtete Kanten; Chamfer-Abstand vom Umriss aus, Stoerkanten kosten nichts) -> am besten belegter Umriss
       -> KANTENZUG (Bildkantenpunkte daran) -> Formwahl per Punktausgleich wie am Wolkenrand (formen_ausgleich/form_waehlen).
    c) Gewaende/Fase: zweite parallele Kante (versatz_suche, nach innen bis 1/4 Breite, nach aussen nur bis Wolkenrand + 3 Zellen), eigener Ausgleich (zweite_kante);
       gilt nur mit Ruecksprung-Beleg aus den Einzelfotos (Innenkante tiefer als Aussenkante) und Beleg >= 2 x Untergrund.
    Ausgabe je Oeffnung: 'breite'/'kaempfer'/'scheitel' = LICHTE Oeffnung (Innenkante), 'aussenmass' = Aussenkante in der Wandebene inkl. Fase, 'gewaende' (links/rechts/Scheitel,
    Tiefe der Innenkante), je mit Quelle und Rest; der alte Wolkenumriss unter 'wolkenrand', Details unter 'wandbild'. Ohne Wandbild alles wie bisher (Fallback).
Ausgabe: <objektordner>/audit/oeffnungen_kanten.json, Bild audit/oeffnungen_kanten_<ebene>.jpg (--bild 1; mit Wandbild als Hintergrund). rc 0 = mindestens eine Oeffnung, rc 3 = keine.
Aufruf: oeffnungen_aus_kanten.py <objekt.json> <ebenen-ordner> [--wolke punkte.npy] [--bild 1] [--nur f00_wand] [--aus ordner] [--wandbild auto|<fassade_fein>|'']
Grenzen (gemessen Schwabentor 21.11.): die stabilen Fotokanten belegen Bogenkanten nur stueckweise - ohne Wolke bleibt dort kein geschlossener Zug; dann traegt der Wolkenrand
die Form ('form_quelle': 'wolkenrand') und die Kanten nur die Stuecke, die es gibt (Zahl steht dabei).
"""
import sys, os, json, argparse, numpy as np  # cv2 nur in der Wandbild-Stufe und im Kontrollbild (venv-seg)
from scipy import ndimage as ndi
from scipy.optimize import minimize
from scipy.spatial import cKDTree

# ---- Schwellen (alle mit Grund; keine ist an einem Bauwerk eingestellt) ----------------------------------------------------------------------
MASSSTAB = 87.0
DRUCK_MIN_M = 0.0008 * MASSSTAB      # 0,07 m: Mindestmass 0,8 mm in H0 (CLAUDE.md) - flachere Ruecksprunge / schmalere Oeffnungen sind nicht druckbar
ZELLE_MIN, ZELLE_MAX = 0.04, 0.10    # Rasterzelle: nicht feiner als das Wolkenrauschen (wenige cm), nicht groeber als ~Druckmindestmass
PUNKTE_JE_ZELLE = 10                 # Zellgroesse so, dass eine Wandzelle im duennen Viertel der Wand ~10 Wolkenpunkte hat (leere Zelle dann kein Zufall: Poisson e^-10)
WAND_UMKREIS_M = 2.0                 # oertliche Wandtiefe = Median im Umkreis +-2 m (Wand verjuengt sich / hat Absaetze); ANNAHME: Oeffnung fuellt den Umkreis nicht zur Haelfte
SIGMA_FAKTOR = 3.0                   # 'hinten' = tiefer als 3 Sigma der Wandrauheit (MAD), mindestens DRUCK_MIN_M
VOR_M = 0.30                         # Punkte > 0,3 m VOR der Wand = Vorbau/Draht (Kantentiefe streut 0,1-0,15 m, METHODE_EBENEN_BAUPLAN) -> 'verdeckt'
RING_M = 0.30                        # Ring um den Fleck, in dem Wand liegen muss
RING_WAND_MIN = 0.65                 # >= 65 % des Rings sind Wand (unter 50 % waere es eher ein Wandrand als ein Loch); bei Flecken OHNE Tiefenpunkte 0,8
MIN_BREITE, MIN_HOEHE = 2 * DRUCK_MIN_M, 4 * DRUCK_MIN_M   # kleinste Oeffnung: 2 x Mindestmass breit (Schlitz), 4 x hoch
KANTEN_LUECKE_M = 0.15               # Kantenband +-0,15 m schliesst fehlende Kantenstuecke bis 0,3 m (ANNAHME: Kantenzug zu >= ~85 % belegt)
FANG_ZELLEN = 3                      # Kantenpunkt 'traegt' einen Umriss, wenn er <= 3 Zellen daneben liegt
KLAR = 0.6                           # reichere/andere Form gewinnt nur, wenn ihr Rest <= 60 % des Rests der einfacheren ist
REST_MAX_ANTEIL = 0.06               # Rest > 6 % der Breite -> keine der Formen beschreibt den Umriss ('unbestimmt')
KANTEN_MIN_PUNKTE, KANTEN_MIN_BELEGT = 40, 0.5   # Form aus Kantenpunkten nur, wenn >= 40 Punkte >= 50 % der Umrisslaenge belegen
# Wandbild-Stufe (Bildkanten des feinen entzerrten Wandbilds, 21.11.2026 abends)
BILD_GLATT_M = 0.02                  # Glaettung vor dem Gradienten: 2 cm = Rundung einer verwitterten Steinkante; feiner misst die Bildkoernung (1-cm-Zelle) mit
RICHTUNG_COS = float(np.cos(np.radians(30)))   # Bildkante traegt den Umriss nur, wenn ihr Gradient <= 30 Grad von der Umrissnormalen abweicht (Sobel-Richtungsrauschen + raue Kante); radiale Bogenfugen tragen nicht
EINZEL_TOL_M = 0.03                  # dieselbe Kante in zwei Einzelfotos: <= 3 cm auseinander (Ausrichtung der Einzelorthos: mittlerer Versatz <= 3 cm, fassade_fein fein.json)
FOTOS_MIN = 3                        # eine Laibungskante gilt erst ab 3 Einzelfotos (Formfamilie aus >= 3 Fotos, CLAUDE.md)
FOTOS_MIN_ANTEIL = 0.25              # ... und in >= 1/4 der Fotos, die die Stelle sehen (ANNAHME: seltener = Textur, Schatten oder Verdeckung eines Fotos)
RU_SPANNE_MIN = 0.3                  # Kantentiefe aus der Parallaxe nur bei Blickrichtungsspanne >= 0,3 (wie oeffnungen_wandbild.tiefe_sweep); 3 cm Lagefehler -> Tiefe auf ~0,1 m
GEWAENDE_MAX_ANTEIL = 0.25           # ANNAHME: Gewaende/Fase je Seite schmaler als 1/4 der Wolkenbreite - weiter innen liegt Durchblick (hintere Portale), nicht das Gewaende
L_BEREICH = (-0.3, 1.5)              # gesuchte Kantentiefe: bis 0,3 m vor der Wand (Profil steht vor) bis 1,5 m dahinter (tiefer ist Durchblick, kein Gewaende)


def ebenen_koord(P, e):
    o, d, n = np.array(e["o"], float), np.array(e["d"], float), np.array(e["n"], float); xy = P[:, :2] - o
    return xy @ d, P[:, 2].astype(float), xy @ n - float(e.get("w", 0.0))


# ---- Umrissmodell ---------------------------------------------------------------------------------------------------------------------------
def umriss(uL, uR, zk, h, zs, schritt=0.01):
    """Punkte des Umrisses: Laibung links/rechts von zs (Sohlbank) bis zk (Kaempfer), Abschluss mit Stich h (0 = Sturz, b/2 = Halbkreis, > b/2 = Spitzbogen).
    Rueckgabe (Punkte, Teil) mit Teil 0 = links, 1 = rechts, 2 = Abschluss."""
    b = max(uR - uL, 1e-3); uc = 0.5 * (uL + uR); nj = max(2, int(max(zk - zs, 0.0) / schritt) + 1); zj = np.linspace(zs, max(zk, zs), nj)
    if h < 1e-3: t = np.linspace(uL, uR, max(2, int(b / schritt))); top = np.c_[t, np.full(len(t), zk)]
    elif h <= b / 2 + 1e-9:
        r = (b * b / 4 + h * h) / (2 * h); zc = zk + h - r; a0 = np.arctan2(zk - zc, b / 2); a = np.linspace(a0, np.pi - a0, max(8, int(r * (np.pi - 2 * a0) / schritt)))
        top = np.c_[uc + r * np.cos(a), zc + r * np.sin(a)]
    else:
        ex = (h * h - b * b / 4) / b; r = b / 2 + ex; a1 = np.arctan2(h, ex); a = np.linspace(0, a1, max(8, int(r * a1 / schritt)))
        re = np.c_[uc - ex + r * np.cos(a), zk + r * np.sin(a)]; top = np.vstack([re, np.c_[2 * uc - re[::-1, 0], re[::-1, 1]]])
    pts = np.vstack([np.c_[np.full(nj, uL), zj], np.c_[np.full(nj, uR), zj], top])
    return pts, np.r_[np.zeros(nj, int), np.ones(nj, int), np.full(len(top), 2)]


def _abst(p, form, Q, zs):
    uL, uR, zk = p[:3]; b = uR - uL
    if b <= 0.02 or zk < zs: return None
    h = 0.0 if form == "sturz" else b / 2 if form == "rundbogen" else p[3]
    if form == "segmentbogen" and not (0.02 * b <= h <= b / 2): return None
    if form == "spitzbogen" and not (b / 2 <= h <= 3 * b): return None
    M, _ = umriss(uL, uR, zk, h, zs, schritt=max(0.01, b / 300)); return cKDTree(M).query(Q)[0]


def fit_form(form, Q, start, zs, delta):
    """Ausgleich einer Form an die Punkte Q (N x 2). Kosten = mittlerer Huber-Abstand (delta) - fehlende Stuecke und Ausreisser ziehen nicht. Rueckgabe dict oder None."""
    def kost(p):
        d = _abst(p, form, Q, zs)
        if d is None: return 1e3
        return float(np.mean(np.where(d < delta, 0.5 * d * d, delta * (d - 0.5 * delta))))
    best = None
    for p0 in start:
        r = minimize(kost, np.array(p0, float), method="Nelder-Mead", options=dict(xatol=1e-3, fatol=1e-8, maxiter=600))
        if best is None or r.fun < best.fun: best = r
    d = _abst(best.x, form, Q, zs)
    if d is None: return None
    uL, uR, zk = best.x[:3]; b = uR - uL; h = 0.0 if form == "sturz" else b / 2 if form == "rundbogen" else float(best.x[3])
    return dict(form=form, uL=float(uL), uR=float(uR), zk=float(zk), h=float(h), rest=float(np.sqrt(np.mean(np.minimum(d, 4 * delta) ** 2))), median=float(np.median(d)),
                innen_anteil=float((d < delta).mean()), punkte=int(len(Q)))


def formen_ausgleich(Q, uL, uR, zt, zs, delta):
    """Alle vier Formen an Q; Startwerte aus dem groben Rahmen (uL, uR, Oberkante zt)."""
    b = uR - uL; F = {}
    F["sturz"] = fit_form("sturz", Q, [[uL, uR, zt]], zs, delta)
    F["rundbogen"] = fit_form("rundbogen", Q, [[uL, uR, zt - b / 2]], zs, delta)
    F["segmentbogen"] = fit_form("segmentbogen", Q, [[uL, uR, zt - f * b, f * b] for f in (0.12, 0.3)], zs, delta)
    F["spitzbogen"] = fit_form("spitzbogen", Q, [[uL, uR, zt - f * b, f * b] for f in (0.65, 0.9, 1.3)], zs, delta)
    F = {k: v for k, v in F.items() if v}; bog = [v["zk"] for k, v in F.items() if k != "sturz"]
    if bog:                                                # Entscheidungsrest nur im ABSCHLUSSBEREICH (ueber dem tiefsten Kaempfer der Bogenformen): die Laibungen darunter sind allen Formen gemeinsam und verduennen den Unterschied
        ob = Q[:, 1] >= min(bog)
        for k, v in F.items():
            d = _abst([v["uL"], v["uR"], v["zk"], v["h"]], k, Q[ob], zs) if ob.sum() >= 10 else None
            v["rest_gesamt"] = v["rest"]
            if d is not None: v["rest"] = float(np.sqrt(np.mean(np.minimum(d, 4 * delta) ** 2))); v["punkte_abschluss"] = int(ob.sum())
    return F


def form_waehlen(F, zelle):
    """Einfachste Form, deren Rest nicht klar unterboten wird. Rueckgabe (form, grund)."""
    if "sturz" not in F or "rundbogen" not in F: return "unbestimmt", "Ausgleich gescheitert"
    boden = 0.3 * zelle                                   # Reste unter dem Rasterrauschen (Stufe +-Zelle/2 -> ~0,3 Zelle) sind gleich gut
    R = {k: max(v["rest"], boden) for k, v in F.items()}; b = F["rundbogen"]["uR"] - F["rundbogen"]["uL"]
    eins, zwei = sorted(("sturz", "rundbogen"), key=lambda k: R[k]); form = eins if R[eins] <= KLAR * R[zwei] else None
    sp, sg = F.get("spitzbogen"), F.get("segmentbogen")
    if form == "rundbogen":
        if sp and R["spitzbogen"] <= KLAR * R["rundbogen"] and sp["h"] / (sp["uR"] - sp["uL"]) > 0.55: form = "spitzbogen"      # Stich > 55 % der Breite: sonst vom Halbkreis (50 %) nicht zu trennen
        elif sg and R["segmentbogen"] <= KLAR * R["rundbogen"] and sg["h"] / (sg["uR"] - sg["uL"]) < 0.45: form = "segmentbogen"
    elif form == "sturz":
        if sg and R["segmentbogen"] <= KLAR * R["sturz"] and sg["h"] > 2 * zelle: form = "segmentbogen"                          # Stich > 2 Zellen: sonst ist es ein gerader Sturz mit Rauschen
        if sp and R["spitzbogen"] <= KLAR * R[form]: form = "spitzbogen"
    else:
        reich = [k for k in ("spitzbogen", "segmentbogen") if k in F and R[k] <= KLAR * R[eins]]
        if reich: form = min(reich, key=lambda k: R[k])
        else: return "unbestimmt", f"sturz {R['sturz']:.3f} gegen rundbogen {R['rundbogen']:.3f}: kein klarer Sieger (Faktor {KLAR})"
    if R[form] > REST_MAX_ANTEIL * b: return "unbestimmt", f"beste Form {form} mit Rest {R[form]:.3f} m > {REST_MAX_ANTEIL:.0%} der Breite"
    return form, "Rest " + ", ".join(f"{k} {F[k]['rest']:.3f}" for k in F)


# ---- Kandidaten -----------------------------------------------------------------------------------------------------------------------------
def _kreis(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]; return x * x + y * y <= r * r


def zellgroesse(u, z, zone):
    """Zelle so, dass im duennen Viertel der belegten 0,5-m-Bloecke ~PUNKTE_JE_ZELLE Punkte je Zelle liegen."""
    u0, u1, z0, z1 = zone; H, _, _ = np.histogram2d(z, u, bins=[np.arange(z0, z1 + 0.5, 0.5), np.arange(u0, u1 + 0.5, 0.5)]); bel = H[H > 0]
    if len(bel) < 4: return ZELLE_MAX
    dichte = np.percentile(bel, 25) / 0.25; return float(np.clip(round(np.sqrt(PUNKTE_JE_ZELLE / max(dichte, 1e-9)), 2), ZELLE_MIN, ZELLE_MAX))


def raster_wolke(uw, zw, ww, zone, zelle, tmax=5.0):
    """Je Zelle: Tiefe T (Median der Punkte bis VOR_M vor der Wand), Zahl n, verdeckt (nur Punkte vor der Wand)."""
    u0, u1, z0, z1 = zone; nu, nz = int(np.ceil((u1 - u0) / zelle)), int(np.ceil((z1 - z0) / zelle))
    iu, iz = np.floor((uw - u0) / zelle).astype(int), np.floor((zw - z0) / zelle).astype(int); ok = (iu >= 0) & (iu < nu) & (iz >= 0) & (iz < nz) & (ww > -tmax)
    iu, iz, ww = iu[ok], iz[ok], ww[ok]; vor = ww > VOR_M; idx = iz * nu + iu
    nv = np.bincount(idx[vor], minlength=nu * nz).reshape(nz, nu); i2, w2 = idx[~vor], ww[~vor]; n = np.bincount(i2, minlength=nu * nz)
    o = np.lexsort((w2, i2)); i2, w2 = i2[o], w2[o]; start = np.r_[0, np.cumsum(n)[:-1]]; T = np.full(nu * nz, np.nan); bel = n > 0; T[bel] = w2[(start + n // 2)[bel]]
    n = n.reshape(nz, nu); return T.reshape(nz, nu), n, (nv > n)


def wandtiefe(T, zelle):
    """Oertliche Wandtiefe W0 und oertliche Rauheit S (1,4826 x MAD): Median der Zelltiefen im Umkreis WAND_UMKREIS_M (auf 0,5-m-Bloecken, dann linear verfeinert).
    Oertlich, weil Waende unten oft bossiert (rau) und oben verputzt (glatt) sind - eine einzige Schwelle waere oben zu grob oder unten zu fein."""
    k = max(1, int(round(0.5 / zelle))); nz, nu = T.shape; bz, bu = int(np.ceil(nz / k)), int(np.ceil(nu / k)); G = np.full((bz, bu), np.nan); S = np.full((bz, bu), np.nan); r = int(round(WAND_UMKREIS_M / zelle))
    for i in range(bz):
        for j in range(bu):
            a = T[max(0, i * k + k // 2 - r):i * k + k // 2 + r + 1, max(0, j * k + k // 2 - r):j * k + k // 2 + r + 1]; a = a[np.isfinite(a)]
            if len(a) >= 20: G[i, j] = np.median(a); S[i, j] = 1.4826 * np.median(np.abs(a - G[i, j]))
    if not np.isfinite(G).any(): return np.zeros_like(T), np.full_like(T, 0.03)
    idx = ndi.distance_transform_edt(~np.isfinite(G), return_distances=False, return_indices=True); G, S = G[tuple(idx)], S[tuple(idx)]
    f = lambda A: ndi.zoom(A, (nz / bz, nu / bu), order=1, mode="nearest", grid_mode=True)[:nz, :nu]
    return f(G), f(S)


def flecken_wolke(T, n, verdeckt, zelle, W0, schwelle, innerhalb=None, rand_frei=True, boden=None):
    """Flecken hinten/leer, von Wand umschlossen. W0 = Bezugstiefe je Zelle, schwelle = Ruecksprung je Zelle, ab dem 'hinten' gilt. Rueckgabe (Liste dict(maske, ...), boden_zeile)."""
    D = T - W0; fin = np.isfinite(D) & ~verdeckt; wand = fin & (D >= -schwelle); hinten = fin & (D < -schwelle); leer = (n == 0) & ~verdeckt
    bereich = np.ones_like(wand) if innerhalb is None else innerhalb
    if boden is None: zeilen = np.where((wand & bereich).sum(1) >= 0.3 * max(1, bereich.sum(1).max()))[0]; boden = int(zeilen.min()) if len(zeilen) else 0     # Boden = unterste Zeile, die zu >= 30 % Wand ist
    O = (hinten | leer) & bereich; O[:boden] = False; L, nl = ndi.label(O); aus = []; ring_r = max(2, int(round(RING_M / zelle))); teile = []
    for k, sl in enumerate(ndi.find_objects(L), 1):
        if (sl[1].stop - sl[1].start) * zelle < MIN_BREITE or (sl[0].stop - sl[0].start) * zelle < MIN_HOEHE: continue
        if rand_frei and (sl[1].start == 0 or sl[1].stop == O.shape[1] or sl[0].stop == O.shape[0]): continue          # beruehrt Seitenrand/Oberrand der Zone = nicht umschlossen
        m = L == k; bodenlos = bool(sl[0].start <= boden + 1)
        # ERST Inseln im Fleck fuellen (Menschen/Autos im Tor, Rauschpunkte, Verdecktes gehoeren zum Loch; steht der Fleck auf dem Boden, schliesst der Boden ihn unten ab),
        # DANN Einzelzellen/duenne Faeden abtragen (kleinstes Mass = 3 Zellen) - umgekehrt zerfaellt ein loechriges Tor-Inneres in Kruemel
        sockel = np.zeros((1, m.shape[1]), bool); sockel[0, sl[1].start:sl[1].stop] = bodenlos
        m = m.copy(); m[boden:] = ndi.binary_fill_holes(np.vstack([sockel, m[boden:]]))[1:] & bereich[boden:]; m = ndi.binary_opening(m, np.ones((3, 3))); L2, _ = ndi.label(m)
        teile += [(L2 == j, s2) for j, s2 in enumerate(ndi.find_objects(L2), 1)]
    for m, sl in teile:
        hz, hu = (sl[0].stop - sl[0].start) * zelle, (sl[1].stop - sl[1].start) * zelle
        if hu < MIN_BREITE or hz < MIN_HOEHE: continue
        bodenlos = bool(sl[0].start <= boden + 1)
        ring = ndi.binary_dilation(m, _kreis(ring_r)) & ~m & bereich & ~verdeckt; ring[:boden] = False      # verdeckte Zellen (Vorbau, Auto davor) sagen nichts ueber die Wand
        if ring.sum() == 0: continue
        rw = float((wand & ring).sum() / ring.sum()); nh = int((hinten & m).sum()); anteil_h = nh / m.sum()
        if rw < (RING_WAND_MIN if anteil_h >= 0.2 else 0.8): continue
        aus.append(dict(maske=m, ring_wand=round(rw, 2), anteil_hinten=round(anteil_h, 2), bodenlos=bodenlos,
                        tiefe=float(-np.median(D[hinten & m])) if nh >= 5 else None, tiefe_zellen=nh))
    return aus, boden


def glatt(T):
    """3x3-Median der Zelltiefen (leere Zellen bleiben leer): nimmt das Zellrauschen, damit ein flacher Ruecksprung (Nische ~0,1-0,15 m) geschlossen statt fleckig erscheint; Ecken runden um <= 1 Zelle."""
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); G = ndi.generic_filter(T, np.nanmedian, size=3, mode="constant", cval=np.nan)
    G[~np.isfinite(T)] = np.nan; return G


def schwellenkarte(T, W0, verdeckt):
    """Schwelle 'hinten' fuer die ganze Ebene: SIGMA_FAKTOR x Wandrauheit (1,4826 x MAD der Zelltiefen gegen die oertliche Wandtiefe, nur Zellen naeher als 0,5 m = Band der Wandebene),
    mindestens DRUCK_MIN_M. Versucht 21.11.: Rauheit OERTLICH im 2-m-Umkreis - verworfen, die Oeffnung selbst blaeht dort die Streuung auf (Schwelle am Tor 0,75 m)."""
    D = T - W0; nah = np.isfinite(D) & ~verdeckt & (np.abs(D) < 0.5); sig = 1.4826 * float(np.median(np.abs(D[nah] - np.median(D[nah])))) if nah.sum() > 50 else 0.03
    return max(DRUCK_MIN_M, SIGMA_FAKTOR * sig)


def fleck_fein(f, wolke, zone, zelle, W0, S, n_grob, z_boden):
    """Fleck im eigenen Ausschnitt mit feinerer Zelle neu rastern, wenn die Wolke dort dichter ist als im duennen Viertel der Wand (Umriss dann auf Zelle/2 genauer).
    Rueckgabe (fleck, u0, z0, zelle, T, n, verdeckt, W0, Schwelle) im Ausschnitt oder None."""
    uw, zw, ww = wolke; ys, xs = np.where(f["maske"]); r = 0.5
    a = [zone[0] + xs.min() * zelle - r, zone[0] + (xs.max() + 1) * zelle + r, max(z_boden, zone[2] + ys.min() * zelle - r), zone[2] + (ys.max() + 1) * zelle + r]
    ink = (uw >= a[0]) & (uw <= a[1]) & (zw >= a[2]) & (zw <= a[3]); wn = ink & (np.abs(ww) < 0.5)
    if wn.sum() < 500: return None
    ring = ndi.binary_dilation(f["maske"], _kreis(int(round(r / zelle)))) & ~f["maske"] & (n_grob > 0)                    # Dichte der WAND um den Fleck (im Fleck selbst ist die Wolke duenn)
    if ring.sum() < 10: return None
    zf = float(np.clip(round(np.sqrt(PUNKTE_JE_ZELLE / (np.percentile(n_grob[ring], 25) / zelle ** 2)), 2), ZELLE_MIN, ZELLE_MAX))
    if zf > 0.8 * zelle: return None
    T, n, verd = raster_wolke(uw[ink], zw[ink], ww[ink], a, zf); nz, nu = T.shape
    iy = np.clip(((a[2] + (np.arange(nz) + 0.5) * zf - zone[2]) / zelle).astype(int), 0, W0.shape[0] - 1); ix = np.clip(((a[0] + (np.arange(nu) + 0.5) * zf - zone[0]) / zelle).astype(int), 0, W0.shape[1] - 1)
    W0f = W0[np.ix_(iy, ix)]; alt = f["maske"][np.ix_(iy, ix)]; T = glatt(T); fl, _ = flecken_wolke(T, n, verd, zf, W0f, S, boden=max(0, int(round((z_boden - a[2]) / zf))))
    fl = [g for g in fl if (g["maske"] & alt).sum() >= 0.5 * min(g["maske"].sum(), alt.sum())]
    if not fl: return None
    g = max(fl, key=lambda g_: (g_["maske"] & alt).sum()); return g, a[0], a[2], zf, T, n, verd, W0f, S


def flecken_kanten(u, z, w, zone, zelle):
    """Geschlossene Kantenzuege ohne Wolke: Kantenband verdickt, eingeschlossene freie Flaeche. Boden = zehnttiefster Kantenpunkt (ANNAHME: tiefste Kanten stehen am Boden; 10 statt 1 gegen Einzelausreisser)."""
    u0, u1, z0, z1 = zone; zb = float(np.sort(z)[min(9, len(z) - 1)]) if len(z) else z0; nu, nz = int(np.ceil((u1 - u0) / zelle)), int(np.ceil((z1 - zb) / zelle))
    iu, iz = np.floor((u - u0) / zelle).astype(int), np.floor((z - zb) / zelle).astype(int); ok = (iu >= 0) & (iu < nu) & (iz >= 0) & (iz < nz)
    K = np.zeros((nz, nu), bool); K[iz[ok], iu[ok]] = True; g = max(1, int(round(KANTEN_LUECKE_M / zelle))); B = ndi.binary_dilation(K, _kreis(g))
    frei = np.pad(~B, ((0, 1), (1, 1)), constant_values=True); L, _ = ndi.label(frei); aussen = set(np.unique(np.r_[L[-1], L[:, 0], L[:, -1]])); L = L[:-1, 1:-1]; aus = []     # unten zu (Boden), oben/seitlich offen
    Hh = np.zeros((nz, nu), int); hin = ok & (w < -DRUCK_MIN_M); np.add.at(Hh, (iz[hin], iu[hin]), 1); Ha = np.zeros((nz, nu), int); np.add.at(Ha, (iz[ok], iu[ok]), 1)
    for k, sl in enumerate(ndi.find_objects(L), 1):
        if sl is None or k in aussen or k == 0: continue
        if (sl[1].stop - sl[1].start) * zelle < MIN_BREITE or (sl[0].stop - sl[0].start) * zelle < MIN_HOEHE: continue      # schon die FREIE Flaeche im Band muss das Mindestmass haben (sonst sind es Poren im Kantenhaufen)
        m = ndi.binary_dilation(L == k, _kreis(g)); ys, xs = np.where(m); hz, hu = (ys.max() - ys.min() + 1) * zelle, (xs.max() - xs.min() + 1) * zelle
        if hu < MIN_BREITE or hz < MIN_HOEHE: continue
        rand = ndi.binary_dilation(m, _kreis(g)) & ~ndi.binary_erosion(m, _kreis(g)); na, nh = int(Ha[rand].sum()), int(Hh[rand].sum())
        tief = nh >= 10 and nh >= 0.1 * na                                                           # >= 10 Punkte und >= 10 % der Randpunkte liegen hinter der Wand = hintere Laibungskante
        M = np.zeros((nz, nu), bool); M[:] = m
        aus.append(dict(maske=M, ring_wand=None, anteil_hinten=round(nh / max(na, 1), 2), bodenlos=bool(ys.min() <= g), tiefe=None, tiefe_zellen=0, ohne_tiefe=not tief))
    return aus, zb


# ---- Vermessung -----------------------------------------------------------------------------------------------------------------------------
def rand_punkte(m, u0, z0, zelle):
    """Randpunkte des Flecks auf den Zellkanten (Treppenlinie, Fehler <= Zelle/2), ohne die Unterkante."""
    f = 4; ys, xs = np.where(m); y0, x0 = ys.min() - 1, xs.min() - 1; sub = m[max(y0, 0):ys.max() + 2, max(x0, 0):xs.max() + 2]; y0, x0 = max(y0, 0), max(x0, 0)
    g = np.kron(sub, np.ones((f, f), bool)); r = g & ~ndi.binary_erosion(g, np.ones((3, 3)), border_value=0); ry, rx = np.where(r)
    # Zellkante statt Mitte des Randpixels: Pixelmitte liegt 1/(2f) Zelle innen
    uu = u0 + (x0 + (rx + 0.5) / f) * zelle; zz = z0 + (y0 + (ry + 0.5) / f) * zelle; return np.c_[uu, zz]


def vermessen(fl, u0, z0, zelle, kant, nur_kanten=False, z_boden=None):
    m = fl["maske"]; ys, xs = np.where(m); R = rand_punkte(m, u0, z0, zelle); zs = z0 + ys.min() * zelle; zt = z0 + (ys.max() + 1) * zelle
    if fl["bodenlos"] and z_boden is not None: zs = z_boden                          # Fleck steht auf dem Boden: Schwelle = Boden (ANNAHME, steht in annahmen)
    # grobe Laibung: Median der Zeilenraender in der unteren Haelfte
    zeil = np.arange(ys.min(), ys.min() + max(1, (ys.max() - ys.min() + 1) // 2)); li = [np.where(m[i])[0].min() for i in zeil if m[i].any()]; re = [np.where(m[i])[0].max() + 1 for i in zeil if m[i].any()]
    uL, uR = u0 + float(np.median(li)) * zelle, u0 + float(np.median(re)) * zelle
    if uR - uL < MIN_BREITE: return None
    Q = R[R[:, 1] > zs + 2 * zelle]                                                 # Unterkante gehoert nicht zum Umrissmodell (Sohlbank wird eigens gemessen)
    if len(Q) < 20: return None
    delta = 2 * zelle; F = formen_ausgleich(Q, uL, uR, zt, zs, delta); form, grund = form_waehlen(F, zelle); quelle = "kantenband" if nur_kanten else "wolkenrand"; Fk = None; nk = 0; bel = 0.0
    ku, kz, kw = kant
    if len(ku):
        nah = cKDTree(R).query(np.c_[ku, kz])[0] <= FANG_ZELLEN * zelle; nah &= kz > zs + 2 * zelle; Qk = np.c_[ku[nah], kz[nah]]; nk = int(nah.sum())
        bez = F.get(form) or min(F.values(), key=lambda f_: f_["rest"])
        if nk >= 5:
            M, _ = umriss(bez["uL"], bez["uR"], bez["zk"], bez["h"], zs, schritt=0.1); bel = float((cKDTree(Qk).query(M)[0] <= FANG_ZELLEN * zelle).mean())
        if nk >= KANTEN_MIN_PUNKTE and bel >= KANTEN_MIN_BELEGT:
            Fk = formen_ausgleich(Qk, bez["uL"], bez["uR"], bez["zk"] + bez["h"], zs, delta); fk, gk = form_waehlen(Fk, zelle)
            if fk != "unbestimmt": form, grund, quelle = fk, gk, "kanten"; F = Fk
    ann = []
    if form == "unbestimmt": bez = min(F.values(), key=lambda f_: f_["rest"]) if F else None; ann.append("ANNAHME: Form unbestimmt - Masse aus der Form mit dem kleinsten Rest (" + (bez["form"] if bez else "-") + ")")
    else: bez = F[form]
    if bez is None: return None
    b = bez["uR"] - bez["uL"]; M, teil = umriss(bez["uL"], bez["uR"], bez["zk"], bez["h"], zs); tr = {}
    if len(ku):
        nah = (ku > bez["uL"] - 1) & (ku < bez["uR"] + 1) & (kz > zs - 1) & (kz < zt + 1); dd, ii = cKDTree(M).query(np.c_[ku[nah], kz[nah]]); tg = dd <= FANG_ZELLEN * zelle
        for t, name in enumerate(("laibung_links", "laibung_rechts", "abschluss")):
            q = tg & (teil[ii] == t); tr[name] = dict(kantenpunkte=int(q.sum()), rest=round(float(np.sqrt(np.mean(dd[q] ** 2))), 3) if q.any() else None)
        wk = kw[nah][tg]; lk = dict(kantenpunkte=int(len(wk)), tiefste_kante=round(float(-np.percentile(wk, 10)), 2) if len(wk) >= 10 else None)      # 10. Perzentil = hintere Laibungskante (Tiefe der Kante streut 0,1-0,15 m)
        us = ku[nah & (np.abs(kz - zs) <= FANG_ZELLEN * zelle) & (ku > bez["uL"]) & (ku < bez["uR"])] if nah.any() else []
        ks = nah & (np.abs(kz - zs) <= FANG_ZELLEN * zelle) & (ku > bez["uL"]) & (ku < bez["uR"]); n_sohl = int(ks.sum()); z_sohl_k = round(float(np.median(kz[ks])), 2) if n_sohl >= 10 and not fl["bodenlos"] else None      # am Boden gibt es keine Sohlbankkante (Punkte dort sind Laibungsenden)
    else: lk = dict(kantenpunkte=0, tiefste_kante=None); n_sohl = 0; z_sohl_k = None
    if fl["bodenlos"]: ann.append("ANNAHME: Schwelle = Boden (unterste Wandzeile bzw. unterste Kantenpunkte); keine eigene Schwellenkante")
    sicher = nur_kanten or fl.get("tiefe") is not None
    if fl.get("tiefe") is None and not nur_kanten: ann.append("ANNAHME: Durchblick oder Wolkenluecke - im Inneren keine Tiefenpunkte, Laibungstiefe nicht gemessen")
    if quelle != "kanten": ann.append(f"Form aus dem {quelle.replace('wolkenrand', 'Rand des Wolkenflecks')}: nur {nk} Kantenpunkte am Umriss, {bel:.0%} der Umrisslaenge belegt (noetig {KANTEN_MIN_PUNKTE} / {KANTEN_MIN_BELEGT:.0%})")
    bog = form in ("rundbogen", "segmentbogen", "spitzbogen") or (form == "unbestimmt" and bez["h"] > 0)
    r3 = lambda x: None if x is None else round(float(x), 3)
    return dict(form=form, sicher=bool(sicher), form_grund=grund, form_quelle=quelle, zone=[r3(bez["uL"]), r3(bez["uR"]), r3(zs), r3(bez["zk"] + bez["h"])], mitte_u=r3(0.5 * (bez["uL"] + bez["uR"])),
                breite=dict(wert=r3(b), punkte=bez["punkte"], rest=r3(bez["rest"]), kantenpunkte_links=tr.get("laibung_links", {}).get("kantenpunkte", 0), kantenpunkte_rechts=tr.get("laibung_rechts", {}).get("kantenpunkte", 0)),
                kaempfer=dict(wert=r3(bez["zk"]) if bog else None, hinweis=None if bog else "gerader Sturz: kein Kaempfer"),
                scheitel=dict(wert=r3(bez["zk"] + bez["h"]), stich=r3(bez["h"]), kantenpunkte=tr.get("abschluss", {}).get("kantenpunkte", 0), rest_kanten=tr.get("abschluss", {}).get("rest")),
                sohlbank=dict(wert=r3(z_sohl_k if z_sohl_k is not None else zs), quelle="kanten" if z_sohl_k is not None else ("boden" if fl["bodenlos"] else "fleckrand"), kantenpunkte=n_sohl, fleckrand=r3(zs)),
                laibung_tiefe=dict(wolke=r3(fl.get("tiefe")), wolke_zellen=fl.get("tiefe_zellen", 0), kanten=lk["tiefste_kante"], kantenpunkte=lk["kantenpunkte"]),
                radius=r3((b * b / 4 + bez["h"] ** 2) / (2 * bez["h"])) if form in ("rundbogen", "segmentbogen") else r3(b / 2 + (bez["h"] ** 2 - b * b / 4) / b) if form == "spitzbogen" else None,
                reste={k: dict(rest=r3(v["rest"]), median=r3(v["median"]), punkte=v["punkte"]) for k, v in F.items()}, kantenpunkte_am_umriss=nk, umriss_belegt=round(bel, 2),
                ring_wand=fl.get("ring_wand"), anteil_hinten=fl.get("anteil_hinten"), annahmen=ann, _fit=bez, _zs=zs)


# ---- Wandbild-Stufe: Laibungs- und Bogenkanten im feinen entzerrten Wandbild -----------------------------------------------------------------
def kameras_lesen(objekt_json):
    """Kamerazentren aus <objektordner>/messprotokoll/K-*.json (wie oeffnungen_wandbild.kameras)."""
    import glob, cv2
    K = {}
    for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(objekt_json)), "messprotokoll", "K-*.json")):
        try: c = json.load(open(f)).get("kamera")
        except Exception: continue
        if isinstance(c, dict) and "rvec" in c and "t" in c: K[os.path.basename(f)[2:-5]] = -cv2.Rodrigues(np.array(c["rvec"], float))[0].T @ np.array(c["t"], float)
    return K


def wandbild_laden(fein_dir, e, objekt_json=None):
    """Wandbild der Fassade zur Ebene e: ortho_<fid>_fein.png (sonst ortho_<fid>.png) aus fassade_fein (1 cm), dazu die Einzelfoto-Orthos ortho_<fid>_einzeln/ mit Kamerazentren.
    Rueckgabe dict(F, bild (grau float32, 0 = leer), quelle, einzeln [(name, grau uint8 mit 0 = nicht gesehen, C)], ...) oder None (dann arbeitet das Werkzeug wie bisher)."""
    import glob, cv2
    fj = os.path.join(fein_dir or "", "fassaden.json")
    if not fein_dir or not os.path.exists(fj): return None
    fid = e.get("fassade") or e["id"].split("_")[0]; F = next((f for f in json.load(open(fj)).get("fassaden", []) if f.get("id") == fid), None)
    if F is None or "raster" not in F: return None
    if abs(np.dot(np.array(e["d"], float), np.array(F["d"], float))) < 0.99: return None          # Ebene und Fassade > 8 Grad verdreht: u nicht uebertragbar
    bilder = []
    for name in (f"ortho_{fid}_fein.png", f"ortho_{fid}.png"):
        p = os.path.join(fein_dir, name)
        if not os.path.exists(p): continue
        im = cv2.imread(p); g_ = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32); g_[im.sum(2) == 0] = 0; bilder.append((name, g_))
    if not bilder: return None
    name, bild = bilder[0]
    C = kameras_lesen(objekt_json) if objekt_json else {}; einz = []
    for q in sorted(glob.glob(os.path.join(fein_dir, f"ortho_{fid}_einzeln", "*.png"))):
        nr = os.path.basename(q)[:-4]
        if nr not in C: continue
        a = cv2.imread(q)
        if a is None or a.shape[:2] != im.shape[:2]: continue
        g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY); g = np.maximum(g, 1); g[a.sum(2) == 0] = 0; einz.append((nr, g, np.asarray(C[nr], float)))
    rp = os.path.join(fein_dir, f"relief_{fid}.png"); rel = None                                        # Projektionsflaeche der Orthos (fassade_ortho: vorderste Modellflaeche, s + 10 m in mm, 0 = keine -> Wandebene)
    if os.path.exists(rp):
        R = cv2.imread(rp, cv2.IMREAD_UNCHANGED)
        if R is not None and R.shape[:2] == im.shape[:2]: rel = np.where(R > 0, R.astype(np.float32) / 1000.0 - 10.0, 0.0).astype(np.float32)
    W = wandbild_aus(F, bild, e, einz, quelle=" + ".join(n_ for n_, _ in bilder), relief=rel); W["bilder"] = [b_ for _, b_ in bilder]; return W


def wandbild_aus(F, bild, e, einzeln=(), quelle="bild", relief=None):
    """Wandbild-dict aus Fassade F (o, d, n, raster{u0, z1, zelle}), Graubild (0 = leer), Einzelfotos [(name, grau uint8 0 = leer, Kamerazentrum xyz)] und Relief der
    Projektionsflaeche (m, + = vor der Fassadenebene; None = Ebene). Auch fuer Tests."""
    fo, fd = np.array(F["o"], float), np.array(F["d"], float); s = float(np.dot(np.array(e["d"], float), fd)); c = float((np.array(e["o"], float) - fo) @ fd)
    return dict(F=F, bild=np.asarray(bild, np.float32), quelle=quelle, einzeln=list(einzeln), relief=relief, u_f=lambda u: c + s * np.asarray(u, float), u_e=lambda uf: (np.asarray(uf, float) - c) / s, s=s)


def _projektionstiefe(W, u, za, zb):
    """Tiefe (m hinter der Fassadenebene) der Flaeche, auf die die Einzelorthos an Ebenen-u projiziert sind (Median ueber za..zb); 0 ohne Relief."""
    R = W.get("relief")
    if R is None or not len(u): return np.zeros(len(u))
    r = W["F"]["raster"]; zl = r["zelle"]; j = np.clip(((W["u_f"](u) - r["u0"]) / zl - 0.5).astype(int), 0, R.shape[1] - 1); i0, i1 = sorted((int((r["z1"] - zb) / zl), int((r["z1"] - za) / zl)))
    return -np.median(R[max(i0, 0):max(i1, i0 + 1), :][:, j], axis=0)


def _gradient(A, zl):
    """Gradient (gu, gz) des Graubilds (Zeile 0 = oben) nach Glaettung BILD_GLATT_M; ungueltig (nan), wo die Glaettung leere Zellen (0) beruehrt."""
    import cv2
    sg = max(1.0, BILD_GLATT_M / zl); A = A.astype(np.float32); leer = A <= 0; B = cv2.GaussianBlur(A, (0, 0), sg)
    gu = cv2.Sobel(B, cv2.CV_32F, 1, 0, ksize=3) / 8.0; gz = -cv2.Sobel(B, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    schlecht = ndi.binary_dilation(leer, iterations=int(np.ceil(3 * sg)) + 1) if leer.any() else leer
    gu[schlecht] = np.nan; gz[schlecht] = np.nan; return gu, gz


def _ausschnitt(W, A, ua, ub, za, zb):
    """Pixelausschnitt (Ebenen-u ua..ub, z za..zb) aus Bild A der Fassade; Rueckgabe (Teilbild, j0, i0) oder None. Spalte j <-> u_f = u0 + (j + 0.5) zelle, Zeile i <-> z = z1 - (i + 0.5) zelle."""
    r = W["F"]["raster"]; zl = r["zelle"]; f = sorted([float(W["u_f"](ua)), float(W["u_f"](ub))])
    j0, j1 = max(int(np.floor((f[0] - r["u0"]) / zl)), 0), min(int(np.ceil((f[1] - r["u0"]) / zl)), A.shape[1]); i0, i1 = max(int(np.floor((r["z1"] - zb) / zl)), 0), min(int(np.ceil((r["z1"] - za) / zl)), A.shape[0])
    if j1 - j0 < 5 or i1 - i0 < 5: return None
    return A[i0:i1, j0:j1], j0, i0


def _profil_spitzen(W, A, ua, ub, za, zb):
    """Senkrechte Bildkanten zwischen ua und ub: je Spalte MEDIAN des waagerechten Gradienten ueber die Zeilen za..zb (durchgehende Kanten bleiben, Fugen und Steinkoernung
    mitteln sich weg). Spitzen ueber SIGMA_FAKTOR x Rauschen (1,4826 x MAD des Profils). Rueckgabe (u_ebene, vorzeichen, staerke) oder None (Stelle nicht gesehen)."""
    from scipy.signal import find_peaks
    r = W["F"]["raster"]; zl = r["zelle"]; pad = 0.1; a = _ausschnitt(W, A, ua - pad, ub + pad, za, zb)
    if a is None: return None
    T, j0, _ = a; gu, _ = _gradient(T, zl); gu = gu * np.sign(W["s"])                                   # Gradient in Ebenen-u-Richtung
    ok = np.isfinite(gu); spalte = ok.mean(0) >= 0.5
    if spalte.mean() < 0.7: return None                                                                  # Stelle in diesem Bild weitgehend leer
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings(): warnings.simplefilter("ignore"); P = np.nanmedian(gu, 0)
    P[~spalte] = 0.0; P = np.nan_to_num(P); rausch = 1.4826 * float(np.median(np.abs(P - np.median(P)))) + 1e-3
    pk, _ = find_peaks(np.abs(P), height=SIGMA_FAKTOR * rausch, distance=max(1, int(DRUCK_MIN_M / zl)))
    ue = W["u_e"](r["u0"] + (j0 + pk + 0.5) * zl); ein = (ue >= ua) & (ue <= ub)
    return ue[ein], np.sign(P[pk][ein]), np.abs(P[pk][ein]) / rausch


def laibungskanten(W, ua, ub, za, zb):
    """Durchgehende senkrechte Kanten im Fenster ua..ub mit LAGE und TIEFE: in jedem Einzelfoto-Ortho erscheint eine Kante in Tiefe L hinter der Wand bei u0 + L * ru
    (ru = (C - P).d / (C - P).n, Parallaxe). Hough ueber (u0, L): Stimmen = Fotos mit gleichsinniger Spitze <= EINZEL_TOL_M daneben; Kante ab FOTOS_MIN Fotos und FOTOS_MIN_ANTEIL
    der Fotos, die die Stelle sehen; dann Ausgleich u0 + L * ru ueber die Treffer. Ohne Einzelfotos: Spitzen des Wandbilds selbst (Tiefe unbekannt).
    Rueckgabe Liste dict(u, tiefe, fotos, rest, vorzeichen, staerke) nach u sortiert, und Zahl der Fotos, die die Stelle sehen."""
    F = W["F"]; o3 = np.array([*F["o"], 0.0]); d3 = np.array([*F["d"], 0.0]); n3 = np.array([*F["n"], 0.0]); um = 0.5 * (ua + ub)
    P = o3 + float(W["u_f"](um)) * d3 + np.array([0, 0, 0.5 * (za + zb)]); bel = []
    for nr, g, C in W["einzeln"]:
        v = C - P; vn = float(v @ n3)
        if vn <= 0.5: continue                                                                           # Kamera hinter / in der Wand
        sp = _profil_spitzen(W, g, ua, ub, za, zb)
        if sp is None: continue
        ru = float(v @ d3) / vn * W["s"]; u_, s_, h_ = sp
        bel.append((ru, u_ + _projektionstiefe(W, u_, za, zb) * ru, s_, h_))                            # Orthos sind auf das Relief projiziert: u_k = u + (L - Lp) ru -> u_k + Lp ru = u + L ru
    aus = []
    if len(bel) >= FOTOS_MIN:
        Ls = np.arange(L_BEREICH[0], L_BEREICH[1] + 1e-9, 0.01); U0 = np.arange(ua, ub + 1e-9, 0.005); frei = [np.ones(len(b[1]), bool) for b in bel]; n_min = max(FOTOS_MIN, int(np.ceil(FOTOS_MIN_ANTEIL * len(bel))))
        for _ in range(12):
            best = None
            for vz in (-1.0, 1.0):
                S = np.zeros((len(Ls), len(U0)))
                for (ru, u_, s_, h_), fr in zip(bel, frei):
                    q = np.sort(u_[fr & (s_ == vz)])
                    if not len(q): continue
                    x = U0[None, :] + Ls[:, None] * ru; k = np.clip(np.searchsorted(q, x), 1, len(q)) ; dd = np.minimum(np.abs(x - q[k - 1]), np.abs(x - q[np.minimum(k, len(q) - 1)])); S += dd <= EINZEL_TOL_M
                i, j = np.unravel_index(np.argmax(S - 1e-3 * np.abs(Ls)[:, None]), S.shape)               # bei Gleichstand die flachere Tiefe (Wand vor Durchblick)
                if best is None or S[i, j] > best[0]: best = (S[i, j], vz, Ls[i], U0[j])
            if best is None or best[0] < n_min: break
            _, vz, L, u0 = best; tr = []
            for b, (ru, u_, s_, h_) in enumerate(bel):
                c_ = np.where(frei[b] & (s_ == vz))[0]
                if not len(c_): continue
                k = c_[np.argmin(np.abs(u_[c_] - (u0 + L * ru)))]
                if abs(u_[k] - (u0 + L * ru)) <= EINZEL_TOL_M: tr.append((ru, u_[k], h_[k])); frei[b][k] = False
            tr = np.array(tr); spanne = float(np.ptp(tr[:, 0]))
            if spanne >= RU_SPANNE_MIN: L, u0 = np.polyfit(tr[:, 0], tr[:, 1], 1); rest = float(np.sqrt(np.mean((tr[:, 1] - u0 - L * tr[:, 0]) ** 2)))
            else: L = None; u0 = float(np.median(tr[:, 1])); rest = float(np.sqrt(np.mean((tr[:, 1] - u0) ** 2)))
            aus.append(dict(u=float(u0), tiefe=None if L is None else float(L), tiefe_tol=None if L is None else max(DRUCK_MIN_M, EINZEL_TOL_M / spanne), fotos=len(tr), rest=rest,
                            vorzeichen=int(vz), staerke=float(np.median(tr[:, 2])), quelle="einzelfotos"))
    if not aus:                                                                                          # Fallback: Spitzen des Wandbilds selbst
        sp = _profil_spitzen(W, W["bild"], ua, ub, za, zb)
        if sp is not None: aus = [dict(u=float(u_), tiefe=None, tiefe_tol=None, fotos=0, rest=None, vorzeichen=int(s_), staerke=float(h_), quelle="wandbild") for u_, s_, h_ in zip(*sp)]
    return sorted(aus, key=lambda k: k["u"]), len(bel)


def gewaende_kandidaten(kanten, u_c, innen, aus_m, ein_m):
    """Startwerte fuer Aussen- und Innenkante einer Laibung aus den durchgehenden senkrechten Kanten. innen = +1 (linke Laibung) / -1 (rechte); x = Abstand vom Wolkenrand nach innen.
    Aussenkante = Kante naechst dem Wolkenrand (der Wolkenfleck beginnt dort, wo die Wand zurueckspringt); Innenkanten-Kandidaten = bis zu 3 naechste Kanten weiter innen
    (welche die lichte Kante ist, entscheidet der Doppelumriss am ganzen Bogen, nicht diese Laibung allein). Rueckgabe (aussen, [innen ...])."""
    K = [dict(k, x=innen * (k["u"] - u_c)) for k in kanten if -aus_m <= innen * (k["u"] - u_c) <= ein_m]
    if not K: return None, []
    a = min(K, key=lambda k: abs(k["x"])); weiter = sorted([k for k in K if k["x"] > a["x"] + DRUCK_MIN_M], key=lambda k: k["x"])
    return a, weiter[:3]


def _normalen(M, teil):
    """Aeussere Einheitsnormalen des Umrisses (links -u, rechts +u, Abschluss senkrecht zur Kurve, nach oben/aussen)."""
    N = np.zeros_like(M); N[teil == 0] = (-1, 0); N[teil == 1] = (1, 0); t = teil == 2
    if t.sum() >= 2:
        T = np.gradient(M[t], axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12; Nn = np.c_[-T[:, 1], T[:, 0]]; Nn[Nn[:, 1] < 0] *= -1; N[t] = Nn
    return N


def _doppelumriss(p, form, zs, schritt=0.02, g=None):
    """Umriss (uL, uR, Kaempfer zk, Stich h; p = [uL, uR, zk, (h)]) und - mit g - dazu der um g nach aussen versetzte Umriss (Fase/Gewaende gleicher Breite rundum; g < 0 = nach innen).
    Rueckgabe (Punkte, Normalen, Teil 0-2 Umriss / 3-5 Versatz) oder None (ungueltig)."""
    uL, uR, zk = p[:3]; b = uR - uL
    if b <= 0.1 or zk < zs: return None
    h = 0.0 if form == "sturz" else b / 2 if form == "rundbogen" else p[3]
    if form == "segmentbogen" and not (0.02 * b <= h <= b / 2): return None
    if form == "spitzbogen" and not (b / 2 <= h <= 3 * b): return None
    M, teil = umriss(uL, uR, zk, h, zs, schritt=schritt); N = _normalen(M, teil)
    if g is None: return M, N, teil
    return np.vstack([M, M + g * N]), np.vstack([N, N]), np.r_[teil, teil + 3]


def _abst_doppel(p, form, T, G, zs, kappe, g=None):
    """Abstand je UMRISSPUNKT (mit g: auch des versetzten Umrisses) zum naechsten Bildkantenpunkt mit passender Richtung (|Gradient . Normale| >= RICHTUNG_COS), gekappt bei 'kappe'.
    Vom Modell aus gemessen (Chamfer): Bildstoerungen abseits des Umrisses (Fugen, Durchblick) kosten nichts, fehlende Kantenstuecke kosten die Kappung.
    Rueckgabe (Abstaende, Umrisspunkte, Teil) oder None."""
    D = _doppelumriss(p, form, zs, g=g)
    if D is None: return None
    A, NA, ti = D; dd, ii = T.query(A, k=8, distance_upper_bound=kappe); Gp = np.vstack([G, np.zeros((1, 2))]); ii = np.minimum(ii, len(G))
    pas = np.abs(np.einsum("nkj,nj->nk", Gp[ii], NA)) >= RICHTUNG_COS; dd = np.where(pas & np.isfinite(dd), dd, kappe); return dd.min(1), A, ti


def fit_bild(form, T, G, start, zs, deltas, zk_min):
    """Ausgleich des Umrisses an die Bildkanten, grob -> fein (Huber-delta der Reihe nach, Kappung 4 delta). Rest fuer die Formwahl nur im Abschlussbereich (z >= zk_min)."""
    def kost_fn(dl):
        def kost(p_):
            r = _abst_doppel(p_, form, T, G, zs, 4 * dl)
            if r is None: return 1e3
            d = r[0]; return float(np.mean(np.where(d < dl, 0.5 * d * d, dl * (d - 0.5 * dl))))
        return kost
    k0 = kost_fn(deltas[0]); start = sorted(start, key=lambda p0: k0(np.array(p0, float)))[:2]; best = None      # nur die 2 besten Startwerte ausgleichen (Rechenzeit)
    for p0 in start:
        p = np.array(p0, float)
        for dl in deltas:
            r = minimize(kost_fn(dl), p, method="Nelder-Mead", options=dict(xatol=1e-3, fatol=1e-9, maxiter=500)); p = r.x
        if best is None or r.fun < best[1]: best = (p, r.fun)
    p = best[0]; dl = deltas[-1]; r = _abst_doppel(p, form, T, G, zs, 4 * dl)
    if r is None: return None
    d, A, ti = r; uL, uR, zk = p[:3]; b = uR - uL; h = 0.0 if form == "sturz" else b / 2 if form == "rundbogen" else float(p[3]); ob = A[:, 1] >= zk_min
    return dict(form=form, uL=float(uL), uR=float(uR), zk=float(zk), h=float(h), rest=float(np.sqrt(np.mean(d[ob] ** 2))) if ob.any() else float(np.sqrt(np.mean(d ** 2))),
                rest_gesamt=float(np.sqrt(np.mean(d ** 2))), belegt=float((d < dl).mean()), punkte=int(len(A)), _p=p)


def bildkanten_punkte(W, ua, ub, za, zb):
    """Kantenpunkte (Canny) mit Gradientrichtung im Ausschnitt. Schwelle: hoch = SIGMA_FAKTOR x Median des Gradientenbetrags (typische Steinkoernung), niedrig = halb (Canny-Hysterese)."""
    import cv2
    r = W["F"]["raster"]; zl = r["zelle"]; QQ, GG = [], []
    for bild in W.get("bilder") or [W["bild"]]:                                                         # feines Wandbild (je Stelle ein Foto) UND Mittelbild (alle Fotos): eine Innenkante, die im
        a = _ausschnitt(W, bild, ua, ub, za, zb)                                                         # gewaehlten Foto verdeckt ist (schraeger Blick), zeigt das Mittelbild - Stoerkanten kosten nichts
        if a is None: continue
        T, j0, i0 = a; gu, gz = _gradient(T, zl); M = np.hypot(gu, gz); ok = np.isfinite(M)
        if ok.mean() < 0.5: continue
        hoch = SIGMA_FAKTOR * float(np.median(M[ok])); B = cv2.GaussianBlur(T, (0, 0), max(1.0, BILD_GLATT_M / zl))
        E = cv2.Canny(np.clip(B, 0, 255).astype(np.uint8), 0.5 * hoch * 8, hoch * 8, L2gradient=True) > 0                 # Canny rechnet mit Sobel ohne /8
        E &= ok; ys, xs = np.where(E); g = np.c_[gu[ys, xs] * np.sign(W["s"]), gz[ys, xs]]; g /= np.linalg.norm(g, axis=1, keepdims=True) + 1e-12
        QQ.append(np.c_[W["u_e"](r["u0"] + (j0 + xs + 0.5) * zl), r["z1"] - (i0 + ys + 0.5) * zl]); GG.append(g)
    return (np.vstack(QQ), np.vstack(GG)) if QQ else None


def _form_p(s_, form):
    return [s_["uL"], s_["uR"], s_["zk"]] + ([s_["h"]] if form in ("segmentbogen", "spitzbogen") else [])


def versetzt(s_, form, g_):
    """Umriss s_ um g_ nach aussen (g_ < 0 nach innen) versetzt; Bogenmittelpunkte bleiben (Radius + g_), Sturz steigt um g_."""
    b_ = s_["uR"] - s_["uL"]; h_ = s_["h"]; b2 = b_ + 2 * g_
    if form == "sturz": h2 = 0.0; zk2 = s_["zk"] + g_
    elif form == "spitzbogen": ex = (h_ * h_ - b_ * b_ / 4) / b_; h2 = float(np.sqrt(max((b_ / 2 + ex + g_) ** 2 - ex ** 2, 0))); zk2 = s_["zk"]
    else: r_ = (b_ * b_ / 4 + h_ * h_) / (2 * h_); zc = s_["zk"] + h_ - r_; zk2 = zc + float(np.sqrt(max((r_ + g_) ** 2 - (b2 / 2) ** 2, 0))); h2 = zc + r_ + g_ - zk2
    return dict(s_, uL=s_["uL"] - g_, uR=s_["uR"] + g_, zk=zk2, h=h2)


def versatz_suche(s, form, T, G, zs, g_lo, g_hi):
    """Zweite, parallele Kante zum Umriss s: Versatz g von g_lo bis g_hi (1 cm Schritt; |g| < 2 x EINZEL_TOL_M ist dieselbe Kante). Beleg je g = Anteil der versetzten
    Umrisspunkte mit gleichgerichteter Bildkante <= EINZEL_TOL_M. Kandidaten = echte oertliche Spitzen der Belegkurve (die Schulter neben der eigenen Kante ist keine).
    Rueckgabe (Spitzen [(g, beleg)] absteigend, Kurve)."""
    kurve = []
    for g in np.arange(round(g_lo, 2), g_hi + 1e-9, 0.01):
        if abs(g) < 2 * EINZEL_TOL_M: continue
        r = _abst_doppel(_form_p(s, form), form, T, G, zs, 4 * EINZEL_TOL_M, g=float(g))
        if r is None: continue
        d, A, ti = r; v = ti >= 3
        if v.any(): kurve.append((round(float(g), 2), round(float((d[v] <= EINZEL_TOL_M).mean()), 3)))
    sp = [kurve[i] for i in range(1, len(kurve) - 1) if kurve[i][1] > kurve[i - 1][1] and kurve[i][1] >= kurve[i + 1][1] and kurve[i + 1][0] - kurve[i - 1][0] < 0.025]
    return sorted(sp, key=lambda x: -x[1]), kurve


def zweite_kante(s, form, g, Q, G, T, zs):
    """Zweite Kante beim Versatz g eigenstaendig vermessen: Kantenzug am versetzten Umriss (gleichgerichtet, <= 2 x EINZEL_TOL_M), Punktausgleich derselben Form (fit_form).
    Rueckgabe (Umriss-dict, Beleg gesamt, Beleg Abschluss) - Beleg = Anteil des Umrisses mit Bildkante <= EINZEL_TOL_M - oder None."""
    so = versetzt(s, form, g); D = _doppelumriss(_form_p(so, form), form, zs, schritt=0.01)
    if D is None: return None
    dq, iq = cKDTree(D[0]).query(Q); zug = (dq <= 2 * EINZEL_TOL_M) & (np.abs(np.einsum("nj,nj->n", D[1][iq], G)) >= RICHTUNG_COS) & (Q[:, 1] > zs + 2 * EINZEL_TOL_M)
    if zug.sum() < KANTEN_MIN_PUNKTE: return None
    F = fit_form(form, Q[zug], [_form_p(so, form)], zs, EINZEL_TOL_M)
    if F is None: return None
    db = 0.5 * ((F["uR"] - F["uL"]) - (s["uR"] - s["uL"]))
    if np.sign(db) != np.sign(g) or abs(db) < 2 * EINZEL_TOL_M: return None                              # muss auf seiner Seite bleiben und eine andere Kante sein
    r = _abst_doppel(_form_p(F, form), form, T, G, zs, 4 * EINZEL_TOL_M)
    if r is None: return None
    d, A, ti = r; return F, float((d <= EINZEL_TOL_M).mean()), float((d[ti == 2] <= EINZEL_TOL_M).mean()) if (ti == 2).any() else 0.0


def wandbild_vermessen(o, W, zelle_wolke, schwelle):
    """Wandbild-Stufe fuer eine Oeffnung o (Ergebnis von vermessen, aus Wolke/Kanten):
     1. Laibungskanten links/rechts (durchgehende senkrechte Bildkanten; Lage und Tiefe ueber die Einzelfotos) -> Startwerte und Beleg.
     2. Umriss je Form (sturz/rund/segment/spitz) an die Bildkanten des feinen Wandbilds und des Mittelbilds ausgleichen (Chamfer-Abstand vom Umriss aus, nur gleichgerichtete
        Kanten); Formwahl wie form_waehlen (einfachere Form bleibt, wenn die reichere den Rest nicht klar senkt), Rest im Abschlussbereich.
     3. Gewaende/Fase: parallele zweite Kante zum gefundenen Umriss (versatz_suche, nach innen oder aussen). Innenkante = die innere der beiden = lichte Oeffnung,
        Aussenkante = die aeussere (in der Wandebene). Ohne zweite Kante: eine Kante, Gewaende unbestimmt.
    Schreibt o['wandbild'] und - wenn die Bildkanten den Abschluss belegen - Form, lichte Weite, Aussenmass, Gewaende in o; der Wolkenumriss bleibt unter o['wolkenrand']."""
    f = o["_fit"]; zs = o["_zs"]; b = f["uR"] - f["uL"]; zt = f["zk"] + f["h"]; H = f["zk"] - zs; info = dict(bild=W["quelle"], einzelfotos=len(W["einzeln"])); o["wandbild"] = info
    r3 = lambda x: None if x is None else round(float(x), 3)
    if b < 2 * MIN_BREITE or H <= 0: info["hinweis"] = "Oeffnung zu klein fuer die Laibungssuche"; return o
    aus_m = FANG_ZELLEN * zelle_wolke + schwelle; ein_m = GEWAENDE_MAX_ANTEIL * b                       # aussen: Lagefehler Wolkenrand + Ruecksprung bis zur Schwelle; innen: hoechstens Gewaendebreite
    za, zb = zs + 0.25 * H, f["zk"] - 0.05 * H                                                        # ANNAHME: unteres Viertel der Laibung oft verdeckt (Menschen, Fahrzeuge, Schilder); Kaempferzone ausgenommen
    kk = lambda k: dict(u=r3(k["u"]), tiefe=r3(k["tiefe"]), tiefe_tol=r3(k.get("tiefe_tol")), fotos=k["fotos"], rest=r3(k["rest"]), quelle=k["quelle"])
    st = {}
    for name, u_c, innen in (("links", f["uL"], 1), ("rechts", f["uR"], -1)):
        ua, ub = sorted((u_c - innen * aus_m, u_c + innen * ein_m)); K, n_sehen = laibungskanten(W, ua, ub, za, zb); a, ii = gewaende_kandidaten(K, u_c, innen, aus_m, ein_m)
        st[name] = (a, ii); info[f"laibung_{name}"] = dict(fotos_sehen=n_sehen, kanten=[kk(k) for k in K], aussen_start=None if a is None else r3(a["u"]), innen_kandidaten=[r3(k["u"]) for k in ii])
    uLa = st["links"][0]["u"] if st["links"][0] else f["uL"]; uRa = st["rechts"][0]["u"] if st["rechts"][0] else f["uR"]
    rand = aus_m + ein_m; pk = bildkanten_punkte(W, min(uLa, f["uL"]) - rand, max(uRa, f["uR"]) + rand, za, zt + 0.25 * b + rand)
    if pk is None: info["hinweis"] = "Wandbild an der Oeffnung leer"; return o
    Q, G = pk; inn = (Q[:, 0] > f["uL"] + ein_m + aus_m) & (Q[:, 0] < f["uR"] - ein_m - aus_m) & (Q[:, 1] < f["zk"])      # Durchblick tief innen (hintere Portale) gehoert nicht zum Umriss
    Q, G = Q[~inn], G[~inn]
    if len(Q) < KANTEN_MIN_PUNKTE: info["hinweis"] = f"nur {len(Q)} Bildkantenpunkte am Umriss"; return o
    T = cKDTree(Q); zk0 = f["zk"]; dls = (max(zelle_wolke, 0.05), EINZEL_TOL_M); S = {}                         # grob: Lagefehler des Wolkenrands; fein: Lagefehler der Orthos
    paare = {(round(f["uL"], 2), round(f["uR"], 2)), (round(uLa, 2), round(uRa, 2))}                            # Startbreiten: Wolkenrand und aeussere Laibungskanten
    for form, qs in (("sturz", [None]), ("rundbogen", [None]), ("segmentbogen", (0.15, 0.35)), ("spitzbogen", (0.6, 0.85))):
        start = []
        for uL_, uR_ in paare:
            bi = uR_ - uL_
            for q in qs:
                if form == "sturz": start.append([uL_, uR_, zt])
                elif form == "rundbogen": start += [[uL_, uR_, zt - bi / 2], [uL_, uR_, zk0]]
                else: start += [[uL_, uR_, zt - q * bi, q * bi], [uL_, uR_, zk0, q * bi]]
        S[form] = fit_bild(form, T, G, start, zs, dls, zk0)
    S = {k: v for k, v in S.items() if v}
    for k, v in S.items():                                                                                   # Formrest nur am ABSCHLUSS selbst: anders als am Wolkenrand sind die Laibungen im Bild
        d, A, ti_ = _abst_doppel(v["_p"], k, T, G, zs, 4 * dls[-1]); ob = ti_ == 2                            # starke gerade Kanten, die jede Form mit hohem Kaempfer billig mitnimmt
        if ob.sum() >= 10: v["rest"] = float(np.sqrt(np.mean(d[ob] ** 2))); v["belegt"] = float((d[ob] <= dls[-1]).mean())
    info["chamfer"] = {k: dict(rest=round(v["rest"], 4), belegt=round(v["belegt"], 2), stich=round(v["h"], 3), breite=round(v["uR"] - v["uL"], 3), uL=round(v["uL"], 3), kaempfer=round(v["zk"], 3)) for k, v in S.items()}
    if not S: info["hinweis"] = "kein Umrissausgleich"; return o
    # KANTENZUG: Bildkantenpunkte (gleichgerichtet, <= 2 x EINZEL_TOL_M) am am besten belegten Umriss - Stoerkanten (Fugen, Durchblick) fallen weg. Die FORM entscheidet dann der
    # Punktausgleich an diesem Kantenzug (formen_ausgleich/form_waehlen wie am Wolkenrand): im Chamfer-Rest kosten Luecken bei allen Formen gleich viel und verwischen den Unterschied.
    sb = max(S.values(), key=lambda v: v["belegt"]); Db = _doppelumriss(sb["_p"], sb["form"], zs, schritt=0.01); dq, iq = cKDTree(Db[0]).query(Q)
    zug = (dq <= 2 * EINZEL_TOL_M) & (np.abs(np.einsum("nj,nj->n", Db[1][iq], G)) >= RICHTUNG_COS) & (Q[:, 1] > zs + 2 * EINZEL_TOL_M); Qz = Q[zug]; info["kantenzug_punkte"] = int(zug.sum())
    if len(Qz) < KANTEN_MIN_PUNKTE: info["hinweis"] = f"Kantenzug nur {len(Qz)} Punkte"; return o
    Qz = Qz[::max(1, len(Qz) // 600)]                                                                     # Ausgleich braucht keine Tausende Punkte: <= ~600 gleichmaessig (Lage auf 1 cm unveraendert)
    Fz = formen_ausgleich(Qz, sb["uL"], sb["uR"], sb["zk"] + sb["h"], zs, EINZEL_TOL_M); form, grund = form_waehlen(Fz, W["F"]["raster"]["zelle"]) if Fz else ("unbestimmt", "kein Ausgleich")
    info["reste"] = {k: dict(rest=round(v["rest"], 4), stich=round(v["h"], 3), breite=round(v["uR"] - v["uL"], 3), kaempfer=round(v["zk"], 3), punkte=v["punkte"]) for k, v in Fz.items()}
    info["form"] = form; info["form_grund"] = grund
    if form == "unbestimmt": return o
    s = dict(Fz[form]); s["_p"] = [s["uL"], s["uR"], s["zk"]] + ([s["h"]] if form in ("segmentbogen", "spitzbogen") else []); d, A, ti = _abst_doppel(s["_p"], form, T, G, zs, 4 * EINZEL_TOL_M); tr = d <= EINZEL_TOL_M
    bel_ab = float(tr[ti == 2].mean()) if (ti == 2).any() else 0.0
    if bel_ab < KANTEN_MIN_BELEGT:
        info["hinweis"] = f"Bildkanten belegen den Abschluss nur zu {bel_ab:.0%} (noetig {KANTEN_MIN_BELEGT:.0%}) - Form aus dem Wolkenrand bleibt"; return o
    # ---- zweite parallele Kante (Gewaende/Fase)
    bel_ges = float(tr[ti < 3].mean())
    # Suchbereich: nach innen bis zur groessten Gewaendebreite; nach aussen nur bis zum Wolkenrand + 3 Zellen Lagefehler - weiter aussen meldet die Wolke Wand IN der Ebene
    # (Bogensteine, Fugen, Rahmenbaender), dort liegt kein Gewaende der Oeffnung
    b_wolke = f["uR"] - f["uL"]
    if "_maske" in o:                                                                                       # Breite des Wolkenflecks selbst (Laibungsband), nicht des Umrissausgleichs (der kann aus Kantenpunkten stammen)
        m_, (ru_, rz_, rc_) = o["_maske"], o["_ras"]; zz_ = rz_ + (np.arange(m_.shape[0]) + 0.5) * rc_; zeil = [i for i in np.where((zz_ >= za) & (zz_ <= zb))[0] if m_[i].any()]
        if zeil: b_wolke = float(np.median([(np.where(m_[i])[0].max() + 1 - np.where(m_[i])[0].min()) * rc_ for i in zeil]))
    d_wolke = 0.5 * (b_wolke - (s["uR"] - s["uL"])); g_hi = max(0.0, d_wolke) + FANG_ZELLEN * zelle_wolke; info["breite_wolkenfleck"] = r3(b_wolke)
    spitzen, kurve = versatz_suche(s, form, T, G, zs, -ein_m, g_hi); g = 0.0; zweit = None; info["versatz"] = dict(bereich=[r3(-ein_m), r3(g_hi)], spitzen=spitzen[:4], kurve=kurve)
    # Annahme einer zweiten Kante: (a) ihr eigener Beleg ist mindestens doppelt so hoch wie der Untergrund (Median der Belegkurve = zufaellige Treffer auf Fugen/Textur bei
    # beliebigem Versatz) und (b) an mindestens einer Laibung liegt eine durchgehende Laibungskante der Einzelfotos (<= 3 x EINZEL_TOL_M; >= FOTOS_MIN Fotos) auf der
    # Innenkante, und sie ist per Parallaxe TIEFER als die Kante an der Aussenkante (Ruecksprung) - eine Fuge oder ein Rahmenband in der Wandebene ist kein Gewaende.
    # Die Innenkante einer tiefen Fase liegt in jedem Foto anders (Parallaxe) - ein fester Anteil am Beleg der Aussenkante waere deshalb zu streng (Schwabentor: 0,30 gegen 0,65).
    untergrund = float(np.median([k_[1] for k_ in kurve])) if kurve else 1.0; info["versatz"]["untergrund"] = round(untergrund, 3)
    lk = {n_: [k_ for k_ in info[f"laibung_{n_}"]["kanten"] if k_["quelle"] == "einzelfotos" and k_["tiefe"] is not None] for n_ in ("links", "rechts")}   # Kanten aus >= FOTOS_MIN Einzelfotos mit Tiefe (Durchblick > L_BEREICH faellt weg)
    def an(n_, u_):
        k_ = min(lk[n_], key=lambda k: abs(k["u"] - u_)) if lk[n_] else None; return k_ if k_ and abs(k_["u"] - u_) <= 3 * EINZEL_TOL_M else None
    def ruecksprung(n_, u_in, u_aus):                                                                       # Gewaende = Ruecksprung: Innenkante liegt TIEFER als die Aussenkante (sonst Fuge/Rahmen in der Ebene)
        ki, ka = an(n_, u_in), an(n_, u_aus)
        return bool(ki) and ki["tiefe"] > (ka["tiefe"] if ka else 0.0) + max(ki["tiefe_tol"] or 0.0, DRUCK_MIN_M)
    for g_, b_ in spitzen[:3]:
        zk_ = zweite_kante(s, form, g_, Q, G, T, zs)
        if zk_ is None: continue
        i_, a_ = (zk_[0], s) if g_ < 0 else (s, zk_[0])
        bestaetigt = [n_ for n_, ui_, ua_ in (("links", i_["uL"], a_["uL"]), ("rechts", i_["uR"], a_["uR"])) if ruecksprung(n_, ui_, ua_)]
        info["versatz"].setdefault("geprueft", []).append(dict(g=g_, beleg_versatz=b_, beleg_eigen=round(zk_[1], 2), beleg_abschluss=round(zk_[2], 2), laibungskante=bestaetigt))
        if zk_[1] >= 2 * untergrund and bestaetigt:
            zweit = zk_; g = 0.5 * ((zk_[0]["uR"] - zk_[0]["uL"]) - (s["uR"] - s["uL"])); break
    if zweit is None:
        si = sa = s; info["hinweis_gewaende"] = "ANNAHME: nur eine Kante belegt - Innen- und Aussenmass gleich, Gewaende unbestimmt" + ("" if W["einzeln"] else " (keine Einzelfotos: zweite Kante nicht bestaetigbar)")
    else: si, sa = (zweit[0], s) if g < 0 else (s, zweit[0])                                               # Innenkante = die innere der beiden
    gw = abs(g)
    info["innen"] = dict(uL=r3(si["uL"]), uR=r3(si["uR"]), breite=r3(si["uR"] - si["uL"]), kaempfer=r3(si["zk"]) if form != "sturz" else None, scheitel=r3(si["zk"] + si["h"]))
    info["aussen"] = dict(uL=r3(sa["uL"]), uR=r3(sa["uR"]), breite=r3(sa["uR"] - sa["uL"]), kaempfer=r3(sa["zk"]) if form != "sturz" else None, scheitel=r3(sa["zk"] + sa["h"]))
    rest_lb = r3(np.sqrt(np.mean(d[ti < 2] ** 2))) if (ti < 2).any() else None; rest_ab = r3(np.sqrt(np.mean(d[ti == 2] ** 2))) if (ti == 2).any() else None
    aus_ist_fit = g >= 0; quelle_fit = "Umrissausgleich an Bildkanten (Kantenzug)"; quelle_vs = "zweite parallele Kante, eigener Ausgleich (Abstand %+.2f m)" % g
    # Laibungskanten (Einzelfotos), die den Umriss tragen (<= 2 x EINZEL_TOL_M neben Innen-/Aussenkante): Beleg mit Parallaxen-Tiefe, keine Eingabe
    for name, ui, ua_ in (("links", si["uL"], sa["uL"]), ("rechts", si["uR"], sa["uR"])):
        L_ = info[f"laibung_{name}"]["kanten"]; naechst = lambda u_: min(L_, key=lambda k: abs(k["u"] - u_)) if L_ else None; ki, ka = naechst(ui), naechst(ua_)
        info[f"laibung_{name}"]["innen"] = ki if ki and abs(ki["u"] - ui) <= 2 * EINZEL_TOL_M else None; info[f"laibung_{name}"]["aussen"] = ka if ka and abs(ka["u"] - ua_) <= 2 * EINZEL_TOL_M else None
    # ---- uebernehmen: Form aus dem Bild, Hauptmasse = lichte Oeffnung (Innenkante); Wolkenumriss aufbewahren
    o["wolkenrand"] = dict(form=o["form"], form_quelle=o["form_quelle"], breite=o["breite"]["wert"], kaempfer=o["kaempfer"]["wert"], scheitel=o["scheitel"]["wert"], reste=o["reste"])
    tief = lambda k: None if not k else k["tiefe"]; vsb = info["versatz"] or {}
    o["form"], o["form_grund"], o["form_quelle"] = form, "Bildkanten: " + grund, "wandbild"                  # "sicher" bleibt wie aus der Wolke (Tiefe belegt?)
    q_i, q_a = (quelle_fit, quelle_vs) if aus_ist_fit else (quelle_vs, quelle_fit)
    rest_f = dict(punktrest=r3(s["rest"]), chamfer_laibungen=rest_lb, chamfer_abschluss=rest_ab, belegt=round(bel_ges, 2), belegt_abschluss=round(bel_ab, 2))
    rest_z = dict(punktrest=r3(zweit[0]["rest"]), belegt=round(zweit[1], 2), belegt_abschluss=round(zweit[2], 2)) if zweit else None
    rest_i, rest_a = (rest_f, rest_z) if aus_ist_fit else (rest_z, rest_f)
    if g == 0: q_a = q_i; rest_a = rest_i
    o["breite"] = dict(wert=info["innen"]["breite"], quelle=q_i, rest=rest_i, hinweis="lichte Weite (Innenkante)")
    o["kaempfer"] = dict(wert=info["innen"]["kaempfer"], quelle=q_i, rest=rest_i, hinweis=None if form != "sturz" else "gerader Sturz: kein Kaempfer")
    o["scheitel"] = dict(wert=info["innen"]["scheitel"], stich=r3(si["h"]), quelle=q_i, rest=rest_i)
    o["aussenmass"] = dict(breite=info["aussen"]["breite"], scheitel=info["aussen"]["scheitel"], kaempfer=info["aussen"]["kaempfer"], quelle=q_a, rest=rest_a, hinweis="Aussenkante in der Wandebene inkl. Fase/Gewaende")
    o["gewaende"] = dict(breite=r3(gw) if g != 0 else None, links=r3(si["uL"] - sa["uL"]) if g != 0 else None, rechts=r3(sa["uR"] - si["uR"]) if g != 0 else None,
                         scheitel=r3(sa["zk"] + sa["h"] - si["zk"] - si["h"]) if g != 0 else None, quelle="Abstand Aussen-/Innenkante" if g != 0 else "keine parallele zweite Kante belegt",
                         tiefe_innenkante_links=tief(info["laibung_links"]["innen"]), tiefe_innenkante_rechts=tief(info["laibung_rechts"]["innen"]),
                         hinweis="Tiefe = Parallaxe der Einzelfotos (m hinter der Fassadenebene), nur wenn eine Laibungskante den Umriss traegt")
    b_ = si["uR"] - si["uL"]; h_ = si["h"]
    o["radius"] = r3((h_ ** 2 + b_ ** 2 / 4) / (2 * h_)) if form in ("rundbogen", "segmentbogen") else r3(b_ / 2 + (h_ ** 2 - b_ ** 2 / 4) / b_) if form == "spitzbogen" else None
    o["zone"] = [r3(sa["uL"]), r3(sa["uR"]), r3(zs), r3(sa["zk"] + sa["h"])]; o["mitte_u"] = r3(0.5 * (si["uL"] + si["uR"]))
    o["_fit_bild"] = si; o["_fit_bild_aussen"] = sa; return o


def _raster_maske(o, m, u0, z0, zelle):
    o["_maske"] = m; o["_ras"] = (u0, z0, zelle); return o


def ebene_auswerten(e, P, wolke=None, wandbild=None):
    """Eine Wandebene. P = Kantenpunkte (N x 3), wolke = (u, z, w) der dichten Wolke in Ebenenkoordinaten oder None, wandbild = wandbild_laden(...) oder None. Rueckgabe dict(oeffnungen, ...)."""
    u, z, w = ebenen_koord(P, e); band = float(e.get("band", 0.5)); zone = list(e["zone"]); ok = np.abs(w) <= band; u, z, w = u[ok], z[ok], w[ok]; aus = []; info = dict(kantenpunkte=int(len(u)))
    if wolke is not None:
        uw, zw, ww = wolke; ink = (uw >= zone[0]) & (uw <= zone[1]) & (zw >= zone[2]) & (zw <= zone[3]); uw, zw, ww = uw[ink], zw[ink], ww[ink]
        if len(uw) < 1000: return dict(oeffnungen=[], hinweis="zu wenig Wolkenpunkte in der Zone", **info)
        zelle = zellgroesse(uw[np.abs(ww) < 0.5], zw[np.abs(ww) < 0.5], zone); T, n, verd = raster_wolke(uw, zw, ww, zone, zelle); T = glatt(T); W0, _ = wandtiefe(T, zelle); SK = schwellenkarte(T, W0, verd)
        for _ in range(2):                                 # Sigma-Clipping: Zellen 'hinten' (Nischen, Loecher) ziehen den Median der Wand nach hinten -> Wandtiefe und Rauheit nur aus den Wandzellen neu
            W0, _ = wandtiefe(np.where(np.abs(T - W0) <= SK, T, np.nan), zelle); SK = schwellenkarte(np.where(np.abs(T - W0) <= SK, T, np.nan), W0, verd)
        fl, boden = flecken_wolke(T, n, verd, zelle, W0, SK)
        info.update(zelle=zelle, schwelle_hinten=round(SK, 3), boden_z=round(zone[2] + boden * zelle, 2), wolkenpunkte=int(len(uw)), quelle="wolke+kanten")
        for f in fl:
            R_ = (f, zone[0], zone[2], zelle, T, n, verd, W0, SK); fein = fleck_fein(f, (uw, zw, ww), zone, zelle, W0, SK, n, zone[2] + boden * zelle)
            if fein: fein[0]["bodenlos"] = f["bodenlos"]; R_ = fein
            g, gu, gz, gc, gT, gn, gv, gW, gS = R_; o = vermessen(g, gu, gz, gc, (u, z, w), z_boden=zone[2] + boden * zelle)
            if o is None: continue
            o["zelle"] = gc; _raster_maske(o, g["maske"], gu, gz, gc)
            if wandbild is not None: wandbild_vermessen(o, wandbild, gc, SK)
            # zweite Stufe: noch tiefere Zone IM Fleck (Fenster in der Nische); Bezug = haeufige Tiefe des Flecks, Schwelle wie an der Wand
            if g.get("tiefe") is not None and g["tiefe_zellen"] >= 50 and g["anteil_hinten"] >= 0.8:      # nur wo der Fleck einen Grund hat (Nische); im Durchblick eines Tors gibt es keine Bezugsflaeche
                bez = np.full_like(gT, np.nanmedian(np.where(g["maske"], gT, np.nan))); f2, _ = flecken_wolke(gT, gn, gv, gc, bez, gS, innerhalb=g["maske"], rand_frei=False)
                inn = [_raster_maske(i_, h_["maske"], gu, gz, gc) for h_ in f2 if h_["maske"].sum() < 0.7 * g["maske"].sum() for i_ in [vermessen(h_, gu, gz, gc, (u, z, w))] if i_]
                if inn: o["innen"] = inn
            aus.append(o)
    else:
        zelle = 0.05; fl, zb = flecken_kanten(u, z, w, zone, zelle); info.update(zelle=zelle, boden_z=round(zb, 2), quelle="nur kanten"); n_ohne = 0       # 5 cm: Kantenpunkte liegen auf wenige cm (METHODE_EBENEN_BAUPLAN)
        for f in fl:
            if f.get("ohne_tiefe"): n_ohne += 1; continue
            o = vermessen(f, zone[0], zb, zelle, (u, z, w), nur_kanten=True, z_boden=zb)
            if o:
                o["zelle"] = zelle
                if wandbild is not None: wandbild_vermessen(o, wandbild, zelle, DRUCK_MIN_M)
                aus.append(_raster_maske(o, f["maske"], zone[0], zb, zelle))
        info["ohne_tiefe"] = n_ohne
    aus.sort(key=lambda o: (o["zone"][2], o["zone"][0]))
    for k, o in enumerate(aus): o["id"] = f"{e['id']}_o{k}"
    return dict(oeffnungen=aus, _kanten=(u, z, w), **info)


def kontrollbild(e, erg, pfad, px_m=60, wandbild=None):
    import cv2
    u0, u1, z0, z1 = e["zone"]; r = 0.5; u0 -= r; u1 += r; H, W = int((z1 - z0) * px_m) + 1, int((u1 - u0) * px_m) + 1; im = np.full((H, W, 3), 255, np.uint8)
    if wandbild is not None:                                                            # Wandbild aufgehellt als Hintergrund (Bildkanten sichtbar pruefen)
        ra = wandbild["F"]["raster"]; uu = wandbild["u_f"](u0 + (np.arange(W) + 0.5) / px_m); zz = z1 - (np.arange(H) + 0.5) / px_m
        mx = ((uu - ra["u0"]) / ra["zelle"] - 0.5).astype(np.float32); my = ((ra["z1"] - zz) / ra["zelle"] - 0.5).astype(np.float32)
        g = cv2.remap(wandbild["bild"], np.tile(mx, (H, 1)), np.tile(my[:, None], (1, W)), cv2.INTER_LINEAR, borderValue=0)
        im[:] = np.where(g[..., None] > 0, (110 + 0.55 * g[..., None]).clip(0, 255), 255).astype(np.uint8)
    X = lambda uu: np.round((np.asarray(uu) - u0) * px_m).astype(int); Y = lambda zz: np.round((z1 - np.asarray(zz)) * px_m).astype(int)
    fl = np.zeros((H, W), bool)
    for o in erg["oeffnungen"]:                                                        # Fleck hellblau (mit Wandbild durchscheinend, damit die Bildkanten sichtbar bleiben)
        ru, rz, zelle = o["_ras"]; ys, xs = np.where(o["_maske"]); x, y = X(ru + (xs + 0.5) * zelle), Y(rz + (ys + 0.5) * zelle); k = max(1, int(zelle * px_m / 2) + 1)
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1): fl[np.clip(y + dy, 0, H - 1), np.clip(x + dx, 0, W - 1)] = True
    im[fl] = (im[fl] * (0.65 if wandbild is not None else 0.0) + np.array([255, 235, 200]) * (0.35 if wandbild is not None else 1.0)).astype(np.uint8)
    ku, kz, kw = erg["_kanten"]; x, y = X(ku), Y(kz); ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
    if wandbild is None: im[y[ok], x[ok]] = np.where((kw[ok] < -DRUCK_MIN_M)[:, None], (200, 80, 0), (90, 90, 90))   # Kanten: grau = Wand, blau = hinter der Wand
    else: ok &= kw < -DRUCK_MIN_M; im[y[ok], x[ok]] = (200, 80, 0)                                                     # mit Wandbild nur die Kanten hinter der Wand (sonst verdecken sie das Bild)
    farbe = dict(sturz=(0, 140, 0), rundbogen=(0, 0, 220), segmentbogen=(0, 140, 220), spitzbogen=(200, 0, 200), unbestimmt=(0, 200, 255))
    def zeichne(o, dick):
        f = o["_fit"]; M, teil = umriss(f["uL"], f["uR"], f["zk"], f["h"], o["_zs"], schritt=0.02); c = farbe[o["form"]]
        for t in (0, 1, 2):
            p = M[teil == t]; cv2.polylines(im, [np.c_[X(p[:, 0]), Y(p[:, 1])].astype(np.int32)], False, c, dick, cv2.LINE_AA)
        if o["kaempfer"]["wert"] is not None: cv2.line(im, (int(X(f["uL"])), int(Y(f["zk"]))), (int(X(f["uR"])), int(Y(f["zk"]))), c, 1, cv2.LINE_AA)
        return c
    def zeichne_bild(o):
        c = farbe[o["form"]]
        for f, dk in ((o.get("_fit_bild_aussen"), 1), (o.get("_fit_bild"), 2)):
            if not f: continue
            M, teil = umriss(f["uL"], f["uR"], f["zk"], f["h"], o["_zs"], schritt=0.02)
            for t in (0, 1, 2): A_ = M[teil == t]; cv2.polylines(im, [np.c_[X(A_[:, 0]), Y(A_[:, 1])].astype(np.int32)], False, c, dk, cv2.LINE_AA)
    for o in erg["oeffnungen"]:
        if o.get("_fit_bild"):                                                          # Wolkenumriss grau duenn, Bildumriss (innen dick, aussen duenn) in Formfarbe
            fw = o["_fit"]; M, teil = umriss(fw["uL"], fw["uR"], fw["zk"], fw["h"], o["_zs"], schritt=0.02)
            for t in (0, 1, 2): p = M[teil == t]; cv2.polylines(im, [np.c_[X(p[:, 0]), Y(p[:, 1])].astype(np.int32)], False, (120, 120, 120), 1, cv2.LINE_AA)
            zeichne_bild(o); c = farbe[o["form"]]
        else: c = zeichne(o, 2)
        for i_ in o.get("innen", []): zeichne(i_, 1)
        t = [f"{o['id'].split('_')[-1]} {'' if o['sicher'] else 'UNSICHER '}{o['form']} ({o['form_quelle']}, Zelle {o['zelle']})", f"B {o['breite']['wert']:.2f}  Sohle {o['sohlbank']['wert']:.2f}",
             (f"Kaempfer {o['kaempfer']['wert']:.2f}  " if o["kaempfer"]["wert"] is not None else "") + f"Scheitel {o['scheitel']['wert']:.2f}",
             "Tiefe " + (f"{o['laibung_tiefe']['wolke']:.2f}" if o["laibung_tiefe"]["wolke"] is not None else "?") + f"  Kantenp. {o['kantenpunkte_am_umriss']}"]
        if o.get("aussenmass"): t.append(f"aussen {o['aussenmass']['breite']:.2f} Scheitel {o['aussenmass']['scheitel']:.2f} Gew. {o['gewaende']['links']}/{o['gewaende']['rechts']}/{o['gewaende']['scheitel']}")
        if o.get("wolkenrand"): t.append(f"Wolke: {o['wolkenrand']['form']} B {o['wolkenrand']['breite']:.2f}")
        if o.get("innen"): i_ = o["innen"][0]; t.append(f"innen: {i_['form']} B {i_['breite']['wert']:.2f} Scheitel {i_['scheitel']['wert']:.2f}")
        tx = int(X(o["zone"][1])) + 6; ty = int(Y(o["zone"][3])) + 12
        if tx + 200 > W: tx = max(2, int(X(o["zone"][0])) - 210)
        for k, s in enumerate(t): cv2.putText(im, s, (tx, ty + 13 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (255, 255, 255), 3, cv2.LINE_AA); cv2.putText(im, s, (tx, ty + 13 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.36, c, 1, cv2.LINE_AA)
    for zz in np.arange(np.ceil(z0), z1, 1.0):
        cv2.line(im, (0, int(Y(zz))), (8 if zz % 5 else 16, int(Y(zz))), (0, 0, 0), 1)
        if zz % 5 == 0: cv2.putText(im, f"{zz:.0f}", (18, int(Y(zz)) + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (0, 0, 0), 1, cv2.LINE_AA)
    for uu in np.arange(np.ceil(u0), u1, 1.0): cv2.line(im, (int(X(uu)), H - 1), (int(X(uu)), H - 8), (0, 0, 0), 1); cv2.putText(im, f"{uu:.0f}", (int(X(uu)) + 2, H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(im, f"{e['id']}  {erg.get('quelle', '')}  Zelle {erg.get('zelle')} m  {len(erg['oeffnungen'])} Oeffnungen", (30, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(pfad, im, [cv2.IMWRITE_JPEG_QUALITY, 85])


def sauber(o):
    if isinstance(o, dict): return {k: sauber(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, (list, tuple)): return [sauber(v) for v in o]
    if isinstance(o, np.generic): return o.item()
    return o


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("ebenen"); ap.add_argument("--wolke", default=""); ap.add_argument("--bild", type=int, default=1)
    ap.add_argument("--nur", default=""); ap.add_argument("--aus", default="", help="Ausgabeordner (Standard <objektordner>/audit)")
    ap.add_argument("--wandbild", default="auto", help="Ordner von fassade_fein (fassaden.json, ortho_<fid>_fein.png, ortho_<fid>_einzeln/); 'auto' = <ebenen>/../fassade_fein, '' = ohne"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit"); os.makedirs(aus, exist_ok=True)
    EJ = [e for e in json.load(open(os.path.join(a.ebenen, "ebenen.json")))["ebenen"] if e.get("art") == "wand" and (not a.nur or e["id"] in a.nur.split(","))]
    W = np.asarray(np.load(a.wolke)[:, :3], float) if a.wolke else None; ber = dict(quelle="tools/oeffnungen_aus_kanten.py", wolke=a.wolke or None, ebenen={}); n_ges = 0
    for e in EJ:
        if not e.get("sweep") or not os.path.exists(e["sweep"]): print(f"{e['id']}: keine Kantenpunkte"); continue
        P = np.load(e["sweep"])["P"].astype(float); wk = None
        if W is not None:
            uw, zw, ww = ebenen_koord(W, e); nah = (ww > -5.0) & (ww < 3.0) & (uw > e["zone"][0] - 0.1) & (uw < e["zone"][1] + 0.1); wk = (uw[nah], zw[nah], ww[nah])
        fd = os.path.join(os.path.dirname(os.path.abspath(a.ebenen.rstrip("/"))), "fassade_fein") if a.wandbild == "auto" else a.wandbild
        wb = wandbild_laden(fd, e, a.objekt) if fd else None
        print(f"{e['id']}: Wandbild " + (f"{wb['quelle']} + {len(wb['einzeln'])} Einzelfotos mit Kamera" if wb else "keins (Form/Masse nur aus Wolke/Kanten)"))
        erg = ebene_auswerten(e, P, wk, wb); erg["wandbild"] = None if wb is None else dict(ordner=fd, bild=wb["quelle"], einzelfotos=len(wb["einzeln"])); n_ges += len(erg["oeffnungen"])
        print(f"{e['id']}: {len(erg['oeffnungen'])} Oeffnungen ({erg.get('quelle')}, Zelle {erg.get('zelle')} m, {erg['kantenpunkte']} Kantenpunkte" + (f", {erg['ohne_tiefe']} geschlossene Zuege ohne Tiefe verworfen" if erg.get("ohne_tiefe") else "") + ")")
        for o in erg["oeffnungen"]:
            print(f"  {o['id']}: {'' if o['sicher'] else 'UNSICHER '}{o['form']:12s} ({o['form_quelle']}) u {o['zone'][0]:+.2f}..{o['zone'][1]:+.2f} Breite {o['breite']['wert']:.2f} Sohle {o['sohlbank']['wert']:.2f} "
                  + (f"Kaempfer {o['kaempfer']['wert']:.2f} " if o["kaempfer"]["wert"] is not None else "") + f"Scheitel {o['scheitel']['wert']:.2f} Tiefe {o['laibung_tiefe']['wolke']} Kantenpunkte {o['kantenpunkte_am_umriss']} ({o['umriss_belegt']:.0%})")
            wi = o.get("wandbild") or {}
            if wi:
                rs = " ".join(f"{k} {v['rest']:.3f}" for k, v in (wi.get("reste") or {}).items())
                gw = o.get("gewaende") or {}
                print(f"      wandbild: form {wi.get('form', '-')} (Reste {rs})  innen {(wi.get('innen') or {}).get('breite')} aussen {(wi.get('aussen') or {}).get('breite')} "
                      f"Gewaende {gw.get('links')}/{gw.get('rechts')}/{gw.get('scheitel')} Tiefe Innenkante {gw.get('tiefe_innenkante_links')}/{gw.get('tiefe_innenkante_rechts')} "
                      f"Scheitel innen {(wi.get('innen') or {}).get('scheitel')} aussen {(wi.get('aussen') or {}).get('scheitel')}" + (f"  HINWEIS {wi['hinweis']}" if wi.get("hinweis") else ""))
            for i_ in o.get("innen", []): print(f"      innen: {i_['form']} Breite {i_['breite']['wert']:.2f} Sohle {i_['sohlbank']['wert']:.2f} Scheitel {i_['scheitel']['wert']:.2f} Tiefe {i_['laibung_tiefe']['wolke']}")
        if a.bild and "_kanten" in erg: kontrollbild(e, erg, os.path.join(aus, f"oeffnungen_kanten_{e['id']}.jpg"), wandbild=wb)
        ber["ebenen"][e["id"]] = sauber(erg)
    json.dump(ber, open(os.path.join(aus, "oeffnungen_kanten.json"), "w"), indent=1, ensure_ascii=False)
    print(f"-> {os.path.join(aus, 'oeffnungen_kanten.json')}: {n_ges} Oeffnungen"); return 0 if n_ges else 3


if __name__ == "__main__": sys.exit(main())
