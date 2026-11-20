#!/usr/bin/env python3
"""sfm_netz.py - GENERISCH: SfM-Netz je Fassadenseite bauen, bewerten und reparieren (Lehren aus Martinstor, Register AH/AI).

Warum ein eigenes Werkzeug statt 'COLMAP ueber alles':
  1. Symmetrische Bauwerke: Fotos gegenueberliegender Seiten duerfen NICHT zusammen gematcht werden (COLMAP verklebt gleiche Fassaden).
     -> Fotoliste je Seite aus objekt.json["sfm"][<seite>] (Seite vorher per Sichtkriterium bestimmt und eingetragen).
  2. Verkleinern MIT EXIF; Brennweiten-Prior aus EXIF (f35 oder Modell-Sensorbreite), bezogen auf die LANGE Bildseite.
  3. Qualitaetsschranken je Kamera NACH dem Aufbau: Brennweite gegen EXIF-Prior (Faktor), Brennweite gegen Bilddiagonale,
     Punktzahl, Lage weit ausserhalb, Punkte hinter der Kamera (Cheiralitaet > 20 % = Spiegelloesung, Register BB) -> 'degeneriert'. Mit --reparieren werden degenerierte Kameras entfernt und neu gebaut
     (max. 3 Runden); Fernaufnahmen (Brennweite > 3 x Bilddiagonale) werden erst gar nicht in den Erstaufbau genommen,
     sondern danach registriert (sie tragen keine Basis bei, verderben aber die Brennweitenschaetzung).
  4. Bericht als JSON (sfm/netz_<seite>.json): je Kamera f, Prior, Verhaeltnis, Punkte, Status; Netzkennzahlen.
  /media/oem/scan/venv-colmap/bin/python -I tools/sfm_netz.py modelle/<objekt>/objekt.json <seite> [--fotos 001 002 ...]
        [--reparieren] [--maxpx 2000] [--fern-faktor 3.0]
Danach: tools/sfm_ausrichten.py ... --sparse modelle/<objekt>/sfm/sparse_<seite>/0
Weitere Optionen: --matcher sift|lightglue|hybrid, --kamera-modell, --kamera-gruppen, --cpu, --ba-gpu, --nur-merkmale, --db-von, --tag <suffix>.
Ausgaben unter modelle/<objekt>/sfm/: db_<seite>.db, sparse_<seite>/<n>/, netz_<seite>.json (mit --tag je Versuch eigener Suffix).
Umgebung: pycolmap -> venv-colmap (s.o.; `tools/py tools/sfm_netz.py ...` waehlt sie ebenfalls). Ohne Fotoliste Abbruch mit Text.
"""
import sys, os, json, time, glob, sqlite3, argparse, shutil, numpy as np
from PIL import Image, ExifTags
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pycolmap

T = {v: k for k, v in ExifTags.TAGS.items()}
SENSOR_MM = {"Canon EOS 1000D": 22.2, "Canon EOS 5D Mark II": 36.0, "PENTAX Optio 50L": 5.76, "DSC-W5": 7.18, "NIKON D7000": 23.6,
             "Canon PowerShot A650 IS": 7.6, "PENTAX K-5": 23.7, "DSC-S500": 5.76, "Canon EOS 5D": 36.0, "Canon EOS 6D": 36.0, "NIKON D90": 23.6,
             "Canon EOS 400D DIGITAL": 22.2, "Canon EOS 450D": 22.2, "Canon EOS 550D": 22.3, "Canon EOS 600D": 22.3, "Canon EOS 7D": 22.3,
             "NIKON D7100": 23.5, "NIKON D5100": 23.6, "NIKON D3100": 23.1, "DMC-TZ10": 6.08, "DMC-TZ7": 6.08, "Canon PowerShot G12": 7.44}

SENSOR_MM.update({"ILCE-6000": 23.5, "NIKON D3200": 23.2, "EX-Z40": 5.76, "NIKON D750": 35.9, "ILCE-7": 35.8, "Canon EOS 70D": 22.5, "Canon EOS 80D": 22.3})

def exif_f_px(im, manifest_eintrag=None):
    """Brennweite in Pixeln der LANGEN Bildseite: aus EXIF der Datei, sonst aus dem Manifest (Commons-API-Metadaten -
    verkleinerte Commons-Downloads tragen kein EXIF mehr)."""
    ex = im.getexif(); exi = ex.get_ifd(0x8769); model = str(ex.get(T["Model"], "")).strip()
    f35 = exi.get(T["FocalLengthIn35mmFilm"]); fmm = exi.get(T["FocalLength"]); L = max(im.size); q = "EXIF"
    if not (f35 or fmm) and manifest_eintrag:
        model = manifest_eintrag.get("exif_model") or ""; f35 = manifest_eintrag.get("exif_f35"); fmm = manifest_eintrag.get("exif_f_mm"); q = "Manifest"
    if f35: return float(f35) * float(np.hypot(*im.size)) / 43.27, f"{q} f35={f35} (Diagonale)"   # 2026-11-04: f35 gilt fuer die DIAGONALE (vorher /36 x Langseite, 4-15 % falsch)
    if fmm and model in SENSOR_MM: return float(fmm) / SENSOR_MM[model] * L, f"{q} {model} {float(fmm):.1f} mm / {SENSOR_MM[model]} mm"
    return None, (f"{model} {fmm} mm ohne Sensorbreite" if fmm else "kein EXIF")

