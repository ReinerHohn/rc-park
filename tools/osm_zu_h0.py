#!/usr/bin/env python3
"""osm_zu_h0.py — beliebiges Bauwerk aus OpenStreetMap-3D-Daten -> wasserdichter Baukoerper (STL, mm, Massstab 1:N, Standard H0 = 1:87).

Datenquelle: OSM (c) OpenStreetMap-Mitwirkende, ODbL. Je Bauteil (building:part, sonst das building selbst) werden
Grundriss, height/min_height, roof:shape und roof:height verwendet. Fehlende Angaben werden GESCHAETZT und im
Bericht ausgewiesen (nichts wird stillschweigend erfunden).
Dachformen: flat, gabled, hipped/pyramidal (alle anderen -> flach, im Bericht vermerkt).

Nutzung:
  osm_zu_h0.py --way 1105286648 ausgabe.stl                      # ein bestimmtes OSM-Gebaeude (+ seine building:part)
  osm_zu_h0.py --name "Martinstor" --lat 47.9954 --lon 7.8548 --radius 60 ausgabe.stl
Optionen: --massstab 87  --bauraum X Y Z  --teilen
"""
import argparse, json, math, os, sys, time, urllib.parse, urllib.request
import numpy as np
import trimesh
from shapely.geometry import Polygon

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h0_druckfertig as druck


def overpass(q):
    for i in range(6):
        url = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")[i % 2]
        req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "rc-park/osm_zu_h0"})
        try:
            return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception as ex:
            print("Overpass:", ex, "- nochmal"); time.sleep(5)
    sys.exit("Overpass nicht erreichbar")


def zahl(v, d=None):
    try:
        return float(str(v).split()[0].replace(",", "."))
    except Exception:
        return d


