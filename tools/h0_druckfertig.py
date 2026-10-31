#!/usr/bin/env python3
"""h0_druckfertig.py — beliebiges Mesh (Scan, LOD2-Bau, Generator-GLB) -> druckfertiges Modell fuer H0 (1:87).

Nur Struktur, keine Textur. Schritte:
  1. laden (GLB/STL/PLY/OBJ), alle Teile zu einem Mesh
  2. optional auf Quader zuschneiden (--crop xmin xmax ymin ymax zmin zmax, Mesh-Koordinaten)
  3. Massstab: --hoehe-m = echte Hoehe des Objekts (aus LOD2/Plan); sonst wird 1 Einheit = 1 m angenommen
  4. aufraeumen: Kleinteile/Schwebeteile weg (--min-anteil), Normalen, Loecher
  5. optional --solid VOXEL_MM: Voxel-Remesh (macht offene Scans wasserdicht, glaettet, entfernt Feinstteile)
  6. Druckbarkeit pruefen (wasserdicht, Wandstaerke, Bauraum) und STL in mm schreiben
Nutzung:
  h0_druckfertig.py eingabe.glb ausgabe.stl --hoehe-m 45.9 [--up z] [--massstab 87] [--solid 0.25]
                    [--min-wand 0.8] [--crop ...] [--bauraum 220 220 250]
Z zeigt nach oben (--up y bei COLMAP-Koordinaten, dann wird gedreht).
"""
import argparse, json, sys
import numpy as np
import trimesh


def lade(pfad):
    s = trimesh.load(pfad, force="scene") if pfad.lower().endswith((".glb", ".gltf")) else trimesh.load(pfad)
    return s.to_geometry() if isinstance(s, trimesh.Scene) else s


def aufraeumen(m, min_anteil):
    m.merge_vertices()
    m.update_faces(m.nondegenerate_faces())
    m.update_faces(m.unique_faces())
    m.remove_unreferenced_vertices()
    teile = m.split(only_watertight=False)
    if len(teile) > 1:
        gross = max(t.area for t in teile)
        teile = [t for t in teile if t.area >= min_anteil * gross]
        m = trimesh.util.concatenate(teile)
    return m


def _meshfix(m):
    import pymeshfix
    f = pymeshfix.MeshFix(m.vertices.copy(), m.faces.copy())
    f.repair()
    v_, f_ = (f.points, f.faces) if hasattr(f, 'points') else (f.v, f.f)
    return trimesh.Trimesh(v_, f_, process=True)


def wasserdicht(m):
    """Wasserdicht machen, ohne Bauteile zu verlieren.
    Frueher: pymeshfix auf das ganze Mesh -> behaelt nur die GROESSTE Komponente (Hofgut: 128 864 Flaechen -> 20 Flaechen, still).
    Jetzt: jede Komponente einzeln reparieren und wieder zusammensetzen."""
    if m.is_watertight:
        trimesh.repair.fix_normals(m)
        return m
    teile = []
    for t in m.split(only_watertight=False):
        if not t.is_watertight:
            try:
                t = _meshfix(t)
            except Exception:
                pass
        if len(t.faces):
            teile.append(t)
    r = trimesh.util.concatenate(teile) if len(teile) > 1 else teile[0]
    trimesh.repair.fix_normals(r)
    return r


