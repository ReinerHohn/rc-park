#!/usr/bin/env python3
"""bilder_holen.py - PIPELINE-SCHRITT: Fotos einer Attraktion aus freien Quellen holen - nur die mit MEHRWERT fuer die Fotowolke.

Konfiguration als DATEN in objekt.json["bildquellen"]:
  {"commons": {"kategorien": [...], "suchen": [...], "geosearch_radius_m": 200, "titel_enthaelt": ["Martinstor", "Martin's Gate"]},
   "mapillary": {"radius_m": 80, "max": 200},             # braucht Token (~/.config/mapillary_token), sonst wird die Quelle gemeldet und uebersprungen
   "videos": [{"url": "...", "lizenz": "..."}],             # nur mit --mit-video (Urheberrecht: keine CC-Quelle)
   "ausgabe": "daten/<objekt>/fotos_eingang", "max_neu": 120, "min_breite_px": 1000, "max_je_blickgruppe": 4}
Lage der Attraktion: anker3d.json mitte_utm (EPSG:25832) -> WGS84 (fuer Geosearch/Mapillary).

Auswahl (Mehrwert statt Masse) - alles auf kleinen Vorschaubildern (640 px), bevor etwas in voller Groesse geladen wird:
  1. Kandidaten: Commons-Kategorien + Volltextsuchen + Geosearch (Titel muss eines der Stichworte enthalten). Schon vorhandene Titel
     (manifest.json des Fotoordners und frueherer Eingaenge) fallen weg. Lizenz + Autor je Bild (Pflicht).
  2. Guete: Originalbreite >= min_breite_px, Schaerfe (Laplace-Varianz) ueber Schwelle.
  3. Aehnlichkeit: Bildhash (pHash, Hamming) und ORB-Merkmale mit Homographie gegen die vorhandenen Fotos UND die schon gewaehlten:
       dup      Hamming <= 6 oder Inlier-Anteil > 0,85 bei fast identischer Abbildung -> nur das bessere (Aufloesung x Schaerfe) bleibt
       aehnlich Inlier-Anteil 0,25..0,85 (ueberlappend, aber mit Parallaxe) -> wertvoll fuers Netz, gedeckelt: max_je_blickgruppe
       neu      sonst -> neuer Blickwinkel, immer (sofern Guete ok)
  4. Blickrichtung, wenn GPS vorhanden: Peilung Kamera -> Objekt im Modellrahmen (anker3d xhat/yhat) -> seite_vorschlag (nord/sued/ost/west);
     Seiten mit wenigen vorhandenen Fotos bekommen Vorrang. Ohne GPS: Seite unbekannt (entscheidet spaeter die Seitentrennung im SfM).
  5. Gewinner in voller Breite laden (Standard 2048 px, Original wenn kleiner), Manifest mit Quelle/Lizenz/Autor/URL/Klasse/aehnlich_zu/
     Score; Bericht mit Zaehlern je Quelle, Klasse, Lizenz, Seite. Nichts wird einsortiert - Nummernvergabe und Seitenzuordnung sind
     der naechste Schritt (objekt.json fotos/sfm), damit laufende Netze unberuehrt bleiben.
  /media/oem/scan/venv-seg/bin/python -W ignore -I tools/bilder_holen.py modelle/<objekt>/objekt.json [--nur-kandidaten] [--mit-video] [--max-neu 120]
"""
import sys, os, json, math, hashlib, argparse, time, urllib.request, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def utm_zu_wgs84(E, N, zone=32):
    """UTM (WGS84-Ellipsoid) -> (lat, lon) in Grad; Standardformeln (Karney/Snyder, ausreichend < 1 m)."""
    a = 6378137.0; f = 1 / 298.257223563; k0 = 0.9996; e2 = f * (2 - f); ep2 = e2 / (1 - e2)
    x = E - 500000.0; y = N; lon0 = math.radians((zone - 1) * 6 - 180 + 3)
    M = y / k0; mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
    N1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2); T1 = math.tan(phi1) ** 2; C1 = ep2 * math.cos(phi1) ** 2; R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5; D = x / (N1 * k0)
    lat = phi1 - (N1 * math.tan(phi1) / R1) * (D ** 2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * ep2) * D ** 4 / 24 + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * ep2 - 3 * C1 ** 2) * D ** 6 / 720)
    lon = lon0 + (D - (1 + 2 * T1 + C1) * D ** 3 / 6 + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * ep2 + 24 * T1 ** 2) * D ** 5 / 120) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)

