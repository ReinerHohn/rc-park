#!/usr/bin/env python3
"""tunnel_preview3d.py — drehbarer 3D-Viewer: Gelände-Gitter + GLEISBETT + Portal-Galerie.

Zeigt die Rippen (Terrain-Lattice) zusammen mit dem Gleisbett-Band auf Schienenhöhe und der
Steinschlaggalerie am Ostportal -> man sieht, wie das Gleis durch den Berg/Tunnel läuft.
"""
import argparse, os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain_eggcrate as te
from scipy.ndimage import gaussian_filter
import trimesh


def strip_mesh(cl, zc, bw, thick, color):
    d = np.gradient(cl, axis=0); t = d/np.maximum(np.hypot(d[:, 0], d[:, 1])[:, None], 1e-9)
    n = np.column_stack([-t[:, 1], t[:, 0]])
    L = cl + n*bw/2; R = cl - n*bw/2
    top = np.column_stack([np.vstack([L, R]), np.concatenate([zc, zc])+thick])
    bot = np.column_stack([np.vstack([L, R]), np.concatenate([zc, zc])])
    V = np.vstack([top, bot]); m = len(cl); nV = 2*m
    F = []
    for i in range(m-1):
        a, b, c, d2 = i, i+1, m+i, m+i+1                    # top quad (L_i,L_i+1,R...)
        F += [[a, b, c], [b, d2, c]]
        F += [[nV+a, nV+c, nV+b], [nV+b, nV+c, nV+d2]]      # bottom
    # Seiten
    for i in range(m-1):
        F += [[i, nV+i, i+1], [i+1, nV+i, nV+i+1]]          # linke Kante
        F += [[m+i, m+i+1, nV+m+i], [m+i+1, nV+m+i+1, nV+m+i]]
    me = trimesh.Trimesh(np.vstack([V]), np.array(F), process=False)
    me.visual.vertex_colors = color; return me


