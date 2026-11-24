#!/usr/bin/env python3
"""werkzeug_aehnlich.py - Doppelgaenger-Warnung: welche tools/*.py tun schon (fast) dasselbe wie ein neuer Auftrag / ein neues Werkzeug?

Anlass 24.11.2026 (Auftrag "Wissen besser archivieren"): Werkzeuge wurden doppelt gebaut, weil der Vorlaeufer unter anderem Wort lag -
  formsitz.py (24.11., "trennscharfes Formmass") neben flaechen_mass.py (11.11., "Formvergleich ueber FLAECHEN statt Kanten", Spec im Archiv),
  Bildwert-Stufe 1 (24.11.) neben foto_wichtigkeit.py / bildwert.py / sweetspot.py / dicht_bildwahl.py (02.-14.11.),
  drahtmaske.py + drahtmasken.py (beide 24.11.). Die Wortsuche (wissen_suchen.py) findet nur gleiche Woerter; hier zaehlt der WORTSCHATZ des
  Kopfkommentars (Name + Docstring, Stamm = erste 6 Zeichen + 4-Gramme fuer Komposita, TF-IDF-Kosinus), damit "Formmass" auch "Flaechenmass"/"Formvergleich" trifft.
Verwandt/Vorlaeufer: tools/wissen_suchen.py (Wortsuche, ruft aehnliche() fuer die Gruppe "Aehnliche Werkzeuge" auf), tools/werkzeug_suche.py (falls vorhanden).

Aufruf (nur Lesen, CPU, < 5 s):
  python3 -I tools/werkzeug_aehnlich.py "<Auftragstext oder Stichwoerter>" [--top 10]   -> aehnlichste Werkzeuge mit Wert 0..1
  python3 -I tools/werkzeug_aehnlich.py --wie tools/neu.py [--top 10]                    -> Doppelgaenger eines (neuen) Werkzeugs
  python3 -I tools/werkzeug_aehnlich.py --paare [--schwelle 0.45] [--json AUS]           -> alle Werkzeugpaare ueber Schwelle (Bestandsaufnahme)
  python3 -I tools/werkzeug_aehnlich.py --kopf-pruefen [--basis tools/werkzeug_basis.json] [--warnung]
        -> jedes tools/*.py, das NICHT in der Basisliste steht und nicht vor dem STICHTAG 25.11.2026 eingecheckt wurde, braucht im Kopf eine Zeile
           "Verwandt:" oder "Vorlaeufer:" (auch "Verwandt/Vorlaeufer:"; Inhalt darf "keine" sein, wenn wissen_suchen nichts fand).
           --basis-schreiben schreibt die Basisliste neu (nur bewusst, z. B. nach Aufraeumen).
test_*.py werden nicht verglichen (spiegeln ihr Werkzeug). rc 0 = ok/Treffer, rc 1 = Kopfpruefung verletzt bzw. nichts gefunden, rc 2 = Aufruffehler.
"""
import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

STAMM = 6
STOPP = set("""
aber alle allem allen aller alles also auch auf aus bei beim bis bzw dann das dass dem den der des die dies diese diesem diesen dieser doch
durch ein eine einem einen einer eines fuer gegen hat hier ihr im in ist jede jedem jeden jeder jedes kein keine mit nach nicht noch nur
oder ohne pro sich sie sind so ueber um und uns unter vom von vor wann was weil wenn werden wie wird wir zu zum zur zwei drei eins
the and for with from this that into not are was def import return none true false self print json argv argparse path open
aufruf python3 python tools py venv bin media oem scan seg colmap usr env datei dateien rcpark rc park objekt objekte modelle modell
ausgabe eingabe standard optional default help json aus ein bild bilder fotos foto teil teile jetzt neu neue neuer alt alte
""".split())
# Wissenswerkzeuge zitieren die Anlass-Faelle in ihrem Kopf -> wuerden jede Suche anfuehren
SELBST = {"werkzeug_aehnlich.py", "wissen_suchen.py", "wissensbaum_luecken.py", "wissen_ablage_pruefen.py"}
KOPF_RX = re.compile(r"(verwandt|vorlaeufer|vorläufer)\s*(/\s*(verwandt|vorlaeufer|vorläufer))?\s*:", re.I)


def falte(s):
    s = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    return s


