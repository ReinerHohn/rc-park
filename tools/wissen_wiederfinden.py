#!/usr/bin/env python3
"""wissen_wiederfinden.py - NACHWEIS: findet die Baumsuche verlorenes Wissen wieder? Recall@5 auf echten Verlustfaellen.

Anlass 24.11.2026 (Nutzer: "Hast du bewiesen, dass wir verlorene Erkenntnisse jetzt finden?"): Stichprobe "Formmass Flaeche" gab 164 Baumtreffer,
oben bahn-anlage.md (Druckflaeche); der Flaechenmass-Vorlaeufer stand nicht oben. Hier laeuft je Fall aus tools/wissen_wiederfinden.json die
Suche mit natuerlichen Agenten-Woertern (nicht den Quellwoertern) und prueft, ob eine erwartete Quelle unter den ersten 5 Trefferzeilen steht.
Verwandt/Vorlaeufer: tools/wissen_suchen.py (die gepruefte Suche), tools/test_wissensbaum_luecken.py (synthetisch), tools/werkzeug_aehnlich.py.

Aufruf: python3 -I tools/wissen_wiederfinden.py [--faelle JSON] [--modul PFAD_ZU_wissen_suchen.py] [--k 5] [--wurzel DIR] [--zeigen]
  --modul: andere Fassung der Suche messen (z. B. alte aus git show, fuer vorher/nachher). Gelesen werden die ersten k Trefferzeilen der
  Ausgabe (neue Fassung: TOP-Liste; alte: erste Gruppenzeilen) - so wie ein Agent sie von oben liest. Memory und git log aus (reproduzierbar).
rc 0 = Recall@k >= mindest_recall der Falldatei, rc 1 = darunter, rc 2 = Aufruffehler.
"""
import argparse
import importlib.util
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

HIER = Path(__file__).resolve().parent
TREFFER_RX = re.compile(r"^\s+(?:\d+\.\s+\[[\d.]+\]\s+)?(\S+?:\S+?: .*)$")


def lade_modul(pfad):
    spec = importlib.util.spec_from_file_location("wissen_suchen_pruefling", str(pfad))
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HIER))
    spec.loader.exec_module(m)
    return m


def erste_treffer(modul, wurzel, woerter, k, synonyme=None, zusatz=()):
    buf = io.StringIO()
    with redirect_stdout(buf):
        modul.main(list(woerter) + ["--wurzel", str(wurzel), "--memory", "aus", "--ohne-git"] + (["--synonyme", synonyme] if synonyme else [])
                   + list(zusatz))
    aus = []
    for z in buf.getvalue().split("\n"):
        if z.startswith("==") or z.startswith("Suche ") or "(mehr: --max 0)" in z:
            continue
        m = TREFFER_RX.match(z)
        if m:
            aus.append(m.group(1))
            if len(aus) >= k:
                break
    return aus


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--faelle", default=None, help="Falldatei (Standard: Konfig 'wissen.faelle', sonst .claude/wissen_wiederfinden.json)")
    ap.add_argument("--modul", default=str(HIER / "wissen_suchen.py"))
    ap.add_argument("--wurzel", default=None, help="Projektordner (Standard wie wissen_suchen)")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--synonyme", default=None, help="andere Synonymdatei (vorher/nachher)")
    ap.add_argument("--zeigen", action="store_true", help="die k Treffer je Fall ausgeben")
    ap.add_argument("--satz", default=None, help="nur diesen Satz messen (faelle, kontrolle, neu_...)")
    ap.add_argument("--ohne-synonyme", action="store_true", help="Suche ohne gelernte Synonyme (Verallgemeinerung)")
    ap.add_argument("--bedeutung", choices=["an", "aus"], default=None, help="Bedeutungssuche der gemessenen Fassung an/aus")
    a = ap.parse_args(argv)
    try:
        modul = lade_modul(a.modul)
        if a.wurzel is None:
            a.wurzel = str(modul.standard_wurzel()) if hasattr(modul, "standard_wurzel") else str(HIER.parent)
        if a.faelle is None:
            k = modul.konfig(a.wurzel) if hasattr(modul, "konfig") else {}
            a.faelle = str(Path(a.wurzel) / k.get("faelle", ".claude/wissen_wiederfinden.json"))
        d = json.loads(Path(a.faelle).read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError) as e:
        print(f"FEHLER: {e}", file=sys.stderr)
        return 2

    argzusatz = (["--ohne-synonyme"] if a.ohne_synonyme else []) + (["--bedeutung", a.bedeutung] if a.bedeutung else [])

    def satz(faelle):
        gefunden = 0
        for f in faelle:
            tr = erste_treffer(modul, a.wurzel, f["suche"], a.k, a.synonyme, argzusatz)
            rx = re.compile(f["erwartet"])
            rang = next((i for i, t in enumerate(tr, 1) if rx.search(t)), None)
            gefunden += rang is not None
            zusatz = f"  [braucht Nutzerentscheid: {f['nutzerentscheid']}]" if f.get("nutzerentscheid") else ""
            print(f"{'OK ' if rang else 'FEHLT'} Rang {rang or '-'}  {f['name']}  <- {' '.join(f['suche'])}{zusatz}")
            if a.zeigen or not rang:
                for t in tr:
                    print(f"       {t[:170]}")
        return gefunden, len(faelle)

    soll = float(d.get("mindest_recall", 0))
    r = 1.0
    if a.satz in (None, "faelle"):
        gefunden, n = satz(d["faelle"])
        r = gefunden / max(1, n)
        print(f"RECALL@{a.k} = {gefunden}/{n} = {r:.2f} (Soll >= {soll:.2f}) - {'OK' if r >= soll else 'ZU NIEDRIG'}")
    if d.get("kontrolle") and a.satz in (None, "kontrolle"):
        # Kontrollsatz: NICHT zum Abstimmen von Synonymen/Rangfolge benutzt -> zeigt, ob die Verbesserung verallgemeinert (nur Bericht)
        print("-- Kontrollsatz (nicht abgestimmt, nur Bericht):")
        g2, n2 = satz(d["kontrolle"])
        print(f"KONTROLLE RECALL@{a.k} = {g2}/{n2} = {g2 / max(1, n2):.2f}")
    # neue echte Fehlsuchen (Saetze 'neu_*', 24.11.2026): zuerst ungelernt messen = Zukunftstest, nur Bericht
    for sk in sorted(x for x in d if x.startswith("neu_") and isinstance(d[x], list)):
        if a.satz in (None, sk):
            print(f"-- Satz {sk} (echte Fehlsuchen, nur Bericht):")
            g3, n3 = satz(d[sk])
            print(f"{sk.upper()} RECALL@{a.k} = {g3}/{n3} = {g3 / max(1, n3):.2f}")
    # Erstversuch-Quote: Anteil echter Faelle, die die damalige Suche beim ERSTEN Anlauf fand (Feld erster_versuch) - laufender
    # Verallgemeinerungs-Nachweis; steigt nur, wenn kuenftige Suchen ohne Nachlernen treffen
    echt = [f for x in d if isinstance(d[x], list) for f in d[x] if isinstance(f, dict) and "erster_versuch" in f]
    if echt and a.satz is None:
        ja = sum(bool(f["erster_versuch"]) for f in echt)
        print(f"ERSTVERSUCH-QUOTE = {ja}/{len(echt)} = {ja / len(echt):.2f} (echte Suchen, beim ersten Anlauf gefunden)")
    return 0 if r >= soll else 1


if __name__ == "__main__":
    sys.exit(main())
