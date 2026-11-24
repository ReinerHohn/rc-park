#!/usr/bin/env python3
"""putz_wandbild.py - glatte Putzflaeche aus dem Wandbild (mehrere entzerrte Einzelfotos einig) und Netz-Relief dort glatt (21.11.2026).

Anlass (Nutzerbild schwabentor-1120 zeigen/umgang_bau_ansicht.jpg, Wand w02 Stadtseite mit Uhr): auf dem glatt verputzten Mittelfeld lagen
'Kruemel' - das Netz der dichten Wolke ist auf hellem, texturarmem Putz lueckenhaft (w02: 39 % Loecher), die verbliebenen Einzelzellen weichen
5-15 cm vom Wandniveau ab (Rauschen, Oberleitungskabel, Schatten) und relief_roh/putz_eben liess alles > 5 cm Abweichung stehen.
KRITERIUM (WANDBILD = BAUPLAN, nicht das Netz): Putz = Zelle, die in >= min_fotos entzerrten Einzelfotos (fassade_fein/ortho_<fid>_einzeln) gesehen wird
und in >= anteil davon KEINE Feinstruktur zeigt (Hochpass 2 cm / Ortshelligkeit 15 cm < schwelle). Kabel, Schatten, Baeume stehen vor der Wand und liegen in
jedem Foto woanders -> die Mehrheit zeigt dort glatten Putz. Quader, Gesimse, Fenstergewaende, Uhr zeigen in allen Fotos Struktur -> kein Putz.
Gemessen Schwabentor f00 (Median ueber 10-24 Fotos): Putz 0,25-0,30, Uhrring 6, Quaderwerk > 2 (Schwelle 0,8).

  glatt_karte(ffn, fid)                -> dict(putz, n, u0, z1, zelle)   (Raster der Fassade, 5 cm)
  putz_auf_relief(npz_relief, ffn)     -> bool-Maske im Relief-Raster oder None (keine passende Fassade / kein Einzelbild); art="quader" = Quaderflaeche laut Wandbild
  relief_putz_glatt(f_in, f_out, putz, frei=[(u, z, r)]) -> dict  Putzzellen = ein Niveau (putz_niveau_m), Rest ohne Netzwoelbung;
                                        Kreise 'frei' (Uhr: baut der Generator aus dem Wandbild) ebenfalls auf das Niveau.
  tiefe_belegt(gemessen, flaeche, px)  -> bool  Netztiefe mit Mehrfoto-Beleg (gemessene Umgebung, keine Netzinsel im Lochfeld); relief_putz_glatt glaettet den Rest.
Westwand w00 (21.11.): Kruemelbaender = einzelne Netzinseln im Lochfeld (kein Wandgemaelde - die Einzelfotos zeigen dort glatten Putz); sie verdeckten in den
Einzelbildern die Wand (schwarze Flecken) und der Hochpass las die Schwarzkanten als Struktur -> Selbstbestaetigung. Beides behoben (normierter Hochpass, tiefe_belegt).
Aufruf (Probe):  putz_wandbild.py <relief/<wand>_voll.npz> <fassade_fein-ordner> [--aus <wand>_glatt.npz]
"""
import sys, os, json, glob, argparse, numpy as np

_CACHE = {}


