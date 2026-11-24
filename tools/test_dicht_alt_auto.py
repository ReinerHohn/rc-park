#!/usr/bin/env python3
"""Test pipeline_objekt.dicht_alt_behandeln (24.11.2026: 1122za brach nach 2 min ab - SfM-Netz neu geschrieben, dichte Wolke alt -> rc 3 mit Handanweisung).
--bis kameras: Hinweis, rc 0, nichts beiseitegelegt. Sonst: automatisch beiseitelegen (nie loeschen) und weiter. RCPARK_DICHT_ALT_AUTO=0: alter Abbruch rc 3."""
import os, sys, time, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_objekt as PO

F = 0
def pruef(b, t):
    global F
    print(("    ok    " if b else "    FEHLER ") + t); F += (not b)


def aufbau():
    S = tempfile.mkdtemp(dir="/media/oem/rcdaten/tmp" if os.path.isdir("/media/oem/rcdaten/tmp") else None)
    D = os.path.join(S, "pipe"); Fo = os.path.join(S, "fotos"); t_ = time.time()
    for d_ in (os.path.join(D, "sfm", "sparse", "0"), os.path.join(D, "sfm", "sparse_dicht"), os.path.join(D, "dicht", "sparse"), Fo): os.makedirs(d_)
    def datei(q, alter): open(os.path.join(D, q), "w").write("x"); os.utime(os.path.join(D, q), (t_ - alter, t_ - alter))
    datei("sfm/sparse/0/images.bin", 10); datei("kameras.json", 5); datei("sfm/sparse_dicht/images.bin", 90); datei("dicht/sparse/images.bin", 80)
    fu = os.path.join(D, "dicht", "fused.ply"); open(fu, "wb").write(b"ply\nformat binary_little_endian 1.0\nelement vertex 0\nproperty float x\nend_header\n"); os.utime(fu, (t_ - 50, t_ - 50))
    return S, D, Fo


S, D, Fo = aufbau(); B = {"stufen": []}
st = PO.stand_pruefen(D, Fo); pruef(len(st["dicht_alt"]) >= 2, f"Ausgangslage: Wolke aelter als das Netz ({st['dicht_alt']})")
st2, rc = PO.dicht_alt_behandeln(D, Fo, st, True, B)
pruef(rc == 0 and os.path.isdir(os.path.join(D, "dicht")) and not any(n.startswith("dicht.alt_") for n in os.listdir(D)), "--bis kameras: rc 0, nichts beiseitegelegt")
st3, rc = PO.dicht_alt_behandeln(D, Fo, st, False, B, auto=True)
alt = [n for n in os.listdir(D) if n.startswith("dicht.alt_")]
pruef(rc == 0 and st3["dicht_alt"] == [] and alt and os.path.exists(os.path.join(D, alt[0], "fused.ply")), f"Automatik: beiseitegelegt (nicht geloescht: {alt}), danach kein veralteter Stand, rc 0")
pruef(any(s_["status"] == "ACHTUNG" and s_["name"] == "dicht" for s_ in B["stufen"]), "Bericht: Stufe dicht ACHTUNG mit Grund")
shutil.rmtree(S, ignore_errors=True)
S, D, Fo = aufbau(); B = {"stufen": []}
st = PO.stand_pruefen(D, Fo); st4, rc = PO.dicht_alt_behandeln(D, Fo, st, False, B, auto=False)
pruef(rc == 3 and os.path.exists(os.path.join(D, "dicht", "fused.ply")) and "FEHLER" in str(B), "abgeschaltet (RCPARK_DICHT_ALT_AUTO=0): alter Abbruch rc 3, nichts bewegt")
st5, rc = PO.dicht_alt_behandeln(D, Fo, dict(st, dicht_alt=[]), False, B)
pruef(rc == 0, "aktueller Stand: nichts zu tun")
shutil.rmtree(S, ignore_errors=True)
print("ALLE TESTS BESTANDEN" if F == 0 else f"{F} FEHLER"); sys.exit(1 if F else 0)
