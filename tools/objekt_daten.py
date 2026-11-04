#!/usr/bin/env python3
"""objekt_daten.py - GENERISCH: amtliche Grunddaten eines neuen Objekts holen und daraus Modellrahmen + 3D-Anker bauen (Nullstart-Stufe 0).

Beim Martinstor war das Handarbeit (masspruefung_daten.py mit festen Koordinaten, anker3d.json von Hand). Hier aus Daten:
  1. Lage: --lat/--lon oder --suche (Nominatim, OSM).
  2. LGL BW opengeodata (Datenlizenz Deutschland Namensnennung 2.0): LoD2, DOM1, DGM1 der 2-km-Kachel -> gemeinsamer Cache
     /media/oem/scan/rc-park_daten/_geo (Grossdaten nie auf die Root-Platte).
  3. LoD2-Gebaeude naechst der Lage (tools/lod2_gebaeude.extract) -> Grundriss, Traufe, First, Boden.
  4. Modellrahmen: Ursprung = Grundriss-Mitte, +x = Langachse des Grundrisses (eher N-S: nach Sueden, eher O-W: nach Osten), +y = +x um 90 Grad links (rechtshaendig), z ueber DGM1;
     seiten_konvention aus dem Kompass, wenn noch Platzhalter.
  5. DOM1-Fenster (Standard 60 x 60 m) -> .npy unter rc-park_daten/<objekt>/, Gelaende = DGM1-Median im Grundriss.
  6. anker3d.json: ecke_boden_i (Grundrissecken, z 0), ecke_wandoben_i (gleiche Ecke, z = Traufe aus LoD2), first_i (Firstpunkte LoD2),
     spitze_dom (DOM1-Maximum im Grundriss) - jeweils mit sigma und Quelle.
  7. objekt.json: ort, lage, laser{fenster_npy, gelaende_m, quelle}, rahmen.
  python3 tools/objekt_daten.py modelle/<objekt>/objekt.json --suche "Historisches Kaufhaus Freiburg" [--fenster 60]
"""
import os, sys, json, math, zipfile, argparse, subprocess, urllib.parse, urllib.request
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CACHE = "/media/oem/scan/rc-park_daten/_geo"
LGL = "https://opengeodata.lgl-bw.de/data"


def utm32(lat, lon):
    a = 6378137.0; f = 1 / 298.257222101; e2 = f * (2 - f); ep2 = e2 / (1 - e2); k0 = 0.9996; lon0 = math.radians(9.0)
    la = math.radians(lat); lo = math.radians(lon); N = a / math.sqrt(1 - e2 * math.sin(la) ** 2); T = math.tan(la) ** 2; C = ep2 * math.cos(la) ** 2; A = math.cos(la) * (lo - lon0)
    M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * la - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * la) + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * la) - (35 * e2 ** 3 / 3072) * math.sin(6 * la))
    return 500000 + k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120), k0 * (M + N * math.tan(la) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720))


def holen(url, ziel):
    if os.path.exists(ziel) and os.path.getsize(ziel) > 1000: return ziel
    os.makedirs(os.path.dirname(ziel), exist_ok=True); print(f"  lade {url}", flush=True)
    subprocess.run(["curl", "-s", "-f", "-m", "900", "-o", ziel + ".tmp", url], check=True); os.replace(ziel + ".tmp", ziel); return ziel


