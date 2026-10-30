#!/usr/bin/env python3
"""fassade_vermessen.py — ERST MESSEN, DANN BAUEN (Methode die der User fordert:
„alle Kanten erkennen, Abstände messen, dann entscheiden welche Objekte man reinsetzt").

Statt Bauteile nach Gefühl zu platzieren und sich korrigieren zu lassen:
  1) Fassade segmentieren (rote Wand / dunkle Öffnungen / Gold).
  2) WAAGRECHTE Kanten = die Höhen-Bänder (Boden, Bogenkämpfer, Bogenscheitel, Brüstung, Sohlbank,
     Fenstersturz, Traufe, First) aus dem Zeilenprofil der Öffnungs-Dichte messen.
  3) SENKRECHTE Kanten je Band = Pfeiler/Fenster-Teilungen → Anzahl + Abstände messen.
  4) Overlay (gemessene Linien eingezeichnet) + JSON (relative Höhen 0..1, Zählungen) ausgeben.

Lauf: /tmp/rv/bin/python tools/fassade_vermessen.py [foto] [x0,y0,x1,y1]
"""
import sys, json
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage, signal

FOTO = sys.argv[1] if len(sys.argv) > 1 else "/home/md/git/rc-park/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg"
BOX = [float(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else [0.17, 0.02, 0.83, 0.99]


def segment(a):
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    red = (r > g+12) & (r > b+10) & (r > 60)                 # rote Sandstein-Wand
    dark = (r < 90) & (g < 90) & (b < 95)                    # dunkle Öffnungen (Glas/Durchgang)
    gold = (r > 120) & (g > 95) & (b < 110) & (r > b+35) & (np.abs(r.astype(int)-g) < 60)
    return red, dark, gold


def h_edges(opening_frac, k=7):
    """waagrechte Kanten = Extrema der Ableitung der Öffnungs-Dichte je Zeile."""
    s = ndimage.uniform_filter1d(opening_frac, k)
    d = np.abs(np.gradient(s))
    pk, _ = signal.find_peaks(d, distance=len(d)//40, prominence=d.max()*0.12)
    return sorted(pk)


def v_count(mask_band):
    """senkrechte Teilung: Spalten-Dichte der Öffnung → Täler (=Pfeiler) trennen die Öffnungen."""
    col = mask_band.mean(0)
    col = ndimage.uniform_filter1d(col, max(3, len(col)//120))
    thr = col.max()*0.5
    openings = col > thr
    # zähle zusammenhängende Öffnungs-Segmente
    lbl, n = ndimage.label(openings)
    centers = [float(np.mean(np.where(lbl == i)[0]))/len(col) for i in range(1, n+1)
               if (lbl == i).sum() > len(col)*0.02]
    return len(centers), centers


def main():
    im = Image.open(FOTO).convert("RGB"); W, H = im.size
    crop = im.crop((int(W*BOX[0]), int(H*BOX[1]), int(W*BOX[2]), int(H*BOX[3])))
    a = np.asarray(crop).astype(int); ch, cw, _ = a.shape
    red, dark, gold = segment(a)
    opening = dark.mean(1)                                   # Anteil dunkler Öffnung je Zeile
    redrow = red.mean(1)
    edges = h_edges(opening)
    # Bänder benennen anhand typischer Reihenfolge (oben=0): Traufe, Fenstersturz, Sohlbank, Brüstung, Bogenscheitel, Bogenkämpfer, Boden
    levels = {f"kante_{i}": round(y/ch, 3) for i, y in enumerate(edges)}
    # Arkade = unteres Drittel: Bögen zählen
    y_lo = int(ch*0.66); band = dark[y_lo:ch, :]
    narch, acent = v_count(band)
    # Fensterband = mittleres Drittel
    y0, y1 = int(ch*0.40), int(ch*0.62); wband = dark[y0:y1, :]
    nwin, wcent = v_count(wband)
    out = {"foto": FOTO, "box": BOX, "h_kanten_rel": [round(y/ch, 3) for y in edges],
           "arkade_boegen": narch, "arkade_zentren_relx": [round(c, 3) for c in acent],
           "fensterband_oeffnungen": nwin, "fenster_zentren_relx": [round(c, 3) for c in wcent]}
    json.dump(out, open("/tmp/fassade_mass.json", "w"), indent=2)
    # Overlay zeichnen
    big = crop.resize((cw*2, ch*2)); d = ImageDraw.Draw(big)
    for y in edges:
        d.line([(0, y*2), (cw*2, y*2)], fill=(0, 255, 0), width=3)
        d.text((6, y*2-14), f"{y/ch:.2f}", fill=(0, 255, 0))
    for c in acent:
        d.line([(c*cw*2, ch*2*0.70), (c*cw*2, ch*2)], fill=(255, 120, 0), width=3)
    for c in wcent:
        d.line([(c*cw*2, ch*2*0.40), (c*cw*2, ch*2*0.62)], fill=(0, 160, 255), width=2)
    big.save("/tmp/fassade_mass.png")
    print("WAAGRECHTE KANTEN (rel. Höhe 0=oben..1=unten):", out["h_kanten_rel"])
    print(f"ARKADE: {narch} Öffnungen bei relx {out['arkade_zentren_relx']}")
    print(f"FENSTERBAND: {nwin} Öffnungen bei relx {out['fenster_zentren_relx']}")
    print("-> /tmp/fassade_mass.png (Kanten/Teilungen eingezeichnet), /tmp/fassade_mass.json")


if __name__ == "__main__":
    main()
