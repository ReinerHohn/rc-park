#!/usr/bin/env python3
"""test_nachhol_zwischenspeicher.py - Ergebnis-Zwischenspeicher des Nachholens nach Eingabe-Hash (24.11.2026, Kette schwabentor-null-1122w: seiten_luecken 48 min,
davon SIFT+Abgleich 18 min - db.db am Skriptende geloescht -, kamera_verfeinern 267 Kameras ~17 min, Download 5 min trotz vollstaendigem Bestand).
NUR CPU, Sekunden, keine GPU (Ersatz-pycolmap, Ersatz-ALIKED/LightGlue/Renderer aus tools/test_kamera_verfeinern_stapel.py).
Prueft:
  (1) tools/nachhol_zwischenspeicher.py: Ablegen/Holen bitgleich, fehlender Eintrag -> nichts veraendert, nur die N juengsten Eintraege bleiben, "0" = aus;
  (2) zusatzfotos_registrieren.merkmale: zweiter Lauf mit gleichen Eingaben rechnet NICHT (SIFT/Abgleich 0 Aufrufe) und liefert db.db + merkmale.json BITGLEICH;
      geaendertes Bild (Inhalt), SIFT-Einstellung (RCPARK_SIFT_MAX), Paarliste (Referenzmodell), Referenz-DB -> neu gerechnet; Notweg (GPU klein/CPU) wird nicht abgelegt;
  (3) kamera_verfeinern --liste: Zwischenspeicher an == aus (K-Dateien bitgleich), zweiter Lauf ganz aus dem Speicher (Renderer wird nicht aufgerufen) und bitgleich;
      geaenderte Referenzkamera -> neu gerechnet, Ergebnis == Rechnung ohne Speicher; Foto-Index == glob (Namen mit Punkten, fehlende);
  (4) seiten_luecken.download_zeile: frische Abfrage uebersprungen, RCPARK_DOWNLOAD_FRISCH_H=0 laedt, Drosselung -> kurze Frist, Fehler -> kein Abbruch, keine Marke.
Aufruf: /media/oem/scan/venv-seg/bin/python -W ignore -I tests/test_nachhol_zwischenspeicher.py   Exit 0 = alles bestanden."""
import os, sys, json, types, shutil, sqlite3, subprocess, argparse, io, contextlib, glob
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); T = os.path.join(R, "tools"); sys.path.insert(0, T)
from pfade import temp_ordner

fehler = 0
D = temp_ordner("nachhol_zs_")
os.environ["RCPARK_NACHHOL_CACHE"] = os.path.join(D, "speicher")


def pruef(ok, text):
    global fehler
    print(("ok   " if ok else "FEHLER ") + text, flush=True); fehler += 0 if ok else 1


def lies(p): return open(p, "rb").read()


