"""Punkt 4 der Recherche (Nutzer 20.11. "Sift und FlexGlue vereinigen, weil die Punkte gleich sind"):
vereint.db = SIFT-DB (volle Merkmale) +
  - Paare, die FlexGlue gerechnet und abgewiesen hat (< 15 Inlier): geloescht (Tuersteher)
  - Paare, die FlexGlue bestaetigt hat: Rohzuordnungen SIFT ∪ FlexGlue (FlexGlue-Indizes = erste 6000 SIFT-Punkte, gleiche Nummern), Geometrie geloescht
    -> danach `colmap geometric_verifier` (rechnet die Paare ohne Geometrie neu)
Aufruf: python vereinigen.py <flexglue-db (k6000)> <sift-db> <ziel-db> [paarliste: nur diese Paare]"""
import sqlite3, sys, numpy as np
F_DB, S_DB, Z_DB = sys.argv[1:4]; nur = None
if len(sys.argv) > 4: nur = {frozenset(l.split()[:2]) for l in open(sys.argv[4]) if len(l.split()) >= 2}
F = sqlite3.connect(f"file:{F_DB}?mode=ro", uri=True); S = sqlite3.connect(f"file:{S_DB}?mode=ro", uri=True); Z = sqlite3.connect(Z_DB); S.backup(Z); S.close()
nmF = dict(F.execute("select image_id, name from images")); idZ = {n: i for i, n in Z.execute("select image_id, name from images")}
pid = lambda i, j: min(i, j) * 2147483647 + max(i, j)
def paar(p):
    j = p % 2147483647; i = (p - j) // 2147483647; return i, j
weg = ver = neu = 0; zuw = []
for p, rows in F.execute("select pair_id, rows from two_view_geometries").fetchall():
    i, j = paar(p); a, b = nmF[i], nmF[j]
    if nur is not None and frozenset((a, b)) not in nur: continue
    ia, ib = idZ[a], idZ[b]; q = pid(ia, ib); tausch = (ia > ib) != (i > j)                 # Reihenfolge der Bilder in Z kann anders sein
    if rows < 15:
        Z.execute("delete from two_view_geometries where pair_id = ?", (q,)); Z.execute("delete from matches where pair_id = ?", (q,)); weg += 1; continue
    r = F.execute("select rows, cols, data from matches where pair_id = ?", (p,)).fetchone()
    mf = np.frombuffer(r[2], np.uint32).reshape(r[0], r[1]) if r and r[0] else np.zeros((0, 2), np.uint32)
    if tausch: mf = mf[:, ::-1]
    r = Z.execute("select rows, cols, data from matches where pair_id = ?", (q,)).fetchone()
    ms = np.frombuffer(r[2], np.uint32).reshape(r[0], r[1]) if r and r[0] else np.zeros((0, 2), np.uint32)
    if len(ms) == 0: neu += 1
    c = np.vstack([ms, mf]).astype(np.uint32); u = c[np.sort(np.unique(c[:, 0], return_index=True)[1])]   # je Punkt in Bild 1 ein Partner; bei Streit gewinnt SIFT (steht vorn)
    Z.execute("insert or replace into matches (pair_id, rows, cols, data) values (?, ?, 2, ?)", (q, len(u), u.tobytes())); Z.execute("delete from two_view_geometries where pair_id = ?", (q,)); ver += 1
Z.commit(); Z.close()
print(f"vereint: {ver} Paare (davon {neu} ohne SIFT-Zuordnung), abgewiesen und geloescht: {weg}")
