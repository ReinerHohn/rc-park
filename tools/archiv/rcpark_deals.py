#!/usr/bin/env python3
"""rcpark_deals.py — Sweet-Spot-Finder für günstige Spur-N-Teile (1:160) für den RC-Park.

Zwei Betriebsarten:
  1) DASHBOARD (immer): baut pro Kategorie 1-Klick-Links zu allen Quellen,
     jeweils "billigste zuerst" vorsortiert → HTML-Seite zum Durchklicken.
  2) LIVE (optional): wenn eBay-API-Zugang hinterlegt ist (ENV EBAY_APP_ID +
     EBAY_CERT_ID, gratis unter developer.ebay.com), holt es echte günstigste
     Preise, bildet den Median je Kategorie und markiert den SWEET SPOT
     (Angebote >= SCHWELLE unter Median).

Beispiele:
  python3 tools/rcpark_deals.py dashboard                 # HTML für ALLE Kategorien
  python3 tools/rcpark_deals.py dashboard --cat autos figuren
  python3 tools/rcpark_deals.py live --cat autos          # echte Preise (braucht eBay-Key)
  python3 tools/rcpark_deals.py cats                       # Kategorien auflisten
"""
import argparse, os, sys, json, html, time, statistics, urllib.parse, webbrowser

# ---------------------------------------------------------------- Kategorien
# Auf den RC-Park zugeschnitten: kaufen = Figuren/Autos/Gleise/Loks/Wagen/Decoder,
# DIY/drucken-Alternative = Natur/Gebäude. Query enthält "Spur N"/"1:160" zum Filtern.
CATEGORIES = {
    # --- FIRST STEP: kompletter laufender Zug zum kleinsten Preis ---
    "startset":   ("★ Startpackung/Startset (First Step)", "Spur N Startpackung Startset Minitrix Fleischmann Arnold Trix"),
    "konvolut":   ("★ Konvolut/Sammlung (billigster €/Stück)", "Spur N Konvolut Sammlung Modellbahn Posten"),
    "gleiskonv":  ("★ Gleis-Konvolut (Schienen billig)", "Spur N Gleis Konvolut Minitrix Fleischmann Paket"),
    "hoellental": ("★ Höllentalbahn-Lok (BR 85 / Regio)", "Spur N BR 85 Lok Fleischmann Minitrix Höllental"),
    "autos":      ("PKW / Autos",        "Herpa Rietze Spur N 1:160 PKW auto"),
    "lkw_bus":    ("LKW & Busse",        "Spur N 1:160 LKW Bus Wiking Rietze"),
    "figuren":    ("Figuren",            "Preiser Noch Spur N Figuren 1:160"),
    "gleise":     ("Gleise",             "Minitrix Fleischmann Spur N Gleis flexgleis"),
    "weichen":    ("Weichen",            "Spur N Weiche Minitrix Fleischmann Peco"),
    "loks":       ("Lokomotiven",        "Spur N Lokomotive Minitrix Fleischmann"),
    "wagen":      ("Wagen",              "Spur N Güterwagen Personenwagen"),
    "decoder":    ("Decoder / DCC",      "Spur N Decoder DCC Next18 Doehler"),
    "signale":    ("Signale",            "Spur N Signal Viessmann Formsignal"),
    "gebaeude":   ("Gebäude / Häuser",   "Spur N Gebäude Haus Faller Kibri 1:160"),
    "natur":      ("Natur (Bäume/Gras)", "Spur N Bäume Grasmatte Noch Busch Belaubung"),
    "beleuchtung":("Beleuchtung",        "Spur N Beleuchtung LED Laterne Strassenlaterne"),
    # --- Magnorail (fahrende Autos) ausführlich, da Hauptwunsch ---
    "magnorail":      ("Magnorail Komplett-Set",   "Magnorail Startset LS-1 BS-2 Spur N"),
    "magnorail_schl": ("Magnorail Schleifer",      "Magnorail Schleifer Fahrzeugschleifer N"),
    "magnorail_bahn": ("Magnorail Schiene/Kette",  "Magnorail Laufschiene Kette Antriebsmodul"),
}

