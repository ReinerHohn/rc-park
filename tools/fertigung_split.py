#!/usr/bin/env python3
"""fertigung_split.py - beliebiges Modell (STL, mm) in LASERCUT-Platten + 3D-DRUCK-Teile aufteilen.

Allgemein, ohne Wissen ueber das Objekt:
  1. Findet grosse EBENE Flaechen (coplanare Dreiecke, zusammenhaengend) -> das sind Laser-Platten.
  2. Je Platte: Umriss + Loecher in der Plattenebene (von aussen gesehen, lesbar nummeriert).
       Loch = Vertiefung (Fenster, Tor, Nische)  -> wird DURCHGESCHNITTEN (rot)
       Loch = Erhebung  (Gewaende, Relief, Tafel) -> Platte bleibt voll, Umriss wird GRAVIERT (gruen) als Klebemarke
  3. Rest = Modell minus Plattenvolumen minus Innenkern (Hohlschale) -> 3D-Druck-Teile
       (Eckpfosten, Zinnen, Reliefs, Tuerme, Kegel ...). Zu grosse Teile werden gleichmaessig geteilt.
  4. Schreibt SVG (Schnitt #f00 / Gravur #0a0, wie laser_blank_cut.py), Druck-STLs, Stueckliste (CSV + Text)
     und startet optional laser_blank_cut.py -> fertige Rohlinge + GRBL-G-Code (Sculpfun S9, 410x400).

Lauf (venv-seg: trimesh, shapely, manifold3d, scipy, skimage):
  /media/oem/scan/venv-seg/bin/python -I tools/fertigung_split.py modelle/stl/martinstor_v4_1-87.stl \
      --out modelle/martinstor_fertigung --dicke 2 --bett 410x400 --druck 220x220x250 --gcode
"""
import argparse, csv, glob, math, os, re, subprocess, sys
import numpy as np, trimesh
import manifold3d as M
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from shapely.geometry import Polygon, MultiPolygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))

# Strich-Font fuer die Plattennummern (aus laser_relief_kit.py, ohne matplotlib-Import)
def _font():
    src = open(os.path.join(HERE, "laser_relief_kit.py")).read().splitlines()
    i = next(k for k, l in enumerate(src) if l.startswith("_A="))
    j = next(k for k, l in enumerate(src) if l.startswith(" 'P':"))
    ns = {}; exec("\n".join(src[i:j + 1]), ns); return ns["FONT"]
FONT = _font()

def glyphs(text, ox, oy, h):
    s = h / 10.0; adv = 6 * s + 2.0; out = []
    for ch in str(text):
        for st in FONT.get(ch, []):
            out.append(np.array([(ox + x * s, oy + y * s) for x, y in st]))
        ox += adv
    return out


# ---------------------------------------------------------------- 1. ebene Flaechen
def planar_clusters(m, ang_deg, tol):
    n = m.face_normals; A = m.area_faces
    fa = m.face_adjacency
    cosA = math.cos(math.radians(ang_deg))
    ok = (n[fa[:, 0]] * n[fa[:, 1]]).sum(1) >= cosA
    # Ebenenabstand: Eckpunkt von Dreieck B gegen Ebene von Dreieck A
    p0 = m.vertices[m.faces[fa[:, 0], 0]]
    d = np.abs(np.einsum("ij,ij->i", n[fa[:, 0]], m.vertices[m.faces[fa[:, 1]]].mean(1) - p0))
    ok &= d < tol
    g = coo_matrix((np.ones(ok.sum()), (fa[ok, 0], fa[ok, 1])), shape=(len(n), len(n)))
    k, lab = connected_components(g, directed=False)
    return k, lab


def plane_frame(normal):
    """Rechte Hand: von aussen auf die Platte gesehen, u nach rechts, v nach oben."""
    n = normal / np.linalg.norm(normal)
    up = np.array([0, 0, 1.0]) if abs(n[2]) < 0.9 else np.array([0, 1.0, 0])
    v = up - n * (up @ n); v /= np.linalg.norm(v)
    u = np.cross(v, n); u /= np.linalg.norm(u)
    return u, v, n


def cluster_polygon(m, fidx, O, u, v):
    tris = []
    for f in fidx:
        P = m.vertices[m.faces[f]] - O
        q = np.column_stack([P @ u, P @ v])
        pg = Polygon(q)
        if pg.area > 1e-9: tris.append(pg if pg.is_valid else pg.buffer(0))
    if not tris: return None
    U = unary_union([t.buffer(1e-4) for t in tris]).buffer(-1e-4)
    return U


