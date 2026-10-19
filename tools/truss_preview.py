#!/usr/bin/env python3
"""truss_preview.py — KONZEPT-3D: 4mm-Balken (Rahmen) + 2mm-Streben (Detail) über echtem Relief.
Zeigt das Dachstuhl-Prinzip, BEVOR die präzisen Einhängeschlitze gebaut werden."""
import argparse, os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_eggcrate as te
from scipy.ndimage import gaussian_filter
import trimesh
from shapely.geometry import Polygon


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--mm", type=float, default=1.5625); ap.add_argument("--nscale", type=float, default=6.25)
    ap.add_argument("--vscale", type=float, default=0.85); ap.add_argument("--base", type=float, default=12.0)
    ap.add_argument("--fnx", type=int, default=4); ap.add_argument("--fny", type=int, default=3, help="BALKEN (4mm) grob")
    ap.add_argument("--dnx", type=int, default=14); ap.add_argument("--dny", type=int, default=11, help="STREBEN (2mm) dicht")
    ap.add_argument("--fth", type=float, default=4.0); ap.add_argument("--dth", type=float, default=2.0)
    ap.add_argument("--ddepth", type=float, default=55.0, help="Streben-Bandtiefe (nicht bis Boden)")
    ap.add_argument("--out", default="modelle/hirschsprung_rahmen/_truss3d.html")
    a = ap.parse_args()

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float); win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    Hf = gaussian_filter(win[::-1]-np.nanmin(win), 0.6)*a.nscale*a.vscale + a.base
    cell = a.mm; NY, NX = Hf.shape; Wx, Dy = NX*cell, NY*cell
    def Hat(x, y):
        xi = min(max(x/cell, 0), NX-1); yi = min(max(y/cell, 0), NY-1); return float(Hf[int(round(yi)), int(round(xi))])

    # Streben = ADAPTIVE Positionen (dicht an scharfen Kanten, NICHT schlechter als Original-Detail)
    dxs, dys = te.rib_positions(Hf, cell, a.dnx, a.dny, 7.0)
    # Balken = grobe Teilmenge davon -> fallen exakt mit Streben-Kreuzungen zusammen
    kfx = max(1, int(round(len(dxs)/max(1, a.fnx)))); kfy = max(1, int(round(len(dys)/max(1, a.fny))))
    fxs = dxs[::kfx]; fys = dys[::kfy]
    bx = set(np.round(fxs, 2)); by = set(np.round(fys, 2))

    def extrude(pg, h):
        geoms = list(pg.geoms) if pg.geom_type == "MultiPolygon" else [pg]
        ms = [trimesh.creation.extrude_polygon(g, h) for g in geoms if g.area >= 1]
        return trimesh.util.concatenate(ms) if ms else None

    meshes = []
    def add_rib(poly, axis, pos, th, color):
        pg = Polygon(poly).buffer(0)
        if pg.is_empty: return
        pm = extrude(pg, th)
        if pm is None: return
        V = pm.vertices
        if axis == "x": pm.vertices = np.column_stack([V[:, 0], V[:, 2]+pos-th/2, V[:, 1]])
        else:           pm.vertices = np.column_stack([V[:, 2]+pos-th/2, V[:, 0], V[:, 1]])
        pm.visual.vertex_colors = color; pm.fix_normals(); meshes.append(pm)

    sl_f = a.fth+0.15; sl_d = a.dth+0.15
    Hbot = lambda x, y: max(0.0, Hat(x, y)-a.ddepth)
    BALK = [120, 85, 45, 255]; STREB = [210, 180, 120, 255]
    for yr in dys:                                     # X-Rippen: Balken(voll) oder Strebe(Band)
        is_b = round(yr, 2) in by; th = a.fth if is_b else a.dth; sw = sl_f if is_b else sl_d
        if is_b:
            cross = [(xp, Hat(xp, yr)/2) for xp in dxs]
            poly = np.array(te.rib(Wx, lambda s, yr=yr: Hat(s, yr), cross, sw, True), float)
        else:
            cross = [(xp, (Hbot(xp, yr)+Hat(xp, yr))/2) for xp in dxs]
            poly = np.array(te.rib(Wx, lambda s, yr=yr: Hat(s, yr), cross, sw, True, lambda s, yr=yr: Hbot(s, yr)), float)
        add_rib(poly, "x", yr, th, BALK if is_b else STREB)
    for xr in dxs:                                     # Y-Rippen
        is_b = round(xr, 2) in bx; th = a.fth if is_b else a.dth; sw = sl_f if is_b else sl_d
        if is_b:
            cross = [(yp, Hat(xr, yp)/2) for yp in dys]
            poly = np.array(te.rib(Dy, lambda s, xr=xr: Hat(xr, s), cross, sw, False), float)
        else:
            cross = [(yp, (Hbot(xr, yp)+Hat(xr, yp))/2) for yp in dys]
            poly = np.array(te.rib(Dy, lambda s, xr=xr: Hat(xr, s), cross, sw, False, lambda s, xr=xr: Hbot(xr, s)), float)
        add_rib(poly, "y", xr, th, BALK if is_b else STREB)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    te.write_html(a.out, trimesh.util.concatenate(meshes))
    print(f"TRUSS-KONZEPT: {a.fnx}x{a.fny} Balken(4mm, dunkel) + {a.dnx}x{a.dny} Streben(2mm Band, hell)")
    print(f"  -> {os.path.abspath(a.out)}")


if __name__ == "__main__":
    main()
