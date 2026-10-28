#!/usr/bin/env python3
"""foto_kanten_messen.py — KANTENERKENNUNG (OpenCV Canny + Hough) + ENTFERNUNGSMESSUNG.

Methode die der User fordert: nicht nach Gefühl platzieren, sondern am Foto die KANTEN erkennen,
die ABSTÄNDE exakt messen (in Metern, über eine bekannte Referenzbreite skaliert) und daraus
entscheiden, welche Bauteile auf welche HÖHE / welchen ABSTAND gehören. Dann Stück für Stück.

Ausgabe:
  - waagrechte Haupt-Kanten (Höhen-Bänder) mit Höhe über Boden in METERN
  - senkrechte Haupt-Kanten (Pfeiler/Teilungen) mit x in Metern + Abstände
  - Vergleich gegen die MODELL-Konstanten (EAVE/RIDGE/SILL/HEAD/ARC_*) → Δ flaggen
  - Overlay-Bild mit eingezeichneten Kanten + Maßen

Lauf: python3 tools/foto_kanten_messen.py [foto] [x0,y0,x1,y1] [ref_breite_m]
(ref_breite_m = reale Gebäudebreite in m, Default 23.0 = aktuelle Modellbreite W)
"""
import sys, json
import numpy as np
import cv2

FOTO = sys.argv[1] if len(sys.argv) > 1 else "/home/md/git/rc-park/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg"
BOX = [float(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else [0.195, 0.075, 0.79, 0.925]  # TIGHT aufs Gebäude (Erker→Erker, Helm→Boden) → Crop-Breite = Gebäudebreite = saubere Skala
REF_W = float(sys.argv[3]) if len(sys.argv) > 3 else 18.5

# Modell-Konstanten (aus tools/kaufhaus_measured.py) zum Gegencheck — Höhe über Boden in m
MODELL = {"Boden": 0.0, "Bogen-Kämpfer": 2.2, "Bogen-Scheitel": 5.2, "Brüstung-OK": 6.2,
          "Fenster-Sohlbank": 6.3, "Fenster-Sturz": 9.1, "Traufe": 9.7, "First": 15.4}


def cluster(vals, lens, tol):
    """1D-Positionen (gewichtet mit Linienlänge) zu Haupt-Kanten clustern."""
    order = np.argsort(vals); vals = np.array(vals)[order]; lens = np.array(lens)[order]
    clusters = []  # [pos, totallen]
    for v, l in zip(vals, lens):
        if clusters and v-clusters[-1][0] < tol:
            p, tl = clusters[-1]
            clusters[-1] = [(p*tl+v*l)/(tl+l), tl+l]
        else:
            clusters.append([v, l])
    return clusters


def main():
    img = cv2.imread(FOTO)
    H0, W0 = img.shape[:2]
    x0, y0, x1, y1 = int(W0*BOX[0]), int(H0*BOX[1]), int(W0*BOX[2]), int(H0*BOX[3])
    crop = img[y0:y1, x0:x1]
    PW = 1400                                                # auf handliche Breite skalieren (Hough stabil)
    crop = cv2.resize(crop, (PW, int(crop.shape[0]*PW/crop.shape[1])))
    ch, cw = crop.shape[:2]
    # --- ROBUSTE ANKER: Gebäude segmentieren → Boden (unterste Kante) + BREITE (links/rechts) ---
    # (vorher Fehler: Skala aus Crop-Breite, Boden = Crop-Unterkante → Höhen/First falsch)
    bch, bgn, brd = crop[:, :, 0].astype(int), crop[:, :, 1].astype(int), crop[:, :, 2].astype(int)
    red = (brd > bgn+12) & (brd > bch+8) & (brd > 60)
    green = (bgn > bch+8) & (bgn > 70) & (bgn < 200) & (brd < bgn+45)
    bld = ((red | green).astype(np.uint8))*255
    bld = cv2.morphologyEx(bld, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    bld = cv2.morphologyEx(bld, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    nlbl, lbl, st, _ = cv2.connectedComponentsWithStats(bld)
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    bx, by, bw_px, bh_px, _ = st[big]
    ground_y = by + bh_px                                    # Unterkante Gebäude = Boden
    ridge_y = by                                            # Oberkante (inkl. Helmspitzen)
    scale = REF_W/bw_px                                      # m/px über GEMESSENE Gebäudebreite (nicht Crop-Breite)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 60, 60)
    med = np.median(gray)
    edges = cv2.Canny(gray, int(max(10, 0.5*med)), int(min(255, 1.2*med)))
    # Hough-Liniensegmente
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=55,
                            minLineLength=int(cw*0.08), maxLineGap=18)
    hy, hl, vx, vl = [], [], [], []
    if lines is not None:
        lines = np.asarray(lines).reshape(-1, 4)             # cv2 5.x gibt (N,4), ältere (N,1,4)
        for ln in lines:
            ax, ay, bx, by = ln; dx, dy = bx-ax, by-ay
            length = np.hypot(dx, dy); ang = np.degrees(np.arctan2(dy, dx))
            if abs(ang) < 8 or abs(abs(ang)-180) < 8:        # waagrecht
                hy.append((ay+by)/2); hl.append(length)
            elif abs(abs(ang)-90) < 8:                       # senkrecht
                vx.append((ax+bx)/2); vl.append(length)
    # waagrechte Haupt-Kanten
    hc = [c for c in cluster(hy, hl, ch*0.014) if c[1] > bw_px*0.3]
    hc.sort(key=lambda c: c[0])
    ridge_m = (ground_y-ridge_y)*scale
    print(f"Gebäude in Crop: Breite {bw_px}px, Boden y={ground_y}, First(inkl.Helm) y={ridge_y}")
    print(f"Skala {scale:.4f} m/px (Ref-Breite {REF_W} m)  → GEMESSENE Gesamthöhe {ridge_m:.2f} m")
    print("\n=== WAAGRECHTE KANTEN (Höhe über Boden, gemessen) ===")
    meas_h = []
    for pos, tl in hc:
        h_m = (ground_y-pos)*scale                           # Höhe über GEMESSENEM Boden
        meas_h.append(h_m)
        print(f"  y={pos/ch:.3f}  -> {h_m:5.2f} m über Boden   (Linienlänge {tl/cw:.1f}·Breite)")
    # Gegencheck: je Modell-Band die nächste gemessene Kante + Δ
    print("\n=== MODELL vs. MESSUNG (nächste gemessene Kante) ===")
    for nm, zz in MODELL.items():
        if not meas_h:
            break
        near = min(meas_h, key=lambda m: abs(m-zz))
        flag = "" if abs(near-zz) < 0.4 else "  <-- Δ prüfen"
        print(f"  {nm:16s} Modell {zz:5.2f} m   nächste Messung {near:5.2f} m   Δ={near-zz:+.2f}{flag}")
    # senkrechte Haupt-Kanten
    vc = [c for c in cluster(vx, vl, cw*0.014) if c[1] > ch*0.14]
    vc.sort(key=lambda c: c[0])
    xs_m = [(pos-bx)*scale for pos, _ in vc]                  # x ab linker Gebäudekante
    print(f"\n=== SENKRECHTE KANTEN (x in m, {len(vc)} Stück) ===")
    print("  x[m]: " + ", ".join(f"{x:.1f}" for x in xs_m))
    if len(xs_m) > 1:
        gaps = np.diff(xs_m)
        print("  Abstände[m]: " + ", ".join(f"{g:.1f}" for g in gaps))
    # HYBRID: je Modell-Feature die nächste gemessene Kante NUR übernehmen, wenn sie nah genug ist
    # (sonst Default behalten) → Messung VERFEINERT das Parametermodell, überschreibt nicht blind.
    TOL = 0.8
    refined = {}
    for nm, zz in MODELL.items():
        if nm == "Boden" or not meas_h:                      # Boden = Datum, bleibt 0 (Crop-Unterkante ist kein Maß)
            refined[nm] = zz; continue
        near = min(meas_h, key=lambda m: abs(m-zz))
        refined[nm] = round(near, 2) if abs(near-zz) <= TOL else zz
    mass = {"skala_m_per_px": scale, "ref_breite_m": REF_W, "toleranz_m": TOL,
            "waagrecht_h_m": [round(h, 2) for h in meas_h],
            "senkrecht_x_m": [round(x, 2) for x in xs_m],
            "features_verfeinert_m": refined,
            "_hinweis": "Höhen = von Messung verfeinert (nur wenn Kante < toleranz_m am Default). Stückzahlen bleiben aus params.json (User-Grundwahrheit)."}
    json.dump(mass, open("/tmp/kanten_mass.json", "w"), indent=2)
    json.dump(mass, open("/home/md/git/rc-park/modelle/kaufhaus_freiburg/kaufhaus_mass.json", "w"), indent=2)
    print("\n=== HYBRID: verfeinerte Feature-Höhen (m) -> kaufhaus_mass.json ===")
    for nm, v in refined.items():
        tag = "" if v == MODELL[nm] else f"  (war {MODELL[nm]})"
        print(f"  {nm:16s} {v:5.2f}{tag}")
    # Overlay
    vis = crop.copy()
    for pos, _ in hc:
        cv2.line(vis, (0, int(pos)), (cw, int(pos)), (0, 255, 0), 2)
        cv2.putText(vis, f"{(ground_y-pos)*scale:.1f}m", (6, int(pos)-5), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    for pos, _ in vc:
        cv2.line(vis, (int(pos), int(ch*0.55)), (int(pos), ch), (0, 140, 255), 2)
    cv2.imwrite("/tmp/kanten_mass.png", vis)
    cv2.imwrite("/tmp/kanten_canny.png", edges)
    print("\n-> /tmp/kanten_mass.png (Kanten+Maße), /tmp/kanten_canny.png (Canny), /tmp/kanten_mass.json")


if __name__ == "__main__":
    main()
