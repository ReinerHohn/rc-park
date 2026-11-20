#!/usr/bin/env python3
"""global_mapper_konsens.py --db <db.db> --bilder <ordner> --ziel <arbeitsordner> [--fotos <ordner>] [--loeschen REGEX] [--ohne-clip] [--svc-start]
   [--lage 0.10] [--rot 2.0] [--label NAME] [--protokoll datei.jsonl]
Rezept 'globaler Mapper stabil' (modelle/GLOBALER_MAPPER_STABIL.md, 19.11.2026), Ergebnis <ziel>/konsens/0:
 1. DB-Kopie bereinigen (tools/sfm_db_variante.py): EXIF-Prioren loeschen (pycolmap-4.2.1-Fehler bis 8,7 Mio px), Kamera je Videoclip, Panoramen/Vorschauen raus (--loeschen).
 2. Zweimal view_graph_calibrator + global_mapper (tools/global_mapper_lauf.py, eigene DB-Kopie je Lauf; der Mapper ist auch mit festem Seed nicht deterministisch:
    36-39 % der Kameras weichen zwischen zwei Laeufen > 10 % Kernradius ab, fast alle in der Peripherie/Fernfotos).
 3. Konsens-Schnitt (tools/sfm_stabil_schnitt.py): nur Kameras, die in beiden Laeufen gleich stehen (Lage < lage x Kernradius, Rotation < rot Grad), bleiben als Rueckgrat.
 3b. Seitenfilter (20.11.2026): Bilder, die in beiden Laeufen in einem anderen Punkt-Stueck liegen als das Rueckgrat, werden NICHT nachregistriert (fremde_seite.txt).
    Martinstor: 313 Bilder, darunter alle 21 zuvor verklebten Sued-Bilder; kostet 62 Bilder unklarer Lage im Nordstueck (lieber fehlen als falsch stehen). --ohne-seitenfilter = alter Stand.
 4. Stufe 2: `colmap mapper --input_path rueckgrat --Mapper.fix_existing_frames 1` haengt die unstabilen Bilder schrittweise gegen das feste Rueckgrat ein (PnP + Triangulation + BA nur fuer neue Kameras, GPU).
 5. Bewertung (tools/mapper_bewerten.py) gegen Lauf A; Ausgabe <ziel>/konsens/0 (+ konsens.json).
Grenzen: Fotos, die auch in Stufe 2 nicht einhaengen, fehlen (lieber fehlen als falsch stehen). GPS-Tor nur, wenn die Geotags Kamerastandorte sind (Schwabentor ja, Martinstor-Wikimedia nein).
Python: /media/oem/scan/venv-colmap/bin/python -I; lange Laeufe ueber tools/job_start.sh (RAM 6000, GPU 2500)."""
import sys, os, json, time, shlex, subprocess, argparse

T = os.path.dirname(os.path.abspath(__file__)); PY = sys.executable
sys.path.insert(0, T); from global_mapper_lauf import COLMAP_BIN, ENV


def lauf(cmd, log):
    with open(log, "w") as fh: r = subprocess.run(cmd, env=ENV, stdout=fh, stderr=subprocess.STDOUT)
    return r.returncode


