#!/usr/bin/env python3
"""Test kamerahoehe_dgm (24.11.2026, Kette 1122z Teil 1 = Ost-Teil: Hang-Kameras am Schlossberg ECHT 20-36 m ueber dem Turmfuss, DGM1 an der GPS-Lage).
Kern ohne pycolmap/DGM-Kacheln: stimmig (Hang + Strasse) -> ok, auf 60 % gestaucht (Kippung/Massstab) -> rot, gestreckt -> rot, ebenes Umfeld -> Steigung nicht
messbar, zu wenig Kameras -> unentschieden, erwartete Hoehen mit Ersatz-DGM (Handhoehe + Objektboden), CLI ohne Massstab -> rc 2."""
import os, sys
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import kamerahoehe_dgm as K

rng = np.random.default_rng(0)
# 1122z-Muster: 15 Strassenkameras (DGM 2,4-5,4 m ueber dem Turmfuss) + 12 Hangkameras (22-38 m)
he = np.r_[rng.uniform(2.4, 5.4, 15), rng.uniform(22, 38, 12)]
e = K.vergleich(he - 1.7 + rng.normal(0, 1.0, len(he)), he)
assert e["ok"] is True and abs(e["steigung"] - 1) < 0.1 and abs(e["versatz_m"] + 1.7) < 0.6, e
e = K.vergleich(0.6 * he + rng.normal(0, 0.5, len(he)), he)              # Hang-Kameras durch Kippung/Massstab um ~10 m abgesenkt
assert e["ok"] is False and "gestaucht" in e["urteil"] and abs(e["steigung"] - 0.6) < 0.1, e
e = K.vergleich(1.5 * he, he)
assert e["ok"] is False and "gestreckt" in e["urteil"], e
# ebenes Umfeld (Teil 0: DGM-Spanne 0,5 m) -> Steigung nicht messbar, Rest entscheidet
hf = rng.uniform(2.3, 2.8, 30)
e = K.vergleich(hf + rng.normal(0, 0.3, 30), hf); assert e["ok"] is True and e["steigung"] is None, e
e = K.vergleich(hf + rng.uniform(-14, 14, 30), hf)                       # Kameras streuen +-14 m im ebenen Umfeld (falsches Lot / Zentren); assert e["ok"] is False and "Rest" in e["urteil"], e
e = K.vergleich([1, 2, 3], [1, 2, 3]); assert e["ok"] is None and "zu wenig" in e["urteil"], e
# erwartete Hoehen: Ersatz-DGM (Hang nach Osten, 0,3 m je m) -> DGM(Kamera) + Handhoehe - DGM(Ursprung)
from bauwerk_pipeline import utm32
E0, N0 = utm32(47.99287686, 7.85411072)[:2]
dgm = lambda E, N: 282.3 + 0.3 * max(0.0, E - E0)
h, z0 = K.erwartete_hoehen([(47.99287686, 7.85411072), (47.992883, 7.855584)], (47.99287686, 7.85411072), dgm=dgm)
assert abs(z0 - 282.3) < 1e-6 and abs(h[0] - K.HAND_M) < 1e-6 and 30 < h[1] - K.HAND_M < 34, (h, z0)    # 110 m oestlich -> ~33 m hoeher
assert K.main(["--modell", "/nicht/da", "--bilder", "/nicht/da", "--ursprung", "48", "7.8"]) == 2
print("OK test_kamerahoehe_dgm")
