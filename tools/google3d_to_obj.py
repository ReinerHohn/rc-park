#!/usr/bin/env python3
"""google3d_to_obj.py — Google Photorealistic 3D Tiles (echte Städte/Orte) → OBJ.

Lädt die 3D-Tiles rund um eine Koordinate (lat/lon + Radius), transformiert sie von
ECEF nach lokalem ENU (Meter, Z=hoch) und speichert ein OBJ — danach durch
`tools/drone_to_print.py` druckfertig machen.

BRAUCHT: gratis Google-Maps-Platform-API-Key mit aktivierter *Map Tiles API*.
  Key holen: console.cloud.google.com → Projekt → „APIs & Services" → Map Tiles API
  aktivieren → Anmeldedaten → API-Schlüssel. Kostenlos im Rahmen des Gratis-Kontingents.
Key übergeben: ENV GOOGLE_MAPS_API_KEY, oder --key, oder Datei ~/.config/gmaps_key.

Beispiel (Kastelburg Waldkirch):
  python3 tools/google3d_to_obj.py --lat 48.0958 --lon 7.9602 --radius 160 \
      --out modelle/scans/kastelburg_google.obj
"""
import argparse, os, sys, json, math, urllib.parse, urllib.request, tempfile
import numpy as np, trimesh

ROOT = "https://tile.googleapis.com/v1/3dtiles/root.json"
BASE = "https://tile.googleapis.com"
A = 6378137.0; F = 1/298.257223563; E2 = F*(2-F)   # WGS84

def geodetic_to_ecef(lat, lon, h=0.0):
    la, lo = math.radians(lat), math.radians(lon)
    N = A/math.sqrt(1-E2*math.sin(la)**2)
    return np.array([(N+h)*math.cos(la)*math.cos(lo),
                     (N+h)*math.cos(la)*math.sin(lo),
                     (N*(1-E2)+h)*math.sin(la)])

def enu_matrix(lat, lon):
    """Rotations-Basis ECEF→ENU am Referenzpunkt."""
    la, lo = math.radians(lat), math.radians(lon)
    e = np.array([-math.sin(lo), math.cos(lo), 0])
    n = np.array([-math.sin(la)*math.cos(lo), -math.sin(la)*math.sin(lo), math.cos(la)])
    u = np.array([ math.cos(la)*math.cos(lo),  math.cos(la)*math.sin(lo), math.sin(la)])
    return np.vstack([e, n, u])          # 3x3, Zeilen = E,N,U

def get_key(args):
    k = args.key or os.environ.get("GOOGLE_MAPS_API_KEY")
    if not k:
        p = os.path.expanduser("~/.config/gmaps_key")
        if os.path.exists(p): k = open(p).read().strip()
    if not k: sys.exit("Kein API-Key. ENV GOOGLE_MAPS_API_KEY / --key / ~/.config/gmaps_key.")
    return k

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "rcpark/1.0"})
    return urllib.request.urlopen(req, timeout=30).read()

def add_params(uri, key, session):
    """content.uri (relativ/absolut) → vollständige URL mit key (+session)."""
    if uri.startswith("http"): full = uri
    elif uri.startswith("/"):  full = BASE + uri
    else:                      full = BASE + "/" + uri
    pr = urllib.parse.urlparse(full); q = dict(urllib.parse.parse_qsl(pr.query))
    q["key"] = key
    if "session" not in q and session: q["session"] = session
    return urllib.parse.urlunparse(pr._replace(query=urllib.parse.urlencode(q)))

def bv_center_ecef(bv):
    if "box" in bv:            # [cx,cy,cz, ...Halbachsen]
        b = bv["box"]; return np.array(b[:3]), max(abs(np.array(b[3:12])).sum()/3, 1)
    if "region" in bv:         # [w,s,e,n,minh,maxh] rad
        w,s,e,n,hmin,hmax = bv["region"]
        lat = math.degrees((s+n)/2); lon = math.degrees((w+e)/2); h=(hmin+hmax)/2
        return geodetic_to_ecef(lat, lon, h), 50.0
    if "sphere" in bv:
        sp = bv["sphere"]; return np.array(sp[:3]), sp[3]
    return None, 0