def staemme(text):
    """Woerter (>= 4 Zeichen, keine Stoppwoerter/Zahlen) -> Stamm = erste STAMM Zeichen. Bindestrich/Unterstrich trennen."""
    aus = []
    for w in re.findall(r"[a-z][a-z0-9]{3,}", falte(text).replace("_", " ").replace("-", " ")):
        if w in STOPP or w.isdigit():
            continue
        aus.append(w[:STAMM])
        # deutsche Komposita ("Bildauswahl" ~ "bildwahl", "Flaechenmass" ~ "Formmass"): zusaetzlich 4-Gramme des Wortes
        aus += ["~" + w[i:i + 4] for i in range(len(w) - 3)]
    return aus


def kopf(p, zeilen=60):
    """Modul-Docstring/Kopfkommentar der ersten Zeilen (roh)."""
    try:
        z = p.read_text(encoding="utf-8", errors="replace").split("\n")[:zeilen]
    except OSError:
        return ""
    t, im, q = [], False, None
    for s in z:
        st = s.strip()
        if im:
            t.append(s)
            if q in st:
                break
            continue
        if st.startswith("#"):
            if not st.startswith("#!"):
                t.append(st.lstrip("# "))
            continue
        if not st:
            continue
        m = re.match(r'^[rubRUB]*("""|\'\'\')', st)
        if m:
            q = m.group(1)
            t.append(st)
            if st.count(q) >= 2 and len(st) > 6:
                break
            im = True
            continue
        if st.startswith(("import ", "from ")):
            continue
        break
    return "\n".join(t)


def werkzeuge(tools_dir):
    """tools_dir = Ordner (alle *.py) oder Liste von Dateien (projektunabhaengig, aus der Konfig von wissen_suchen)."""
    dateien = sorted(Path(tools_dir).glob("*.py")) if isinstance(tools_dir, (str, Path)) else [Path(p) for p in tools_dir]
    return [p for p in dateien if not p.name.startswith("test_")]


def vektoren(tools_dir):
    """{name: Counter(staemme)}; Dateiname zaehlt doppelt (Name ist die schaerfste Beschreibung)."""
    v = {}
    for p in werkzeuge(tools_dir):
        c = Counter(staemme(kopf(p)))
        for s in staemme(p.stem):
            c[s] += 2
        v[p.name] = c
    return v


def idf(v):
    df = Counter()
    for c in v.values():
        df.update(set(c))
    n = max(1, len(v))
    return {s: math.log((1 + n) / (1 + d)) + 1 for s, d in df.items()}


def gewichtet(c, w):
    g = {s: (1 + math.log(k)) * w.get(s, 1.0) for s, k in c.items() if k > 0}
    nrm = math.sqrt(sum(x * x for x in g.values())) or 1.0
    return {s: x / nrm for s, x in g.items()}


def kosinus(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(s, 0.0) for s, x in a.items())


def aehnliche(text, tools_dir, top=10, mindest=0.08, ohne=()):
    """[(wert, name, erste Kopfzeile)] der tools, deren Kopf-Wortschatz dem Text am naechsten ist."""
    pfad = {p.name: p for p in werkzeuge(tools_dir)}
    v = vektoren(tools_dir)
    w = idf(v)
    q = gewichtet(Counter(staemme(text)), w)
    if not q:
        return []
    aus = []
    for name, c in v.items():
        if name in ohne or name in SELBST:
            continue
        k = kosinus(q, gewichtet(c, w))
        if k >= mindest:
            aus.append((round(k, 3), name, erste_zeile(pfad[name])))
    aus.sort(key=lambda t: (-t[0], t[1]))
    return aus[:top]


def erste_zeile(p):
    k = kopf(p)
    for z in k.split("\n"):
        z = z.strip().strip('"\'').strip()
        if len(z) > 3:
            return z[:150]
    return ""


def paare(tools_dir, schwelle=0.45):
    v = vektoren(tools_dir)
    w = idf(v)
    g = {n: gewichtet(c, w) for n, c in v.items()}
    namen = sorted(g)
    aus = []
    for i, a in enumerate(namen):
        for b in namen[i + 1:]:
            k = kosinus(g[a], g[b])
            if k >= schwelle:
                aus.append((round(k, 3), a, b))
    aus.sort(key=lambda t: -t[0])
    return aus


def kopf_hat_verwandt(p):
    return bool(KOPF_RX.search(falte(kopf(p, 80))))


STICHTAG = "2026-11-25"   # vorher eingecheckte Werkzeuge (auch aus parallelen Zweigen, die erst spaeter gemergt werden) gelten als alt


