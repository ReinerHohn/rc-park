#!/usr/bin/env python3
"""openbuildings_fallback.py — HEBEL 5: Weltklasse-Fallback-Geometrie, wenn weder
Google 3D Tiles (Hebel 1) noch lokales LOD2 (Hebel 3) ein Mesh liefern.

Quellen (KI-vorberechnete Gebäude-Grundgerüste, global):
  • Google Open Buildings 2.5D   — Footprint-Polygon + geschätzte Höhe
  • GlobalBuildingAtlas (TUM)     — globales LoD1 (Footprint + Höhe), weltweit lückenlos

Beide liefern 2.5D (Grundriss + eine Höhe) — kein Dachdetail. Dieses Modul
extrudiert Footprint × Höhe zu einem soliden, wasserdichten LoD1-Block als
Mesh-ERSATZ. Dach/Fassade kommen danach aus Hebel 2/6/7 (Street-View-Relief).

Datenbezug (die Tiles sind groß → lokal bereitstellen, nicht live je Gebäude):
  Open Buildings:  gs://open-buildings-data/v3/  (CSV/Parquet je S2-Zelle)
  GBA:             TUM-Portal → GeoPackage/Parquet-Kachel der Region
Dieses Tool liest eine lokale Footprint-Datei (GeoJSON/Parquet) ODER ein bereits
ausgeschnittenes Polygon und extrudiert. --fetch-Hinweis gibt die Bezugs-URL aus.

  python3 tools/openbuildings_fallback.py --lat 47.9956 --lon 7.8522 \
      --footprints daten/freiburg/open_buildings.geojson --out modelle/x/ob.obj
"""
import argparse, sys, os, json, math
import numpy as np


def nearest_footprint(features, lat, lon):
    """aus GeoJSON-FeatureCollection das Polygon, dessen Zentroid (lat,lon) am
    nächsten liegt (grobe ebene Distanz reicht lokal)."""
    best, bd = None, 1e18
    for ft in features:
        geom = ft.get("geometry", {})
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        rings = geom["coordinates"] if geom["type"] == "Polygon" else geom["coordinates"][0]
        pts = np.array(rings[0], float)                 # [lon,lat] äußerer Ring
        c = pts.mean(0)
        d = (c[1]-lat)**2 + ((c[0]-lon)*math.cos(math.radians(lat)))**2
        if d < bd:
            bd, best = d, (pts, ft.get("properties", {}))
    return best


def extrude(pts_lonlat, lat0, lon0, height_m):
    """Footprint (lon,lat-Ring) → lokales ENU-Meter-Prisma, wasserdicht."""
    import trimesh
    from shapely.geometry import Polygon
    R = 6378137.0
    xs = (pts_lonlat[:, 0] - lon0) * math.radians(1) * R * math.cos(math.radians(lat0))
    ys = (pts_lonlat[:, 1] - lat0) * math.radians(1) * R
    poly = Polygon(np.column_stack([xs, ys]))
    if not poly.is_valid:
        poly = poly.buffer(0)
    mesh = trimesh.creation.extrude_polygon(poly, height=height_m)
    return mesh


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--footprints", help="lokale GeoJSON der Region (Open Buildings / GBA)")
    p.add_argument("--height", type=float, help="Höhe [m] erzwingen (sonst aus Property)")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    if not a.footprints or not os.path.exists(a.footprints):
        print("Keine lokale Footprint-Datei. Bezug:")
        print("  Open Buildings: https://sites.research.google/open-buildings/  (S2-Zelle der Region)")
        print("  GlobalBuildingAtlas: https://globalbuildingatlas.tum.de/  (LoD1-Kachel)")
        print("  → als GeoJSON ausschneiden und mit --footprints übergeben.")
        sys.exit("Fallback-Daten fehlen.")

    fc = json.load(open(a.footprints))
    feats = fc["features"] if "features" in fc else fc
    found = nearest_footprint(feats, a.lat, a.lon)
    if not found:
        sys.exit("Kein Polygon in der Nähe gefunden.")
    pts, props = found
    h = a.height or float(props.get("height") or props.get("mean_height") or 12.0)
    print(f"Footprint {len(pts)} Punkte, Höhe {h:.1f} m (Quelle: {list(props)[:4]})")
    mesh = extrude(pts, a.lat, a.lon, h)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    mesh.export(a.out)
    e = mesh.extents
    print(f"LoD1-Block: {len(mesh.faces)} faces, {e[0]:.0f}×{e[1]:.0f}×{e[2]:.0f} m → {a.out}")
    print("Dach/Fassade kommen aus Hebel 2/6/7 (Street-View-Relief).")


if __name__ == "__main__":
    main()
