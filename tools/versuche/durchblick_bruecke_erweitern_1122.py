#!/usr/bin/env python3
"""durchblick_bruecke_erweitern_1122.py - VERSUCH (22.11.2026): Gruppenverbindungen, die die Stufe Durchblick mit >= 1 starkem Paar (>= 200 Inlier) bestaetigt hat,
bekommen ihre schwaecheren Paare zurueck (>= --min Inlier, sonst gleiche Pruefung: Zellen, statischer Anteil, GPS-Veto). Grund: am Schwabentor haengt die Ecke (Gruppe 27)
nur ueber 3 Paare / ein Teil-0-Bild am Rest -> globaler Mapper knickt Teil 1 um 25 Grad; die Ursprungs-DB hat 15 Paare dorthin.
python -I ... <db_ursprung> <db_durch_mapper> <seiten_durch.json> <seiten.json der Kette> <fotos> <objekt.json> <db_aus> [--min 30]"""
import os, sys, json, shutil, sqlite3, argparse, numpy as np
T = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, T)
import seiten_erkennen as SE
MAXID = 2147483647


def main(argv=None):
    ap = argparse.ArgumentParser(); [ap.add_argument(k) for k in ("db", "db_durch", "seiten_durch", "seiten", "bilder", "objekt", "aus")]; ap.add_argument("--min", type=int, default=30)
    a = ap.parse_args(argv)
    sd = json.load(open(a.seiten_durch)); g = json.load(open(a.seiten))["gemeinschaft"]
    bruecken = {tuple(sorted((d["ga"], d["gb"]))) for d in sd.get("durchblick", []) if d.get("urteil") == "durchblick"}
    print("bestaetigte Gruppenverbindungen:", sorted(bruecken))
    src = sqlite3.connect(f"file:{a.db}?immutable=1", uri=True); nm = {i: n for i, n in src.execute("select image_id, name from images")}
    wh = {i: (w, h) for i, w, h in src.execute("select i.image_id, c.width, c.height from images i join cameras c on c.camera_id = i.camera_id")}
    shutil.copy(a.db_durch, a.aus); dst = sqlite3.connect(a.aus)
    da = {r[0] for r in dst.execute("select pair_id from two_view_geometries")}
    from paarvorwahl import gps_aus_exif; from netz_fotos_holen import geo; mitte = geo(json.load(open(a.objekt))); az = {}
    def w(n):
        if n not in az:
            q = gps_aus_exif(os.path.join(a.bilder, n)); az[n] = None
            if q is not None:
                ww, d = SE.richtung(mitte, q); az[n] = ww if 15 <= d <= 300 else None
        return az[n]
    def kp(i):
        rr, cc, dd = src.execute("select rows, cols, data from keypoints where image_id=?", (i,)).fetchone(); return np.frombuffer(dd, np.float32).reshape(rr, cc)[:, :2]
    neu = []
    for row in src.execute("select * from two_view_geometries where rows >= ?", (a.min,)).fetchall():
        pid, rows = row[0], row[1]; x, y = pid // MAXID, pid % MAXID
        if pid in da or tuple(sorted((g.get(nm[x]), g.get(nm[y])))) not in bruecken: continue
        ij = np.frombuffer(row[3], np.uint32).reshape(rows, row[2]); m = SE.paar_staerke(kp(x)[ij[:, 0]], kp(y)[ij[:, 1]], wh[x], wh[y])
        wa, wb = w(nm[x]), w(nm[y]); dw = abs((wa - wb + 180) % 360 - 180) if wa is not None and wb is not None else None
        u, grund = SE.durchblick_ok(m, dw, min_inlier=a.min)
        print(f"  {nm[x][-14:]} G{g.get(nm[x])} | {nm[y][-14:]} G{g.get(nm[y])}: n {m['n']} n_eff {m['n_eff']} Zellen {m['zellen0']}/{m['zellen1']} GPS {dw} -> {u} {grund}")
        if u == "durchblick": neu.append(row)
    cols = [r[1] for r in dst.execute("pragma table_info(two_view_geometries)")]
    dst.executemany(f"insert into two_view_geometries ({','.join(cols)}) values ({','.join('?' * len(cols))})", neu)
    mcols = [r[1] for r in dst.execute("pragma table_info(matches)")]
    for r in neu:
        mm = src.execute("select * from matches where pair_id=?", (r[0],)).fetchone()
        if mm and not dst.execute("select 1 from matches where pair_id=?", (r[0],)).fetchone():
            dst.execute(f"insert into matches ({','.join(mcols)}) values ({','.join('?' * len(mcols))})", mm)
    dst.commit(); print(f"{len(neu)} Paare zurueck -> {a.aus}")


if __name__ == "__main__": main()