# ---------- (1) Modul ----------
def teil1():
    import nachhol_zwischenspeicher as NZ
    q = os.path.join(D, "q1"); os.makedirs(q); a_ = os.path.join(q, "a.bin"); open(a_, "wb").write(os.urandom(5000)); b_ = os.path.join(q, "b.json"); open(b_, "w").write('{"x": 1}')
    pruef(NZ.ablegen("probe", "k1", {"a.bin": a_, "b.json": b_}, melden=None), "Modul: Ablegen gelingt")
    z = os.path.join(D, "z1"); os.makedirs(z)
    ok = NZ.holen("probe", "k1", {"a.bin": os.path.join(z, "a"), "b.json": os.path.join(z, "b")}, melden=None)
    pruef(ok and lies(os.path.join(z, "a")) == lies(a_) and lies(os.path.join(z, "b")) == lies(b_), "Modul: Holen liefert bitgleiche Dateien")
    pruef(not NZ.holen("probe", "fehlt", {"a.bin": os.path.join(z, "neu")}, melden=None) and not os.path.exists(os.path.join(z, "neu")), "Modul: fehlender Eintrag -> False, nichts geschrieben")
    os.environ["RCPARK_NACHHOL_CACHE_N"] = "2"
    import time
    shutil.rmtree(os.path.join(NZ.wurzel(), "probe", "k1"))
    for i in range(4): NZ.ablegen("probe", f"r{i}", {"a.bin": a_}, behalten=None, melden=None); os.utime(os.path.join(NZ.wurzel(), "probe", f"r{i}"), (time.time() - 100 + i, time.time() - 100 + i))
    NZ.ablegen("probe", "r4", {"a.bin": a_}, melden=None); del os.environ["RCPARK_NACHHOL_CACHE_N"]
    pruef(sorted(os.listdir(os.path.join(NZ.wurzel(), "probe"))) == ["r3", "r4"], f"Modul: nur die 2 juengsten Eintraege bleiben ({sorted(os.listdir(os.path.join(NZ.wurzel(), 'probe')))})")
    alt = os.environ["RCPARK_NACHHOL_CACHE"]; os.environ["RCPARK_NACHHOL_CACHE"] = "0"
    pruef(not NZ.an() and not NZ.ablegen("probe", "x", {"a.bin": a_}, melden=None) and not NZ.holen("probe", "r4", {"a.bin": os.path.join(z, "c")}, melden=None), "Modul: RCPARK_NACHHOL_CACHE=0 -> aus")
    os.environ["RCPARK_NACHHOL_CACHE"] = alt
    pruef(NZ.json_ablegen("kv", "ab12", dict(rc=0)) and NZ.json_holen("kv", "ab12") == dict(rc=0) and NZ.json_holen("kv", "cd34") is None, "Modul: kleine JSON-Eintraege")


# ---------- (2) merkmale ----------
class _SiftOpt:
    def __init__(self): self.first_octave = -1; self.max_num_features = 8192


class _EO:
    def __init__(self): self.sift = _SiftOpt(); self.use_gpu = True; self.max_image_size = 3200


def ersatz_pycolmap(reg):
    pc = types.ModuleType("pycolmap"); pc.__version__ = "ersatz-1"; pc.set_random_seed = lambda s: None; pc.FeatureExtractionOptions = _EO
    class Rec:
        def __init__(self, p):
            self.images = {i: types.SimpleNamespace(name=n, has_pose=True) for i, n in enumerate(json.load(open(os.path.join(p, "reg.json"))))}
            self.cameras = {1: types.SimpleNamespace(model="CameraModelId.SIMPLE_RADIAL")}
    pc.Reconstruction = Rec; return pc


ZAEHLER = dict(sift=0, match=0); NOTWEG = [False]


def ersatz_sift(pycolmap, db, bilddir, bilder, names, f0):
    ZAEHLER["sift"] += 1; con = sqlite3.connect(db); n0 = con.execute("select coalesce(max(image_id),0) from images").fetchone()[0]
    for i, n in enumerate(names):
        con.execute("insert into images values (?,?)", (n0 + 1 + i, n)); con.execute("insert into keypoints values (?,?)", (n0 + 1 + i, sum(open(os.path.join(bilddir, n), "rb").read()) % 997 + 1))
    con.commit(); con.close(); return dict(gpu_klein=(["x"] if NOTWEG[0] else []), cpu=[], fehlend=[])


def ersatz_match(db, paare_txt, pycolmap=None, saat=False):
    ZAEHLER["match"] += 1; con = sqlite3.connect(db); z = [l_.split() for l_ in open(paare_txt) if l_.strip()]
    con.executemany("insert into two_view_geometries values (?,?)", [(i, (len(a_) * 7 + len(b_)) % 50) for i, (a_, b_) in enumerate(z)]); con.commit()
    v = con.execute("select count(*) from two_view_geometries where rows>0").fetchone()[0]; con.close(); return v


