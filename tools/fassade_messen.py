#!/usr/bin/env python3
"""fassade_messen.py — GENERISCHE Fassaden-Vermessung per Kantenerkennung (kein Augenmaß!).

measure(foto, box, eave_m, n_axes) segmentiert die Putzfassade per Farbe, nimmt ihre
Bounding-Box als Anker (Traufe=Oberkante, Ränder=links/rechts), skaliert über die amtliche
Traufhöhe (Traufe->Boden) und misst automatisch:
  - reale Gebäudebreite W (m)
  - EG-Oberkante / Gurtgesims (m über Boden)  -> Geschosstrennung
  - N saubere Fensterachsen (x-Fraktionen) via Spalten-Projektion (Fenster+Läden = ein Peak)

Diese Funktion wird direkt im bauwerk_generator aufgerufen -> Datenerkennung ist Teil der
Pipeline (nicht manuell abgetippt).

  CLI: python3 tools/fassade_messen.py <foto> <x0,y0,x1,y1 frac> <eave_m> [n_axes] [--out m.json]
"""
import sys, json
import numpy as np
import cv2


def _facade_mask(crop):
    b, g, r = crop[:, :, 0].astype(int), crop[:, :, 1].astype(int), crop[:, :, 2].astype(int)
    cream = (r > 150) & (g > 140) & (b < 190) & (r >= b) & (g >= b - 12) & ((r + g) > 2.05 * b)
    m = (cream.astype(np.uint8)) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    nl, lbl, st, _ = cv2.connectedComponentsWithStats(m)
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    return (lbl == big).astype(np.uint8), st[big]


def _axis_peaks(facade, fx, fw, y0, y1, n):
    """N Fensterachsen aus Spalten-Projektion: wo Fenster/Läden/Blumen sind, ist KEIN Putz.
    non-cream-Anteil je Spalte -> Runs über Schwelle -> n breiteste = Achsen (x-Fraktion)."""
    strip = facade[y0:y1, fx:fx + fw]
    noncream = 1.0 - strip.mean(0)                      # 0..1 je Spalte
    k = max(3, int(fw * 0.02)); ker = np.ones(k) / k
    s = np.convolve(noncream, ker, mode="same")
    thr = max(0.35, s.mean())
    runs, i = [], 0
    while i < len(s):
        if s[i] > thr:
            j = i
            while j < len(s) and s[j] > thr:
                j += 1
            runs.append((i, j, (s[i:j].sum())))        # (start,end,gewicht)
            i = j
        else:
            i += 1
    runs.sort(key=lambda rr: rr[2], reverse=True)
    runs = sorted(runs[:n], key=lambda rr: rr[0])
    return [round(((a + bb) / 2) / fw, 3) for a, bb, _ in runs]


def _h_bands(crop, fx, fw, fy, ground_y, scale):
    gray = cv2.bilateralFilter(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), 7, 60, 60)
    med = np.median(gray)
    edges = cv2.Canny(gray, int(max(10, .5 * med)), int(min(255, 1.2 * med)))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 55, minLineLength=int(fw * 0.35), maxLineGap=18)
    hy, hl = [], []
    if lines is not None:
        for ax, ay, bx2, by2 in np.asarray(lines).reshape(-1, 4):
            if abs(np.degrees(np.arctan2(by2 - ay, bx2 - ax))) < 8:
                hy.append((ay + by2) / 2); hl.append(np.hypot(bx2 - ax, by2 - ay))
    o = np.argsort(hy); hy = np.array(hy)[o]; hl = np.array(hl)[o]; cl = []
    for v, l in zip(hy, hl):
        if cl and v - cl[-1][0] < (ground_y - fy) * 0.012:
            p, tl = cl[-1]; cl[-1] = [(p * tl + v * l) / (tl + l), tl + l]
        else:
            cl.append([v, l])
    return sorted([round((ground_y - p) * scale, 2) for p, _ in cl if _ > fw * 0.25], reverse=True)


