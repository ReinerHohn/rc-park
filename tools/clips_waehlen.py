#!/usr/bin/env python3
"""clips_waehlen.py <video_kandidaten.json> [--max 12] - Clips fuer die SfM automatisch waehlen (ersetzt die Sichtpruefung von Hand).
Lehre Schwabentor 2026-11-14: Auswahl nach Kontaktabzug von Hand; ein CGI-Standbild ('durch Zeit und Feuer') bestand die Merkmalspruefung.
Regeln (allgemein):
  1. geprueft, >= --min_treffer Treffer und Trefferanteil >= --min_anteil (oder >= 15 Treffer bei langen Clips)
  2. Titel ohne Archiv/Geschichte/Animation (Wortliste) und ohne Jahreszahl < --ab_jahr (heutiger Bauzustand)
  2b Titel nennt ein ANDERES Objekt des Repos (modelle/*/objekt.json name), aber nicht dieses -> raus (aehnliche Tortuerme verwechselbar:
     'Martinstor'-Clip bestand die Schwabentor-Pruefung mit 5 Treffern). Mit --objekt.
  3. Standbild-Clips (Treffer an fast jedem Bild, aber nur 1 Objektfoto getroffen und Dauer > 60 s) raus; Rest faellt in
     tools/fotos_sammeln.py als Dublette weg (Vorschau-Vergleich)
Ausgabe: JSON-Liste [{id, fps, max, titel, grund}] auf stdout bzw. --aus; fps so, dass ~120 Bilder je Clip entstehen (0,5..2 fps).
"""
import sys, json, re, argparse

SPERR = re.compile(r"archiv|archive|history|geschichte|histor|zeitreise|animation|cgi|rekonstruktion|reconstruction|footage|damals|früher|frueher", re.I)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("kandidaten"); ap.add_argument("--aus", default=""); ap.add_argument("--max", type=int, default=12)
    ap.add_argument("--min_treffer", type=int, default=3); ap.add_argument("--min_anteil", type=float, default=0.1); ap.add_argument("--ab_jahr", type=int, default=2015)
    ap.add_argument("--objekt", default="", help="objekt.json dieses Objekts (Name) - andere Objektnamen aus modelle/*/objekt.json sperren")
    a = ap.parse_args(); K = json.load(open(a.kandidaten))["clips"]; wahl = []; raus = []
    eigen, andere = None, set()
    if a.objekt:
        import os, glob
        wort = lambda n: re.split(r"[\s(,-]", n.strip())[0].lower() if n else ""
        eigen = wort(json.load(open(a.objekt)).get("name", "")); root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(a.objekt))))
        for p in glob.glob(os.path.join(root, "modelle", "*", "objekt.json")):
            try: w = wort(json.load(open(p)).get("name", ""))
            except Exception: continue
            if len(w) >= 5 and w != eigen and w not in ("historisches",): andere.add(w)
    for c in K:
        if c.get("status") != "geprueft": continue
        t, b = c.get("treffer", 0), max(1, c.get("bilder", 1)); titel = c.get("titel", "")
        jahre = [int(j) for j in re.findall(r"\b(19\d\d|20\d\d)\b", titel)]
        if t < a.min_treffer or (t / b < a.min_anteil and t < 15): raus.append((c["id"], "zu wenig Treffer")); continue
        if SPERR.search(titel): raus.append((c["id"], "Titel Archiv/Geschichte/Animation")); continue
        tl = titel.lower(); fremd = [w for w in andere if w in tl]
        if fremd and eigen and eigen not in tl: raus.append((c["id"], f"anderes Objekt im Titel ({fremd[0]})")); continue
        if jahre and min(jahre) < a.ab_jahr: raus.append((c["id"], f"Jahr {min(jahre)}")); continue
        if t / b > 0.6 and c.get("fotos_getroffen", 0) <= 1 and (c.get("dauer") or 0) > 60: raus.append((c["id"], "Standbild-Verdacht")); continue
        du = c.get("dauer") or 60; fps = min(2.0, max(0.5, 120 / du))
        wahl.append(dict(id=c["id"], fps=round(fps, 2), max=int(min(300, du * fps)), titel=titel, treffer=t, bilder=b))
    wahl.sort(key=lambda w: -w["treffer"]); wahl = wahl[:a.max]
    out = dict(gewaehlt=wahl, verworfen=[dict(id=i, grund=g) for i, g in raus])
    if a.aus: json.dump(out, open(a.aus, "w"), indent=1, ensure_ascii=False)
    for w in wahl: print(f"  JA   {w['id']} {w['treffer']}/{w['bilder']} fps {w['fps']} {w['titel'][:60]!r}")
    for i, g in raus: print(f"  NEIN {i} {g}")


if __name__ == "__main__":
    main()
