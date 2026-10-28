#!/usr/bin/env python3
"""foto_bogen_abgleich.py — beweist die BOGENFORM aus einem Foto.

Kernidee: die Bogen-Leibung (Innenkante) ist im Foto die Oberkante der dunklen
Öffnung. Ein Kreis-Fit daran liefert Radius R und Leibungsbreite (Spannweite).
Ist Spannweite/2R ≈ 1,0 bei kleinem Fit-Fehler, ist der Bogen ein echter HALBKREIS
— unabhängig vom globalen Maßstab (das Verhältnis ist perspektiv-robust, lokal).
Über eine bekannte reale Spannweite wird zusätzlich der Maßstab px→m gesetzt.

  python3 tools/foto_bogen_abgleich.py --foto daten/ravenna/fotos/rv_panorama.jpg \\
      --piers 1500,2234,3281,4646,6174 --y0 2080 --y1 2950 \\
      --span-m 20 --modell-stich-span 0.5
"""
import argparse, numpy as np
from scipy import ndimage
from PIL import Image; Image.MAX_IMAGE_PIXELS = None
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt


def fit_circle(P):
    x, y = P[:, 0], P[:, 1]
    A = np.c_[2*x, 2*y, np.ones(len(x))]; b = x**2 + y**2
    c, *_ = np.linalg.lstsq(A, b, rcond=None)
    xc, yc = c[:2]; R = np.sqrt(c[2] + xc**2 + yc**2)
    return xc, yc, R, float(np.sqrt(((np.hypot(x-xc, y-yc)-R)**2).mean()))


def arch_intrados(rgb, dark=105):
    g = rgb.mean(2); M = g < dark
    lab, n = ndimage.label(M)
    if n == 0:
        return None
    big = 1 + int(np.argmax(ndimage.sum(np.ones_like(lab), lab, range(1, n+1))))
    M = lab == big
    cols = np.where(M.any(0))[0]
    top = np.array([(x, np.where(M[:, x])[0].min()) for x in cols], float)
    lo, hi = np.percentile(cols, [6, 94])
    return top[(top[:, 0] > lo) & (top[:, 0] < hi)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--foto", required=True)
    ap.add_argument("--piers", required=True, help="Pfeiler-x kommagetrennt")
    ap.add_argument("--y0", type=int, required=True); ap.add_argument("--y1", type=int, required=True)
    ap.add_argument("--span-m", type=float, default=0.0, help="bekannte reale Spannweite m (Maßstab)")
    ap.add_argument("--modell-stich-span", type=float, default=0.5, help="Modell Stich/Spann (0,5=Halbkreis)")
    ap.add_argument("--out", default="/tmp/foto_bogen_abgleich.png")
    a = ap.parse_args()
    piers = [int(x) for x in a.piers.split(",")]
    im = Image.open(a.foto)

    print("Bogen |  R(px) | Spann(px) | Spann/2R | Stich/Spann | Fit-Fehler%")
    rows = []; fig, axes = plt.subplots(1, len(piers)-1, figsize=(3.2*(len(piers)-1), 3.4))
    if len(piers)-1 == 1: axes = [axes]
    for i, (x0, x1) in enumerate(zip(piers[:-1], piers[1:])):
        rgb = np.array(im.crop((x0, a.y0, x1, a.y1)))
        P = arch_intrados(rgb)
        ax = axes[i]; ax.imshow(rgb); ax.axis("off")
        if P is None or len(P) < 15:
            ax.set_title("—"); continue
        xc, yc, R, res = fit_circle(P)
        span = P[:, 0].max() - P[:, 0].min()
        s2r = span/(2*R); stich = R/span            # Halbkreis: Stich=R, Span=2R -> R/span=0,5
        rows.append((R, span, s2r, stich, res/span*100))
        th = np.linspace(0, np.pi, 80)
        ax.plot(xc+R*np.cos(th), yc-R*np.sin(th), "r-", lw=1.8)
        ax.set_title(f"S/2R={s2r:.2f}\nStich/Span={stich:.2f}", fontsize=9)
        print(f"{x0:5d} | {R:5.0f} | {span:7.0f}   | {s2r:.2f}     | {stich:.2f}        | {res/span*100:.1f}")
    fig.suptitle("Foto-Bogen-Abgleich: roter Halbkreis an echte Leibung  (Stich/Span 0,50 = Halbkreis)")
    fig.tight_layout(); fig.savefig(a.out, dpi=110, bbox_inches="tight")

    R = np.array(rows)
    print(f"\nMittel über {len(R)} Bögen: Stich/Span = {R[:,3].mean():.3f} ± {R[:,3].std():.3f}  "
          f"(Modell {a.modell_stich_span})  | Fit-Fehler {R[:,4].mean():.1f}%")
    if a.span_m:
        px_per_m = R[:, 1].mean()/a.span_m
        print(f"Maßstab aus bekannter Spannweite {a.span_m} m: {1/px_per_m*100:.1f} cm/px "
              f"-> mittlerer Bogen-R = {R[:,0].mean()/px_per_m:.1f} m")
    verd = "PASS — HALBKREIS, Modell-Form bestätigt" if abs(R[:,3].mean()-a.modell_stich_span) < 0.06 \
        else "ABWEICHUNG"
    print(f"VERDIKT: {verd}  -> {a.out}")


if __name__ == "__main__":
    main()