def glatt_karte(ffn, fid, zelle=0.05, schwelle=0.8, min_fotos=3, anteil=0.6, hochpass=0.02, ort=0.15, rau_schwelle=3.0, rau_fenster=0.55):
    """Putzkarte einer Fassade aus ihren entzerrten Einzelfotos (Raster aus fassade_fein/fassaden.json). Ohne Einzelbilder None.
    Zusaetzlich 'quader' (21.11.2026, Schwabentor w01): Zelle in >= anteil der sehenden Fotos mit Feinstruktur >= rau_schwelle (Quaderwerk > 2, Putz 0,25-0,30,
    Uhrring 6 - gemessen f00) UND Mehrheit im Fenster rau_fenster (Einzelkanten von Fenstern, Schildern, Kabeln zaehlen nicht als Flaeche)."""
    from PIL import Image                                                 # ohne cv2: laeuft auch in der Generator-Umgebung (fassaden_kette.anbauen)
    from scipy.ndimage import gaussian_filter
    key = (os.path.abspath(ffn), fid, zelle, schwelle, min_fotos, anteil, rau_schwelle, rau_fenster)
    if key in _CACHE: return _CACHE[key]
    try: FF = {f["id"]: f for f in json.load(open(os.path.join(ffn, "fassaden.json")))["fassaden"]}
    except Exception: return None
    R = (FF.get(fid) or {}).get("raster"); fs = sorted(glob.glob(os.path.join(ffn, f"ortho_{fid}_einzeln", "*.png")))
    if not R or len(fs) < min_fotos: return None
    c = float(R["zelle"]); k = max(1, int(round(zelle / c))); n = None; g_ = None; r_ = None
    for f in fs:
        try: g = np.asarray(Image.open(f).convert("L"), np.float32)
        except Exception: continue
        da = g > 0
        # 21.11.2026 (w00 Westwand): schwarze Verdeckungsflecken der Einzelbilder (fassade_ortho: erster Strahltreffer = Netzkruemel des eigenen Modells) lasen sich als
        # 'Feinstruktur' (Hochpass ueber die Schwarzkante) -> Kruemel bestaetigten sich selbst. Filter nur ueber gueltige Pixel (normierte Faltung), Randpixel ohne Umgebung nicht werten.
        w_ = da.astype(np.float32); ws_ = gaussian_filter(w_, hochpass / c, truncate=3.0)
        def nf(x, s): return gaussian_filter(x * w_, s, truncate=3.0) / np.maximum(gaussian_filter(w_, s, truncate=3.0), 1e-3)
        t = np.abs(g - nf(g, hochpass / c)) / (nf(g, ort / c) + 10.0) * 100.0; da = da & (ws_ > 0.5)
        H, W = (g.shape[0] // k) * k, (g.shape[1] // k) * k
        s = np.where(da, t, 0.0)[:H, :W].reshape(H // k, k, W // k, k).sum((1, 3)); m = da[:H, :W].reshape(H // k, k, W // k, k).sum((1, 3))
        sicht = m >= 0.5 * k * k; gl = sicht & (s / np.maximum(m, 1) < schwelle)
        ra = sicht & (s / np.maximum(m, 1) >= rau_schwelle)
        n = sicht.astype(np.int32) if n is None else n + sicht; g_ = gl.astype(np.int32) if g_ is None else g_ + gl; r_ = ra.astype(np.int32) if r_ is None else r_ + ra
    if n is None: return None
    putz = (n >= min_fotos) & (g_ >= anteil * np.maximum(n, 1))
    from scipy.ndimage import uniform_filter
    kf = max(1, int(round(rau_fenster / (c * k)))) | 1; q_ = ((n >= min_fotos) & (r_ >= anteil * np.maximum(n, 1))).astype(np.float32)
    quader = (uniform_filter(q_, kf, mode="nearest") >= 0.5) & (n >= min_fotos)
    erg = dict(putz=putz, quader=quader, n=n, glatt=g_, rau=r_, u0=float(R["u0"]), z1=float(R["z1"]), zelle=c * k, fotos=len(fs)); _CACHE[key] = erg; return erg


def putz_auf_relief(Z, ffn, parallel=0.95, abstand=1.0, art="putz", **kw):
    """Putzkarte der passenden Fassade (Normale parallel, Ebene < abstand m) auf das Relief-Raster Z (dict/npz mit a, t, n, u0, z0, px, rel) legen.
    Zellen ohne Fassadenbild = False (kein Putz-Beleg). None, wenn keine Fassade passt.
    art="quader": stattdessen die Zellen, die das Wandbild als Quaderflaeche belegt (glatt_karte 'quader'); ohne Fassadenbild False.
    Fuer relief_putz.py: Farb-Putz nur, wo das Wandbild nicht Quaderwerk zeigt."""
    try: FF = json.load(open(os.path.join(ffn, "fassaden.json")))["fassaden"]
    except Exception: return None
    a = np.asarray(Z["a"], float)[:2]; t = np.asarray(Z["t"], float)[:2]; nw = np.asarray(Z["n"], float)[:2]; H, W = Z["rel"].shape; px = float(Z["px"]); u0, z0 = float(Z["u0"]), float(Z["z0"])
    uu = u0 + (np.arange(W) + 0.5) * px; zz = z0 + (H - 1 - np.arange(H) + 0.5) * px; xy = a[None, :] + uu[:, None] * t[None, :]
    best = None
    for F in FF:
        o = np.asarray(F["o"], float); d = np.asarray(F["d"], float); n = np.asarray(F["n"], float)
        if n @ nw < parallel: continue
        ab = float(np.median(np.abs((xy - o) @ n)))
        if ab > abstand or (best is not None and ab >= best[0]): continue
        best = (ab, F, o, d)
    if best is None: return None
    K = glatt_karte(ffn, best[1]["id"], **kw)
    if K is None: return None
    uf = (xy - best[2]) @ best[3]; j = np.floor((uf - K["u0"]) / K["zelle"]).astype(int); i = np.floor((K["z1"] - zz) / K["zelle"]).astype(int)
    P = K["quader"] if art == "quader" else K["putz"]; okj = (j >= 0) & (j < P.shape[1]); oki = (i >= 0) & (i < P.shape[0])
    M = np.zeros((H, W), bool); M[np.ix_(oki, okj)] = P[np.ix_(i[oki], j[okj])]; return M


def tiefe_belegt(gemessen, flaeche, px, fenster=0.25, min_dichte=0.6, insel_m2=0.1):
    """Netz-Tiefe mit Mehrfoto-Beleg (21.11.2026, w00 Westwand schwabentor-1120): eine gemessene Netzzelle traegt Relief nur, wenn ihre Umgebung (fenster m) zu >= min_dichte
    gemessen ist UND sie zu einer gemessenen Flaeche >= insel_m2 gehoert (4er-Nachbarschaft). Die dichte Wolke fusioniert nur, wo mehrere Fotos dieselbe Tiefe sehen; einzelne
    Netzinseln mitten im Lochfeld (texturarmer Putz, Oberleitung/Kabel davor) sind Tiefen OHNE konsistenten Mehrfoto-Beleg -> Kruemel. Gemessen (Rohnetz):
    w00 Lochfeld-Sprenkel 1 Zelle gross, Abweichung 10-13 cm, fast alle unbelegt; Nordquader w01/w03 94-98 % der Abweichungen >= 5 cm belegt (Huelle 43 % / 42 % Loch roh).
    gemessen/flaeche = bool-Raster (flaeche = Wand ohne Oeffnung). Rueckgabe bool-Raster belegt."""
    from scipy import ndimage as ndi
    gemessen = np.asarray(gemessen, bool); flaeche = np.asarray(flaeche, bool)
    k = max(3, int(round(fenster / px)) | 1)
    dichte = ndi.uniform_filter(gemessen.astype(np.float32), k) / np.maximum(ndi.uniform_filter(flaeche.astype(np.float32), k), 1e-6)
    lab, n = ndi.label(gemessen)
    if not n: return np.zeros_like(gemessen)
    gr = ndi.sum(np.ones(gemessen.shape, np.float32), lab, np.arange(1, n + 1)) * px * px
    return gemessen & np.isin(lab, np.flatnonzero(gr >= insel_m2) + 1) & (dichte >= min_dichte)


def relief_putz_glatt(f_in, f_out, putz, frei=(), kruemel_m2=0.15, band=0.05, koerper_m2=0.25, spitze=0.03):
    """Relief einer Putzwand (relief_roh-Ergebnis <wand>_voll.npz) glaetten: Putzniveau = Median der Putzzellen; Putzzellen und kleine Nicht-Putz-Inseln
    (< kruemel_m2, ringsum Putz: Kabelreste, Naegel) auf das Niveau; uebrige Zellen ohne die grobe Netzwoelbung (rel - Wandniveau + Niveau), Form bleibt.
    frei = Kreise (u, z, r) in Reliefkoordinaten, die der Generator selbst baut (Uhr) -> Niveau. Schreibt f_out (+ .jpg) mit putz_niveau_m."""
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from fassaden_kette import wandniveau
    Z = dict(np.load(f_in)); rel = Z["rel"].astype(np.float32); px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); H, W = rel.shape
    wand = Z["wand"] if "wand" in Z else np.ones_like(rel, bool); oe = Z["oeffnung"] & wand; m = wand & ~oe & (rel > 0.0)
    p = putz & m
    if p.sum() < max(20, 0.02 * m.sum()): return dict(unveraendert=True, putz_anteil=round(float(p.sum() / max(m.sum(), 1)), 3))
    lab, k = ndi.label(m & ~p)                                            # Nicht-Putz-Inseln im Putz: klein und ohne Kontakt zum Wandrand -> Kruemel
    if k:
        gr = ndi.sum(np.ones_like(rel), lab, np.arange(1, k + 1)) * px * px; rand = np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])
        klein = np.flatnonzero(gr < kruemel_m2) + 1; klein = klein[~np.isin(klein, rand)]; p |= np.isin(lab, klein) & m
    jj, ii = np.meshgrid(np.arange(W), np.arange(H)); uu = u0 + (jj + 0.5) * px; zz = z0 + (H - 1 - ii + 0.5) * px; fr = np.zeros_like(m)
    for (uc, zc, r) in frei: fr |= (uu - uc) ** 2 + (zz - zc) ** 2 <= r * r
    L = wandniveau(rel, m, px); niv = float(np.median(rel[p]))            # Wandniveau aus ALLEN Wandzellen (nur aus Putz: Kachelstufen, wo Putz fehlt)
    if L is None: L = np.full_like(rel, niv)
    # Ein einfarbiger Bauteilkoerper (Gesims, Lisene) sieht im Bild wie Putz aus. Er bleibt, wenn er im Netz ein ZUSAMMENHAENGENDER Koerper ist (Abweichung >= band,
    # 4er-Nachbarschaft, >= koerper_m2, fuellt >= 50 % seines Rahmens); Kruemel sind verstreute Einzelzellen zwischen Netzloechern.
    loch = Z["loch"] if "loch" in Z else np.zeros_like(m)                 # Netzloch (relief_roh: konstant 'vorstand') = Wandflaeche ohne Messung -> Niveau, keine Woelbung aufpraegen
    # 21.11.2026 (w00 Westwand, Kruemelbaender): Relief nur, wo die Netztiefe Mehrfoto-Beleg hat (tiefe_belegt: gemessene Umgebung, keine Netzinsel im Lochfeld).
    # Unbelegte Zellen = Niveau wie das Loch, auch wo kein Einzelfoto die Wand zeigt (dort fehlte bisher jedes Putzkriterium). OHNE_TIEFENBELEG=1 = alter Stand.
    unbel = np.zeros_like(m) if os.environ.get("OHNE_TIEFENBELEG") == "1" else m & ~tiefe_belegt(m & ~loch, m, px)
    lab2, k2 = ndi.label(m & ~unbel & (np.abs(rel - L) >= band)); n_koerper = 0
    for k_, sl in enumerate(ndi.find_objects(lab2), 1):
        if sl is None: continue
        cc = lab2[sl] == k_
        if cc.sum() * px * px >= koerper_m2 and cc.mean() >= 0.5: p[sl] &= ~cc; n_koerper += 1
    neu = np.where(m, rel - L + niv, rel); neu[(p | fr | loch | unbel) & m] = niv; neu = neu.astype(np.float32)
    if spitze and os.environ.get("OHNE_TIEFENBELEG") != "1":                # Spitzen (>= spitze gegen den 3x3-Median, hoechstens 1 Nachbar gleichsinnig) = Rauschen unter dem Netzraster -> Median.
        med = ndi.median_filter(neu, 3); dv = neu - med; sp = np.zeros_like(m)        # Linien (Fugen, Kanten) haben >= 2 gleichsinnige Nachbarn und bleiben
        for sg in (1.0, -1.0):
            hoch = (sg * dv >= 0.5 * spitze).astype(np.int32); nb = ndi.convolve(hoch, np.ones((3, 3), np.int32), mode="constant") - hoch
            sp |= m & (sg * dv >= spitze) & (nb <= 1)
        neu[sp] = med[sp]
    n_unbel = int((unbel & ~loch & ~p & (np.abs(rel - L) >= band)).sum())  # Abweichungen >= band, die nur der Tiefenbeleg glaettet
    Z["rel"] = neu; Z["putz_niveau_m"] = niv; Z["putz_wandbild"] = p; Z["tiefe_unbelegt"] = unbel; np.savez_compressed(f_out, **Z)
    try:
        from PIL import Image
        lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); g_ = (np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8); im_ = np.stack([g_] * 3, -1)
        im_[p] = (im_[p] * 0.7 + np.array([0, 0, 70])).astype(np.uint8); im_[fr & m] = (im_[fr & m] * 0.6 + np.array([90, 70, 0])).astype(np.uint8)
        u_ = unbel & ~loch & ~p; im_[u_] = (im_[u_] * 0.6 + np.array([0, 80, 0])).astype(np.uint8); im_[~wand] = (90, 90, 90); im_[oe] = (0, 60, 120)
        Image.fromarray(np.repeat(np.repeat(im_, 3, 0), 3, 1)).save(f_out[:-4] + ".jpg", quality=88)     # blaustichig = Putz (Wandbild), gelbstichig = frei (Uhr), gruenstichig = Netztiefe ohne Beleg (glatt), dunkelblau = Oeffnung
    except Exception: pass
    vorher = float(np.std(rel[p] - L[p])) if p.any() else 0.0
    return dict(putz_anteil=round(float(p.sum() / max(m.sum(), 1)), 3), putz_niveau_m=round(niv, 3), rausch_vorher_cm=round(vorher * 100, 1), frei=len(frei), koerper_behalten=n_koerper,
                unbelegt_kruemel_m2=round(n_unbel * px * px, 2))


