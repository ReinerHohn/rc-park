#!/usr/bin/env python3
"""Wissen suchen: EIN Aufruf durchsucht Wissensbaum, Register, Archiv, Logbuecher, Memory, Werkzeug-Kopfkommentare und git log.

Anlass 24.11.2026: Vorarbeit zu Fotoauswahl/Bildwert/Sweet Spot (VERSUCHSREGISTER BM/BN, tools/foto_wichtigkeit.py,
bildwert.py, sweetspot.py) wurde nicht gefunden, weil nur der Baum und mit dem falschen Wort gesucht wurde; Archiv
("archiviert = bringt nichts", Nutzer) und Memory-Archiv wurden gar nicht durchsucht.

PROJEKTKOPIE der projektunabhaengigen Fassung (Vorschlag fuer ~/git/claude-mds: claude/skills/doku-pflege/wissen_suchen.py, Stand in
tools/claude_mds_vorschlag/). Quellen kommen aus .claude/doku-pflege.json "wissen" - kein rc-park-Pfad im Code. Nach Uebernahme wird diese
Datei ein Aufruf der Skill-Fassung.
Aufruf:  python3 -I tools/wissen_suchen.py "<begriff>" [weitere ...] [--max 5] [--top 10] [--ohne-git] [--ohne-synonyme] [--memory DIR]
         (Skill-Fassung: python3 ~/.claude/skills/doku-pflege/wissen_suchen.py ... im Projektordner)
- Mehrwort-Suche wie man fragt ("weniger Fotos dichte Wolke auswaehlen"): Fuellwoerter fallen weg, Wendungen aus Synonymgruppen bleiben
  zusammen, Originalwoerter treffen auch als Stamm/Teilwort ("auswaehlen" ~ "Fotoauswahl", "Wert" ~ "Rueckfallwert").
- Ausgabe zuerst TOP 10 nach Relevanz (IDF, Abdeckung aller Begriffe, Bonus Dateiname/Ueberschrift), dann je Quellgruppe.
  Nachweis: tools/wissen_wiederfinden.py (Recall@5 auf echten Verlustfaellen, Schnelltest).
- Jeder Begriff wird um seine Synonymgruppe aus tools/wissen_synonyme.json erweitert (Fotoauswahl -> Bildauswahl,
  Teilmenge, Bildwert, Sweet Spot, ...). Gross/klein und Umlaut/ae egal; Woerter bis 4 Zeichen nur als ganzes Wort.
- Mehrere Begriffe: Zeilen mit mehr getroffenen Begriffen zuerst; --und = nur Zeilen mit allen Begriffen.
- Ausgabe gruppiert, Baum-Treffer zuerst, je Treffer "Datei:Zeile: Text" (gekuerzt), je Gruppe max. --max Zeilen.
- Gruppe "Aehnliche Werkzeuge (Wortschatz)" (24.11.2026, tools/werkzeug_aehnlich.py): tools/*.py, deren Kopf-Wortschatz dem Suchtext nahe
  ist, auch OHNE gleiches Wort (formsitz "Formmass" ~ flaechen_mass "Formvergleich ueber Flaechen"). Vor jedem Agentenauftrag/neuen Werkzeug
  ansehen: steht dort ein Vorlaeufer, gehoert er in den Auftrag und in die Kopfzeile "Verwandt:" des neuen Werkzeugs (--ohne-aehnlich = aus).
- Wenige Baumtreffer (< 3): Wortvorschlaege aus den aehnlichen Werkzeugen ausgeben - damit erneut suchen und ein Treffer-Wort als Synonym
  in tools/wissen_synonyme.json eintragen (so lernt die Synonymliste aus Fehlsuchen).
Verwandt: tools/wissensbaum_luecken.py (Vollstaendigkeit des Baums), tools/werkzeug_aehnlich.py, tools/wissen_ablage_pruefen.py.
rc 0 = Treffer, rc 1 = nichts gefunden, rc 2 = Aufruffehler.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

GRUPPEN_REIHE = ["Wissensbaum", "Register/Methoden", "Logbuecher", "Archiv", "Memory", "Werkzeuge (Kopf)",
                 "Aehnliche Werkzeuge (Wortschatz)", "git log"]


def falte(s):
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return s


def lade_synonyme(pfad):
    try:
        return json.loads(Path(pfad).read_text(encoding="utf-8")).get("gruppen", [])
    except (OSError, ValueError):
        return []


def erweitern(begriff, gruppen):
    """Alle Woerter der Gruppen, zu denen der Begriff passt (gleich, oder eines enthaelt das andere bei >= 5 Zeichen).
    Steht der Begriff in einer Gruppe GENAU, zaehlen nur solche Gruppen (24.11.: "Drahtgitter" = Kantenmodell zog ueber "Draht" die
    Oberleitungs-Gruppe mit - gleiche Silbe, anderes Ding)."""
    b = falte(begriff)
    aus = [begriff]
    genau = [g for g in gruppen if any(falte(w) == b for w in g)]
    if genau:
        for g in genau:
            aus += [x for x in g if x not in aus]
        return aus
    for g in gruppen:
        for w in g:
            fw = falte(w)
            # nur wenn der Suchbegriff das Gruppenwort ENTHAELT (spezieller ist): "Bildauswahlstufe" -> Bildauswahl. Umgekehrt nicht:
            # "Flaeche" zog sonst die ganze Flaechenmass-Gruppe (24.11.2026)
            if fw == b or (len(fw) >= 5 and fw in b):
                aus += [x for x in g if x not in aus]
                break
    return aus


def muster(woerter):
    teile = []
    for w in woerter:
        fw = re.escape(falte(w)).replace(r"\ ", r"[\s_-]?")
        teile.append(r"(?<![a-z0-9])" + fw + r"(?![a-z0-9])" if len(falte(w)) <= 4 else fw)
    return re.compile("|".join(teile))


# Quellen je Projekt: <repo>/.claude/doku-pflege.json, Schluessel "wissen" (fehlende Schluessel = Standard unten). Projektunabhaengig
# (24.11.2026, Nutzer: Werkzeug nach ~/git/claude-mds, Skill doku-pflege); rc-park traegt dort modelle/ ein.
KONFIG_STANDARD = {
    "baum": ["PROJEKT.md", "Doku/projekt/**/*.md"],
    "register": ["Doku/*.md"],
    "logbuch": ["LOGBUCH*.md", "Doku/**/LOGBUCH*.md"],
    "archiv": ["Doku/archiv/**/*.md"],
    "werkzeuge": ["tools/*.py", "scripts/*.py"],
    "meta_werkzeuge": [],
    "synonyme": ".claude/wissen_synonyme.json",
}


def konfig(wurzel):
    k = dict(KONFIG_STANDARD)
    try:
        k.update(json.loads((Path(wurzel) / ".claude" / "doku-pflege.json").read_text(encoding="utf-8")).get("wissen", {}))
    except (OSError, ValueError, AttributeError):
        pass
    return k


def _globs(w, muster_liste, ohne=()):
    aus, gesehen = [], set(ohne)
    for g in muster_liste:
        for p in sorted(Path(w).glob(g)):
            r = p.resolve()
            relp = "/" + str(p.relative_to(w))
            if p.is_file() and r not in gesehen and "/.claude/worktrees/" not in relp and "/node_modules/" not in relp:
                gesehen.add(r)
                aus.append(p)
    return aus


def quellen(wurzel, memory, kfg=None):
    w = Path(wurzel)
    k = kfg or konfig(w)
    q = {g: [] for g in GRUPPEN_REIHE}
    q["Wissensbaum"] = _globs(w, k["baum"])
    schon = {p.resolve() for p in q["Wissensbaum"]}
    q["Logbuecher"] = _globs(w, k["logbuch"], schon)
    schon |= {p.resolve() for p in q["Logbuecher"]}
    q["Archiv"] = _globs(w, k["archiv"], schon)
    schon |= {p.resolve() for p in q["Archiv"]}
    q["Register/Methoden"] = _globs(w, k["register"], schon)
    if memory and Path(memory).is_dir():
        q["Memory"] = sorted(Path(memory).glob("*.md"))
    return {g: [p for p in ps if p.exists()] for g, ps in q.items()}


def werkzeug_kopf(p):
    """Kopfkommentar + Modul-Docstring der ersten ~80 Zeilen: [(zeilennr, text)]."""
    try:
        zeilen = p.read_text(encoding="utf-8", errors="replace").split("\n")[:80]
    except OSError:
        return []
    aus, im_doc, quote = [], False, None
    for i, z in enumerate(zeilen, 1):
        s = z.strip()
        if im_doc:
            aus.append((i, z))
            if quote in s:
                break
            continue
        if s.startswith("#") or not s:
            if s.startswith("#") and not s.startswith("#!"):
                aus.append((i, z))
            continue
        mq = re.match(r'^[rubRUB]*("""|\'\'\')', s)
        if mq:
            quote = mq.group(1)
            aus.append((i, z))
            if s.count(quote) >= 2 and len(s) > 3:
                break
            im_doc = True
            continue
        if s.startswith(("import ", "from ")) and aus:
            continue
        break
    return aus


