#!/usr/bin/env python3
"""bruecke_nachmatchen.py - eine COLMAP-Datenbank NUR fuer eine kleine Bildmenge (Bruecken-Region, 20-200 Bilder) mit ALIKED+LightGlue verstaerken (22.11.2026).

Zweck: ein spaeterer inkrementeller Mapper (colmap mapper --Mapper.image_list_path <liste>) auf dieser Menge nutzt SIFT- UND ALIKED-Matches.
Generisch, nichts Objektspezifisches. Baut auf vorhandenem Code auf:
  Stufe 1 (venv-seg, GPU, gemischte Genauigkeit): tools/lg_match.py --namen <liste> -> ALLE Paare n*(n-1)/2 -> <aus>/lg.npz
  Stufe 2 (CPU): Kopie <db_in> -> <aus>/db.db (db_in wird nur lesend geoeffnet), tools/zusatzfotos_lightglue.lg_anhaengen
           (ALIKED-Merkmale HINTER die SIFT-Merkmale: SIFT-Indizes bleiben unveraendert - Modellkopplung ueber (Bildname, Merkmalsindex)),
           Paare mit SIFT-Matches: SIFT vorn + ALIKED mit Versatz dahinter; danach colmap geometric_verifier (eigener 4.3-Bau, RCPARK_COLMAP) fuer genau diese Paare.
  Danach two_view_geometries aller ANDEREN Paare bytegleich aus db_in zurueck (geometric_verifier prueft sonst auch leere Fremdpaare neu).
  Abschluss-Probe: die ersten n0 Merkmale jedes Bildes und die SIFT-Matches jedes Paares sind bytegleich mit db_in (sonst rc 1).
Aufruf (braucht nur numpy + sqlite; KEIN pycolmap: 4.2.1 kann 4.3-Datenbanken nicht oeffnen):
  tools/py tools/bruecke_nachmatchen.py <db_in> <fotos_dir> <bilderliste.txt> --aus <ordner> [--max-kp 4096] [--resize 2048] [--min-matches 15]
        [--vram-mb 4500] [--faeden 8] [--trotz-kette]
Ausgabe: <aus>/db.db, <aus>/lg.npz, <aus>/paare.txt, <aus>/nachmatchen.json (Paare, Inlier vorher/nachher, Versatz je Bild, Laufzeit, VRAM-Spitze).
rc 0 = ok, 1 = Fehler/Probe rot, 3 = Kettenlauf aktiv (nicht gerechnet).
"""
import sys, os, json, argparse, sqlite3, subprocess, shutil, threading, time, itertools
import numpy as np
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
from zusatzfotos_lightglue import lg_anhaengen, paar_id

VENV_SEG = "/media/oem/scan/venv-seg/bin/python"
COLMAP = os.environ.get("RCPARK_COLMAP", "/media/oem/scan/colmap-build/prefix/bin/colmap")
CUDA_KONTEXT_MB = 600     # ANNAHME: CUDA-Kontext + cuDNN ausserhalb des torch-Zuteilers (nicht vom Zuteiler-Deckel erfasst)


def kette_aktiv():
    """Laufende Kettenjobs (systemd --user rcpark-kette-*) -> Liste der Einheiten."""
    try: o = subprocess.run(["systemctl", "--user", "list-units", "rcpark-kette-*", "--no-legend", "--plain", "--state=active,activating"], capture_output=True, text=True, timeout=20).stdout
    except Exception: return []
    return [z.split()[0] for z in o.splitlines() if z.strip()]


def vram_waechter(pid, stopp, spitze):
    """Speicher des Kindprozesses (nvidia-smi je Prozess) jede Sekunde abfragen, Spitze in spitze[0] (MiB)."""
    while not stopp.is_set():
        try:
            o = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout
            for z in o.splitlines():
                p, m = [x.strip() for x in z.split(",")[:2]]
                if p == str(pid): spitze[0] = max(spitze[0], int(m))
        except Exception: pass
        stopp.wait(1.0)


