#!/usr/bin/env python3
"""hofgut_detail2.py — Detail-Modell AUF der echten LOD2-Geometrie (nichts wegwerfen!).

Korrektur gegenüber hofgut_sternen.py (das die echte Gliederung durch eine Box ersetzte):
  Basis = echtes LOD2-Mesh (mit dem mittleren vorderen VORBAU + aller Artikulation).
  Details werden an die ECHTEN süd-orientierten (Talseite) Flächen angesetzt:
    - Balkonbänder: Horizontal-Schnitt der Südwände bei z=3 und z=6, nach Süden ausgekragt
      → folgt automatisch dem Vorbau.
    - Gauben: auf den süd-orientierten Dachflächen (zwei Höhenbänder).
    - Kamine: an den höchsten First-Punkten.
  Farben: Sockel (z<3) Stein, Wände Putz/Holz, Dach Schindel.

Talseite (Süd) = datengetrieben aus DOP (Vorplatz/Terrasse im Süden).
"""
import argparse, os, sys
import numpy as np
import trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as L

SOUTH = np.array([0.0, -1.0])     # Talseite-Normale in (E,N): nach Süden


def tris_from(picked, types, origin):
    m, _ = L.build_mesh(picked, types=types, origin=origin)
    return m


def plane_cut_segments(mesh, z0, want_south=True, min_dot=0.25, vertical=True):
    """Schnittsegmente der Dreiecke mit Ebene z=z0, gefiltert nach Außen-Normale (Süd)."""
    V, F, N = mesh.vertices, mesh.faces, mesh.face_normals
    segs = []
    for f, n in zip(F, N):
        nh = n[:2]; nn = np.linalg.norm(nh)
        if nn < 1e-6:
            continue
        if want_south and np.dot(nh / nn, SOUTH) < min_dot:
            continue
        if vertical and abs(n[2]) > 0.6:     # nur ~senkrechte Wände
            continue
        if (not vertical) and n[2] < 0.2:     # nur Dach-Oberseiten
            continue
        p = V[f]
        zs = p[:, 2]
        if zs.min() > z0 or zs.max() < z0:
            continue
        pts = []
        for i in range(3):
            a, b = p[i], p[(i + 1) % 3]
            if (a[2] - z0) * (b[2] - z0) < 0:
                t = (z0 - a[2]) / (b[2] - a[2])
                pts.append(a + t * (b - a))
        if len(pts) == 2:
            segs.append((np.array(pts[0]), np.array(pts[1]), n[:2] / nn))
    return segs


def box(x0, y0, z0, dx, dy, dz):
    b = trimesh.creation.box(extents=(dx, dy, dz))
    b.apply_translation((x0 + dx / 2, y0 + dy / 2, z0 + dz / 2))
    return b


def balcony(segs, z0, proj, origin_xy):
    """Deck + Brüstung entlang der Südwand-Segmente, nach außen ausgekragt."""
    parts = []
    for p0, p1, n in segs:
        L_ = np.linalg.norm(p1[:2] - p0[:2])
        if L_ < 1.0:
            continue
        out = np.array([n[0], n[1], 0.0]) * proj
        # Deck-Quad (p0,p1 an der Wand; +out nach außen), Dicke 0.18
        A, B = p0.copy(), p1.copy()
        A[2] = B[2] = z0
        quad = [A, B, B + out, A + out]
        deck = trimesh.Trimesh(vertices=np.array(quad + [q - [0, 0, 0.18] for q in quad]),
                               faces=_boxfaces(), process=True)
        parts.append(deck)
        # Brüstung: Pfosten + Leiste außen
        edge0, edge1 = A + out, B + out
        nseg = max(2, int(L_ / 1.0))
        for t in np.linspace(0, 1, nseg):
            pp = edge0 + (edge1 - edge0) * t
            parts.append(box(pp[0] - 0.04, pp[1] - 0.04, z0, 0.08, 0.08, 1.0))
        # obere/untere Leiste
        for zz in (z0 + 0.9, z0 + 0.1):
            mid = (edge0 + edge1) / 2
            d = edge1 - edge0; ln = np.linalg.norm(d)
            ang = np.arctan2(d[1], d[0])
            bar = trimesh.creation.box(extents=(ln, 0.07, 0.07))
            Trot = trimesh.transformations.rotation_matrix(ang, [0, 0, 1])
            bar.apply_transform(Trot); bar.apply_translation((mid[0], mid[1], zz))
            parts.append(bar)
    return trimesh.util.concatenate(parts) if parts else None


