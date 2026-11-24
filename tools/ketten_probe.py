#!/usr/bin/env python3
"""ketten_probe.py - Helfer des Ketten-Probelaufs (tools/ketten_probelauf.sh): Fotowahl, Marken verstellen, Sichern der Kettenausgaben im Code-Ordner, Auswertung.

WARUM (24.11.2026, Kettenlauf 1122za): nach dem Merge von 16 Aenderungen (Schnelltest 0 Fehler) brach die Kette nach 2 min ab - der Seitenmodell-Code hatte sich
geaendert, die Kette schrieb das SfM-Netz neu, die dichte Wolke galt als "aelter als das Netz" -> Abbruch mit Handanweisung (--neu dicht). Einzeltests und
Schnelltest pruefen Stufen EINZELN, nicht das ZUSAMMENSPIEL der Stufen mit vorhandenen Zwischenstaenden. Der Probelauf laesst die ganze Kette auf einem kleinen
Objekt in einer KOPIE laufen; dieses Werkzeug liefert die Bausteine (nur Standardbibliothek, laeuft mit python3 -I).

  fotowahl KAMERAS.json FOTOORDNER AUSORDNER [--n 60] [--plan]
      N registrierte Bilder eines frueheren SfM-Laufs, gleichmaessig ueber den Blickwinkel um die Kameramitte verteilt (alle hatten registriert -> kleines
      Netz traegt). Kopiert die echten Dateien (Verknuepfungen aufgeloest, Praefix 'eigen__' weg). --plan: nur auflisten.
  marken DATEN [MODELL] [--plan]
      Szenario "Code-Stand einer Stufe geaendert": jeder Code-Stand (12 Hex-Zeichen von tools/code_stand.py, auch mit Anhang '+...'/'_...'; in *stand.json jeder,
      sonst nur unter Schluesseln mit code/stand/detektor - Daten-Kennungen wie RAHMEN 'id' bleiben) in JSON-Dateien unter
      DATEN (ohne beiseitegelegte *.alt_*/.veraltet_*-Staende und Fotoordner) und MODELL wird auf 000000000000 gesetzt, und das SfM-Netz pipe/sfm/sparse/0 bekommt
      die Zeit jetzt (= "Netz neu geschrieben", genau der Fall 1122za: Wolke/Kameras aelter als das Netz). rc 3, wenn nichts zu verstellen war.
  sichern CODEORDNER MARKE TAR [--getrackt LISTE]
      alle Dateien/Verknuepfungen im Code-Ordner, die nicht im Repo-Stand sind (LISTE = ls-tree -r --name-only REV) oder nach der Marke (Datei) geaendert sind (= was die Kette ausserhalb von DATEN schreibt: modelle/<ziel>,
      daten/<ziel>, Generator-Rumpf, STL), als tar sichern (ohne __pycache__).
  auswerten BERICHT.json [--log LOG --ab-zeile N] [--szenario NAME] [--bekannt a,b] [--json AUS]
      letzter Lauf (ab LAUF_START): Stufen, rc, Zeit, rote Stufen getrennt nach ABLAUF (veralteter Stand, Handanweisung, Absturz, Abbruch, stiller Erfolg *_beleg)
      und DATEN (Tor-Urteil am Objekt). rc 0 = Ablauf in Ordnung, 1 = Ablauffehler, 2 = Abbruch aus Datengruenden (kein Urteil ueber den Ablauf).
      --bekannt: Stufennamen, die schon im Grundstand rot waren -> nur Hinweis.
"""
import os, sys, re, json, time, math, shutil, tarfile

HEX = re.compile(r"^[0-9a-f]{12}(?=$|[+_])")
NULL = "000000000000"
ALT = re.compile(r"\.alt_|\.veraltet_|beiseite")
# ABLAUF: Folgestufe nimmt einen alten Stand, verlangt Handarbeit oder stuerzt ab
ABLAUF = re.compile(r"aelter als|veraltet|--neu \w|RCPARK_PIPE_NEU|von Hand|Handanweisung|nicht neu geschrieben|NICHT neu|Traceback|abgestuerzt|"
                    r"(Error|Exception)\b|nicht lesbar|zuerst Stufe", re.I)
# DATEN: Abbruch mit Urteil ueber das Objekt (Lage, Seitenverklebung, zu wenig Bilder) - sagt nichts ueber den Ablauf
DATEN = re.compile(r"keine Lage besteht|SEITEN-BLICK-TOR durchgefallen|LAGE FRUEH|keine Bilder in fotos_dir|registriert[^|]*< ?50|DATENMANGEL|Platz", re.I)


def _schreiben(p, d):
    t = p + ".tmp_probe"; json.dump(d, open(t, "w"), ensure_ascii=False, indent=1); os.replace(t, p)


