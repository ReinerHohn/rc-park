#!/usr/bin/env python3
"""truss_kit.py — ZWEI-LAGEN-Gerüst: tragende 4mm-BALKEN (grob, voll) + dichte 2mm-STREBEN (Band).

Dachstuhl-Prinzip: wenige 4mm-Balken tragen; viele 2mm-Streben (adaptive Dichte) hängen in die
Balken EIN (Einhängeschlitze schon im 4mm vorgeschnitten) und geben das feine Relief.
- Balken×Balken: tragender Halblap (4mm, Treffebene halbe Höhe).
- Balken×Strebe: 2mm-Einhängeschlitz im Balken (von oben, Treffebene Band-Mitte).
- Strebe×Strebe: nur Durchsteck-Schlitz (nicht tragend).
Streben haben KEINEN Zapfen untereinander. Diese Stufe: Geometrie + 3D-Verifikation.
"""
import argparse, os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_eggcrate as te
from scipy.ndimage import gaussian_filter
import trimesh
from shapely.geometry import Polygon


def rib2(L, hs, bs, cross, from_top, step=1.0):
    """Rippe mit PRO-KREUZUNG variablem Schlitz. cross=[(pos, slot_width, meet_z)].
    from_top: Schlitz von Oberkante runter bis meet_z (X-Rippe); sonst von Unterkante hoch."""
    S = np.arange(0, L+step/2, step); pts = [(0.0, bs(0.0))]
    if from_top:
        for s in S[1:]: pts.append((float(s), bs(float(s))))
        if pts[-1][0] < L-1e-6: pts.append((L, bs(L)))
        pts.append((L, hs(L)))
        for s in S[::-1]:
            for (pos, sw, mz) in sorted(cross, reverse=True):
                if s <= pos < s+step:
                    pts += [(pos+sw/2, hs(pos)), (pos+sw/2, mz), (pos-sw/2, mz), (pos-sw/2, hs(pos))]
            pts.append((float(s), hs(float(s))))
    else:
        crs = sorted(cross)
        for s in S[1:]:
            su = float(s)
            for (pos, sw, mz) in crs:
                if su-step <= pos < su:
                    pts += [(pos-sw/2, bs(pos)), (pos-sw/2, mz), (pos+sw/2, mz), (pos+sw/2, bs(pos))]
            pts.append((su, bs(su)))
        if pts[-1][0] < L-1e-6: pts.append((L, bs(L)))
        pts.append((L, hs(L)))
        for s in S[::-1]: pts.append((float(s), hs(float(s))))
    pts.append((0.0, bs(0.0)))
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--mm", type=float, default=1.5625); ap.add_argument("--nscale", type=float, default=6.25)
    ap.add_argument("--vscale", type=float, default=0.85); ap.add_argument("--base", type=float, default=12.0)
    ap.add_argument("--dnx", type=int, default=22); ap.add_argument("--dny", type=int, default=18, help="Streben-Dichte (adaptiv)")
    ap.add_argument("--fnx", type=int, default=4); ap.add_argument("--fny", type=int, default=3, help="Balken-Anzahl (grob)")
    ap.add_argument("--fth", type=float, default=4.0); ap.add_argument("--dth", type=float, default=2.0)
    ap.add_argument("--ddepth", type=float, default=55.0, help="Streben-Bandtiefe")
    ap.add_argument("--fit", type=float, default=-0.4)
    ap.add_argument("--out", default="modelle/hirschsprung_truss")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float); win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    Hf = gaussian_filter(win[::-1]-np.nanmin(win), 0.6)*a.nscale*a.vscale + a.base
    cell = a.mm; NY, NX = Hf.shape; Wx, Dy = NX*cell, NY*cell
    def Hat(x, y):
        xi = min(max(x/cell, 0), NX-1); yi = min(max(y/cell, 0), NY-1); return float(Hf[int(round(yi)), int(round(xi))])

    dxs, dys = te.rib_positions(Hf, cell, a.dnx, a.dny, 7.0)   # Streben adaptiv
    fxs = dxs[::max(1, int(round(len(dxs)/a.fnx)))]            # Balken = grobe Teilmenge
    fys = dys[::max(1, int(round(len(dys)/a.fny)))]
    bx = set(np.round(fxs, 2)); by = set(np.round(fys, 2))
    is_bx = lambda x: round(x, 2) in bx; is_by = lambda y: round(y, 2) in by

    def meetz(x, y, both_full):
        return Hat(x, y)/2 if both_full else max(0.0, Hat(x, y) - a.ddepth/2)
    def Hbot(x, y): return max(0.0, Hat(x, y)-a.ddepth)

    meshes = []
    def addmesh(poly, axis, pos, th, color):
        pg = Polygon(poly).buffer(0)
        if pg.is_empty: return
        geoms = list(pg.geoms) if pg.geom_type == "MultiPolygon" else [pg]
        ms = [trimesh.creation.extrude_polygon(g, th) for g in geoms if g.area >= 2]
        if not ms: return
        pm = trimesh.util.concatenate(ms); V = pm.vertices
        if axis == "x": pm.vertices = np.column_stack([V[:, 0], V[:, 2]+pos-th/2, V[:, 1]])
        else:           pm.vertices = np.column_stack([V[:, 2]+pos-th/2, V[:, 0], V[:, 1]])
        pm.visual.vertex_colors = color; pm.fix_normals(); meshes.append(pm)

    BALK = [120, 85, 45, 255]; STREB = [205, 175, 115, 255]
    # X-Rippen (an dys)
    for yr in dys:
        bthis = is_by(yr); th = a.fth if bthis else a.dth
        bs = (lambda s: 0.0) if bthis else (lambda s, yr=yr: Hbot(s, yr))
        cross = []
        for xp in dxs:
            partner_full = is_bx(xp)
            both_full = bthis and partner_full
            sw = (a.fth if partner_full else a.dth) + a.fit
            cross.append((xp, sw, meetz(xp, yr, both_full)))
        poly = np.array(rib2(Wx, lambda s, yr=yr: Hat(s, yr), bs, cross, True), float)
        addmesh(poly, "x", yr, th, BALK if bthis else STREB)
    # Y-Rippen (an dxs)
    for xr in dxs:
        bthis = is_bx(xr); th = a.fth if bthis else a.dth
        bs = (lambda s: 0.0) if bthis else (lambda s, xr=xr: Hbot(xr, s))
        cross = []
        for yp in dys:
            partner_full = is_by(yp)
            both_full = bthis and partner_full
            sw = (a.fth if partner_full else a.dth) + a.fit
            cross.append((yp, sw, meetz(xr, yp, both_full)))
        poly = np.array(rib2(Dy, lambda s, xr=xr: Hat(xr, s), bs, cross, False), float)
        addmesh(poly, "y", xr, th, BALK if bthis else STREB)

    scene = trimesh.util.concatenate(meshes)
    te.write_html(f"{a.out}/_truss3d.html", scene)

    # Statische 3D-Vorschau (für Verifikation)
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    fig = plt.figure(figsize=(11, 8)); ax = fig.add_subplot(111, projection="3d")
    V = scene.vertices; F = scene.faces
    segs = V[F[:, [0, 1, 2, 0]]][:, :, :3]
    ax.add_collection3d(Line3DCollection(segs[::3].reshape(-1, 4, 3), colors="#555", lw=0.15))
    ax.set_xlim(0, Wx); ax.set_ylim(0, Dy); ax.set_zlim(0, Hf.max())
    ax.set_box_aspect((Wx, Dy, Hf.max())); ax.view_init(18, -60)
    ax.set_title(f"Zwei-Lagen: {len(fxs)}+{len(fys)} Balken(4mm) + {len(dxs)-len(fxs)}+{len(dys)-len(fys)} Streben(2mm Band)")
    plt.tight_layout(); plt.savefig(f"{a.out}/_truss3d.png", dpi=110); plt.close(fig)
    print(f"Balken {len(fxs)}+{len(fys)} (4mm voll) | Streben {len(dxs)-len(fxs)}+{len(dys)-len(fys)} (2mm Band)")
    print(f"watertight={scene.is_watertight}  -> {a.out}/_truss3d.html + _truss3d.png")


if __name__ == "__main__":
    main()
