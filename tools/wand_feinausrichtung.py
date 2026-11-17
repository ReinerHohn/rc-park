#!/usr/bin/env python3
"""wand_feinausrichtung.py - Feinausrichtung mehrerer entzerrter Wandbilder (gleiches Wandraster) gegeneinander, NACH Homographie/Kameraprojektion.

Warum (Nutzer 17.11.2026: "Bilder pixelgenau uebereinander legen"; Recherche A1): die Einzelfotos liegen nach Homographie bzw. Kameraprojektion noch 1-3 cm
gegeneinander versetzt (Kamerareste, Flaeche != echte Tiefe). Median/Mittel ueber die Fotos verwischt dann Fugen und Kanten.
Ablauf (generisch, GPU per torch):
  1. Je Bild Grau -> Bandpass (Gauss 1 Zelle minus Gauss --hp Zellen, maskiert normiert): Helligkeit/Schatten der Fotos faellt weg, Fugen/Kanten bleiben.
  2. Bezug je Foto = Median der ANDEREN Fotos (leave-one-out: ein Foto zieht seinen Bezug nicht zu sich), iterativ (--iter).
  3. Dichtes Blockmatching (NCC, Fenster --fenster m) aller ganzzahligen Verschiebungen bis --max m, Subpixel per Parabel. Vertrauen nur, wo
     (a) NCC >= --min_ncc, (b) Spitze deutlich (Kruemmung), (c) nicht am Suchrand, (d) Vorwaerts-Rueckwaerts-Probe <= --fb Zellen, (e) Textur in beiden Bildern.
     Verdecker (Baum, Draht, Auto, Passant) stimmen nicht mit dem Median der anderen ueberein -> kein Vertrauen -> dort KEINE eigene Verschiebung.
  4. Feld = normierte Gauss-Faltung (--glatt m) der vertrauten Verschiebungen mit Vorgabe 0 (wo keine Belege: Homographie bleibt), zwei Durchgaenge mit
     Ausreisser-Verwurf (> 1,5 Zellen vom glatten Feld), Kappung auf --max m. Mittel der Felder ueber die Fotos wird abgezogen (die Gesamtlage bleibt die der Kameras).
  5. Bild/Maske mit dem Gesamtfeld neu abgetastet (cv2.remap). Bericht: Restversatz je Foto vorher/nachher (gleiches Matching UND unabhaengig per Phasenkorrelation je Kachel).
Aufruf als Bibliothek: fein_ausrichten(bilder, masken, zelle, ...) -> (bilder_neu, masken_neu, felder, bericht). Bilder uint8 HxWx3 (0 = ungueltig erlaubt), Masken bool HxW.
Kommandozeile (Selbsttest): python3 tools/wand_feinausrichtung.py --selbsttest
"""
import sys, os, json, time, argparse, numpy as np, cv2

_DEV = None


def _torch():
    import torch
    global _DEV
    if _DEV is None: _DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch, _DEV


def bandpass(g, m, s0=1.0, s1=8.0):
    """maskierter Bandpass (Gauss s0 minus Gauss s1, Zellen), ausserhalb der Maske 0"""
    g = g.astype(np.float32); mf = m.astype(np.float32)
    def gm(s): return cv2.GaussianBlur(g * mf, (0, 0), s) / np.maximum(cv2.GaussianBlur(mf, (0, 0), s), 1e-3)
    b = gm(s0) - gm(s1); b[~m] = 0; return b


