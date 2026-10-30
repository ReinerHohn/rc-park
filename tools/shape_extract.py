#!/usr/bin/env python3
"""shape_extract.py — FORM AUTOMATISCH AUS DEM FOTO MESSEN (statt Augenmaß).

Segmentiert ein Bauteil (z.B. Fenster) gegen die rote Wand und extrahiert seine OBER-KONTUR
(Kopfform) als normierte Punkte → die Geometrie wird aus der GEMESSENEN Kontur gebaut, nicht aus
fehleranfälliger Interpretation. Gibt Profil-JSON + Beleg-Overlay (gemessene Kontur eingezeichnet).

Aufruf: /tmp/rv/bin/python tools/shape_extract.py <foto> x0,y0,x1,y1 <profil.json> <overlay.png>
  (Box als Bruchteile 0..1; TIGHT um EIN Bauteil, ohne Nachbar/Statue.)
"""
import sys, json, numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


def main():
    photo, boxs, outj, outp = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    box = [float(v) for v in boxs.split(",")]
    im = Image.open(photo).convert("RGB"); W, H = im.size
    crop = im.crop((int(W*box[0]), int(H*box[1]), int(W*box[2]), int(H*box[3])))
    a = np.asarray(crop).astype(int); ch, cw, _ = a.shape
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    # ROTE Wand: r>>g,b UND g≈b (NICHT Gold, das gelblich ist: g>>b). So bleibt der Goldrahmen Teil des Fensters.
    redwall = (r > g+18) & (r > b+18) & (np.abs(g-b) < 22) & (r > 70)
    win = ndimage.binary_closing(~redwall, iterations=2)        # Fenster = Goldrahmen + dunkles Glas
    lbl, n = ndimage.label(win)                                 # größte zusammenhängende Insel = das Fenster
    if n == 0:
        print("kein Fenster segmentiert"); return
    big = 1 + int(np.argmax(ndimage.sum(np.ones_like(lbl), lbl, range(1, n+1))))
    win = ndimage.binary_fill_holes(lbl == big)
    cols = np.where(win.any(0))[0]; x0, x1 = int(cols.min()), int(cols.max())
    top = {}; bot = {}
    for x in range(x0, x1+1):
        ys = np.where(win[:, x])[0]
        if len(ys):
            top[x] = int(ys.min()); bot[x] = int(ys.max())
    sill_y = max(bot.values()); top_y = min(top.values()); Hw = max(1, sill_y-top_y)
    xmid = (x0+x1)/2; wpx = x1-x0
    profile = [((x-xmid)/wpx, (sill_y-top[x])/Hw) for x in sorted(top)]   # Ober-Kontur normiert
    # ASPEKT ROBUST über Projektionen (NICHT aus der fragilen Segment-BBox: die bricht auf/klippt → früher
    # fälschlich ~0.97 statt echt ~0.45). Fensterfläche je Zeile/Spalte; Ausdehnung wo Anteil > Schwelle.
    rowf = win.mean(1); colf = win.mean(0)
    rr = np.where(rowf > 0.35)[0]; cc = np.where(colf > 0.35)[0]
    aspect_robust = (float(cc.max()-cc.min()) / max(1, float(rr.max()-rr.min()))) if len(rr) > 2 and len(cc) > 2 else wpx/Hw
    json.dump({"profile_top": profile, "aspect_w_h": round(aspect_robust, 3), "aspect_segment": round(wpx/Hw, 3)}, open(outj, "w"))
    # Beleg: ganze gemessene Außenkontur als durchgehende LINIE (oben grün, Seiten/Sohle blau)
    big = crop.resize((cw*3, ch*3)); d = ImageDraw.Draw(big)
    topline = [(x*3, top[x]*3) for x in sorted(top)]
    d.line(topline, fill=(0, 255, 0), width=4)                           # gemessene Kopf-Kontur
    left = [(x*3, bot[x]*3) for x in sorted(bot)]
    d.line(left, fill=(0, 140, 255), width=3)                            # Unterkante/Sohle
    for xx in (x0, x1):
        d.line([(xx*3, top[xx]*3), (xx*3, bot[xx]*3)], fill=(0, 140, 255), width=3)
    big.save(outp)
    print(f"aspect w/h = {wpx/Hw:.2f}  | Konturpunkte: {len(profile)}  -> {outj}, {outp}")


if __name__ == "__main__":
    main()
