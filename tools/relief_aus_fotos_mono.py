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


def tiefe_kacheln(bild, m, kachel, s_hp, gpu_mb=3300, seite=518):
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
            acc[y0:y0 + k, x0:x0 + k] += win * hp / (hp[mm].std() + 1e-9); ws[y0:y0 + k, x0:x0 + k] += win
    if dev.type == "cuda": torch.cuda.empty_cache()
    return acc / np.maximum(ws, 1e-6), ws


def taeler(r, s_cm):
    """Fugen-/Taelerkarte eines Hoehenbilds (1 cm): Black-Top-Hat mit Scheibe s_cm"""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (s_cm, s_cm)); return cv2.morphologyEx(r.astype(np.float32), cv2.MORPH_BLACKHAT, k)


def linienkarte(g, polaritaet, s_cm=9):
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (s_cm, s_cm)); g = cv2.GaussianBlur(g.astype(np.float32), (0, 0), 1.0)
    return cv2.morphologyEx(g, cv2.MORPH_BLACKHAT if polaritaet == "dunkel" else cv2.MORPH_TOPHAT, k)


def fugen_abgleich(r_rel, r_foto, m, anteil=0.12, tol=2, schub=(13, 9)):
    """Anteil der staerksten 'anteil' Relief-Taeler, die <= tol cm neben den staerksten Foto-Linien (Holdout) liegen, und umgekehrt; F1. Zufall: Relief um 'schub' cm verschoben."""
    def oben(x): th = np.quantile(x[m], 1 - anteil); return (x >= th) & m
    a = oben(r_foto); dt_a = ndi.distance_transform_edt(~a)
    def f1(b):
        if b.sum() == 0: return 0.0, 0.0, 0.0
        p = float((dt_a[b] <= tol).mean()); dt_b = ndi.distance_transform_edt(~b); r = float((dt_b[a] <= tol).mean()); return p, r, 2 * p * r / max(p + r, 1e-9)
    b = oben(r_rel); bs = np.roll(np.roll(b, schub[0], 1), schub[1], 0) & m
    return dict(praezision=f1(b)[0], trefferquote=f1(b)[1], f1=f1(b)[2], f1_zufall=f1(bs)[2])


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
    ap.add_argument("--gpu_mb", type=int, default=3300); ap.add_argument("--min_korr", type=float, default=0.2); ap.add_argument("--kachel", type=float, default=1.5, help="Kachelkante m fuer das Tiefenmodell"); ap.add_argument("--abstand", type=float, default=0.5, help="Mindestabstand der Fotostandorte m"); ap.add_argument("--draht", type=float, default=0.05, help="duenne ERHABENE Linien schmaler als das (m) je Foto weg (Graustufen-Oeffnung): Oberleitungen, Kabel")
    ap.add_argument("--ohne", nargs=4, type=float, action="append", default=[], help="Feld u0 u1 z0 z1 ohne Foto-Relief (Fremdkoerper: Verkehrsschild, Lampe) - dort bleibt der Scan"); ap.add_argument("--zwischen", default=None, help="Ordner fuer Zwischenbilder (Datenplatte)"); a = ap.parse_args()
    T0 = time.time(); sys.path.insert(0, HIER); import fassade_ein_foto as FE, render_kern as rk, trimesh, torch
    if torch.cuda.is_available(): torch.cuda.set_per_process_memory_fraction(min(0.95, a.gpu_mb / (torch.cuda.get_device_properties(0).total_memory / 2**20)))   # Budget gilt auch fuer das Sichtbarkeitsraster
    if os.path.exists(a.aus): print("Ziel existiert schon (nicht ueberschreiben):", a.aus); return 2
    Z = dict(np.load(a.relief)); rel = Z["rel"].astype(np.float64); H, W = rel.shape; rp = float(Z["px"]); u0 = float(Z["u0"]); z0 = float(Z["z0"]); A = Z["a"]; t = Z["t"]; nv = Z["n"]
    tu, tz = [float(v) for v in Z["trend_je_m"]]; niv = float(Z.get("putz_niveau_m", 0.0))
    f0, f1, g0, g1 = a.feld; c = 0.01; nu = int(round((f1 - f0) / c)); nz = int(round((g1 - g0) / c)); jj, ii = np.meshgrid(np.arange(nu), np.arange(nz)); U = f0 + (jj + 0.5) * c; ZZ = g1 - (ii + 0.5) * c
    dpl = float(Z["ebene_abstand_m"]) + tu * (U - u0) - tz * ((z0 + H * rp) - ZZ)
    X = A[0] + U * t[0] + dpl * nv[0]; Y = A[1] + U * t[1] + dpl * nv[1]; Zw = ZZ.copy()
    if a.massstab: k = a.massstab[0]; Mp = a.massstab[1:]; X = Mp[0] + k * (X - Mp[0]); Y = Mp[1] + k * (Y - Mp[1]); Zw = Mp[2] + k * (ZZ - Mp[2])
    P = np.stack([X, Y, Zw], -1).reshape(-1, 3)
    def gross(x, interp=cv2.INTER_LINEAR): return cv2.remap(x.astype(np.float32), ((U - u0) / rp - 0.5).astype(np.float32), (H - (ZZ - z0) / rp - 0.5).astype(np.float32), interp, borderMode=cv2.BORDER_REPLICATE).astype(np.float64)
    scan = gross(rel); putz = gross(Z["putz"]) > 0.5 if "putz" in Z else np.zeros(U.shape, bool); gen = gross(Z["generiert"]) > 0.5 if "generiert" in Z else np.zeros(U.shape, bool)
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
    hp_liste = []; info = []; bilder = []
    for q in wahl:
        tq = time.time(); b, ok_, mpp = entzerren(q); m = ok_ & ~oeff & (b.max(2) > 8)
        if m.sum() < 5000: info.append(dict(foto=q[1], verworfen="zu wenig sichtbar")); continue
        fuell = b.copy(); fuell[~m] = cv2.inpaint(b, (~m).astype(np.uint8), 15, cv2.INPAINT_TELEA)[~m]
        hp, ws = tiefe_kacheln(fuell, m, int(round(a.kachel / c)), s_tr, a.gpu_mb); m &= ws > 0.05
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
        hp = np.roll(np.roll(kq * hp, vb[1], 0), vb[2], 1); m = np.roll(np.roll(m, vb[1], 0), vb[2], 1); hp[~m] = np.nan
        info.append(dict(foto=q[1], cm_je_px=round(mpp * 100, 2), sichtbar=round(float(ok_.mean()), 3), massstab=kq, korrelation_band_scan=round(r, 3),
                         bester_versatz_cm=dict(nach_unten=vb[1], nach_rechts=vb[2], korrelation=round(vb[0], 3)), sekunden=round(time.time() - tq, 1)))
        print(f"  {q[1][-30:]}: {mpp * 100:.1f} cm/px, sichtbar {ok_.mean() * 100:.0f} %, Korrelation mit Scan (2-{a.trenn * 100:.0f} cm) {r:+.2f} "
              f"(verschoben {vb[1]:+d}/{vb[2]:+d} cm: {vb[0]:+.2f}), Massstab {kq:.4g}, {time.time() - tq:.0f} s", flush=True)
        if r < a.min_korr: info[-1]["verworfen"] = "keine Korrelation mit dem Scan (Modell sieht andere Form)"; continue
        hp_liste.append(hp); bilder.append(b)
        if a.zwischen: os.makedirs(a.zwischen, exist_ok=True); cv2.imwrite(os.path.join(a.zwischen, q[1][-40:] + "_wand.jpg"), b); np.save(os.path.join(a.zwischen, q[1][-40:] + "_hp.npy"), hp.astype(np.float32))
    if not hp_liste: print("kein Foto mit Korrelation zum Scan - nichts erzeugt"); json.dump(dict(fotos=info), open(a.aus.replace(".npz", ".json"), "w"), indent=1); return 4
    # Fotos vereinen: gewichtetes Mittel mit (a) Rand-Auslauf je Foto (20 cm ab Sichtgrenze - sonst Naehte, wo ein Foto endet: Nord 17.11. harte Linien) und
    # (b) Kappung auf Median +- 1,5 Streuungen (ein Draht/Passant in EINEM Foto zieht das Mittel nicht mit). Ein Foto allein = sein Wert.
    S = np.stack(hp_liste); fin = np.isfinite(S); nfoto = fin.sum(0); S0 = np.where(fin, S, 0.0)
    with np.errstate(all="ignore"): med = np.nan_to_num(np.nanmedian(np.where(fin, S, np.nan), 0))
    tau = 1.5 * mad((S - med)[fin]); Wg = np.stack([np.clip(ndi.distance_transform_edt(f_) * c / 0.20, 0, 1) for f_ in fin])
    hpm = (Wg * np.clip(S0, med - tau, med + tau)).sum(0) / np.maximum(Wg.sum(0), 1e-6); hpm = np.where(nfoto > 0, hpm, 0.0)
    lp_scan = gauss_maske(scan, ~oeff, s_tr)[0]
    for q0, q1, r0, r1 in a.ohne: oeff = oeff | ((U >= q0) & (U <= q1) & (ZZ >= r0) & (ZZ <= r1))
    foto_da = (nfoto > 0) & ~putz & ~oeff
    neu = np.where(foto_da, lp_scan + hpm, scan); neu = np.where(putz, scan, neu)
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
    erg = dict(relief=a.relief, feld=a.feld, trenn_m=a.trenn, fotos=info, holdout=hold[1] if hold else None, fugenabgleich=abgl, foto_anteil=float(foto_da.mean()),
               hub_p5_p95_scan=float(np.ptp(np.quantile(scan[echt], [0.05, 0.95]))) if echt.any() else None, hub_p5_p95_neu=float(np.ptp(np.quantile(neu[foto_da], [0.05, 0.95]))) if foto_da.any() else None,
               sekunden_gesamt=round(T, 1), sekunden_laden=round(T1 - T0, 1), modell="Depth-Anything-V2-Small-hf (Apache-2.0)",
               hinweis="Hochpass-Feinform aus monokularer Tiefe, Massstab am Scan-Bandpass verankert; Fugentiefe daher Scan-Massstab, nicht gemessen = ANNAHME")
    json.dump(erg, open(a.aus.replace(".npz", ".json"), "w"), indent=1)
    print(f"geschrieben {a.aus} ({rel_aus.shape[1]} x {rel_aus.shape[0]} Zellen a {a.px * 100:.0f} cm), Fotoanteil {foto_da.mean() * 100:.0f} %, {T:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