def vorbau_zonen(od, Z, parallel=0.95, abstand=1.0):
    """Rechtecke (u0, u1, z0, z1) im Relief-Raster Z hinter/unter Vorbauten (audit/vorbauten_auto.json, Gruppe u0..u1, z0..max(z1, Vordach-Anschluss)) der Fassade,
    deren Normale zu Z passt und deren Ebene < abstand m von der Reliefwand liegt. [] ohne Datei."""
    f = os.path.join(od, "audit", "vorbauten_auto.json")
    if not os.path.exists(f): return []
    a = np.asarray(Z["a"], float)[:2]; t = np.asarray(Z["t"], float)[:2]; nw = np.asarray(Z["n"], float)[:2]; r = []
    for F in json.load(open(f)).get("fassaden", []):
        o = np.asarray(F["o"], float); d = np.asarray(F["d"], float); n = np.asarray(F["n"], float)
        if n @ nw < parallel or abs((o - a) @ nw) > abstand: continue
        for g in F.get("gruppen", []):
            V = ((g.get("galerie") or {}).get("vordach") or {}); z1 = max(float(g["z1"]), float(V.get("z_anschluss", g["z1"])))
            ua, ub = sorted((float((o + g["u0"] * d - a) @ t), float((o + g["u1"] * d - a) @ t))); r.append((ua, ub, float(g["z0"]), z1))
    return r