def paar_stand(db, namen):
    """{(a, b): (matches, inlier, config)} fuer alle Paare der Liste (a < b nach Name)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True); ids = dict(con.execute("select name, image_id from images")); st = {}
    for a, b in itertools.combinations(sorted(namen), 2):
        pid = paar_id(ids[a], ids[b]); m = con.execute("select rows from matches where pair_id=?", (pid,)).fetchone()
        g = con.execute("select rows, config from two_view_geometries where pair_id=?", (pid,)).fetchone()
        st[(a, b)] = (int(m[0]) if m else 0, int(g[0]) if g else 0, int(g[1]) if g else None)
    con.close(); return st


def probe_sift_unveraendert(db_in, db, namen):
    """SIFT-Merkmale (erste n0 Zeilen) und SIFT-Matches (erste Zeilen) jedes Bildes/Paares bytegleich? -> Liste der Abweichungen."""
    A = sqlite3.connect(f"file:{db_in}?mode=ro", uri=True); B = sqlite3.connect(f"file:{db}?mode=ro", uri=True); fehl = []
    ids = dict(A.execute("select name, image_id from images"))
    if ids != dict(B.execute("select name, image_id from images")): return ["Bild-IDs/Namen verschieden"]
    for n in namen:
        r0, c0, d0 = A.execute("select rows, cols, data from keypoints where image_id=?", (ids[n],)).fetchone(); r1, c1, d1 = B.execute("select rows, cols, data from keypoints where image_id=?", (ids[n],)).fetchone()
        if c0 != c1 or r1 < r0 or d1[:len(d0)] != d0: fehl.append(f"Merkmale {n}")
    for a, b in itertools.combinations(namen, 2):
        pid = paar_id(ids[a], ids[b]); m0 = A.execute("select rows, data from matches where pair_id=?", (pid,)).fetchone()
        if not m0 or not m0[0]: continue
        m1 = B.execute("select rows, data from matches where pair_id=?", (pid,)).fetchone()
        if not m1 or m1[0] < m0[0] or m1[1][:len(m0[1])] != m0[1]: fehl.append(f"SIFT-Matches {a}|{b}")
    A.close(); B.close(); return fehl


def fremde_geometrien_zuruecksetzen(db_in, db, eigene):
    """two_view_geometries aller Paare AUSSER eigene (pair_ids) bytegleich aus db_in zurueckholen. -> Anzahl Paare, die abwichen.
    22.11.2026 (Schwabentor 1122): geometric_verifier prueft auch Paare mit LEERER Geometrie (rows 0, config 1) der ganzen Datenbank neu
    (149 Paare ausserhalb der Bruecke bekamen 15-16 Inlier) - das Werkzeug darf nur die eigenen Paare veraendern."""
    con = sqlite3.connect(f"file:{db}", uri=True); con.execute("attach database ? as alt", (f"file:{db_in}?mode=ro",))   # db_in nur lesend
    con.execute("create temp table eigen (pair_id integer primary key)"); con.executemany("insert into eigen values (?)", [(int(p),) for p in eigene])
    n = con.execute("""select count(*) from (select pair_id, rows, cols, data, config from main.two_view_geometries where pair_id not in (select pair_id from eigen)
                       except select pair_id, rows, cols, data, config from alt.two_view_geometries where pair_id not in (select pair_id from eigen))""").fetchone()[0]
    n += con.execute("""select count(*) from alt.two_view_geometries where pair_id not in (select pair_id from eigen) and pair_id not in (select pair_id from main.two_view_geometries)""").fetchone()[0]
    if n:
        con.execute("delete from main.two_view_geometries where pair_id not in (select pair_id from eigen)")
        con.execute("insert into main.two_view_geometries select * from alt.two_view_geometries where pair_id not in (select pair_id from eigen)")
    con.commit(); con.execute("detach database alt"); con.close(); return int(n)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("db_in"); ap.add_argument("fotos"); ap.add_argument("liste"); ap.add_argument("--aus", required=True)
    ap.add_argument("--max-kp", type=int, default=4096); ap.add_argument("--resize", type=int, default=2048); ap.add_argument("--min-matches", type=int, default=15)
    ap.add_argument("--vram-mb", type=int, default=4500, help="Obergrenze GPU-Speicher des Matchers (MiB)"); ap.add_argument("--faeden", type=int, default=8); ap.add_argument("--trotz-kette", action="store_true", help="auch rechnen, wenn ein Kettenlauf aktiv ist")
    a = ap.parse_args(argv); t0 = time.time()
    k = kette_aktiv()
    if k and not a.trotz_kette: print("Kettenlauf aktiv, nicht gerechnet:", " ".join(k)); return 3
    namen = [z.strip() for z in open(a.liste) if z.strip()]; namen = sorted(dict.fromkeys(namen))
    con = sqlite3.connect(f"file:{a.db_in}?mode=ro", uri=True); ids = dict(con.execute("select name, image_id from images")); con.close()
    fehlt = [n for n in namen if n not in ids or not os.path.isfile(os.path.join(a.fotos, n))]
    if fehlt: print("Bilder fehlen in Datenbank oder Fotoordner:", fehlt[:10]); return 1
    if len(namen) < 2: print("weniger als 2 Bilder"); return 1
    os.makedirs(a.aus, exist_ok=True); npz = os.path.join(a.aus, "lg.npz"); db = os.path.join(a.aus, "db.db")
    vorher = paar_stand(a.db_in, namen)

    # Stufe 1: ALIKED+LightGlue, alle Paare (lg_match.py, venv-seg)
    # 22.11.2026 (Schwabentor 1122, 3000x4000-Fotos): ALIKED bei --resize 2048 braucht ~4,8 GB (dichte Merkmalskarte) -> passt nicht in 4500 MiB;
    # bei Speichermangel dieselbe Stufe mit kleinerer Bildgroesse wiederholen (x0,8 bis 1024), benutzte Groesse steht im Bericht
    env = dict(os.environ, RCPARK_LG_VRAM_MB=str(max(500, a.vram_mb - CUDA_KONTEXT_MB)), PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    t1 = time.time(); spitze = [0]; resize = a.resize; versuche = []
    while True:
        cmd = [VENV_SEG, "-I", os.path.join(T, "lg_match.py"), a.fotos, npz, "--max-kp", str(a.max_kp), "--resize", str(resize), "--min-matches", str(a.min_matches), "--namen"] + namen
        stopp = threading.Event(); log = os.path.join(a.aus, "lg_match.log")
        with open(log, "w") as lg:
            p = subprocess.Popen(cmd, stdout=lg, stderr=subprocess.STDOUT, env=env); w = threading.Thread(target=vram_waechter, args=(p.pid, stopp, spitze), daemon=True); w.start(); rc = p.wait()
        stopp.set(); w.join(); oom = rc != 0 and "OutOfMemoryError" in open(log, errors="replace").read(); versuche.append(dict(resize=resize, rc=rc, speichermangel=oom))
        if not oom or resize <= 1024: break
        resize = max(1024, int(resize * 0.8)); print(f"Speichermangel, wiederhole mit --resize {resize}", flush=True)
    t_lg = time.time() - t1
    if rc != 0 or not os.path.isfile(npz): print(f"lg_match.py rc {rc}, siehe {log}"); return 1

    # Stufe 2: Kopie + Anhaengen (sqlite) + Verifikation mit der COLMAP-Binaerdatei
    t2 = time.time()
    for f in (db, db + "-wal", db + "-shm"):
        if os.path.exists(f): os.remove(f)
    src = sqlite3.connect(f"file:{a.db_in}?mode=ro", uri=True); dst = sqlite3.connect(db); src.backup(dst); dst.close(); src.close()   # konsistente Kopie, db_in nur lesend
    D = np.load(npz, allow_pickle=True); off, pl = lg_anhaengen(db, D)
    pf = os.path.join(a.aus, "paare.txt"); open(pf, "w").write("".join(f"{x} {y}\n" for x, y in pl))
    if pl:
        # 22.11.2026: NICHT pycolmap 4.2.1 - Datenbanken des eigenen COLMAP-4.3-Baus (user_version 4030001) oeffnet es nicht ("No registered database
        # factory succeeded") und setzt dabei user_version auf 4020100 zurueck. geometric_verifier prueft nur Paare MIT Matches und OHNE two_view_geometry,
        # das sind genau die von lg_anhaengen beschriebenen (deren Geometrie dort geloescht wurde); alle anderen Paare bleiben unberuehrt.
        from sfm_seiten_modelle import CUDA_LIBS
        env2 = dict(os.environ, LD_LIBRARY_PATH=":".join(CUDA_LIBS + [x for x in [os.environ.get("LD_LIBRARY_PATH", "")] if x]))
        with open(os.path.join(a.aus, "verifikation.log"), "w") as lg:
            rc = subprocess.call([COLMAP, "geometric_verifier", "--database_path", db, "--TwoViewGeometry.random_seed", "0", "--num_threads", str(a.faeden)], stdout=lg, stderr=subprocess.STDOUT, env=env2)
        if rc != 0: print(f"geometric_verifier rc {rc}, siehe {a.aus}/verifikation.log"); return 1
    ids_db = dict(sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute("select name, image_id from images"))
    zurueck = fremde_geometrien_zuruecksetzen(a.db_in, db, [paar_id(ids_db[x], ids_db[y]) for x, y in pl])
    t_ein = time.time() - t2
    fehl = probe_sift_unveraendert(a.db_in, db, namen); nachher = paar_stand(db, namen)
    if fremde_geometrien_zuruecksetzen(a.db_in, db, [paar_id(ids_db[x], ids_db[y]) for x, y in pl]): fehl.append("fremde Paar-Geometrien weichen nach dem Zuruecksetzen ab")

    lgm = {tuple(sorted(k[2:].split("|"))): int(D[k].shape[0]) for k in D.files if k.startswith("m_")}
    pv = []
    for (x, y), (m0, i0, c0) in sorted(vorher.items()):
        m1, i1, c1 = nachher[(x, y)]; pv.append(dict(a=x, b=y, sift_matches=m0, sift_inlier=i0, aliked_matches=lgm.get((x, y), 0), matches_nachher=m1, inlier_nachher=i1, config_nachher=c1))
    def n_ok(st, idx, ab=15): return sum(1 for v in st.values() if v[idx] >= ab)
    ber = dict(db_in=a.db_in, db=db, fotos=a.fotos, liste=a.liste, bilder=len(namen), paare_gesamt=len(vorher), paare_aliked_gematcht=len(pl),
               paare_mit_sift_geometrie_vorher=sum(1 for v in vorher.values() if v[1] > 0), paare_mit_geometrie_nachher=sum(1 for v in nachher.values() if v[1] > 0),
               paare_inlier_ab15_vorher=n_ok(vorher, 1), paare_inlier_ab15_nachher=n_ok(nachher, 1),
               inlier_summe_vorher=int(sum(v[1] for v in vorher.values())), inlier_summe_nachher=int(sum(v[1] for v in nachher.values())),
               inlier_median_vorher_verifizierte=float(np.median([v[1] for v in vorher.values() if v[1] > 0])) if any(v[1] > 0 for v in vorher.values()) else 0.0,
               inlier_median_nachher_verifizierte=float(np.median([v[1] for v in nachher.values() if v[1] > 0])) if any(v[1] > 0 for v in nachher.values()) else 0.0,
               sift_merkmale_je_bild=off, fremde_geometrien_zurueckgesetzt=zurueck, probe_sift_unveraendert=not fehl, probe_abweichungen=fehl[:20],
               zeit_s=dict(lightglue=round(t_lg, 1), einlesen_verifizieren=round(t_ein, 1), gesamt=round(time.time() - t0, 1)), vram_spitze_mib=spitze[0],
               einstellungen=dict(max_kp=a.max_kp, resize=resize, resize_versuche=versuche, min_matches=a.min_matches, vram_mb=a.vram_mb), paare=pv)
    json.dump(ber, open(os.path.join(a.aus, "nachmatchen.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in ber.items() if k not in ("paare", "sift_merkmale_je_bild")}, ensure_ascii=False)[:1500])
    return 0 if not fehl else 1


if __name__ == "__main__": sys.exit(main())
