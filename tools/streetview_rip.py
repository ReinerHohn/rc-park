#!/usr/bin/env python3
"""streetview_rip.py — HEBEL 2: aus Google Street View automatisch dutzende
fassaden-ausgerichtete Einzelfotos rund um ein Gebäude erzeugen — ohne eigenen
Fotoaufwand. Speist die Kaufhaus-Fotometrie (fenster_ml, shape_extract,
foto_kanten_messen ...) ODER Photogrammetrie (dust3r_run).

Drei Stufen (jede einzeln aufrufbar, aber normal verkettet):

  1) PANO-SUCHE  — rund um die Zielkoordinate einen Ring von Abfragepunkten legen
     und per offizieller Street-View-Metadata-API die Pano-IDs + echte Pano-GPS
     einsammeln (dedupliziert). Braucht einen Maps-API-Key (Metadata ist gratis).

  2) PANO-RIP    — je Pano das volle equirektanguläre 360°-Bild in MAX-Auflösung
     aus dem Kachel-Endpunkt stitchen (zoom 0..5; z5 ≈ 16384×8192). Kein Key.

  3) REPROJEKTION — aus jedem Pano perspektivische (pinhole) Einzelviews rendern,
     ausgerichtet auf die PEILUNG Pano→Gebäude (± Fächer), mit Pitch/FOV wählbar.
     Das sind die fassaden-geraden "Fotos", die die Mess-Tools erwarten.

Rechtlicher Hinweis (ehrlich): der Kachel-Endpunkt (--source tiles) ist nicht
dokumentiert und laut Google-ToS nur eingeschränkt nutzbar; für Produktiv-/
Veröffentlichungszwecke die offizielle Static-API (--source static, Key nötig,
max 640px/Request, wird hier zu einem Pano gestitcht) verwenden.

Beispiel (Historisches Kaufhaus Freiburg):
  python3 tools/streetview_rip.py --lat 47.9956 --lon 7.8522 \
      --out daten/kaufhaus_freiburg/streetview \
      --ring-r 28 --ring-n 8 --zoom 4 --views 3 --fov 70
"""
import argparse, os, sys, json, math, io, urllib.parse, urllib.request
import numpy as np, cv2

META = "https://maps.googleapis.com/maps/api/streetview/metadata"
STATIC = "https://maps.googleapis.com/maps/api/streetview"
# undokumentierter Kachel-Endpunkt (volle Auflösung, kein Key):
TILE = "https://streetviewpixels-pa.googleapis.com/v1/tile"
TS = 512                                  # Kachelkantenlänge


# ---------- Geo-Helfer ----------
def dest_point(lat, lon, bearing_deg, dist_m):
    """Zielpunkt dist_m in Richtung bearing von (lat,lon) — grob, ebene Näherung."""
    R = 6378137.0
    br = math.radians(bearing_deg)
    dlat = (dist_m * math.cos(br)) / R
    dlon = (dist_m * math.sin(br)) / (R * math.cos(math.radians(lat)))
    return lat + math.degrees(dlat), lon + math.degrees(dlon)