# ---------------------------------------------------------------- fotowahl
def fotowahl(kameras, fotos, aus, n=60, plan=False):
    K = json.load(open(kameras)); b = [x for x in K.get("bilder", []) if x.get("C") and len(x["C"]) >= 2]
    if not b: raise SystemExit(f"FEHLER {kameras}: keine Bilder mit Kameramitte C")
    mx = sum(x["C"][0] for x in b) / len(b); my = sum(x["C"][1] for x in b) / len(b)
    b.sort(key=lambda x: (math.atan2(x["C"][1] - my, x["C"][0] - mx), x["name"]))
    n = min(n, len(b)); wahl = [b[int(i * len(b) / n)] for i in range(n)]
    ok, fehlt = [], []
    for x in wahl:
        q = os.path.realpath(os.path.join(fotos, x["name"]))
        (ok if os.path.isfile(q) else fehlt).append((x["name"], q))
    print(f"FOTOWAHL: {len(ok)} von {len(b)} registrierten Bildern (Ziel {n}), fehlend {len(fehlt)}" + (f": {[f for f, _ in fehlt][:5]}" if fehlt else ""))
    if plan:
        for nm, q in ok[:5]: print("    z. B.", nm, "<-", q)
        return ok
    os.makedirs(aus, exist_ok=True)
    for nm, q in ok:
        z = os.path.join(aus, nm[len("eigen__"):] if nm.startswith("eigen__") else nm)
        if not os.path.exists(z): shutil.copy2(q, z)
    return ok


# ---------------------------------------------------------------- marken
CODEKEY = re.compile(r"code|stand|detektor", re.I)      # nur Code-Staende; Daten-Kennungen (RAHMEN.json 'id', K-Dateien 'rahmen') bleiben


def _verstellen(o, wege, weg="", alle=False):
    """alle=True: Datei ist selbst eine Stand-Datei (*stand.json) - jeder Code-Stand darin zaehlt; sonst nur unter einem Schluessel mit code/stand/detektor."""
    if isinstance(o, dict): return {k: _verstellen(v, wege, f"{weg}/{k}", alle) for k, v in o.items()}
    if isinstance(o, list): return [_verstellen(v, wege, f"{weg}/{i}", alle) for i, v in enumerate(o)]
    if isinstance(o, str) and HEX.match(o) and not o.startswith(NULL):
        k = next((x for x in reversed(weg.split("/")) if x and not x.isdigit()), "")
        if alle or CODEKEY.search(k): wege.append(weg); return NULL + o[12:]
    return o


def marken(daten, modell=None, plan=False):
    geaendert = []
    for wurzel in [w for w in (daten, modell) if w and os.path.isdir(w)]:
        for d, dn, fn in os.walk(wurzel):
            dn[:] = [x for x in dn if not ALT.search(x) and not x.startswith("fotos") and x not in ("images", "stereo", "video_frames", "commons")]
            for f in fn:
                if not f.endswith(".json") or ALT.search(f): continue
                p = os.path.join(d, f)
                try:
                    if os.path.islink(p) or os.path.getsize(p) > 20e6: continue
                    o = json.load(open(p))
                except Exception: continue
                wege = []; neu = _verstellen(o, wege, alle=f.endswith("stand.json"))
                if wege:
                    geaendert.append((os.path.relpath(p, wurzel), wege))
                    if not plan: _schreiben(p, neu)
    netz = os.path.join(daten, "pipe", "sfm", "sparse", "0"); netz_f = sorted(os.listdir(netz)) if os.path.isdir(netz) else []
    if not plan:
        t = time.time()
        for f in netz_f: os.utime(os.path.join(netz, f), (t, t))
    for p, w in geaendert: print(f"MARKE {'(plan) ' if plan else ''}{p}: {len(w)} Code-Stand(e) -> {NULL} ({', '.join(w[:3])})")
    print(f"NETZ {'(plan) ' if plan else ''}pipe/sfm/sparse/0: {len(netz_f)} Dateien -> Zeit jetzt" if netz_f else "NETZ: pipe/sfm/sparse/0 fehlt")
    return geaendert, netz_f


# ---------------------------------------------------------------- sichern
def sichern(code, marke, tar, getrackt=None):
    """Eintraege (Dateien, Verknuepfungen) im Code-Ordner, die NICHT im Repo-Stand sind (getrackt = Menge relativer Pfade; None = nur Zeitkriterium) oder nach der
    Marke geaendert wurden -> tar (Zeiten bleiben). So bleiben auch Kettenausgaben eines frueheren Grundstands erhalten, die dieser Lauf nicht neu schrieb."""
    t0 = os.path.getmtime(marke); n = 0; eigen = {os.path.abspath(marke), os.path.abspath(os.path.join(code, ".ketten_probe"))}
    with tarfile.open(tar, "w") as T:
        for d, dn, fn in os.walk(code):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for x in fn + [y for y in dn if os.path.islink(os.path.join(d, y))]:
                p = os.path.join(d, x); r = os.path.relpath(p, code)
                if os.path.abspath(p) in eigen: continue
                if (getrackt is not None and r not in getrackt) or os.lstat(p).st_mtime > t0:
                    T.add(p, arcname=r, recursive=False); n += 1
    print(f"SICHERN: {n} Eintraege aus {code} -> {tar}"); return n


