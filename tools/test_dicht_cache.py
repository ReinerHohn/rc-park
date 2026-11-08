#!/usr/bin/env python3
"""test_dicht_cache.py - Gegenproben fuer dicht_handy_cache.py, OHNE GPU/PatchMatch.
(1) synthetisch: Schluessel aendern sich bei jeder relevanten Eingabeaenderung und nur dann; Treffer/Fehltreffer; cfg-Filter; Bitgleichheit; Manipulation -> Fehltreffer.
(3) Realdaten NUR LESEND (--real ARBEITSORDNER --cache-test DIR): Schluessel berechnen, N Bilder in Test-Cache, zurueckholen in leeren Ordner, Hash vergleichen.
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/test_dicht_cache.py [--real W --cache-test DIR --n 3]"""
import os, sys, json, copy, tempfile, argparse, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dicht_handy_cache as C

ok_alle = True
def pruefe(name, bed):
    global ok_alle
    ok_alle &= bool(bed); print(("OK   " if bed else "FEHL ") + name, flush=True)

def basis():
    def b(i): return dict(bild=f"img{i}", kamera=["PINHOLE", 100, 80, "f1", "f2"], pose=[f"p{i}"] * 7, punkte=f"pt{i}", maske=f"m{i}")
    return dict(bilder={f"a{i}.jpg": b(i) for i in range(6)},
                partner={"a0.jpg": ["a1.jpg", "a2.jpg"], "a1.jpg": ["a0.jpg", "a2.jpg"], "a2.jpg": ["a0.jpg", "a3.jpg"], "a3.jpg": ["a2.jpg", "a4.jpg"], "a4.jpg": ["a3.jpg"], "a5.jpg": ["a4.jpg"]})
OPT = dict(max_image_size=1600, geom_consistency=True, window_step=1, num_iterations=5)

def keys(be=None, opt=None, ver="4.2.1", mm=True):
    return C.alle_schluessel(be or basis(), opt or OPT, ver, mm)

