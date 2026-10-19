#!/usr/bin/env python3
"""laser_zone_nest.py — FLEXIBLER Zonen-Nester: beliebige Blattgröße auf kleinem Cutter.

Packt alle Teile dicht auf die Blattgröße (--sheet), legt dann ein Raster aus <=Cutter-großen
SCHNITTZONEN (--machine) drüber. Teile über eine Zonengrenze werden DORT mit FINGERZINKEN
geteilt (Hälften in Nachbarzonen, verleimen). Pro Zone: fertige SVG+Gcode mit Cutter-Rahmen,
Eck-Füßen und Registrier-Kreuzen -> Werkstück NICHT sägen, nur umsetzen & schneiden.

  Bett-große Blätter -> 1 Zone/Blatt (kein Umsetzen):   --sheet 400x400
  Große Platte tilen (umsetzen):                         --sheet 1200x600

  python3 tools/laser_zone_nest.py modelle/hirschsprung_geruest \
      --sheet 1200x600 --machine 410x400 --gcode --out /tmp/zonen
"""
import argparse, glob, os, re, math, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly
from matplotlib.path import Path as MPath
from scipy.signal import fftconvolve
from scipy.ndimage import binary_dilation
from shapely.geometry import Polygon as SP, box
from shapely.ops import unary_union
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from laser_relief_kit import glyph_strokes


def area(p):
    x, y = p[:, 0], p[:, 1]
    return abs(np.sum(x*np.roll(y, -1) - np.roll(x, -1)*y))/2


def parse_paths(txt):
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
        for i, panel in enumerate(cut):
            mn, mx = panel.min(0), panel.max(0)
            pe = [s for s in eng if (mn[0]-2 <= s[:, 0].mean() <= mx[0]+2 and mn[1]-2 <= s[:, 1].mean() <= mx[1]+2)]
            parts.append({"name": f"deck{i}", "cut": [panel], "eng": pe})
    for fn in sorted(glob.glob(os.path.join(d, "tunnel", "*.svg"))):   # Tunnel-Kit mitschneiden
        cut, eng = parse_paths(open(fn).read())
        if cut: parts.append({"name": os.path.basename(fn)[:-4], "cut": cut, "eng": eng})
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


def comb_split(poly, axis, pos, fdepth, fw):
    g = SP(poly)
    if not g.is_valid: g = g.buffer(0)
    x0, y0, x1, y1 = g.bounds
    A_t, B_t = [], []
    if axis == "x":
        k = int(np.floor(y0/fw)); y = k*fw
        while y < y1:
            z0, z1 = max(y, y0), min(y+fw, y1)
            (A_t if k % 2 == 0 else B_t).append(box(pos, z0, pos+fdepth, z1) if k % 2 == 0 else box(pos-fdepth, z0, pos, z1))
            k += 1; y = k*fw
        reg = box(x0-50, y0-50, pos, y1+50)
    else:
        k = int(np.floor(x0/fw)); x = k*fw
        while x < x1:
            s0, s1 = max(x, x0), min(x+fw, x1)
            (A_t if k % 2 == 0 else B_t).append(box(s0, pos, s1, pos+fdepth) if k % 2 == 0 else box(s0, pos-fdepth, s1, pos))
            k += 1; x = k*fw
        reg = box(x0-50, y0-50, x1+50, pos)
    if A_t: reg = reg.union(unary_union(A_t))
    if B_t: reg = reg.difference(unary_union(B_t))
    A = g.intersection(reg); B = g.difference(reg)

    def expl(gg):
        return [np.array(h.exterior.coords) for h in (list(gg.geoms) if gg.geom_type in ("MultiPolygon", "GeometryCollection") else [gg])
                if h.geom_type == "Polygon" and h.area >= 15]
    return expl(A), expl(B)


def split_at_lines(placed, xlines, ylines, fdepth, fw):
    items = [(pt["name"], p, e) for pt in placed for (p, e) in [(pt["cut"], pt["eng"])]]
    # Teile als (name, cutpolys, engs); zum Splitten je Cut-Poly einzeln behandeln, eng mitnehmen
    out = []
    for (nm, cuts, engs) in items:
        out.append([nm, cuts, engs])
    def do(axis, lines):
        nonlocal out
        for L in lines:
            nxt = []
            for (nm, cuts, engs) in out:
                allp = np.vstack(cuts); lo, hi = (allp[:, 0].min(), allp[:, 0].max()) if axis == "x" else (allp[:, 1].min(), allp[:, 1].max())
                if lo < L-0.5 and hi > L+0.5:
                    Ac, Bc = [], []
                    for c in cuts:
                        a, b = comb_split(c, axis, L, fdepth, fw); Ac += a; Bc += b
                    # Gravur der Seite zuordnen (Mittelpunkt)
                    key = (lambda s: s[:, 0].mean() < L) if axis == "x" else (lambda s: s[:, 1].mean() < L)
                    Ae = [s for s in engs if key(s)]; Be = [s for s in engs if not key(s)]
                    if Ac: nxt.append([nm, Ac, Ae])
                    if Bc: nxt.append([nm, Bc, Be])
                else:
                    nxt.append([nm, cuts, engs])
            out = nxt
    do("x", xlines); do("y", ylines)
    return out


