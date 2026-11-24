#!/usr/bin/env python3
"""Rote Probe Kette 1122zb, Stufe konvergenz (628 s, rc 3, alle Seiten 'kein Beleg (Datendecke -> Fotoauftrag)'): die Ursache waren Werkzeugfehler, kein Datenbefund.
  1. foto_diff_batch Rastermodus: VRAM-Deckel aus JOB_GPU_MB, sonst Job-Buchung RCPARK_GPU_MB - 300 (Kette: RCPARK_GPU_MB=6000 -> 5700 statt 1500, 20/20 Fotos OOM);
     alle Aufgaben gescheitert -> Ausgang 2 statt 0.
  2. teil_fotoform: Pfad auf objekt.json (so ruft konvergenz.py) -> Objektname (vorher 'modelle/modelle/<obj>/objekt.json/objekt.json' FileNotFoundError).
  3. konvergenz: gescheiterte Messung heisst MESSFEHLER, nicht 'Datendecke -> Fotoauftrag'; echte Datenluecke bleibt 'kein Beleg'.
Aufruf: CUDA_VISIBLE_DEVICES= /media/oem/scan/venv-seg/bin/python -W ignore -I tests/test_konvergenz_messfehler.py"""
import os, sys, json, tempfile, shutil, inspect
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); T = os.path.join(R, "tools"); sys.path.insert(0, T)
F = []
def ok(c, t):
    print(("    ok   " if c else "    FEHLER ") + t, flush=True)
    if not c: F.append(t)

print("1. foto_diff_batch VRAM-Deckel")
import foto_diff_batch as FDB
alt = lambda env: float(env.get("JOB_GPU_MB", "1500"))      # bisherige Regel
kette = {"RCPARK_GPU_MB": "6000", "RCPARK_RAM_MB": "11000"}       # Umgebung der Kette 1122zb/1122zc (systemctl show)
ok(alt(kette) == 1500.0 and FDB.vram_deckel_mb(kette) == 5700.0, f"Kette (RCPARK_GPU_MB=6000, ohne JOB_GPU_MB): Deckel {FDB.vram_deckel_mb(kette):.0f} MiB (bisher {alt(kette):.0f})")
ok(FDB.vram_deckel_mb({"JOB_GPU_MB": "2000", "RCPARK_GPU_MB": "6000"}) == 2000.0, "JOB_GPU_MB ausdruecklich gewinnt")
ok(FDB.vram_deckel_mb({}) == 1500.0, "ohne Buchung wie bisher 1500")
ok(FDB.vram_deckel_mb({"RCPARK_GPU_MB": "900"}) == 1000.0, "kleine Buchung: mindestens 1000")
src = open(os.path.join(T, "foto_diff_batch.py")).read()
ok("vram_deckel_mb(os.environ)" in src and 'all("fehler" in v' in src, "Rastermodus nutzt vram_deckel_mb; alle Aufgaben gescheitert -> Ausgang 2")

print("2. teil_fotoform Objektname")
import teil_fotoform as TF
ok(TF.objekt_name("kaufhaus") == "kaufhaus", "Name bleibt Name")
cwd = os.getcwd(); os.chdir(R)
try:
    n = TF.objekt_name("modelle/kaufhaus/objekt.json")
    ok(n == "kaufhaus" and os.path.exists(os.path.join(TF.R0, "modelle", n, "objekt.json")), f"Pfad modelle/kaufhaus/objekt.json -> '{n}', objekt.json gefunden")
    ok(not os.path.exists(os.path.join(TF.R0, "modelle", "modelle/kaufhaus/objekt.json", "objekt.json")), "rote Probe: ohne Umwandlung waere der Pfad doppelt (Datei fehlt)")
finally: os.chdir(cwd)
ok("a.objekt = objekt_name(a.objekt)" in inspect.getsource(TF.main), "main wandelt das Argument um")

print("3. konvergenz MESSFEHLER statt Datendecke")
import konvergenz as KV
W = tempfile.mkdtemp(prefix="kvmf_")
try:
    E = {f"m|f{i}": dict(fehler="OutOfMemoryError: CUDA out of memory. Tried to allocate 32.00 MiB.") for i in range(5)}; E["m|g0"] = dict(kosten_lr=0.4, modellkanten_px=900)
    json.dump(dict(ergebnisse=E), open(os.path.join(W, "batch_ergebnis.json"), "w"))
    fg = KV.messfehler_grob(W)
    ok(set(fg) == {f"f{i}" for i in range(5)}, f"batch_ergebnis.json: {len(fg)} Fotos mit Werkzeugfehler erkannt")
    ok(KV.status_messfehler(KV.KEIN, ["f0", "f1"], fg, False) == KV.MESSFEHLER, "alle Fotos der Seite gescheitert -> MESSFEHLER")
    ok(KV.status_messfehler(KV.KEIN, ["f0", "g0"], fg, False) == KV.KEIN, "nur ein Teil gescheitert -> bleibt 'kein Beleg'")
    ok(KV.status_messfehler(KV.KEIN, ["h0"], {}, False) == KV.KEIN, "keine Fehler -> echte Datenluecke bleibt 'kein Beleg'")
    ok(KV.status_messfehler(KV.PLATEAU, ["f0"], fg, True) == KV.PLATEAU, "belegter Status bleibt")
    ok(KV.status_messfehler(KV.KEIN, [], {}, True, rund=True) == KV.MESSFEHLER and KV.status_messfehler(KV.KEIN, [], {}, False, rund=True) == KV.KEIN, "rund: feine Messung gescheitert -> MESSFEHLER")
    ok(KV.messfehler_grob(os.path.join(W, "fehlt")) == {}, "ohne batch_ergebnis.json: keine Fehler")
    m = inspect.getsource(KV.main)
    ok("status_messfehler(" in m and "fein_fehl = True" in m and "messfehler_grob(quelle)" in m, "main setzt den MESSFEHLER-Status (grob aus batch_ergebnis, fein aus teil_fotoform-rc)")
finally: shutil.rmtree(W, ignore_errors=True)
print("ALLE OK" if not F else f"FEHLER: {len(F)}: {F}")
sys.exit(1 if F else 0)