def kanten_wand(ebenen_json, Z, parallel=0.95, abstand=1.0):
    """Triangulierte Fotokanten der passenden WAND-Ebene (tools/ebenen_bauplan.py -> ebenen.json, sweep.npz 'P') im Relief-Raster Z: (u, z, w) mit w = Abstand vor der
    Reliefebene (Normale Z['n']). None ohne passende Ebene."""
    try: E = json.load(open(ebenen_json))["ebenen"]
    except Exception: return None
    a = np.asarray(Z["a"], float)[:2]; t = np.asarray(Z["t"], float)[:2]; nw = np.asarray(Z["n"], float)[:2]; best = None
    for e in E:
        if e.get("art") != "wand": continue
        o = np.asarray(e["o"], float); n = np.asarray(e["n"], float)
        if n @ nw < parallel: continue
        ab = abs((o + float(e.get("w", 0.0)) * n - a) @ nw)
        if ab <= abstand and (best is None or ab < best[0]): best = (ab, e)
    if best is None: return None
    sw = best[1].get("sweep") or os.path.join(os.path.dirname(ebenen_json), best[1]["id"], "sweep.npz")
    try: P = np.load(sw)["P"]
    except Exception: return None
    return np.stack([(P[:, :2] - a) @ t, P[:, 2], (P[:, :2] - a) @ nw], 1)


