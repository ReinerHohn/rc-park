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
META_WERKZEUGE = {"wissen_suchen.py", "werkzeug_aehnlich.py", "wissensbaum_luecken.py", "wissen_ablage_pruefen.py", "wissen_wiederfinden.py",
                  "test_wissensbaum_luecken.py", "test_wissen_ablage.py"}


STOPPWOERTER = set("""der die das den dem des ein eine einen einem einer und oder aber mit ohne von vom zu zum zur im in an am auf aus bei
fuer für ist sind wird werden wurde war hat haben nach vor ueber über unter wie was wer ob als auch noch nur nicht kein keine es er sie wir
man sich so dann wenn weil dass statt beim bis gegen durch um mal schon jetzt hier dort sehr mehr""".split())


def begriffe_teilen(begriffe, gruppen):
    """Suchtext -> Begriffe: alle Woerter (auch aus Mehrwort-Argumenten), Wendungen aus einer Synonymgruppe ("Sweet Spot",
    "dichte Wolke", "weniger Fotos") bleiben zusammen, Fuellwoerter fallen weg (24.11.2026: "wie hoch ist das Martinstor" -
    Fuellwoerter senkten die Abdeckung jeder echten Fundstelle)."""
    ganz = {falte(w) for g in gruppen for w in g}
    woerter = [x for b in begriffe for x in b.split() if x]
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


def suchen(wurzel, begriffe, gruppen, memory=None, mit_git=True, und=False, kfg=None):
    """{gruppe: [(relevanz, "datei:zeile: text")]} nach Relevanz (24.11.2026, vorher nur ODER + Trefferzahl: "Formmass Flaeche" gab
    164 Baumtreffer, oben bahn-anlage.md "Druckflaeche"). Relevanz je Zeile = Summe je Begriff des besten Wortes (IDF ueber alle
    durchsuchten Zeilen; Synonym x0,75) x Abdeckung (getroffene Begriffe / alle)^1,5 + Bonus Dateiname/Ueberschrift, x Quellgruppe,
    lange Tabellenzeilen leicht abgewertet."""
    import math
    w = Path(wurzel)
    terme = []
    for t in begriffe:
        ws_ = [(x, muster([x]), x == t) for x in erweitern(t, gruppen)]
        sm = stamm_muster(t)
        if sm is not None:
            ws_[0] = (t, sm, True)
        terme.append((t, ws_))
    alle_woerter = [x for _, ws_ in terme for x, _, _ in ws_]
    rx_alle = re.compile("|".join(rx.pattern for _, ws_ in terme for _, rx, _ in ws_)) if alle_woerter else re.compile("(?!)")
    zeilen = []                                   # (gruppe, name, nr, text, faltung)

    for g, dateien in quellen(w, memory, kfg).items():
        for p in dateien:
            try:
                name = "memory/" + p.name if g == "Memory" else str(p.relative_to(w))
            except ValueError:
                name = str(p)
            try:
                for nr, z in enumerate(p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                    zeilen.append((g, name, nr, z, falte(z)))
            except OSError:
                pass
    werkzeugnamen = []
    # Meta-Werkzeuge (diese Suche, Lueckenpruefung, Nachweis) zitieren die Verlustfaelle im Kopf -> stuenden sonst bei jeder Suche oben
    for p in werkzeug_dateien(w, kfg):
        rel = str(p.relative_to(w))
        for nr, z in werkzeug_kopf(p):
            zeilen.append(("Werkzeuge (Kopf)", rel, nr, z, falte(z)))
        werkzeugnamen.append(p)
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
            for x, rx, orig in ws_:
                if rx.search(f):
                    best = max(best, idf[x] * (1.0 if orig else SYNONYM_GEWICHT))
                if stamm and rx.search(stamm):
                    name_bonus = max(name_bonus, 0.5 * idf[x] * (1.0 if orig else SYNONYM_GEWICHT))
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
    t = suchen(w, begriffe, gruppen, mem, not a.ohne_git, a.und, kfg)
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