def largest(poly):
    if isinstance(poly, MultiPolygon): return max(poly.geoms, key=lambda g: g.area)
    return poly



def classify_hole(m, hole, O, u, v, n, through_min, maxcells=3000):
    """Raster aus Strahlen von aussen: Zellen tiefer als through_min (oder ohne Treffer) = Durchbruch,
    Zellen ueber der Ebene = Erhebung. Gibt (durchbruch_geom, erhebung_geom) in Plattenkoordinaten."""
    from shapely.geometry import box
    x0, y0, x1, y1 = hole.bounds
    g = max(0.4, math.sqrt(max(hole.area, 1e-6) / maxcells))
    xs = np.arange(x0 + g / 2, x1, g); ys = np.arange(y0 + g / 2, y1, g)
    X, Y = np.meshgrid(xs, ys); pts = np.column_stack([X.ravel(), Y.ravel()])
    from shapely import contains_xy
    inside = contains_xy(hole, pts[:, 0], pts[:, 1]); pts = pts[inside]
    if len(pts) == 0: return None, hole
    org = O + np.outer(pts[:, 0], u) + np.outer(pts[:, 1], v) + n * 6.0
    dirs = np.tile(-n, (len(pts), 1))
    loc, ir, _ = m.ray.intersects_location(org, dirs, multiple_hits=False)
    dd = np.full(len(pts), np.inf); dd[ir] = np.linalg.norm(loc - org[ir], axis=1)
    depth = dd - 6.0
    thr = depth >= through_min                       # tiefer oder kein Treffer (inf)
    boxes = [box(p[0] - g / 2, p[1] - g / 2, p[0] + g / 2, p[1] + g / 2) for p in pts[thr]]
    through = unary_union(boxes).intersection(hole).buffer(g * 0.3).intersection(hole) if boxes else None
    relief = hole if through is None else hole.difference(through)
    return through, relief

# ---------------------------------------------------------------- 3. Kern / Hohlschale
def to_manifold(mesh):
    mm = M.Mesh(np.asarray(mesh.vertices, np.float32), np.asarray(mesh.faces, np.uint32))
    return M.Manifold(mm)

def from_manifold(man):
    mm = man.to_mesh()
    return trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3].astype(float), np.asarray(mm.tri_verts), process=True)

def core_mesh(m, shell, pitch):
    """Innenkern = alles, was tiefer als 'shell' unter der Oberflaeche liegt (grobes Voxel-Netz, nur zum Abziehen)."""
    vox = m.voxelized(pitch).fill()
    mat = np.pad(vox.matrix, 2)
    dt = ndi.distance_transform_edt(mat) * pitch
    if dt.max() <= shell: return None
    from skimage import measure
    vv, ff, _, _ = measure.marching_cubes(dt, level=shell, spacing=(pitch,) * 3)
    org = vox.transform[:3, 3] - 2 * pitch
    c = trimesh.Trimesh(vv + org, ff, process=True)
    c.fix_normals()
    return c


def split_oversize(man, limit, name):
    """Teile > Bauraum gleichmaessig an Ebenen senkrecht zur laengsten Achse (rekursiv)."""
    lo, hi = man.bounding_box()[:3], man.bounding_box()[3:]
    ext = np.array(hi) - np.array(lo)
    # beste Lage: Achsenzuordnung der Teilegroesse zu den Bauraumachsen (sortiert)
    order = np.argsort(-ext); lim_sorted = np.sort(np.array(limit))[::-1]
    over = [(a, ext[a] / lim_sorted[i]) for i, a in enumerate(order) if ext[a] > lim_sorted[i]]
    if not over: return [man]
    ax = max(over, key=lambda t: t[1])[0]
    pieces = int(math.ceil(ext[ax] / lim_sorted[list(order).index(ax)] - 1e-9))
    pieces = max(2, pieces)
    cuts = [lo[ax] + ext[ax] * k / pieces for k in range(1, pieces)]
    out = []; rest = man
    nrm = np.zeros(3); nrm[ax] = 1.0
    for c in cuts:
        a = rest.trim_by_plane(tuple(-nrm), -c)    # unterer Teil (<= c)
        rest = rest.trim_by_plane(tuple(nrm), c)   # oberer Teil
        out.append(a)
    out.append(rest)
    res = []
    for p in out: res += split_oversize(p, limit, name)
    return res


