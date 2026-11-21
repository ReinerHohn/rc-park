#!/usr/bin/env python3
"""db_masken_filter.py <db.db> <masken-ordner> --aus <kopie.db> [--min 15]

Bestaetigte Bildpaare von VORDERGRUND-Zuordnungen befreien (21.11.2026, Martinstor): eine Person in Selbstaufnahme-Videobildern stand auf BEIDEN Torseiten; ihre Merkmale
verbanden Sued- und Nordseite ("echt" im Paar-Pruefer, weil dasselbe Motiv) -> Seitenerkennung trennte nicht, der Mapper klebte die Seiten aufeinander.
Masken aus tools/handy_masken.py / video_masken.py (<masken>/<bildname>.png, 0 = ignorieren; beliebig tief in Unterordnern). Ohne neue Merkmalsextraktion:
  - je Bild die Merkmale, die in der Maske liegen (Maske auf Bildgroesse skaliert);
  - je Paar in two_view_geometries die Inlier-Zuordnungen streichen, an denen ein maskiertes Merkmal haengt; bleiben < --min, wird das Paar geloescht (auch in matches).
Die Merkmale selbst bleiben (IDs stabil). Ausgabe: Zahlen je Schritt + <kopie>.masken.json (Paare vorher/nachher, geloeschte Paare, Bilder mit > 30 % maskierten Merkmalen).
Fuer NEUE Laeufe gehoert die Maske schon in die Merkmalsextraktion (ImageReader.mask_path) - dieses Werkzeug rettet vorhandene Datenbanken.
"""
import sys, os, json, argparse, sqlite3, shutil
import numpy as np

MAXID = 2147483647


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("db"); ap.add_argument("masken"); ap.add_argument("--aus", required=True); ap.add_argument("--min", type=int, default=15); a = ap.parse_args()
    import cv2
    M = {}
    for w, _, fs in os.walk(a.masken):
        for f in fs:
            if f.endswith(".png"): M[f[:-4]] = os.path.join(w, f)
    shutil.copyfile(a.db, a.aus); c = sqlite3.connect(a.aus); B = {i: n for i, n in c.execute("select image_id, name from images")}; weg = {}; viel = []
    for i, n in B.items():
        k = os.path.basename(n); mp = M.get(k) or M.get(os.path.splitext(k)[0])
        if not mp: continue
        r = c.execute("select rows, cols, data from keypoints where image_id=?", (i,)).fetchone()
        if not r or not r[0]: continue
        K = np.frombuffer(r[2], np.float32).reshape(r[0], r[1])[:, :2]; m = cv2.imread(mp, 0); kam = c.execute("select width, height from cameras where camera_id=(select camera_id from images where image_id=?)", (i,)).fetchone()
        x = np.clip((K[:, 0] * m.shape[1] / kam[0]).astype(int), 0, m.shape[1] - 1); y = np.clip((K[:, 1] * m.shape[0] / kam[1]).astype(int), 0, m.shape[0] - 1); w_ = m[y, x] == 0
        if w_.any(): weg[i] = w_
        if w_.mean() > 0.3: viel.append((k, round(float(w_.mean()), 2)))
    print(f"{len(B)} Bilder, {len(M)} Masken, {len(weg)} Bilder mit maskierten Merkmalen, {len(viel)} mit > 30 %", flush=True)
    n_v = n_g = n_l = z_v = z_n = 0; neu = []; loe = []
    for pid, rows, cols, data in c.execute("select pair_id, rows, cols, data from two_view_geometries where rows > 0").fetchall():
        i2 = pid % MAXID; i1 = (pid - i2) // MAXID; n_v += 1; z_v += rows
        if i1 not in weg and i2 not in weg: z_n += rows; continue
        Z = np.frombuffer(data, np.uint32).reshape(rows, cols); ok = np.ones(rows, bool)
        if i1 in weg: ok &= ~weg[i1][np.clip(Z[:, 0], 0, len(weg[i1]) - 1)]
        if i2 in weg: ok &= ~weg[i2][np.clip(Z[:, 1], 0, len(weg[i2]) - 1)]
        if ok.all(): z_n += rows; continue
        n_g += 1
        if ok.sum() < a.min: loe.append(pid); n_l += 1
        else: neu.append((int(ok.sum()), Z[ok].tobytes(), pid)); z_n += int(ok.sum())
    c.executemany("update two_view_geometries set rows=?, data=? where pair_id=?", neu); c.executemany("delete from two_view_geometries where pair_id=?", [(p,) for p in loe]); c.executemany("delete from matches where pair_id=?", [(p,) for p in loe]); c.commit(); c.close()
    print(f"Paare {n_v}: {n_g} gekuerzt, {n_l} geloescht (< {a.min} Zuordnungen ohne Vordergrund); Zuordnungen {z_v} -> {z_n} -> {a.aus}")
    json.dump(dict(db=a.db, paare=n_v, gekuerzt=n_g, geloescht=n_l, zuordnungen_vorher=z_v, zuordnungen_nachher=z_n, viel_maskiert=sorted(viel, key=lambda t: -t[1])[:200]), open(a.aus + ".masken.json", "w"), indent=1); return 0


if __name__ == "__main__": sys.exit(main())
