#!/usr/bin/env python3
"""kaufhaus_bauplan.py — bemaßter Bauplan Historisches Kaufhaus Freiburg,
aus dem Frontalfoto vermessen (Referenz Traufe 9,7 / First 21,4 m = LOD2 amtlich).
Front-Ansicht + Querschnitt + Maßherkunft. Maße = Modell kaufhaus_measured.py.
"""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon as MPoly, Arc

# Maße (m) — identisch mit kaufhaus_measured.py
W, D = 25.0, 13.0
EAVE, RIDGE = 9.7, 21.4
ARC_SPRING, ARC_TOP = 2.8, 4.3
SILL, HEAD = 5.3, 8.4
N_ARCH = 6
C_REF = "#1f6feb"    # LOD2 amtlich (Referenz)
C_FOTO = "#c0392b"   # Foto-gemessen
BK = "#1a1a1a"


def dimv(ax, x, z0, z1, t, c):
    ax.annotate("", (x, z1), (x, z0), arrowprops=dict(arrowstyle="<->", color=c, lw=1.1))
    ax.text(x-0.35, (z0+z1)/2, t, ha="right", va="center", rotation=90, color=c, fontsize=8, fontweight="bold")


def dimh(ax, x0, x1, z, t, c):
    ax.annotate("", (x1, z), (x0, z), arrowprops=dict(arrowstyle="<->", color=c, lw=1.1))
    ax.text((x0+x1)/2, z+0.2, t, ha="center", va="bottom", color=c, fontsize=8, fontweight="bold")


def elevation(ax):
    # Wandflächen
    ax.add_patch(Rectangle((0, 0), W, EAVE, fc="#d9a79a", ec=BK, lw=1.2))
    # Arkade (6 Spitzbögen)
    pitch = W/N_ARCH
    for i in range(N_ARCH):
        xc = pitch*(i+0.5); a = pitch*0.36
        ax.add_patch(Rectangle((xc-a, 0), 2*a, ARC_SPRING, fc="white", ec=BK, lw=0.8))
        ax.add_patch(MPoly([(xc-a, ARC_SPRING), (xc, ARC_TOP), (xc+a, ARC_SPRING)], closed=True, fc="white", ec=BK, lw=0.8))
    # Galerie-Brüstung
    ax.add_patch(Rectangle((0.3, ARC_TOP+0.2), W-0.6, 0.9, fc="#c9a24a", ec=BK, lw=0.6))
    # Fensterband
    for i in range(14):
        xc = W*(0.05+0.90*i/13)
        ax.add_patch(Rectangle((xc-0.5, SILL), 1.0, HEAD-SILL, fc="#2b3038", ec=BK, lw=0.6))
    # Erker
    for xf in (0.085*W, 0.915*W):
        ax.add_patch(Rectangle((xf-1.6, ARC_TOP), 3.2, 11.5-ARC_TOP, fc="#c9a24a", ec=BK, lw=0.8))
        ax.add_patch(MPoly([(xf-1.6, 11.5), (xf, 15.0), (xf+1.6, 11.5)], closed=True, fc="#c9a24a", ec=BK, lw=0.8))
    # Dach (steil) + Treppengiebel-Silhouette
    ax.add_patch(MPoly([(0, EAVE), (W, EAVE), (W, RIDGE), (0, RIDGE)], closed=True, fc="#6b574c", ec=BK, lw=1.0))
    for xg in (0, W):
        s = -1 if xg == 0 else 1
        pts = [(xg, EAVE)]
        for i in range(6):
            z0 = EAVE+(RIDGE-EAVE)*i/6; z1 = EAVE+(RIDGE-EAVE)*(i+1)/6; x = xg+s*W*0.06*(i+1)
            pts += [(xg+s*W*0.06*i, z1), (x, z1)]
        ax.add_patch(MPoly(pts+[(xg, RIDGE)], closed=True, fc="#8a7466", ec=BK, lw=0.5))
    # Gauben
    for frac, n, w in [(0.14, 6, 1.3), (0.34, 5, 1.1), (0.56, 3, 0.9)]:
        z = EAVE+frac*(RIDGE-EAVE)
        for i in range(n):
            xc = W*(0.12+0.76*i/max(n-1, 1))
            ax.add_patch(Rectangle((xc-w/2, z), w, 1.3, fc="#3a3029", ec=BK, lw=0.5))
    # Bemaßung
    dimv(ax, -1.6, 0, RIDGE, f"First {RIDGE} m", C_REF)
    dimv(ax, -4.0, 0, EAVE, f"Traufe {EAVE} m", C_REF)
    dimv(ax, W+1.6, 0, ARC_SPRING, f"{ARC_SPRING}", C_FOTO)
    dimv(ax, W+1.6, ARC_SPRING, ARC_TOP, "Arkade", C_FOTO)
    dimv(ax, W+1.6, SILL, HEAD, f"Fenster {HEAD-SILL:.1f}", C_FOTO)
    dimv(ax, W+4.0, EAVE, RIDGE, f"Dach {RIDGE-EAVE:.1f} m", C_FOTO)
    dimh(ax, 0, W, -1.6, f"Fassadenbreite {W} m", C_REF)
    dimh(ax, 0, W/N_ARCH, -3.2, f"Achse {W/N_ARCH:.1f}", C_FOTO)
    ax.text(W/2, RIDGE+1.2, "FRONT-ANSICHT (Münsterplatz)", ha="center", fontsize=11, fontweight="bold")
    ax.set_xlim(-7, W+7); ax.set_ylim(-5, RIDGE+3); ax.set_aspect("equal"); ax.axis("off")


