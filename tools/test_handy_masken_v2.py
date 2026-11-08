#!/usr/bin/env python3
"""Test handy_masken_v2 (ohne GPU): Statue haengt an Fassade -> frei; Person am Boden -> maskiert; Box ohne Boden -> frei; Fleck im Pflaster -> verworfen; Fahrzeug immer."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handy_masken_v2 as M
lab = {0: "wall, ", 1: "building, edifice", 3: "floor, flooring", 6: "road, route", 11: "sidewalk, pavement", 12: "person, individual", 20: "car, auto", 41: "box", 76: "boat", 13: "earth"}
nm = M.namen(lab); ids = dict(alle=sorted(M.ids_von(nm, M.IMMER + M.BODENPFLICHT + M.MARKT)))
assert 76 not in ids["alle"]
seg = np.full((200, 200), 1, np.uint8); seg[120:, :] = 11            # Fassade oben, Boden ab Zeile 120
seg[30:50, 20:30] = 12                                                # Statue am Obergeschoss (Fassade ringsum)
seg[90:120, 60:72] = 12                                               # Person, Fuesse am Boden
seg[60:75, 100:120] = 41                                              # Kiste an der Fassade, kein Boden
seg[150:156, 150:160] = 41                                            # kleine Kiste ringsum Boden = Fleck
seg[80:100, 140:190] = 20                                             # Auto
res = {(r["klasse"], tuple(r["bbox"][:2])): r["behalten"] for r, _ in M.komponenten(seg, nm, ids)}
assert res[("person", (20, 30))] is False, res
assert res[("person", (60, 90))] is True, res
assert res[("box", (100, 60))] is False, res
assert res[("box", (150, 150))] is False, res
assert res[("car", (140, 80))] is True, res
print("test_handy_masken_v2: bestanden")
