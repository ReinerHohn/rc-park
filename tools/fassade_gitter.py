#!/usr/bin/env python3
"""fassade_gitter.py — Fassade GENERELL in Regionen zerlegen (KEINE hardcodierten Crops).

Ablauf (alles erkannt, nichts fest eingegeben):
  1) GRÜNES Glasurdach segmentieren = eindeutiger Anker → Gebäude-Breite (x-Spanne) + TRAUFE (Dach-Unterkante).
  2) Fassade = unter der Traufe, gleiche x-Spanne, bis zum Boden (unterste rote Zeile).
  3) FENSTERBAND = erste zusammenhängende Zone dunkler Öffnungen direkt unter der Traufe.
  4) Senkrechte Teilung im Fensterband (Spalten-Dunkelprofil) → FENSTER-Spalten (dunkel) vs. Pfeiler/Statuen.
  5) ERKER = die äußersten Spalten (an den Gebäude-Ecken, jenseits des regelmäßigen Fensterrasters).
Gibt relative Regionen (Fensterband, je Fenster, Erker) → die Detail-Detektoren (shape_extract,
fenster_struktur) laufen DARAUF statt auf festen Boxen. Überträgt sich auf jedes Foto.

Lauf: python3 tools/fassade_gitter.py [foto]  → /tmp/fassade_gitter.png + JSON
"""
import sys, json
import numpy as np
import cv2
from scipy import ndimage, signal

FOTO = sys.argv[1] if len(sys.argv) > 1 else "/home/md/git/rc-park/daten/kaufhaus_freiburg/fotos/kh_jm3289.jpg"


def green_roof_bbox(img):
    b, g, r = img[:, :, 0].astype(int), img[:, :, 1].astype(int), img[:, :, 2].astype(int)
    green = ((g >= r-8) & (g > b+4) & (g > 60) & (g < 205)).astype(np.uint8)*255
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))     # ERST öffnen (Nachbar-Fragmente weg) ...
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))  # ... DANN schließen (sonst mergt das Dach mit Nachbardächern)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(green)
    if n < 2:
        return None
    big = 1+int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, _ = st[big]
    return x, y, w, h


