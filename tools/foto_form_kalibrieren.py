#!/usr/bin/env python3
"""foto_form_kalibrieren.py — Bauwerk-Form aus MEHREREN Fotos kalibriert bestimmen.

Ein einzelnes perspektivisches Foto ist mehrdeutig (Leibung vs. Hintergrund,
Verzerrung). Dieses Tool gleicht die Form über VIELE Bilder ab und kalibriert
den Maßstab über bekannte Größen (dokumentierte Spannweite, ODER ein Zug/Objekt
bekannter Länge im Bild). Es fittet mehrere Bogen-Kurventypen und sagt, welcher
real passt — in Metern. Allgemein für jedes Bogen-Bauwerk.

Config (JSON): Liste von Bildern, je:
  { "img": "...jpg", "bbox": [x0,y0,x1,y1],              # Bogen-Öffnung
    "ref_px": [x1,y1,x2,y2], "ref_m": 20.0,              # bekannte Strecke -> Maßstab
    "dark": 105 }                                         # Schwelle Öffnung (optional)

  python3 tools/foto_form_kalibrieren.py --config daten/ravenna/formcfg.json \\
      --out daten/ravenna/form_kalib.png
"""
import argparse, json, numpy as np
from scipy import ndimage, optimize
from PIL import Image; Image.MAX_IMAGE_PIXELS = None
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt


def intrados_points(img_rgb, bbox, dark):
    """Obere Leibung = Oberkante der größten dunklen Öffnung (min-y je Spalte)."""
    x0, y0, x1, y1 = bbox
    sub = img_rgb[y0:y1, x0:x1].mean(2)
    M = sub < dark
    lab, n = ndimage.label(M)
    if n == 0:
        return np.empty((0, 2))
    big = 1 + int(np.argmax(ndimage.sum(np.ones_like(lab), lab, range(1, n+1))))
    M = lab == big
    cols = np.where(M.any(0))[0]
    lo, hi = np.percentile(cols, [5, 95])
    pts = [(x, np.where(M[:, x])[0].min()) for x in cols if lo < x < hi]
    return np.array(pts, float)     # (x,y) lokal, y nach unten


# --- Kurvenmodelle (Krone oben; y nach unten). Rückgabe: fit-RMS + Parameter ---
def fit_circle(x, y):
    A = np.c_[2*x, 2*y, np.ones(len(x))]; b = x**2 + y**2
    c, *_ = np.linalg.lstsq(A, b, rcond=None); cx, cy = c[:2]; R = np.sqrt(c[2]+cx**2+cy**2)
    rms = np.sqrt(((np.hypot(x-cx, y-cy)-R)**2).mean())
    return rms, dict(typ="Kreisbogen", R=R, cx=cx, cy=cy)


def fit_ellipse(x, y):
    # Halb-Ellipse: y = cy - b*sqrt(1-((x-cx)/a)^2), Krone oben
    def resid(p):
        cx, cy, a, b = p
        v = 1-((x-cx)/a)**2; v = np.clip(v, 0, None)
        return (cy - b*np.sqrt(v)) - y
    a0 = (x.max()-x.min())/2; cx0 = x.mean(); cy0 = y.max(); b0 = y.max()-y.min()
    r = optimize.least_squares(resid, [cx0, cy0, a0, b0], method="lm")
    cx, cy, a, b = r.x
    return np.sqrt((resid(r.x)**2).mean()), dict(typ="Halb-Ellipse", a=abs(a), b=abs(b), cx=cx, cy=cy)


def fit_parabola(x, y):
    c = np.polyfit(x, y, 2); rms = np.sqrt(((np.polyval(c, x)-y)**2).mean())
    xv = -c[1]/(2*c[0])                               # Scheitel-x
    return rms, dict(typ="Parabel", c=c, scheitel_x=xv)