# Typischer NEU-Preis je Kategorie (€) + Hinweis — Basis für die Schnäppchen-Bewertung.
# Grobe Richtwerte eines gängigen Einzelartikels; Konvolute pro Stück rechnen.
REFERENCE_UVP = {
    "startset": (120, "N-Startpackung neu (Lok+Gleisoval+Trafo)"),
    "konvolut": (0, "Bündel – pro Stück rechnen, kein Einzel-UVP"),
    "gleiskonv": (0, "Gleis-Bündel – pro Meter/Stück rechnen"),
    "hoellental": (140, "N-Lok (BR 85 Dampf teurer, Regio günstiger)"),
    "autos": (14, "Herpa/Rietze Einzel-PKW"),
    "lkw_bus": (29, "Herpa/Rietze LKW/Bus"),
    "figuren": (14, "Preiser Figuren-Set"),
    "gleise": (4, "Flexgleis/Gleisstück"),
    "weichen": (28, "E-Weiche Minitrix/Fleischmann"),
    "loks": (140, "N-Lok analog"),
    "wagen": (32, "Güter-/Personenwagen"),
    "decoder": (35, "Next18/DCC-Decoder"),
    "signale": (30, "Licht-/Formsignal"),
    "gebaeude": (30, "Faller/Kibri N-Bausatz"),
    "natur": (12, "Bäume/Grasmatte-Pack"),
    "beleuchtung": (15, "LED-Laterne/Beleuchtung"),
    "magnorail": (89, "LS-1 Startset UVP"),
    "magnorail_schl": (15, "2er-Schleifer-Set"),
    "magnorail_bahn": (25, "Schiene/Kette-Nachkauf"),
}

def rate_offer(price, ref):
    """Schnäppchen-Verdikt gegen Referenz-Neupreis."""
    if not ref or price <= 0: return ("", 9)
    r = price / ref
    if r <= 0.70: return ("🔥🔥 Top-Schnäppchen", 0)
    if r <= 0.85: return ("🔥 Schnäppchen", 1)
    if r <= 1.15: return ("👍 fair", 2)
    return ("💸 teuer", 3)

# ---------------------------------------------------------------- Quellen
# build(q) -> URL mit "billigste zuerst"-Sortierung wo möglich.
def _q(s): return urllib.parse.quote_plus(s)
SOURCES = {
    "eBay (günstigste inkl. Versand)": {
        "trust": 3,
        "build": lambda q: f"https://www.ebay.de/sch/i.html?_nkw={_q(q)}&_sop=15",
    },
    "Geizhals (Preis aufst.)": {
        "trust": 3,
        "build": lambda q: f"https://geizhals.de/?fs={_q(q)}&sort=p",
    },
    "idealo (Preisvergleich)": {
        "trust": 3,
        "build": lambda q: f"https://www.idealo.de/preisvergleich/MainSearchProductCategory.html?q={_q(q)}",
    },
    "1zu220-Shop (N-Spezialist)": {
        "trust": 2,
        "build": lambda q: f"https://www.1zu220-shop.de/advanced_search_result.php?keywords={_q(q)}",
    },
    "Modellbahnshop Lippe": {
        "trust": 2,
        "build": lambda q: f"https://www.modellbahnshop-lippe.com/?LA=1&AT=1&q={_q(q)}",
    },
    "Kleinanzeigen (gebraucht)": {
        "trust": 2,
        "build": lambda q: f"https://www.kleinanzeigen.de/s-sortierung:preis/{_q(q).replace('+','-')}/k0",
    },
}

SWEETSPOT_THRESHOLD = 0.20   # >=20% unter Median = Sweet Spot

# ---------------------------------------------------------------- eBay-API (optional, live)
def ebay_token():
    app, cert = os.environ.get("EBAY_APP_ID"), os.environ.get("EBAY_CERT_ID")
    if not (app and cert): return None
    import requests, base64
    cred = base64.b64encode(f"{app}:{cert}".encode()).decode()
    r = requests.post("https://api.ebay.com/identity/v1/oauth2/token",
        headers={"Authorization": f"Basic {cred}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials",
              "scope": "https://api.ebay.com/oauth/api_scope"}, timeout=15)
    r.raise_for_status(); return r.json()["access_token"]