def relief_vorbau_flach(f_in, f_out, zonen, kanten, band=0.05, radius=0.3, min_punkte=3, anteil=0.5, kachel=2.0):
    """Relief HINTER/UNTER VORBAUTEN nur mit Kantenbeleg (21.11.2026, Nutzerbild neben_eigen__IMG_20261106_113231: Wandgemaelde unter dem Vordach als Klumpen).
    Dort sieht kaum ein Foto die Wand frei (Pfosten, Bruestung, Vordach davor); die dichte Wolke verschmiert den Vordergrund in die Wand - das Netz ist dicht
    (tiefe_belegt greift nicht) und das Gemaelde ist bunt (kein Putz). KRITERIUM aus den triangulierten Fotokanten der Wandebene: eine Reliefzelle mit Abweichung >= band
    vom Wandniveau bleibt nur, wenn im Umkreis 'radius' >= min_punkte Kantenpunkte liegen und >= anteil davon gleichsinnig >= band/2 vor/hinter der Kanten-Wandebene
    (Median der Kanten in der Zone) liegen = echter Tiefensprung. Gemalte Kanten liegen auf der Wandebene, fehlende Kanten = kein Mehrfoto-Beleg -> Wandniveau.
    zonen = [(u0, u1, z0, z1)] (vorbau_zonen), kanten = (N, 3) u, z, w (kanten_wand) oder None (dann keine Zelle belegt). Schreibt f_out (+ .jpg), Rueckgabe dict."""
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from fassaden_kette import wandniveau
    Z = dict(np.load(f_in)); rel = Z["rel"].astype(np.float32); px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); H, W = rel.shape
    m = np.isfinite(rel) & (rel != 0)
    if "wand" in Z: m &= Z["wand"].astype(bool)
    if "oeffnung" in Z: m &= ~Z["oeffnung"].astype(bool)
    jj, ii = np.meshgrid(np.arange(W), np.arange(H)); uu = u0 + (jj + 0.5) * px; zz = z0 + (H - 1 - ii + 0.5) * px; zo = np.zeros((H, W), bool)
    for (ua, ub, za, zb) in zonen: zo |= (uu >= ua) & (uu <= ub) & (zz >= za) & (zz <= zb)
    zo &= m
    if not zo.any(): return dict(unveraendert=True, zone_m2=0.0)
    L = wandniveau(rel, m, px, kachel=kachel)
    if L is None: return dict(unveraendert=True, zone_m2=round(float(zo.sum()) * px * px, 2))
    dv = rel - L; ab = zo & (np.abs(dv) >= band)
    vor = np.zeros((H, W), np.float32); hin = np.zeros_like(vor); alle = np.zeros_like(vor)
    if kanten is not None and len(kanten):
        K = np.asarray(kanten, float); ci = (H - 1 - np.floor((K[:, 1] - z0) / px)).astype(int); cj = np.floor((K[:, 0] - u0) / px).astype(int); ok = (ci >= 0) & (ci < H) & (cj >= 0) & (cj < W)
        K, ci, cj = K[ok], ci[ok], cj[ok]; inz = zo[ci, cj]
        if inz.sum() >= min_punkte:
            w_ref = float(np.median(K[inz, 2])); dk = K[:, 2] - w_ref
            np.add.at(alle, (ci, cj), 1.0); np.add.at(vor, (ci[dk >= band / 2], cj[dk >= band / 2]), 1.0); np.add.at(hin, (ci[dk <= -band / 2], cj[dk <= -band / 2]), 1.0)
    # je zusammenhaengendem Abweichungskoerper (gleiches Vorzeichen): Kanten in seinem um 'radius' erweiterten Umriss - Innenflaechen echter Koerper haben keine Kanten,
    # ihr Rand schon (dort liegt der Tiefensprung); eine gemalte Blase hat Kanten nur auf der Wandebene.
    beleg = np.zeros((H, W), bool); r_ = max(1, int(round(radius / px))); st = np.ones((2 * r_ + 1, 2 * r_ + 1), bool)
    for sg, zahl in ((1.0, vor), (-1.0, hin)):
        lab, nk = ndi.label(ab & (sg * dv > 0))
        for k_, sl in enumerate(ndi.find_objects(lab), 1):
            if sl is None: continue
            s2 = tuple(slice(max(0, s.start - r_), s.stop + r_) for s in sl); cc = lab[s2] == k_; um = ndi.binary_dilation(cc, st)
            n_ = float(alle[s2][um].sum()); g_ = float(zahl[s2][um].sum())
            if n_ >= min_punkte and g_ >= anteil * n_: beleg[s2] |= cc
    flach = ab & ~beleg
    if os.environ.get("OHNE_KANTENBELEG") != "1": flach = _rand_mit(flach, dv, zo, px, band=band)      # 24.11.2026: Umriss der Klumpen mit (sonst 'wirre Wuelste' 1122w Nord)
    neu = rel.copy(); neu[flach] = L[flach]
    Z["rel"] = neu; Z["vorbau_flach"] = flach; np.savez_compressed(f_out, **Z)
    try:
        from PIL import Image
        lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); g_ = (np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8); im_ = np.stack([g_] * 3, -1)
        im_[flach] = (im_[flach] * 0.6 + np.array([90, 0, 60])).astype(np.uint8); im_[zo & ~flach & ab] = (im_[zo & ~flach & ab] * 0.6 + np.array([0, 90, 0])).astype(np.uint8)
        Image.fromarray(np.repeat(np.repeat(im_, 3, 0), 3, 1)).save(f_out[:-4] + ".jpg", quality=88)     # violett = ohne Kantenbeleg auf Wandniveau, gruen = Tiefensprung belegt
    except Exception: pass
    return dict(zone_m2=round(float(zo.sum()) * px * px, 2), abweichung_m2=round(float(ab.sum()) * px * px, 2), flach_m2=round(float(flach.sum()) * px * px, 2),
                belegt_m2=round(float((ab & beleg).sum()) * px * px, 2), kanten=0 if kanten is None else int(len(kanten)))