def frame_marks(MW, MH, foot=16.0):
    """Cutter-Rahmen + Eck-Füße + Registrier-Kreuze an Kantenmitten — alles INNERHALB [0,MW]x[0,MH]."""
    e = [np.array([(0, 0), (MW, 0), (MW, MH), (0, MH), (0, 0)])]        # Rahmen = Cutter-Extent
    for (cx, cy, sx, sy) in [(0, 0, 1, 1), (MW, 0, -1, 1), (0, MH, 1, -1), (MW, MH, -1, -1)]:
        e.append(np.array([(cx+sx*foot, cy+sy*2), (cx+sx*2, cy+sy*2), (cx+sx*2, cy+sy*foot)]))
    for (mx, my, dx, dy) in [(MW/2, 8, 1, 0), (MW/2, MH-8, 1, 0), (8, MH/2, 0, 1), (MW-8, MH/2, 0, 1)]:
        e.append(np.array([(mx-6*dx, my-6*dy), (mx+6*dx, my+6*dy)]))    # Kreuz-Balken quer
        e.append(np.array([(mx-6*dy, my-6*dx), (mx+6*dy, my+6*dx)]))
    return e


def write_svg(fn, cuts, engr, MW, MH):
    L = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{MW:.1f}mm" height="{MH:.1f}mm" viewBox="0 0 {MW:.1f} {MH:.1f}">']
    for p in cuts:
        L.append(f'<path d="M ' + " L ".join(f"{x:.2f},{y:.2f}" for x, y in p) + ' Z" fill="none" stroke="#f00" stroke-width="0.1"/>')
    for s in engr:
        L.append(f'<path d="M ' + " L ".join(f"{x:.2f},{y:.2f}" for x, y in s) + '" fill="none" stroke="#0a0" stroke-width="0.1"/>')
    L.append("</svg>"); open(fn, "w").write("\n".join(L)+"\n")


