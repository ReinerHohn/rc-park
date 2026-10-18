#!/usr/bin/env python3
"""laser_zone_nest.py — ZONEN-Nester für kleine Cutter (S9 410x400) + große Platten (1200x600).

Packt alle Teile DICHT auf die Kaufplatte (max Materialausnutzung), legt dann ein Raster
aus <=Cutter-großen SCHNITTZONEN drüber. Jedes Teil, das eine Zonengrenze kreuzt, wird GENAU
DORT mit FINGERZINKEN geteilt (beide Hälften in Nachbarzonen, später verleimt). Pro Zone wird
zusätzlich der CUTTER-RAHMEN + ECK-FÜSSE + REGISTRIER-KREUZE graviert, damit du das Werkstück
zwischen den Schnitten sauber umsetzen kannst (alles bleibt passgenau).

  python3 tools/laser_zone_nest.py modelle/hirschsprung_geruest \
      --sheet 1200x600 --machine 410x400 --gap 4 --finger 12 --out /tmp/zonen
"""
import argparse, glob, os, re, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly
from matplotlib.path import Path as MPath
from scipy.signal import fftconvolve
from scipy.ndimage import binary_dilation
from shapely.geometry import Polygon as SP, box
from shapely.ops import unary_union
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from laser_relief_kit import glyph_strokes, svg_write, gcode_write


def polys_from_svg(fn):
    out = []
    for d in re.findall(r'<path d="M ([^"]+?) Z"', open(fn).read()):
        pts = [tuple(map(float, t.split(","))) for t in d.replace(" L", " ").split() if "," in t]
        if len(pts) >= 3: out.append(np.array(pts, float))
    return out


def area(p):
    x, y = p[:, 0], p[:, 1]
    return abs(np.sum(x*np.roll(y, -1) - np.roll(x, -1)*y))/2


def form_nest(parts, SW, SH, gap, res=4.0):
    """Dichtes Form-Nesting (FFT-Kollision, Bottom-Left, Rot/Spiegel). Gibt Platten mit
    platzierten Teilen (name, poly in mm) zurück."""
    GW, GH = int(SW/res), int(SH/res); gm = max(1, int(round(gap/res)))

    def mask_of(poly, rot, flip):
        p = poly.copy()
        if flip: p = np.column_stack([-p[:, 0], p[:, 1]])
        if rot: p = (np.column_stack([-p[:, 1], p[:, 0]]) if rot == 1 else
                     np.column_stack([-p[:, 0], -p[:, 1]]) if rot == 2 else
                     np.column_stack([p[:, 1], -p[:, 0]]))
        p = p - p.min(0)
        w = int(np.ceil(np.ptp(p[:, 0])/res))+1; h = int(np.ceil(np.ptp(p[:, 1])/res))+1
        gx, gy = np.meshgrid((np.arange(w)+0.5)*res, (np.arange(h)+0.5)*res)
        m = MPath(p).contains_points(np.column_stack([gx.ravel(), gy.ravel()])).reshape(h, w)
        if gm: m = binary_dilation(m, iterations=gm)
        return m, p

    def try_place(grid, mask):
        mh, mw = mask.shape
        if mw > GW or mh > GH: return None
        conv = fftconvolve(grid.astype(float), mask[::-1, ::-1].astype(float), mode="valid")
        ys, xs = np.where(conv < 0.5)
        if len(ys) == 0: return None
        i = np.lexsort((xs, ys))[0]; return int(ys[i]), int(xs[i])

    items = sorted(parts, key=lambda t: area(t[1]), reverse=True)
    sheets = []
    for (nm, poly, w, h, ar) in items:
        rots = (0, 1, 2, 3); flips = (False, True) if nm.startswith("rib") else (False,)
        placed = False
        for sh in sheets + [None]:
            if sh is None: sh = {"grid": np.zeros((GH, GW), bool), "placed": []}; sheets.append(sh)
            best = None
            for fl in flips:
                for rt in rots:
                    m, pm = mask_of(poly, rt, fl)
                    p = try_place(sh["grid"], m)
                    if p and (best is None or p[0] < best[0]): best = (p[0], p[1], m, pm)
            if best:
                gy, gx, m, pm = best; mh, mw = m.shape
                sh["grid"][gy:gy+mh, gx:gx+mw] |= m
                sh["placed"].append((nm, pm + [gx*res, gy*res])); placed = True; break
    return sheets