def manifest_laden(root, obj):
    try:
        M = json.load(open(os.path.join(root, obj["fotos_dir"], "manifest.json")))["images"]; return {m["file"][:3]: m for m in M}
    except Exception: return {}

def kamera_gruppen(root, obj, nrs, fallback=True):
    """Automatische Kameragruppen (Plan 2.1, Nutzerregel 'alles vollautomatisch'): Fotos mit gleicher Kamera UND Brennweite UND Bildgroesse bekommen EINE gemeinsame
    Kamera (Intrinsik) statt je Bild eine eigene. Schluessel aus der EXIF-Datei IM FOTO (Make, Model, FocalLength, FocalLengthIn35mm, Bildgroesse), nicht aus dem Manifest.
    Verschiedene Zoomstufen haben verschiedene FocalLength und landen deshalb in verschiedenen Gruppen. Ausschnitt-Fotos (sfm_ausschnitt) und Fotos ohne Modell/Brennweite
    bleiben einzeln; Gruppen mit nur 1 Foto entfallen. GRENZE: gleiche EXIF-Brennweite heisst nicht gleiche Verzeichnung bei Smartphone-Computational-Fotografie (ANNAHME)."""
    import collections; from PIL import Image
    key = {}
    for nr in nrs:
        if obj.get("fotos", {}).get(nr, {}).get("sfm_ausschnitt"): continue
        try:
            im = Image.open(glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]); ex = im.getexif(); sub = ex.get_ifd(0x8769)
            make, model, fl, f35 = ex.get(0x010F), ex.get(0x0110), sub.get(0x920A), sub.get(0xA405)
        except Exception: continue
        if not model or not (fl or f35): continue
        key[nr] = (str(make or "").strip(), str(model).strip(), round(float(fl), 2) if fl else None, int(f35) if f35 else None, im.size)
    if fallback:      # M7 FALLBACK (ANNAHME): EXIF-Datei leer (Commons-Downsizes) -> Manifest (exif_model, exif_f_mm, exif_f35, w x h) + Dateiname-SERIE (Datum + Titelanfang = gleiche Aufnahmesitzung)
        import re; MF = manifest_laden(root, obj)
        for nr in nrs:
            if nr in key or obj.get("fotos", {}).get(nr, {}).get("sfm_ausschnitt"): continue
            m = MF.get(nr) or {}; model = m.get("exif_model")
            if not model or not m.get("w"): continue
            toks = [t for t in re.split(r"[_\-\s]+", re.sub(r"\.[A-Za-z]+$", "", m.get("file", "")[4:])) if t and not re.fullmatch(r"\d{1,3}", t)][:5]
            if len(toks) < 3: continue      # Serie nicht erkennbar -> einzeln lassen
            key[nr] = ("FALLBACK-Manifest/Dateiname", str(model).strip(), m.get("exif_f_mm"), m.get("exif_f35"), (m.get("w"), m.get("h")), "_".join(toks).lower())
    n = collections.Counter(key.values()); return {nr: k for nr, k in key.items() if n[k] >= 2}

def gruppen_in_db(db, gruppen):
    """Legt die Kameras je Gruppe zusammen (COLMAP >= 3.12: Kamera + Rig + Frame + frame_data je Bild, SENSOR_TYPE_CAMERA = 0). Gibt {schluessel: [namen]} zurueck."""
    con = sqlite3.connect(db); cur = con.cursor(); cur.execute("pragma foreign_keys=on")
    img = {n: c for n, c in cur.execute("select name, camera_id from images")}; by = {}
    for nr, k in gruppen.items():
        if nr + ".jpg" in img: by.setdefault(k, []).append(nr + ".jpg")
    erg = {}
    for k, names in by.items():
        if len(names) < 2: continue
        names.sort(); m = img[names[0]]; rig_m = cur.execute("select rig_id from rigs where ref_sensor_id=? and ref_sensor_type=0", (m,)).fetchone()[0]
        for n in names[1:]:
            c = img[n]
            if c == m: continue
            rig_o = cur.execute("select rig_id from rigs where ref_sensor_id=? and ref_sensor_type=0", (c,)).fetchone()[0]
            cur.execute("update frames set rig_id=? where rig_id=?", (rig_m, rig_o))
            cur.execute("update frame_data set sensor_id=? where sensor_id=? and sensor_type=0", (m, c))
            cur.execute("update images set camera_id=? where camera_id=?", (m, c))
            cur.execute("delete from rigs where rig_id=?", (rig_o,)); cur.execute("delete from cameras where camera_id=?", (c,))
        erg[str(k)] = names
    con.commit(); con.close(); return erg

