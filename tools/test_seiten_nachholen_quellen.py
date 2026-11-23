#!/usr/bin/env python3
"""test_seiten_nachholen_quellen.py - Befunde Kettenlauf schwabentor-1122p (23.11.2026), Sekunden, keine echten Daten, kein Netz:
(1) seiten_luecken: Kandidaten nur aus vorhandenen Dateien; das Nachholskript leert roh/ von ALTEN Verknuepfungen (nur symlinks, echte Dateien bleiben)
    - 1122p: 305 tote Links eines frueheren Laufs in roh/ -> FileNotFoundError in vorbereiten, Ostseite blieb leer.
(2) zusatzfotos_registrieren vorbereiten: tote Verknuepfung -> aussortiert mit Grund statt Absturz.
(3) bilder_vorpruefen.kette_merkmale: unlesbares/fehlendes Bild -> None statt AttributeError (Stufe vorpruefen rot).
(4) http_holen: HTTP 429 mit Retry-After/Backoff wiederholt, Budget erschoepft -> Gedrosselt, andere Fehler unveraendert.
(5) commons_harvest.bild_ok: vorhandene gueltige Datei wird uebernommen (kein Neuladen aller Bilder je Lauf).
(6) verlustbilanz.gruende_nicht_registriert: Grund je nicht registriertem Bild (Konsens fremde Seite, Seitenerkennung fremd, kein Paar, schwach, Mapper).
  /media/oem/scan/venv-seg/bin/python -I tools/test_seiten_nachholen_quellen.py"""
import os, sys, io, json, struct, sqlite3, subprocess, argparse, urllib.error, email.message
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, cv2
import pfade
TD = os.path.dirname(os.path.abspath(__file__))

F = 0
def pruef(ok, text):
    global F
    print(("    ok    " if ok else "    FEHLER ") + text); F += 0 if ok else 1


T = pfade.temp_ordner("test_seiten_nachholen_quellen_")
fotos = os.path.join(T, "fotos"); os.makedirs(fotos)
for i in range(3): cv2.imwrite(os.path.join(fotos, f"b{i}.jpg"), np.random.default_rng(i).integers(0, 255, (60, 80, 3), np.uint8))
os.symlink(os.path.join(T, "weg", "eigen__vf_007.jpg"), os.path.join(fotos, "tot.jpg"))

# (1) seiten_luecken
import seiten_luecken as SL
alle = sorted(os.path.join(fotos, f) for f in os.listdir(fotos))
ok_, tot = SL.nur_vorhandene(alle)
pruef(len(ok_) == 3 and [os.path.basename(t) for t in tot] == ["tot.jpg"], f"Kandidaten nur aus vorhandenen Dateien ({len(ok_)} da, tot {[os.path.basename(t) for t in tot]})")
Z = os.path.join(T, "nachholen"); roh = os.path.join(Z, "roh"); os.makedirs(roh)
os.symlink(os.path.join(T, "weg", "eigen__007.jpg"), os.path.join(roh, "eigen__007.jpg"))      # toter Link eines frueheren Laufs
os.symlink(os.path.join(fotos, "b0.jpg"), os.path.join(roh, "alt_lebt.jpg"))                  # lebender Link eines frueheren Laufs (anderer Kandidatensatz)
open(os.path.join(roh, "echt.jpg"), "wb").write(b"\xff\xd8x")                                  # echte Datei: darf NIE geloescht werden
r = subprocess.run(["bash", "-c", "set -e; " + SL.roh_neu_zeile(Z)], capture_output=True, text=True)
rest = sorted(os.listdir(roh))
pruef(r.returncode == 0 and rest == ["echt.jpg"] and "2 Verknuepfungen" in r.stdout and "davon 1 tot" in r.stdout, f"roh/ vor dem Neuaufbau: alte Verknuepfungen weg, echte Datei bleibt ({rest}; {r.stdout.strip()[:90]})")
src = open(os.path.join(TD, "seiten_luecken.py")).read()
pruef(src.index("roh_neu_zeile(Z)") < src.index('zeilen += [f"ln -sf'), "Skript leert roh/ VOR dem Verlinken der Kandidaten (Quelltext)")

