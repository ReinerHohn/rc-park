#!/usr/bin/env python3
"""test_tiefe_lokal_zwischenstand.py - Zwischenstand der Feinrechnung (tools/tiefe_lokal.py) und Fotowahl nur aus dem Buendel (24.11.2026).
Anlass: Kette schwabentor-null-1122w, Teillauf seiten_wiederholung 6141 s; darin fassaden_kette 3285 s, davon 5 x tiefe_lokal (PatchMatch 435-585 s, seriell wegen
RAM-Grenze), obwohl die nachgeholten Kameras nur K-Dateien sind und NICHT im Buendel stehen - PatchMatch rechnete dasselbe Teilnetz ein zweites Mal. Zudem belegten
diese K-Dateien Plaetze der Fotowahl und fielen erst danach heraus (w01: 574k -> 384k Punkte im Teillauf).
  1. stereo_fotos: Kandidat ohne Bild im Buendel wird uebersprungen, der naechste gueltige rueckt nach; ohne Buendelmenge = alte Wahl (gleiche Reihenfolge).
     Wahl mit Buendelmenge ist unabhaengig von zusaetzlichen K-Dateien ausserhalb des Buendels (Teillauf = Hauptlauf).
  2. fused_schluessel: gleiche Eingaben -> gleicher Schluessel (auch in einem zweiten Prozess); andere Pose, anderer Bildinhalt, anderes max_size -> anderer Schluessel;
     Zeitstempel allein aendert ihn nicht.
  3. zwischenstand_passt / stereo_rechnen-Ablauf: passt nur mit gleicher Schluesseldatei UND nicht leerem fused.ply; RCPARK_TIEFE_LOKAL_NEU=1 erzwingt Neurechnen.
  4. Rasterung ist deterministisch: gleiches fused.ply -> byte-gleiches Relief (Zwischenstand liefert dasselbe Ergebnis wie der Lauf, der ihn schrieb).
Nur CPU, Sekunden. Umgebung: /media/oem/scan/venv-colmap/bin/python -I tests/test_tiefe_lokal_zwischenstand.py
"""
import os, sys, json, subprocess, tempfile, shutil, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); T = os.path.join(ROOT, "tools"); sys.path.insert(0, T)
import tiefe_lokal as TL
import pycolmap
n_ok = 0


def ok(b, t):
    global n_ok
    if not b: print("FEHLER:", t); sys.exit(1)
    n_ok += 1; print("    ok", t)