def _rand_mit(flach, dv, m, px, rand=0.3, band=0.05, eps=0.005):
    """Flachgelegte Abweichungskoerper MIT ihrem Uebergangsrand: gleichsinnige Zellen unter 'band' (|dv| > eps), die mit dem Koerper zusammenhaengen, hoechstens 'rand' m weit
    (sonst bleibt der Umriss als 1-5-cm-Stufe stehen - 24.11.2026 Nutzerbild 1122w Nord: 'wirre Wuelste' = Umrisslinien der in relief_vorbau_flach flachgelegten Gemaelde-Klumpen)."""
    from scipy import ndimage as ndi
    if not flach.any() or rand <= 0: return flach
    r_ = max(1, int(round(rand / px))); st = np.ones((2 * r_ + 1, 2 * r_ + 1), bool); out = flach.copy()
    for sg in (1.0, -1.0):
        f_ = flach & (sg * dv > 0)
        if not f_.any(): continue
        zone = ndi.binary_dilation(f_, st) & m & (sg * dv > eps) & ((np.abs(dv) < band) | f_)
        lab, n = ndi.label(zone)
        if n: out |= np.isin(lab, np.unique(lab[f_ & zone])) & (lab > 0) & (np.abs(dv) < band)
    return out


def relief_kanten_beleg(f_in, f_out, kanten, band=0.05, radius=0.3, min_punkte=4, anteil=0.35, tol=0.15, umfeld=1.0, rand=0.3, lang=1.5, dick=0.45, fuell=0.5,
                        druck_min=0.07, kachel=2.0, aus_maske=None, rille=0.06):
    """KRUEMEL OHNE KANTE WEG - Relief einer ganzen Wand nur mit Tiefenbeleg in den triangulierten Fotokanten (24.11.2026, Lauf 1122w, Nutzerbild neben_eigen__IMG_20261106_113231
    + neben_sued_w: 'Knochen'-Blob ueber dem Torbogen Nord, Beulen im bemalten Putzfeld Sued, Wulst am Brunnen). URSACHE: relief_putz_glatt glaettet nur die Zellen, die das
    Wandbild als Putz (glatt in allen Einzelfotos) belegt; ein Wandgemaelde, ein freistehender Brunnen davor oder Quaderwerk zeigen dort Feinstruktur -> kein Putz -> die Netztiefe
    (bzw. Mono-Tiefe aus Farbe) blieb ungeprueft als Relief stehen (putz_wandbild auf w02/w06 = 0 % Putz). KRITERIUM (Kernmethode Form = Fotokanten + Triangulation):
    ein zusammenhaengender Abweichungskoerper (>= band vom Wandniveau, gleiches Vorzeichen) bleibt nur, wenn
      (a) im Umriss + radius >= min_punkte Kantenpunkte liegen, deren Tiefe (gegen den Median der Kanten im Umfeld 'umfeld' m) gleichsinnig >= band/2 und hoechstens
          Koerperhoehe + tol vor/hinter der Wand liegt, und das >= anteil der Kanten bis zu dieser Tiefe sind (Gemaelde: Kanten auf der Wand; Vordach/Galerie 1 m davor zaehlt nicht), oder
      (b) er linienhaft ist (Gesims/Band/Lisene wie relief_bereinigen: lang x dick, gerade), oder
      (c) er den Oeffnungsrand beruehrt (Bogen/Gewaende: dort ist der Oeffnungsrand die Kante);
    Zellen der Maske aus_maske (Quaderraster 'stein_id' > 0) samt 'rille' m Rand werden nicht gewertet (dort entscheidet das Wandbild);
    und seine kleinere Ausdehnung >= druck_min m ist (0,8 mm H0 bei 1:87 = 0,07 m; schmalere Grate druckt man nicht).
    Sonst Wandniveau samt Uebergangsrand (_rand_mit). kanten = (N, 3) u, z, w (kanten_wand) - ohne Kanten (None/leer) bleibt das Relief UNVERAENDERT
    (keine Kantenstufe = kein Urteil). Schreibt f_out (+ .jpg: rot = ohne Kantenbeleg flach, gruen = belegt, blau = linienhaft), Rueckgabe dict."""
    from scipy import ndimage as ndi
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from fassaden_kette import wandniveau
    Z = dict(np.load(f_in)); rel = Z["rel"].astype(np.float32); px = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); H, W = rel.shape
    if kanten is None or len(kanten) < min_punkte: return dict(unveraendert=True, grund="keine Fotokanten der Wandebene")
    m = np.isfinite(rel) & (rel != 0)
    if "wand" in Z: m &= np.asarray(Z["wand"], bool)
    if "oeffnung" in Z: m &= ~np.asarray(Z["oeffnung"], bool)
    if m.sum() < 20: return dict(unveraendert=True, grund="keine Wandzellen")
    L = wandniveau(rel, m, px, kachel=kachel)
    if L is None: return dict(unveraendert=True, grund="kein Wandniveau")
    dv = np.where(m, rel - L, 0.0).astype(np.float32)
    K = np.asarray(kanten, float); ci = (H - 1 - np.floor((K[:, 1] - z0) / px)).astype(int); cj = np.floor((K[:, 0] - u0) / px).astype(int)
    ok = (ci >= 0) & (ci < H) & (cj >= 0) & (cj < W); K, ci, cj = K[ok], ci[ok], cj[ok]
    if len(K) < min_punkte: return dict(unveraendert=True, grund="keine Fotokanten im Reliefraster")
    # Kanten je Zelle als Liste (Index sortiert nach Zelle) fuer schnelle Auswahl je Koerper
    zid = ci * W + cj; ordn = np.argsort(zid, kind="stable"); zid_s = zid[ordn]
    def kanten_in(maske):
        z_ = np.flatnonzero(maske.ravel()); lo = np.searchsorted(zid_s, z_, "left"); hi = np.searchsorted(zid_s, z_, "right")
        if not len(z_) or not (hi > lo).any(): return np.zeros(0, int)
        return np.concatenate([ordn[a:b] for a, b in zip(lo, hi) if b > a])
    r_ = max(1, int(round(radius / px))); ru = max(r_, int(round(umfeld / px)))
    aus = np.zeros((H, W), bool) if aus_maske is None else np.asarray(aus_maske, bool)
    if aus.any(): aus = ndi.binary_dilation(aus, np.ones((2 * max(1, int(round(rille / px))) + 1,) * 2, bool))      # Steine + ihre Rillen (Quaderraster) nicht werten
    oe = np.asarray(Z["oeffnung"], bool) if "oeffnung" in Z else np.zeros((H, W), bool)
    oe_d = ndi.binary_dilation(oe, np.ones((5, 5), bool)) if oe.any() else oe          # Gewaende/Bogen am Oeffnungsrand: Kante = der Oeffnungsrand selbst (Laibung baut eigene Stufe)
    flach = np.zeros((H, W), bool); bel_m = np.zeros((H, W), bool); lin_m = np.zeros((H, W), bool); n_k = dict(belegt=0, linienhaft=0, oeffnung=0, flach=0, schmal=0)
    for sg in (1.0, -1.0):
        lab, nk = ndi.label(m & ~aus & (sg * dv >= band))
        for k_, sl in enumerate(ndi.find_objects(lab), 1):
            if sl is None: continue
            cc = lab[sl] == k_; h_ = (sl[0].stop - sl[0].start) * px; b_ = (sl[1].stop - sl[1].start) * px
            def setz(ziel): ziel[sl] |= cc
            if (oe_d[sl] & cc).any(): n_k["oeffnung"] += 1; continue
            if min(h_, b_) < druck_min - 1e-9: setz(flach); n_k["schmal"] += 1; continue
            if ((b_ >= lang and h_ <= dick) or (h_ >= lang and b_ <= dick)) and cc.mean() >= fuell: setz(lin_m); n_k["linienhaft"] += 1; continue
            s2 = tuple(slice(max(0, s.start - ru), s.stop + ru) for s in sl); ganz = np.zeros((H, W), bool); ganz[sl] = cc
            nah = ndi.binary_dilation(ganz[s2], np.ones((2 * r_ + 1, 2 * r_ + 1), bool)); weit = ndi.binary_dilation(ganz[s2], np.ones((2 * ru + 1, 2 * ru + 1), bool))
            N_ = np.zeros((H, W), bool); N_[s2] = nah; Wm = np.zeros((H, W), bool); Wm[s2] = weit & ~nah
            iw = kanten_in(Wm); inah = kanten_in(N_); hmax = float((sg * dv[sl])[cc].max())
            wref = float(np.median(K[iw, 2])) if len(iw) >= min_punkte else (float(np.median(K[inah, 2])) if len(inah) else 0.0)
            dk = sg * (K[inah, 2] - wref); bis = dk <= hmax + tol; gl = bis & (dk >= band / 2)
            if gl.sum() >= min_punkte and gl.sum() >= anteil * max(bis.sum(), 1): setz(bel_m); n_k["belegt"] += 1; continue
            setz(flach); n_k["flach"] += 1
    weg = _rand_mit(flach, dv, m, px, rand=rand, band=band) & ~aus
    neu = rel.copy(); neu[weg] = L[weg]; Z["rel"] = neu.astype(np.float32); Z["ohne_kantenbeleg"] = weg; np.savez_compressed(f_out, **Z)
    try:
        from PIL import Image
        lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); g_ = (np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8); im_ = np.stack([g_] * 3, -1)
        for mm, col in ((weg, (120, 0, 0)), (bel_m, (0, 90, 0)), (lin_m, (0, 0, 110))): im_[mm] = (im_[mm] * 0.6 + np.array(col)).astype(np.uint8)
        Image.fromarray(np.repeat(np.repeat(im_, 3, 0), 3, 1)).save(f_out[:-4] + ".jpg", quality=88)
    except Exception: pass
    return dict(flach_m2=round(float(weg.sum()) * px * px, 2), belegt_m2=round(float(bel_m.sum()) * px * px, 2), linienhaft_m2=round(float(lin_m.sum()) * px * px, 2),
                koerper=n_k, kanten=int(len(K)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("fein"); ap.add_argument("--aus"); a = ap.parse_args()
    Z = np.load(a.relief); M = putz_auf_relief(Z, a.fein)
    if M is None: print("keine passende Fassade / keine Einzelbilder"); return 3
    aus = a.aus or a.relief.replace("_voll.npz", "_glatt.npz"); print(relief_putz_glatt(a.relief, aus, M), "->", aus); return 0


if __name__ == "__main__":
    sys.exit(main())
