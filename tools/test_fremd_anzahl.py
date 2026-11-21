#!/usr/bin/env python3
"""seiten.json 'fremd' als Liste (Martinstor 1121b: SfM-Ziel blieb 1053 statt ~373, weil int(list) still scheiterte)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline_objekt import fremd_anzahl
assert fremd_anzahl({"fremd": ["a.jpg"] * 1362}) == 1362
assert fremd_anzahl({"fremd": 12}) == 12
assert fremd_anzahl({}) == 0 and fremd_anzahl(None) == 0
n_gueltig, n_fremd = 2107, fremd_anzahl({"fremd": ["x"] * 1362})
assert 0.5 * (n_gueltig - n_fremd) < 574, "574 registrierte Objektbilder muessen das Ziel erreichen"
print("OK fremd_anzahl")
