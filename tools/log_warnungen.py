#!/usr/bin/env python3
"""log_warnungen.py LOG_ODER_ORDNER ... [--json AUS.json] [--top 30] - alle Warnungen/Fehler aus COLMAP-/Ketten-Logs sammeln, gleiche zusammenfassen, zaehlen.
Lehre 15.11.2026 (Nutzer): der globale Mapper wurde verworfen, obwohl die Ursache als Warnung im Log stand
("Less than 50% of cameras have prior focal lengths"); ebenso "GPU nicht verfuegbar" und "CuTexImage ... out of memory" blieben ungelesen.
Erkannt: glog-Zeilen W.../E.../F... (COLMAP), WARNUNG/FEHLER/HINWEIS (eigene Werkzeuge), Warning/Error/Traceback, 'Falling back', 'nicht verfuegbar',
'out of memory', NO_CONVERGENCE, 'KEINE_LOESUNG', 'ABBRUCH'. Zahlen/Zeitstempel/Pfade werden fuer die Zusammenfassung neutralisiert.
Ordner: alle *.log darin (nicht rekursiv). Exit 0 immer (Bericht); die Gesamtkette schreibt das Ergebnis in ihren Bericht ('warnungen')."""
import sys, os, re, json, glob, collections

MUSTER = re.compile(r"^[WEF]\d{8} |WARNUNG|FEHLER|HINWEIS|Warning|WARNING|Error|Traceback|Falling back|nicht verfuegbar|out of memory|NO_CONVERGENCE|KEINE_LOESUNG|ABBRUCH|rejected")
NEUTRAL = [(re.compile(r"^[WEFI]\d{8} [\d:.]+ +\d+ "), ""), (re.compile(r"/[\w./\-]+"), "<pfad>"), (re.compile(r"0x[0-9a-f]+"), "<hex>"), (re.compile(r"-?\d+([.,]\d+)?"), "#")]
AUSNAHME = re.compile(r"Unknown EXIF orientation|^\s+File \"|raise |warnings\.warn")   # bekannt harmlos bzw. Traceback-Zwischenzeilen


def sammeln(pfade, ab_zeile=None, seit=None):
    """ab_zeile = {pfad: n}: in dieser Datei nur Zeilen NACH Zeile n; seit = Zeitstempel: andere Dateien nur, wenn danach geaendert.
    16.11.2026: die Gesamtkette meldete als 'WARNUNGEN im Lauf' auch alles aus frueheren Laeufen (das Log wird fortgeschrieben) - 16 laengst behobene Fehler standen oben."""
    ab_zeile = ab_zeile or {}
    dateien = []
    for p in pfade:
        dateien += sorted(glob.glob(os.path.join(p, "*.log"))) if os.path.isdir(p) else [p]
    z = collections.OrderedDict()
    for d in dateien:
        try: zeilen = open(d, errors="replace").read().splitlines()
        except OSError: continue
        if seit is not None and d not in ab_zeile and os.path.getmtime(d) < seit: continue
        ab = ab_zeile.get(d, 0)
        for nr, l in enumerate(zeilen, 1):
            if nr <= ab or not MUSTER.search(l) or AUSNAHME.search(l): continue
            k = l.strip()
            for m, e in NEUTRAL: k = m.sub(e, k)
            k = k[:200]; e = z.setdefault(k, dict(n=0, beispiel=l.strip()[:300], datei=d, zeile=nr, dateien=set())); e["n"] += 1; e["dateien"].add(os.path.basename(d))
    return [dict(n=e["n"], text=e["beispiel"], datei=e["datei"], zeile=e["zeile"], dateien=sorted(e["dateien"])) for e in sorted(z.values(), key=lambda e: -e["n"])]


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    top = int(a[a.index("--top") + 1]) if "--top" in a else 30; aus = a[a.index("--json") + 1] if "--json" in a else ""
    pf = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--top", "--json"))]
    w = sammeln(pf)
    print(f"{len(w)} verschiedene Warnungen/Fehler in {len(pf)} Quelle(n):")
    for e in w[:top]: print(f"  {e['n']:5d}x  {e['text'][:170]}   [{os.path.basename(e['datei'])}:{e['zeile']}]")
    if aus: json.dump(w, open(aus, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
