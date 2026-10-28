#!/usr/bin/env python3
"""erker_finden.py — ERKER robust lokalisieren über die HELMSPITZEN (ragen über den First).

Eindeutiges, generelles Signal: die bunten Spitzhelme der Eck-Erker sind die ZWEI HÖCHSTEN Punkte
der Gebäude-Oberkante (Silhouette) an den Ecken — höher als die First-Plateau-Linie in der Mitte.
Also: Oberkante je Spalte (erste Nicht-Himmel-Zeile) → zwei Gipfel an den Rändern = Erker-x-Mitten.
Erker-BREITE = Breite der „über dem First" ragenden Struktur an jedem Gipfel. Keine hardcodierten Crops.

Lauf: python3 tools/erker_finden.py [foto]  → /tmp/erker_fund.png + JSON (x-Mitte, Breite, Helmhöhe)
"""
import sys, json
import numpy as np
import cv2
from scipy import ndimage, signal


def green_roof_bbox(img):
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    m = (((g >= r-8) & (g > b+4) & (g > 60) & (g < 205)).astype(np.uint8))*255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(m)
    big = 1+int(np.argmax(st[1:, cv2.CC_STAT_AREA])); x, y, w, h, _ = st[big]
    return x, y, w, h


def main():
    FOTO = sys.argv[1] if len(sys.argv) > 1 else "/home/md/git/rc-park/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg"
    img = cv2.imread(FOTO); H, W = img.shape[:2]
    gx, gy, gw, gh = green_roof_bbox(img)                       # Gebäude-x-Spanne aus grünem Dach
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV); sat = hsv[:, :, 1].astype(int); val = hsv[:, :, 2].astype(int)
    sky = (val > 150) & (sat < 45)                             # heller, entsättigter Himmel
    notsky = ~sky
    # Oberkante je Spalte (erste Nicht-Himmel-Zeile) im Gebäude-x-Bereich, nur oberes Drittel absuchen
    top = np.full(gw, gy+gh, float)
    y_search = slice(max(0, gy-int(gh*1.2)), gy+gh)
    for i in range(gw):
        col = notsky[y_search, gx+i]
        ys = np.where(col)[0]
        if len(ys):
            top[i] = (y_search.start+ys.min())
    height = -ndimage.uniform_filter1d(top, max(3, gw//80))    # höher = kleineres y
    # Gipfel = Helmspitzen; die über dem Median (First-Plateau) + an den Rändern
    base = np.median(height)
    pk, props = signal.find_peaks(height, prominence=(height.max()-base)*0.3, distance=gw//8)
    pk = sorted(pk, key=lambda i: -(height[i]-base))[:4]        # stärkste Gipfel
    pk = sorted(pk)
    erker = []
    for i in pk:
        # Breite der „über dem First" ragenden Struktur um den Gipfel (height > base)
        l = i
        while l > 0 and height[l] > base:
            l -= 1
        rr = i
        while rr < gw-1 and height[rr] > base:
            rr += 1
        wpk = rr-l
        if wpk < gw*0.02:
            continue
        erker.append({"x_mitte_rel": round((gx+i)/W, 3),
                      "breite_rel_gebaeude": round(wpk/gw, 3),
                      "breite_m": round(wpk/gw*18.5, 1),
                      "helm_ueber_first_rel": round((base-height[i])/gh if gh else 0, 2)})
    # nur die zwei äußersten (Eck-Erker)
    if len(erker) > 2:
        erker = [erker[0], erker[-1]]
    out = {"foto": FOTO, "n_erker": len(erker), "erker": erker}
    json.dump(out, open("/tmp/erker_fund.json", "w"), indent=2)
    print(json.dumps(out, indent=2))
    vis = img.copy()
    cv2.line(vis, (gx, int(gy-base-0)), (gx+gw, int(gy-base-0)), (255, 255, 0), 1)
    for e in erker:
        xc = int(e["x_mitte_rel"]*W); ww = int(e["breite_rel_gebaeude"]*gw)
        cv2.rectangle(vis, (xc-ww//2, gy-int(gh*0.9)), (xc+ww//2, gy+gh), (0, 0, 255), 4)
        cv2.circle(vis, (xc, int(top[xc-gx]) if 0 <= xc-gx < gw else gy), 10, (0, 255, 0), -1)
    cv2.imwrite("/tmp/erker_fund.png", vis)
    print(f"-> {len(erker)} Erker über Helmspitzen; /tmp/erker_fund.png")


if __name__ == "__main__":
    main()