def stelle(text, rx, breite=220):
    t = text.strip()
    if len(t) <= breite:
        return t
    m = rx.search(falte(t))
    a = max(0, (m.start() if m else 0) - 60)
    return ("…" if a else "") + t[a:a + breite] + "…"


def werkzeug_dateien(wurzel, kfg=None):
    k = kfg or konfig(wurzel)
    meta = META_WERKZEUGE | set(k.get("meta_werkzeuge", []))
    return [p for p in _globs(wurzel, k["werkzeuge"]) if p.name not in meta]


def aehnliche_werkzeuge(wurzel, begriffe, gruppen, top=6, kfg=None):
    """([(wert, name, erste Zeile)], modul) ueber werkzeug_aehnlich.py (liegt neben dieser Datei); leer, wenn das Modul fehlt."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import werkzeug_aehnlich as wa
    except ImportError:
        return [], None
    text = " ".join(x for b in begriffe for x in erweitern(b, gruppen))
    return wa.aehnliche(text, werkzeug_dateien(wurzel, kfg), top=top), wa


def wortvorschlaege(wurzel, begriffe, gruppen, aehnlich, wa, n=8):
    """Woerter (>= 6 Zeichen) aus den Koepfen der aehnlichsten Werkzeuge, die im Suchtext fehlen, nach Haeufigkeit."""
    if not aehnlich or wa is None:
        return []
    pfad = {p.name: p for p in werkzeug_dateien(wurzel)}
    schon = {falte(x) for b in begriffe for x in erweitern(b, gruppen)}
    zaehl = {}
    for _, name, _ in aehnlich[:3]:
        for wort in re.findall(r"[a-z]{6,}", falte(wa.kopf(pfad[name]))):
            if wort in wa.STOPP or any(wort in x or x in wort for x in schon):
                continue
            zaehl[wort] = zaehl.get(wort, 0) + 1
    return [w for w, _ in sorted(zaehl.items(), key=lambda t: (-t[1], -len(t[0])))[:n]]


GRUPPEN_FAKTOR = {"Wissensbaum": 1.15, "Register/Methoden": 1.1, "Werkzeuge (Kopf)": 1.1, "Archiv": 0.95,
                  "Logbuecher": 0.9, "Memory": 0.9, "git log": 0.8, "Aehnliche Werkzeuge (Wortschatz)": 0.7}
SYNONYM_GEWICHT = 0.75
META_WERKZEUGE = {"wissen_suchen.py", "wissen_bedeutung.py", "wissen_fragen.py", "werkzeug_aehnlich.py", "wissensbaum_luecken.py", "wissen_ablage_pruefen.py", "wissen_wiederfinden.py",
                  "test_wissensbaum_luecken.py", "test_wissen_ablage.py"}


STOPPWOERTER = set("""der die das den dem des ein eine einen einem einer und oder aber mit ohne von vom zu zum zur im in an am auf aus bei
fuer für ist sind wird werden wurde war hat haben nach vor ueber über unter wie was wer ob als auch noch nur nicht kein keine es er sie wir
man sich so dann wenn weil dass statt beim bis gegen durch um mal schon jetzt hier dort sehr mehr
ich du mich mir mein meine meinen meinem unser unsere uns ihr euch kann koennen kannst muss musst soll sollte will wollen warum wieso
weshalb welche welcher welches wo wann woran gibt geht immer einfach ganz eigentlich bitte etwa dabei denn doch nun also da dem diese
dieser dieses jemand etwas irgendwie""".split())  # 25.11.: Alltagsfragen in ganzen Saetzen


def begriffe_teilen(begriffe, gruppen):
    """Suchtext -> Begriffe: alle Woerter (auch aus Mehrwort-Argumenten), Wendungen aus einer Synonymgruppe ("Sweet Spot",
    "dichte Wolke", "weniger Fotos") bleiben zusammen, Fuellwoerter fallen weg (24.11.2026: "wie hoch ist das Martinstor" -
    Fuellwoerter senkten die Abdeckung jeder echten Fundstelle)."""
    ganz = {falte(w) for g in gruppen for w in g}
    # Satzzeichen ab (25.11.2026: ganze Fragesaetze - "schief," und "Senkrechte?" trafen sonst nur mit Komma/Fragezeichen)
    woerter = [y for b in begriffe for x in b.split() for y in [x.strip(PUNKT)] if y]
    aus, i = [], 0
    while i < len(woerter):
        for n in (3, 2):
            if i + n <= len(woerter) and falte(" ".join(woerter[i:i + n])) in ganz:
                aus.append(" ".join(woerter[i:i + n]))
                i += n
                break
        else:
            if falte(woerter[i]) not in STOPPWOERTER:
                aus.append(woerter[i])
            i += 1
    return aus or woerter


PUNKT = ".,;:!?()[]{}\"'„“”‚‘’«»…"
ENDUNGEN = ("ern", "en", "er", "es", "e", "n", "s")


def stamm_muster(wort):
    """Originalwort des Nutzers -> Stamm-Regex: Endung ab (mind. 5 Zeichen bleiben), Umlaut lose (ae|a), als Teilwort -
    "auswaehlen" trifft "Fotoauswahl", "Zusatzfotos" trifft "zusatzfoto". Woerter < 6 Zeichen bleiben wie muster()."""
    f = falte(wort)
    if " " in f or len(f) < 4:
        return None
    if len(f) < 6:
        # kurzes Nomen: ganzes Wort ODER Grundwort am Ende eines Kompositums ("Wert" -> "Rueckfallwert"), nie mitten im Wort
        e = re.escape(f)
        return re.compile(rf"(?<![a-z0-9]){e}(?![a-z0-9])|[a-z]{{3,}}{e}(?![a-z0-9])")
    for e in ENDUNGEN:
        if f.endswith(e) and len(f) - len(e) >= 5:
            f = f[: -len(e)]
            break
    r = re.escape(f)
    for u, v in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        r = r.replace(u, f"(?:{u}|{v})")
    return re.compile(r)


FRAGEN = True         # Alltagsfragen je Zeile mitsuchen (doc2query, 24.11.2026)


def zeilen_hash(z):
    import hashlib
    return hashlib.sha1(z.strip().encode("utf-8")).hexdigest()[:12]


def alltagsfragen(wurzel, rel, kfg=None):
    """{zeilen_hash: [fragen]} aus <fragen_ordner>/<rel mit / -> __>.jsonl (Konfig 'fragen_ordner', Standard Doku/projekt/.fragen);
    geschrieben von tools/wissen_fragen.py. Fehlt die Datei: leer."""
    k = kfg or konfig(wurzel)
    q = Path(wurzel) / k.get("fragen_ordner", "Doku/projekt/.fragen") / (str(rel).replace("/", "__") + ".jsonl")
    aus = {}
    try:
        for z in q.read_text(encoding="utf-8").splitlines():
            if z.strip():
                d = json.loads(z)
                aus[d["hash"]] = d.get("fragen", [])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return aus


TEILWORT = True       # Kompositazerlegung (allgemein statt je Fall gelernter Synonyme, 24.11.2026)
TEIL_GEWICHT = 0.6


def wortschatz_aus(zeilen, mindest=2):
    """Woerter (>= 3 Zeichen, gefaltet), die im durchsuchten Wissen mindestens `mindest`-mal vorkommen."""
    z = {}
    for x in zeilen:
        for wort in re.findall(r"[a-z]{3,}", x[4]):
            z[wort] = z.get(wort, 0) + 1
    return {w for w, n in z.items() if n >= mindest}


def teilwoerter(begriff, wortschatz):
    """Kompositum -> Teile, die es im Wissen gibt ("Gewoelberippen-Buendel" -> gewoelbe, rippen, buendel; "Arbeitsspeicher" ->
    arbeit, speicher). Bindestrich trennt immer; sonst die Zerlegung mit dem laengsten bekannten Grundwort (>= 4 Zeichen) und
    bekanntem Bestimmungswort (>= 3, Fugen-s/-n/-en erlaubt). Ohne Wortschatz: nur Bindestrich."""
    f = falte(begriff)
    teile = [x for x in re.split(r"[-_/]", f) if len(x) >= 4] if re.search(r"[-_/]", f) else []
    for wort in (teile or [f]):
        if len(wort) < 9 or not wortschatz:
            continue
        for i in range(3, len(wort) - 3):
            kopf, grund = wort[:i], wort[i:]
            if grund in wortschatz and any(
                    k in wortschatz and len(k) >= 3 for k in (kopf, kopf[:-1] if kopf.endswith(("s", "n")) else kopf,
                                                              kopf[:-2] if kopf.endswith("en") else kopf)):
                teile += [kopf.rstrip("s") if kopf.rstrip("s") in wortschatz else kopf, grund]
                break
    aus = []
    for x in teile:
        if x != f and x not in aus and x not in STOPPWOERTER:
            aus.append(x)
    return aus


def suchen(wurzel, begriffe, gruppen, memory=None, mit_git=True, und=False, kfg=None):
    """{gruppe: [(relevanz, "datei:zeile: text")]} nach Relevanz (24.11.2026, vorher nur ODER + Trefferzahl: "Formmass Flaeche" gab
    164 Baumtreffer, oben bahn-anlage.md "Druckflaeche"). Relevanz je Zeile = Summe je Begriff des besten Wortes (IDF ueber alle
    durchsuchten Zeilen; Synonym x0,75) x Abdeckung (getroffene Begriffe / alle)^1,5 + Bonus Dateiname/Ueberschrift, x Quellgruppe,
    lange Tabellenzeilen leicht abgewertet."""
    import math
    w = Path(wurzel)
    zeilen = []                                   # (gruppe, name, nr, text, faltung)

    for g, dateien in quellen(w, memory, kfg).items():
        for p in dateien:
            try:
                name = "memory/" + p.name if g == "Memory" else str(p.relative_to(w))
            except ValueError:
                name = str(p)
            fr = alltagsfragen(w, name, kfg) if FRAGEN and g != "Memory" else {}
            try:
                for nr, z in enumerate(p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                    zf = fr.get(zeilen_hash(z)) if fr else None
                    # Alltagsfragen zur Zeile (doc2query, tools/wissen_fragen.py) zaehlen beim Treffen mit, gezeigt wird die Zeile
                    zeilen.append((g, name, nr, z, falte(z + " ¦ " + " ".join(zf)) if zf else falte(z)))
            except OSError:
                pass
    werkzeugnamen = []
    # Meta-Werkzeuge (diese Suche, Lueckenpruefung, Nachweis) zitieren die Verlustfaelle im Kopf -> stuenden sonst bei jeder Suche oben
    for p in werkzeug_dateien(w, kfg):
        rel = str(p.relative_to(w))
        for nr, z in werkzeug_kopf(p):
            zeilen.append(("Werkzeuge (Kopf)", rel, nr, z, falte(z)))
        werkzeugnamen.append(p)
    terme = []
    wortschatz = wortschatz_aus(zeilen) if TEILWORT else set()
    for t in begriffe:
        ws_ = [(x, muster([x]), 1.0 if x == t else SYNONYM_GEWICHT) for x in erweitern(t, gruppen)]
        sm = stamm_muster(t)
        if sm is not None:
            ws_[0] = (t, sm, 1.0)
        schon = {falte(x) for x, _, _ in ws_}
        for teil in teilwoerter(t, wortschatz):
            if teil not in schon:
                schon.add(teil)
                ws_.append((teil, stamm_muster(teil) or muster([teil]), TEIL_GEWICHT))
        terme.append((t, ws_))
    alle_woerter = [x for _, ws_ in terme for x, _, _ in ws_]
    rx_alle = re.compile("|".join(rx.pattern for _, ws_ in terme for _, rx, _ in ws_)) if alle_woerter else re.compile("(?!)")
    if mit_git:
        cmd = ["git", "-C", str(w), "log", "--all", "-i", "--format=%h %as %s", "-n", "300"]
        for x in sorted(set(alle_woerter)):
            cmd += ["--grep", x]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            for z in r.stdout.splitlines():
                zeilen.append(("git log", "commit", z.split(" ")[0], z, falte(z)))
        except (OSError, subprocess.TimeoutExpired):
            pass

    kandidaten = [z for z in zeilen if rx_alle.search(z[4])]
    n_ges = max(1, len(zeilen))
    df = {x: sum(1 for z in kandidaten if rx.search(z[4])) for _, ws_ in terme for x, rx, _ in ws_}
    idf = {x: math.log((n_ges + 1) / (d + 1)) + 0.1 for x, d in df.items()}
    T = max(1, len(terme))

    def bewerte(f, stamm):
        summe, getroffen, name_bonus = 0.0, 0, 0.0
        for _, ws_ in terme:
            best = 0.0
            for x, rx, gew in ws_:
                if rx.search(f):
                    best = max(best, idf[x] * gew)
                if stamm and rx.search(stamm):
                    name_bonus = max(name_bonus, 0.5 * idf[x] * gew)
            if best > 0:
                summe += best
                getroffen += 1
        return summe, getroffen, name_bonus

    treffer = {g: [] for g in GRUPPEN_REIHE}
    for g, name, nr, z, f in kandidaten:
        stamm = falte(Path(name).stem).replace("_", " ").replace("-", " ") if g != "git log" else ""
        summe, getroffen, nb = bewerte(f, stamm)
        if not getroffen or (und and getroffen < T):
            continue
        r = summe * (getroffen / T) ** 1.5 + nb
        if z.lstrip().startswith("#") and g != "Werkzeuge (Kopf)":
            r *= 1.3                                  # Ueberschrift / Unterast-Titel
        r *= GRUPPEN_FAKTOR.get(g, 1.0) / (1 + max(0, len(z) - 400) / 1500)
        treffer[g].append((round(r, 3), f"{name}:{nr}: {stelle(z, rx_alle)}"))
    # der Werkzeugname selbst zaehlt (z. B. Suche "bildwert" -> tools/bildwert.py)
    for p in werkzeugnamen:
        stamm = falte(p.stem).replace("_", " ")
        summe, getroffen, nb = bewerte(stamm, "")
        if getroffen and not (und and getroffen < T) and not any(t[1].startswith(f"{p.relative_to(w)}:") for t in treffer["Werkzeuge (Kopf)"]):
            treffer["Werkzeuge (Kopf)"].append((round(summe * (getroffen / T) ** 1.5 * 0.8, 3), f"{p.relative_to(w)}:1: (Dateiname)"))
    for g in treffer:
        treffer[g].sort(key=lambda t: -t[0])          # stabil: innerhalb gleicher Relevanz Dateireihenfolge
    return treffer


def rangliste(treffer, k=10, je_datei=2):
    """Gesamt-Rangliste ueber alle Gruppen, hoechstens je_datei Zeilen je Datei (sonst fuellt ein Register die ersten 10)."""
    if k <= 0:
        return []
    alle = sorted(((r, g, s) for g, ts in treffer.items() for r, s in ts), key=lambda t: -t[0])
    aus, je = [], {}
    for r, g, s in alle:
        d = s.split(":")[0]
        if je.get(d, 0) >= je_datei:
            continue
        je[d] = je.get(d, 0) + 1
        aus.append((r, g, s))
        if len(aus) >= k:
            break
    return aus


RRF_K = 20            # Rangfusion 1/(k+Rang); abgestimmt NUR auf tools/wissen_dev.json (25.11.: k<=20 -> 4/20, k=60 g=1 -> 3/20)
BED_GEWICHT = 1.5
BED_TOP = 300


def bedeutung_verfuegbar(kfg):
    """(python, grund): Bedeutungssuche nur, wenn die Konfig 'wissen.bedeutung' einen vorhandenen Python + Modellordner nennt."""
    import os
    if os.environ.get("WISSEN_BEDEUTUNG", "").lower() in ("0", "aus", "nein", "off"):
        return None, "WISSEN_BEDEUTUNG=aus"
    b = kfg.get("bedeutung") or {}
    py = b.get("python")
    if not py or not Path(py).exists():
        return None, "kein Python mit torch/transformers in .claude/doku-pflege.json 'wissen.bedeutung.python'"
    if b.get("modell") and not Path(b["modell"]).exists():
        return None, f"Modell fehlt: {b['modell']}"
    if not (Path(__file__).resolve().parent / "wissen_bedeutung.py").exists():
        return None, "wissen_bedeutung.py fehlt neben wissen_suchen.py"
    return py, ""


def bedeutung_treffer(wurzel, text, kfg, memory=None, top=BED_TOP):
    """Bedeutungs-Rangliste [{name, nr, gruppe, wert, text}] aus wissen_bedeutung.py (Unterprozess, nur CPU, nice 19), oder
    (None, grund) - nie ein Absturz: fehlt Paket/Modell/Index, bleibt es bei der Wortsuche."""
    import os
    py, grund = bedeutung_verfuegbar(kfg)
    if py is None:
        return None, grund
    cmd = [py, "-I", str(Path(__file__).resolve().parent / "wissen_bedeutung.py"), "--wurzel", str(wurzel), "--anfrage", text,
           "--top", str(top)] + (["--memory", str(memory)] if memory and Path(memory).is_dir() else [])
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"Unterprozess: {type(e).__name__}"
    if r.returncode == 3:
        return None, f"Index zu alt - einmal bauen: {py} -I {cmd[2]} --bauen"
    if r.returncode != 0:
        return None, (r.stderr.strip().split("\n") or ["?"])[-1][:200]
    try:
        return json.loads(r.stdout), ""
    except ValueError:
        return None, "Ausgabe kein JSON"


def fusionieren(treffer, bed, k=RRF_K, gewicht=BED_GEWICHT):
    """Rangfusion (RRF) von Wortsuche und Bedeutungssuche: Wert = 1000 x (1/(k+Rang_Wort) + gewicht/(k+Rang_Bedeutung)).
    Werkzeugkoepfe zaehlen je Datei (die Bedeutung bettet den ganzen Kopf als eine Einheit ein). Nur-Bedeutungs-Treffer kommen dazu."""
    def schluessel(g, name, nr):
        return name if g == "Werkzeuge (Kopf)" else f"{name}:{nr}"
    wort = sorted(((r, g, s) for g, ts in treffer.items() if g != "Aehnliche Werkzeuge (Wortschatz)" for r, s in ts),
                  key=lambda t: -t[0])
    rang_w = {}
    for i, (r, g, s) in enumerate(wort, 1):
        teil = s.split(":")
        rang_w.setdefault(schluessel(g, teil[0], teil[1] if len(teil) > 1 else ""), i)
    rang_b, text_b = {}, {}
    for i, x in enumerate(bed, 1):
        key = schluessel(x["gruppe"], x["name"], x["nr"])
        if key not in rang_b:
            rang_b[key] = len(rang_b) + 1
            text_b[key] = (x["gruppe"], x["name"], x["nr"], x["text"])

    def wert(key):
        v = 1.0 / (k + rang_w[key]) if key in rang_w else 0.0
        if key in rang_b:
            v += gewicht / (k + rang_b[key])
        return round(1000 * v, 3)

    neu = {g: [] for g in treffer}
    for r, g, s in wort:
        teil = s.split(":")
        neu[g].append((wert(schluessel(g, teil[0], teil[1] if len(teil) > 1 else "")), s))
    for key, (g, name, nr, roh) in text_b.items():
        if key not in rang_w and g in neu:
            t = roh.strip()
            neu[g].append((wert(key), f"{name}:{nr}: {t[:220] + ('…' if len(t) > 220 else '')}"))
    neu["Aehnliche Werkzeuge (Wortschatz)"] = treffer.get("Aehnliche Werkzeuge (Wortschatz)", [])
    for g in neu:
        neu[g].sort(key=lambda t: -t[0])
    return neu


def standard_memory(wurzel):
    s = str(Path(wurzel).resolve())
    if "/.claude/worktrees/" in s:
        s = s.split("/.claude/worktrees/")[0]
    return Path.home() / ".claude" / "projects" / s.replace("/", "-") / "memory"


def standard_wurzel():
    """git-Wurzel des Arbeitsordners; liegt diese Datei in <projekt>/tools/, dann dieses Projekt (Projektkopie)."""
    hier = Path(__file__).resolve().parent
    if hier.name == "tools" and (hier.parent / ".claude").is_dir():
        return hier.parent
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except OSError:
        pass
    return Path.cwd()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("begriffe", nargs="+")
    ap.add_argument("--wurzel", default=None, help="Projektordner (Standard: git-Wurzel des Arbeitsordners)")
    ap.add_argument("--memory", default=None, help="Memory-Ordner ('aus' = ohne)")
    ap.add_argument("--synonyme", default=None, help="Synonymdatei (Standard tools/wissen_synonyme.json)")
    ap.add_argument("--ohne-synonyme", action="store_true")
    ap.add_argument("--ohne-git", action="store_true")
    ap.add_argument("--ohne-aehnlich", action="store_true", help="ohne Gruppe 'Aehnliche Werkzeuge'")
    ap.add_argument("--und", action="store_true", help="nur Zeilen mit allen Begriffen")
    ap.add_argument("--max", type=int, default=5, help="Treffer je Gruppe (0 = alle)")
    ap.add_argument("--top", type=int, default=10, help="Laenge der Gesamt-Rangliste (0 = aus)")
    ap.add_argument("--bedeutung", choices=["an", "aus"], default="an",
                    help="Bedeutungssuche (Satz-Embedding, wissen_bedeutung.py) per Rangfusion dazu; an = wenn verfuegbar")
    a = ap.parse_args(argv)
    w = Path(a.wurzel) if a.wurzel else standard_wurzel()
    kfg = konfig(w)
    if not _globs(w, kfg["baum"]):
        print(f"FEHLER: {w}: kein Wissensbaum ({', '.join(kfg['baum'])}) - Projektordner? Quellen: .claude/doku-pflege.json 'wissen'",
              file=sys.stderr)
        return 2
    gruppen = [] if a.ohne_synonyme else lade_synonyme(a.synonyme or w / kfg["synonyme"])
    mem = None if a.memory == "aus" else Path(a.memory) if a.memory else standard_memory(w)
    begriffe = begriffe_teilen(a.begriffe, gruppen)
    for b in begriffe:
        e = erweitern(b, gruppen)
        if len(e) > 1:
            print(f"Suche '{b}' + Synonyme: {', '.join(e[1:])}")
    # Bedeutungssuche im Hintergrund, waehrend die Wortsuche laeuft (Unterprozess: Laden von torch/Modell ~ so lang wie die Wortsuche)
    bed_erg = {}
    faden = None
    if a.bedeutung == "an" and not a.und:
        import threading
        faden = threading.Thread(target=lambda: bed_erg.update(r=bedeutung_treffer(w, " ".join(a.begriffe), kfg, mem)), daemon=True)
        faden.start()
    t = suchen(w, begriffe, gruppen, mem, not a.ohne_git, a.und, kfg)
    if faden is not None:
        faden.join()
        bed, grund = bed_erg.get("r", (None, "Faden ohne Ergebnis"))
        if bed:
            t = fusionieren(t, bed)
        elif kfg.get("bedeutung"):
            print(f"HINWEIS: nur Wortsuche (Bedeutungssuche aus: {grund})")
    aehnlich, wa = ([], None) if a.ohne_aehnlich else aehnliche_werkzeuge(w, begriffe, gruppen, kfg=kfg)
    namen_kopf = {x.split(":")[0] for _, x in t["Werkzeuge (Kopf)"]}
    rel = {p.name: str(p.relative_to(w)) for p in werkzeug_dateien(w, kfg)}
    t["Aehnliche Werkzeuge (Wortschatz)"] = [(k, f"{rel.get(n, n)}: ({k:.2f}) {z}") for k, n, z in aehnlich if rel.get(n, n) not in namen_kopf]
    top = rangliste(t, a.top)
    if top:
        print(f"== TOP {len(top)} nach Relevanz (alle Quellen, max. 2 Zeilen je Datei)")
        for i, (r, g, x) in enumerate(top, 1):
            print(f"  {i:2d}. [{r:.1f}] {x}")
    gesamt = 0
    for g in GRUPPEN_REIHE:
        z = t[g]
        if not z:
            continue
        gesamt += len(z)
        zeige = z if a.max <= 0 else z[:a.max]
        print(f"== {g}: {len(z)} Treffer")
        for _, s in zeige:
            print("  " + s)
        if len(z) > len(zeige):
            print(f"  ... +{len(z) - len(zeige)} (mehr: --max 0)")
    if len(t["Wissensbaum"]) < 3 and aehnlich:
        wv = wortvorschlaege(w, begriffe, gruppen, aehnlich, wa)
        if wv:
            print(f"HINWEIS: nur {len(t['Wissensbaum'])} Baumtreffer - Woerter aus aehnlichen Werkzeugen: {', '.join(wv)}")
            print("  -> damit erneut suchen; passt ein Wort, als Synonym in tools/wissen_synonyme.json eintragen (Fehlsuche = neue Synonymgruppe)")
    if not gesamt:
        print("nichts gefunden")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
