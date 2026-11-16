#!/usr/bin/env python3
"""gesamtkette.py - EINE Kette von den Bildquellen bis zur 3D-Seite, fuer jedes Objekt, mit Toren und Korrekturkreislauf.
Lehre Schwabentor 2026-11-14: Bausteine waren allgemein, die Kette nicht (Quellen von Hand, Clipwahl von Hand, Tore nur im Nullstart,
Lagefehler von Hand korrigiert). Nutzer: "bau die Gesamtkette und beweise es".

  /media/oem/scan/venv-seg/bin/python -I tools/gesamtkette.py <quelle_objekt> --ziel <neuer_name> [--ab stufe] [--bis stufe]
        [--fremd ORDNER ...] [--commons-kategorie "Category:..."] [--ohne-video] [--referenz-wolke npy] [--max-loesung 3]
Stufen (Bericht: /media/oem/scan/rc-park_daten/<ziel>/gesamtkette_bericht.json; jede Stufe ok/fehler/uebersprungen mit Grund):
  anlegen    modelle/<ziel>/objekt.json aus der Quelle (name, ort, lod2, rahmen, fotos_dir, ...) + Generator-Vorlage (LoD2+Dach);
             fehlen lod2/rahmen: tools/rahmen_aus_lod2.py (Gebaeude per GML-Namensattribut, Rahmen aus Grundriss, Gelaende DGM1)
  commons    optional: tools/commons_harvest.py --category (frei lizenziert) -> Fremdordner
  video      tools/video_suchen.py (GPU) -> tools/clips_waehlen.py (Regeln statt Sichtpruefung) -> tools/video_frames.py
  vorpruefen tools/bilder_vorpruefen.py (GPU, Videokette) gegen fotos_dir (vertrauenswuerdige Bilder)
  sammeln    tools/fotos_sammeln.py (Dubletten, Quelle im Namen)
  sfm        tools/pipeline_objekt.py fein (SfM mit Paarliste, Bildwahl, Tiefenkarten GPU, LoD2-Abgleich)
  tore       kamera_abdeckung, lage_gps_pruefen, wolke_grundriss_pruefen; KORREKTUR: faellt GPS (rc 3) oder Grundriss A (rc 3) durch,
             sfm_lod2_ausrichten --loesung 1..max probieren, die erste Loesung, die ALLE Tore besteht, gilt; sonst Abbruch mit Bericht
  dach       tools/dach_vermessen.py (DOM1, mit Wolke)
  bauen      tools/bauen_abnehmen.sh <ziel> (Generator aus Vorlage = LoD2 + Dach)
  kanten     KERNMETHODE (15.11.): tools/kantenstufe.py - SfM-Kameras -> Stabilkarten -> Kanten-Tiefen-Sweep um die Modellflaeche -> 3D-Kanten-F1 + Liste fehlender Kanten
  fototor    tools/kameras_aus_buendel.py (K-<foto>.json) -> tools/foto_diff.py auf den Fotos mit bester Modellsicht (Foto-Tor)
  (in fototor: tools/kamera_plausibel.py --beiseite; nach fenster: tools/umriss_tor.py --eintragen; fassaden/fenster/seiten siehe modelle/PIPELINE_FASSADEN.md)
  html       tools/modell_3d_html.py -> <daten>/<ziel>_3d.html
  vergleich  optional --referenz-wolke: Abstand neue Wolke -> bewiesene Wolke (Median, Anteil < 0,5 m) = Konvergenzbeweis
"""
import sys, os, re, json, glob, shutil, subprocess, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "/media/oem/scan/venv-seg/bin/python"; PYC = "/media/oem/scan/venv-colmap/bin/python"
STUFEN = ["anlegen", "commons", "video", "vorpruefen", "sammeln", "sfm", "tore", "dach", "bauen", "kanten", "fototor", "fassaden", "fenster", "seiten", "html", "vergleich"]
UEBERNEHMEN = ["name", "ort", "lod2", "rahmen", "rahmen_wand", "koordinate_utm", "hoehe_m", "fotos_dir", "seiten_konvention", "bildquellen"]


class _Erg:                                                                  # wie subprocess.CompletedProcess (returncode, stdout)
    def __init__(self, rc, out): self.returncode, self.stdout = rc, out


