#!/usr/bin/env python3
"""foto_metrologie.py — Bauwerk-Geometrie aus einem Foto MESSEN und gegen das Modell prüfen.

Prinzip (robust, kein fragiles Linien-Hough im Wald-Rauschen): die Bögen sind bekanntlich
Rund-/Halbkreisbögen. Wir fitten die Bogen-Leibung (Intrados) mit RANSAC als KREIS
(skimage) — das ist zugleich die Formprüfung (kleiner Rest = echter Halbkreis) und liefert
Spannweite (2R) + Stich (R) + Stich:Spann. Maßstab optional über eine bekannte Referenz
(Normalspur 1,435 m / Deckhöhe).

Aufruf:
  python3 tools/foto_metrologie.py --img daten/ravenna/fotos/rv_panorama.jpg \
      --model-rise-span 0.50 --out /tmp/rv_metrologie.png
"""
import argparse, sys
import numpy as np
import cv2


def opening_masks(img, min_area=0.004):
    """dunkle Durchsichten (Wald/Schatten hinter den Bögen) als Öffnungs-Regionen."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = g.shape
    bs = max(31, int(W * 0.06) | 1)        # Blockgröße skaliert mit Bildbreite (ungerade)
    th = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                               cv2.THRESH_BINARY_INV, bs, 10)
    k = max(5, int(W * 0.004))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, np.ones((2*k, 2*k), np.uint8))
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        # Öffnung: groß genug UND hochkant-ish (nicht ein flacher Waldstreifen)
        if cv2.contourArea(c) > min_area * H * W and 0.3 < w / max(h, 1) < 2.5:
            out.append(c[:, 0, :])
    return sorted(out, key=lambda c: cv2.boundingRect(c)[0])  # nach x


def intrados_points(contour):
    """obere Begründung (Intrados) der Öffnung: je x-Spalte der oberste Konturpunkt."""
    x, y, w, h = cv2.boundingRect(contour.reshape(-1, 1, 2))
    pts = contour
    top = {}
    for px, py in pts:
        if px not in top or py < top[px]:
            top[px] = py
    xs = np.array(sorted(top))
    ys = np.array([top[x] for x in xs])
    # nur mittlerer Bereich = Bogenkurve (Ränder sind senkrechte Leibung)
    m = (xs > x + 0.06 * w) & (xs < x + 0.94 * w) & (ys < y + 0.6 * h)
    return np.c_[xs[m], ys[m]].astype(float), (x, y, w, h)


def fit_circle_ransac(P):
    from skimage.measure import CircleModel, ransac
    if len(P) < 20:
        return None
    model, inl = ransac(P, CircleModel, min_samples=3,
                        residual_threshold=max(3, 0.01 * np.ptp(P[:, 0])),
                        max_trials=300)
    if model is None:
        return None
    try:
        (cx, cy), r = model.center, model.radius      # skimage ≥0.26
    except AttributeError:
        cx, cy, r = model.params
    resid = np.abs(np.sqrt((P[inl, 0]-cx)**2 + (P[inl, 1]-cy)**2) - r)
    return dict(cx=cx, cy=cy, r=r, inl=inl, rms=float(np.sqrt(np.mean(resid**2))),
                n=int(inl.sum()), ntot=len(P))


def width_at_row(contour, y, tol):
    """UNABHÄNGIGE Spannweite: Öffnungsbreite der Maske auf Höhe y (Kämpferlinie)."""
    sel = contour[np.abs(contour[:, 1] - y) < tol]
    if len(sel) < 2:
        return None
    return float(sel[:, 0].max() - sel[:, 0].min())


def measure_arch(contour):
    """LEHRE: keine Form aufzwingen. Echte Öffnungskante verfolgen → Breite-über-Höhe-
    Profil → am KÄMPFER trennen (Pfeiler unten / Bogen oben) → Kreis NUR auf die
    Bogenzone fitten. Gibt die wahre Geometrie zurück (oder None)."""
    from scipy.ndimage import uniform_filter1d
    pts = contour
    x, y, w, h = cv2.boundingRect(pts.reshape(-1, 1, 2))
    rows = []
    for yy in range(y, y + h):
        xs = pts[np.abs(pts[:, 1] - yy) < 2][:, 0]
        if len(xs) >= 2:
            rows.append((yy, xs.min(), xs.max()))
    if len(rows) < 30:
        return None
    rows = np.array(rows, float)
    yy, xl, xr = rows[:, 0], rows[:, 1], rows[:, 2]
    width = uniform_filter1d(xr - xl, max(5, h // 40))
    wmax = np.percentile(width, 92)
    arch = yy < yy[width >= 0.90 * wmax][0]     # oberhalb Kämpfer = Bogenzone
    if arch.sum() < 15:
        return None
    # Kreisfit NUR auf Bogen-Leibung (beide Kanten)
    P = np.vstack([np.c_[xl[arch], yy[arch]], np.c_[xr[arch], yy[arch]]])
    A = np.c_[2*P[:, 0], 2*P[:, 1], np.ones(len(P))]
    sol, *_ = np.linalg.lstsq(A, P[:, 0]**2 + P[:, 1]**2, rcond=None)
    cx, cy = sol[0], sol[1]; R = np.sqrt(sol[2] + cx**2 + cy**2)
    rms = float(np.mean(np.abs(np.hypot(P[:, 0]-cx, P[:, 1]-cy) - R)))
    span = float(wmax)
    return dict(cx=cx, cy=cy, R=R, span=span, rms=rms, box=(x, y, w, h),
                semicircle=abs(2*R - span) / span < 0.10,
                rms_frac=rms / R, pier_frac=float((y + h - cy) / h))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--model-rise-span", type=float, default=0.50)
    ap.add_argument("--scale", type=float, default=0.0, help="m pro Pixel (optional)")
    ap.add_argument("--span-m", type=float, default=0.0, help="bekannte Spannweite in m → Maßstab")
    ap.add_argument("--out", default="/tmp/foto_metrologie.png")
    a = ap.parse_args()

    img = cv2.imread(a.img)
    if img is None:
        sys.exit(f"Bild nicht gefunden: {a.img}")
    H, W = img.shape[:2]
    sc = 2400 / W
    img = cv2.resize(img, (2400, int(H * sc)))
    H, W = img.shape[:2]

    masks = opening_masks(img)
    print(f"Öffnungen erkannt: {len(masks)}")
    vis = img.copy()
    arches = []
    for c in masks:
        x0, y0, bw, bh = cv2.boundingRect(c.reshape(-1, 1, 2))
        if x0 <= 2 or x0 + bw >= W - 2:           # am Bildrand abgeschnitten → kein ganzer Bogen
            continue
        m = measure_arch(c)                       # NEUE Methode: Kante verfolgen + zerlegen
        if not m:
            continue
        m["r"] = m["R"]; m["ok"] = m["rms_frac"] < 0.02 and m["semicircle"]
        arches.append(m)
        col = (0, 200, 0) if m["ok"] else (0, 140, 255)
        cx, cy, R, span = m["cx"], m["cy"], m["R"], m["span"]
        cv2.ellipse(vis, (int(cx), int(cy)), (int(R), int(R)), 0, 180, 360, col, 3)
        cv2.line(vis, (int(cx-span/2), int(cy)), (int(cx+span/2), int(cy)), (255, 0, 0), 2)
        x, y = m["box"][0], m["box"][1]
        cv2.putText(vis, f"R{R:.0f} Spann{span:.0f} {'HK' if m['semicircle'] else 'seg'}",
                    (x, max(22, y - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
    cv2.imwrite(a.out, cv2.resize(vis, (1300, int(H * 1300 / W))))

    if not arches:
        print("keine Bögen vermessbar"); print(f"-> {a.out}"); return
    arches.sort(key=lambda d: d["cx"])
    rs = np.array([d["R"] / d["span"] for d in arches])          # echtes Stich:Spann (Bogen-R vs Spann)
    spans2R = np.array([d["span"] for d in arches])              # unabhängig gemessene Spannweite
    # Pfeiler:Spann + Feldteilung NUR aus SAUBEREN (Halbkreis) Nachbarbögen, Lücken verwerfen
    clean = [d for d in arches if d["ok"]]
    pier_span_l, pitch_span_l = [], []
    for i in range(len(clean) - 1):
        pitch = clean[i+1]["cx"] - clean[i]["cx"]
        sp = (clean[i]["span"] + clean[i+1]["span"]) / 2
        if sp <= 0 or not (1.0 < pitch / sp < 1.6):   # Nachbar? (Lücke/Überlapp raus)
            continue
        pier_span_l.append((pitch - sp) / sp)
        pitch_span_l.append(pitch / sp)
    pier_span = float(np.median(pier_span_l)) if pier_span_l else float('nan')
    pitch_span = float(np.median(pitch_span_l)) if pitch_span_l else float('nan')

    def cmp(name, meas, soll, tolrel):
        err = abs(meas - soll) / soll if soll else 0
        v = "PASS" if err < tolrel else ("WARN" if err < 2*tolrel else "FAIL")
        print(f"  {name:22s} Foto {meas:6.2f}   Modell {soll:6.2f}   Δ{err*100:4.0f}%  [{v}]")
        return v

    print("\n=== VOLLE GEOMETRIE: Foto gemessen  vs  Modell-Soll ===")
    print(f"  Bogenzahl              Foto {len(arches):2d}      Modell  9   "
          f"({'alle erfasst' if len(arches)>=9 else 'nicht alle erkannt'})")
    cmp("Stich:Spann", float(np.median(rs)), a.model_rise_span, 0.06)
    if not np.isnan(pier_span):
        cmp("Pfeiler:Spann", pier_span, 0.244, 0.20)           # Modell PIER/SPAN=4.89/20
        cmp("Feldteilung:Spann", pitch_span, 1.244, 0.15)
    else:
        print("  Pfeiler:Spann / Feldteilung:  keine zwei sauberen Nachbarbögen → Rektifizierung nötig")
    nhk = sum(d["semicircle"] for d in arches)
    print(f"  Bogenform:             {nhk}/{len(arches)} Halbkreis (2R≈Spann), "
          f"Fit-RMS median {np.median([d['rms_frac'] for d in arches])*100:.1f} % von R")
    # absoluter Maßstab über bekannte Spannweite
    scale = a.span_m / float(np.median(spans2R)) if a.span_m else a.scale
    if scale:
        print(f"\n  --- absolute Meter (Maßstab {scale*100:.2f} cm/px) ---")
        print(f"  Spannweite:   {np.median(spans2R)*scale:5.1f} m" + (f"  (gesetzt {a.span_m})" if a.span_m else ""))
        if pier_span_l:
            print(f"  Pfeilerbreite:{np.median([p*sp for p in [pier_span] for sp in [np.median(spans2R)]])*scale:5.1f} m")
        if not np.isnan(pitch_span):
            print(f"  Feldteilung:  {pitch_span*np.median(spans2R)*scale:5.1f} m")
        print(f"  Bogen-R:      {np.median([d['R'] for d in arches])*scale:5.1f} m")
    else:
        print("  (kein Maßstab → nur Verhältnisse; --span-m 20 für echte Meter + Gegenprobe)")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