def box_panels(center, fwd, bw, h, length, zbase, color):
    """einfache Galerie: Dach + 2 Seitenwände als dünne Platten."""
    fwd = fwd/np.linalg.norm(fwd); side = np.array([-fwd[1], fwd[0]])
    th = 2.0; parts = []
    def quad(p0, p1, p2, p3):
        return trimesh.Trimesh(np.array([p0, p1, p2, p3]), np.array([[0, 1, 2], [0, 2, 3]]), process=False)
    c = np.array([center[0], center[1]])
    a0 = c + side*bw/2; a1 = c - side*bw/2
    b0 = a0 - fwd*length; b1 = a1 - fwd*length
    # Dach
    z = zbase+h
    roof = quad([*a0, z], [*a1, z], [*b1, z], [*b0, z]); parts.append(roof)
    # 2 Wände
    wl = quad([*a0, zbase], [*b0, zbase], [*b0, z], [*a0, z])
    wr = quad([*a1, zbase], [*b1, zbase], [*b1, z], [*a1, z]); parts += [wl, wr]
    for p in parts: p.visual.vertex_colors = color
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", default="daten/hoellental/hoellental_track.npy")
    ap.add_argument("--dem", default="daten/hoellental/dgm025_full.npy")
    ap.add_argument("--mm", type=float, default=1.5625); ap.add_argument("--nscale", type=float, default=6.25)
    ap.add_argument("--r0", type=int, default=470); ap.add_argument("--r1", type=int, default=640)
    ap.add_argument("--c0", type=int, default=3310); ap.add_argument("--c1", type=int, default=3570)
    ap.add_argument("--vscale", type=float, default=0.85); ap.add_argument("--base", type=float, default=12.0)
    ap.add_argument("--bw", type=float, default=22.0); ap.add_argument("--thick", type=float, default=4.0)
    ap.add_argument("--out", default="modelle/hirschsprung_geruest/tunnel/_tunnel3d.html")
    a = ap.parse_args()

    win = np.load(a.dem)[a.r0:a.r1, a.c0:a.c1].astype(float); win = np.where(win < -1000, np.nan, win)
    if np.isnan(win).any(): win = np.where(np.isnan(win), np.nanmin(win), win)
    Hf = gaussian_filter(win[::-1]-np.nanmin(win), 0.6)*a.nscale*a.vscale + a.base
    cell = a.mm; NY, NX = Hf.shape; Wx, Dy = NX*cell, NY*cell
    xpos, ypos = te.rib_positions(Hf, cell, 22, 18, 7.0)
    slotw = a.thick + 0.15

    def Hat(x, y):
        xi = min(max(x/cell, 0), NX-1); yi = min(max(y/cell, 0), NY-1); return float(Hf[int(round(yi)), int(round(xi))])

    from shapely.geometry import Polygon
    def extrude(pg, h):
        geoms = list(pg.geoms) if pg.geom_type == "MultiPolygon" else [pg]
        ms = [trimesh.creation.extrude_polygon(g, h) for g in geoms if g.area >= 1]
        return trimesh.util.concatenate(ms) if ms else None
    meshes = []
    for yr in ypos:                                          # X-Rippen
        cross = [(xp, Hat(xp, yr)/2) for xp in xpos]
        poly = np.array(te.rib(Wx, lambda s, yr=yr: Hat(s, yr), cross, slotw, True), float)
        pg = Polygon(poly).buffer(0)
        if pg.is_empty: continue
        pm = extrude(pg, a.thick)
        if pm is None: continue
        V = pm.vertices
        pm.vertices = np.column_stack([V[:, 0], V[:, 2]+yr-a.thick/2, V[:, 1]]); pm.visual.vertex_colors = [200, 165, 110, 255]; meshes.append(pm)
    for xr in xpos:                                          # Y-Rippen
        cross = [(yp, Hat(xr, yp)/2) for yp in ypos]
        poly = np.array(te.rib(Dy, lambda s, xr=xr: Hat(xr, s), cross, slotw, False), float)
        pg = Polygon(poly).buffer(0)
        if pg.is_empty: continue
        pm = extrude(pg, a.thick)
        if pm is None: continue
        V = pm.vertices
        pm.vertices = np.column_stack([V[:, 2]+xr-a.thick/2, V[:, 0], V[:, 1]]); pm.visual.vertex_colors = [110, 160, 125, 255]; meshes.append(pm)

    # Gleisbett auf Schienenhöhe
    tr = np.load(a.track)
    def resample(pts, step=2.0):
        out = [pts[0]]
        for i in range(len(pts)-1):
            A, B = pts[i], pts[i+1]; dd = np.hypot(*(B-A)); n = max(1, int(dd/step))
            for k in range(1, n+1): out.append(A+(B-A)*k/n)
        return np.array(out)
    cl = resample(tr[:, :2], 2.0)
    s_tr = np.concatenate([[0], np.cumsum(np.hypot(np.diff(tr[:, 0]), np.diff(tr[:, 1])))])
    s_cl = np.concatenate([[0], np.cumsum(np.hypot(np.diff(cl[:, 0]), np.diff(cl[:, 1])))])
    zc = np.interp(s_cl, s_tr, tr[:, 2])
    meshes.append(strip_mesh(cl, zc, a.bw, 2.0, [60, 60, 70, 255]))

    # Portal-Galerie am letzten Tunnelpunkt
    tun = tr[:, 3] > 0.5; pi = int(np.where(tun)[0][-1])
    fwd = tr[min(pi+1, len(tr)-1), :2] - tr[pi, :2]
    meshes += box_panels(tr[pi, :2], fwd, a.bw+8, 36, 48, tr[pi, 2], [120, 120, 125, 255])

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    tr3 = np.column_stack([cl, zc+1])
    te.write_html(a.out, trimesh.util.concatenate(meshes), [tr3])
    print(f"3D-HTML -> {os.path.abspath(a.out)}  ({len(meshes)} Meshes)")


if __name__ == "__main__":
    main()
