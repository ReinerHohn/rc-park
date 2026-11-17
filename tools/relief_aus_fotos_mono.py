#!/usr/bin/env python3
"""relief_aus_fotos_mono.py <relief.npz> <objekt.json> <aus.npz> --feld u0 u1 z0 z1 --stl <stl> [--n 5] [--px 0.02] [--trenn 0.25] [--massstab k x y z]

VERSUCH 17.11.2026 (Nutzerbefund Druck Steinplatte Tor Sued: "Mitte rechts Brei statt Fugen, Bogen ohne Bogensteine").
Relief (Steinwoelbung, Fugen) aus EINZELNEN scharfen Fotos per monokularer Tiefenschaetzung, generisch fuer jede Wand mit Kameras.
KERNMETHODE bleibt: Lage, Ebene, Massstab und Kanten der Wand kommen aus Kameras/Fotokanten und dem Generator; das Modell liefert NUR die Feinform vor der Ebene.
  1. Raster 1 cm auf der Wandebene DES RELIEFS (a, t, n, ebene_abstand_m, trend_je_m wie tools/steine_aus_foto.py --foto), optional --massstab (Relief im Rohrahmen).
  2. Fotos automatisch: Abdeckung^2 / (m je Pixel), Verdeckung gegen das Modell-STL (fassade_ein_foto.sichtbar, GPU-Raster); die n besten mit <= --max_mpp,
     das naechste Foto von ANDEREM Standort wird HOLDOUT (nur fuer den Fugenabgleich, nie im Relief).
  3. Je Foto entzerrtes 1-cm-Wandbild -> Depth Anything V2 SMALL (Apache-2.0, Gewichte /media/oem/scan/hf_depth) in einem Durchlauf auf dem ganzen Feld
     (relative Disparitaet; Wand frontal -> affin zur Hoehe vor der Wand).
  4. Massstab je Foto: Bandpass (3-25 cm) des Modells gegen denselben Bandpass des Scan-Reliefs, nur wo das Scan-Relief echt ist (nicht generiert/Putz).
     Korrelation je Foto wird ausgegeben - sie zeigt, ob das Modell dieselben Steine sieht wie der Scan.
  5. Fotos mitteln: Median der skalierten Hochpass-Anteile (< --trenn) ueber die Fotos (Verdecker/Passanten fallen heraus, wo >= 3 Fotos).
  6. Relief = Tiefpass des Scan-Reliefs (Lage, Woelbung > trenn) + Hochpass aus den Fotos. Putz bleibt Scan (eben), ohne Fotodaten bleibt Scan.
NACHTRAG 17.11.2026 abends (Integration Schwabentor, drei Fehlerbilder generisch behoben):
  - Entzerrung auf der FLAECHE des Eingangsreliefs statt der Ebene (--auf_relief 1): vorspringende Teile (Steintafel Sued) lagen je Foto an anderer Stelle -> Doppelstrich.
  - Drahtlinien je Foto (draht_linien: gerichteter Linienfilter + Hough + Duennheitsprobe), Maske geteilt fuer Fotos vom selben Standort (< 1 m), WEICH ausgeblendet;
    wo alle Fotos den Draht zeigen, steht die Feinform des Eingangsreliefs (Nord: Oberleitung + Isolator weg, dafuer ein Streifen Scan-Feinform).
  - Kachel-Normierung robust (MAD im Kachelinneren, +-5 gekappt, --kachel_norm) und Rand-Auslauf erst ab --rand_weg (8 cm) hinter der SICHTgrenze (nicht an Oeffnungen).
  Fugen-F1 Sued gegen Holdout 113836 (Zufall ~0,28): Feld 0,395 -> 0,417, Bogen 3,0-8,4/4,0-7,5: 0,42, Brei-Zone 0,41 (Scan 0,34/0,35/0,35).
NACHTRAG 17.11.2026 nachts (Agent Feinausrichtung):
  - --fein_ausrichten 1: die entzerrten Wandbilder werden VOR dem Tiefenmodell gegeneinander fein ausgerichtet (tools/wand_feinausrichtung.py; Holdout unberuehrt);
    danach EIN gemeinsamer Versatz zum Scan aus dem Mittel der Hochpaesse (--fa_versatz mittel), nicht mehr je Foto in ganzen cm (das brachte 1-2 cm Unterschied zurueck).
    Sued (5 Fotos, Holdout 113836): Restversatz 1,2-2,5 -> 0,2-0,5 cm (Phasenkorrelation unabhaengig 1,1-2,9 -> 0,2-0,5), Schaerfe Median-Wandbild +26 %,
    Fugen-F1 Feld 0,417 -> 0,431 (Bogen 0,421 -> 0,436, Brei-Zone 0,408 -> 0,417), Wiederholung bitgleich. Das unscharfe Foto 113939 bleibt unausgerichtet (2 % vertraut).
  - --anker_fein <tiefe_lokal.npz>: Massstab des Hochpasses je Kachel aus den Feinpunkten (Huber, Fit-/Pruefhaelfte, anker_fein). Sued: 52/107 Kacheln angenommen,
    a ~ 0,6-0,7 (Regressionsdaempfung, da Mono verrauscht); Scan-Massstab liegt in 69 % der Kacheln in der Spanne [a_lo, a_hi] -> Fugentiefe (Scan-Massstab) durch Feinpunkte
    BESTAETIGT, nicht genauer gemessen; F1 faellt leicht (0,431 -> 0,421). Darum nur als Gegenprobe, Standard aus.
aus.npz im Format der Relief-Einsaetze (rel, a, t, n, u0, z0, px, ebene_abstand_m, trend_je_m, putz_niveau_m, fein = Fotoanteil, putz), dazu
aus.jpg (Foto | Scan | neu, Schattierung) und aus.json (Zahlen, Fugenabgleich gegen das Holdout-Foto, Rechenzeit). Fugentiefe = Scan-Massstab (siehe 4), sonst ANNAHME.
Lizenz: nur Depth Anything V2 SMALL (Apache-2.0). DSINE (Imperial, nur Forschung) und Base/Large/Giant (NC) NICHT verwenden.
"""
import sys, os, json, time, glob, argparse, numpy as np, cv2
from scipy import ndimage as ndi

HIER = os.path.dirname(os.path.abspath(__file__))


def gauss_maske(x, m, s):
    """normierte Faltung: Mittel nur ueber gueltige Zellen"""
    a = ndi.gaussian_filter(np.where(m, x, 0.0), s); b = ndi.gaussian_filter(m.astype(np.float64), s); return a / np.maximum(b, 1e-6), b


def _da2_modell(gpu_mb):
    import torch
    os.environ.setdefault("HF_HUB_CACHE", "/media/oem/scan/hf_depth/hub"); os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from transformers import AutoModelForDepthEstimation
    global _MOD
    if "_MOD" not in globals():
        if torch.cuda.is_available(): torch.cuda.set_per_process_memory_fraction(min(0.95, gpu_mb / (torch.cuda.get_device_properties(0).total_memory / 2**20)))
        _MOD = AutoModelForDepthEstimation.from_pretrained("depth-anything/Depth-Anything-V2-Small-hf", dtype=torch.float16 if torch.cuda.is_available() else torch.float32).eval().to("cuda" if torch.cuda.is_available() else "cpu")
    return _MOD