def erstes_commit_datum(p):
    """Datum (JJJJ-MM-TT) des ersten Commits, der die Datei anlegte; None = nicht eingecheckt / kein git."""
    try:
        import subprocess
        r = subprocess.run(["git", "-C", str(p.parent), "log", "--diff-filter=A", "--format=%as", "--", p.name],
                           capture_output=True, text=True, timeout=30)
        d = r.stdout.split()
        return d[-1] if r.returncode == 0 and d else None
    except (OSError, ValueError):
        return None


def kopf_pruefen(tools_dir, basis, stichtag=STICHTAG):
    """Neue Werkzeuge (nicht in der Basis, nicht vor dem Stichtag eingecheckt) ohne Verwandt-/Vorlaeufer-Zeile -> Liste."""
    bekannt = set(basis)
    aus = []
    for p in werkzeuge(tools_dir):
        if p.name in bekannt or kopf_hat_verwandt(p):
            continue
        d = erstes_commit_datum(p)
        if d and d < stichtag:
            continue
        aus.append(p.name)
    return aus


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("text", nargs="*")
    hier = Path(__file__).resolve().parent
    ap.add_argument("--tools", default=str(hier if hier.name == "tools" else Path.cwd() / "tools"),
                    help="Werkzeugordner (Standard: dieser tools/-Ordner bzw. ./tools)")
    ap.add_argument("--wie", default=None, help="Doppelgaenger dieses Werkzeugs suchen")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--mindest", type=float, default=0.08)
    ap.add_argument("--paare", action="store_true")
    ap.add_argument("--schwelle", type=float, default=0.45)
    ap.add_argument("--json", default=None)
    ap.add_argument("--kopf-pruefen", action="store_true")
    ap.add_argument("--basis", default=None)
    ap.add_argument("--basis-schreiben", action="store_true")
    ap.add_argument("--warnung", action="store_true", help="Kopfpruefung nur melden (rc 0)")
    a = ap.parse_args(argv)
    td = Path(a.tools)
    basis_pfad = Path(a.basis) if a.basis else td / "werkzeug_basis.json"

    if a.basis_schreiben:
        namen = [p.name for p in werkzeuge(td)]
        basis_pfad.write_text(json.dumps({"_hinweis": "Werkzeuge vor Einfuehrung der Pflicht-Kopfzeile 'Verwandt:/Vorlaeufer:' (24.11.2026); "
                                          "neue tools/*.py stehen NICHT hier und brauchen die Zeile (werkzeug_aehnlich.py --kopf-pruefen).",
                                          "werkzeuge": namen}, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        print(f"Basis geschrieben: {len(namen)} Werkzeuge -> {basis_pfad}")
        return 0
    if a.kopf_pruefen:
        try:
            basis = json.loads(basis_pfad.read_text(encoding="utf-8")).get("werkzeuge", [])
        except (OSError, ValueError):
            print(f"FEHLER: Basisliste {basis_pfad} fehlt/kaputt", file=sys.stderr)
            return 2
        fehlt = kopf_pruefen(td, basis)
        if not fehlt:
            print(f"Kopfpruefung OK: alle neuen Werkzeuge nennen Verwandt/Vorlaeufer (Basis {len(basis)})")
            return 0
        print(f"{'WARNUNG' if a.warnung else 'FEHLER'}: {len(fehlt)} neue(s) Werkzeug(e) ohne Kopfzeile 'Verwandt:'/'Vorlaeufer:' "
              f"(Inhalt aus python3 -I tools/werkzeug_aehnlich.py --wie tools/<x>.py):")
        for n in fehlt:
            print(f"  tools/{n}")
        return 0 if a.warnung else 1
    if a.paare:
        pp = paare(td, a.schwelle)
        if a.json:
            Path(a.json).write_text(json.dumps([{"wert": k, "a": x, "b": y} for k, x, y in pp], indent=1), encoding="utf-8")
        print(f"{len(pp)} Paare >= {a.schwelle}")
        for k, x, y in pp[: a.top if a.top > 0 else None]:
            print(f"  {k:.2f}  {x}  <->  {y}")
        return 0
    if a.wie:
        p = Path(a.wie)
        if not p.exists():
            print(f"FEHLER: {p} fehlt", file=sys.stderr)
            return 2
        text = kopf(p) + " " + " ".join([p.stem] * 2)
        tr = aehnliche(text, td, a.top, a.mindest, ohne={p.name})
    else:
        if not a.text:
            ap.print_usage()
            return 2
        tr = aehnliche(" ".join(a.text), td, a.top, a.mindest)
    if not tr:
        print("kein aehnliches Werkzeug")
        return 1
    for k, n, z in tr:
        print(f"  {k:.2f}  tools/{n}: {z}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