def vorbereiten(root, obj, nrs, bilder, maxpx):
    os.makedirs(bilder, exist_ok=True); prior = {}; info = {}; MF = manifest_laden(root, obj)
    for nr in nrs:
        p = glob.glob(os.path.join(root, obj["fotos_dir"], nr + "_*"))[0]; im = Image.open(p); im = im.convert("RGB") if im.mode != "RGB" else im
        # Brennweite (2026-11-04, Lernregister 1): zuerst exif_brennweite.py (f35 auf die Diagonale, beschnittfest ueber FocalPlaneXResolution, Sensor-DB),
        # erst dann die alte Manifest-/Tabellen-Variante (verkleinerte Commons-Downloads ohne EXIF)
        import exif_brennweite as EB
        fpx, grund = EB.brennweite_px(p, im.size[0], im.size[1])
        if not fpx: fpx, grund = exif_f_px(im, MF.get(nr))
        s = min(1.0, maxpx / max(im.size)); W0, H0 = im.size; x0 = y0 = 0
        if fpx is None and obj.get("fotos", {}).get(nr, {}).get("brennweite_px"):     # dritte Quelle: objekt.json (f_gruppe, aus anderem Netz uebertragen)
            fpx = float(obj["fotos"][nr]["brennweite_px"]); grund = "objekt.json: " + obj["fotos"][nr].get("brennweite_quelle", "brennweite_px")[:60]
        aus = obj.get("fotos", {}).get(nr, {}).get("sfm_ausschnitt")
        if aus:   # Turmbereich in voller Aufloesung (ggf. vergroessert): Hauptpunkt wandert mit, Brennweite skaliert mit zoom
            x0, y0, w, h = aus["xywh"]; s = float(aus.get("zoom", 1.0)); im = im.crop((x0, y0, x0 + w, y0 + h))
        im2 = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS) if s != 1 else im
        kw = {"exif": im.info["exif"]} if "exif" in im.info else {}
        im2.save(os.path.join(bilder, nr + ".jpg"), quality=95, **kw)
        if fpx: prior[nr + ".jpg"] = fpx * s
        pp = ((W0 / 2 - x0) * s, (H0 / 2 - y0) * s) if aus else None
        if pp: prior[nr + ".jpg:pp"] = pp
        info[nr] = dict(orig=[W0, H0], sfm=[im2.width, im2.height], prior_f_px=(fpx * s if fpx else None), prior_grund=grund, ausschnitt=([x0, y0, s] if aus else None))
    return prior, info

LG_PYTHON = "/media/oem/scan/venv-seg/bin/python"       # torch-Umgebung fuer tools/lg_match.py (LightGlue + ALIKED)

def lightglue_in_db(db, tmp, nrs, extractor, max_kp, resize, nur_fotos=None, anhaengen=False):
    """SIFT-Merkmale/Matches durch ALIKED+LightGlue ersetzen (Lizenzen: Apache-2.0 / BSD-3, siehe modelle/LIZENZ_WERKZEUGE.md),
    dann geometrische Verifikation durch COLMAP. Rohschema: keypoints float32 Nx2, descriptors uint8 Nx128 (Platzhalter), matches uint32 Mx2."""
    import subprocess
    npz = os.path.join(os.path.dirname(db), f"lg_{os.path.basename(db)[3:-3]}.npz"); tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lg_match.py")
    cmd = [LG_PYTHON, "-I", tool, tmp, npz, "--namen"] + [nr + ".jpg" for nr in nrs] + ["--extractor", extractor, "--max-kp", str(max_kp), "--resize", str(resize)]
    print("  LightGlue:", " ".join(cmd[2:5]), "...", flush=True); subprocess.run(cmd, check=True)
    Z = np.load(npz, allow_pickle=True); con = sqlite3.connect(db); cur = con.cursor()
    ids = {name: iid for iid, name in cur.execute("select image_id, name from images")}
    typ = cur.execute("select sql from sqlite_master where name='descriptors'").fetchone()[0]
    offset = {}
    if anhaengen:
        # HYBRID: SIFT-Merkmale und -Matches bleiben; ALIKED-Merkmale werden je Bild ANGEHAENGT (Index-Versatz), Matches nur fuer Paare mit nur_fotos
        for name, iid in ids.items():
            row = cur.execute("select rows, cols, data from keypoints where image_id=?", (iid,)).fetchone()
            n0, cols, data = (row if row else (0, 2, b"")); alt = np.frombuffer(data, np.float32).reshape(n0, cols) if n0 else np.zeros((0, cols), np.float32)
            kp = Z["kp_" + name].astype(np.float32)
            neu = np.zeros((kp.shape[0], cols), np.float32); neu[:, :2] = kp
            if cols >= 6: neu[:, 2] = 1.0; neu[:, 5] = 1.0                    # affine Form (x, y, a11, a12, a21, a22): Einheitsmatrix
            elif cols == 4: neu[:, 2] = 1.0                                    # (x, y, scale, orientation)
            allk = np.vstack([alt, neu]); offset[name] = n0
            cur.execute("delete from keypoints where image_id=?", (iid,)); cur.execute("insert into keypoints (image_id, rows, cols, data) values (?,?,?,?)", (iid, allk.shape[0], cols, allk.tobytes()))
            d = cur.execute("select rows, cols, data from descriptors where image_id=?", (iid,)).fetchone()
            dalt = np.frombuffer(d[2], np.uint8).reshape(d[0], d[1]) if d and d[0] else np.zeros((0, 128), np.uint8)
            dall = np.vstack([dalt, np.zeros((kp.shape[0], dalt.shape[1] if dalt.shape[0] else 128), np.uint8)])
            cur.execute("delete from descriptors where image_id=?", (iid,))
            if "type" in typ: cur.execute("insert into descriptors (image_id, type, rows, cols, data) values (?,?,?,?,?)", (iid, 0, dall.shape[0], dall.shape[1], dall.tobytes()))
            else: cur.execute("insert into descriptors (image_id, rows, cols, data) values (?,?,?,?)", (iid, dall.shape[0], dall.shape[1], dall.tobytes()))
    else:
        for t in ("keypoints", "descriptors", "matches", "two_view_geometries"): cur.execute(f"delete from {t}")
        for name, iid in ids.items():
            kp = Z["kp_" + name].astype(np.float32); cur.execute("insert into keypoints (image_id, rows, cols, data) values (?,?,?,?)", (iid, kp.shape[0], 2, kp.tobytes())); offset[name] = 0
            if "type" in typ: cur.execute("insert into descriptors (image_id, type, rows, cols, data) values (?,?,?,?,?)", (iid, 0, kp.shape[0], 128, np.zeros((kp.shape[0], 128), np.uint8).tobytes()))
            else: cur.execute("insert into descriptors (image_id, rows, cols, data) values (?,?,?,?)", (iid, kp.shape[0], 128, np.zeros((kp.shape[0], 128), np.uint8).tobytes()))
    paare = []; nur = set((nur_fotos or []))
    for key in Z.files:
        if not key.startswith("m_"): continue
        a, b = key[2:].split("|")
        if nur and a[:-4] not in nur and b[:-4] not in nur: continue
        ia, ib = ids[a], ids[b]; m = Z[key].astype(np.uint32) + np.array([offset[a], offset[b]], np.uint32)
        if ia > ib: ia, ib = ib, ia; m = m[:, ::-1].copy()
        pid = int(pycolmap.image_pair_to_pair_id(ia, ib))
        if anhaengen:   # vorhandene SIFT-Matches des Paares behalten und ALIKED-Matches anhaengen; Verifikation danach fuer beide zusammen
            alt = cur.execute("select rows, data from matches where pair_id=?", (pid,)).fetchone()
            if alt and alt[0]: m = np.vstack([np.frombuffer(alt[1], np.uint32).reshape(alt[0], 2), m])
        cur.execute("delete from matches where pair_id=?", (pid,)); cur.execute("delete from two_view_geometries where pair_id=?", (pid,))
        cur.execute("insert into matches (pair_id, rows, cols, data) values (?,?,?,?)", (pid, m.shape[0], 2, m.tobytes())); paare.append(f"{a} {b}")
    con.commit(); con.close()
    pf = npz[:-4] + "_paare.txt"; open(pf, "w").write("\n".join(paare) + "\n")
    pycolmap.verify_matches(db, pf)
    con = sqlite3.connect(db); n = con.execute("select count(*) from two_view_geometries where rows >= 15").fetchone()[0]; con.close()
    print(f"  LightGlue: {len(paare)} Paare mit Matches, {n} geometrisch verifiziert (>= 15 Inlier)", flush=True)

