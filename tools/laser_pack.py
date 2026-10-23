#!/usr/bin/env python3
"""laser_pack.py — kleine Teile DICHT auf Bretter PACKEN (nicht teilen) + 2-Durchgang-Gcode je Brett.

Für Teile die schon aufs Brett passen (kein Zonen-Split nötig). Shelf-Packing mit 90°-Drehung.
Liest rib*.svg (Cut #f00, Gravur #0a0), legt sie auf --sheet-Bretter, schreibt pro Brett
G-Code (Gravur zuerst, dann N Cut-Durchgänge) + eine Pack-Vorschau PNG.

  python3 tools/laser_pack.py <dir> --sheet 200x250 --passes 2 --out <dir>/bretter
"""
import argparse, glob, os, re, math, fnmatch, numpy as np


def parse(fn):
    txt = open(fn).read(); cuts = []; eng = []
    for m in re.finditer(r'<path d="([^"]*)"[^>]*stroke="(#[0-9a-f]+)"', txt):
        pts = [(float(a), float(b)) for a, b in re.findall(r'([-\d.]+),([-\d.]+)', m.group(1))]
        if m.group(2) == '#f00': cuts.append(pts)
        elif m.group(2) == '#0a0': eng.append(pts)
    return cuts, eng


def bbox(polys):
    a = np.array([p for pl in polys for p in pl]); return a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()


def shift(L, dx, dy): return [[(x+dx, y+dy) for x, y in pl] for pl in L]


def norm(cuts, eng):
    x0, y0, _, _ = bbox(cuts); return shift(cuts, -x0, -y0), shift(eng, -x0, -y0)


def rot90(cuts, eng):
    g = lambda L: [[(y, -x) for x, y in pl] for pl in L]
    return norm(g(cuts), g(eng))


def rot180(cuts, eng):
    g = lambda L: [[(-x, -y) for x, y in pl] for pl in L]
    return norm(g(cuts), g(eng))