def _box(x, k):
    torch, _ = _torch(); import torch.nn.functional as Fn
    return Fn.avg_pool2d(x[None, None], k, stride=1, padding=k // 2, count_include_pad=False)[0, 0]


def match_dicht(A, mA, B, mB, D, k, min_ncc=0.5, min_kr=0.02, min_std=0.0, zeilen=360):
    """Verschiebung d(x) mit A(x) ~ B(x + d), dichte NCC (Fenster k Zellen, |d| <= D Zellen, ganzzahlig + Parabel). Rueckgabe dy, dx, ncc, ok (numpy)."""
    torch, dev = _torch(); H, W = A.shape; k = k | 1; r = k // 2
    dy = np.zeros((H, W), np.float32); dx = np.zeros((H, W), np.float32); best = np.full((H, W), -1.0, np.float32); ok = np.zeros((H, W), bool)
    sh = [(a, b) for a in range(-D, D + 1) for b in range(-D, D + 1)]; idx = {s: i for i, s in enumerate(sh)}
    for y0 in range(0, H, zeilen):
        ya = max(0, y0 - r - D); yb = min(H, y0 + zeilen + r + D); ca = y0 - ya; cb = ca + min(zeilen, H - y0)
        a = torch.from_numpy(A[ya:yb]).to(dev); ma = torch.from_numpy(mA[ya:yb].astype(np.float32)).to(dev)
        bp = torch.nn.functional.pad(torch.from_numpy(B[ya:yb]).to(dev)[None, None], (D, D, D, D))[0, 0]
        mbp = torch.nn.functional.pad(torch.from_numpy(mB[ya:yb].astype(np.float32)).to(dev)[None, None], (D, D, D, D))[0, 0]
        h_, w_ = a.shape; vol = torch.empty((len(sh), h_, w_), dtype=torch.float32, device=dev)
        for i, (sy, sx) in enumerate(sh):
            b = bp[D + sy:D + sy + h_, D + sx:D + sx + w_]; mb = mbp[D + sy:D + sy + h_, D + sx:D + sx + w_]; mm = ma * mb
            n = _box(mm, k).clamp_min(1e-6); a_ = a * mm; b_ = b * mm
            ma_ = _box(a_, k) / n; mb_ = _box(b_, k) / n
            va = (_box(a_ * a, k) / n - ma_ ** 2).clamp_min(0); vb = (_box(b_ * b, k) / n - mb_ ** 2).clamp_min(0); cv = _box(a_ * b, k) / n - ma_ * mb_
            v = cv / torch.sqrt(va * vb + 1e-12); v[(n < 0.8) | (va <= min_std ** 2) | (vb <= min_std ** 2)] = -1.0; vol[i] = v
        mx, am = vol.max(0); am_ = am.cpu().numpy(); mx_ = mx.cpu().numpy(); volc = vol
        sy = np.array([s[0] for s in sh])[am_]; sx = np.array([s[1] for s in sh])[am_]
        def wert(oy, ox):
            j = np.full(am_.shape, -1); ty = sy + oy; tx = sx + ox; inn = (np.abs(ty) <= D) & (np.abs(tx) <= D)
            j[inn] = ((ty[inn] + D) * (2 * D + 1) + (tx[inn] + D)); jt = torch.from_numpy(np.clip(j, 0, len(sh) - 1)).to(dev)
            v = torch.gather(volc, 0, jt[None].long())[0].cpu().numpy(); v[~inn] = np.nan; return v
        vu, vd, vl, vr = wert(-1, 0), wert(1, 0), wert(0, -1), wert(0, 1)
        def para(m1, p1):
            den = m1 - 2 * mx_ + p1; o = np.where(np.abs(den) > 1e-6, 0.5 * (m1 - p1) / den, 0.0); return np.clip(np.nan_to_num(o), -0.5, 0.5), den
        oy, deny = para(vu, vd); ox, denx = para(vl, vr)
        kr = np.minimum(np.nan_to_num(mx_ - (vu + vd) / 2, nan=0), np.nan_to_num(mx_ - (vl + vr) / 2, nan=0))
        rand = (np.abs(sy) == D) | (np.abs(sx) == D)
        o = (mx_ >= min_ncc) & (kr >= min_kr) & ~rand & (ma.cpu().numpy() > 0)
        sl = slice(ca, cb); dy[y0:y0 + (cb - ca)] = (sy + oy)[sl]; dx[y0:y0 + (cb - ca)] = (sx + ox)[sl]; best[y0:y0 + (cb - ca)] = mx_[sl]; ok[y0:y0 + (cb - ca)] = o[sl]
        del vol, volc
    return dy, dx, best, ok


def glattes_feld(dy, dx, w, s, vorgabe=0.05, ausr=1.5, D=5.0):
    """normierte Gauss-Faltung mit Vorgabe 0 (Gewicht 'vorgabe' relativ zu einem voll belegten Fenster), Ausreisser-Verwurf, Kappung auf D"""
    w = w.astype(np.float32)
    for _ in range(2):
        gw = cv2.GaussianBlur(w, (0, 0), s); fy = cv2.GaussianBlur(w * dy, (0, 0), s) / (gw + vorgabe); fx = cv2.GaussianBlur(w * dx, (0, 0), s) / (gw + vorgabe)
        w = w * ((np.hypot(dy - fy, dx - fx) <= ausr).astype(np.float32))
    gw = cv2.GaussianBlur(w, (0, 0), s); fy = cv2.GaussianBlur(w * dy, (0, 0), s) / (gw + vorgabe); fx = cv2.GaussianBlur(w * dx, (0, 0), s) / (gw + vorgabe)
    return np.clip(fy, -D, D).astype(np.float32), np.clip(fx, -D, D).astype(np.float32), gw / (gw + vorgabe)


def _warp(x, fy, fx, interp=cv2.INTER_LINEAR):
    H, W = x.shape[:2]; jj, ii = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    return cv2.remap(x, jj + fx, ii + fy, interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def _median_ohne(G, M, i):
    idx = [j for j in range(len(G)) if j != i]; T = np.stack([np.where(M[j], G[j], np.nan) for j in idx])
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore"); med = np.nanmedian(T, 0); n = np.isfinite(T).sum(0)
    return np.nan_to_num(med).astype(np.float32), n


def restversatz(G, M, D, k, min_ncc, min_n=2, fb=1.0):
    """Restversatz je Foto gegen den Median der anderen: Median |d| (Zellen) an vertrauten Stellen (vorwaerts-rueckwaerts geprueft), Anteil vertraut, Median NCC"""
    aus = []
    for i in range(len(G)):
        R, n = _median_ohne(G, M, i); mR = n >= min_n; dy, dx, nc, ok = match_dicht(G[i], M[i], R, mR, D, k, min_ncc)
        by, bx, _, okb = match_dicht(R, mR, G[i], M[i], D, k, min_ncc)
        H, W = dy.shape; jj, ii = np.meshgrid(np.arange(W), np.arange(H)); yy = np.clip(np.round(ii + dy).astype(int), 0, H - 1); xx = np.clip(np.round(jj + dx).astype(int), 0, W - 1)
        ok &= okb[yy, xx] & (np.hypot(dy + by[yy, xx], dx + bx[yy, xx]) <= fb)
        ber = M[i] & mR
        aus.append(dict(median_zellen=float(np.median(np.hypot(dy, dx)[ok])) if ok.sum() > 100 else None, p90_zellen=float(np.quantile(np.hypot(dy, dx)[ok], 0.9)) if ok.sum() > 100 else None,
                        vertraut=float(ok.sum() / max(ber.sum(), 1)), ncc_median=float(np.median(nc[ber & (nc > -1)])) if (ber & (nc > -1)).sum() > 100 else None))
    return aus


def rest_dis(G, M, min_n=2, kachel=64, min_antwort=0.15):
    """UNABHAENGIGE Probe (anderes Verfahren als das NCC-Matching): Phasenkorrelation je Kachel (kachel Zellen, Hann-Fenster) Foto gegen den Median der
    anderen; Median |Verschiebung| (Zellen) ueber Kacheln mit Antwort >= min_antwort und voller gemeinsamer Maske. (Name historisch: zuerst DIS-Fluss, der auf
    unterschiedlich belichteten Fotos Unsinn lieferte - 10-30 Zellen, wo NCC < 1 sah.)"""
    aus = []; hann = cv2.createHanningWindow((kachel, kachel), cv2.CV_32F)
    for i in range(len(G)):
        R, n = _median_ohne(G, M, i); m = M[i] & (n >= min_n); v = []
        for y in range(0, m.shape[0] - kachel + 1, kachel):
            for x in range(0, m.shape[1] - kachel + 1, kachel):
                if m[y:y + kachel, x:x + kachel].mean() < 0.98: continue
                a_ = G[i][y:y + kachel, x:x + kachel].astype(np.float32); b_ = R[y:y + kachel, x:x + kachel].astype(np.float32)
                if a_.std() < 1e-3 or b_.std() < 1e-3: continue
                (sx, sy), r = cv2.phaseCorrelate(a_, b_, hann)
                if r >= min_antwort: v.append(float(np.hypot(sx, sy)))
        aus.append(float(np.median(v)) if len(v) >= 5 else None)
    return aus


def ndi_ero(m, k): return cv2.erode(m.astype(np.uint8), np.ones((k, k), np.uint8)).astype(bool)


def global_versatz(G, M, Dg, min_antwort=0.05):
    """starre Verschiebung je Foto gegen den Median der anderen (Phasenkorrelation des ganzen Bandpass-Bilds, gemeinsame Maske, Hann). Rueckgabe [(gy, gx, antwort)] in Zellen,
    Vorzeichen wie das Feld (Bild wird an x + f abgetastet). Nur angenommen bei Antwort >= min_antwort und |f| <= Dg, sonst 0."""
    aus = []
    for i in range(len(G)):
        R, n = _median_ohne(G, M, i); m = (M[i] & (n >= 2)).astype(np.float32); H, W = m.shape; hann = cv2.createHanningWindow((W, H), cv2.CV_32F)
        (sx, sy), r = cv2.phaseCorrelate((R * m).astype(np.float32), (G[i] * m).astype(np.float32), hann)
        ok = r >= min_antwort and np.hypot(sx, sy) <= Dg; aus.append((float(sy) if ok else 0.0, float(sx) if ok else 0.0, float(r)))
    return aus


def fein_ausrichten(bilder, masken, zelle, max_m=0.05, fenster_m=0.25, glatt_m=0.30, min_ncc=0.5, fb=1.0, iter=3, hp_m=0.08, vorgabe=0.05, global_m=0.15, min_vertraut=0.10, gpu_mb=2500, bericht_dis=True, log=print):
    """bilder: Liste uint8 HxWx3 (gleiches Wandraster), masken: Liste bool HxW. Rueckgabe (bilder_neu, masken_neu, felder [(fy, fx) Zellen], bericht)"""
    torch, dev = _torch(); T0 = time.time()
    if dev.type == "cuda": torch.cuda.set_per_process_memory_fraction(min(0.95, gpu_mb / (torch.cuda.get_device_properties(0).total_memory / 2**20)))
    n = len(bilder); D = max(1, int(round(max_m / zelle))); k = max(5, int(round(fenster_m / zelle)) | 1); s = glatt_m / zelle; hp = hp_m / zelle
    gr = [cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32) for b in bilder]; M0 = [m.copy() for m in masken]
    G0 = [bandpass(g, m, 1.0, hp) for g, m in zip(gr, M0)]
    FY = [np.zeros(m.shape, np.float32) for m in M0]; FX = [np.zeros(m.shape, np.float32) for m in M0]
    ber = dict(parameter=dict(zelle=zelle, max_m=max_m, global_m=global_m, min_vertraut=min_vertraut, fenster_m=fenster_m, glatt_m=glatt_m, min_ncc=min_ncc, fb_zellen=fb, iter=iter, hp_m=hp_m, vorgabe=vorgabe), iterationen=[])
    if n < 3:
        ber["hinweis"] = "weniger als 3 Fotos: kein robuster Bezug, nichts ausgerichtet"; return bilder, masken, list(zip(FY, FX)), ber
    ber["vorher"] = restversatz(G0, M0, D, k, min_ncc); ber["vorher_dis"] = rest_dis(G0, M0) if bericht_dis else None
    # Stufe 0 (17.11.: Foto 113939 lag 5-7 cm neben den anderen = ausserhalb des Suchbereichs, 1 % vertraut): starre Verschiebung je Foto bis global_m, zweimal
    GY = np.zeros(n, np.float32); GX = np.zeros(n, np.float32); G = [g.copy() for g in G0]; M = [m.copy() for m in M0]; ber["global"] = []
    for _ in range(2 if global_m > 0 else 0):
        gv = global_versatz(G, M, global_m / zelle); ber["global"].append([[round(v, 2) for v in x] for x in gv])
        GY = GY + np.array([x[0] for x in gv], np.float32); GX = GX + np.array([x[1] for x in gv], np.float32); GY -= np.median(GY); GX -= np.median(GX)
        G = [_warp(g, np.full(g.shape, gy, np.float32), np.full(g.shape, gx, np.float32)) for g, gy, gx in zip(G0, GY, GX)]; M = [_warp(m.astype(np.uint8), np.full(m.shape, gy, np.float32), np.full(m.shape, gx, np.float32), cv2.INTER_NEAREST).astype(bool) for m, gy, gx in zip(M0, GY, GX)]
    if global_m > 0: log("  starrer Versatz je Foto (cm): " + ", ".join(f"{gy * zelle * 100:+.1f}/{gx * zelle * 100:+.1f}" for gy, gx in zip(GY, GX)), flush=True)
    FY = [np.full(m.shape, gy, np.float32) for m, gy in zip(M0, GY)]; FX = [np.full(m.shape, gx, np.float32) for m, gx in zip(M0, GX)]
    for it in range(iter):
        inc = []; info = []
        for i in range(n):
            R, nn = _median_ohne(G, M, i); mR = nn >= 2
            dy, dx, nc, ok = match_dicht(G[i], M[i], R, mR, D, k, min_ncc); by, bx, _, okb = match_dicht(R, mR, G[i], M[i], D, k, min_ncc)
            H, W = dy.shape; jj, ii = np.meshgrid(np.arange(W), np.arange(H)); yy = np.clip(np.round(ii + dy).astype(int), 0, H - 1); xx = np.clip(np.round(jj + dx).astype(int), 0, W - 1)
            ok &= okb[yy, xx] & (np.hypot(dy + by[yy, xx], dx + bx[yy, xx]) <= fb)
            w = ok * np.clip((nc - min_ncc) / (1 - min_ncc), 0, 1); fy, fx, kon = glattes_feld(dy, dx, w, s, vorgabe, 1.5, D)
            inc.append((-fy, -fx)); info.append(dict(vertraut=round(float(ok.sum() / max((M[i] & mR).sum(), 1)), 3), feld_median_zellen=round(float(np.median(np.hypot(fy, fx)[M[i]])), 3)))
        for i in range(n): FY[i] = np.clip(FY[i] + inc[i][0], GY[i] - D, GY[i] + D); FX[i] = np.clip(FX[i] + inc[i][1], GX[i] - D, GX[i] + D)   # lokal hoechstens max_m um den starren Versatz
        # Gesamtlage = Kameras: MEDIAN der Felder ueber die Fotos, die die Stelle sehen, abziehen (ein Ausreisser-Foto verschiebt die anderen nicht)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); my = np.nan_to_num(np.nanmedian(np.stack([np.where(m, f, np.nan) for f, m in zip(FY, M0)]), 0)); mx = np.nan_to_num(np.nanmedian(np.stack([np.where(m, f, np.nan) for f, m in zip(FX, M0)]), 0))
        for i in range(n): FY[i] = FY[i] - my; FX[i] = FX[i] - mx
        G = [_warp(g, fy, fx) for g, fy, fx in zip(G0, FY, FX)]; M = [_warp(m.astype(np.uint8), fy, fx, cv2.INTER_NEAREST).astype(bool) for m, fy, fx in zip(M0, FY, FX)]
        ber["iterationen"].append(info); log(f"  Feinausrichtung Runde {it + 1}: " + ", ".join(f"vertraut {x['vertraut']:.0%} Feld {x['feld_median_zellen'] * zelle * 100:.1f} cm" for x in info), flush=True)
    ber["feld_cm"] = [dict(median=round(float(np.median(np.hypot(fy, fx)[m])) * zelle * 100, 2), p95=round(float(np.quantile(np.hypot(fy, fx)[m], 0.95)) * zelle * 100, 2)) for fy, fx, m in zip(FY, FX, M0)]
    # Foto ohne Belege (Anteil vertraut < min_vertraut in der letzten Runde, z. B. unscharfes/verwackeltes Foto): Feld 0 = Homographie/Kamera bleibt
    for i, x in enumerate(ber["iterationen"][-1] if ber["iterationen"] else []):
        if x["vertraut"] < min_vertraut: FY[i] = np.zeros_like(FY[i]); FX[i] = np.zeros_like(FX[i]); x["zurueckgesetzt"] = True
    # Farbbilder KUBISCH neu abtasten: bilinear verwischt bei Teilzellen-Verschiebung (Kaufhaus 17.11.: Feld ~0, Schaerfe trotzdem 3390 -> 3295)
    neu = [np.where(_warp(m.astype(np.uint8), fy, fx, cv2.INTER_NEAREST)[..., None] > 0, _warp(b, fy, fx, cv2.INTER_CUBIC), 0).astype(np.uint8) for b, m, fy, fx in zip(bilder, M0, FY, FX)]
    M = [_warp(m.astype(np.uint8), fy, fx, cv2.INTER_NEAREST).astype(bool) for m, fy, fx in zip(M0, FY, FX)]; ber["sekunden"] = round(time.time() - T0, 1)
    G = [_warp(g, fy, fx) for g, fy, fx in zip(G0, FY, FX)]; ber["nachher"] = restversatz(G, M, D, k, min_ncc); ber["nachher_dis"] = rest_dis(G, M) if bericht_dis else None
    def cm(v): return "-" if v is None else f"{v * zelle * 100:.2f}"
    log("  Restversatz je Foto (Median, cm) vorher -> nachher: " + ", ".join(f"{cm(a['median_zellen'])}->{cm(b['median_zellen'])}" for a, b in zip(ber["vorher"], ber["nachher"]))
        + (("; Phasenkorr.-Probe: " + ", ".join(f"{cm(a)}->{cm(b)}" for a, b in zip(ber["vorher_dis"], ber["nachher_dis"]))) if bericht_dis else "") + f" ({ber['sekunden']:.0f} s)", flush=True)
    return neu, M, list(zip(FY, FX)), ber


def schaerfe(bilder, masken, zone=None, min_n=3):
    """Gradientenenergie des Median-Wandbilds (Grau, Bandpass-frei: Sobel) in der Zone, wo >= min_n Fotos liegen"""
    T = np.stack([np.where(m, cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32), np.nan) for b, m in zip(bilder, masken)])
    import warnings
    with warnings.catch_warnings(): warnings.simplefilter("ignore"); med = np.nanmedian(T, 0); n = np.isfinite(T).sum(0)
    med = np.nan_to_num(med); z = (n >= min_n) & ndi_ero(n >= min_n, 7)
    if zone is not None: z &= zone
    gx = cv2.Sobel(med, cv2.CV_32F, 1, 0); gy = cv2.Sobel(med, cv2.CV_32F, 0, 1); return float(np.mean((gx ** 2 + gy ** 2)[z])) if z.any() else None, med