NUR_CPU = False
MATCH_THREADS = 1      # 1 = reproduzierbar (Register CA); 0 = alle Kerne
PRIOR_TOL = 0.15       # Brennweiten-Prior nur festhalten, wenn der Mapper ihn auf +-15 % bestaetigt (wie EXIF-Pruefdurchgang sfm_lod2_buendel.py)
KAMERA_MODELL = "SIMPLE_RADIAL"
GRUPPEN = {}      # {nr: schluessel} aus kamera_gruppen (--kamera-gruppen); leer = je Bild eine Kamera (Standard, bisheriges Verhalten)
def _merkmale_und_matches(db, tmp, nrs, prior, matcher, lg):
    _ro = pycolmap.ImageReaderOptions(); _ro.camera_model = KAMERA_MODELL                 # SIMPLE_RADIAL (Standard) | RADIAL | OPENCV (--kamera-modell)
    if NUR_CPU: pycolmap.extract_features(db, tmp, camera_mode=pycolmap.CameraMode.PER_IMAGE, reader_options=_ro, device=pycolmap.Device.cpu)   # --cpu: GPU frei lassen (Suednetz parallel zum dichten Schritt)
    else: pycolmap.extract_features(db, tmp, camera_mode=pycolmap.CameraMode.PER_IMAGE, reader_options=_ro)
    # GPU-Rueckfall: scheitert SIFT-GPU (z. B. 'illegal memory access', wenn ein anderer Prozess die GPU belegt), bleiben Bilder ohne Merkmale
    # -> Datenbank neu und auf der CPU extrahieren/zuordnen (langsamer, gleiches Ergebnis in der Geometrie). Nullstart 3, Register BA.
    _gpu_ok = True
    try:
        if NUR_CPU: raise StopIteration
        _c = sqlite3.connect(db); _n_img = _c.execute("select count(*) from images").fetchone()[0]; _n_kp = _c.execute("select count(*) from keypoints where rows > 0").fetchone()[0]; _c.close()
        _gpu_ok = _n_img > 0 and _n_kp >= 0.8 * _n_img
    except StopIteration: _gpu_ok = False
    except Exception: _gpu_ok = False
    if not _gpu_ok and not NUR_CPU:
        print(f"   SIFT-GPU: nur {_n_kp if '_n_kp' in dir() else '?'} von {_n_img if '_n_img' in dir() else '?'} Bildern mit Merkmalen - Rueckfall auf CPU")
        os.remove(db); pycolmap.extract_features(db, tmp, camera_mode=pycolmap.CameraMode.PER_IMAGE, reader_options=_ro, device=pycolmap.Device.cpu)
    con = sqlite3.connect(db); cur = con.cursor()
    for img_id, name, cam_id in cur.execute("select image_id, name, camera_id from images").fetchall():
        if name not in prior and name + ":pp" not in prior: continue
        params = cur.execute("select params from cameras where camera_id=?", (cam_id,)).fetchone()[0]
        par = np.frombuffer(params, dtype=np.float64).copy()
        if name in prior: par[0] = prior[name]
        if name + ":pp" in prior: par[1], par[2] = prior[name + ":pp"]           # Hauptpunkt des Ausschnitts (bleibt fest: ba_refine_principal_point=False)
        cur.execute("update cameras set params=?, prior_focal_length=? where camera_id=?", (par.tobytes(), 1 if name in prior else 0, cam_id))
    con.commit(); con.close()
    if GRUPPEN:
        _g = gruppen_in_db(db, GRUPPEN); print(f"   Kameragruppen: {sum(len(v) for v in _g.values())} Bilder in {len(_g)} gemeinsamen Kameras", flush=True)
    if matcher == "lightglue": lightglue_in_db(db, tmp, nrs, "aliked", lg[0], lg[1])
    elif matcher == "hybrid":
        pycolmap.match_exhaustive(db)                                            # SIFT fuer alles (bewaehrte Geometrie der Strassenfotos)
        lightglue_in_db(db, tmp, nrs, "aliked", lg[0], lg[1], nur_fotos=lg[2], anhaengen=True)   # LightGlue nur fuer Paare mit den schwierigen Fotos
    else:
        mo = pycolmap.FeatureMatchingOptions(); mo.num_threads = MATCH_THREADS; vo = pycolmap.TwoViewGeometryOptions(); vo.ransac.random_seed = 0          # Register CA: Mehrfaden-RANSAC macht two_view_geometries bei jedem Lauf anders
        pycolmap.match_exhaustive(db, matching_options=mo, verification_options=vo, device=(pycolmap.Device.auto if _gpu_ok else pycolmap.Device.cpu))

