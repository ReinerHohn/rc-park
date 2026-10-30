#!/usr/bin/env python3
"""mapillary_rip.py — HEBEL 2 (Google-frei): fassaden-ausgerichtete Fotos aus
MAPILLARY statt Google Street View. Crowdgesourcte Straßenbilder, georeferenziert
+ mit Blickrichtung, freie Lizenz, Token GRATIS ohne Kreditkarte.

Gleiche Ausgabe wie streetview_rip.py (sv_*.jpg + manifest.json) → speist direkt
Hebel 6 (fenster_ml) + Hebel 7 (foto_displacement).

Ablauf:
  1) Bounding-Box um die Zielkoordinate → Mapillary Graph-API nach Bildern fragen.
  2) Peilung Foto-Standort → Gebäude rechnen.
     • perspektivische Bilder: behalten, wenn die KAMERA Richtung Gebäude zeigt
       (compass_angle nahe der Peilung) — sonst blickt es weg.
     • sphärische 360°-Bilder: perspektivischen Ausschnitt auf die Peilung
       reprojizieren (gleiche Mathematik wie streetview_rip).
  3) Bild in 2048 px laden, als sv_*.jpg ablegen + Metadaten ins Manifest.

Token (gratis): mapillary.com → Settings → Developers → Register Application →
Token kopieren. Übergabe: --token / ENV MAPILLARY_TOKEN / ~/.config/mapillary_token

  python3 tools/mapillary_rip.py --lat 47.9931 --lon 7.8503 \
      --out daten/martinstor/mapillary --radius 40 --max 30
"""
import argparse, os, sys, json, math, urllib.parse, urllib.request
import numpy as np, cv2
from streetview_rip import reproject, bearing          # Hebel-2-Mathematik teilen

GRAPH = "https://graph.mapillary.com/images"


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "rcpark/1.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def get_token(a):
    t = a.token or os.environ.get("MAPILLARY_TOKEN")
    if not t:
        p = os.path.expanduser("~/.config/mapillary_token")
        if os.path.exists(p):
            t = open(p).read().strip()
    if not t:
        sys.exit("Kein Token. Gratis holen (ohne Kreditkarte): mapillary.com → Settings → "
                 "Developers → Register Application. Dann --token / ENV MAPILLARY_TOKEN / "
                 "~/.config/mapillary_token.")
    return t


def ang_diff(a, b):
    """kleinste Winkeldifferenz in Grad (0..180)."""
    return abs((a - b + 180) % 360 - 180)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--token")
    p.add_argument("--radius", type=float, default=40, help="Suchradius [m]")
    p.add_argument("--max", type=int, default=30, help="max. Bilder")
    p.add_argument("--aim-tol", type=float, default=45,
                   help="max. Abweichung Kamera↔Gebäude-Peilung [Grad] (perspektivisch)")
    p.add_argument("--fov", type=float, default=70, help="FOV der 360°-Ausschnitte")
    p.add_argument("--pitch", type=float, default=8)
    p.add_argument("--raw", action="store_true",
                   help="ROH-Modus für Photogrammetrie: ALLE Bilder im Radius ungeschnitten "
                        "speichern + volle GPS/Kompass/Kameratyp-Metadaten (→ opensfm_run.py)")
    a = p.parse_args()
    token = get_token(a)
    os.makedirs(a.out, exist_ok=True)

    # Bounding-Box aus Radius
    dlat = a.radius / 111320.0
    dlon = a.radius / (111320.0 * math.cos(math.radians(a.lat)))
    bbox = f"{a.lon-dlon},{a.lat-dlat},{a.lon+dlon},{a.lat+dlat}"
    fields = ("id,geometry,compass_angle,computed_compass_angle,computed_geometry,"
              "camera_type,captured_at,thumb_2048_url")
    q = urllib.parse.urlencode({"access_token": token, "fields": fields,
                                "bbox": bbox, "limit": max(a.max * 3, 50)})
    print(f"Mapillary-Suche bbox={bbox} ...")
    try:
        data = json.loads(fetch(f"{GRAPH}?{q}"))
    except Exception as ex:
        sys.exit(f"API-Fehler: {ex}  (Token gültig? Rechte 'Read'?)")
    imgs = data.get("data", [])
    print(f"  {len(imgs)} Bilder im Umkreis")

    manifest, kept = [], 0
    for im in imgs:
        if kept >= a.max:
            break
        geom = im.get("computed_geometry") or im.get("geometry") or {}
        c = geom.get("coordinates")
        if not c:
            continue
        ilon, ilat = c[0], c[1]
        head_to_bldg = bearing(ilat, ilon, a.lat, a.lon)
        cam = im.get("computed_compass_angle")
        if cam is None:
            cam = im.get("compass_angle")
        url = im.get("thumb_2048_url")
        if not url:
            continue
        try:
            raw = fetch(url)
            img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        except Exception as ex:
            print(f"  dl-err {im['id']}: {ex}"); continue
        if img is None:
            continue
        ctype = (im.get("camera_type") or "").lower()
        if a.raw:
            # Photogrammetrie: Originalbild ungeschnitten, kein Blickrichtungsfilter
            fn = f"img_{kept:03d}.jpg"
            view = img; tag = ctype or "perspective"
        elif ctype in ("spherical", "equirectangular"):
            view = reproject(img, head_to_bldg, a.pitch, a.fov)   # 360° → Ausschnitt
            fn = f"sv_{kept:02d}_360.jpg"; tag = "360"
        else:
            if cam is None or ang_diff(cam, head_to_bldg) > a.aim_tol:
                continue                                           # Kamera blickt weg
            view = img; fn = f"sv_{kept:02d}_persp.jpg"; tag = "persp"
        cv2.imwrite(os.path.join(a.out, fn), view)
        alt = (c[2] if len(c) > 2 else None)
        manifest.append({"file": fn, "mapillary_id": im["id"], "lat": ilat, "lon": ilon,
                         "alt": alt, "heading": round(head_to_bldg, 1), "cam_angle": cam,
                         "camera_type": ctype or "perspective", "tag": tag,
                         "captured_at": im.get("captured_at")})
        kept += 1

    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump({"target": [a.lat, a.lon], "source": "mapillary", "views": manifest}, f, indent=2)
    if not kept:
        print("Keine passenden Bilder — Radius/aim-tol erhöhen oder Ort hat keine Abdeckung.")
    else:
        print(f"\n{kept} fassaden-Views → {a.out}")
        print("Nächster Schritt: Hebel 6/7 (fenster_ml.py --out-mask, foto_displacement.py) auf sv_*.jpg")


if __name__ == "__main__":
    main()