def tiefe_kacheln(bild, m, kachel, s_hp, gpu_mb=3300, seite=518, norm="robust"):
    """Hochpass der relativen Disparitaet (gross = nah) aus Depth Anything V2 Small, KACHELWEISE (kachel Zellen, halbe Ueberlappung, Hann-Fenster).
    Gemessen 17.11.2026 Schwabentor Sued (1-cm-Wandbild): ganzes Feld in einem Durchlauf sieht nur Tor/Wand (Korrelation mit dem Scan-Bandpass 0,04);
    Kacheln 1,0/1,5/2,5/4,0 m: 0,23/0,24/0,23/0,11 (Foto 113851), 0,28/0,28/0,17/0,09 (Foto 113830). Je Kachel Hochpass (Gauss s_hp) und auf Streuung 1 normiert
    (die Disparitaet ist nur bis auf eine affine Abbildung je Kachel bestimmt); der Massstab kommt danach vom Scan."""
    import torch
    mod = _da2_modell(gpu_mb); dev = next(mod.parameters()).device; H, W = bild.shape[:2]; k = min(kachel, H, W); st = max(k // 2, 1)
    win = np.outer(np.hanning(k + 2)[1:-1], np.hanning(k + 2)[1:-1]); acc = np.zeros((H, W)); ws = np.zeros((H, W))
    ys = sorted(set(list(range(0, H - k + 1, st)) + [H - k])); xs = sorted(set(list(range(0, W - k + 1, st)) + [W - k]))
    for y0 in ys:
        for x0 in xs:
            mm = m[y0:y0 + k, x0:x0 + k]
            if mm.mean() < 0.3: continue
            x = cv2.resize(cv2.cvtColor(bild[y0:y0 + k, x0:x0 + k], cv2.COLOR_BGR2RGB), (seite, seite), interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
            x = (x - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
            with torch.no_grad(): d = mod(pixel_values=torch.from_numpy(x.transpose(2, 0, 1)[None].copy()).to(dev, next(mod.parameters()).dtype)).predicted_depth[0].float().cpu().numpy()
            d = cv2.resize(d, (k, k), interpolation=cv2.INTER_CUBIC).astype(np.float64); hp = d - gauss_maske(d, mm, s_hp)[0]
            # 17.11.2026 (Keilsteine Bogen Sued schwach): Streuung NUR im Kachelinneren und robust (MAD) - der Rand zur Toroeffnung/Sichtgrenze (gefuellte Flaeche)
            # gibt im Modell einen starken Saum; mit std ueber die ganze Kachel drueckte er die Steine aller Kacheln am Tor; Saum auf +-5 Streuungen gekappt
            if norm == "std": acc[y0:y0 + k, x0:x0 + k] += win * hp / (hp[mm].std() + 1e-9)
            else:
                mi = ndi.binary_erosion(mm, np.ones((21, 21))); mi = mi if mi.sum() > 0.2 * mm.sum() else mm
                sk = 1.4826 * float(np.median(np.abs(hp[mi] - np.median(hp[mi])))) + 1e-9; acc[y0:y0 + k, x0:x0 + k] += win * np.clip(hp / sk, -5.0, 5.0)
            ws[y0:y0 + k, x0:x0 + k] += win
    if dev.type == "cuda": torch.cuda.empty_cache()
    return acc / np.maximum(ws, 1e-6), ws


def taeler(r, s_cm):
    """Fugen-/Taelerkarte eines Hoehenbilds (1 cm): Black-Top-Hat mit Scheibe s_cm"""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (s_cm, s_cm)); return cv2.morphologyEx(r.astype(np.float32), cv2.MORPH_BLACKHAT, k)


def linienkarte(g, polaritaet, s_cm=9):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (s_cm, s_cm)); g = cv2.GaussianBlur(g.astype(np.float32), (0, 0), 1.0)
    return cv2.morphologyEx(g, cv2.MORPH_BLACKHAT if polaritaet == "dunkel" else cv2.MORPH_TOPHAT, k)


def draht_linien(b, m, c, min_len=1.0, breite=0.08, winkel=4.0, dick=0.05, lk=0.6, k=3.0, quote=0.6):
    """Maske duenner, langer, GERADER dunkler Linien im entzerrten Wandbild (Oberleitung, Kabel, Abspannseil) - je Foto, generisch.
    17.11.2026: die Graustufen-Oeffnung des Hochpasses (--draht) nimmt nur erhabene Grate < 5 cm; das Tiefenmodell liest einen Draht vor der Wand aber oft als
    Rille + Grat (Nord oben rechts: Oberleitung mit Isolator, Sued: Spanndraht ueber dem Bogen). Ablauf: Black-Top-Hat (dunkle Linie < dick) -> GERICHTETER
    Linienfilter (Mittel ueber lk m je Richtung, 2-Grad-Schritte; Steintextur mittelt sich weg, ein Draht nicht) -> Hough (>= min_len, Luecken <= 30 cm) ->
    je Strecke Probe: >= quote der Punkte ueber Schwelle UND quer +-5 cm deutlich schwaecher (duenn). Lagerfugen (waagerecht +-winkel Grad) ausgenommen,
    Stossfugen sind zu kurz. Gemessen Sued 113830/113851: Spanndraehte ueber dem Bogen gefunden, Bild-/Sichtrand nicht (Rand 5 cm weg). Maske = Linie +-breite."""
    g = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32); kd = int(round(dick / c)) | 1
    r = cv2.morphologyEx(cv2.GaussianBlur(g, (0, 0), 0.8), cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kd + 2, kd + 2))); r[~m] = 0
    me = ndi.binary_erosion(m, np.ones((11, 11))); mm = ndi.binary_erosion(m, np.ones((31, 31)))
    if mm.sum() < 5000: return np.zeros(m.shape, bool), []
    Lk = int(round(lk / c)) | 1; h = Lk // 2; R = np.zeros_like(r)
    for w in np.arange(0.0, 180.0, 2.0):
        if min(w, 180.0 - w) < winkel: continue
        kk = np.zeros((Lk, Lk), np.float32); d = np.array([np.cos(np.radians(w)), np.sin(np.radians(w))])
        cv2.line(kk, (int(h - h * d[0]), int(h - h * d[1])), (int(h + h * d[0]), int(h + h * d[1])), 1, 1); R = np.maximum(R, cv2.filter2D(r, -1, kk / kk.sum()))
    med = float(np.median(R[mm])); mad = 1.4826 * float(np.median(np.abs(R[mm] - med))) + 1e-6; th = med + k * mad
    bw = ((R > th) & me).astype(np.uint8) * 255; L = int(round(min_len / c))
    seg = cv2.HoughLinesP(bw, 1, np.pi / 360, threshold=int(0.25 * L), minLineLength=L, maxLineGap=int(round(0.3 / c)))
    aus = np.zeros(m.shape, np.uint8); gut = []; ve = int(round(0.30 / c)); o = 0.05 / c
    def probe(xs, ys, dx, dy): return R[np.clip(np.round(ys + dy).astype(int), 0, R.shape[0] - 1), np.clip(np.round(xs + dx).astype(int), 0, R.shape[1] - 1)]
    for x0, y0, x1, y1 in ([] if seg is None else seg.reshape(-1, 4)):
        w_ = np.degrees(np.arctan2(y1 - y0, x1 - x0)) % 180.0
        if min(w_, 180.0 - w_) < winkel: continue                          # waagerecht = Lagerfuge
        d_ = np.array([x1 - x0, y1 - y0], float); d_ /= max(np.linalg.norm(d_), 1e-9); nv_ = np.array([-d_[1], d_[0]])
        tt = np.linspace(0, 1, max(int(np.hypot(x1 - x0, y1 - y0)), 2)); xs = x0 + tt * (x1 - x0); ys = y0 + tt * (y1 - y0)
        mitte = np.max([probe(xs, ys, nv_[0] * e, nv_[1] * e) for e in (-1, 0, 1)], 0); seite = np.maximum(probe(xs, ys, nv_[0] * o, nv_[1] * o), probe(xs, ys, -nv_[0] * o, -nv_[1] * o))
        if (mitte > th).mean() < quote or np.median(mitte - seite) < 2.0 * mad: continue
        p0 = (int(x0 - ve * d_[0]), int(y0 - ve * d_[1])); p1 = (int(x1 + ve * d_[0]), int(y1 + ve * d_[1]))
        cv2.line(aus, p0, p1, 1, 2 * int(round(breite / c)) + 1); gut.append([int(x0), int(y0), int(x1), int(y1)])
    return aus.astype(bool) & m, gut