def entpacken(z):
    d = z[:-4]
    if not os.path.isdir(d): zipfile.ZipFile(z).extractall(os.path.dirname(z))
    return d


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--suche"); ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--fenster", type=int, default=60); ap.add_argument("--radius", type=float, default=25.0, help="Suchradius LoD2-Gebaeude um die Lage (m)"); a = ap.parse_args()
    op = os.path.abspath(a.objekt); od = os.path.dirname(op); ob = os.path.basename(od); obj = json.load(open(op)) if os.path.exists(op) else {}
    if a.lat is None:
        q = urllib.parse.urlencode(dict(q=a.suche, format="json", limit=1))
        r = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers={"User-Agent": "rc-park/1.0 (Modellbau)"}), timeout=30).read())
        if not r: sys.exit(f"Nominatim: nichts gefunden fuer '{a.suche}'")
        a.lat, a.lon = float(r[0]["lat"]), float(r[0]["lon"]); lage_q = f"Nominatim (OSM, ODbL): {r[0]['display_name']}"
    else: lage_q = "Eingabe --lat/--lon"
    E, N = utm32(a.lat, a.lon); ek, nk = int(E // 1000), int(N // 1000); t2 = f"{ek if ek % 2 else ek - 1}_{nk if nk % 2 == 0 else nk - 1}"; t1 = f"{ek}_{nk}"
    print(f"Lage {a.lat:.6f}, {a.lon:.6f} -> UTM32 E {E:.1f} N {N:.1f}, Kachel {t2} ({lage_q})")
    # LoD2
    lz = holen(f"{LGL}/lod2/LoD2_32_{t2}_2_bw.zip", f"{CACHE}/LoD2_32_{t2}_2_bw.zip"); ld = entpacken(lz)
    gml = os.path.join(ld, f"LoD2_32_{t1}_1_BW.gml")
    if not os.path.exists(gml): gml = next(os.path.join(dp, f) for dp, _, fs in os.walk(ld) for f in fs if f.lower() == f"lod2_32_{t1}_1_bw.gml")
    import lod2_gebaeude as LG
    picked = LG.extract(gml, center=(E, N), radius=a.radius)
    if not picked: sys.exit(f"kein LoD2-Gebaeude im Radius {a.radius} m")
    from matplotlib.path import Path as _P
    def trifft(mp):                                                                          # Lage liegt im Grundriss -> dieses Gebaeude; sonst naechste Mitte
        gr = [P for t, P in mp[1] if t == "GroundSurface"]
        return any(_P(P[:, :2]).contains_point((E, N)) for P in gr)
    b, polys = next((mp for mp in picked if trifft(mp)), None) or min(picked, key=lambda mp: math.hypot(mp[0]["center_utm"][0] - E, mp[0]["center_utm"][1] - N))
    print(f"  LoD2-Kandidaten im Radius: {len(picked)}; gewaehlt {b['id']} ({'Lage im Grundriss' if trifft((b, polys)) else 'naechste Mitte'})")
    grnd = [P for t, P in polys if t == "GroundSurface"]; roof = [P for t, P in polys if t == "RoofSurface"]
    gz = b["ground_z"]; G = np.vstack(grnd)[:, :2]
    # Grundriss: konvexe Huelle -> Ecken (Winkel < 160 Grad), Langachse = Hauptachse (PCA)
    from scipy.spatial import ConvexHull
    H = G[ConvexHull(G).vertices]; ecken = []
    for i in range(len(H)):
        p0, p1, p2 = H[i - 1], H[i], H[(i + 1) % len(H)]; v1, v2 = p0 - p1, p2 - p1
        w = math.degrees(math.acos(np.clip(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9), -1, 1)))
        if w < 160: ecken.append(p1)
    ecken = np.array(ecken); c0 = G.mean(0)
    _, _, Vt = np.linalg.svd(G - c0); xh = Vt[0] / np.linalg.norm(Vt[0])
    if abs(xh[1]) >= abs(xh[0]):                                                             # Langachse eher N-S: +x nach Sueden (Konvention Martinstor)
        if xh[1] > 0: xh = -xh
    elif xh[0] < 0: xh = -xh                                                                 # Langachse eher O-W: +x nach Osten (stabil, kein Vorzeichenkippen bei kleiner N-Komponente)
    yh = np.array([-xh[1], xh[0]])                                                           # immer rechtshaendig (z oben): +y = +x um 90 Grad gegen Uhrzeiger
    himmel = lambda v: ("Nord", "Ost", "Sued", "West")[int(((math.degrees(math.atan2(v[0], v[1])) + 45) % 360) // 90)]   # Kompassrichtung eines Vektors (E, N)
    lok = lambda p: [round(float((np.asarray(p[:2]) - c0) @ xh), 3), round(float((np.asarray(p[:2]) - c0) @ yh), 3)]
    # DOM1/DGM1
    dz_ = entpacken(holen(f"{LGL}/dom1/dom1_32_{t2}_2_bw.zip", f"{CACHE}/dom1_32_{t2}_2_bw.zip")); gz_ = entpacken(holen(f"{LGL}/dgm/dgm1_32_{t2}_2_bw.zip", f"{CACHE}/dgm1_32_{t2}_2_bw.zip"))
    from PIL import Image; Image.MAX_IMAGE_PIXELS = None
    dom = os.path.join(dz_, f"dom1_32_{t1}_1_bw_2017"); A = np.array(Image.open(dom + ".tif")).astype(float); A[A < -100] = np.nan
    x0, y0 = [float(x) for x in open(dom + ".tfw")][4:6]
    g = np.loadtxt(os.path.join(gz_, f"dgm1_32_{t1}_1_bw_2017.xyz"))
    im_ = _P(H).contains_points(g[:, :2]); gel = float(np.median(g[im_, 2])) if im_.sum() >= 3 else float(gz)
    h = a.fenster // 2; cc, rr = int(c0[0] - x0), int(y0 - c0[1]); W = A[rr - h:rr + h, cc - h:cc + h]
    datd = f"/media/oem/scan/rc-park_daten/{ob}"; os.makedirs(datd, exist_ok=True); wn = os.path.join(datd, f"dom1_fenster_{a.fenster}m.npy"); np.save(wn, W)
    # DOM1-Maximum im Grundriss
    yy, xx = np.mgrid[:W.shape[0], :W.shape[1]]; U = np.c_[(x0 + cc - h + xx.ravel()), (y0 - (rr - h) - yy.ravel())]   # .tfw = Mitte des Pixels links oben (LGL 414000.5/5316999.5): kein +0,5 (Fix 2026-11-04)
    inn = _P(H).contains_points(U).reshape(W.shape); Wm = np.where(inn, W, np.nan); iy, ix = np.unravel_index(np.nanargmax(Wm), Wm.shape); pk = U[iy * W.shape[1] + ix]
    # Traufe/First je Ecke aus den Dachflaechen (naechster Dachpunkt zur Ecke)
    R = np.vstack(roof) if roof else None
    anker = {}
    for i, e in enumerate(ecken):
        anker[f"ecke_boden_{i}"] = dict(xyz=lok(e) + [0.0], sigma=0.3, quelle=f"LoD2 {b['id']} Grundrissecke (LGL BW)", quelltyp="lod2")
        if R is not None:
            d = np.hypot(R[:, 0] - e[0], R[:, 1] - e[1]); zt = float(R[d < max(d.min() + 0.5, 1.0), 2].min() - gel)
            anker[f"ecke_wandoben_{i}"] = dict(xyz=lok(e) + [round(zt, 2)], sigma=0.5, quelle=f"LoD2 {b['id']}: Traufe an der Ecke (tiefster Dachpunkt dort)", quelltyp="lod2")
    if R is not None:
        top = R[R[:, 2] >= R[:, 2].max() - 0.3]
        for i, p in enumerate(top[np.unique(np.round(top[:, :2], 0), axis=0, return_index=True)[1]][:4]):
            anker[f"first_{i}"] = dict(xyz=lok(p) + [round(float(p[2] - gel), 2)], sigma=0.5, quelle=f"LoD2 {b['id']}: Firstpunkt", quelltyp="lod2")
    anker["spitze_dom"] = dict(xyz=lok(pk) + [round(float(np.nanmax(Wm) - gel), 2)], sigma=0.5, quelle="DOM1 1 m: Maximum im LoD2-Grundriss (Laser blind fuer Bauteile < ~3 m, Regel 4)", quelltyp="laser_dom1")
    rahmen = dict(mitte_utm=[round(float(c0[0]), 2), round(float(c0[1]), 2)], xhat_utm=[round(float(xh[0]), 4), round(float(xh[1]), 4)], yhat_utm=[round(float(yh[0]), 4), round(float(yh[1]), 4)],
                  gelaende=round(gel, 2), hinweis=f"Modellrahmen aus LoD2 (tools/objekt_daten.py): Ursprung Grundriss-Mitte, +x Langachse nach {himmel(xh)}, +y nach {himmel(yh)} (rechtshaendig), z ueber DGM1")
    json.dump(dict(**rahmen, anker=anker), open(os.path.join(od, "anker3d.json"), "w"), indent=1, ensure_ascii=False)
    obj.update(lage=dict(lat=a.lat, lon=a.lon, utm32=[round(E, 2), round(N, 2)], quelle=lage_q), rahmen=rahmen,
               laser=dict(fenster_npy=wn, gelaende_m=round(gel, 2), raster_n=a.fenster, quelle=f"LGL BW DOM1 1 m, Fenster {a.fenster}x{a.fenster} m um die Grundriss-Mitte (tools/objekt_daten.py); Gelaende DGM1-Median im Grundriss"),
               lod2=dict(gml=gml, id=b["id"], traufe_m=b.get("eave_m"), first_m=b.get("ridge_m"), grundriss_kanten_m=b.get("footprint_edges_m"), dachtyp=[LG.ROOFNAMES.get(x, x) for x in b.get("rooftypes", [])]))
    sk = obj.get("seiten_konvention") or {}
    if not sk or sk.get("quelle") == "OFFEN" or "festlegen" in str(sk.get("+x", "")):              # Platzhalter aus objekt_anlegen.py -> aus dem Rahmen (Kompass); vom Nutzer gesetzte bleibt
        obj["seiten_konvention"] = {"+x": himmel(xh), "-x": himmel(-xh), "+y": himmel(yh), "-y": himmel(-yh),
                                    "quelle": "tools/objekt_daten.py: Kompassrichtung der Rahmenachsen (LoD2-Grundriss); Fassadennamen/Merkmale je Seite noch am Foto festlegen"}
    json.dump(obj, open(op, "w"), indent=1, ensure_ascii=False)
    print(f"Seiten: {obj['seiten_konvention']}")
    print(f"LoD2 {b['id']} ({b.get('name')}): Traufe {b.get('eave_m'):.1f} m, First {b.get('ridge_m'):.1f} m, Grundriss {b.get('footprint_edges_m', [])[:4]} m, Dach {obj['lod2']['dachtyp']}")
    print(f"Gelaende {gel:.2f} m ue.NN; DOM1-Maximum {np.nanmax(Wm) - gel:.2f} m ueber Gelaende; {len(ecken)} Grundrissecken; {len(anker)} Anker -> {os.path.join(od, 'anker3d.json')}")
    print(f"DOM1-Fenster -> {wn}")


if __name__ == "__main__":
    main()