def measure(foto, box, eave_m, n_axes=4):
    img = cv2.imread(foto); H0, W0 = img.shape[:2]
    x0, y0, x1, y1 = int(W0 * box[0]), int(H0 * box[1]), int(W0 * box[2]), int(H0 * box[3])
    crop = img[y0:y1, x0:x1]; PW = 1400
    crop = cv2.resize(crop, (PW, int(crop.shape[0] * PW / crop.shape[1])))
    ch, cw = crop.shape[:2]
    facade, (fx, fy, fw, fh, _) = _facade_mask(crop)
    eave_y, cream_bot = fy, fy + fh
    r = crop[:, :, 2].astype(int); g = crop[:, :, 1].astype(int); b = crop[:, :, 0].astype(int)
    dark = (r < 150) & (g < 130) & (b < 120)
    col = slice(fx + fw // 4, fx + 3 * fw // 4)
    drows = np.where(dark[:, col].mean(1) > 0.4)[0]
    ground_y = int(drows[drows > cream_bot].max()) if np.any(drows > cream_bot) else ch - 1
    scale = eave_m / (ground_y - eave_y)                 # Traufe->Boden = amtliche Traufhöhe
    W_m = fw * scale
    # First (Dach-Oberkante, perspektivisch verkürzt) über der Traufe, zentrale Spalten
    # (Ränder meiden -> keine höheren Nachbarhäuser). non-Himmel von oben her.
    cc = slice(fx + int(0.25 * fw), fx + int(0.75 * fw))
    notsky = ~((r > 188) & (g > 188) & (b > 183))
    rr = np.where(notsky[:eave_y, cc].mean(1) > 0.5)[0]
    ridge_y = int(rr.min()) if len(rr) else eave_y
    roof_rise_m = round((eave_y - ridge_y) * scale, 2)    # GEMESSENE Dachhöhe (Front)
    # SCHORNSTEIN-DETEKTOR (gegen Halluzination): Spalten, deren Skyline DEUTLICH über dem
    # First liegen = Silhouette-Beulen. Keine Beulen -> keine Schornsteine (egal was Config sagt).
    xs_c = range(fx + int(0.08 * fw), fx + int(0.92 * fw))
    skyline = np.array([(np.where(notsky[:eave_y, x])[0].min() if notsky[:eave_y, x].any() else eave_y)
                        for x in xs_c])
    base = np.median(skyline); thr = 0.05 * (ground_y - eave_y); minw = max(3, int(0.015 * fw))
    prot = skyline < base - thr
    n_chimneys = 0; i = 0
    while i < len(prot):
        if prot[i]:
            j = i
            while j < len(prot) and prot[j]:
                j += 1
            if j - i >= minw:
                n_chimneys += 1
            i = j
        else:
            i += 1
    # DACH-ÖFFNUNGS-DETEKTOR (gegen Halluzination): Gauben = helle Fenster in der UNTEREN
    # Dachschräge, Dachluken = kleine dunkle Rechtecke in der OBEREN Schräge. Nur so viele
    # bauen wie wirklich zu sehen.
    gr = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    rh = max(eave_y - ridge_y, 12); xs0, xs1 = fx + int(0.03 * fw), fx + int(0.97 * fw)

    def _count(mask, amin, amax, wmin):
        mm = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n, _, stt, _ = cv2.connectedComponentsWithStats(mm)
        return sum(1 for k in range(1, n)
                   if amin <= stt[k, cv2.CC_STAT_AREA] <= amax and stt[k, cv2.CC_STAT_WIDTH] >= wmin)
    brite = gr > 168
    brite[:eave_y - int(0.55 * rh), :] = False; brite[eave_y:, :] = False
    brite[:, :xs0] = False; brite[:, xs1:] = False
    n_dormers = _count(brite, (0.02 * fw) ** 2, (0.16 * fw) ** 2, int(0.025 * fw))
    # DACHLUKEN (Velux): LOKALE Merkmalserkennung per Top-Hat/Black-Hat auf Velux-Skala —
    # unterdrückt die langsam variierende Dachtextur, isoliert kleine lokal-kontrastierende
    # Rechtecke (heller Reflex ODER dunkler Rahmen). Obere Schräge, über den Gauben.
    se = int(0.035 * fw) | 1
    kk = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (se, se))
    yA, yB = ridge_y + int(0.05 * rh), ridge_y + int(0.52 * rh)
    roi = gr[yA:yB, xs0:xs1]
    resp = cv2.max(cv2.morphologyEx(roi, cv2.MORPH_BLACKHAT, kk),
                   cv2.morphologyEx(roi, cv2.MORPH_TOPHAT, kk))
    mm = (resp > resp.mean() + 3.0 * resp.std()).astype(np.uint8) * 255
    mm = cv2.morphologyEx(mm, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    mm = cv2.morphologyEx(mm, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ncc, _, stt2, ctr2 = cv2.connectedComponentsWithStats(mm)
    sky_x = []
    for k in range(1, ncc):
        a, w, h = stt2[k, cv2.CC_STAT_AREA], stt2[k, cv2.CC_STAT_WIDTH], stt2[k, cv2.CC_STAT_HEIGHT]
        xf_ = (ctr2[k][0] + xs0 - fx) / fw
        if (0.012 * fw) ** 2 <= a <= (0.06 * fw) ** 2 and 0.4 <= w / max(h, 1) <= 2.6 \
                and w >= 0.015 * fw and 0.1 <= xf_ <= 0.9:          # Ränder meiden (Nachbarhaus)
            sky_x.append(round(xf_, 3))
    sky_x.sort(); n_skylights = len(sky_x)
    # FARB-DETEKTOR: repräsentative Element-Farben aus dem Foto (RGB) — damit die Farben auf
    # den ersten Schlag stimmen (Dach nicht zu hell etc.). Median je Region (robust).
    def _med(mask):
        if int(mask.sum()) < 25:
            return None
        m = np.median(crop[mask], 0)            # crop ist BGR
        return [int(m[2]), int(m[1]), int(m[0]), 255]
    regf = np.zeros((ch, cw), bool); regf[fy:cream_bot, fx:fx + fw] = True
    facb = facade.astype(bool)
    colors = {"fassade": _med(facb)}
    roofm = np.zeros((ch, cw), bool); roofm[ridge_y:eave_y, fx:fx + fw] = True
    roofm &= ~((r > 185) & (g > 185) & (b > 180)) & (np.abs(r - b) < 50) & (r < 175)
    colors["dach"] = _med(roofm)
    # Läden: NUR grün-dominante Pixel (g>r), sonst fällt Olivbraun/Schatten rein -> None -> Default
    colors["laeden"] = _med(regf & ~facb & (g > r + 1) & (g > b + 8) & (g > 85) & (g < 205))
    colors["blumen"] = _med(regf & (r > g + 18) & (r > b + 18) & (r > 90))
    # Holz-Sockel (Wainscot) = dunkle Zone im unteren EG; die EG-WAND selbst bleibt cremefarben
    egm = np.zeros((ch, cw), bool); egm[cream_bot:ground_y, fx:fx + fw] = True
    colors["sockel_holz"] = _med(egm & (r < 130) & (r >= g - 6) & (g >= b - 6))
    # WEISSABGLEICH / BELEUCHTUNGS-NORMIERUNG: Messfarbe = Material×Licht. Für Render-Albedo muss
    # das Licht raus -> durch die Weißreferenz (weiße Fensterrahmen = hell+neutral) teilen.
    neutral = regf & (np.abs(r - g) < 16) & (np.abs(g - b) < 16) & (r > 150)
    gain = np.ones(3)
    if int(neutral.sum()) > 50:
        wr = np.percentile(crop[neutral], 80, axis=0)            # BGR, hell-neutral
        white = np.array([wr[2], wr[1], wr[0]], float)
        gain = np.clip(235.0 / np.maximum(white, 60), 1.0, 2.0)
    colors = {k: [int(min(255, v[0] * gain[0])), int(min(255, v[1] * gain[1])),
                  int(min(255, v[2] * gain[2])), 255] for k, v in colors.items() if v}
    colors["_weissref_gain"] = [round(float(x), 2) for x in gain]
    # ZIERBAND-DETEKTOR: stärkstes waagrechtes CHROMATISCHES (blaues) Band quer über die Fassade
    # (z.B. gemalte Gurtlinie). Himmelsreflexe in Fenstern sind nur punktuell -> Schwelle hoch.
    blue = (b > r + 10) & (b > g + 6) & (b > 90)
    rf = np.array([blue[y, fx:fx + fw].mean() for y in range(fy, fy + fh)])
    zierband = None
    if rf.max() > 0.4:
        ym = int(np.argmax(rf)); y0b = y1b = ym
        while y0b > 0 and rf[y0b - 1] > 0.3:
            y0b -= 1
        while y1b < len(rf) - 1 and rf[y1b + 1] > 0.3:
            y1b += 1
        bnd = crop[fy + y0b:fy + y1b + 1, fx:fx + fw]
        bm = bnd[:, :, 0].astype(int) > bnd[:, :, 2].astype(int) + 8
        cc2 = np.median(bnd[bm], 0) if int(bm.sum()) > 10 else [195, 160, 150]
        zierband = {"h_m": round((ground_y - (fy + (y0b + y1b) // 2)) * scale, 2),
                    "color": [int(cc2[2]), int(cc2[1]), int(cc2[0]), 255]}
    bands = _h_bands(crop, fx, fw, fy, ground_y, scale)
    # EG-Oberkante = stärkstes Band im Bereich 0.25..0.40 der Traufhöhe (Gurtgesims)
    cand = [h for h in bands if 0.24 * eave_m <= h <= 0.42 * eave_m]
    eg_top = round(float(np.median(cand)), 2) if cand else round(0.30 * eave_m, 2)
    axes = _axis_peaks(facade, fx, fw, eave_y + int(0.03 * fh), cream_bot - int(0.02 * fh), n_axes)
    # SCHRIFTZUG-DETEKTOR: Zeilenband mit hoher KANTENdichte (Text) in der unteren Creme.
    # -> photo_region (Bild-Fraktionen) + Höhe, damit der Generator den Streifen automatisch
    # aus dem Foto holt und als Textur aufsetzt ('nur Kanten erkennen und draufmachen').
    lettering = None
    e2 = cv2.Canny(gr, 60, 160)
    lo0, lo1 = cream_bot - int(0.22 * fh), min(cream_bot + int(0.06 * fh), ch - 1)  # unterer Creme-Bereich
    if lo1 > lo0 + 6:
        # Kantendichte NUR auf Creme-Pixeln (Text auf Putz); dunkle Schaufensterzeilen -> 0
        ed = []
        for y in range(lo0, lo1):
            cr = facade[y, fx:fx + fw].astype(float)
            ed.append(float((e2[y, fx:fx + fw] * cr).mean()) if cr.mean() > 0.35 else 0.0)
        ed = np.array(ed)
        if ed.max() > 0.02:
            pk = lo0 + int(np.argmax(ed))            # crop-Zeile des Kanten-Peaks (Textzeile)
            cy0, cy1 = pk - int(0.07 * fh), pk + int(0.02 * fh)
            def _fx(x): return round(box[0] + (x / cw) * (box[2] - box[0]), 4)
            def _fy(y): return round(box[1] + (y / ch) * (box[3] - box[1]), 4)
            lettering = {"photo_region": [_fx(fx), _fy(cy0), _fx(fx + fw), _fy(cy1)],
                         "h_m": round((ground_y - (cy0 + cy1) // 2) * scale, 2)}
    # FASSADEN-REGIONEN (Bild-Fraktionen) zum Texturieren der Wand-Panels (Schrift/Blau/Farbe
    # kommen damit automatisch aus der Textur, egal wo sie sind).
    def _ffx(x): return round(box[0] + (x / cw) * (box[2] - box[0]), 4)
    def _ffy(y): return round(box[1] + (y / ch) * (box[3] - box[1]), 4)
    facade_up = [_ffx(fx), _ffy(eave_y), _ffx(fx + fw), _ffy(cream_bot)]
    facade_eg = [_ffx(fx), _ffy(cream_bot), _ffx(fx + fw), _ffy(ground_y)]
    res = {"quelle": foto, "eave_ref_m": eave_m, "scale_m_per_px": round(scale, 5),
           "lettering": lettering, "facade_region_upper": facade_up, "facade_region_eg": facade_eg,
           "W_m": round(W_m, 2), "eg_top_m": eg_top, "axes_x_frac": axes,
           "roof_rise_m": roof_rise_m, "ridge_y": ridge_y, "n_chimneys": int(n_chimneys),
           "n_dormers": int(n_dormers), "n_skylights": int(n_skylights), "skylight_x_frac": sky_x,
           "colors": colors, "zierband": zierband,
           "baender_h_m": bands, "ground_y": ground_y, "eave_y": int(eave_y), "fw_px": int(fw)}
    return res, crop, facade, (fx, fy, fw, fh), ground_y, scale


if __name__ == "__main__":
    foto = sys.argv[1]; box = [float(v) for v in sys.argv[2].split(",")]; eave = float(sys.argv[3])
    nax = int(sys.argv[4]) if len(sys.argv) > 4 and not sys.argv[4].startswith("--") else 4
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "/tmp/fassade_mass.json"
    res, crop, facade, (fx, fy, fw, fh), ground_y, scale = measure(foto, box, eave, nax)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    json.dump(res, open(out, "w"), indent=2, ensure_ascii=False)
    vis = crop.copy()
    cv2.rectangle(vis, (fx, fy), (fx + fw, fy + fh), (255, 0, 0), 2)
    cv2.line(vis, (0, ground_y), (vis.shape[1], ground_y), (0, 0, 255), 2)
    for xf in res["axes_x_frac"]:
        X = int(fx + xf * fw); cv2.line(vis, (X, fy), (X, fy + fh), (0, 160, 255), 3)
    egy = int(ground_y - res["eg_top_m"] / scale)
    cv2.line(vis, (fx, egy), (fx + fw, egy), (0, 255, 0), 2)
    cv2.imwrite("/tmp/fassade_mass.png", vis)
    print(f"-> {out} + /tmp/fassade_mass.png")
