#!/usr/bin/env python3
"""wissen_fragen.py - Alltagsfragen je Wissenszeile (doc2query): schliesst die Vokabelluecke zwischen Fachkurzschrift und Frage.

Anlass 24.11.2026: Baumzeilen sind Fachkurzschrift ("fTetWild ... 1506 Komponenten, nicht wasserdicht"), Agenten fragen in
Alltagssprache ("die Huelle hat ueberall Loecher"). Wortsuche + gelernte Synonyme fanden auf einem Dev-Satz in Satzform 0/20,
ein Satz-Embedding (multilingual-e5-small/-base) 1/20. Standardmittel doc2query: je Zeile 2-3 Fragen, "die diese Zeile beantwortet"
(Problem statt Loesung, moeglichst ohne Fachwoerter der Zeile), beim Indexieren mitsuchen; der Treffer zeigt die Originalzeile.
Ablage: <fragen_ordner>/<quellpfad mit / -> __>.jsonl, je Zeile {"hash": sha1(zeile.strip())[:12], "fragen": [...]}; der Hash haelt
die Fragen an der Zeile (Zeile geaendert -> Fragen veraltet -> wieder offen). Konfig .claude/doku-pflege.json "wissen.fragen_ordner"
(Standard Doku/projekt/.fragen). Die Fragen schreibt ein Sprachmodell (Agent) - dieses Werkzeug liefert die offenen Zeilen in Bloecken
und pflegt die Antworten ein.
Verwandt/Vorlaeufer: tools/wissen_suchen.py (liest die Fragen beim Suchen), tools/wissen_bedeutung.py (bettet sie ein),
tools/wissen_synonyme.json (fallweise gelernte Synonyme = Vorlaeufer), tools/wissen_ablage_pruefen.py (Pflegeregel).

Aufruf:
  python3 -I tools/wissen_fragen.py --offen [--glob 'Doku/projekt/**/*.md'] [--block 100] [--aus DIR]   offene Zeilen als Bloecke (JSON)
  python3 -I tools/wissen_fragen.py --einpflegen DATEI.jsonl [...]   Antworten {"hash","datei","fragen"} uebernehmen
  python3 -I tools/wissen_fragen.py --pruefen                        Zahl der Baumzeilen ohne (aktuelle) Fragen; rc 0 immer (Warnung)
"""
import argparse
import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import wissen_suchen as ws  # noqa: E402

MIN_LAENGE = 40


zeilen_hash = ws.zeilen_hash


def ordner(wurzel, kfg=None):
    k = kfg or ws.konfig(wurzel)
    return Path(wurzel) / k.get("fragen_ordner", "Doku/projekt/.fragen")


def fragen_datei(wurzel, rel, kfg=None):
    return ordner(wurzel, kfg) / (str(rel).replace("/", "__") + ".jsonl")


def lade(wurzel, rel, kfg=None):
    """{hash: [fragen]} fuer eine Quelldatei (relativ zur Wurzel); leer, wenn keine Fragen abgelegt sind."""
    return ws.alltagsfragen(wurzel, rel, kfg)


def relevante_zeile(z):
    s = z.strip()
    return s.startswith(("- ", "* ", "| ")) and len(s) >= MIN_LAENGE and not set(s) <= set("|-: ")


def relevanter_kopf(z):
    return bool(re.match(r"^#{2,3} \S.{14,}", z))


