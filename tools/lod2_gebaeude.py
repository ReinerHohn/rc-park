#!/usr/bin/env python3
"""lod2_gebaeude.py — GENERISCH: ein (oder mehrere) Gebäude aus LGL-LOD2-CityGML
als echtes 3D-Mesh extrahieren. Das ist das GROBE GERÜST (Massenmodell) der
Vermesser-Pipeline: amtlicher Grundriss + echte Höhen + Dachform, maßstabstreu.

Methode (robust, kein voll-CityGML-Parser nötig):
  Gebäude am <gml:name> ODER am nächsten zu einer UTM-Koordinate finden
  → alle <gml:posList> der Wand-/Dach-/Bodenflächen (inkl. BuildingParts) lesen
  → jede Fläche Fan-triangulieren → trimesh. Lokaler Ursprung = Footprint-min,
  damit das Modell bei 0 liegt; UTM-Origin + Grund-z bleiben als Metadaten
  (für Georeferenz / Platzierung in der Szene).

  python3 tools/lod2_gebaeude.py \
      --gml daten/ravenna/lod2/.../LoD2_32_430_5307_1_BW.gml \
      --name "Hofgut Sternen" \
      --stl modelle/hofgut_sternen/hofgut_lod2.stl \
      --info modelle/hofgut_sternen/hofgut_lod2.json
"""
import argparse, json, os, re, sys
import numpy as np
import trimesh

NS_POS = re.compile(r'<gml:posList[^>]*>([^<]+)</gml:posList>')
NS_BLD = re.compile(r'(?=<bldg:Building gml:id=)')
SURF = re.compile(r'<bldg:(WallSurface|RoofSurface|GroundSurface|ClosureSurface)\b')


def _floats(txt):
    return np.array([float(x) for x in txt.split()], float)


def polygons_from_chunk(chunk):
    """alle Ring-Polygone (als (N,3)-Arrays) mit Flächentyp aus einem Building-Chunk.
    Rückgabe: Liste (typ, P). Typ aus der umschließenden bldg:*Surface."""
    polys = []
    # alle *Surface-Blöcke mit Typ durchgehen; posLists darin erben den Typ
    for ms in re.finditer(r'<bldg:(WallSurface|RoofSurface|GroundSurface|ClosureSurface)\b.*?</bldg:\1>',
                          chunk, re.S):
        typ = ms.group(1)
        for m in NS_POS.finditer(ms.group(0)):
            v = _floats(m.group(1))
            if len(v) < 9 or len(v) % 3:
                continue
            P = v.reshape(-1, 3)
            if len(P) >= 4 and np.allclose(P[0], P[-1]):
                P = P[:-1]
            if len(P) >= 3:
                polys.append((typ, P))
    return polys


def planar_triangulate(P):
    """robuste Triangulierung eines ebenen 3D-Polygons: auf Best-Fit-Ebene projizieren,
    2D ear-clipping (mapbox_earcut), Indizes zurück auf die 3D-Punkte."""
    import mapbox_earcut as ec
    C = P.mean(0)
    Q = P - C
    _, _, Vt = np.linalg.svd(Q, full_matrices=False)
    u, v = Vt[0], Vt[1]
    xy = np.c_[Q @ u, Q @ v].astype(np.float64)
    try:
        idx = ec.triangulate_float64(xy, np.array([len(xy)], np.uint32))
    except Exception:
        return [(0, i, i + 1) for i in range(1, len(P) - 1)]  # Fallback Fächer
    return [tuple(idx[i:i + 3]) for i in range(0, len(idx), 3)]


def building_chunks(gml_text):
    chunks = NS_BLD.split(gml_text)
    return [c for c in chunks if c.startswith('<bldg:Building gml:id=')]


def chunk_meta(chunk):
    gid = re.search(r'gml:id="([^"]+)"', chunk)
    nm = re.search(r'<gml:name>([^<]+)</gml:name>', chunk)
    h = re.findall(r'<bldg:measuredHeight[^>]*>([\d.]+)', chunk)
    rt = re.findall(r'<bldg:roofType[^>]*>(\d+)', chunk)
    return dict(id=gid.group(1) if gid else "?",
                name=nm.group(1) if nm else None,
                heights=[float(x) for x in h],
                rooftypes=rt)


ROOFNAMES = {"1000": "Flachdach", "2100": "Pultdach", "3100": "Satteldach",
             "3200": "Walmdach", "3300": "Kruewalm", "3500": "Zeltdach",
             "5000": "Sheddach", "9999": "sonstige"}


