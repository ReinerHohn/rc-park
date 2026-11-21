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
Ausgabe: <objektordner>/audit/oeffnungen_kanten.json, Bild audit/oeffnungen_kanten_<ebene>.jpg (--bild 1). rc 0 = mindestens eine Oeffnung, rc 3 = keine.
Aufruf: oeffnungen_aus_kanten.py <objekt.json> <ebenen-ordner> [--wolke punkte.npy] [--bild 1] [--nur f00_wand] [--aus ordner]
Grenzen (gemessen Schwabentor 21.11.): die stabilen Fotokanten belegen Bogenkanten nur stueckweise - ohne Wolke bleibt dort kein geschlossener Zug; dann traegt der Wolkenrand
die Form ('form_quelle': 'wolkenrand') und die Kanten nur die Stuecke, die es gibt (Zahl steht dabei).
"""
import sys, os, json, argparse, numpy as np
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


def _raster_maske(o, m, u0, z0, zelle):
    o["_maske"] = m; o["_ras"] = (u0, z0, zelle); return o


def ebene_auswerten(e, P, wolke=None):
    """Eine Wandebene. P = Kantenpunkte (N x 3), wolke = (u, z, w) der dichten Wolke in Ebenenkoordinaten oder None. Rueckgabe dict(oeffnungen, ...)."""
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
            if o: o["zelle"] = zelle; aus.append(_raster_maske(o, f["maske"], zone[0], zb, zelle))
        info["ohne_tiefe"] = n_ohne
    aus.sort(key=lambda o: (o["zone"][2], o["zone"][0]))
    for k, o in enumerate(aus): o["id"] = f"{e['id']}_o{k}"
    return dict(oeffnungen=aus, _kanten=(u, z, w), **info)


def kontrollbild(e, erg, pfad, px_m=60):
    import cv2
    u0, u1, z0, z1 = e["zone"]; r = 0.5; u0 -= r; u1 += r; H, W = int((z1 - z0) * px_m) + 1, int((u1 - u0) * px_m) + 1; im = np.full((H, W, 3), 255, np.uint8)
    X = lambda uu: np.round((np.asarray(uu) - u0) * px_m).astype(int); Y = lambda zz: np.round((z1 - np.asarray(zz)) * px_m).astype(int)
    for o in erg["oeffnungen"]:                                                        # Fleck hellblau
        ru, rz, zelle = o["_ras"]; ys, xs = np.where(o["_maske"]); x, y = X(ru + (xs + 0.5) * zelle), Y(rz + (ys + 0.5) * zelle); k = max(1, int(zelle * px_m / 2) + 1)
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1): im[np.clip(y + dy, 0, H - 1), np.clip(x + dx, 0, W - 1)] = (255, 235, 200)
    ku, kz, kw = erg["_kanten"]; x, y = X(ku), Y(kz); ok = (x >= 0) & (x < W) & (y >= 0) & (y < H); im[y[ok], x[ok]] = np.where((kw[ok] < -DRUCK_MIN_M)[:, None], (200, 80, 0), (90, 90, 90))   # Kanten: grau = Wand, blau = hinter der Wand
    farbe = dict(sturz=(0, 140, 0), rundbogen=(0, 0, 220), segmentbogen=(0, 140, 220), spitzbogen=(200, 0, 200), unbestimmt=(0, 200, 255))
    def zeichne(o, dick):
        f = o["_fit"]; M, teil = umriss(f["uL"], f["uR"], f["zk"], f["h"], o["_zs"], schritt=0.02); c = farbe[o["form"]]
        for t in (0, 1, 2):
            p = M[teil == t]; cv2.polylines(im, [np.c_[X(p[:, 0]), Y(p[:, 1])].astype(np.int32)], False, c, dick, cv2.LINE_AA)
        if o["kaempfer"]["wert"] is not None: cv2.line(im, (int(X(f["uL"])), int(Y(f["zk"]))), (int(X(f["uR"])), int(Y(f["zk"]))), c, 1, cv2.LINE_AA)
        return c
    for o in erg["oeffnungen"]:
        c = zeichne(o, 2)
        for i_ in o.get("innen", []): zeichne(i_, 1)
        t = [f"{o['id'].split('_')[-1]} {'' if o['sicher'] else 'UNSICHER '}{o['form']} ({o['form_quelle']}, Zelle {o['zelle']})", f"B {o['breite']['wert']:.2f}  Sohle {o['sohlbank']['wert']:.2f}",
             (f"Kaempfer {o['kaempfer']['wert']:.2f}  " if o["kaempfer"]["wert"] is not None else "") + f"Scheitel {o['scheitel']['wert']:.2f}",
             "Tiefe " + (f"{o['laibung_tiefe']['wolke']:.2f}" if o["laibung_tiefe"]["wolke"] is not None else "?") + f"  Kantenp. {o['kantenpunkte_am_umriss']}"]
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
    ap.add_argument("--nur", default=""); ap.add_argument("--aus", default="", help="Ausgabeordner (Standard <objektordner>/audit)"); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); aus = a.aus or os.path.join(od, "audit"); os.makedirs(aus, exist_ok=True)
    EJ = [e for e in json.load(open(os.path.join(a.ebenen, "ebenen.json")))["ebenen"] if e.get("art") == "wand" and (not a.nur or e["id"] in a.nur.split(","))]
    W = np.asarray(np.load(a.wolke)[:, :3], float) if a.wolke else None; ber = dict(quelle="tools/oeffnungen_aus_kanten.py", wolke=a.wolke or None, ebenen={}); n_ges = 0
    for e in EJ:
        if not e.get("sweep") or not os.path.exists(e["sweep"]): print(f"{e['id']}: keine Kantenpunkte"); continue
        P = np.load(e["sweep"])["P"].astype(float); wk = None
        if W is not None:
            uw, zw, ww = ebenen_koord(W, e); nah = (ww > -5.0) & (ww < 3.0) & (uw > e["zone"][0] - 0.1) & (uw < e["zone"][1] + 0.1); wk = (uw[nah], zw[nah], ww[nah])
        erg = ebene_auswerten(e, P, wk); n_ges += len(erg["oeffnungen"])
        print(f"{e['id']}: {len(erg['oeffnungen'])} Oeffnungen ({erg.get('quelle')}, Zelle {erg.get('zelle')} m, {erg['kantenpunkte']} Kantenpunkte" + (f", {erg['ohne_tiefe']} geschlossene Zuege ohne Tiefe verworfen" if erg.get("ohne_tiefe") else "") + ")")
        for o in erg["oeffnungen"]:
            print(f"  {o['id']}: {'' if o['sicher'] else 'UNSICHER '}{o['form']:12s} ({o['form_quelle']}) u {o['zone'][0]:+.2f}..{o['zone'][1]:+.2f} Breite {o['breite']['wert']:.2f} Sohle {o['sohlbank']['wert']:.2f} "
                  + (f"Kaempfer {o['kaempfer']['wert']:.2f} " if o["kaempfer"]["wert"] is not None else "") + f"Scheitel {o['scheitel']['wert']:.2f} Tiefe {o['laibung_tiefe']['wolke']} Kantenpunkte {o['kantenpunkte_am_umriss']} ({o['umriss_belegt']:.0%})")
            for i_ in o.get("innen", []): print(f"      innen: {i_['form']} Breite {i_['breite']['wert']:.2f} Sohle {i_['sohlbank']['wert']:.2f} Scheitel {i_['scheitel']['wert']:.2f} Tiefe {i_['laibung_tiefe']['wolke']}")
        if a.bild and "_kanten" in erg: kontrollbild(e, erg, os.path.join(aus, f"oeffnungen_kanten_{e['id']}.jpg"))
        ber["ebenen"][e["id"]] = sauber(erg)
    json.dump(ber, open(os.path.join(aus, "oeffnungen_kanten.json"), "w"), indent=1, ensure_ascii=False)
    print(f"-> {os.path.join(aus, 'oeffnungen_kanten.json')}: {n_ges} Oeffnungen"); return 0 if n_ges else 3


if __name__ == "__main__": sys.exit(main())
