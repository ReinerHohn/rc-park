#!/usr/bin/env python3
"""test_seiten_erkennen.py - feste Erwartungen fuer tools/seiten_erkennen.py (ohne GPU, ohne Bilder): Gemeinschaften, Zusammenhangsteile, Urteil."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seiten_erkennen import gemeinschaften, teile, urteil, quelle

f = 0
def pruefe(name, ok):
    global f; print(("  ok    " if ok else "  FEHLER ") + name); f += 0 if ok else 1

# zwei dichte Bildgruppen (je 8 Bilder, alle Paare 300 Zuordnungen), dazwischen 6 schwache 'Verwechslungs'-Paare (40) + ein Einzelbild
K = [(a, b, 300) for a in range(8) for b in range(a + 1, 8)] + [(a, b, 300) for a in range(10, 18) for b in range(a + 1, 18)] + [(i, 10 + i, 40) for i in range(6)]
C = gemeinschaften(K, list(range(8)) + list(range(10, 18)) + [99])
pruefe("zwei Seiten trotz Querverbindungen getrennt, Einzelbild eigene Gruppe", [sorted(c) for c in C] == [list(range(8)), list(range(10, 18)), [99]])
pruefe("wiederholbar (fester Zufallskeim)", gemeinschaften(K, list(range(8)) + list(range(10, 18)) + [99]) == C)
pruefe("Zusammenhang: verwechselte Verbindung entfernt -> zwei Teile", teile(3, []) == [[0], [1], [2]] and teile(3, [(0, 1)]) == [[0, 1], [2]])
pruefe("Urteil: 0,32 verwechselt, 0,52 unklar, 0,57 echt (Martinstor 19.11.2026)", (urteil(0.32, 0.45), urteil(0.52, 0.45), urteil(0.57, 0.45)) == ("verwechselt", "unklar", "echt"))
pruefe("Quelle aus Bildname", quelle("video_frames_abc__vf_012.jpg") == "video_frames_abc" and quelle("eigen__001_x.jpg") == "eigen")
sys.exit(1 if f else 0)
