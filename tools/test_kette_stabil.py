#!/usr/bin/env python3
"""test_kette_stabil.py - feste, schnelle Tests gegen STILLE Fehler der Gesamtkette (17.11.2026; Aufruf aus tools/schnelltest.sh, ~15 s, nur Kleinstdateien).
Zweite Durchsicht 17.11.2026 (Stufenwerkzeuge): Tests ab 'json_sicher' - je Test der nachgestellte Ausloeser aus der Fundliste (Werkzeug lief mit rc 0 ohne Ergebnis, loeschte/ueberschrieb einen guten Stand,
nahm das falsche Bild). Kein Netz, keine SfM, keine Fusion: Fremdprogramme sind durch Attrappen ersetzt (bauen_abnehmen: Attrappen-Werkzeuge in einem Kleinstbaum; Fusion: eingehaengte Funktion).

  /media/oem/scan/venv-seg/bin/python -I tools/test_kette_stabil.py
Jeder Test stellt einen Fall nach, der am 17.11.2026 bei der Durchsicht gefunden wurde (rc 0 trotz leerem Ergebnis, veraltete Ausgabe als frisch gelesen, Verknuepfung ins Leere).
Ausgabe: je Test eine Zeile, am Ende 'KETTE_STABIL: n Fehler'; rc = Zahl der Fehler. Arbeitsordner: eigener Ordner unter /media/oem/scan/tmp (netz_aus_dicht verlangt die Datenplatte), wird am Ende entfernt.
"""
import os, sys, json, time, glob, shutil, subprocess, tempfile
T = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(T); sys.path.insert(0, T)
PY = sys.executable
FEHLER = []


def test(name):
    def deko(fn):
        try: fn(); print(f"    ok    {name}")
        except Exception as e: FEHLER.append(name); print(f"    FEHLER {name}: {type(e).__name__}: {str(e)[:300]}")
    return deko


def werkzeug(*arg, env=None):
    r = subprocess.run([PY, "-W", "ignore", "-I", *arg], capture_output=True, text=True, cwd=ROOT, env=env); return r.returncode, r.stdout + r.stderr


def mini_objekt(S, name="x"):
    """Kleinstobjekt unter S/modelle/<name>: objekt.json, STL (ein Dreieck), leerer Fotoordner, Ausrichtung ohne Kameras."""
    od = os.path.join(S, "modelle", name); os.makedirs(os.path.join(od, "messprotokoll"), exist_ok=True); os.makedirs(os.path.join(S, "fotos"), exist_ok=True)
    open(os.path.join(S, "m.stl"), "w").write("solid a\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 100 0 0\nvertex 0 100 50\nendloop\nendfacet\nendsolid a\n")
    json.dump(dict(name=name, stl="m.stl", fotos_dir="fotos", zentrierung="achse"), open(os.path.join(od, "objekt.json"), "w"))
    au = os.path.join(od, "messprotokoll", f"SFM-AUSRICHTUNG-{name}.json"); json.dump(dict(kameras={}, transformation=dict(s=1.0, rvec=[0, 0, 0], t=[0, 0, 0])), open(au, "w"))
    return od, au


