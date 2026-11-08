#!/usr/bin/env python3
"""fenster_einbauen.py - Typfenster (fenster_fit.py, Ortho-Pixel) als 3D-Koerper ins Netz einbauen (manifold3d): Glasnische (Laibungstiefe aus Wolke) + Sprossen/Riegel.
  venv-seg/bin/python -I tools/fenster_einbauen.py objekt.json --dicht sfm/dicht_alle --fit fit.json --lagen "x,y;x,y;..." --box x0,y0,z0,x1,y1,z1 --normale nx,ny --zelle 0.02 --netz in.stl --aus out.stl [--nur-fenster f.stl]
Tiefe (Wandflaeche w_wand, Glas/Laibung w_glas) wird je Fenster aus der Wolke gemessen (nahester Punkt je 2-cm-Zelle, Median): Wand = Streifen links/rechts neben dem Fenster, Glas = belegte Zellen im Glas.
Koordinaten: Ortho (px) -> K-Rahmen (wolke_front.py: mitte, n, d) -> Netzrahmen (z - rahmen_verschiebung 0.431) -> STL (mm = m*1000/87).
ANNAHME: gleiche Typparameter fuer alle Fenster (Median); Stabtiefe = Wandflaeche - 1 cm (nicht gemessen)."""
import os, sys, json, argparse, numpy as np, trimesh, manifold3d as m3d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolke_front as WF
ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--dicht", required=True); ap.add_argument("--fit", required=True); ap.add_argument("--lagen", required=True)
ap.add_argument("--box", required=True); ap.add_argument("--normale", required=True); ap.add_argument("--zelle", type=float, default=0.02); ap.add_argument("--netz", required=True); ap.add_argument("--aus", required=True)
ap.add_argument("--ohne-staebe", action="store_true", help="nur Nische, keine Sprossen/Riegel"); ap.add_argument("--offen", action="store_true", help="Oeffnung DURCH die Wand (kein Glas; Plexiglas wird dahinter geklebt), Rahmen+Sprossen ab Wandvorderseite -0,10 m"); ap.add_argument("--stab-min-mm", type=float, default=0.0, help="Mindeststabbreite im Modell in mm (Druck: 0,8)"); ap.add_argument("--nur-fenster"); ap.add_argument("--rv-z", type=float, default=0.431); ap.add_argument("--massstab", type=float, default=87.0); ap.add_argument("--stab-zurueck", type=float, default=0.01); a = ap.parse_args()
od = os.path.dirname(os.path.abspath(a.objekt)); P = json.load(open(a.fit))["typ"]
x0, y0, z0, x1, y1, z1 = [float(v) for v in a.box.split(",")]; n = np.array([float(v) for v in a.normale.split(",")] + [0.0]); n /= np.linalg.norm(n); d = np.array([-n[1], n[0], 0.0])
s, Rm, t0, CM, rest = WF.rahmen_umeyama(a.dicht, od); X, _ = WF.ply_farbe(os.path.join(a.dicht, "fused.ply")); X = s * (Rm @ X.T).T + t0
mitte = np.array([(x0 + x1) / 2, (y0 + y1) / 2, 0.0]); ecken = np.array([[x, y, 0] for x in (x0, x1) for y in (y0, y1)]) - mitte; u0 = (ecken @ d).min()
Pm = X - mitte; w = Pm @ n; u = Pm @ d; v = X[:, 2]; z = a.zelle
lagen = [tuple(float(q) for q in t.split(",")) for t in a.lagen.split(";")]   # linke obere Ecke der Fensterausschnitte (px im Ortho, Ortho Zeile 0 = z1)
def loc2K(px, py, wv=0.0): return mitte + (u0 + px * z) * d + wv * n + np.array([0, 0, z1 - py * z])
def mm(Pk): Pk = np.array(Pk, float); Pk[..., 2] -= a.rv_z; return Pk * (1000.0 / a.massstab)
def tiefe(px0, py0, w_px, h_px, xl, xr, yt, yb):
    ok = (np.abs(w) <= 6.0); iu = np.floor((u - u0) / z).astype(int); iv = np.floor((z1 - v) / z).astype(int)
    def reg(c0, c1, r0, r1): m_ = ok & (iu >= c0) & (iu < c1) & (iv >= r0) & (iv < r1); return w[m_]
    wand = np.concatenate([reg(px0 + xl - 12, px0 + xl - 3, py0 + 45, py0 + 110), reg(px0 + xr + 3, px0 + xr + 12, py0 + 45, py0 + 110)])
    glas = reg(px0 + xl + 4, px0 + xr - 4, py0 + yt + 30, py0 + yb - 6)
    return float(np.median(wand)), float(np.percentile(glas, 50)), len(wand), len(glas)
