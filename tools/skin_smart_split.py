#!/usr/bin/env python3
"""skin_smart_split.py — teilt die 3D-Haut KLUG in druckoptimierte Stücke.

Nicht stur im XY-Raster, sondern ENTLANG DER GELÄNDE-KANTEN: segmentiert die
Oberfläche nach Hangneigung (flach / schräg / steil), schneidet an den Kanten, und
richtet JEDES Stück FLACH aus (dominante Fläche -> liegend) → max Fläche pro Layer,
min Bauhöhe = schnell + wenig/kein Support. Steile 90°-Wände werden abgetrennt und
separat flach gedruckt. Jedes Stück als STL (druckfertig orientiert) + Montage-Karte
(welches Stück deckt welchen Footprint aufs Gerüst).

  python3 tools/skin_smart_split.py --dem daten/hoellental/dgm025_full.npy \
      --mm 1.5625 --nscale 6.25 --r0 470 --r1 640 --c0 3310 --c1 3570 \
      --vscale 0.85 --skin 6 --out /tmp/smartskin
"""
import argparse, os, sys, numpy as np, trimesh, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
import trimesh.transformations as T
from shapely.geometry import Polygon
from scipy.ndimage import label, gaussian_filter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain_skin_panels import shell
from laser_relief_kit import contour_polys

BIG = "daten/hoellental/hirsch_big.npy"; MM = 6.25


def orient_flat(m):
    """Mesh flach legen (min Bauhöhe): dünnste PCA-Achse der Punkte -> +z."""
    V = m.vertices - m.vertices.mean(0)
    w, vec = np.linalg.eigh(V.T @ V)          # aufsteigend; vec[:,0] = dünnste Richtung
    n = vec[:, 0]; z = np.array([0, 0, 1.0])
    v = np.cross(n, z); s = np.linalg.norm(v); c = float(n.dot(z))
    if s < 1e-6:
        R = np.eye(4) if c > 0 else T.rotation_matrix(np.pi, [1, 0, 0])
    else:
        R = T.rotation_matrix(np.arccos(np.clip(c, -1, 1)), v / s)
    m.apply_transform(R); m.apply_translation(-m.bounds[0])
    return m


def tile_xy(m, bx, by):
    """Flach gelegtes Stück in Bett-Kacheln (XY) schneiden, falls zu groß."""
    (x0, y0, z0), (x1, y1, z1) = m.bounds
    nx = int(np.ceil((x1-x0)/bx)); ny = int(np.ceil((y1-y0)/by))
    if nx*ny <= 1: return [m]
    xs = np.linspace(x0, x1, nx+1); ys = np.linspace(y0, y1, ny+1); out = []
    for i in range(nx):
        for j in range(ny):
            box = trimesh.creation.box(extents=[xs[i+1]-xs[i], ys[j+1]-ys[j], (z1-z0)+10])
            box.apply_translation([(xs[i]+xs[i+1])/2, (ys[j]+ys[j+1])/2, (z0+z1)/2])
            try: p = m.intersection(box)
            except Exception: p = None
            if p is not None and not p.is_empty and len(p.faces) > 0:
                p.apply_translation(-p.bounds[0]); out.append(p)
    return out


