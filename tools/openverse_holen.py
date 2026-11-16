#!/usr/bin/env python3
"""openverse_holen.py --aus DIR --suche "Schwabentor Freiburg" ["Freiburg Luftbild" ...] [--max 150] [--min-breite 900] [--bekannt herkunft.json ...]

Frei lizenzierte Fotos zu einem Objekt ueber OPENVERSE holen (ein Suchindex ueber Flickr, Wikimedia, Museen ...; kein Schluessel noetig).
Nutzer 16.11.2026 (Schwabentor Ostseite ohne Fotos): "da musst du halt alle Quellen, die du holen kannst, holen". Ergaenzt tools/commons_harvest.py
(Geosuche) und tools/online_ansichten_holen.py (Hochblicke auf Commons) um Flickr und andere Quellen.
Nur Lizenzen, die Bearbeitung und gewerbliche Nutzung erlauben (CC0, PDM, CC BY, CC BY-SA) - license_type=commercial,modification; NC/ND kommen nicht mit.
Je Bild in DIR/herkunft.json: datei, titel, url, seite, lizenz, urheber, quelle, breite, hoehe, suche (Namensnennung fuer ein Verkaufsprodukt beilegen).
Schon bekannte Bilder (gleiche URL oder gleicher Titel in --bekannt-Dateien bzw. frueherem herkunft.json) werden nicht noch einmal geladen.
Hoeflich: 1 Abfrage je 2 s, je Quelle 1 Bild je 1,5 s (Wikimedia 25 s); HTTP 429 sperrt nur diese Quelle fuer den Lauf. Danach: tools/seiten_luecken.py (Nachregistrieren) bzw. tools/fotos_eingang.py.
"""
import sys, os, json, time, argparse, urllib.request, urllib.parse

UA = {"User-Agent": "rc-park-modellbau/1.0 (Architekturmodell aus Fotos; nicht-automatisierte Einzelabrufe)"}


def hole(url, roh=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        b = r.read(); return b if roh else json.loads(b)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--aus", required=True); ap.add_argument("--suche", nargs="+", required=True); ap.add_argument("--max", type=int, default=150); ap.add_argument("--min-breite", type=int, default=900)
    ap.add_argument("--bekannt", nargs="*", default=[]); ap.add_argument("--ohne-wikimedia", action="store_true", help="Wikimedia-Treffer auslassen (kommen ueber commons_harvest.py / nach einer Drosselung)"); a = ap.parse_args(); os.makedirs(a.aus, exist_ok=True); hp = os.path.join(a.aus, "herkunft.json"); H = json.load(open(hp)) if os.path.exists(hp) else []
    bek = set()
    for f in a.bekannt + [hp]:
        if os.path.exists(f):
            d = json.load(open(f)); d = d if isinstance(d, list) else d.get("bilder", d.get("files", []))
            for e in d:
                if isinstance(e, dict): bek.update(str(e.get(k, "")).strip().lower() for k in ("url", "titel", "title") if e.get(k))
    n = 0; gesperrt = set(); zuletzt = {}
    for q in a.suche:
        seite = 1
        while n < a.max and seite <= 12:
            try: d = hole("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(dict(q=q, license_type="commercial,modification", page_size=20, page=seite)))
            except Exception as e: print("Abfrage abgebrochen:", str(e)[:120]); break
            for r in d.get("results", []):
                if n >= a.max: break
                if (r.get("width") or 0) < a.min_breite or not r.get("url"): continue
                if r["url"].lower() in bek or (r.get("title") or "").strip().lower() in bek: continue
                host = urllib.parse.urlparse(r["url"]).netloc
                if host in gesperrt or (a.ohne_wikimedia and "wikimedia" in host): continue
                warte = 25.0 if "wikimedia" in host else 1.5                # Wikimedia-Etikette (Lehre 9.11. und 16.11.): 1 Datei je >= 25 s, sonst HTTP 429
                if host in zuletzt: time.sleep(max(0.0, warte - (time.time() - zuletzt[host])))
                zuletzt[host] = time.time()
                dn = f"ov_{len(H):04d}.jpg"
                try:
                    b = hole(r["url"], roh=True)
                    if len(b) < 20000: continue
                    open(os.path.join(a.aus, dn), "wb").write(b)
                except Exception as e:
                    if "429" in str(e): gesperrt.add(host); print(f"HTTP 429 von {host} - diese Quelle fuer diesen Lauf gesperrt (nicht wiederholen, Drosselung ~15 min)")
                    continue
                H.append(dict(datei=dn, titel=r.get("title"), url=r["url"], seite=r.get("foreign_landing_url"), lizenz=f"{r.get('license')} {r.get('license_version') or ''}".strip(), urheber=r.get("creator"), quelle=r.get("source"), breite=r.get("width"), hoehe=r.get("height"), suche=q))
                bek.update([r["url"].lower(), (r.get("title") or "").strip().lower()]); n += 1
            if seite >= (d.get("page_count") or 1): break
            seite += 1; time.sleep(2.0)
        json.dump(H, open(hp, "w"), indent=1, ensure_ascii=False); print(f"'{q}': bisher {n} neue Bilder")
    print(f"{a.aus}: {n} neue Bilder, herkunft.json mit {len(H)} Eintraegen")


if __name__ == "__main__":
    sys.exit(main())