def fugen_abgleich(r_rel, r_foto, m, anteil=0.12, tol=2, schub=(13, 9)):
    """Anteil der staerksten 'anteil' Relief-Taeler, die <= tol cm neben den staerksten Foto-Linien (Holdout) liegen, und umgekehrt; F1. Zufall: Relief um 'schub' cm verschoben."""
    def oben(x): th = np.quantile(x[m], 1 - anteil); return (x >= th) & m
    a = oben(r_foto); dt_a = ndi.distance_transform_edt(~a)
    def f1(b):
        if b.sum() == 0: return 0.0, 0.0, 0.0
        p = float((dt_a[b] <= tol).mean()); dt_b = ndi.distance_transform_edt(~b); r = float((dt_b[a] <= tol).mean()); return p, r, 2 * p * r / max(p + r, 1e-9)
    b = oben(r_rel); bs = np.roll(np.roll(b, schub[0], 1), schub[1], 0) & m
    return dict(praezision=f1(b)[0], trefferquote=f1(b)[1], f1=f1(b)[2], f1_zufall=f1(bs)[2])


def huber_affin(x, y, k=1.345, it=8):
    """robuste Gerade y ~ a x + b (Huber-IRLS, Skala MAD)"""
    w = np.ones_like(x)
    for _ in range(it):
        X = np.stack([x, np.ones_like(x)], 1) * np.sqrt(w)[:, None]; ab = np.linalg.lstsq(X, y * np.sqrt(w), rcond=None)[0]; r = y - ab[0] * x - ab[1]
        sk = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-9; u = np.abs(r) / (k * sk); w = np.where(u <= 1, 1.0, 1.0 / np.maximum(u, 1e-9))
    return float(ab[0]), float(ab[1])


def fein_auf_raster(Zf, U, ZZ, X, Y, c):
    """Feinpunkt-Hoehenbild (tiefe_lokal.py, Relief-Format) auf das Raster: Hoehe der Feinflaeche ueber der Ebene des Rasters (Weltpunkt X/Y der Ebene,
    entlang der Feinnormalen). Rueckgabe (hoehe, gueltig). Allgemeiner Rahmen (a, t, n, Ebene, Trend der Feindatei duerfen anders sein)."""
    rf = Zf["rel"].astype(np.float64); Hf = rf.shape[0]; pf = float(Zf["px"]); Af = Zf["a"]; tf = Zf["t"]; nf = Zf["n"]; u0f = float(Zf["u0"]); z0f = float(Zf["z0"]); tuf, tzf = [float(v) for v in Zf["trend_je_m"]]
    uf = (X - Af[0]) * tf[0] + (Y - Af[1]) * tf[1]; sf = (X - Af[0]) * nf[0] + (Y - Af[1]) * nf[1]
    gm = (np.abs(rf) > 1e-6) & np.isfinite(rf)
    if "oeffnung" in Zf: gm &= ~(Zf["oeffnung"] > 0.5)
    mx = ((uf - u0f) / pf - 0.5).astype(np.float32); my = (Hf - (ZZ - z0f) / pf - 0.5).astype(np.float32)
    r_ = cv2.remap(np.nan_to_num(rf).astype(np.float32), mx, my, cv2.INTER_NEAREST, borderValue=0).astype(np.float64)
    g_ = cv2.remap(gm.astype(np.uint8), mx, my, cv2.INTER_NEAREST, borderValue=0) > 0
    ebf = float(Zf["ebene_abstand_m"]) + tuf * (uf - u0f) - tzf * ((z0f + Hf * pf) - ZZ)
    return np.where(g_, ebf + r_ - sf, 0.0), g_


