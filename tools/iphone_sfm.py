#!/usr/bin/env python3
"""iphone_sfm.py <bilderordner> <arbeitsordner> - COLMAP-SfM (pycolmap, SIFT-GPU, exhaustive, Mapper) fuer die iPhone-Fotos; GPU von Anfang an (Nutzerregel).
  /media/oem/scan/venv-colmap/bin/python -I tools/iphone_sfm.py <bilderordner> <arbeitsordner> [--mapper auto|auto_alt|global|inkrementell|konsens] [--flexglue]
  (oder `tools/py col tools/iphone_sfm.py ...`; ohne 'col' waehlt tools/py venv-seg, dort fehlt pycolmap). RCPARK_FLEXGLUE=1 wie --flexglue. Defekte Bilder vorher nach quarantaene/ (fotos_pruefen.py).
VORSTUFE 'seiten' (21.11.2026, Standard AN, tools/sfm_seiten_vorstufe.py): Vordergrund-Masken (handy_masken, GPU) -> Masken in der Merkmalssuche (ImageReader.mask_path; vorhandene
  Datenbank ohne Masken: db_masken_filter als Rueckfall) -> seiten_erkennen --streng --masken -> Mapper rechnet auf db_seiten.db. Zwischenstaende werden wiederverwendet.
  RCPARK_SEITEN=0 schaltet sie ab, =immer nimmt db_seiten.db auch ohne 'verwechselt'-Urteil; RCPARK_MASKEN_EXTRAKTION=0 = Masken nur als Filter; RCPARK_MASKEN_BATCH (2).
SEITENMODELLE (21.11.2026, Standard AN, tools/sfm_seiten_modelle.py): trennt die Vorstufe die Bilder in MEHRERE Bildteile (Seiten ohne echte Verbindung) und haben mindestens zwei
  davon >= 30 Bilder (RCPARK_SEITEN_MIN_BILDER), rechnet statt EINES Mappers je Teil der globale Mapper zweimal, danach je Teil eine dichte Wolke und tools/seiten_vereinen.py;
  sparse/0 ist dann das VEREINTE Modell (oder, gemeldet, Teil A allein). Bericht seiten_modelle.json, Arbeitsordner seiten_modelle/. Bei genau einem Teil bleibt alles wie bisher.
  RCPARK_SEITEN_MODELLE=0 = Stand davor (ein Mapper, fehlende Seite nur gemeldet). Gilt fuer --mapper auto|auto_alt|global; ein erzwungener anderer Mapper bleibt erzwungen.
NUR NACHSTUFE (22.11.2026, RCPARK_SFM_NUR_NACHSTUFE=1, setzt tools/pipeline_objekt.py, wenn 'nachstufe_code' in seiten_modelle.json nicht mehr zum Code passt): alles
  Teure MUSS aus dem Zwischenstand kommen (Merkmale/Paare aus db.db, Seitenmodelle je Teil, dichte Wolken je Teil); passt db.db nicht zum Fotoordner oder sind die Seiten nicht
  getrennt, bricht der Lauf VOR jedem Mapper ab (sparse/ bleibt unberuehrt) - neu rechnen dann bewusst mit --neu sfm. Neu laufen Vereinen, Tore, Einsetzen, mapper_wahl.json.
DB-BEREINIGUNG vor JEDEM Mapper (Kamera je Videoclip, EXIF-Prioren weg, tools/sfm_db_variante.py -> db_mapper.db; der Konsens-Weg bereinigt selbst). RCPARK_DB_BEREINIGEN=0 = alter Stand.
Ausgaben in <arbeitsordner>: db.db, paare.txt (ab > 300 Bildern), sparse/<n>/ (COLMAP-Modelle), mapper_wahl.json (Mapperwahl + GPS-Tor + 'seiten': Bildteile, fehlende Seiten),
  masken/, masken_colmap/, seiten.json, db_seiten.db, db_mapper.db, seiten_modelle.json + seiten_modelle/ (nur bei mehreren Bildteilen).
Exit 0 = fertig; Abbruch mit Text, wenn der erzwungene Konsens- bzw. der globale Mapper scheitert.
"""
import sys, os, pycolmap, time


