#!/usr/bin/env python3
"""pipeline_objekt.py <objekt> <fotos_ordner> <daten_ordner> - Foto-Pipeline in FESTER Reihenfolge, jede Stufe geprueft.

Reihenfolge (Regel: Fotos zuerst, LOD2 nur als Abgleich):
  1 fotos      tools/fotos_pruefen.py: defekte Bilder -> quarantaene/ (nichts loeschen)
  2 sfm        tools/iphone_sfm.py: duenne Wolke (COLMAP, GPU); Pruefung: >= 50 % der Fotos registriert
  3 dicht      COLMAP undistort -> patch_match (GPU) -> stereo_fusion -> fused.ply; Pruefung: Datei > 0 Byte
  4 kandidaten tools/lod2_kandidaten.py: Gebaeude um die Koordinate (nur Liste, nichts uebernehmen)
  5 abgleich   tools/sfm_lod2_ausrichten.py --radius 30 --schreiben: Guete berichten, Entscheidung NICHT automatisch
  6 abnahme    tools/bauen_abnehmen.sh <objekt>: Generator + Pruefstand + Sichtblatt (nur wenn Generator existiert)
Ergebnis: <daten_ordner>/pipeline_bericht.json mit Status je Stufe. Eine Stufe, die ausfaellt, stoppt die Kette
und wird im Bericht mit der Ursache festgehalten. Fehlt ein Eingang (z. B. Koordinate), wird die Stufe als OFFEN markiert.
Aufruf (ueber GPU-Steuerung): JOB_GPU_MB=6000 tools/job_start.sh pipe_<objekt> <log> /media/oem/scan/venv-seg/bin/python -I tools/pipeline_objekt.py <objekt> <fotos> <daten>
"""
import sys, os, json, glob, subprocess, time, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_SEG = "/media/oem/scan/venv-seg/bin/python"
PY_COL = "/media/oem/scan/venv-colmap/bin/python"  # pycolmap (SfM, Kamera-Export)
PY_SEG = "/media/oem/scan/venv-seg/bin/python"    # torch auf der GPU (Ausrichtung, Luecken)

def run(cmd, log=None):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if log: open(log, "a").write(out)
    return r.returncode, out

def stufe(bericht, name, status, detail):
    bericht["stufen"].append({"name": name, "status": status, "detail": detail})
    print(f"[{status}] {name}: {detail}", flush=True)

