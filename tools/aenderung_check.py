#!/usr/bin/env python3
"""aenderung_check.py — ÄNDERUNGS-WÄCHTER gegen Regressionen.

Harte Lehre (teuer, mehrfach): ich habe gute Stände kaputtgeändert und „verbessert" behauptet,
 OHNE den neuen Render gegen den VORHER-Stand UND das Foto zu prüfen. Dieser Wächter erzwingt
genau das: er legt VORHER | NACHHER | WAS-GEÄNDERT (Heatmap) | FOTO nebeneinander und lokalisiert
die grösste Änderung, damit man sie NICHT übersehen kann. Pflicht nach JEDER Modell-Änderung.

  python3 tools/aenderung_check.py <vorher_render.png> <nachher_render.png> <foto.jpg> <out.png>
"""
import argparse
import numpy as np
import cv2


def _autocrop(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    m = g < 245
    ys, xs = np.where(m)
    if not len(xs):
        return bgr
    return bgr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vorher"); ap.add_argument("nachher"); ap.add_argument("foto"); ap.add_argument("out")
    a = ap.parse_args()
    A = _autocrop(cv2.imread(a.vorher)); B = _autocrop(cv2.imread(a.nachher))
    H = 560
    def rs(x): return cv2.resize(x, (int(x.shape[1] * H / x.shape[0]), H))
    A = rs(A); B = rs(B)
    Bw = cv2.resize(B, (A.shape[1], A.shape[0]))

    diff = np.abs(A.astype(int) - Bw.astype(int)).sum(2).astype(np.uint8)
    changed = (diff > 40).astype(np.uint8)
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    frac = float(changed.mean())
    heat = cv2.applyColorMap((np.clip(diff, 0, 120) * 2).astype(np.uint8), cv2.COLORMAP_JET)
    heat = cv2.addWeighted(A, 0.45, heat, 0.55, 0)
    # grösste Änderungsregion einrahmen
    n, lab, st, _ = cv2.connectedComponentsWithStats(changed)
    region = None
    if n > 1:
        i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        x, y, w, h, _ = st[i]
        cv2.rectangle(heat, (x, y), (x + w, y + h), (255, 255, 255), 3)
        region = (x, y, w, h)

    foto = rs(_autocrop(cv2.imread(a.foto)) if cv2.imread(a.foto) is not None else A)
    foto = cv2.resize(foto, (A.shape[1], A.shape[0]))
    panels = [("VORHER", A), ("NACHHER", B), ("WAS GEAENDERT", heat), ("FOTO", foto)]
    labeled = []
    for name, img in panels:
        c = img.copy(); cv2.rectangle(c, (0, 0), (c.shape[1], 26), (255, 255, 255), -1)
        cv2.putText(c, name, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        labeled.append(c)
    board = np.hstack(labeled)
    cv2.imwrite(a.out, board)
    print(f"Geänderte Fläche: {frac*100:.1f}%  |  grösste Änderungsregion: {region}")
    print("-> VOR dem 'verbessert'-Sagen: WAS-GEAENDERT-Heatmap anschauen und gegen FOTO prüfen,")
    print("   ob die Änderung die Realität wirklich BESSER trifft (nicht nur 'anders').")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