def write_gcode(fn, cuts, engr, feed, power, passes, eng_power):
    S, ES = int(power*10), int(eng_power*10)
    L = ["G21", "G90", "G17", "M5 S0", "G92 X0 Y0"]
    def trace(poly, close, s, f):
        L.append("M5"); L.append(f"G0 X{poly[0][0]:.2f} Y{poly[0][1]:.2f}"); L.append(f"M4 S{s}")
        for p in poly[1:]: L.append(f"G1 X{p[0]:.2f} Y{p[1]:.2f} F{f:.0f}")
        if close: L.append(f"G1 X{poly[0][0]:.2f} Y{poly[0][1]:.2f} F{f:.0f}")
        L.append("M5")
    for s in engr: trace(s, False, ES, 3000)
    for _ in range(passes):
        for p in cuts: trace(p, True, S, feed)
    L += ["M5 S0", "G0 X0 Y0"]; open(fn, "w").write("\n".join(L)+"\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--sheet", default="1200x600"); ap.add_argument("--machine", default="410x400")
    ap.add_argument("--gap", type=float, default=4.0); ap.add_argument("--finger", type=float, default=12.0)
    ap.add_argument("--fdepth", type=float, default=3.0); ap.add_argument("--margin", type=float, default=2.0)
    ap.add_argument("--gcode", action="store_true")
    ap.add_argument("--feed", type=float, default=300); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=20)
    ap.add_argument("--out", default="/tmp/zonen")
    a = ap.parse_args()
    SW, SH = (float(x) for x in a.sheet.lower().split("x"))
    MW, MH = (float(x) for x in a.machine.lower().split("x"))
    os.makedirs(a.out, exist_ok=True)
    for f in glob.glob(os.path.join(a.out, "platte*")): os.remove(f)
    # Zonen so, dass Zone + beidseitige Zinken + Rand IMMER in den Cutter passen
    lim_w = MW - 2*a.fdepth - 2*a.margin; lim_h = MH - 2*a.fdepth - 2*a.margin
    ncols = max(1, int(np.ceil(SW/lim_w))); nrows = max(1, int(np.ceil(SH/lim_h)))
    STEPX, STEPY = SW/ncols, SH/nrows

    parts = load_parts(a.dir)
    tot = sum(max(area(c) for c in P["cut"]) for P in parts)
    sheets = nest(parts, SW, SH, a.gap)
    xlines = [STEPX*i for i in range(1, ncols)]; ylines = [STEPY*j for j in range(1, nrows)]
    tiled = ncols*nrows > 1

    man = [f"ZONEN-NEST  Blatt {SW:.0f}x{SH:.0f}  |  Cutter {MW:.0f}x{MH:.0f}  (Zinken {a.fdepth:.0f}, Rand {a.margin:.0f})",
           f"{len(parts)} Teile, Fläche {tot/100:.0f} cm²  |  {len(sheets)} Blätter, {ncols}x{nrows} Zonen/Blatt (~{STEPX:.0f}x{STEPY:.0f})",
           ("TILING: Werkstück an fester Anschlag-Ecke; pro Zone Rahmen+Füße+Kreuze graviert. Nächste Zone: Werkstück"
            if tiled else "KEIN UMSETZEN: jede Zone = ein eigenes Blatt (Blattgröße = Cutter)."),
           ("um genau eine Zonenbreite weiterschieben, bis die Registrier-Kreuze wieder am Rahmen/Nullpunkt liegen. Zinken verleimen."
            if tiled else ""), ""]

    total_zones = 0; over = 0
    for si, sh in enumerate(sheets):
        items = split_at_lines(sh["parts"], xlines, ylines, a.fdepth, a.finger)
        zones = {}
        for (nm, cuts, engs) in items:
            c = np.vstack(cuts).mean(0)
            col = min(ncols-1, int(c[0]//STEPX)); row = min(nrows-1, int(c[1]//STEPY))
            zones.setdefault((row, col), {"cut": [], "eng": []})
            zones[(row, col)]["cut"] += cuts; zones[(row, col)]["eng"] += engs
        # Overview
        fig, ax = plt.subplots(figsize=(13, 13*SH/SW))
        ax.add_patch(plt.Rectangle((0, 0), SW, SH, fill=False, ec="k", lw=2))
        for gx in xlines: ax.axvline(gx, color="purple", ls="--", lw=1.2)
        for gy in ylines: ax.axhline(gy, color="purple", ls="--", lw=1.2)
        for (nm, cuts, engs) in items:
            for p in cuts: ax.add_patch(MplPoly(p, closed=True, fc="#e0b878", ec="saddlebrown", lw=0.3))
        for (row, col), z in sorted(zones.items()):
            total_zones += 1
            P = np.vstack(z["cut"]); mn = P.min(0); w, h = np.ptp(P, 0)
            if w > MW+0.5 or h > MH+0.5: over += 1
            off = mn - [(MW-w)/2, (MH-h)/2]            # im Cutter-Rahmen zentrieren
            cut = [p - off for p in z["cut"]]; eng = [s - off for s in z["eng"]]
            eng = eng + frame_marks(MW, MH) + glyph_strokes(f"P{si+1} Z{row}{col}", 14, MH-16, h=9)
            base = os.path.join(a.out, f"platte{si+1}_zone_r{row}c{col}")
            write_svg(f"{base}.svg", cut, eng, MW, MH)
            if a.gcode: write_gcode(f"{base}.gcode", cut, eng, a.feed, a.power, a.passes, a.eng_power)
            ax.text(col*STEPX+STEPX/2, row*STEPY+STEPY/2, f"Z{row}{col}\n{len(z['cut'])}T\n{w:.0f}x{h:.0f}",
                    ha="center", va="center", color="purple", fontsize=10, weight="bold", alpha=0.55)
        ax.set_xlim(-10, SW+10); ax.set_ylim(-10, SH+10); ax.set_aspect("equal"); ax.invert_yaxis()
        ax.set_title(f"Blatt {si+1}/{len(sheets)} — {len(zones)} Schnittzonen (je ≤{MW:.0f}x{MH:.0f}), lila=Zinken-Grenze")
        plt.tight_layout(); plt.savefig(os.path.join(a.out, f"platte_{si+1:02d}.png"), dpi=95); plt.close(fig)
        man.append(f"Blatt {si+1}: {len(zones)} Zonen")

    man.insert(2, f"==> {len(sheets)} Blätter, {total_zones} Schnitt-Durchgänge ({'Umsetzungen' if tiled else 'Blätter'}), "
                  f"Verschnitt {100*(1-tot/(SW*SH*len(sheets))):.0f} %")
    if over: man.append(f"!! {over} Zonen > Cutter — --fdepth/--margin kleiner oder --machine prüfen")
    open(os.path.join(a.out, "MANIFEST.txt"), "w").write("\n".join(man)+"\n")
    print("\n".join(man)); print(f"\n-> {os.path.abspath(a.out)}/")


if __name__ == "__main__":
    main()