def urteil(kj, n_bilder, n_clips, lief=True):
    """Traegt das Konsens-Modell? Liefert (gruende, ursachen, abhilfe); gruende leer = traegt (19.11.2026, Nutzer: 'es darf nicht sein, dass wir laenger brauchen und
    die schlechtere Methode nehmen, nur weil wir zu wenig Daten haben' -> der Mangel wird benannt, nie still ausgewichen).
    gruende = was am ERGEBNIS nicht reicht (gemessen), ursachen = was an den DATEN fehlt, abhilfe = was zu beschaffen ist.
    ANNAHME Schwellen: Rueckgrat >= 50 % der gemeinsamen Kameras und >= 30 Kameras (gemessen gut: Schwabentor 60-80 %, Martinstor 72 %), >= 50 % der Bilder im Modell
    (gleiche Schwelle wie die Kettenpruefung der Stufe sfm); Datenhinweise < 100 Bilder / kein Videoclip aus modelle/GLOBALER_MAPPER_STABIL.md (geschaetzt, nicht gemessen)."""
    g = []; s = (kj or {}).get("schnitt") or {}; b = (kj or {}).get("bewertung") or {}
    if not lief or not kj: g.append("Konsens-Lauf ohne Ergebnis (konsens.log)")
    if s:
        if s.get("stabil", 0) < 0.5 * max(s.get("gemeinsam", 0), 1): g.append(f"Rueckgrat: nur {s.get('stabil', 0)} von {s.get('gemeinsam', 0)} Kameras stehen in beiden Laeufen gleich (unter 50 %)")
        elif s.get("stabil", 0) < 30: g.append(f"Rueckgrat: nur {s.get('stabil', 0)} stabile Kameras (unter 30)")
    # 19.11.2026 (Durchsicht Punkt 40): stuerzt mapper_bewerten.py ab, steht hier {'fehler': ...} OHNE n_reg - das zaehlte als '0 Bilder im Modell' = falscher DATENMANGEL,
    # das fertige Konsens-Modell wurde verworfen. Ohne n_reg gibt es keine Aussage ueber die Bildzahl.
    if b and "n_reg" in b and n_bilder and b.get("n_reg", 0) < 0.5 * n_bilder: g.append(f"nur {b.get('n_reg', 0)} von {n_bilder} Bildern im Modell (unter 50 %)")
    u = []
    if g:
        if n_bilder < 100: u.append(f"nur {n_bilder} Bilder (unter etwa 100)")
        if n_clips == 0: u.append("kein Videoclip - das Videorueckgrat fehlt (Einzelfotos mit freier Brennweite wandern zwischen den Laeufen)")
        elif n_clips < 3: u.append(f"nur {n_clips} Videoclip(s)")
        if not u: u.append("Bildzahl und Clips reichen nominell - Ueberlappung/Abdeckung pruefen (tools/kamera_abdeckung.py, konsens_arbeit/unstabil.txt)")
    ab = "ein Video-Rundgang um das Objekt (langsam, ohne Zoom) und mehr Fotos rundum; Fotobedarf: tools/foto_auftrag.py, fehlende Seiten: tools/seiten_luecken.py" if g else ""
    return g, u, ab


