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
        t = np.abs(g - gaussian_filter(g, hochpass / c, truncate=3.0)) / (gaussian_filter(g, ort / c, truncate=3.0) + 10.0) * 100.0
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


def relief_putz_glatt(f_in, f_out, putz, frei=(), kruemel_m2=0.15, band=0.05, koerper_m2=0.25):
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
    lab2, k2 = ndi.label(m & (np.abs(rel - L) >= band)); n_koerper = 0
    for k_, sl in enumerate(ndi.find_objects(lab2), 1):
        if sl is None: continue
        cc = lab2[sl] == k_
        if cc.sum() * px * px >= koerper_m2 and cc.mean() >= 0.5: p[sl] &= ~cc; n_koerper += 1
    loch = Z["loch"] if "loch" in Z else np.zeros_like(m)                 # Netzloch (relief_roh: konstant 'vorstand') = Wandflaeche ohne Messung -> Niveau, keine Woelbung aufpraegen
    neu = np.where(m, rel - L + niv, rel); neu[(p | fr | loch) & m] = niv; neu = neu.astype(np.float32)
    Z["rel"] = neu; Z["putz_niveau_m"] = niv; Z["putz_wandbild"] = p; np.savez_compressed(f_out, **Z)
    try:
        from PIL import Image
        lx = np.gradient(neu, px, axis=1); lz = np.gradient(neu, px, axis=0); g_ = (np.clip(0.7 - 0.5 * lx + 0.7 * lz, 0, 1) * 255).astype(np.uint8); im_ = np.stack([g_] * 3, -1)
        im_[p] = (im_[p] * 0.7 + np.array([0, 0, 70])).astype(np.uint8); im_[fr & m] = (im_[fr & m] * 0.6 + np.array([90, 70, 0])).astype(np.uint8); im_[~wand] = (90, 90, 90); im_[oe] = (0, 60, 120)
        Image.fromarray(np.repeat(np.repeat(im_, 3, 0), 3, 1)).save(f_out[:-4] + ".jpg", quality=88)     # blaustichig = Putz (Wandbild), gelbstichig = frei (Uhr), dunkelblau = Oeffnung
    except Exception: pass
    vorher = float(np.std(rel[p] - L[p])) if p.any() else 0.0
    return dict(putz_anteil=round(float(p.sum() / max(m.sum(), 1)), 3), putz_niveau_m=round(niv, 3), rausch_vorher_cm=round(vorher * 100, 1), frei=len(frei), koerper_behalten=n_koerper)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("fein"); ap.add_argument("--aus"); a = ap.parse_args()
    Z = np.load(a.relief); M = putz_auf_relief(Z, a.fein)
    if M is None: print("keine passende Fassade / keine Einzelbilder"); return 3
    aus = a.aus or a.relief.replace("_voll.npz", "_glatt.npz"); print(relief_putz_glatt(a.relief, aus, M), "->", aus); return 0


if __name__ == "__main__":
    sys.exit(main())