# (2) zusatzfotos_registrieren vorbereiten mit totem Link
import zusatzfotos_registrieren as ZR
roh2 = os.path.join(T, "roh2"); os.makedirs(roh2)
os.symlink(os.path.join(fotos, "b1.jpg"), os.path.join(roh2, "gut.jpg")); os.symlink(os.path.join(T, "weg", "x.jpg"), os.path.join(roh2, "eigen__007.jpg"))
aus = os.path.join(T, "aus"); os.makedirs(aus)
try:
    ZR.vorbereiten(argparse.Namespace(ausschluss=None, fotos=[roh2], aus=aus, unten=0.0, breite=0)); V = json.load(open(os.path.join(aus, "vorbereitet.json")))
    g = [v["grund"] for v in V["verworfen"]]
    pruef(list(V["bilder"]) == ["gut.jpg"] and len(g) == 1 and g[0].startswith("tote Verknuepfung"), f"vorbereiten: toter Link aussortiert mit Grund ({g})")
except Exception as e: pruef(False, f"vorbereiten stuerzt bei totem Link ab: {type(e).__name__} {e}")

# (3) bilder_vorpruefen.kette_merkmale
import bilder_vorpruefen as BV
kaputt = os.path.join(T, "kaputt.jpg"); open(kaputt, "wb").write(b"\xff\xd8 abgeschnitten")
cache = {}; aufrufe = []
try:
    a1 = BV.kette_merkmale(kaputt, cache, lambda g: aufrufe.append(g.shape) or ("P", "f"))
    a2 = BV.kette_merkmale(os.path.join(T, "fehlt.jpg"), cache, lambda g: ("P", "f"))
    a3 = BV.kette_merkmale(os.path.join(fotos, "b2.jpg"), cache, lambda g: aufrufe.append(g.shape) or ("P", "f"))
    pruef(a1 is None and a2 is None and a3 == ("P", "f") and aufrufe == [(60, 80)], f"Vorpruefung Kette: unlesbar/fehlt -> None, lesbares Bild -> Merkmale ({a1}, {a2}, {aufrufe})")
except Exception as e: pruef(False, f"kette_merkmale stuerzt ab: {type(e).__name__} {e}")
bsrc = open(os.path.join(TD, "bilder_vorpruefen.py")).read()
pruef("M0 is None or M1 is None" in bsrc and "unlesbar(p_)" in bsrc, "Kette behandelt None (aussortiert mit Grund 'nicht lesbar', Quelltext)")

# (4) http_holen
os.environ["RCPARK_DROSSEL_DATEI"] = os.path.join(T, "drossel_marken.json")      # 23.11.2026: Drossel-Marken des Tests nie in die echte Datei
import http_holen as HH
class Antwort(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): self.close()
def fehler(code, ra=None):
    h = email.message.Message()
    if ra is not None: h["Retry-After"] = str(ra)
    return urllib.error.HTTPError("https://upload.wikimedia.org/x.jpg", code, "Too many requests", h, None)
def oeffner(folge):
    def o(rq, timeout):
        x = folge.pop(0)
        if isinstance(x, Exception): raise x
        return Antwort(x)
    return o
still = lambda *a, **k: None
HH._verbraucht[0] = 0.0; schl = []
d = HH.hole("https://upload.wikimedia.org/x.jpg", oeffnen=oeffner([fehler(429, 7), fehler(429), b"JPEG"]), schlafen=schl.append, melden=still)
pruef(d == b"JPEG" and schl == [7.0, 120.0], f"429: Retry-After 7 s befolgt, dann Backoff 60*2^1 = 120 s, dann geladen (Wartezeiten {schl})")
os.environ["RCPARK_429_BUDGET_S"] = "100"; HH._verbraucht[0] = 0.0; schl = []
try: HH.hole("https://u/x", oeffnen=oeffner([fehler(429)] * 5), schlafen=schl.append, melden=still); pruef(False, "Budget erschoepft ohne Gedrosselt")
except HH.Gedrosselt as e: pruef(schl == [60.0], f"Wartebudget 100 s: nach einmal 60 s Gedrosselt statt Retry-Sturm ({schl})")
os.environ.pop("RCPARK_429_BUDGET_S"); HH._verbraucht[0] = 0.0
try: HH.hole("https://u/x", oeffnen=oeffner([fehler(404)]), schlafen=still, melden=still); pruef(False, "404 nicht durchgereicht")
except urllib.error.HTTPError as e: pruef(e.code == 404, "anderer HTTP-Fehler (404) geht ohne Warten durch")
pruef(HH.retry_after_s("Wed, 21 Oct 2015 07:28:00 GMT", jetzt=1445412470.0) == 10.0, "Retry-After als HTTP-Datum")
for t_ in ("online_ansichten_holen.py", "openverse_holen.py", "commons_harvest.py"):
    pruef("http_holen.hole(" in open(os.path.join(TD, t_)).read(), f"{t_} laedt ueber http_holen (Backoff)")