def offene(wurzel, globs, kfg=None, koepfe=False):
    """[(rel, nr, hash, ueberschrift, zeile)] ohne aktuelle Fragen. koepfe=True: Abschnittskoepfe (## / ###) statt Listenzeilen
    (Register/Archiv/Logbuch: ein Abschnitt = ein Eintrag); 'zeile' enthaelt dann Kopf + die ersten Inhaltszeilen als Kontext."""
    w = Path(wurzel)
    aus = []
    for p in ws._globs(w, globs):
        rel = str(p.relative_to(w))
        da = lade(w, rel, kfg)
        kopf = ""
        zeilen = p.read_text(encoding="utf-8", errors="replace").split("\n")
        for nr, z in enumerate(zeilen, 1):
            if z.lstrip().startswith("#"):
                kopf = z.strip("# ").strip()
            if koepfe:
                if relevanter_kopf(z) and zeilen_hash(z) not in da:
                    inhalt = [x.strip() for x in zeilen[nr:nr + 8] if x.strip() and not x.startswith("#")][:3]
                    aus.append((rel, nr, zeilen_hash(z), z.strip("# ").strip(), (z.strip() + " / " + " / ".join(inhalt))[:700]))
            elif relevante_zeile(z) and zeilen_hash(z) not in da:
                aus.append((rel, nr, zeilen_hash(z), kopf, z.strip()))
    return aus


def einpflegen(wurzel, dateien, kfg=None):
    neu = {}
    for d in dateien:
        for z in Path(d).read_text(encoding="utf-8").splitlines():
            if not z.strip():
                continue
            x = json.loads(z)
            fr = [f.strip() for f in x.get("fragen", []) if f and f.strip()]
            if fr:
                neu.setdefault(x["datei"], {})[x["hash"]] = fr
    n = 0
    for rel, m in neu.items():
        p = Path(wurzel) / rel
        lebend = {zeilen_hash(z) for z in p.read_text(encoding="utf-8").split("\n")} if p.exists() else set()
        alt = lade(wurzel, rel, kfg)
        alt.update(m)
        alt = {h: f for h, f in alt.items() if h in lebend}           # Fragen veralteter Zeilen fallen weg
        q = fragen_datei(wurzel, rel, kfg)
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text("".join(json.dumps({"hash": h, "fragen": f}, ensure_ascii=False) + "\n" for h, f in sorted(alt.items())),
                     encoding="utf-8")
        n += len(m)
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wurzel", default=None)
    ap.add_argument("--offen", action="store_true")
    ap.add_argument("--glob", action="append", default=None)
    ap.add_argument("--block", type=int, default=100)
    ap.add_argument("--aus", default=None, help="Ordner fuer Block-Dateien block_NNN.json (sonst stdout)")
    ap.add_argument("--einpflegen", nargs="+", default=None)
    ap.add_argument("--pruefen", action="store_true")
    ap.add_argument("--koepfe", action="store_true", help="Abschnittskoepfe statt Listenzeilen (Register/Archiv/Logbuch)")
    a = ap.parse_args(argv)
    w = Path(a.wurzel) if a.wurzel else ws.standard_wurzel()
    kfg = ws.konfig(w)
    globs = a.glob or kfg["baum"]
    if a.einpflegen:
        print(f"{einpflegen(w, a.einpflegen, kfg)} Zeilen mit Fragen eingepflegt -> {ordner(w, kfg)}")
        return 0
    off = offene(w, globs, kfg, a.koepfe)
    if a.pruefen:
        ges = sum(1 for p in ws._globs(w, globs) for z in p.read_text(encoding="utf-8", errors="replace").split("\n")
                  if (relevanter_kopf(z) if a.koepfe else relevante_zeile(z)))
        print(f"Wissenszeilen ohne Alltagsfragen: {len(off)} von {ges} (nachtragen: --offen, Fragen schreiben, --einpflegen)")
        return 0
    if a.offen:
        bl = [off[i:i + a.block] for i in range(0, len(off), a.block)]
        if a.aus:
            Path(a.aus).mkdir(parents=True, exist_ok=True)
            for i, b in enumerate(bl):
                (Path(a.aus) / f"block_{i:03d}.json").write_text(json.dumps(
                    [{"datei": r, "nr": n, "hash": h, "ueberschrift": k, "zeile": z} for r, n, h, k, z in b],
                    ensure_ascii=False, indent=0), encoding="utf-8")
            print(f"{len(off)} offene Zeilen in {len(bl)} Bloecken -> {a.aus}")
        else:
            for r, n, h, k, z in off:
                print(json.dumps({"datei": r, "nr": n, "hash": h, "ueberschrift": k, "zeile": z}, ensure_ascii=False))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
