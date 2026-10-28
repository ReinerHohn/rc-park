#!/usr/bin/env python3
"""gebaeude_detailer.py — GENERISCH: beliebiges LOD2-Gebäude → echte Geometrie + Details.

Nichts wird weggeworfen: Basis = echtes LOD2-Mesh (volle Artikulation, Vorbauten).
Details werden an die ECHTEN, zur TALSEITE orientierten Flächen angesetzt:
  - Sockel/Wand farblich getrennt (Höhen-Schnitt)
  - Balkonbänder: Horizontal-Schnitt der Talseiten-Wände, ausgekragt (folgt Vorbauten)
  - Gauben: auf den Talseiten-Dachflächen (beliebige Höhenbänder)
  - Kamine: an den höchsten First-Bereichen

Talseite (Front) datengetrieben: DGM-Talrichtung (bergab) ODER --front-az; sonst
Footprint-Heuristik. KEIN Bauwerk hartcodiert — Hofgut Sternen ist nur ein Aufruf:

  python3 tools/gebaeude_detailer.py \
     --gml .../LoD2_32_430_5307_1_BW.gml --name "Hofgut Sternen" \
     --dgm daten/ravenna/ravenna_dgm1.npy --dgm-origin 429000,5306000 \
     --socle 3 --floor 3 --balc-levels 2 --dormer-rows 0.30:7,0.62:6 --chimneys 3 \
     --outdir modelle/hofgut_sternen --prefix hofgut
"""
import argparse, os, sys
import numpy as np
import trimesh
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lod2_gebaeude as L


# ---------------- Talseite (Front) datengetrieben bestimmen ----------------

def front_from_dgm(dgm_path, origin_en, center_en, res=1.0, win=60):
    """Talrichtung (bergab) am Gebäude = Front-Normale (E,N). Generelles Prinzip:
    Gebäude am Hang zeigen zum Tal."""
    a = np.load(dgm_path)
    E0, N0 = origin_en
    cx = int((center_en[0] - E0) / res)
    cy = int((center_en[1] - N0) / res)
    H, W = a.shape
    # Konvention: Zeile 0 = Nord (oben) ODER Süd? LGL-XYZ→npy meist row0=Nmin.
    # Wir testen beide: nehmen die mit plausiblerem Gefälle (größerer |grad|).
    def grad_at(row_is_north):
        r = (H - 1 - cy) if row_is_north else cy
        r = min(max(r, win), H - win - 1); c = min(max(cx, win), W - win - 1)
        patch = a[r - win:r + win, c - win:c + win]
        gy, gx = np.gradient(patch)        # gx: +col(=+E), gy: +row
        ge = np.nanmedian(gx) / res
        gn = (-np.nanmedian(gy) if row_is_north else np.nanmedian(gy)) / res
        return np.array([ge, gn])
    g = grad_at(True)
    if np.linalg.norm(g) < 1e-4:
        g = grad_at(False)
    down = -g                               # bergab
    n = np.linalg.norm(down)
    return down / n if n > 1e-6 else None


def front_from_footprint(foot_xy, center_xy):
    """Fallback: längste Fassade, Außen-Normale weg vom Schwerpunkt."""
    P = foot_xy
    d = np.diff(np.vstack([P, P[:1]]), axis=0)
    Ln = np.hypot(d[:, 0], d[:, 1]); k = Ln.argmax()
    mid = (P[k] + P[(k + 1) % len(P)]) / 2
    nrm = np.array([d[k, 1], -d[k, 0]]); nrm = nrm / np.linalg.norm(nrm)
    if np.dot(mid - center_xy, nrm) < 0:
        nrm = -nrm
    return nrm


# ---------------- Geometrie-Helfer (generisch) ----------------

def _boxfaces():
    return np.array([[0, 1, 2], [0, 2, 3], [4, 6, 5], [4, 7, 6],
                     [0, 4, 5], [0, 5, 1], [1, 5, 6], [1, 6, 2],
                     [2, 6, 7], [2, 7, 3], [3, 7, 4], [3, 4, 0]])


def box(x0, y0, z0, dx, dy, dz):
    b = trimesh.creation.box(extents=(dx, dy, dz))
    b.apply_translation((x0 + dx / 2, y0 + dy / 2, z0 + dz / 2))
    return b


