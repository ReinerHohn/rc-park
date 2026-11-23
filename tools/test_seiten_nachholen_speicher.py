#!/usr/bin/env python3
"""test_seiten_nachholen_speicher.py - Nachbau des Fehlschlags der Kettenstufe seiten_luecken (23.11.2026, Kette schwabentor-null-1122n/o):
SiftGPU 'out of memory' (fremde GPU-Jobs) -> COLMAP laesst die neuen Bilder STILL aus der Datenbank weg (rc 0) -> Matching 5 min umsonst -> KeyError ->
Fehlschlag-Marke sperrt die Speicher-Wiederholung und den Folgelauf; Sued-/Ostwand bleiben leer (394 von 766 Fotos registriert).
Prueft: (1) zusatzfotos_registrieren.sift_sicher holt fehlende Bilder nach (GPU klein, dann CPU) und meldet echte Restfehler; merkmale prueft VOR dem Matching;
(2) seiten_luecken.sperrt: Speichermangel sperrt nicht, fester Fehler bei gleichem CODE-STAND schon; (3) skript_laufen bewertet nur den abgebrochenen Schritt;
(4) code_stand rechnet __import__("x") / importlib.import_module("x") mit ein. Echte pycolmap-Merkmale auf der CPU (winzige Bilder), GPU-Ausfall simuliert.
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/test_seiten_nachholen_speicher.py   Exit 0 = alles bestanden."""
import os, sys, json, sqlite3, subprocess
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import numpy as np, cv2, pycolmap
from pfade import temp_ordner
import zusatzfotos_registrieren as ZR, seiten_luecken as SL, code_stand as CS
from speicher_muster import speicher_fehler

fehler = 0


def pruef(ok, text):
    global fehler
    print(("ok   " if ok else "FEHLER ") + text, flush=True); fehler += 0 if ok else 1


def bilder_bauen(d, n=3):
    bd = os.path.join(d, "bilder"); os.makedirs(bd); rng = np.random.default_rng(0); info = {}
    for i in range(n):
        im = cv2.GaussianBlur((rng.random((240, 320)) * 255).astype(np.uint8), (5, 5), 0); nm = f"dl_x__{i}_W\u00fcrttemberg.jpg"      # Umlaut wie die Commons-Namen
        cv2.imwrite(os.path.join(bd, nm), im); info[nm] = dict(bild=[320, 240])
    return bd, info


def falsch_gpu(scheitert):
    """Ersatz fuer pycolmap.extract_features: Geraete in <scheitert> verhalten sich wie SiftGPU bei VRAM-Mangel (nichts schreiben, kein Fehler); sonst echtes CPU-SIFT."""
    aufrufe = []
    def ex(db, bd, image_names=(), device=None, extraction_options=None, **kw):
        g = {pycolmap.Device.auto: "auto", pycolmap.Device.cuda: "gpu", pycolmap.Device.cpu: "cpu"}[device]; aufrufe.append((g, len(image_names), extraction_options.max_image_size))
        if g in scheitert: return
        extraction_options.use_gpu = False; pycolmap.extract_features(db, bd, image_names=image_names, extraction_options=extraction_options, device=pycolmap.Device.cpu, **kw)
    return ex, aufrufe