def bauen(bilder, db, aus, nrs, prior, matcher="sift", lg=(4096, 2048), nur_merkmale=False, db_wieder=False, seed=None, threads=0, mapper="incremental", ba_gpu=False):
    """db_wieder: vorhandene Datenbank (Merkmale + Matches) nur fuer die Rekonstruktion nutzen; nur_merkmale: nach dem Matching aufhoeren;
    seed/threads: der COLMAP-Mapper ist nicht deterministisch (Register BF) - parallele Versuche mit eigenem Seed."""
    if db_wieder and not os.path.exists(db): db_wieder = False
    if os.path.exists(db) and not db_wieder: os.remove(db)
    shutil.rmtree(aus, ignore_errors=True); os.makedirs(aus, exist_ok=True)
    # nur die gewuenschten Bilder: eigener Ordner mit Links
    tmp = aus + "_bilder"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    for nr in nrs: os.symlink(os.path.abspath(os.path.join(bilder, nr + ".jpg")), os.path.join(tmp, nr + ".jpg"))
    if not db_wieder:
        pycolmap.set_random_seed(0)      # RANSAC der geometrischen Verifikation (verify_matches/match_exhaustive) ist sonst bei jedem Lauf anders (Register CA: two_view_geometries 80398 vs 80450 Zeilen)
        _merkmale_und_matches(db, tmp, nrs, prior, matcher, lg)
    if nur_merkmale: return None, tmp
    opt = pycolmap.IncrementalPipelineOptions(); opt.min_focal_length_ratio = 0.4; opt.max_focal_length_ratio = 3.5   # Standard 0,1..10 liess f = 10865 x Diagonale zu
    if seed is not None: opt.random_seed = int(seed)
    if threads: opt.num_threads = int(threads)
    if ba_gpu: opt.ba_use_gpu = True; opt.ba_gpu_index = "0"          # Buendelausgleich (Ceres) auf der GPU; nur EIN Mapper zur Zeit (Register AY/BA), Messung Register/Versuchslog colmap-ba-gpu
    if mapper == "global":                                                    # GLOMAP (in pycolmap >= 4): alle Kameras gemeinsam, kein Aufbau-Reihenfolge-Zufall
        gp = pycolmap.GlobalPipelineOptions()
        if seed is not None:
            try: gp.random_seed = int(seed)
            except Exception: pass
        if threads: gp.num_threads = int(threads)
        karten = pycolmap.global_mapping(db, tmp, aus, options=gp)
    else: karten = pycolmap.incremental_mapping(db, tmp, aus, options=opt)
    if not karten: return None, tmp
    k = max(karten.values(), key=lambda r: r.num_reg_images())
    # EXIF-Brennweiten FESTHALTEN (auf den Prior zuruecksetzen, Intrinsics dieser Kameras konstant), die WEICHE Freigabe macht erst sfm_lod2_buendel.py
    # (EXIF-Prior sigma 5 %, Pruefdurchgang). 2026-11-04 getestet: COLMAP-BA kennt keinen weichen Prior - mit FREIEN Intrinsics kollabierte das
    # Martinstor-Suednetz in 6 von 6 Seeds (Brennweite gegen Tiefe bei Telefotos, Turm flachgedrueckt, Pick-Massstab +-50..100 %).
    # Geaendert bleibt: der Prior selbst ist jetzt richtig (exif_brennweite.py: Diagonale, FocalPlane beschnittfest) statt f35/36 x Langseite.
    # PRUEFUNG vor dem Festhalten (2026-11-04, kaufhaus_null2): der Mapper verfeinert f frei vom Prior aus - weicht er > PRIOR_TOL ab, widersprechen die
    # Bilder dem EXIF (verkleinerte Panoramio-Bilder 124/125: FocalPlaneXResolution gilt fuer den Originalsensor -> 2904 statt ~1000 px; Beschnitt 065:
    # f35 2948 statt ~1400 px). Festhalten auf so einem Prior verbog das Netz (33 Punkte hinter Kameras, p90 17,7 px) und liess den Buendelausgleich
    # divergieren. Widersprochene Priors bleiben frei (Mapper-Wert), Bericht <aus>_prior_pruefung.json. Gleiche Schwelle wie der EXIF-Pruefdurchgang im Buendel.
    fix = []; pruef = {}
    for im in k.images.values():
        if im.name in prior:
            c = k.cameras[im.camera_id]; p = list(c.params); v = float(p[0]) / float(prior[im.name])
            ok = abs(np.log(v)) <= np.log(1 + PRIOR_TOL); pruef[im.name] = dict(f_mapper_px=round(float(p[0]), 1), f_prior_px=round(float(prior[im.name]), 1), verhaeltnis=round(v, 3), festgehalten=bool(ok))
            if not ok: continue
            p[0] = prior[im.name]; c.params = p; fix.append(c.camera_id)
    weg = {n: d["verhaeltnis"] for n, d in pruef.items() if not d["festgehalten"]}
    if pruef: json.dump(dict(toleranz=PRIOR_TOL, kameras=pruef, verworfen=sorted(weg)), open(aus + "_prior_pruefung.json", "w"), indent=1)
    print(f"   Prior-Pruefung: {len(pruef) - len(weg)} von {len(pruef)} Brennweiten-Priors bestaetigt und festgehalten, verworfen (Mapper/Prior): {weg}", flush=True)
    if fix:
        cfg = pycolmap.BundleAdjustmentConfig()
        for im in k.images.values():
            if im.has_pose: cfg.add_image(im.image_id)
        for cid in set(fix): cfg.set_constant_cam_intrinsics(cid)
        for pid in list(k.points3D.keys()): cfg.add_variable_point(pid)
        bo = pycolmap.BundleAdjustmentOptions(); bo.refine_focal_length = True; bo.refine_extra_params = True; bo.refine_principal_point = False
        pycolmap.create_default_bundle_adjuster(bo, cfg, k).solve(); k.write(aus + "/0")
    return k, tmp

