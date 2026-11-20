#!/usr/bin/env python3
"""
webfotos.py — Fotos eines Gebaeudes automatisch aus dem Netz sammeln -> Meshroom (GPU) -> 3D-Modell.

Ablauf (jede Stufe ist fortsetzbar, alles liegt in --work):
  1) SAMMELN   Wikimedia Commons: Kategorie (+Unterkategorien), Volltextsuche, Geosuche im Umkreis.
               Optional: Mapillary (env MAPILLARY_TOKEN), Flickr (env FLICKR_KEY, nur CC-Lizenzen).
  2) FILTERN   kleine Vorschau (500 px) laden, SIFT-Abgleich gegen Referenzfotos (Kategorie-Bilder):
               nur Fotos, die geometrisch zum Gebaeude passen (RANSAC-Inlier), Dubletten raus, S/W raus.
  3) LADEN     Treffer in 1280 px (Wikimedia-Standardgroesse, kein 429), hoefliche Pausen + Retry-After.
  4) MESHROOM  (--run) Feature-Extraktion auf der GPU, Exhaustive Matching, Textur als JPG.
  Quellen/Lizenzen landen in <work>/QUELLEN.csv (Namensnennung!).

Beispiel:
  python3 webfotos.py --name Martinstor --lat 47.99345 --lon 7.84912 \
      --category "Martinstor (Freiburg im Breisgau)" --search "Martinstor Freiburg" --run
"""
import argparse, csv, glob, hashlib, json, math, os, subprocess, sys, time
import urllib.parse, urllib.request
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np

UA = {"User-Agent": "rc-park-photogrammetry/0.3 (private non-commercial 3D reconstruction; python-urllib)"}
API = "https://commons.wikimedia.org/w/api.php"
PAUSE = float(os.environ.get("PAUSE", "2"))
MESHROOM = os.environ.get("MESHROOM", os.path.expanduser("~/3DScan/Tools/Meshroom-2023.3.0"))

def log(*a): print(*a, flush=True)

def http(url, tries=5):
    """GET mit Backoff (beachtet Retry-After bei 429/503)."""
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504): raise
            wait = int(e.headers.get("Retry-After") or 0) or 20 * (k + 1)
            log(f"  {e.code} -> warte {wait}s"); time.sleep(wait)
        except Exception as e:
            log(f"  {e} -> nochmal"); time.sleep(10 * (k + 1))
    raise RuntimeError("zu viele Fehlversuche: " + url)

def api(**p):
    return json.loads(http(API + "?" + urllib.parse.urlencode({**p, "format": "json"})))

# ---------------------------------------------------------------- 1) Sammeln
def commons_category(cat, depth=1):
    ids, cats, seen = set(), [cat], set()
    for _ in range(depth + 1):
        nxt = []
        for c in cats:
            if c in seen: continue
            seen.add(c); cont = {}
            while True:
                d = api(action="query", list="categorymembers", cmtitle="Category:" + c,
                        cmtype="file|subcat", cmlimit=500, **cont)
                for m in d["query"]["categorymembers"]:
                    if m["ns"] == 14: nxt.append(m["title"].split(":", 1)[1])
                    else: ids.add(m["pageid"])
                if "continue" not in d: break
                cont = {"cmcontinue": d["continue"]["cmcontinue"]}
        cats = [c for c in nxt if "history" not in c.lower()]  # historische Unterkategorien = S/W
    return ids

def commons_search(q):
    ids, off = set(), 0
    while off < 1000:
        d = api(action="query", list="search", srsearch=q, srnamespace=6, srlimit=500, sroffset=off)
        ids |= {r["pageid"] for r in d["query"]["search"]}
        if "continue" not in d: break
        off = d["continue"]["sroffset"]
    return ids

