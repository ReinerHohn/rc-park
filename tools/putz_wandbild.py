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
  putz_auf_relief(npz_relief, ffn)     -> bool-Maske im Relief-Raster oder None (keine passende Fassade / kein Einzelbild)
  relief_putz_glatt(f_in, f_out, putz, frei=[(u, z, r)]) -> dict  Putzzellen = ein Niveau (putz_niveau_m), Rest ohne Netzwoelbung;
                                        Kreise 'frei' (Uhr: baut der Generator aus dem Wandbild) ebenfalls auf das Niveau.
  tiefe_belegt(gemessen, flaeche, px)  -> bool  Netztiefe mit Mehrfoto-Beleg (gemessene Umgebung, keine Netzinsel im Lochfeld); relief_putz_glatt glaettet den Rest.
Westwand w00 (21.11.): Kruemelbaender = einzelne Netzinseln im Lochfeld (kein Wandgemaelde - die Einzelfotos zeigen dort glatten Putz); sie verdeckten in den
Einzelbildern die Wand (schwarze Flecken) und der Hochpass las die Schwarzkanten als Struktur -> Selbstbestaetigung. Beides behoben (normierter Hochpass, tiefe_belegt).
Aufruf (Probe):  putz_wandbild.py <relief/<wand>_voll.npz> <fassade_fein-ordner> [--aus <wand>_glatt.npz]
"""
import sys, os, json, glob, argparse, numpy as np

_CACHE = {}


def glatt_karte(ffn, fid, zelle=0.05, schwelle=0.8, min_fotos=3, anteil=0.6, hochpass=0.02, ort=0.15):
    """Putzkarte einer Fassade aus ihren entzerrten Einzelfotos (Raster aus fassade_fein/fassaden.json). Ohne Einzelbilder None."""
    from PIL import Image                                                 # ohne cv2: laeuft auch in der Generator-Umgebung (fassaden_kette.anbauen)
    from scipy.ndimage import gaussian_filter
    key = (os.path.abspath(ffn), fid, zelle, schwelle, min_fotos, anteil)
    if key in _CACHE: return _CACHE[key]
    try: FF = {f["id"]: f for f in json.load(open(os.path.join(ffn, "fassaden.json")))["fassaden"]}
    except Exception: return None
    R = (FF.get(fid) or {}).get("raster"); fs = sorted(glob.glob(os.path.join(ffn, f"ortho_{fid}_einzeln", "*.png")))
    if not R or len(fs) < min_fotos: return None
    c = float(R["zelle"]); k = max(1, int(round(zelle / c))); n = None; g_ = None
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
        n = sicht.astype(np.int32) if n is None else n + sicht; g_ = gl.astype(np.int32) if g_ is None else g_ + gl
    if n is None: return None
    putz = (n >= min_fotos) & (g_ >= anteil * np.maximum(n, 1))
    erg = dict(putz=putz, n=n, u0=float(R["u0"]), z1=float(R["z1"]), zelle=c * k, fotos=len(fs)); _CACHE[key] = erg; return erg


def putz_auf_relief(Z, ffn, parallel=0.95, abstand=1.0, **kw):
    """Putzkarte der passenden Fassade (Normale parallel, Ebene < abstand m) auf das Relief-Raster Z (dict/npz mit a, t, n, u0, z0, px, rel) legen.
    Zellen ohne Fassadenbild = False (kein Putz-Beleg). None, wenn keine Fassade passt."""
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
    P = K["putz"]; okj = (j >= 0) & (j < P.shape[1]); oki = (i >= 0) & (i < P.shape[0])
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


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("fein"); ap.add_argument("--aus"); a = ap.parse_args()
    Z = np.load(a.relief); M = putz_auf_relief(Z, a.fein)
    if M is None: print("keine passende Fassade / keine Einzelbilder"); return 3
    aus = a.aus or a.relief.replace("_voll.npz", "_glatt.npz"); print(relief_putz_glatt(a.relief, aus, M), "->", aus); return 0


if __name__ == "__main__":
    sys.exit(main())
