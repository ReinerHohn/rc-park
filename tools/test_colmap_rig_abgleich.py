#!/usr/bin/env python3
"""test_colmap_rig_abgleich.py - synthetischer Nachbau des Absturzes der Kettenstufe seiten_luecken (22.11.2026, schwabentor-1120, Laeufe 1122c/1122d):
"ValueError: [reconstruction.cc:327] Check failed: existing_frame.RigId() == frame.RigId()" in pycolmap.triangulate_points (tools/zusatzfotos_lightglue.py einlesen).
Nachbau: pycolmap.synthesize_dataset (2 Kameras x 3 Bilder, im Modell GETEILT) -> in der Datenbank bekommt ein Bild eine eigene Kamera + eigenen Rig (wie pipe/sfm/db.db:
je Bild eine Kamera, Modell: Videobilder teilen eine). Erwartet: ohne Angleichen derselbe Absturz; nach tools/colmap_rig_abgleich.angleichen laeuft triangulate_points;
probe() meldet ok auf der echten Konstellation, Konflikte vorher > 0, nachher 0; seiten_luecken erzeugt ein Skript mit Vorpruefung, Schritt-Staenden und Fehlschlag-Marke.
Umgebung: venv-colmap (pycolmap). Ohne pycolmap: UEBERSPRUNGEN (rc 0). Dauer ~2 s."""
import os, sys, sqlite3, shutil, tempfile, subprocess
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from pfade import temp_ordner                                         # 22.11.2026: Temp nicht auf Root, beim Ende aufgeraeumt (auch nach assert)
try: import pycolmap
except ImportError: print("UEBERSPRUNGEN: pycolmap fehlt (venv-colmap nutzen)"); sys.exit(0)
import colmap_rig_abgleich as RA

fehler = 0
def pruef(ok, text):
    global fehler
    print(("OK    " if ok else "FEHLER") + " " + text)
    if not ok: fehler += 1


def aufbau(d):
    o = pycolmap.SyntheticDatasetOptions(); o.num_rigs = 2; o.num_cameras_per_rig = 1; o.num_frames_per_rig = 3; o.num_points3D = 150
    dbp = os.path.join(d, "db.db"); db = pycolmap.Database.open(dbp) if hasattr(pycolmap.Database, "open") else pycolmap.Database(dbp)
    rec = pycolmap.synthesize_dataset(o, db); db.close(); sp = os.path.join(d, "sp"); os.makedirs(sp); rec.write(sp)
    con = sqlite3.connect(dbp)                       # Bild 2 bekommt in der DATENBANK eigene Kamera 7 + eigenen Rig 7 (wie die Kette: je Bild eine Kamera)
    row = con.execute("select model, width, height, params, prior_focal_length from cameras where camera_id=1").fetchone()
    con.execute("insert into cameras (camera_id, model, width, height, params, prior_focal_length) values (7,?,?,?,?,?)", row)
    con.execute("insert into rigs (rig_id, ref_sensor_id, ref_sensor_type) values (7, 7, 0)")
    con.execute("update images set camera_id=7 where image_id=2"); con.execute("update frames set rig_id=7 where frame_id=2")
    con.execute("update frame_data set sensor_id=7 where frame_id=2 and data_id=2"); con.commit(); con.close()
    return dbp, sp


def tri(dbp, sp, d, name):
    td = os.path.join(d, name); os.makedirs(td, exist_ok=True); bd = os.path.join(d, "bilder"); os.makedirs(bd, exist_ok=True)
    return pycolmap.triangulate_points(pycolmap.Reconstruction(sp), dbp, bd, td, clear_points=True)


