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
STUFEN = ["anlegen", "commons", "video", "vorpruefen", "sammeln", "sfm", "tore", "dach", "bauen", "kanten", "fototor", "fassaden", "fenster", "bauplan", "seiten", "html", "vergleich", "druck"]
UEBERNEHMEN = ["name", "ort", "lod2", "rahmen", "rahmen_wand", "koordinate_utm", "hoehe_m", "fotos_dir", "seiten_konvention", "bildquellen"]


class _Erg:                                                                  # wie subprocess.CompletedProcess (returncode, stdout)
    def __init__(self, rc, out): self.returncode, self.stdout = rc, out


_ABSCHLUSS = [None]                                                          # Abschlussfunktion des laufenden Kettenlaufs (fuer Abbrueche aus lauf())
DATEN = "/media/oem/scan"                                                    # Datenplatte: alles Grosse liegt hier (CLAUDE.md); Test: RCPARK_DATEN


def platz_fehler(pfade, min_gb=None):
    """Freier Platz auf den Dateisystemen, auf denen `pfade` WIRKLICH liegen (Verknuepfungen aufgeloest). '' = in Ordnung, sonst Fehlertext.
    17.11.2026: tools/platz_pruefen.py sieht nur / und die Datenplatte; kaufhaus_gk/pipe ist aber eine Verknuepfung auf eine externe Platte - voll oder nicht eingehaengt blieb unbemerkt
    (alle `os.path.exists(pipe/...)` sind dann einfach falsch, die Stufen wurden still uebersprungen)."""
    min_gb = float(os.environ.get("RCPARK_PLATZ_MIN_GB", "5")) if min_gb is None else min_gb
    for p in pfade:
        if os.path.islink(p) and not os.path.exists(p): return f"{p} ist eine Verknuepfung auf {os.path.realpath(p)} - Ziel fehlt (Platte nicht eingehaengt?)"
        q = os.path.realpath(p)
        while not os.path.exists(q) and q != os.path.dirname(q): q = os.path.dirname(q)
        frei = shutil.disk_usage(q).free / 1e9
        if frei < min_gb: return f"nur {frei:.1f} GB frei auf der Platte von {p} (-> {os.path.realpath(p)}), Grenze {min_gb:g} GB"
    return ""


def platte_fehler(daten=None):
    """Die Datenplatte muss eingehaengt sein, sonst legt `os.makedirs` die Kettenordner still auf der Systemplatte an (dort ist kein Platz fuer SfM/Wolken)."""
    daten = daten or os.environ.get("RCPARK_DATEN", DATEN)
    return "" if os.path.ismount(daten) else f"Datenplatte {daten} ist nicht eingehaengt - die Kette wuerde ihre Ordner auf der Systemplatte anlegen"


def frisch(pfad, seit):
    """True, wenn die Datei existiert und seit dem Zeitpunkt `seit` (time.time() vor dem Stufenstart) geschrieben wurde - sonst ist sie die Ausgabe eines FRUEHEREN Laufs."""
    return os.path.exists(pfad) and os.path.getmtime(pfad) >= seit - 2.0


