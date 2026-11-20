import sqlite3, numpy as np
Z = "/media/oem/rcdaten/tmp/flexglue"; c = sqlite3.connect(f"file:{Z}/stich.db?mode=ro", uri=True); nm = dict(c.execute("select image_id, name from images"))
V = np.load("/media/oem/rcdaten/tmp/bildsuche/mt_k40.txt.npy"); s = sqlite3.connect("file:/media/oem/scan/rc-park_daten/martinstor_gk3/pipe/sfm/db.db?mode=ro", uri=True)
namen = [n for (n,) in s.execute("select name from images order by image_id")]; ix = {n: i for i, n in enumerate(namen)}
S = V @ V.T; np.fill_diagonal(S, -1); rang = np.argsort(np.argsort(-S, 1), 1)
gesamt = c.execute("select count(*) from two_view_geometries").fetchone()[0]; neu = []
for pid, rows in c.execute("select pair_id, rows from two_view_geometries where rows >= 15"):
    j = pid % 2147483647; i = (pid - j) // 2147483647; a, b = ix[nm[i]], ix[nm[j]]; neu.append((rows, min(rang[a, b], rang[b, a])))
neu = np.array(neu).reshape(-1, 2)
print(f"STICHPROBE: {gesamt} gerechnet, {len(neu)} NEU bestaetigt ({100*len(neu)/max(1,gesamt):.1f} %), Inlier-Median {np.median(neu[:,0]) if len(neu) else 0:.0f}")
for k in (40, 80, 150, 300): print(f"  davon in Bildsuche top-{k}: {(neu[:,1] < k).sum()} ({100*(neu[:,1] < k).mean() if len(neu) else 0:.0f} %)")