def col_profile(cuts, res, pad=0.0):
    """Pro-Spalte Unter-/Oberkante (vertikale Material-Ausdehnung) in Raster res.
    Fuer Skyline-Nesting: so verzahnen sich die Gelaende-Dreiecke statt Bounding-Box-Verschnitt.
    pad = Sicherheits-Puffer (haelt Nachbarn auf Abstand -> kein Overlap)."""
    from shapely.geometry import Polygon as SP, LineString
    polys = [SP(c).buffer(0) for c in cuts if len(c) >= 4]
    poly = max(polys, key=lambda g: g.area) if polys else None
    if poly is None or poly.is_empty:
        return None
    if pad > 0: poly = poly.buffer(pad, join_style=2)
    x0, y0, x1, y1 = poly.bounds
    nc = max(1, int(round((x1-x0)/res)))
    bot = [None]*nc; top = [None]*nc
    for i in range(nc):
        xx = x0 + (i+0.5)*res
        it = poly.intersection(LineString([(xx, y0-1), (xx, y1+1)]))
        if it.is_empty: continue
        ys = []
        for g in ([it] if it.geom_type == "LineString" else list(getattr(it, "geoms", [it]))):
            b = g.bounds; ys += [b[1], b[3]]
        if ys: bot[i] = min(ys)-y0; top[i] = max(ys)-y0
    return bot, top, (x1-x0), (y1-y0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--sheet", default="200x250"); ap.add_argument("--margin", type=float, default=5.0)
    ap.add_argument("--gap", type=float, default=6.0)
    ap.add_argument("--feed", type=float, default=300); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--eng-power", type=float, default=85); ap.add_argument("--eng-feed", type=float, default=1200)
    ap.add_argument("--priority", action="store_true", help="Coarse-first: jede zweite Rippe zuerst (ergibt frueh ein stehendes grobes Gitter), Detail spaeter")
    ap.add_argument("--nest", action="store_true", help="Skyline-Nesting (Gelaende-Rippen verzahnen sich in die Taeler der vorigen -> viel weniger Verschnitt)")
    ap.add_argument("--res", type=float, default=2.0, help="Nesting-Raster mm")
    ap.add_argument("--only", default="", help="Nur diese Teile packen: Komma-Liste von Rippen-Namen OHNE 'rib'-Prefix (z.B. Y0,X0a), fnmatch-Globs erlaubt (z.B. 'X*a'). Fuer das Nachlegen schon geschnittener Saetze.")
    ap.add_argument("--exclude", default="", help="Diese Teile AUSLASSEN (z.B. schon geschnittene), gleiche Syntax wie --only")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    out = a.out or os.path.join(a.dir, "bretter"); os.makedirs(out, exist_ok=True)
    SW, SH = [float(v) for v in a.sheet.lower().split("x")]
    BW, BH = SW-2*a.margin, SH-2*a.margin

    only = [s.strip() for s in a.only.split(",") if s.strip()]
    excl = [s.strip() for s in a.exclude.split(",") if s.strip()]
    def _keep(nm):
        if only and not any(fnmatch.fnmatch(nm, p) for p in only): return False
        if excl and any(fnmatch.fnmatch(nm, p) for p in excl): return False
        return True
    pieces = []; skipped = []
    for fn in sorted(glob.glob(os.path.join(a.dir, "rib*.svg"))):
        nm = os.path.basename(fn)[3:-4]
        if not _keep(nm): skipped.append(nm); continue
        c, e = parse(fn)
        if not c: continue
        c, e = norm(c, e); _, _, w, h = bbox(c)
        pieces.append([nm, c, e, w, h])
    if only or excl:
        print("[pack] %d Teile ausgewaehlt: %s" % (len(pieces), ", ".join(p[0] for p in pieces)))
        if skipped: print("[pack] %d uebersprungen: %s" % (len(skipped), ", ".join(skipped)))
    if not pieces:
        print("!! Keine Teile nach Filter uebrig — --only/--exclude pruefen."); return
    if a.priority:
        def num(nm):
            m = re.search(r'(\d+)', nm); return int(m.group(1)) if m else 0
        groups = [sorted([p for p in pieces if num(p[0]) % 2 == 0], key=lambda p: -p[4]),   # grob zuerst
                  sorted([p for p in pieces if num(p[0]) % 2 == 1], key=lambda p: -p[4])]    # dann Detail
    else:
        groups = [sorted(pieces, key=lambda p: -p[4])]

    sheets = []
    if a.nest:
        from matplotlib.path import Path as _MP
        try:
            from scipy.ndimage import binary_dilation as _dil
        except Exception:
            _dil = None
        res = a.res; BWg = int(BW/res); BHg = int(BH/res); d = max(1, int(round(a.gap/2/res)))
        rcache = {}
        def parea(p):
            x = p[:, 0]; y = p[:, 1]; return abs(np.dot(x, np.roll(y, 1))-np.dot(y, np.roll(x, 1)))/2
        def raster(pc, flip, r90):
            key = (pc[0], flip, r90)
            if key not in rcache:
                cc, ee = (rot90(pc[1], pc[2]) if r90 else (pc[1], pc[2]))
                if flip: cc, ee = rot180(cc, ee)
                polys = [np.array(c, float) for c in cc if len(c) >= 4]
                fp = max(polys, key=parea) if polys else None
                if fp is None: rcache[key] = None; return None
                nx = max(1, int(np.ceil(fp[:, 0].max()/res))); ny = max(1, int(np.ceil(fp[:, 1].max()/res)))
                xs = (np.arange(nx)+0.5)*res; ys = (np.arange(ny)+0.5)*res
                X, Y = np.meshgrid(xs, ys)
                m0 = _MP(fp[:, :2]).contains_points(np.column_stack([X.ravel(), Y.ravel()])).reshape(ny, nx)
                big = np.zeros((ny+2*d, nx+2*d), bool); big[d:d+ny, d:d+nx] = m0      # Rand fuer Gap
                mask = _dil(big, iterations=d) if _dil is not None else big           # auf Abstand aufblasen
                rcache[key] = (cc, ee, mask)
            return rcache[key]
        def fit(occ, mask):
            mny, mnx = mask.shape
            if mny > BHg or mnx > BWg: return None
            for yy in range(0, BHg-mny+1):                 # bottom-left (beste Ausnutzung bei brett~=rippenhoehe)
                band = occ[yy:yy+mny]
                for xx in range(0, BWg-mnx+1):
                    if not (band[:, xx:xx+mnx] & mask).any(): return (yy, xx)
            return None
        for gi, grp in enumerate(groups):
            gsheets = []
            for pc in grp:
                cand = [(o, r) for o in ((False, False), (True, False), (False, True), (True, True))
                        for r in [raster(pc, o[0], o[1])] if r]
                done = False
                for sh in gsheets:
                    best = None
                    for f, (cc, ee, mask) in cand:
                        p = fit(sh['occ'], mask)
                        if p and (best is None or p < best[0]): best = (p, cc, ee, mask)
                    if best:
                        (yy, xx), cc, ee, mask = best
                        sh['occ'][yy:yy+mask.shape[0], xx:xx+mask.shape[1]] |= mask
                        sh['items'].append((pc[0], cc, ee, (xx+d)*res, (yy+d)*res)); done = True; break
                if not done:
                    sh = {'items': [], 'occ': np.zeros((BHg, BWg), bool)}
                    best = None
                    for f, (cc, ee, mask) in cand:
                        p = fit(sh['occ'], mask)
                        if p and (best is None or p < best[0]): best = (p, cc, ee, mask)
                    if best is None:
                        print(f"  WARN: {pc[0]} passt NICHT in {BW:.0f}x{BH:.0f} mm (zu gross) -> uebersprungen")
                        continue
                    gsheets.append(sh)
                    (yy, xx), cc, ee, mask = best
                    sh['occ'][yy:yy+mask.shape[0], xx:xx+mask.shape[1]] |= mask
                    sh['items'].append((pc[0], cc, ee, (xx+d)*res, (yy+d)*res))
            for sh in gsheets: sh['grp'] = gi
            sheets += gsheets
    else:
        def try_put(sh, pc):
            name, c, e, w, h = pc
            for (cc, ee, ww, hh) in [(c, e, w, h), (*rot90(c, e), h, w)]:
                if sh['x']+ww <= BW and sh['y']+hh <= BH:                 # in aktuelle Reihe
                    sh['items'].append((name, cc, ee, sh['x'], sh['y']))
                    sh['x'] += ww+a.gap; sh['rh'] = max(sh['rh'], hh); return True
            ny = sh['y']+sh['rh']+a.gap
            for (cc, ee, ww, hh) in [(c, e, w, h), (*rot90(c, e), h, w)]:
                if ww <= BW and ny+hh <= BH:                             # neue Reihe
                    sh['items'].append((name, cc, ee, 0, ny)); sh['x'] = ww+a.gap; sh['y'] = ny; sh['rh'] = hh; return True
            return False
        for gi, grp in enumerate(groups):
            gsheets = []                                                 # jede Gruppe eigene Bretter (grob|detail nicht mischen)
            for pc in grp:
                if not any(try_put(sh, pc) for sh in gsheets):
                    sh = {'items': [], 'x': 0, 'y': 0, 'rh': 0}; gsheets.append(sh); try_put(sh, pc)
            for sh in gsheets: sh['grp'] = gi
            sheets += gsheets

    S = int(a.power*10); ES = int(a.eng_power*10)
    print(f"{len(pieces)} Teile -> {len(sheets)} Bretter ({a.sheet})")
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    for bi, sh in enumerate(sheets, 1):
        G = ["G21", "G90", "G17", "M5 S0", "G92 X0 Y0"]
        def trace(poly, close, s, f):
            G.append("M5"); G.append(f"G0 X{poly[0][0]:.2f} Y{poly[0][1]:.2f}"); G.append(f"M4 S{int(s)}")
            for p in poly[1:]: G.append(f"G1 X{p[0]:.2f} Y{p[1]:.2f} F{f:.0f}")
            if close: G.append(f"G1 X{poly[0][0]:.2f} Y{poly[0][1]:.2f} F{f:.0f}")
            G.append("M5")
        M = a.margin
        for (name, cc, ee, ox, oy) in sh['items']:
            for st in ee: trace([(x+ox+M, y+oy+M) for x, y in st], False, ES, a.eng_feed)
        for _ in range(a.passes):
            for (name, cc, ee, ox, oy) in sh['items']:
                for c in cc: trace([(x+ox+M, y+oy+M) for x, y in c], True, S, a.feed)
        G += ["M5 S0", "G0 X0 Y0"]
        open(f"{out}/brett{bi}.gcode", "w").write("\n".join(G)+"\n")
        allp = np.array([(x+ox+M, y+oy+M) for (n, cc, ee, ox, oy) in sh['items'] for c in cc for x, y in c])
        cl = sum(math.hypot(c[i+1][0]-c[i][0], c[i+1][1]-c[i][1]) for (n, cc, ee, ox, oy) in sh['items'] for c in cc for i in range(len(c)-1))
        fig, ax = plt.subplots(figsize=(4, 5))
        ax.add_patch(plt.Rectangle((0, 0), SW, SH, fill=False, ec='b'))
        for (name, cc, ee, ox, oy) in sh['items']:
            for c in cc:
                p = np.array([(x+ox+M, y+oy+M) for x, y in c]); ax.plot(p[:, 0], p[:, 1], 'r', lw=0.6)
            ax.text(ox+M+5, oy+M+5, name, fontsize=7)
        ax.set_xlim(-5, SW+5); ax.set_ylim(-5, SH+5); ax.set_aspect('equal'); ax.invert_yaxis()
        plt.tight_layout(); plt.savefig(f"{out}/brett{bi}.png", dpi=90); plt.close()
        print(f"  brett{bi}: {','.join(n for n,_,_,_,_ in sh['items'])} | {allp[:,0].max():.0f}x{allp[:,1].max():.0f}mm | {a.passes}x@{a.feed:.0f}={cl*a.passes/a.feed:.1f}min")


if __name__ == "__main__":
    main()
