#!/usr/bin/env python3
"""stadtmesh_laden.py - Stadtmesh Freiburg 2025 (Quellentyp 19, STADT_MESH) fuer ein Objekt laden (Auftrag G4).

NUR PRUEFREFERENZ (Overlay, Kontur-Diff, Sichtvergleich). Lizenz fuer das Mesh ist NICHT geklaert (Klasse "ungeklaert",
modelle/LIZENZ_WERKZEUGE.md): Mesh-Geometrie darf NICHT in den Generator. Datei nur unter modelle/<objekt>/audit/referenz_stadtmesh/.

Cesium-3D-Tiles: tileset.json -> verschachtelte externe Tilesets (*.json) -> b3dm. Jeder Knoten hat eine 4x4-Transform (spaltenweise,
relativ zum Elternknoten) und eine OBB (box = Mitte + 3 Halbachsen im Knotenrahmen). Wir laufen rekursiv, akkumulieren die Transform,
bringen die 8 Boxecken nach ECEF -> WGS84 -> UTM32 und behalten nur Knoten, deren E/N-Huelle den Objektumriss (+ --rand m) schneidet;
geladen wird der feinste Knoten (kein Kind schneidet). b3dm -> glb (28-Byte-Kopf + Feature/Batch-Tabellen ueberspringen) -> trimesh ->
glTF y-up -> z-up (3D-Tiles-Konvention) -> Tile-Transform -> ECEF -> UTM32 -> Modellrahmen (wie baukasten_gen.lokal).

Hoehen: ECEF-Z der Kacheln entspricht (gemessen, Kaufhaus: Abweichung 0,3 m) schon der Hoehe ue.NN wie bei LGL. Ein Rest-Versatz wird NICHT
angenommen, sondern aus dem Mesh selbst geschaetzt (5. Perzentil der Hoehe im 25-m-Umkreis = Strassenniveau, gleichgesetzt mit rahmen.gelaende aus DGM1);
der Wert steht in der Meta-Datei (ANNAHME: Strassenniveau = DGM1, +-1 m wegen Fahrzeuge/Gefaelle).

  /media/oem/scan/venv-seg/bin/python -I tools/stadtmesh_laden.py modelle/kaufhaus_null5/objekt.json
"""
import argparse, datetime, glob, hashlib, io, json, math, os, struct, sys, urllib.error, urllib.parse, urllib.request
import numpy as np

BASIS = "https://3d.freiburg.de/datasource-data/2025_befliegung/22_Mesh3D_Cesium/"
DATEN = "/media/oem/scan/rc-park_daten/freiburg_stadt/mesh"
A_WGS, F_WGS = 6378137.0, 1 / 298.257223563
E2 = F_WGS * (2 - F_WGS)