def tiefen(rec, im):
    """Tiefen (z im Kamerasystem) aller 3D-Punkte eines registrierten Bildes. Cheiralitaet: ein richtig gesetztes Bild sieht seine
    Punkte VOR sich (z > 0). Liegen sie dahinter, ist die Pose eine Spiegelloesung (Nullstart 5: fuenf Ultraweitwinkel-Fotos mit
    EXIF-Prior, alle Punkte z < 0; PatchMatch bricht dann ohne Tiefenbereich ab)."""
    P = np.array([rec.points3D[p.point3D_id].xyz for p in im.points2D if p.has_point3D()])
    return (im.cam_from_world() * P)[:, 2] if len(P) else np.zeros(0)

def bewerten(rec, info, prior, fern_faktor):
    """je Kamera: Status ok / degeneriert (Grund)."""
    rows = {}
    for im in rec.images.values():
        if not im.has_pose: continue                      # nach deregister_frame bleibt das Bild im Objekt, aber ohne Pose
        nr = os.path.splitext(im.name)[0]; c = rec.cameras[im.camera_id]; f = float(c.params[0]); diag = float(np.hypot(c.width, c.height))
        pr = prior.get(im.name); grund = []
        d = tiefen(rec, im); hinter = float((d <= 0).mean()) if len(d) else 1.0
        if hinter > 0.2: grund.append(f"{hinter:.0%} der Punkte hinter der Kamera (Spiegelloesung)")
        if pr and not (0.7 <= f / pr <= 1.4): grund.append(f"f/EXIF = {f / pr:.2f}")
        if f > 4.0 * diag and not pr: grund.append(f"f = {f / diag:.1f} x Diagonale (Fernaufnahme/degeneriert)")   # mit EXIF-Prior ist eine lange Brennweite kein Fehler
        if f < 0.3 * diag: grund.append(f"f = {f / diag:.2f} x Diagonale (unplausibel weit)")
        if im.num_points3D < (25 if pr else 40): grund.append(f"nur {im.num_points3D} Punkte")   # Fern-/Luftbilder mit EXIF-Prior: 25 reichen
        rows[nr] = dict(f_px=round(f, 1), prior_f_px=(round(pr, 1) if pr else None), f_zu_prior=(round(f / pr, 3) if pr else None), f_zu_diag=round(f / diag, 3),
                        punkte=int(im.num_points3D), hinter_kamera=round(hinter, 3), status="ok" if not grund else "degeneriert", grund=grund)
    return rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("objekt"); ap.add_argument("seite"); ap.add_argument("--fotos", nargs="*")
    ap.add_argument("--kamera-modell", default="SIMPLE_RADIAL", choices=["SIMPLE_RADIAL", "RADIAL", "OPENCV", "SIMPLE_PINHOLE", "PINHOLE"], help="COLMAP-Kameramodell (Suednetz: projektive Verbiegung -> RADIAL/OPENCV testen, Register AI)"); ap.add_argument("--reparieren", action="store_true"); ap.add_argument("--maxpx", type=int, default=2000); ap.add_argument("--fern-faktor", type=float, default=3.0)
    ap.add_argument("--matcher", default="sift", choices=["sift", "lightglue", "hybrid"], help="lightglue = ALIKED+LightGlue fuer alles; hybrid = SIFT fuer alles + LightGlue nur fuer Paare mit --lg-fotos (Register AK)")
    ap.add_argument("--lg-fotos", nargs="*", default=[], help="hybrid: Fotos, deren Paare per LightGlue gematcht werden (z. B. Luftbilder)")
    ap.add_argument("--lg-max-kp", type=int, default=4096); ap.add_argument("--lg-resize", type=int, default=2048)
    ap.add_argument("--kein-gruppen-fallback", action="store_true", help="mit --kamera-gruppen: NUR EXIF-Datei, kein Fallback ueber Manifest/Dateiname (ANNAHME gleicher Zoom)")
    ap.add_argument("--kamera-gruppen", action="store_true", help="gemeinsame Kamera je (Modell, Brennweite, Bildgroesse) aus der EXIF-Datei statt je Bild eine eigene (Plan 2.1)")
    ap.add_argument("--cpu", action="store_true", help="Merkmale und Matching auf der CPU (laesst die GPU frei)"); ap.add_argument("--mapper", default="incremental", choices=["incremental", "global"], help="incremental (Standard) | global = GLOMAP")
    ap.add_argument("--ba-gpu", action="store_true", help="Buendelausgleich (Ceres) auf der GPU - GPU rechnet erst ab 50 registrierten Bildern und nur im globalen BA. Messung 2026-11-04 Kaufhaus ~100 Bilder: KEIN Gewinn (Mapper 207-212 s GPU vs 195 s CPU ungestoert, Guete gleich); CASPAR ist im inkrementellen Mapper von COLMAP gesperrt. Nur fuer grosse Netze erneut messen")
    ap.add_argument("--nur-merkmale", action="store_true", help="nur Merkmale + Matches in db_<seite>.db rechnen (GPU), keine Rekonstruktion")
    ap.add_argument("--db-von", help="vorhandene db_<seite>.db kopieren und nur die Rekonstruktion rechnen (parallele Versuche, CPU)"); ap.add_argument("--seed", type=int, help="Mapper-Seed (Versuch)")
    ap.add_argument("--tag", default="", help="Suffix fuer db/sparse/netz-Bericht eines Versuchs, z. B. v1"); ap.add_argument("--threads", type=int, default=0, help="Mapper-Threads je Versuch (0 = COLMAP-Standard)")
    a = ap.parse_args(); global KAMERA_MODELL, NUR_CPU; KAMERA_MODELL = a.kamera_modell; NUR_CPU = a.cpu; obj = json.load(open(a.objekt)); od = os.path.dirname(os.path.abspath(a.objekt)); root = os.path.dirname(os.path.dirname(od))
    if a.cpu and a.mapper == 'global' and not a.db_von: print('WARNUNG: GLOMAP mit CPU-SIFT-Datenbank lieferte in 6 von 6 Versuchen unbrauchbare Netze (Sigma 27-54 %, Register BK); GPU-SIFT-Datenbank nutzen (--nur-merkmale ohne --cpu) oder --mapper incremental', flush=True)
    nrs = a.fotos or obj.get("sfm", {}).get(a.seite)
    if not nrs: raise SystemExit(f"keine Fotoliste: --fotos oder objekt.json['sfm']['{a.seite}']")
    sd = os.path.join(od, "sfm"); bilder = os.path.join(sd, f"bilder_{a.seite}"); T_ = f"_{a.tag}" if a.tag else ""; db = os.path.join(sd, f"db_{a.seite}{T_}.db"); aus = os.path.join(sd, f"sparse_{a.seite}{T_}")
    for p in (bilder, db):      # Symlinks auf die Datenpartition respektieren
        pass
    prior, info = vorbereiten(root, obj, nrs, bilder, a.maxpx)
    global GRUPPEN
    if a.kamera_gruppen:
        GRUPPEN = kamera_gruppen(root, obj, nrs, fallback=not a.kein_gruppen_fallback); _fb = [nr for nr, k in GRUPPEN.items() if k[0] == "FALLBACK-Manifest/Dateiname"]
        print(f"Kameragruppen: {len(GRUPPEN)} von {len(nrs)} Fotos in {len(set(GRUPPEN.values()))} Gruppen (EXIF-Datei: {len(GRUPPEN) - len(_fb)}, Fallback Manifest/Dateiname: {len(_fb)})" + ("  ANNAHME: Fallback-Gruppen = gleiche Kamera, gleiche Sitzung, gleicher Zoom (nicht belegt!)" if _fb else ""), flush=True)
    for nr in nrs: print(f"  {nr}: {info[nr]['orig']} -> {info[nr]['sfm']}, Prior {('%.0f px' % info[nr]['prior_f_px']) if info[nr]['prior_f_px'] else '-'} ({info[nr]['prior_grund']})")
    # Fernaufnahmen (Prior > fern_faktor x Diagonale) erst nach dem Erstaufbau registrieren
    def diag(nr): return float(np.hypot(*info[nr]["sfm"]))
    fern = [nr for nr in nrs if info[nr]["prior_f_px"] and info[nr]["prior_f_px"] > a.fern_faktor * diag(nr)]
    aktiv = [nr for nr in nrs if nr not in fern]; ausgeschlossen = {nr: "Fernaufnahme (EXIF-Prior)" for nr in fern}
    bericht = dict(seite=a.seite, fotos=nrs, runden=[], seed=a.seed, tag=a.tag, kamera_gruppen={k: str(v) for k, v in GRUPPEN.items()})
    if a.db_von: shutil.copy2(a.db_von if os.path.isabs(a.db_von) else os.path.join(sd, a.db_von), db)
    for runde in range(1, 4):
        t0 = time.time(); rec, tmp = bauen(bilder, db, aus, aktiv, prior, a.matcher, (a.lg_max_kp, a.lg_resize, a.lg_fotos), nur_merkmale=a.nur_merkmale, db_wieder=bool(a.db_von) and runde == 1, seed=a.seed, threads=a.threads, mapper=a.mapper, ba_gpu=a.ba_gpu)
        if a.nur_merkmale: print("Merkmale + Matches fertig:", db); return
        if rec is None: print("kein Modell"); break
        rows = bewerten(rec, info, prior, a.fern_faktor); reg = sorted(rows)
        fehlt = sorted(set(aktiv) - set(reg)); deg = [nr for nr in reg if rows[nr]["status"] != "ok"]
        print(f"\nRunde {runde} ({time.time() - t0:.0f} s): {len(reg)} von {len(aktiv)} registriert, {rec.num_points3D()} Punkte, Reproj {rec.compute_mean_reprojection_error():.2f} px; nicht registriert: {fehlt}")
        for nr in reg:
            r = rows[nr]; print(f"   {nr}: f={r['f_px']:.0f} px  Prior {r['prior_f_px'] or '-'}  f/Prior {r['f_zu_prior'] or '-'}  f/Diag {r['f_zu_diag']}  {r['punkte']} Pkt  {r['status']} {('; '.join(r['grund'])) if r['grund'] else ''}")
        bericht["runden"].append(dict(aktiv=aktiv, registriert=reg, nicht_registriert=fehlt, punkte=rec.num_points3D(), reproj_px=float(rec.compute_mean_reprojection_error()), kameras=rows, degeneriert=deg))
        if not deg or not a.reparieren: break
        for nr in deg: ausgeschlossen[nr] = "; ".join(rows[nr]["grund"])
        # Reparatur 1: degenerierte Kameras aus dem BESTEHENDEN Netz nehmen und nur nachgleichen (Neuaufbau ist reihenfolgeabhaengig
        # und wurde beim Martinstor-Suednetz jede Runde schlechter); Neuaufbau nur, wenn danach weniger als 3 Kameras uebrig sind.
        for im in list(rec.images.values()):
            if os.path.splitext(im.name)[0] in deg: rec.deregister_frame(im.frame_id)
        rest = [os.path.splitext(im.name)[0] for im in rec.images.values() if im.has_pose]
        if len(rest) >= 3:
            cfg = pycolmap.BundleAdjustmentConfig()
            for im in rec.images.values():
                if im.has_pose: cfg.add_image(im.image_id)
            for im in rec.images.values():
                if im.has_pose and im.name in prior: cfg.set_constant_cam_intrinsics(im.camera_id)
            for pid in list(rec.points3D.keys()): cfg.add_variable_point(pid)
            bo = pycolmap.BundleAdjustmentOptions(); bo.refine_principal_point = False
            pycolmap.create_default_bundle_adjuster(bo, cfg, rec).solve(); rec.write(aus + "/0")
            rows = bewerten(rec, info, prior, a.fern_faktor); deg2 = [nr for nr in rows if rows[nr]["status"] != "ok"]
            print(f"   -> {deg} entfernt und nachgeglichen: {len(rows)} Kameras, {rec.num_points3D()} Punkte, Reproj {rec.compute_mean_reprojection_error():.2f} px; degeneriert jetzt: {deg2}")
            for nr in rows:
                r = rows[nr]; print(f"      {nr}: f={r['f_px']:.0f} px  f/Prior {r['f_zu_prior'] or '-'}  f/Diag {r['f_zu_diag']}  {r['punkte']} Pkt  {r['status']}")
            bericht["runden"].append(dict(art="nachgleich", entfernt=deg, kameras=rows, punkte=rec.num_points3D(), reproj_px=float(rec.compute_mean_reprojection_error())))
            if not deg2: break
            aktiv = [nr for nr in rows if nr not in deg2]
            for nr in deg2: ausgeschlossen[nr] = "; ".join(rows[nr]["grund"])
            print(f"   -> immer noch degeneriert {deg2}: Neuaufbau mit {aktiv}")
        else:
            aktiv = [nr for nr in aktiv if nr not in deg]; print(f"   -> entferne {deg}, neuer Aufbau")
    bericht["ausgeschlossen"] = ausgeschlossen
    if rec is not None:
        bericht["ergebnis"] = dict(sparse=os.path.relpath(os.path.join(aus, "0"), root), registriert=sorted(os.path.splitext(i.name)[0] for i in rec.images.values()), punkte=rec.num_points3D(), reproj_px=float(rec.compute_mean_reprojection_error()))
        # Fernaufnahmen nachregistrieren (gleiche DB, Bilder liegen im tmp-Ordner nicht - deshalb nur Hinweis)
        if fern: print(f"\nFernaufnahmen nicht im Erstaufbau: {fern} ({len(fern)}); Nachregistrierung: spaeter mit pycolmap (offen)")
    json.dump(bericht, open(os.path.join(sd, f"netz_{a.seite}{T_}.json"), "w"), indent=1, ensure_ascii=False); print("Bericht:", os.path.join(sd, f"netz_{a.seite}{T_}.json"))

if __name__ == "__main__":
    main()
