#!/usr/bin/env python3
"""kanten_abgleich.py — ALLE markanten KANTEN Foto↔Modell überlagern & Lücken finden (Detail-Netz).

Warum: Zähl-/Proportions-Checks übersehen LOKALE Kantenformen (z.B. gestufter vs. gerader Querbalken,
Erker-Absätze, Gesims-Stufen). Dieses Werkzeug nimmt einen Bildausschnitt aus Foto + den DECKUNGSGLEICH
zugeschnittenen Modell-Render, rechnet beide auf gleiche Größe, extrahiert die Kanten (Canny) und
ÜBERLAGERT sie: Foto-Kante ROT, Modell-Kante GRÜN, Deckung GELB. Wo ROT ohne Gelb = Kante im Foto, die
dem Modell FEHLT → genau die Details, die bisher durchrutschten. Gibt Overlay + Recall/Precision + die
Rasterzellen mit den größten fehlenden Kanten.

Lauf: /tmp/rv/bin/python tools/kanten_abgleich.py <foto_crop.png> <modell_crop.png> [out.png] [--grid 6]
"""
import sys
import numpy as np
from PIL import Image
import cv2
from scipy import ndimage


def edges(img, size, structural=True):
    g = np.asarray(img.convert("L").resize(size)).astype(np.uint8)
    # STRUKTUR statt Textur: moderat glätten → Waben/Schuppen (feine, hochfrequente Muster) verschwinden,
    # große Kanten (Rahmen, Kämpfer, Pfosten, Bogenkopf, Bänder) bleiben. Blur-Stärke skaliert mild mit Größe.
    kb = 7 if structural else 3
    g = cv2.GaussianBlur(g, (kb, kb), 0)
    m = np.median(g); lo = int(max(0, 0.66*m)); hi = int(min(255, 1.33*m))
    return cv2.Canny(g, lo, hi) > 0


def main():
    fp, mp = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else "/tmp/kanten_overlay.png"
    grid = int(sys.argv[sys.argv.index("--grid")+1]) if "--grid" in sys.argv else 6
    size = (360, 480)
    pe = edges(Image.open(fp), size); me = edges(Image.open(mp), size)
    tol = 3                                                        # Kanten gelten als deckungsgleich bis 3 px
    md = ndimage.distance_transform_edt(~me); pd = ndimage.distance_transform_edt(~pe)
    recall = float((pe & (md <= tol)).sum()) / max(1, pe.sum())    # Foto-Kanten, die das Modell trifft
    prec = float((me & (pd <= tol)).sum()) / max(1, me.sum())      # Modell-Kanten, die das Foto trifft
    # Overlay-Bild
    H, W = size[1], size[0]; ov = np.zeros((H, W, 3), np.uint8)
    base = np.asarray(Image.open(fp).convert("L").resize(size))[:, :, None]//3
    ov += base.astype(np.uint8)
    ov[pe] = [255, 40, 40]                                         # Foto-Kante ROT
    ov[me] = [40, 220, 40]                                         # Modell-Kante GRÜN
    ov[pe & (md <= tol)] = [240, 240, 40]                          # Deckung GELB
    # fehlende Kanten (Foto-Kante ohne Modell-Nähe) je Rasterzelle
    missing = pe & (md > tol)
    cellH, cellW = H//grid, W//grid; worst = []
    for j in range(grid):
        for i in range(grid):
            c = missing[j*cellH:(j+1)*cellH, i*cellW:(i+1)*cellW].sum()
            worst.append((int(c), i, j))
    worst.sort(reverse=True)
    Image.fromarray(ov).save(out)
    print(f"Kanten-Abgleich {fp}  vs  {mp}")
    print(f"  Recall (Foto-Kanten vom Modell getroffen) = {recall:.2f}")
    print(f"  Precision (Modell-Kanten im Foto belegt)  = {prec:.2f}")
    print(f"  Overlay: {out}  (ROT=Foto fehlt im Modell, GRÜN=Modell-Extra, GELB=Deckung)")
    tot = missing.sum()
    print(f"  größte FEHLENDE-Kanten-Zellen (von {grid}x{grid}):")
    for c, i, j in worst[:4]:
        if c > tot*0.06:
            print(f"    Zelle (Spalte {i}, Zeile {j}): {c} fehlende Kantenpixel  ← Detail prüfen")
    verdict = "PASS" if recall >= 0.6 else "WARN: viele Foto-Kanten fehlen im Modell"
    print(f"  → {verdict}")


if __name__ == "__main__":
    main()