def mask_polys(mask, cell):
    """Rand-Polygone einer bool-Maske (mm), via Kontur @0.5."""
    pad = np.pad(mask.astype(float), 1, constant_values=0.0)
    cs = plt.contour(pad, levels=[0.5]); segs = cs.allsegs[0] if cs.allsegs else []
    plt.close("all")
    return [(s - 1.0) * cell for s in segs if len(s) >= 4]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default=BIG); ap.add_argument("--mm", type=float, default=MM)
    ap.add_argument("--nscale", type=float, default=MM)
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--vscale", type=float, default=0.85); ap.add_argument("--skin", type=float, default=6.0)
    ap.add_argument("--smooth", type=float, default=0.5)
    ap.add_argument("--flat-deg", type=float, default=25); ap.add_argument("--steep-deg", type=float, default=55)
    ap.add_argument("--slope-smooth", type=float, default=3.0, help="Neigungsfeld glätten (höher=weniger/größere Stücke)")
    ap.add_argument("--min-cells", type=int, default=200, help="kleinere Flecken verwerfen (mit großem Rest-Fleck verschmolzen)")
    ap.add_argument("--bed-x", type=float, default=250); ap.add_argument("--bed-y", type=float, default=210)
    ap.add_argument("--layer", type=float, default=0.2, help="Layerhöhe mm (für Zeit-Schätzung)")
    ap.add_argument("--out", default="/tmp/smartskin")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):                          # alte Stücke aufräumen
        if f.endswith(".stl"): os.remove(os.path.join(a.out, f))

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    win = win[::-1]                                     # +y=Nord (nicht gespiegelt)
    Z = gaussian_filter(win - win.min(), a.smooth) * a.nscale * a.vscale
    cell = a.mm
    full = shell(Z, cell, a.skin)

    # --- Hangneigung -> Bänder -> zusammenhängende Flecken ---
    gy, gx = np.gradient(Z, cell)
    slope = np.degrees(np.arctan(np.hypot(gy, gx)))
    slope = gaussian_filter(slope, a.slope_smooth)         # Sprenkel glätten -> größere Stücke
    band = np.digitize(slope, [a.flat_deg, a.steep_deg])   # 0 flach, 1 schräg, 2 steil
    from scipy.ndimage import binary_closing, binary_opening
    patches = []
    for b, nm in [(0, "flach"), (1, "schraeg"), (2, "steil")]:
        m0 = binary_opening(binary_closing(band == b, iterations=2), iterations=1)  # Löcher/Zacken weg
        lab, n = label(m0)
        for i in range(1, n + 1):
            mk = lab == i
            if mk.sum() >= a.min_cells: patches.append((nm, mk))
    print(f"Oberfläche {Z.shape[1]*cell:.0f}x{Z.shape[0]*cell:.0f} mm -> {len(patches)} kluge Stücke "
          f"(flach<{a.flat_deg:.0f}° / schräg / steil>{a.steep_deg:.0f}°)")

    man = ["SMART-SPLIT HAUT — Stücke nach Hangneigung, flach-liegend druckbar.",
           "Montage: jedes Stück an seinem Footprint aufs Gerüst (siehe _montage.png).", ""]
    labmap = np.zeros(Z.shape, int); made = 0; stats = []
    for idx, (nm, mk) in enumerate(patches):
        polys = mask_polys(mk, cell)
        if not polys: continue
        try:
            pg = Polygon(max(polys, key=len))
            if not pg.is_valid: pg = pg.buffer(0)
            prism = trimesh.creation.extrude_polygon(pg, Z.max() - Z.min() + 4*a.skin + 20)
            prism.apply_translation([0, 0, Z.min() - 2*a.skin - 10])
            piece = full.intersection(prism)
        except Exception:
            continue
        if piece.is_empty or len(piece.faces) == 0: continue
        h_before = piece.extents[2]
        piece = orient_flat(piece)
        ext = piece.extents                                  # flach gelegt (vor XY-Kachelung)
        saved = (h_before - ext[2]) / max(a.layer, 1e-6)
        tiles = tile_xy(piece, a.bed_x, a.bed_y)             # zu große Stücke aufs Bett kacheln
        labmap[mk] = idx + 1
        for ti, tp in enumerate(tiles):
            te = tp.extents
            fit = te[0] <= a.bed_x + 1 and te[1] <= a.bed_y + 1
            sfx = "" if len(tiles) == 1 else f"_t{ti}"
            fn = f"{a.out}/haut_{idx:02d}_{nm}{sfx}.stl"; tp.export(fn); made += 1
            stats.append((idx, nm, te, h_before, saved, fit))
            man.append(f"  {idx:02d}{sfx} {nm}: liegend {te[0]:.0f}x{te[1]:.0f}x{te[2]:.0f} mm "
                       f"(statt {h_before:.0f} hoch -> ~{saved:.0f} Layer gespart)" + ("" if fit else "  !!>Bett"))
    open(f"{a.out}/MANIFEST.txt", "w").write("\n".join(man) + "\n")
    print("\n".join(man[3:]))
    print(f"\n{made} Stücke -> {a.out}/")

    # --- Montage-Karte: Footprint eingefärbt nach Stück ---
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.imshow(labmap, origin="lower", cmap="tab20",
              extent=[0, Z.shape[1]*cell, 0, Z.shape[0]*cell])
    for (idx, nm, ext, hb, sv, fit) in stats:
        ys, xs = np.where(labmap == idx + 1)
        if len(xs): ax.text(xs.mean()*cell, ys.mean()*cell, str(idx), fontsize=9, weight="bold", ha="center")
    ax.set_title("Montage-Karte: welches Haut-Stück wohin (Nr. = STL)")
    ax.set_xlabel("x mm (Ost)"); ax.set_ylabel("y mm (Nord)")
    plt.tight_layout(); plt.savefig(f"{a.out}/_montage.png", dpi=95)
    print(f"Montage-Karte -> {os.path.abspath(a.out)}/_montage.png")


if __name__ == "__main__":
    main()