def paarliste(db, w, max_voll=300, nachbarn=10, schluessel=4):
    """Lehre Schwabentor 2026-11-14 (Nutzer: 'koennen wir nicht weiter beschleunigen?'): ~580 Bilder exhaustive = 168 000 Paare, davon
    ~300 Videobilder, die fast nur ihre Nachbarn sehen. Ab > max_voll Bildern: Fotos x Fotos voll; Videobilder (Name '<clip>__vf_NNN')
    je Clip sequenziell +-nachbarn; jedes schluessel-te Videobild x alle Fotos und x Schluesselbilder anderer Clips. Rund 3x weniger Paare."""
    import sqlite3, re, itertools
    c = sqlite3.connect(db); namen = [r[0] for r in c.execute("SELECT name FROM images")]; c.close()
    if len(namen) <= max_voll: return None
    clips = {}; fotos = []
    for n in namen:
        m = re.match(r"(.+)__vf_(\d+)\.", n)
        if m: clips.setdefault(m.group(1), []).append((int(m.group(2)), n))
        else: fotos.append(n)
    paare = set(itertools.combinations(sorted(fotos), 2)); schl = []
    for k, L in clips.items():
        L = [n for _, n in sorted(L)]
        for i, n in enumerate(L):
            for j in range(i + 1, min(len(L), i + 1 + nachbarn)): paare.add((n, L[j]))
        schl += [(k, n) for n in L[::schluessel]]
    for k, n in schl:
        for f in fotos: paare.add((n, f))
    for (k1, a), (k2, b) in itertools.combinations(schl, 2):
        if k1 != k2: paare.add((a, b))
    pf = os.path.join(w, "paare.txt"); open(pf, "w").write("\n".join(f"{a} {b}" for a, b in sorted(paare)) + "\n")
    voll = len(namen) * (len(namen) - 1) // 2
    print(f"Paarliste: {len(paare)} statt {voll} Paare ({len(fotos)} Fotos, {sum(map(len, clips.values()))} Videobilder in {len(clips)} Clips)", flush=True)
    return pf