def section(ax):
    ax.add_patch(Rectangle((0, 0), D, EAVE, fc="#d9a79a", ec=BK, lw=1.2))
    ax.add_patch(MPoly([(0, EAVE), (D, EAVE), (D/2, RIDGE)], closed=True, fc="#6b574c", ec=BK, lw=1.0))
    for z in (ARC_TOP, SILL, HEAD):
        ax.plot([0, D], [z, z], color=BK, lw=0.5, ls=":")
    pitch = np.degrees(np.arctan2(RIDGE-EAVE, D/2))
    ax.text(D/2, (EAVE+RIDGE)/2, f"{pitch:.0f}°", ha="center", color=C_FOTO, fontsize=10, fontweight="bold")
    dimh(ax, 0, D, -1.6, f"Tiefe {D} m", C_REF)
    ax.text(D/2, RIDGE+1.2, "QUERSCHNITT", ha="center", fontsize=11, fontweight="bold")
    ax.set_xlim(-3, D+3); ax.set_ylim(-5, RIDGE+3); ax.set_aspect("equal"); ax.axis("off")


def main():
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("HISTORISCHES KAUFHAUS FREIBURG  ·  Vermesser-Bauplan aus Frontalfoto + LOD2-Referenz",
                 fontsize=14, fontweight="bold", y=0.97)
    ax1 = fig.add_axes([0.03, 0.30, 0.62, 0.62]); elevation(ax1)
    ax2 = fig.add_axes([0.67, 0.30, 0.30, 0.62]); section(ax2)
    ax3 = fig.add_axes([0.03, 0.02, 0.94, 0.22]); ax3.axis("off")
    ax3.text(0, 0.9, "MASSHERKUNFT", fontsize=11, fontweight="bold")
    for i, (c, t) in enumerate([
        (C_REF, "LOD2 (LGL, amtlich) = Referenz-Lineal: Traufe 9,7 m · First 21,4 m · Breite 25 m · Tiefe 13 m"),
        (C_FOTO, "Foto-vermessen (kh_front2025b, an der Referenz skaliert, ±~10 %): Arkade 6 Spitzbögen (Kämpfer 2,8/Scheitel 4,3),\n"
                 "        Fensterband 5,3–8,4 m, 2 Erker mit Spitzhelm, 3 Gaubenreihen (6/5/3), Treppengiebel, Dachneigung ~60°")]):
        ax3.plot([0, 0.04], [0.74-i*0.26]*2, color=c, lw=3)
        ax3.text(0.05, 0.74-i*0.26, t, fontsize=8.5, va="center")
    ax3.text(0, 0.05, "Methode: maßstäbliches Foto → Kanten an bekannter Referenz messen → Geometrie mit echten Details. "
             "Modell: tools/kaufhaus_measured.py", fontsize=8, style="italic", color="#555")
    ax3.set_xlim(0, 1); ax3.set_ylim(0, 1)
    out = "modelle/kaufhaus_freiburg/kaufhaus_bauplan.png"
    fig.savefig(out, dpi=130, bbox_inches="tight", facecolor="white")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