d = temp_ordner("nachholen_speicher_")
if True:
    try:
        # (1) Nachholen fehlender Bilder
        for fall, scheitert, erwart in (("GPU belegt, kleine GPU-Runde klappt", {"auto"}, ("gpu_klein", 3)),
                                        ("GPU ganz weg, CPU-Rueckfall", {"auto", "gpu"}, ("cpu", 3)),
                                        ("alles scheitert (kaputte Datei)", {"auto", "gpu", "cpu"}, ("fehlend", 3))):
            dd = os.path.join(d, str(len(os.listdir(d)))); os.makedirs(dd); bd, info = bilder_bauen(dd); db = os.path.join(dd, "db.db"); ex, auf = falsch_gpu(scheitert)
            r = ZR.sift_sicher(pycolmap, db, bd, info, sorted(info), 300.0, extrahieren=ex, warte_s=0)
            n_ok = {k: len(v) for k, v in r.items()}
            pruef(n_ok[erwart[0]] == erwart[1] and sum(n_ok.values()) == 3 and (erwart[0] == "fehlend" or not ZR.sift_fehlend(db, sorted(info))),
                  f"{fall}: {n_ok} (Aufrufe {auf})")
        pruef(any(g == "gpu" and m == 1600 for g, m in [(a_[0], a_[2]) for a_ in auf]), "Wiederholung auf der GPU mit max_image_size 1600 (weniger VRAM)")
        q = open(os.path.join(T, "zusatzfotos_registrieren.py")).read(); i_s = q.find("sift = sift_sicher("); i_f = q.find('if sift["fehlend"]'); i_m = q.find("ver = sift_paare_matchen(db, pf")      # 23.11.2026: Matching in sift_paare_matchen (Schalter RCPARK_NACHHOL_SIFT_NUR_GEWAEHLT)
        pruef(0 < i_s < i_f < i_m, "merkmale: Nachholen und Abbruch bei fehlenden Bildern VOR dem Matching (1122n: 5 min Matching, dann KeyError)")

        # (2) Sperre der Fehlschlag-Marke
        pruef(SL.sperrt(dict(code_stand="abc", art="fest"), "abc") and SL.sperrt(dict(code_stand="abc"), "abc"), "fester Fehler (auch alte Marke ohne 'art') + gleicher CODE-STAND sperrt")
        pruef(not SL.sperrt(dict(code_stand="abc", art="speicher"), "abc"), "Speichermangel sperrt NICHT (1122n: Wiederholung lief nach 8 s in die Sperre)")
        pruef(not SL.sperrt(dict(code_stand="abc", art="fest"), "neu"), "geaenderter CODE-STAND gibt frei")

        # (3) Nur der abgebrochene Schritt entscheidet ueber 'Speichermangel'
        for name, zeilen, erwart in (("OOM im abgebrochenen Schritt", ["echo 'SCHRITT a: rechnen'", "echo ok", "echo 'SCHRITT b: rechnen'", "echo 'CuTexImage::InitTexture2D:\tout of memory'", "exit 1"], True),
                                     ("OOM frueher aufgefangen, fester Fehler spaeter", ["echo 'SCHRITT a: rechnen'", "echo 'FilterH:\tout of memory'", "echo 'SCHRITT b: rechnen'", "echo 'KeyError: x'", "exit 1"], False)):
            sk = os.path.join(d, "s.sh"); open(sk, "w").write("\n".join(["#!/bin/bash"] + zeilen) + "\n"); lg = os.path.join(d, "log", "l.log")
            rc, schluss = SL.skript_laufen(sk, lg)
            pruef(rc == 1 and speicher_fehler(rc, schluss) == erwart and "SCHRITT b" in open(lg).read(), f"{name}: Speichermangel = {speicher_fehler(rc, schluss)} (erwartet {erwart}), Log geschrieben")

        # (4) code_stand sieht dynamische Importe
        w = os.path.join(d, "w"); os.makedirs(w)
        open(os.path.join(w, "a.py"), "w").write('import importlib\nx = __import__("b").f\ny = importlib.import_module("c")\n'); open(os.path.join(w, "b.py"), "w").write("f = 1\n"); open(os.path.join(w, "c.py"), "w").write("g = 1\n")
        alt = CS.code_stand("a.py", wurzel=w); open(os.path.join(w, "b.py"), "w").write("f = 2\n")
        pruef({os.path.basename(p) for p in CS.dateien("a.py", wurzel=w)} == {"a.py", "b.py", "c.py"} and CS.code_stand("a.py", wurzel=w) != alt,
              "code_stand: __import__/import_module-Module zaehlen mit, ihre Aenderung gibt die Sperre frei")
        pruef("speicher_muster.py" in {os.path.basename(p) for p in CS.dateien(*SL.NACHHOL_WERKZEUGE)} and "json_sicher.py" in {os.path.basename(p) for p in CS.dateien(*SL.NACHHOL_WERKZEUGE)},
              "CODE-STAND der Nachhol-Werkzeuge enthaelt speicher_muster.py und json_sicher.py")
        # (5) Kontaktbogen zeigt ALLE Kandidaten (1122o: nur 120 von 372)
        kd = os.path.join(d, "kand"); os.makedirs(kd); fs = []
        for i in range(250): fs.append(os.path.join(kd, f"k{i:03d}.jpg")); cv2.imwrite(fs[-1], np.full((20, 30, 3), i % 255, np.uint8))
        bo = SL.kontaktboegen(fs, os.path.join(d, "seiten_luecken_kandidaten.jpg"))
        pruef([os.path.basename(p) for p in bo] == ["seiten_luecken_kandidaten.jpg", "seiten_luecken_kandidaten_2.jpg", "seiten_luecken_kandidaten_3.jpg"]
              and cv2.imread(bo[2]).shape[0] == 200 and cv2.imread(bo[0]).shape[0] == 2400, f"Kontaktbogen: 250 Kandidaten auf 3 Seiten ({[os.path.basename(p) for p in bo]})")
        import gesamtkette as GK
        pruef(GK.speichermangel(5, "CuTexImage::InitTexture2D:\tout of memory") and not GK.speichermangel(5, "KeyError"), "Kette und seiten_luecken nutzen dasselbe Speicher-Muster")
    except Exception as e:
        import traceback; traceback.print_exc(); pruef(False, f"Ausnahme {type(e).__name__}: {e}")
print("ERGEBNIS:", "alles bestanden" if not fehler else f"{fehler} Fehler"); sys.exit(1 if fehler else 0)