def plane_cut_segments(mesh, z0, front, min_dot=0.25, want="wall"):
    """Schnittsegmente der Front-orientierten Dreiecke mit Ebene z=z0.
    want='wall' (~senkrecht) oder 'roof' (Oberseite)."""
    V, F, N = mesh.vertices, mesh.faces, mesh.face_normals
    segs = []
    for f, n in zip(F, N):
        nh = n[:2]; nn = np.linalg.norm(nh)
        if nn < 1e-6 or np.dot(nh / nn, front) < min_dot:
            continue
        if want == "wall" and abs(n[2]) > 0.6:
            continue
        if want == "roof" and n[2] < 0.2:
            continue
        p = V[f]; zs = p[:, 2]
        if zs.min() > z0 or zs.max() < z0:
            continue
        pts = []
        for i in range(3):
            A, B = p[i], p[(i + 1) % 3]
            if (A[2] - z0) * (B[2] - z0) < 0:
                t = (z0 - A[2]) / (B[2] - A[2]); pts.append(A + t * (B - A))
        if len(pts) == 2:
            segs.append((np.array(pts[0]), np.array(pts[1]), nh / nn))
    return segs


def balcony_band(segs, z0, proj):
    parts = []
    for p0, p1, n in segs:
        ln = np.linalg.norm(p1[:2] - p0[:2])
        if ln < 1.0:
            continue
        out = np.array([n[0], n[1], 0.0]) * proj
        A, B = p0.copy(), p1.copy(); A[2] = B[2] = z0
        quad = [A, B, B + out, A + out]
        deck = trimesh.Trimesh(vertices=np.array(quad + [q - [0, 0, 0.18] for q in quad]),
                               faces=_boxfaces(), process=True)
        parts.append(deck)
        e0, e1 = A + out, B + out
        for t in np.linspace(0, 1, max(2, int(ln / 1.0))):
            pp = e0 + (e1 - e0) * t
            parts.append(box(pp[0] - 0.04, pp[1] - 0.04, z0, 0.08, 0.08, 1.0))
        d = e1 - e0; ang = np.arctan2(d[1], d[0]); mid = (e0 + e1) / 2
        for zz in (z0 + 0.9, z0 + 0.1):
            bar = trimesh.creation.box(extents=(np.linalg.norm(d), 0.07, 0.07))
            bar.apply_transform(trimesh.transformations.rotation_matrix(ang, [0, 0, 1]))
            bar.apply_translation((mid[0], mid[1], zz)); parts.append(bar)
    return trimesh.util.concatenate(parts) if parts else None


def dormer_row(roof, z0, n_target, front):
    segs = plane_cut_segments(roof, z0, front, min_dot=0.2, want="roof")
    if not segs:
        return None
    mids = np.array([(p0 + p1) / 2 for p0, p1, _ in segs]); norms = [s[2] for s in segs]
    # entlang Haupt-Erstreckung (längere Achse) verteilen
    span = mids.max(0) - mids.min(0); ax = 0 if abs(span[0]) >= abs(span[1]) else 1
    order = np.argsort(mids[:, ax]); mids = mids[order]; norms = [norms[i] for i in order]
    ts = np.linspace(mids[:, ax].min() + 1, mids[:, ax].max() - 1, n_target)
    parts = []
    for tv in ts:
        j = int(np.argmin(np.abs(mids[:, ax] - tv))); p = mids[j]; n = norms[j]
        out = np.array([n[0], n[1], 0.0]); perp = np.array([-n[1], n[0], 0.0])
        w, proj, h = 1.8, 1.6, 1.5; base = np.array([p[0], p[1], z0]); fo = base + out * proj
        V = [base + perp * w / 2, base - perp * w / 2, fo + perp * w / 2, fo - perp * w / 2,
             fo + perp * w / 2 + [0, 0, h], fo - perp * w / 2 + [0, 0, h],
             base + perp * w / 2 + [0, 0, h + 0.3], base - perp * w / 2 + [0, 0, h + 0.3]]
        F = [(2, 3, 5), (2, 5, 4), (4, 5, 7), (4, 7, 6), (0, 2, 4), (0, 4, 6),
             (1, 5, 3), (1, 7, 5), (0, 1, 3), (0, 3, 2)]
        parts.append(trimesh.Trimesh(vertices=np.array(V, float), faces=np.array(F), process=True))
    return trimesh.util.concatenate(parts)


