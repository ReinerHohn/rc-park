#!/usr/bin/env python3
"""test_sift_einstellung.py - zentrale SIFT-Einstellung + Pflicht-Tor (tools/sift_einstellung.py, 24.11.2026). Keine grossen Rechnungen: winzige Bilder, CPU.
Prueft: (1) Standard = volle Aufloesung + first_octave 0 + GPU; RCPARK_SIFT_ALT=1 alt; RCPARK_SIFT_MAX Obergrenze;
(2) ROT-PROBE: eine Attrappe wie SiftGPU bei VRAM-Mangel ('Failed to process the image' auf stderr, Bild fehlt, kein Fehler) - der ALTE Aufruf
    (extract_features ohne Tor) meldet nichts, das Tor zaehlt Fehlbild + Logzeile, holt auf der CPU nach bzw. meldet ROT;
(3) echte pycolmap-CPU-Merkmale mit der zentralen Einstellung (kleine Bilder + eine kaputte Datei -> rot, Rest hat Merkmale);
(4) die Kettenwerkzeuge rufen die zentrale Stelle auf (kein eigenes FeatureExtractionOptions/extract_features mehr), gesamtkette liest sift_tor.json.
Aufruf: /media/oem/scan/venv-colmap/bin/python -I tools/test_sift_einstellung.py   Exit 0 = bestanden."""
import os, sys, io, json, sqlite3, contextlib
T = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, T)
import numpy as np, cv2, pycolmap
from pfade import temp_ordner
import sift_einstellung as SE

fehler = 0
def pruef(ok, text):
    global fehler
    print(("ok   " if ok else "FEHLER ") + text, flush=True); fehler += 0 if ok else 1

for k in ("RCPARK_SIFT_ALT", "RCPARK_SIFT_MAX"): os.environ.pop(k, None)

# (1) Einstellung
eo = SE.optionen(pycolmap)
pruef(eo.sift.first_octave == 0 and eo.use_gpu and eo.eff_max_image_size() >= 30000, f"Standard: {SE.beschreibung(eo)} (eff {eo.eff_max_image_size()} px, Handyfotos <= ~6000 px)")
pruef(not SE.optionen(pycolmap, geraet="cpu").use_gpu, "geraet=cpu -> use_gpu False")
os.environ["RCPARK_SIFT_ALT"] = "1"; ea = SE.optionen(pycolmap, alt_max=2400, max_num_features=6400)
pruef(ea.sift.first_octave == -1 and ea.max_image_size == 2400 and ea.sift.max_num_features == 6400, f"RCPARK_SIFT_ALT=1: {SE.beschreibung(ea)}")
os.environ.pop("RCPARK_SIFT_ALT"); os.environ["RCPARK_SIFT_MAX"] = "1600"; ec = SE.optionen(pycolmap)
pruef(ec.max_image_size == 1600 and ec.sift.first_octave == 0, f"RCPARK_SIFT_MAX=1600 Obergrenze: {SE.beschreibung(ec)}"); os.environ.pop("RCPARK_SIFT_MAX")


# (2) Rot-Probe mit Attrappe
def db_anlegen(db):
    c = sqlite3.connect(db); c.execute("create table if not exists images(image_id integer primary key, name text)"); c.execute("create table if not exists keypoints(image_id integer primary key, rows integer)"); c.commit(); c.close()

def attrappe(verwirft):
    """wie SiftGPU bei VRAM-Mangel: Bilder aus <verwirft[geraet]> schreibt sie NICHT, meldet 'Failed to process' auf fd 2, endet normal."""
    auf = []
    def ex(db, bd, image_names=(), device=None, extraction_options=None, **kw):
        g = "cpu" if device == pycolmap.Device.cpu else "gpu"; namen = list(image_names) or SE.bildnamen(bd); auf.append((g, len(namen), extraction_options.sift.first_octave))
        db_anlegen(db); c = sqlite3.connect(db)
        for n in namen:
            if n in verwirft.get(g, ()): os.write(2, f"E20261124 sift.cc] FAILURE: Failed to process the image {n}\n".encode()); continue
            i = (c.execute("select image_id from images where name=?", (n,)).fetchone() or [None])[0]
            if i is None: i = c.execute("insert into images(name) values(?)", (n,)).lastrowid
            c.execute("insert or replace into keypoints values(?,?)", (i, 500))
        c.commit(); c.close()
    return ex, auf

d = temp_ordner("sift_einstellung_"); bd = os.path.join(d, "bilder"); os.makedirs(bd); rng = np.random.default_rng(0)
for i in range(3): cv2.imwrite(os.path.join(bd, f"b{i}.jpg"), cv2.GaussianBlur((rng.random((240, 320)) * 255).astype(np.uint8), (5, 5), 0))
namen = SE.bildnamen(bd)
from kette_beleg import db_fehlende_bilder