# (5) commons_harvest.bild_ok
import commons_harvest as CH
klein = os.path.join(T, "000_klein.jpg"); open(klein, "wb").write(b"\xff\xd8" + b"0" * 10)
gross = os.path.join(T, "001_gross.jpg"); open(gross, "wb").write(b"\xff\xd8" + b"0" * 5000)
html = os.path.join(T, "002_html.jpg"); open(html, "wb").write(b"<html>" + b"0" * 5000)
pruef(CH.bild_ok(gross) and not CH.bild_ok(klein) and not CH.bild_ok(html) and not CH.bild_ok(os.path.join(T, "fehlt")), "commons: nur gueltige vorhandene Bilder werden uebernommen")
pruef("schon vorhanden, nicht neu geladen" in open(os.path.join(TD, "commons_harvest.py")).read(), "commons: vorhandene Bilder statt Neuladen (Quelltext)")

# (6) verlustbilanz: Grund je Bild
import verlustbilanz as VB
sfm = os.path.join(T, "sfm"); sp = os.path.join(sfm, "sparse", "0"); os.makedirs(sp); os.makedirs(os.path.join(sfm, "konsens_arbeit"))
namen = ["r1.jpg", "r2.jpg", "r3.jpg", "r4.jpg", "fs.jpg", "fr.jpg", "nokp.jpg", "allein.jpg", "schwach.jpg", "mapper.jpg"]
with open(os.path.join(sp, "images.bin"), "wb") as f:
    f.write(struct.pack("<Q", 4))
    for i, n in enumerate(namen[:4], 1): f.write(struct.pack("<I", i) + b"\0" * 56 + struct.pack("<I", 1) + n.encode() + b"\0" + struct.pack("<Q", 1) + b"\0" * 24)
con = sqlite3.connect(os.path.join(sfm, "db.db"))
con.execute("create table images(image_id integer, name text)"); con.execute("create table keypoints(image_id integer, rows integer)"); con.execute("create table two_view_geometries(pair_id integer, rows integer)")
for i, n in enumerate(namen, 1):
    con.execute("insert into images values (?,?)", (i, n)); con.execute("insert into keypoints values (?,?)", (i, 0 if n == "nokp.jpg" else 3000))
pid = lambda a, b: min(a, b) * 2147483647 + max(a, b)
for a, b, r in [(9, 1, 40), (9, 2, 10), (10, 1, 200), (10, 2, 150), (10, 3, 90), (5, 1, 300), (5, 2, 280), (5, 3, 260)]: con.execute("insert into two_view_geometries values (?,?)", (pid(a, b), r))
con.commit(); con.close()
open(os.path.join(sfm, "konsens_arbeit", "fremde_seite.txt"), "w").write("fs.jpg\n")
json.dump(dict(fremd=["fr.jpg"]), open(os.path.join(sfm, "seiten.json"), "w"))
G = VB.gruende_nicht_registriert(sfm); k = {n: g[0].split(" ")[0] for n, g in G.items()}
pruef(k == {"fs.jpg": "Konsens-Mapper:", "fr.jpg": "Seitenerkennung:", "nokp.jpg": "keine", "allein.jpg": "kein", "schwach.jpg": "zu", "mapper.jpg": "Mapper"}, f"Grund je nicht registriertem Bild ({k})")
D = os.path.join(T, "daten"); os.makedirs(os.path.join(D, "pipe")); os.rename(sfm, os.path.join(D, "pipe", "sfm"))
json.dump(dict(stufen=[dict(name="sfm", detail="registriert 4 von 10 (Ziel >= 2)")]), open(os.path.join(D, "pipe", "pipeline_bericht.json"), "w"))
V = VB.bilanz(D, os.path.join(T, "modell")); e = [x for x in V["stufen"] if x["stufe"] == "sfm_registriert"][0]
pruef(e["ohne_grund"] == 0 and len(e.get("je_bild", {})) == 6 and not any("sfm_registriert" in w for w in V["warnungen"]), f"Verlustbilanz sfm_registriert: 6 Verluste alle mit Grund, keine WARNUNG ({e['rein']} -> {e['raus']}, ohne Grund {e['ohne_grund']})")

print(f"test_seiten_nachholen_quellen: {F} Fehler"); sys.exit(1 if F else 0)
