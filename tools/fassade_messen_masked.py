#!/usr/bin/env python3
"""fassade_messen_masked.py — Kaufhaus-Methode: Fassade aus dem FREIGESTELLTEN Gebäude (ML-Maske) +
MASSSTAB (LOD2) per Bildverarbeitung messen. Kanten NUR im Gebäude (Clutter weg) → waagrechte Bänder
(EG-Oberkante/Galerie/Traufe) in Metern + Fensterachsen. Schreibt facade_mass.json für den Generator.

Lauf: /tmp/ml/bin/python tools/fassade_messen_masked.py --name hofgut_sternen --foto g2 --ridge-m 17.46
"""
import argparse, json, os
import numpy as np
import cv2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--foto", default="g2")
    ap.add_argument("--ridge-m", type=float, default=17.46, help="Gesamthöhe Boden→First in m (LOD2)")
    a = ap.parse_args()
    fdir = f"daten/{a.name}/fotos"
    im = cv2.imread(f"{fdir}/{a.foto}.jpg")
    mask = cv2.imread(f"{fdir}/{a.foto}_mask.png", 0)
    if mask is None:
        raise SystemExit("Maske fehlt — erst tools/gebaeude_segment.py laufen lassen")
    mb = mask > 127
    ys, xs = np.where(mb)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    Hpx = y1 - y0
    pxm = Hpx / a.ridge_m                                    # MASSSTAB: Silhouettenhöhe = First (LOD2)

    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150); edges[~mb] = 0        # Kanten NUR im Gebäude
    roi = edges[y0:y1, x0:x1]
    # waagrechte Bänder: Zeilen-Kantendichte
    rowden = cv2.GaussianBlur(roi.sum(1).astype(float).reshape(-1, 1), (1, 9), 0).ravel()
    thr = rowden.mean() + 0.8 * rowden.std()
    bands = []
    for i in range(1, len(rowden) - 1):
        if rowden[i] > thr and rowden[i] >= rowden[i - 1] and rowden[i] > rowden[i + 1]:
            if bands and i - bands[-1] < 0.04 * Hpx:
                continue
            bands.append(i)
    bands_m = sorted(round((y1 - (y0 + b)) / pxm, 2) for b in bands)   # Höhe über Fuß in m

    # Fensterachsen: senkrechte Kantendichte
    colden = cv2.GaussianBlur(roi.sum(0).astype(float).reshape(1, -1), (0, 0), 3).ravel()
    tc = colden.mean() + 0.5 * colden.std()
    axes = []
    for i in range(1, len(colden) - 1):
        if colden[i] > tc and colden[i] >= colden[i - 1] and colden[i] > colden[i + 1]:
            if axes and i - axes[-1] < 0.03 * (x1 - x0):
                continue
            axes.append(i)
    n_axes = max(1, len(axes))

    # Interpretation: EG-Oberkante = tiefstes starkes Band in der unteren Hälfte; Galerie darüber;
    # Traufe = oberstes starkes Band im Wandbereich (unter ~Dachanteil).
    wall_bands = [b for b in bands_m if 1.0 < b < a.ridge_m * 0.6]
    eg_top = min(wall_bands) if wall_bands else a.ridge_m * 0.26
    gallery = sorted(wall_bands)[len(wall_bands) // 2] if wall_bands else a.ridge_m * 0.5
    eave = max(wall_bands) if wall_bands else a.ridge_m * 0.52

    out = {
        "quelle": f"Bildverarbeitung auf freigestelltem {a.foto} (ML-Maske) + LOD2-Maßstab {pxm:.1f}px/m",
        "ridge_m": a.ridge_m, "eave_m": round(eave, 2), "eg_top_m": round(eg_top, 2),
        "gallery_m": round(gallery, 2), "n_axes": n_axes,
        "alle_baender_m": bands_m,
    }
    json.dump(out, open(f"modelle/{a.name}/facade_mass.json", "w"), indent=1, ensure_ascii=False)

    # Overlay
    ov = im.copy(); ov[~mb] = (ov[~mb] * 0.3).astype(np.uint8)
    for b in bands:
        y = y0 + b; cv2.line(ov, (x0, y), (x1, y), (0, 200, 255), 2)
        cv2.putText(ov, f"{(y1-y)/pxm:.1f}m", (x1 - 70, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)
    for p in axes:
        cv2.line(ov, (x0 + p, y0), (x0 + p, y1), (200, 200, 200), 1)
    cv2.imwrite(f"modelle/{a.name}/facade_mass.png", cv2.resize(ov, None, fx=1.5, fy=1.5))
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"-> modelle/{a.name}/facade_mass.json + facade_mass.png")


if __name__ == "__main__":
    main()
