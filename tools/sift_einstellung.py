#!/usr/bin/env python3
"""sift_einstellung.py - EINE Stelle fuer die COLMAP-SIFT-Merkmalssuche der Gesamtkette (24.11.2026) + Pflicht-Tor gegen still verworfene Bilder.

WARUM (Messung 23.11.2026, tools/versuche/sift_oktave_vergleich.sh, Logbuch LOGBUCH_SCHWABENTOR_KETTE_2026-11-21.md "SIFT"):
  first_octave -1 (COLMAP-Standard) VERDOPPELT das Bild. Bei voller Aufloesung (Handyfotos bis ~27 MPx) braucht SiftGPU dann > 8 GB VRAM und COLMAP
  verwirft die Bilder STILL ('FAILURE: Failed to process the image', rc 0). Volle Aufloesung, CPU: -1 = 197 Paare >= 30 Inlier, 1446 s; 0 = 195 Paare, 115 s.
  -> Standard jetzt: volle Bildaufloesung (keine Verkleinerung) + first_octave 0, auf der GPU. Bisher: max_image_size 2400 (iphone_sfm) bzw. 3200 (pycolmap-Standard).
Schalter:
  RCPARK_SIFT_ALT=1   alte Einstellung zurueck (first_octave -1, max_image_size wie der Aufrufer es frueher hatte)
  RCPARK_SIFT_MAX=N   ausdrueckliche Obergrenze (z. B. bauteil_kreis/parallele Spuren mit wenig VRAM); gilt in beiden Modi
Tor (nie still): nach jeder Extraktion fehlende Bilder in der DB zaehlen (kette_beleg.db_fehlende_bilder) + 'Failed to process' im COLMAP-Log zaehlen;
  fehlende einmal auf der CPU nachholen (Geschwister: zusatzfotos_registrieren.sift_sicher); fehlt danach noch etwas -> 'STUFE ROT SIFT-TOR' + rot=True.
  optionen(pycolmap, alt_max, max_num_features, geraet)       -> FeatureExtractionOptions
  extrahieren_mit_tor(pycolmap, db, bilddir, ..., tor_json)   -> Tor-dict (bilder, fehlend, nachgeholt_cpu, log_failed, rot, optionen)
Test: tools/test_sift_einstellung.py (Schnelltest)."""
import os, sys, json, time, tempfile

VOLL_PX = 100000                  # max_image_size so gross, dass COLMAP nie verkleinert (eff_max_image_size == Wert; -1 hiesse in pycolmap 4.2.1 = 3200)
OKTAVE = 0                        # 0 = Bild nicht verdoppeln (passt auf 8-GB-GPU), -1 = COLMAP-Standard
FEHL_MUSTER = ("Failed to process the image",)
BILD_ENDUNGEN = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")


def alt_modus(): return os.environ.get("RCPARK_SIFT_ALT", "0") == "1"


def optionen(pycolmap, alt_max=None, max_num_features=None, geraet="gpu"):
    """Zentrale FeatureExtractionOptions. <alt_max>: max_image_size, die der Aufrufer VOR der Umstellung nutzte (nur bei RCPARK_SIFT_ALT=1)."""
    eo = pycolmap.FeatureExtractionOptions(); eo.use_gpu = geraet != "cpu"
    if max_num_features: eo.sift.max_num_features = int(max_num_features)
    if alt_modus():
        eo.sift.first_octave = -1
        if alt_max: eo.max_image_size = int(alt_max)
    else:
        eo.sift.first_octave = OKTAVE; eo.max_image_size = VOLL_PX
    cap = os.environ.get("RCPARK_SIFT_MAX")
    if cap: eo.max_image_size = int(cap)
    return eo


def beschreibung(eo):
    m = eo.max_image_size
    return f"SIFT first_octave {eo.sift.first_octave}, max_image_size {'voll' if m >= VOLL_PX else m}, {'GPU' if eo.use_gpu else 'CPU'}" + (" (RCPARK_SIFT_ALT=1)" if alt_modus() else "")


def bildnamen(bilddir):
    """Alle Bilder unter <bilddir> als COLMAP-Namen (relativ, '/' als Trenner; Unterordner wie bei CameraMode.PER_FOLDER)."""
    out = []
    for w, _, fs in os.walk(bilddir):
        for f in fs:
            if f.lower().endswith(BILD_ENDUNGEN): out.append(os.path.relpath(os.path.join(w, f), bilddir).replace(os.sep, "/"))
    return sorted(out)


