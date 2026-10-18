#!/usr/bin/env python3
"""laser_blank_cut.py — Weg 1: pro BETT-ROHLING (S9 410x400) eine fertige Schnitt-Datei.

Liest die erzeugten Teile-SVGs (Rippen + Deckplatten), trennt Schnitt (#f00) von Gravur
(#0a0), nestet alles dicht auf S9-große Rohlinge und schreibt PRO ROHLING eine SVG + GRBL-
Gcode: Umrisse werden geschnitten, Nummern/Koordinaten graviert, plus Cutter-Rahmen + Eck-
Füße zum Ausrichten. Kein Umsetzen eines großen Sheets — jeder Rohling startet frisch bei 0.

  python3 tools/laser_blank_cut.py modelle/hirschsprung_geruest \
      --machine 410x400 --gap 4 --gcode --out modelle/hirschsprung_geruest/rohlinge
"""
import argparse, glob, os, re, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly
from matplotlib.path import Path as MPath
from scipy.signal import fftconvolve
from scipy.ndimage import binary_dilation
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from laser_relief_kit import glyph_strokes, svg_write, gcode_write


def area(p):
    x, y = p[:, 0], p[:, 1]
    return abs(np.sum(x*np.roll(y, -1) - np.roll(x, -1)*y))/2


def parse_paths(txt):
    """Pfade nach Farbe trennen: Schnitt (#f00) vs Gravur (#0a0)."""
    cut, eng = [], []
    for m in re.finditer(r'<path d="M ([^"]+?)"[^>]*stroke="(#[0-9a-fA-F]+)"', txt):
        d, col = m.group(1), m.group(2).lower()
        ds = d[:-1] if d.rstrip().endswith("Z") else d
        pts = [tuple(map(float, t.split(","))) for t in ds.replace(" L", " ").split() if "," in t]
        if len(pts) < 2: continue
        p = np.array(pts, float)
        if col == "#f00": cut.append(p)
        elif col == "#0a0": eng.append(p)
    return cut, eng


def load_parts(d):
    parts = []
    for fn in sorted(glob.glob(os.path.join(d, "rib*.svg"))):
        cut, eng = parse_paths(open(fn).read())
        if cut: parts.append({"name": os.path.basename(fn)[:-4], "cut": cut, "eng": eng})
    for fn in glob.glob(os.path.join(d, "deck", "deck_cut_layout.svg")) + glob.glob(os.path.join(d, "deck_cut_layout.svg")):
        cut, eng = parse_paths(open(fn).read())
        for i, panel in enumerate(cut):                      # jede Zelle = eigenes Teil
            mn, mx = panel.min(0), panel.max(0)
            pe = [s for s in eng if (mn[0]-2 <= s[:, 0].mean() <= mx[0]+2 and mn[1]-2 <= s[:, 1].mean() <= mx[1]+2)]
            parts.append({"name": f"deck{i}", "cut": [panel], "eng": pe})
    return parts


def xf(p, rot, flip):
    q = p.copy()
    if flip: q = np.column_stack([-q[:, 0], q[:, 1]])
    if rot == 1:  q = np.column_stack([-q[:, 1], q[:, 0]])
    elif rot == 2: q = np.column_stack([-q[:, 0], -q[:, 1]])
    elif rot == 3: q = np.column_stack([q[:, 1], -q[:, 0]])
    return q


def nest(parts, SW, SH, gap, res=4.0):
    GW, GH = int(SW/res), int(SH/res); gm = max(1, int(round(gap/res)))

    def prep(part, rot, flip):
        ac = [xf(p, rot, flip) for p in part["cut"]]; ae = [xf(p, rot, flip) for p in part["eng"]]
        mn = np.vstack(ac).min(0); ac = [p-mn for p in ac]; ae = [p-mn for p in ae]
        outline = max(ac, key=area)
        w = int(np.ceil(np.ptp(outline[:, 0])/res))+1; h = int(np.ceil(np.ptp(outline[:, 1])/res))+1
        gx, gy = np.meshgrid((np.arange(w)+0.5)*res, (np.arange(h)+0.5)*res)
        m = MPath(outline).contains_points(np.column_stack([gx.ravel(), gy.ravel()])).reshape(h, w)
        if gm: m = binary_dilation(m, iterations=gm)
        return m, ac, ae

    items = sorted(parts, key=lambda P: max(area(c) for c in P["cut"]), reverse=True)
    sheets = []
    for part in items:
        flips = (False, True) if part["name"].startswith("rib") else (False,)
        cand = [prep(part, rt, fl) for fl in flips for rt in (0, 1, 2, 3)]
        done = False
        for sh in sheets + [None]:
            if sh is None: sh = {"grid": np.zeros((GH, GW), bool), "parts": []}; sheets.append(sh)
            best = None
            for (m, ac, ae) in cand:
                mh, mw = m.shape
                if mw > GW or mh > GH: continue
                conv = fftconvolve(sh["grid"].astype(float), m[::-1, ::-1].astype(float), mode="valid")
                ys, xs = np.where(conv < 0.5)
                if len(ys) == 0: continue
                i = np.lexsort((xs, ys))[0]
                if best is None or ys[i] < best[0]: best = (int(ys[i]), int(xs[i]), m, ac, ae)
            if best:
                gy, gx, m, ac, ae = best; mh, mw = m.shape
                sh["grid"][gy:gy+mh, gx:gx+mw] |= m
                off = np.array([gx*res, gy*res])
                sh["parts"].append({"name": part["name"], "cut": [p+off for p in ac], "eng": [p+off for p in ae]})
                done = True; break
    return sheets


