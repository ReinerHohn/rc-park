#!/usr/bin/env python3
"""test_bruecke_nachmatchen.py - DB-Anhaenge-Logik von tools/bruecke_nachmatchen.py / zusatzfotos_lightglue.lg_anhaengen ohne GPU/torch/pycolmap (22.11.2026).
Winzige synthetische COLMAP-artige sqlite-DB (3 Bilder, SIFT-Merkmale, ein Paar mit SIFT-Matches + two_view_geometry), dazu ALIKED-Merkmale/-Matches als dict.
Erwartet: SIFT-Merkmale bytegleich vorn (Indizes unveraendert), ALIKED dahinter (+0,5 px Pixelmitte), Versatz = alte Anzahl, Beschreiber aufgefuellt,
SIFT-Matches vorn + ALIKED mit Versatz, Paar-Schluessel id1*2147483647+id2 mit id1<id2 (auch bei vertauschter Namensreihenfolge), alte Geometrie geloescht,
fremde Bilder unberuehrt; probe_sift_unveraendert meldet die Kopie als gleich und eine manipulierte als abweichend. Dauer < 1 s."""
import os, sys, sqlite3, shutil
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from zusatzfotos_lightglue import lg_anhaengen, paar_id
import bruecke_nachmatchen as BN

fehler = 0
def pruef(ok, text):
    global fehler
    print(("    ok " if ok else "FEHLER ") + text)
    if not ok: fehler += 1


def db_bauen(p, sift):
    con = sqlite3.connect(p)
    con.execute("create table images (image_id integer primary key, name text unique, camera_id integer)")
    con.execute("create table keypoints (image_id integer primary key, rows integer, cols integer, data blob)")
    con.execute("create table descriptors (image_id integer primary key, type integer not null, rows integer, cols integer, data blob)")
    con.execute("create table matches (pair_id integer primary key, rows integer, cols integer, data blob)")
    con.execute("create table two_view_geometries (pair_id integer primary key, rows integer, cols integer, data blob, config integer)")
    for iid, (n, k) in enumerate(sift.items(), start=1):
        con.execute("insert into images values (?,?,1)", (iid, n)); con.execute("insert into keypoints values (?,?,6,?)", (iid, k.shape[0], k.tobytes()))
        d = np.full((k.shape[0], 128), iid, np.uint8); con.execute("insert into descriptors values (?,0,?,128,?)", (iid, k.shape[0], d.tobytes()))
    m = np.array([[0, 1], [2, 0]], np.uint32)          # Paar a(1)-b(2): SIFT-Matches + Geometrie
    con.execute("insert into matches values (?,?,2,?)", (paar_id(1, 2), 2, m.tobytes())); con.execute("insert into two_view_geometries values (?,?,2,?,2)", (paar_id(1, 2), 2, m.tobytes()))
    con.commit(); con.close()


