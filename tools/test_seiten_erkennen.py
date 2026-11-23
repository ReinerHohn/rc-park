#!/usr/bin/env python3
"""test_seiten_erkennen.py - feste Erwartungen fuer tools/seiten_erkennen.py (ohne GPU, ohne Bilder): Gemeinschaften, Zusammenhangsteile, Urteil."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seiten_erkennen import gemeinschaften, teile, urteil, quelle, richtung, gruppen_richtung, urteil_gps, fernsicht_gruppen, fernsicht_behalten

f = 0
def pruefe(name, ok):
    global f; print(("  ok    " if ok else "  FEHLER ") + name); f += 0 if ok else 1

# zwei dichte Bildgruppen (je 8 Bilder, alle Paare 300 Zuordnungen), dazwischen 6 schwache 'Verwechslungs'-Paare (40) + ein Einzelbild
K = [(a, b, 300) for a in range(8) for b in range(a + 1, 8)] + [(a, b, 300) for a in range(10, 18) for b in range(a + 1, 18)] + [(i, 10 + i, 40) for i in range(6)]
C = gemeinschaften(K, list(range(8)) + list(range(10, 18)) + [99])
pruefe("zwei Seiten trotz Querverbindungen getrennt, Einzelbild eigene Gruppe", [sorted(c) for c in C] == [list(range(8)), list(range(10, 18)), [99]])
pruefe("wiederholbar (fester Zufallskeim)", gemeinschaften(K, list(range(8)) + list(range(10, 18)) + [99]) == C)
pruefe("Zusammenhang: verwechselte Verbindung entfernt -> zwei Teile", teile(3, []) == [[0], [1], [2]] and teile(3, [(0, 1)]) == [[0, 1], [2]])
pruefe("Urteil: kein Paar sieht gleich aus -> verwechselt; einige eindeutig gleiche -> echt; dazwischen unklar; zu kleine Stichprobe unklar", (urteil([0.2, 0.3, 0.33, 0.35, 0.4, 0.42, 0.3, 0.25, 0.45, 0.31]), urteil([0.3, 0.4, 0.5, 0.45, 0.9, 0.95, 0.35, 0.5, 0.6, 0.4]), urteil([0.4, 0.5, 0.55, 0.6, 0.62, 0.45, 0.5, 0.52, 0.48, 0.7]), urteil([0.1, 0.1])) == ("verwechselt", "echt", "unklar", "unklar"))
pruefe("Quelle aus Bildname", quelle("video_frames_abc__vf_012.jpg") == "video_frames_abc" and quelle("eigen__001_x.jpg") == "eigen")
w, d = richtung((47.99, 7.85), (47.9909, 7.85))
pruefe("GPS: Foto 100 m noerdlich der Objektmitte -> Richtung 0 Grad, Abstand ~100 m", (w < 1 or w > 359) and 99 < d < 101)
pruefe("GPS: Gruppenrichtung ueber Nord hinweg gemittelt (350, 10, 0 -> 0 Grad); rundum verteilte Gruppe und < 3 Fotos = keine Richtung", (lambda r: r is not None and (r[0] < 1 or r[0] > 359))(gruppen_richtung([350, 10, 0])) and gruppen_richtung([0, 120, 240]) is None and gruppen_richtung([5, 6]) is None)
pruefe("GPS: gegenueber (170 Grad) verwechselt, benachbart (40 Grad) echt, Ecke (90 Grad) keine Aussage, ohne GPS keine Aussage", (urteil_gps((10, 1), (180, 1)), urteil_gps((350, 1), (30, 1)), urteil_gps((0, 1), (90, 1)), urteil_gps(None, (90, 1))) == ("verwechselt", "echt", None, None))
# FERNSICHT (22.11.2026, schwabentor-1122: 10 Fernfotos aus ~320 m als eigene 'Seite' abgeschnitten -> Ausrichtung ohne Hebel). Synthetisch, Mitte (48.0, 7.85):
M_ = (48.0, 7.85); m = 1 / 111320.0
gq = {0: [(48.0 + 20 * m, 7.85), (48.0 + 25 * m, 7.85 + 3 * m), (48.0 + 22 * m, 7.85)],                               # Nah-Seite 20-25 m
      22: [(48.0 + 320 * m, 7.85 + i * m) for i in range(6)] + [(48.0 + 30 * m, 7.85)],                               # Fernsicht: 6 von 7 bei 320 m, 6 Orte
      5: [(48.0 + 272 * m, 7.85)] * 4,                                                                                 # eingefrorener Geotag: 4x derselbe Ort
      7: [(48.0 + 19000 * m, 7.85)] * 2 + [(48.0 + 19000 * m, 7.85 + m)],                                             # 19 km = Ortsmarke
      9: [(48.0 + 320 * m, 7.85)]}                                                                                    # zu wenige GPS-Fotos
pruefe("Fernsicht: nur Gruppe mit ueberwiegend fernen GPS-Fotos an mehreren Orten (nicht nah, nicht eingefroren, nicht Ortsmarke, nicht < 3 Fotos)", fernsicht_gruppen(gq, M_) == {22})
verb = [dict(a=0, b=22, paare=95, urteil="unklar"), dict(a=1, b=22, paare=40, urteil="unklar"), dict(a=3, b=22, paare=200, urteil="verwechselt"), dict(a=0, b=1, paare=50, urteil="unklar")]
beh = fernsicht_behalten(verb, {22})
pruefe("Fernsicht: genau EINE Verbindung behalten (staerkste unklare 0<->22), nie die verwechselte, nie zwei Seiten verbruecken, Nicht-Fernsicht unberuehrt", beh == {(0, 22)} and bool(verb[0].get("fernsicht_behalten")) and not verb[1].get("fernsicht_behalten") and not verb[2].get("fernsicht_behalten") and not verb[3].get("fernsicht_behalten"))
pruefe("Fernsicht: ohne Fernsicht-Gruppen bleibt --streng unveraendert", fernsicht_behalten([dict(a=0, b=22, paare=95, urteil="unklar")], set()) == set())
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfm_seiten_vorstufe.py")).read()
pruefe("Verdrahtung: sfm_seiten_vorstufe gibt --fernsicht <RCPARK_SEITEN_OBJEKT> an seiten_erkennen und rechnet bei neuer Regel neu (Stand)", '"--fernsicht", oj' in src and "+ ref + fs, check=False" in src and '"fernsicht2"' in src)
sys.exit(1 if f else 0)
