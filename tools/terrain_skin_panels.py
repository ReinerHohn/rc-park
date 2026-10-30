#!/usr/bin/env python3
"""terrain_skin_panels.py — Höhenfeld -> 3D-DRUCK-OBERFLÄCHENPLATTEN (Haut) fürs Gerüst.

Hybrid-Partner zu terrain_eggcrate.py: der Laser macht das Gerüst (trägt die Masse),
der 3D-Drucker macht die dünne sichtbare Oberfläche als PLATTEN, die man oben aufs
Gerüst montiert. KEIN GIPS. Die Haut = dünne Schale (top=Gelände, bottom=Gelände−dicke),
gekachelt auf Druckbett (XY) und Bauhöhe (Z). Pro Kachel ein STL + drehbare HTML-Vorschau.

  python3 tools/terrain_skin_panels.py --r0 830 --r1 888 --c0 832 --c1 890 \
      --vscale 0.85 --skin 6 --bed-x 250 --bed-y 210 --max-z 200 --out /tmp/skin
"""
import argparse, os, sys, numpy as np, trimesh, matplotlib
matplotlib.use("Agg")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain_eggcrate import write_html

BIG = "daten/hoellental/hirsch_big.npy"; MM = 6.25


def rock_texture(shape, amp, octaves=6, seed=7):
    """Prozedurale Fels-Rauheit (fraktales Rauschen), additiv auf das Höhenfeld."""
    rng = np.random.default_rng(seed); out = np.zeros(shape); a = amp
    from scipy.ndimage import zoom as _z
    for o in range(octaves):
        r = max(3, shape[0]//(2**(octaves-o)))
        n = rng.random((r, r))
        n = _z(n, (shape[0]/r, shape[1]/r), order=3)[:shape[0], :shape[1]]
        out += (n - 0.5) * a; a *= 0.55
    return out


def shell(Z, cell, t):
    """Watertight dünne Schale: Oberseite=Z, Unterseite=Z−t, + Randwände."""
    ny, nx = Z.shape
    xs = np.arange(nx)*cell; ys = np.arange(ny)*cell
    TX, TY = np.meshgrid(xs, ys)
    top = np.column_stack([TX.ravel(), TY.ravel(), Z.ravel()])
    bot = np.column_stack([TX.ravel(), TY.ravel(), (Z-t).ravel()])
    V = np.vstack([top, bot]); nt = nx*ny
    ti = lambda r, c: r*nx+c; bi = lambda r, c: nt+r*nx+c; F = []
    for r in range(ny-1):
        for c in range(nx-1):
            F += [[ti(r,c),ti(r+1,c),ti(r+1,c+1)], [ti(r,c),ti(r+1,c+1),ti(r,c+1)]]
            F += [[bi(r,c),bi(r+1,c+1),bi(r+1,c)], [bi(r,c),bi(r,c+1),bi(r+1,c+1)]]
    R, C = ny-1, nx-1
    for c in range(nx-1):
        F += [[ti(0,c),ti(0,c+1),bi(0,c)], [ti(0,c+1),bi(0,c+1),bi(0,c)]]
        F += [[ti(R,c),bi(R,c),ti(R,c+1)], [ti(R,c+1),bi(R,c),bi(R,c+1)]]
    for r in range(ny-1):
        F += [[ti(r,0),bi(r,0),ti(r+1,0)], [ti(r+1,0),bi(r,0),bi(r+1,0)]]
        F += [[ti(r,C),ti(r+1,C),bi(r,C)], [ti(r+1,C),bi(r+1,C),bi(r,C)]]
    m = trimesh.Trimesh(V, np.array(F), process=False)
    trimesh.repair.fix_normals(m)
    return m


def zsplit(m, max_z):
    """Mesh in Z-Bänder ≤ max_z schneiden (Box-Intersection)."""
    z0, z1 = m.bounds[0][2], m.bounds[1][2]
    H = z1 - z0; n = max(1, int(np.ceil(H/max_z)))
    if n == 1: return [m]
    zs = np.linspace(z0, z1, n+1); out = []
    (x0, y0, _), (x1, y1, _) = m.bounds
    for k in range(n):
        box = trimesh.creation.box(extents=[(x1-x0)+20, (y1-y0)+20, zs[k+1]-zs[k]])
        box.apply_translation([(x0+x1)/2, (y0+y1)/2, (zs[k]+zs[k+1])/2])
        try:
            piece = m.intersection(box)
        except Exception:
            piece = None
        if piece is not None and not piece.is_empty and len(piece.faces) > 0:
            out.append(piece)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default=BIG); ap.add_argument("--mm", type=float, default=MM, help="HORIZONTAL mm pro DEM-Zelle (Zellgröße_m × nscale)")
    ap.add_argument("--nscale", type=float, default=MM, help="VERTIKAL mm pro echtem Meter (6.25=Spur N)")
    ap.add_argument("--r0", type=int, default=830); ap.add_argument("--r1", type=int, default=888)
    ap.add_argument("--c0", type=int, default=832); ap.add_argument("--c1", type=int, default=890)
    ap.add_argument("--vscale", type=float, default=0.85)
    ap.add_argument("--skin", type=float, default=6.0, help="Schalendicke mm")
    ap.add_argument("--smooth", type=float, default=0.5, help="GERING halten = volle LiDAR-Detailtiefe (Haut wird 3D-gedruckt)")
    ap.add_argument("--rough", type=float, default=0.0, help="prozedurale Felstextur-Amplitude mm (0=aus, ~6-12 für Fels)")
    ap.add_argument("--zoom", type=int, default=4, help="Mesh-Upsampling (1 für feine 0.25m-Daten, 4 für grobe 1m)")
    ap.add_argument("--bed-x", type=float, default=250); ap.add_argument("--bed-y", type=float, default=210)
    ap.add_argument("--max-z", type=float, default=200, help="Drucker-Bauhöhe")
    ap.add_argument("--out", default="/tmp/skin")
    a = ap.parse_args()
    from scipy.ndimage import zoom, gaussian_filter
    os.makedirs(a.out, exist_ok=True)

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)          # nodata (DGM025 -9999)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    win = win[::-1]                                   # Zeile ↓=Süd -> flippen, sonst spiegelverkehrt (+y=Nord)
    zf = max(1, a.zoom)
    rel_m = (zoom(win-win.min(), zf, order=1) if zf > 1 else (win-win.min()))   # Relief in METERN
    Z = gaussian_filter(rel_m, a.smooth) * a.nscale * a.vscale                  # -> mm (nscale = mm/Meter)
    if a.rough > 0:                                   # prozedurale Felstextur (slope-betont)
        gy, gx = np.gradient(Z); sl = np.hypot(gy, gx)
        sw = np.clip(sl/(sl.mean()+1e-6), 0.3, 2.0)
        Z = Z + rock_texture(Z.shape, a.rough) * sw
    cell = a.mm/zf
    NY, NX = Z.shape; W, D, Hh = NX*cell, NY*cell, Z.max()
    # XY-Kachelung über Zell-Indizes
    nxp = int(np.ceil(W/a.bed_x)); nyp = int(np.ceil(D/a.bed_y))
    cxs = np.linspace(0, NX, nxp+1).astype(int); cys = np.linspace(0, NY, nyp+1).astype(int)
    print(f"Haut {W:.0f}x{D:.0f}x{Hh:.0f} mm, Schale {a.skin} mm -> {nxp}x{nyp} XY-Kacheln")

    import matplotlib.cm as cm
    panels = []; allmesh = []
    for yi in range(nyp):
        for xi in range(nxp):
            r0, r1 = cys[yi], min(cys[yi+1]+1, NY); c0, c1 = cxs[xi], min(cxs[xi+1]+1, NX)
            sub = Z[r0:r1, c0:c1]
            if sub.shape[0] < 2 or sub.shape[1] < 2: continue
            m = shell(sub, cell, a.skin)
            m.apply_translation([c0*cell, r0*cell, 0])     # an globale Position
            for zi, piece in enumerate(zsplit(m, a.max_z)):
                nm = f"skin_y{yi}x{xi}_z{zi}"
                loc = piece.copy(); loc.apply_translation(-loc.bounds[0])
                ext = loc.extents
                fit = ext[0] <= a.bed_x and ext[1] <= a.bed_y and ext[2] <= a.max_z+1
                loc.export(f"{a.out}/{nm}.stl")
                panels.append((nm, ext, fit))
                # fürs Preview an Originalposition + Höhenfarbe
                pv = piece.copy()
                h = pv.vertices[:,2]; hn = (h-Z.min())/(np.ptp(Z)+1e-9)
                pv.visual.vertex_colors = (cm.terrain(hn)*255).astype(np.uint8)
                allmesh.append(pv)

    man = [f"HAUT-PLATTEN  {W:.0f}x{D:.0f}x{Hh:.0f} mm (vscale {a.vscale}), Schale {a.skin} mm",
           f"Montage: oben aufs Laser-Gerüst (terrain_eggcrate) legen/kleben/schrauben.", ""]
    bad = 0
    for (nm, ext, fit) in panels:
        man.append(f"  {nm}: {ext[0]:.0f}x{ext[1]:.0f}x{ext[2]:.0f} mm" + ("" if fit else "  !! > Bett/Z"))
        if not fit: bad += 1
    open(f"{a.out}/MANIFEST.txt", "w").write("\n".join(man)+"\n")
    print("\n".join(man))
    print(f"\n{len(panels)} Platten -> {a.out}/  ({bad} über Bett)" if panels else "keine Platten")
    if allmesh:
        write_html(f"{a.out}/_haut.html", trimesh.util.concatenate(allmesh))
        print(f"3D-HTML -> {os.path.abspath(a.out)}/_haut.html")
    print(f"== {os.path.abspath(a.out)}/ ==")


if __name__ == "__main__":
    main()
