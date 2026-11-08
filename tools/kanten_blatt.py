#!/usr/bin/env python3
"""kanten_blatt.py - Sichtblatt S10: Foto-Ausschnitt | P1 | P2 | P3 | P4 | weiches Mittel | Abstimmung k=2,3,4 (Skelette) nebeneinander.
Aufruf: kanten_blatt.py --bild FOTO.jpg --karten ORDNER --name 004 --ausschnitt x0,y0,x1,y1 --aus BLATT.jpg [--skala 3]
Karten kommen aus kanten_pipelines.py (<karten>/p1..p4/<name>.png). Keine Schwellen ausser SCHWELLE 0,5 (wie test_kanten_pipelines)."""
import argparse, os, sys
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kanten_pipelines as KP
import test_kanten_pipelines as T


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bild", required=True); ap.add_argument("--karten", required=True); ap.add_argument("--name", required=True)
    ap.add_argument("--ausschnitt", help="x0,y0,x1,y1 in Bildpixeln"); ap.add_argument("--aus", required=True); ap.add_argument("--skala", type=float, default=2.0)
    a = ap.parse_args(argv)
    bgr = cv2.imread(a.bild); H, W = bgr.shape[:2]
    x0, y0, x1, y1 = [int(v) for v in a.ausschnitt.split(",")] if a.ausschnitt else (0, 0, W, H)
    km = {p: KP.laden(os.path.join(a.karten, p, a.name + ".png")) for p in KP.PIPES}
    sk = [T.skelett(km[p]) for p in KP.PIPES]
    mitt = np.mean([km[p] for p in KP.PIPES], 0)
    ansichten = [("Foto", bgr)] + [(f"{p} {KP.NAMEN[p]}", cv2.cvtColor((km[p] * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)) for p in KP.PIPES]
    ansichten.append(("weich Mittel", cv2.cvtColor((mitt * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)))
    for k in (2, 3, 4):
        ansichten.append((f"Stimmen k={k}", cv2.cvtColor(cv2.dilate(T.abstimmung(sk, k).astype(np.uint8) * 255, np.ones((2, 2), np.uint8)), cv2.COLOR_GRAY2BGR)))
    t = []
    for n, im in ansichten:
        c = cv2.resize(im[y0:y1, x0:x1], None, fx=a.skala, fy=a.skala, interpolation=cv2.INTER_NEAREST if n != "Foto" else cv2.INTER_CUBIC)
        c = c.copy(); cv2.putText(c, n, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2); t.append(c)
    while len(t) % 4: t.append(np.zeros_like(t[0]))
    cv2.imwrite(a.aus, np.vstack([np.hstack(t[i:i + 4]) for i in range(0, len(t), 4)]))
    print("geschrieben", a.aus)


if __name__ == "__main__":
    main()
