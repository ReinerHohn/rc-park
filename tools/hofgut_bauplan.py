#!/usr/bin/env python3
"""hofgut_bauplan.py — bemaßter Bauplan (Vermesser-Zeichnung) des Hofgut Sternen:
Front-Ansicht + Querschnitt + Grundriss (aus LOD2), jede Maßzahl mit HERKUNFT
(LOD2 amtlich / Foto gemessen / Doku). Das ist der „Bauplan mit Maßen".
"""
import argparse, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly, Rectangle

# Farbcode Maßherkunft
C_LOD2 = "#1f6feb"   # amtlich
C_FOTO = "#c0392b"   # Foto gemessen
C_DOK = "#7a5c00"    # Doku/Karte
BLACK = "#1a1a1a"


def dim_h(ax, x0, x1, y, text, color, off=0.0):
    ax.annotate("", (x1, y), (x0, y), arrowprops=dict(arrowstyle="<->", color=color, lw=1.2))
    ax.text((x0 + x1) / 2, y + off + 0.25, text, ha="center", va="bottom",
            color=color, fontsize=8.5, fontweight="bold")


def dim_v(ax, x, y0, y1, text, color):
    ax.annotate("", (x, y1), (x, y0), arrowprops=dict(arrowstyle="<->", color=color, lw=1.2))
    ax.text(x - 0.4, (y0 + y1) / 2, text, ha="right", va="center", rotation=90,
            color=color, fontsize=8.5, fontweight="bold")


def elevation(ax, P):
    Lf, E, Rz = P["Lf"], P["eave"], P["ridge"]
    s, f = P["socle"], P["floor"]
    inset = P["inset"]
    # Wandkörper
    ax.add_patch(Rectangle((0, 0), Lf, s, fc="#cfc7bb", ec=BLACK, lw=1.0))           # Sockel
    ax.add_patch(Rectangle((0, s), Lf, E - s, fc="#e0c48c", ec=BLACK, lw=1.0))        # Fassade
    # Balkonlinien
    for z in (s, s + f):
        ax.plot([0, Lf], [z, z], color="#5a3d28", lw=2.2)
    # Dach (Krüppelwalm als Trapez-Silhouette)
    ax.add_patch(MplPoly([(0, E), (Lf, E), (Lf - inset, Rz), (inset, Rz)],
                         closed=True, fc="#6b574c", ec=BLACK, lw=1.0))
    # Gauben 2 Reihen
    for frac, n in [(0.22, P["dl"]), (0.55, P["du"])]:
        z = E + frac * (Rz - E)
        for x in np.linspace(Lf * 0.12, Lf * 0.88, n):
            ax.add_patch(Rectangle((x - 0.7, z), 1.4, 1.1, fc="#8a6a56", ec=BLACK, lw=0.6))
    # Kamine
    for x in np.linspace(Lf * 0.25, Lf * 0.8, P["chim"]):
        ax.add_patch(Rectangle((x - 0.5, Rz - 0.6), 1.0, 2.2, fc="#7a6a60", ec=BLACK, lw=0.6))
    # Fresko-Panel (Foto)
    ax.add_patch(Rectangle((Lf/2 - 4, s + f + 0.6), 8, 1.8, fc="#d8cdb0", ec="#8a7a50", lw=0.8))
    ax.text(Lf/2, s + f + 1.5, "Fresko", ha="center", va="center", fontsize=6.5, color="#8a7a50")

    # Maße
    dim_h(ax, 0, Lf, -1.6, f"Fassadenlänge {Lf:.0f} m", C_LOD2)
    dim_v(ax, -1.8, 0, Rz, f"First {Rz:.1f} m", C_LOD2)
    dim_v(ax, -4.2, 0, E, f"Traufe {E:.1f} m", C_FOTO)
    dim_v(ax, Lf + 1.8, 0, s, f"Sockel {s:.0f}", C_FOTO)
    dim_v(ax, Lf + 1.8, s, s + f, f"1.OG {f:.0f}", C_FOTO)
    dim_v(ax, Lf + 1.8, s + f, E, f"2.OG {E-s-f:.0f}", C_FOTO)
    dim_v(ax, Lf + 4.2, E, Rz, f"Dach {Rz-E:.1f} m", C_FOTO)
    ax.text(Lf/2, Rz + 1.0, "FRONT-ANSICHT (Talseite)", ha="center", fontsize=10, fontweight="bold")
    ax.set_xlim(-7, Lf + 7); ax.set_ylim(-3, Rz + 3); ax.set_aspect("equal"); ax.axis("off")


