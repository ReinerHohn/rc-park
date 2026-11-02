#!/usr/bin/env python3
"""nullstart_serie.py - wertet modelle/<objekt>/nullstart_serie.json aus (jeder Nullstart haengt einen Lauf an): welche Pruefung scheitert in
wie vielen Laeufen? SYSTEMATISCH (fast immer) = Fehler in der Ableitung/Referenz, FLACKERND (manchmal) = Instabilitaet der Wolke, SELTEN = Zufall.
  python3 tools/nullstart_serie.py modelle/<objekt>/nullstart_serie.json [--ab N]
Pruefungsnamen werden ohne Zahlen verglichen (Bandgrenzen wandern von Lauf zu Lauf)."""
import sys, json, re, collections

def norm(n): return re.sub(r"\s+", " ", re.sub(r"\d+([.,]\d+)?", "#", n)).strip()

def main():
    S = json.load(open(sys.argv[1]))["laeufe"]; ab = int(sys.argv[sys.argv.index("--ab") + 1]) if "--ab" in sys.argv else 1; S = S[ab - 1:]; n = len(S)
    print(f"{n} Laeufe:")
    for i, l in enumerate(S, ab):
        print(f"  {i}: {l['datum']}  {l['bestanden']:>6s}  Mapper {l.get('mapper', '?')}{' streng' if l.get('streng') else ''}  Netz {l.get('netzwahl', '-')}  frisch abgeleitet {l.get('frisch_abgeleitet', '?')}"
              + (f"  [{l['quelle']}]" if l.get("quelle") else ""))
    c = collections.Counter(); m = collections.Counter()
    for l in S:
        for k in {norm(x) for x in l["nicht_bestanden"]}: c[k] += 1
        for k in l.get("masse_abweichend", []): m[k] += 1
    print("\nPruefungen nach Haeufigkeit des Scheiterns:")
    for k, v in c.most_common():
        art = "SYSTEMATISCH" if v >= 0.8 * n and n >= 3 else ("flackernd" if v >= 2 else "selten")
        print(f"  {v}/{n} {art:12s} {k[:95]}")
    if m: print("\nMasse ueber 0,3 m daneben:", ", ".join(f"{k} {v}/{n}" for k, v in m.most_common()))

if __name__ == "__main__":
    main()
