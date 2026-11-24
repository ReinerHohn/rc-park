#!/usr/bin/env python3
"""Wissen suchen: EIN Aufruf durchsucht Wissensbaum, Register, Archiv, Logbuecher, Memory, Werkzeug-Kopfkommentare und git log.

Anlass 24.11.2026: Vorarbeit zu Fotoauswahl/Bildwert/Sweet Spot (VERSUCHSREGISTER BM/BN, tools/foto_wichtigkeit.py,
bildwert.py, sweetspot.py) wurde nicht gefunden, weil nur der Baum und mit dem falschen Wort gesucht wurde; Archiv
("archiviert = bringt nichts", Nutzer) und Memory-Archiv wurden gar nicht durchsucht.

Aufruf:  python3 -I tools/wissen_suchen.py "<begriff>" [weitere ...] [--max 8] [--ohne-git] [--ohne-synonyme] [--memory DIR]
- Jeder Begriff wird um seine Synonymgruppe aus tools/wissen_synonyme.json erweitert (Fotoauswahl -> Bildauswahl,
  Teilmenge, Bildwert, Sweet Spot, ...). Gross/klein und Umlaut/ae egal; Woerter bis 4 Zeichen nur als ganzes Wort.
- Mehrere Begriffe: Zeilen mit mehr getroffenen Begriffen zuerst; --und = nur Zeilen mit allen Begriffen.
- Ausgabe gruppiert, Baum-Treffer zuerst, je Treffer "Datei:Zeile: Text" (gekuerzt), je Gruppe max. --max Zeilen.
rc 0 = Treffer, rc 1 = nichts gefunden, rc 2 = Aufruffehler.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

GRUPPEN_REIHE = ["Wissensbaum", "Register/Methoden (modelle/)", "Logbuecher", "Archiv", "Memory", "Werkzeuge (Kopf)", "git log"]


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
    """Alle Woerter der Gruppen, zu denen der Begriff passt (gleich, oder eines enthaelt das andere bei >= 5 Zeichen)."""
    b = falte(begriff)
    aus = [begriff]
    for g in gruppen:
        for w in g:
            fw = falte(w)
            if fw == b or (len(fw) >= 5 and len(b) >= 5 and (fw in b or b in fw)):
                aus += [x for x in g if x not in aus]
                break
    return aus


def muster(woerter):
    teile = []
    for w in woerter:
        fw = re.escape(falte(w)).replace(r"\ ", r"[\s_-]?")
        teile.append(r"(?<![a-z0-9])" + fw + r"(?![a-z0-9])" if len(falte(w)) <= 4 else fw)
    return re.compile("|".join(teile))


def quellen(wurzel, memory):
    w = Path(wurzel)
    m = w / "modelle"
    q = {g: [] for g in GRUPPEN_REIHE}
    q["Wissensbaum"] = [w / "PROJEKT.md"] + sorted((w / "Doku" / "projekt").rglob("*.md"))
    for p in sorted(m.glob("*.md")):
        (q["Logbuecher"] if p.name.startswith("LOGBUCH_") else q["Register/Methoden (modelle/)"]).append(p)
    q["Logbuecher"] += sorted(m.glob("*/LOGBUCH*.md"))
    q["Archiv"] = sorted((m / "archiv").glob("*.md")) + sorted((w / "Doku" / "archiv").rglob("*.md"))
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


def suchen(wurzel, begriffe, gruppen, memory=None, mit_git=True, und=False):
    rxe = [muster(erweitern(b, gruppen)) for b in begriffe]
    rx_alle = re.compile("|".join(r.pattern for r in rxe))
    w = Path(wurzel)
    treffer = {g: [] for g in GRUPPEN_REIHE}

    def pruefe(gruppe, name, nr, text):
        f = falte(text)
        n = sum(1 for r in rxe if r.search(f))
        if n and (not und or n == len(rxe)):
            treffer[gruppe].append((n, f"{name}:{nr}: {stelle(text, rx_alle)}"))

    for g, dateien in quellen(w, memory).items():
        for p in dateien:
            try:
                name = "memory/" + p.name if g == "Memory" else str(p.relative_to(w))
            except ValueError:
                name = str(p)
            try:
                for nr, z in enumerate(p.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                    pruefe(g, name, nr, z)
            except OSError:
                pass
    for p in sorted((w / "tools").glob("*.py")):
        for nr, z in werkzeug_kopf(p):
            pruefe("Werkzeuge (Kopf)", f"tools/{p.name}", nr, z)
        # der Werkzeugname selbst zaehlt (z. B. Suche "bildwert" -> tools/bildwert.py)
        if any(r.search(falte(p.stem)) for r in rxe) and not any(t[1].startswith(f"tools/{p.name}:") for t in treffer["Werkzeuge (Kopf)"]):
            treffer["Werkzeuge (Kopf)"].append((1, f"tools/{p.name}:1: (Dateiname)"))
    if mit_git:
        woerter = sorted({x for b in begriffe for x in erweitern(b, gruppen)})
        cmd = ["git", "-C", str(w), "log", "--all", "-i", "--format=%h %as %s", "-n", "300"]
        for x in woerter:
            cmd += ["--grep", x]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            for z in r.stdout.splitlines():
                pruefe("git log", "commit", z.split(" ")[0], z)
        except (OSError, subprocess.TimeoutExpired):
            pass
    for g in treffer:
        treffer[g].sort(key=lambda t: -t[0])          # stabil: innerhalb gleicher Trefferzahl Dateireihenfolge
    return treffer


def standard_memory(wurzel):
    s = str(Path(wurzel).resolve())
    if "/.claude/worktrees/" in s:
        s = s.split("/.claude/worktrees/")[0]
    return Path.home() / ".claude" / "projects" / s.replace("/", "-") / "memory"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("begriffe", nargs="+")
    ap.add_argument("--wurzel", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--memory", default=None, help="Memory-Ordner ('aus' = ohne)")
    ap.add_argument("--synonyme", default=None, help="Synonymdatei (Standard tools/wissen_synonyme.json)")
    ap.add_argument("--ohne-synonyme", action="store_true")
    ap.add_argument("--ohne-git", action="store_true")
    ap.add_argument("--und", action="store_true", help="nur Zeilen mit allen Begriffen")
    ap.add_argument("--max", type=int, default=8, help="Treffer je Gruppe (0 = alle)")
    a = ap.parse_args(argv)
    w = Path(a.wurzel)
    if not (w / "modelle").is_dir() and not (w / "Doku").is_dir():
        print(f"FEHLER: {w} ist kein Projektordner", file=sys.stderr)
        return 2
    gruppen = [] if a.ohne_synonyme else lade_synonyme(a.synonyme or w / "tools" / "wissen_synonyme.json")
    mem = None if a.memory == "aus" else Path(a.memory) if a.memory else standard_memory(w)
    for b in a.begriffe:
        e = erweitern(b, gruppen)
        if len(e) > 1:
            print(f"Suche '{b}' + Synonyme: {', '.join(e[1:])}")
    t = suchen(w, a.begriffe, gruppen, mem, not a.ohne_git, a.und)
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
    if not gesamt:
        print("nichts gefunden")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
