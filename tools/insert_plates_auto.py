#!/usr/bin/env python3
"""insert_plates_auto.py — schneidet die Flächen, die das grobe Egg-Crate vertreppt, als
flache Einhäng-Platten auf die ECHTE Kontur (keine Rechtecke), in zwei Kategorien:

  FLACH  (Neigung <= --slope-max): große zusammenhängende Flachbereiche (Talboden/Terrassen/
          Trasse) -> HORIZONTALE Platte, auf die Kontur geschnitten (begrenzt wo der Hang steil
          ansteigt), Dübel-Löcher an den Rippenkreuzungen.
  STEIL  (Neigung >= --steep-min): steile Faces (z.B. Tunnel-Steilwand) -> VERTIKALE Wand-
          Platte, als ABGEWICKELTER Streifen (Länge entlang der Wandbasis × Höhe), mit Steck-
          Laschen, die in die Rippen-/Boden-Schlitze fallen.

  python3 tools/insert_plates_auto.py --dem daten/hoellental/dgm025_full.npy \
      --r0 470 --r1 640 --c0 3310 --c1 3570 --zoom 1 --mm 0.78125 --nscale 3.125 \
      --vscale 0.85 --slope-max 22 --steep-min 55 --snap-edges --gcode \
      --out modelle/hoellental_A3_set/platten
"""
import argparse, os, sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from scipy.ndimage import gaussian_filter, label as _label, binary_opening, binary_closing, binary_fill_holes, binary_dilation, binary_erosion, distance_transform_edt
from scipy.interpolate import RegularGridInterpolator
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import insert_plate as ip
from terrain_eggcrate import rib_positions
from laser_relief_kit import glyph_strokes, svg_write, gcode_write, contour_polys, decimate, pip

SHOE = lambda p: abs(np.dot(p[:, 0], np.roll(p[:, 1], 1)) - np.dot(p[:, 1], np.roll(p[:, 0], 1))) / 2.0


def slope_field(Hf, cell, smooth_px):
    Hs = gaussian_filter(Hf, smooth_px)
    gy, gx = np.gradient(Hs, cell)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def rib_miss_mask(Hf, cell, xpos, ypos, thresh):
    """DIE Schwelle: wo treffen die groben Rippen die echte Form NICHT? Rekonstruiere die
    Fläche, die das Rippen-Raster liefert (bilineare Interpolation zwischen den Rippen-Linien),
    und nimm die Zellen, wo |Gelände − Rippen-Fläche| > thresh. Dort (scharfe Kanten, Tunnel)
    brauchen wir Extra-Platten; smoothe Hänge treffen die Rippen gut -> fallen raus."""
    NY, NX = Hf.shape
    xs = np.array(sorted(set(xpos))); ys = np.array(sorted(set(ypos)))
    ci = np.clip((xs / cell).astype(int), 0, NX - 1); cj = np.clip((ys / cell).astype(int), 0, NY - 1)
    G = Hf[np.ix_(cj, ci)]
    rgi = RegularGridInterpolator((ys, xs), G, bounds_error=False, fill_value=None)
    Xf, Yf = np.meshgrid(np.arange(NX) * cell, np.arange(NY) * cell)
    ribsurf = rgi(np.column_stack([Yf.ravel(), Xf.ravel()])).reshape(NY, NX)
    err = np.abs(Hf - ribsurf)
    return err, err > thresh