# ---------------------------------------------------------------- Hauptprogramm
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stl"); ap.add_argument("--out", required=True)
    ap.add_argument("--dicke", type=float, default=2.0, help="Plattendicke mm (Karton/Sperrholz)")
    ap.add_argument("--bett", default="410x400", help="Laserbett BxH mm (S9: 410x400)")
    ap.add_argument("--druck", default="220x220x250", help="Bauraum des Druckers X x Y x Z mm")
    ap.add_argument("--min-flaeche", type=float, default=600.0, help="kleinste Laserplatte, mm2")
    ap.add_argument("--min-breite", type=float, default=10.0, help="kuerzeste Plattenseite mm")
    ap.add_argument("--winkel", type=float, default=0.6, help="Toleranz coplanar, Grad")
    ap.add_argument("--abstand", type=float, default=0.12, help="Toleranz coplanar, mm")
    ap.add_argument("--schale", type=float, default=2.4, help="Wandstaerke der gedruckten Hohlteile mm")
    ap.add_argument("--durchbruch-ab", type=float, default=1.0, help="Vertiefung tiefer als x mm = durchschneiden")
    ap.add_argument("--traeger", type=float, default=0.5, help="Traegerschicht unter Aufsaetzen mm (verbindet Reliefs)")
    ap.add_argument("--traeger-rand", type=float, default=0.8, help="Traeger ragt x mm ueber das Relief hinaus")
    ap.add_argument("--inset", type=float, default=0.0, help="Plattenumriss um x mm verkleinern (Stossfuge)")
    ap.add_argument("--horizontal", action="store_true", help="auch waagrechte Flaechen (Boden/Decke) als Platten")
    ap.add_argument("--kein-kern", action="store_true", help="Druckteile massiv (nicht aushoehlen)")
    ap.add_argument("--voxel", type=float, default=1.0, help="Voxelgroesse fuer Kernberechnung mm")
    ap.add_argument("--gcode", action="store_true", help="laser_blank_cut.py aufrufen: Rohlinge + G-Code")
    ap.add_argument("--keine-platten", action="store_true", help="nur Druckteile (Test)")
    a = ap.parse_args()

    out = a.out; os.makedirs(out + "/laser", exist_ok=True); os.makedirs(out + "/druck", exist_ok=True)
    for f in glob.glob(out + "/laser/*") + glob.glob(out + "/druck/*"):
        if os.path.isfile(f): os.remove(f)
    bw, bh = (float(x) for x in a.bett.lower().split("x"))
    lim = tuple(float(x) for x in a.druck.lower().split("x"))

    m = trimesh.load(a.stl); m.merge_vertices()
    print(f"Modell {np.round(m.extents,1)} mm, {len(m.faces)} Dreiecke, wasserdicht={m.is_watertight}")
    if not m.is_watertight: print("WARNUNG: nicht wasserdicht - Ergebnis unsicher")

    # ---- 1. Platten finden
    k, lab = planar_clusters(m, a.winkel, a.abstand)
    area = np.bincount(lab, weights=m.area_faces, minlength=k)
    cand = [c for c in np.argsort(-area) if area[c] >= a.min_flaeche]
    panels = []
    for c in cand:
        fidx = np.where(lab == c)[0]
        nrm = (m.face_normals[fidx] * m.area_faces[fidx, None]).sum(0); nrm /= np.linalg.norm(nrm)
        if abs(nrm[2]) > 0.97 and not a.horizontal: continue
        O = m.triangles_center[fidx].mean(0)
        u, v, n = plane_frame(nrm)
        pg = cluster_polygon(m, fidx, O, u, v)
        if pg is None or pg.is_empty: continue
        pg = largest(pg)
        w = pg.minimum_rotated_rectangle
        xs, ys = np.array(w.exterior.coords)[:3], None
        e = [np.linalg.norm(np.array(w.exterior.coords)[i + 1] - np.array(w.exterior.coords)[i]) for i in range(2)]
        if min(e) < a.min_breite: continue
        panels.append(dict(c=c, fidx=fidx, n=n, u=u, v=v, O=O, poly=pg, area=pg.area, w=max(e), h=min(e)))
    if a.keine_platten: panels = []
    print(f"{len(panels)} Laser-Platten (>= {a.min_flaeche:.0f} mm2, >= {a.min_breite:.0f} mm breit)")

    # ---- 2. Loecher klassifizieren (Erhebung vs. Vertiefung) per Strahl
    cut_polys = {}   # id -> (outer ring pts, [hole rings], [engrave rings])
    prisms = []; carriers = []
    D = a.schale + 0.8
    manifest = []
    for pid, P in enumerate(panels, 1):
        poly = P["poly"]; O, u, v, n = P["O"], P["u"], P["v"], P["n"]
        holes = [Polygon(r) for r in poly.interiors]
        outer = Polygon(poly.exterior)
        keep_holes, eng = [], []
        for h in holes:
            thr, rel = classify_hole(m, h, O, u, v, n, a.durchbruch_ab)
            if thr is not None and not thr.is_empty: keep_holes.append(thr)
            if rel is not None and not rel.is_empty:
                for gpart in (rel.geoms if hasattr(rel, 'geoms') else [rel]):
                    if gpart.geom_type == 'Polygon' and gpart.area > 0.5: eng.append(gpart)
        sheet = outer
        for h in keep_holes: sheet = sheet.difference(h)
        P['carrier'] = unary_union([e.buffer(a.traeger_rand) for e in eng]).intersection(outer) if eng else None
        if a.inset > 0: sheet = sheet.buffer(-a.inset)
        sheet = largest(sheet)
        P.update(sheet=sheet, eng=eng, nkeep=len(keep_holes), neng=len(eng), id=pid)
        # Volumen, das die Platte ersetzt: Umriss ohne Durchbrueche, 'D' mm nach innen
        vol = outer
        for h in keep_holes: vol = vol.difference(h)
        vol = largest(vol)
        rings = [np.array(orient(vol).exterior.coords)[:-1]] + [np.array(r.coords)[:-1][::-1] for r in orient(vol).interiors]
        if vol.area > 1:
            pr = M.Manifold.extrude(M.CrossSection([np.asarray(r, float) for r in rings]), D).translate((0, 0, -D))
            Rm = np.column_stack([u, v, n, O])             # local (x,y,z) -> Welt
            prisms.append(pr.transform(Rm))
            cr = P.get('carrier')
            if cr is not None and not cr.is_empty:
                for g in (cr.geoms if hasattr(cr, 'geoms') else [cr]):
                    if g.area < 1 or g.geom_type != 'Polygon': continue
                    g = orient(g)
                    rr = [np.array(g.exterior.coords)[:-1]] + [np.array(r.coords)[:-1][::-1] for r in g.interiors]
                    carriers.append(M.Manifold.extrude(M.CrossSection([np.asarray(r, float) for r in rr]), a.traeger).translate((0, 0, -a.traeger)).transform(Rm))
        mn = np.array(sheet.bounds)
        P["wh"] = (mn[2] - mn[0], mn[3] - mn[1])
        manifest.append(P)

    # ---- SVGs je Platte (y nach unten fuer SVG; von aussen gesehen)
    csv_rows = []
    for P in manifest:
        sheet = P["sheet"]; mnx, mny, mxx, mxy = sheet.bounds
        def T(c): c = np.asarray(c); return np.column_stack([c[:, 0] - mnx + 6, (mxy - c[:, 1]) + 6])
        paths = []
        def add(ring, col):
            r = T(ring)
            paths.append(f'<path d="M {" L ".join(f"{x:.2f},{y:.2f}" for x, y in r)} Z" fill="none" stroke="{col}" stroke-width="0.1"/>')
        add(np.array(sheet.exterior.coords)[:-1], "#f00")
        for r in sheet.interiors: add(np.array(r.coords)[:-1], "#f00")
        for h in P["eng"]: add(np.array(h.exterior.coords)[:-1], "#0a0")
        label = f"{P['id']}"
        hh = min(8.0, max(3.0, (mxy - mny) * 0.1))
        rp = sheet.representative_point()
        for st in glyphs(label, 0, 0, hh):
            st = st + np.array([rp.x, rp.y])           # in Plattenkoords, y nach oben
            r = T(st); paths.append(f'<path d="M {" L ".join(f"{x:.2f},{y:.2f}" for x, y in r)}" fill="none" stroke="#0a0" stroke-width="0.1"/>')
        W = mxx - mnx + 12; H = mxy - mny + 12
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}mm" height="{H:.1f}mm" viewBox="0 0 {W:.1f} {H:.1f}">'] + paths + ["</svg>"]
        open(f"{out}/laser/rib_platte_{P['id']:02d}.svg", "w").write("\n".join(svg) + "\n")
        csv_rows.append([f"platte_{P['id']:02d}", f"{P['wh'][0]:.1f}", f"{P['wh'][1]:.1f}", f"{a.dicke:.1f}",
                         P["nkeep"], P["neng"], *[f"{x:.1f}" for x in P["O"]], *[f"{x:.3f}" for x in P["n"]]])

    # ---- 3. Druckteile
    man = to_manifold(m)
    for pr in prisms: man = man - pr
    if not a.kein_kern and a.schale > 0:
        core = core_mesh(m, a.schale, a.voxel)
        if core is not None and len(core.faces) > 0:
            man = man - to_manifold(core)
            print(f"Kern abgezogen (Schale {a.schale} mm)")
    for cr in carriers: man = man + cr
    comps = [c for c in man.decompose() if c.volume() > 0.5 and min(np.array(c.bounding_box()[3:]) - np.array(c.bounding_box()[:3])) > 0.3]   # Splitter < 0,3 mm raus
    comps.sort(key=lambda c: -c.volume())
    print(f"{len(comps)} Druck-Einzelteile")
    plist = []
    for ci, c in enumerate(comps, 1):
        pieces = split_oversize(c, lim, f"d{ci}")
        for pi, pm in enumerate(pieces, 1):
            mesh = from_manifold(pm)
            if len(mesh.faces) < 4 or mesh.volume < 0.5: print('  verworfen', name_dbg := f'druck_{ci:03d}_{pi}', len(mesh.faces)); continue
            e = np.sort(mesh.extents)[::-1]; fits = all(e[i] <= sorted(lim, reverse=True)[i] + 1e-6 for i in range(3))
            name = f"druck_{ci:03d}" + (f"_{pi}von{len(pieces)}" if len(pieces) > 1 else "")
            mesh.export(f"{out}/druck/{name}.stl")
            plist.append((name, mesh.extents, mesh.volume / 1000.0, fits, len(pieces)))

    # ---- Stueckliste
    with open(out + "/laser_platten.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["name", "breite_mm", "hoehe_mm", "dicke_mm", "durchbrueche", "klebemarken", "ox", "oy", "oz", "nx", "ny", "nz"]); w.writerows(csv_rows)
    sheet_area = sum(P["sheet"].area for P in manifest)
    L = [f"FERTIGUNG  {os.path.basename(a.stl)}  ({np.round(m.extents,1)} mm)",
         f"Laser: {len(manifest)} Platten, {a.dicke:.1f} mm, Summe {sheet_area/100:.0f} cm2 (Bett {bw:.0f}x{bh:.0f})",
         f"Druck: {len(plist)} Dateien, Volumen {sum(p[2] for p in plist):.1f} cm3 (Bauraum {a.druck})", ""]
    big = [P for P in manifest if (P['wh'][0] > bw - 10 or P['wh'][1] > bh - 10) and max(P['wh']) > max(bw, bh) - 10]
    if big: L.append("WARNUNG Platten groesser als Bett: " + ", ".join(f"platte_{P['id']:02d}" for P in big))
    L.append("PLATTEN (Nr  BxH mm  Durchbrueche/Klebemarken):")
    for P in manifest: L.append(f"  {P['id']:02d}  {P['wh'][0]:.0f}x{P['wh'][1]:.0f}  {P['nkeep']}/{P['neng']}")
    L.append("DRUCKTEILE (Datei  Masse mm  cm3  passt):")
    for n_, e_, v_, ft, k_ in plist:
        L.append(f"  {n_}.stl  {e_[0]:.0f}x{e_[1]:.0f}x{e_[2]:.0f}  {v_:.2f}  {'ja' if ft else 'NEIN'}" + (f"  (geteilt in {k_})" if k_ > 1 else ""))
    open(out + "/STUECKLISTE.txt", "w").write("\n".join(L) + "\n")
    print("\n".join(L[:4])); print(f"-> {out}/STUECKLISTE.txt")

    # ---- Rohlinge + G-Code
    if a.gcode and manifest:
        py = os.path.expanduser("~/.venvs/strom/bin/python")
        if not os.path.exists(py): py = sys.executable
        r = subprocess.run([py, os.path.join(HERE, "laser_blank_cut.py"), out + "/laser", "--machine", a.bett,
                            "--gcode", "--out", out + "/rohlinge"], capture_output=True, text=True)
        print(r.stdout[-600:] + (r.stderr[-400:] if r.returncode else ""))


if __name__ == "__main__":
    main()