def _boxfaces():
    return np.array([[0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
                     [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
                     [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0]])


def dormers_on_roof(roof, z_levels, origin_xy, per=0.0):
    """Gauben entlang der Süd-Dach-Schnittlinien bei gegebenen Höhen."""
    parts = []
    for z0, n_target in z_levels:
        segs = plane_cut_segments(roof, z0, want_south=True, min_dot=0.2, vertical=False)
        # Segmente zu einer Linie ordnen (nach x), Gauben gleichmäßig verteilen
        if not segs:
            continue
        mids = np.array([((p0 + p1) / 2) for p0, p1, _ in segs])
        order = np.argsort(mids[:, 0])
        mids = mids[order]; norms = [segs[i][2] for i in order]
        # entlang x gleichmäßig n_target Stück
        xs = np.linspace(mids[:, 0].min() + 1.0, mids[:, 0].max() - 1.0, n_target)
        for x in xs:
            j = np.argmin(np.abs(mids[:, 0] - x))
            p = mids[j]; n = norms[j]
            out = np.array([n[0], n[1], 0.0])
            w = 1.8; proj = 1.6; h = 1.5
            # Front-Wand der Gaube (außen), + kleines Pultdach zurück zur Schräge
            perp = np.array([-n[1], n[0], 0.0])
            base = np.array([p[0], p[1], z0])
            fo = base + out * proj
            V = [base + perp * (w / 2), base - perp * (w / 2),
                 fo + perp * (w / 2) + [0, 0, 0], fo - perp * (w / 2),
                 fo + perp * (w / 2) + [0, 0, h], fo - perp * (w / 2) + [0, 0, h],
                 base + perp * (w / 2) + [0, 0, h + 0.3], base - perp * (w / 2) + [0, 0, h + 0.3]]
            F = [(2, 3, 5), (2, 5, 4), (4, 5, 7), (4, 7, 6),
                 (0, 2, 4), (0, 4, 6), (1, 5, 3), (1, 7, 5),
                 (0, 1, 3), (0, 3, 2)]
            parts.append(trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True))
    return trimesh.util.concatenate(parts) if parts else None


def chimneys_from_ridge(roof, n_ch):
    """Kamine an den höchsten First-Bereichen (lokale z-Maxima der Dachknoten)."""
    V = roof.vertices
    zmax = V[:, 2].max()
    top = V[V[:, 2] > zmax - 1.5]
    if len(top) == 0:
        return None
    order = np.argsort(top[:, 0])
    top = top[order]
    xs = np.linspace(top[:, 0].min() + 2, top[:, 0].max() - 2, n_ch)
    parts = []
    for x in xs:
        j = np.argmin(np.abs(top[:, 0] - x)); p = top[j]
        parts.append(box(p[0] - 0.5, p[1] - 0.5, p[2] - 1.0, 1.0, 1.0, 2.6))
    return trimesh.util.concatenate(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml", default="daten/ravenna/lod2/LoD2_32_429_5306_2_bw/LoD2_32_430_5307_1_BW.gml")
    ap.add_argument("--socle", type=float, default=3.0)
    ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--balc-proj", type=float, default=1.3)
    ap.add_argument("--chimneys", type=int, default=3)
    ap.add_argument("--outdir", default="modelle/hofgut_sternen")
    a = ap.parse_args()

    picked = L.extract(a.gml, name="Hofgut Sternen")
    allpts = np.vstack([P for _, polys in picked for _, P in polys])
    o = np.array([allpts[:, 0].min(), allpts[:, 1].min(), allpts[:, 2].min()])

    roof = tris_from(picked, {"RoofSurface"}, o)
    walls = tris_from(picked, {"WallSurface", "ClosureSurface"}, o)
    ground = tris_from(picked, {"GroundSurface"}, o)

    # Sockel/Wände farblich trennen: Dreiecke unter/über socle
    def split_z(mesh, zc):
        V, F = mesh.vertices, mesh.faces
        lo, hi = [], []
        for f in F:
            (lo if V[f][:, 2].mean() < zc else hi).append(f)
        a_ = trimesh.Trimesh(V, np.array(lo), process=False) if lo else None
        b_ = trimesh.Trimesh(V, np.array(hi), process=False) if hi else None
        return a_, b_
    sockel, wand = split_z(walls, a.socle)

    south_lvls = [(a.socle + 0.1, None), (a.socle + a.floor + 0.1, None)]
    balk = []
    for z0, _ in south_lvls:
        segs = plane_cut_segments(walls, z0, want_south=True, min_dot=0.25, vertical=True)
        b = balcony(segs, z0, a.balc_proj, o)
        if b: balk.append(b)
    balkone = trimesh.util.concatenate(balk) if balk else None

    eave = min(m.get("eave_m", 9) for m, _ in picked if m.get("eave_m"))
    ridge = max(m.get("ridge_m", 17.5) for m, _ in picked if m.get("ridge_m"))
    gauben = dormers_on_roof(roof, [(eave + 0.30 * (ridge - eave), 7),
                                    (eave + 0.62 * (ridge - eave), 6)], o)
    kamine = chimneys_from_ridge(roof, a.chimneys)

    os.makedirs(a.outdir, exist_ok=True)
    out = {"hofgut_r_sockel": sockel, "hofgut_r_wand": wand, "hofgut_r_dach": roof,
           "hofgut_r_balkone": balkone, "hofgut_r_gauben": gauben, "hofgut_r_kamine": kamine}
    tot = []
    for nm, m in out.items():
        if m is None or len(m.faces) == 0:
            print(f"  (leer: {nm})"); continue
        m.export(f"{a.outdir}/{nm}.stl"); tot.append(m)
        print(f"  {nm}: {len(m.faces)} F")
    full = trimesh.util.concatenate(tot); full.export(f"{a.outdir}/hofgut_real_detail.stl")
    ext = full.bounds[1] - full.bounds[0]
    print(f"\nECHTE Geometrie + Detail: {len(full.faces)} F  L×B×H {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f} m")
    print(f"  Traufe {eave:.1f} First {ridge:.1f} m · Vorbau+Artikulation ERHALTEN")
    print(f"-> {a.outdir}/hofgut_real_detail.stl")


if __name__ == "__main__":
    main()