def lauf(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
    """Eine Stufe starten. 16.11.2026 (Stabilisierung): Ausgabe laeuft ZEILENWEISE ins Log (vorher erst am Stufenende - eine 30-Minuten-Stufe war blind, ein Haenger nicht zu erkennen);
    Zeitlimit je Stufe (Standard RCPARK_STUFE_MAX_S = 3 h, die Prozessgruppe wird beendet) - ein Haenger auf einem Kern hielt am 16.11. die Kette stundenlang an."""
    import threading, signal
    if subprocess.run(["python3", os.path.join(ROOT, "tools", "platz_pruefen.py")], capture_output=True).returncode != 0:      # Platztor VOR jeder Stufe (16.11.2026: Systemplatte lief mitten im Lauf unter 5 GB, die Stufe danach scheiterte halb)
        e = dict(stufe=name, rc=3, ok=False, sekunden=0, fehler="PLATZ ZU KNAPP vor Stufenstart (tools/platz_pruefen.py) - Kette haelt an"); B["schritte"].append(e); __import__("json_sicher").schreiben(B["_pfad"], B); print("    FEHLER: " + e["fehler"], flush=True)
        if _ABSCHLUSS[0]: _ABSCHLUSS[0](3)                                                            # 17.11.2026: auch dieser Abbruch schreibt 'lauf_ergebnis' (sonst steht im Bericht das Ergebnis des VORIGEN Laufs)
        raise SystemExit(3)
    pf_ = platz_fehler(platz) if platz else ""
    if pf_:                                                                                           # 17.11.2026: Stufe schreibt auf eine andere Platte (Verknuepfung) - dort pruefen; kein Abbruch der Kette, die Stufe gilt als gescheitert
        e = dict(stufe=name, rc=3, ok=False, sekunden=0, fehler="PLATZ/PLATTE: " + pf_ + " - Stufe nicht gestartet"); B["schritte"].append(e); __import__("json_sicher").schreiben(B["_pfad"], B); print("    FEHLER: " + e["fehler"], flush=True); return 3, ""
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
    if r.returncode < 0: e["ok"] = False; e["fehler"] = f"vom System beendet (Signal {-r.returncode}" + (", vermutlich Arbeitsspeicher voll" if r.returncode == -9 else "") + ")"; print("    FEHLER: " + e["fehler"], flush=True)      # 17.11.2026: rc -9 stand ohne Erklaerung im Bericht
    if "tools/bauen_abnehmen.sh" in cmd and "ERGEBNIS:" not in r.stdout: e["ok"] = False; e["fehler"] = "Bau/Abnahme lief nicht bis zur Ergebniszeile (Generator abgestuerzt oder vom System beendet?) - rc 1 heisst hier NICHT 'nur Pruefstand rot'"; print("    FEHLER: " + e["fehler"], flush=True)      # 16.11.2026: rc 1 galt als bestanden, ein Python-Absturz im Generator gibt aber auch rc 1
    B["schritte"].append(e); __import__("json_sicher").schreiben(B["_pfad"], B)
    print(f"    rc {r.returncode} ({e['sekunden']} s) {' | '.join(e['ende'])[:300]}", flush=True); return r.returncode, r.stdout


def notiz(B, name, ok, **k):
    B["schritte"].append(dict(stufe=name, ok=ok, **k)); __import__("json_sicher").schreiben(B["_pfad"], B); print(f"    {name}: {k}", flush=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("quelle"); ap.add_argument("--ziel", required=True)
    ap.add_argument("--trotz-lage", action="store_true", help="Fotostufen auch dann rechnen, wenn die Lage-Tore rot sind (nur zum Untersuchen)"); ap.add_argument("--ab", default="anlegen", choices=STUFEN); ap.add_argument("--bis", default="vergleich", choices=STUFEN)
    ap.add_argument("--fremd", nargs="*", default=[]); ap.add_argument("--commons-kategorie", default=""); ap.add_argument("--ohne-video", action="store_true"); ap.add_argument("--ohne-netz", action="store_true", help="Stufe commons: nur die Commons-Kategorie, keine weiteren Netzquellen (tools/netz_fotos_holen.py)")
    ap.add_argument("--ohne-weitere-fotos", action="store_true", help="nur fotos_dir + Commons/Video (alt); Standard: alle Fotoordner des Objekts unter rc-park_daten (tools/fotoquellen.py) als Fremdquelle vorpruefen")
    ap.add_argument("--dicht-stufe", default="schnell", choices=["grob", "schnell", "fein"], help="schnell = ohne geometrischen PatchMatch-Durchgang (Standard 15.11.2026); fein nur wenn ein Tor zweifelt"); ap.add_argument("--referenz-wolke", default=""); ap.add_argument("--max-loesung", type=int, default=3); ap.add_argument("--fotos", default="", help="fotos_dir ersetzen"); ap.add_argument("--mapper", default="", choices=["", "auto", "auto_alt", "global", "inkrementell", "konsens"], help="an iphone_sfm.py durchreichen; leer = dessen Standard (auto = Konsens zuerst, bei Datenmangel Meldung + alter Weg). konsens = erzwingen: zwei globale Laeufe + Rueckgrat (modelle/GLOBALER_MAPPER_STABIL.md)")
    a = ap.parse_args()
    if platte_fehler(): print("ABBRUCH: " + platte_fehler(), flush=True); return 2                  # 17.11.2026: ohne eingehaengte Datenplatte entstand der Kettenordner auf der Systemplatte
    D = f"/media/oem/scan/rc-park_daten/{a.ziel}"; os.makedirs(D, exist_ok=True); log = os.path.join(D, "gesamtkette.log"); log_ab = sum(1 for _ in open(log, errors="replace")) if os.path.exists(log) else 0; t_lauf = time.time()
    Z = os.path.join(ROOT, "modelle", a.ziel); ZJ = os.path.join(Z, "objekt.json"); ZR = os.path.relpath(ZJ, ROOT)
    bp = os.path.join(D, "gesamtkette_bericht.json")
    B = json.load(open(bp)) if os.path.exists(bp) and a.ab != "anlegen" else dict(quelle=a.quelle, ziel=a.ziel, start=time.strftime("%Y-%m-%d %H:%M"), schritte=[])
    B.setdefault("schritte", []).append(dict(stufe="LAUF_START", ok=True, zeit=time.strftime("%Y-%m-%d %H:%M:%S"), ab=a.ab, bis=a.bis)); n_start = len(B["schritte"])      # 16.11.2026: der Bericht haengt alle Laeufe aneinander - Marke, damit man den letzten findet
    B["_pfad"] = bp; i0, i1 = STUFEN.index(a.ab), STUFEN.index(a.bis); dran = lambda s: i0 <= STUFEN.index(s) <= i1
    QJ = os.path.join(ROOT, "modelle", a.quelle, "objekt.json"); P = os.path.join(D, "pipe")

    def abschluss(rc=0, abbruch=""):
        """Ende JEDES Laufs, auch der Abbrueche (17.11.2026: `return 3/4` mitten in der Kette liess 'lauf_ergebnis' und oft auch 'lage' des VORIGEN Laufs im Bericht stehen - der Bericht sah gut aus, der Lauf war abgebrochen)."""
        _ABSCHLUSS[0] = None
        if abbruch: print("ABBRUCH: " + abbruch, flush=True); notiz(B, "abbruch", False, fehler=abbruch)
        try:                                                                   # 15.11. (Nutzer): Warnungen aller Logs des Laufs in den Bericht - nichts ungelesen verwerfen
            sys.path.insert(0, os.path.join(ROOT, "tools")); import log_warnungen as LW
            w = LW.sammeln([log] + sorted(glob.glob(os.path.join(P, "*.log"))) + sorted(glob.glob(os.path.join(P, "sfm", "*.log"))), ab_zeile={log: log_ab}, seit=t_lauf)
            B["warnungen"] = [dict(n=e["n"], text=e["text"][:240], datei=os.path.basename(e["datei"]), zeile=e["zeile"]) for e in w[:40]]
            print(f"WARNUNGEN im Lauf: {len(w)} verschiedene (Bericht 'warnungen'); haeufigste: " + " | ".join(f"{e['n']}x {e['text'][:90]}" for e in w[:3]), flush=True)
        except Exception as e: print("Warnungen nicht gesammelt:", type(e).__name__, e, flush=True)
        rot = [e for e in B["schritte"][n_start:] if e.get("ok") is False]      # 16.11.2026: die Kette endete IMMER mit rc 0 - auch mit abgestuerzten Stufen
        rc = rc or (4 if rot else 0)
        B["lauf_ergebnis"] = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), stufen=len(B["schritte"]) - n_start, fehlgeschlagen=[e["stufe"] for e in rot], rc=rc, abbruch=abbruch); __import__("json_sicher").schreiben(bp, B)
        print(f"ERGEBNIS DES LAUFS: {len(B['schritte']) - n_start} Stufen, " + (f"{len(rot)} NICHT in Ordnung: " + ", ".join(e["stufe"] for e in rot) if rot else "alle in Ordnung") + (" - ABGEBROCHEN" if abbruch else ""), flush=True)
        for e in rot: print(f"    {e['stufe']}: {str(e.get('fehler') or ' | '.join(e.get('ende', [])) or e.get('hinweis', ''))[:200]}", flush=True)
        print("GESAMTKETTE_ENDE", bp, flush=True); return rc
    _ABSCHLUSS[0] = abschluss
    if os.path.islink(P) and not os.path.exists(P) and any(dran(s_) for s_ in ("sfm", "tore", "fassaden", "seiten")):      # 17.11.2026: kaufhaus_gk/pipe zeigt auf eine externe Platte; ist sie nicht eingehaengt, sind alle `exists(pipe/...)` falsch und die Stufen fielen still aus
        notiz(B, "pipe", False, fehler=f"{P} ist eine Verknuepfung auf {os.path.realpath(P)} - Ziel fehlt (Platte nicht eingehaengt?). Stufen sfm/tore/fassaden/seiten finden ihr SfM-Netz, die dichte Wolke und das Netz nicht")

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
    if not os.path.exists(ZJ): return abschluss(2, f"{ZR} fehlt - zuerst Stufe 'anlegen' (--ab anlegen)")
    obj = json.load(open(ZJ)); fd = obj["fotos_dir"]; fd = fd if os.path.isabs(fd) else os.path.join(ROOT, fd)
    if obj.get("fotos_dir_quelle") and os.path.realpath(fd) == os.path.realpath(os.path.join(D, "fotos")):      # 17.11.2026: nach dem ersten Lauf zeigt fotos_dir auf den SAMMELORDNER (siehe unten). Ein Einstieg --ab commons..sammeln nahm ihn dann
        fd = obj["fotos_dir_quelle"]; fd = fd if os.path.isabs(fd) else os.path.join(ROOT, fd)                  # als 'eigene Fotos': alle Fremdbilder wurden zu eigen__eigen__..., die Namen passten nicht mehr zu Netz und K-Dateien, Fremdbilder bestaetigten sich selbst
    fremd = list(a.fremd); VF = os.path.join(D, "video_frames"); CO = os.path.join(D, "commons")
    if not a.ohne_weitere_fotos and dran("vorpruefen"):      # 17.11.2026 (kaufhaus_gk gegen Handmodell grob3): nur fotos_dir (333) + Commons gesammelt; iPhone-Fotos, Handyserien, Nutzerfotos, Videobilder und Mapillary
        from fotoquellen import finden as fotoquellen_finden    # desselben Gebaeudes (rund 2700 Bilder in 46 Ordnern unter rc-park_daten/kaufhaus*) blieben liegen. Alle als Fremdquelle -> bilder_vorpruefen entscheidet je Bild.
        aus_ = list((obj.get("fotos_eingang") or {}).get("ausschluss") or []) + list(obj.get("fotos_ausschluss") or [])
        weitere = [d_ for d_, _ in fotoquellen_finden(fd, ziel=D, ausschluss=aus_) if d_ not in fremd]; fremd += weitere
        notiz(B, "weitere_fotos", True, ordner=len(weitere), hinweis="tools/fotoquellen.py: " + "; ".join(os.path.relpath(d_, os.path.dirname(D)) for d_ in weitere[:60]))

    kat = a.commons_kategorie or ((obj.get("bildquellen") or {}).get("commons", {}).get("kategorien") or [""])[0]   # objekt.json bildquellen
    if dran("commons") and kat:
        lauf(B, "commons", ["python3", "-I", "tools/commons_harvest.py", "--category", kat, "--max", "120", "--width", "1600", "--out", CO], log)
    NZ = os.path.join(D, "netz")                                         # 19.11.2026 (Nutzer: "der automatische Bilderholer muss in die Pipeline"): ALLE freien Netzquellen VOR der SfM (Openverse/Flickr, Commons-Umkreis,
    if dran("commons") and not a.ohne_netz:                              # Hochblicke) - bisher erst in der spaeten Stufe 'seiten', die bei gescheiterter Lage nie drankam. Zwischenspeicher 7 Tage (netz_stand.json).
        bw = [D] + [x_ for x_ in [os.path.join(os.path.dirname(D), a.quelle)] if os.path.isdir(x_) and os.path.realpath(x_) != os.path.realpath(D)]
        rc_n = lauf(B, "netz_fotos", [PY, "-I", "tools/netz_fotos_holen.py", ZR, "--aus", NZ, "--bekannt-wurzel"] + bw, log, ok=(0, 2), timeout=4 * 3600)[0]
        if rc_n == 2: notiz(B, "netz_fotos_quellen", False, fehler="keine Netzquelle erreicht (kein Netz?) - es wird nur mit dem Bestand gerechnet")
    if os.path.isdir(NZ) and NZ not in fremd: fremd.append(NZ)
    bild = lambda d: os.path.isdir(d) and any(f.lower().endswith((".jpg", ".jpeg", ".png")) for f in os.listdir(d))
    if not bild(fd):                                       # Lehre Martinstor 2026-11-14: eigene Fotos verloren (Auslagerungsplatte) -> Commons-Kategorie wird Basis
        if not bild(CO): notiz(B, "basis", False, fehler=f"keine Bilder in fotos_dir {fd} und keine Commons-Ernte (--commons-kategorie)"); return abschluss(1)
        fd = CO; obj["fotos_dir"] = CO; __import__("json_sicher").schreiben(ZJ, obj)
        notiz(B, "basis", True, fotos_dir=CO, hinweis="ANNAHME: Bilder der Commons-Kategorie zeigen das Objekt (Kategorie = Kuratierung); Ausreisser faellt die SfM")
    if os.path.isdir(CO) and CO not in fremd and os.path.realpath(CO) != os.path.realpath(fd): fremd.append(CO)

    if dran("video") and not a.ohne_video:
        VK = os.path.join(D, "video_kand")
        t_c = time.time(); cj = os.path.join(D, "clips.json")      # 17.11.2026: scheiterte die Suche (kein Netz) oder die Clipwahl, las die Kette die clips.json eines FRUEHEREN Laufs - oder stuerzte ohne Bericht ab, wenn es keine gab
        clips = []
        if lauf(B, "video_suchen", [PY, "-I", "tools/video_suchen.py", ZR, "--aus", VK, "--suchen", "12"], log)[0] == 0 and lauf(B, "clips_waehlen", ["python3", "-I", "tools/clips_waehlen.py", os.path.join(VK, "video_kandidaten.json"), "--objekt", ZR, "--aus", cj], log)[0] == 0:
            if frisch(cj, t_c): clips = json.load(open(cj)).get("gewaehlt", [])
            else: notiz(B, "video", False, fehler=f"{cj} wurde von der Clipwahl nicht neu geschrieben - alte Clipliste wird NICHT verwendet")
        else: notiz(B, "video", False, fehler="Videosuche/Clipwahl gescheitert - keine neuen Videobilder in diesem Lauf (Bilder frueherer Laeufe unter video_frames bleiben Fremdquelle)")
        for c in clips:
            if not bild(os.path.join(VF, c["id"])):      # 17.11.2026: 'Ordner existiert' galt als erledigt - ein gescheiterter Download (kaufhaus_gk: 12 leere Clip-Ordner, yt-dlp-Fehler) wurde nie wiederholt
                lauf(B, f"frames_{c['id']}", ["python3", "tools/video_frames.py", "--url", f"https://www.youtube.com/watch?v={c['id']}", "--out", os.path.join(VF, c["id"]),
                                              "--fps", str(c["fps"]), "--max", str(c["max"]), "--min-sharp", "20"], log)
    if os.path.isdir(VF): fremd.append(VF)

    vp = os.path.join(D, "vorpruefung.json")
    vp_ok = os.path.exists(vp)
    if dran("vorpruefen"):
        if fremd:
            t_v = time.time(); vp_ok = lauf(B, "vorpruefen", [PY, "-I", "tools/bilder_vorpruefen.py", ZR] + fremd + ["--aus", vp], log)[0] == 0 and frisch(vp, t_v)
            if not vp_ok: notiz(B, "vorpruefen_ergebnis", False, fehler="Vorpruefung gescheitert oder vorpruefung.json nicht neu geschrieben - Fremdbilder werden in diesem Lauf NICHT gesammelt (17.11.2026: vorher galt still die Liste eines frueheren Laufs)")
        else: notiz(B, "vorpruefen", True, uebersprungen="keine Fremdquellen"); vp_ok = False
    FV = os.path.join(D, "fotos")
    if dran("sammeln"):
        if lauf(B, "sammeln", ["python3", "-I", "tools/fotos_sammeln.py", FV, "--eigen", fd] + (["--geprueft", vp] if vp_ok else []), log)[0] != 0 or not bild(FV):
            return abschluss(4, f"Fotos sammeln gescheitert oder Sammelordner {FV} leer - die folgenden Stufen wuerden mit dem Ordner eines frueheren Laufs rechnen")

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
    W = os.path.join(Z, "sfm", f"punkte_modell_{a.ziel}.npy"); AU = os.path.join(Z, "messprotokoll", f"SFM-AUSRICHTUNG-{a.ziel}.json")
    if dran("sfm"):
        # 17.11.2026: (1) scheiterte die SfM, rechneten Tore und alle Folgestufen mit Wolke/Ausrichtung eines FRUEHEREN Laufs weiter. (2) pipeline_objekt.py endet auch dann mit rc 0, wenn sein
        # LoD2-Abgleich abstuerzt (Zeile 'abgleich ... FEHLER' steht nur in pipe/pipeline.log) - dann sind Wolke und Ausrichtung alt. Beides: Abbruch statt stiller Weiterarbeit. 'lage' gilt bis zum naechsten Tor-Lauf als ungeprueft.
        t_s = time.time(); rc_s = lauf(B, "sfm", [PY, "-u", "-I", "tools/pipeline_objekt.py", a.ziel, FV, P, "--stufe", a.dicht_stufe] + (["--mapper", a.mapper] if a.mapper else []), log, platz=[P])[0]
        B["lage"] = dict(bestanden=None, hinweis="neue SfM - Lage-Tore noch nicht gelaufen (Stufe 'tore')")
        mwj = os.path.join(P, "sfm", "mapper_wahl.json")                         # 19.11.2026 (Nutzer): trug der Konsens-Mapper nicht, steht der DATENMANGEL als eigene rote Zeile im Bericht (nie still die langsamere/schlechtere Methode)
        try:
            mw = json.load(open(mwj)) if os.path.isfile(mwj) and os.path.getmtime(mwj) >= t_s else {}
            if mw.get("datenmangel"): print("ACHTUNG DATENMANGEL (Mapper): " + "; ".join(mw["datenmangel"].get("ursachen", [])) + " | ABHILFE: " + mw["datenmangel"].get("abhilfe", ""), flush=True); notiz(B, "datenmangel", False, mapper=mw.get("gewaehlt"), **mw["datenmangel"])
            elif mw: notiz(B, "mapper", True, gewaehlt=mw.get("gewaehlt"), sekunden=mw.get("konsens_sek") or mw.get("global_sek"))
        except Exception as e_: print("HINWEIS mapper_wahl.json nicht lesbar:", e_, flush=True)
        if rc_s != 0: return abschluss(4, f"SfM gescheitert (rc {rc_s}) - Wolke/Ausrichtung eines frueheren Laufs werden NICHT weiterverwendet")
        alt = [x_ for x_ in (W, AU) if not frisch(x_, t_s)]
        if alt: return abschluss(4, "SfM endete mit rc 0, schrieb aber NICHT neu: " + ", ".join(os.path.relpath(x_, ROOT) for x_ in alt) + f" (LoD2-Abgleich gescheitert? {P}/pipeline.log) - alte Wolke/Ausrichtung werden nicht weiterverwendet")

    def tore(tag):
        sp = os.path.join(P, "sfm", "sparse", "0"); erg = {}
        if not os.path.isdir(sp): notiz(B, f"tor_kamera{tag}", False, fehler=f"kein SfM-Netz {sp} - Kameraabdeckung und Insel-Tor NICHT geprueft (17.11.2026: wurden still uebersprungen)")
        if not os.path.exists(AU): notiz(B, f"tor_gps{tag}", False, fehler=f"keine Ausrichtung {AU} - GPS-Tor und Kamera-Gelaende-Tor NICHT geprueft")
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
            if _o.get("lod2", {}).get("id") and "hoehen_tor" not in _o: _o["hoehen_tor"] = True; __import__("json_sicher").schreiben(os.path.join(ROOT, ZR), _o)
        except Exception as e_: print("hoehen_tor nicht gesetzt:", e_, flush=True)
        if (not bestanden(erg) or erg.get("insel") == 3) and (erg.get("kamera_gelaende") == 3 or erg.get("insel") == 3) and erg.get("gps") in (0, None):   # 15.11.: Geisterwand aus Kameras unter Gelaende -> ohne sie neu fusionieren (Minuten), Tore wiederholen
            rc_f, _ = lauf(B, "neu_fusionieren", [PYC, "-I", "tools/wolke_neu_fusionieren.py", ZR, P, "--stufe", a.dicht_stufe], log, ok=(0, 2), platz=[P])
            if rc_f == 0: erg = tore("_ohne_tiefe_kameras")
            if rc_f in (0, 2) and not bestanden(erg) and erg.get("grundriss") == 3:        # Haufen aus EINER Bildquelle (Geisterwand, Kameras nicht unter Gelaende) -> diese Bilder auch weg
                rc_h, _ = lauf(B, "neu_fusionieren_haufen", [PYC, "-I", "tools/wolke_neu_fusionieren.py", ZR, P, "--stufe", a.dicht_stufe, "--haufen"], log, ok=(0, 2))
                if rc_h == 0: erg = tore("_ohne_haufenquelle")
        kaputt = lambda e: e.get("gps") in (1, 4) or e.get("grundriss") in (1, 4)          # rc 1/4 = Werkzeug abgestuerzt/nicht geprueft (15.11.: CUDA out of memory) - kein Lage-Urteil
        if kaputt(erg): B["lage"] = dict(tore=erg, bestanden=False, fehler="tor_abgestuerzt"); return abschluss(4, f"Tor-Werkzeug abgestuerzt/nicht geprueft {erg} (Log ansehen, z. B. GPU-Speicher) - KEIN Lage-Urteil")
        k = 0
        while not bestanden(erg) and k < a.max_loesung:
            k += 1
            rc, out = lauf(B, f"korrektur_loesung{k}", [PY, "-u", "-I", "tools/sfm_lod2_ausrichten.py", ZR, "--kameras", os.path.join(P, "kameras.json"), "--dicht",
                                                        os.path.join(P, "dicht", "fused.ply"), "--name", a.ziel, "--radius", "30", "--schreiben", "--fotos", FV, "--loesung", str(k)], log, ok=(0, 5))
            if rc == 5: break
            if rc != 0: B["lage"] = dict(loesung=k, tore=erg, bestanden=False, fehler="ausrichtung_abgestuerzt"); return abschluss(4, f"Ausrichtung Loesung {k} abgestuerzt (rc {rc}) - KEIN Lage-Urteil")      # 17.11.2026: 'lage' blieb hier auf dem Stand des vorigen Laufs (evtl. 'bestanden')
            erg = tore(f"_l{k}")
            if kaputt(erg): B["lage"] = dict(loesung=k, tore=erg, bestanden=False, fehler="tor_abgestuerzt"); return abschluss(4, f"Tor-Werkzeug abgestuerzt {erg} - KEIN Lage-Urteil")
        B["lage"] = dict(loesung=k, tore=erg, bestanden=bestanden(erg)); __import__("json_sicher").schreiben(bp, B)
        print(f"    LAGE: Loesung {k}, Tore {erg} -> {'BESTANDEN' if bestanden(erg) else 'NICHT bestanden'}", flush=True)
        if not bestanden(erg) and k > 0:                                     # 17.11.2026 (Stabilitaetsrunde): nach gescheitertem Kreislauf lag die LETZTE Loesung auf der Platte (Martinstor: Loesung 3 von 10, Guete 0,9 %) - Loesung 0 zurueckschreiben
            lauf(B, "loesung0_zurueck", [PY, "-u", "-I", "tools/sfm_lod2_ausrichten.py", ZR, "--kameras", os.path.join(P, "kameras.json"), "--dicht", os.path.join(P, "dicht", "fused.ply"), "--name", a.ziel, "--radius", "30", "--schreiben", "--fotos", FV, "--loesung", "0"], log, ok=(0, 5))
            # 18.11.2026 (Kaufhaus gk2g --ab tore): die ersten Tore prueften die ALTE Ausrichtung der Stufe sfm; der Kreislauf rechnete mit neuem Code eine gute Loesung 0
            # (Guete 48 %, GPS-Veto bestanden), fand keine zweite (rc 5) - und die zurueckgeschriebene Loesung 0 wurde nie geprueft -> Abbruch. Jetzt: Tore auf der neuen Loesung 0.
            erg0 = tore("_l0neu")
            if kaputt(erg0): B["lage"] = dict(loesung=0, tore=erg0, bestanden=False, fehler="tor_abgestuerzt"); return abschluss(4, f"Tor-Werkzeug abgestuerzt {erg0} - KEIN Lage-Urteil")
            print(f"    LAGE: Loesung 0 neu gerechnet, Tore {erg0} -> {'BESTANDEN' if bestanden(erg0) else 'NICHT bestanden'}", flush=True)
            if bestanden(erg0): erg = erg0; B["lage"] = dict(loesung=0, tore=erg, bestanden=True, hinweis="Loesung 0 nach dem Kreislauf neu gerechnet und geprueft"); __import__("json_sicher").schreiben(bp, B)
        if not bestanden(erg):
            return abschluss(3, "keine Lage besteht alle Tore - nicht modellieren (Bericht, audit/lage_gps.json, audit/wolke_grundriss.png)")

    if "bestanden" in (B.get("lage") or {}) and not B["lage"]["bestanden"] and "--trotz-lage" not in sys.argv:      # 17.11.2026: am Martinstor waren ALLE Lage-Tore rot (GPS widerspricht, Grundriss passt nicht) - die Kette baute trotzdem Fassaden aus dem falsch liegenden Netz (9 % Bilddaten, 0 Fenster)
        gesperrt = [s_ for s_ in ("kanten", "fototor", "fassaden", "fenster", "seiten") if dran(s_)]
        if gesperrt:
            notiz(B, "lage_tor", False, fehler=f"Lage des Fotonetzes ist NICHT belegt ({B['lage'].get('hinweis') or B['lage'].get('fehler') or ''} Tore {B['lage'].get('tore')}) - Stufen {', '.join(gesperrt)} uebersprungen. Erst Ausrichtung klaeren (mehr Fotos rundum, GPS, Stufe 'tore'); erzwingen: --trotz-lage")
            _dran0 = dran; dran = lambda s_: _dran0(s_) and s_ not in gesperrt
    if dran("dach"):
        lauf(B, "dach", [PY, "-I", "tools/dach_vermessen.py", ZR] + (["--wolke", W] if os.path.exists(W) else []), log)
    if dran("bauen"):
        t_b = time.time(); lauf(B, "bauen", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1)); stl_b = os.path.join(ROOT, json.load(open(ZJ)).get("stl") or os.path.join("modelle", "stl", f"{a.ziel}_1-87.stl"))
        if not frisch(stl_b, t_b): notiz(B, "bauen_stl", False, fehler=f"{os.path.relpath(stl_b, ROOT)} wurde vom Bau NICHT neu geschrieben - Kanten, Foto-Tor, Fassadenbilder und 3D-Seite dieses Laufs zeigen das Modell eines frueheren Baus")      # 17.11.2026: nach gescheitertem Bau lasen alle Folgestufen das alte STL als frisch
    KD = os.path.join(D, "kanten")
    if dran("kanten"):
        if os.path.exists(AU):
            if lauf(B, "kanten", [PY, "-u", "-I", "tools/kantenstufe.py", ZR, "--ausrichtung", AU, "--bilder", FV, "--aus", KD], log, ok=(0, 4))[0] == 4:      # 17.11.2026: rc 4 (< 6 Kameras sehen das Modell / < 2000 Kantenpunkte) stand als 'in Ordnung' im Bericht -
                notiz(B, "kanten_ergebnis", False, fehler="Kantenstufe OHNE Ergebnis (rc 4: zu wenige Kameras oder Kantenpunkte, kein Kanten-F1) - Kernmethode nicht erfuellt; Kameras/Stabilkarten pruefen (kanten_bericht.json 'fehler')")      # die Kernmethode (Fotokanten) lief leer
        else: notiz(B, "kanten", False, fehler=f"keine Ausrichtung {AU}")
    for s_ in ("fototor", "fassaden", "seiten"):                         # 17.11.2026: ohne Ausrichtung fielen diese Stufen STILL aus ("alle in Ordnung" bei 0 Stufen)
        if dran(s_) and not os.path.exists(AU): notiz(B, s_, False, fehler=f"keine Ausrichtung {AU} - Stufe {s_} NICHT gelaufen")
    if dran("fototor") and os.path.exists(AU):
        rc_k = lauf(B, "fototor_kameras", [PYC, "-I", "tools/kameras_aus_buendel.py", ZR, "--ausrichtung", AU, "--fotos", FV] + (["--sparse", os.path.join(P, "sfm", "sparse", "0")] if os.path.exists(os.path.join(P, "sfm", "sparse", "0", "images.bin")) else []), log)[0]
        lauf(B, "kamera_plausibel", [PY, "-I", "tools/kamera_plausibel.py", Z, "--beiseite", "--tief=3"], log, ok=(0, 3))      # 16.11.2026: Kameras "am Mond" (Abstand/Zoom nicht trennbar) beiseitelegen, bevor ein Werkzeug sie benutzt
        kw = os.path.join(KD, "kam_wahl.json"); wahl = list(json.load(open(kw))) if os.path.exists(kw) else []
        wahl = [f for f in wahl if os.path.exists(os.path.join(Z, "messprotokoll", "K-" + os.path.splitext(f)[0] + ".json"))][:6]      # erst filtern, dann die besten 6 (vorher [:6] zuerst: waren die ersten 6 beiseitegelegt, blieb das Foto-Tor leer)      # 17.11.2026: beiseitegelegte (unplausible) Kameras standen noch in der Fotowahl der Kantenstufe -> 3 Stufen "keine Kamera" am Martinstor
        if rc_k != 0: notiz(B, "fototor", False, fehler=f"Kameras nicht geschrieben (fototor_kameras rc {rc_k}) - Foto-Tor NICHT gelaufen; K-Dateien eines frueheren Laufs sind fuer diese Ausrichtung nicht belegt"); wahl = []
        elif not wahl: notiz(B, "fototor", False, fehler=f"KEIN Foto geprueft ({kw} fehlt/leer oder alle gewaehlten Kameras beiseitegelegt) - das Foto-Tor ist damit NICHT bestanden (17.11.2026: lief mit 0 Fotos still durch)")
        for f in wahl: lauf(B, f"fototor_{os.path.splitext(f)[0]}", [PY, "-W", "ignore", "-I", "tools/foto_diff.py", ZR, os.path.splitext(f)[0], "--bild", os.path.join(FV, f)], log)
        # 17.11.2026: foto_diff-Zahlen allein trennen gut/schlecht nicht (Messreihe im Kopf von foto_diff.py) -> URTEIL nur im Paarvergleich gegen den Bezugsstand je Foto
        # (tools/foto_tor_bezug.py, Nachweis tools/test_foto_tor_bezug.py). rc 3 = belegte Verschlechterung (rot, Bezug bleibt; rc 1 = Absturz), 2 = nicht beurteilbar (kein Bezug -> wird angelegt), 0 = gleich/besser (Bezug fortgeschrieben)
        wahl_t = [f for f in (list(json.load(open(kw))) if os.path.exists(kw) else []) if os.path.exists(os.path.join(Z, "messprotokoll", "K-" + os.path.splitext(f)[0] + ".json"))][:15] if wahl else []   # Urteil = Mittel ueber Fotos: mit 6 Fotos 83 %, mit ~10 sitzenden 92 % der deutlichen Faelle (Nachweis) -> bis 15 Fotos, ~10 s je Foto
        if wahl_t:
            rc_t = lauf(B, "fototor_bezug", [PY, "-W", "ignore", "-I", "tools/foto_tor_bezug.py", ZR, "--fotos", ",".join(os.path.splitext(f)[0] for f in wahl_t), "--bilder_dir", FV, "--setzen_wenn_ok"], log, ok=(0, 2, 3))[0]
            try: g_ = json.load(open(os.path.join(Z, "audit", "fototor_vergleich.json")))["gesamt"]
            except Exception: g_ = {}
            if rc_t == 3: notiz(B, "fototor_urteil", False, urteil="schlechter", gesamt=g_, fehler=f"BELEGTE VERSCHLECHTERUNG gegen den Bezugsstand ({g_.get('schlechter')} von {g_.get('beurteilbar')} beurteilbaren Fotos schlechter, ueber der Rauschgrenze) - audit/fototor_<foto>.jpg ansehen; Bezug NICHT fortgeschrieben")
            elif rc_t == 2: notiz(B, "fototor_urteil", True, urteil="nicht beurteilbar", gesamt=g_, hinweis="KEIN Urteil (kein Bezugsstand oder < 2 beurteilbare Fotos) - Bezug angelegt; erst der naechste Lauf vergleicht. Nicht als 'besser' lesen")
            elif rc_t == 0: notiz(B, "fototor_urteil", True, urteil=g_.get("urteil"), gesamt=g_, hinweis="nicht schlechter als der Bezugsstand; Bezug fortgeschrieben")
    # --- 17.11.2026 Stufe 'dachfoto' (gehoert zu fototor: braucht die Messkameras): Dachhoehe und Dachumriss aus der Himmelskante der Fotos (tools/dach_aus_fotos.py) ---
    # rc 0 belegt, 3 belegt mit gemeldetem Widerspruch zu DOM1/LoD2 oder zwischen Kameragruppen, 2 nicht belegt (DOM1-Dach bleibt). Belegt -> Block 'foto' in dach.json, neu bauen.
    if dran("fototor") and os.path.exists(AU) and os.path.exists(os.path.join(Z, "dach.json")):
        if lauf(B, "dachfoto", [PY, "-W", "ignore", "-I", "tools/dach_aus_fotos.py", ZR, "--schreiben"], log, ok=(0, 2, 3))[0] in (0, 3): lauf(B, "bauen_mit_fotodach", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1))
    # --- Ende Stufe 'dachfoto' ---
    gp_ = os.path.join(ROOT, "modelle", f"{a.ziel}_gen.py")           # 16.11.2026: schwab_auto hatte einen Generator aus einer alten Vorlage - Reliefs und Fenster wurden gerechnet, aber nie gebaut (Modell blieb bei 244 Dreiecken)
    if (dran("bauen") or dran("fassaden") or dran("fenster")) and os.path.exists(gp_) and not all(w_ in open(gp_).read() for w_ in ("fassaden_kette", "fenster_aus_json")): lauf(B, "generator_erneuern", ["python3", "tools/objekt_anlegen.py", a.ziel, "--generator-erneuern"], log, ok=(0, 3))      # unberuehrter alter Rumpf -> aktuelle Vorlage (alter bleibt als .alt_<zeit>)
    if (dran("fassaden") or dran("fenster")) and os.path.exists(gp_) and not all(w_ in open(gp_).read() for w_ in ("fassaden_kette", "fenster_aus_json")):
        notiz(B, "generator_vorlage", False, fehler=f"{os.path.basename(gp_)} ruft fassaden_kette.anbauen / bauteile.fenster_aus_json nicht auf - Ergebnisse der Stufen fassaden/fenster kommen NICHT ins Modell (Zeilen aus der Vorlage in tools/objekt_anlegen.py uebernehmen)")
    def dach_leer():                                                     # 17.11.2026: dach_vermessen schreibt bei Misserfolg (keine DOM1-Kachel) eine dach.json mit teile: [] - 'Datei existiert' reichte, fassaden_kette stuerzte daran ab
        try: return not json.load(open(os.path.join(Z, "dach.json"))).get("teile")
        except Exception: return True
    if dran("fassaden") and os.path.exists(AU) and dach_leer(): lauf(B, "dach_nachholen", [PY, "-I", "tools/dach_vermessen.py", ZR] + (["--wolke", W] if os.path.exists(W) else []), log)      # 17.11.2026: Einstieg ab 'fassaden' ohne dach.json -> fassaden_kette stuerzte ab (Martinstor)
    if dran("fassaden") and os.path.exists(AU):                         # 15.11.2026: Fassaden-Kette automatisch (Netz -> Relief je LoD2-Wand -> Putz per Fotofarbe -> Steine in Loechern), danach neu bauen
        dd = os.path.join(P, "dicht"); nz = os.path.join(P, "openmvs", "mesh_modell_ausschnitt.npz")
        t_n = time.time()
        if os.path.exists(os.path.join(dd, "fused.ply")) and lauf(B, "fassaden_netz", [PY, "-I", "tools/netz_aus_dicht.py", ZR, dd], log)[0] == 0 and frisch(nz, t_n):      # frisch: ein Netzausschnitt eines frueheren Laufs gilt nicht
            if lauf(B, "fassaden_kette", [PY, "-I", "tools/fassaden_kette.py", ZR, "--netz", nz, "--fotosteine"] + (["--fein", os.path.join(dd, "sparse"), FV] if os.path.isdir(os.path.join(dd, "sparse")) else []), log)[0] == 0: lauf(B, "bauen_mit_fassaden", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1))   # --fein: lokale Feinrechnung der Tiefe je Wand (GPU, ~11 min je Wand)
        else: notiz(B, "fassaden", False, fehler=f"kein dichter Ordner ({dd}/fused.ply) oder Netzstufe ohne neues Ergebnis ({nz})")
    if dran("fassaden") and os.path.exists(os.path.join(Z, "audit", "fassaden_kette.json")) and os.environ.get("RCPARK_OHNE_MONO") != "1":      # 17.11.2026 Stufe 'mono' (nach relief_putz/steine der Fassaden-Kette): Feinrelief aus Einzelfotos,
        fkj = os.path.join(Z, "audit", "fassaden_kette.json"); FK = json.load(open(fkj)); stl_m = os.path.join(ROOT, "modelle", "stl", f"{a.ziel}_1-87.stl"); mono_w = []      # tools/relief_aus_fotos_mono.py (Depth Anything V2 Small, Apache-2.0), Feld = Wand bis 10 m
        for w_ in FK.get("waende", []):                                   # TOR: Korrelation je Foto mit dem Scan-Bandpass >= 0,2 (schwaechere Fotos verwirft das Werkzeug; keins uebrig = rc 4 = Wand ohne Mono-Relief)
            rq_ = [os.path.join(Z, "relief", w_["name"] + e_ + ".npz") for e_ in ("_misch", "_voll")]; rq_ = [q_ for q_ in rq_ if os.path.exists(q_)]
            L_, z1m = float(w_.get("laenge", 0.0)), round(min(float(w_.get("z1", 0.0)), 10.0), 2)
            if w_.get("aus") or w_.get("nur_foto") or not rq_ or not os.path.exists(stl_m) or L_ < 2.0 or z1m < 2.0: continue
            mo = os.path.join(Z, "relief", w_["name"] + "_mono.npz")
            for e_ in (".npz", ".jpg", ".json"):
                if os.path.exists(mo[:-4] + e_): os.remove(mo[:-4] + e_)      # Ergebnis eines frueheren Laufs gilt nicht (das Werkzeug ueberschreibt nie)
            rc_ = lauf(B, "mono_" + w_["name"], [PY, "-I", "tools/relief_aus_fotos_mono.py", rq_[0], ZR, mo, "--feld", "0.1", str(round(L_ - 0.1, 2)), "0", str(z1m), "--stl", stl_m, "--min_korr", "0.2", "--gpu_mb", "3500"], log, ok=(0, 3, 4))[0]
            jm = mo[:-4] + ".json"; Jm = json.load(open(jm)) if os.path.exists(jm) else {}
            kor = [f_.get("korrelation_band_scan") for f_ in Jm.get("fotos", []) if "verworfen" not in f_]
            w_["mono"] = dict(rc=rc_, feld=[0.1, round(L_ - 0.1, 2), 0.0, z1m], korrelation=kor, fugen_f1=(Jm.get("fugenabgleich") or {}).get("feld"), datei=os.path.basename(mo) if rc_ == 0 and os.path.exists(mo) else None)
            if w_["mono"]["datei"]: mono_w.append(w_["name"])
        json.dump(FK, open(fkj, "w"), indent=1, ensure_ascii=False)
        notiz(B, "mono", True, waende=mono_w, hinweis="ANSEHEN: relief/<wand>_mono.jpg (Foto | Scan | neu); fassaden_kette.anbauen setzt <wand>_mono.npz noch NICHT ein (Generator von Hand: relief_koerper(..., trend=True, rand_auslauf=False), grobes Relief mit dem Feld als tief_felder)")
    if dran("fenster") and os.path.exists(AU):                          # 15.11.2026: Fenster automatisch (Mehrfoto-Ortho -> OWLv2 -> Scheiben gruppieren); Probe Nordgiebel Schwabentor-Nachbarhaus: 6 von 6 sichtbaren Fenstern, 1-4 cm
        fo = os.path.join(D, "fassade"); stl_ = os.path.join(ROOT, "modelle", "stl", f"{a.ziel}_1-87.stl"); fa = os.path.join(Z, "audit", "fenster_auto.json")
        if lauf(B, "fenster_ortho", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--stl", stl_, "--aus", fo, "--einzeln", "--min-flaeche", "6"], log)[0] == 0:
            try: nfo = sum(len(f_.get("fotos") or {}) for f_ in json.load(open(os.path.join(fo, "fassaden.json")))["fassaden"])
            except Exception: nfo = 0
            if nfo == 0: notiz(B, "fenster_ortho_inhalt", False, fehler="KEIN Foto auf irgendeiner Fassade - Kameras/fotos_dir pruefen (rc 0 allein beweist nichts; 16.11.2026 lief die Kette so leer durch)")
            env_alt = dict(os.environ); os.environ.update(HF_HOME="/media/oem/scan/hf_cache", HF_HUB_OFFLINE="1")
            if lauf(B, "fenster_parsing", [PY, "-W", "ignore", "-I", "tools/fassade_parsing.py", "--ortho", fo, "--gpu"], log)[0] == 0 and (lauf(B, "fenster_ortho_fein", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--stl", stl_, "--aus", fo + "_fein", "--einzeln", "--min-flaeche", "6", "--zelle", "0.01", "--max-mpp", "0.02", "--beste", "3"], log, ok=(0, 1))[0] in (0, 1)) and (lauf(B, "fenster_fein", [PY, "-I", "tools/fassade_fein.py", fo + "_fein"], log, ok=(0, 1))[0] in (0, 1)) and lauf(B, "fenster_bauen_liste", [PY, "-I", "tools/fenster_aus_parsing.py", fo, "--aus", fa, "--fein", fo + "_fein"], log)[0] == 0:   # feines, ausgerichtetes 1-cm-Bild fuer Sprossen/Muster (Nutzer 15.11.: "immer alle Details mitnehmen"); wo kein Foto <= 2 cm/px hat, bleibt das grobe
                # 17.11.2026 (Schwabentor stand als geschlossener Klotz da): Bogenoeffnungen/Tordurchfahrten. Das Parsing fand den Torbogen (8 von 8 Stimmen), aber nur die Klasse 'fenster' ging in den Generator.
                # oeffnungen_bogen.py: Bogenkasten = Suchfenster -> Ebenen-Sweep (Durchblick belegt?) -> Formfamilie -> audit/oeffnungen_auto.json -> bauteile.oeffnungen_aus_json (Vorlage objekt_anlegen.py). Scheitert es, bleibt die Wand zu (rc != 0 nur im Bericht).
                if lauf(B, "oeffnungen_bogen", [PY, "-W", "ignore", "-I", "tools/oeffnungen_bogen.py", fo, "--objekt", ZR, "--aus", os.path.join(Z, "audit", "oeffnungen_auto.json")], log, ok=(0,))[0] == 0 and os.path.exists(gp_) and "oeffnungen_aus_json" not in open(gp_).read():
                    lauf(B, "generator_erneuern_oeffnungen", ["python3", "tools/objekt_anlegen.py", a.ziel, "--generator-erneuern"], log, ok=(0, 3))
                    if "oeffnungen_aus_json" not in open(gp_).read(): notiz(B, "generator_vorlage_oeffnungen", False, fehler=f"{os.path.basename(gp_)} ruft bauteile.oeffnungen_aus_json nicht auf - erkannte Tore/Bogenoeffnungen kommen NICHT ins Modell (Zeilen aus der Vorlage in tools/objekt_anlegen.py uebernehmen)")
                lauf(B, "bauen_mit_fenstern", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1))
            os.environ.clear(); os.environ.update(env_alt)
    if dran("fenster") and os.path.exists(os.path.join(Z, "messprotokoll")):
        if not json.load(open(ZJ)).get("neben_fotos"): lauf(B, "neben_fotos_waehlen", [PY, "-W", "ignore", "-I", "tools/neben_fotos_waehlen.py", ZR, "--eintragen"], log, ok=(0, 3))      # 16.11.2026: ohne neben_fotos liefen Umriss-Tor und 'Modell neben Foto' leer durch
        lauf(B, "umriss_tor", [PY, "-W", "ignore", "-I", "tools/umriss_tor.py", ZR, "--eintragen"], log, ok=(0, 3))  # rc 2 (nichts geprueft) = Fehler im Bericht      # 16.11.2026: Dachlinie Modell gegen Himmelskante; Befunde -> beobachtungen_offen
    # --- 18.11.2026 Stufe 'bauplan' (Ziel H0 von null, modelle/ZIEL_PIPELINE_H0.md L2; Grundsatz WANDBILD = BAUPLAN): was ein Agent am Kaufhaus von Hand in objekt.json eintrug,
    # schreibt jetzt die Kette selbst - NUR objekt.json-Eintraege + Belege/Bilder, der Generator (Vorlage tools/objekt_anlegen.py) liest sie:
    #   (c) "rueckwand" (Leibungstiefe fuer bauteile.rueckwaende): oeffnungen_wandbild.py auf den Aussenwaenden -> rueckwand_tiefe.py (Median der Fenstertiefen, sonst ANNAHME mit Beleg)
    #   (a) "innenwaende": innenwaende_finden.py (Ebenen-Sweep durch grosse Erkennerzonen; Kriterium im Kopf des Werkzeugs; Tiefe nur LAGE)
    #   (b) "innenwand_oeffnungen": je Innenwand Sicht-Modell (Zonen davor offen) -> fassade_ortho 5 cm + 1 cm -> fassade_fein --fein_ausrichten 1 -> fassade_parsing -> oeffnungen_wandbild.py
    # Von Hand eingetragene Werte (ohne "auto") bleiben unberuehrt (die Werkzeuge melden rc 3).
    if dran("bauplan") and os.path.exists(AU):
        fo = os.path.join(D, "fassade"); ffn = fo + "_fein"; bp_ = os.path.join(D, "bauplan"); os.makedirs(bp_, exist_ok=True); stl_ = os.path.join(ROOT, "modelle", "stl", f"{a.ziel}_1-87.stl"); erg_ = {}
        if os.path.exists(gp_) and not all(w_ in open(gp_).read() for w_ in ("rueckwaende", "laube_aus_wandbild")): lauf(B, "generator_erneuern_bauplan", ["python3", "tools/objekt_anlegen.py", a.ziel, "--generator-erneuern"], log, ok=(0, 3))
        if not all(os.path.exists(os.path.join(fo, f_)) for f_ in ("fassaden.json", "elemente.json")): notiz(B, "bauplan", False, fehler=f"{fo}/fassaden.json oder elemente.json fehlt (Stufe fenster: fassade_ortho + fassade_parsing)")
        else:
            oa_ = os.path.join(Z, "audit", "oeffnungen_aussen.json")
            # 18.11.2026: Innenwandsuche ZUERST - ihre Tiefenkarten (bauplan/tiefe/tiefe_fNN.npz, Sweep bis Gebaeudetiefe) entscheiden, ob ein Bogen offen ist (Laube; Kaufhaus: 3 von 4 Boegen fielen weg)
            erg_["innenwaende_rc"] = lauf(B, "bauplan_innenwaende", [PY, "-W", "ignore", "-I", "tools/innenwaende_finden.py", ZR, fo, "--arbeit", os.path.join(bp_, "tiefe"), "--schreiben"], log, ok=(0, 3))[0]
            if os.path.isdir(ffn) and lauf(B, "bauplan_oeffnungen_aussen", [PY, "-W", "ignore", "-I", "tools/oeffnungen_wandbild.py", ZR, ffn, "--grob", fo, "--aus", oa_, "--tiefe_ordner", os.path.join(bp_, "tiefe")], log)[0] == 0: pass
            erg_["rueckwand_rc"] = lauf(B, "bauplan_rueckwand", [PY, "-I", "tools/rueckwand_tiefe.py", ZR, oa_, "--schreiben"], log, ok=(0, 3))[0]
            oz_ = json.load(open(ZJ)); IW_ = [x_["name"] for x_ in oz_.get("innenwaende", []) if x_.get("auto")]; IO_ = oz_.get("innenwand_oeffnungen")
            if IW_ and not (IO_ and not IO_.get("auto")):
                nur_ = ",".join(IW_); si_ = os.path.join(bp_, "sicht.stl"); io_ = os.path.join(bp_, "innen"); iof_ = io_ + "_fein"; oi_ = os.path.join(Z, "audit", "oeffnungen_innen.json")
                env_alt = dict(os.environ); os.environ.update(HF_HOME="/media/oem/scan/hf_cache", HF_HUB_OFFLINE="1")
                ok_ = (lauf(B, "bauplan_sicht_stl", [PY, "-W", "ignore", "-I", "tools/innenwaende_finden.py", ZR, "--sicht_stl", stl_, si_], log)[0] == 0
                       and lauf(B, "bauplan_innen_ortho", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--stl", si_, "--aus", io_, "--einzeln", "--nur", nur_], log)[0] == 0
                       and lauf(B, "bauplan_innen_ortho_fein", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--stl", si_, "--aus", iof_, "--einzeln", "--nur", nur_, "--zelle", "0.01", "--max-mpp", "0.02", "--beste", "3"], log, ok=(0, 1))[0] in (0, 1)
                       and lauf(B, "bauplan_innen_fein", [PY, "-I", "tools/fassade_fein.py", iof_, "--fein_ausrichten", "1"], log, ok=(0, 1))[0] in (0, 1)
                       and lauf(B, "bauplan_innen_parsing", [PY, "-W", "ignore", "-I", "tools/fassade_parsing.py", "--ortho", io_, "--gpu", "--mind-px", "64"], log)[0] == 0
                       and lauf(B, "bauplan_innen_oeffnungen", [PY, "-W", "ignore", "-I", "tools/oeffnungen_wandbild.py", ZR, iof_, "--grob", io_, "--nur", nur_, "--aus", oi_], log)[0] == 0)
                os.environ.clear(); os.environ.update(env_alt); oz_ = json.load(open(ZJ))
                if ok_ and os.path.exists(oi_):
                    oz_["innenwand_oeffnungen"] = dict(datei=os.path.relpath(oi_, Z), ncc_min=0.2, auto="bauplan " + time.strftime("%Y-%m-%d"), quelle=f"Kettenstufe bauplan: Sicht-Modell (innenwaende_finden --sicht_stl) -> fassade_ortho {nur_} 5 cm + 1 cm einzeln -> fassade_fein --fein_ausrichten 1 -> fassade_parsing (OWLv2) -> tools/oeffnungen_wandbild.py; Bilder {io_}/elemente_*.jpg, {oi_[:-5]}.jpg")
                    erg_["innenwand_oeffnungen"] = sum(len(F_.get("oeffnungen", [])) for F_ in json.load(open(oi_)).values())
                elif IO_ and IO_.get("auto"): oz_.pop("innenwand_oeffnungen", None)
                __import__("json_sicher").schreiben(ZJ, oz_)
            elif not IW_ and IO_ and IO_.get("auto"): oz_.pop("innenwand_oeffnungen", None); __import__("json_sicher").schreiben(ZJ, oz_)
            oz_ = json.load(open(ZJ)); erg_.update(innenwaende=[(x_["name"], x_.get("versatz"), x_.get("u"), x_.get("z")) for x_ in oz_.get("innenwaende", [])], rueckwand=(oz_.get("rueckwand") or {}).get("tiefe"))
            if os.path.exists(gp_): lauf(B, "bauen_mit_bauplan", ["bash", "tools/bauen_abnehmen.sh", a.ziel], log, ok=(0, 1))
            notiz(B, "bauplan", True, **erg_, hinweis="ANSEHEN: audit/innenwaende_auto.jpg (Tiefe je Fassade), audit/oeffnungen_innen.jpg, audit/rueckwand_auto.json; Generator-Belege 'Rueckwand' / 'Innenwand'")
    # --- Ende Stufe 'bauplan' ---
    # 18.11.2026: die Kantenstufe bewertet den LoD2-Klotz VOR den Fassaden (Kaufhaus gk2 F1 0,01 - Fotokanten im Fensterband, der Klotz hat dort keine). Zweite Bewertung am
    # FERTIGEN Modell mit demselben Sweep -> kanten_bericht_fertig.json, audit/kanten3d_fertig.png (Kernmethode: misst, ob Fassaden/Bauplan die Fotokanten treffen).
    if (dran("bauplan") or dran("fassaden")) and os.path.exists(os.path.join(KD, "sweep.npz")) and os.path.exists(AU):
        lauf(B, "kanten_fertig", [PY, "-u", "-I", "tools/kantenstufe.py", ZR, "--ausrichtung", AU, "--bilder", FV, "--aus", KD, "--nur_bewerten", "--name", "_fertig"], log, ok=(0, 4))
    if dran("seiten") and os.path.exists(AU):                           # 16.11.2026 Nutzer (Schwabentor Ostseite): "Er muss doch wissen, dass dort Bilder fehlen und die sich dann holen, notfalls downloaden. Alles muss in die Pipeline."
        # 18.11.2026: dicht/sparse (ENTZERRT, PINHOLE) ans Ende - Nachregistrieren braucht das Modell der Originalbilder zur Datenbank (Kaufhaus gk2i: Absturz nach 90 min)
        fo = os.path.join(D, "fassade"); sp = next((q_ for q_ in (os.path.join(P, "sparse_ba"), os.path.join(P, "sparse", "0"), os.path.join(P, "sfm", "sparse", "0"), os.path.join(P, "sfm", "sparse_dicht"), os.path.join(P, "sfm", "sparse"), os.path.join(P, "dicht", "sparse")) if os.path.exists(os.path.join(q_, "images.bin"))), None); db = next((q_ for q_ in (os.path.join(P, "db.db"), os.path.join(P, "sfm", "db.db")) if os.path.exists(q_)), os.path.join(P, "db.db"))
        try: nfo_s = sum(len(f_.get("fotos") or {}) for f_ in json.load(open(os.path.join(fo, "fassaden.json")))["fassaden"])
        except Exception: nfo_s = -1
        if nfo_s == 0: notiz(B, "seiten", False, fehler="kein Foto auf IRGENDEINER Fassade = Einrichtungsfehler (Kameras/fotos_dir), keine Fotoluecke - Download uebersprungen (16.11.2026: 32 min und 1,8 GB umsonst)")
        elif os.path.exists(os.path.join(fo, "fassaden.json")) and sp and os.path.exists(db):
            nf = len(json.load(open(os.path.join(fo, "fassaden.json")))["fassaden"]); vb = {}
            for i_ in range(nf):                                              # 16.11.2026: Vorbauten/Nischen automatisch (Ebenen-Sweep je Fassade); rc 2 = zu wenige Fotos, rc 4 = nicht belastbar
                if lauf(B, f"vorbauten_f{i_:02d}", [PY, "-W", "ignore", "-I", "tools/fassade_tiefe.py", ZR, fo, str(i_)], log, ok=(0, 2, 4))[0] == 0:
                    vj = os.path.join(fo, f"vorbauten_f{i_:02d}.json"); vb[f"f{i_:02d}"] = len(json.load(open(vj))["kandidaten"]) if os.path.exists(vj) else 0
            notiz(B, "vorbauten", True, kandidaten=vb, hinweis="Vorschlaege mit eigener Messebene (vorbauten_fNN.json, Bild tiefe_fNN.jpg ansehen); noch kein automatischer Bau")
            t_sl = time.time(); rc, out = lauf(B, "seiten_luecken", [PY, "-I", "tools/seiten_luecken.py", ZR, fo, "--sparse", sp, "--ref-db", db, "--download", "--holen"], log, ok=(0, 3))   # rc 3 = Wand ohne Foto: freie Quellen laden (Commons, Hochblicke, Openverse), Kandidaten nachregistrieren
            sl = os.path.join(Z, "audit", "seiten_luecken.json"); ung = json.load(open(sl)).get("ungesehen", []) if frisch(sl, t_sl) else ["?"]      # 17.11.2026: nach einem Absturz von seiten_luecken galt der Bericht eines frueheren Laufs (oder 'keine Luecke', wenn es keinen gab)
            if ung == ["?"]: notiz(B, "seiten_bericht", False, fehler=f"{sl} wurde nicht neu geschrieben (seiten_luecken rc {rc}) - Luecken UNBEKANNT")
            wj = os.path.join(Z, "fotowuensche.json"); lauf(B, "foto_auftrag", [PY, "-W", "ignore", "-I", "tools/foto_auftrag.py", ZR, fo, os.path.join(D, f"fotoauftrag_{a.ziel}.html")] + (["--wunsch", wj] if os.path.exists(wj) else []), log)   # 16.11.2026: dem Nutzer zeigen, welche Fotos fehlen (Lageplan, Standorte, markierte Ziele)
            notiz(B, "seiten", not ung, ungesehen=ung, hinweis="" if not ung else "nach dem Nachregistrieren fassade_ortho/fassade_fein neu; bleibt die Wand leer: Kontaktbogen audit/seiten_luecken_kandidaten.jpg ansehen, Kamera aus Modellpunkten + tools/fassade_ein_foto.py (PIPELINE_FASSADEN.md 'Ungesehene Seite')")
        else: notiz(B, "seiten", False, fehler="kein fassaden.json (Stufe fenster) oder kein SfM-Netz/Datenbank")
    if dran("html"):
        args = [PY, "-I", "tools/modell_3d_html.py", ZR, os.path.join(D, f"{a.ziel}_3d.html")]
        if os.path.exists(W): args += ["--wolke", W] + (["--farben", W.replace("punkte_modell_", "punkte_farben_")] if os.path.exists(W.replace("punkte_modell_", "punkte_farben_")) else [])
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
    if dran("druck"):                                                    # 18.11.2026 (Ziel H0-druckbar von null, modelle/ZIEL_PIPELINE_H0.md L1): Bausatz fuer MK4S (Koerper) + Bambu (Platten)
        mk_ = sorted(os.path.relpath(q_, Z) for q_ in glob.glob(os.path.join(Z, "relief", "*_putz.npz")))
        if not mk_: notiz(B, "druck", False, fehler="keine Putzmasken relief/*_putz.npz (Stufe fassaden) - Bausatz braucht sie fuer die Steinplatten; ohne Masken kein Bausatz")
        else:
            rc_, out_ = lauf(B, "druck", ["bash", "tools/bausatz.sh", a.ziel, ",".join(mk_)], log, ok=(0, 3))
            notiz(B, "druck_ergebnis", rc_ == 0, masken=len(mk_), hinweis="rc 3 = Luftinsel/Abbruch (Meldungen im Log); Teile: modelle/stl/<ziel>_teile, Platten: modelle/stl/<ziel>_farbteile")
    return abschluss()


if __name__ == "__main__":
    sys.exit(main())
