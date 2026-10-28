#!/usr/bin/env python3
"""fenster_detail_check.py — FEINE interne Kanten eines Fensters Foto↔Modell (Pfosten/Kämpfer/Bogenkopf).

Das Farbzonen-Gate (kanten_abgleich) sieht nur Zonen-UMRISSE, nicht die INTERNEN Linien → degenerierte
oder zu kurze Pfosten rutschten durch. Hier: je EINE Fenster-Einheit aus Foto + Modell tight-croppen,
auf gleiche Größe, Canny mit moderatem Blur (Waben weg, Pfosten/Kämpfer/Rahmen bleiben), überlagern,
Recall pro HORIZONTALEM BAND (oben/Mitte/unten) → fehlt oben Kante = Pfosten/Bogen reicht nicht hoch.

Lauf: python3 tools/fenster_detail_check.py <foto_unit.png> <modell_unit.png> [out.png]
"""
import sys
import numpy as np
from PIL import Image
import cv2
from scipy import ndimage


def edges(img, size):
    g = np.asarray(img.convert("L").resize(size)).astype(np.uint8)
    g = cv2.GaussianBlur(g, (5, 5), 0)
    m = np.median(g)
    return cv2.Canny(g, int(max(0, 0.6*m)), int(min(255, 1.4*m))) > 0


def main():
    fp, mp = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else "/tmp/fenster_detail.png"
    size = (240, 360); tol = 4
    pe = edges(Image.open(fp), size); me = edges(Image.open(mp), size)
    md = ndimage.distance_transform_edt(~me)
    bands = {"oben (Bogenkopf)": (0.0, 0.40), "Mitte (Pfosten/Kämpfer)": (0.40, 0.75), "unten (Sohlbank)": (0.75, 1.0)}
    H = size[1]
    print(f"Fenster-Detail {fp} vs {mp}")
    worst = 1.0
    for name, (a, b) in bands.items():
        y0, y1 = int(H*a), int(H*b)
        pb = pe[y0:y1]; rec = float((pb & (md[y0:y1] <= tol)).sum())/max(1, pb.sum())
        worst = min(worst, rec)
        flag = "  <-- Kanten FEHLEN" if rec < 0.5 else ""
        print(f"  {name:<26} Recall {rec:.2f}{flag}")
    ov = (np.asarray(Image.open(fp).convert("L").resize(size))[:, :, None]//3).repeat(3, 2).astype(np.uint8)
    ov[pe] = [255, 40, 40]; ov[me] = [40, 220, 40]; ov[pe & (md <= tol)] = [240, 240, 40]
    Image.fromarray(ov).save(out)
    print(f"  Overlay: {out}  (ROT=Foto fehlt im Modell) → {'PASS' if worst>=0.5 else 'WARN'}")


if __name__ == "__main__":
    main()
