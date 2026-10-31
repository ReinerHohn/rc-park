#!/usr/bin/env python3
"""foto_spitze_vollbild.py - Spitzenlaenge ueber dem Dach aus Vollbild-Silhouetten (Himmelsmaske), ohne Kamerafit.
Je Foto: Spitze (hoechster Nicht-Himmel-Punkt nahe Mitte), Dach-Oberkante (Breitensprung), Dachflanken-Steigung s (Breite je Zeile) und Breite oben w.
Massstab k (px/m) aus: Dachbasis = B m und Dachhoehe = HR m (Modellwerte, ANNAHME):  w + s*HR*k = B*k  ->  k = w / (B - s*HR).
Spitzenlaenge A_m = A_px / k.  Nur fuer annaehernd frontale Fotos aussagekraeftig; Streuung ueber Fotos = Unsicherheit.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/foto_spitze_vollbild.py 049 001 ...   (B=7.15, HR=10.7 Standard)
"""
import sys, glob, cv2, numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0]); import foto_silhouette_gpu as F
B, HR = 7.15, 10.7
def run(nr):
    im = cv2.imread(glob.glob(F.FD + nr + "_*")[0]); H, W = im.shape[:2]; N = ~F.sky_mask(im)
    cols = np.arange(int(W * .25), int(W * .75)); ys = [np.argmax(N[:, c]) if N[:, c].any() else H for c in cols]
    k = int(np.argmin(ys)); x0, y0 = int(cols[k]), int(ys[k])
    def width(y):
        r = N[y]; l = x0
        if not r[x0]:
            return 0
        while l > 0 and r[l - 1]: l -= 1
        rr = x0
        while rr < W - 1 and r[rr + 1]: rr += 1
        return rr - l + 1
    ws = np.array([width(y) for y in range(y0, min(H, y0 + int(0.6 * H)))])
    base = np.maximum.accumulate(np.convolve(ws, np.ones(5) / 5, "same"))
    # Dach-Oberkante: erste Zeile, in der die Breite > 12 % der max. Breite im Fenster springt und danach nicht mehr zurueckfaellt
    thr = 0.12 * ws[: len(ws) // 2].max() if ws[: len(ws) // 2].max() > 0 else 1
    jump = next((i for i in range(5, len(ws) - 5) if ws[i] > thr and ws[i + 1:i + 40].min() > 0.8 * ws[i]), None)
    if jump is None: return None
    w = ws[jump + 3]; win = int(0.30 * jump); seg = ws[jump + 3: jump + 3 + win]
    d = np.diff(seg[::4]) / 4.0; s = float(np.median(d)) if len(d) > 5 else np.nan   # robust gegen Verschmelzen mit Nachbarn
    kpm = w / (B - s * HR) if B - s * HR > 0.5 else np.nan
    return dict(nr=nr, spitze=(x0, y0), A_px=jump, w_top_px=int(w), steigung=float(s), k_px_pro_m=float(kpm), A_m=float(jump / kpm), bild=(W, H))
if __name__ == "__main__":
    print("Foto  A_px  w_oben  Steigung  k px/m   Spitzenlaenge m   (Modell 8,6)")
    for nr in sys.argv[1:]:
        try: r = run(nr)
        except Exception as e: print(nr, "Fehler", e); continue
        print(nr, "keine Dach-Oberkante" if r is None else f"{r['A_px']:6d} {r['w_top_px']:6d}  {r['steigung']:7.3f}  {r['k_px_pro_m']:6.1f}   {r['A_m']:6.1f}")