def voxel_solid(m, pitch):
    """Offene/rauhe Flaeche -> massiver Koerper: voxeln, innen fuellen, kleine Spitzen/Rauschen schliessen."""
    from scipy import ndimage
    try:
        v = m.voxelized(pitch).fill()
        mat, transform = v.matrix, v.transform
    except (ValueError, MemoryError):
        # trimesh.voxelized scheitert bei sehr grossen/duennen Dreiecken ("max_iter exceeded"):
        # Ausweg ueber dicht abgetastete Oberflaechenpunkte, dann Hohlraeume fuellen
        n = int(min(8e6, max(2e5, m.area / (pitch * pitch) * 6)))
        pts, _ = trimesh.sample.sample_surface(m, n)
        lo = pts.min(0) - 2 * pitch
        idx = np.floor((pts - lo) / pitch).astype(int)
        mat = np.zeros(idx.max(0) + 3, bool)
        mat[idx[:, 0], idx[:, 1], idx[:, 2]] = True
        mat = ndimage.binary_closing(mat, iterations=2)
        mat = ndimage.binary_fill_holes(mat)
        transform = np.eye(4); transform[:3, :3] *= pitch; transform[:3, 3] = lo
        class _V: pass
        v = _V(); v.transform = transform
    a = ndimage.binary_closing(mat, iterations=1)
    a = ndimage.binary_opening(a, iterations=1)
    lab, n = ndimage.label(a)
    if n > 1:
        gr = np.bincount(lab.ravel())[1:]
        a = lab == (1 + gr.argmax())
    vox = trimesh.voxel.VoxelGrid(trimesh.voxel.encoding.DenseEncoding(a), transform=v.transform)
    r = vox.marching_cubes
    # trimesh liefert hier Voxel-Indizes (ohne Pitch/Ursprung) -> in mm zurueckrechnen, sonst Massstab falsch (Faktor 1/pitch)
    r.apply_transform(v.transform)
    return trimesh.smoothing.filter_taubin(r, iterations=10) or r


def in_scheiben(m, hmax):
    """Waagerecht in gleich hohe, wasserdichte Scheiben (Boolean mit Quader) - jede passt in den Bauraum."""
    n = int(np.ceil(m.extents[2] / hmax)); dz = m.extents[2] / n
    out = []
    for i in range(n):
        box = trimesh.creation.box(extents=[m.extents[0] * 2, m.extents[1] * 2, dz],
                                   transform=trimesh.transformations.translation_matrix([0, 0, i * dz + dz / 2]))
        out.append(trimesh.boolean.intersection([m, box], engine="manifold"))
    return out


def in_stuecke(m, bauraum):
    """In Quader-Stuecke schneiden, die in den Bauraum passen (alle drei Achsen). Liefert [(index, mesh)]."""
    n = [max(1, int(np.ceil(m.extents[i] / bauraum[i]))) for i in range(3)]
    d = [m.extents[i] / n[i] for i in range(3)]
    o = m.bounds[0]
    out = []
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                c = o + (np.array([i, j, k]) + 0.5) * d
                box = trimesh.creation.box(extents=np.array(d), transform=trimesh.transformations.translation_matrix(c))
                t = trimesh.boolean.intersection([m, box], engine="manifold")
                if len(t.faces):
                    t.vertices -= t.bounds[0]
                    out.append(((i + 1, j + 1, k + 1), t))
    return out


