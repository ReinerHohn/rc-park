#!/usr/bin/env python3
"""laser_nest.py — Laser-Teile (SVGs) auf Platten nesten + Plattenzahl/Verschnitt.

Liest alle <path ... Z>-Polygone aus den SVGs eines Ordners (Rippen + deck_cut_layout),
bestimmt je Teil die Bounding-Box + echte Fläche, packt sie (gedreht erlaubt) auf
Platten W×H (Shelf / First-Fit-Decreasing) und zeigt: wie viele Platten + Verschnitt.

  python3 tools/laser_nest.py modelle/hirschsprung_geruest --sheet 1200x600 --gap 4
"""
import argparse, glob, os, re, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly


def polys_from_svg(fn):
    out = []
    for d in re.findall(r'<path d="M ([^"]+?) Z"', open(fn).read()):
        pts = []
        for tok in d.replace(" L", " ").split():
            if "," in tok: pts.append(tuple(map(float, tok.split(","))))
        if len(pts) >= 3: out.append(np.array(pts, float))
    return out


def area(poly):
    x, y = poly[:, 0], poly[:, 1]
    return abs(np.sum(x*np.roll(y, -1) - np.roll(x, -1)*y))/2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--sheet", default="1200x600"); ap.add_argument("--gap", type=float, default=4.0)
    ap.add_argument("--split-len", type=float, default=0.0,
                    help="Rippen in Stücke <= N mm zerteilen (Puzzle/Fingerzinken) -> packt dichter, spart Verschnitt. 0=aus")
    ap.add_argument("--out", default="/tmp/nest")
    a = ap.parse_args()
    SW, SH = (float(x) for x in a.sheet.lower().split("x"))
    os.makedirs(a.out, exist_ok=True)

    def split_poly(p, maxlen):
        """Polygon entlang vertikaler Linien in Stücke <= maxlen (für geteilte Rippen)."""
        from shapely.geometry import Polygon as SPoly, box
        g = SPoly(p)
        if not g.is_valid: g = g.buffer(0)
        x0, y0, x1, y1 = g.bounds; W = x1 - x0
        n = max(1, int(np.ceil(W / maxlen)))
        if n == 1: return [p]
        step = W / n; out = []
        for k in range(n):
            clip = box(x0 + k*step, y0 - 1, x0 + (k+1)*step, y1 + 1)
            seg = g.intersection(clip)
            geoms = list(seg.geoms) if seg.geom_type == "MultiPolygon" else [seg]
            for gg in geoms:
                if gg.area < 1: continue
                out.append(np.array(gg.exterior.coords))
        return out

    parts = []   # (name, poly_local(0-based), w, h, area)
    # Rippen: je SVG das GRÖSSTE Polygon = das Teil (Tunnel-Löcher/Gravur ignorieren fürs Nesten)
    for fn in sorted(glob.glob(os.path.join(a.dir, "rib*.svg"))):
        ps = polys_from_svg(fn)
        if not ps: continue
        p = max(ps, key=area); p = p - p.min(0)
        segs = split_poly(p, a.split_len) if a.split_len > 0 else [p]
        for si, sp in enumerate(segs):
            sp = sp - sp.min(0); nm = os.path.basename(fn)[:-4] + (f"_{si}" if len(segs) > 1 else "")
            parts.append((nm, sp, np.ptp(sp[:, 0]), np.ptp(sp[:, 1]), area(sp)))
    # Deck: jedes Polygon im Layout = eine Platte
    for fn in glob.glob(os.path.join(a.dir, "deck", "deck_cut_layout.svg")) + glob.glob(os.path.join(a.dir, "deck_cut_layout.svg")):
        for k, p in enumerate(polys_from_svg(fn)):
            p = p - p.min(0)
            parts.append((f"deck{k}", p, np.ptp(p[:, 0]), np.ptp(p[:, 1]), area(p)))

    tot_area = sum(pp[4] for pp in parts)
    print(f"{len(parts)} Teile, echte Fläche {tot_area/100:.0f} cm²  |  Platte {SW:.0f}x{SH:.0f} = {SW*SH/100:.0f} cm²")
    print(f"theoretisches Minimum (perfekt): {tot_area/(SW*SH):.2f} -> {int(np.ceil(tot_area/(SW*SH)))} Platten")

    # --- ECHTES FORM-NESTING: rasterbasiert, Bottom-Left, Rotation+Spiegel, FFT-Kollision ---
    from matplotlib.path import Path as MPath
    from scipy.signal import fftconvolve
    res = 4.0                                              # mm/Rasterzelle
    GW, GH = int(SW/res), int(SH/res)
    gm = max(1, int(round(a.gap/res)))                     # Spalt in Zellen

    def mask_of(poly, rot, flip):
        p = poly.copy()
        if flip: p = np.column_stack([-p[:, 0], p[:, 1]])
        if rot:  p = np.column_stack([-p[:, 1], p[:, 0]]) if rot == 1 else (
                     np.column_stack([-p[:, 0], -p[:, 1]]) if rot == 2 else np.column_stack([p[:, 1], -p[:, 0]]))
        p = p - p.min(0)
        w = int(np.ceil(np.ptp(p[:, 0])/res))+1; h = int(np.ceil(np.ptp(p[:, 1])/res))+1
        gx, gy = np.meshgrid((np.arange(w)+0.5)*res, (np.arange(h)+0.5)*res)
        m = MPath(p).contains_points(np.column_stack([gx.ravel(), gy.ravel()])).reshape(h, w)
        if gm: from scipy.ndimage import binary_dilation; m = binary_dilation(m, iterations=gm)
        return m, p

    items = sorted(parts, key=lambda t: area(t[1]), reverse=True)
    sheets = []  # list of dict(grid, placed=[(nm,p_mm,ox,oy)])

    def try_place(sh, mask):
        mh, mw = mask.shape
        if mw > GW or mh > GH: return None
        conv = fftconvolve(sh["grid"].astype(float), mask[::-1, ::-1].astype(float), mode="valid")
        free = conv < 0.5                                  # Positionen ohne Kollision
        ys, xs = np.where(free)
        if len(ys) == 0: return None
        i = np.lexsort((xs, ys))[0]                        # Bottom-Left (kleinstes y, dann x)
        return int(ys[i]), int(xs[i])

    for (nm, poly, w, h, ar) in items:
        rots = (0, 1, 2, 3); flips = (False, True) if nm.startswith("rib") else (False,)
        done = False
        for sh in sheets:
            best = None
            for fl in flips:
                for rt in rots:
                    m, pm = mask_of(poly, rt, fl)
                    pos = try_place(sh, m)
                    if pos and (best is None or pos[0] < best[0]):
                        best = (pos[0], pos[1], m, pm)
            if best:
                gy, gx, m, pm = best; mh, mw = m.shape
                sh["grid"][gy:gy+mh, gx:gx+mw] |= m
                sh["placed"].append((nm, pm + [gx*res, gy*res])); done = True; break
        if not done:
            sh = {"grid": np.zeros((GH, GW), bool), "placed": []}
            best = None
            for fl in flips:
                for rt in rots:
                    m, pm = mask_of(poly, rt, fl)
                    pos = try_place(sh, m)
                    if pos and (best is None or pos[0] < best[0]): best = (pos[0], pos[1], m, pm)
            if best:
                gy, gx, m, pm = best; mh, mw = m.shape
                sh["grid"][gy:gy+mh, gx:gx+mw] |= m
                sh["placed"].append((nm, pm + [gx*res, gy*res]))
            sheets.append(sh)

    used = SW*SH*len(sheets)
    print(f"\n==> {len(sheets)} x {SW:.0f}x{SH:.0f} noetig  (Verschnitt {100*(1-tot_area/used):.0f} %, Minimum waere {int(np.ceil(tot_area/(SW*SH)))})")

    for si, sh in enumerate(sheets):
        fig, ax = plt.subplots(figsize=(12, 12*SH/SW))
        ax.add_patch(plt.Rectangle((0, 0), SW, SH, fill=False, ec="k", lw=2))
        for (nm, pm) in sh["placed"]:
            ax.add_patch(MplPoly(pm, closed=True, fc="tan", ec="saddlebrown", lw=0.4))
            c = pm.mean(0); ax.text(c[0], c[1], nm.replace("deck", "d").replace("rib", ""), fontsize=4.5, ha="center")
        ax.set_xlim(-10, SW+10); ax.set_ylim(-10, SH+10); ax.set_aspect("equal")
        ax.set_title(f"Platte {si+1}/{len(sheets)}  ({len(sh['placed'])} Teile) {SW:.0f}x{SH:.0f}x4mm")
        plt.tight_layout(); plt.savefig(f"{a.out}/platte_{si+1:02d}.png", dpi=95); plt.close(fig)
    print(f"Layouts -> {os.path.abspath(a.out)}/platte_*.png")


if __name__ == "__main__":
    main()
