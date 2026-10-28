#!/usr/bin/env python3
"""fenster_struktur.py — Fenster-GLIEDERUNG aus dem Foto ERKENNEN (kein Hardcoding).

Detektiert per Kanten/Helligkeit die goldenen Stege eines Fensters:
  - VERTIKALE Pfosten (Mullions) → Anzahl + x-Lagen (zentriert -0.5..0.5, Außenrahmen ausgenommen)
  - HORIZONTALE Kämpfer (Transoms) → Anzahl + z-Lagen (0=Sohlbank .. 1=Sturz)
  - Waben-Zellgröße (Hex) relativ zur Fensterbreite (FFT der Bleistege)
Schreibt modelle/<bau>/win_struct.json. Der Generator LIEST das (kein hartkodierter Pfosten).

Lauf: python3 tools/fenster_struktur.py [foto] [x0,y0,x1,y1] [out.json]
"""
import sys, json
import numpy as np
import cv2
from scipy import ndimage, signal

FOTO = sys.argv[1] if len(sys.argv) > 1 else "/home/md/git/rc-park/daten/kaufhaus_freiburg/fotos/kh_fenster.jpg"
BOX = [float(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else [0.435, 0.37, 0.575, 0.63]
OUT = sys.argv[3] if len(sys.argv) > 3 else "/home/md/git/rc-park/modelle/kaufhaus_freiburg/win_struct.json"


def main():
    img = cv2.imread(FOTO); H, W = img.shape[:2]
    x0, y0, x1, y1 = [int(v) for v in (W*BOX[0], H*BOX[1], W*BOX[2], H*BOX[3])]
    win = img[y0:y1, x0:x1]; wh, ww = win.shape[:2]
    b, g, r = win[:, :, 0].astype(int), win[:, :, 1].astype(int), win[:, :, 2].astype(int)
    gold = ((r > 110) & (g > 85) & (r > b+25) & (g > b+10)).astype(float)
    dark = ((r < 95) & (g < 95) & (b < 100)).astype(float)       # Glas → Fensterausdehnung

    # VERTIKALE Pfosten: Spalten mit viel Gold im mittleren Höhenband; Außenrand (links/rechts) weg
    band = gold[int(wh*0.28):int(wh*0.9)]
    cp = ndimage.uniform_filter1d(band.mean(0), max(3, ww//50))
    cpk, _ = signal.find_peaks(cp, height=cp.max()*0.45, distance=ww//12)
    mull = [p/ww for p in cpk if 0.12 < p/ww < 0.88]             # innere Pfosten (Außenrahmen 0/1 raus)
    # HORIZONTALE Kämpfer: Zeilen mit viel Gold; oberen Bogen-Rahmen (z-rel<0.2) ausnehmen
    rp = ndimage.uniform_filter1d(gold[:, int(ww*0.12):int(ww*0.88)].mean(1), max(3, wh//50))
    rpk, _ = signal.find_peaks(rp, height=rp.max()*0.45, distance=wh//12)
    # Fensterausdehnung vertikal aus dunkler Glasfläche
    drow = dark.mean(1); gy = np.where(drow > drow.max()*0.4)[0]
    gtop, gbot = (gy.min(), gy.max()) if len(gy) else (0, wh)
    trans = [1-(p-gtop)/max(1, gbot-gtop) for p in rpk if 0.2 < p/wh < 0.95]   # 0=Sohlbank..1=Sturz

    # Hex-Zellgröße: FFT der dunklen Bleistege in einer reinen Glaszelle
    cell = cv2.cvtColor(win[int(wh*0.55):int(wh*0.9), int(ww*0.05):int(ww*0.28)], cv2.COLOR_BGR2GRAY).astype(float)
    prof = cell.mean(1)-cell.mean(1).mean(); F = np.abs(np.fft.rfft(prof*np.hanning(len(prof)))); F[:2] = 0
    per = 1/np.fft.rfftfreq(len(prof))[np.argmax(F)] if np.argmax(F) else wh*0.1
    hexR_rel = (per/wh)/np.sqrt(3)                               # Reihenabstand 2*hh=R*sqrt3 → R

    # Pfosten-Lagen symmetrisieren (Fenster IST symmetrisch — Anzahl bleibt wie erkannt, kein Hardcoding)
    mc = sorted(m-0.5 for m in mull); nM = len(mc)
    if nM:
        mags = sorted(abs(v) for v in mc)
        if nM % 2 == 0:                                         # paarweise ±
            pair = [np.mean(mags[2*i:2*i+2]) for i in range(nM//2)]
            msym = sorted([-p for p in pair]+[p for p in pair])
        else:
            pair = [0.0]+[np.mean(mags[1+2*i:3+2*i]) for i in range((nM-1)//2)]
            msym = sorted([-p for p in pair if p > 0]+[0.0]+[p for p in pair if p > 0])
    else:
        msym = []
    out = {"mullions_xrel_centered": [round(float(v), 3) for v in msym],
           "n_mullions": len(mull),
           "transoms_zrel": sorted(round(t, 3) for t in trans),
           "n_transoms": len(trans),
           "hex_R_rel_breite": round(float(hexR_rel), 4),
           "_quelle": f"fenster_struktur.py aus {FOTO} box {BOX}"}
    json.dump(out, open(OUT, "w"), indent=2)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