d = temp_ordner("test_rig_")
try:
    dbp, sp = aufbau(d); rec = pycolmap.Reconstruction(sp)
    k = RA.konflikte(dbp, rec); pruef(len(k) == 2 and {x["art"] for x in k} == {"Kamera anders", "Rig anders"}, f"Konflikt erkannt (Kamera + Rig von Bild 2): {[(x['name'], x['art']) for x in k]}")
    kopie = os.path.join(d, "kopie.db"); shutil.copy(dbp, kopie)
    try: tri(kopie, sp, d, "t0"); pruef(False, "ohne Angleichen haette triangulate_points abstuerzen muessen (Nachbau stimmt nicht)")
    except ValueError as e: pruef("RigId" in str(e), f"Nachbau: ohne Angleichen derselbe Absturz wie in der Kette ({str(e)[:70]})")
    ok, t = RA.probe(dbp, sp, os.path.join(d, "probe")); pruef(ok and "2 Zuordnungskonflikte" in t, f"probe (Mini-Datenbank ohne Merkmale): {t[:110]}")
    n = RA.angleichen(kopie, rec); pruef(n == 1 and RA.konflikte(kopie, rec) == [], f"angleichen haengt 1 Bild um, danach 0 Konflikte (n={n})")
    r = tri(kopie, sp, d, "t1"); pruef(r.num_points3D() > 100, f"nach Angleichen triangulate_points ok: {r.num_points3D()} Punkte")
    pruef(RA.angleichen(kopie, rec) == 0, "zweites Angleichen aendert nichts")
    con = sqlite3.connect(dbp); con.execute("update images set name='falsch.png' where image_id=3"); con.commit(); con.close()
    try: RA.angleichen(dbp, rec); pruef(False, "fremde Datenbank (Name anders) haette ValueError geben muessen")
    except ValueError: pruef(True, "fremde Datenbank (Name anders) -> ValueError statt stiller Umhaengung")
    ok, t = RA.probe(dbp, sp, os.path.join(d, "probe2")); pruef(not ok, f"probe meldet fremde Datenbank als gescheitert: {t[:80]}")
    # zusatzfotos_lightglue einlesen ruft das Angleichen vor triangulate_points auf (Quelltext-Pruefung: Reihenfolge)
    q = open(os.path.join(T, "zusatzfotos_lightglue.py")).read(); i_a = q.find("colmap_rig_abgleich"); i_t = q.find("pycolmap.triangulate_points(ref")
    pruef(0 < i_a < i_t, "zusatzfotos_lightglue.einlesen gleicht die Datenbank vor triangulate_points an")

    # --- Teil 2: Kettenstufe seiten_luecken scheitert SCHNELL (Vorpruefung) und merkt sich den Fehlschlag mit CODE-STAND -------------------------------
    import json, time, numpy as np, cv2
    root = os.path.join(d, "r"); od = os.path.join(root, "modelle", "xtest"); fd = os.path.join(root, "fotos"); fo = os.path.join(root, "fassade")
    for p in (od, fd, fo): os.makedirs(p)
    os.symlink(T, os.path.join(root, "tools"))      # seiten_luecken nimmt die Werkzeuge aus <wurzel>/tools
    json.dump(dict(fotos_dir="fotos", name="Test", stl="modelle/xtest/m.stl"), open(os.path.join(od, "objekt.json"), "w"))
    import struct      # 24.11.2026: Frueh-Abbruch seiten_luecken.belegbar braucht ein STL mit Dreiecken + eine Referenzkamera (sonst rc 5 VOR dieser Vorpruefung)
    open(os.path.join(od, "m.stl"), "wb").write(b"\0" * 80 + struct.pack("<I", 1) + struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0))
    os.makedirs(os.path.join(od, "messprotokoll")); json.dump(dict(kamera=dict(rvec=[0, 0, 0], t=[0, 0, 5])), open(os.path.join(od, "messprotokoll", "K-ref.json"), "w"))
    json.dump(dict(fassaden=[dict(id="f00", flaeche_m2=80.0, n=[1.0, 0.0], o=[0.0, 0.0], raster=dict(nu=40, nz=30, u0=0.0, z1=3.0, zelle=0.1), polys_uz=[[[0, 0], [4, 0], [4, 3], [0, 3]]], fotos={})]),
              open(os.path.join(fo, "fassaden.json"), "w")); cv2.imwrite(os.path.join(fo, "ortho_f00.png"), np.zeros((30, 40, 3), np.uint8))      # Wand ohne Bilddaten = ungesehen
    for n in [os.path.splitext(i.name)[0] for i in rec.images.values()] + ["neu_a", "neu_b"]: cv2.imwrite(os.path.join(fd, n + ".jpg"), np.full((32, 32, 3), 99, np.uint8))
    # dbp ist jetzt "fremd" (Name von Bild 3 geaendert, s. o.) -> die Vorpruefung muss in Sekunden scheitern
    env = dict(os.environ, SEITEN_LUECKEN_DATEN=os.path.join(root, "daten")); env.pop("SEITEN_NEU", None); Zt = os.path.join(root, "daten", "xtest", "seiten_nachholen")
    arg = [sys.executable, "-I", os.path.join(T, "seiten_luecken.py"), os.path.join(od, "objekt.json"), fo, "--sparse", sp, "--ref-db", dbp, "--holen"]
    def sl(**e):
        t0 = time.time(); r = subprocess.run(arg, capture_output=True, text=True, env=dict(env, **e)); return r.returncode, r.stdout + r.stderr, time.time() - t0
    rc, out, dt = sl(); sk = open(os.path.join(od, "audit", "seiten_luecken_holen.sh")).read().split("\n")
    pruef(rc == 5 and "VORPRUEFUNG GESCHEITERT" in out and "Fehlschlag-Marke" in out and dt < 60, f"fremde Referenz-DB: Nachholen scheitert an der Vorpruefung in {dt:.0f} s mit rc 5 (rc {rc}; {out.strip().splitlines()[-1][:90] if out.strip() else ''})")
    i_p = next((i for i, z in enumerate(sk) if "colmap_rig_abgleich.py probe" in z), 99); i_v = next((i for i, z in enumerate(sk) if "zusatzfotos_registrieren.py vorbereiten" in z), -1)
    pruef(0 < i_p < 6 < i_v and not any(z.startswith("rm -rf") and "/bilder" in z for z in sk[:i_v - 2]), "Skript: Vorpruefung ganz vorn, kein pauschales Loeschen der Zwischenstaende vor den Schritten")
    pruef(subprocess.run(["bash", "-n", os.path.join(od, "audit", "seiten_luecken_holen.sh")]).returncode == 0, "erzeugtes Nachhol-Skript ist gueltiges bash (bash -n)")
    pruef(sum("schritt_noetig " in z for z in sk) >= 9 and any("schritt_noetig einlesen 'zusatzfotos_lightglue.py colmap_rig_abgleich.py'" in z for z in sk), "Skript: jeder Teilschritt mit Zwischenstand, einlesen traegt CODE-STAND")
    fm = [f for f in os.listdir(Zt) if f.startswith("fehlschlag_")] if os.path.isdir(Zt) else []
    F = json.load(open(os.path.join(Zt, fm[0]))) if fm else {}
    pruef(len(fm) == 1 and len(F.get("code_stand", "")) == 12 and "Vorpruefung" in F.get("schritt", ""), f"Fehlschlag-Marke mit CODE-STAND und Schritt: {F.get('schritt')} / {F.get('code_stand')}")
    rc, out, dt = sl()
    pruef(rc == 5 and "bekannter Fehlschlag" in out and "VORPRUEFUNG" not in out and dt < 30, f"zweiter Lauf, gleicher Code: sofort rc 5 ohne Rechnen ({dt:.1f} s)")
    rc, out, dt = sl(SEITEN_NEU="1"); pruef(rc == 5 and "VORPRUEFUNG GESCHEITERT" in out, "SEITEN_NEU=1 erzwingt den neuen Versuch")

    # --- Teil 3: Zwischenstaende je Teilschritt (schritt_helfer): Fehler in Schritt 2 verwirft Schritt 1 nicht; Codeaenderung rechnet nur ab dem betroffenen Schritt ---
    import seiten_luecken as SL
    Z = os.path.join(d, "z"); os.makedirs(os.path.join(Z, "stand")); wz = os.path.join(d, "werkzeug_test.py"); open(wz, "w").write("a = 1\n")
    def lauf(fehler2=False):
        z = ["#!/bin/bash", "set -e"] + SL.schritt_helfer(Z, T) + ["KETTE=anfang"]
        for n_, cw, cmd in (("s1", "", f"echo x >> {Z}/n1"), ("s2", wz, "false" if fehler2 else f"echo x >> {Z}/n2"), ("s3", "", f"echo x >> {Z}/n3")):
            z += [f"if schritt_noetig {n_} '{cw}' 0; then", f"  {cmd}", f"  schritt_fertig {n_}", "fi"]
        p = os.path.join(Z, "s.sh"); open(p, "w").write("\n".join(z) + "\n"); return subprocess.run(["bash", p], capture_output=True, text=True).returncode
    def zahl(n): return len(open(os.path.join(Z, n)).read().split()) if os.path.exists(os.path.join(Z, n)) else 0
    r1 = lauf(True); pruef(r1 != 0 and zahl("n1") == 1 and open(os.path.join(Z, "stand", "aktuell")).read().strip() == "s2", "Fehler in Schritt 2: Skript bricht ab, 'aktuell' nennt s2")
    lauf(); pruef((zahl("n1"), zahl("n2"), zahl("n3")) == (1, 1, 1), "naechster Lauf: Schritt 1 aus Zwischenstand, 2 und 3 gerechnet")
    lauf(); pruef((zahl("n1"), zahl("n2"), zahl("n3")) == (1, 1, 1), "unveraendert: alle Schritte aus Zwischenstand")
    open(wz, "w").write("a = 2\n"); lauf(); pruef((zahl("n1"), zahl("n2"), zahl("n3")) == (1, 2, 2), "Code von Schritt 2 geaendert: nur 2 und 3 neu")

    # --- Teil 3 (23.11.2026, Kette 1122r): VEREINTES Seitenmodell vergibt eine Kamera-ID, die in der DB eine FREMDE Kamera ist ---------------------------------
    # sfm_seiten_modelle.modelle_zusammen gab einer doppelt ausgeglichenen Kamera max(Modell)+1 = 822; in der DB war 822 die 1920er-Kamera eines anderen Videobilds
    # -> probe: "[reconstruction.cc:303] Check failed: existing_camera.width == camera.width (1280 vs. 1920)". Nachbau: Modell haengt Bilder 4-6 (DB: Kamera 2) an Kamera 9;
    # in der DB ist 9 die Kamera eines Bildes 'fremd.png' ausserhalb des Modells (a: andere Breite, b: gleiche Groesse, andere Brennweite = stille Verfaelschung).
    def vereint_nachbau(d3, breite_anders):
        os.makedirs(d3); dbp3, sp3 = aufbau(d3); con = sqlite3.connect(dbp3)                  # aufbau: Bild 2 eigene Kamera 7 -> wieder auf Kamera 1 (hier nur die ID-Kollision)
        con.execute("update images set camera_id=1 where image_id=2"); con.execute("update frames set rig_id=1 where frame_id=2"); con.execute("update frame_data set sensor_id=1 where frame_id=2 and data_id=2")
        m, w, h, p, pf = con.execute("select model, width, height, params, prior_focal_length from cameras where camera_id=2").fetchone()
        pa = np.frombuffer(p, "<f8").copy(); pa[0] *= 1.37
        con.execute("insert into cameras (camera_id, model, width, height, params, prior_focal_length) values (9,?,?,?,?,?)", (m, w * 2 if breite_anders else w, h * 2 if breite_anders else h, pa.tobytes(), pf))
        con.execute("insert into rigs (rig_id, ref_sensor_id, ref_sensor_type) values (9, 9, 0)"); con.execute("insert into frames (frame_id, rig_id) values (20, 9)")
        con.execute("insert into frame_data (frame_id, data_id, sensor_id, sensor_type) values (20, 20, 9, 0)"); con.execute("insert into images (image_id, name, camera_id) values (20, 'fremd.png', 9)")
        con.commit(); con.close()
        Q = pycolmap.Reconstruction(sp3); V = pycolmap.Reconstruction(); kmap = {1: 1, 2: 9}     # Nachbau von modelle_zusammen: Kamera 2 -> neue ID 9
        for c_alt, c_neu in kmap.items():
            q = Q.cameras[c_alt]; V.add_camera_with_trivial_rig(pycolmap.Camera(model=q.model, width=q.width, height=q.height, params=q.params, camera_id=c_neu))
        for i in sorted(Q.reg_image_ids()):
            im = Q.images[i]; xy = np.array([p_.xy for p_ in im.points2D], float).reshape(-1, 2)
            V.add_image_with_trivial_frame(pycolmap.Image(name=im.name, keypoints=xy, camera_id=kmap[im.camera_id], image_id=i), im.cam_from_world())
        for pid in sorted(Q.points3D):
            tr = pycolmap.Track()
            for el in Q.points3D[pid].track.elements: tr.add_element(el.image_id, el.point2D_idx)
            V.add_point3D(Q.points3D[pid].xyz, tr, Q.points3D[pid].color)
        sv = os.path.join(d3, "vereint"); os.makedirs(sv); V.write(sv); return dbp3, sv, pa, (w * 2 if breite_anders else w)
    for fall, anders in (("a andere Breite", True), ("b gleiche Groesse, andere Brennweite", False)):
        d3 = os.path.join(d, "vereint_" + fall[0]); dbp3, sv, pa, w9 = vereint_nachbau(d3, anders); rv = pycolmap.Reconstruction(sv)
        k3 = RA.konflikte(dbp3, rv); pruef(any(x["art"] == "Kamera-ID fremd belegt" and x["name"] == "Kamera 9" for x in k3), f"{fall}: Kamera 9 als fremd belegt erkannt ({[(x['name'], x['art']) for x in k3][:4]})")
        if anders:
            alt = os.path.join(d3, "alt.db"); shutil.copy(dbp3, alt); con = sqlite3.connect(alt)
            for iid in (4, 5, 6): con.execute("update images set camera_id=9 where image_id=?", (iid,)); con.execute("update frames set rig_id=9 where frame_id=?", (iid,)); con.execute("update frame_data set sensor_id=9 where frame_id=? and data_id=?", (iid, iid))
            con.commit(); con.close()                                                        # = altes angleichen (nur Kamera-ID umhaengen)
            try: tri(alt, sv, d3, "t_alt"); pruef(False, "a: altes Angleichen haette scheitern muessen (Nachbau stimmt nicht)")
            except ValueError as e: pruef("width" in str(e), f"a: Nachbau des Kettenfehlers mit altem Angleichen ({str(e)[:80]})")
        ok, t = RA.probe(dbp3, sv, os.path.join(d3, "probe")); pruef(ok, f"{fall}: probe besteht ({t[:100]})")
        kop = os.path.join(d3, "kopie.db"); shutil.copy(dbp3, kop); RA.angleichen(kop, rv); pruef(RA.konflikte(kop, rv) == [], f"{fall}: nach angleichen 0 Konflikte")
        r3 = tri(kop, sv, d3, "t3"); pruef(r3.num_points3D() > 100, f"{fall}: triangulate_points auf der angeglichenen Kopie: {r3.num_points3D()} Punkte")
        con = sqlite3.connect(kop); c_f, = con.execute("select camera_id from images where name='fremd.png'").fetchone()
        w_f, p_f = con.execute("select width, params from cameras where camera_id=?", (c_f,)).fetchone()
        rig_f = con.execute("select f.rig_id, r.ref_sensor_id from frame_data d join frames f on f.frame_id=d.frame_id join rigs r on r.rig_id=f.rig_id where d.data_id=20").fetchone()
        w9n, p9 = con.execute("select width, params from cameras where camera_id=9").fetchone(); con.close()
        pruef(c_f not in (1, 2, 9) and w_f == w9 and np.allclose(np.frombuffer(p_f, "<f8"), pa) and rig_f == (rig_f[0], c_f),
              f"{fall}: fremdes Bild behaelt SEINE Kamera unter neuer ID {c_f} (Breite {w_f}, f {np.frombuffer(p_f, '<f8')[0]:.0f}, eigener Rig {rig_f})")
        pruef(w9n == rv.cameras[9].width and np.allclose(np.frombuffer(p9, "<f8"), rv.cameras[9].params), f"{fall}: Kamera 9 der DB-Kopie traegt die Werte des Modells")
        pruef(dbp3 != kop and sqlite3.connect(dbp3).execute("select camera_id from images where name='fremd.png'").fetchone()[0] == 9, f"{fall}: Quelle unberuehrt (probe arbeitet auf Mini-DB)")
finally:
    shutil.rmtree(d, ignore_errors=True)
print("ERGEBNIS:", "alles bestanden" if not fehler else f"{fehler} Fehler"); sys.exit(1 if fehler else 0)
