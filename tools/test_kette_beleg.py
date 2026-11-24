#!/usr/bin/env python3
"""test_kette_beleg.py - Beleg-Helfer gegen 'stille Erfolge' (tools/kette_beleg.py, gesamtkette.beleg/sweep_altstand; Audit modelle/AUDIT_STILLE_ERFOLGE_2026-11-23.md).
Synthetisch, Sekunden, keine echten Daten. Faelle:
(1) pruefen: fehlt / Altdatei (mtime vor Stufenstart) / frisch / frisch aber leer (Mindestinhalt > 0) / seit=None = nur Existenz.
(2) beiseite: nur Altdateien -> .veraltet_<marke>, frische bleiben, nichts geloescht.
(3) db_fehlende_bilder: Bild fehlt in der COLMAP-Datenbank (SiftGPU out of memory) / 0 Schluesselpunkte / Datenbank ohne Tabellen.
(4) gesamtkette.sweep_altstand: Lauf 1122t - fassade_tiefe rc 2 schrieb nichts, vorbauten_f01.json eines frueheren Laufs kommt beiseite, frische Datei bleibt.
(5) gesamtkette.beleg: Verstoss -> Zeile '<name>_beleg' ok False mit Grund, Altstand beiseite; belegt -> keine Zeile.
(6) Quelltext: rc von bauplan_oeffnungen_aussen nicht mehr verworfen; Beleg fuer fenster/kanten/fassaden_kette/befunde; iphone_sfm prueft fehlende SIFT-Bilder."""
import os, sys, json, time, tempfile, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kette_beleg as KB

F = 0
def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text); F += 0 if ok else 1


def schreib(p, inhalt, alter_s=0):
    os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(inhalt, open(p, "w"))
    if alter_s: t_ = time.time() - alter_s; os.utime(p, (t_, t_))