def main():
    obj, fotos, daten = sys.argv[1], sys.argv[2], sys.argv[3]
    stufe_wahl = sys.argv[sys.argv.index("--stufe") + 1] if "--stufe" in sys.argv else "schnell"   # grob: Vorschau 800 px; schnell (Standard seit 15.11.2026, Nutzer "Ja"): 1600 px nur fotometrisch + Filter, Fusion min_num_pixels 8 (Schwabentor: 2 cm Median zur geometrischen Wolke, ~50 statt ~125 min, aber 4,0 statt 2,2 % Strassenpunkte); fein: mit geometrischem Durchgang - nur wenn ein Tor zweifelt
    os.makedirs(daten, exist_ok=True)
    bericht = {"objekt": obj, "start": time.strftime("%Y-%m-%d %H:%M:%S"), "stufen": []}
    spath = os.path.join(daten, "pipeline_bericht.json")
    def sichern(): json.dump(bericht, open(spath, "w"), indent=1, ensure_ascii=False)
    log = os.path.join(daten, "pipeline.log")

    # 0 Eingangscheck (Lehre Schwabentor 13.11.: Platzhalter-Objekt und fehlender Fotopfad fielen erst spaet auf)
    oj = os.path.join(ROOT, "modelle", obj, "objekt.json")
    cfg = json.load(open(oj)) if os.path.exists(oj) else {}
    probleme = []
    if not os.path.isdir(fotos): probleme.append(f"Fotoordner fehlt: {fotos}")
    if not cfg: probleme.append(f"objekt.json fehlt: {oj}")
    if cfg and "koordinate_utm" not in cfg: probleme.append("koordinate_utm fehlt (fuer Kandidatenliste)")
    if cfg and "rahmen_wand" not in cfg: probleme.append("rahmen_wand fehlt (fuer Foto-Luecken)")
    stufe(bericht, "eingang", "OK" if not probleme else "OFFEN", "; ".join(probleme) if probleme else "Fotos, Objekt, Koordinate, Rahmen vorhanden")
    if not os.path.isdir(fotos): sichern(); return 4
    sichern()

    # 1 Fotos
    rc, out = run([PY_SEG, "-I", "tools/fotos_pruefen.py", fotos], log)
    n_gueltig = len([f for f in os.listdir(fotos) if os.path.isfile(os.path.join(fotos, f))])
    stufe(bericht, "fotos", "OK" if rc in (0, 1) and n_gueltig > 0 else "FEHLER", f"{n_gueltig} Dateien im Ordner nach Pruefung; rc={rc}")
    if n_gueltig == 0: sichern(); return 1
    sichern()

    # 2 SfM (duenne Wolke)
    # --sfm-von DIR: Fotowolke aus einem frueheren Lauf mit denselben Fotos wiederverwenden (identisches Ergebnis, spart die Stunde nicht, aber Minuten)
    if "--sfm-von" in sys.argv:
        quelle = os.path.join(sys.argv[sys.argv.index("--sfm-von") + 1], "sfm")
        ziel = os.path.join(daten, "sfm")
        if os.path.isdir(os.path.join(quelle, "sparse", "0")) and not os.path.exists(ziel):
            os.symlink(os.path.abspath(quelle), ziel)
            print(f"Fotowolke wiederverwendet aus {quelle}", flush=True)
    sparse_dir = os.path.join(daten, "sfm", "sparse", "0")
    if not os.path.isdir(sparse_dir):
        rc, out = run([PY_COL, "-I", "tools/iphone_sfm.py", fotos, os.path.join(daten, "sfm")], log)
    rc_ok = os.path.isdir(sparse_dir)
    reg = None
    if rc_ok:
        rc2, o2 = run([PY_COL, "-I", "-c", f"import pycolmap;r=pycolmap.Reconstruction({sparse_dir!r});print('REG',r.num_reg_images())"])
        m = re.findall(r"REG (\d+)", o2)
        reg = int(m[-1]) if m else None
    ziel = 0.5 * n_gueltig
    status = "OK" if rc_ok and reg is not None and reg >= ziel else "FEHLER"
    stufe(bericht, "sfm", status, f"registriert {reg} von {n_gueltig} (Ziel >= {int(ziel)})")
    if status != "OK": sichern(); return 2
    sichern()

    # Kameras als JSON fuer die GPU-Umgebung (Ausrichtung und Luecken brauchen kein pycolmap mehr)
    kam_json = os.path.join(daten, "kameras.json")
    if not os.path.exists(kam_json):
        run([PY_COL, "-I", "tools/kamera_export.py", sparse_dir, kam_json], log)

    # Parallel: Kandidatenliste (CPU, LOD2-Text) laeuft waehrend der dichten Stufe (GPU). Keine gemeinsame Ressource.
    koord = cfg.get("koordinate_utm")
    gml = (cfg.get("lod2") or {}).get("gml")
    kand_proc = None
    if koord and gml:
        kand_log = open(os.path.join(daten, "kandidaten.log"), "w")
        kand_proc = subprocess.Popen([PY_SEG, "-W", "ignore", "-I", "tools/lod2_kandidaten.py", "--gml", gml, "--e", str(koord[0]), "--n", str(koord[1]), "--radius", "45"], cwd=ROOT, stdout=kand_log, stderr=subprocess.STDOUT)
        # 3 dichte Wolke
    fused = os.path.join(daten, "dicht", "fused.ply")
    if not (os.path.exists(fused) and os.path.getsize(fused) > 0):
        # Bildwahl fuer Tiefenkarten (Lehre 14.11.: Fernansichten/gleiche Videobilder kosten voll, bringen am Objekt wenig) -> tools/dicht_bildwahl.py
        sparse_wahl = os.path.join(daten, "sfm", "sparse_dicht")
        if stufe_wahl != "grob" and not os.path.isdir(sparse_wahl):
            rc_w, out_w = run([PY_COL, "-I", "tools/dicht_bildwahl.py", sparse_dir, sparse_wahl], log); print(out_w.strip()[-400:], flush=True)
            if rc_w != 0: sparse_wahl = sparse_dir
        sparse_dicht = sparse_wahl if os.path.isdir(sparse_wahl) else sparse_dir
        script = os.path.join(daten, "dicht_kette.py")
        open(script, "w").write(f'''import pycolmap, os, time
bilder = {fotos!r}; sparse = {sparse_dicht!r}; out = {os.path.join(daten, "dicht")!r}
os.makedirs(out, exist_ok=True)
STUFE = {stufe_wahl!r}
uo = pycolmap.UndistortCameraOptions(); uo.max_image_size = 1600
import glob as _g
_n = pycolmap.Reconstruction(sparse).num_reg_images()   # nur eingehaengte Bilder bekommen Tiefenkarten
_dm = os.path.join(out, "stereo", "depth_maps")
_fertig = os.path.isdir(_dm) and len(_g.glob(os.path.join(_dm, "*.photometric.bin"))) >= _n and (STUFE != "fein" or len(_g.glob(os.path.join(_dm, "*.geometric.bin"))) >= _n)
if _fertig:
    print("Tiefenkarten aus Cache (" + str(_n) + " Bilder, Modus " + STUFE + ")", flush=True)
else:
    pycolmap.undistort_images(out, sparse, bilder, output_type="COLMAP", undistort_options=uo)
GROB = STUFE == "grob"
po = pycolmap.PatchMatchOptions(); po.max_image_size = 800 if GROB else 1600; po.gpu_index = "0"
FEIN = STUFE == "fein"; po.geom_consistency = FEIN; po.filter = True
if STUFE == "schnell": po.window_step = 2   # Messung 15.11.2026 (Schwabentor, 40 Referenzbilder): 196 statt 485 s, 11 % weniger Punkte, Abstand zur Standardwolke Median 1,3 cm, p90 4,4 cm, 0,4 % > 30 cm   # grob/schnell: nur fotometrisch (gefiltert); fein: mit geometrischer Konsistenz
if not _fertig:
    pycolmap.patch_match_stereo(out, options=po)
fo = pycolmap.StereoFusionOptions(); fo.max_image_size = 800 if GROB else 1600
if STUFE == "schnell": fo.min_num_pixels = 8   # strenger, weil die geometrische Pruefung fehlt (COLMAP-FAQ)
pycolmap.stereo_fusion(os.path.join(out, "fused.ply"), out, options=fo, input_type="geometric" if FEIN else "photometric", output_type="ply")
print("FERTIG", flush=True)
''')
        rc, out = run([PY_COL, "-I", script], log)
    ok = os.path.exists(fused) and os.path.getsize(fused) > 0
    stufe(bericht, "dicht", "OK" if ok else "FEHLER", f"fused.ply {os.path.getsize(fused) if ok else 0} Byte")
    if not ok: sichern(); return 3
    sichern()

    # 4 Kandidaten (laufen parallel zur dichten Stufe, hier nur einsammeln)
    if kand_proc is not None:
        rc = kand_proc.wait(); out = open(os.path.join(daten, "kandidaten.log")).read()
        kand = [l for l in out.splitlines() if re.match(r"\s*\d+\.\d+\s+\S+\s+\S+", l)]
        stufe(bericht, "kandidaten", "OK" if rc == 0 else "FEHLER", f"{len(kand)} Gebaeude im Umkreis (Liste siehe Log)")
    else:
        stufe(bericht, "kandidaten", "OFFEN", "keine koordinate_utm/lod2.gml in objekt.json")
    sichern()

    # 5 Abgleich (Ausrichtung, Entscheidung beim Nutzer)
    if os.path.exists(oj) and sparse_dir:
        rc, out = run([PY_SEG, "-u", "-I", "tools/sfm_lod2_ausrichten.py", oj, "--kameras", kam_json, "--dicht", fused, "--name", obj, "--radius", "30", "--schreiben", "--fotos", fotos], log)   # --fotos: GPS-Startmassstab aus den Bildern dieses Laufs (15.11.)
        g = re.findall(r"Guete[^\n]*", out)
        stufe(bericht, "abgleich", "OK" if rc == 0 else "FEHLER", (g[-1] if g else "ohne Guete-Zeile") + " | Entscheidung beim Nutzer")
    else:
        stufe(bericht, "abgleich", "OFFEN", "kein objekt.json")
    sichern()

    # 5b Foto-Luecken (was noch fotografiert werden muss)
    if os.path.exists(oj) and "rahmen_wand" in cfg and os.path.isdir(sparse_dir):
        rc, out = run([PY_SEG, "-W", "ignore", "-I", "tools/foto_luecken_plan.py", oj, "--kameras", kam_json, "--schritt", "3"], log)
        n = len(re.findall(r"^\s+- ", out, re.M))   # Luecken-Zeilen beginnen mit "  - "
        stufe(bericht, "foto_luecken", "OK" if rc == 0 else "FEHLER", f"{n} Luecken; Liste in modelle/{obj}/foto_luecken.json")
    sichern()

    # 6 Abnahme
    if os.path.exists(os.path.join(ROOT, "modelle", f"{obj}_gen.py")) or os.path.exists(os.path.join(ROOT, "modelle", obj, "objekt.json")):
        rc, out = run(["bash", "tools/bauen_abnehmen.sh", obj], log)
        stufe(bericht, "abnahme", "OK" if rc == 0 else f"ROT rc={rc}", "bauen_abnehmen.sh; Sichtblatt audit/seiten.jpg ansehen")
    sichern()
    print("BERICHT", spath, flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
