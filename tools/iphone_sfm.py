#!/usr/bin/env python3
"""iphone_sfm.py <bilderordner> <arbeitsordner> - COLMAP-SfM (pycolmap, SIFT-GPU, exhaustive, Mapper) fuer die iPhone-Fotos; GPU von Anfang an (Nutzerregel)."""
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
# Mapper: COLMAP-Binaerdatei mit CUDA (GPU-Bündelausgleich, BundleAdjustmentCeres.use_gpu). Die pycolmap-Python-Bibliothek hat keine GPU-Ceres.
COLMAP_BIN = "/media/oem/scan/colmap-build/prefix/bin/colmap"
_env = dict(os.environ, LD_LIBRARY_PATH=":".join(["/media/oem/scan/cuda-toolkit-combo/lib64", "/media/oem/scan/venv-seg/lib/python3.12/site-packages/nvidia/cu13/lib", "/media/oem/scan/cudss-pkg/py/nvidia/cu13/lib", "/media/oem/scan/venv-colmap/lib/python3.12/site-packages/nvidia/curand/lib"]))
# ein Thread: reproduzierbare Anzahl eingehaengter Bilder (Messung 13.11.: Mehrthread 181/149/181/21, Einthread 181/181); Qualitaet vor Tempo
subprocess.run([COLMAP_BIN, "mapper", "--database_path", db, "--image_path", img, "--output_path", f"{w}/sparse",
                "--Mapper.num_threads", "1", "--Mapper.ba_use_gpu", "1", "--Mapper.ba_gpu_index", "0", "--Mapper.ba_max_num_images_direct_dense_gpu_solver", "0"], env=_env, check=True)
rec = {k: pycolmap.Reconstruction(os.path.join(f"{w}/sparse", k)) for k in sorted(os.listdir(f"{w}/sparse")) if k.isdigit()}
for k, r in rec.items(): print(k, r.summary(), flush=True)
