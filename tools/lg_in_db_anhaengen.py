#!/usr/bin/env python3
"""lg_in_db_anhaengen.py <db.db> <lg.npz> <objekt.json> [--max_az 110] [--mitte x y] [--alt_weg_ab 120] - ALIKED+LightGlue-Zuordnungen (tools/lg_match.py) an eine
vorhandene COLMAP-Datenbank ANHAENGEN (SIFT bleibt), aber nur fuer Bildpaare, deren Kamerastandorte um das Objekt hoechstens --max_az Grad auseinanderliegen.

Lehre Schwabentor v3 15.11.2026: die Turmseiten hingen im SfM nur ueber 140 schwache Eckpaare zusammen (45-90 Grad), dazu 12 falsche Nord<->Sued-Paare ->
Sued-Fotogruppe verzerrt (Massstab 0,89, Knauf 5,9 m zu tief). LightGlue findet 4 368 Eckpaare (60-120 Grad, >= 50 Zuordnungen), aber auch 12 780 Paare
GEGENUEBERLIEGENDER Seiten (gleiche Motive: Uhr, Eckquader, Bogen) - die duerfen nicht hinein (Lehre Martinstor, sfm_netz.py).
Azimut je Bild aus den K-Dateien des Objekts (messprotokoll/K-<bild>.json, standort_xyz) um --mitte (Standard: Mitte des STL-Grundrisses aus objekt.json nicht noetig -
bitte angeben). Bilder ohne K-Datei: Paar wird verworfen. Vorhandene (SIFT-)Paare mit Azimut-Unterschied > --alt_weg_ab werden aus matches/two_view_geometries
geloescht. Danach geometrische Verifikation der geaenderten Paare (pycolmap.verify_matches). Die Datenbank wird VERAENDERT - auf einer Kopie arbeiten.
"""
import sys, os, json, glob, math, sqlite3, argparse, numpy as np


