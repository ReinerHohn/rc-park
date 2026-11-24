#!/usr/bin/env python3
"""register_ids_eindeutig.py - doppelt vergebene Register-IDs (REZEPT, NICHTS_GEBRACHT, VERSUCHSREGISTER) umbenennen: n-tes Vorkommen bekommt
Buchstaben-Suffix (L-KR28#2 -> L-KR28b), Baumverweise [QUELLE ID#n] werden mitgezogen. Einmal-Lauf 24.11.2026 (Nutzer: ja, 49 IDs).
Aufruf im Repo-Wurzelordner: python3 -I tools/register_ids_eindeutig.py
Verwandt/Vorlaeufer: tools/wissensbaum_luecken.py (_eindeutig), tools/wissen_ablage_pruefen.py (doppelte_ids)."""
import sys, re
from pathlib import Path
sys.path.insert(0, "tools")
import wissensbaum_luecken as WL
w = Path(".")
plan = []  # (datei, zeile, alt, neu, quelle, schluessel)
for name, eintraege, register in WL.sammeln(w, None):
    if not register: continue
    ids = [e for e in eintraege if e.art == "id"]
    vorhanden = {e.schluessel.split("#")[0] for e in ids}
    for e in ids:
        if "#" not in e.schluessel: continue
        basis, n = e.schluessel.split("#"); n = int(n)
        # Suffix: Buchstabe vor einem evtl. "-Wort"-Anhang
        m = re.match(r"^(.*?[0-9A-Z])((?:-[A-Z][A-Za-z]+)?)$", basis)
        kern, anh = m.group(1), m.group(2)
        for b in "bcdefghijk"[n-2:]:
            neu = kern + b + anh
            if neu not in vorhanden: break
        vorhanden.add(neu)
        plan.append((e.datei, e.von, basis, neu, e.quelle, e.schluessel))
fehl = 0
for datei, von, alt, neu, q, k in plan:
    p = Path(datei); z = p.read_text(encoding="utf-8").split("\n")
    l = z[von-1]
    mm = re.search(r"(?<![A-Za-z0-9])" + re.escape(alt) + r"(?![A-Za-z0-9])", l)
    if not mm: print("NICHT GEFUNDEN", datei, von, alt); fehl += 1; continue
    z[von-1] = l[:mm.start()] + neu + l[mm.end():]
    p.write_text("\n".join(z), encoding="utf-8")
# Baumverweise
baum = list(Path("Doku/projekt").rglob("*.md")) + [Path("PROJEKT.md")]
nref = 0
for p in baum:
    s = p.read_text(encoding="utf-8"); s0 = s
    for datei, von, alt, neu, q, k in plan:
        s = s.replace(f"[{q} {k}]", f"[{q} {neu}]")
    if s != s0:
        nref += sum(s0.count(f"[{q} {k}]") for _, _, _, _, q, k in plan); p.write_text(s, encoding="utf-8")
for x in plan: print(f"{Path(x[0]).name}:{x[1]} {x[5]} -> {x[3]}")
print("umbenannt", len(plan), "fehl", fehl, "Baumverweise", nref)