def traverse(node, key, session, target, radius, min_ge, glbs, xform=np.eye(4), depth=0):
    """Rekursiv Tiles einsammeln, deren Bounding-Volume nahe am Zielpunkt liegt."""
    if depth > 30: return
    t = node.get("transform")
    M = xform @ np.array(t, float).reshape(4,4).T if t else xform
    bv = node.get("boundingVolume", {})
    center, bvr = bv_center_ecef(bv)
    if center is not None:
        cw = (M @ np.append(center, 1))[:3]
        if np.linalg.norm(cw - target) > radius + bvr:   # zu weit weg → Zweig abschneiden
            return
    ge = node.get("geometricError", 0)
    content = node.get("content") or {}
    uri = content.get("uri") or content.get("url")
    children = node.get("children", [])
    # Blatt-/Detail-Logik: feines Tile (kleiner geometricError) mit Geometrie einsammeln
    if uri:
        low = uri.lower()
        if low.endswith(".json"):            # Sub-Tileset → laden & weiter absteigen
            try:
                sub = json.loads(fetch(add_params(uri, key, session)))
                sess = session
                # neue session evtl. in sub-URIs; einfach weiterreichen
                traverse(sub["root"], key, sess, target, radius, min_ge, glbs, M, depth+1)
            except Exception as ex:
                print(f"  sub-tileset err d{depth}: {ex}")
            return
        elif low.split("?")[0].endswith((".glb", ".gltf")):
            if ge <= min_ge or not children:   # fein genug oder Blatt → nehmen
                glbs.append((add_params(uri, key, session), M.copy()))
                return
    for ch in children:
        traverse(ch, key, session, target, radius, min_ge, glbs, M, depth+1)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lat", type=float, required=True); p.add_argument("--lon", type=float, required=True)
    p.add_argument("--radius", type=float, default=150, help="Einzugsradius [m]")
    p.add_argument("--min-ge", type=float, default=4.0, help="Ziel-geometricError [m] (kleiner=feiner)")
    p.add_argument("--out", required=True); p.add_argument("--key")
    a = p.parse_args()
    key = get_key(a)
    target = geodetic_to_ecef(a.lat, a.lon, 0)
    print(f"Lade Root-Tileset ...")
    root = json.loads(fetch(f"{ROOT}?key={key}"))
    # Session-Param aus erster content.uri ziehen (Google hängt ?session=... an)
    session = None
    def find_sess(n):
        nonlocal session
        c = (n.get("content") or {}); u = c.get("uri") or c.get("url") or ""
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(
            u if u.startswith("http") else "http://x/"+u.lstrip("/")).query))
        if "session" in q: session = q["session"]
        for ch in n.get("children", []):
            if session: break
            find_sess(ch)
    find_sess(root["root"])
    print(f"  session={session}")
    glbs = []
    traverse(root["root"], key, session, target, a.radius, a.min_ge, glbs)
    print(f"Gefundene Geometrie-Tiles: {len(glbs)}")
    if not glbs: sys.exit("Nichts im Radius gefunden — Radius/min-ge erhöhen oder Koordinaten prüfen.")

    R = enu_matrix(a.lat, a.lon)           # ECEF→ENU
    parts = []
    for i, (url, M) in enumerate(glbs):
        try:
            data = fetch(url)
            with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as f:
                f.write(data); tmp = f.name
            g = trimesh.load(tmp, force="mesh")
            if g.vertices is None or len(g.vertices) == 0: continue
            V = (M @ np.c_[g.vertices, np.ones(len(g.vertices))].T).T[:, :3]  # → ECEF
            V = (R @ (V - target).T).T                                       # → lokal ENU (m)
            parts.append(trimesh.Trimesh(vertices=V, faces=g.faces, process=False))
            if i % 10 == 0: print(f"  {i+1}/{len(glbs)} tiles ...")
        except Exception as ex:
            print(f"  tile {i} err: {ex}")
    if not parts: sys.exit("Keine Geometrie ladbar.")
    full = trimesh.util.concatenate(parts)
    full.export(a.out)
    e = full.extents
    print(f"OBJ: {len(full.faces):,} faces, bbox {e[0]:.0f} x {e[1]:.0f} x {e[2]:.0f} m → {a.out}")
    print(f"Nächster Schritt: python3 tools/drone_to_print.py {a.out} --mode detail --foot 160 --out modelle/stl/kastelburg_google.stl")

if __name__ == "__main__":
    main()