def _selbsttest(klein=False):
    """synthetisch: Steinwand mit Fugen, 4 Fotos mit glattem Versatz bis 3 cm, eins mit 'Baum' (fremde Textur) -> Restversatz < 0,5 cm, Baum nicht eingezogen"""
    rng = np.random.default_rng(1); H, W = (160, 220) if klein else (300, 400); zl = 0.01
    base = np.full((H, W), 150, np.float32)
    for y in range(0, H, 30): base[y:y + 2] = 60
    for r_, y in enumerate(range(0, H, 30)):
        for x in range((r_ % 2) * 25, W, 50): base[y:y + 30, x:x + 2] = 60
    base = cv2.GaussianBlur(base + rng.normal(0, 8, (H, W)).astype(np.float32), (0, 0), 1.0)
    jj, ii = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32)); B = []; M = []; wahr = []
    for i in range(5):
        fy = (1.5 * np.sin(jj / 130 + i) + (i - 2) * 0.6).astype(np.float32); fx = (1.5 * np.cos(ii / 110 + 2 * i) - (i - 2) * 0.5 + (7.0 if i == 4 else 0.0)).astype(np.float32)
        im = cv2.remap(base, jj - fx, ii - fy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) + rng.normal(0, 3, (H, W)).astype(np.float32)
        b = np.clip(np.stack([im] * 3, -1), 1, 255).astype(np.uint8); wahr.append((fy, fx))
        if i == 0: b[60:140, 120:200] = np.clip(rng.normal(90, 40, (80, 80, 1)), 0, 255).astype(np.uint8).repeat(3, 2)    # Baum nur in Foto 0
        B.append(b); M.append(np.ones((H, W), bool))
    neu, Mn, F, ber = fein_ausrichten(B, M, zl, max_m=0.05, fenster_m=0.25, glatt_m=0.3, iter=2 if klein else 3, bericht_dis=not klein, log=lambda *a, **k: None)
    vor = [x["median_zellen"] for x in ber["vorher"]]; nach = [x["median_zellen"] for x in ber["nachher"]]
    baum_feld = float(np.median(np.hypot(*F[0])[60:140, 120:200]))
    s0, _ = schaerfe(B, M); s1, _ = schaerfe(neu, Mn)
    print("Selbsttest: Restversatz vorher", [round(v, 2) for v in vor], "nachher", [round(v, 2) for v in nach], "Schaerfe", round(s0), "->", round(s1), "Feld im Baum", round(baum_feld, 2))
    ok = max(nach[1:]) < 0.5 and np.median(vor) > 1.0 and s1 > s0 and bitgleich_test(B, M)
    return 0 if ok else 1


def bitgleich_test(B, M):
    a = fein_ausrichten(B, M, 0.01, iter=1, bericht_dis=False, log=lambda *a, **k: None)[0]; b = fein_ausrichten(B, M, 0.01, iter=1, bericht_dis=False, log=lambda *a, **k: None)[0]
    return all(np.array_equal(x, y) for x, y in zip(a, b))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--selbsttest", action="store_true"); ap.add_argument("--klein", action="store_true"); a = ap.parse_args()
    if a.selbsttest: sys.exit(_selbsttest(a.klein))
    print(__doc__); sys.exit(0)
