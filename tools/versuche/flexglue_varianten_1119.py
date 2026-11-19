"""Varianten-DBs fuer den Vergleich (Nutzer 19.11.2026 23:20 "vergleichen wir beides"):
  tuersteher.db = SIFT-DB (volle Merkmale), Paare entfernt, die FlexGlue (k6000.db) gerechnet und abgewiesen hat (< 15 Inlier)
  flexglue.db   = k6000.db (FlexGlue-Zuordnungen, 6000 Merkmale je Bild)
Aufruf: python varianten.py <arbeitsordner>"""
import sqlite3, sys, os
Z = sys.argv[1]; SIFT = "/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db"
F = sqlite3.connect(f"file:{Z}/k6000.db?mode=ro", uri=True)
nmF = dict(F.execute("select image_id, name from images")); abgewiesen = set()
for pid, rows in F.execute("select pair_id, rows from two_view_geometries"):
    j = pid % 2147483647; i = (pid - j) // 2147483647
    if rows < 15: abgewiesen.add(frozenset((nmF[i], nmF[j])))
S = sqlite3.connect(f"file:{SIFT}?mode=ro", uri=True); T = sqlite3.connect(f"{Z}/tuersteher.db"); S.backup(T); S.close()
nmT = dict(T.execute("select image_id, name from images")); weg = []
for pid, rows in T.execute("select pair_id, rows from two_view_geometries where rows >= 15").fetchall():
    j = pid % 2147483647; i = (pid - j) // 2147483647
    if frozenset((nmT[i], nmT[j])) in abgewiesen: weg.append((pid,))
T.executemany("delete from two_view_geometries where pair_id = ?", weg); T.executemany("delete from matches where pair_id = ?", weg); T.commit(); T.close()
G = sqlite3.connect(f"{Z}/flexglue.db"); F.backup(G); G.close()
print(f"Tuersteher: {len(weg)} SIFT-Paare entfernt (FlexGlue abgewiesen: {len(abgewiesen)} Paare insgesamt)")