def section(ax, P):
    D, E, Rz = P["D"], P["eave"], P["ridge"]
    s, f, bp = P["socle"], P["floor"], P["balc"]
    ax.add_patch(Rectangle((0, 0), D, E, fc="#e0c48c", ec=BLACK, lw=1.0))
    ax.add_patch(Rectangle((0, 0), D, s, fc="#cfc7bb", ec=BLACK, lw=1.0))
    # Dach Satteldach-Schnitt
    ax.add_patch(MplPoly([(0, E), (D, E), (D/2, Rz)], closed=True, fc="#6b574c", ec=BLACK, lw=1.0))
    # Geschossdecken
    for z in (s, s + f):
        ax.plot([0, D], [z, z], color=BLACK, lw=0.8)
    # Balkon vorn
    ax.add_patch(Rectangle((-bp, s - 0.15), bp, 0.15, fc="#5a3d28"))
    ax.add_patch(Rectangle((-bp, s + f - 0.15), bp, 0.15, fc="#5a3d28"))
    # Dachneigung
    pitch = np.degrees(np.arctan2(Rz - E, D / 2))
    ax.text(D/2, (E + Rz)/2, f"{pitch:.0f}°", ha="center", color=C_FOTO, fontsize=9, fontweight="bold")
    dim_h(ax, 0, D, -1.6, f"Tiefe {D:.0f} m", C_LOD2)
    dim_h(ax, -bp, 0, s - 0.9, f"Balkon {bp:.1f}", C_FOTO)
    ax.text(D/2, Rz + 1.0, "QUERSCHNITT", ha="center", fontsize=10, fontweight="bold")
    ax.set_xlim(-bp - 2, D + 3); ax.set_ylim(-3, Rz + 3); ax.set_aspect("equal"); ax.axis("off")


def plan(ax, foot):
    if foot is None:
        ax.axis("off"); return
    F = foot - foot.min(0)
    ax.add_patch(MplPoly(F, closed=True, fc="#d9d2c4", ec=BLACK, lw=1.2))
    w, h = np.ptp(F[:, 0]), np.ptp(F[:, 1])
    dim_h(ax, 0, w, -3, f"{w:.0f} m", C_LOD2)
    dim_v(ax, -2.5, 0, h, f"{h:.0f} m", C_LOD2)
    ax.text(w/2, h + 3, "GRUNDRISS (LOD2-Footprint, 946 m²)", ha="center", fontsize=9.5, fontweight="bold")
    ax.set_xlim(-8, w + 5); ax.set_ylim(-7, h + 7); ax.set_aspect("equal"); ax.axis("off")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--footprint", default="/tmp/hofgut_footprint.npy")
    ap.add_argument("--out", default="modelle/hofgut_sternen/hofgut_bauplan.png")
    a = ap.parse_args()
    P = dict(Lf=40, D=13, eave=9.0, ridge=17.5, socle=3.0, floor=3.0, balc=1.3,
             inset=5.0, dl=7, du=6, chim=3)
    try:
        foot = np.load(a.footprint)
    except Exception:
        foot = None

    fig = plt.figure(figsize=(16, 11))
    fig.suptitle("HOFGUT STERNEN  ·  Höllsteig / Ravennaschlucht  ·  Vermesser-Bauplan aus Fotos + LOD2",
                 fontsize=14, fontweight="bold", y=0.985)
    ax1 = fig.add_axes([0.04, 0.42, 0.62, 0.50]); elevation(ax1, P)
    ax2 = fig.add_axes([0.68, 0.42, 0.30, 0.50]); section(ax2, P)
    ax3 = fig.add_axes([0.04, 0.04, 0.55, 0.34]); plan(ax3, foot)
    # Legende Maßherkunft + Quellen
    ax4 = fig.add_axes([0.62, 0.04, 0.36, 0.34]); ax4.axis("off")
    ax4.text(0, 1.0, "MASSHERKUNFT", fontsize=11, fontweight="bold")
    for i, (c, t) in enumerate([
        (C_LOD2, "LOD2 (LGL, amtlich): Länge, Grundriss, First 17,5 m, Grund 713,5 m ü.NN"),
        (C_FOTO, "Foto gemessen: Traufe 9 m (Dachanteil 46% LOD2 ↔ ~50% Foto = PASS),\n"
                 "        3 Ebenen, 2 Balkone, 7+6 Gauben, 3 Kamine, Dachneigung ~52°"),
        (C_DOK, "Doku/Karte: Lage 47,9167 N 8,0732 E, Höllsteig 76, Erstnennung 1446")]):
        ax4.plot([0, 0.06], [0.84 - i*0.22]*2, color=c, lw=3)
        ax4.text(0.09, 0.84 - i*0.22, t, fontsize=8.3, va="center")
    ax4.text(0, 0.1, "Prinzip: Modell = Merge aller Quellen; jeder Detailschritt belegt.\n"
             "Quellen: LGL LOD2/DGM1/DOP · Google-Fotos · schwarzwald-tourismus.info",
             fontsize=7.5, style="italic", color="#555")
    ax4.set_xlim(0, 1); ax4.set_ylim(0, 1)

    fig.savefig(a.out, dpi=130, bbox_inches="tight", facecolor="white")
    print(f"-> {a.out}")


if __name__ == "__main__":
    main()
