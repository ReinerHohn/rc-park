#!/usr/bin/env python3
"""test_bau_parallel.py - Bau-Beschleunigung (24.11.2026) aendert das Ergebnis nicht; < 30 s, nur CPU.

Befund: ein Generatorlauf (Schwabentor-1122) dauerte 200-360 s auf praktisch EINEM Kern. Beschleunigt wurden (tools/bau_parallel.py, bauteile.py, fassaden_kette.py, ortsteine.py):
  1 unique_zeilen  = np.unique(axis=0) per lexsort (kneifkanten_schliessen, stl_schreiben): gleiche Zeilen, Reihenfolge, Zuordnung, Zaehlung.
  2 prozess_map    Dateischritte je Wand/Fassade in Kindprozessen: Ergebnisse + Ausgabe in Aufgabenreihenfolge, Fehler des Kindes kommt mit Typ im Elternprozess an,
                   RCPARK_BAU_SERIELL=1 rechnet im eigenen Prozess (alter Weg).
  3 STL            kneifkanten_schliessen + stl_schreiben neu vs. alter Weg (RCPARK_BAU_SERIELL=1) an einem Koerper mit Beruehrkante: bitgleiche Dreiecksmenge.
  4 Strahlsonde    _oberflaeche_w mit Netz-Zwischenspeicher = ohne; anderer Koerper = neues Netz (kein veralteter Treffer).
  5 Vergleich      bau_parallel.vergleichen erkennt gleich (0) und verschoben (Hausdorff > 0,01).
  6 Putzkarte      putz_wandbild.glatt_karte ueber RCPARK_GLATT_CACHE: 3 Kindprozesse, einmal gerechnet (Dateisperre), Ergebnis = Rechnung im Prozess.
"""
import sys, os, io, contextlib, numpy as np
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HIER), "tools")); sys.path.insert(0, HIER)
F = 0


def pruef(ok, text):
    global F
    print(("  ok     " if ok else "  FEHLER ") + text)
    if not ok: F += 1


def quadrat_mit_ausgabe(x):                                                # Aufgabe fuer die Kindprozesse (Modul test_bau_parallel ist dort importierbar)
    print(f"aufgabe {x}"); return x * x


def wirft(x):
    raise ValueError(f"absichtlich {x}")