def teil2():
    import zusatzfotos_registrieren as ZR
    ZR.sift_sicher = ersatz_sift; ZR.sift_paare_matchen = ersatz_match
    w = os.path.join(D, "m"); aus = os.path.join(w, "aus"); sp = os.path.join(w, "sparse"); os.makedirs(os.path.join(aus, "bilder")); os.makedirs(sp)
    refdb = os.path.join(w, "ref.db"); con = sqlite3.connect(refdb)
    for t_ in ("images (image_id INTEGER PRIMARY KEY, name TEXT)", "keypoints (image_id INTEGER, rows INTEGER)", "two_view_geometries (pair_id INTEGER, rows INTEGER)",
               "cameras (camera_id INTEGER, model INTEGER, width INTEGER, height INTEGER, params BLOB, prior_focal_length INTEGER)"):
        con.execute("create table " + t_)
    con.execute("insert into images values (1, 'ref_a.jpg')"); con.execute("insert into images values (2, 'ref_b.jpg')"); con.commit(); con.close()
    json.dump(["ref_a.jpg", "ref_b.jpg"], open(os.path.join(sp, "reg.json"), "w"))
    V = dict(bilder={}); import random; rnd = random.Random(3)
    for n in ("n1.jpg", "n2.jpg", "n3.jpg"):
        open(os.path.join(aus, "bilder", n), "wb").write(bytes(rnd.randrange(256) for _ in range(3000))); V["bilder"][n] = dict(bild=[640, 480])
    json.dump(V, open(os.path.join(aus, "vorbereitet.json"), "w"))
    sys.modules["pycolmap"] = ersatz_pycolmap(None)
    a = argparse.Namespace(ref_db=refdb, sparse=sp, aus=aus, f_px=1444.0); db = os.path.join(aus, "db.db"); mj = os.path.join(aus, "merkmale.json")
    def lauf():
        for p_ in (db, mj):
            if os.path.exists(p_): os.remove(p_)
        z0 = dict(ZAEHLER); buf = io.StringIO()
        with contextlib.redirect_stdout(buf): ZR.merkmale(a)
        return ZAEHLER["sift"] - z0["sift"], lies(db), lies(mj), buf.getvalue()
    s1, db1, mj1, _ = lauf()
    pruef(s1 == 1 and json.loads(mj1)["verifizierte_paare_gesamt"] > 0, "merkmale: erster Lauf rechnet (SIFT 1 Aufruf)")
    s2, db2, mj2, o2 = lauf()
    pruef(s2 == 0 and db2 == db1 and mj2 == mj1 and "Zwischenspeicher" in o2, "merkmale: zweiter Lauf, gleiche Eingaben -> KEINE Rechnung, db.db + merkmale.json bitgleich")
    os.environ["RCPARK_NACHHOL_CACHE"] = "0"; s0, db0, mj0, _ = lauf(); os.environ["RCPARK_NACHHOL_CACHE"] = os.path.join(D, "speicher")
    pruef(s0 == 1 and db0 == db1 and mj0 == mj1, "merkmale: ohne Zwischenspeicher gerechnet == aus dem Zwischenspeicher (gleiche Eingaben -> gleiche Ausgaben)")
    b = os.path.join(aus, "bilder", "n2.jpg"); alt = lies(b); open(b, "wb").write(alt[:-1] + bytes([(alt[-1] + 1) % 256]))
    s3, db3, _, _ = lauf(); open(b, "wb").write(alt)
    pruef(s3 == 1 and db3 != db1, "merkmale: ein Byte eines Bildes anders -> neu gerechnet")
    s3b, db3b, _, _ = lauf(); pruef(s3b == 0 and db3b == db1, "merkmale: Bild zurueck -> wieder der alte Eintrag (bitgleich)")
    os.environ["RCPARK_SIFT_MAX"] = "1600"; s4, _, _, _ = lauf(); del os.environ["RCPARK_SIFT_MAX"]
    pruef(s4 == 1, "merkmale: andere SIFT-Einstellung (RCPARK_SIFT_MAX) -> neu gerechnet")
    json.dump(["ref_a.jpg"], open(os.path.join(sp, "reg.json"), "w")); s5, _, _, _ = lauf(); json.dump(["ref_a.jpg", "ref_b.jpg"], open(os.path.join(sp, "reg.json"), "w"))
    pruef(s5 == 1, "merkmale: andere Paarliste (Referenzmodell mit weniger Bildern) -> neu gerechnet")
    con = sqlite3.connect(refdb); con.execute("insert into images values (3, 'ref_c.jpg')"); con.commit(); con.close(); s6, _, _, _ = lauf()
    pruef(s6 == 1, "merkmale: andere Referenz-Datenbank (Inhalt) -> neu gerechnet")
    NOTWEG[0] = True; os.environ["RCPARK_SIFT_MAX"] = "1234"; s7, _, _, _ = lauf(); s8, _, _, _ = lauf(); NOTWEG[0] = False; del os.environ["RCPARK_SIFT_MAX"]
    pruef(s7 == 1 and s8 == 1, "merkmale: Notweg (GPU klein/CPU nachgeholt) wird NICHT abgelegt - der naechste Lauf rechnet regulaer")
    sys.modules.pop("pycolmap", None)


