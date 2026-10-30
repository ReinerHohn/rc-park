#!/usr/bin/env python3
"""ortho_drape.py — Oberfläche aus Daten: LGL-Orthophoto (DOP20) deckungsgleich zum
Gelände-Modell zuschneiden und als MASSSTABSgenauer Druck-Bogen ausgeben. Über die Gips-Haut
gelegt = Gras/Wald/Fels/Feld/Straße/Wasser ohne Anmalen (der echte Ort, farbgenau).

Deckungsgleich zum terrain_eggcrate-Fenster (gleiche r0/r1/c0/c1 + gleicher Maßstab).

Nutzung:
  python3 tools/ortho_drape.py --r0 470 --r1 640 --c0 3310 --c1 3570 --mm 0.78125 \
      --tile 425_5308 --out modelle/hoellental_geruest_a3/ortho
  (--tile = LGL-2km-Paket, wird geladen; oder --dop <lokale .tif>)
"""
import os, sys, argparse, zipfile, urllib.request, glob
import numpy as np

TFW_DEFAULT = "daten/hoellental/dgm025_32_426_5309_1_bw_2017.tfw"
DOP_URL = "https://opengeodata.lgl-bw.de/data/dop20/dop20rgb_32_{tile}_2_bw.zip"

def utm_window(tfw, r0, r1, c0, c1):
    A, D, B, E, C, F = [float(x) for x in open(tfw)]   # Pixel 0.25, Ursprung E=C N=F
    E0 = C + c0 * A; E1 = C + c1 * A
    N_top = F + r0 * E; N_bot = F + r1 * E             # E ist negativ (-0.25)
    return min(E0, E1), max(E0, E1), min(N_top, N_bot), max(N_top, N_bot)

def get_dop_tif(a):
    if a.dop and os.path.exists(a.dop):
        return a.dop
    os.makedirs(a.out, exist_ok=True)
    zp = os.path.join(a.out, f"dop20_{a.tile}.zip")
    if not os.path.exists(zp):
        url = DOP_URL.format(tile=a.tile)
        print(f"Lade DOP-Paket ({a.tile}) … {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "modellbau/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(zp, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b: break
                f.write(b)
        print(f"  geladen: {os.path.getsize(zp)//1024//1024} MB")
    ddir = os.path.join(a.out, "dop_extract")
    with zipfile.ZipFile(zp) as z:
        z.extractall(ddir)
    tifs = glob.glob(os.path.join(ddir, "**", "*.tif"), recursive=True) + \
           glob.glob(os.path.join(ddir, "**", "*.jp2"), recursive=True)
    return tifs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r0", type=int, required=True); ap.add_argument("--r1", type=int, required=True)
    ap.add_argument("--c0", type=int, required=True); ap.add_argument("--c1", type=int, required=True)
    ap.add_argument("--mm", type=float, default=0.78125, help="Modell-mm je DGM-Zelle (0.78125=50%, 1.5625=true-N, 0.390625=25%)")
    ap.add_argument("--tfw", default=TFW_DEFAULT, help="Georef des DGM (gleiche Kachel)")
    ap.add_argument("--tile", default="425_5308", help="LGL-2km-DOP-Paket E_N (E ungerade, N gerade)")
    ap.add_argument("--dop", default="", help="lokale DOP-GeoTIFF statt Download")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--out", default="/tmp/ortho")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    import rasterio
    from rasterio.windows import from_bounds
    import cv2

    E0, E1, N0, N1 = utm_window(a.tfw, a.r0, a.r1, a.c0, a.c1)
    print(f"Modell-Fenster UTM: E[{E0:.0f}..{E1:.0f}] N[{N0:.0f}..{N1:.0f}]  ({E1-E0:.0f}×{N1-N0:.0f} m real)")
    w_mm = (a.c1 - a.c0) * a.mm; h_mm = (a.r1 - a.r0) * a.mm
    print(f"Modell-Druckgröße: {w_mm:.0f}×{h_mm:.0f} mm")

    cands = get_dop_tif(a)
    if isinstance(cands, str): cands = [cands]
    img = None
    for tif in cands:
        try:
            with rasterio.open(tif) as ds:
                b = ds.bounds
                if not (b.left <= E0 and b.right >= E1 and b.bottom <= N0 and b.top >= N1):
                    continue
                win = from_bounds(E0, N0, E1, N1, ds.transform)
                arr = ds.read([1, 2, 3], window=win)       # (3,H,W)
                img = np.transpose(arr, (1, 2, 0)).astype(np.uint8)
                print(f"DOP-Kachel: {os.path.basename(tif)}  Crop {img.shape[1]}×{img.shape[0]} px")
                break
        except Exception as e:
            continue
    if img is None:
        print("!! Keine DOP-Kachel deckt das Fenster. Kandidaten:", [os.path.basename(c) for c in cands][:6]); return

    img = img[::-1]                                        # Modell +y=Nord (wie DGM-Flip)
    px_w = int(round(w_mm * a.dpi / 25.4)); px_h = int(round(h_mm * a.dpi / 25.4))
    out = cv2.resize(img, (px_w, px_h), interpolation=cv2.INTER_AREA)
    # Maßstabsbalken 10 mm + Eck-Schnittmarken
    bar = int(round(10 * a.dpi / 25.4)); m = int(0.02 * a.dpi)
    out[px_h - m - 6:px_h - m, m:m + bar] = (0, 0, 0)
    for (yy, xx) in [(0, 0), (0, px_w - 1), (px_h - 1, 0), (px_h - 1, px_w - 1)]:
        cv2.drawMarker(out, (xx, yy), (0, 0, 0), cv2.MARKER_CROSS, 20, 2)
    outfn = os.path.join(a.out, "ortho_drape.png")
    cv2.imwrite(outfn, out)
    print(f"-> {outfn}  ({px_w}×{px_h}px @ {a.dpi}dpi = {w_mm:.0f}×{h_mm:.0f}mm bei 100% Druck)")
    print(f"   10-mm-Balken unten links zur Druck-Kontrolle. Über die Gips-Haut legen.")

if __name__ == "__main__":
    main()