# ALTER Aufruf (ohne Tor): rc normal, keine Ausnahme -> niemand merkt das Fehlbild
db0 = os.path.join(d, "alt.db"); ex, _ = attrappe({"gpu": {"b1.jpg"}})
err = io.StringIO()
try: ex(db0, bd, device=pycolmap.Device.cuda, extraction_options=SE.optionen(pycolmap)); alt_ausnahme = False
except Exception: alt_ausnahme = True
pruef(not alt_ausnahme and db_fehlende_bilder(db0, namen) == ["b1.jpg"], "Rot-Probe: alter Aufruf endet normal, Fehlbild b1.jpg bleibt STILL (nur in der DB-Zaehlung sichtbar)")

# Tor: GPU verwirft, CPU holt nach -> nicht rot, aber gemeldet
out = io.StringIO(); db1 = os.path.join(d, "t1.db"); ex, auf = attrappe({"gpu": {"b1.jpg"}}); tj = os.path.join(d, "t1.json")
with contextlib.redirect_stdout(out): tor = SE.extrahieren_mit_tor(pycolmap, db1, bd, namen, extrahieren=ex, tor_json=tj, stufe="probe")
pruef(not tor["rot"] and tor["nachgeholt_cpu"] == ["b1.jpg"] and tor["log_failed"] == 1 and "WARNUNG probe" in out.getvalue() and [a[0] for a in auf] == ["gpu", "cpu"]
      and all(a[2] == 0 for a in auf), f"Tor: GPU-Fehlbild + Logzeile gezaehlt, CPU nachgeholt (Aufrufe {auf}, Tor {tor['nachgeholt_cpu']}, log_failed {tor['log_failed']})")
pruef(json.load(open(tj))["rot"] is False, "Tor-JSON geschrieben")

# Tor: auch CPU verwirft -> ROT
out = io.StringIO(); db2 = os.path.join(d, "t2.db"); ex, auf = attrappe({"gpu": {"b1.jpg", "b2.jpg"}, "cpu": {"b2.jpg"}})
with contextlib.redirect_stdout(out): tor = SE.extrahieren_mit_tor(pycolmap, db2, bd, namen, extrahieren=ex, tor_json=os.path.join(d, "t2.json"), stufe="probe")
pruef(tor["rot"] and tor["fehlend"] == ["b2.jpg"] and tor["nachgeholt_cpu"] == ["b1.jpg"] and tor["log_failed"] == 3 and "STUFE ROT SIFT-TOR" in out.getvalue(),
      f"Tor: Restfehler -> STUFE ROT (fehlend {tor['fehlend']}, log_failed {tor['log_failed']})")

# Logfang: stderr geht weiter, Text kommt zurueck, auch bei Ausnahme wiederhergestellt
def wirft(): os.write(2, b"Failed to process the image x\n"); raise RuntimeError("probe")
try: SE.mit_logfang(wirft); w_ok = False
except RuntimeError: w_ok = True
r, txt = SE.mit_logfang(lambda: os.write(2, b"Failed to process the image y\n") and 7)
pruef(w_ok and r == 7 and SE.log_fehler(txt) == 1, "Logfang zaehlt 'Failed to process', reicht Ausnahmen durch")

# (3) echte pycolmap-Merkmale, CPU, zentrale Einstellung; kaputte Datei -> rot
open(os.path.join(bd, "kaputt.jpg"), "wb").write(b"\xff\xd8\xff\xe0kein jpeg")
out = io.StringIO(); db3 = os.path.join(d, "echt.db")
with contextlib.redirect_stdout(out): tor = SE.extrahieren_mit_tor(pycolmap, db3, bd, camera_mode=pycolmap.CameraMode.PER_IMAGE, geraet="cpu", stufe="echt")
pruef(tor["bilder"] == 4 and tor["fehlend"] == ["kaputt.jpg"] and tor["rot"] and not db_fehlende_bilder(db3, namen), f"echtes CPU-SIFT (first_octave 0, voll): 3 Bilder mit Merkmalen, kaputt.jpg ROT ({tor['optionen']})")

# (4) Kettenwerkzeuge nutzen die zentrale Stelle
for f, muss in (("iphone_sfm.py", "SE.extrahieren_mit_tor("), ("sfm_netz.py", "SE.extrahieren_mit_tor("), ("video_sfm.py", "SE.extrahieren_mit_tor("), ("zusatzfotos_registrieren.py", "SE.optionen(")):
    q = open(os.path.join(T, f)).read(); code = "\n".join(z.split("#")[0] for z in q.splitlines())
    pruef(muss in code and "pycolmap.FeatureExtractionOptions(" not in code and (f == "zusatzfotos_registrieren.py" or "pycolmap.extract_features(" not in code), f"{f}: zentrale SIFT-Einstellung ({muss})")
g = open(os.path.join(T, "gesamtkette.py")).read()
pruef('"sift_tor.json"' in g and 'notiz(B, "sift_tor"' in g, "gesamtkette: Zeile 'sift_tor' aus sfm/sift_tor.json")

print("BESTANDEN" if not fehler else f"{fehler} FEHLER"); sys.exit(1 if fehler else 0)