def bearing(lat1, lon1, lat2, lon2):
    """Kompass-Peilung von Punkt1 → Punkt2 in Grad (0=Nord, im Uhrzeigersinn)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 rcpark/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


# ---------- Stufe 1: Pano-Suche ----------
def discover(lat, lon, key, ring_r, ring_n):
    """Ring von Abfragepunkten → Metadata-API → eindeutige Panos (id, lat, lon, date)."""
    seen, panos = set(), []
    # Zentrum + Ring (Ring fängt Panos aus verschiedenen Fußgängerstandorten)
    pts = [(lat, lon)] + [dest_point(lat, lon, b, ring_r)
                          for b in np.linspace(0, 360, ring_n, endpoint=False)]
    for qlat, qlon in pts:
        q = urllib.parse.urlencode({"location": f"{qlat},{qlon}",
                                    "source": "outdoor", "key": key})
        try:
            m = json.loads(fetch(f"{META}?{q}"))
        except Exception as ex:
            print(f"  meta-err {qlat:.5f},{qlon:.5f}: {ex}"); continue
        if m.get("status") != "OK":
            continue
        pid = m.get("pano_id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        loc = m["location"]
        panos.append({"pano_id": pid, "lat": loc["lat"], "lon": loc["lng"],
                      "date": m.get("date", "")})
    print(f"  {len(panos)} eindeutige Panos gefunden")
    return panos


# ---------- Stufe 2: Pano-Rip (voll-equirektangulär) ----------
def rip_tiles(pano_id, zoom):
    """volles 360°-Pano aus dem Kachel-Endpunkt stitchen. Grid wird robust
    probiert und auf den tatsächlich gefüllten Bereich zugeschnitten."""
    cols = 2 ** zoom
    rows = max(1, 2 ** (zoom - 1))
    canvas = np.zeros((rows * TS, cols * TS, 3), np.uint8)
    got = np.zeros((rows, cols), bool)
    for y in range(rows):
        for x in range(cols):
            q = urllib.parse.urlencode({"cb_client": "maps_sv.tactile",
                                        "panoid": pano_id, "x": x, "y": y,
                                        "zoom": zoom, "nbt": 1, "fover": 2})
            try:
                raw = fetch(f"{TILE}?{q}", timeout=20)
                img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                if img is None or img.mean() < 1:
                    continue
                canvas[y*TS:(y+1)*TS, x*TS:(x+1)*TS] = img[:TS, :TS]
                got[y, x] = True
            except Exception:
                continue
    if not got.any():
        return None
    ys, xs = np.where(got.any(1))[0], np.where(got.any(0))[0]
    return canvas[: (ys.max()+1)*TS, : (xs.max()+1)*TS]


def rip_static(pano_id, key, fov=90, pitch=0):
    """offizielle Static-API: 4 Headings × 640px zu grobem Pano stitchen (Fallback)."""
    strips = []
    for h in (0, 90, 180, 270):
        q = urllib.parse.urlencode({"size": "640x640", "pano": pano_id,
                                    "heading": h, "pitch": pitch, "fov": fov, "key": key})
        try:
            raw = fetch(f"{STATIC}?{q}")
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            if img is not None:
                strips.append(img)
        except Exception as ex:
            print(f"  static-err h{h}: {ex}")
    return np.hstack(strips) if strips else None


# ---------- Stufe 3: equirektangulär → perspektivisch ----------
def reproject(equi, heading, pitch, fov_deg, out_w=1280, out_h=960):
    """pinhole-View aus dem Pano schneiden. heading=Kompass (0=Nord), pitch=hoch+.
    Annahme: Pano-Spalte x=0 ↔ Nord (Google-Konvention; bei Versatz --yaw-fix)."""
    H, W = equi.shape[:2]
    f = (out_w / 2) / math.tan(math.radians(fov_deg) / 2)
    u, v = np.meshgrid(np.arange(out_w), np.arange(out_h))
    # Strahl im Kamera-Frame (x rechts, y hoch, z vorwärts)
    xc = (u - out_w / 2) / f
    yc = -(v - out_h / 2) / f
    zc = np.ones_like(xc)
    n = np.sqrt(xc*xc + yc*yc + zc*zc)
    xc, yc, zc = xc/n, yc/n, zc/n
    # Pitch (um Rechts-Achse) dann Yaw (um Hoch-Achse)
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    yp = yc*cp - zc*sp
    zp = yc*sp + zc*cp
    cy, sy = math.cos(math.radians(heading)), math.sin(math.radians(heading))
    east = xc*cy + zp*sy        # +Ost
    north = -xc*sy + zp*cy      # +Nord
    up = yp
    lon = np.arctan2(east, north)                 # 0=Nord, Ost positiv
    lat = np.arcsin(np.clip(up, -1, 1))
    mapx = ((lon / (2*math.pi)) % 1.0) * W
    mapy = (0.5 - lat / math.pi) * H
    return cv2.remap(equi, mapx.astype(np.float32), mapy.astype(np.float32),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


# ---------- Orchestrierung ----------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--out", required=True, help="Ausgabeordner")
    p.add_argument("--key", help="Maps-API-Key (ENV GOOGLE_MAPS_API_KEY / ~/.config/gmaps_key)")
    p.add_argument("--pano", help="direkte Pano-ID (überspringt Suche)")
    p.add_argument("--source", choices=["tiles", "static"], default="tiles")
    p.add_argument("--ring-r", type=float, default=28, help="Suchring-Radius [m]")
    p.add_argument("--ring-n", type=int, default=8, help="Abfragepunkte auf dem Ring")
    p.add_argument("--zoom", type=int, default=4, help="Kachel-Zoom 0..5 (5=max)")
    p.add_argument("--views", type=int, default=3, help="perspektivische Views je Pano (Fächer)")
    p.add_argument("--spread", type=float, default=25, help="Fächerbreite der Views [Grad]")
    p.add_argument("--fov", type=float, default=70)
    p.add_argument("--pitch", type=float, default=8, help="Blick leicht nach oben (Fassade)")
    p.add_argument("--yaw-fix", type=float, default=0, help="Pano-Nord-Korrektur [Grad]")
    a = p.parse_args()

    key = a.key or os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        kp = os.path.expanduser("~/.config/gmaps_key")
        if os.path.exists(kp):
            key = open(kp).read().strip()
    os.makedirs(a.out, exist_ok=True)

    if a.pano:
        panos = [{"pano_id": a.pano, "lat": a.lat, "lon": a.lon, "date": ""}]
    else:
        if not key:
            sys.exit("Pano-Suche braucht --key (oder direkt --pano angeben).")
        print("Suche Panos ...")
        panos = discover(a.lat, a.lon, key, a.ring_r, a.ring_n)
    if not panos:
        sys.exit("Keine Panos gefunden — Ring vergrößern oder Koordinate prüfen.")

    manifest = []
    for i, pn in enumerate(panos):
        pid = pn["pano_id"]
        print(f"[{i+1}/{len(panos)}] Pano {pid[:16]}… rippe ({a.source}) ...")
        if a.source == "tiles":
            equi = rip_tiles(pid, a.zoom)
        else:
            if not key: sys.exit("--source static braucht --key.")
            equi = rip_static(pid, key)
        if equi is None:
            print("  leer, übersprungen"); continue
        cv2.imwrite(os.path.join(a.out, f"pano_{i:02d}.jpg"), equi)
        # Peilung Pano → Gebäude: so steht die Fassade mittig im View
        head0 = bearing(pn["lat"], pn["lon"], a.lat, a.lon) + a.yaw_fix
        offs = (np.linspace(-a.spread, a.spread, a.views) if a.views > 1 else [0.0])
        for j, off in enumerate(offs):
            view = reproject(equi, head0 + off, a.pitch, a.fov)
            fn = f"sv_{i:02d}_{j}.jpg"
            cv2.imwrite(os.path.join(a.out, fn), view)
            manifest.append({"file": fn, "pano_id": pid, "pano_lat": pn["lat"],
                             "pano_lon": pn["lon"], "heading": round(head0 + off, 1),
                             "pitch": a.pitch, "fov": a.fov, "date": pn["date"]})
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump({"target": [a.lat, a.lon], "views": manifest}, f, indent=2)
    print(f"\n{len(manifest)} fassaden-Views + {len(panos)} Panos → {a.out}")
    print("Nächster Schritt: tools/fenster_ml.py / foto_kanten_messen.py auf sv_*.jpg,")
    print("oder tools/dust3r_run.py für Multi-View-Photogrammetrie.")


if __name__ == "__main__":
    main()
