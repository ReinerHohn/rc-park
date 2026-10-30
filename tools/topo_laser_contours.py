#!/usr/bin/env python3
"""topo_laser_contours.py — DEM-Fenster in LASER-SCHNITT-Höhenschichten zerlegen.

Klassischer Contour-Stack fürs Lasern: pro Höhenstufe eine flache Lage (Sperrholz/
MDF). Jede Lage = Außenkontur (Cut) + 2 Dübellöcher (Registrierung) + eingravierte
Nummer. Die Dübellöcher liegen am Gipfel → in JEDER Lage vorhanden (Gipfelpunkt ist
in allen Konturen) → man steckt den Stapel über 2 Rundstäbe exakt zusammen.

Vertikal: n_layers Lagen × thickness = Modellhöhe. true-N wären sehr viele Lagen,
darum ist moderate Vertikal-Stauchung (für Laser-Topo üblich) der Default.

  python3 tools/topo_laser_contours.py --layers 25 --thickness 3 --out /tmp/laser
"""
import argparse, os, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BIG = "daten/hoellental/hirsch_big.npy"
MM = 6.25


def contour_polys(Z, level):
    """GESCHLOSSENE, GLATTE Außenkontur(en) der Region Z>=level.
    Kontur aus dem KONTINUIERLICHEN (geglätteten) Feld — runde Kurven statt
    Pixel-Treppe. Rand mit sehr niedrigem Wert padden -> alle Konturen schließen."""
    pad = np.pad(Z, 1, mode="constant", constant_values=float(Z.min()) - 1e6)
    cs = plt.contour(pad, levels=[level])
    segs = cs.allsegs[0] if cs.allsegs else []
    plt.close("all")
    return [s - 1.0 for s in segs if len(s) >= 4]


def svg_path(poly):
    d = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in poly) + " Z"
    return d


def decimate(poly, min_seg):
    """Punkte zusammenfassen, die näher als min_seg mm liegen (weniger Laserzeit)."""
    if min_seg <= 0 or len(poly) < 4:
        return poly
    out = [poly[0]]
    for p in poly[1:]:
        if np.hypot(p[0]-out[-1][0], p[1]-out[-1][1]) >= min_seg:
            out.append(p)
    if len(out) >= 3 and np.hypot(out[0][0]-out[-1][0], out[0][1]-out[-1][1]) > 1e-6:
        out.append(out[0])
    return np.array(out)


