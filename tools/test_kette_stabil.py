#!/usr/bin/env python3
"""test_kette_stabil.py - feste, schnelle Tests gegen STILLE Fehler der Gesamtkette (17.11.2026; Aufruf aus tools/schnelltest.sh, ~5 s, nur Kleinstdateien).

  /media/oem/scan/venv-seg/bin/python -I tools/test_kette_stabil.py
Jeder Test stellt einen Fall nach, der am 17.11.2026 bei der Durchsicht gefunden wurde (rc 0 trotz leerem Ergebnis, veraltete Ausgabe als frisch gelesen, Verknuepfung ins Leere).
Ausgabe: je Test eine Zeile, am Ende 'KETTE_STABIL: n Fehler'; rc = Zahl der Fehler. Arbeitsordner: eigener Ordner unter /media/oem/scan/tmp (netz_aus_dicht verlangt die Datenplatte), wird am Ende entfernt.
"""
import os, sys, json, time, shutil, subprocess, tempfile
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
    finally: shutil.rmtree(S, ignore_errors=True)
    print(f"KETTE_STABIL: {len(FEHLER)} Fehler"); return len(FEHLER)


if __name__ == "__main__":
    sys.exit(main())
