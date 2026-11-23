"""Eckmodell mit Eckliste + neuen Suedseiten-Bildern (DB-Kopie neu/db.db), Varianten SIFT + Teilkameras ueber EK.zwischenmodell (CPU, kein Nachmatchen)."""
import sys, os, json, shutil, sqlite3, numpy as np, pycolmap
sys.path.insert(0, "/home/oem/git/rc-park/.claude/worktrees/agent-a38678dacd05d031c/tools")
import seiten_eck_koppeln as EK
EK.NACHMATCHEN = False
A = "/media/oem/rcdaten/tmp/bruecke_sued_agent"; N = A + "/neu_usb"; aus = sys.argv[1]; mit_neu = sys.argv[2] == "1"
R = {t: pycolmap.Reconstruction(f"{A}/teil{t}") for t in (0, 1)}; at = {}
for t in R: EK.NAMEN[t] = {im.name for im in R[t].images.values() if im.has_pose}; at[t] = EK.ausdehnung([p.xyz for p in R[t].points3D.values()])
tv = {n: t for t in (1, 0) for n in EK.NAMEN[t]}
ks = EK.kandidaten(json.load(open(A + "/seiten.json")), tv, N + "/db.db"); k = ks[0]
neu = [x.strip() for x in open(N + "/neu.txt") if x.strip()]
c = sqlite3.connect(f"file:{N}/db.db?mode=ro", uri=True); idn = {n: i for i, n in c.execute("select image_id, name from images")}
reg = set()
for pid, r in c.execute("select pair_id, rows from two_view_geometries where rows >= 30"):
    a, b = idn and (pid // EK.MAXID, pid % EK.MAXID); reg |= {a, b}
inv = {i: n for n, i in idn.items()}; gut = [n for n in neu if idn.get(n) in reg]
print("neue Bilder", len(neu), "mit >= 30 Inlier-Paar", len(gut))
if mit_neu: k = dict(k, bilder=sorted(set(k["bilder"]) | set(gut)))
os.makedirs(aus, exist_ok=True); dba = EK.arbeits_db(N + "/db.db", aus)
try: z = EK.zwischenmodell(k, 0, dba, N + "/mix", aus, 2, R, at)
finally:
    for x in (dba, dba + "-wal", dba + "-shm"):
        if os.path.exists(x): os.remove(x)
z.pop("_gut", None); json.dump(z, open(aus + "/z.json", "w"), indent=1, default=str)
v = z.get("varianten", {}); print("gewaehlt", v.get("gewaehlt"), "bilder", z.get("bilder"))
for n in ("sift", "teilkameras"):
    vv = v.get(n) or {}; print(n, "s", vv.get("schwelle"), vv.get("teilkameras"), (vv.get("bruecke_duenn") or {}).get("grund"))
    for t, kk in (vv.get("kopplungen") or {}).items(): print("   T", t, kk.get("anteil"), kk.get("rest_rel"), kk.get("massstab_haelften_rel"), kk.get("kameras_rel"), kk.get("hebel"), kk.get("bilder"), kk.get("grund"))
print("sens", z.get("sensitivitaet")); print("wdh", (z.get("wiederholbarkeit") or {}).get("gekoppelt"), (z.get("wiederholbarkeit") or {}).get("max"))