# ---------- (3) kamera_verfeinern ----------
def teil3():
    import test_kamera_verfeinern_stapel as TS
    KV = TS.module_einsetzen(); neu = ["commons_n0", "commons_n1", "commons_n2"]
    d = os.path.join(D, "kv"); os.makedirs(d); od, mp = TS.szene(d); start = os.path.join(d, "start"); shutil.copytree(mp, start)
    O, FJ = os.path.join(od, "objekt.json"), os.path.join(od, "fassaden.json"); L = os.path.join(d, "liste.txt"); open(L, "w").write("\n".join(neu))
    def neu_start(): shutil.rmtree(mp); shutil.copytree(start, mp)
    def stapel():
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): KV.main([O, FJ, "-", "--liste", L, "--schreiben"])
        return TS.k_lesen(mp), buf.getvalue()
    sp_ = os.environ["RCPARK_NACHHOL_CACHE"]
    os.environ["RCPARK_NACHHOL_CACHE"] = "0"; ref, o_ref = stapel()
    os.environ["RCPARK_NACHHOL_CACHE"] = sp_; neu_start(); k1, o1 = stapel()
    pruef(k1 == ref and sum(1 for n in neu if json.loads(ref[f"K-{n}.json"]).get("kamera", {}).get("vertrauen")) == 3,
          "kamera_verfeinern: Zwischenspeicher an (leer) == aus, K-Dateien bitgleich, 3 Kameras nachgezogen")
    echt = KV.rk.dreiecke_rastern; aufrufe = [0]
    def zaehl(*x, **y): aufrufe[0] += 1; return echt(*x, **y)
    KV.rk.dreiecke_rastern = zaehl; neu_start(); k2, o2 = stapel()
    pruef(k2 == ref and aufrufe[0] == 0 and "3 von 3 Kameras" in o2, f"kamera_verfeinern: zweiter Lauf ganz aus dem Speicher (Renderer {aufrufe[0]} Aufrufe), K-Dateien bitgleich")
    pruef([z_ for z_ in o2.splitlines() if not z_.startswith("ZWISCHENSPEICHER")] == [z_ for z_ in o_ref.splitlines()], "kamera_verfeinern: Ausgabe aus dem Speicher == gerechnete Ausgabe (Zeile fuer Zeile)")
    neu_start(); kp = os.path.join(mp, "K-eigen__r2.json"); k_ = json.load(open(kp)); k_["kamera"]["f_px"] = k_["kamera"]["f_px"] * 1.01; json.dump(k_, open(kp, "w"))
    shutil.rmtree(start); shutil.copytree(mp, start)
    aufrufe[0] = 0; k3, _ = stapel(); n3 = aufrufe[0]
    os.environ["RCPARK_NACHHOL_CACHE"] = "0"; neu_start(); k3_ref, _ = stapel(); os.environ["RCPARK_NACHHOL_CACHE"] = sp_
    pruef(n3 > 0 and k3 == k3_ref and k3 != ref, f"kamera_verfeinern: geaenderte Referenzkamera -> neu gerechnet ({n3} Renderaufrufe), Ergebnis == Rechnung ohne Speicher")
    KV.rk.dreiecke_rastern = echt
    fd = os.path.join(d, "fx"); os.makedirs(fd)
    for n in ("a.jpg", "a.b.jpg", "a.png", "b.c.d.jpeg", "c", ".versteckt.jpg"): open(os.path.join(fd, n), "w").write("x")
    os.symlink(os.path.join(fd, "fehlt.jpg"), os.path.join(fd, "tot.jpg"))
    FX = KV.foto_index(fd); namen = ["a", "a.b", "b", "b.c", "b.c.d", "c", "tot", "fehlt", ".versteckt", "x"]
    gl = {n: (glob.glob(os.path.join(fd, n + ".*")) or [None])[0] for n in namen}; ix = {n: FX.pfad(n) for n in namen}
    pruef(ix == gl, f"Foto-Index == glob.glob(<fd>/<n>.*)[0] ({ {n: (os.path.basename(v) if v else None) for n, v in ix.items()} })")
    s0 = FX.signatur(); open(os.path.join(fd, "neu.jpg"), "w").write("y"); os.utime(fd, ns=(os.stat(fd).st_atime_ns, os.stat(fd).st_mtime_ns + 10 ** 9))
    pruef(FX.pfad("neu") == os.path.join(fd, "neu.jpg") and FX.signatur() != s0, "Foto-Index: neue Datei im Ordner -> Index und Signatur neu")