with tempfile.TemporaryDirectory(prefix="test_kette_beleg_") as T:
    alt, neu, leer = (os.path.join(T, n) for n in ("alt.json", "neu.json", "leer.json"))
    schreib(alt, dict(kandidaten=[1]), alter_s=3600); seit = time.time(); schreib(neu, dict(kandidaten=[1, 2])); schreib(leer, dict(kandidaten=[]))
    f_ = KB.pruefen([os.path.join(T, "fehlt.json")], seit); pruef(len(f_) == 1 and "fehlt" in f_[0], f"(1) fehlende Ausgabe = Verstoss: {f_}")
    f_ = KB.pruefen([alt], seit); pruef(len(f_) == 1 and "FRUEHEREN" in f_[0], f"(1) Altdatei = Verstoss: {f_}")
    pruef(KB.pruefen([neu], seit) == [], "(1) frische Datei belegt")
    f_ = KB.pruefen([leer], seit, inhalt={leer: KB.mindestens_eins("kandidaten")}); pruef(len(f_) == 1 and "leer" in f_[0], f"(1) frisch aber leer = Verstoss: {f_}")
    pruef(KB.pruefen([neu], seit, inhalt={neu: KB.mindestens_eins("kandidaten")}) == [], "(1) frisch mit Inhalt belegt")
    pruef(KB.pruefen([alt], None) == [], "(1) seit=None (Erzeuger lief nicht in diesem Lauf) = nur Existenz")
    weg = KB.beiseite([alt, neu, os.path.join(T, "fehlt.json")], seit, marke="t")
    pruef(weg == [alt + ".veraltet_t"] and os.path.exists(alt + ".veraltet_t") and not os.path.exists(alt) and os.path.exists(neu), f"(2) nur Altdatei beiseite, nichts geloescht: {weg}")
    pruef(KB.beiseite([neu], None) == [], "(2) seit=None legt nichts beiseite")

    db = os.path.join(T, "db.db"); c = sqlite3.connect(db)
    c.execute("create table images (image_id integer, name text)"); c.execute("create table keypoints (image_id integer, rows integer)")
    c.executemany("insert into images values (?,?)", [(1, "a.jpg"), (2, "b.jpg")]); c.executemany("insert into keypoints values (?,?)", [(1, 500), (2, 0)]); c.commit(); c.close()
    pruef(KB.db_fehlende_bilder(db, ["a.jpg", "b.jpg", "c.jpg"]) == ["b.jpg", "c.jpg"], "(3) fehlendes Bild und Bild ohne Schluesselpunkte gefunden")
    db0 = os.path.join(T, "leer.db"); sqlite3.connect(db0).close()
    pruef(KB.db_fehlende_bilder(db0, ["a.jpg"]) == ["a.jpg"], "(3) Datenbank ohne Tabellen -> alle fehlen")

    import gesamtkette as G
    fo = os.path.join(T, "fassade"); B = dict(schritte=[], _pfad=os.path.join(T, "bericht.json"))
    schreib(os.path.join(fo, "vorbauten_f01.json"), dict(belastbar=True, kandidaten=[dict(u0=0)]), alter_s=7200)
    open(os.path.join(fo, "tiefe_f01.npz"), "wb").write(b"x"); t_ = time.time() - 7200; os.utime(os.path.join(fo, "tiefe_f01.npz"), (t_, t_))
    t0 = time.time(); schreib(os.path.join(fo, "vorbauten_f02.json"), dict(belastbar=False))
    w1 = G.sweep_altstand(B, "bauplan_sweep_f01", fo, 1, t0); w2 = G.sweep_altstand(B, "bauplan_sweep_f02", fo, 2, t0)
    pruef(len(w1) == 2 and not os.path.exists(os.path.join(fo, "vorbauten_f01.json")) and w2 == [] and os.path.exists(os.path.join(fo, "vorbauten_f02.json")),
          f"(4) 1122t: Sweep f01 ohne Schreiben -> Altstand beiseite, frischer f02 bleibt: {[os.path.basename(x) for x in w1]}")
    pruef(any(s["stufe"] == "bauplan_sweep_f01_altstand" and s["ok"] is True for s in B["schritte"]), "(4) Schutz steht im Bericht (Stufe bleibt in Ordnung)")

    B = dict(schritte=[], _pfad=os.path.join(T, "bericht2.json")); fa = os.path.join(T, "audit", "fenster_auto.json"); schreib(fa, {"f00": {}}, alter_s=3600)
    ok = G.beleg(B, "fenster", [fa], time.time(), altstand_beiseite=True, folge="Test")
    z = [s for s in B["schritte"] if s["stufe"] == "fenster_beleg"]
    pruef(not ok and z and z[0]["ok"] is False and "FRUEHEREN" in z[0]["fehler"] and z[0]["beiseite"] and not os.path.exists(fa), f"(5) Altstand -> fenster_beleg rot, beiseite: {z[0] if z else None}")
    schreib(fa, {"f00": {}}); n0 = len(B["schritte"])
    pruef(G.beleg(B, "fenster", [fa], time.time() - 5) and len(B["schritte"]) == n0, "(5) frisch -> belegt, keine Zeile")

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "gesamtkette.py")).read()
pruef('"--tiefe_ordner", os.path.join(bp_, "tiefe")], log)[0] == 0: pass' not in src, "(6) rc von bauplan_oeffnungen_aussen wird nicht mehr verworfen")
pruef(all(f'beleg(B, "{n}"' in src for n in ("fenster", "kanten", "fassaden_kette", "bauplan_oeffnungen_aussen", "bauplan_ebenen")) and "sweep_altstand(B, f\"vorbauten_f" in src and 'KB_frisch(os.path.join(Z, "audit", "befunde.json")' in src,
      "(6) Beleg fuer fenster/kanten/fassaden_kette/oeffnungen_aussen/ebenen, Sweep-Altstand in bauplan+seiten, befunde.json frisch")
isrc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "iphone_sfm.py")).read()
ssrc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sift_einstellung.py")).read()      # 24.11.2026: Nachholer zentral in sift_einstellung.extrahieren_mit_tor
pruef("SE.extrahieren_mit_tor(" in isrc and "db_fehlende_bilder(db, alle)" in ssrc and "device=pycolmap.Device.cpu" in ssrc, "(6) iphone_sfm prueft nach GPU-SIFT fehlende Bilder und holt sie auf der CPU nach (sift_einstellung)")
print("ERGEBNIS test_kette_beleg:", "alle bestanden" if F == 0 else f"{F} FEHLER"); sys.exit(1 if F else 0)
