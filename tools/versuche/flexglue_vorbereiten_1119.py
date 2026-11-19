# FlexGlue-Test Martinstor: DB-Kopie ohne Zuordnungen + Paarlisten (quer = Nord-Bild gegen Sued-Bild, die heute verklebten; Kontrolle = innerhalb einer Seite)
import sqlite3, random, pycolmap, shutil, os
Q = "/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db"; Z = "/media/oem/rcdaten/tmp/flexglue"; W = "/media/oem/rcdaten/tmp/mt_seiten"
src = sqlite3.connect(f"file:{Q}?mode=ro", uri=True); dst = sqlite3.connect(Z + "/db.db"); src.backup(dst)
dst.execute("delete from matches"); dst.execute("delete from two_view_geometries"); dst.commit(); dst.execute("vacuum"); dst.close()
A = {i.name for i in pycolmap.Reconstruction(W + "/konsens3s/konsens/0").images.values()}; B = {i.name for i in pycolmap.Reconstruction(W + "/teil1/sparse/0").images.values()}
nm = dict(src.execute("select image_id, name from images").fetchall()); quer, inA, inB = [], [], []
for pid, rows in src.execute("select pair_id, rows from two_view_geometries where rows >= 15"):
    j = pid % 2147483647; i = (pid - j) // 2147483647; a, b = nm[i], nm[j]
    if (a in A and b in B) or (a in B and b in A):
        if not (a in A and a in B) and not (b in A and b in B): quer.append((a, b, rows))
    elif a in A and b in A: inA.append((a, b, rows))
    elif a in B and b in B: inB.append((a, b, rows))
random.seed(0); kA = random.sample(inA, min(1500, len(inA))); kB = random.sample(inB, min(1500, len(inB)))
for n, L in (("quer", quer), ("kontrolle_nord", kA), ("kontrolle_sued", kB)):
    open(f"{Z}/{n}.txt", "w").write("".join(f"{a} {b}\n" for a, b, _ in L)); print(n, len(L), "Paare, SIFT-Inlier Median", sorted(r for *_, r in L)[len(L) // 2] if L else 0)
open(f"{Z}/alle.txt", "w").write("".join(open(f"{Z}/{n}.txt").read() for n in ("quer", "kontrolle_nord", "kontrolle_sued")))
