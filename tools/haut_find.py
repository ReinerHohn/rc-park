#!/usr/bin/env python3
"""haut_find.py — Haut-Teil(e) auf der Bauplan-Karte FINDEN (Nummer -> wo hin).

  python3 tools/haut_find.py 5 60 23        # markiert Teil 5, 60, 23
  python3 tools/haut_find.py 5 --out /tmp/find.png

Liest die Szenen-Positionen aus <dir>/MANIFEST.txt (von skin_smart_split) und
zeichnet den Hillshade mit ALLEN Nummern klein + den GESUCHTEN groß/rot markiert.
"""
import argparse, os, re, sys, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from scipy.ndimage import gaussian_filter

DEM = "daten/hoellental/dgm025_full.npy"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("nums", nargs="+", type=int, help="Teil-Nummer(n)")
    ap.add_argument("--dir", default="modelle/hirschsprung_haut", help="Ordner mit MANIFEST.txt")
    ap.add_argument("--dem", default=DEM)
    ap.add_argument("--mm", type=float, default=1.5625); ap.add_argument("--nscale", type=float, default=6.25)
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--vscale", type=float, default=0.85)
    ap.add_argument("--out", default="/tmp/haut_find.png")
    a = ap.parse_args()

    pos = {}
    for ln in open(os.path.join(a.dir, "MANIFEST.txt"), errors="ignore"):
        m = re.search(r"Nr\s+(\d+).*@ Szene \((-?\d+),(-?\d+)\)", ln)
        if m: pos[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
    if not pos:
        print("keine Positionen im MANIFEST gefunden"); sys.exit(1)

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    Z = gaussian_filter(win[::-1] - win.min(), 0.6) * a.nscale * a.vscale
    cell = a.mm; NY, NX = Z.shape

    fig, ax = plt.subplots(figsize=(11, 8))
    ls = LightSource(azdeg=315, altdeg=45)
    ext = [0, NX*cell, 0, NY*cell]
    ax.imshow(ls.hillshade(Z, vert_exag=1, dx=cell, dy=cell), cmap="gray", origin="lower", extent=ext)
    ax.imshow(Z, cmap="terrain", alpha=0.4, origin="lower", extent=ext)
    want = set(a.nums)
    for pid, (cx, cy) in pos.items():
        if pid in want:
            ax.plot(cx, cy, "o", ms=30, mfc="red", mec="yellow", mew=2.5, zorder=5)
            ax.text(cx, cy, str(pid), fontsize=13, weight="bold", ha="center", va="center", color="white", zorder=6)
        else:
            ax.text(cx, cy, str(pid), fontsize=6, ha="center", va="center", color="k", alpha=0.45)
    ax.set_title(f"GESUCHT: Teil {', '.join(map(str, a.nums))} (rot) — Nord oben, Ost rechts")
    ax.set_xlabel("Ost mm"); ax.set_ylabel("Nord mm"); ax.set_aspect("equal")
    plt.tight_layout(); plt.savefig(a.out, dpi=110)
    print(f"Karte -> {os.path.abspath(a.out)}")
    for n in a.nums:
        if n in pos: print(f"  Teil {n}: Szene ({pos[n][0]:.0f}, {pos[n][1]:.0f}) mm")
        else: print(f"  Teil {n}: NICHT gefunden (gibt's die Nummer?)")


if __name__ == "__main__":
    main()
