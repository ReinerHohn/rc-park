"""FlexGlue-Vorbereitung (wie Martinstor k6000.db): DB-Kopie, Merkmale je Bild auf die ersten 6000 gekuerzt (VRAM 8 GB), Zuordnungen geleert; Paarlisten stufe1 (SIFT-bestaetigt) / stufe2 (Rest)."""
import sqlite3, sys, numpy as np
Q, Z, D = sys.argv[1], sys.argv[2], sys.argv[3]; N = 6000
s = sqlite3.connect(f"file:{Q}?mode=ro", uri=True); d = sqlite3.connect(Z); s.backup(d)
gek = 0
for iid, r, c, b in d.execute("select image_id, rows, cols, data from keypoints").fetchall():
    if r > N: d.execute("update keypoints set rows=?, data=? where image_id=?", (N, np.frombuffer(b, np.float32).reshape(r, c)[:N].tobytes(), iid)); gek += 1
for iid, r, c, b in d.execute("select image_id, rows, cols, data from descriptors").fetchall():
    if r > N: d.execute("update descriptors set rows=?, data=? where image_id=?", (N, np.frombuffer(b, np.uint8).reshape(r, c)[:N].tobytes(), iid))
nm = dict(d.execute("select image_id, name from images")); p1, p2 = [], []
for pid, rows in s.execute("select pair_id, rows from two_view_geometries"):
    j = pid % 2147483647; i = (pid - j) // 2147483647; (p1 if rows >= 15 else p2).append(f"{nm[i]} {nm[j]}")
d.execute("delete from matches"); d.execute("delete from two_view_geometries"); d.commit()
open(f"{D}/stufe1.txt", "w").write("\n".join(p1) + "\n"); open(f"{D}/stufe2.txt", "w").write("\n".join(p2) + "\n")
print(f"gekuerzt {gek} Bilder; stufe1 {len(p1)}, stufe2 {len(p2)}")