# ---------- (4) Download-Frische ----------
def teil4():
    import seiten_luecken as SL
    Z = os.path.join(D, "dl"); os.makedirs(Z); zf = os.path.join(Z, "zaehler")
    def sk(cmd, umg=None, fehler_="echo FEHLERZWEIG $RC"):
        txt = "set -e\n" + "\n".join(SL.download_zeile(Z, "probe", cmd, fehler_)) + "\necho ENDE\n"
        r = subprocess.run(["bash", "-c", txt], capture_output=True, text=True, env=dict(os.environ, **(umg or {}))); return r
    cmd = f"echo geladen >> {zf}; echo 'fertig'"
    r1 = sk(cmd); r2 = sk(cmd); n = len(open(zf).read().split())
    pruef(r1.returncode == 0 and r2.returncode == 0 and n == 1 and "uebersprungen" in r2.stdout and "ENDE" in r2.stdout, f"Download: frische Abfrage (< 24 h) uebersprungen ({n} Aufruf)")
    r3 = sk(cmd, {"RCPARK_DOWNLOAD_FRISCH_H": "0"}); pruef(len(open(zf).read().split()) == 2 and "fertig" in r3.stdout, "Download: RCPARK_DOWNLOAD_FRISCH_H=0 -> immer laden")
    cmd2 = f"echo geladen >> {zf}; echo 'HTTP 429 von upload.wikimedia.org'"
    sk(cmd2); r5 = sk(cmd2); r6 = sk(cmd2, {"RCPARK_DOWNLOAD_DROSSEL_H": "0"})
    pruef(len(open(zf).read().split()) == 4 and "uebersprungen" in r5.stdout and os.path.exists(glob.glob(os.path.join(Z, "download_stand", "probe_*.drossel"))[0]),
          "Download: Drosselung -> Marke .drossel mit eigener (kurzer) Frist; Frist 0 -> neu versucht")
    cmd3 = f"echo geladen >> {zf}; exit 3"
    r7 = sk(cmd3); r8 = sk(cmd3)
    pruef(r7.returncode == 0 and "FEHLERZWEIG 3" in r7.stdout and "ENDE" in r7.stdout and len(open(zf).read().split()) == 6, "Download: rc != 0 -> Fehlerzweig, kein Abbruch (set -e), KEINE Marke (naechster Lauf versucht neu)")


def main():
    teil1(); teil2(); teil3(); teil4()
    print("ALLE BESTANDEN" if not fehler else f"{fehler} FEHLER"); return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
