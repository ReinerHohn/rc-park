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
             "gsradius": min(radius, 10000), "gsnamespace": 6, "gslimit": 500, "gsprimary": "all"}   # ohne gsprimary=all: 0 Treffer (Martinstor 2026-11-01)
        if cont: p["gscontinue"] = cont
        d = api(p)
        out += [g["title"] for g in d.get("query", {}).get("geosearch", [])]
        cont = d.get("continue", {}).get("gscontinue")
        if not cont: break
    return out[:limit]


def fulltext(query, limit):
    """Volltextsuche im Datei-Namensraum (srlimit max. 50 je Anfrage)."""
    out, cont = [], {}
    while len(out) < limit:
        d = api({"action": "query", "list": "search", "srsearch": query, "srnamespace": 6, "srlimit": 50, **cont})
        out += [x["title"] for x in d.get("query", {}).get("search", [])]
        cont = d.get("continue")
        if not cont: break
    return out[:limit]


def category_files(cat, limit, tiefe=0):
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
                if tiefe > 0: out += category_files(m["title"], limit - len(out), tiefe - 1)      # 16.11.2026: Unterkategorien mitnehmen (--tiefe)
                continue
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
                 "iiprop": "url|extmetadata|mime|size|metadata", "iiurlwidth": width})
        for pg in d.get("query", {}).get("pages", {}).values():
            ii = (pg.get("imageinfo") or [None])[0]
            if not ii or not ii.get("mime", "").startswith("image"):
                continue
            em = ii.get("extmetadata", {})
            # EXIF aus der API: verkleinerte Commons-Thumbnails tragen KEIN EXIF mehr - fuer SfM-Brennweiten-Prior hier mitschreiben
            md = {m.get("name"): m.get("value") for m in (ii.get("metadata") or []) if isinstance(m, dict)}
            def num(v):
                try: return float(v)
                except Exception:
                    try: a, b = str(v).split("/"); return float(a) / float(b)
                    except Exception: return None
            info[pg["title"]] = {
                "url": ii.get("thumburl") or ii.get("url"),
                "w": ii.get("thumbwidth") or ii.get("width"),
                "h": ii.get("thumbheight") or ii.get("height"),
                "orig_w": ii.get("width"), "orig_h": ii.get("height"),
                "license": (em.get("LicenseShortName", {}) or {}).get("value", "?"),
                "artist": (em.get("Artist", {}) or {}).get("value", "?")[:120],
                "exif_model": (str(md.get("Model") or "").strip() or None),
                "exif_f_mm": num(md.get("FocalLength")), "exif_f35": num(md.get("FocalLengthIn35mmFilm")),
            }
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float); ap.add_argument("--lon", type=float)
    ap.add_argument("--radius", type=float, default=150, help="Geosearch-Radius [m]")
    ap.add_argument("--category", default="", help="Commons-Kategorie")
    ap.add_argument("--max", type=int, default=300)
    ap.add_argument("--tiefe", type=int, default=0, help="Unterkategorien so viele Ebenen tief mitnehmen; mehrere Kategorien mit | trennen")
    ap.add_argument("--pause", type=float, default=0.5, help="Sekunden zwischen zwei Bildern (Wikimedia drosselt Serien: 3-5 s und Standardbreiten 1280/1920 nehmen)")
    ap.add_argument("--width", type=int, default=2048, help="Zielbreite [px]")
    ap.add_argument("--out", required=True)
    ap.add_argument("--search", default="", help="Volltextsuche im Datei-Namensraum, z. B. 'Martinstor Freiburg'")
    ap.add_argument("--titel-enthaelt", default="", help="nur Titel mit diesem Text (Geosearch liefert sonst alles im Umkreis)")
    ap.add_argument("--skip-manifest", nargs="*", default=[], help="manifest.json frueherer Ernten: diese Titel nicht noch einmal laden")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    titles = []
    if a.category:
        for c_ in a.category.split("|"): titles += category_files(c_, a.max, a.tiefe)
        print(f"  Kategorie '{a.category}': {len(titles)} Dateien")
    if a.search:
        s = fulltext(a.search, a.max); print(f"  Volltext '{a.search}': {len(s)} Dateien"); titles += s
    if a.lat is not None and a.lon is not None:
        g = geosearch(a.lat, a.lon, a.radius, a.max)
        if a.titel_enthaelt: g = [t for t in g if a.titel_enthaelt.lower() in t.lower()]
        print(f"  Geosearch {a.radius} m: {len(g)} Dateien" + (f" (Titel enthaelt '{a.titel_enthaelt}')" if a.titel_enthaelt else ""))
        titles += g
    titles = list(dict.fromkeys(titles))[:a.max]        # dedup, Reihenfolge erhalten
    bekannt = set()
    for mp in a.skip_manifest:
        try: bekannt |= {m["title"] for m in json.load(open(mp))["images"]}
        except Exception as ex: print(f"  skip-manifest {mp}: {ex}")
    if bekannt:
        vorher = len(titles); titles = [t for t in titles if t not in bekannt]; print(f"  {vorher - len(titles)} schon vorhanden (skip-manifest), {len(titles)} neu")
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
        safe = "".join(c for c in safe if c.isalnum() or c in "._-"); stamm_, ext_ = os.path.splitext(safe)
        safe = stamm_[:max(1, 80 - len(ext_))] + ext_      # 19.11.2026 (Martinstor, 75 LABW-Bilder): der Schnitt auf 80 Zeichen nahm langen Titeln die Endung - Vorpruefung und SfM sahen die Dateien nie
        dst = os.path.join(a.out, f"{n:03d}_{safe}")
        daten = None
        for versuch in range(4):                                   # 429 (Ratenlimit) mit Wartezeit wiederholen; Datei erst nach Erfolg schreiben
            try:
                req = urllib.request.Request(meta["url"], headers={"User-Agent": UA})
                daten = urllib.request.urlopen(req, timeout=60).read(); break
            except urllib.error.HTTPError as ex:
                if ex.code == 429 and versuch < 3: time.sleep(60 * (versuch + 1)); continue
                print(f"  dl-err {t[:40]}: {ex}"); break
            except Exception as ex:
                print(f"  dl-err {t[:40]}: {ex}"); break
        if daten is None: continue
        open(dst, "wb").write(daten); time.sleep(a.pause)
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
    if n == 0:                                                            # 17.11.2026: 0 geladene Bilder (Drosselung 429, keine freie Lizenz, keine Rasterbilder) endeten mit rc 0
        print(f"FEHLER: KEIN Bild geladen ({len(titles)} Kandidaten, {len(info)} mit Bildinfo) - Drosselung/Lizenzfilter pruefen"); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