def analyse(img, cfg, ax=None):
    rgb = np.array(Image.open(cfg["img"]))
    P = intrados_points(rgb, cfg["bbox"], cfg.get("dark", 105))
    if len(P) < 15:
        return None
    x0, y0 = cfg["bbox"][0], cfg["bbox"][1]
    # Maßstab aus Referenzstrecke
    rx1, ry1, rx2, ry2 = cfg["ref_px"]
    px_per_m = np.hypot(rx2-rx1, ry2-ry1)/cfg["ref_m"]
    x, y = P[:, 0], P[:, 1]
    fits = [f(x, y) for f in (fit_circle, fit_ellipse, fit_parabola)]
    span_px = x.max()-x.min(); rise_px = y.max()-y.min()
    span_m = span_px/px_per_m; rise_m = rise_px/px_per_m
    best = min(fits, key=lambda t: t[0])
    res = dict(img=cfg["img"].split("/")[-1], px_per_m=px_per_m,
               span_m=span_m, rise_m=rise_m, stich_span=rise_m/span_m,
               best=best[1]["typ"], fits={f[1]["typ"]: f[0] for f in fits})
    if ax is not None:
        ax.imshow(rgb[cfg["bbox"][1]:cfg["bbox"][3], cfg["bbox"][0]:cfg["bbox"][2]])
        ax.plot(x, y, "c.", ms=2)
        xx = np.linspace(x.min(), x.max(), 100)
        rc, cp = fits[0]; ax.plot(xx, cp["cy"]-np.sqrt(np.clip(cp["R"]**2-(xx-cp["cx"])**2, 0, None)), "r-", lw=1.3, label=f"Kreis rms{rc:.1f}")
        re, ep = fits[1]; ax.plot(xx, ep["cy"]-ep["b"]*np.sqrt(np.clip(1-((xx-ep["cx"])/ep["a"])**2, 0, None)), "y-", lw=1.3, label=f"Ellipse rms{re:.1f}")
        ax.legend(fontsize=7); ax.axis("off")
        ax.set_title(f"{res['img']}\nSpan {span_m:.1f}m Stich {rise_m:.1f}m ({res['stich_span']:.2f})\nbest: {res['best']}", fontsize=8)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True); ap.add_argument("--out", default="/tmp/form_kalib.png")
    a = ap.parse_args()
    cfgs = json.load(open(a.config))
    fig, axes = plt.subplots(1, len(cfgs), figsize=(4.5*len(cfgs), 4.5))
    if len(cfgs) == 1: axes = [axes]
    results = []
    for cfg, ax in zip(cfgs, axes):
        r = analyse(cfg["img"], cfg, ax)
        if r: results.append(r)
    fig.suptitle("Multi-Bild-Form-Kalibrierung (rot=Kreis, gelb=Ellipse; kleinste rms gewinnt)")
    fig.tight_layout(); fig.savefig(a.out, dpi=110, bbox_inches="tight")

    print(f"{'Bild':22s} {'px/m':>6s} {'Span_m':>7s} {'Stich_m':>7s} {'St/Sp':>6s} {'bester Fit':>14s}  rms(Kreis/Ell/Par)")
    for r in results:
        f = r["fits"]
        print(f"{r['img']:22s} {r['px_per_m']:6.1f} {r['span_m']:7.1f} {r['rise_m']:7.1f} "
              f"{r['stich_span']:6.2f} {r['best']:>14s}  "
              f"{f.get('Kreisbogen',0):.1f}/{f.get('Halb-Ellipse',0):.1f}/{f.get('Parabel',0):.1f}")
    if results:
        ss = np.array([r["stich_span"] for r in results]); sp = np.array([r["span_m"] for r in results])
        print(f"\nABGLEICH über {len(results)} Bilder: Stich/Span = {ss.mean():.2f} ± {ss.std():.2f}  "
              f"Span = {sp.mean():.1f} ± {sp.std():.1f} m")
        print(f"  0,50 = Halbkreis | 0,21 (Wiki) = flacher Segmentbogen | dazwischen = Korb-/Ellipsenbogen")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