def chimneys(roof, n_ch):
    V = roof.vertices; top = V[V[:, 2] > V[:, 2].max() - 1.5]
    if not len(top):
        return None
    span = top.max(0) - top.min(0); ax = 0 if abs(span[0]) >= abs(span[1]) else 1
    order = np.argsort(top[:, ax]); top = top[order]
    parts = [box(p[0] - 0.5, p[1] - 0.5, p[2] - 1.0, 1.0, 1.0, 2.6)
             for p in top[np.linspace(0, len(top) - 1, n_ch + 2).astype(int)[1:-1]]]
    return trimesh.util.concatenate(parts)


def newell_normal(P):
    n = np.zeros(3)
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    nn = np.linalg.norm(n)
    return n / nn if nn > 1e-9 else n


def oriented_box(center, u, w, h, n, t):
    """Box aus Mittelpunkt + Achsen u(Breite w), z(Höhe h), n(Tiefe t)."""
    z = np.array([0, 0, 1.0])
    pts = []
    for sx in (-w / 2, w / 2):
        for sy in (-h / 2, h / 2):
            for sz in (-t / 2, t / 2):
                pts.append(center + u * sx + z * sy + n * sz)
    V = np.array(pts)
    F = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
         (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    return trimesh.Trimesh(vertices=V, faces=np.array(F), process=True)


def windows_on_walls(picked, o, front, storey_levels, axis_m, win_w, win_h, min_dot=0.3):
    """AUTO: Fenster-Raster auf ALLE Talseiten-Wandflächen kacheln (Zahl = Länge/Achse)."""
    frames, glass = [], []
    for _, polys in picked:
        for typ, P in polys:
            if typ != "WallSurface":
                continue
            Pl = P - o
            nrm = newell_normal(Pl); nh = nrm[:2]; nn = np.linalg.norm(nh)
            if nn < 1e-6 or abs(nrm[2]) > 0.5 or np.dot(nh / nn, front) < min_dot:
                continue
            nh = nh / nn
            u = np.array([-nh[1], nh[0], 0.0])              # horizontale Richtung in der Wand
            pu = Pl[:, :2] @ u[:2]
            u0, u1 = pu.min(), pu.max()
            zb, zt = Pl[:, 2].min(), Pl[:, 2].max()
            if u1 - u0 < 1.5 or zt - zb < 2.0:
                continue
            anchor = Pl[np.argmin(pu), :2]                  # xy bei u0
            n3 = np.array([nh[0], nh[1], 0.0])
            margin = max(0.8, axis_m * 0.35)
            uu = np.arange(u0 + margin, u1 - margin + 1e-6, axis_m)
            for v in storey_levels:
                if not (zb + 0.9 < v < zt - 0.4):
                    continue
                for uc in uu:
                    cxy = anchor + u[:2] * (uc - u0)
                    c = np.array([cxy[0], cxy[1], v])
                    frames.append(oriented_box(c + n3 * 0.02, u, win_w + 0.2, win_h + 0.2, n3, 0.10))
                    glass.append(oriented_box(c - n3 * 0.05, u, win_w, win_h, n3, 0.06))
    fr = trimesh.util.concatenate(frames) if frames else None
    gl = trimesh.util.concatenate(glass) if glass else None
    return fr, gl


def split_z(mesh, zc):
    V, F = mesh.vertices, mesh.faces
    lo = [f for f in F if V[f][:, 2].mean() < zc]
    hi = [f for f in F if V[f][:, 2].mean() >= zc]
    a = trimesh.Trimesh(V, np.array(lo), process=False) if lo else None
    b = trimesh.Trimesh(V, np.array(hi), process=False) if hi else None
    return a, b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--center", default="", help="E,N statt Name")
    ap.add_argument("--dgm", default=""); ap.add_argument("--dgm-origin", default="")
    ap.add_argument("--front-az", type=float, default=None, help="Talseite-Azimut Grad (sonst auto)")
    ap.add_argument("--socle", type=float, default=3.0)
    ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--balc-levels", type=int, default=2)
    ap.add_argument("--balc-proj", type=float, default=1.3)
    ap.add_argument("--dormer-rows", default="0.30:7,0.62:6", help="frac:n,frac:n (Höhenanteil Trauf→First)")
    ap.add_argument("--chimneys", type=int, default=3)
    ap.add_argument("--raster", default="", help="facade_raster.json (aus foto_fassade_raster.py) → Fenster")
    ap.add_argument("--outdir", required=True); ap.add_argument("--prefix", default="geb")
    a = ap.parse_args()

    center = tuple(float(x) for x in a.center.split(",")) if a.center else None
    picked = L.extract(a.gml, name=a.name or None, center=center, radius=40)
    if not picked:
        sys.exit("kein Gebäude gefunden")
    allpts = np.vstack([P for _, polys in picked for _, P in polys])
    o = np.array([allpts[:, 0].min(), allpts[:, 1].min(), allpts[:, 2].min()])
    ctr_en = allpts[:, :2].mean(0)

    # ---- Talseite (Front) bestimmen ----
    front = None; how = ""
    if a.front_az is not None:
        az = np.radians(a.front_az); front = np.array([np.sin(az), np.cos(az)]); how = f"--front-az {a.front_az}"
    elif a.dgm and a.dgm_origin:
        oe = tuple(float(x) for x in a.dgm_origin.split(","))
        front = front_from_dgm(a.dgm, oe, ctr_en); how = "DGM-Talrichtung (bergab)"
    if front is None:
        front = front_from_footprint(allpts[:, :2] - o, ctr_en - o); how = "Footprint-Heuristik"
    az_deg = (np.degrees(np.arctan2(front[0], front[1]))) % 360
    print(f"Talseite/Front: Azimut {az_deg:.0f}°  ({how})")

    # ---- echte Geometrie ----
    roof = tris_from = L.build_mesh(picked, types={"RoofSurface"}, origin=o)[0]
    walls = L.build_mesh(picked, types={"WallSurface", "ClosureSurface"}, origin=o)[0]
    sockel, wand = split_z(walls, a.socle)

    # ---- Details an echten Front-Flächen ----
    balk = []
    for i in range(a.balc_levels):
        z0 = a.socle + i * a.floor + 0.1
        b = balcony_band(plane_cut_segments(walls, z0, front, 0.25, "wall"), z0, a.balc_proj)
        if b: balk.append(b)
    balkone = trimesh.util.concatenate(balk) if balk else None

    eave = min([m.get("eave_m") for m, _ in picked if m.get("eave_m")] or [a.socle + a.balc_levels * a.floor])
    ridge = max([m.get("ridge_m") for m, _ in picked if m.get("ridge_m")] or [eave + 8])
    rows = []
    for spec in a.dormer_rows.split(","):
        frac, n = spec.split(":"); z0 = eave + float(frac) * (ridge - eave)
        r = dormer_row(roof, z0, int(n), front)
        if r: rows.append(r)
    gauben = trimesh.util.concatenate(rows) if rows else None
    kam = chimneys(roof, a.chimneys)

    # Fenster-Raster aus Foto AUTOMATISCH auf echte Front-Wände kacheln
    fenster = glas = None
    if a.raster:
        import json
        r = json.load(open(a.raster))
        axis_m = r.get("axis_m") or 3.5
        floor_m = r.get("floor_m") or a.floor
        ww, wh = r.get("win_w", 1.1), r.get("win_h", 1.4)
        levels = [a.socle * 0.5 + 0.9] + [a.socle + i * a.floor + a.floor * 0.5
                                          for i in range(a.balc_levels)]
        fenster, glas = windows_on_walls(picked, o, front, levels, axis_m, ww, wh)
        nwin = 0 if glas is None else len(glas.faces) // 12
        print(f"Fenster automatisch gekachelt: {nwin} Stück (Achse {axis_m} m, {ww}×{wh} m)")

    os.makedirs(a.outdir, exist_ok=True)
    out = {"sockel": sockel, "wand": wand, "dach": roof,
           "balkone": balkone, "gauben": gauben, "kamine": kam,
           "fensterrahmen": fenster, "glas": glas}
    tot = []
    for nm, m in out.items():
        if m is None or len(m.faces) == 0:
            print(f"  (leer: {nm})"); continue
        m.export(f"{a.outdir}/{a.prefix}_{nm}.stl"); tot.append(m); print(f"  {a.prefix}_{nm}: {len(m.faces)} F")
    full = trimesh.util.concatenate(tot); full.export(f"{a.outdir}/{a.prefix}_detail.stl")
    ext = full.bounds[1] - full.bounds[0]
    print(f"\nECHTE Geometrie + Detail: {len(full.faces)} F  {ext[0]:.1f}×{ext[1]:.1f}×{ext[2]:.1f} m  "
          f"(Trauf {eave:.1f} First {ridge:.1f})")
    print(f"-> {a.outdir}/{a.prefix}_detail.stl")


if __name__ == "__main__":
    main()
