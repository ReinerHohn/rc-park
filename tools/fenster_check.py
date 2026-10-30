#!/usr/bin/env python3
"""fenster_check.py — prüft das FENSTER-SEITENVERHÄLTNIS (Höhe:Breite) Modell vs. Foto.

Diese Prüfung fehlte bisher: alle alten Checker verglichen LAGE/Offenheit/Anzahl/Silhouette, aber NIE
das Fenster-Seitenverhältnis → gedrungene Fenster (aspect 0.97 statt echt 0.45) rutschten durch.
Robuste Messung über PROJEKTIONEN (nicht fragile Segmentierung): im Fensterband je Fenster-Einheit
die Fensterfläche (Gold+dunkles Glas bzw. im Render: nicht-Wand) → Breite/Höhe. PASS wenn nah am Foto.

Lauf: /tmp/rv/bin/python tools/fenster_check.py   (optional: --tol 0.12)
"""
import os, sys, json, importlib.util
os.environ["PYOPENGL_PLATFORM"] = "egl"
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = "/home/md/git/rc-park"
PHOTO = f"{ROOT}/daten/kaufhaus_freiburg/fotos/kh_fenster.jpg"
TOL = 0.12
if "--tol" in sys.argv:
    TOL = float(sys.argv[sys.argv.index("--tol")+1])


def photo_aspect():
    """Median-Seitenverhältnis der 5 Fenster-Einheiten im Foto (nicht-rote-Wand per Projektion)."""
    a = np.asarray(Image.open(PHOTO).convert("RGB")).astype(int); H, W = a.shape[:2]
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    win = ~((r > g+18) & (r > b+18) & (np.abs(g-b) < 22) & (r > 70))     # Fenster = NICHT rote Wand
    units = [(0.015, 0.125), (0.22, 0.33), (0.425, 0.535), (0.63, 0.74), (0.83, 0.945)]
    asp = []
    for xa, xb in units:
        sub = win[int(H*0.25):int(H*0.605), int(W*xa):int(W*xb)]
        rr = np.where(sub.mean(1) > 0.35)[0]; cc = np.where(sub.mean(0) > 0.35)[0]
        if len(rr) > 2 and len(cc) > 2:
            asp.append((cc.max()-cc.min())/(rr.max()-rr.min()))
    return float(np.median(asp)), asp


def model_aspect():
    """Seitenverhältnis einer Modell-Fenster-Einheit aus dem Render (dunkles Glas per Projektion)."""
    d = os.path.join(ROOT, "tools"); argv = sys.argv; sys.argv = ["x"]
    spec = importlib.util.spec_from_file_location("od", os.path.join(d, "overlay_diff.py"))
    od = importlib.util.module_from_spec(spec); spec.loader.exec_module(od); sys.argv = argv
    if "--model" in sys.argv:
        a = np.asarray(Image.open(sys.argv[sys.argv.index("--model")+1]).convert("RGB"))
    else:
        im = od.render(); a = np.asarray(im.convert("RGB"))
    H, W = a.shape[:2]
    r, g, b = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    glass = (r < 95) & (g < 100) & (b < 115)                            # dunkles Bleiglas im Render
    by0, by1 = int(H*0.40), int(H*0.63)                                 # Fensterband (über Balkon, unter Traufe)
    bx0, bx1 = int(W*0.14), int(W*0.86)                                 # NUR Hauptfassade (Erker-Buchtfenster raus)
    band = glass[by0:by1, bx0:bx1]
    col = ndimage.uniform_filter1d(band.mean(0), max(3, W//120))
    on = col > col.max()*0.45                                           # Fenster-Spalten (dunkel) vs Pfeiler/Statuen
    runs = []; i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            runs.append((i, j)); i = j
        else:
            i += 1
    runs = [rn for rn in runs if rn[1]-rn[0] > (bx1-bx0)*0.03]
    asp = []
    for a0, a1 in runs:
        colsub = band[:, a0:a1]                                         # Höhe NUR im Fensterband messen (nicht ganze Spalte → sonst Arkade dazu)
        rows = np.where(colsub.mean(1) > 0.30)[0]
        if len(rows) > 2:
            asp.append((a1-a0)/(rows.max()-rows.min()))
    return (float(np.median(asp)) if asp else None), asp


def main():
    pa, pall = photo_aspect()
    ma, mall = model_aspect()
    print(f"FOTO  Fenster-Seitenverhältnis (B/H) = {pa:.3f}   (5 Einheiten {[round(x,2) for x in pall]})")
    if ma is None:
        print("MODELL: keine Fenster im Render gefunden → FAIL"); sys.exit(1)
    print(f"MODELL Fenster-Seitenverhältnis (B/H) = {ma:.3f}   ({len(mall)} Fenster {[round(x,2) for x in mall]})")
    diff = abs(ma-pa)
    verdict = "PASS" if diff <= TOL else "FAIL"
    print(f"Δ = {diff:.3f}  (Toleranz {TOL})  → {verdict}")
    if verdict == "FAIL":
        hoch = "zu GEDRUNGEN (zu breit/niedrig)" if ma > pa else "zu SCHMAL/HOCH"
        print(f"  Modell-Fenster {hoch}. WIN_ASPECT in win_profile.json an Foto {pa:.2f} angleichen.")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
