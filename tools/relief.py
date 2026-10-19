#!/usr/bin/env python3
"""relief.py — SCHNELL von DEM-Crop zu 3D-Relief: druckbares STL + drehbare HTML + Hillshade.

Der „erst digital sehen"-Schritt der Methodik: in Sekunden ein sauberes 3D-Relief aus echten
Höhendaten — ansehen/prüfen, DANN pro Modell entscheiden (3D-Druck oder Laser+Gips).

  python3 tools/relief.py --dem daten/hoellental/dgm025_full.npy \
      --r0 470 --r1 640 --c0 3310 --c1 3570 --mm 1.5625 --nscale 6.25 --vscale 0.85 \
      --out modelle/hoellental_relief
"""
import argparse, os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_eggcrate as te
from scipy.ndimage import gaussian_filter, zoom
import trimesh


def solid_relief(Hf, cell, floor=0.0):
    """Höhenfeld -> watertight Solid (Oberfläche + 4 Wände + Boden), druckbar."""
    ny, nx = Hf.shape
    xs = np.arange(nx)*cell; ys = np.arange(ny)*cell
    X, Y = np.meshgrid(xs, ys)
    Vtop = np.column_stack([X.ravel(), Y.ravel(), Hf.ravel()])
    Vbot = np.column_stack([X.ravel(), Y.ravel(), np.full(nx*ny, floor)])
    V = np.vstack([Vtop, Vbot]); N = nx*ny; F = []
    def q(a, b, c, d): F.extend([[a, b, c], [a, c, d]])
    for j in range(ny-1):                         # Oberfläche
        for i in range(nx-1):
            a = j*nx+i; q(a, a+nx, a+nx+1, a+1)
    for j in range(ny-1):                         # Boden (umgedreht)
        for i in range(nx-1):
            a = N+j*nx+i; q(a, a+1, a+nx+1, a+nx)
    for i in range(nx-1):                         # Wand vorne (j=0) + hinten
        q(i, i+1, N+i+1, N+i)
        b = (ny-1)*nx; q(b+i, N+b+i, N+b+i+1, b+i+1)
    for j in range(ny-1):                         # Wand links (i=0) + rechts
        q(j*nx, N+j*nx, N+(j+1)*nx, (j+1)*nx)
        r = nx-1; q(j*nx+r, (j+1)*nx+r, N+(j+1)*nx+r, N+j*nx+r)
    m = trimesh.Trimesh(V, np.array(F), process=True); m.fix_normals()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True)
    ap.add_argument("--r0", type=int, required=True); ap.add_argument("--r1", type=int, required=True)
    ap.add_argument("--c0", type=int, required=True); ap.add_argument("--c1", type=int, required=True)
    ap.add_argument("--mm", type=float, default=1.5625); ap.add_argument("--nscale", type=float, default=6.25)
    ap.add_argument("--vscale", type=float, default=0.85); ap.add_argument("--base", type=float, default=8.0)
    ap.add_argument("--smooth", type=float, default=0.6); ap.add_argument("--zoom", type=int, default=1)
    ap.add_argument("--step", type=int, default=1, help="DEM-Downsampling fürs Mesh (2=schneller/gröber)")
    ap.add_argument("--out", default="/tmp/relief")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float)
    win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    win = win[::-1]
    rel = gaussian_filter(zoom(win-win.min(), a.zoom, order=1) if a.zoom > 1 else (win-win.min()), a.smooth)
    cell = a.mm/max(1, a.zoom)
    Hf = rel*a.nscale*a.vscale + a.base
    if a.step > 1: Hf = Hf[::a.step, ::a.step]; cell *= a.step
    NY, NX = Hf.shape; Wx, Dy = NX*cell, NY*cell

    # --- STL (druckbar) ---
    mesh = solid_relief(Hf, cell, 0.0)
    mesh.export(f"{a.out}.stl")

    # --- HTML (drehbar) mit Höhen-Einfärbung ---
    import matplotlib.cm as cm
    col = mesh.vertices[:, 2].copy()
    col = (col - col.min())/max(np.ptp(col), 1)
    mesh.visual.vertex_colors = (cm.terrain(0.25+0.6*col)*255).astype(np.uint8)
    te.write_html(f"{a.out}.html", mesh)

    # --- Hillshade PNG (Draufsicht) ---
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource
    fig, ax = plt.subplots(figsize=(10, 10*Dy/Wx)); ls = LightSource(315, 45)
    ax.imshow(ls.hillshade(Hf, dx=cell, dy=cell), cmap="gray", origin="lower", extent=[0, Wx, 0, Dy])
    ax.imshow(Hf, cmap="terrain", alpha=0.4, origin="lower", extent=[0, Wx, 0, Dy])
    ax.set_title(f"Relief {Wx:.0f}x{Dy:.0f}x{Hf.max():.0f} mm"); ax.set_aspect("equal")
    plt.tight_layout(); plt.savefig(f"{a.out}_hillshade.png", dpi=110); plt.close(fig)

    print(f"3D-RELIEF  {Wx:.0f} x {Dy:.0f} x {Hf.max():.0f} mm  ({mesh.vertices.shape[0]} Punkte, watertight={mesh.is_watertight})")
    print(f"  -> {a.out}.stl   (druckbar)")
    print(f"  -> {a.out}.html  (drehbar ansehen)")
    print(f"  -> {a.out}_hillshade.png")


if __name__ == "__main__":
    main()