def fremde_seite(ziel, rueckgrat, min_punkte=15):
    """-> (Datenbank fuer Stufe 2, Zahl ausgeschlossener Bilder, Rueckgrat fuer Stufe 2). Ausgeschlossen = in lauf1 UND lauf2 ausserhalb des Punkt-Stuecks, das die meisten Rueckgrat-Bilder
    enthaelt. Ihre Bildpaare werden in einer DB-Kopie (stufe2.db) geloescht, so kann der Mapper sie nicht einhaengen. (Erst --Mapper.image_list_path versucht:
    COLMAP-Mapper mit --input_path stuerzt damit ab, 'key was not found in unordered_node_map', 20.11.2026.) Ohne fremde Bilder: lauf1/db_kalib.db unveraendert.
    Rueckgrat-Bilder, die danach kein gueltiges Paar (>= 15 Inlier) mehr haben, laedt COLMAP nicht -> derselbe Absturz (Martinstor: commons_037, nur mit der
    Sued-Seite verbunden). Sie fliegen aus einer Rueckgrat-Kopie (rueckgrat_gefiltert/0) - ein Bild, das nur die fremde Seite sieht, ist selbst verdaechtig."""
    import sqlite3, pycolmap, modell_zerlegen as MZ
    rg = {i.name for i in pycolmap.Reconstruction(rueckgrat).images.values()}; fremd = None
    for s in (1, 2):
        r = pycolmap.Reconstruction(os.path.join(ziel, f"lauf{s}", "0")); S = [{r.images[i].name for i in st} for st in MZ.stuecke(r, min_punkte)]
        haupt = max(S, key=lambda x: len(x & rg)); aus = set().union(*S) - haupt
        fremd = aus if fremd is None else fremd & aus
    fremd -= rg
    open(os.path.join(ziel, "fremde_seite.txt"), "w").write("".join(n + "\n" for n in sorted(fremd)))
    q = os.path.join(ziel, "lauf1", "db_kalib.db")
    if not fremd: return q, 0, rueckgrat
    p = os.path.join(ziel, "stufe2.db"); src = sqlite3.connect(f"file:{q}?mode=ro", uri=True); d = sqlite3.connect(p); src.backup(d); src.close()
    ids = {i for i, n in d.execute("select image_id, name from images") if n in fremd}; M = 2147483647; weg = 0
    for pid, in d.execute("select pair_id from two_view_geometries").fetchall():
        j = pid % M; i = (pid - j) // M
        if i in ids or j in ids: d.execute("delete from two_view_geometries where pair_id = ?", (pid,)); d.execute("delete from matches where pair_id = ?", (pid,)); weg += 1
    d.commit(); rest = {}
    for pid, rows, cfg in d.execute("select pair_id, rows, config from two_view_geometries"):
        if rows >= 15 and cfg not in (0, 1): j = pid % M; i = (pid - j) // M; rest[i] = rest.get(i, 0) + 1; rest[j] = rest.get(j, 0) + 1
    d.close(); R = pycolmap.Reconstruction(rueckgrat); los = [i for i in R.images if rest.get(i, 0) == 0]
    if los:
        for fid in {R.images[i].frame_id for i in los}: R.deregister_frame(fid)
        rueckgrat = os.path.join(ziel, "rueckgrat_gefiltert", "0"); os.makedirs(rueckgrat, exist_ok=True); R.write(rueckgrat)
        print(f"FREMDE SEITE: {len(los)} Rueckgrat-Bilder nur mit der fremden Seite verbunden -> aus dem Rueckgrat genommen", flush=True)
    print(f"FREMDE SEITE: {len(fremd)} Bilder liegen in beiden Laeufen in einem anderen Punkt-Stueck als das Rueckgrat -> nicht nachregistriert ({ziel}/fremde_seite.txt)", flush=True)
    return p, len(fremd), rueckgrat


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--db", required=True); ap.add_argument("--bilder", required=True); ap.add_argument("--ziel", required=True); ap.add_argument("--fotos", default="")
    ap.add_argument("--loeschen", default=r"_360\."); ap.add_argument("--ohne-clip", action="store_true"); ap.add_argument("--svc-start", action="store_true", help="AnyCalib als Startwert (Schwabentor S5: gleichwertig, nicht besser)")
    ap.add_argument("--lage", type=float, default=0.10); ap.add_argument("--rot", type=float, default=2.0); ap.add_argument("--label", default="konsens"); ap.add_argument("--protokoll", default="")
    ap.add_argument("--mapper-opt", default=""); ap.add_argument("--mit-rueckfall", action="store_true", help="Stufe 2 mit strukturlosem Registrierungs-Rueckfall (bringt ferne Kameras; nur zum Messen)")
    ap.add_argument("--ohne-seitenfilter", action="store_true", help="fremde Seite NICHT ausschliessen (Stand vor 20.11.2026; Martinstor: 21 Sued-Bilder verklebt)"); a = ap.parse_args()
    os.makedirs(a.ziel, exist_ok=True); t0 = time.time(); ber = dict(label=a.label, zeiten={}); fotos = a.fotos or a.bilder
    dbv = os.path.join(a.ziel, "db_bereinigt.db")
    cmd = [PY, "-I", os.path.join(T, "sfm_db_variante.py"), a.db, dbv, "--priors", "loeschen"] + ([] if a.ohne_clip else ["--kamera-je-clip"]) + (["--loeschen", a.loeschen] if a.loeschen else [])
    if lauf(cmd, os.path.join(a.ziel, "variante.log")) != 0: sys.exit("DB-Variante fehlgeschlagen: " + a.ziel + "/variante.log")
    ber["zeiten"]["variante_s"] = round(time.time() - t0)
    for s in (1, 2):   # zwei unabhaengige globale Laeufe
        t = time.time(); z = os.path.join(a.ziel, f"lauf{s}")
        cmd = [PY, "-I", os.path.join(T, "global_mapper_lauf.py"), "--db", dbv, "--bilder", a.bilder, "--ziel", z, "--fotos", fotos, "--label", f"{a.label}_lauf{s}", "--seed", str(s)] + (["--svc", "--svc-als-start"] if a.svc_start else [])
        if a.mapper_opt: cmd += ["--mapper-opt", a.mapper_opt]
        if a.protokoll: cmd += ["--protokoll", a.protokoll]
        if lauf(cmd, os.path.join(a.ziel, f"lauf{s}.log")) != 0 or not os.path.isfile(os.path.join(z, "0", "cameras.bin")): sys.exit(f"globaler Lauf {s} fehlgeschlagen: {a.ziel}/lauf{s}.log")
        ber["zeiten"][f"lauf{s}_s"] = round(time.time() - t)
    t = time.time(); st = os.path.join(a.ziel, "rueckgrat", "0"); liste = os.path.join(a.ziel, "unstabil.txt")
    o = subprocess.run([PY, "-I", os.path.join(T, "sfm_stabil_schnitt.py"), os.path.join(a.ziel, "lauf1", "0"), os.path.join(a.ziel, "lauf2", "0"), "--ausgabe", st, "--liste", liste, "--lage", str(a.lage), "--rot", str(a.rot)], capture_output=True, text=True)
    if o.returncode != 0: sys.exit("Schnitt fehlgeschlagen: " + o.stdout[-300:] + o.stderr[-300:])
    ber["schnitt"] = json.loads(o.stdout.strip().splitlines()[-1]); ber["zeiten"]["schnitt_s"] = round(time.time() - t)
    # 20.11.2026 (Martinstor-Kettenmodell: 21 Sued-Bilder in Stufe 2 ins Nordmodell gezwungen, 24 % neben ihrer Lage): Bilder, die in BEIDEN globalen Laeufen
    # in einem anderen Punkt-Stueck (tools/modell_zerlegen.py) als das Rueckgrat liegen, = fremde Seite -> nicht nachregistrieren, Liste fremde_seite.txt.
    db2, ber["fremde_seite"], st2 = (os.path.join(a.ziel, "lauf1", "db_kalib.db"), 0, st) if a.ohne_seitenfilter else fremde_seite(a.ziel, st)
    t = time.time(); kz = os.path.join(a.ziel, "konsens", "0"); os.makedirs(kz, exist_ok=True)
    # Schwabentor S8/S8c/S8d (19.11. 03:16): ALLE fernen Kameras ('zum Mond') der Stufe 2 kamen aus dem strukturlosen Registrierungs-Rueckfall
    # (generalisierte Relativpose ohne 3D-Punkte); mit Rueckfall aus: 0 ferne, 0 unplausible Kameras, GPS-Kern 3 %. Inlier-Schwellen (100/0,5) brachten nichts.
    cmd = [COLMAP_BIN, "mapper", "--database_path", db2, "--image_path", a.bilder, "--input_path", st2, "--output_path", kz,
           "--Mapper.fix_existing_frames", "1", "--Mapper.ba_use_gpu", "1", "--Mapper.ba_max_num_images_direct_dense_gpu_solver", "0",
           "--Mapper.structure_less_registration_fallback", "1" if a.mit_rueckfall else "0"]
    if lauf(cmd, os.path.join(a.ziel, "stufe2.log")) != 0: sys.exit("Stufe 2 (mapper fix_existing_frames) fehlgeschlagen: " + a.ziel + "/stufe2.log")
    ber["zeiten"]["stufe2_s"] = round(time.time() - t); ber["zeiten"]["gesamt_s"] = round(time.time() - t0)
    bw = [PY, "-I", os.path.join(T, "mapper_bewerten.py"), os.path.join(a.ziel, "konsens"), "--fotos", fotos, "--label", a.label, "--sek", str(ber["zeiten"]["gesamt_s"]), "--vergleich", os.path.join(a.ziel, "lauf1"), "--befehl", " ; ".join(c if isinstance(c, str) else c[0] for c in [cmd])]
    if a.protokoll: bw += ["--protokoll", a.protokoll]
    o = subprocess.run(bw, capture_output=True, text=True); ber["bewertung"] = json.loads(o.stdout.strip().splitlines()[-1]) if o.returncode == 0 and o.stdout.strip() else dict(fehler=o.stderr[-300:])
    json.dump(ber, open(os.path.join(a.ziel, "konsens.json"), "w"), indent=1); print("KONSENS", json.dumps(ber["bewertung"]), "| Zeiten", json.dumps(ber["zeiten"]), flush=True)


if __name__ == "__main__": main()
