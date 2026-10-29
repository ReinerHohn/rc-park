#!/usr/bin/env python3
"""bauplan_aus_foto.py — die beschriebene Methode als EINE Kette:
  1) Gebäude aus Umgebung freistellen (ML-Maske, gebaeude_segment)
  2) auf das Gebäude zuschneiden
  3) PERSPEKTIVE raus (fassade_entzerren, Fluchtpunkte)
  4) Kantenerkennung am entzerrten Objekt + MASSSTAB (LOD2) → Bänder/Achsen in Metern
  5) BAUPLAN (Aufriss mit Maßen) + bauplan.json für den 3D-Generator.

Lauf: /tmp/ml/bin/python tools/bauplan_aus_foto.py --name hofgut_sternen --foto g2 --ridge-m 17.46
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, "tools")
from fassade_entzerren import rectify


def peaks(sig, frac_gap, thr_k):
    thr = sig.mean() + thr_k * sig.std(); out = []
    for i in range(1, len(sig) - 1):
        if sig[i] > thr and sig[i] >= sig[i - 1] and sig[i] > sig[i + 1]:
            if out and i - out[-1] < frac_gap:
                continue
            out.append(i)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True); ap.add_argument("--foto", default="g2")
    ap.add_argument("--ridge-m", type=float, default=17.46)
    a = ap.parse_args()
    fdir = f"daten/{a.name}/fotos"; md = f"modelle/{a.name}"
    im = cv2.imread(f"{fdir}/{a.foto}.jpg"); mask = cv2.imread(f"{fdir}/{a.foto}_mask.png", 0)
    if mask is None:
        raise SystemExit("erst gebaeude_segment.py (Maske fehlt)")

    # 2) auf Gebäude zuschneiden (etwas Rand für die Entzerrung)
    ys, xs = np.where(mask > 127); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    pad = int(0.04 * (x1 - x0))
    crop = im[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
    cmask = (mask[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] > 127)

    # 3) Perspektive raus (rectify gibt (bild, H, linienzahlen))
    rect, _H, _n = rectify(crop)
    # Maske mitentzerren: grob über erneute Helligkeits-Silhouette der Rektifizierung
    rg = cv2.cvtColor(rect, cv2.COLOR_BGR2GRAY)
    rmask = rg > 8                                          # Entzerrung füllt Rand mit schwarz
    ys2, xs2 = np.where(rmask); ry0, ry1, rx0, rx1 = ys2.min(), ys2.max(), xs2.min(), xs2.max()
    rect = rect[ry0:ry1, rx0:rx1]; Hpx, Wpx = rect.shape[:2]
    pxm = Hpx / a.ridge_m                                   # MASSSTAB: entzerrte Höhe = First (LOD2)

    # 4) Kanten + Bänder/Achsen
    gray = cv2.cvtColor(rect, cv2.COLOR_BGR2GRAY); edges = cv2.Canny(gray, 50, 150)
    rowden = cv2.GaussianBlur(edges.sum(1).astype(float).reshape(-1, 1), (1, 9), 0).ravel()
    colden = cv2.GaussianBlur(edges.sum(0).astype(float).reshape(1, -1), (0, 0), 3).ravel()
    hb = peaks(rowden, 0.04 * Hpx, 0.8); vb = peaks(colden, 0.03 * Wpx, 0.5)
    bands_m = sorted(round((Hpx - b) / pxm, 2) for b in hb)
    n_axes = max(1, len(vb))

    wall_bands = [b for b in bands_m if 1.0 < b < a.ridge_m * 0.62]
    out = {
        "quelle": f"freigestellt+entzerrt {a.foto} + LOD2-Maßstab {pxm:.1f}px/m (Perspektive korrigiert)",
        "ridge_m": a.ridge_m,
        "eg_top_m": round(min(wall_bands), 2) if wall_bands else round(a.ridge_m * 0.26, 2),
        "gallery_m": round(sorted(wall_bands)[len(wall_bands) // 2], 2) if wall_bands else round(a.ridge_m * 0.5, 2),
        "eave_m": round(max(wall_bands), 2) if wall_bands else round(a.ridge_m * 0.54, 2),
        "n_axes": n_axes, "alle_baender_m": bands_m,
    }
    json.dump(out, open(f"{md}/bauplan.json", "w"), indent=1, ensure_ascii=False)

    # 5) BAUPLAN zeichnen
    bp = rect.copy()
    for b in hb:
        cv2.line(bp, (0, b), (Wpx, b), (0, 180, 255), 1)
        cv2.putText(bp, f"{(Hpx-b)/pxm:.1f}m", (4, b - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 180, 255), 1)
    for p in vb:
        cv2.line(bp, (p, 0), (p, Hpx), (200, 200, 200), 1)
    cv2.putText(bp, f"BAUPLAN (entzerrt, Massstab LOD2): {n_axes} Achsen, Traufe {out['eave_m']}m",
                (6, Hpx - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    cv2.imwrite(f"{md}/bauplan.png", bp)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"-> {md}/bauplan.json + bauplan.png")


if __name__ == "__main__":
    main()