def detect_regions(slope, cell, lo_deg, hi_deg, min_area, close_mm, fill, gate=None, split_mm=0.0):
    """Zusammenhängende Bereiche mit Neigung in [lo,hi] (optional nur innerhalb gate) als Masken.
    split_mm>0: GROSSE Flächen an Engstellen (Necks schmaler als ~2*split_mm) auftrennen — Erosion
    trennt die Bänke, Distanz-Transform wächst jede wieder bis zur Flächen-Grenze zurück. So wird
    der zusammenhängende Talboden in einzelne Bänke/Platten zerlegt statt EIN Riesen-Blob."""
    sel = (slope >= lo_deg) & (slope <= hi_deg)
    if gate is not None:
        sel = sel & gate
    r = max(1, int(round(close_mm / cell)))
    sel = binary_closing(binary_opening(sel, iterations=1), iterations=r)
    if split_mm > 0:
        core = binary_erosion(sel, iterations=max(1, int(round(split_mm / cell))))
        lab, n = _label(core)
        if n >= 1:
            idx = distance_transform_edt(lab == 0, return_distances=False, return_indices=True)
            grown = lab[tuple(idx)]; grown[~sel] = 0
            out = []
            for i in range(1, n + 1):
                m = grown == i
                if fill:
                    m = binary_fill_holes(m)
                if m.sum() * cell * cell >= min_area:
                    out.append(m)
            out.sort(key=lambda m: -m.sum())
            return out
    lab, n = _label(sel)
    out = []
    for i in range(1, n + 1):
        m = lab == i
        if fill:
            m = binary_fill_holes(m)
        if m.sum() * cell * cell >= min_area:
            out.append(m)
    out.sort(key=lambda m: -m.sum())
    return out


def seed_regions(slope, cell, seeds, slope_max, min_area, close_mm):
    """MANUELL: je Seed-Punkt (x,y mm) EINE flache Platte = die flache Bank um den Punkt,
    aufgeteilt per Voronoi (jeder Seed bekommt den ihm nächsten Teil der Flachfläche) und auf
    den flachen Teil (Neigung <= slope_max) begrenzt. Du bestimmst WO, der Code schneidet die
    echte Flach→Steil-Kante. So kriegst du exakt deine Einteilung mit echten Kanten."""
    NY, NX = slope.shape
    flat = (slope <= slope_max)
    r = max(1, int(round(close_mm / cell)))
    flat = binary_closing(binary_opening(flat, iterations=1), iterations=r)
    marker = np.zeros((NY, NX), int); rc = []
    for k, (sx, sy) in enumerate(seeds):
        p = (min(max(int(sy / cell), 0), NY - 1), min(max(int(sx / cell), 0), NX - 1))
        rc.append(p); marker[p] = k + 1
    idx = distance_transform_edt(marker == 0, return_distances=False, return_indices=True)
    vor = marker[tuple(idx)]                                   # Voronoi-Zuordnung zu den Seeds
    out = []
    for k, p in enumerate(rc):
        m = (vor == k + 1) & flat
        lab, n = _label(m)
        if n == 0:
            continue
        sl = lab[p] if lab[p] > 0 else 1 + int(np.argmax([(lab == i).sum() for i in range(1, n + 1)]))
        m = binary_fill_holes(lab == sl)
        if m.sum() * cell * cell >= min_area:
            out.append(m)
    return out


def segment_planes(Hf, cell, smooth_px, normal_tol_deg, min_area, max_slope_deg):
    """GERADE Flächen zusammenfassen: Region-Growing über die Oberflächen-NORMALEN. Benachbarte
    Zellen mit fast gleicher Normale (coplanar, Winkel < normal_tol) werden EIN Segment; an KANTEN
    (Normalensprung = Bruchkante) wird getrennt. -> große planare Facetten (Talboden/Bänke/Trog),
    begrenzt GENAU an den Kanten. Nur nicht-senkrechte (Neigung <= max_slope) = flache Platten."""
    Hs = gaussian_filter(Hf, smooth_px)
    gy, gx = np.gradient(Hs, cell)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))           # Zenit (Neigung)
    azim = np.degrees(np.arctan2(gy, gx)) % 360.0             # Ausrichtung (wohin es abfällt)
    b = max(5.0, normal_tol_deg)                              # Bin-Größe Grad
    sb = np.round(slope / b).astype(int)
    ab = np.round(azim / b).astype(int) % max(1, int(round(360.0 / b)))
    ab[slope < b] = -1                                        # flache Zellen: Azimut egal -> EINE Flach-Familie
    binimg = sb * 1000 + ab                                   # gleiche Orientierung = gleicher Bin = coplanar
    out = []
    for v in np.unique(binimg):                               # je Orientierungs-Bin: zusammenhängende Facetten
        comp, ncomp = _label(binimg == v)
        for i in range(1, ncomp + 1):
            m = comp == i
            if m.sum() * cell * cell < min_area:
                continue
            if float(np.median(slope[m])) > max_slope_deg:    # senkrechte Wände raus (flache Platten)
                continue
            out.append(binary_fill_holes(m))
    out.sort(key=lambda m: -m.sum())
    return out


