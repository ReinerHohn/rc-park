#!/usr/bin/env python3
"""wissen_ablage_pruefen.py - Ablage-Tor fuer Projektwissen: liegt das Wissen so, dass die Baumsuche (wissen_suchen.py) es findet?

Anlass 24.11.2026 (Auftrag "Wissen besser archivieren"): Wissen war da und wurde nicht gefunden -
  die Spec archiv/SPEC_FLAECHENMASS (11.11.) war NIE eingecheckt, tools/flaechen_mass.py verweist darauf; formsitz.py wurde 24.11. neu erdacht;
  REZEPT-Lehre L55 steht 5x mit verschiedenem Inhalt (wer "L55" zitiert, meint irgendeine); Martinstor-Hoehe 45 / 54,8 / 60-66 m stand nebeneinander,
  obwohl MASSPRUEFUNG_MARTINSTOR 31.10. 54,8 m (Laser) belegt und 60-66 m widerlegt hatte - am 19.11. wurde wieder mit "Turm ~60 m" gerechnet.
Verwandt/Vorlaeufer: tools/wissensbaum_luecken.py (steht jeder Quelleintrag im Baum? - liefert hier die Register-Parser),
  tools/wissen_suchen.py (Suche), tools/werkzeug_aehnlich.py (Doppelgaenger-Werkzeuge), tools/doku_links_pruefen.py (falls vorhanden: Links).

Pruefungen:
  1 ungetrackt   Wissensdateien (modelle/**/*.md, Doku/**/*.md, PROJEKT.md, tools/*.py) die git nicht kennt -> WARNUNG (fremde Arbeitsdateien
                 blockieren nie, Nutzer entscheidet: einchecken oder verwerfen). Auf dem anderen Rechner/Worktree gibt es sie nicht.
  2 tote_verweise  Pfade modelle/...md / Doku/...md in Baum, Registern, Werkzeugkoepfen, die NICHT eingecheckt sind -> WARNUNG mit Zahl;
                 rc 1 nur, wenn es MEHR sind als in der Basis (Sperrklinke, tools/wissen_ablage_basis.json).
  3 doppelte_ids   Register-IDs (VERSUCHSREGISTER, NICHTS_GEBRACHT, REZEPT, LERNJOURNAL) doppelt vergeben -> rc 1 fuer jede NEUE Doppelung
                 (nicht in der Basis); alte stehen als Liste in der Basis und werden mit gemeldet (Umbenennen nur mit Nutzer: Zitate zeigen darauf).
  4 widersprueche  modelle/WIDERSPRUECHE.md: jede Eintragszeile "- ... · ..." braucht "Status: offen" oder "Status: geklaert" (+ "gilt:") -> rc 1 sonst.
Aufruf: python3 -I tools/wissen_ablage_pruefen.py [--wurzel DIR] [--basis JSON] [--basis-schreiben] [--json AUS] [--still]
rc 0 = ok (Warnungen moeglich), rc 1 = neue Doppel-ID / mehr tote Verweise als Basis / Widerspruchszeile ohne Status, rc 2 = Aufruffehler.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wissensbaum_luecken as WL  # noqa: E402

VERWEIS_RX = re.compile(r"(?<![A-Za-z0-9_/.-])((?:modelle|Doku)/[A-Za-z0-9_./-]*?[A-Za-z0-9_-]+\.md)\b")
STATUS_RX = re.compile(r"Status:\s*(offen|geklaert|geklärt)", re.I)


def git_dateien(w, *args):
    try:
        r = subprocess.run(["git", "-C", str(w), "ls-files", *args], capture_output=True, text=True, timeout=60)
        return set(r.stdout.split("\n")) - {""} if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def ungetrackt(w):
    fremd = git_dateien(w, "--others", "--exclude-standard", "modelle", "Doku", "tools", "PROJEKT.md")
    if fremd is None:
        return []
    return sorted(x for x in fremd if (x.endswith(".md") and not x.startswith("modelle/inhalt/")) or (x.startswith("tools/") and x.endswith(".py")))


def wissensquellen(w):
    w = Path(w)
    q = [w / "PROJEKT.md"] + sorted((w / "Doku" / "projekt").rglob("*.md")) + sorted((w / "modelle").glob("*.md"))
    return [p for p in q if p.exists()]


def tote_verweise(w, getrackt):
    """[(verweis, ort)] fuer Verweise auf nicht eingecheckte .md (Baum, modelle/*.md, Werkzeugkoepfe)."""
    w = Path(w)
    aus = []
    orte = [(p, WL.lies(p)) for p in wissensquellen(w)]
    for p in sorted((w / "tools").glob("*.py")):
        if p.name.startswith("test_"):
            continue                          # Tests nennen erfundene Pfade (synthetische Faelle)
        try:
            orte.append((p, p.read_text(encoding="utf-8", errors="replace").split("\n")[:80]))
        except OSError:
            pass
    for p, zeilen in orte:
        rel = str(p.relative_to(w))
        for i, z in enumerate(zeilen, 1):
            for m in VERWEIS_RX.finditer(z):
                v = m.group(1).rstrip(".")
                if "<" in v or "*" in v or v.startswith("modelle/inhalt/"):
                    continue
                if v not in getrackt:
                    aus.append((v, f"{rel}:{i}"))
    return aus


def doppelte_ids(w):
    """{quelle: {id: anzahl}} fuer Register-IDs, die mehr als einmal vorkommen."""
    aus = {}
    for name, eintraege, register in WL.sammeln(w, None):
        if not register:
            continue
        c = Counter(e.schluessel.split("#")[0] for e in eintraege if e.art == "id")
        d = {k: n for k, n in c.items() if n > 1}
        if d:
            aus[name] = dict(sorted(d.items()))
    return aus


def widersprueche_pruefen(w):
    p = Path(w) / "modelle" / "WIDERSPRUECHE.md"
    if not p.exists():
        return None, []
    fehl, n = [], 0
    for i, z in enumerate(WL.lies(p), 1):
        if z.startswith("- ") and "·" in z:          # Eintrag = Aufzaehlung mit Trennpunkten (Regelzeilen haben keine)
            n += 1
            m = STATUS_RX.search(z)
            if not m:
                fehl.append(f"modelle/WIDERSPRUECHE.md:{i}: ohne 'Status: offen|geklaert'")
            elif m.group(1).lower().startswith("gekl") and "gilt:" not in z.lower():
                fehl.append(f"modelle/WIDERSPRUECHE.md:{i}: geklaert ohne 'gilt:'")
    return n, fehl


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--wurzel", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--basis", default=None)
    ap.add_argument("--basis-schreiben", action="store_true")
    ap.add_argument("--json", default=None)
    ap.add_argument("--still", action="store_true", help="nur Zusammenfassung")
    a = ap.parse_args(argv)
    w = Path(a.wurzel)
    if not (w / "modelle").is_dir():
        print(f"FEHLER: {w} ist kein Projektordner", file=sys.stderr)
        return 2
    basis_pfad = Path(a.basis) if a.basis else w / "tools" / "wissen_ablage_basis.json"
    getrackt = git_dateien(w) or set()
    fremd = ungetrackt(w)
    tote = tote_verweise(w, getrackt) if getrackt else []
    dopp = doppelte_ids(w)
    n_wid, wid_fehl = widersprueche_pruefen(w)

    if a.basis_schreiben:
        basis_pfad.write_text(json.dumps({
            "_hinweis": "Sperrklinke fuer tools/wissen_ablage_pruefen.py (24.11.2026): alte Doppel-IDs und Zahl toter Verweise duerfen nur sinken. "
                        "Neu schreiben nur bewusst (--basis-schreiben) nach Aufraeumen, nie um eine neue Doppelung durchzulassen.",
            "tote_verweise": len(tote), "doppelte_ids": dopp}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"Basis geschrieben: {len(tote)} tote Verweise, {sum(len(d) for d in dopp.values())} doppelte IDs -> {basis_pfad}")
        return 0
    try:
        basis = json.loads(basis_pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        basis = {"tote_verweise": 0, "doppelte_ids": {}}
    neu_dopp = [f"{q} {k} ({n}x)" for q, d in dopp.items() for k, n in d.items()
                if n > basis.get("doppelte_ids", {}).get(q, {}).get(k, 1)]
    rc = 0
    print(f"1 ungetrackt: {len(fremd)} Wissensdatei(en) nicht eingecheckt" + (" - WARNUNG (Nutzer entscheidet: einchecken/verwerfen)" if fremd else ""))
    for x in fremd[: 0 if a.still else 30]:
        print(f"    {x}")
    bt = basis.get("tote_verweise", 0)
    print(f"2 tote_verweise: {len(tote)} Verweis(e) auf nicht eingecheckte .md (Basis {bt})")
    for v, o in tote[: 0 if a.still else 20]:
        print(f"    {v}  <- {o}")
    if len(tote) > bt:
        print(f"  FEHLER: {len(tote) - bt} neue(r) tote(r) Verweis(e) - Datei einchecken oder Verweis berichtigen")
        rc = 1
    n_alt = sum(len(d) for d in dopp.values())
    print(f"3 doppelte_ids: {n_alt} ID(s) mehrfach vergeben, davon neu: {len(neu_dopp)}")
    if not a.still:
        for q, d in dopp.items():
            print(f"    {q}: " + ", ".join(f"{k} {n}x" for k, n in d.items()))
    if neu_dopp:
        print("  FEHLER: neue Doppel-ID(s) - naechste freie ID vergeben: " + "; ".join(neu_dopp))
        rc = 1
    if n_wid is None:
        print("4 widersprueche: modelle/WIDERSPRUECHE.md fehlt (WARNUNG)")
    else:
        print(f"4 widersprueche: {n_wid} Eintraege, {len(wid_fehl)} ohne Status")
        for f in wid_fehl:
            print(f"    {f}")
        if wid_fehl:
            rc = 1
    # 5 Alltagsfragen (doc2query, 24.11.2026): neue Baumzeile bekommt beim Eintragen ihre Fragen (tools/wissen_fragen.py) - nur WARNUNG
    try:
        import wissen_fragen as wf
        kfg = wf.ws.konfig(w)
        off = wf.offene(w, kfg["baum"], kfg)
        if wf.ordner(w, kfg).is_dir() or off:
            print(f"5 alltagsfragen: {len(off)} Baumzeile(n) ohne Alltagsfragen" + (" - WARNUNG (python3 -I tools/wissen_fragen.py --offen ..."
                                                                                     " Fragen schreiben, --einpflegen)" if off else ""))
    except (ImportError, OSError, KeyError) as ex:
        print(f"5 alltagsfragen: nicht geprueft ({type(ex).__name__})")
    if a.json:
        Path(a.json).write_text(json.dumps({"ungetrackt": fremd, "tote_verweise": tote, "doppelte_ids": dopp,
                                            "neu_doppelt": neu_dopp, "widersprueche_fehler": wid_fehl}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("WISSEN-ABLAGE " + ("OK" if rc == 0 else "FEHLER"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
