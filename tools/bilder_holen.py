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
    # ---- Vorschaubilder (1024 px) + Guete + Hash + gelernte Merkmale (ALIKED + LightGlue, GPU; Lizenz: Apache/BSD, siehe LIZENZ_WERKZEUGE.md)
    import torch; from lightglue import LightGlue, ALIKED; from lightglue.utils import load_image
    dev = "cuda" if torch.cuda.is_available() else "cpu"; ext = ALIKED(max_num_keypoints=2048).eval().to(dev); matcher = LightGlue(features="aliked").eval().to(dev)
    print(f"  Matcher ALIKED+LightGlue auf {dev}")
    def merkmale(pfad):
        im = cv2.imread(pfad)
        if im is None: return None
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); s_ = 1024 / max(g.shape); g = cv2.resize(g, None, fx=s_, fy=s_) if s_ < 1 else g
        with torch.no_grad(): f = ext.extract(load_image(pfad, resize=1024).to(dev))
        return dict(sharp=float(cv2.Laplacian(g, cv2.CV_64F).var()), ph=phash(g), f=f, kp=f["keypoints"][0].cpu().numpy())
    def inlier(A, B):
        """Zahl geometrisch bestaetigter Zuordnungen (LightGlue + Fundamentalmatrix-RANSAC) - Mass fuer 'gleiches Objekt, ueberlappende Sicht'."""
        with torch.no_grad(): m = matcher({"image0": A["f"], "image1": B["f"]})
        idx = m["matches"][0].cpu().numpy()
        if len(idx) < 12: return 0
        p1, p2 = A["kp"][idx[:, 0]], B["kp"][idx[:, 1]]; F, mask = cv2.findFundamentalMat(p1, p2, cv2.FM_RANSAC, 2.0, 0.999)
        return int(mask.sum()) if mask is not None else 0
    basis = []
    for f in sorted(os.listdir(os.path.join(repo, obj["fotos_dir"]))):
        if not f.lower().endswith((".jpg", ".jpeg", ".png")): continue
        pv = os.path.join(th, "basis_" + f + ".jpg")
        if not os.path.exists(pv):
            im = cv2.imread(os.path.join(repo, obj["fotos_dir"], f)); s_ = 1024 / max(im.shape[:2]); cv2.imwrite(pv, cv2.resize(im, None, fx=s_, fy=s_) if s_ < 1 else im)
        mk = merkmale(pv)
        if mk: mk["name"] = f; mk["seite"] = str((obj.get("fotos") or {}).get(f.split("_")[0], {}).get("seite", "")).lower(); basis.append(mk)
    # Schwellen aus den VORHANDENEN Fotos kalibrieren (gleiches Objekt): Inlier zwischen Basisfotos derselben Seite = 'aehnlich/ueberlappend',
    # ueber Seiten hinweg = 'gleiches Objekt, andere Sicht'. T_rel = p10 aller Basispaare mit Inliern > 0 ... konservativ: feste Untergrenze 20
    paare_gleich, paare_alle = [], []
    for i in range(len(basis)):
        for j in range(i + 1, len(basis)):
            n = inlier(basis[i], basis[j]); paare_alle.append(n)
            if basis[i]["seite"] and basis[i]["seite"] == basis[j]["seite"]: paare_gleich.append(n)
    pa, pg = np.array(paare_alle), np.array(paare_gleich)
    T_rel = max(20, int(np.percentile(pa[pa > 0], 10))) if (pa > 0).sum() > 10 else 20
    T_sim = max(T_rel * 2, int(np.percentile(pg[pg > 0], 50))) if (pg > 0).sum() > 10 else T_rel * 3
    print(f"  Kalibrierung an {len(basis)} Basisfotos: Paare gesamt {len(pa)} (Inlier p10/p50/p90 {np.percentile(pa,[10,50,90]).astype(int).tolist()}), gleiche Seite {len(pg)} (p50 {int(np.median(pg)) if len(pg) else '-'}) -> relevant >= {T_rel}, aehnlich >= {T_sim}")
    seiten_vorhanden = {}
    for b in basis: seiten_vorhanden[b["seite"] or "unbekannt"] = seiten_vorhanden.get(b["seite"] or "unbekannt", 0) + 1
    print(f"  Seiten vorhanden: {seiten_vorhanden}")
    rows = []
    for k in kand:
        pv = os.path.join(th, hashlib.md5(k["title"].encode()).hexdigest() + "_1024.jpg")
        if not lade_bild(k["url"], pv): continue
        mk = merkmale(pv)
        if not mk: continue
        k.update(sharp=round(mk["sharp"], 1)); k["_mk"] = mk
        if mk["sharp"] < min_sharp: k["klasse"] = "unscharf"; rows.append(k); continue
        best = max(((inlier(mk, b), b) for b in basis), key=lambda q: q[0])
        k["aehnlich_basis"] = dict(name=best[1]["name"], seite=best[1]["seite"], inlier=int(best[0]))
        if best[0] < T_rel: k["klasse"] = "irrelevant"; rows.append(k); continue          # zeigt dieses Objekt nicht (oder nur winzig)
        k["guete"] = float(k["orig_w"]) * math.log10(max(mk["sharp"], 1.0)); rows.append(k)
    # ---- Auswahl: relevante zuerst nach Guete; dup (pHash) raus, aehnlich gedeckelt je Blickgruppe, neu immer (bis max_neu)
    gew = []; gruppen = {}
    for k in sorted([r for r in rows if r.get("klasse") not in ("unscharf", "irrelevant")], key=lambda r: -r["guete"]):
        mk = k["_mk"]; klasse = "neu"; bezug = None
        for other in gew + basis:
            if hamming(mk["ph"], (other["_mk"] if "_mk" in other else other)["ph"]) <= 6: klasse, bezug = "dup", other.get("title") or other.get("name"); break
        if klasse != "dup":
            best_g = max(((inlier(mk, o["_mk"]), o["title"]) for o in gew), default=(0, None), key=lambda q: q[0])
            ib = k["aehnlich_basis"]["inlier"]
            if max(best_g[0], ib) >= T_sim: klasse, bezug = "aehnlich", (best_g[1] if best_g[0] >= ib else k["aehnlich_basis"]["name"])
        k["klasse"] = klasse; k["aehnlich_zu"] = bezug
        if klasse == "dup": continue
        if klasse == "aehnlich":
            gruppen[bezug] = gruppen.get(bezug, 0) + 1
            if gruppen[bezug] > max_grp: k["klasse"] = "aehnlich_ueberzaehlig"; continue
        if len(gew) >= max_neu: k["klasse"] = "ueber_max"; continue
        gew.append(k)
    # ---- Gewinner in voller Breite laden + Manifest
    voll = CH.image_info([k["title"] for k in gew], a.breite) if gew else {}
    man = dict(source="bilder_holen (Commons)", stand=time.strftime("%Y-%m-%d"), objekt=obj.get("name"), lat=lat, lon=lon, images=[])
    for k in gew:
        v = voll.get(k["title"], {}); name = "neu_" + hashlib.md5(k["title"].encode()).hexdigest()[:10] + os.path.splitext(k["title"])[1].lower().replace(".jpeg", ".jpg")
        if not lade_bild(v.get("url") or k["url"], os.path.join(aus, name)): continue
        man["images"].append(dict(file=name, title=k["title"], url=v.get("url") or k["url"], license=k["license"], artist=k["artist"], orig_w=k["orig_w"], orig_h=k["orig_h"], sharp=k["sharp"], klasse=k["klasse"], aehnlich_zu=k.get("aehnlich_zu"), aehnlich_basis=k.get("aehnlich_basis"), guete=round(k["guete"], 1), exif_f35=k.get("exif_f35"), exif_model=k.get("exif_model"), seite_vorschlag=(k.get("aehnlich_basis") or {}).get("seite") or None))
    json.dump(man, open(os.path.join(aus, "manifest.json"), "w"), indent=1, ensure_ascii=False)
    z = {}
    for r in rows: z[r.get("klasse", "?")] = z.get(r.get("klasse", "?"), 0) + 1
    liz = {}
    for it in man["images"]: liz[it["license"]] = liz.get(it["license"], 0) + 1
    bericht = dict(kandidaten=len(kand), klassen=z, geladen=len(man["images"]), lizenzen=liz, max_neu=max_neu, max_je_blickgruppe=max_grp, schwellen=dict(relevant=T_rel, aehnlich=T_sim), matcher="ALIKED+LightGlue (" + dev + ")", quellen=dict(commons=True, mapillary="kein Token" if not (os.path.exists(os.path.expanduser("~/.config/mapillary_token")) or os.environ.get("MAPILLARY_TOKEN")) else "moeglich", video="nur mit --mit-video (Urheberrecht)"))
    json.dump(bericht, open(os.path.join(aus, "bericht.json"), "w"), indent=1, ensure_ascii=False)
    print(f"\nAuswahl: {len(man['images'])} geladen von {len(kand)} Kandidaten; Klassen {z}; Lizenzen {liz}")
    print(f"Manifest: {os.path.join(aus, 'manifest.json')}  Bericht: {os.path.join(aus, 'bericht.json')}")

if __name__ == "__main__":
    main()