TMP = tempfile.mkdtemp(prefix="test_tiefe_zw_")
try:
    # 1 stereo_fotos
    od = os.path.join(TMP, "obj"); mp = os.path.join(od, "messprotokoll"); os.makedirs(mp)
    mitte = np.array([0.0, 0.0, 5.0])
    def kdatei(name, winkel_grad, r=20.0):
        w = np.radians(winkel_grad); S = [r * np.sin(w), -r * np.cos(w), 5.0]
        json.dump(dict(kamera=dict(standort=S)), open(os.path.join(mp, f"K-{name}.json"), "w"))
    # Standorte im Bogen alle 6 Grad -> jedes Paar benachbarter Fotos 6 Grad auseinander (4-35 Grad gilt), keine Doppel
    namen = [f"b{i:02d}" for i in range(10)]
    for i, nm in enumerate(namen): kdatei(nm, -30 + 6 * i)
    kdatei("nachgeholt_a", -27); kdatei("nachgeholt_b", 3)
    kand0 = [(100.0 - i, 0.9, nm) for i, nm in enumerate(namen)]
    kand1 = [(200.0, 0.9, "nachgeholt_a")] + kand0[:5] + [(95.5, 0.9, "nachgeholt_b")] + kand0[5:]       # nachgeholte K-Dateien mit hoher Guete dazwischen
    g_alt, _, _ = TL.stereo_fotos(od, kand0, mitte, 6, None)
    g_b0, _, ob0 = TL.stereo_fotos(od, kand0, mitte, 6, set(namen))
    ok([f for _, f in g_alt] == [f for _, f in g_b0] and not ob0, "ohne fremde K-Dateien: Wahl mit Buendelmenge = alte Wahl")
    g_b1, _, ob1 = TL.stereo_fotos(od, kand1, mitte, 6, set(namen))
    ok([f for _, f in g_b1] == [f for _, f in g_b0] and ob1 == ["nachgeholt_a", "nachgeholt_b"], "nachgeholte K-Dateien ausserhalb des Buendels aendern die Wahl NICHT (Teillauf = Hauptlauf), werden gemeldet")
    g_a1, _, _ = TL.stereo_fotos(od, kand1, mitte, 6, None)
    ok(sum(f in namen for _, f in g_a1) < len(g_b1), "Gegenprobe alter Weg: fremde K-Dateien belegen Plaetze, nach dem Buendel-Filter blieben weniger Stereo-Bilder")
    ok(len(g_b1) == 6, "k Plaetze werden mit Bildern des Buendels gefuellt")

    # 2 fused_schluessel auf einem kleinen synthetischen Teilnetz
    bilder = os.path.join(TMP, "bilder"); os.makedirs(bilder)
    def teilnetz(d, dx=0.0, n=3):
        rec = pycolmap.Reconstruction(); cam = pycolmap.Camera.create_from_model_name(1, "SIMPLE_RADIAL", 100.0, 64, 48); rec.add_camera_with_trivial_rig(cam)
        for i in range(n):
            im = pycolmap.Image(name=f"b{i}.jpg", camera_id=1, image_id=i + 1)
            rec.add_image_with_trivial_frame(im, pycolmap.Rigid3d(pycolmap.Rotation3d(), np.array([float(i) + (dx if i == 1 else 0.0), 0.0, 0.0])))
        rec.add_point3D(np.array([0.0, 0.0, 5.0]), pycolmap.Track(), np.array([10, 20, 30], np.uint8))
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d); rec.write(d); return d
    rng = np.random.default_rng(0)
    for i in range(3):
        import cv2; cv2.imwrite(os.path.join(bilder, f"b{i}.jpg"), rng.integers(0, 255, (48, 64, 3), dtype=np.uint8))
    sp = teilnetz(os.path.join(TMP, "sp"))
    s1 = TL.fused_schluessel(sp, bilder, 3200); s1b = TL.fused_schluessel(teilnetz(os.path.join(TMP, "sp2")), bilder, 3200)
    ok(s1 == s1b and len(s1) == 16, f"gleiche Eingaben, neu geschriebenes Teilnetz -> gleicher Schluessel ({s1})")
    code = f"import sys; sys.path.insert(0, {T!r}); import tiefe_lokal as TL; print(TL.fused_schluessel({sp!r}, {bilder!r}, 3200))"
    s_p = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True).stdout.strip().splitlines()[-1]
    ok(s_p == s1, "zweiter Prozess -> gleicher Schluessel (keine Zufalls-/Speicherreihenfolge)")
    ok(TL.fused_schluessel(teilnetz(os.path.join(TMP, "sp3"), dx=0.01), bilder, 3200) != s1, "andere Pose eines Bildes -> anderer Schluessel")
    ok(TL.fused_schluessel(teilnetz(os.path.join(TMP, "sp4"), n=2), bilder, 3200) != s1, "anderes Bild-Set -> anderer Schluessel")
    ok(TL.fused_schluessel(sp, bilder, 4000) != s1, "anderes max_size -> anderer Schluessel")
    p1 = os.path.join(bilder, "b1.jpg"); alt = open(p1, "rb").read()
    os.utime(p1, (time.time() + 100, time.time() + 100)); ok(TL.fused_schluessel(sp, bilder, 3200) == s1, "nur Zeitstempel geaendert -> gleicher Schluessel (Inhalt zaehlt)")
    open(p1, "wb").write(alt[:-1] + bytes([alt[-1] ^ 1])); ok(TL.fused_schluessel(sp, bilder, 3200) != s1, "Bildinhalt geaendert -> anderer Schluessel")
    open(p1, "wb").write(alt); ok(TL.fused_schluessel(sp, bilder, 3200) == s1, "Inhalt zurueck -> wieder derselbe Schluessel")

    # 3 zwischenstand_passt
    W = os.path.join(TMP, "w_fein"); os.makedirs(W)
    ok(not TL.zwischenstand_passt(W, s1), "ohne fused.ply/Schluessel -> rechnen")
    open(os.path.join(W, "fused.ply"), "wb").write(b"x"); ok(not TL.zwischenstand_passt(W, s1), "fused.ply ohne Schluesseldatei (Altstand vor 24.11.) -> rechnen")
    open(os.path.join(W, TL.SCHLUESSEL_DATEI), "w").write(s1 + "\n"); ok(TL.zwischenstand_passt(W, s1), "gleicher Schluessel + fused.ply -> uebernehmen")
    ok(not TL.zwischenstand_passt(W, "0" * 16), "anderer Schluessel -> rechnen")
    os.environ["RCPARK_TIEFE_LOKAL_NEU"] = "1"; ok(not TL.zwischenstand_passt(W, s1), "RCPARK_TIEFE_LOKAL_NEU=1 -> rechnen"); os.environ.pop("RCPARK_TIEFE_LOKAL_NEU")
    open(os.path.join(W, "fused.ply"), "wb").write(b""); ok(not TL.zwischenstand_passt(W, s1), "leeres fused.ply -> rechnen")
    src = open(os.path.join(T, "tiefe_lokal.py")).read()
    ok(src.index("os.remove(p_)") < src.index("pycolmap.patch_match_stereo") < src.index("SCHLUESSEL_DATEI), \"w\")"), "stereo_rechnen: Altstand+Schluessel weg VOR PatchMatch, Schluessel erst NACH der Fusion")

    # 4 Rasterung deterministisch: ein synthetisches fused.ply, zweimal --nur_raster -> byte-gleiche Reliefs
    ob = os.path.join(TMP, "objekte", "probe"); os.makedirs(os.path.join(ob, "messprotokoll"))
    json.dump(dict(transformation=dict(s=1.0, rvec=[0.0, 0.0, 0.0], t=[0.0, 0.0, 0.0])), open(os.path.join(ob, "messprotokoll", "SFM-AUSRICHTUNG-probe.json"), "w"))
    json.dump(dict(name="probe"), open(os.path.join(ob, "objekt.json"), "w"))
    Wr = os.path.join(TMP, "arbeit"); os.makedirs(Wr)
    uu, zz = np.meshgrid(np.linspace(0.05, 1.95, 120), np.linspace(0.05, 1.95, 120)); dd = 0.02 * np.sin(6 * uu) * np.cos(4 * zz)
    P = np.c_[uu.ravel(), dd.ravel(), zz.ravel()].astype("<f4")
    with open(os.path.join(Wr, "fused.ply"), "wb") as f:
        f.write(f"ply\nformat binary_little_endian 1.0\nelement vertex {len(P)}\nproperty float x\nproperty float y\nproperty float z\nend_header\n".encode()); f.write(P.tobytes())
    def raster():
        r = subprocess.run([sys.executable, "-I", os.path.join(T, "tiefe_lokal.py"), os.path.join(ob, "objekt.json"), "-", "-", "--name", "probe_fein", "--a", "0", "0", "--b", "2", "0",
                            "--aussen", "0", "-5", "--feld", "0", "2", "0", "2", "--px", "0.02", "--nur_raster", "--arbeit", Wr], capture_output=True, text=True, cwd=ROOT)
        p = os.path.join(ob, "relief", "probe_fein.npz")
        if r.returncode != 0 or not os.path.exists(p): print(r.stdout[-800:], r.stderr[-800:]); return None
        Z = dict(np.load(p)); os.remove(p); return Z
    r1 = raster(); r2 = raster()
    ok(r1 is not None and r2 is not None and r1.keys() == r2.keys() and all(np.array_equal(r1[k], r2[k]) for k in r1), "gleiches fused.ply -> gleiches Relief (Rasterung deterministisch, Zwischenstand = Ergebnis des Erzeugerlaufs)")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print(f"ALLE {n_ok} TESTS BESTANDEN")