def commons_geo(lat, lon, radius):
    """Geosuche ist auf 500 Treffer begrenzt -> Umkreis in kleine Kreise kacheln."""
    ids, step = set(), max(30.0, radius / 3)
    n = int(radius // step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            if math.hypot(i, j) * step > radius + 1: continue
            la = lat + i * step / 110574.0
            lo = lon + j * step / (111320.0 * math.cos(math.radians(lat)))
            for k in range(6):  # CirrusSearch ist oft "too busy" -> Pause, nochmal
                d = api(action="query", list="geosearch", gsnamespace=6, gscoord=f"{la}|{lo}",
                        gsradius=int(step * 0.75) + 10, gslimit=500)
                if "query" in d: break
                time.sleep(15 * (k + 1))
            time.sleep(2)
            if "query" not in d: log("  Geosuche aufgegeben:", d.get("error", {}).get("code")); continue
            ids |= {g["pageid"] for g in d["query"]["geosearch"]}
    return ids

def commons_info(ids, width):
    out, ids = {}, sorted(ids)
    for i in range(0, len(ids), 50):
        d = api(action="query", pageids="|".join(map(str, ids[i:i + 50])), prop="imageinfo",
                iiprop="url|mime|extmetadata", iiurlwidth=width)
        for p in d["query"]["pages"].values():
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("mime") != "image/jpeg": continue
            md = ii.get("extmetadata", {})
            out[f"c{p['pageid']}"] = dict(src="commons", title=p["title"], url=ii.get("thumburl") or ii["url"],
                                         page=ii.get("descriptionurl", ""),
                                         author=md.get("Artist", {}).get("value", "")[:200],
                                         license=md.get("LicenseShortName", {}).get("value", ""))
        time.sleep(0.5)
    return out

def mapillary(lat, lon, radius, token):
    dl = radius / 110574.0; dn = radius / (111320.0 * math.cos(math.radians(lat)))
    q = urllib.parse.urlencode(dict(access_token=token, fields="id,thumb_2048_url,thumb_1024_url,creator",
                                    bbox=f"{lon-dn},{lat-dl},{lon+dn},{lat+dl}", limit=2000))
    d = json.loads(http("https://graph.mapillary.com/images?" + q))
    return {f"m{x['id']}": dict(src="mapillary", title=x["id"], url=x.get("thumb_2048_url"),
                                small=x.get("thumb_1024_url"), page=f"https://www.mapillary.com/app/?pKey={x['id']}",
                                author=(x.get("creator") or {}).get("username", ""), license="CC-BY-SA 4.0")
            for x in d.get("data", []) if x.get("thumb_2048_url")}

def flickr(lat, lon, radius, key, text):
    q = urllib.parse.urlencode(dict(method="flickr.photos.search", api_key=key, lat=lat, lon=lon,
                                    radius=max(0.05, radius / 1000), text=text, license="1,2,3,4,5,6,9,10",
                                    extras="url_l,url_m,owner_name,license", per_page=500,
                                    format="json", nojsoncallback=1))
    d = json.loads(http("https://api.flickr.com/services/rest/?" + q))
    return {f"f{x['id']}": dict(src="flickr", title=x.get("title", ""), url=x["url_l"], small=x.get("url_m"),
                                page=f"https://www.flickr.com/photos/{x['owner']}/{x['id']}",
                                author=x.get("ownername", ""), license=f"flickr-license-{x['license']}")
            for x in d.get("photos", {}).get("photo", []) if x.get("url_l")}

# ---------------------------------------------------------------- 2) Filtern
_sift = None
def feats(path):
    global _sift
    _sift = _sift or cv2.SIFT_create(nfeatures=2000)
    g = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if g is None: return None
    s = 500.0 / max(g.shape); g = cv2.resize(g, None, fx=s, fy=s) if s < 1 else g
    kp, des = _sift.detectAndCompute(g, None)
    if des is None or len(kp) < 30: return None
    return np.float32([k.pt for k in kp]), des

def inliers(a, b):
    m = cv2.BFMatcher(cv2.NORM_L2).knnMatch(a[1], b[1], k=2)
    good = [x[0] for x in m if len(x) == 2 and x[0].distance < 0.75 * x[1].distance]
    if len(good) < 15: return 0
    p1 = a[0][[g.queryIdx for g in good]]; p2 = b[0][[g.trainIdx for g in good]]
    _, mask = cv2.findFundamentalMat(p1, p2, cv2.FM_RANSAC, 2.0, 0.99)
    return int(mask.sum()) if mask is not None else 0

_refs = None
def _init(ref_paths):
    global _refs
    _refs = [f for f in (feats(p) for p in ref_paths) if f is not None]

def score(path):
    f = feats(path)
    if f is None: return path, 0
    return path, max((inliers(f, r) for r in _refs), default=0)

def colorful(path):
    im = cv2.imread(path)
    if im is None: return False
    return cv2.cvtColor(cv2.resize(im, (64, 64)), cv2.COLOR_BGR2HSV)[..., 1].mean() > 18

def ahash(path):
    g = cv2.resize(cv2.imread(path, cv2.IMREAD_GRAYSCALE), (16, 16), interpolation=cv2.INTER_AREA)
    return (g > g.mean()).flatten()

def fetch(cands, key, folder, label):
    os.makedirs(folder, exist_ok=True); n = 0
    for i, (cid, c) in enumerate(cands.items()):
        fn = os.path.join(folder, cid + ".jpg")
        if os.path.exists(fn): continue
        url = c.get(key) or c["url"]
        try:
            data = http(url); n += 1
            open(fn, "wb").write(data)
        except Exception as e:
            log(f"  {cid}: {e}")
        if (i + 1) % 25 == 0: log(f"  {label}: {i+1}/{len(cands)}")
        time.sleep(PAUSE if c["src"] == "commons" else 0.2)
    return n

# ---------------------------------------------------------------- Video (yt-dlp + ffmpeg)
def video_frames(urls, search, name, work, fps=3.0):
    """Videos (z.B. Drohnen-Orbits) -> scharfe Einzelbilder; EXIF Make/Model = Video-ID,
    damit Meshroom jedes Video als eigene Kamera kalibriert."""
    from PIL import Image
    vdir, out = os.path.join(work, "video"), os.path.join(work, "video_frames")
    os.makedirs(vdir, exist_ok=True); os.makedirs(out, exist_ok=True)
    ids = [u.split("v=")[-1].split("/")[-1] for u in urls]
    for q in search:  # nur Treffer, deren Titel den Gebaeudenamen enthaelt, max 3 min
        r = subprocess.run(["yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(duration)s\t%(title)s",
                            f"ytsearch15:{q}"], capture_output=True, text=True).stdout
        for line in r.splitlines():
            vid, dur, title = (line.split("\t") + ["", ""])[:3]
            if name.lower() in title.lower() and dur not in ("NA", "") and float(dur) <= 180: ids.append(vid)
    ids = list(dict.fromkeys(ids)); log(f"Videos: {len(ids)}")
    for vid in ids:
        if glob.glob(os.path.join(out, vid + "_*.jpg")): continue
        f = os.path.join(vdir, vid + ".mp4")
        subprocess.call(["yt-dlp", "-q", "--no-warnings", "-f", "bv*[height<=2160]", "--remux-video", "mp4",
                         "-o", f, "https://www.youtube.com/watch?v=" + vid])
        if not os.path.exists(f): continue
        raw = os.path.join(vdir, vid); os.makedirs(raw, exist_ok=True)
        subprocess.call(["ffmpeg", "-v", "error", "-i", f, "-vf", f"fps={fps},scale='min(2000,iw)':-2",
                         "-q:v", "2", os.path.join(raw, vid + "_%04d.jpg")])
        fs = sorted(glob.glob(os.path.join(raw, "*.jpg")))
        if not fs: continue
        sh = [cv2.Laplacian(cv2.imread(x, 0), cv2.CV_64F).var() for x in fs]
        ref, last, kept = np.percentile(sh, 60), None, 0
        for s, x in zip(sh, fs):
            if s < 0.5 * ref: continue  # unscharf
            g = cv2.resize(cv2.imread(x, 0), (32, 32)).astype(float)
            if last is not None and np.abs(g - last).mean() < 4: continue  # Standbild
            last = g
            ex = Image.Exif(); ex[271] = "YouTube"; ex[272] = vid
            Image.open(x).save(os.path.join(out, os.path.basename(x)), quality=93, exif=ex); kept += 1
        log(f"  {vid}: {kept}/{len(fs)} Frames")
    return out

# ---------------------------------------------------------------- 4) Meshroom
def meshroom(fotos, work):
    batch = os.path.join(MESHROOM, "meshroom_batch")
    out, cache = os.path.join(work, "modell"), os.path.join(work, "cache")
    os.makedirs(out, exist_ok=True)
    cmd = [batch, "--input", os.path.abspath(fotos), "--output", os.path.abspath(out),
           "--cache", os.path.abspath(cache), "--paramOverrides",
           "CameraInit:defaultFieldOfView=55",
           "FeatureExtraction:forceCpuExtraction=False",      # SIFT auf der GPU (Standard waere CPU!)
           "FeatureExtraction:describerTypes=sift", "FeatureExtraction:describerPreset=high",
           # Video-Frames: Nachbarn in Zeitfolge + VocTree; reine Fotos: jedes mit jedem
           *(["ImageMatching:method=SequentialAndVocabularyTree", "ImageMatching:nbNeighbors=12",
              "ImageMatching:nbMatches=60"] if len(os.listdir(fotos)) > 300 else ["ImageMatching:method=Exhaustive"]),
           "FeatureMatching:describerTypes=sift", "FeatureMatching:guidedMatching=True",
           "StructureFromMotion:describerTypes=sift",
           "DepthMap:downscale=1",                              # Tiefenkarten in voller Aufloesung (GPU)
           "Meshing:maxPoints=15000000", "Texturing:downscale=1", "Texturing:fillHoles=True"]
    log("Meshroom laeuft (GPU) ..."); t = time.time()
    rc = subprocess.call(cmd, stdout=open(os.path.join(work, "meshroom.log"), "w"), stderr=subprocess.STDOUT)
    log(f"Meshroom fertig: RC {rc}, {(time.time()-t)/60:.1f} min")
    sfm = glob.glob(os.path.join(cache, "StructureFromMotion", "*", "cameras.sfm"))
    if sfm:
        d = json.load(open(sfm[0]))
        log(f"ausgerichtet: {len(d.get('poses', []))} / {len(d['views'])} Fotos")
    for exr in glob.glob(os.path.join(out, "*.exr")):  # EXR -> JPG (Browser-Viewer zeigt EXR schwarz)
        env = dict(os.environ, LD_LIBRARY_PATH=f"{MESHROOM}/aliceVision/lib:{MESHROOM}/lib",
                   ALICEVISION_ROOT=f"{MESHROOM}/aliceVision")
        subprocess.call([f"{MESHROOM}/aliceVision/bin/aliceVision_imageProcessing", "--input", exr, "--output", out,
                         "--extension", "jpg", "--outputFormat", "rgb", "--outputColorSpace", "srgb",
                         "--maxWidth", "4096"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for mtl in glob.glob(os.path.join(out, "*.mtl")):
        s = open(mtl).read().replace(".exr", ".jpg"); open(mtl, "w").write(s)
    return out

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True)
    ap.add_argument("--lat", type=float, required=True); ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius", type=float, default=150, help="Geosuche-Umkreis in m")
    ap.add_argument("--category", action="append", default=[], help="Commons-Kategorie (= Referenzfotos)")
    ap.add_argument("--search", action="append", default=[], help="Commons-Volltextsuche")
    ap.add_argument("--work", default=None, help="Arbeitsordner (Standard /dev/shm/webscan/<name>)")
    ap.add_argument("--min-inliers", type=int, default=25)
    ap.add_argument("--video", action="append", default=[], help="YouTube-URL/ID (z.B. Drohnen-Orbit)")
    ap.add_argument("--video-search", action="append", default=[], help="YouTube-Suche (Titel muss --name enthalten)")
    ap.add_argument("--run", action="store_true", help="danach Meshroom starten")
    a = ap.parse_args()
    work = a.work or f"/dev/shm/webscan/{a.name}"
    os.makedirs(work, exist_ok=True)
    cfile = os.path.join(work, "kandidaten.json")

    # 1) Sammeln
    if os.path.exists(cfile):
        C = json.load(open(cfile)); log(f"{len(C)} Kandidaten aus Cache")
    else:
        ref_ids = set()
        for c in a.category: ref_ids |= commons_category(c)
        log(f"Kategorie: {len(ref_ids)}")
        ids = set(ref_ids)
        for q in a.search: ids |= commons_search(q)
        log(f"+ Suche: {len(ids)}")
        ids |= commons_geo(a.lat, a.lon, a.radius)
        log(f"+ Geosuche {a.radius:.0f} m: {len(ids)}")
        small = commons_info(ids, 500); big = commons_info(ids, 1280)
        C = {k: {**v, "small": small[k]["url"], "url": big.get(k, v)["url"],
                 "ref": int(k[1:]) in ref_ids} for k, v in small.items()}
        if os.environ.get("MAPILLARY_TOKEN"):
            M = mapillary(a.lat, a.lon, min(a.radius, 80), os.environ["MAPILLARY_TOKEN"]); C.update(M)
            log(f"+ Mapillary: {len(M)}")
        if os.environ.get("FLICKR_KEY"):
            F = flickr(a.lat, a.lon, a.radius, os.environ["FLICKR_KEY"], a.name); C.update(F)
            log(f"+ Flickr: {len(F)}")
        json.dump(C, open(cfile, "w"), indent=1)
        log(f"{len(C)} Kandidaten (JPEG)")

    # 2) Filtern: Vorschau laden, S/W raus, SIFT gegen Referenzen
    vdir = os.path.join(work, "vorschau")
    fetch(C, "small", vdir, "Vorschau")
    paths = {k: os.path.join(vdir, k + ".jpg") for k in C if os.path.exists(os.path.join(vdir, k + ".jpg"))}
    paths = {k: p for k, p in paths.items() if colorful(p)}
    refs = [p for k, p in paths.items() if C[k].get("ref")]
    log(f"{len(paths)} farbige Vorschauen, {len(refs)} Referenzen")
    with ProcessPoolExecutor(initializer=_init, initargs=(refs,)) as ex:
        S = dict(ex.map(score, paths.values(), chunksize=4))
    keep = {k for k, p in paths.items() if S[p] >= a.min_inliers}
    # Referenzen selbst muessen auch zu den anderen passen (Kategorie enthaelt Wappen-Details, Innenansichten ...)
    hashes, final = [], []
    for k in sorted(keep, key=lambda k: -S[paths[k]]):
        h = ahash(paths[k])
        if any((h != o).sum() < 12 for o in hashes): continue  # Dublette
        hashes.append(h); final.append(k)
    log(f"relevant: {len(final)} Fotos (min {a.min_inliers} Inlier), Rest verworfen")
    json.dump({k: S[paths[k]] for k in final}, open(os.path.join(work, "relevanz.json"), "w"), indent=1)

    # 3) Laden in gross
    fdir = os.path.join(work, "fotos")
    fetch({k: C[k] for k in final}, "url", fdir, "Fotos")
    with open(os.path.join(work, "QUELLEN.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["datei", "quelle", "titel", "autor", "lizenz", "seite"])
        for k in final: w.writerow([k + ".jpg", C[k]["src"], C[k]["title"], C[k]["author"], C[k]["license"], C[k]["page"]])
    log(f"{len(glob.glob(fdir + '/*.jpg'))} Fotos in {fdir}, Quellen in QUELLEN.csv")

    # Video-Frames dazu (gleicher Ordner -> ein gemeinsamer Meshroom-Lauf)
    if a.video or a.video_search:
        vf = video_frames(a.video, a.video_search, a.name, work)
        for f in glob.glob(vf + "/*.jpg"):
            dst = os.path.join(fdir, os.path.basename(f))
            if not os.path.exists(dst): os.link(f, dst)
        log(f"{len(glob.glob(fdir + '/*.jpg'))} Bilder gesamt (Fotos + Video-Frames)")

    # 4) Meshroom
    if a.run:
        out = meshroom(fdir, work)
        log(f"Modell: {out}/texturedMesh.obj")

if __name__ == "__main__":
    main()