def prisma(poly_uz, w_a, w_b, px0, py0):
    """Polygon in Fensterpixeln (x,y) -> geschlossener Koerper zwischen den Tiefen w_a (hinten) und w_b (vorn) im K-Rahmen (Prisma entlang n).
    earcut direkt auf den Polygonpunkten (ohne Schlusspunkt-Duplikat), Seitenwaende aus den Polygonkanten."""
    import mapbox_earcut as ec
    pts = np.array(poly_uz, float)
    if np.allclose(pts[0], pts[-1]): pts = pts[:-1]
    nv = len(pts); tri = ec.triangulate_float64(pts, np.array([nv], np.uint32)).reshape(-1, 3)
    A = np.array([loc2K(px0 + x, py0 + y, w_a) for x, y in pts]); B = np.array([loc2K(px0 + x, py0 + y, w_b) for x, y in pts])
    F = [list(t[::-1]) for t in tri] + [[i + nv for i in t] for t in tri]
    for i in range(nv): j = (i + 1) % nv; F += [[i, j, j + nv], [i, j + nv, i + nv]]
    m = trimesh.Trimesh(np.vstack([A, B]), np.array(F), process=True); trimesh.repair.fix_winding(m); trimesh.repair.fix_normals(m)
    if m.volume < 0: m.invert()
    assert m.is_watertight, "Prisma nicht wasserdicht"; return m
def oeffnung(Pr):
    xl, xr, yt, yb, sh, m1, m2 = [Pr[k] for k in ("xl", "xr", "yt", "yb", "s", "m1", "m2")]
    t = np.linspace(0, 1, 14); L = [(m1 - (m1 - xl) * q, yt + sh * (1 - (1 - q) ** 2)) for q in t]; R = [(m2 + (xr - m2) * q, yt + sh * (1 - (1 - q) ** 2)) for q in t]
    return [(xl, yb), (xr, yb)] + R[::-1] + L  # im Uhrzeigersinn egal (earcut)
def box_poly(xa, ya, xb, yb_): return [(xa, ya), (xb, ya), (xb, yb_), (xa, yb_)]
netz = trimesh.load(a.netz, force="mesh"); netz.vertices = netz.vertices * (a.massstab / 1000.0) + np.array([0, 0, a.rv_z])   # STL mm -> K-Rahmen m (wie foto_diff._netz)
ms = lambda m: m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
ges = ms(netz); alle = []; bericht = []
for k, (px0, py0) in enumerate(lagen):
    px0 = int(px0); py0 = int(py0); wand, glas, nw, ng = tiefe(px0, py0, 118, 142, P["xl"], P["xr"], P["yt"], P["yb"]); bericht.append(dict(fenster=k, w_wand=round(wand, 3), w_glas=round(glas, 3), nische_m=round(wand - glas, 3), n_wand=nw, n_glas=ng))
    if not (0.02 < wand - glas < 1.0): print("Fenster", k, "Nischentiefe unplausibel", wand - glas, "- uebersprungen"); continue
    nische = prisma(oeffnung(P), (wand - 0.6) if a.offen else glas, wand + 0.3, px0, py0); b = max(P["b"], a.stab_min_mm * a.massstab / 1000.0 / z); sv = wand - a.stab_zurueck; hinten = (wand - 0.10) if a.offen else (glas - 0.01)
    stäbe = [box_poly(P["m1"] - b / 2, P["yt"] - 4, P["m1"] + b / 2, P["yb"] + 3), box_poly(P["m2"] - b / 2, P["yt"] - 4, P["m2"] + b / 2, P["yb"] + 3),
             box_poly(P["xl"] - 3, P["to"] - b / 2, P["m1"], P["to"] + b / 2), box_poly(P["m2"], P["to"] - b / 2, P["xr"] + 3, P["to"] + b / 2), box_poly(P["m1"], P["tm"] - b / 2, P["m2"], P["tm"] + b / 2)]
    ges = ges - ms(nische)
    for sp in ([] if a.ohne_staebe else stäbe): ges = ges + ms(prisma(sp, hinten, sv, px0, py0)) if True else ges
    alle.append(nische)
out = ges.to_mesh(); res = trimesh.Trimesh(mm(np.asarray(out.vert_properties)[:, :3]), np.asarray(out.tri_verts)); res.export(a.aus)
print(json.dumps(dict(fenster=bericht, wasserdicht=bool(res.is_watertight), flaechen=len(res.faces), volumen_mm3=float(res.volume))))