def lauf(B, name, cmd, log, ok=(0,), timeout=None):
    """Eine Stufe starten. 16.11.2026 (Stabilisierung): Ausgabe laeuft ZEILENWEISE ins Log (vorher erst am Stufenende - eine 30-Minuten-Stufe war blind, ein Haenger nicht zu erkennen);
    Zeitlimit je Stufe (Standard RCPARK_STUFE_MAX_S = 3 h, die Prozessgruppe wird beendet) - ein Haenger auf einem Kern hielt am 16.11. die Kette stundenlang an."""
    import threading, signal
    if subprocess.run(["python3", os.path.join(ROOT, "tools", "platz_pruefen.py")], capture_output=True).returncode != 0:      # Platztor VOR jeder Stufe (16.11.2026: Systemplatte lief mitten im Lauf unter 5 GB, die Stufe danach scheiterte halb)
        e = dict(stufe=name, rc=3, ok=False, sekunden=0, fehler="PLATZ ZU KNAPP vor Stufenstart (tools/platz_pruefen.py) - Kette haelt an"); B["schritte"].append(e); __import__("json_sicher").schreiben(B["_pfad"], B); print("    FEHLER: " + e["fehler"], flush=True); raise SystemExit(3)
    t0 = time.time(); print(f"[{time.strftime('%H:%M:%S')}] {name}: {' '.join(cmd)[:220]}", flush=True); timeout = timeout or float(os.environ.get("RCPARK_STUFE_MAX_S", "10800")); teile = []; abgelaufen = []
    with open(log, "a") as L:
        L.write(f"\n=== {name}  [{time.strftime('%Y-%m-%d %H:%M:%S')}]\n"); L.flush()
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
        def _stop():
            abgelaufen.append(1)
            try:
                os.killpg(p.pid, signal.SIGTERM)
                try: p.wait(timeout=10)
                except subprocess.TimeoutExpired: pass
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        uhr = threading.Timer(timeout, _stop); uhr.daemon = True; uhr.start()
        for z in p.stdout: teile.append(z); L.write(z); L.flush()
        p.wait(); uhr.cancel()
        if abgelaufen: L.write(f"ZEITLIMIT {timeout:.0f} s ueberschritten - Stufe beendet\n")
    r = _Erg(p.returncode if not abgelaufen else 124, "".join(teile) + (f"\nZEITLIMIT {timeout:.0f} s ueberschritten - Stufe beendet" if abgelaufen else ""))
    e = dict(stufe=name, rc=r.returncode, ok=r.returncode in ok, sekunden=round(time.time() - t0), ende=r.stdout.strip().splitlines()[-3:] if r.stdout.strip() else [])
    if r.returncode != 0 and "Traceback (most recent call last)" in r.stdout: e["ok"] = False; e["fehler"] = "Python-Absturz: " + ([z_ for z_ in r.stdout.strip().splitlines() if re.match(r"^[\w.]*(Error|Exception|Exit|Interrupt)\b", z_)] or r.stdout.strip().splitlines())[-1][:200]; print("    FEHLER: " + e["fehler"], flush=True)      # 16.11.2026: mehrere Stufen lassen rc 1/3/4 als Hinweis gelten - ein Absturz ist nie ein Hinweis
    if "tools/bauen_abnehmen.sh" in cmd and "ERGEBNIS:" not in r.stdout: e["ok"] = False; e["fehler"] = "Bau/Abnahme lief nicht bis zur Ergebniszeile (Generator abgestuerzt oder vom System beendet?) - rc 1 heisst hier NICHT 'nur Pruefstand rot'"; print("    FEHLER: " + e["fehler"], flush=True)      # 16.11.2026: rc 1 galt als bestanden, ein Python-Absturz im Generator gibt aber auch rc 1
    B["schritte"].append(e); __import__("json_sicher").schreiben(B["_pfad"], B)
    print(f"    rc {r.returncode} ({e['sekunden']} s) {' | '.join(e['ende'])[:300]}", flush=True); return r.returncode, r.stdout