def comb_split(poly, axis, pos, fdepth, fw):
    """Polygon an einer Linie (axis 'x'=vertikal/'y'=horizontal bei pos) mit INEINANDER-
    GREIFENDEN Fingerzinken teilen. Global gebändertes Muster -> beide Hälften passen formschlüssig."""
    g = SP(poly)
    if not g.is_valid: g = g.buffer(0)
    x0, y0, x1, y1 = g.bounds
    if axis == "x":
        A_t, B_t = [], []; k = int(np.floor(y0/fw)); y = k*fw
        while y < y1:
            z0, z1 = max(y, y0), min(y+fw, y1)
            if k % 2 == 0: A_t.append(box(pos, z0, pos+fdepth, z1))      # A-Zahn ragt nach +x
            else:          B_t.append(box(pos-fdepth, z0, pos, z1))      # B-Zahn -> Nut in A
            k += 1; y = k*fw
        reg = box(x0-50, y0-50, pos, y1+50)
    else:
        A_t, B_t = [], []; k = int(np.floor(x0/fw)); x = k*fw
        while x < x1:
            s0, s1 = max(x, x0), min(x+fw, x1)
            if k % 2 == 0: A_t.append(box(s0, pos, s1, pos+fdepth))
            else:          B_t.append(box(s0, pos-fdepth, s1, pos))
            k += 1; x = k*fw
        reg = box(x0-50, y0-50, x1+50, pos)
    if A_t: reg = reg.union(unary_union(A_t))
    if B_t: reg = reg.difference(unary_union(B_t))
    A = g.intersection(reg); B = g.difference(reg)

    def expl(gg):
        out = []
        for h in (list(gg.geoms) if gg.geom_type in ("MultiPolygon", "GeometryCollection") else [gg]):
            if h.geom_type == "Polygon" and h.area >= 15: out.append(np.array(h.exterior.coords))
        return out
    return expl(A), expl(B)


def split_at_lines(placed, xlines, ylines, fdepth, fw):
    """Alle Teile an den Zonengrenzen (xlines vertikal, ylines horizontal) verzinkt teilen."""
    items = list(placed)
    for gx in xlines:
        new = []
        for (nm, p) in items:
            if p[:, 0].min() < gx-0.5 and p[:, 0].max() > gx+0.5:
                A, B = comb_split(p, "x", gx, fdepth, fw)
                new += [(nm, q) for q in A] + [(nm, q) for q in B]
            else: new.append((nm, p))
        items = new
    for gy in ylines:
        new = []
        for (nm, p) in items:
            if p[:, 1].min() < gy-0.5 and p[:, 1].max() > gy+0.5:
                A, B = comb_split(p, "y", gy, fdepth, fw)
                new += [(nm, q) for q in A] + [(nm, q) for q in B]
            else: new.append((nm, p))
        items = new
    return items