def mit_logfang(fn, *a, **k):
    """fn(*a, **k) mit mitgeschnittenem stderr (Datei-Deskriptor 2: dort schreibt glog/COLMAP). Der Mitschnitt geht danach unveraendert auf stderr weiter
    (Joblog bleibt vollstaendig). Rueckgabe (Ergebnis, Text). Ausnahmen laufen durch (stderr wird vorher wiederhergestellt)."""
    sys.stderr.flush(); alt = os.dup(2); tf = tempfile.TemporaryFile(mode="w+b")
    os.dup2(tf.fileno(), 2)
    try: r = fn(*a, **k)
    finally:
        sys.stderr.flush(); os.dup2(alt, 2); os.close(alt)
        tf.seek(0); roh = tf.read(); tf.close()
        if roh: os.write(2, roh)
        mit_logfang.letzter = roh.decode("utf-8", "replace")
    return r, mit_logfang.letzter


def log_fehler(text): return sum(text.count(m) for m in FEHL_MUSTER)


def extrahieren_mit_tor(pycolmap, db, bilddir, namen=None, camera_mode=None, reader_options=None, alt_max=None, max_num_features=None,
                        geraet="gpu", nachholen=True, tor_json=None, stufe="sift", extrahieren=None):
    """Merkmalssuche mit zentraler Einstellung, CPU-Nachholen fehlender Bilder und Pflicht-Tor. <namen> None = alle Bilder unter <bilddir>.
    <geraet>: gpu | auto | cpu. <extrahieren>: Ersatz fuer pycolmap.extract_features (Test)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from kette_beleg import db_fehlende_bilder
    ex = extrahieren or pycolmap.extract_features; t0 = time.time()
    alle = list(namen) if namen is not None else bildnamen(bilddir)
    kw = dict(reader_options=reader_options or pycolmap.ImageReaderOptions())
    if camera_mode is not None: kw["camera_mode"] = camera_mode
    if namen is not None: kw["image_names"] = alle
    eo = optionen(pycolmap, alt_max, max_num_features, geraet)
    dev = {"gpu": pycolmap.Device.cuda, "auto": pycolmap.Device.auto, "cpu": pycolmap.Device.cpu}[geraet]
    print(f"{stufe}: {beschreibung(eo)} - {len(alle)} Bilder", flush=True)
    _, log1 = mit_logfang(ex, db, bilddir, extraction_options=eo, device=dev, **kw)
    n_log = log_fehler(log1); fehl = db_fehlende_bilder(db, alle); nach = []
    if fehl or n_log:
        print(f"WARNUNG {stufe}: {len(fehl)} von {len(alle)} Bildern ohne Merkmale, {n_log}x 'Failed to process' im COLMAP-Log ({beschreibung(eo)}) - z. B. {fehl[:3]}", flush=True)
    if fehl and nachholen and geraet != "cpu":
        eo_c = optionen(pycolmap, alt_max, max_num_features, "cpu"); kw_c = dict(kw, image_names=fehl)
        print(f"{stufe}: {len(fehl)} fehlende Bilder auf der CPU nachholen ({beschreibung(eo_c)})", flush=True)
        _, log2 = mit_logfang(ex, db, bilddir, extraction_options=eo_c, device=pycolmap.Device.cpu, **kw_c)
        rest = db_fehlende_bilder(db, fehl); nach = [n for n in fehl if n not in rest]; fehl = rest; n_log += log_fehler(log2)
    tor = dict(stufe=stufe, bilder=len(alle), fehlend=fehl, nachgeholt_cpu=nach, log_failed=n_log, rot=bool(fehl), optionen=beschreibung(eo),
               sekunden=round(time.time() - t0, 1), zeit=time.strftime("%Y-%m-%d %H:%M"))
    if fehl: print(f"STUFE ROT SIFT-TOR ({stufe}): {len(fehl)} von {len(alle)} Bildern OHNE Merkmale auch nach CPU-Nachholen - fehlen in der SfM: {fehl[:5]}", flush=True)
    elif nach: print(f"SIFT-TOR ({stufe}): alle {len(alle)} Bilder haben Merkmale, {len(nach)} davon erst auf der CPU nachgeholt (GPU verwarf sie)", flush=True)
    else: print(f"SIFT-TOR ({stufe}): alle {len(alle)} Bilder haben Merkmale", flush=True)
    if tor_json:
        with open(tor_json, "w") as f: json.dump(tor, f, indent=1)
    return tor