def main():
    d = __import__("pfade").temp_ordner("test_bruecke_"); rng = np.random.default_rng(0)
    pruef(paar_id(3, 5) == 3 * 2147483647 + 5 == paar_id(5, 3) == 6442450946, "paar_id: kleinere ID zuerst, id1*2147483647+id2 (wie pycolmap: 6442450946)")
    sift = {n: rng.random((k, 6)).astype(np.float32) * 100 for n, k in (("a.jpg", 3), ("b.jpg", 4), ("c.jpg", 2))}
    dbi = os.path.join(d, "ein.db"); db_bauen(dbi, sift); db = os.path.join(d, "db.db"); shutil.copy(dbi, db)
    kp = {"a.jpg": np.array([[10, 20], [30, 40]], np.float32), "b.jpg": np.array([[1, 2], [3, 4], [5, 6]], np.float32)}
    D = {"namen": np.array(["a.jpg", "b.jpg"]), "kp_a.jpg": kp["a.jpg"], "kp_b.jpg": kp["b.jpg"],
         "m_b.jpg|a.jpg": np.array([[0, 1], [2, 0]], np.int32)}       # Namensreihenfolge b|a: Spalten muessen getauscht werden (Bild-ID a=1 < b=2)
    off, pl = lg_anhaengen(db, D)
    pruef(off == {"a.jpg": 3, "b.jpg": 4}, f"Versatz = alte SIFT-Anzahl je Bild: {off}")
    pruef(pl == [("b.jpg", "a.jpg")], f"geschriebene Paare {pl}")
    con = sqlite3.connect(db)
    for iid, n in ((1, "a.jpg"), (2, "b.jpg")):
        r, c, data = con.execute("select rows, cols, data from keypoints where image_id=?", (iid,)).fetchone(); K = np.frombuffer(data, np.float32).reshape(r, c)
        pruef(r == sift[n].shape[0] + kp[n].shape[0] and c == 6, f"{n}: {r} Merkmale = SIFT + ALIKED")
        pruef(K[:sift[n].shape[0]].tobytes() == sift[n].tobytes(), f"{n}: SIFT-Merkmale bytegleich vorn (Indizes unveraendert)")
        pruef(np.allclose(K[sift[n].shape[0]:, :2], kp[n] + 0.5) and np.all(K[sift[n].shape[0]:, 2] == 1) and np.all(K[sift[n].shape[0]:, 5] == 1), f"{n}: ALIKED hinten, +0,5 px, Einheits-Affinform")
        dr, dc, dd = con.execute("select rows, cols, data from descriptors where image_id=?", (iid,)).fetchone(); Dd = np.frombuffer(dd, np.uint8).reshape(dr, dc)
        pruef(dr == r and np.all(Dd[:sift[n].shape[0]] == iid) and np.all(Dd[sift[n].shape[0]:] == 0), f"{n}: Beschreiber SIFT vorn, Nullen hinten")
    r, c, data = con.execute("select rows, cols, data from keypoints where image_id=3").fetchone()
    pruef(r == 2 and data == sift["c.jpg"].tobytes(), "fremdes Bild c unberuehrt")
    r, data = con.execute("select rows, data from matches where pair_id=?", (paar_id(1, 2),)).fetchone(); M = np.frombuffer(data, np.uint32).reshape(r, 2)
    erw = np.array([[0, 1], [2, 0], [3 + 1, 4 + 0], [3 + 0, 4 + 2]], np.uint32)    # SIFT vorn; ALIKED b|a=(0,1),(2,0) -> a,b=(1,0),(0,2) + Versatz (3,4)
    pruef(M.tolist() == erw.tolist(), f"Matches: SIFT vorn, ALIKED getauscht + Versatz: {M.tolist()}")
    pruef(con.execute("select count(*) from two_view_geometries where pair_id=?", (paar_id(1, 2),)).fetchone()[0] == 0, "alte Geometrie des Paares geloescht (wird neu verifiziert)")
    pruef(con.execute("select count(*) from matches").fetchone()[0] == 1, "kein falscher Paar-Schluessel angelegt")
    con.close()
    pruef(BN.probe_sift_unveraendert(dbi, db, ["a.jpg", "b.jpg", "c.jpg"]) == [], "Probe: SIFT-Teil der Kopie gleich")
    con = sqlite3.connect(db); K = np.frombuffer(con.execute("select data from keypoints where image_id=1").fetchone()[0], np.float32).copy(); K[0] += 1
    con.execute("update keypoints set data=? where image_id=1", (K.tobytes(),)); con.commit(); con.close()
    pruef(BN.probe_sift_unveraendert(dbi, db, ["a.jpg", "b.jpg", "c.jpg"]) == ["Merkmale a.jpg"], "Probe: veraendertes SIFT-Merkmal erkannt")
    # Fremdpaar a-c (leere Geometrie) wird vom Verifizierer "neu geprueft", eigenes Paar a-b neu verifiziert: nur a-c zuruecksetzen
    con = sqlite3.connect(dbi); con.execute("insert into two_view_geometries values (?,0,2,NULL,1)", (paar_id(1, 3),)); con.commit(); con.close()
    con = sqlite3.connect(db); con.execute("insert into two_view_geometries values (?,1,2,?,3)", (paar_id(1, 3), np.array([[0, 0]], np.uint32).tobytes()))
    con.execute("insert into two_view_geometries values (?,4,2,?,2)", (paar_id(1, 2), M.tobytes())); con.commit(); con.close()
    n = BN.fremde_geometrien_zuruecksetzen(dbi, db, [paar_id(1, 2)])
    con = sqlite3.connect(db); g13 = con.execute("select rows, config from two_view_geometries where pair_id=?", (paar_id(1, 3),)).fetchone(); g12 = con.execute("select rows from two_view_geometries where pair_id=?", (paar_id(1, 2),)).fetchone(); con.close()
    pruef(n == 1 and g13 == (0, 1) and g12 == (4,), f"Fremdpaar-Geometrie zurueckgesetzt ({n}, a-c {g13}), eigene neu verifizierte bleibt ({g12})")
    pruef(BN.fremde_geometrien_zuruecksetzen(dbi, db, [paar_id(1, 2)]) == 0, "zweites Zuruecksetzen findet nichts mehr")
    st = BN.paar_stand(dbi, ["a.jpg", "b.jpg", "c.jpg"])
    pruef(st[("a.jpg", "b.jpg")] == (2, 2, 2) and st[("a.jpg", "c.jpg")] == (0, 0, 1) and st[("b.jpg", "c.jpg")] == (0, 0, None), f"paar_stand: {st}")
    print("FEHLER gesamt:", fehler); return 1 if fehler else 0


if __name__ == "__main__": sys.exit(main())
