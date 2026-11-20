#!/usr/bin/env python3
"""
martinstor_osm_gen.py — Martinstor (Freiburg) als druckbarer Baukoerper aus den echten
OSM-3D-Daten (building:part mit height/min_height/roof:shape): Hauptturm 53 m mit
Walmdach + 4 Ecktuermchen. Massstab wie Hero-Modelle (1:500 -> ~106 mm hoch).

Dient als exaktes Mass-Geruest; Fassadendetail kommt aus dem Foto-Scan (Meshroom).
Daten: (c) OpenStreetMap-Mitwirkende, ODbL.  Rein stdlib.

  python3 martinstor_osm_gen.py            # Overpass abfragen -> stl/martinstor_osm.stl
  SCALE=300 python3 martinstor_osm_gen.py  # anderer Massstab (1:300)
"""
import json, math, os, struct, time, urllib.parse, urllib.request

SCALE = float(os.environ.get("SCALE", "500"))  # 1:SCALE
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl", "martinstor_osm.stl")
GATE = 1105286648  # OSM-Way "Martinstor"
Q = f'[out:json];way({GATE});map_to_area->.a;way["building:part"](area.a);out tags geom;'

def num(v, d=0.0):
    try: return float(str(v).split()[0].replace(",", "."))
    except Exception: return d

def overpass(q):
    for i in range(6):  # Overpass ist oft ueberlastet (502/504) -> wechselnde Server, Pause
        url = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")[i % 2]
        req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(),
                                     headers={"User-Agent": "rc-park/martinstor_osm_gen"})
        try: return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception as ex: print("Overpass:", ex, "- nochmal"); time.sleep(5)
    raise SystemExit("Overpass nicht erreichbar")

parts = [e for e in overpass(Q)["elements"] if e.get("geometry")]
lat0 = sum(p["lat"] for e in parts for p in e["geometry"]) / sum(len(e["geometry"]) for e in parts)
lon0 = sum(p["lon"] for e in parts for p in e["geometry"]) / sum(len(e["geometry"]) for e in parts)
mlat, mlon = 110574.0, 111320.0 * math.cos(math.radians(lat0))
k = 1000.0 / SCALE  # m -> mm

tris = []
for e in parts:
    ring = [((p["lon"] - lon0) * mlon * k, (p["lat"] - lat0) * mlat * k) for p in e["geometry"]]
    if ring[0] == ring[-1]: ring = ring[:-1]
    if sum(ring[i][0] * ring[i - 1][1] - ring[i - 1][0] * ring[i][1] for i in range(len(ring))) > 0:
        ring.reverse()  # einheitlich im Uhrzeigersinn -> Normalen nach aussen
    t = e["tags"]
    z0, z1 = num(t.get("min_height")) * k, num(t.get("height")) * k
    rh = num(t.get("roof:height")) * k if t.get("roof:shape", "flat") != "flat" else 0.0
    zw = z1 - rh  # Traufhoehe
    cx, cy = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
    n = len(ring)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        tris += [((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], zw)),
                 ((a[0], a[1], z0), (b[0], b[1], zw), (a[0], a[1], zw)),
                 ((cx, cy, z0), (b[0], b[1], z0), (a[0], a[1], z0))]  # Boden
        # Dach: Walm/Pyramide auf fast quadratischem Grundriss -> Spitze ueber Schwerpunkt
        tris.append(((a[0], a[1], zw), (b[0], b[1], zw), (cx, cy, z1)))

def normal(t):
    (ax, ay, az), (bx, by, bz), (cx_, cy_, cz) = t
    u, v = (bx - ax, by - ay, bz - az), (cx_ - ax, cy_ - ay, cz - az)
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    l = math.sqrt(sum(c * c for c in n)) or 1.0
    return tuple(c / l for c in n)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "wb") as f:
    f.write(b"martinstor_osm (c) OpenStreetMap ODbL".ljust(80, b" "))
    f.write(struct.pack("<I", len(tris)))
    for t in tris:
        f.write(struct.pack("<12fH", *normal(t), *t[0], *t[1], *t[2], 0))
xs = [p[0] for t in tris for p in t]; ys = [p[1] for t in tris for p in t]; zs = [p[2] for t in tris for p in t]
print(f"{len(parts)} Bauteile, {len(tris)} Dreiecke -> {OUT}")
print(f"1:{SCALE:.0f}: {max(xs)-min(xs):.1f} x {max(ys)-min(ys):.1f} x {max(zs)-min(zs):.1f} mm")