def main():
    import gesamtkette as G, log_warnungen as LW, io, contextlib
    _lauf = G.lauf
    def leise(*x, **k):                                                # die Meldungen von lauf() ("FEHLER: ...") gehoeren hier zum Test, nicht in die Testausgabe
        with contextlib.redirect_stdout(io.StringIO()): return _lauf(*x, **k)
    G.lauf = leise
    S = tempfile.mkdtemp(prefix="kette_stabil_", dir="/media/oem/scan/tmp" if os.path.isdir("/media/oem/scan/tmp") else None)
    try:
        B = dict(schritte=[], _pfad=os.path.join(S, "b.json")); L = os.path.join(S, "l.log")

        @test("frisch(): Datei eines frueheren Laufs gilt nicht als Ausgabe dieser Stufe")
        def _():
            p = os.path.join(S, "alt.json"); open(p, "w").write("{}"); os.utime(p, (time.time() - 3600, time.time() - 3600))
            assert not G.frisch(p, time.time()) and not G.frisch(os.path.join(S, "gibtsnicht"), 0)
            t0 = time.time(); open(p, "w").write("{}"); assert G.frisch(p, t0)

        @test("Platz/Platte: Verknuepfung ins Leere, volle Platte hinter Verknuepfung, Datenplatte nicht eingehaengt")
        def _():
            ln = os.path.join(S, "pipe"); os.symlink(os.path.join(S, "nicht_da", "pipe"), ln)
            assert "Ziel fehlt" in G.platz_fehler([ln]) and G.platz_fehler([S], min_gb=0) == "" and "GB frei" in G.platz_fehler([os.path.join(S, "neu", "tief")], min_gb=1e9)
            assert G.platte_fehler(S) and G.platte_fehler() == ""
            m = os.path.join(S, "lief.txt"); rc, _ = G.lauf(B, "auf_fehlender_platte", ["bash", "-c", f"touch {m}"], L, platz=[ln])
            assert rc == 3 and not B["schritte"][-1]["ok"] and not os.path.exists(m), "Stufe lief trotz fehlender Platte"

        @test("lauf(): vom System beendete Stufe (Signal 9) ist ein benannter Fehler, auch wenn der rc erlaubt waere")
        def _():
            rc, _ = G.lauf(B, "getoetet", ["bash", "-c", "kill -9 $$"], L, ok=(0, -9)); e = B["schritte"][-1]; assert rc == -9 and not e["ok"] and "Signal 9" in e["fehler"]

        @test("log_warnungen: ACHTUNG/ZEITLIMIT/volle Platte werden gesammelt; gekuerztes Log faellt nicht still weg")
        def _():
            p = os.path.join(S, "w.log"); open(p, "w").write("alles gut\nACHTUNG GPU-Fehler nach 3 Paaren\nZEITLIMIT 10 s ueberschritten\nOSError: [Errno 28] No space left on device\n")
            assert len(LW.sammeln([p])) == 3 and len(LW.sammeln([p], ab_zeile={p: 999})) == 3 and len(LW.sammeln([p], ab_zeile={p: 2})) == 2

        @test("kameras_aus_buendel: keine Kamera geschrieben = rc 2; alte Kamera derselben Ausrichtung wird beiseitegelegt")
        def _():
            od, au = mini_objekt(S); alt = os.path.join(od, "messprotokoll", "K-altfoto.json"); hand = os.path.join(od, "messprotokoll", "K-hand.json")
            json.dump(dict(kamera=dict(brennweite_quelle="buendel", quelle="kameras_aus_buendel.py aus modelle/x/messprotokoll/SFM-AUSRICHTUNG-x.json (test)")), open(alt, "w"))
            json.dump(dict(kamera=dict(brennweite_quelle="hand", quelle="Handpicks")), open(hand, "w"))
            for p in (alt, hand): os.utime(p, (time.time() - 3600, time.time() - 3600))
            rc, out = werkzeug("tools/kameras_aus_buendel.py", os.path.join(od, "objekt.json"), "--ausrichtung", au)
            assert rc == 2 and "KEINE Kamera" in out, (rc, out[-300:])
            assert not os.path.exists(alt) and os.path.exists(alt + ".veraltet") and os.path.exists(hand), "veraltete Buendelkamera blieb liegen oder Handkamera wurde angefasst"

        @test("seiten_luecken: 'keine Wand geprueft' und fehlendes Fassadenbild sind rc 2, nicht 'alle gesehen' / 'ungesehen'")
        def _():
            od, _au = mini_objekt(S, "y"); fo = os.path.join(S, "fassade"); sp = os.path.join(S, "sparse"); os.makedirs(fo, exist_ok=True); os.makedirs(sp, exist_ok=True)
            open(os.path.join(sp, "images.bin"), "wb").write(b"\0" * 8); open(os.path.join(S, "fotos", "a.jpg"), "wb").write(b"x")
            wand = lambda m2: dict(id="f00", flaeche_m2=m2, n=[1.0, 0.0], o=[0.0, 0.0], raster=dict(nu=40, nz=30, u0=0.0, z1=3.0, zelle=0.1), polys_uz=[[[0, 0], [4, 0], [4, 3], [0, 3]]], fotos={})
            arg = ["tools/seiten_luecken.py", os.path.join(od, "objekt.json"), fo, "--sparse", sp, "--ref-db", os.path.join(S, "db.db")]
            json.dump(dict(fassaden=[wand(12.0)]), open(os.path.join(fo, "fassaden.json"), "w")); rc, out = werkzeug(*arg); assert rc == 2 and "KEINE Wand geprueft" in out, (rc, out[-300:])
            json.dump(dict(fassaden=[wand(80.0)]), open(os.path.join(fo, "fassaden.json"), "w")); rc, out = werkzeug(*arg); assert rc == 2 and "fehlt/unlesbar" in out, (rc, out[-300:])
            assert not os.path.exists(os.path.join(od, "audit", "seiten_luecken.json")), "Bericht trotz Fehler geschrieben"

        @test("netz_aus_dicht: Netz ausserhalb des Rahmens = rc 4, kein leerer Netzausschnitt")
        def _():
            if not S.startswith("/media/oem/scan/"): raise RuntimeError("Datenplatte fehlt")
            od, _au = mini_objekt(S, "z"); dd = os.path.join(S, "pipe_z", "dicht"); om = os.path.join(S, "pipe_z", "openmvs"); os.makedirs(dd); os.makedirs(om)
            open(os.path.join(om, "mesh.ply"), "w").write("ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nelement face 1\nproperty list uchar int vertex_indices\nend_header\n900 900 0\n901 900 0\n900 901 1\n3 0 1 2\n")
            rc, out = werkzeug("tools/netz_aus_dicht.py", os.path.join(od, "objekt.json"), dd); assert rc == 4 and "ABBRUCH" in out, (rc, out[-300:])
            assert not os.path.exists(os.path.join(om, "mesh_modell_ausschnitt.npz"))

        @test("Kette: Abbruch schreibt ein eigenes Laufergebnis (rc, Grund) in den Bericht")
        def _():
            if G.platte_fehler(): raise RuntimeError(G.platte_fehler())
            ziel = "_schnelltest_kette"; D = "/media/oem/scan/rc-park_daten/_schnelltest_kette"
            assert not os.path.exists(os.path.join(ROOT, "modelle", ziel)) and not os.path.exists(D), "Testordner eines frueheren Laufs liegt noch da: " + D
            try:
                r = subprocess.run(["python3", "-I", "tools/gesamtkette.py", "ober_tvdr", "--ziel", ziel, "--ab", "html", "--bis", "html"], capture_output=True, text=True, cwd=ROOT)
                b = json.load(open(os.path.join(D, "gesamtkette_bericht.json"))); e = b["lauf_ergebnis"]
                assert r.returncode == 2 and e["rc"] == 2 and "fehlt" in e["abbruch"] and e["fehlgeschlagen"] == ["abbruch"] and "ABGEBROCHEN" in r.stdout, (r.returncode, e, r.stdout[-300:], r.stderr[-300:])
            finally: shutil.rmtree("/media/oem/scan/rc-park_daten/_schnelltest_kette", ignore_errors=True)

        # ---------------- zweite Durchsicht 17.11.2026: stille Fehler in den Stufenwerkzeugen ----------------
        import numpy as np, cv2
        bild = lambda q: cv2.imwrite(q, (np.random.default_rng(len(q)).random((48, 64, 3)) * 255).astype(np.uint8))

        @test("json_sicher: NaN/Inf werden null (gueltiges JSON, Meldung), numpy-Zahlen als Schluessel gehen; nan='fehler' laesst die alte Datei stehen")
        def _():
            import json_sicher as J
            q = os.path.join(S, "j.json"); err = io.StringIO()
            with contextlib.redirect_stderr(err): J.schreiben(q, dict(a=float("nan"), b=[np.float32("inf"), 1.5], c={np.int64(3): np.arange(2), np.bool_(True): (1, 2)}))
            d = json.loads(open(q).read(), parse_constant=lambda c_: (_ for _ in ()).throw(ValueError("ungueltiges JSON: " + c_)))
            assert d == dict(a=None, b=[None, 1.5], c={"3": [0, 1], "true": [1, 2]}) and "ACHTUNG json_sicher" in err.getvalue() and "b[0]" in err.getvalue(), (d, err.getvalue())
            try: J.schreiben(q, dict(x=float("nan")), nan="fehler"); raise AssertionError("nan='fehler' warf nicht")
            except ValueError: pass
            assert json.load(open(q))["a"] is None and not [f for f in os.listdir(S) if ".neu" in f]

        @test("fotos_sammeln: leerer/fehlender --eigen-Ordner = rc 2, die Verknuepfungen des Sammelordners bleiben")
        def _():
            e = os.path.join(S, "fs_eigen"); z = os.path.join(S, "fs_ziel"); leer = os.path.join(S, "fs_leer"); os.makedirs(e); os.makedirs(leer); bild(os.path.join(e, "a.JPG"))
            r = subprocess.run(["python3", "-I", "tools/fotos_sammeln.py", z, "--eigen", e], capture_output=True, text=True, cwd=ROOT); assert r.returncode == 0 and os.path.islink(os.path.join(z, "eigen__a.JPG")), r.stdout + r.stderr
            for d_ in (leer, os.path.join(S, "fs_gibtsnicht")):
                r = subprocess.run(["python3", "-I", "tools/fotos_sammeln.py", z, "--eigen", d_], capture_output=True, text=True, cwd=ROOT)
                assert r.returncode == 2 and "UNVERAENDERT" in r.stdout and os.path.islink(os.path.join(z, "eigen__a.JPG")), (r.returncode, r.stdout[-300:])

        @test("Referenzfotos: .JPG zaehlt, im Sammelordner nur eigen__*, fotos_dir_quelle geht vor; ohne Referenz rc 2 (video_suchen, bilder_vorpruefen)")
        def _():
            import video_suchen as VS
            a_ = os.path.join(S, "rf", "a"); q_ = os.path.join(S, "rf", "q"); os.makedirs(a_); os.makedirs(q_); os.makedirs(os.path.join(S, "rf", "leer")); os.makedirs(os.path.join(S, "rf", "modelle", "x"))
            for f in ("eigen__1.JPG", "eigen__2.jpg", "commons__3.jpg", "video__4.PNG", "x.txt"): open(os.path.join(a_, f), "w").write("x")
            open(os.path.join(q_, "IMG.JPEG"), "w").write("x"); R = os.path.join(S, "rf"); nm = lambda o: [os.path.basename(x) for x in VS.referenzfotos(o, R)[0]]
            assert nm(dict(fotos_dir="a")) == ["eigen__1.JPG", "eigen__2.jpg"] and nm(dict(fotos_dir="a", fotos_dir_quelle="q")) == ["IMG.JPEG"] and nm(dict(fotos_dir="q")) == ["IMG.JPEG"] and nm(dict(fotos_dir="fehlt")) == []
            oj = os.path.join(R, "modelle", "x", "objekt.json"); json.dump(dict(name="x", fotos_dir="leer"), open(oj, "w")); vp = os.path.join(R, "vp.json")
            rc, out = werkzeug("tools/video_suchen.py", oj, "--aus", os.path.join(R, "vk")); assert rc == 2 and "kein Objektfoto" in out, (rc, out[-300:])
            rc, out = werkzeug("tools/bilder_vorpruefen.py", oj, a_, "--aus", vp); assert rc == 2 and not os.path.exists(vp), (rc, out[-300:])

        @test("video_frames / commons_harvest: 0 Bilder = rc 2 (nicht 'erledigt')")
        def _():
            if shutil.which("ffmpeg"):
                r = subprocess.run(["python3", "tools/video_frames.py", "--file", os.path.join(S, "gibtsnicht.mp4"), "--out", os.path.join(S, "vf")], capture_output=True, text=True, cwd=ROOT)
                assert r.returncode == 2 and "KEIN Bild" in r.stdout, (r.returncode, r.stdout[-300:], r.stderr[-200:])
            import commons_harvest as CH
            alt_ = (CH.category_files, CH.image_info, sys.argv); CH.category_files = lambda c_, m_, t_: ["File:a.jpg", "File:b.jpg"]; CH.image_info = lambda t_, w_: {x: dict(url=None, license="x") for x in t_}
            try:
                sys.argv = ["x", "--category", "K", "--out", os.path.join(S, "co")]
                with contextlib.redirect_stdout(io.StringIO()): rc = CH.main()
            finally: CH.category_files, CH.image_info, sys.argv = alt_
            assert rc == 2, rc

        @test("bauen_abnehmen: Absturz des Hoehen-Tors (rc 1) und des Sichtblatts = rc 3 mit Meldung, Skript laeuft bis zum Ende")
        def _():
            T_ = os.path.join(S, "ba", "tools"); os.makedirs(T_); os.makedirs(os.path.join(S, "ba", "modelle", "_stabiltest")); shutil.copy(os.path.join(T, "bauen_abnehmen.sh"), T_)
            json.dump(dict(hoehen_tor=True), open(os.path.join(S, "ba", "modelle", "_stabiltest", "objekt.json"), "w"))
            for t_ in ("platz_pruefen", "freiraum_audit", "umriss_tor", "rundum_kanten"): open(os.path.join(T_, t_ + ".py"), "w").write("")
            open(os.path.join(T_, "pruefstand.py"), "w").write('print("ERGEBNIS: alle Pruefungen bestanden")\n')
            for t_, v_ in (("hoehe_gegen_dom1", "STUB_RH"), ("seiten_audit", "STUB_RS")): open(os.path.join(T_, t_ + ".py"), "w").write(f'import os, sys; sys.exit(int(os.environ.get("{v_}", "0")))\n')
            try:
                for rh, rs, soll, text in ((0, 0, 0, "ERGEBNIS: alle"), (1, 0, 3, "HOEHEN-TOR (DOM1) NICHT GEPRUEFT"), (0, 1, 3, "SICHTBLATT FEHLGESCHLAGEN"), (3, 1, 3, "HOEHEN-TOR (DOM1) NICHT BESTANDEN")):
                    r = subprocess.run(["bash", os.path.join(T_, "bauen_abnehmen.sh"), "_stabiltest", "--nur-pruefen"], capture_output=True, text=True, env=dict(os.environ, STUB_RH=str(rh), STUB_RS=str(rs)))
                    assert r.returncode == soll and text in r.stdout, (rh, rs, r.returncode, r.stdout[-300:], r.stderr[-200:])
            finally:
                if os.path.exists("/tmp/rcpark_bau__stabiltest.lock"): os.remove("/tmp/rcpark_bau__stabiltest.lock")

        @test("foto_diff: 0 Modellkanten = rc 2 'NICHT BEURTEILBAR' (nicht '0 % falsch', rc 0)")
        def _():
            kd = os.path.join(ROOT, "modelle", "ober_tvdr", "messprotokoll"); nr = next((f[2:-5] for f in sorted(os.listdir(kd)) if f.startswith("K-eigen__") and f.endswith(".json")), None) if os.path.isdir(kd) else None
            if nr is None or not glob.glob(os.path.join(ROOT, "daten", "schwab_v3", "fotos", nr + ".*")): print("          (uebersprungen: ober_tvdr-Kamera/Foto fehlt)"); return
            rc, out = werkzeug("tools/foto_diff.py", "modelle/ober_tvdr/objekt.json", nr, "--aus", os.path.join(S, "fd"), "--dichte-max", "0.00001")
            e = json.load(open(os.path.join(S, "fd", f"foto_diff_{nr}.json"))); assert rc == 2 and "NICHT BEURTEILBAR" in out and e["modellkanten_px"] == 0 and e["beurteilbar"] is False, (rc, out[-300:])

        @test("Lage-Tore: unter 10 GPS-Fotos ist 'NICHT GEPRUEFT' (geprueft: false); Grundriss-Tor mit 300 Wandpunkten = rc 4, kein '0 % Strasse'")
        def _():
            oq = os.path.join(ROOT, "modelle", "ober_tvdr", "objekt.json"); od = os.path.join(S, "tor", "modelle", "w"); fo = os.path.join(S, "tor", "fo"); os.makedirs(od); os.makedirs(fo); shutil.copy(oq, od)
            au = os.path.join(S, "tor", "au.json"); json.dump(dict(kameras={f"k{i}": dict(standort=[i, 0, 1.6]) for i in range(3)}, transformation={}), open(au, "w"))
            for i in range(3): bild(os.path.join(fo, f"k{i}.jpg"))
            rc, out = werkzeug("tools/lage_gps_pruefen.py", os.path.join(od, "objekt.json"), au, "--fotos", fo); g = json.load(open(os.path.join(od, "audit", "lage_gps.json")))
            assert rc == 0 and "NICHT GEPRUEFT" in out and g["geprueft"] is False and g["ergebnis"].startswith("nicht geprueft"), (rc, out[-300:], g)
            r_ = np.random.default_rng(0); wk = os.path.join(S, "tor", "klein.npy"); np.save(wk, np.c_[r_.uniform(-3, 3, (300, 2)), r_.uniform(2, 8, 300)].astype(np.float32))
            rc, out = werkzeug("tools/wolke_grundriss_pruefen.py", os.path.join(od, "objekt.json"), "--wolke", wk); w_ = json.load(open(os.path.join(od, "audit", "wolke_grundriss.json")))
            assert rc == 4 and "NICHT GEPRUEFT" in out and w_["geprueft"] is False and w_["strasse"]["haufen"] == [], (rc, out[-300:])

        @test("kantenstufe.bild_finden: IMG_1 trifft nicht IMG_10; Endung in beliebiger Schreibweise; <name>_<zusatz> nur eindeutig")
        def _():
            import kantenstufe as KS
            b = os.path.join(S, "ks"); os.makedirs(b)
            for f in ("IMG_10.jpg", "IMG_2.JPEG", "IMG_3.jpg", "IMG_3_2.jpg", "122_commons.jpg", "IMG_4_x.jpg", "IMG_4_y.jpg", "IMG_5.txt"): open(os.path.join(b, f), "w").write("x")
            ist = {n: KS.bild_finden(b, n) for n in ("IMG_1", "IMG_2", "IMG_3", "122", "IMG_4", "IMG_5", "IMG_10")}
            assert ist == {"IMG_1": None, "IMG_2": "IMG_2.JPEG", "IMG_3": "IMG_3.jpg", "122": "122_commons.jpg", "IMG_4": None, "IMG_5": None, "IMG_10": "IMG_10.jpg"}, ist

        @test("foto_auftrag: Fassadenbild nach Kennung (f02), nicht nach Listenplatz - voll belegte Wand ergibt keinen Auftrag")
        def _():
            R = os.path.join(S, "fa"); os.makedirs(os.path.join(R, "modelle", "x", "messprotokoll")); os.makedirs(os.path.join(R, "fotos")); os.makedirs(os.path.join(R, "fas"))
            json.dump(dict(name="x", fotos_dir="fotos", rahmen=dict(mitte_utm=[414525.9, 5316153.75], xhat_utm=[0.0, 1.0], yhat_utm=[-1.0, 0.0])), open(os.path.join(R, "modelle", "x", "objekt.json"), "w"))
            json.dump(dict(fassaden=[dict(id="f02", flaeche_m2=50.0, n=[1.0, 0.0], o=[5.0, 0.0], d=[0.0, 1.0], u=[0.0, 10.0], z=[0.0, 5.0], raster=dict(nu=100, nz=50, u0=0.0, z1=5.0, zelle=0.1), fotos={})]), open(os.path.join(R, "fas", "fassaden.json"), "w"))
            cv2.imwrite(os.path.join(R, "fas", "ortho_f02.png"), np.full((50, 100, 3), 200, np.uint8)); html = os.path.join(R, "auftrag.html")
            r = subprocess.run([PY, "-W", "ignore", "-I", os.path.join(T, "foto_auftrag.py"), "modelle/x/objekt.json", "fas", html], capture_output=True, text=True, cwd=R, env=dict(os.environ, https_proxy="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9"))      # Kartenkacheln: Netz gesperrt -> schematischer Plan
            assert r.returncode == 0 and ": 0 Auftraege" in r.stdout and "fehlt/unlesbar" not in r.stdout, (r.returncode, r.stdout[-300:], r.stderr[-300:])

        @test("sfm_lod2_ausrichten: Ausrichtung+Wolke als ein Stand (Fehler laesst alles stehen, Verknuepfung bleibt); nach der letzten Loesung (rc 5) wird Loesung 0 zurueckgeschrieben")
        def _():
            import sfm_lod2_ausrichten as SA
            assert SA.loesung_index(0, 3, True) == (0, 0) and SA.loesung_index(2, 3, True) == (2, 0) and SA.loesung_index(3, 3, True) == (0, 5) and SA.loesung_index(3, 3, False) == (None, 5) and SA.loesung_index(1, 0, True) == (None, 5)
            od = os.path.join(S, "sa", "modelle", "x"); pl = os.path.join(S, "sa", "platte"); os.makedirs(os.path.join(od, "sfm")); os.makedirs(pl); ziel = os.path.join(pl, "pm.npy"); np.save(ziel, np.zeros((2, 3))); os.symlink(ziel, os.path.join(od, "sfm", "punkte_modell_x.npy"))
            pth = SA.ergebnis_schreiben(od, "-x", "_x", dict(transformation=dict(s=1.0, loesung_nr=0)), np.ones((5, 3), np.float32), np.ones((5, 3), np.uint8))
            assert os.path.islink(os.path.join(od, "sfm", "punkte_modell_x.npy")) and np.load(ziel).shape == (5, 3) and json.load(open(pth))["transformation"]["loesung_nr"] == 0
            try: SA.ergebnis_schreiben(od, "-x", "_x", dict(transformation=dict(s=object(), loesung_nr=1)), np.full((7, 3), 9.0), np.ones((7, 3), np.uint8)); raise AssertionError("kein Fehler")
            except TypeError: pass
            assert np.load(ziel).shape == (5, 3) and json.load(open(pth))["transformation"]["loesung_nr"] == 0 and not [f for d_ in (os.path.join(od, "sfm"), os.path.join(od, "messprotokoll"), pl) for f in os.listdir(d_) if ".neu" in f], "halber Stand"

        @test("wolke_neu_fusionieren: Absturz der Fusion laesst fusion.cfg/fused.ply wie vorher; Bilder ausserhalb der Listen kommen zurueck; abgeschnittene PLY haengt nicht")
        def _():
            import wolke_neu_fusionieren as WN
            od = os.path.join(S, "wnf", "modelle", "x"); D = os.path.join(S, "wnf", "pipe", "dicht"); cfg = os.path.join(D, "stereo", "fusion.cfg")
            for d_ in (os.path.join(od, "audit"), os.path.join(od, "messprotokoll"), os.path.join(od, "sfm"), os.path.join(D, "stereo"), os.path.join(D, "images")): os.makedirs(d_)
            def ply(q, n):
                V = np.zeros(n, np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("red", "u1"), ("green", "u1"), ("blue", "u1")]))
                open(q, "wb").write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n" % n).encode() + V.tobytes())
            open(cfg, "w").write("a.jpg\nb.jpg\nc.jpg\nd.jpg\n"); ply(os.path.join(D, "fused.ply"), 400); json.dump(dict(transformation=dict(s=1.0, rvec=[0, 0, 0], t=[0, 0, 0])), open(os.path.join(od, "messprotokoll", "SFM-AUSRICHTUNG-x.json"), "w"))
            liste = lambda l: json.dump(dict(ausschliessen=l), open(os.path.join(od, "audit", "kamera_plausibel.json"), "w"))
            def kaputt(z, D_, st): open(z, "wb").write(b"halb"); raise RuntimeError("Arbeitsspeicher")
            def lauf_(fus):
                alt_ = (WN.fusionieren, sys.argv); WN.fusionieren = fus; sys.argv = ["x", os.path.join(od, "objekt.json"), os.path.join(S, "wnf", "pipe")]
                try:
                    with contextlib.redirect_stdout(io.StringIO()): return WN.main()
                except RuntimeError: return "absturz"
                finally: WN.fusionieren, sys.argv = alt_
            zust = lambda: (open(cfg).read().split(), WN.ply_punkte(os.path.join(D, "fused.ply")), sorted(f for f in os.listdir(D) if f.startswith("fused")), os.path.exists(cfg + ".laeuft"))
            liste(["b"]); assert lauf_(kaputt) == "absturz" and zust() == (["a.jpg", "b.jpg", "c.jpg", "d.jpg"], 400, ["fused.ply"], False), zust()
            gut = lambda z, D_, st: ply(z, 100 * len(WN.zeilen(cfg)))
            assert lauf_(gut) == 0 and zust() == (["a.jpg", "c.jpg", "d.jpg"], 300, ["fused.ply", "fused_alle.ply"], False) and np.load(os.path.join(od, "sfm", "punkte_modell_x.npy")).shape == (300, 3), zust()
            assert lauf_(gut) == 2, "gleiche Liste muesste rc 2 sein"
            liste([]); assert lauf_(gut) == 0 and zust()[:2] == (["a.jpg", "b.jpg", "c.jpg", "d.jpg"], 400), zust()
            open(os.path.join(S, "wnf", "halb.ply"), "wb").write(b"ply\nformat binary")
            try: WN.ply_lesen(os.path.join(S, "wnf", "halb.ply")); raise AssertionError("kein Fehler")
            except ValueError: pass

        @test("pipeline_objekt: neue/fehlende Bilder gegen die SfM-Datenbank, Staende aelter als das Netz, fused.ply mit 0 Punkten, Beiseitelegen statt Loeschen")
        def _():
            import pipeline_objekt as PO, sqlite3
            D = os.path.join(S, "po", "pipe"); Fo = os.path.join(S, "po", "fotos"); t_ = time.time()
            for d_ in (os.path.join(D, "sfm", "sparse", "0"), os.path.join(D, "sfm", "sparse_dicht"), os.path.join(D, "dicht", "sparse"), Fo): os.makedirs(d_)
            for f in ("a.jpg", "b.JPG", "neu.png", "sammlung.json"): open(os.path.join(Fo, f), "w").write("x")
            c = sqlite3.connect(os.path.join(D, "sfm", "db.db")); c.execute("CREATE TABLE images (name TEXT)"); c.executemany("INSERT INTO images VALUES (?)", [("a.jpg",), ("b.JPG",), ("weg.jpg",)]); c.commit(); c.close()
            def datei(q, alter): open(os.path.join(D, q), "w").write("x"); os.utime(os.path.join(D, q), (t_ - alter, t_ - alter))
            datei("sfm/sparse/0/images.bin", 100); datei("kameras.json", 100); datei("sfm/sparse_dicht/images.bin", 90); datei("dicht/sparse/images.bin", 80)
            fu = os.path.join(D, "dicht", "fused.ply"); open(fu, "wb").write(b"ply\nformat binary_little_endian 1.0\nelement vertex 0\nproperty float x\nend_header\n"); os.utime(fu, (t_ - 50, t_ - 50))
            st = PO.stand_pruefen(D, Fo); assert st["neu"] == ["neu.png"] and st["fehlend"] == ["weg.jpg"] and not st["kameras_alt"] and st["dicht_alt"] == [] and PO.ply_punkte(fu) == 0 and PO.ply_punkte(fu + "x") == 0, st
            datei("sfm/sparse/0/images.bin", 10); st = PO.stand_pruefen(D, Fo); assert st["kameras_alt"] and len(st["dicht_alt"]) == 3, st
            weg = PO.beiseite([os.path.join(D, "dicht"), os.path.join(D, "nichtda")], "T"); assert weg == [os.path.join(D, "dicht.alt_T")] and os.path.exists(os.path.join(D, "dicht.alt_T", "fused.ply")) and not os.path.exists(os.path.join(D, "dicht"))

        @test("fassaden_kette: Absturz eines Teilwerkzeugs = rc 3 (nicht 'kein Ergebnis'), kein einziges Relief = rc 2")
        def _():
            od = os.path.join(S, "fk", "modelle", "x"); os.makedirs(os.path.join(od, "messprotokoll")); json.dump(dict(name="x", stl="m.stl"), open(os.path.join(od, "objekt.json"), "w"))
            kap = os.path.join(S, "fk", "kaputt.npz"); np.savez(kap, v=np.zeros((0, 3))); fern = os.path.join(S, "fk", "fern.npz"); np.savez(fern, V=np.array([[900.0, 900, 0], [901, 900, 0], [900, 901, 1]]), F=np.array([[0, 1, 2]]))
            wand = ["--wand", "w00", "0", "0", "6", "0", "3", "-5", "8"]
            rc, out = werkzeug("tools/fassaden_kette.py", os.path.join(od, "objekt.json"), "--netz", kap, *wand); assert rc == 3 and "abgestuerzt" in out, (rc, out[-400:])
            rc, out = werkzeug("tools/fassaden_kette.py", os.path.join(od, "objekt.json"), "--netz", fern, *wand); assert rc == 2 and "KEIN Relief" in out, (rc, out[-400:])
    finally: shutil.rmtree(S, ignore_errors=True)
    print(f"KETTE_STABIL: {len(FEHLER)} Fehler"); return len(FEHLER)


if __name__ == "__main__":
    sys.exit(main())