def ecef_zu_utm(P, zone=32):
    """Nx3 ECEF -> (E, N, h_ellipsoid) (Bowring-Iteration; UTM Snyder-Reihe, < 1 cm im Zonenbereich)."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]; lon = np.arctan2(y, x); p = np.hypot(x, y); lat = np.arctan2(z, p * (1 - E2))
    for _ in range(6):
        N_ = A_WGS / np.sqrt(1 - E2 * np.sin(lat) ** 2); h = p / np.cos(lat) - N_; lat = np.arctan2(z, p * (1 - E2 * N_ / (N_ + h)))
    N_ = A_WGS / np.sqrt(1 - E2 * np.sin(lat) ** 2); h = p / np.cos(lat) - N_
    ep2 = E2 / (1 - E2); k0 = 0.9996; lam0 = math.radians((zone - 1) * 6 - 180 + 3)
    T = np.tan(lat) ** 2; C = ep2 * np.cos(lat) ** 2; Aa = np.cos(lat) * (lon - lam0)
    M = A_WGS * ((1 - E2 / 4 - 3 * E2 ** 2 / 64 - 5 * E2 ** 3 / 256) * lat - (3 * E2 / 8 + 3 * E2 ** 2 / 32 + 45 * E2 ** 3 / 1024) * np.sin(2 * lat)
                 + (15 * E2 ** 2 / 256 + 45 * E2 ** 3 / 1024) * np.sin(4 * lat) - (35 * E2 ** 3 / 3072) * np.sin(6 * lat))
    E = k0 * N_ * (Aa + (1 - T + C) * Aa ** 3 / 6 + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * Aa ** 5 / 120) + 500000.0
    Nn = k0 * (M + N_ * np.tan(lat) * (Aa ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * Aa ** 4 / 24 + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * Aa ** 6 / 720))
    return np.c_[E, Nn, h]


def holen(url, ziel, log):
    if os.path.exists(ziel) and os.path.getsize(ziel) > 0: return open(ziel, "rb").read()
    try:
        d = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "rc-park/1.0 (Modellbau, Pruefreferenz)"}), timeout=60).read()
        log.append((url, 200, len(d)))
    except urllib.error.HTTPError as e:
        log.append((url, e.code, 0)); raise
    os.makedirs(os.path.dirname(ziel), exist_ok=True); open(ziel + ".tmp", "wb").write(d); os.replace(ziel + ".tmp", ziel)
    return d


def box_ecken_utm(box, T):
    c = np.array(box[:3]); H = np.array(box[3:]).reshape(3, 3)
    pts = np.array([c + sx * H[0] + sy * H[1] + sz * H[2] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    pts = (np.c_[pts, np.ones(8)] @ T.T)[:, :3]
    return ecef_zu_utm(pts)


def schneidet(box, T, bb):
    u = box_ecken_utm(box, T)
    return not (u[:, 0].max() < bb[0] or u[:, 0].min() > bb[2] or u[:, 1].max() < bb[1] or u[:, 1].min() > bb[3])


def knoten(n, Tp):
    t = np.array(n["transform"], float).reshape(4, 4).T if "transform" in n else np.eye(4)   # 3D Tiles: spaltenweise
    return Tp @ t


def sammeln(node, Tp, bb, cache, log, urlbasis, tiles, tiefe=0):
    """Gibt True zurueck, wenn der Knoten (oder ein Nachfahre) den Umriss schneidet. Feinste schneidende Knoten -> tiles."""
    T = knoten(node, Tp); bv = node.get("boundingVolume", {})
    if "box" in bv and not schneidet(bv["box"], T, bb): return False
    kinder = list(node.get("children", [])); uri = (node.get("content") or {}).get("uri")
    if uri and uri.lower().endswith(".json"):                                             # externes Tileset: dessen root ersetzt den Inhalt
        u = urllib.parse.urljoin(urlbasis, uri); ts = json.loads(holen(u, os.path.join(cache, "ts_" + hashlib.md5(u.encode()).hexdigest() + ".json"), log))
        return sammeln(ts["root"], T, bb, cache, log, u, tiles, tiefe + 1) or False
    treffer = False
    for k in kinder:
        treffer |= sammeln(k, T, bb, cache, log, urlbasis, tiles, tiefe + 1)
    if not treffer and uri:
        tiles.append((urllib.parse.urljoin(urlbasis, uri), T)); return True
    return treffer


def b3dm_zu_glb(d):
    mag, ver, bl, fj, fb, bj, bb_ = struct.unpack("<4sIIIIII", d[:28])
    if mag != b"b3dm": raise ValueError(f"kein b3dm: {mag}")
    rtc = None
    if fj:
        ft = json.loads(d[28:28 + fj].decode().strip() or "{}"); rtc = ft.get("RTC_CENTER")
    return d[28 + fj + fb + bj + bb_:bl], rtc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("objekt"); ap.add_argument("--rand", type=float, default=20.0); ap.add_argument("--aus", default=None)
    ap.add_argument("--umriss", default=None, help="stadt_lod2.json (Standard modelle/<objekt>/stadt_lod2.json): Umriss = LGL-Grundriss; sonst Rahmen mitte +-25 m")
    a = ap.parse_args()
    import trimesh
    od = os.path.dirname(os.path.abspath(a.objekt)); name = os.path.basename(od); obj = json.load(open(a.objekt))
    R = obj.get("rahmen") or json.load(open(os.path.join(od, "anker3d.json")))
    C0 = np.array(R["mitte_utm"], float); XH = np.array(R["xhat_utm"], float); YH = np.array(R["yhat_utm"], float); Z0 = float(R["gelaende"])
    up = a.umriss or os.path.join(od, "stadt_lod2.json")
    if os.path.exists(up):                                                                # LGL-Umriss aus der G4-Datei (Boden- und Dachprojektion)
        J = json.load(open(up)); xy = np.array([p for g in J["stadt"]["gebaeude"] for f in g["flaechen"] for p in f["utm"]])[:, :2]
        bb0 = [xy[:, 0].min(), xy[:, 1].min(), xy[:, 0].max(), xy[:, 1].max()]; umriss_q = f"{os.path.basename(up)} (Stadt-LoD2-Gebaeude, Huelle)"
    else:
        bb0 = [C0[0] - 25, C0[1] - 25, C0[0] + 25, C0[1] + 25]; umriss_q = "ANNAHME: Rahmenmitte +-25 m"
    bb = [bb0[0] - a.rand, bb0[1] - a.rand, bb0[2] + a.rand, bb0[3] + a.rand]
    cache = os.path.join(DATEN, name); os.makedirs(cache, exist_ok=True); log = []
    tiles = []
    try:
        ts = json.loads(holen(BASIS + "tileset.json", os.path.join(cache, "tileset.json"), log))
        sammeln(ts["root"], np.eye(4), bb, cache, log, BASIS + "tileset.json", tiles)
    except urllib.error.HTTPError as e:
        print(f"FEHLSCHLAG HTTP {e.code} bei {e.url}"); json.dump(dict(log=log), open(os.path.join(cache, "zugriffslog.json"), "w")); sys.exit(4)
    print(f"{len(tiles)} feinste Kacheln schneiden Umriss {np.round(bb, 1).tolist()}")
    teile = []
    for u, T in tiles:
        try: d = holen(u, os.path.join(cache, "tiles", hashlib.md5(u.encode()).hexdigest() + "_" + os.path.basename(u)), log)
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code} {u}"); continue
        glb, rtc = b3dm_zu_glb(d)
        sc = trimesh.load(io.BytesIO(glb), file_type="glb", force="scene")
        for g in sc.dump():
            V = np.asarray(g.vertices, float); V = np.c_[V[:, 0], -V[:, 2], V[:, 1]]       # glTF y-up -> z-up (3D Tiles)
            if rtc: V = V + np.array(rtc)
            Pe = (np.c_[V, np.ones(len(V))] @ T.T)[:, :3]
            try: col = g.visual.to_color().vertex_colors[:, :3]
            except Exception: col = np.full((len(V), 3), 160, np.uint8)
            teile.append((Pe, np.asarray(g.faces), np.asarray(col)))
    if not teile:
        print("FEHLSCHLAG: keine Kachel geladen"); json.dump(dict(log=log), open(os.path.join(cache, "zugriffslog.json"), "w")); sys.exit(4)
    Ve, Fa, Co, off = [], [], [], 0
    for Pe, F, C in teile: Ve.append(Pe); Fa.append(F + off); Co.append(C); off += len(Pe)
    Pe = np.vstack(Ve); F = np.vstack(Fa); C = np.vstack(Co)
    U = ecef_zu_utm(Pe); d = U[:, :2] - C0; loc = np.c_[d @ XH, d @ YH, U[:, 2]]
    r = (loc[:, 0] ** 2 + loc[:, 1] ** 2) ** 0.5; boden = np.percentile(loc[r < 25, 2], 5)
    und = float(boden - Z0); loc[:, 2] -= und + Z0                                         # z ueber Gelaende, Strassenniveau = DGM1 (ANNAHME)
    keep = np.all((U[F][:, :, 0] > bb[0]) & (U[F][:, :, 0] < bb[2]) & (U[F][:, :, 1] > bb[1]) & (U[F][:, :, 1] < bb[3]), axis=1)
    F = F[keep]; used = np.unique(F); mp = -np.ones(len(loc), int); mp[used] = np.arange(len(used))
    m = trimesh.Trimesh(loc[used], mp[F], vertex_colors=C[used], process=False)
    aus = a.aus or os.path.join(od, "audit", "referenz_stadtmesh"); os.makedirs(aus, exist_ok=True)
    m.export(os.path.join(aus, "mesh.ply"))
    meta = dict(objekt=name, datum=datetime.date.today().isoformat(), werkzeug="tools/stadtmesh_laden.py (G4)", quelle=BASIS + "tileset.json",
                register_typ=19, lizenz_klasse="ungeklaert (nur Pruefreferenz; Anfrage vermessung@freiburg.de ausstehend)",
                umriss=umriss_q, bbox_utm=np.round(bb, 2).tolist(), rand_m=a.rand, kacheln=[u for u, _ in tiles], n_kacheln=len(tiles),
                dreiecke=int(len(m.faces)), vertices=int(len(m.vertices)), ausdehnung_m=np.round(m.bounds, 2).tolist(),
                rahmen=dict(mitte_utm=C0.tolist(), xhat_utm=XH.tolist(), yhat_utm=YH.tolist(), gelaende=Z0),
                z_bezug=dict(ellipsoid_minus_gelaende_m=round(und, 3), hinweis="ANNAHME: 5. Perzentil der Mesh-Hoehe im 25-m-Umkreis = Strassenniveau = DGM1-Gelaende; Messwert ist klein (<1 m): die Kacheln tragen schon Hoehen ue.NN (KEINE Geoidundulation ~47 m im ECEF); Rest = Strassenniveau-Schaetzfehler +-1 m"),
                http_log=[dict(url=u, code=c, bytes=b) for u, c, b in log])
    json.dump(meta, open(os.path.join(aus, "mesh_meta.json"), "w"), indent=1, ensure_ascii=False)
    print(f"mesh.ply: {len(m.vertices)} Punkte, {len(m.faces)} Dreiecke, Ausdehnung {np.round(m.bounds, 1).tolist()}, Undulation+Bezug {und:.2f} m -> {aus}")


if __name__ == "__main__":
    main()