def wgs84_zu_utm(lat, lon, zone=32):
    a = 6378137.0; f = 1 / 298.257223563; k0 = 0.9996; e2 = f * (2 - f); ep2 = e2 / (1 - e2)
    phi, lam = math.radians(lat), math.radians(lon); lam0 = math.radians((zone - 1) * 6 - 180 + 3)
    N = a / math.sqrt(1 - e2 * math.sin(phi) ** 2); T = math.tan(phi) ** 2; C = ep2 * math.cos(phi) ** 2; A = math.cos(phi) * (lam - lam0)
    M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi) + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi) - (35 * e2 ** 3 / 3072) * math.sin(6 * phi))
    E = k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T ** 2 + 72 * C - 58 * ep2) * A ** 5 / 120) + 500000.0
    Nn = k0 * (M + N * math.tan(phi) * (A ** 2 / 2 + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24 + (61 - 58 * T + T ** 2 + 600 * C - 330 * ep2) * A ** 6 / 720))
    return E, Nn

def phash(gray):
    import cv2
    g = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32); d = cv2.dct(g)[:8, :8]; m = np.median(d[1:, 1:]); return (d > m).flatten()

def hamming(a, b): return int(np.count_nonzero(a != b))

def lade_bild(url, pfad):
    if os.path.exists(pfad): return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rcpark-landmark/1.0 (3d-print research; contact via opmd1988@googlemail.com)"})
        data = urllib.request.urlopen(req, timeout=60).read(); open(pfad, "wb").write(data); return True
    except Exception as e:
        print("   Download fehlgeschlagen:", url[:80], e); return False

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--nur-kandidaten", action="store_true"); ap.add_argument("--mit-video", action="store_true"); ap.add_argument("--max-neu", type=int); ap.add_argument("--breite", type=int, default=2048)
    a = ap.parse_args(); import cv2; import commons_harvest as CH
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od)); Q = obj.get("bildquellen")
    if not Q: sys.exit("objekt.json['bildquellen'] fehlt (Kategorien/Suchen/Stichworte als Daten)")
    A3 = json.load(open(os.path.join(od, "anker3d.json"))); E0, N0 = A3["mitte_utm"]; lat, lon = utm_zu_wgs84(E0, N0); xh, yh = np.array(A3["xhat_utm"]), np.array(A3["yhat_utm"])
    aus = os.path.join(repo, Q.get("ausgabe", f"daten/{os.path.basename(od)}/fotos_eingang")); th = os.path.join(aus, "_vorschau"); os.makedirs(th, exist_ok=True)
    max_neu = a.max_neu or Q.get("max_neu", 120); min_b = Q.get("min_breite_px", 1000); max_grp = Q.get("max_je_blickgruppe", 4); min_sharp = Q.get("min_schaerfe", 40.0)
    print(f"Objekt {obj.get('name')}: {lat:.5f} N {lon:.5f} E; Ausgabe {os.path.relpath(aus, repo)}")
    # ---- vorhandene Titel (nicht nochmal) + vorhandene Fotos als Vergleichsbasis
    bekannt = set(); vorhanden_mf = os.path.join(repo, obj["fotos_dir"], "manifest.json")
    for mp in [vorhanden_mf, os.path.join(aus, "manifest.json")]:
        if os.path.exists(mp):
            M = json.load(open(mp)); items = M.get("images") or M.get("bilder") or []
            for it in (items.values() if isinstance(items, dict) else items):
                t = it.get("title") or it.get("titel") or (it if isinstance(it, str) else None)
                if t: bekannt.add(t)
    # ---- 1. Kandidaten (Commons)
    C = Q.get("commons", {}); titel = []
    for cat in C.get("kategorien", []): t = CH.category_files(cat, 2000); print(f"  Kategorie {cat}: {len(t)}"); titel += t
    for s in C.get("suchen", []): t = CH.fulltext(s, 500); print(f"  Suche '{s}': {len(t)}"); titel += t
    stich = [w.lower() for w in C.get("titel_enthaelt", [])]
    if C.get("geosearch_radius_m"):
        g = CH.geosearch(lat, lon, C["geosearch_radius_m"], 2000); gf = [t for t in g if not stich or any(w in t.lower() for w in stich)]; print(f"  Geosearch {C['geosearch_radius_m']} m: {len(g)} (mit Stichwort {len(gf)})"); titel += gf
    titel = [t for t in dict.fromkeys(titel) if t not in bekannt and t.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))]
    print(f"  Kandidaten neu: {len(titel)} (bekannt uebersprungen: {len(bekannt)})")
    info = CH.image_info(titel, 640)
    kand = []
    for t, i in info.items():
        if not i.get("orig_w") or i["orig_w"] < min_b: continue
        kand.append(dict(title=t, **i))
    print(f"  mit Breite >= {min_b} px: {len(kand)}")
    if a.nur_kandidaten:
        json.dump(kand, open(os.path.join(aus, "kandidaten.json"), "w"), indent=1, ensure_ascii=False); print("nur Kandidaten geschrieben"); return
    # ---- Vorschaubilder + Guete + Hash + Merkmale
    orb = cv2.ORB_create(1500); bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    def merkmale(pfad):
        im = cv2.imread(pfad)
        if im is None: return None
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); s = max(640 / max(g.shape), 0.01); g = cv2.resize(g, None, fx=s, fy=s) if s < 1 else g
        kp, de = orb.detectAndCompute(g, None); return dict(sharp=float(cv2.Laplacian(g, cv2.CV_64F).var()), ph=phash(g), kp=kp, de=de, form=g.shape)
    def inlier_anteil(A, B):
        if A["de"] is None or B["de"] is None or len(A["kp"]) < 30 or len(B["kp"]) < 30: return 0.0, 0.0
        m = bf.knnMatch(A["de"], B["de"], k=2); gut = [x[0] for x in m if len(x) == 2 and x[0].distance < 0.75 * x[1].distance]
        if len(gut) < 15: return 0.0, 0.0
        p1 = np.float32([A["kp"][x.queryIdx].pt for x in gut]); p2 = np.float32([B["kp"][x.trainIdx].pt for x in gut])
        H, mask = cv2.findHomography(p1, p2, cv2.RANSAC, 5.0)
        if H is None: return 0.0, 0.0
        inl = int(mask.sum()); ident = float(np.abs(H - np.eye(3)).max()) if H[2, 2] else 9.0
        return inl / min(len(A["kp"]), len(B["kp"])), ident
    basis = []                                                                              # vorhandene Fotos als Vergleich (Vorschau-Cache)
    for f in sorted(os.listdir(os.path.join(repo, obj["fotos_dir"]))):
        if not f.lower().endswith((".jpg", ".jpeg", ".png")): continue
        pv = os.path.join(th, "basis_" + f + ".jpg")
        if not os.path.exists(pv):
            im = cv2.imread(os.path.join(repo, obj["fotos_dir"], f)); s = 640 / max(im.shape[:2]); cv2.imwrite(pv, cv2.resize(im, None, fx=s, fy=s) if s < 1 else im)
        mk = merkmale(pv)
        if mk: mk["name"] = f; basis.append(mk)
    # Seitenstatistik der vorhandenen Fotos (fuer Vorrang schwach belegter Seiten)
    seiten_vorhanden = {}
    for nr, fi in (obj.get("fotos") or {}).items():
        s = str(fi.get("seite", "")).lower()
        if s: seiten_vorhanden[s] = seiten_vorhanden.get(s, 0) + 1
    print(f"  Vergleichsbasis: {len(basis)} vorhandene Fotos; Seiten vorhanden: {seiten_vorhanden}")
    def seite_aus_gps(glat, glon):
        E, N = wgs84_zu_utm(glat, glon); d = np.array([E - E0, N - N0]); x, y = float(d @ xh), float(d @ yh)   # Modellrahmen: +x Sued, +y Ost
        if math.hypot(x, y) < 3: return None, None
        s = ("sued" if x > 0 else "nord") if abs(x) >= abs(y) else ("ost" if y > 0 else "west"); return s, round(math.hypot(x, y), 1)
    rows = []
    for k in kand:
        pv = os.path.join(th, hashlib.md5(k["title"].encode()).hexdigest() + ".jpg")
        if not lade_bild(k["url"], pv): continue
        mk = merkmale(pv)
        if not mk: continue
        k.update(sharp=round(mk["sharp"], 1)); k["_mk"] = mk
        if mk["sharp"] < min_sharp: k["klasse"] = "unscharf"; rows.append(k); continue
        # Aehnlichkeit gegen Basis
        best_b = max(((inlier_anteil(mk, b), b["name"]) for b in basis), default=((0.0, 9.0), None), key=lambda q: q[0][0])
        k["aehnlich_basis"] = dict(name=best_b[1], inlier=round(best_b[0][0], 3)) if best_b[1] else None
        k["guete"] = float(k["orig_w"]) * math.log10(max(mk["sharp"], 1.0))
        rows.append(k)
    # ---- Auswahl: beste Guete zuerst; Klassen gegen Basis + bereits Gewaehlte
    gew = []; gruppen = {}
    for k in sorted([r for r in rows if r.get("klasse") != "unscharf"], key=lambda r: -r["guete"]):
        mk = k["_mk"]; klasse = "neu"; bezug = None; dup_von = None
        for other in gew + basis:
            omk = other["_mk"] if "_mk" in other else other
            hd = hamming(mk["ph"], omk["ph"])
            if hd <= 6: klasse, dup_von = "dup", other.get("title") or other.get("name"); break
        if klasse != "dup":
            best = (0.0, None)
            for other in gew:
                ia, ident = inlier_anteil(mk, other["_mk"])
                if ia > best[0]: best = (ia, other["title"])
                if ia > 0.85 and ident < 0.08: klasse, dup_von = "dup", other["title"]; break
            if klasse != "dup":
                ib = k["aehnlich_basis"]["inlier"] if k.get("aehnlich_basis") else 0.0
                if max(best[0], ib) >= 0.25: klasse, bezug = "aehnlich", (best[1] if best[0] >= ib else k["aehnlich_basis"]["name"])
        k["klasse"] = klasse; k["aehnlich_zu"] = bezug or dup_von
        if klasse == "dup": continue
        if klasse == "aehnlich":
            g = bezug; gruppen[g] = gruppen.get(g, 0) + 1
            if gruppen[g] > max_grp: k["klasse"] = "aehnlich_ueberzaehlig"; continue
        if len(gew) >= max_neu: k["klasse"] = "ueber_max"; continue
        gew.append(k)
    # ---- Gewinner in voller Breite laden + Manifest
    voll = CH.image_info([k["title"] for k in gew], a.breite) if gew else {}
    man = dict(source="bilder_holen (Commons)", stand=time.strftime("%Y-%m-%d"), objekt=obj.get("name"), lat=lat, lon=lon, images=[])
    for k in gew:
        v = voll.get(k["title"], {}); name = "neu_" + hashlib.md5(k["title"].encode()).hexdigest()[:10] + os.path.splitext(k["title"])[1].lower().replace(".jpeg", ".jpg")
        if not lade_bild(v.get("url") or k["url"], os.path.join(aus, name)): continue
        man["images"].append(dict(file=name, title=k["title"], url=v.get("url") or k["url"], license=k["license"], artist=k["artist"], orig_w=k["orig_w"], orig_h=k["orig_h"], sharp=k["sharp"], klasse=k["klasse"], aehnlich_zu=k.get("aehnlich_zu"), aehnlich_basis=k.get("aehnlich_basis"), guete=round(k["guete"], 1), exif_f35=k.get("exif_f35"), exif_model=k.get("exif_model"), seite_vorschlag=None))
    json.dump(man, open(os.path.join(aus, "manifest.json"), "w"), indent=1, ensure_ascii=False)
    z = {}
    for r in rows: z[r.get("klasse", "?")] = z.get(r.get("klasse", "?"), 0) + 1
    liz = {}
    for it in man["images"]: liz[it["license"]] = liz.get(it["license"], 0) + 1
    bericht = dict(kandidaten=len(kand), klassen=z, geladen=len(man["images"]), lizenzen=liz, max_neu=max_neu, max_je_blickgruppe=max_grp, quellen=dict(commons=True, mapillary="kein Token" if not (os.path.exists(os.path.expanduser("~/.config/mapillary_token")) or os.environ.get("MAPILLARY_TOKEN")) else "moeglich", video="nur mit --mit-video (Urheberrecht)"))
    json.dump(bericht, open(os.path.join(aus, "bericht.json"), "w"), indent=1, ensure_ascii=False)
    print(f"\nAuswahl: {len(man['images'])} geladen von {len(kand)} Kandidaten; Klassen {z}; Lizenzen {liz}")
    print(f"Manifest: {os.path.join(aus, 'manifest.json')}  Bericht: {os.path.join(aus, 'bericht.json')}")

if __name__ == "__main__":
    main()
