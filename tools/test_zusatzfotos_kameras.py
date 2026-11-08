#!/usr/bin/env python3
"""Test zusatzfotos_registrieren.kamera_gruppen: Gruppen aus Format UND Zoomklasse, f/k1/cy aus Parameter-JSON (f in Bildpixeln = f_orig*skala),
Hauptpunkt auf das UNGECROPPTE Original bezogen, unbekannter Zoom -> normal aber markiert, fehlende Gruppe -> Fehler. Reine Funktionen, synthetisch."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zusatzfotos_registrieren as Z

P = {"kameras": {g: {"f_orig": (9550 if g.endswith("zoom") else 2790), "k1": (0.17 if g.endswith("zoom") else 0.02)} for g in ("quer_normal", "hoch_normal", "quer_zoom", "hoch_zoom")}}
B = {"h_a_01.jpg": dict(orig=[4000, 3000], bild=[2000, 1425], skala=0.5),
     "h_a_02.jpg": dict(orig=[3000, 4000], bild=[2000, 2533], skala=2 / 3),
     "h_f_01.jpg": dict(orig=[3000, 4000], bild=[2000, 2533], skala=2 / 3),
     "h_k_01.jpg": dict(orig=[4000, 3000], bild=[2000, 1425], skala=0.5),
     "h_k_02.jpg": dict(orig=[3000, 4000], bild=[2000, 2533], skala=2 / 3)}
ZO = {"bilder": {"h_a_01.jpg": {"klasse": "normal"}, "h_a_02.jpg": {"klasse": "abweichend"}, "h_f_01.jpg": {"klasse": "gezoomt"}}}
G, zu = Z.kamera_gruppen(B, ZO, P)
assert zu["h_a_01.jpg"] == ("quer_normal", "bewertet") and zu["h_a_02.jpg"] == ("hoch_normal", "bewertet")
assert zu["h_f_01.jpg"] == ("hoch_zoom", "bewertet")
assert zu["h_k_01.jpg"] == ("quer_normal", "unbekannt") and zu["h_k_02.jpg"] == ("hoch_normal", "unbekannt")
f, cx, cy, k1 = G["quer_normal"]["params"]; assert abs(f - 1395) < 1e-9 and abs(cx - 1000) < 1e-9 and abs(cy - 750) < 1e-9 and k1 == 0.02   # cy=1500*0.5, nicht 1425/2
f, cx, cy, k1 = G["hoch_normal"]["params"]; assert abs(f - 1860) < 1e-6 and abs(cx - 1000) < 1e-6 and abs(cy - 4000 / 2 * 2 / 3) < 1e-6   # gleiche Linse: f_Bild Hoch = 4/3 * Quer / ... aus f_orig
assert abs(G["hoch_zoom"]["params"][0] - 9550 * 2 / 3) < 1e-6 and G["hoch_zoom"]["params"][3] == 0.17
assert sorted(G["quer_normal"]["namen"]) == ["h_a_01.jpg", "h_k_01.jpg"]
_, zu2 = Z.kamera_gruppen(B, None, P); assert all(v[1] == "ohne_zoomdatei" for v in zu2.values())
try: Z.kamera_gruppen(B, ZO, {"kameras": {"quer_normal": P["kameras"]["quer_normal"]}}); assert False
except KeyError: pass
print("test_zusatzfotos_kameras: bestanden")