def frame_engrave(zw, zh):
    """Cutter-Rahmen + Eck-Füße + Registrier-Kreuze (Gravur, Koordinaten lokal 0..zw/0..zh)."""
    eng = []
    foot = 18.0                                   # Länge der Eck-Füße
    for (cx, cy, sx, sy) in [(0, 0, 1, 1), (zw, 0, -1, 1), (0, zh, 1, -1), (zw, zh, -1, -1)]:
        eng.append(np.array([(cx+sx*foot, cy), (cx, cy), (cx, cy+sy*foot)]))   # L-Fuß
    # Registrier-Kreuze an den Kantenmitten (beim Umsetzen aneinander ausrichten)
    for (mx, my) in [(zw/2, 0), (zw/2, zh), (0, zh/2), (zw, zh/2)]:
        eng.append(np.array([(mx-7, my), (mx+7, my)])); eng.append(np.array([(mx, my-7), (mx, my+7)]))
    return eng


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--sheet", default="1200x600"); ap.add_argument("--machine", default="410x400")
    ap.add_argument("--gap", type=float, default=4.0); ap.add_argument("--finger", type=float, default=12.0)
    ap.add_argument("--fdepth", type=float, default=4.0, help="Zinken-Tiefe an Zonengrenzen (flach ok, wird verleimt)")
    ap.add_argument("--margin", type=float, default=6.0,
                    help="Sicherheitsrand je Zone (Cutter-Verfahrweg kleiner als nominal)")
    ap.add_argument("--gcode", action="store_true")
    ap.add_argument("--feed", type=float, default=300); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=20)
    ap.add_argument("--out", default="/tmp/zonen")
    a = ap.parse_args()
    SW, SH = (float(x) for x in a.sheet.lower().split("x"))
    MW, MH = (float(x) for x in a.machine.lower().split("x"))
    os.makedirs(a.out, exist_ok=True)
    # Spalten/Zeilen so, dass Zone + beidseitige Zinken + Rand IMMER <= Cutter-Fläche bleibt
    lim_w, lim_h = MW - 2*a.fdepth - a.margin, MH - 2*a.fdepth - a.margin
    ncols = max(1, int(np.ceil(SW/lim_w))); nrows = max(1, int(np.ceil(SH/lim_h)))
    STEPX, STEPY = SW/ncols, SH/nrows

    parts = []
    for fn in sorted(glob.glob(os.path.join(a.dir, "rib*.svg"))):
        ps = polys_from_svg(fn)
        if ps: p = max(ps, key=area); p = p - p.min(0); parts.append((os.path.basename(fn)[:-4], p, np.ptp(p[:, 0]), np.ptp(p[:, 1]), area(p)))
    for fn in glob.glob(os.path.join(a.dir, "deck", "deck_cut_layout.svg")) + glob.glob(os.path.join(a.dir, "deck_cut_layout.svg")):
        for k, p in enumerate(polys_from_svg(fn)):
            p = p - p.min(0); parts.append((f"deck{k}", p, np.ptp(p[:, 0]), np.ptp(p[:, 1]), area(p)))
    tot = sum(pp[4] for pp in parts)

    sheets = form_nest(parts, SW, SH, a.gap)
    xlines = [STEPX*i for i in range(1, ncols)]
    ylines = [STEPY*j for j in range(1, nrows)]

    total_zones = 0; over = 0; manifest = [
        f"ZONEN-NEST  Platte {SW:.0f}x{SH:.0f}  |  Cutter {MW:.0f}x{MH:.0f} (Rand {a.margin:.0f}, Zinken {a.fdepth:.0f})",
        f"{len(parts)} Teile, echte Fläche {tot/100:.0f} cm²  |  {len(sheets)} Kaufplatten, Raster {ncols}x{nrows} Zonen/Platte (Zone ~{STEPX:.0f}x{STEPY:.0f})",
        "Teile über Zonengrenzen sind mit FINGERZINKEN geteilt (verleimen). Pro Zone: Cutter-Rahmen+Eck-Füße+Registrier-Kreuze graviert.",
        "UMSETZEN: Werkstück an fester Anschlag-Ecke spannen; Schnitt mittig im gravierten Rahmen. Für die nächste",
        "Zone Werkstück um genau eine Zonenbreite weiterschieben, bis die Registrier-Kreuze wieder am Rahmen/Nullpunkt liegen.", ""]

    for si, sh in enumerate(sheets):
        items = split_at_lines(sh["placed"], xlines, ylines, a.fdepth, a.finger)
        zones = {}
        for (nm, p) in items:
            c = p.mean(0); col = min(ncols-1, int(c[0]//STEPX)); row = min(nrows-1, int(c[1]//STEPY))
            zones.setdefault((row, col), []).append((nm, p))
        fig, ax = plt.subplots(figsize=(13, 13*SH/SW))
        ax.add_patch(plt.Rectangle((0, 0), SW, SH, fill=False, ec="k", lw=2))
        for gx in xlines: ax.axvline(gx, color="purple", ls="--", lw=1.2)
        for gy in ylines: ax.axhline(gy, color="purple", ls="--", lw=1.2)
        for (nm, p) in items:
            ax.add_patch(MplPoly(p, closed=True, fc="#e0b878", ec="saddlebrown", lw=0.4))
        for (row, col), zl in sorted(zones.items()):
            total_zones += 1
            P = np.vstack([p for (nm, p) in zl]); mn = P.min(0); w, h = np.ptp(P, 0)
            if w > MW+0.5 or h > MH+0.5: over += 1
            off = mn - [(MW-w)/2, (MH-h)/2]        # Inhalt im Cutter-Rahmen zentrieren
            cut = [p - off for (nm, p) in zl]
            eng = frame_engrave(MW, MH) + glyph_strokes(f"P{si+1} Z{row}{col}", 12, MH-18, h=9)
            znm = f"{a.out}/platte{si+1}_zone_r{row}c{col}"
            svg_write(f"{znm}.svg", cut, [], [], eng, 0)
            if a.gcode:
                gcode_write(f"{znm}.gcode", cut, [], [], eng, 0, a.feed, a.power, a.passes, a.eng_power)
            ax.text(col*STEPX+STEPX/2, row*STEPY+STEPY/2, f"Z{row}{col}\n{len(zl)} Teile\n{w:.0f}x{h:.0f}",
                    ha="center", va="center", color="purple", fontsize=10, weight="bold", alpha=0.55)
        ax.set_xlim(-10, SW+10); ax.set_ylim(-10, SH+10); ax.set_aspect("equal"); ax.invert_yaxis()
        ax.set_title(f"Platte {si+1}/{len(sheets)} — {len(zones)} Schnittzonen (je ≤{MW:.0f}x{MH:.0f}), lila=Zinken-Grenze")
        plt.tight_layout(); plt.savefig(f"{a.out}/platte_{si+1:02d}.png", dpi=95); plt.close(fig)
        manifest.append(f"Platte {si+1}: {len(zones)} Schnittzonen")
    if over: manifest.append(f"!! {over} Zonen > Cutter ({MW:.0f}x{MH:.0f}) — fdepth/margin kleiner oder feiner rastern")

    manifest.insert(3, f"==> {len(sheets)} Kaufplatten, {total_zones} Schnitt-Durchgänge "
                       f"(Verschnitt {100*(1-tot/(SW*SH*len(sheets))):.0f} %)")
    open(f"{a.out}/MANIFEST.txt", "w").write("\n".join(manifest)+"\n")
    print("\n".join(manifest))
    print(f"\n-> {os.path.abspath(a.out)}/  (platte_*.png + zone-SVGs" + (" + gcode" if a.gcode else "") + ")")


if __name__ == "__main__":
    main()