def notiz(B, name, ok, **k):
    B["schritte"].append(dict(stufe=name, ok=ok, **k)); __import__("json_sicher").schreiben(B["_pfad"], B); print(f"    {name}: {k}", flush=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("quelle"); ap.add_argument("--ziel", required=True)
    ap.add_argument("--ab", default="anlegen", choices=STUFEN); ap.add_argument("--bis", default="vergleich", choices=STUFEN)
    ap.add_argument("--fremd", nargs="*", default=[]); ap.add_argument("--commons-kategorie", default=""); ap.add_argument("--ohne-video", action="store_true")
    ap.add_argument("--dicht-stufe", default="schnell", choices=["grob", "schnell", "fein"], help="schnell = ohne geometrischen PatchMatch-Durchgang (Standard 15.11.2026); fein nur wenn ein Tor zweifelt"); ap.add_argument("--referenz-wolke", default=""); ap.add_argument("--max-loesung", type=int, default=3); ap.add_argument("--fotos", default="", help="fotos_dir ersetzen")
    a = ap.parse_args()
    D = f"/media/oem/scan/rc-park_daten/{a.ziel}"; os.makedirs(D, exist_ok=True); log = os.path.join(D, "gesamtkette.log"); log_ab = sum(1 for _ in open(log, errors="replace")) if os.path.exists(log) else 0; t_lauf = time.time()
    Z = os.path.join(ROOT, "modelle", a.ziel); ZJ = os.path.join(Z, "objekt.json"); ZR = os.path.relpath(ZJ, ROOT)
    bp = os.path.join(D, "gesamtkette_bericht.json")
    B = json.load(open(bp)) if os.path.exists(bp) and a.ab != "anlegen" else dict(quelle=a.quelle, ziel=a.ziel, start=time.strftime("%Y-%m-%d %H:%M"), schritte=[])
    B.setdefault("schritte", []).append(dict(stufe="LAUF_START", ok=True, zeit=time.strftime("%Y-%m-%d %H:%M:%S"), ab=a.ab, bis=a.bis)); n_start = len(B["schritte"])      # 16.11.2026: der Bericht haengt alle Laeufe aneinander - Marke, damit man den letzten findet
    B["_pfad"] = bp; i0, i1 = STUFEN.index(a.ab), STUFEN.index(a.bis); dran = lambda s: i0 <= STUFEN.index(s) <= i1
    QJ = os.path.join(ROOT, "modelle", a.quelle, "objekt.json")

    if dran("anlegen"):
        if not os.path.exists(ZJ):
            lauf(B, "anlegen", ["python3", "-I", "tools/objekt_anlegen.py", a.ziel], log)
        q = json.load(open(QJ)); z = json.load(open(ZJ))
        for k in UEBERNEHMEN:
            if k in q: z[k] = q[k]
        if a.fotos: z["fotos_dir"] = a.fotos
        z["gesamtkette"] = dict(quelle=a.quelle, hinweis="von tools/gesamtkette.py angelegt; Masse/Pruefungen nur aus Quellen dieser Kette")
        __import__("json_sicher").schreiben(ZJ, z)
        if not isinstance(z.get("lod2"), dict) or not z["lod2"].get("id") or "rahmen" not in z:          # von null: Gebaeude per GML-Name, Rahmen aus Grundriss
            lauf(B, "rahmen_aus_lod2", [PY, "-I", "tools/rahmen_aus_lod2.py", ZR, "--schreiben"], log); z = json.load(open(ZJ))
        notiz(B, "anlegen", bool(z.get("lod2", {}).get("id")) and "rahmen" in z, lod2=z.get("lod2", {}).get("id"), fotos_dir=z.get("fotos_dir"))
    obj = json.load(open(ZJ)); fd = obj["fotos_dir"]; fd = fd if os.path.isabs(fd) else os.path.join(ROOT, fd)
    fremd = list(a.fremd); VF = os.path.join(D, "video_frames"); CO = os.path.join(D, "commons")

    kat = a.commons_kategorie or ((obj.get("bildquellen") or {}).get("commons", {}).get("kategorien") or [""])[0]   # objekt.json bildquellen
    if dran("commons") and kat:
        lauf(B, "commons", ["python3", "-I", "tools/commons_harvest.py", "--category", kat, "--max", "120", "--width", "1600", "--out", CO], log)
    bild = lambda d: os.path.isdir(d) and any(f.lower().endswith((".jpg", ".jpeg", ".png")) for f in os.listdir(d))
    if not bild(fd):                                       # Lehre Martinstor 2026-11-14: eigene Fotos verloren (Auslagerungsplatte) -> Commons-Kategorie wird Basis
        if not bild(CO): notiz(B, "basis", False, fehler=f"keine Bilder in fotos_dir {fd} und keine Commons-Ernte (--commons-kategorie)"); return 1
        fd = CO; obj["fotos_dir"] = CO; __import__("json_sicher").schreiben(ZJ, obj)
        notiz(B, "basis", True, fotos_dir=CO, hinweis="ANNAHME: Bilder der Commons-Kategorie zeigen das Objekt (Kategorie = Kuratierung); Ausreisser faellt die SfM")
    if os.path.isdir(CO) and CO not in fremd and os.path.realpath(CO) != os.path.realpath(fd): fremd.append(CO)

    if dran("video") and not a.ohne_video:
        VK = os.path.join(D, "video_kand")
        lauf(B, "video_suchen", [PY, "-I", "tools/video_suchen.py", ZR, "--aus", VK, "--suchen", "12"], log)
        lauf(B, "clips_waehlen", ["python3", "-I", "tools/clips_waehlen.py", os.path.join(VK, "video_kandidaten.json"), "--objekt", ZR, "--aus", os.path.join(D, "clips.json")], log)
        for c in json.load(open(os.path.join(D, "clips.json")))["gewaehlt"]:
            if not os.path.isdir(os.path.join(VF, c["id"])):
                lauf(B, f"frames_{c['id']}", ["python3", "tools/video_frames.py", "--url", f"https://www.youtube.com/watch?v={c['id']}", "--out", os.path.join(VF, c["id"]),
                                              "--fps", str(c["fps"]), "--max", str(c["max"]), "--min-sharp", "20"], log)
    if os.path.isdir(VF): fremd.append(VF)

    vp = os.path.join(D, "vorpruefung.json")
    if dran("vorpruefen"):
        if fremd: lauf(B, "vorpruefen", [PY, "-I", "tools/bilder_vorpruefen.py", ZR] + fremd + ["--aus", vp], log)
        else: notiz(B, "vorpruefen", True, uebersprungen="keine Fremdquellen")
    FV = os.path.join(D, "fotos")
    if dran("sammeln"):
        lauf(B, "sammeln", ["python3", "-I", "tools/fotos_sammeln.py", FV, "--eigen", fd] + (["--geprueft", vp] if os.path.exists(vp) else []), log)

    if os.path.isdir(FV) and len(os.listdir(FV)) > 0:                    # 16.11.2026 (Kettenlauf schwab_auto: 0 Fotos auf allen Fassaden, IndexError in fassaden_kette): die Kameras K-<name> heissen nach den GESAMMELTEN Fotos,
        ln = os.path.join(ROOT, "daten", a.ziel, "fotos"); oj = json.load(open(ZJ))      # objekt.json zeigte aber noch auf den Fotoordner der Quelle. Verknuepfung daten/<ziel>/fotos -> Sammelordner, fotos_dir darauf.
        if os.path.realpath(os.path.join(ROOT, oj.get("fotos_dir", ""))) != os.path.realpath(FV):
            os.makedirs(os.path.dirname(ln), exist_ok=True)
            if os.path.isdir(ln) and not os.path.islink(ln) and not os.listdir(ln): os.rmdir(ln)      # leerer Ordner aus Stufe anlegen
            if not os.path.lexists(ln): os.symlink(FV, ln)
            if os.path.realpath(ln) == os.path.realpath(FV):
                oj.setdefault("fotos_dir_quelle", oj.get("fotos_dir")); oj["fotos_dir"] = os.path.relpath(ln, ROOT); __import__("json_sicher").schreiben(ZJ, oj); notiz(B, "fotos_dir", True, hinweis=f"fotos_dir -> {oj['fotos_dir']} (Sammelordner); vorher {oj['fotos_dir_quelle']}")
            else: notiz(B, "fotos_dir", False, fehler=f"{ln} existiert und zeigt nicht auf {FV}")

    P = os.path.join(D, "pipe")
    if dran("sfm"):
        lauf(B, "sfm", [PY, "-u", "-I", "tools/pipeline_objekt.py", a.ziel, FV, P, "--stufe", a.dicht_stufe], log)
    W = os.path.join(Z, "sfm", f"punkte_modell_{a.ziel}.npy"); AU = os.path.join(Z, "messprotokoll", f"SFM-AUSRICHTUNG-{a.ziel}.json")

    def tore(tag):
        sp = os.path.join(P, "sfm", "sparse", "0"); erg = {}
        if os.path.isdir(sp): erg["kamera"] = lauf(B, f"tor_kamera{tag}", [PY, "-I", "tools/kamera_abdeckung.py", sp], log, ok=(0, 2))[0]
        erg["gps"] = lauf(B, f"tor_gps{tag}", [PY, "-I", "tools/lage_gps_pruefen.py", ZR, os.path.relpath(AU, ROOT), "--fotos", FV], log)[0] if os.path.exists(AU) else None
        if os.path.exists(AU): erg["kamera_gelaende"] = lauf(B, f"tor_kamera_gelaende{tag}", ["python3", "-I", "tools/kamera_gelaende.py", ZR, os.path.relpath(AU, ROOT)], log, ok=(0, 3))[0]   # Hinweis-Tor (15.11.): Bildgruppen unter Gelaende = Geisterwaende
        if os.path.isdir(sp): erg["insel"] = lauf(B, f"tor_insel{tag}", [PYC, "-I", "tools/kette_insel_pruefen.py", ZR, sp], log, ok=(0, 3))[0]   # 15.11. (Schwabentor): Bildketten ohne Fremdstuetze (Videoclip) = Faecher/Geisterwolke; schreibt audit/kette_insel.json
        erg["grundriss"] = lauf(B, f"tor_grundriss{tag}", [PY, "-I", "tools/wolke_grundriss_pruefen.py", ZR, "--wolke", W], log)[0] if os.path.exists(W) else None
        return erg

    if dran("tore"):
        erg = tore("")
        bestanden = lambda e: e.get("gps") in (0, None) and e.get("grundriss") == 0
        try:                                                             # 15.11.: Hoehen-Tor (DOM1-Laser gegen Modelldach) bei jedem neuen Objekt mit LoD2 in bauen_abnehmen einschalten
            _o = json.load(open(os.path.join(ROOT, ZR)))
            if _o.get("lod2", {}).get("id") and "hoehen_tor" not in _o: _o["hoehen_tor"] = True; json.dump(_o, open(os.path.join(ROOT, ZR), "w"), indent=1, ensure_ascii=False)
        except Exception as e_: print("hoehen_tor nicht gesetzt:", e_, flush=True)
        if (not bestanden(erg) or erg.get("insel") == 3) and (erg.get("kamera_gelaende") == 3 or erg.get("insel") == 3) and erg.get("gps") in (0, None):   # 15.11.: Geisterwand aus Kameras unter Gelaende -> ohne sie neu fusionieren (Minuten), Tore wiederholen
            rc_f, _ = lauf(B, "neu_fusionieren", [PYC, "-I", "tools/wolke_neu_fusionieren.py", ZR, P, "--stufe", a.dicht_stufe], log, ok=(0, 2))
            if rc_f == 0: erg = tore("_ohne_tiefe_kameras")
            if rc_f in (0, 2) and not bestanden(erg) and erg.get("grundriss") == 3:        # Haufen aus EINER Bildquelle (Geisterwand, Kameras nicht unter Gelaende) -> diese Bilder auch weg
                rc_h, _ = lauf(B, "neu_fusionieren_haufen", [PYC, "-I", "tools/wolke_neu_fusionieren.py", ZR, P, "--stufe", a.dicht_stufe, "--haufen"], log, ok=(0, 2))
                if rc_h == 0: erg = tore("_ohne_haufenquelle")
        kaputt = lambda e: e.get("gps") in (1, 4) or e.get("grundriss") == 1          # rc 1/4 = Werkzeug abgestuerzt/nicht geprueft (15.11.: CUDA out of memory) - kein Lage-Urteil
        if kaputt(erg): print(f"ABBRUCH: Tor-Werkzeug abgestuerzt/nicht geprueft {erg} (Log ansehen, z. B. GPU-Speicher) - KEIN Lage-Urteil", flush=True); B["lage"] = dict(tore=erg, bestanden=False, fehler="tor_abgestuerzt"); __import__("json_sicher").schreiben(bp, B); return 4
        k = 0
        while not bestanden(erg) and k < a.max_loesung:
            k += 1
            rc, out = lauf(B, f"korrektur_loesung{k}", [PY, "-u", "-I", "tools/sfm_lod2_ausrichten.py", ZR, "--kameras", os.path.join(P, "kameras.json"), "--dicht",
                                                        os.path.join(P, "dicht", "fused.ply"), "--name", a.ziel, "--radius", "30", "--schreiben", "--fotos", FV, "--loesung", str(k)], log, ok=(0, 5))
            if rc == 5: break
            if rc != 0: print(f"ABBRUCH: Ausrichtung Loesung {k} abgestuerzt (rc {rc}) - KEIN Lage-Urteil", flush=True); return 4
            erg = tore(f"_l{k}")
            if kaputt(erg): print(f"ABBRUCH: Tor-Werkzeug abgestuerzt {erg} - KEIN Lage-Urteil", flush=True); return 4
        B["lage"] = dict(loesung=k, tore=erg, bestanden=bestanden(erg)); __import__("json_sicher").schreiben(bp, B)
        print(f"    LAGE: Loesung {k}, Tore {erg} -> {'BESTANDEN' if bestanden(erg) else 'NICHT bestanden'}", flush=True)
        if not bestanden(erg):
            print("ABBRUCH: keine Lage besteht alle Tore - nicht modellieren (Bericht, audit/lage_gps.json, audit/wolke_grundriss.png)", flush=True); return 3

    if dran("dach"):
        lauf(B, "dach", [PY, "-I", "tools/dach_vermessen.py", ZR] + (["--wolke", W] if os.path.exists(W) else []), log)
    if dran("bauen"):
        lauf(B, "bauen", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1))
    KD = os.path.join(D, "kanten")
    if dran("kanten"):
        if os.path.exists(AU): lauf(B, "kanten", [PY, "-u", "-I", "tools/kantenstufe.py", ZR, "--ausrichtung", AU, "--bilder", FV, "--aus", KD], log, ok=(0, 4))
        else: notiz(B, "kanten", False, fehler=f"keine Ausrichtung {AU}")
    if dran("fototor") and os.path.exists(AU):
        lauf(B, "fototor_kameras", [PYC, "-I", "tools/kameras_aus_buendel.py", ZR, "--ausrichtung", AU, "--fotos", FV] + (["--sparse", os.path.join(P, "sfm", "sparse", "0")] if os.path.exists(os.path.join(P, "sfm", "sparse", "0", "images.bin")) else []), log)
        lauf(B, "kamera_plausibel", [PY, "-I", "tools/kamera_plausibel.py", Z, "--beiseite", "--tief=3"], log, ok=(0, 3))      # 16.11.2026: Kameras "am Mond" (Abstand/Zoom nicht trennbar) beiseitelegen, bevor ein Werkzeug sie benutzt
        kw = os.path.join(KD, "kam_wahl.json"); wahl = list(json.load(open(kw)))[:6] if os.path.exists(kw) else []
        for f in wahl: lauf(B, f"fototor_{os.path.splitext(f)[0]}", [PY, "-W", "ignore", "-I", "tools/foto_diff.py", ZR, os.path.splitext(f)[0], "--bild", os.path.join(FV, f)], log)
    gp_ = os.path.join(ROOT, "modelle", f"{a.ziel}_gen.py")           # 16.11.2026: schwab_auto hatte einen Generator aus einer alten Vorlage - Reliefs und Fenster wurden gerechnet, aber nie gebaut (Modell blieb bei 244 Dreiecken)
    if (dran("fassaden") or dran("fenster")) and os.path.exists(gp_) and not all(w_ in open(gp_).read() for w_ in ("fassaden_kette", "fenster_aus_json")):
        notiz(B, "generator_vorlage", False, fehler=f"{os.path.basename(gp_)} ruft fassaden_kette.anbauen / bauteile.fenster_aus_json nicht auf - Ergebnisse der Stufen fassaden/fenster kommen NICHT ins Modell (Zeilen aus der Vorlage in tools/objekt_anlegen.py uebernehmen)")
    if dran("fassaden") and os.path.exists(AU):                         # 15.11.2026: Fassaden-Kette automatisch (Netz -> Relief je LoD2-Wand -> Putz per Fotofarbe -> Steine in Loechern), danach neu bauen
        dd = os.path.join(P, "dicht"); nz = os.path.join(P, "openmvs", "mesh_modell_ausschnitt.npz")
        if os.path.exists(os.path.join(dd, "fused.ply")) and lauf(B, "fassaden_netz", [PY, "-I", "tools/netz_aus_dicht.py", ZR, dd], log)[0] == 0 and os.path.exists(nz):
            if lauf(B, "fassaden_kette", [PY, "-I", "tools/fassaden_kette.py", ZR, "--netz", nz, "--fotosteine"] + (["--fein", os.path.join(dd, "sparse"), FV] if os.path.isdir(os.path.join(dd, "sparse")) else []), log)[0] == 0: lauf(B, "bauen_mit_fassaden", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1))   # --fein: lokale Feinrechnung der Tiefe je Wand (GPU, ~11 min je Wand)
        else: notiz(B, "fassaden", False, fehler="kein dichter Ordner / Netz")
    if dran("fenster") and os.path.exists(AU):                          # 15.11.2026: Fenster automatisch (Mehrfoto-Ortho -> OWLv2 -> Scheiben gruppieren); Probe Nordgiebel Schwabentor-Nachbarhaus: 6 von 6 sichtbaren Fenstern, 1-4 cm
        fo = os.path.join(D, "fassade"); stl_ = os.path.join(ROOT, "modelle", "stl", f"{a.ziel}_1-87.stl"); fa = os.path.join(Z, "audit", "fenster_auto.json")
        if lauf(B, "fenster_ortho", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--stl", stl_, "--aus", fo, "--einzeln", "--min-flaeche", "6"], log)[0] == 0:
            try: nfo = sum(len(f_.get("fotos") or {}) for f_ in json.load(open(os.path.join(fo, "fassaden.json")))["fassaden"])
            except Exception: nfo = 0
            if nfo == 0: notiz(B, "fenster_ortho_inhalt", False, fehler="KEIN Foto auf irgendeiner Fassade - Kameras/fotos_dir pruefen (rc 0 allein beweist nichts; 16.11.2026 lief die Kette so leer durch)")
            env_alt = dict(os.environ); os.environ.update(HF_HOME="/media/oem/scan/hf_cache", HF_HUB_OFFLINE="1")
            if lauf(B, "fenster_parsing", [PY, "-W", "ignore", "-I", "tools/fassade_parsing.py", "--ortho", fo, "--gpu"], log)[0] == 0 and (lauf(B, "fenster_ortho_fein", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--stl", stl_, "--aus", fo + "_fein", "--einzeln", "--min-flaeche", "6", "--zelle", "0.01", "--max-mpp", "0.02", "--beste", "3"], log, ok=(0, 1))[0] in (0, 1)) and (lauf(B, "fenster_fein", [PY, "-I", "tools/fassade_fein.py", fo + "_fein"], log, ok=(0, 1))[0] in (0, 1)) and lauf(B, "fenster_bauen_liste", [PY, "-I", "tools/fenster_aus_parsing.py", fo, "--aus", fa, "--fein", fo + "_fein"], log)[0] == 0:   # feines, ausgerichtetes 1-cm-Bild fuer Sprossen/Muster (Nutzer 15.11.: "immer alle Details mitnehmen"); wo kein Foto <= 2 cm/px hat, bleibt das grobe
                lauf(B, "bauen_mit_fenstern", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1))
            os.environ.clear(); os.environ.update(env_alt)
    if dran("fenster") and os.path.exists(os.path.join(Z, "messprotokoll")):
        if not json.load(open(ZJ)).get("neben_fotos"): lauf(B, "neben_fotos_waehlen", [PY, "-W", "ignore", "-I", "tools/neben_fotos_waehlen.py", ZR, "--eintragen"], log, ok=(0, 3))      # 16.11.2026: ohne neben_fotos liefen Umriss-Tor und 'Modell neben Foto' leer durch
        lauf(B, "umriss_tor", [PY, "-W", "ignore", "-I", "tools/umriss_tor.py", ZR, "--eintragen"], log, ok=(0, 3))  # rc 2 (nichts geprueft) = Fehler im Bericht      # 16.11.2026: Dachlinie Modell gegen Himmelskante; Befunde -> beobachtungen_offen
    if dran("seiten") and os.path.exists(AU):                           # 16.11.2026 Nutzer (Schwabentor Ostseite): "Er muss doch wissen, dass dort Bilder fehlen und die sich dann holen, notfalls downloaden. Alles muss in die Pipeline."
        fo = os.path.join(D, "fassade"); sp = next((q_ for q_ in (os.path.join(P, "sparse_ba"), os.path.join(P, "dicht", "sparse"), os.path.join(P, "sparse", "0"), os.path.join(P, "sfm", "sparse_dicht"), os.path.join(P, "sfm", "sparse", "0"), os.path.join(P, "sfm", "sparse")) if os.path.exists(os.path.join(q_, "images.bin"))), None); db = next((q_ for q_ in (os.path.join(P, "db.db"), os.path.join(P, "sfm", "db.db")) if os.path.exists(q_)), os.path.join(P, "db.db"))
        try: nfo_s = sum(len(f_.get("fotos") or {}) for f_ in json.load(open(os.path.join(fo, "fassaden.json")))["fassaden"])
        except Exception: nfo_s = -1
        if nfo_s == 0: notiz(B, "seiten", False, fehler="kein Foto auf IRGENDEINER Fassade = Einrichtungsfehler (Kameras/fotos_dir), keine Fotoluecke - Download uebersprungen (16.11.2026: 32 min und 1,8 GB umsonst)")
        elif os.path.exists(os.path.join(fo, "fassaden.json")) and sp and os.path.exists(db):
            nf = len(json.load(open(os.path.join(fo, "fassaden.json")))["fassaden"]); vb = {}
            for i_ in range(nf):                                              # 16.11.2026: Vorbauten/Nischen automatisch (Ebenen-Sweep je Fassade); rc 2 = zu wenige Fotos, rc 4 = nicht belastbar
                if lauf(B, f"vorbauten_f{i_:02d}", [PY, "-W", "ignore", "-I", "tools/fassade_tiefe.py", ZR, fo, str(i_)], log, ok=(0, 2, 4))[0] == 0:
                    vj = os.path.join(fo, f"vorbauten_f{i_:02d}.json"); vb[f"f{i_:02d}"] = len(json.load(open(vj))["kandidaten"]) if os.path.exists(vj) else 0
            notiz(B, "vorbauten", True, kandidaten=vb, hinweis="Vorschlaege mit eigener Messebene (vorbauten_fNN.json, Bild tiefe_fNN.jpg ansehen); noch kein automatischer Bau")
            rc, out = lauf(B, "seiten_luecken", [PY, "-I", "tools/seiten_luecken.py", ZR, fo, "--sparse", sp, "--ref-db", db, "--download", "--holen"], log, ok=(0, 3))   # rc 3 = Wand ohne Foto: freie Quellen laden (Commons, Hochblicke, Openverse), Kandidaten nachregistrieren
            sl = os.path.join(Z, "audit", "seiten_luecken.json"); ung = json.load(open(sl)).get("ungesehen", []) if os.path.exists(sl) else []
            wj = os.path.join(Z, "fotowuensche.json"); lauf(B, "foto_auftrag", [PY, "-W", "ignore", "-I", "tools/foto_auftrag.py", ZR, fo, os.path.join(D, f"fotoauftrag_{a.ziel}.html")] + (["--wunsch", wj] if os.path.exists(wj) else []), log)   # 16.11.2026: dem Nutzer zeigen, welche Fotos fehlen (Lageplan, Standorte, markierte Ziele)
            notiz(B, "seiten", not ung, ungesehen=ung, hinweis="" if not ung else "nach dem Nachregistrieren fassade_ortho/fassade_fein neu; bleibt die Wand leer: Kontaktbogen audit/seiten_luecken_kandidaten.jpg ansehen, Kamera aus Modellpunkten + tools/fassade_ein_foto.py (PIPELINE_FASSADEN.md 'Ungesehene Seite')")
        else: notiz(B, "seiten", False, fehler="kein fassaden.json (Stufe fenster) oder kein SfM-Netz/Datenbank")
    if dran("html"):
        args = [PY, "-I", "tools/modell_3d_html.py", ZR, os.path.join(D, f"{a.ziel}_3d.html")]
        if os.path.exists(W): args += ["--wolke", W, "--farben", W.replace("punkte_modell_", "punkte_farben_")]
        lauf(B, "html", args, log)
    if dran("vergleich") and a.referenz_wolke and os.path.exists(W):       # 15.11.: in venv-seg (torch/gpu_knn); die Kette selbst laeuft mit System-Python
        code = ("import sys, json, numpy as np; sys.path.insert(0, 'tools'); from gpu_knn import min_abstand; rng = np.random.default_rng(0); "
                "N = np.load(sys.argv[1], mmap_mode='r'); R_ = np.load(sys.argv[2], mmap_mode='r'); "
                "n = np.asarray(N[rng.choice(len(N), min(200000, len(N)), replace=False)], float); r_ = np.asarray(R_[rng.choice(len(R_), min(400000, len(R_)), replace=False)], float); "
                "mr = np.median(r_[:, :2], 0); n = n[np.hypot(*(n[:, :2] - mr).T) < 30]; d = min_abstand(n, r_); "
                "print('VERGLEICH ' + json.dumps(dict(punkte=int(len(d)), median_m=round(float(np.median(d)), 3), anteil_unter_0_5m=round(float((d < 0.5).mean()), 3), p90_m=round(float(np.percentile(d, 90)), 3))))")
        rc, out = lauf(B, "vergleich", [PY, "-I", "-c", code, W, a.referenz_wolke], log)
        try:
            v = json.loads([l for l in out.splitlines() if l.startswith("VERGLEICH ")][-1][10:]); notiz(B, "vergleich_ergebnis", bool(v["median_m"] < 0.5), referenz=a.referenz_wolke, **v)
        except Exception as e: notiz(B, "vergleich_ergebnis", False, fehler=str(e)[:200])
    try:                                                                   # 15.11. (Nutzer): Warnungen aller Logs des Laufs in den Bericht - nichts ungelesen verwerfen
        sys.path.insert(0, os.path.join(ROOT, "tools")); import log_warnungen as LW
        w = LW.sammeln([log] + sorted(glob.glob(os.path.join(P, "*.log"))) + sorted(glob.glob(os.path.join(P, "sfm", "*.log"))), ab_zeile={log: log_ab}, seit=t_lauf)
        B["warnungen"] = [dict(n=e["n"], text=e["text"][:240], datei=os.path.basename(e["datei"]), zeile=e["zeile"]) for e in w[:40]]; __import__("json_sicher").schreiben(bp, B)
        print(f"WARNUNGEN im Lauf: {len(w)} verschiedene (Bericht 'warnungen'); haeufigste: " + " | ".join(f"{e['n']}x {e['text'][:90]}" for e in w[:3]), flush=True)
    except Exception as e: print("Warnungen nicht gesammelt:", type(e).__name__, e, flush=True)
    rot = [e for e in B["schritte"][n_start:] if e.get("ok") is False]      # 16.11.2026: die Kette endete IMMER mit rc 0 - auch mit abgestuerzten Stufen
    B["lauf_ergebnis"] = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), stufen=len(B["schritte"]) - n_start, fehlgeschlagen=[e["stufe"] for e in rot]); json.dump({k_: v_ for k_, v_ in B.items()}, open(bp + ".neu", "w"), indent=1, ensure_ascii=False); os.replace(bp + ".neu", bp)
    print(f"ERGEBNIS DES LAUFS: {len(B['schritte']) - n_start} Stufen, " + (f"{len(rot)} NICHT in Ordnung: " + ", ".join(e["stufe"] for e in rot) if rot else "alle in Ordnung"), flush=True)
    for e in rot: print(f"    {e['stufe']}: {str(e.get('fehler') or ' | '.join(e.get('ende', [])) or e.get('hinweis', ''))[:200]}", flush=True)
    print("GESAMTKETTE_ENDE", bp, flush=True); return 4 if rot else 0


if __name__ == "__main__":
    sys.exit(main())