def ebay_search(token, query, limit=20):
    import requests
    r = requests.get("https://api.ebay.com/buy/browse/v1/item_summary/search",
        headers={"Authorization": f"Bearer {token}",
                 "X-EBAY-C-MARKETPLACE-ID": "EBAY_DE"},
        params={"q": query, "limit": limit, "sort": "price"}, timeout=20)
    r.raise_for_status()
    out = []
    for it in r.json().get("itemSummaries", []):
        p = it.get("price", {}) or {}
        ship = 0.0
        for o in it.get("shippingOptions", []) or []:
            ship = float((o.get("shippingCost") or {}).get("value", 0) or 0); break
        try: total = float(p.get("value", 0)) + ship
        except (TypeError, ValueError): continue
        out.append({"title": it.get("title", ""), "price": total,
                    "url": it.get("itemWebUrl", ""), "cond": it.get("condition", "")})
    return sorted(out, key=lambda x: x["price"])

def mark_sweetspots(items, ref=None):
    med = statistics.median(i["price"] for i in items) if items else 0
    for i in items:
        i["median"] = med
        i["sweet"] = len(items) >= 3 and i["price"] <= med * (1 - SWEETSPOT_THRESHOLD)
        i["verdict"], i["rank"] = rate_offer(i["price"], ref)
    return items

# ---------------------------------------------------------------- Ausgaben
def cmd_cats():
    print("Kategorien (RC-Park, Spur N):")
    for k, (name, q) in CATEGORIES.items():
        print(f"  {k:12s} {name:28s} » {q}")

def selected(cats):
    if not cats: return list(CATEGORIES)
    bad = [c for c in cats if c not in CATEGORIES]
    if bad: sys.exit(f"Unbekannte Kategorie(n): {bad}. 'cats' zeigt alle.")
    return cats

def cmd_dashboard(cats, out, do_open):
    cats = selected(cats)
    rows = []
    for k in cats:
        name, q = CATEGORIES[k]
        btns = "".join(
            f'<a class="src t{d["trust"]}" href="{html.escape(d["build"](q))}" target="_blank">{html.escape(s)}</a>'
            for s, d in SOURCES.items())
        ref, refnote = REFERENCE_UVP.get(k, (None, ""))
        refhtml = (f'<span class="ref">üblich neu ~{ref} € · 🔥 ab {ref*0.85:.0f} € · '
                   f'🔥🔥 ab {ref*0.70:.0f} €</span>') if ref else ""
        rows.append(f'<div class="cat"><h2>{html.escape(name)}</h2>'
                    f'<div class="q">Suchbegriff: <code>{html.escape(q)}</code> {refhtml}</div>'
                    f'<div class="srcs">{btns}</div></div>')
    page = DASH_HTML.replace("{{ROWS}}", "\n".join(rows)).replace("{{N}}", str(len(cats)))
    open(out, "w").write(page)
    print(f"Dashboard geschrieben: {out}  ({len(cats)} Kategorien, {len(SOURCES)} Quellen)")
    if do_open:
        try: webbrowser.open("file://" + os.path.abspath(out))
        except Exception: pass

def cmd_live(cats, out):
    tok = ebay_token()
    if not tok:
        sys.exit("Kein eBay-Zugang. Setze ENV EBAY_APP_ID und EBAY_CERT_ID "
                 "(gratis: developer.ebay.com → Keys). Ohne das nutze 'dashboard'.")
    cats = selected(cats)
    report = []
    for k in cats:
        name, q = CATEGORIES[k]
        ref, refnote = REFERENCE_UVP.get(k, (None, ""))
        try:
            items = mark_sweetspots(ebay_search(tok, q), ref)
        except Exception as e:
            print(f"[{k}] Fehler: {e}"); continue
        items.sort(key=lambda x: (x["rank"], x["price"]))   # beste Schnäppchen zuerst
        hdr = f"\n== {name} ==  (üblich ~{ref} € {refnote})" if ref else f"\n== {name} =="
        print(hdr if items else f"\n== {name} == (leer)")
        for i in items[:8]:
            print(f"  {i.get('verdict',''):18s} {i['price']:7.2f} €  {i['cond'][:12]:12s} {i['title'][:55]}")
        report.append((name, q, items, ref, refnote))
    if out:
        _write_live_html(report, out)
        print(f"\nLive-Report: {out}")

