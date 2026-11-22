#!/usr/bin/env python3
"""Fester Test (Sekunden, nur Standardbibliothek) fuer tools/code_stand.py (22.11.2026, Nulllauf kette-schwabentor-null-1122c: Zwischenstaende ohne Code-Stand -> Fix lief nie).
  1 Hilfsmodul aendert sich (Import in einer Funktion) -> Code-Stand anders; unbeteiligte Datei aendert sich -> gleich; Fremdbibliothek (json) zaehlt nicht; Kreisimport endet
  2 Nachstufe der Seitenmodelle: sfm_seiten_modelle.NACHSTUFE nennt Vereinen (Klappung + Foto-GPS) und Tore; ihr Code-Stand steckt in den Stand-Dateien des Vereinens
  3 Verdrahtung: pipeline_objekt.py prueft 'nachstufe_code' und ruft iphone_sfm.py mit RCPARK_SFM_NUR_NACHSTUFE=1; iphone_sfm.py bricht in diesem Modus vor jedem Mapper ab,
    wenn etwas Teures neu zu rechnen waere. Den Kettenablauf mit Attrappen prueft tools/test_seiten_modelle.py (Abschnitte 4f und 5).
Python: python3 -I tools/test_code_stand.py"""
import os, sys, tempfile, shutil
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
from code_stand import code_stand, dateien

S = temp_ordner("test_code_stand_")
try:
    open(os.path.join(S, "a.py"), "w").write("import json, os\ndef f():\n    from b import g\n    return g()\n")
    open(os.path.join(S, "b.py"), "w").write("import a\ndef g(): return 1\n")              # Kreisimport a <-> b
    open(os.path.join(S, "c.py"), "w").write("x = 1\n")
    d = [os.path.basename(p) for p in dateien("a.py", wurzel=S)]; assert d == ["a.py", "b.py"], f"eingerechnete Dateien {d}"
    s0 = code_stand("a.py", wurzel=S); assert len(s0) == 12 and s0 == code_stand("a.py", wurzel=S), "Code-Stand nicht stabil"
    open(os.path.join(S, "c.py"), "w").write("x = 2\n"); assert code_stand("a.py", wurzel=S) == s0, "unbeteiligte Datei aendert den Code-Stand"
    open(os.path.join(S, "b.py"), "w").write("import a\ndef g(): return 2\n"); s1 = code_stand("a.py", wurzel=S); assert s1 != s0, "geaendertes Hilfsmodul nicht erkannt"
    assert code_stand("a.py", "fehlt.py", wurzel=S) != s1, "fehlende Datei nicht eingerechnet"
    print(f"ok 1: Code-Stand {s0} -> {s1} nach Aenderung im Hilfsmodul, unbeteiligte Datei/Fremdbibliothek zaehlen nicht, Kreisimport endet")
finally: shutil.rmtree(S, ignore_errors=True)

q = lambda n: open(os.path.join(T, n)).read()
sm = q("sfm_seiten_modelle.py")
assert all(w in sm.split("NACHSTUFE = (")[1].split(")")[0] for w in ("seiten_vereinen.py", "seiten_gps_vereinen.py", "seiten_blick_tor.py", "gps_seiten_pruefen.py")), "NACHSTUFE unvollstaendig"
assert sm.count('code_stand("seiten_vereinen.py"') == 1 and sm.count('code_stand("seiten_gps_vereinen.py"') == 1 and 'ber["nachstufe_code"]' in sm, "Vereinen ohne Code-Stand in der Stand-Datei"
print("ok 2: Nachstufe (Klappung, Foto-GPS, Blick-Tor, GPS-Seiten-Tor) traegt den Code-Stand")
po, ip = q("pipeline_objekt.py"), q("iphone_sfm.py")
assert "seiten_nachstufe_veraltet(daten)" in po and 'RCPARK_SFM_NUR_NACHSTUFE="1"' in po, "pipeline_objekt prueft den Code-Stand der Nachstufe nicht"
assert ip.count("if NUR_NACHSTUFE and not") == 2 and ip.index("if NUR_NACHSTUFE and not _db_ok") < ip.index("pycolmap.extract_features") and ip.index("if NUR_NACHSTUFE and not _sm") < ip.index("_konsens(f\"{w}/sparse_konsens\")"), \
    "iphone_sfm NUR NACHSTUFE bricht nicht vor Merkmalssuche/Mapper ab"
assert "code_stand('lod2_gebaeude.py')" in q("sfm_lod2_ausrichten.py"), "LoD2-Cache ohne Code-Stand des Lesers"
print("ok 3: Verdrahtung pipeline_objekt -> iphone_sfm (nur Nachstufe), Schutz vor teurem Neurechnen, LoD2-Cache mit Code-Stand")
