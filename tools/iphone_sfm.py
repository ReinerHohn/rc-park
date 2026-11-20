#!/usr/bin/env python3
"""iphone_sfm.py <bilderordner> <arbeitsordner> - COLMAP-SfM (pycolmap, SIFT-GPU, exhaustive, Mapper) fuer die iPhone-Fotos; GPU von Anfang an (Nutzerregel).
  /media/oem/scan/venv-colmap/bin/python -I tools/iphone_sfm.py <bilderordner> <arbeitsordner> [--mapper auto|auto_alt|global|inkrementell|konsens] [--flexglue]
  (oder `tools/py col tools/iphone_sfm.py ...`; ohne 'col' waehlt tools/py venv-seg, dort fehlt pycolmap). RCPARK_FLEXGLUE=1 wie --flexglue. Defekte Bilder vorher nach quarantaene/ (fotos_pruefen.py).
Ausgaben in <arbeitsordner>: db.db, paare.txt (ab > 300 Bildern), sparse/<n>/ (COLMAP-Modelle), mapper_wahl.json (Mapperwahl + GPS-Tor).
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
so = pycolmap.FeatureExtractionOptions(); so.sift.max_num_features = 6400; so.max_image_size = 2400
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
if _db_ok:
    print(f"Merkmale und Paare aus Cache ({_ni} Bilder, {_nm} Paare)", flush=True)
else:
    pycolmap.extract_features(db, img, camera_mode=pycolmap.CameraMode.PER_IMAGE, extraction_options=so, device=pycolmap.Device.cuda); print("Merkmale", time.time() - t, flush=True)
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
def _inkrementell(ziel):
    os.makedirs(ziel, exist_ok=True)
    subprocess.run([COLMAP_BIN, "mapper", "--database_path", db, "--image_path", img, "--output_path", ziel,
                    "--Mapper.num_threads", "1", "--Mapper.ba_use_gpu", "1", "--Mapper.ba_gpu_index", "0", "--Mapper.ba_max_num_images_direct_dense_gpu_solver", "0"], env=_env, check=True)
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
    g, u, ab = GK.urteil(kj, len(namen), len(clips), lief)
    return dict(bilder=len(namen), videoclips=len(clips), rueckgrat=(kj or {}).get("schnitt", {}).get("stabil"), gemeinsam=(kj or {}).get("schnitt", {}).get("gemeinsam"),
                im_modell=(kj or {}).get("bewertung", {}).get("n_reg"), gruende=g, ursachen=u, abhilfe=ab)
def _global(ziel):
    dbg = db + ".global.db"; shutil.copyfile(db, dbg); os.makedirs(ziel, exist_ok=True)       # Kalibrierung aendert Intrinsik/Zweibild-Geometrien in der DB -> nur auf der Kopie
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
if MAPPER in ("auto", "konsens"):                                         # 19.11.2026 (Nutzer 'Ja, mach es als Standard'): Konsens-Mapper zuerst
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
json.dump(wahl, open(os.path.join(w, "mapper_wahl.json"), "w"), indent=1); print("MAPPERWAHL", json.dumps(wahl), flush=True)
rec = {k: pycolmap.Reconstruction(os.path.join(f"{w}/sparse", k)) for k in sorted(os.listdir(f"{w}/sparse")) if k.isdigit()}
for k, r in rec.items(): print(k, r.summary(), flush=True)
