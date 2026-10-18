#!/usr/bin/env python3
"""eggcrate_deck.py — Laser-DECKPLATTEN für das Egg-Crate-Gerüst (Gips-Basis).

Schließt die Rippen-Lücken mit flachen Laser-Teilen, die auf den Rippen-Oberkanten
liegen -> Basis für Gips (Details machst du mit Gips drüber). Nutzt DIESELBE adaptive
Rippen-Platzierung wie terrain_eggcrate.py, also passen die Platten exakt zwischen die Rippen.
Nur SANFTE Zellen (Höhendifferenz klein) kriegen eine flache Platte; STEILE (Felswand)
werden gelistet -> die schließt du mit Gipsbinde/Karton (flache Platte sitzt da eh nicht).

  python3 tools/eggcrate_deck.py --dem daten/hoellental/dgm025_full.npy --mm 1.5625 \
      --nscale 6.25 --zoom 1 --r0 470 --r1 640 --c0 3310 --c1 3570 --vscale 0.85 \
      --nx 10 --ny 10 --out /tmp/deck
"""
import argparse, os, sys, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain_eggcrate import adaptive_pos, rib_positions
from laser_relief_kit import svg_write, gcode_write, glyph_strokes
from scipy.ndimage import gaussian_filter, zoom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True); ap.add_argument("--mm", type=float, default=1.5625)
    ap.add_argument("--nscale", type=float, default=6.25); ap.add_argument("--zoom", type=int, default=1)
    ap.add_argument("--r0", type=int, required=True); ap.add_argument("--r1", type=int, required=True)
    ap.add_argument("--c0", type=int, required=True); ap.add_argument("--c1", type=int, required=True)
    ap.add_argument("--vscale", type=float, default=0.85)
    ap.add_argument("--nx", type=int, default=10); ap.add_argument("--ny", type=int, default=10)
    ap.add_argument("--min-gap", type=float, default=7.0)
    ap.add_argument("--max-gap", type=float, default=0.0, help="Max Rippenabstand mm in flachen Zonen (0=auto, MUSS zum Gerüst passen)")
    ap.add_argument("--smooth", type=float, default=4.0)
    ap.add_argument("--kerf", type=float, default=0.5, help="Platte pro Seite kleiner (Laser-Spalt/Spiel)")
    ap.add_argument("--flat-mm", type=float, default=18.0, help="max Höhendiff je Zelle für flache Platte (sonst Gips)")
    ap.add_argument("--bed-x", type=float, default=410); ap.add_argument("--bed-y", type=float, default=400)
    ap.add_argument("--gap", type=float, default=6.0, help="Abstand der Platten im Cut-Layout")
    ap.add_argument("--gcode", action="store_true")
    ap.add_argument("--feed", type=float, default=400); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=20)
    ap.add_argument("--out", default="/tmp/deck")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    win = win[::-1]; zf = max(1, a.zoom)
    rel = gaussian_filter(zoom(win-win.min(), zf, order=1) if zf > 1 else (win-win.min()), a.smooth)
    cell = a.mm/zf; Hf = rel*a.nscale*a.vscale
    NY, NX = Hf.shape; Wx, Dy = NX*cell, NY*cell

    # EXAKT dieselben adaptiven Rippen-Positionen wie das Gerüst (eine gemeinsame Quelle)
    mg = a.max_gap if a.max_gap > 0 else None
    xpos, ypos = rib_positions(Hf, cell, a.nx, a.ny, a.min_gap, mg)
    bx = np.array(sorted({0.0, *xpos.tolist(), Wx})); by = np.array(sorted({0.0, *ypos.tolist(), Dy}))

    def hrange(x0, x1, y0, y1):
        c0, c1 = int(x0/cell), max(int(x1/cell), int(x0/cell)+1)
        r0, r1 = int(y0/cell), max(int(y1/cell), int(y0/cell)+1)
        sub = Hf[r0:min(r1, NY), c0:min(c1, NX)]
        return (float(sub.max()-sub.min()), float(sub.mean())) if sub.size else (0, 0)

    panels = []; steep = []                                  # (name, w, d, poly) / steep list
    for j in range(len(by)-1):
        for i in range(len(bx)-1):
            x0, x1, y0, y1 = bx[i], bx[i+1], by[j], by[j+1]
            w, d = x1-x0, y1-y0
            if w < 4 or d < 4: continue
            hr, hm = hrange(x0, x1, y0, y1)
            nm = f"r{j}c{i}"
            if hr > a.flat_mm:
                steep.append((nm, round(hr))); continue      # Felswand -> Gips, keine flache Platte
            pw, pd = w-2*a.kerf, d-2*a.kerf
            poly = [(0, 0), (pw, 0), (pw, pd), (0, pd), (0, 0)]
            panels.append((nm, pw, pd, poly, x0, y0))

    # --- Cut-Layout: Platten nebeneinander auf den Lasertisch packen + Nummer gravieren ---
    cut_polys, engrave = [], []; ox = a.gap; oy = a.gap; rowh = 0; placed = 0
    for (nm, pw, pd, poly, sx, sy) in panels:
        if ox + pw + a.gap > a.bed_x: ox = a.gap; oy += rowh + a.gap; rowh = 0
        cut_polys.append([(px+ox, py+oy) for (px, py) in poly])
        label = f"{nm} {sx+pw/2:.0f},{sy+pd/2:.0f}"       # Zelle + Szenen-X,Y (Mitte) gravieren
        for st in glyph_strokes(label, ox+3, oy+pd/2-3, h=5): engrave.append(st)
        ox += pw + a.gap; rowh = max(rowh, pd); placed += 1
    svg_write(f"{a.out}/deck_cut_layout.svg", cut_polys, [], [], engrave, 0)
    if a.gcode:
        gcode_write(f"{a.out}/deck_cut.gcode", cut_polys, [], [], engrave, 0,
                    a.feed, a.power, a.passes, a.eng_power)

    # --- Platzierungs-Karte: welche Platte in welche Zelle ---
    fig, ax = plt.subplots(figsize=(10, 10*Dy/Wx))
    ax.imshow(Hf, origin="lower", cmap="terrain", extent=[0, Wx, 0, Dy], alpha=0.85)
    for xr in xpos: ax.axvline(xr, color="saddlebrown", lw=1)
    for yr in ypos: ax.axhline(yr, color="saddlebrown", lw=1)
    for (nm, pw, pd, poly, sx, sy) in panels:
        ax.text(sx+pw/2, sy+pd/2, nm, fontsize=7, ha="center", va="center", weight="bold")
    for (nm, hr) in steep:
        pass
    ax.set_title(f"DECKPLATTEN-Karte: {placed} flache Platten (Gips-Basis) + {len(steep)} steile Zellen=Gips\nNord oben")
    ax.set_xlabel("Ost mm"); ax.set_ylabel("Nord mm"); ax.set_aspect("equal")
    plt.tight_layout(); plt.savefig(f"{a.out}/deck_karte.png", dpi=105)

    man = [f"LASER-DECKPLATTEN (Gips-Basis)  {Wx:.0f}x{Dy:.0f} mm",
           f"{placed} flache Platten -> deck_cut_layout.svg (Nummer graviert, in Zelle legen laut deck_karte.png)",
           f"{len(steep)} STEILE Zellen (Höhendiff > {a.flat_mm:.0f} mm) -> KEINE flache Platte, mit Gipsbinde/Karton schließen:",
           "   " + ", ".join(f"{nm}({hr}mm)" for nm, hr in steep), "",
           "MONTAGE: Rippen stecken -> flache Platten in ihre Zelle auf die Rippen-Oberkanten legen/kleben",
           "  -> steile Zellen mit Gipsbinde überbrücken -> GIPS über alles + Details modellieren -> bemalen."]
    open(f"{a.out}/MANIFEST.txt", "w").write("\n".join(man)+"\n")
    print("\n".join(man))
    print(f"\n-> {os.path.abspath(a.out)}/  (deck_cut_layout.svg + deck_karte.png)")


if __name__ == "__main__":
    main()