def main():
    img = cv2.imread(FOTO); H, W = img.shape[:2]
    rb = green_roof_bbox(img)
    if rb is None:
        print("kein Dach gefunden"); return
    gx, gy, gw, gh = rb
    eave_y = gy+gh                                     # Traufe = Dach-Unterkante
    bx0, bx1 = gx, gx+gw                               # Gebäudebreite = Dachbreite
    # Boden: unterste Zeile, in der die rote Wand über die Gebäudebreite reicht
    r = img[:, bx0:bx1, 2].astype(int); g = img[:, bx0:bx1, 1].astype(int); b = img[:, bx0:bx1, 0].astype(int)
    red = (r > g+15) & (r > b+10) & (r > 55)
    rows_red = np.where(red.mean(1) > 0.25)[0]
    ground_y = rows_red.max() if len(rows_red) else H-1
    # Öffnungs-Dunkel je Zeile in der Fassade (unter Traufe)
    roi = img[eave_y:ground_y, bx0:bx1]
    rr, gg, bb = roi[:, :, 2].astype(int), roi[:, :, 1].astype(int), roi[:, :, 0].astype(int)
    dark = ((rr < 95) & (gg < 95) & (bb < 100)).astype(float)
    rowdark = ndimage.uniform_filter1d(dark.mean(1), 9)
    # FENSTERBAND = erste zusammenhängende Zone mit rowdark über Schwelle, direkt unter der Traufe
    thr = max(0.12, rowdark.max()*0.4)
    on = rowdark > thr
    bands = []
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            bands.append((i, j)); i = j
        else:
            i += 1
    bands = [bd for bd in bands if bd[1]-bd[0] > (ground_y-eave_y)*0.05]
    if not bands:
        print("kein Fensterband gefunden"); return
    wb0, wb1 = bands[0]                                 # oberstes = Fensterband (Arkade ist weiter unten)
    wb0 += eave_y; wb1 += eave_y
    # GEMESSENER Fensterbreiten-Anteil = Dunkel-Anteil im inneren Fensterband (Erker ausgenommen) → win_struct.json
    inn = img[wb0:wb1, int(bx0+gw*0.12):int(bx1-gw*0.12)]
    ir, ig, ib = inn[:, :, 2].astype(int), inn[:, :, 1].astype(int), inn[:, :, 0].astype(int)
    bfrac = float((((ir < 95) & (ig < 95) & (ib < 100)).mean()))
    try:
        ws = json.load(open("/home/md/git/rc-park/modelle/kaufhaus_freiburg/win_struct.json"))
    except Exception:
        ws = {}
    ws["breite_frac"] = round(bfrac, 3)
    json.dump(ws, open("/home/md/git/rc-park/modelle/kaufhaus_freiburg/win_struct.json", "w"), indent=2)
    # GEMESSENE Arkaden-Bogenbreite = Dunkel-Anteil im oberen Arkadenbereich (über den Ständen) → mass.json
    az0 = int(wb1+(ground_y-wb1)*0.15); az1 = int(wb1+(ground_y-wb1)*0.45)
    aroi = img[az0:az1, int(bx0+gw*0.10):int(bx1-gw*0.10)]
    ar, ag, ab = aroi[:, :, 2].astype(int), aroi[:, :, 1].astype(int), aroi[:, :, 0].astype(int)
    abf = float((((ar < 95) & (ag < 95) & (ab < 100)).mean()))
    mp = "/home/md/git/rc-park/modelle/kaufhaus_freiburg/kaufhaus_mass.json"
    try:
        mm = json.load(open(mp))
    except Exception:
        mm = {}
    mm["bogen_breite_frac"] = round(abf, 3)
    json.dump(mm, open(mp, "w"), indent=2)
    # Senkrechte Teilung im Fensterband: Spalten-Dunkelprofil → Fenster (dunkel) vs Pfeiler (hell)
    wband = img[wb0:wb1, bx0:bx1]
    wr, wg, wb_ = wband[:, :, 2].astype(int), wband[:, :, 1].astype(int), wband[:, :, 0].astype(int)
    wdark = (((wr < 95) & (wg < 95) & (wb_ < 100)).mean(0))
    wdark = ndimage.uniform_filter1d(wdark, max(3, gw//80))
    # PFEILER/STATUEN = TÄLER im Dunkelprofil (hell), trennen die dunklen Fenster → Fenster = dazwischen
    valleys, _ = signal.find_peaks(-wdark, prominence=wdark.max()*0.22, distance=gw//12)
    bounds = [int(gw*0.02)] + list(valleys) + [int(gw*0.98)]
    wins = []
    for a, b2 in zip(bounds[:-1], bounds[1:]):
        if b2-a > gw*0.04 and wdark[a:b2].mean() > wdark.max()*0.3:     # nur echte Fenster-Zwischenräume (dunkel)
            wins.append((a/gw, b2/gw))
    # ERKER = die zwei ÄUSSERSTEN Spalten (an den Ecken); regelmäßige Fenster = dazwischen
    erker = []
    if len(wins) >= 3:
        erker = [wins[0], wins[-1]]; fenster = wins[1:-1]
    else:
        fenster = wins
    def rel(x, y): return [round((bx0+x)/W, 3), round(y/H, 3)]
    out = {"foto": FOTO,
           "gebaeude_x_rel": [round(bx0/W, 3), round(bx1/W, 3)],
           "traufe_y_rel": round(eave_y/H, 3), "boden_y_rel": round(ground_y/H, 3),
           "fensterband_y_rel": [round(wb0/H, 3), round(wb1/H, 3)],
           "n_fenster": len(fenster),
           "fenster_x_rel": [[round(bx0/W+a*gw/W, 3), round(bx0/W+b2*gw/W, 3)] for a, b2 in fenster],
           "erker_x_rel": [[round(bx0/W+a*gw/W, 3), round(bx0/W+b2*gw/W, 3)] for a, b2 in erker]}
    json.dump(out, open("/tmp/fassade_gitter.json", "w"), indent=2)
    print(json.dumps(out, indent=2))
    # Visualisierung
    vis = img.copy()
    cv2.rectangle(vis, (bx0, gy), (bx1, ground_y), (255, 255, 0), 3)            # Gebäude
    cv2.line(vis, (bx0, eave_y), (bx1, eave_y), (0, 255, 0), 3)                 # Traufe
    cv2.rectangle(vis, (bx0, wb0), (bx1, wb1), (255, 0, 255), 2)                # Fensterband
    for a, b2 in fenster:
        cv2.rectangle(vis, (int(bx0+a*gw), wb0), (int(bx0+b2*gw), wb1), (0, 200, 255), 3)   # Fenster orange
    for a, b2 in erker:
        cv2.rectangle(vis, (int(bx0+a*gw), gy), (int(bx0+b2*gw), wb1), (0, 0, 255), 4)      # Erker rot
    cv2.imwrite("/tmp/fassade_gitter.png", vis)
    print(f"-> Fenster: {len(fenster)}, Erker: {len(erker)}; /tmp/fassade_gitter.png")


if __name__ == "__main__":
    main()
