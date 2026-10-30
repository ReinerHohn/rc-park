#!/usr/bin/env python3
"""pointcloud_overhang.py — ÜBERHÄNGENDE man-made Strukturen (Tunnelausgang-Überdachung/Galerie,
Brücke, Vordach) aus der rohen LiDAR-PUNKTWOLKE (LAS/LAZ) erfassen — das, was 2.5D-Raster
(DGM/DOM/nDOM) PRINZIPIELL nicht können (eine Höhe pro XY-Zelle; ein Dach über Hohlraum ist nicht
darstellbar; Jochem et al. 2009, Sensors).

Zwei Wege (der erste ist robust, der zweite der Fallback):
  A) KLASSIFIKATION — LGL-BW ALS-Daten sind von Profis vorklassifiziert: Klasse 17=Brücke, 6=Gebäude.
     Überhang = diese Klassen direkt extrahieren. KEIN fragiles Raten.
  B) GEOMETRISCH (für unklassifizierte Überhänge) — vertikaler HOHLRAUM pro XY-Zelle (Punkte mit
     >GAP m leerem Raum darunter) UND lokale PLANARITÄT (Open3D-Kovarianz-Eigenwerte: scatter=l2/l0
     klein = ebene Fläche) -> trennt Dach/Deck von Vegetation (Vegetation ist gestreut, nicht eben).
     ⚠️ Grenze: ein SOLIDES Deck verdeckt den Boden darunter -> dann fehlt der Hohlraum-Nachweis
     (Occlusion); dafür ist Weg A oder Deep-Learning-Segmentierung (KPConv/RandLA-Net) nötig.

Rekonstruktion: Open3D Alpha-Shape (create_from_point_cloud_alpha_shape, EIN alpha) -> Mesh, das als
Überhang-Teil (Dach + Wände) in die Egg-Crate-Rippen integriert werden kann.

Datenquelle BW: LGL Open GeoData, ALS_2/ALS_3 (LAZ, >=8 Pkt/m², 5-7 Klassen inkl. Brücke/Gebäude).
  - Freie TESTDATEN: lgl-bw.de/downloads/Produkte/Testdaten/Galerien/Dokumente/TD_Laserscandaten_LAZ.zip
  - Echte Kachel: E-Mail-Bestellung geodaten@lgl.bwl.de (Open-Data-Lizenz, aber Bearbeitungsgebühr min. 60€).

  python3 tools/pointcloud_overhang.py --laz datei.laz [--class 17] [--gap 2.0] [--out modelle/overhang]
"""
import argparse, os, sys, numpy as np


def read_laz(path):
    import laspy
    las = laspy.read(path)
    return (np.asarray(las.x), np.asarray(las.y), np.asarray(las.z),
            np.asarray(las.classification), np.asarray(las.number_of_returns))


def overhang_by_class(cls, classes=(17, 6)):
    """Weg A: Überhang = vorklassifizierte Brücke(17)/Gebäude(6)-Punkte."""
    m = np.zeros(len(cls), bool)
    for c in classes:
        m |= (cls == c)
    return m


def overhang_geometric(x, y, z, cell=0.5, gap=2.0, scatter_max=0.06, knn=16):
    """Weg B: vertikaler Hohlraum pro XY-Zelle UND lokal planar (Vegetation raus)."""
    import open3d as o3d
    n = len(x)
    ix = ((x - x.min()) / cell).astype(np.int64); iy = ((y - y.min()) / cell).astype(np.int64)
    key = ix * 100000 + iy
    order = np.lexsort((z, key)); ks = key[order]; zs = z[order]
    same = np.r_[False, ks[1:] == ks[:-1]]
    gb = np.zeros(n, bool); gb[1:] = same[1:] & ((zs[1:] - zs[:-1]) > gap)   # Hohlraum unter dem Punkt
    cs = np.cumsum(gb.astype(int)); cc = ~same
    start = np.maximum.accumulate(np.where(cc, np.arange(n), 0))
    void = np.zeros(n, bool); void[order] = (cs - cs[start]) > 0
    # Planarität via Kovarianz-Eigenwerte
    pcd = o3d.geometry.PointCloud(); pcd.points = o3d.utility.Vector3dVector(np.column_stack([x, y, z]))
    pcd.estimate_covariances(o3d.geometry.KDTreeSearchParamKNN(knn=knn))
    ev = np.linalg.eigvalsh(np.asarray(pcd.covariances))           # l2<=l1<=l0
    scatter = ev[:, 0] / ev[:, 2].clip(1e-9)
    return void & (scatter < scatter_max)


def alpha_mesh(pts, alphas=(1.5, 2.5, 4.0)):
    import open3d as o3d
    pcd = o3d.geometry.PointCloud(); pcd.points = o3d.utility.Vector3dVector(pts - pts.mean(0))
    best = None
    for a in alphas:
        try:
            m = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd, a)
            if len(m.triangles) > 50:
                return m, a
            best = (m, a)
        except Exception:
            continue
    return best if best else (None, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--laz", required=True)
    ap.add_argument("--mode", choices=["class", "geom"], default="class")
    ap.add_argument("--classes", type=int, nargs="+", default=[17, 6])
    ap.add_argument("--gap", type=float, default=2.0)
    ap.add_argument("--out", default="modelle/overhang")
    a = ap.parse_args()
    x, y, z, cls, nret = read_laz(a.laz)
    print(f"Punktwolke: {len(x)} Punkte, Klassen {sorted(set(cls.tolist()))}")
    m = (overhang_by_class(cls, tuple(a.classes)) if a.mode == "class"
         else overhang_geometric(x, y, z, gap=a.gap))
    print(f"Überhang-Punkte ({a.mode}): {int(m.sum())}")
    if m.sum() < 10:
        print("Zu wenige Überhang-Punkte — andere Klasse/Parameter oder Kachel ohne Überhang.")
        return
    pts = np.column_stack([x[m], y[m], z[m]])
    mesh, alpha = alpha_mesh(pts)
    os.makedirs(a.out, exist_ok=True)
    if mesh is not None:
        import open3d as o3d
        o3d.io.write_triangle_mesh(f"{a.out}/overhang.ply", mesh)
        print(f"Überhang-Mesh (alpha={alpha}): {len(mesh.triangles)} Dreiecke -> {a.out}/overhang.ply")
    np.save(f"{a.out}/overhang_points.npy", pts)
    print(f"-> {a.out}/overhang_points.npy")


if __name__ == "__main__":
    main()