img, w = sys.argv[1], sys.argv[2]; os.makedirs(w, exist_ok=True); db = f"{w}/db.db"; t = time.time()
# Vor dem Lauf: defekte Bilder nach quarantaene/ verschieben (Lehre Schwabentor 13.11.: 0-Byte-Datei brach erst im Lauf auf).
import subprocess
subprocess.run(["/media/oem/scan/venv-seg/bin/python", "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fotos_pruefen.py"), img], check=False)
# 24.11.2026: SIFT-Einstellung zentral (tools/sift_einstellung.py): volle Aufloesung + first_octave 0 auf der GPU; RCPARK_SIFT_ALT=1 = alt (max_image_size 2400, first_octave -1)
SIFT_MERKMALE, SIFT_ALT_MAX = 6400, 2400
# VORSTUFE 'seiten', Schritt 1 (21.11.2026): Masken fuer Personen/Fahrzeuge/Baeume VOR der Merkmalssuche (Martinstor: eine Person in Selbstaufnahme-Videobildern verband Sued- und Nordseite).
SEITEN = os.environ.get("RCPARK_SEITEN", "1"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sfm_seiten_vorstufe as SV, json
_seiten = {}; _roh = f"{w}/masken"; _mk = f"{w}/db.masken.json"       # db.masken.json = Beleg, dass db.db MIT Masken in der Merkmalssuche entstand
_mit_maske = SEITEN != "0" and os.environ.get("RCPARK_MASKEN_EXTRAKTION", "1") != "0"
if SEITEN != "0": _seiten["masken"] = SV.masken_rechnen(img, w)
else: print("VORSTUFE 'seiten' ABGESCHALTET (RCPARK_SEITEN=0): keine Masken, keine Seitenerkennung - Seitenverklebung symmetrischer Bauwerke moeglich", flush=True)
# Cache: Merkmale und Paare aus einem frueheren Lauf wiederverwenden, wenn die Datenbank genau diese Fotos enthaelt (keine Qualitaetsaenderung).
import sqlite3
_n_fotos = len([f for f in os.listdir(img) if os.path.isfile(os.path.join(img, f))])
_db_ok = False
if os.path.exists(db):
    try:
        _c = sqlite3.connect(db); _ni = _c.execute("SELECT COUNT(*) FROM images").fetchone()[0]; _nm = _c.execute("SELECT COUNT(*) FROM two_view_geometries").fetchone()[0]; _c.close()
        _db_ok = (_ni == _n_fotos and _nm > 0)
    except Exception:
        _db_ok = False
NUR_NACHSTUFE = os.environ.get("RCPARK_SFM_NUR_NACHSTUFE") == "1"
if NUR_NACHSTUFE and not _db_ok: raise SystemExit(f"NUR NACHSTUFE: db.db passt nicht zum Fotoordner ({_n_fotos} Dateien) - Merkmale wuerden neu gerechnet; bewusst neu: --neu sfm")
if _db_ok:
    print(f"Merkmale und Paare aus Cache ({_ni} Bilder, {_nm} Paare)", flush=True)
else:
    _db_neu = not os.path.exists(db); _ro = pycolmap.ImageReaderOptions(); _n_mask = 0
    if os.path.exists(_mk): os.remove(_mk)                                # Beleg gilt nur fuer die Datenbank, die er beschreibt
    if _mit_maske:                                                        # Masken schon in der Merkmalssuche (COLMAP: <mask_path>/<Bildname>.png, 0 = ignorieren) - besser als nachtraeglich filtern
        _ro.mask_path = f"{w}/masken_colmap"; _n_mask, _n_leer = SV.masken_colmap(img, _roh, _ro.mask_path); print(f"Merkmalssuche mit Masken: {_n_mask} von {_n_fotos} Bildern, {_n_leer} mit leerer Maske (COLMAP ueberspringt Bilder ohne Maskendatei)", flush=True)
    # 23.11.2026 AUDIT STILLE ERFOLGE: SiftGPU laesst Bilder bei 'out of memory' still WEG, extract_features endet normal - die SfM rechnete dann ohne sie.
    # 24.11.2026: zentral in sift_einstellung.extrahieren_mit_tor (statt pycolmap.extract_features hier): GPU, fehlende Bilder einmal auf der CPU nachholen,
    # Pflicht-Tor sfm/sift_tor.json (gesamtkette: Zeile 'sift_tor', rot bei Restfehlern).
    import sift_einstellung as SE
    _alle = sorted(f for f in os.listdir(img) if os.path.isfile(os.path.join(img, f)) and f.lower().endswith(SE.BILD_ENDUNGEN))
    SE.extrahieren_mit_tor(pycolmap, db, img, _alle, camera_mode=pycolmap.CameraMode.PER_IMAGE, reader_options=_ro, alt_max=SIFT_ALT_MAX, max_num_features=SIFT_MERKMALE,
                           geraet="gpu", tor_json=f"{w}/sift_tor.json", stufe="sfm merkmale"); print("Merkmale", time.time() - t, flush=True)
    if _mit_maske and _db_neu: json.dump(dict(masken=_n_mask, bilder=_n_fotos, zeit=time.strftime("%Y-%m-%d %H:%M")), open(_mk, "w"))   # bestand db.db schon (Teilstand), haben alte Bilder Merkmale OHNE Maske -> kein Beleg, Filter-Rueckfall
    _paare = paarliste(db, w)
    if _paare:
        po_ = pycolmap.ImportedPairingOptions(); po_.match_list_path = _paare
        pycolmap.match_image_pairs(db, pairing_options=po_, device=pycolmap.Device.cuda); print("Abgleich (Paarliste)", time.time() - t, flush=True)
    else:
        pycolmap.match_exhaustive(db, device=pycolmap.Device.cuda); print("Abgleich", time.time() - t, flush=True)
os.makedirs(f"{w}/sparse", exist_ok=True)
# 20.11.2026 (Messung Martinstor/Schwabentor, LOGBUCH_KETTENTEST_2026-11-19.md): FlexGlue-Zuordnung der SIFT-bestaetigten Paare VOR dem Mapper - Martinstor +30/+40 % Bilder,
# Schwabentor +6 %, Lage und Seitentrennung gleich. Zuschaltbar (--flexglue oder RCPARK_FLEXGLUE=1), ~0,2 s je Paar auf der GPU; Mapper rechnen dann auf db_flexglue.db.
if "--flexglue" in sys.argv or os.environ.get("RCPARK_FLEXGLUE") == "1":
    _fg = f"{w}/db_flexglue.db"
    _r = subprocess.run([sys.executable, "-I", os.path.join(os.path.dirname(os.path.abspath(__file__)), "flexglue_zuordnung.py"), "--db", db, "--bilder", img, "--aus", _fg], check=False)
    if _r.returncode == 0: db = _fg; print("Mapper rechnen auf FlexGlue-Zuordnungen:", db, flush=True)
    else: print("ACHTUNG FlexGlue nicht vollstaendig (rc", _r.returncode, ") - Mapper rechnen auf SIFT", flush=True)
# VORSTUFE 'seiten', Schritte 2+3 (21.11.2026): vorhandene Datenbank ohne Masken -> Vordergrund-Zuordnungen nachtraeglich streichen (db_maske.db); dann Seitenerkennung (GPU, Paar-Pruefer
# mit Masken) -> db_seiten.db ohne die Paare zwischen aehnlichen, aber verschiedenen Seiten. Scheitert ein Schritt, bricht die SfM ab (kein stiller Mapper-Lauf auf ungefilterten Paaren).
if SEITEN != "0":
    _seiten["masken_weg"] = "merkmalssuche" if os.path.isfile(_mk) else "filter"
    if not os.path.isfile(_mk): db = SV.masken_filter(db, _roh, w)
    _db_ursprung = db                                                     # MIT den Querpaaren zwischen den Seiten - die braucht tools/seiten_vereinen.py (db_seiten.db hat sie nicht mehr)
    db, _seiten["erkennung"] = SV.seiten(db, img, w, _roh, modus=SEITEN)
# Mapper: COLMAP-Binaerdatei mit CUDA (GPU-Bündelausgleich, BundleAdjustmentCeres.use_gpu). Die pycolmap-Python-Bibliothek hat keine GPU-Ceres.
COLMAP_BIN = "/media/oem/scan/colmap-build/prefix/bin/colmap"
_env = dict(os.environ, LD_LIBRARY_PATH=":".join(["/media/oem/scan/cuda-toolkit-combo/lib64", "/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib", "/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib", "/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib"]))
# ein Thread: reproduzierbare Anzahl eingehaengter Bilder (Messung 13.11.: Mehrthread 181/149/181/21, Einthread 181/181); Qualitaet vor Tempo
# MAPPERWAHL: --mapper auto (Standard) | auto_alt | global | inkrementell | konsens
#   auto (seit 19.11.2026, Nutzer 'Ja, mach es als Standard'): ZUERST Konsens-Mapper (tools/global_mapper_konsens.py, modelle/GLOBALER_MAPPER_STABIL.md). Traegt er nicht
#   (Rueckgrat < 50 % / < 30 Kameras, < 50 % der Bilder im Modell), wird 'ACHTUNG DATENMANGEL' mit Ursache (Bildzahl, Videoclips) und Abhilfe ausgegeben
#   (mapper_wahl.json 'datenmangel', Kettenbericht) und erst DANN der alte Weg gerechnet. konsens = erzwingen; auto_alt = alter Weg ohne Konsens.
#   alter Weg (15.11.2026, Bericht Massnahmen 1+2): erst global (view_graph_calibrator auf DB-KOPIE + global_mapper, Minuten statt 40 min), dann GPS-TOR (tools/mapper_gps_vergleich.py: Anteil der
#   eigenen GPS-Fotos > 15 m neben GPS). Besteht (<= 15 %, >= 15 GPS-Fotos) -> global gilt. Sonst zusaetzlich schrittweise und das Modell mit dem kleineren
#   Anteil nehmen. Ohne GPS-Beleg (< 15 Fotos) gilt wie bisher der schrittweise Mapper (kein Urteil moeglich). Messungen: Schwabentor global 3 % / schrittweise
#   18 %; global ist NICHT immun (Variante gemeinsame Kamera: 18 %) -> Tor ist Pflicht. Ergebnis: <w>/mapper_wahl.json.
import re, json, shutil
MAPPER = sys.argv[sys.argv.index("--mapper") + 1] if "--mapper" in sys.argv else "auto"; _tools = os.path.dirname(os.path.abspath(__file__))
_dbm = []
def _db_mapper():
    """DB-Bereinigung fuer JEDEN Mapper-Weg (21.11.2026; vorher nur im Konsens-Weg): Kamera je Videoclip, EXIF-Prioren weg, Panoramen raus -> <w>/db_mapper.db. Erst beim ersten
    Bedarf gerechnet (der Konsens-Weg bereinigt seine eigene Kopie; eine Kopie der Datenbank ist am Martinstor 2,8 GB)."""
    if not _dbm: _dbm.append(db if os.environ.get("RCPARK_DB_BEREINIGEN", "1") == "0" else SV.bereinigen(db, w))
    return _dbm[0]
def _inkrementell(ziel):
    os.makedirs(ziel, exist_ok=True)
    subprocess.run([COLMAP_BIN, "mapper", "--database_path", _db_mapper(), "--image_path", img, "--output_path", ziel,
                    "--Mapper.num_threads", os.environ.get("RCPARK_MAPPER_FAEDEN", "-1"), "--Mapper.ba_use_gpu", "1", "--Mapper.ba_gpu_index", "0", "--Mapper.ba_max_num_images_direct_dense_gpu_solver", "0"], env=_env, check=True)
    # 20.11.2026: Faeden 1 -> -1 (alle). Der Wert steuert laut COLMAP-Quelltext Ceres-Ableitungen und RANSAC der Lageschaetzung; "1" stand seit 14.11. ohne Grund da.
    # A/B Schwabentor 203 Bilder (tools/versuche/mapper_faeden_ab.sh): 179 Bilder nach 540 s gegen 217 s (2,5 x), Ergebnis gleichwertig (181 Bilder / 65 019 Punkte / 1,239 px
    # gegen 180 / 63 519 / 1,236 px beim Abbruch des 1-Faden-Laufs). RCPARK_MAPPER_FAEDEN=1 = alter Stand.
def _konsens(ziel):
    """--mapper konsens (19.11.2026, modelle/GLOBALER_MAPPER_STABIL.md): DB bereinigen (EXIF-Prioren weg, Kamera je Clip, Panoramen raus) -> zwei globale Laeufe ->
    Konsens-Rueckgrat (nur in beiden Laeufen gleich stehende Kameras) -> Rest per `mapper --fix_existing_frames 1` ohne strukturlosen Rueckfall. Standard bleibt 'auto'."""
    arb = f"{w}/konsens_arbeit"; r = subprocess.run([sys.executable, "-I", os.path.join(_tools, "global_mapper_konsens.py"), "--db", db, "--bilder", img, "--ziel", arb, "--label", "konsens"],
                       env=_env, stdout=open(os.path.join(w, "konsens.log"), "w"), stderr=subprocess.STDOUT)
    q = os.path.join(arb, "konsens", "0")
    if r.returncode != 0 or not os.path.isfile(os.path.join(q, "cameras.bin")): return False
    shutil.rmtree(ziel, ignore_errors=True); os.makedirs(ziel); shutil.copytree(q, os.path.join(ziel, "0")); return True
def _konsens_urteil(lief):
    """Urteil ueber das Konsens-Modell + Datenlage (Bilder, Videoclips); Regel in global_mapper_konsens.urteil."""
    import global_mapper_konsens as GK
    namen = [f for f in os.listdir(img) if os.path.isfile(os.path.join(img, f))]; clips = {n_.split("__vf_")[0] for n_ in namen if "__vf_" in n_}
    kp = f"{w}/konsens_arbeit/konsens.json"; kj = json.load(open(kp)) if lief and os.path.isfile(kp) else None
    # 21.11.2026: Bilder, die die Seitenerkennung als FREMD aus den Paaren nahm (anderes Bauwerk; Martinstor 1362 von 2107), koennen nicht ins Modell - sie zaehlen nicht zur Bildzahl,
    # sonst hiesse es 'unter 50 % im Modell' = falscher DATENMANGEL und der langsame Ausweichweg liefe an.
    _e = _seiten.get("erkennung") or {}; n_fremd = _e.get("fremd", 0) if _e.get("db", "").endswith("db_seiten.db") else 0
    g, u, ab = GK.urteil(kj, len(namen) - n_fremd, len(clips), lief)
    return dict(bilder=len(namen), fremd=n_fremd, videoclips=len(clips), rueckgrat=(kj or {}).get("schnitt", {}).get("stabil"), gemeinsam=(kj or {}).get("schnitt", {}).get("gemeinsam"),
                im_modell=(kj or {}).get("bewertung", {}).get("n_reg"), gruende=g, ursachen=u, abhilfe=ab)
def _global(ziel):
    dbg = db + ".global.db"; shutil.copyfile(_db_mapper(), dbg); os.makedirs(ziel, exist_ok=True)       # Kalibrierung aendert Intrinsik/Zweibild-Geometrien in der DB -> nur auf der Kopie
    r1 = subprocess.run([COLMAP_BIN, "view_graph_calibrator", "--database_path", dbg], env=_env, stdout=open(os.path.join(w, "kalib.log"), "w"), stderr=subprocess.STDOUT)
    r2 = subprocess.run([COLMAP_BIN, "global_mapper", "--database_path", dbg, "--image_path", img, "--output_path", ziel], env=_env, stdout=open(os.path.join(w, "global.log"), "w"), stderr=subprocess.STDOUT)
    os.remove(dbg); return r1.returncode == 0 and r2.returncode == 0 and os.path.isdir(os.path.join(ziel, "0"))
def _gps_tor(modell):
    o = subprocess.run([sys.executable, "-I", os.path.join(_tools, "mapper_gps_vergleich.py"), img, modell], capture_output=True, text=True).stdout
    n = re.search(r"mit GPS: (\d+)", o); a_ = re.search(r"Anteil > 15 m (\d+) %", o); m_ = re.search(r"Median ([\d.]+) m", o)
    return dict(n_gps=int(n.group(1)) if n else 0, anteil_ueber_15m=int(a_.group(1)) if a_ else None, median_m=float(m_.group(1)) if m_ else None)
sys.path.insert(0, _tools); import gpu_buchung as GB; GB.frei()   # Mapper rechnet fast nur auf der CPU (global ~7 min, schrittweise ~40 min) -> GPU-Budget solange freigeben
_t0 = _t_anfang = time.time(); wahl = dict(mapper=MAPPER)
_fertig = False
# SEITENMODELLE, Phase 1 (21.11.2026, Handbeweis Martinstor GLOBALER_MAPPER_STABIL.md 12:23-14:42): mehrere Bildteile -> je Teil zwei globale Laeufe statt eines Mappers ueber alles
# (der koennte die Teile ohnehin nicht in ein Modell legen). Weniger als zwei Teile mit genug Bildern oder kein Teilmodell -> Mapperwahl wie bisher (gemeldet).
_sm = None; _e0 = _seiten.get("erkennung") or {}
if _e0.get("getrennt"):
    if os.environ.get("RCPARK_SEITEN_MODELLE", "1") == "0": print("SEITENMODELLE ABGESCHALTET (RCPARK_SEITEN_MODELLE=0): ein Mapper ueber alle Bildteile, fehlende Seiten werden nur gemeldet", flush=True)
    elif MAPPER not in ("auto", "auto_alt", "global"): print(f"SEITENMODELLE nicht gerechnet: --mapper {MAPPER} ist erzwungen (belegt ist nur der globale Mapper je Seite)", flush=True)
    else:
        import sfm_seiten_modelle as SM
        _sm = SM.modelle(w, img, _e0["seiten_json"], _db_mapper(), int(os.environ.get("RCPARK_SEITEN_MIN_BILDER", SM.MIN_BILDER))); wahl["seiten_modelle_sek"] = round(time.time() - _t0)
        if _sm.get("grund") or _sm.get("fehler"):
            print("SEITENMODELLE: " + (_sm.get("grund") or "FEHLER " + _sm["fehler"]) + " - Mapperwahl wie bisher", flush=True); SM.schreiben(w, _sm)
            wahl["seiten_modelle"] = dict(gerechnet=False, grund=_sm.get("grund") or _sm.get("fehler"), meldungen=_sm.get("meldungen")); _sm = None; _t0 = time.time()
        else: wahl["gewaehlt"] = "seiten_global"; _fertig = True
if NUR_NACHSTUFE and not _sm: raise SystemExit("NUR NACHSTUFE: kein Seitenmodell-Weg (Seiten nicht getrennt, abgeschaltet oder kein Teilmodell) - ein Mapper wuerde neu rechnen; bewusst neu: --neu sfm")
if NUR_NACHSTUFE: print("NUR NACHSTUFE: Seitenmodelle aus dem Zwischenstand - Vereinen, Tore und Einsetzen laufen mit dem aktuellen Code", flush=True)
if not _fertig and MAPPER in ("auto", "konsens"):                                         # 19.11.2026 (Nutzer 'Ja, mach es als Standard'): Konsens-Mapper zuerst
    ok_k = _konsens(f"{w}/sparse_konsens"); wahl["konsens_sek"] = round(time.time() - _t0); ku = _konsens_urteil(ok_k); wahl["konsens"] = ku
    print("Mapper konsens:", "ok" if ok_k else "FEHLGESCHLAGEN", wahl["konsens_sek"], "s, Rueckgrat", ku["rueckgrat"], "von", ku["gemeinsam"], "im Modell", ku["im_modell"], "von", ku["bilder"], flush=True)
    if ku["gruende"]:
        wahl["datenmangel"] = dict(gruende=ku["gruende"], ursachen=ku["ursachen"], abhilfe=ku["abhilfe"])
        print("ACHTUNG DATENMANGEL: Konsens-Mapper traegt nicht - " + "; ".join(ku["gruende"]) + " | URSACHE: " + "; ".join(ku["ursachen"]) + " | ABHILFE: " + ku["abhilfe"], flush=True)
    if ok_k and (MAPPER == "konsens" or not ku["gruende"]):
        shutil.rmtree(f"{w}/sparse", ignore_errors=True); os.rename(f"{w}/sparse_konsens", f"{w}/sparse"); wahl["gewaehlt"] = "konsens"; _fertig = True
    elif MAPPER == "konsens": raise SystemExit("Konsens-Mapper fehlgeschlagen (konsens.log)")
    else:
        print("ACHTUNG DATENMANGEL: weiche auf den alten Weg aus (globaler Lauf + GPS-Tor, sonst schrittweiser Mapper) - das dauert LAENGER und ist UNSICHERER; Ursache sind fehlende Daten, nicht die Methode", flush=True)
        wahl["datenmangel"]["folge"] = "Ausweichweg global+GPS-Tor/schrittweise (laenger, unsicherer)"; _t0 = time.time()
if _fertig: pass
elif MAPPER == "inkrementell": _inkrementell(f"{w}/sparse"); wahl["gewaehlt"] = "inkrementell"
else:
    # 20.11.2026 (Messung martinstor-1120): der Ausweichweg rechnete nach dem Konsens NOCHMAL einen globalen Lauf (51 min) - gleiches Verfahren wie Konsens-Lauf 1
    # (1681 Bilder / 31 Stuecke, Hauptstueck 817 gegen lauf1 1669 Bilder / Hauptstueck 825; Unterschied = Streuung des nicht deterministischen Mappers).
    # Liegt lauf1 aus DIESEM Aufruf vor, wird es als globaler Lauf uebernommen. RCPARK_GLOBAL_NEU=1 erzwingt den eigenen Lauf (alter Stand).
    _l1 = f"{w}/konsens_arbeit/lauf1/0"
    if os.environ.get("RCPARK_GLOBAL_NEU") != "1" and os.path.isfile(_l1 + "/images.bin") and os.path.getmtime(_l1 + "/images.bin") >= _t_anfang:
        shutil.rmtree(f"{w}/sparse_global", ignore_errors=True); os.makedirs(f"{w}/sparse_global"); shutil.copytree(_l1, f"{w}/sparse_global/0")
        wahl["global_aus"] = "konsens_lauf1"; print("Mapper global: Konsens-Lauf 1 uebernommen (kein dritter globaler Lauf)", flush=True); _global = lambda ziel: True
    ok_g = _global(f"{w}/sparse_global"); wahl["global_sek"] = round(time.time() - _t0); tg = _gps_tor(f"{w}/sparse_global/0") if ok_g else dict(n_gps=0, anteil_ueber_15m=None); wahl["tor_global"] = tg
    print("Mapper global:", "ok" if ok_g else "FEHLGESCHLAGEN", wahl["global_sek"], "s, GPS-Tor", tg, flush=True)
    besteht = ok_g and tg["n_gps"] >= 15 and tg["anteil_ueber_15m"] is not None and tg["anteil_ueber_15m"] <= 15   # ANNAHME Schwelle 15 % (Einzelmodell-Messung 15.11.: gutes Modell 12 % inkl. Ausreisserkameras, verwechselte 16 % und 26 %); Durchfall kostet nur Zeit (Vergleichslauf)
    if MAPPER == "global" or besteht:
        if not ok_g: raise SystemExit("globaler Mapper fehlgeschlagen (kalib.log/global.log)")
        shutil.rmtree(f"{w}/sparse", ignore_errors=True); os.rename(f"{w}/sparse_global", f"{w}/sparse"); wahl["gewaehlt"] = "global"
    else:
        _t1 = time.time(); _inkrementell(f"{w}/sparse_inkr"); wahl["inkrementell_sek"] = round(time.time() - _t1); ti = _gps_tor(f"{w}/sparse_inkr/0"); wahl["tor_inkrementell"] = ti
        print("Mapper schrittweise:", wahl["inkrementell_sek"], "s, GPS-Tor", ti, flush=True)
        g_besser = ok_g and tg["n_gps"] >= 15 and ti["anteil_ueber_15m"] is not None and tg["anteil_ueber_15m"] is not None and tg["anteil_ueber_15m"] < ti["anteil_ueber_15m"]
        nimm = "sparse_global" if g_besser else "sparse_inkr"; wahl["gewaehlt"] = "global" if g_besser else "inkrementell"
        wahl["hinweis"] = "kein Modell besteht das GPS-Tor (<= 15 % > 15 m) - Lage NICHT glauben" if tg["n_gps"] >= 15 else "zu wenig GPS-Fotos fuer ein Urteil - schrittweiser Mapper wie bisher"
        shutil.rmtree(f"{w}/sparse", ignore_errors=True); os.rename(f"{w}/{nimm}", f"{w}/sparse")
GB.belegen()
if _sm:                                                                   # SEITENMODELLE, Phase 2 (GPU): je Teil dichte Wolke, vereinen, Blick-Tor; Ergebnis -> sparse/0 (vereint oder Teil A allein)
    SM.dicht_vereinen(w, img, _e0["seiten_json"], _db_ursprung, _sm); _ok_sm = SM.einsetzen(w, _sm); SM.schreiben(w, _sm)
    if not _ok_sm: raise SystemExit("SEITENMODELLE: kein Ergebnismodell (seiten_modelle.json) - bewusst ohne diesen Weg: RCPARK_SEITEN_MODELLE=0")
    wahl["seiten_modelle"] = dict(gerechnet=True, art=_sm["ergebnis"]["art"], teil_a=_sm.get("teil_a"), vereint=_sm.get("vereint"), nicht_vereint=_sm.get("nicht_vereint"), fotoluecken=_sm.get("fotoluecken"), meldungen=_sm.get("meldungen"),
                                  dicht=_sm["ergebnis"].get("dicht"), bericht=os.path.join(w, "seiten_modelle.json"))
json.dump(wahl, open(os.path.join(w, "mapper_wahl.json"), "w"), indent=1); print("MAPPERWAHL", json.dumps(wahl), flush=True)
rec = {k: pycolmap.Reconstruction(os.path.join(f"{w}/sparse", k)) for k in sorted(os.listdir(f"{w}/sparse")) if k.isdigit()}
for k, r in rec.items(): print(k, r.summary(), flush=True)
# 21.11.2026: Modelle und Seiten MELDEN - die Kette verwendet nur sparse/0; fehlt dort ein Bildteil (Seite), darf das nicht still bleiben.
_reg = lambda r: {r.images[i].name for i in r.reg_image_ids()} if hasattr(r, "reg_image_ids") else {im.name for im in r.images.values()}
wahl["modelle"] = {k: len(_reg(r)) for k, r in rec.items()}
if len(rec) > 1: print(f"ACHTUNG {len(rec)} MODELLE: " + ", ".join(f"sparse/{k} {n} Bilder" for k, n in wahl["modelle"].items()) + " - die Kette verwendet nur sparse/0", flush=True)
if SEITEN != "0":
    _e = _seiten.get("erkennung") or {}
    if _e.get("db", "").endswith("db_seiten.db"):
        _e["im_modell"], _e["meldungen"] = SV.teile_im_modell(_e["seiten_json"], {k: _reg(r) for k, r in rec.items()})
        if _sm and len(_sm.get("vereint") or []) > 1:                     # vereinte Seiten stehen ABSICHTLICH ohne gemeinsame Punkte in sparse/0 (Lage aus seiten_vereinen, Blick-Tor bestanden)
            _e["meldungen"] = [m_ for m_ in _e["meldungen"] if "ohne echte Verbindung" not in m_]; _e["vereint"] = _sm["vereint"]
        print("SEITEN IM MODELL: " + "; ".join(f"Teil {t_['teil']} ({t_['bilder']} Bilder): " + ", ".join(f"sparse/{m} {n}" for m, n in t_["im_modell"].items()) for t_ in _e["im_modell"][:8]), flush=True)
        for m_ in _e["meldungen"]: print("ACHTUNG SEITE: " + m_, flush=True)
    wahl["seiten"] = _seiten
else: wahl["seiten"] = dict(abgeschaltet=True)
json.dump(wahl, open(os.path.join(w, "mapper_wahl.json"), "w"), indent=1)