def synthetisch():
    k0 = keys(); pruefe("deterministisch (zweimal gleich)", k0 == keys())
    # a0 hat Partner a1,a2; Partner-Partner: a0,a2 / a0,a3. a4/a5 sind weit weg (a5 -> a4 -> a3).
    def aender(f):
        be = basis(); f(be); return keys(be)
    def diff(k): return {n for n in k0 if k0[n] != k[n]}
    pruefe("eigenes Bild a0 geaendert -> a0 + alle die a0 als Partner/Partner-Partner haben (a1,a2,a3)",
           diff(aender(lambda b: b["bilder"]["a0.jpg"].__setitem__("bild", "NEU"))) == {"a0.jpg", "a1.jpg", "a2.jpg", "a3.jpg"})
    pruefe("Bild a5 geaendert -> nur a5 (niemand hat a5 als Partner)", diff(aender(lambda b: b["bilder"]["a5.jpg"].__setitem__("bild", "NEU"))) == {"a5.jpg"})
    pruefe("Pose a4 geaendert -> a4,a3,a5 + a2 (a2->a3->a4 Partner-Partner) ; a1,a0 nicht",
           diff(aender(lambda b: b["bilder"]["a4.jpg"].__setitem__("pose", ["x"] * 7))) == {"a4.jpg", "a3.jpg", "a5.jpg", "a2.jpg"})
    pruefe("Kamera a2 geaendert -> Schluessel von a0 aendert sich", "a0.jpg" in diff(aender(lambda b: b["bilder"]["a2.jpg"].__setitem__("kamera", ["PINHOLE", 1, 1, "z"]))))
    pruefe("Sparse-Punkte (Tiefenbereich) a1 geaendert -> a0 aendert sich", "a0.jpg" in diff(aender(lambda b: b["bilder"]["a1.jpg"].__setitem__("punkte", "andere"))))
    pruefe("Partnerliste a0 umsortiert -> a0 aendert sich", "a0.jpg" in diff(aender(lambda b: b["partner"].__setitem__("a0.jpg", ["a2.jpg", "a1.jpg"]))))
    pruefe("Partner a0 hat zusaetzlichen Partner -> a0 aendert sich", "a0.jpg" in diff(aender(lambda b: b["partner"].__setitem__("a0.jpg", ["a1.jpg", "a2.jpg", "a5.jpg"]))))
    pruefe("Partnerliste von a2 (Partner von a0) geaendert -> a0 aendert sich (photometrische Karte von a2 haengt daran)", "a0.jpg" in diff(aender(lambda b: b["partner"].__setitem__("a2.jpg", ["a0.jpg", "a4.jpg"]))))
    pruefe("Option max_image_size -> alle", diff(keys(opt=dict(OPT, max_image_size=2000))) == set(k0))
    pruefe("Option window_step -> alle", diff(keys(opt=dict(OPT, window_step=2))) == set(k0))
    pruefe("Option geom_consistency False -> alle", diff(keys(opt=dict(OPT, geom_consistency=False))) == set(k0))
    pruefe("COLMAP-Version -> alle", diff(keys(ver="4.3.0")) == set(k0))
    be = basis(); be["bilder"]["a0.jpg"]["maske"] = "mNEU"
    pruefe("Maske a0 geaendert -> nur a0 (mit_maske=True)", diff(keys(be)) == {"a0.jpg"})
    pruefe("Maske a0 geaendert, mit_maske=False -> gar nichts", keys(be, mm=False) == keys(mm=False))
    pruefe("Optionen ohne gpu_index/num_threads aendern Schluessel nicht", C.optionen_dict(dict(OPT, gpu_index="0", num_threads=3)) == C.optionen_dict(dict(OPT, gpu_index="1", num_threads=9)))
    pruefe("unabhaengige Aenderung a5 laesst a0..a4 unberuehrt (kein Ueberinvalidieren)", len(set(k0.values())) == 6)

    with tempfile.TemporaryDirectory() as td:
        W = os.path.join(td, "W"); cache = os.path.join(td, "cache"); rng = __import__("random").Random(1)
        for sub in ("depth_maps", "normal_maps"): os.makedirs(os.path.join(W, "stereo", sub))
        def schreibe(n, z=0):
            for c, p in C.quell_pfade(W, n): open(p, "wb").write(b"1&1&1&" + bytes(rng.getrandbits(8) for _ in range(500)) + bytes([z]))
        k = keys(); namen = list(k)
        for n in namen: schreibe(n)
        h0 = {n: [C.sha(p) for _, p in C.quell_pfade(W, n)] for n in namen}
        for n in namen[:4]: pruefe(f"speichern {n}", C.speichern(cache, k[n], W, n, "t"))
        pruefe("Treffer-Logik: 4 gueltig, 2 nicht", [C.gueltig(cache, k[n]) for n in namen] == [True] * 4 + [False] * 2)
        # Wiederholungslauf: Ordner leer, Treffer einsetzen
        W2 = os.path.join(td, "W2"); Wsave = W; W = W2
        for sub in ("depth_maps", "normal_maps"): os.makedirs(os.path.join(W, "stereo", sub))
        erg = {n: C.einsetzen(cache, k[n], W2, n) for n in namen}
        pruefe("einsetzen: 4 Treffer, 2 Fehltreffer", [erg[n] for n in namen] == [True] * 4 + [False] * 2)
        pruefe("Bitgleichheit Cache -> Arbeitsordner (sha256 aller 4 Karten)", all([C.sha(p) for _, p in C.quell_pfade(W2, n)] == h0[n] for n in namen[:4]))
        pruefe("kopiert, nicht hartverlinkt (Inode verschieden)", os.stat(C.quell_pfade(W2, namen[0])[0][1]).st_ino != os.stat(os.path.join(cache, k[namen[0]], "depth_geometric.bin")).st_ino)
        p = C.quell_pfade(W2, namen[0])[0][1]; open(p, "wb").write(b"maskiert")      # simuliert fusionieren(): in place ueberschreiben
        pruefe("In-place-Maskierung im Arbeitsordner zerstoert Cache nicht", C.gueltig(cache, k[namen[0]]))
        # Manipulation
        pm = os.path.join(cache, k[namen[1]], "normal_photometric.bin"); os.chmod(pm, 0o644); open(pm, "ab").write(b"x")
        pruefe("manipulierte Cachedatei -> Fehltreffer (nicht einsetzen)", not C.gueltig(cache, k[namen[1]]) and not C.einsetzen(cache, k[namen[1]], W2, namen[1]))
        os.remove(os.path.join(cache, k[namen[2]], "depth_geometric.bin"))
        pruefe("fehlende Cachedatei -> Fehltreffer", not C.gueltig(cache, k[namen[2]]))
        # cfg-Filter
        cfg = os.path.join(td, "pm.cfg"); open(cfg, "w").write("".join(f"{r}\n{', '.join(q)}\n" for r, q in basis()["partner"].items()))
        n = C.cfg_filtern(cfg, cfg + ".f", ["a4.jpg", "a5.jpg"]); z = C.lese_cfg(cfg + ".f")
        pruefe("cfg-Filter: nur fehlende Refs, Quellzeilen unveraendert", n == 2 and z == [("a4.jpg", ["a3.jpg"]), ("a5.jpg", ["a4.jpg"])])
        pruefe("cfg-Filter: leer -> 0", C.cfg_filtern(cfg, cfg + ".g", []) == 0)
        # Idempotenz speichern
        pruefe("speichern idempotent", C.speichern(cache, k[namen[0]], Wsave, namen[0]) and C.gueltig(cache, k[namen[0]]))
        b = C.bericht(cache, budget_gb=1e-9); pruefe("Bericht liefert LRU-Vorschlag, loescht nichts", b["eintraege"] == 4 and len(b["vorschlag_loeschen_lru"]) >= 1 and os.path.isdir(os.path.join(cache, k[namen[0]])))

