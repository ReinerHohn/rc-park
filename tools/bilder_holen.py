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

PRODUKT_KLASSEN = "frei,frei_namensnennung,frei_sharealike"      # Klassen, deren Pixel im Produkt moeglich sind (frei_sharealike nur BEDINGT, siehe lizenz_register.produkt)

def lizenz_klasse(lizenz, quelle=""):
    """Lizenzklasse je Bild - ZENTRAL aus tools/lizenz_register.py (frei | frei_namensnennung | frei_sharealike | nc | unfrei | unklar); hier keine eigene Logik.
    Bleibt im Manifest ('lizenz_klasse', Originaltext in 'license'), im Foto-Eintrag und im Lizenzregister erhalten."""
    import lizenz_register as LR
    return LR.klasse(lizenz, quelle)

def exif_stufe(k):
    """EXIF-Stufe eines Kandidaten aus den API-Metadaten (verkleinerte Commons-Thumbnails tragen kein EXIF mehr, die API schon):
       vollstaendig = Kameramodell UND Brennweite (mm oder KB-aequivalent) -> Brennweiten-Prior fuer SfM moeglich; teilweise = eins davon; fehlt = nichts.
       Bilder mit 'fehlt' sind als Texturquelle abzuwerten (Kamera nur per Selbstkalibrierung, Plan M10)."""
    m = bool(k.get("exif_model")); f = bool(k.get("exif_f_mm") or k.get("exif_f35"))
    return "vollstaendig" if (m and f) else ("teilweise" if (m or f) else "fehlt")
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
    import urllib.error
    for versuch in range(6):                                                                 # HTTP 429 (Wikimedia-Ratenlimit): warten (Retry-After, sonst 5/10/20/40/80 s) und neu
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "rcpark-landmark/1.0 (3d-print research; contact via opmd1988@googlemail.com)"})
            data = urllib.request.urlopen(req, timeout=60).read(); open(pfad, "wb").write(data); time.sleep(0.3); return True
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and versuch < 5:
                w = int(e.headers.get("Retry-After") or 0) or 5 * 2 ** versuch; print(f"   HTTP {e.code}, warte {w} s ({url[:60]})", flush=True); time.sleep(w); continue
            print("   Download fehlgeschlagen:", url[:80], e); return False
        except Exception as e:
            print("   Download fehlgeschlagen:", url[:80], e); return False
    return False

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("--nur-kandidaten", action="store_true"); ap.add_argument("--mit-video", action="store_true"); ap.add_argument("--max-neu", type=int); ap.add_argument("--breite", type=int, default=2048)
    ap.add_argument("--ausgabe", help="Eingangsordner (ueberschreibt bildquellen.ausgabe; absolut oder relativ zum Repo), z. B. je Runde der Bilder-Schleife")
    ap.add_argument("--seiten", help="Komma-Liste nord,sued,ost,west: Seiten mit Luecke (Vorrang bei der Auswahl)")
    ap.add_argument("--nur-seiten", action="store_true", help="nur Bilder, deren Seitenvorschlag in --seiten liegt (sonst Klasse 'nicht_luecke', wird nicht geladen)")
    ap.add_argument("--lizenz-klassen", default="alle", help="erlaubte Lizenzklassen (Komma-Liste aus frei,frei_namensnennung,frei_sharealike,nc,unfrei,unklar) oder 'alle'; Verkaufsweg: " + PRODUKT_KLASSEN)
    ap.add_argument("--bekannt-aus", nargs="*", default=[], help="weitere manifest.json (fruehere Runden): deren Titel nicht nochmal holen")
    ap.add_argument("--bild-klassen", default="neu,aehnlich", help="Stufe 0/1: nur 'neu' (verschiedene Blickwinkel); spaetere Stufen: 'neu,aehnlich' (aehnlich = Parallaxe fuer schlecht bestimmte Netze); Dubletten werden nie genommen")
    ap.add_argument("--aehnlich-seiten", help="Komma-Liste: 'aehnlich' nur fuer diese Seiten erlaubt (Netz dort schlecht bestimmt)")
    ap.add_argument("--max-je-seite", type=int, help="hoechstens N Bilder je Seitenvorschlag in dieser Stufe (Stufe 0: 1)"); ap.add_argument("--max-je-gruppe", type=int, help="ueberschreibt bildquellen.max_je_blickgruppe (Deckel 'aehnlich' je Blickgruppe und Stufe)")
    ap.add_argument("--schwellen-cache", help="JSON mit T_rel/T_sim: vorhanden -> Kalibrierung ueberspringen (Stufen 1+ derselben Schleife); sonst nach der Kalibrierung dorthin schreiben")
    ap.add_argument("--cache-ordner", help="gemeinsamer Cache fuer Vorschauen und Merkmale (_vorschau/_merkmale) ueber mehrere Stufen; Standard: im Eingangsordner")
    ap.add_argument("--max-kandidaten", type=int, help="nur die N breitesten Kandidaten bewerten (Test/Rechenzeit; Voreinstellung: alle)")
    a = ap.parse_args(); import cv2; import commons_harvest as CH
    obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); repo = os.path.dirname(os.path.dirname(od)); Q = obj.get("bildquellen")
    if not Q: sys.exit("objekt.json['bildquellen'] fehlt (Kategorien/Suchen/Stichworte als Daten)")
    A3 = json.load(open(os.path.join(od, "anker3d.json"))); E0, N0 = A3["mitte_utm"]; lat, lon = utm_zu_wgs84(E0, N0); xh, yh = np.array(A3["xhat_utm"]), np.array(A3["yhat_utm"])
    aus = os.path.join(repo, a.ausgabe or Q.get("ausgabe", f"daten/{os.path.basename(od)}/fotos_eingang")); th = os.path.join(a.cache_ordner or aus, "_vorschau"); os.makedirs(th, exist_ok=True)
    max_neu = a.max_neu or Q.get("max_neu", 120); min_b = Q.get("min_breite_px", 1000); max_grp = a.max_je_gruppe if a.max_je_gruppe else Q.get("max_je_blickgruppe", 4); min_sharp = Q.get("min_schaerfe", 40.0)
    print(f"Objekt {obj.get('name')}: {lat:.5f} N {lon:.5f} E; Ausgabe {os.path.relpath(aus, repo)}")
    # ---- vorhandene Titel (nicht nochmal) + vorhandene Fotos als Vergleichsbasis
    bekannt = set(); vorhanden_mf = os.path.join(repo, obj["fotos_dir"], "manifest.json")
    for mp in [vorhanden_mf, os.path.join(aus, "manifest.json")] + list(a.bekannt_aus):
        if os.path.exists(mp):
            M = json.load(open(mp)); items = M.get("images") or M.get("bilder") or []
            for it in (items.values() if isinstance(items, dict) else items):
                t = it.get("title") or it.get("titel") or (it if isinstance(it, str) else None)
                if t: bekannt.add(t)
    # ---- 1. Kandidaten (Commons)
    C = Q.get("commons", {}); titel = []
    aus_kat = set()                                                                          # Titel aus den Objekt-Kategorien (Kaltstart-Saat, siehe unten)
    for cat in C.get("kategorien", []): t = CH.category_files(cat, 2000); print(f"  Kategorie {cat}: {len(t)}"); titel += t; aus_kat.update(t)
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
        kand.append(dict(title=t, lizenz_klasse=lizenz_klasse(i.get("license")), exif_stufe=exif_stufe(i), **i))
    print(f"  mit Breite >= {min_b} px: {len(kand)}")
    erlaubt = {"frei", "frei_namensnennung", "frei_sharealike", "nc", "unfrei", "unklar"} if a.lizenz_klassen.strip() == "alle" else {x.strip() for x in a.lizenz_klassen.split(",") if x.strip()}; lk = {}
    for k in kand: lk[k["lizenz_klasse"]] = lk.get(k["lizenz_klasse"], 0) + 1
    n_lz = len(kand); kand = [k for k in kand if k["lizenz_klasse"] in erlaubt]
    print(f"  Lizenzklassen der Kandidaten {lk}; erlaubt {sorted(erlaubt)} -> {len(kand)} von {n_lz}")
    if a.max_kandidaten and len(kand) > a.max_kandidaten:
        kand = sorted(kand, key=lambda k: -k["orig_w"])[:a.max_kandidaten]; print(f"  --max-kandidaten: nur die {len(kand)} breitesten werden bewertet")
    seiten_luecke = [x.strip().lower() for x in (a.seiten or "").split(",") if x.strip()]; aehn_seiten = [x.strip().lower() for x in (a.aehnlich_seiten or "").split(",") if x.strip()]; bk = {x.strip() for x in a.bild_klassen.split(",") if x.strip()}; je_seite_n = {}
    if a.nur_kandidaten:
        json.dump(kand, open(os.path.join(aus, "kandidaten.json"), "w"), indent=1, ensure_ascii=False); print("nur Kandidaten geschrieben"); return
    # ---- Vorschaubilder (1024 px) + Guete + Hash + gelernte Merkmale (ALIKED + LightGlue, GPU; Lizenz: Apache/BSD, siehe LIZENZ_WERKZEUGE.md)
    import torch; from lightglue import LightGlue, ALIKED; from lightglue.utils import load_image
    from concurrent.futures import ThreadPoolExecutor
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cuda": torch.cuda.set_per_process_memory_fraction(float(Q.get("gpu_anteil", 0.45)))   # Deckel: COLMAP/andere GPU-Jobs koennen daneben laufen
    ext = ALIKED(max_num_keypoints=2048).eval().to(dev); matcher = LightGlue(features="aliked").eval().to(dev)
    cache = os.path.join(a.cache_ordner or aus, "_merkmale"); os.makedirs(cache, exist_ok=True); pool = ThreadPoolExecutor(max_workers=4)
    print(f"  Matcher ALIKED+LightGlue auf {dev}; Merkmals-Cache {os.path.relpath(cache, repo) if cache.startswith(repo) else cache}")
    def merkmale(pfad):
        """ALIKED-Merkmale (gecacht als .pt neben den Vorschauen), Schaerfe und pHash."""
        cp = os.path.join(cache, os.path.basename(pfad) + ".pt")
        if os.path.exists(cp):
            d = torch.load(cp, map_location=dev, weights_only=False); d["f"] = {k: v.to(dev) if hasattr(v, "to") else v for k, v in d["f"].items()}; return d
        im = cv2.imread(pfad)
        if im is None: return None
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY); s_ = 1024 / max(g.shape); g = cv2.resize(g, None, fx=s_, fy=s_) if s_ < 1 else g
        with torch.no_grad(): f = ext.extract(load_image(pfad, resize=1024).to(dev))
        d = dict(sharp=float(cv2.Laplacian(g, cv2.CV_64F).var()), ph=phash(g), f={k: v.detach().cpu() for k, v in f.items()}, kp=f["keypoints"][0].cpu().numpy())
        torch.save(d, cp); d["f"] = {k: v.to(dev) if hasattr(v, "to") else v for k, v in d["f"].items()}; return d
    def _geom(kpA, kpB, idx):
        if len(idx) < 12: return 0
        F, mask = cv2.findFundamentalMat(kpA[idx[:, 0]], kpB[idx[:, 1]], cv2.FM_RANSAC, 2.0, 0.999); return int(mask.sum()) if mask is not None else 0
    def inlier_viele(A, Bs):
        """Ein Kandidat gegen viele Bilder: GPU matcht der Reihe nach, die RANSAC-Geometrie laeuft parallel im Thread-Pool (GPU wartet nicht auf die CPU)."""
        futs = []
        for B in Bs:
            with torch.no_grad(): m = matcher({"image0": A["f"], "image1": B["f"]})
            futs.append(pool.submit(_geom, A["kp"], B["kp"], m["matches"][0].cpu().numpy()))
        return [f.result() for f in futs]
    def inlier(A, B): return inlier_viele(A, [B])[0]
    basis = []
    for f in sorted(os.listdir(os.path.join(repo, obj["fotos_dir"]))):
        if not f.lower().endswith((".jpg", ".jpeg", ".png")): continue
        pv = os.path.join(th, "basis_" + f + ".jpg")
        if not os.path.exists(pv):
            im = cv2.imread(os.path.join(repo, obj["fotos_dir"], f)); s_ = 1024 / max(im.shape[:2]); cv2.imwrite(pv, cv2.resize(im, None, fx=s_, fy=s_) if s_ < 1 else im)
        mk = merkmale(pv)
        if mk: mk["name"] = f; mk["seite"] = str((obj.get("fotos") or {}).get(f.split("_")[0], {}).get("seite", "")).lower(); basis.append(mk)
    saat = set()
    if not basis:
        # KALTSTART (neues Objekt, noch keine Fotos): Basis = groesste zusammenhaengende Gruppe der Kategorie-Bilder, die sich untereinander
        # geometrisch bestaetigen (>= 40 Inlier, Untergrenze wie T_rel). Innenraum/Fremdes haengt nicht an der Aussen-Gruppe und faellt heraus.
        S_ = [k for k in kand if k["title"] in aus_kat]; sm = []
        for k in S_:
            pv = os.path.join(th, hashlib.md5(k["title"].encode()).hexdigest() + "_1024.jpg")
            if lade_bild(k["url"], pv):
                mk = merkmale(pv)
                if mk and mk["sharp"] >= min_sharp: mk["name"] = k["title"]; mk["seite"] = ""; sm.append(mk)
        T0 = int(Q.get("saat_inlier", 40)); nb = {i: set() for i in range(len(sm))}
        for i in range(len(sm)):
            for j, w in zip(range(i + 1, len(sm)), inlier_viele(sm[i], sm[i + 1:]) if i + 1 < len(sm) else []):
                if w >= T0: nb[i].add(j); nb[j].add(i)
        komp, frei_ = [], set(nb)
        while frei_:
            st = [frei_.pop()]; c_ = set(st)
            while st:
                for j in nb[st.pop()]:
                    if j in frei_: frei_.discard(j); c_.add(j); st.append(j)
            komp.append(c_)
        komp.sort(key=len, reverse=True)
        basis = [sm[i] for i in (komp[0] if komp else [])]; saat = {b["name"] for b in basis}
        print(f"  KALTSTART: keine Fotos in {obj['fotos_dir']}; Saat aus {len(sm)} Kategorie-Bildern -> groesste Gruppe {len(basis)} (Gruppen {[len(c) for c in komp[:6]]}, Inlier >= {T0})")
        if not basis: sys.exit("Kaltstart: keine zusammenhaengende Bildgruppe in den Kategorien - bildquellen.commons.kategorien pruefen")
    # Schwellen aus den VORHANDENEN Fotos kalibrieren (gleiches Objekt): Inlier zwischen Basisfotos derselben Seite = 'aehnlich/ueberlappend',
    # ueber Seiten hinweg = 'gleiches Objekt, andere Sicht'. T_rel = p10 aller Basispaare mit Inliern > 0 ... konservativ: feste Untergrenze 20
    _sc = a.schwellen_cache if (a.schwellen_cache and os.path.exists(a.schwellen_cache)) else None
    if _sc:
        _d = json.load(open(_sc)); T_rel, T_sim = int(_d["T_rel"]), int(_d["T_sim"]); print(f"  Schwellen aus Cache {_sc}: relevant >= {T_rel}, aehnlich >= {T_sim} (Kalibrierung uebersprungen)")
    else:
        paare_gleich, paare_alle = [], []; import random; random.seed(0)
        for i in range(len(basis)):
            partner = [basis[j] for j in range(i + 1, len(basis)) if basis[i]["seite"] and basis[i]["seite"] == basis[j]["seite"]]
            fremd = [basis[j] for j in range(i + 1, len(basis)) if not (basis[i]["seite"] and basis[i]["seite"] == basis[j]["seite"])]
            partner_n = inlier_viele(basis[i], partner) if partner else []; paare_gleich += partner_n; paare_alle += partner_n
            stich = random.sample(fremd, min(3, len(fremd))) if fremd else []; paare_alle += inlier_viele(basis[i], stich) if stich else []
        pa, pg = np.array(paare_alle), np.array(paare_gleich)
        # relevant: Untergrenze 40 Inlier (Befund Ernte 2: fremde 'Martinstore' aus Ladenburg/Wangen erreichten 20-35, echte Fernsichten ab ~42),
        # sonst p10 der Basispaare derselben Seite (gleiches Objekt, ueberlappend)
        T_rel = max(40, int(np.percentile(pg[pg > 0], 10))) if (pg > 0).sum() > 10 else 40
        T_sim = max(T_rel * 2, int(np.percentile(pg[pg > 0], 50))) if (pg > 0).sum() > 10 else T_rel * 3
        print(f"  Kalibrierung an {len(basis)} Basisfotos: Paare gesamt {len(pa)} (Inlier p10/p50/p90 {np.percentile(pa,[10,50,90]).astype(int).tolist() if len(pa) else '-'}), gleiche Seite {len(pg)} (p50 {int(np.median(pg)) if len(pg) else '-'}) -> relevant >= {T_rel}, aehnlich >= {T_sim}")
        if a.schwellen_cache: os.makedirs(os.path.dirname(os.path.abspath(a.schwellen_cache)), exist_ok=True); json.dump(dict(T_rel=int(T_rel), T_sim=int(T_sim), basisfotos=len(basis), stand=time.strftime("%F %T")), open(a.schwellen_cache, "w"))
    seiten_vorhanden = {}
    for b in basis: seiten_vorhanden[b["seite"] or "unbekannt"] = seiten_vorhanden.get(b["seite"] or "unbekannt", 0) + 1
    print(f"  Seiten vorhanden: {seiten_vorhanden}")
    repr_ = []
    for sd in sorted({b["seite"] for b in basis}):
        repr_ += sorted([b for b in basis if b["seite"] == sd], key=lambda b: -len(b["kp"]))[:4]
    print(f"  Repraesentanten fuer den Relevanz-Vortest: {len(repr_)} ({', '.join(b['name'][:12] for b in repr_)})")
    rows = []
    for k in kand:
        pv = os.path.join(th, hashlib.md5(k["title"].encode()).hexdigest() + "_1024.jpg")
        if not lade_bild(k["url"], pv): continue
        mk = merkmale(pv)
        if not mk: continue
        k.update(sharp=round(mk["sharp"], 1)); k["_mk"] = mk
        if mk["sharp"] < min_sharp: k["klasse"] = "unscharf"; rows.append(k); continue
        if k["title"] in saat:                                                              # Saat-Bild: gehoert per Konstruktion zum Objekt
            k["aehnlich_basis"] = dict(name=k["title"], seite="", inlier=0, saat=True); k["guete"] = float(k["orig_w"]) * math.log10(max(mk["sharp"], 1.0)); rows.append(k); continue
        vor = inlier_viele(mk, repr_); bestv = max(zip(vor, repr_), key=lambda q: q[0])
        if bestv[0] < T_rel * 0.5: k["aehnlich_basis"] = dict(name=bestv[1]["name"], seite=bestv[1]["seite"], inlier=int(bestv[0])); k["klasse"] = "irrelevant"; rows.append(k); continue   # Vortest: weit unter relevant
        alle = inlier_viele(mk, basis); best = max(zip(alle, basis), key=lambda q: q[0])
        k["aehnlich_basis"] = dict(name=best[1]["name"], seite=best[1]["seite"], inlier=int(best[0]))
        if best[0] < T_rel: k["klasse"] = "irrelevant"; rows.append(k); continue          # zeigt dieses Objekt nicht (oder nur winzig)
        k["guete"] = float(k["orig_w"]) * math.log10(max(mk["sharp"], 1.0)); rows.append(k)
    # ---- Auswahl: relevante zuerst nach Guete; dup (pHash) raus, aehnlich gedeckelt je Blickgruppe, neu immer (bis max_neu)
    gew = []; gruppen = {}
    def _sv(r): return (r.get("aehnlich_basis") or {}).get("seite") or None
    for k in sorted([r for r in rows if r.get("klasse") not in ("unscharf", "irrelevant")], key=lambda r: (0 if (_sv(r) or "").lower() in seiten_luecke else 1, -r["guete"])):
        mk = k["_mk"]; klasse = "neu"; bezug = None
        for other in gew + [b for b in basis if b["name"] != k["title"]]:
            if hamming(mk["ph"], (other["_mk"] if "_mk" in other else other)["ph"]) <= 6: klasse, bezug = "dup", other.get("title") or other.get("name"); break
        if klasse != "dup":
            best_g = max(zip(inlier_viele(mk, [o["_mk"] for o in gew]), [o["title"] for o in gew]), default=(0, None), key=lambda q: q[0]) if gew else (0, None)
            ib = k["aehnlich_basis"]["inlier"]
            if max(best_g[0], ib) >= T_sim: klasse, bezug = "aehnlich", (best_g[1] if best_g[0] >= ib else k["aehnlich_basis"]["name"])
        k["klasse"] = klasse; k["aehnlich_zu"] = bezug
        if klasse == "dup": continue
        if a.nur_seiten and seiten_luecke and (_sv(k) or "").lower() not in seiten_luecke: k["klasse"] = "nicht_luecke"; continue
        if klasse not in bk or (klasse == "aehnlich" and aehn_seiten and (_sv(k) or "").lower() not in aehn_seiten): k["klasse"] = klasse + "_nicht_diese_stufe"; continue
        if a.max_je_seite and je_seite_n.get(_sv(k) or "unbekannt", 0) >= a.max_je_seite: k["klasse"] = "seite_voll"; continue
        if klasse == "aehnlich":
            gruppen[bezug] = gruppen.get(bezug, 0) + 1
            if gruppen[bezug] > max_grp: k["klasse"] = "aehnlich_ueberzaehlig"; continue
        if len(gew) >= max_neu: k["klasse"] = "ueber_max"; continue
        gew.append(k); je_seite_n[_sv(k) or "unbekannt"] = je_seite_n.get(_sv(k) or "unbekannt", 0) + 1
    # ---- Gewinner in voller Breite laden + Manifest
    voll = CH.image_info([k["title"] for k in gew], a.breite) if gew else {}
    man = dict(source="bilder_holen (Commons)", stand=time.strftime("%Y-%m-%d"), objekt=obj.get("name"), lat=lat, lon=lon, images=[])
    for k in gew:
        v = voll.get(k["title"], {}); name = "neu_" + hashlib.md5(k["title"].encode()).hexdigest()[:10] + os.path.splitext(k["title"])[1].lower().replace(".jpeg", ".jpg")
        if not lade_bild(v.get("url") or k["url"], os.path.join(aus, name)): continue
        man["images"].append(dict(file=name, title=k["title"], url=v.get("url") or k["url"], license=k["license"], artist=k["artist"], orig_w=k["orig_w"], orig_h=k["orig_h"], sharp=k["sharp"], klasse=k["klasse"], lizenz_klasse=k["lizenz_klasse"], produkt_pixel=__import__("lizenz_register").produkt(k["lizenz_klasse"])[0], produkt_auflage=__import__("lizenz_register").produkt(k["lizenz_klasse"])[1], exif_stufe=k["exif_stufe"], exif_f_mm=k.get("exif_f_mm"), aehnlich_zu=k.get("aehnlich_zu"), aehnlich_basis=k.get("aehnlich_basis"), guete=round(k["guete"], 1), exif_f35=k.get("exif_f35"), exif_model=k.get("exif_model"), seite_vorschlag=(k.get("aehnlich_basis") or {}).get("seite") or None))
    json.dump(man, open(os.path.join(aus, "manifest.json"), "w"), indent=1, ensure_ascii=False)
    z = {}
    for r in rows: z[r.get("klasse", "?")] = z.get(r.get("klasse", "?"), 0) + 1
    liz = {}
    for it in man["images"]: liz[it["license"]] = liz.get(it["license"], 0) + 1
    bericht = dict(kandidaten=len(kand), lizenzklassen_kandidaten=lk, erlaubte_lizenzklassen=sorted(erlaubt), seiten_luecke=seiten_luecke, nur_seiten=a.nur_seiten, klassen=z, geladen=len(man["images"]), lizenzen=liz, max_neu=max_neu, max_je_blickgruppe=max_grp, schwellen=dict(relevant=T_rel, aehnlich=T_sim), matcher="ALIKED+LightGlue (" + dev + ")", quellen=dict(commons=True, mapillary="kein Token" if not (os.path.exists(os.path.expanduser("~/.config/mapillary_token")) or os.environ.get("MAPILLARY_TOKEN")) else "moeglich", video="nur mit --mit-video (Urheberrecht)"))
    json.dump(bericht, open(os.path.join(aus, "bericht.json"), "w"), indent=1, ensure_ascii=False)
    print(f"\nAuswahl: {len(man['images'])} geladen von {len(kand)} Kandidaten; Klassen {z}; Lizenzen {liz}")
    print(f"Manifest: {os.path.join(aus, 'manifest.json')}  Bericht: {os.path.join(aus, 'bericht.json')}")

if __name__ == "__main__":
    main()
