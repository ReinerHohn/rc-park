#!/usr/bin/env python3
"""global_mapper_lauf.py --db <db> --bilder <ordner> --ziel <ausgabe> --fotos <fotoordner> --label NAME [--protokoll datei.jsonl]
   [--ohne-kalib] [--kalib-opt "--max_calibration_error 2 ..."] [--mapper-opt "--GlobalMapper.image_list_path x ..."] [--seed N]
   [--svc [--svc-opt "..."]] [--nachregistrieren [--reg-opt "..."]]
Ein Versuch globaler Mapper: Kopie der DB nach <ziel>/db_kalib.db -> optional single_view_calibrator (AnyCalib, Brennweite je Bild, GPU) -> view_graph_calibrator
-> colmap global_mapper -> tools/mapper_bewerten.py (Kennzahlen, Protokollzeile) -> optional Stufe 2 (--nachregistrieren: image_registrator + point_triangulator
+ bundle_adjuster in <ziel>_reg). Zeiten je Stufe werden gemessen. Logs: <ziel>/svc.log, kalib.log, global.log.
Binary: COLMAP 4.3.dev (CUDA) wie tools/iphone_sfm.py. Python: /media/oem/scan/venv-colmap/bin/python -I. Lange Laeufe nur ueber tools/job_start.sh."""
import sys, os, time, json, shlex, subprocess, argparse

COLMAP_BIN = "/media/oem/scan/colmap-build/prefix/bin/colmap"
# ONNX-Runtime-CUDA-Provider (single_view_calibrator/AnyCalib) ist gegen CUDA 12 gebaut (libcudart.so.12, libcublas.so.12): die liegen nur im Ollama-Paket;
# cuDNN 9 aus venv-seg. Ohne diese Pfade: "OrtSessionOptionsAppendExecutionProvider_Cuda: Failed to load shared library" (19.11.2026).
ENV = dict(os.environ, LD_LIBRARY_PATH=":".join(["/media/oem/scan/colmap-build/prefix/lib", "/usr/local/lib/ollama/cuda_v12", "/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cudnn/lib",
                                                 "/media/oem/scan/cuda-toolkit-combo/lib64", "/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib",
                                                 "/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib", "/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib"]))
T = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--ziel", required=True); ap.add_argument("--fotos", required=True)
    ap.add_argument("--label", required=True); ap.add_argument("--protokoll", default=""); ap.add_argument("--ohne-kalib", action="store_true"); ap.add_argument("--kalib-opt", default="")
    ap.add_argument("--mapper-opt", default=""); ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--svc", action="store_true", help="vorher single_view_calibrator (AnyCalib, GPU): Brennweiten-Prior fuer JEDES Bild, je Kamera Median")
    ap.add_argument("--svc-opt", default=""); ap.add_argument("--svc-als-start", action="store_true", help="AnyCalib-Brennweite nur als Startwert (Quelle GUESS), Kalibrator optimiert weiter")
    ap.add_argument("--nachregistrieren", action="store_true", help="Stufe 2: restliche Bilder per image_registrator + point_triangulator + bundle_adjuster (GPU) in Modell 0 einhaengen")
    ap.add_argument("--reg-opt", default=""); a = ap.parse_args()
    os.makedirs(a.ziel, exist_ok=True); t0 = time.time(); zeiten = {}; befehl = []
    if not a.ohne_kalib or a.svc:
        # Lehre 19.11. 00:50: der Kalibrator schreibt Brennweiten (source VIEW_GRAPH) und Zweibild-Geometrien IN die DB; ein zweiter Lauf auf derselben Datei
        # kalibriert nichts mehr (Prior gilt als fest) und arbeitet auf gefilterten Paaren (13134 statt 26880). Darum immer eigene Kopie je Versuch.
        import shutil; dbk = os.path.join(a.ziel, "db_kalib.db"); shutil.copyfile(a.db, dbk); a.db = dbk
    if a.svc:
        cmd = [COLMAP_BIN, "single_view_calibrator", "--database_path", a.db, "--image_path", a.bilder] + shlex.split(a.svc_opt); befehl.append(" ".join(cmd[1:]))
        r = subprocess.run(cmd, env=ENV, stdout=open(os.path.join(a.ziel, "svc.log"), "w"), stderr=subprocess.STDOUT); zeiten["svc_s"] = round(time.time() - t0)
        if r.returncode != 0: print("single_view_calibrator rc", r.returncode, "-> svc.log"); sys.exit(2)
        if a.svc_als_start:   # Lehre S3/S4 (Schwabentor 02:20): AnyCalib als FESTER Prior schaltet den view_graph_calibrator ab (alle Kameras 'haben Prior') -> GPS-Tor 29-30 % statt 11 %.
            import sqlite3; c = sqlite3.connect(a.db); sp = [r_[1] for r_ in c.execute("PRAGMA table_info(cameras)")]
            if "source" in sp:   # COLMAP 4.3: cameras hat je Kamera EINE ZEILE JE QUELLE (PRIMARY KEY camera_id, source); AnyCalib legt source=4 (SINGLE_VIEW) daneben.
                n = c.execute("UPDATE cameras SET params=(SELECT s.params FROM cameras s WHERE s.camera_id=cameras.camera_id AND s.source=4), model=(SELECT s.model FROM cameras s WHERE s.camera_id=cameras.camera_id AND s.source=4) "
                              "WHERE source=2 AND EXISTS (SELECT 1 FROM cameras s WHERE s.camera_id=cameras.camera_id AND s.source=4)").rowcount
                c.execute("DELETE FROM cameras WHERE source=4")   # Startwert in die GUESS-Zeile uebernommen, Prior-Zeile weg -> Kalibrator optimiert weiter
            else: n = c.execute("UPDATE cameras SET prior_focal_length=0").rowcount
            c.commit(); c.close(); print("AnyCalib nur als Startwert:", n, "Kameras (GUESS)", flush=True)
    if not a.ohne_kalib:
        tk = time.time(); cmd = [COLMAP_BIN, "view_graph_calibrator", "--database_path", a.db] + shlex.split(a.kalib_opt); befehl.append(" ".join(cmd[1:]))
        r = subprocess.run(cmd, env=ENV, stdout=open(os.path.join(a.ziel, "kalib.log"), "w"), stderr=subprocess.STDOUT); zeiten["kalib_s"] = round(time.time() - tk)
        if r.returncode != 0: print("Kalibrator rc", r.returncode, "-> kalib.log"); sys.exit(2)
    t1 = time.time()
    cmd = [COLMAP_BIN, "global_mapper", "--database_path", a.db, "--image_path", a.bilder, "--output_path", a.ziel] + shlex.split(a.mapper_opt)
    if a.seed is not None: cmd += ["--GlobalMapper.random_seed", str(a.seed)]
    befehl.append(" ".join(cmd[1:]))
    r = subprocess.run(cmd, env=ENV, stdout=open(os.path.join(a.ziel, "global.log"), "w"), stderr=subprocess.STDOUT); zeiten["mapper_s"] = round(time.time() - t1); zeiten["gesamt_s"] = round(time.time() - t0)
    print("Zeiten", json.dumps(zeiten), "rc", r.returncode, flush=True)
    if r.returncode != 0 or not os.path.isfile(os.path.join(a.ziel, "0", "cameras.bin")):
        print("globaler Mapper fehlgeschlagen -> global.log"); sys.exit(3)
    bw = [sys.executable, "-I", os.path.join(T, "mapper_bewerten.py"), a.ziel, "--fotos", a.fotos, "--label", a.label, "--sek", str(zeiten["gesamt_s"]), "--befehl", " ; ".join(befehl)]
    if a.protokoll: bw += ["--protokoll", a.protokoll]
    subprocess.run(bw, check=False); print("FERTIG", a.label, flush=True)
    # Fund 20.11.2026 (Martinstor): der globale Mapper legt punktlos getrennte Stuecke in EIN Modell (Lage zueinander beliebig, sah aus wie 'Seiten verklebt').
    # Pruefen; zerfaellt Modell 0, Stuecke zusaetzlich nach <ziel>_stuecke/<k> (Modell 0 bleibt unveraendert) und laut warnen.
    zs = a.ziel.rstrip("/") + "_stuecke"
    rz = subprocess.run([sys.executable, "-I", os.path.join(T, "modell_zerlegen.py"), os.path.join(a.ziel, "0"), "--aus", zs, "--min-bilder", "10"], capture_output=True, text=True)
    print([l for l in rz.stdout.splitlines() if l.startswith("ZERLEGEN")][-1:] or rz.stderr[-300:], flush=True)
    if rz.returncode == 3: print(f"ACHTUNG ZERFALL: Modell 0 besteht aus mehreren punktlos getrennten Stuecken -> {zs}/ (jedes Stueck einzeln weiter, z. B. seiten_vereinen.py)", flush=True)
    if a.nachregistrieren:
        # Stufe 2 (zweistufig): alle noch nicht registrierten Bilder der DB per PnP in Modell 0 einhaengen (image_registrator), Punkte nachtriangulieren,
        # Buendelausgleich auf der GPU. Globaler Mapper kennt keinen Posen-Start, darum so. Ergebnis in <ziel>_reg/0, eigene Bewertung (Label +_reg).
        t2 = time.time(); zr = a.ziel.rstrip("/") + "_reg"; os.makedirs(os.path.join(zr, "0"), exist_ok=True); m0 = os.path.join(a.ziel, "0")
        stufen = [["image_registrator", "--database_path", a.db, "--input_path", m0, "--output_path", os.path.join(zr, "0"), "--Mapper.ba_use_gpu", "1"] + shlex.split(a.reg_opt),
                  ["point_triangulator", "--database_path", a.db, "--image_path", a.bilder, "--input_path", os.path.join(zr, "0"), "--output_path", os.path.join(zr, "0"), "--clear_points", "0"],
                  ["bundle_adjuster", "--input_path", os.path.join(zr, "0"), "--output_path", os.path.join(zr, "0"), "--BundleAdjustmentCeres.use_gpu", "1"]]
        for st in stufen:
            r = subprocess.run([COLMAP_BIN] + st, env=ENV, stdout=open(os.path.join(zr, st[0] + ".log"), "w"), stderr=subprocess.STDOUT); befehl.append(" ".join(st))
            if r.returncode != 0: print(st[0], "rc", r.returncode, "-> " + zr); break
        zeiten["nachreg_s"] = round(time.time() - t2); print("Zeiten", json.dumps(zeiten), flush=True)
        bw = [sys.executable, "-I", os.path.join(T, "mapper_bewerten.py"), zr, "--fotos", a.fotos, "--label", a.label + "_reg", "--sek", str(zeiten["gesamt_s"] + zeiten["nachreg_s"]), "--befehl", " ; ".join(befehl), "--vergleich", a.ziel]
        if a.protokoll: bw += ["--protokoll", a.protokoll]
        subprocess.run(bw, check=False); print("FERTIG", a.label + "_reg", flush=True)


if __name__ == "__main__": main()
