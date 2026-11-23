#!/usr/bin/env python3
"""online_ansichten_holen.py - hochliegende Webfotos (Turm-/Dach-/Luftansichten) zu einem Objekt von Wikimedia Commons holen, mit Herkunft+Lizenz je Bild.
Generisch: Ort/Objekt nur als Parameter. Ergebnis AUS/orig/od_NN.jpg + AUS/herkunft.json (datei, titel, url, page, lic, artist, date, w, h).
Aufruf: python3 tools/online_ansichten_holen.py --aus DIR --suche "Historisches Kaufhaus Freiburg" "Blick vom Muensterturm Freiburg" --kategorien "Category:Muensterplatz (Freiburg im Breisgau)"
          [--muster REGEX] [--max 30] [--nur-liste] [--min-breite 1000]
Standard-Muster fuer Hochblick: Blick vom|Turm|Aussicht|Aerial|Luftbild|von oben|Dach|Drohne|drone|Panorama|view from|rooftop.
Wikimedia-Etikette (Lehre 9.11.): 1 Datei je >= 25 s, KEIN Retry-Sturm (HTTP 429 = IP-Drosselung ~15 min, Retries verlaengern sie);
  seit 23.11.: 429 -> Retry-After bzw. Backoff 60/120/240 s (tools/http_holen.py, Budget RCPARK_429_BUDGET_S), erst danach Abbruch.
Lizenz: nur freie Lizenzen (CC0/CC BY/CC BY-SA/PD) werden genommen; Urheber+Lizenz bleiben in herkunft.json (Verkauf: Namensnennung beilegen). Pruefung: Tool nimmt nur Treffer mit LicenseShortName.
Registrierung danach: tools/online_dach_registrieren.py rein/reg (EXIF-Brennweite je Bild), Schwaechen: Turmblicke ohne Bodenueberlapp scheitern (siehe REZEPT Lehren-Register)."""
import sys, os, re, json, time, argparse, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import http_holen      # 23.11.2026: HTTP 429 mit Retry-After/Backoff statt Abbruch beim ersten 429 (Lauf 1122p: od_02)
UA = {"User-Agent": "RCParkResearchBot/1.0 (private non-commercial research)"}
STD = r"Blick vom|Turm|Aussicht|Aerial|Luftbild|von oben|Dach|Drohne|drone|Panorama|view from|rooftop|Kreuzblume|Achteck"


def jpeg_ok(p):
    """Datei ist ein echtes JPEG (Magic-Bytes FF D8, Groesse > 0)."""
    try:
        with open(p, "rb") as f: return f.read(2) == b"\xff\xd8"
    except OSError: return False

def api(**p):
    p["format"] = "json"; u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)
    return json.loads(http_holen.hole(u, UA, timeout=60))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aus", required=True); ap.add_argument("--suche", nargs="*", default=[]); ap.add_argument("--kategorien", nargs="*", default=[])
    ap.add_argument("--muster", default=STD); ap.add_argument("--max", type=int, default=30); ap.add_argument("--nur-liste", action="store_true"); ap.add_argument("--min-breite", type=int, default=1000)
    a = ap.parse_args(); rx = re.compile(a.muster, re.I); titel = {}
    for q in a.suche:
        r = api(action="query", list="search", srsearch=q, srnamespace=6, srlimit=50)
        for m in r["query"]["search"]: titel[m["title"]] = q
        time.sleep(3)
    for c in a.kategorien:
        r = api(action="query", list="categorymembers", cmtitle=c, cmlimit=500)
        for m in r["query"]["categorymembers"]:
            if m["ns"] == 6: titel[m["title"]] = c
        time.sleep(3)
    sel = [t for t in titel if rx.search(t)][:a.max * 2]; info = []
    for i in range(0, len(sel), 20):
        r = api(action="query", titles="|".join(sel[i:i + 20]), prop="imageinfo", iiprop="url|size|extmetadata|mime|thumbmime", iiurlwidth=2400)
        for p in r["query"]["pages"].values():
            ii = (p.get("imageinfo") or [{}])[0]; em = ii.get("extmetadata", {}); g = lambda k: re.sub("<[^>]+>", "", em.get(k, {}).get("value", ""))
            if not ii.get("url") or ii.get("mime") != "image/jpeg" or (ii.get("width") or 0) < a.min_breite or not g("LicenseShortName"): continue
            info.append(dict(titel=p["title"], url=(ii.get("thumburl") or ii["url"]).split("?")[0], page=ii.get("descriptionurl"), lic=g("LicenseShortName"), artist=g("Artist")[:100], date=g("DateTimeOriginal")[:30], w=ii["width"], h=ii["height"]))
        time.sleep(3)
    info = info[:a.max]; os.makedirs(a.aus + "/orig", exist_ok=True)
    for i, m in enumerate(info): m["datei"] = f"od_{i:02d}.jpg"
    json.dump(info, open(a.aus + "/herkunft.json", "w"), ensure_ascii=False, indent=1); print(len(info), "Treffer")
    if a.nur_liste: return
    http_holen.vorrat_melden(sum(1 for m in info if jpeg_ok(f"{a.aus}/orig/{m['datei']}")))      # 23.11.2026 (Lauf 1122q: 6 min Warten fuer 0 neue): schon Bilder da + frische Drossel-Marke -> nicht warten
    for m in info:
        p = f"{a.aus}/orig/{m['datei']}"
        if os.path.exists(p) and jpeg_ok(p): continue
        # Erst laden und pruefen, dann atomar schreiben: ein Fehler hinterlaesst KEINE leere Datei (Lehre Schwabentor 13.11.: od_10 war 0 Byte, Abbruch per 429 mitgezaehlt).
        try: daten = http_holen.hole(m["url"], UA, timeout=120)
        except http_holen.Gedrosselt as e:
            print("Abbruch (Drosselung, Wartebudget erschoepft)", m["datei"], e, "- naechster Lauf setzt fort, bereits geladene werden uebersprungen"); break
        except Exception as e:
            print("Fehler", m["datei"], str(e)[:150], "- Bild uebersprungen"); continue
        if not daten[:2] == b"\xff\xd8":
            print("kein JPEG, verworfen:", m["datei"], len(daten), "Byte"); continue
        open(p + ".tmp", "wb").write(daten); os.replace(p + ".tmp", p)
        time.sleep(25)
    print("geladen (gueltige JPEG):", sum(1 for m in info if jpeg_ok(f"{a.aus}/orig/{m['datei']}")), "von", len(info))


if __name__ == "__main__":
    main()