def wandstaerke(m, n=4000, seed=0):
    """Lokale Wandstaerke: Strahl von der Oberflaeche nach innen bis zur Gegenseite."""
    rng = np.random.default_rng(seed)
    pts, fid = trimesh.sample.sample_surface(m, n, seed=seed)
    nrm = m.face_normals[fid]
    org = pts - nrm * 1e-4
    ort, ray, _ = m.ray.intersects_location(org, -nrm, multiple_hits=False)
    d = np.full(n, np.nan)
    d[ray] = np.linalg.norm(ort - org[ray], axis=1)
    return d[~np.isnan(d)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("eingabe"); ap.add_argument("ausgabe")
    ap.add_argument("--hoehe-m", type=float, help="echte Objekthoehe in Metern (setzt den Massstab des Scans)")
    ap.add_argument("--massstab", type=float, default=87.0, help="1:N (H0 = 87)")
    ap.add_argument("--up", choices="xyz", default="z", help="Achse, die nach oben zeigt")
    ap.add_argument("--up-negativ", action="store_true", help="Achse zeigt nach unten (COLMAP: y nach unten)")
    ap.add_argument("--crop", type=float, nargs=6, metavar=("XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"))
    ap.add_argument("--min-anteil", type=float, default=0.0, help="Teile kleiner als dieser Anteil der groessten Flaeche fliegen raus (Scans: 0.02; gebaute Modelle: 0 = nichts loeschen)")
    ap.add_argument("--teilen", action="store_true", help="in waagerechte Scheiben schneiden, die in den Bauraum passen (je Scheibe eine STL)")
    ap.add_argument("--solid", type=float, metavar="VOXEL_MM", help="Voxel-Remesh in mm (macht Scans massiv und wasserdicht)")
    ap.add_argument("--min-wand", type=float, default=0.8, help="kleinste druckbare Wand in mm (FDM 0.8, Resin 0.4)")
    ap.add_argument("--bauraum", type=float, nargs=3, default=[220, 220, 250], metavar=("X", "Y", "Z"))
    a = ap.parse_args()

    m = lade(a.eingabe)
    print(f"geladen: {len(m.faces)} Flaechen, wasserdicht={m.is_watertight}")
    if a.crop:
        c = np.array(a.crop).reshape(3, 2)
        faces_ok = ((m.vertices[m.faces] >= c[:, 0]) & (m.vertices[m.faces] <= c[:, 1])).all(axis=(1, 2))
        m.update_faces(faces_ok); m.remove_unreferenced_vertices()
        print(f"Zuschnitt: {len(m.faces)} Flaechen")
    # Achsen: oben -> Z
    perm = {"x": [1, 2, 0], "y": [0, 2, 1], "z": [0, 1, 2]}[a.up]
    m.vertices = m.vertices[:, perm]
    if a.up_negativ:
        m.vertices[:, 2] *= -1
    m = aufraeumen(m, a.min_anteil)
    m.vertices -= [(m.bounds[0, 0] + m.bounds[1, 0]) / 2, (m.bounds[0, 1] + m.bounds[1, 1]) / 2, m.bounds[0, 2]]
    # Massstab: Modelleinheiten -> echte Meter -> mm im Massstab 1:N
    meter = (a.hoehe_m / m.extents[2]) if a.hoehe_m else 1.0
    m.vertices *= meter * 1000.0 / a.massstab
    if a.solid:
        m = voxel_solid(m, a.solid)
    m_vor = m
    m = wasserdicht(aufraeumen(m, 0.0))
    # Schutz: die Reparatur darf das Modell nicht verkleinern (Teile verloren) - sonst Abbruch statt stiller Falschmeldung
    if not a.solid and (np.abs(m.extents - m_vor.extents) > 0.02 * np.maximum(m_vor.extents, 1e-9)).any():
        sys.exit("FEHLER: Reparatur hat Teile entfernt (Ausdehnung %s -> %s mm). Mit --solid VOXEL_MM neu versuchen." % (m_vor.extents.round(1), m.extents.round(1)))
    d = wandstaerke(m)
    ex = m.extents
    bericht = {
        "flaechen": int(len(m.faces)), "wasserdicht": bool(m.is_watertight),
        "volumen_mm3": round(float(m.volume), 1) if m.is_watertight else None,
        "ausdehnung_mm": [round(float(x), 1) for x in ex],
        "passt_in_bauraum": bool((ex <= np.array(a.bauraum)).all()),
        "wand_p5_mm": round(float(np.percentile(d, 5)), 2) if len(d) else None,
        "wand_median_mm": round(float(np.median(d)), 2) if len(d) else None,
        "anteil_zu_duenn": round(float((d < a.min_wand).mean()), 3) if len(d) else None,
        "massstab": f"1:{a.massstab:g}", "min_wand_mm": a.min_wand,
    }
    m.export(a.ausgabe)
    if a.teilen and not bericht["passt_in_bauraum"]:
        bericht["teile"] = []
        for (i, j, k), t in in_stuecke(m, a.bauraum):
            t.export(a.ausgabe.rsplit(".", 1)[0] + f"_teil_{i}{j}{k}.stl")
            bericht["teile"].append({"nr": f"{i}{j}{k}", "mm": [round(float(x), 1) for x in t.extents], "wasserdicht": bool(t.is_watertight)})
        bericht["passt_in_bauraum"] = all(max(np.array(t["mm"]) - np.array(a.bauraum)) <= 0.5 for t in bericht["teile"])
    json.dump(bericht, open(a.ausgabe.rsplit(".", 1)[0] + ".bericht.json", "w"), indent=1)
    print(json.dumps(bericht, indent=1, ensure_ascii=False))
    if not bericht["wasserdicht"] or not bericht["passt_in_bauraum"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