def main():
    import pycolmap
    ap = argparse.ArgumentParser(); ap.add_argument("db"); ap.add_argument("npz"); ap.add_argument("objekt"); ap.add_argument("--max_az", type=float, default=110.0)
    ap.add_argument("--mitte", nargs=2, type=float, required=True); ap.add_argument("--alt_weg_ab", type=float, default=120.0); ap.add_argument("--min_matches", type=int, default=20); a = ap.parse_args()
    od = os.path.dirname(os.path.abspath(a.objekt)); az = {}
    for f in glob.glob(os.path.join(od, "messprotokoll", "K-*.json")):
        s = json.load(open(f))["kamera"]["standort_xyz"]; d = math.hypot(s[0] - a.mitte[0], s[1] - a.mitte[1])
        if 4 < d < 400: az[os.path.basename(f)[2:-5]] = math.degrees(math.atan2(s[1] - a.mitte[1], s[0] - a.mitte[0]))
    daz = lambda p, q: abs((az[p] - az[q] + 180) % 360 - 180)
    Z = np.load(a.npz, allow_pickle=True); con = sqlite3.connect(a.db); cur = con.cursor(); ids = {name: iid for iid, name in cur.execute("select image_id, name from images")}; inv = {v: k for k, v in ids.items()}
    typ = cur.execute("select sql from sqlite_master where name='descriptors'").fetchone()[0]; stamm = lambda n: os.path.splitext(n)[0]
    # 1) alte Paare gegenueberliegender Seiten loeschen
    weg = 0
    for (pid,) in cur.execute("select pair_id from two_view_geometries where rows > 0").fetchall():
        i, j = pid // 2147483647, pid % 2147483647; p, q = stamm(inv.get(i, "")), stamm(inv.get(j, ""))
        if p in az and q in az and daz(p, q) > a.alt_weg_ab: cur.execute("delete from two_view_geometries where pair_id=?", (pid,)); cur.execute("delete from matches where pair_id=?", (pid,)); weg += 1
    # 2) ALIKED-Merkmale anhaengen
    namen = [k[3:] for k in Z.files if k.startswith("kp_") and k[3:] in ids]; offset = {}
    for name in namen:
        iid = ids[name]; row = cur.execute("select rows, cols, data from keypoints where image_id=?", (iid,)).fetchone(); n0, cols, data = (row if row else (0, 2, b""))
        alt = np.frombuffer(data, np.float32).reshape(n0, cols) if n0 else np.zeros((0, cols), np.float32); kp = Z["kp_" + name].astype(np.float32); neu = np.zeros((kp.shape[0], cols), np.float32); neu[:, :2] = kp
        if cols >= 6: neu[:, 2] = 1.0; neu[:, 5] = 1.0
        elif cols == 4: neu[:, 2] = 1.0
        allk = np.vstack([alt, neu]); offset[name] = n0
        cur.execute("delete from keypoints where image_id=?", (iid,)); cur.execute("insert into keypoints (image_id, rows, cols, data) values (?,?,?,?)", (iid, allk.shape[0], cols, allk.tobytes()))
        d = cur.execute("select rows, cols, data from descriptors where image_id=?", (iid,)).fetchone(); dalt = np.frombuffer(d[2], np.uint8).reshape(d[0], d[1]) if d and d[0] else np.zeros((0, 128), np.uint8)
        dall = np.vstack([dalt, np.zeros((kp.shape[0], dalt.shape[1] if dalt.shape[0] else 128), np.uint8)]); cur.execute("delete from descriptors where image_id=?", (iid,))
        if "type" in typ: cur.execute("insert into descriptors (image_id, type, rows, cols, data) values (?,?,?,?,?)", (iid, 0, dall.shape[0], dall.shape[1], dall.tobytes()))
        else: cur.execute("insert into descriptors (image_id, rows, cols, data) values (?,?,?,?)", (iid, dall.shape[0], dall.shape[1], dall.tobytes()))
    # 3) Zuordnungen der zulaessigen Paare anhaengen
    paare = []; verw = 0
    for key in Z.files:
        if not key.startswith("m_"): continue
        na, nb = key[2:].split("|")
        if na not in offset or nb not in offset: continue
        p, q = stamm(na), stamm(nb)
        if p not in az or q not in az or daz(p, q) > a.max_az or len(Z[key]) < a.min_matches: verw += 1; continue
        ia, ib = ids[na], ids[nb]; m = Z[key].astype(np.uint32) + np.array([offset[na], offset[nb]], np.uint32)
        if ia > ib: ia, ib = ib, ia; m = m[:, ::-1].copy()
        pid = int(pycolmap.image_pair_to_pair_id(ia, ib)); alt = cur.execute("select rows, data from matches where pair_id=?", (pid,)).fetchone()
        if alt and alt[0]: m = np.vstack([np.frombuffer(alt[1], np.uint32).reshape(alt[0], 2), m])
        cur.execute("delete from matches where pair_id=?", (pid,)); cur.execute("delete from two_view_geometries where pair_id=?", (pid,))
        cur.execute("insert into matches (pair_id, rows, cols, data) values (?,?,?,?)", (pid, m.shape[0], 2, np.ascontiguousarray(m).tobytes())); paare.append(f"{na} {nb}")
    con.commit(); con.close(); pf = a.db + ".lg_paare.txt"; open(pf, "w").write("\n".join(paare) + "\n")
    print(f"alte Paare > {a.alt_weg_ab:.0f} Grad geloescht: {weg}; Bilder mit angehaengten Merkmalen: {len(namen)}; LightGlue-Paare uebernommen: {len(paare)}, verworfen (Azimut/zu wenig/ohne Kamera): {verw}", flush=True)
    pycolmap.set_random_seed(0); pycolmap.verify_matches(a.db, pf)
    con = sqlite3.connect(a.db); n = con.execute("select count(*) from two_view_geometries where rows >= 15").fetchone()[0]; con.close(); print(f"geometrisch bestaetigte Paare gesamt (>= 15 Inlier): {n}")


if __name__ == "__main__":
    main()