def anker_fein(hp, fein, gf, m, c, kachel_m=1.5, s_tr=24.0, min_n=1500, block_m=0.10, min_gewinn=0.02):
    """Massstab des Mono-Hochpasses JE KACHEL aus den Feinpunkten (gemessen) statt aus dem Scan-Bandpass (Schritt B2 der Recherche 17.11.).
    Band 2 Zellen .. s_tr beider Seiten; Huber-Gerade fein ~ a * hp + b auf der FIT-Haelfte (Schachbrett aus block_m-Bloecken), Pruefung auf der anderen Haelfte:
    angenommen nur, wenn der Pruefrest (MAD) mit a um >= min_gewinn (relativ) kleiner ist als mit a = 1 (Scan-Massstab). a auf [0, 3] begrenzt (a ~ 0 = Feinpunkte
    sehen dort KEIN Relief -> Mono-Erfindung wird gedaempft, Nullkontrolle glatter Traeger). Rueckgabe (Faktorfeld, Bericht)."""
    H, W = hp.shape; k = int(round(kachel_m / c)); st = max(k // 2, 1); bk = max(int(round(block_m / c)), 1)
    def band(x, mm): return gauss_maske(x, mm, 2)[0] - gauss_maske(x, mm, s_tr)[0]
    def mad_(r): return 1.4826 * float(np.median(np.abs(r - np.median(r))))
    g = gf & m; bf = band(fein, gf); bh = band(np.nan_to_num(hp), m)
    jj, ii = np.meshgrid(np.arange(W), np.arange(H)); fit = ((jj // bk + ii // bk) % 2) == 0
    win = np.outer(np.hanning(k + 2)[1:-1], np.hanning(k + 2)[1:-1]); acc = np.zeros((H, W)); ws = np.zeros((H, W)); kach = []
    ys = sorted(set(list(range(0, max(H - k, 0) + 1, st)) + [max(H - k, 0)])); xs = sorted(set(list(range(0, max(W - k, 0) + 1, st)) + [max(W - k, 0)]))
    for y0 in ys:
        for x0 in xs:
            sl = (slice(y0, y0 + k), slice(x0, x0 + k)); gg = g[sl]; a_ = 1.0; e = dict(u_zelle=x0, z_zelle=y0, n=int(gg.sum()))
            if (gg & fit[sl]).sum() >= min_n and (gg & ~fit[sl]).sum() >= min_n:
                xf = bh[sl][gg & fit[sl]]; yf = bf[sl][gg & fit[sl]]; xp = bh[sl][gg & ~fit[sl]]; yp = bf[sl][gg & ~fit[sl]]
                af, bfit = huber_affin(xf, yf); af = float(np.clip(af, 0.0, 3.0)); b1 = float(np.median(yf - xf))
                cv_ = float(np.cov(xf, yf)[0, 1]); a_lo = cv_ / max(float(np.var(xf)), 1e-12); a_hi = float(np.var(yf)) / cv_ if cv_ > 0 else float('inf')   # Spanne: Rauschen in x daempft a_lo, Rauschen in y hebt a_hi
                rf_ = mad_(yp - af * xp - bfit); rs_ = mad_(yp - xp - b1); r0_ = mad_(yp)
                ok = rf_ < (1 - min_gewinn) * rs_; a_ = af if ok else 1.0
                e.update(a=round(af, 3), pruef_rest_fein_mm=round(rf_ * 1000, 2), pruef_rest_scan_mm=round(rs_ * 1000, 2), pruef_streuung_fein_mm=round(r0_ * 1000, 2),
                         korrelation_fit=round(float(np.corrcoef(xf, yf)[0, 1]), 3), a_spanne=[round(a_lo, 3), round(min(a_hi, 99.0), 3)], scan_in_spanne=bool(a_lo <= 1.0 <= a_hi), angenommen=bool(ok))
            kach.append(e); wv = win[:sl[0].stop - y0, :sl[1].stop - x0]; acc[sl] += wv * a_; ws[sl] += wv
    A = np.where(ws > 1e-6, acc / np.maximum(ws, 1e-6), 1.0)
    an = [e for e in kach if e.get("angenommen")]; geprueft = [e for e in kach if "a" in e]
    ber = dict(kacheln=len(kach), geprueft=len(geprueft), angenommen=len(an), a_median_angenommen=float(np.median([e["a"] for e in an])) if an else None,
               pruef_rest_fein_mm_median=float(np.median([e["pruef_rest_fein_mm"] for e in geprueft])) if geprueft else None,
               pruef_rest_scan_mm_median=float(np.median([e["pruef_rest_scan_mm"] for e in geprueft])) if geprueft else None,
               scan_massstab_in_spanne=round(float(np.mean([e["scan_in_spanne"] for e in geprueft])), 3) if geprueft else None, kachel_liste=kach)
    return A, ber


def schatten(r, px, zmax=None):
    gy, gx = np.gradient(r, px); l = np.array([-1.0, 1.0, 1.2]); l /= np.linalg.norm(l); nn = np.sqrt(gx ** 2 + gy ** 2 + 1)
    s = (-gx * l[0] + gy * l[1] + l[2]) / nn; return np.clip((s - 0.3) / 0.7 * 255, 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("relief"); ap.add_argument("objekt"); ap.add_argument("aus")
    ap.add_argument("--feld", nargs=4, type=float, required=True); ap.add_argument("--stl", required=True); ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--fotos", default="auto", help="auto oder Liste name,name (dann --holdout angeben)"); ap.add_argument("--holdout", default=None)
    ap.add_argument("--px", type=float, default=0.02); ap.add_argument("--trenn", type=float, default=0.6, help="Trennwellenlaenge m: darueber Scan, darunter Fotos")
    ap.add_argument("--max_mpp", type=float, default=0.025); ap.add_argument("--massstab", nargs=4, type=float); ap.add_argument("--polaritaet", default="dunkel", choices=["dunkel", "hell"])
    ap.add_argument("--zone", nargs=4, type=float, action="append", default=[], help="Pruefzone u0 u1 z0 z1 (z. B. Brei-Zone) fuer den Fugenabgleich")
    ap.add_argument("--gpu_mb", type=int, default=3300); ap.add_argument("--min_korr", type=float, default=0.2); ap.add_argument("--kachel", type=float, default=1.5, help="Kachelkante m fuer das Tiefenmodell"); ap.add_argument("--abstand", type=float, default=0.5, help="Mindestabstand der Fotostandorte m"); ap.add_argument("--draht", type=float, default=0.05, help="duenne ERHABENE Linien schmaler als das (m) je Foto weg (Graustufen-Oeffnung): Oberleitungen, Kabel"); ap.add_argument("--auf_relief", type=int, default=1, help="1 = Fotos auf die Reliefflaeche entzerren (Parallaxe vorspringender Teile), 0 = auf die Ebene"); ap.add_argument("--kachel_norm", default="robust", choices=["robust", "std"], help="Streuung je Kachel: robust (MAD im Inneren, Saum gekappt) oder std (bis 17.11.)"); ap.add_argument("--rand_weg", type=float, default=0.08, help="Saum an der Sichtgrenze je Foto (m) ohne Gewicht"); ap.add_argument("--draht_laenge", type=float, default=1.0, help="gerade dunkle Linien (Draht/Kabel) ab dieser Laenge m je Foto ausblenden (draht_linien), 0 = aus")
    ap.add_argument("--ohne", nargs=4, type=float, action="append", default=[], help="Feld u0 u1 z0 z1 ohne Foto-Relief (Fremdkoerper: Verkehrsschild, Lampe) - dort bleibt der Scan"); ap.add_argument("--zwischen", default=None, help="Ordner fuer Zwischenbilder (Datenplatte)")
    ap.add_argument("--fein_ausrichten", type=int, default=1, help="1 (Standard seit 17.11.2026 nach Test Sued: F1 0,417 -> 0,431) = Wandbilder der Fotos vor dem Tiefenmodell gegeneinander fein ausrichten (wand_feinausrichtung.py), 0 = wie bis 17.11."); ap.add_argument("--fa_max", type=float, default=0.05, help="Feinausrichtung: max. Verschiebung m"); ap.add_argument("--fa_glatt", type=float, default=0.30, help="Feinausrichtung: Glaettung des Felds (Gauss-Sigma m)"); ap.add_argument("--fa_fenster", type=float, default=0.25, help="Feinausrichtung: NCC-Fenster m"); ap.add_argument("--fa_iter", type=int, default=3, help="Feinausrichtung: Runden des glatten Felds (0 = nur starr)"); ap.add_argument("--fa_global", type=float, default=0.15, help="Feinausrichtung: max. starrer Versatz je Foto m (0 = aus)"); ap.add_argument("--fa_versatz", default="mittel", choices=["mittel", "median"], help="Feinausrichtung: gemeinsamer Versatz zum Scan aus dem Mittel-Hochpass oder Median der Einzelversaetze")
    ap.add_argument("--anker_fein", default=None, help="Feinpunkt-Hoehenbild (tiefe_lokal.py, Relief-Format): Massstab des Hochpasses JE KACHEL daraus (anker_fein), sonst Scan")
    a = ap.parse_args()
    T0 = time.time(); sys.path.insert(0, HIER); import fassade_ein_foto as FE, render_kern as rk, trimesh, torch
    if torch.cuda.is_available(): torch.cuda.set_per_process_memory_fraction(min(0.95, a.gpu_mb / (torch.cuda.get_device_properties(0).total_memory / 2**20)))   # Budget gilt auch fuer das Sichtbarkeitsraster
    if os.path.exists(a.aus): print("Ziel existiert schon (nicht ueberschreiben):", a.aus); return 2
    Z = dict(np.load(a.relief)); rel = Z["rel"].astype(np.float64); H, W = rel.shape; rp = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); A = Z["a"]; t = Z["t"]; nv = Z["n"]
    tu, tz = [float(v) for v in Z["trend_je_m"]]; niv = float(Z.get("putz_niveau_m", 0.0))
    f0, f1, g0, g1 = a.feld; c = 0.01; nu = int(round((f1 - f0) / c)); nz = int(round((g1 - g0) / c)); jj, ii = np.meshgrid(np.arange(nu), np.arange(nz)); U = f0 + (jj + 0.5) * c; ZZ = g1 - (ii + 0.5) * c
    dpl = float(Z["ebene_abstand_m"]) + tu * (U - u0) - tz * ((z0 + H * rp) - ZZ)
    def gross(x, interp=cv2.INTER_LINEAR): return cv2.remap(x.astype(np.float32), ((U - u0) / rp - 0.5).astype(np.float32), (H - (ZZ - z0) / rp - 0.5).astype(np.float32), interp, borderMode=cv2.BORDER_REPLICATE).astype(np.float64)
    scan = gross(rel); putz = gross(Z["putz"]) > 0.5 if "putz" in Z else np.zeros(U.shape, bool); gen = gross(Z["generiert"]) > 0.5 if "generiert" in Z else np.zeros(U.shape, bool)
    # 17.11.2026 (Sued: senkrechter Doppelstrich rechts an der Steintafel): auf der EBENE entzerrt stand die vorspringende Tafel in jedem Foto an anderer Stelle (Parallaxe,
    # 113830/113849/113851: Kante 0,45 m auseinander) -> zwei Kanten im Mittel. Entzerrt wird jetzt auf der FLAECHE des Eingangsreliefs (Ebene + Scan-Relief, 5 cm geglaettet).
    hs = np.abs(scan) > 1e-6; dpl = dpl + (gauss_maske(scan, hs, 5)[0] * hs if a.auf_relief else 0.0)
    dpl0 = float(Z["ebene_abstand_m"]) + tu * (U - u0) - tz * ((z0 + H * rp) - ZZ); Xe = A[0] + U * t[0] + dpl0 * nv[0]; Ye = A[1] + U * t[1] + dpl0 * nv[1]   # Ebene im Reliefrahmen (fuer --anker_fein)
    X = A[0] + U * t[0] + dpl * nv[0]; Y = A[1] + U * t[1] + dpl * nv[1]; Zw = ZZ.copy()
    if a.massstab: k = a.massstab[0]; Mp = a.massstab[1:]; X = Mp[0] + k * (X - Mp[0]); Y = Mp[1] + k * (Y - Mp[1]); Zw = Mp[2] + k * (ZZ - Mp[2])
    P = np.stack([X, Y, Zw], -1).reshape(-1, 3)
    oeff = gross(Z["oeffnung"]) > 0.5 if "oeffnung" in Z else np.zeros(U.shape, bool)
    od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od)); obj = json.load(open(a.objekt)); mp = os.path.join(od, "messprotokoll")
    mm = trimesh.load(a.stl); mm.apply_scale(float(obj.get("stl_massstab", 87)) / 1000.0); T1 = time.time()
    def foto_pfad(n_): q = glob.glob(os.path.join(root, obj["fotos_dir"], n_ + ".*")); return q[0] if q else None
    G = P.reshape(U.shape + (3,))[::25, ::25].reshape(-1, 3); Pm = G.mean(0); kand = []
    for kf in glob.glob(os.path.join(mp, "K-*.json")):
        n_ = os.path.basename(kf)[2:-5]; K_ = FE.kamera(kf)
        if K_ is None or n_.startswith("video") or (n_.startswith(("dl_", "neu__")) and not K_.get("vertrauen")) or not foto_pfad(n_): continue
        R_ = cv2.Rodrigues(np.array(K_["rvec"]))[0]; C_ = -R_.T @ np.array(K_["t"]); v_ = C_ - Pm; di_ = np.linalg.norm(v_); cw_ = float(v_[:2] @ nv[:2] / di_)
        if cw_ >= 0.3 and di_ <= 250: kand.append((di_ / (K_["f_px"] * cw_), n_, K_, C_))
    kand.sort(key=lambda q: q[0]); rang = []
    for mpp_, n_, K_, C_ in kand[:24]:
        ok0 = FE.sichtbar(mm, K_, G, rk, tol=0.6)[0]; rang.append((float(ok0.mean()) ** 2 / max(mpp_, 0.005), n_, float(ok0.mean()), mpp_, K_, C_))
    rang.sort(key=lambda q: -q[0])
    if a.fotos == "auto":
        wahl = []                                                          # Standorte streuen (>= --abstand m): Draehte/Leitungen VOR der Wand wandern dann von Foto zu Foto und fallen im Median heraus
        for q in rang:                                                      # (17.11.: fuenf Fotos aus einer Serie am selben Standort -> Oberleitung als Relieflinie)
            if q[2] >= 0.3 and q[3] <= a.max_mpp and all(np.linalg.norm(q[5] - w[5]) >= a.abstand for w in wahl): wahl.append(q)
            if len(wahl) >= a.n: break
        rest = [q for q in rang if q not in wahl and q[2] >= 0.3 and q[3] <= 2 * a.max_mpp and all(np.linalg.norm(q[5] - w[5]) > 0.3 for w in wahl)]
        hold = rest[0] if rest else None
    else:
        nm = a.fotos.split(","); wahl = [q for q in rang if q[1] in nm]; hold = next((q for q in rang if q[1] == a.holdout), None)
    if len(wahl) < 1: print("kein brauchbares Foto (Abdeckung >= 30 %, <= max_mpp)"); return 3
    print("Fotos:", [(q[1][-26:], f"{q[2] * 100:.0f} %", f"{q[3] * 100:.1f} cm/px") for q in wahl]); print("Holdout:", (hold[1][-26:], f"{hold[3] * 100:.1f} cm/px") if hold else None)
    def entzerren(q):
        ok_, mx_, my_, zc_ = FE.sichtbar(mm, q[4], P, rk, tol=0.6); im = cv2.imread(foto_pfad(q[1]))
        b = cv2.remap(im, mx_.astype(np.float32).reshape(U.shape), my_.astype(np.float32).reshape(U.shape), cv2.INTER_AREA if False else cv2.INTER_LINEAR, borderValue=(0, 0, 0))
        ok_ = ok_.reshape(U.shape); return b, ok_, float(np.median(zc_[ok_.ravel()]) / q[4]["f_px"]) if ok_.any() else 9.0
    loch = ndi.binary_dilation(ndi.binary_opening(np.abs(scan) < 1e-6, np.ones((9, 9))), np.ones((9, 9)))     # Scan ohne Flaeche (Tor, Durchblick): nie Foto-Relief, vor dem Modell zugemalt
    oeff = oeff | loch
    echt = ~putz & ~gen & ~oeff & (np.abs(scan) > 1e-6)                    # Scan-Relief vorhanden und nicht generiert/Putz
    def band(x, m, s0, s1): return gauss_maske(x, m, s0)[0] - gauss_maske(x, m, s1)[0]
    s_tr = a.trenn / c / 2.5                                              # Gauss-Sigma der Trennung (Zellen)
    def mad(x): return 1.4826 * float(np.median(np.abs(x - np.median(x))))
    hp_liste = []; info = []; bilder = []; sicht_liste = []; draht_liste = []; standorte = []; vb_liste = []; vb_ok = []
    vor = []
    for q in wahl:
        b, ok_, mpp = entzerren(q); vor.append((b, ok_, mpp, ok_ & ~oeff & (b.max(2) > 8)))
    fa_ber = None
    if a.fein_ausrichten:                                                 # Feinausrichtung der Wandbilder gegeneinander (tools/wand_feinausrichtung.py), Holdout bleibt unberuehrt
        import wand_feinausrichtung as WF
        ix = [i for i, v in enumerate(vor) if v[3].sum() >= 5000]
        if len(ix) >= 3:
            nb, nm_, _, fa_ber = WF.fein_ausrichten([vor[i][0] for i in ix], [vor[i][3] for i in ix], c, max_m=a.fa_max, glatt_m=a.fa_glatt, fenster_m=a.fa_fenster, iter=a.fa_iter, global_m=a.fa_global, gpu_mb=a.gpu_mb)
            zon = [("feld", None), ("echt", echt)] + [(f"zone{i}", (U >= z_[0]) & (U <= z_[1]) & (ZZ >= z_[2]) & (ZZ <= z_[3])) for i, z_ in enumerate(a.zone)]
            fa_ber["schaerfe_median_wandbild"] = {}
            for zn, zm in zon:
                s0, med0 = WF.schaerfe([vor[i][0] for i in ix], [vor[i][3] for i in ix], zm); s1, med1 = WF.schaerfe(nb, nm_, zm); fa_ber["schaerfe_median_wandbild"][zn] = [s0, s1]
            print("  Schaerfe Median-Wandbild (Gradientenenergie) vorher -> nachher: " + ", ".join(f"{k_} {v_[0]:.0f}->{v_[1]:.0f}" for k_, v_ in fa_ber["schaerfe_median_wandbild"].items() if v_[0]), flush=True)
            if a.zwischen:
                os.makedirs(a.zwischen, exist_ok=True); cv2.imwrite(os.path.join(a.zwischen, "median_vorher.png"), np.clip(med0, 0, 255).astype(np.uint8)); cv2.imwrite(os.path.join(a.zwischen, "median_nachher.png"), np.clip(med1, 0, 255).astype(np.uint8))
            for j, i in enumerate(ix): vor[i] = (nb[j], vor[i][1], vor[i][2], nm_[j] & ~oeff)
    for q, (b, ok_, mpp, m) in zip(wahl, vor):
        tq = time.time()
        if m.sum() < 5000: info.append(dict(foto=q[1], verworfen="zu wenig sichtbar")); continue
        fuell = b.copy(); fuell[~m] = cv2.inpaint(b, (~m).astype(np.uint8), 15, cv2.INPAINT_TELEA)[~m]
        hp, ws = tiefe_kacheln(fuell, m, int(round(a.kachel / c)), s_tr, a.gpu_mb, norm=a.kachel_norm); m &= ws > 0.05
        dm, dseg = draht_linien(b, m, c, min_len=a.draht_laenge) if a.draht_laenge > 0 else (np.zeros(m.shape, bool), [])
        m &= ~dm                                                          # Drahtlinien dieses Fotos: kein Foto-Relief (andere Fotos oder Luecken-Fuellung uebernehmen)
        bm = band(hp, m, 2, s_tr); bs = band(scan, m & echt, 2, s_tr); mk = m & echt & ndi.binary_erosion(m, np.ones((15, 15)))
        x = bm[mk]; y = bs[mk]; r = float(np.corrcoef(x, y)[0, 1]) if mk.sum() > 100 else 0.0
        kq = mad(y) / max(mad(x), 1e-12) * (1.0 if r >= 0 else -1.0)      # Massstab = gleiche Streuung im Band wie der Scan (Regression wuerde bei r ~ 0,3 auf ein Drittel daempfen)
        vs = []                                                         # Versatz Foto <-> Scan (nur Bericht): beste Verschiebung im Band, +-12 cm
        for dy in range(-12, 13, 2):
            for dx in range(-12, 13, 2):
                xs_ = np.roll(np.roll(bm, dy, 0), dx, 1)[mk]; vs.append((float(np.corrcoef(xs_, y)[0, 1]), dy, dx))
        vb = max(vs)
        for dy in range(vb[1] - 1, vb[1] + 2):                           # fein (1 cm) um den besten Versatz
            for dx in range(vb[2] - 1, vb[2] + 2): vb = max(vb, (float(np.corrcoef(np.roll(np.roll(bm, dy, 0), dx, 1)[mk], y)[0, 1]), dy, dx))
        # LAGE kommt vom Scan (Geometrie), nicht vom Tiefenmodell: gemessen 17.11. sitzen die Modell-Taeler 4-6 cm UNTER den Scan-Fugen (Schattenfuge unter dem Stein
        # wird als Vertiefung gelesen; Holdout-Fotolinien liegen auf dem Scan, Versatz 0). Darum Hochpass um den besten Versatz zurueckschieben (Grenze +-12 cm).
        if a.draht > 0:                                                   # Oberleitung/Kabel vor der Wand: das Modell liest sie als schmale erhabene Grate (17.11. Sued/Nord); Steinkuppen sind breiter
            kd = int(round(a.draht / c)) | 1; hp = np.minimum(hp, cv2.morphologyEx(hp.astype(np.float32), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kd, kd))).astype(np.float64))
        # Mit Feinausrichtung liegen die Fotos schon deckungsgleich: der Versatz zum Scan wird danach EINMAL gemeinsam (Median) angewandt - je Foto in ganzen cm
        # gerollt kamen 1-2 cm Unterschied zwischen den Fotos zurueck (17.11.2026: F1 0,417 -> 0,400 trotz Restversatz 0,2-0,5 cm)
        ry, rx = (0, 0) if fa_ber is not None else (vb[1], vb[2]); vb_liste.append((vb[1], vb[2]))
        hp = np.roll(np.roll(kq * hp, ry, 0), rx, 1); m = np.roll(np.roll(m, ry, 0), rx, 1); hp[~m] = np.nan; dm = np.roll(np.roll(dm, ry, 0), rx, 1)
        info.append(dict(foto=q[1], cm_je_px=round(mpp * 100, 2), sichtbar=round(float(ok_.mean()), 3), massstab=kq, korrelation_band_scan=round(r, 3),
                         bester_versatz_cm=dict(nach_unten=vb[1], nach_rechts=vb[2], korrelation=round(vb[0], 3)), draht_linien=len(dseg), draht_anteil=round(float(dm.mean()), 4), sekunden=round(time.time() - tq, 1)))
        print(f"  {q[1][-30:]}: {mpp * 100:.1f} cm/px, sichtbar {ok_.mean() * 100:.0f} %, Korrelation mit Scan (2-{a.trenn * 100:.0f} cm) {r:+.2f} "
              f"(verschoben {vb[1]:+d}/{vb[2]:+d} cm: {vb[0]:+.2f}), Massstab {kq:.4g}, {time.time() - tq:.0f} s", flush=True)
        if r < a.min_korr: info[-1]["verworfen"] = "keine Korrelation mit dem Scan (Modell sieht andere Form)"; continue
        vb_ok.append(vb_liste[-1]); hp_liste.append(hp); bilder.append(b); sicht_liste.append(m | dm); draht_liste.append(dm); standorte.append(np.asarray(q[5], float)); draht_u = dm if not hp_liste[:-1] else (draht_u | dm)
        if a.zwischen:
            os.makedirs(a.zwischen, exist_ok=True); bd = b.copy()
            for x0, y0, x1, y1 in dseg: cv2.line(bd, (x0, y0), (x1, y1), (0, 0, 255), 3)
            cv2.imwrite(os.path.join(a.zwischen, q[1][-40:] + "_wand.jpg"), bd); np.save(os.path.join(a.zwischen, q[1][-40:] + "_hp.npy"), hp.astype(np.float32))
    if fa_ber is not None and hp_liste:
        # gemeinsamer Versatz zum Scan aus dem MITTEL der (deckungsgleichen) Hochpaesse - ein Schaetzer statt Median der Einzelschaetzer (17.11.: Median -6/+1 cm gab F1 0,397)
        with np.errstate(all="ignore"): Sm = np.nanmean(np.stack(hp_liste), 0)
        mf = np.isfinite(Sm); bm_ = band(np.nan_to_num(Sm), mf, 2, s_tr); bs_ = band(scan, mf & echt, 2, s_tr); mk_ = mf & echt & ndi.binary_erosion(mf, np.ones((15, 15))); y_ = bs_[mk_]
        def kor(dy, dx): return float(np.corrcoef(np.roll(np.roll(bm_, dy, 0), dx, 1)[mk_], y_)[0, 1])
        vg = max((kor(dy, dx), dy, dx) for dy in range(-12, 13, 2) for dx in range(-12, 13, 2)); vg = max([vg] + [(kor(dy, dx), dy, dx) for dy in range(vg[1] - 1, vg[1] + 2) for dx in range(vg[2] - 1, vg[2] + 2)])
        ry, rx = (vg[1], vg[2]) if a.fa_versatz == "mittel" else (int(np.median([v[0] for v in vb_ok])), int(np.median([v[1] for v in vb_ok])))
        fa_ber["gemeinsamer_versatz_scan_cm"] = [ry, rx]; fa_ber["versatz_mittel_cm"] = [vg[1], vg[2], round(vg[0], 3)]; fa_ber["versatz_median_einzeln_cm"] = [int(np.median([v[0] for v in vb_ok])), int(np.median([v[1] for v in vb_ok]))]
        print(f"  gemeinsamer Versatz zum Scan ({a.fa_versatz}): {ry:+d}/{rx:+d} cm (Mittel-Hochpass {vg[1]:+d}/{vg[2]:+d} r {vg[0]:.2f}, Median einzeln {fa_ber['versatz_median_einzeln_cm']})", flush=True)
        def _r(x): return np.roll(np.roll(x, ry, 0), rx, 1)
        hp_liste = [_r(h_) for h_ in hp_liste]; sicht_liste = [_r(x) for x in sicht_liste]; draht_liste = [_r(x) for x in draht_liste]
    if not hp_liste: print("kein Foto mit Korrelation zum Scan - nichts erzeugt"); json.dump(dict(fotos=info), open(a.aus.replace(".npz", ".json"), "w"), indent=1); return 4
    # Fotos vereinen: gewichtetes Mittel mit (a) Rand-Auslauf je Foto (20 cm ab Sichtgrenze - sonst Naehte, wo ein Foto endet: Nord 17.11. harte Linien) und
    # (b) Kappung auf Median +- 1,5 Streuungen (ein Draht/Passant in EINEM Foto zieht das Mittel nicht mit). Ein Foto allein = sein Wert.
    # Draehte vom selben Standort (< 1 m) liegen im Wandbild an derselben Stelle: Drahtmaske eines Fotos gilt fuer alle Fotos dieses Standorts
    # (17.11.2026 Nord: Serie 113602-113610, Isolator oben rechts nur in 113608 erkannt - im Mittel der anderen blieb er stehen)
    draht_liste = [np.any([d_ for d_, c_ in zip(draht_liste, standorte) if np.linalg.norm(c_ - ci) < 1.0], 0) for ci in standorte]
    for h_, d_ in zip(hp_liste, draht_liste): h_[d_] = np.nan
    draht_u = np.any(draht_liste, 0)
    S = np.stack(hp_liste); fin = np.isfinite(S); nfoto = fin.sum(0); S0 = np.where(fin, S, 0.0)
    with np.errstate(all="ignore"): med = np.nan_to_num(np.nanmedian(np.where(fin, S, np.nan), 0))
    # Rand-Auslauf ab der SICHTgrenze des Fotos (nicht ab Oeffnungen - dort enden alle Fotos, der Saum ist fuer alle gleich); die ersten --rand_weg m ganz ohne Gewicht:
    # 17.11.2026 Sued, senkrechter Strich rechts der Steintafel = Sichtgrenze von Foto 113849 (gefuellte Flaeche jenseits der Grenze -> Saum im Tiefenmodell)
    # Drahtstreifen sind KEINE Sichtgrenze (sonst Rampen = Doppellinien neben dem Draht, Nord 17.11.): Gewicht aus der Sicht ohne Drahtmaske, Drahtzellen nur ohne Wert
    tau = 1.5 * mad((S - med)[fin]); Wr = np.stack([np.clip((ndi.distance_transform_edt(f_ | oeff) * c - a.rand_weg) / 0.20, 0, 1) for f_ in sicht_liste])
    # Drahtstreifen WEICH ausblenden (Rampe ~10 cm): hart ausgeschnitten gab der Wechsel der Fotomenge an den Streifenkanten Doppellinien (Sued 17.11., s_std gegen s_std_ohnedraht)
    Wg = Wr * fin * np.stack([1.0 - np.clip(ndi.gaussian_filter(d_.astype(np.float64), 4.0) * 2.0 + d_, 0, 1) for d_ in draht_liste])
    hpm = (Wg * np.clip(S0, med - tau, med + tau)).sum(0) / np.maximum(Wg.sum(0), 1e-6); sicht = np.any(sicht_liste, 0); hpm = np.where(nfoto > 0, hpm, 0.0)
    # Drahtstreifen, die in KEINEM Foto frei sind (Fotoserie vom selben Standort: Draht liegt ueberall gleich): dort KEIN Foto-Relief, sondern die Feinform des
    # Eingangsreliefs (das Netz kennt keinen Draht) - weich ueber das Gewicht wsum. Sackgassen 17.11. Nord: Telea-Fuellung des Hochpasses nur im Streifen gab eine Rinne
    # (Saum des Drahts am Rand), Telea ueber alle Zellen mit > 50 % Gewichtsverlust zog den Isolator-Umriss wieder hinein. Rest: ein Band Feinform (rauer) quer ueber die Steine.
    lp_scan = gauss_maske(scan, ~oeff, s_tr)[0]
    anker = None
    if a.anker_fein:                                                      # Massstab je Kachel aus Feinpunkten (gemessen) statt Scan-Bandpass, mit Fit-/Pruefhaelfte
        fh, fg = fein_auf_raster(dict(np.load(a.anker_fein)), U, ZZ, Xe, Ye, c); Af_, anker = anker_fein(hpm, fh, fg & ~putz & ~oeff, (nfoto > 0) & ~putz & ~oeff, c, a.kachel, s_tr)
        anker["feinpunkte_anteil_feld"] = round(float(fg.mean()), 3); hpm = hpm * Af_
        anker["gemessen_anteil_fotoflaeche"] = round(float((np.abs(Af_ - 1) > 1e-3)[nfoto > 0].mean()), 3)
        print(f"Anker Feinpunkte: {anker['angenommen']}/{anker['geprueft']} Kacheln angenommen (a Median {anker['a_median_angenommen']}), Pruefrest Median fein {anker['pruef_rest_fein_mm_median']} mm / Scan {anker['pruef_rest_scan_mm_median']} mm; Scan-Massstab in der Spanne [a_lo, a_hi] in {anker['scan_massstab_in_spanne']:.0%} der Kacheln", flush=True)
    for q0, q1, r0, r1 in a.ohne: oeff = oeff | ((U >= q0) & (U <= q1) & (ZZ >= r0) & (ZZ <= r1))
    foto_da = sicht & ~putz & ~oeff
    wsum = np.clip(Wg.sum(0), 0, 1)      # wo kein Foto Gewicht hat (Saum an allen Sichtgrenzen, Draht in allen Fotos): Feinform des Eingangsreliefs statt glatt
    neu = np.where(foto_da, lp_scan + wsum * hpm + (1 - wsum) * (scan - lp_scan), scan); neu = np.where(putz, scan, neu)
    # Rand der Fotodaten weich in den Scan ueberfuehren (5 cm)
    w = ndi.gaussian_filter(foto_da.astype(np.float64), 3) * foto_da; neu = w * neu + (1 - w) * scan
    neu = np.clip(neu, float(np.quantile(scan, 0.001)) - 0.03, float(np.quantile(scan, 0.999)) + 0.03)
    # Fugenabgleich gegen das HOLDOUT-Foto (nicht im Relief)
    abgl = {}
    if hold:
        bh, okh, mpph = entzerren(hold); lk = linienkarte(cv2.cvtColor(bh, cv2.COLOR_BGR2GRAY), a.polaritaet)
        mz = okh & foto_da & ~gen & ndi.binary_erosion(okh & foto_da, np.ones((11, 11)))
        zonen = [("feld", np.ones(U.shape, bool))] + [(f"zone{i}", (U >= z_[0]) & (U <= z_[1]) & (ZZ >= z_[2]) & (ZZ <= z_[3])) for i, z_ in enumerate(a.zone)]
        for zn, zm in zonen:
            m_ = mz & zm
            if m_.sum() < 2000: continue
            ts, tn = taeler(scan, 7), taeler(neu, 7)
            def bester(tt): return max((fugen_abgleich(np.roll(np.roll(tt, dy, 0), dx, 1), lk, m_)["f1"], dy, dx) for dy in range(-8, 9, 2) for dx in range(-8, 9, 2))
            abgl[zn] = dict(zellen=int(m_.sum()), scan=fugen_abgleich(ts, lk, m_), neu=fugen_abgleich(tn, lk, m_), scan_bester_versatz=bester(ts), neu_bester_versatz=bester(tn))
            print(f"Fugenabgleich {zn} gegen Holdout {hold[1][-26:]} ({m_.sum() / 1e4:.1f} m2): Scan F1 {abgl[zn]['scan']['f1']:.3f} (Zufall {abgl[zn]['scan']['f1_zufall']:.3f}), "
                  f"neu F1 {abgl[zn]['neu']['f1']:.3f} (Zufall {abgl[zn]['neu']['f1_zufall']:.3f}); mit bestem Versatz (+-8 cm) Scan {abgl[zn]['scan_bester_versatz']}, neu {abgl[zn]['neu_bester_versatz']}")
        if a.zwischen: cv2.imwrite(os.path.join(a.zwischen, "holdout_wand.jpg"), bh)
    # Ausgabe im Format der Relief-Einsaetze, px a.px
    f = int(round(a.px / c)); hh, ww = nz // f, nu // f
    def klein(x): return x[:hh * f, :ww * f].reshape(hh, f, ww, f).mean((1, 3))
    rel_aus = klein(neu).astype(np.float32); fein = klein(foto_da.astype(np.float64)) > 0.5
    zo = g1 - hh * f * c
    eb = float(Z["ebene_abstand_m"]) + tu * (f0 - u0) + tz * (g1 - (z0 + H * rp))      # Ebene des Trends am neuen Ursprung (links oben), wie steine_aus_foto.py
    np.savez_compressed(a.aus, rel=rel_aus, a=A, t=t, n=nv, u0=f0, z0=zo, px=a.px, ebene_abstand_m=eb, trend_je_m=Z["trend_je_m"], putz_niveau_m=niv,
                        fein=fein, putz=klein(putz.astype(np.float64)) > 0.5, quelle=np.array("relief_aus_fotos_mono.py: Tiefpass Scan + Hochpass Depth-Anything-V2-Small (Kacheln, Median ueber Fotos)"),
                        fotos=np.array([q[1] for q in wahl]), trenn_m=a.trenn)
    # Generator wie bei steine_aus_foto: relief_koerper(aus, trend=True, rand_auslauf=False), grobes Relief dort tief_felder.
    T = time.time() - T0
    # Bild: Foto | Scan | neu (Schattierung, gleiche Beleuchtung)
    vis = bilder[0].copy()
    def zeile(x): return cv2.cvtColor(schatten(x, c), cv2.COLOR_GRAY2BGR)
    tafel = np.hstack([vis, np.full((nz, 8, 3), 255, np.uint8), zeile(scan), np.full((nz, 8, 3), 255, np.uint8), zeile(neu)])
    for i, txt in enumerate(["Foto " + wahl[0][1][-22:], "Scan-Relief (Bestand)", "neu: Scan tief + Fotos hoch"]):
        cv2.putText(tafel, txt, (10 + i * (nu + 8), 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3)
    for z_ in a.zone:
        for i in range(3):
            x0 = int((z_[0] - f0) / c) + i * (nu + 8); x1 = int((z_[1] - f0) / c) + i * (nu + 8); y0 = int((g1 - z_[3]) / c); y1 = int((g1 - z_[2]) / c); cv2.rectangle(tafel, (x0, y0), (x1, y1), (0, 200, 255), 3)
    cv2.imwrite(a.aus.replace(".npz", ".jpg"), tafel, [cv2.IMWRITE_JPEG_QUALITY, 88])
    erg = dict(relief=a.relief, feld=a.feld, feinausrichtung=fa_ber, anker_fein=anker, trenn_m=a.trenn, fotos=info, holdout=hold[1] if hold else None, fugenabgleich=abgl, foto_anteil=float(foto_da.mean()),
               hub_p5_p95_scan=float(np.ptp(np.quantile(scan[echt], [0.05, 0.95]))) if echt.any() else None, hub_p5_p95_neu=float(np.ptp(np.quantile(neu[foto_da], [0.05, 0.95]))) if foto_da.any() else None,
               sekunden_gesamt=round(T, 1), sekunden_laden=round(T1 - T0, 1), modell="Depth-Anything-V2-Small-hf (Apache-2.0)",
               hinweis="Hochpass-Feinform aus monokularer Tiefe, Massstab am Scan-Bandpass verankert; Fugentiefe daher Scan-Massstab, nicht gemessen = ANNAHME")
    json.dump(erg, open(a.aus.replace(".npz", ".json"), "w"), indent=1)
    print(f"geschrieben {a.aus} ({rel_aus.shape[1]} x {rel_aus.shape[0]} Zellen a {a.px * 100:.0f} cm), Fotoanteil {foto_da.mean() * 100:.0f} %, {T:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