# ---------------------------------------------------------------- auswerten
def _text(e):
    t = [str(e.get(k) or "") for k in ("fehler", "grund", "hinweis")] + [" | ".join(map(str, e.get("ende") or []))]
    return " | ".join(x for x in t if x)


def auswerten(B, log_zeilen=None, bekannt=()):
    S = B.get("schritte") or []; st = max([i for i, e in enumerate(S) if e.get("stufe") == "LAUF_START"] or [-1])
    L = S[st + 1:] if st >= 0 else S; t_start = S[st].get("zeit", "") if st >= 0 else ""
    E = B.get("lauf_ergebnis") or {}; e_frisch = bool(E) and str(E.get("zeit", "")) >= t_start
    ende = e_frisch if log_zeilen is None else any("GESAMTKETTE_ENDE" in z for z in log_zeilen)
    tb = sum("Traceback (most recent call last)" in z for z in (log_zeilen or []))
    rot = [e for e in L if e.get("ok") is False]; abbruch = str(E.get("abbruch") or "") if e_frisch else ""
    ablauf, daten = [], []
    for e in rot:
        t = _text(e); name = e.get("stufe", "?")
        if name in bekannt: daten.append((name, "bekannt aus dem Grundstand: " + t)); continue
        if name == "abbruch": continue
        (ablauf if ABLAUF.search(t) or name.endswith("_beleg") else daten).append((name, t))
    urteil = 0
    if abbruch:
        if DATEN.search(abbruch) and not ablauf: urteil = 2; daten.append(("abbruch", abbruch))
        else: ablauf.append(("abbruch", abbruch))
    if not ende: ablauf.append(("ende", "Kette ohne GESAMTKETTE_ENDE / ohne lauf_ergebnis dieses Laufs (Absturz, Abbruch von aussen, Zeitgrenze)"))
    if tb: ablauf.append(("traceback", f"{tb} Traceback(s) im Log dieses Laufs"))
    if ablauf: urteil = 1
    sek = sum(float(e.get("sekunden") or 0) for e in L)
    return dict(urteil=urteil, stufen=len(L), rc=E.get("rc") if e_frisch else None, sekunden=round(sek), ende=ende, ablauf=ablauf, daten=daten,
                erster_fehler=ablauf[0] if ablauf else None, start=t_start,
                langsam=sorted([(e.get("stufe"), round(float(e.get("sekunden") or 0))) for e in L if e.get("sekunden")], key=lambda x: -x[1])[:5])


def drucken(szenario, R):
    wort = {0: "OK", 1: "FEHLER", 2: "KEIN_URTEIL"}[R["urteil"]]
    print(f"SZENARIO {szenario}: {wort} | rc {R['rc']} | {R['stufen']} Stufen, {R['sekunden'] / 60:.1f} min | Ende {'ja' if R['ende'] else 'NEIN'} | "
          f"Ablauffehler {len(R['ablauf'])} | rot (Daten) {len(R['daten'])}" + (": " + ", ".join(n for n, _ in R["daten"][:8]) if R["daten"] else ""))
    if R["langsam"]: print("    langsamste: " + ", ".join(f"{n} {s} s" for n, s in R["langsam"]))
    for n, t in R["ablauf"][:5]: print(f"    ABLAUF {n}: {t[:220]}")
    if R["erster_fehler"]: print(f"    ERSTER FEHLER: {R['erster_fehler'][0]}: {R['erster_fehler'][1][:300]}")


def main(a):
    if not a or a[0] in ("-h", "--help"): print(__doc__); return 0
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    plan = "--plan" in a; pos = [x for i, x in enumerate(a[1:], 1) if not x.startswith("--") and not (i > 1 and a[i - 1] in ("--n", "--log", "--ab-zeile", "--szenario", "--bekannt", "--json", "--getrackt"))]
    if a[0] == "fotowahl": return 0 if fotowahl(pos[0], pos[1], pos[2], int(opt("--n", "60")), plan) else 3
    if a[0] == "marken":
        g, nf = marken(pos[0], pos[1] if len(pos) > 1 else None, plan); return 0 if (g or nf) else 3
    if a[0] == "sichern":
        g = set(open(opt("--getrackt")).read().splitlines()) if opt("--getrackt") else None; sichern(pos[0], pos[1], pos[2], g); return 0
    if a[0] == "auswerten":
        B = json.load(open(pos[0])); lz = None
        if opt("--log"):
            lz = open(opt("--log"), errors="replace").read().splitlines()[int(opt("--ab-zeile", "0")):] if os.path.exists(opt("--log")) else []
        R = auswerten(B, lz, [x for x in (opt("--bekannt", "") or "").split(",") if x]); drucken(opt("--szenario", "lauf"), R)
        if opt("--json"): _schreiben(opt("--json"), dict(R, szenario=opt("--szenario", "lauf"), bericht=pos[0]))
        return R["urteil"]
    print("unbekannter Befehl", a[0]); return 3


if __name__ == "__main__": sys.exit(main(sys.argv[1:]))
