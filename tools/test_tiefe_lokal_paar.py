#!/usr/bin/env python3
"""test_tiefe_lokal_paar.py - Feinrechnung der Tiefe (tools/tiefe_lokal.py) bekommt ein passendes Buendel/Bild-Paar (21.11.2026).
Anlass: Kettenlauf schwabentor 1121o/p - tiefe_lokal 550 s + 622 s fuer 'fein 0 %' / 'fein 1 %' (Loecher 99,95 %): die Kette gab das ENTZERRTE Buendel
der dichten Wolke (dicht/sparse, PINHOLE 1200x1600) mit den VERZERRTEN Originalfotos (3000x4000, SIMPLE_RADIAL k1 bis 0,78) weiter.
  1. paar_pruefen: PINHOLE + andere Dateigroesse = rot (laute Meldung), PINHOLE + gleiche Groesse = ok, SIMPLE_RADIAL + andere Groesse (nur Massstab) = ok.
  2. gesamtkette.fein_paar: verzerrtes Quellbuendel sfm/sparse_dicht (sonst sfm/sparse/0) + Originalfotos; ohne das dicht/sparse + dicht/images; nie dicht/sparse + Originalfotos.
  3. cache_groesse: Cache fuer PatchMatch/Fusion aus dem freien RAM, 1-6 GB (vorher fest 12 GB / 32 GB auf 15-GB-Rechner, Signal 6 neben globalem OOM).
  4. fassaden_kette: rc 2 von tiefe_lokal schaltet die Feinrechnung fuer alle Waende ab (FEIN_AUS), rc 3 = 'ohne Abdeckung' wird gemeldet.
"""
import os, sys, tempfile
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER)
import tiefe_lokal as TL
import gesamtkette as GK
n_ok = 0


def ok(b, t):
    global n_ok
    if not b: print("FEHLER:", t); sys.exit(1)
    n_ok += 1; print("    ok", t)


# 1 paar_pruefen
k_ent = {"a.jpg": ("PINHOLE", 1200, 1600), "b.jpg": ("PINHOLE", 1600, 900)}
r = TL.paar_pruefen(k_ent, {"a.jpg": (3000, 4000), "b.jpg": (1920, 1080)}); ok(not r[0] and "ENTZERRTES Buendel mit ORIGINALFOTOS" in r[1] and "2 von 2" in r[1], "entzerrtes Buendel + Originalfotos -> Guard rot mit Meldung")
ok(TL.paar_pruefen(k_ent, {"a.jpg": (1200, 1600), "b.jpg": (1600, 900)})[0], "entzerrtes Buendel + seine entzerrten Bilder -> ok")
ok(TL.paar_pruefen({"a.jpg": ("SIMPLE_RADIAL", 1200, 1600)}, {"a.jpg": (3000, 4000)})[0], "verzerrtes Buendel, nur Massstab anders -> ok (bilder_anpassen skaliert)")
ok(not TL.paar_pruefen({"a.jpg": ("SIMPLE_PINHOLE", 1200, 1600), "b.jpg": ("SIMPLE_RADIAL", 3000, 4000)}, {"a.jpg": (3000, 4000), "b.jpg": (3000, 4000)})[0], "schon EIN verzerrungsfreies Bild mit falscher Groesse -> rot")
ok(TL.paar_pruefen(k_ent, {"a.jpg": None, "b.jpg": (1600, 900)})[0], "fehlende Datei entscheidet bilder_anpassen (nimmt sie raus), nicht der Guard")

# 2 fein_paar
with tempfile.TemporaryDirectory() as d:
    P = os.path.join(d, "pipe"); FV = os.path.join(d, "fotos"); os.makedirs(FV)
    def mk(*p):
        q = os.path.join(P, *p); os.makedirs(q, exist_ok=True); open(os.path.join(q, "images.bin"), "w").close()
    ok(GK.fein_paar(P, FV) == [], "ohne Buendel keine Feinrechnung")
    mk("dicht", "sparse"); ok(GK.fein_paar(P, FV) == [], "nur dicht/sparse ohne dicht/images -> NICHT mit Originalfotos (alter Fehler)")
    os.makedirs(os.path.join(P, "dicht", "images")); ok(GK.fein_paar(P, FV) == ["--fein", os.path.join(P, "dicht", "sparse"), os.path.join(P, "dicht", "images")], "dicht/sparse + dicht/images (entzerrt zu entzerrt)")
    mk("sfm", "sparse", "0"); ok(GK.fein_paar(P, FV) == ["--fein", os.path.join(P, "sfm", "sparse", "0"), FV], "sfm/sparse/0 (verzerrt) + Originalfotos vor dem 1600-px-Paar")
    mk("sfm", "sparse_dicht"); ok(GK.fein_paar(P, FV) == ["--fein", os.path.join(P, "sfm", "sparse_dicht"), FV], "sfm/sparse_dicht (Quelle der dichten Wolke) zuerst")

# 3 cache_groesse
ok(TL.cache_groesse(15.0) == 5.0 and TL.cache_groesse(40.0) == 6.0 and TL.cache_groesse(1.0) == 1.0, "Cache = RAM/3 in 1..6 GB")
src = open(os.path.join(HIER, "tiefe_lokal.py")).read()
ok("po.cache_size = 12" not in src and "fo.cache_size = cache_gb" in src, "kein fester 12-GB-Cache mehr, Fusion mit begrenztem Cache")

# 4 fassaden_kette
fk = open(os.path.join(HIER, "fassaden_kette.py")).read()
ok("rf_.returncode == 2" in fk and "FEIN_AUS[0] = " in fk and "not FEIN_AUS[0]" in fk, "fassaden_kette: Guard rc 2 -> Feinrechnung fuer alle Waende aus")
ok("rf_.returncode == 3" in fk, "fassaden_kette: rc 3 (Abdeckung) wird gemeldet")
gk = open(os.path.join(HIER, "gesamtkette.py")).read()
ok('"--fein", os.path.join(dd, "sparse"), FV' not in gk and "fein_paar(P, FV)" in gk, "gesamtkette ruft fein_paar statt dicht/sparse + Originalfotos")
print(f"{n_ok} Tests ok")
