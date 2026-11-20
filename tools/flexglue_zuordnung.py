#!/usr/bin/env python3
"""flexglue_zuordnung.py --db <sift-db> --bilder <ordner> --aus <ziel-db> [--stufe2] [--max-merkmale 6000] [--paare-max N]

FlexGlue-Zuordnung als Kettenstufe (Messung 20.11.2026, modelle/LOGBUCH_KETTENTEST_2026-11-19.md): NACH SIFT-Merkmalen + SIFT-Zuordnung, VOR dem Mapper.
Martinstor: globaler Mapper registriert damit stabil +30 % (Nord) / +40 % (Sued) Bilder bei gleicher Lage und gleicher Seitentrennung; Schwabentor +6 %.
Ablauf:
 1. DB-Kopie, Merkmale je Bild auf die ersten --max-merkmale gekuerzt (FlexGlue braucht sonst > 8 GB VRAM; Nummern bleiben gleich), Zuordnungen geleert.
 2. Paarliste = von SIFT bestaetigte Paare (>= 15 Inlier) [--stufe2: zusaetzlich die von SIFT abgewiesenen; Martinstor: 24 % davon bestaetigt FlexGlue, ~20 h].
 3. colmap matches_importer --FeatureMatching.type FLEXGLUE (COLMAP-Testbau colmap-test/prefix + CUDA-12-Bibliotheken fuer ONNX), 1 Arbeiter, 1 Inferenz,
    Merkmalspuffer 16 (sonst Speicherabbruch); bis 6 Anlaeufe, gerechnete Paare werden uebersprungen (Wiederaufnahme).
Ergebnis: <aus> mit FlexGlue-Zuordnungen und -Geometrie, direkt fuer view_graph_calibrator + global_mapper. ~0,17-0,20 s je Paar, ~3,3 GB VRAM (JOB_GPU_MB=4000).
Lizenz: FlexGlue-Gewichte MIT + DINOv3-Lizenz (Verkauf erlaubt, modelle/LIZENZ_WERKZEUGE.md). rc 0 = ok, rc 3 = FlexGlue lief nicht durch."""
import os, sys, sqlite3, argparse, subprocess, time
import numpy as np

TEST = "/media/oem/rcdaten/colmap-test"; COLMAP = TEST + "/prefix/bin/colmap"; M = 2147483647
CUDA12 = ":".join(f"{TEST}/cuda12-onnx/pip/nvidia/{x}/lib" for x in ("cublas", "cuda_runtime", "cudnn", "cufft"))


def umgebung():
    env = dict(os.environ); zeile = [l for l in open(TEST + "/prefix/colmap-umgebung.sh") if l.startswith("export LD_LIBRARY_PATH=")][0]
    basis = zeile.split("=", 1)[1].strip().strip('"').replace("${LD_LIBRARY_PATH}", "").replace("${LD_LIBRARY_PATH:-}", "").rstrip(":")
    env["LD_LIBRARY_PATH"] = CUDA12 + ":" + basis + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else ""); return env


def vorbereiten(q, z, n_max, stufe2):
    s = sqlite3.connect(f"file:{q}?mode=ro", uri=True); d = sqlite3.connect(z); s.backup(d); gek = 0
    for tab, typ in (("keypoints", np.float32), ("descriptors", np.uint8)):
        for iid, r, c, b in d.execute(f"select image_id, rows, cols, data from {tab}").fetchall():
            if r > n_max: d.execute(f"update {tab} set rows=?, data=? where image_id=?", (n_max, np.frombuffer(b, typ).reshape(r, c)[:n_max].tobytes(), iid)); gek += tab == "keypoints"
    nm = dict(d.execute("select image_id, name from images")); paare = []
    for pid, rows in s.execute("select pair_id, rows from two_view_geometries"):
        if rows >= 15 or stufe2: j = pid % M; i = (pid - j) // M; paare.append((nm[i], nm[j]))
    d.execute("delete from matches"); d.execute("delete from two_view_geometries"); d.commit(); d.close()
    return paare, gek


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--aus", required=True)
    ap.add_argument("--stufe2", action="store_true"); ap.add_argument("--max-merkmale", type=int, default=6000); ap.add_argument("--paare-max", type=int, help="nur die ersten N Paare (Funktionstest)")
    a = ap.parse_args(argv); t0 = time.time()
    if not os.path.exists(a.aus):
        paare, gek = vorbereiten(a.db, a.aus, a.max_merkmale, a.stufe2); print(f"FLEXGLUE vorbereitet: {len(paare)} Paare, {gek} Bilder auf {a.max_merkmale} Merkmale gekuerzt", flush=True)
        open(a.aus + ".paare.txt", "w").write("".join(f"{x} {y}\n" for x, y in paare[:a.paare_max]))
    else: print("FLEXGLUE: Ziel-DB vorhanden -> Wiederaufnahme", flush=True)
    cmd = [COLMAP, "matches_importer", "--database_path", a.aus, "--match_list_path", a.aus + ".paare.txt", "--match_type", "pairs", "--FeatureMatching.type", "FLEXGLUE",
           "--FlexGlueMatching.image_path", a.bilder, "--FlexGlueMatching.min_covisibility", "0.5", "--FlexGlueMatching.num_workers_per_gpu", "1",
           "--FlexGlueMatching.num_inferences_per_gpu", "1", "--FlexGlueMatching.feature_cache_size", "16"]
    env = umgebung(); rc = 1
    for anlauf in range(1, 7):
        rc = subprocess.run(cmd, env=env, stdout=open(a.aus + ".log", "a"), stderr=subprocess.STDOUT).returncode
        if rc == 0: break
        print(f"FLEXGLUE Anlauf {anlauf} abgebrochen (rc {rc}, meist Grafikspeicher) - weiter, gerechnete Paare bleiben", flush=True)
    c = sqlite3.connect(f"file:{a.aus}?mode=ro", uri=True); n, ok = c.execute("select count(*), coalesce(sum(rows >= 15), 0) from two_view_geometries").fetchone()
    soll = sum(1 for _ in open(a.aus + ".paare.txt"))
    print(f"FLEXGLUE: {n} von {soll} Paaren gerechnet, {ok} bestaetigt, {round(time.time() - t0)} s, rc {rc}", flush=True)
    return 0 if rc == 0 and n >= soll else 3


if __name__ == "__main__": sys.exit(main())