def extract(gml_path, name=None, center=None, radius=40.0):
    s = open(gml_path, encoding="utf-8", errors="replace").read()
    chunks = building_chunks(s)
    picked = []
    for c in chunks:
        meta = chunk_meta(c)
        polys = polygons_from_chunk(c)
        if not polys:
            continue
        allpts = np.vstack([P for _, P in polys])
        ctr = allpts[:, :2].mean(0)
        meta["center_utm"] = ctr.tolist()
        # Traufe = tiefster Punkt der Dachflächen; First = höchster
        roof = [P for t, P in polys if t == "RoofSurface"]
        grnd = [P for t, P in polys if t == "GroundSurface"]
        gz = np.vstack(grnd)[:, 2].min() if grnd else allpts[:, 2].min()
        if roof:
            rz = np.vstack(roof)[:, 2]
            meta["eave_m"] = float(rz.min() - gz)
            meta["ridge_m"] = float(rz.max() - gz)
        meta["ground_z"] = float(gz)
        # Grundriss: Kantenlängen der GroundSurface -> Front-Breite (kurze Seite) + Tiefe (lange)
        if grnd:
            xy = np.vstack(grnd)[:, :2]
            ring = xy[:len(grnd[0])] if len(grnd) == 1 else xy
            d = np.linalg.norm(np.diff(np.vstack([ring, ring[:1]]), axis=0), axis=1)
            d = sorted([float(x) for x in d if x > 0.5], reverse=True)
            if len(d) >= 2:
                meta["footprint_edges_m"] = [round(x, 2) for x in d]
                meta["depth_m"] = round(d[0], 2)          # lange Seite = Parzellentiefe
                meta["front_w_m"] = round(d[-1], 2)       # kurze Seite = giebelständige Front
        if name and meta["name"] and name.lower() in meta["name"].lower():
            picked.append((meta, polys))
        elif center is not None and np.hypot(*(ctr - np.array(center))) <= radius:
            picked.append((meta, polys))
    return picked


def build_mesh(picked, types=None, origin=None):
    """gewählte Flächentypen → ein trimesh, lokaler Ursprung. types=None → alle.
    origin: gemeinsamer Ursprung über mehrere Aufrufe (sonst verrutschen Teil-Meshes!)."""
    allpts = np.vstack([P for _, polys in picked for _, P in polys])
    o = np.array([allpts[:, 0].min(), allpts[:, 1].min(), allpts[:, 2].min()]) if origin is None else np.asarray(origin)
    V, F = [], []
    for _, polys in picked:
        for typ, P in polys:
            if types and typ not in types:
                continue
            Pl = P - o
            base = len(V)
            V.extend(Pl.tolist())
            for tri in planar_triangulate(Pl):
                F.append((base + tri[0], base + tri[1], base + tri[2]))
    mesh = trimesh.Trimesh(vertices=np.array(V), faces=np.array(F), process=True)
    return mesh, o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gml", required=True)
    ap.add_argument("--name", default="")
    ap.add_argument("--center", default="", help="E,N UTM — statt Name")
    ap.add_argument("--radius", type=float, default=40.0)
    ap.add_argument("--stl", required=True)
    ap.add_argument("--info", default="")
    a = ap.parse_args()

    center = tuple(float(x) for x in a.center.split(",")) if a.center else None
    picked = extract(a.gml, name=a.name or None, center=center, radius=a.radius)
    if not picked:
        sys.exit("kein Gebäude gefunden (Name/Koordinate prüfen)")

    print(f"Gebäude gefunden: {len(picked)}")
    for meta, polys in picked:
        rts = "/".join(ROOFNAMES.get(r, r) for r in meta["rooftypes"][:6])
        eave = meta.get("eave_m"); ridge = meta.get("ridge_m")
        ev = f"Trauf {eave:.1f} First {ridge:.1f}m" if eave else ""
        print(f"  {meta['id']}  {meta['name'] or '(ohne Name)'}  "
              f"Teile={len(meta['heights'])}  Hmax={max(meta['heights']) if meta['heights'] else 0:.1f}m  "
              f"{ev}  Dach={rts}  Flächen={len(polys)}")

    mesh, origin = build_mesh(picked)
    ext = mesh.bounds[1] - mesh.bounds[0]
    print(f"\nMesh: {len(mesh.vertices)} V / {len(mesh.faces)} F   "
          f"BBox L×B×H = {ext[0]:.1f} × {ext[1]:.1f} × {ext[2]:.1f} m   "
          f"watertight={mesh.is_watertight}  euler={mesh.euler_number}")

    os.makedirs(os.path.dirname(a.stl), exist_ok=True)
    mesh.export(a.stl)
    print(f"-> {a.stl}")

    if a.info:
        info = {
            "bauwerk": a.name or "LOD2-Gebäude",
            "quelle": os.path.basename(a.gml),
            "utm_origin": origin.tolist(),
            "epsg": "25832 (UTM32N)",
            "bbox_lbh_m": [float(ext[0]), float(ext[1]), float(ext[2])],
            "grund_z_m_nn": float(origin[2]),
            "gebaeude": [
                {"id": m["id"], "name": m["name"], "teile": len(m["heights"]),
                 "hoehen_m": m["heights"], "dachtypen": m["rooftypes"],
                 "eave_m": m.get("eave_m"), "ridge_m": m.get("ridge_m"),
                 "front_w_m": m.get("front_w_m"), "depth_m": m.get("depth_m"),
                 "footprint_edges_m": m.get("footprint_edges_m"),
                 "center_utm": m["center_utm"]}
                for m, _ in picked],
        }
        json.dump(info, open(a.info, "w"), indent=2, ensure_ascii=False)
        print(f"-> {a.info}")


if __name__ == "__main__":
    main()