def dach_koerper(poly, z0, zw, z1, form, rh):
    """Wand (z0..zw) + Dach (zw..z1) als ein wasserdichter Koerper aus Boolean mit Dachprismen."""
    wand = trimesh.creation.extrude_polygon(poly, z1 - z0); wand.apply_translation([0, 0, z0])
    if form not in ("gabled", "hipped", "pyramidal", "half-hipped", "gambrel", "mansard") or rh <= 0.01:
        return wand
    rect = poly.minimum_rotated_rectangle
    c = np.array(rect.exterior.coords)[:4]
    e1, e2 = c[1] - c[0], c[2] - c[1]
    lang, kurz = (e1, e2) if np.linalg.norm(e1) >= np.linalg.norm(e2) else (e2, e1)
    L, W = np.linalg.norm(lang), np.linalg.norm(kurz)
    mitte = c.mean(0); ang = math.atan2(lang[1], lang[0])
    lh, wh = L / 2 + 1e-3, W / 2 + 1e-3
    T = trimesh.transformations.translation_matrix([*mitte, 0]) @ trimesh.transformations.rotation_matrix(ang, [0, 0, 1])

    def prisma(querschnitt, laenge):                      # Querschnitt in (y,z), Laenge entlang x
        pr = trimesh.creation.extrude_polygon(Polygon(querschnitt), laenge)
        pr.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]) @ np.eye(4))
        return pr
    # Giebelprisma: Querschnitt (y,z) mit Walm-/Giebel-Steigung, entlang der Firstrichtung x
    q_giebel = [(-wh, z0 - 1), (wh, z0 - 1), (wh, zw), (0, z1), (-wh, zw)]
    g = trimesh.creation.extrude_polygon(Polygon([(y, z) for y, z in q_giebel]), 2 * lh + 2)
    # extrude_polygon extrudiert entlang z -> in x-Richtung drehen: (x,y,z)->(z,x,y)
    R = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1.0]])
    g.apply_transform(R); g.apply_translation([-lh - 1, 0, 0]); g.apply_transform(T)
    teile = [wand, g]
    if form in ("hipped", "pyramidal", "half-hipped"):    # Walm: zweites Prisma quer, gleiche Steigung
        s = rh / wh
        ls = max(lh - wh, 0.0)
        q2 = [(-lh, z0 - 1), (lh, z0 - 1), (lh, zw), (ls, z1), (-ls, z1), (-lh, zw)]
        h = trimesh.creation.extrude_polygon(Polygon(q2), 2 * wh + 2)
        R2 = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1.0]])
        h.apply_transform(R2); h.apply_translation([0, -wh - 1, 0]); h.apply_transform(T)
        teile.append(h)
    return trimesh.boolean.intersection(teile, engine="manifold")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ausgabe")
    ap.add_argument("--way", type=int); ap.add_argument("--name"); ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--radius", type=float, default=60); ap.add_argument("--massstab", type=float, default=87.0)
    ap.add_argument("--hoehe-m", type=float, help="gesicherte echte Gesamthoehe; streckt das Modell in der Hoehe darauf (OSM/LOD2 koennen falsch sein)")
    ap.add_argument("--bauraum", type=float, nargs=3, default=[220, 220, 250]); ap.add_argument("--teilen", action="store_true")
    a = ap.parse_args()

    if a.way:
        q = f'[out:json];way({a.way})->.w;.w map_to_area->.a;(.w;way["building:part"](area.a););out tags geom;'
    elif a.name and a.lat is not None:
        q = (f'[out:json];way["building"]["name"~"{a.name}",i](around:{a.radius},{a.lat},{a.lon})->.w;'
             f'.w map_to_area->.a;(.w;way["building:part"](area.a););out tags geom;')
    else:
        sys.exit("--way ID oder --name NAME --lat --lon angeben")
    els = [e for e in overpass(q)["elements"] if e.get("geometry")]
    teile_el = [e for e in els if "building:part" in e["tags"]] or [e for e in els if "building" in e["tags"]]
    if not teile_el:
        sys.exit("nichts gefunden")
    lat0 = np.mean([p["lat"] for e in teile_el for p in e["geometry"]]); lon0 = np.mean([p["lon"] for e in teile_el for p in e["geometry"]])
    mlat, mlon = 110574.0, 111320.0 * math.cos(math.radians(lat0))

    koerper, geschaetzt = [], []
    for e in teile_el:
        ring = [((p["lon"] - lon0) * mlon, (p["lat"] - lat0) * mlat) for p in e["geometry"]]
        poly = Polygon(ring).buffer(0)
        if poly.is_empty or poly.area < 1.0:
            continue
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)
        t = e["tags"]
        form = t.get("roof:shape", "flat")
        h = zahl(t.get("height")); z0 = zahl(t.get("min_height"), 0.0)
        if h is None:
            lv = zahl(t.get("building:levels"))
            h = (lv * 3.0 if lv else 9.0) + (3.0 if form != "flat" else 0.0)
            geschaetzt.append(f"{t.get('name', e['id'])}: Hoehe {h:.1f} m geschaetzt")
        rh = zahl(t.get("roof:height"))
        if rh is None and form != "flat":
            rh = 0.35 * (poly.minimum_rotated_rectangle.length / 2 - 0)  # grob; Walm/Giebel
            rh = min(rh, 0.45 * (h - z0)); geschaetzt.append(f"{t.get('name', e['id'])}: Dachhoehe {rh:.1f} m geschaetzt")
        zw = h - (rh or 0)
        k = dach_koerper(poly, z0, zw, h, form, rh or 0)
        koerper.append(k)
    m = trimesh.boolean.union(koerper, engine="manifold") if len(koerper) > 1 else koerper[0]
    if not m.is_watertight:
        m = druck.wasserdicht(m)
    hoehe_osm = float(m.extents[2]); hoehe_m = a.hoehe_m or hoehe_osm
    if a.hoehe_m:
        m.vertices[:, 2] *= a.hoehe_m / hoehe_osm
        geschaetzt.append(f"Hoehe von {hoehe_osm:.1f} m (OSM) auf {a.hoehe_m:.1f} m (vorgegeben) gestreckt - nur Z, Grundriss unveraendert")
    m.vertices -= [(m.bounds[0, 0] + m.bounds[1, 0]) / 2, (m.bounds[0, 1] + m.bounds[1, 1]) / 2, m.bounds[0, 2]]
    m.vertices *= 1000.0 / a.massstab
    ex = m.extents
    b = {"quelle": "OpenStreetMap (ODbL)", "bauteile": len(koerper), "hoehe_echt_m": round(hoehe_m, 1), "hoehe_osm_m": round(hoehe_osm, 1),
         "ausdehnung_mm": [round(float(x), 1) for x in ex], "massstab": f"1:{a.massstab:g}", "wasserdicht": bool(m.is_watertight),
         "volumen_mm3": round(float(m.volume)) if m.is_watertight else None, "geschaetzte_angaben": geschaetzt,
         "passt_in_bauraum": bool((ex <= np.array(a.bauraum)).all())}
    m.export(a.ausgabe)
    if a.teilen and not b["passt_in_bauraum"]:
        b["teile"] = []
        for (i, j, k), t in druck.in_stuecke(m, a.bauraum):
            t.export(a.ausgabe.rsplit(".", 1)[0] + f"_teil_{i}{j}{k}.stl")
            b["teile"].append({"nr": f"{i}{j}{k}", "mm": [round(float(x), 1) for x in t.extents], "wasserdicht": bool(t.is_watertight)})
        b["passt_in_bauraum"] = all(max(np.array(t["mm"]) - np.array(a.bauraum)) <= 0.5 for t in b["teile"])
    json.dump(b, open(a.ausgabe.rsplit(".", 1)[0] + ".bericht.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(b, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