def frame_feet(MW, MH, foot=18.0):
    e = []
    for (cx, cy, sx, sy) in [(0, 0, 1, 1), (MW, 0, -1, 1), (0, MH, 1, -1), (MW, MH, -1, -1)]:
        e.append(np.array([(cx+sx*foot, cy), (cx, cy), (cx, cy+sy*foot)]))     # L-Fuß in die Ecke
    e.append(np.array([(0, 0), (MW, 0), (MW, MH), (0, MH), (0, 0)]))           # Cutter-Rahmen
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--machine", default="410x400"); ap.add_argument("--gap", type=float, default=4.0)
    ap.add_argument("--margin", type=float, default=5.0)
    ap.add_argument("--gcode", action="store_true")
    ap.add_argument("--feed", type=float, default=300); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=20)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    MW, MH = (float(x) for x in a.machine.lower().split("x"))
    BW, BH = MW - 2*a.margin, MH - 2*a.margin                 # nutzbare Rohlingfläche
    out = a.out or os.path.join(a.dir, "rohlinge")
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "rohling_*")): os.remove(f)

    parts = load_parts(a.dir)
    tot = sum(max(area(c) for c in P["cut"]) for P in parts)
    sheets = nest(parts, BW, BH, a.gap)
    man = [f"BETT-ROHLINGE (Weg 1)  Cutter {MW:.0f}x{MH:.0f} (nutzbar {BW:.0f}x{BH:.0f}, Rand {a.margin:.0f})",
           f"{len(parts)} Teile -> {len(sheets)} Rohlinge. Je Rohling: Umrisse schneiden, Nummern gravieren, Rahmen+Füße ausrichten.",
           f"ABLAUF: Rohling ~{MW:.0f}x{MH:.0f} an Anschlag-Ecke spannen -> rohling_NN.gcode -> nächster Rohling. Kein Umsetzen.", ""]

    for si, sh in enumerate(sheets):
        cutp = [p for pt in sh["parts"] for p in pt["cut"]]
        engs = [p for pt in sh["parts"] for p in pt["eng"]]
        eng = engs + frame_feet(MW, MH) + glyph_strokes(f"ROHLING {si+1}/{len(sheets)}", a.margin+4, MH-14, h=8)
        base = os.path.join(out, f"rohling_{si+1:02d}")
        svg_write(f"{base}.svg", cutp, [], [], eng, 0)
        if a.gcode:
            gcode_write(f"{base}.gcode", cutp, [], [], eng, 0, a.feed, a.power, a.passes, a.eng_power)
        man.append(f"Rohling {si+1:02d}: {len(sh['parts'])} Teile")
        # Vorschau
        fig, ax = plt.subplots(figsize=(8, 8*MH/MW))
        ax.add_patch(plt.Rectangle((0, 0), MW, MH, fill=False, ec="k", lw=2))
        for p in cutp: ax.add_patch(MplPoly(p, closed=True, fc="#e0b878", ec="saddlebrown", lw=0.4))
        for s in engs: ax.plot(s[:, 0], s[:, 1], "#0a7", lw=0.5)
        ax.set_xlim(-10, MW+10); ax.set_ylim(-10, MH+10); ax.set_aspect("equal"); ax.invert_yaxis()
        ax.set_title(f"Rohling {si+1}/{len(sheets)} — {len(sh['parts'])} Teile ({MW:.0f}x{MH:.0f})")
        plt.tight_layout(); plt.savefig(f"{base}.png", dpi=95); plt.close(fig)

    open(os.path.join(out, "MANIFEST.txt"), "w").write("\n".join(man)+"\n")
    print("\n".join(man)); print(f"\n-> {os.path.abspath(out)}/  (rohling_*.svg/.png" + (" + .gcode" if a.gcode else "") + ")")


if __name__ == "__main__":
    main()