def real(W, cache, n, max_size):
    import pycolmap
    opt = pycolmap.PatchMatchOptions(); opt.max_image_size = max_size; opt.geom_consistency = True
    vor = os.stat(os.path.join(W, "stereo", "patch-match.cfg")).st_mtime
    be = C.beschreibe_stapel(W); k = C.alle_schluessel(be, C.optionen_dict(opt), pycolmap.__version__)
    pruefe(f"real: {len(k)} Schluessel, alle verschieden", len(set(k.values())) == len(k))
    pruefe("real: zweite Berechnung identisch", k == C.alle_schluessel(C.beschreibe_stapel(W), C.optionen_dict(opt), pycolmap.__version__))
    be2 = copy.deepcopy(be); nm = sorted(k)[0]; be2["bilder"][nm]["pose"][0] = "x"
    pruefe("real: Posenaenderung eines Bildes aendert dessen Schluessel", C.alle_schluessel(be2, C.optionen_dict(opt), pycolmap.__version__)[nm] != k[nm])
    pruefe("real: Option max_image_size aendert Schluessel", C.alle_schluessel(be, C.optionen_dict(opt) | {"max_image_size": max_size + 1}, pycolmap.__version__)[nm] != k[nm])
    ausw = sorted(k)[:n]; print("Bilder:", ausw)
    for m in ausw: pruefe(f"real: speichern {m}", C.speichern(cache, k[m], W, m, "real-test"))
    with tempfile.TemporaryDirectory(dir=os.path.dirname(cache.rstrip("/"))) as td:
        for sub in ("depth_maps", "normal_maps"): os.makedirs(os.path.join(td, "stereo", sub))
        for m in ausw:
            pruefe(f"real: einsetzen {m}", C.einsetzen(cache, k[m], td, m))
            pruefe(f"real: Bitgleichheit {m} (4 Karten, sha256)", [C.sha(p) for _, p in C.quell_pfade(td, m)] == [C.sha(p) for _, p in C.quell_pfade(W, m)])
    pruefe("real: Arbeitsordner unveraendert (cfg-mtime)", vor == os.stat(os.path.join(W, "stereo", "patch-match.cfg")).st_mtime)
    print(json.dumps(C.bericht(cache), indent=1))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--real"); ap.add_argument("--cache-test"); ap.add_argument("--n", type=int, default=3); ap.add_argument("--max-size", type=int, default=1600)
    a = ap.parse_args(); synthetisch()
    if a.real: real(a.real, a.cache_test, a.n, a.max_size)
    print("ALLE GEPRUEFT: OK" if ok_alle else "FEHLER"); sys.exit(0 if ok_alle else 1)