def write_gcode(fn, polys, holes, dowel_d, feed, power, passes):
    """GRBL-Laser-G-Code: Konturen + Dübel-Kreise, M4 (dyn.), mehrere Passes.
    Koordinaten lokal (min-Ecke ~5mm). Nullpunkt = aktuelle Kopfposition (G92)."""
    S = int(round(power * 10))              # % -> S (GRBL $30 default 1000)
    L = ["; topo laser layer", "G21", "G90", "G17", "M5 S0", "G92 X0 Y0"]
    def trace(poly, close=True):
        x0, y0 = poly[0]
        L.append("M5")
        L.append(f"G0 X{x0:.2f} Y{y0:.2f}")
        L.append(f"M4 S{S}")
        for (x, y) in poly[1:]:
            L.append(f"G1 X{x:.2f} Y{y:.2f} F{feed:.0f}")
        if close:
            L.append(f"G1 X{x0:.2f} Y{y0:.2f} F{feed:.0f}")
        L.append("M5")
    import math
    for _ in range(max(1, passes)):
        for poly in polys:
            trace(poly)
        for (hx, hy) in holes:
            r = dowel_d / 2
            circ = [(hx + r*math.cos(t), hy + r*math.sin(t))
                    for t in [k*2*math.pi/24 for k in range(25)]]
            trace(circ, close=False)
    L += ["M5 S0", "G0 X0 Y0", "; end"]
    with open(fn, "w") as f:
        f.write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r0", type=int, default=854); ap.add_argument("--r1", type=int, default=880)
    ap.add_argument("--c0", type=int, default=850); ap.add_argument("--c1", type=int, default=886)
    ap.add_argument("--layers", type=int, default=25)
    ap.add_argument("--thickness", type=float, default=3.0, help="Materialdicke mm")
    ap.add_argument("--cell-mm", type=float, default=None,
                    help="mm pro DEM-Zelle (default true-N = MM=6.25)")
    ap.add_argument("--dowel-d", type=float, default=3.2, help="Dübelloch Ø mm")
    ap.add_argument("--kerf", type=float, default=0.0, help="Laser-Kerf-Kompensation mm (außen +)")
    ap.add_argument("--out", default="/tmp/laser")
    ap.add_argument("--gcode", action="store_true", help="auch GRBL-G-Code pro Lage")
    ap.add_argument("--feed", type=float, default=400, help="Schnitt-Vorschub mm/min")
    ap.add_argument("--power", type=float, default=90, help="Leistung %% (S=power*10)")
    ap.add_argument("--passes", type=int, default=2, help="Durchgänge pro Lage")
    ap.add_argument("--smooth", type=float, default=3.0, help="Glättung (Gauß-Sigma, Zacken weg)")
    ap.add_argument("--min-seg", type=float, default=0.6, help="Punkte näher als X mm zusammenfassen")
    a = ap.parse_args()

    from scipy.ndimage import zoom, gaussian_filter
    big = np.load(BIG)
    win = big[a.r0:a.r1, a.c0:a.c1].astype(float)
    cell0 = a.cell_mm if a.cell_mm else MM
    # Upsampling + GLÄTTUNG für zackenfreie Konturen (grobes DEM -> feiner -> weich)
    ZF = 4
    rel = zoom(win - win.min(), ZF, order=1)
    if a.smooth > 0:
        rel = gaussian_filter(rel, a.smooth)
    cell = cell0 / ZF
    ny, nx = rel.shape
    zmin = 0.0
    Hreal = rel.max() * MM
    os.makedirs(a.out, exist_ok=True)

    levels = np.linspace(rel.max() * 0.001, rel.max() * 0.999, a.layers)

    # Dübellöcher: in eine HOHE, aber noch breite Lage legen (in allen tieferen Lagen
    # vorhanden). Suche höchstes Level, dessen Region-Bbox >= 40x25 mm ist, 2 Löcher
    # entlang der langen Achse, 10 mm eingerückt.
    holes = []
    for lv in reversed(levels):
        polys = contour_polys(rel, lv)
        if not polys:
            continue
        big_poly = max(polys, key=lambda p: (p[:,0].max()-p[:,0].min()) *
                                             (p[:,1].max()-p[:,1].min()))
        pm = big_poly * cell
        bw = pm[:,0].max()-pm[:,0].min(); bh = pm[:,1].max()-pm[:,1].min()
        if bw >= 40 and bh >= 25:
            cx = (pm[:,0].min()+pm[:,0].max())/2; cy = (pm[:,1].min()+pm[:,1].max())/2
            if bw >= bh:
                holes = [(pm[:,0].min()+12, cy), (pm[:,0].max()-12, cy)]
            else:
                holes = [(cx, pm[:,1].min()+12), (cx, pm[:,1].max()-12)]
            break
    if not holes:   # Fallback: Mitte des Grundrisses
        holes = [(nx*cell*0.35, ny*cell*0.5), (nx*cell*0.65, ny*cell*0.5)]
    made = 0; stats = []; preview = []
    for i, lv in enumerate(levels):
        polys = contour_polys(rel, lv)
        if not polys:
            continue
        # DEM-Index -> mm, dann glätten/vereinfachen (Zacken + Laserzeit weg)
        polys_mm = [decimate(p * cell, a.min_seg) for p in polys]
        preview.append((i, polys_mm))
        # bounding box
        allpts = np.vstack(polys_mm)
        mn = allpts.min(0); mx = allpts.max(0)
        W = mx[0] - mn[0] + 10; H = mx[1] - mn[1] + 10
        # SVG schreiben (mm)
        fn = f"{a.out}/layer_{i:03d}.svg"
        with open(fn, "w") as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" '
                    f'height="{H:.1f}mm" viewBox="0 0 {W:.1f} {H:.1f}">\n')
            # CUT = Konturen (rot, hairline)
            for p in polys_mm:
                pp = p - mn + 5
                f.write(f'  <path d="{svg_path(pp)}" fill="none" '
                        f'stroke="#ff0000" stroke-width="0.1"/>\n')
            # Dübellöcher (blau) — nur wenn innerhalb dieser Kontur
            for (hx, hy) in holes:
                inside = any(_pt_in_poly(hx, hy, p) for p in polys_mm)
                if inside:
                    cx, cy = hx - mn[0] + 5, hy - mn[1] + 5
                    f.write(f'  <circle cx="{cx:.2f}" cy="{cy:.2f}" '
                            f'r="{a.dowel_d/2:.2f}" fill="none" stroke="#0000ff" '
                            f'stroke-width="0.1"/>\n')
            # Gravur: Lagennummer (grün)
            f.write(f'  <text x="8" y="{H-4:.1f}" font-size="6" '
                    f'fill="#00aa00">{i:03d}</text>\n')
            f.write('</svg>\n')
        # GRBL-G-Code (gleiche lokale Koordinaten wie SVG)
        if a.gcode:
            polys_off = [p - mn + 5 for p in polys_mm]
            holes_off = [(hx - mn[0] + 5, hy - mn[1] + 5) for (hx, hy) in holes
                         if any(_pt_in_poly(hx, hy, p) for p in polys_mm)]
            write_gcode(f"{a.out}/layer_{i:03d}.gcode", polys_off, holes_off,
                        a.dowel_d, a.feed, a.power, a.passes)
        made += 1; stats.append((i, W, H))

    model_h = a.layers * a.thickness
    print(f"Fenster {nx}x{ny} Zellen -> {nx*cell:.0f}x{ny*cell:.0f} mm Grundriss")
    print(f"{made} Lagen @ {a.thickness} mm = Modellhöhe {model_h:.0f} mm "
          f"(true-N wäre {Hreal:.0f} mm -> Vertikal x{model_h/Hreal:.2f})")
    print(f"SVGs -> {a.out}/layer_*.svg  (rot=Cut, blau=Dübelloch, grün=Nr.)")

    # Vorschau: alle Konturen übereinander (aus gesammelten Polygonen, kein State-Konflikt)
    plt.close("all")
    fig, ax = plt.subplots(figsize=(6, 6*ny/nx))
    for (i, polys_mm) in preview:
        for pm in polys_mm:
            ax.plot(pm[:, 0], pm[:, 1], lw=0.5, color=plt.cm.terrain(i/max(1, a.layers)))
    for (hx, hy) in holes:
        ax.plot(hx, hy, "b+", ms=14, mew=2)
    ax.set_aspect("equal"); ax.invert_yaxis()
    ax.set_title(f"{made} Laser-Höhenschichten (Dübel = blau +)")
    plt.tight_layout(); plt.savefig(f"{a.out}/_vorschau.png", dpi=90)
    print(f"Vorschau -> {a.out}/_vorschau.png")


def _pt_in_poly(x, y, poly):
    n = len(poly); inside = False; j = n-1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj-xi)*(y-yi)/(yj-yi+1e-9)+xi):
            inside = not inside
        j = i
    return inside


if __name__ == "__main__":
    main()