def main():
    from bauteile import unique_zeilen, kneifkanten_schliessen, stl_schreiben, _oberflaeche_w, _oberflaeche_w_leeren, Wand
    import bau_parallel as BP
    from manifold3d import Manifold as M
    from pfade import temp_ordner
    rng = np.random.default_rng(3)
    # 1
    A = np.round(rng.uniform(-3.0, 3.0, (20000, 3)), 1); E = rng.integers(0, 50, (30000, 2)); G = np.round(rng.uniform(-5e5, 5e5, (5000, 3)), 3)
    for X, st, nm in ((A, None, "Gleitkomma-Ecken, lexsort"), (A, 1, "Gleitkomma-Ecken gerundet, int64-Schluessel"), (E, None, "Ganzzahl-Kanten"), (np.r_[G, G[:900]], 3, "zu breit fuer 62 Bit -> lexsort")):
        u0, i0, c0 = np.unique(X, axis=0, return_inverse=True, return_counts=True); u1, i1, c1 = unique_zeilen(X, inverse=True, counts=True, stellen=st)
        pruef(np.array_equal(u0, u1) and np.array_equal(i0.ravel(), i1) and np.array_equal(c0, c1), f"unique_zeilen = np.unique(axis=0) ({nm}, {len(u0)} verschiedene)")
    # 2
    os.environ.pop("RCPARK_BAU_SERIELL", None)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = BP.prozess_map("test_bau_parallel", "quadrat_mit_ausgabe", [((i,), {}) for i in range(5)], name="T", n=3)
    zeilen = [z for z in buf.getvalue().splitlines() if z.startswith("aufgabe")]
    pruef(r == [0, 1, 4, 9, 16] and zeilen == [f"aufgabe {i}" for i in range(5)], f"prozess_map 3 Prozesse: Ergebnis + Ausgabe in Reihenfolge ({r})")
    try:
        with contextlib.redirect_stdout(io.StringIO()): BP.prozess_map("test_bau_parallel", "wirft", [((1,), {}), ((2,), {})], name="T", n=2)
        pruef(False, "Fehler im Kind kommt an")
    except ValueError as e: pruef("absichtlich 1" in str(e), "Fehler im Kind kommt als ValueError im Elternprozess an")
    os.environ["RCPARK_BAU_SERIELL"] = "1"; buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = BP.prozess_map("test_bau_parallel", "quadrat_mit_ausgabe", [((i,), {}) for i in range(3)], name="T", n=3)
    pruef(r == [0, 1, 4] and "Prozessen" not in buf.getvalue(), "RCPARK_BAU_SERIELL=1: im eigenen Prozess, ohne Kinder")
    os.environ.pop("RCPARK_BAU_SERIELL", None)
    # 3: zwei Quader, die sich nur an einer Kante beruehren (4 Flaechen an einer Kante) + Kugel
    k = M.cube((10, 10, 10)).translate((5, 5, 5)) + M.cube((10, 10, 10)).translate((15, 15, 5)) + M.sphere(4, 64).translate((30, 8, 9))
    td = temp_ordner("test_bau_parallel_"); pa, pb = os.path.join(td, "neu.stl"), os.path.join(td, "alt.stl")
    with contextlib.redirect_stdout(io.StringIO()):
        n_neu = stl_schreiben(k, pa); os.environ["RCPARK_BAU_SERIELL"] = "1"; n_alt = stl_schreiben(k, pb); os.environ.pop("RCPARK_BAU_SERIELL", None)
    v = BP.vergleichen(pa, pb)
    pruef(n_neu == n_alt and v["bitgleich"] and v["hausdorff_schranke"] == 0.0, f"stl_schreiben neu = alt (Kneifkante geschlossen): {v}")
    with contextlib.redirect_stdout(io.StringIO()): kv = kneifkanten_schliessen(k, r=0.25, stellen=3)
    os.environ["RCPARK_BAU_SERIELL"] = "1"
    with contextlib.redirect_stdout(io.StringIO()): ka = kneifkanten_schliessen(k, r=0.25, stellen=3)
    os.environ.pop("RCPARK_BAU_SERIELL", None)
    pruef(kv.num_tri() == ka.num_tri() and abs(kv.volume() - ka.volume()) < 1e-9 and kv.num_tri() > k.num_tri(), f"kneifkanten_schliessen neu = alt ({kv.num_tri()} Dreiecke, Klotz eingefuegt)")
    # 5
    with contextlib.redirect_stdout(io.StringIO()): stl_schreiben(k.translate((0.02, 0, 0)), pb)
    v2 = BP.vergleichen(pa, pb); pruef(not v2["bitgleich"] and v2["hausdorff_schranke"] > 0.01, f"vergleichen erkennt 0,02 Verschiebung (Hausdorff {v2['hausdorff_schranke']:.3f})")
    # 4
    W = Wand((0, -20), (0, 20), (10, 0)); P = [(u, z) for u in (5, 10, 20, 30) for z in (2, 6, 9)]
    k1 = M.cube((6, 40, 12)).translate((-6, -20, 0)); k2 = k1 + M.cube((1, 40, 12)).translate((0, -20, 0))
    _oberflaeche_w_leeren(); a1 = _oberflaeche_w(k1, W, P); a1b = _oberflaeche_w(k1, W, P); a2 = _oberflaeche_w(k2, W, P)
    os.environ["RCPARK_BAU_SERIELL"] = "1"; s2 = _oberflaeche_w(k2, W, P); os.environ.pop("RCPARK_BAU_SERIELL", None); _oberflaeche_w_leeren()
    pruef(a1 == a1b and a2 == s2 and all(abs(x) < 1e-9 for x in a1) and all(abs(x - 1.0) < 1e-9 for x in a2), f"Strahlsonde mit Zwischenspeicher = ohne, neuer Koerper neu gemessen ({a1[0]:.2f} -> {a2[0]:.2f})")
    # 6: Putzkarte ueber Kindprozesse geteilt (putz_wandbild.glatt_karte, RCPARK_GLATT_CACHE) = im Prozess gerechnet
    import json as _js
    from PIL import Image
    import putz_wandbild as PW
    ffn = os.path.join(td, "fein"); os.makedirs(os.path.join(ffn, "ortho_f00_einzeln")); _js.dump(dict(fassaden=[dict(id="f00", raster=dict(zelle=0.01, u0=0.0, z1=2.0))]), open(os.path.join(ffn, "fassaden.json"), "w"))
    for i in range(3):
        g = np.full((200, 300), 120.0); g[:, 150:] += rng.normal(0, 40, (200, 150)); g[:20, :40] = 0       # links glatt, rechts rau, Ecke verdeckt
        Image.fromarray(np.clip(g, 1, 255).astype(np.uint8)).save(os.path.join(ffn, "ortho_f00_einzeln", f"{i}.png"))
    PW._CACHE.clear(); ref = PW.glatt_karte(ffn, "f00"); gd = os.path.join(td, "glatt"); os.makedirs(gd); os.environ["RCPARK_GLATT_CACHE"] = gd
    with contextlib.redirect_stdout(io.StringIO()): R = BP.prozess_map("putz_wandbild", "glatt_karte", [((ffn, "f00"), {})] * 3, name="T", n=3)
    os.environ.pop("RCPARK_GLATT_CACHE", None)
    gleich = all(set(r) == set(ref) and all(np.array_equal(r[k_], ref[k_]) if isinstance(ref[k_], np.ndarray) else r[k_] == ref[k_] for k_ in ref) for r in R)
    pruef(gleich and len([x for x in os.listdir(gd) if x.endswith(".pkl")]) == 1 and 0.2 < ref["putz"].mean() < 0.8,
          f"Putzkarte in 3 Kindprozessen einmal gerechnet, gleich der Rechnung im Prozess (Putzanteil {ref['putz'].mean():.2f})")
    print("FEHLER:", F); return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