def fit_plane_mask(Hf, cell, m):
    rr, cc = np.where(m)
    X = (cc + 0.5) * cell; Y = (rr + 0.5) * cell; Z = Hf[rr, cc]
    coef, *_ = np.linalg.lstsq(np.column_stack([X, Y, np.ones(X.size)]), Z, rcond=None)
    res = np.column_stack([X, Y, np.ones(X.size)]) @ coef - Z
    return float(coef[0]), float(coef[1]), float(coef[2]), float(np.sqrt(np.mean(res ** 2)))


def mask_contour_mm(m, cell, simplify):
    polys = contour_polys(m.astype(float), 0.5)
    if not polys:
        return None
    poly = max(polys, key=SHOE)
    w = decimate(np.column_stack([poly[:, 0] * cell, poly[:, 1] * cell]), simplify)
    return w if len(w) >= 4 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--zoom", type=int, default=1); ap.add_argument("--mm", type=float, default=0.78125)
    ap.add_argument("--nscale", type=float, default=3.125); ap.add_argument("--vscale", type=float, default=0.85)
    ap.add_argument("--base", type=float, default=12.0); ap.add_argument("--smooth", type=float, default=0.4)
    ap.add_argument("--nx", type=int, default=6); ap.add_argument("--ny", type=int, default=6)
    ap.add_argument("--min-gap", type=float, default=7.0)
    ap.add_argument("--snap-edges", action="store_true"); ap.add_argument("--snap-pct", type=float, default=92.0)
    ap.add_argument("--thickness", type=float, default=3.0); ap.add_argument("--dowel-d", type=float, default=3.2)
    # FLACH
    ap.add_argument("--slope-max", type=float, default=30.0, help="bis zu dieser Neigung = 'flach' (Bank reicht bis zur Flach→Steil-Kante)")
    ap.add_argument("--min-area", type=float, default=800.0, help="min Flachplatten-Fläche mm²")
    ap.add_argument("--close-mm", type=float, default=3.0, help="Lücken bis N mm schließen (kleiner = mehr getrennte Bereiche)")
    ap.add_argument("--seg-smooth", type=float, default=3.5, help="Glättung Neigungsfeld px (HÖHER = ignoriert Flach-Wackeln, ruhigere Bänke)")
    ap.add_argument("--need-steep-edge", type=int, default=1, help="1=nur Flächen, die an eine Steilkante grenzen (echte Flach→Steil-Kante); 0=alle flachen")
    ap.add_argument("--split-necks", type=float, default=7.0, help="große Flächen an Engstellen (schmaler als ~2*N mm) in einzelne Bänke/Platten auftrennen (0=aus, EIN Blob)")
    # STEIL (vertikale Wände)
    ap.add_argument("--steep-min", type=float, default=55.0, help="ab dieser Neigung = steile Wand (vertikale Platte)")
    ap.add_argument("--wall-min-area", type=float, default=200.0, help="min Wand-Fläche mm²")
    ap.add_argument("--wall-max-area", type=float, default=3000.0, help="max Wand-Grundriss mm² — nur LOKALE Steilwände (Tunnel/Stützmauer), keine ganzen Hänge")
    ap.add_argument("--rib-miss", type=float, default=0.0, help="optional: Platte nur wo Rippen die Form um >N mm verfehlen (0=aus; reagiert sonst auf Flach-Wackeln)")
    ap.add_argument("--contour-simplify", type=float, default=2.5, help="Kontur-Punkte mind. N mm auseinander")
    ap.add_argument("--normal-tol", type=float, default=12.0, help="Normalen-Winkeltoleranz Grad fürs Zusammenfassen coplanar: höher = größere Platten (mehr verschmolzen), kleiner = feiner an Kanten getrennt (12 fängt Gullys/Rinnen)")
    ap.add_argument("--flat-max-slope", type=float, default=40.0, help="Facetten mit mittlerer Neigung über N° = senkrechte Wand (raus bei den flachen Platten)")
    ap.add_argument("--seeds", default="", help="MANUELL: Platten-Stellen 'x,y x,y ...' (mm). Je Seed EINE Platte (flache Bank um den Punkt, echte Kante). Leer=Auto.")
    ap.add_argument("--max-plates", type=int, default=8); ap.add_argument("--max-walls", type=int, default=6)
    ap.add_argument("--feed", type=float, default=150); ap.add_argument("--power", type=float, default=100)
    ap.add_argument("--passes", type=int, default=4); ap.add_argument("--eng-power", type=float, default=85)
    ap.add_argument("--gcode", action="store_true")
    ap.add_argument("--out", default="/tmp/platten")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    Hf, cell = ip.load_hf(a)
    NY, NX = Hf.shape; Wx, Dy = NX * cell, NY * cell
    xpos, ypos = rib_positions(Hf, cell, a.nx, a.ny, a.min_gap, None, False, a.snap_edges, a.snap_pct)
    slope = slope_field(Hf, cell, a.seg_smooth)
    if a.seeds.strip():                                       # MANUELL: du gibst die Stellen vor
        _sd = [tuple(float(v) for v in s.split(",")) for s in a.seeds.split()]
        flats = seed_regions(slope, cell, _sd, a.slope_max, a.min_area, a.close_mm)[:a.max_plates]
        walls = []
    else:                                                     # AUTO: ALLE planaren Facetten — flach=Platte, STEIL=Wand (gleiche Erkennung)
        _ms = lambda m: float(np.median(slope[m]))
        _facets = segment_planes(Hf, cell, a.seg_smooth, a.normal_tol, min(a.min_area, a.wall_min_area), 90.0)
        flats = [m for m in _facets if _ms(m) < a.flat_max_slope and m.sum() * cell * cell >= a.min_area][:a.max_plates]
        walls = [m for m in _facets if _ms(m) >= a.flat_max_slope and m.sum() * cell * cell <= a.wall_max_area][:a.max_walls]   # nur lokale Wände (keine ganzen Hänge)

    man = [f"AUTO-EINHÄNGPLATTEN — Fenster {Wx:.0f}x{Dy:.0f} mm", "", "FLACHE Platten (horizontal, auf echte Kontur):"]
    flat2d = []; wall2d = []; kept = 0
    for m in flats:
        w = mask_contour_mm(m, cell, a.contour_simplify)
        if w is None:
            continue
        wx, wy = w[:, 0], w[:, 1]
        av, bv, cv, rms = fit_plane_mask(Hf, cell, m)
        sx, sy = np.hypot(1.0, av), np.hypot(1.0, bv)
        ox, oy = float(wx.min()), float(wy.min())
        plate = [((px - ox) * sx, (py - oy) * sy) for px, py in zip(wx, wy)]
        wl = list(zip(wx, wy))
        hw = [(xp, yp) for xp in xpos for yp in ypos if pip(xp, yp, wl)]   # Dübel an X/Y-Kreuzungen
        if not hw:                                                          # keine Kreuzung drin -> an Rippen-LINIEN durch den Schwerpunkt
            cx = float(np.mean(wx)); cy = float(np.mean(wy))
            hw = [(xp, cy) for xp in xpos if pip(xp, cy, wl)] + [(cx, yp) for yp in ypos if pip(cx, yp, wl)]
        holes = [((hx - ox) * sx, (hy - oy) * sy) for (hx, hy) in hw]
        Wp = (float(wx.max()) - ox) * sx; Dp = (float(wy.max()) - oy) * sy
        eng = glyph_strokes(f"P{kept}", 2, max(2.0, Dp - 6), h=4)
        fn = os.path.join(a.out, f"plate_{kept:02d}")
        svg_write(fn + ".svg", [plate], [], holes, eng, a.dowel_d / 2)
        if a.gcode:
            gcode_write(fn + ".gcode", [plate], [], holes, eng, a.dowel_d / 2, a.feed, a.power, a.passes, a.eng_power)
        flat2d.append(w)
        man.append(f"  P{kept}: ~{Wp:.0f}x{Dp:.0f} mm | {SHOE(w):.0f} mm² | Neigung {np.degrees(np.arctan(np.hypot(av,bv))):.0f}° "
                   f"| {len(plate)} Konturpunkte | {len(holes)} Dübel")
        kept += 1

    man += ["", "STEILE WÄNDE (vertikal, z.B. Tunnel-Steilwand) — als abgewickelter Streifen:"]
    kw = 0
    for m in walls:
        w = mask_contour_mm(m, cell, a.contour_simplify)
        if w is None:
            continue
        wx, wy = w[:, 0], w[:, 1]
        rr, cc = np.where(m)
        zt = float(Hf[rr, cc].max()); zb = float(Hf[rr, cc].min()); height = zt - zb
        # Abwicklung: Länge entlang der Wandbasis (PCA-Hauptachse der Fußlinie) × Wandhöhe
        pts = np.column_stack([(cc + 0.5) * cell, (rr + 0.5) * cell])
        c0 = pts.mean(0); u, s, vt = np.linalg.svd(pts - c0, full_matrices=False)
        axis = vt[0]; t = (pts - c0) @ axis; length = float(t.max() - t.min())
        strip = [(0, 0), (length, 0), (length, height), (0, height), (0, 0)]
        # Steck-Laschen unten (fallen in Boden-/Rippen-Schlitze)
        eng = glyph_strokes(f"W{kw}", 2, height - 6 if height > 10 else 2, h=4)
        fn = os.path.join(a.out, f"wall_{kw:02d}")
        svg_write(fn + ".svg", [strip], [], [], eng, 0)
        if a.gcode:
            gcode_write(fn + ".gcode", [strip], [], [], eng, 0, a.feed, a.power, a.passes, a.eng_power)
        wall2d.append(w)
        man.append(f"  W{kw}: Wand L~{length:.0f} mm × H~{height:.0f} mm | {SHOE(w):.0f} mm² Grundriss "
                   f"-> Streifen {length:.0f}x{height:.0f} mm")
        kw += 1
    man[0] = f"AUTO-EINHÄNGPLATTEN — Fenster {Wx:.0f}x{Dy:.0f} mm, {kept} flache + {kw} steile (Wand) Platten"
    open(os.path.join(a.out, "MANIFEST.txt"), "w").write("\n".join(man) + "\n")

    # Draufsicht: Hillshade + flache Platten (farbig) + steile Wände (rot)
    fig, ax = plt.subplots(figsize=(11, 7))
    ls = LightSource(azdeg=315, altdeg=45)
    ax.imshow(ls.hillshade(Hf, vert_exag=1.0, dx=cell, dy=cell), cmap="gray", origin="lower", extent=[0, Wx, 0, Dy])
    cols = plt.cm.tab10(np.linspace(0, 1, 10))
    for k, p in enumerate(flat2d):
        ax.fill(p[:, 0], p[:, 1], facecolor=cols[k % 10], edgecolor="k", linewidth=1.4, alpha=0.5)
        ax.text(p[:, 0].mean(), p[:, 1].mean(), f"P{k}", ha="center", va="center", fontsize=9, fontweight="bold")
    for k, p in enumerate(wall2d):
        ax.fill(p[:, 0], p[:, 1], facecolor="none", edgecolor="red", linewidth=2.0, hatch="///")
        ax.text(p[:, 0].mean(), p[:, 1].mean(), f"W{k}", color="red", ha="center", va="center", fontsize=8, fontweight="bold")
    ax.set_xlim(0, Wx); ax.set_ylim(0, Dy); ax.set_aspect("equal")
    ax.set_xticks(np.arange(0, Wx + 1, 20)); ax.set_yticks(np.arange(0, Dy + 1, 20))
    ax.grid(True, color="w", alpha=0.3, lw=0.5)               # Gitter zum Ablesen der Seed-Koordinaten
    ax.set_title(f"{kept} flache Platten (farbig) + {kw} steile Wände (rot) — auf echte Kontur")
    ax.set_xlabel("x [mm]"); ax.set_ylabel("y [mm]")
    plt.tight_layout(); png = os.path.join(a.out, "_platten_overview.png"); plt.savefig(png, dpi=130)

    print("\n".join(man)); print(f"-> {kept} flache + {kw} Wand-Platten in {a.out}/  | {png}")


if __name__ == "__main__":
    main()
