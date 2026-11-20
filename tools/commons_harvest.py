#!/usr/bin/env python3
"""commons_harvest.py — Wikimedia-Commons-Foto-Ernte für datenreiche Wahrzeichen.
Für den "Internet-Foto-Photogrammetrie"-Ansatz: ein weltberühmtes Gebäude hat
hunderte/tausende FREI LIZENZIERTE Fotos aus allen Winkeln → Open-Source-SfM
(opensfm_run.py / COLMAP) baut daraus ein extrem detailliertes Modell.

Kein API-Key nötig. Zwei Suchwege (kombinierbar):
  • geosearch  — alle File-Seiten im Radius um lat/lon (gilt für jedes Wahrzeichen)
  • category   — Commons-Kategorie (z.B. "Freiburg Minster"); meist bessere Treffer

Erfasst PFLICHT für legale Nutzung: Lizenz + Autor je Bild im manifest.json
(Commons = frei, aber oft Namensnennung/Share-Alike → Attribution mitschreiben).

  python3 tools/commons_harvest.py --lat 47.99556 --lon 7.85250 --radius 150 \
      --category "Freiburg Minster" --max 300 --width 2048 \
      --out daten/muenster/commons
"""
import argparse, os, sys, json, time, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "rcpark-landmark/1.0 (3d-print research; contact via opmd1988@googlemail.com)"


def api(params):
    params = {**params, "format": "json"}
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=40).read())


def geosearch(lat, lon, radius, limit):
    """File-Seiten im Umkreis (namespace 6)."""
    out, cont = [], None
    while len(out) < limit:
        p = {"action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}",
             "gsradius": min(radius, 10000), "gsnamespace": 6, "gslimit": 500}
        if cont: p["gscontinue"] = cont
        d = api(p)
        out += [g["title"] for g in d.get("query", {}).get("geosearch", [])]
        cont = d.get("continue", {}).get("gscontinue")
        if not cont: break
    return out[:limit]


def search_files(query, limit):
    """Volltext-Suche in Datei-Namespace (robuster als Kategorie/Geosearch)."""
    out, off = [], 0
    while len(out) < limit:
        d = api({"action": "query", "list": "search", "srsearch": query,
                 "srnamespace": 6, "srlimit": 50, "sroffset": off})
        hits = d.get("query", {}).get("search", [])
        out += [h["title"] for h in hits]
        off = d.get("continue", {}).get("sroffset")
        if not off: break
    return out[:limit]


def category_files(cat, limit):
    """alle Datei-Mitglieder einer Kategorie (rekursiv 1 Ebene)."""
    cat = cat if cat.lower().startswith("category:") else f"Category:{cat}"
    out, cont = [], None
    while len(out) < limit:
        p = {"action": "query", "list": "categorymembers", "cmtitle": cat,
             "cmtype": "file|subcat", "cmlimit": 500}
        if cont: p["cmcontinue"] = cont
        d = api(p)
        for m in d.get("query", {}).get("categorymembers", []):
            if m["title"].lower().startswith("category:"):
                continue                               # Unterkategorien hier ignorieren
            out.append(m["title"])
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont: break
    return out[:limit]


def image_info(titles, width):
    """URL + Lizenz/Autor je Titel (in 50er-Batches)."""
    info = {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i+50]
        d = api({"action": "query", "titles": "|".join(batch), "prop": "imageinfo",
                 "iiprop": "url|extmetadata|mime|size", "iiurlwidth": width})
        for pg in d.get("query", {}).get("pages", {}).values():
            ii = (pg.get("imageinfo") or [None])[0]
            if not ii or not ii.get("mime", "").startswith("image"):
                continue
            em = ii.get("extmetadata", {})
            info[pg["title"]] = {
                "url": ii.get("thumburl") or ii.get("url"),
                "w": ii.get("thumbwidth") or ii.get("width"),
                "h": ii.get("thumbheight") or ii.get("height"),
                "license": (em.get("LicenseShortName", {}) or {}).get("value", "?"),
                "artist": (em.get("Artist", {}) or {}).get("value", "?")[:120],
            }
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--radius", type=float, default=150, help="Geosearch-Radius [m]")
    ap.add_argument("--category", default="", help="Commons-Kategorie")
    ap.add_argument("--search", default="", help="Volltext-Suche (robustester Weg)")
    ap.add_argument("--max", type=int, default=300)
    ap.add_argument("--width", type=int, default=2048, help="Zielbreite [px]")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    titles = []
    if a.search:
        titles += search_files(a.search, a.max)
        print(f"  Suche '{a.search}': {len(titles)} Dateien")
    if a.category:
        titles += category_files(a.category, a.max)
        print(f"  Kategorie '{a.category}': {len(titles)} Dateien")
    if a.lat is not None and a.lon is not None:
        g = geosearch(a.lat, a.lon, a.radius, a.max)
        print(f"  Geosearch {a.radius} m: {len(g)} Dateien")
        titles += g
    titles = list(dict.fromkeys(titles))[:a.max]        # dedup, Reihenfolge erhalten
    if not titles:
        sys.exit("Nichts gefunden — Kategorie/Koordinate/Radius prüfen.")
    # nur Rasterbilder
    titles = [t for t in titles if t.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))]
    print(f"  {len(titles)} Bildkandidaten → hole URLs/Lizenzen ...")
    info = image_info(titles, a.width)

    manifest, n = [], 0
    for t, meta in info.items():
        if not meta["url"]: continue
        safe = t.replace("File:", "").replace(" ", "_")
        safe = "".join(c for c in safe if c.isalnum() or c in "._-")[:80]
        dst = os.path.join(a.out, f"{n:03d}_{safe}")
        try:
            req = urllib.request.Request(meta["url"], headers={"User-Agent": UA})
            open(dst, "wb").write(urllib.request.urlopen(req, timeout=60).read())
        except Exception as ex:
            print(f"  dl-err {t[:40]}: {ex}"); continue
        manifest.append({"file": os.path.basename(dst), "title": t, **meta})
        n += 1
        if n % 25 == 0:
            print(f"  {n} geladen ..."); time.sleep(0.3)
    json.dump({"source": "wikimedia_commons", "query": {"lat": a.lat, "lon": a.lon,
              "radius": a.radius, "category": a.category}, "images": manifest},
              open(os.path.join(a.out, "manifest.json"), "w"), indent=2, ensure_ascii=False)
    lics = {}
    for m in manifest: lics[m["license"]] = lics.get(m["license"], 0) + 1
    print(f"\n{n} frei lizenzierte Fotos → {a.out}")
    print(f"Lizenzen: {lics}")
    print("Nächster Schritt: tools/opensfm_run.py --images <out> ...  (oder COLMAP)")
    print("ACHTUNG Attribution: manifest.json führt Autor+Lizenz je Bild (Namensnennung wahren).")


if __name__ == "__main__":
    main()