def _write_live_html(report, out):
    blocks = []
    for name, q, items, ref, refnote in report:
        lis = "".join(
            f'<li class="r{i.get("rank",9)}">'
            f'<span class="v">{html.escape(i.get("verdict",""))}</span> '
            f'<span class="p">{i["price"]:.2f} €</span> '
            f'<a href="{html.escape(i["url"])}" target="_blank">{html.escape(i["title"][:80])}</a> '
            f'<em>{html.escape(i["cond"])}</em></li>'
            for i in items[:12])
        if items:
            blocks.append(f'<div class="cat"><h2>{html.escape(name)}</h2>'
                          f'<div class="q">üblich neu ~{ref} € ({html.escape(refnote)}) · '
                          f'Median Treffer {items[0].get("median",0):.2f} €</div>'
                          f'<ul>{lis}</ul></div>')
        else:
            blocks.append(f'<div class="cat"><h2>{html.escape(name)}</h2><p>keine Treffer</p></div>')
    open(out, "w").write(LIVE_HTML.replace("{{ROWS}}", "\n".join(blocks)))

# ---------------------------------------------------------------- HTML-Templates
DASH_HTML = """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RC-Park · Spur-N Sweet-Spot-Finder</title><style>
body{font-family:system-ui,sans-serif;background:#0f1419;color:#e6e6e6;margin:0;padding:24px}
h1{margin:0 0 4px} .sub{color:#8aa;margin-bottom:22px}
.cat{background:#171e26;border:1px solid #243;border-radius:10px;padding:14px 16px;margin:12px 0}
.cat h2{margin:0 0 6px;font-size:18px;color:#9fe}
.q{font-size:13px;color:#9ab;margin-bottom:10px} code{color:#fd8;background:#0c1116;padding:2px 6px;border-radius:4px}
.ref{margin-left:10px;color:#6f9;font-weight:600}
.srcs{display:flex;flex-wrap:wrap;gap:8px}
.src{display:inline-block;padding:8px 12px;border-radius:7px;text-decoration:none;font-size:13px;font-weight:600;
     background:#223;color:#cfe;border:1px solid #345}
.src:hover{background:#2c4055} .t3{border-color:#3a7} .t2{border-color:#558}
</style></head><body>
<h1>🚂 RC-Park · Spur-N Sweet-Spot-Finder</h1>
<div class="sub">{{N}} Kategorien · jede Quelle öffnet „billigste zuerst". Grün umrandet = Top-Quelle für Preise.</div>
{{ROWS}}
</body></html>"""

LIVE_HTML = """<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<title>RC-Park · Live-Preise Spur N</title><style>
body{font-family:system-ui,sans-serif;background:#0f1419;color:#e6e6e6;margin:0;padding:24px}
.cat{background:#171e26;border:1px solid #243;border-radius:10px;padding:14px 16px;margin:12px 0}
h2{margin:0 0 4px;color:#9fe} .q{font-size:13px;color:#9ab;margin-bottom:8px}
ul{list-style:none;margin:0;padding:0} li{padding:5px 8px;border-radius:6px;margin:2px 0}
li.r0{background:#15351f;border:1px solid #4c8} li.r1{background:#12301c;border:1px solid #294}
li.r3{opacity:.55}
.v{display:inline-block;min-width:150px;font-weight:600}
.p{font-weight:700;color:#fd8;display:inline-block;min-width:80px} a{color:#cfe} em{color:#89a;font-size:12px}
</style></head><body><h1>🚂 RC-Park · Live Spur-N Preise (eBay)</h1>{{ROWS}}</body></html>"""

# ---------------------------------------------------------------- CLI
def main():
    p = argparse.ArgumentParser(description="Sweet-Spot-Finder für Spur-N-Teile (RC-Park)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cats", help="Kategorien auflisten")
    d = sub.add_parser("dashboard", help="HTML-Deal-Dashboard (Links, billigste zuerst)")
    d.add_argument("--cat", nargs="*", help="nur diese Kategorien (sonst alle)")
    d.add_argument("--out", default="rcpark_deals_dashboard.html")
    d.add_argument("--no-open", action="store_true")
    l = sub.add_parser("live", help="Echte Preise via eBay-API + Sweet-Spot (braucht EBAY_APP_ID/CERT_ID)")
    l.add_argument("--cat", nargs="*")
    l.add_argument("--out", default="rcpark_deals_live.html")
    a = p.parse_args()
    if a.cmd == "cats": cmd_cats()
    elif a.cmd == "dashboard": cmd_dashboard(a.cat, a.out, not a.no_open)
    elif a.cmd == "live": cmd_live(a.cat, a.out)

if __name__ == "__main__":
    main()
