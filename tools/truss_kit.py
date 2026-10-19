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


def place_label(poly, label):
    """Gravur in eine garantiert SOLIDE Stelle (nicht in einen Schlitz) — echte Glyphen gegen Polygon."""
    from matplotlib.path import Path as _MP
    poly = np.asarray(poly, float)
    def dense(strokes):
        pts = []
        for s in strokes:
            s = np.array(s, float)
            for k in range(len(s)-1):
                d = np.hypot(*(s[k+1]-s[k])); n = max(1, int(d/0.8))
                for t in np.linspace(0, 1, n+1): pts.append(s[k]+(s[k+1]-s[k])*t)
        return np.array(pts) if pts else np.zeros((1, 2))
    mp = _MP(poly[:, :2]); x0 = float(poly[:, 0].min()); x1 = float(poly[:, 0].max()); ph = float(np.ptp(poly[:, 1]))
    for lh in (5.0, 4.0, 3.0, 2.5):
        tmpl = dense(te.glyph_strokes(str(label), 0, 0, h=lh)); cw = float(tmpl[:, 0].max()); ch = float(tmpl[:, 1].max())
        if cw > (x1-x0)-4: continue
        for yb in np.linspace(2.0, max(2.0, ph-ch-2), 16):
            for cand in np.linspace(x0+2, max(x0+2, x1-cw-2), 45):
                if mp.contains_points(tmpl + [cand, yb]).all():
                    return te.glyph_strokes(str(label), cand, yb, h=lh)
    return te.glyph_strokes(str(label), x0+3, 2, h=5.0)


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
    ap.add_argument("--track", default="daten/hoellental/hoellental_track.npy")
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

    # --- Tunnel: Lichtraum-Löcher wo Trasse Rippen kreuzt (wie terrain_eggcrate) ---
    CW, CH = 30.0, 36.0; track = None
    if a.track and os.path.exists(a.track):
        tr = np.load(a.track)
        dense = []
        for k in range(len(tr)-1):
            p, q = tr[k], tr[k+1]; Lk = max(2, int(np.hypot(q[0]-p[0], q[1]-p[1])/2))
            for tt in np.linspace(0, 1, Lk, endpoint=(k == len(tr)-2)):
                dense.append((p[0]+(q[0]-p[0])*tt, p[1]+(q[1]-p[1])*tt, p[2]+(q[2]-p[2])*tt))
        track = [pp for pp in dense if -6 <= pp[0] <= Wx+6 and -6 <= pp[1] <= Dy+6]
    def holes(axis, pos):
        cuts = []
        if not track: return cuts
        for k in range(len(track)-1):
            p, q = track[k], track[k+1]
            a0, a1, s0, s1 = (p[1], q[1], p[0], q[0]) if axis == "x" else (p[0], q[0], p[1], q[1])
            if (a0-pos)*(a1-pos) <= 0 and abs(a1-a0) > 1e-6:
                t = (pos-a0)/(a1-a0); s = s0+(s1-s0)*t; z = p[2]+(q[2]-p[2])*t
                w = CW*min(2.6, float(np.hypot(s1-s0, a1-a0))/abs(a1-a0))
                cuts.append(Polygon([(s-w/2, z-4), (s+w/2, z-4), (s+w/2, z+CH), (s-w/2, z+CH)]))
        return cuts

    meshes = []
    def addmesh(poly, axis, pos, th, color, hls=None):
        pg = Polygon(poly).buffer(0)
        for h in (hls or []):
            if h.is_valid and not h.is_empty: pg = pg.difference(h)
        if pg.is_empty: return
        geoms = list(pg.geoms) if pg.geom_type == "MultiPolygon" else [pg]
        ms = [trimesh.creation.extrude_polygon(g, th) for g in geoms if g.area >= 2]
        if not ms: return
        pm = trimesh.util.concatenate(ms); V = pm.vertices
        if axis == "x": pm.vertices = np.column_stack([V[:, 0], V[:, 2]+pos-th/2, V[:, 1]])
        else:           pm.vertices = np.column_stack([V[:, 2]+pos-th/2, V[:, 0], V[:, 1]])
        pm.visual.vertex_colors = color; pm.fix_normals(); meshes.append(pm)

    BALK = [120, 85, 45, 255]; STREB = [205, 175, 115, 255]
    balken = []                                    # (name, poly, axis, pos, holeslist)
    bi = 0
    for yr in dys:                                 # X-Rippen (an dys)
        bthis = is_by(yr); th = a.fth if bthis else a.dth
        bs = (lambda s: 0.0) if bthis else (lambda s, yr=yr: Hbot(s, yr))
        cross = [(xp, (a.fth if is_bx(xp) else a.dth)+a.fit, meetz(xp, yr, bthis and is_bx(xp))) for xp in dxs]
        poly = np.array(rib2(Wx, lambda s, yr=yr: Hat(s, yr), bs, cross, True), float)
        hl = holes("x", yr)
        addmesh(poly, "x", yr, th, BALK if bthis else STREB, hl)
        if bthis: balken.append((f"BX{bi}", poly, "x", yr, hl)); bi += 1
    bi = 0
    for xr in dxs:                                 # Y-Rippen (an dxs)
        bthis = is_bx(xr); th = a.fth if bthis else a.dth
        bs = (lambda s: 0.0) if bthis else (lambda s, xr=xr: Hbot(xr, s))
        cross = [(yp, (a.fth if is_by(yp) else a.dth)+a.fit, meetz(xr, yp, bthis and is_by(yp))) for yp in dys]
        poly = np.array(rib2(Dy, lambda s, xr=xr: Hat(xr, s), bs, cross, False), float)
        hl = holes("y", xr)
        addmesh(poly, "y", xr, th, BALK if bthis else STREB, hl)
        if bthis: balken.append((f"BY{bi}", poly, "y", xr, hl)); bi += 1

    # --- 4mm-BALKEN als Laser-Teile (Fingerzinken-Split + Tunnel + Nummer) ---
    fdepth = max(8.0, 2*a.fth); slotw4 = a.fth + 0.15
    def clip_holes(sp, hls):
        seg = Polygon(sp); seg = seg if seg.is_valid else seg.buffer(0); out = []
        for h in hls:
            it = seg.intersection(h)
            if it.is_empty or it.area < 1: continue
            for g in (list(it.geoms) if it.geom_type == "MultiPolygon" else [it]):
                if g.area >= 1: out.append(np.array(g.exterior.coords))
        return out
    for (nm, poly, axis, pos, hl) in balken:
        L = Wx if axis == "x" else Dy
        cs = list(dxs) if axis == "x" else list(dys)      # Naht nie auf eine Kreuzung
        seams = te.choose_seams(cs, L, 200, 2*fdepth+slotw4+4) if np.ptp(poly[:, 0]) > 200 else []
        segs = te.finger_split(poly, seams, fdepth, 12) if seams else [poly]
        for si, sp in enumerate(segs):
            lt = chr(97+si) if len(segs) > 1 else ""
            hh = clip_holes(sp, hl) if hl else []
            lbl = f"{nm}{lt} {pos:.0f}"
            eng = place_label(sp, lbl)
            cuts = [np.array(sp)] + hh
            te.svg_write(f"{a.out}/rib{nm}{lt}.svg", cuts, [], [], eng, 0)
            te.gcode_write(f"{a.out}/rib{nm}{lt}.gcode", cuts, [], [], eng, 0, 300, 100, 4, 85)

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
