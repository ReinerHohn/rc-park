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
  sfm        tools/pipeline_objekt.py fein (SfM mit Paarliste, Bildwahl, Tiefenkarten GPU, LoD2-Abgleich); VORSTUFE 'Lage frueh' (22.11.2026, tools/lage_frueh.py):
             erst pipeline_objekt --bis kameras, dann Ausrichtung + GPS-Tor + Lageproben auf dem duennen Netz, eindeutig durchgefallen -> Abbruch VOR der dichten Wolke
             (RCPARK_LAGE_FRUEH=1 Standard, =hinweis nur melden, =0 aus)
  tore       kamera_abdeckung, lage_gps_pruefen, wolke_grundriss_pruefen; KORREKTUR: faellt GPS (rc 3) oder Grundriss A (rc 3) durch,
             sfm_lod2_ausrichten --loesung 1..max probieren, die erste Loesung, die ALLE Tore besteht, gilt; sonst Abbruch mit Bericht
  dach       tools/dach_vermessen.py (DOM1, mit Wolke)
  bauen      tools/bauen_abnehmen.sh <ziel> (Generator aus Vorlage = LoD2 + Dach)
  kanten     KERNMETHODE (15.11.): tools/kantenstufe.py - SfM-Kameras -> Stabilkarten -> Kanten-Tiefen-Sweep um den MODELLFREIEN Messkoerper (22.11.: 2 m vor bis 0,5 m hinter LoD2-flach + Wandversatz, Wolke nur Lage-Veto; vorher Vormodell = Kreis) -> 3D-Kanten-F1 + Liste fehlender Kanten
  fototor    tools/kameras_aus_buendel.py (K-<foto>.json) -> tools/foto_diff.py auf den Fotos mit bester Modellsicht (Foto-Tor)
  (in fototor: tools/kamera_plausibel.py --beiseite; nach fenster: tools/umriss_tor.py --eintragen; fassaden/fenster/seiten siehe modelle/PIPELINE_FASSADEN.md)
  seiten     tools/seiten_luecken.py --holen (Fotos fuer ungesehene Waende nachregistrieren, Tor tools/kameras_nachtragen_tor.py); sehen BELEGTE neue Kameras eine ungesehene Wand
             und steigt deren Abdeckung messbar: EIN Teillauf ab fenster bis seiten im selben Lauf (tools/seiten_wiederholung.py, 23.11.2026)
  draehte    tools/wolke_draehte.py: Draehte/Oberleitung + Fahnen (Draht als schmales Blatt) + Freiraum (SfM-Strahlen durch Gewirr vor der Wand) aus einer KOPIE der Wolke -> <daten>/wolke_anzeige/ (nur Anzeige;
             Original + Wolke-Tore unveraendert), Bericht audit/wolke_draehte.json + audit/wolke_draehte.jpg (24.11.2026, Nutzerbefund 1122 Nordseite)
  html       tools/modell_3d_html.py -> <daten>/<ziel>_3d.html (Wolke = gefilterte Kopie, wenn neuer als das Original)
  vergleich  optional --referenz-wolke: Abstand neue Wolke -> bewiesene Wolke (Median, Anteil < 0,5 m) = Konvergenzbeweis
  (am Ende) tools/konvergenz.py -> audit/konvergenz.jsonl + konvergenz.png: F1 grob/fein je Seite auf FESTEM Fotosatz, Status steigt/PLATEAU/kein Beleg
  (immer am Ende) tools/befundliste.py -> audit/befunde.json + audit/befunde/bNN.jpg: sichtbare Fehler je Ort/Art/Beleg/Werkzeug fuer die Agenten-Schleife
Umgebung: venv-seg (s.o.) oder `tools/py tools/gesamtkette.py ...`; Teilschritte mit pycolmap ruft die Kette selbst mit venv-colmap.
Exit: 0 = Kette durchgelaufen, 2 = Datenplatte fehlt / modelle/<ziel>/objekt.json fehlt, 3 = keine Lage besteht alle Tore oder Platz zu knapp,
      4 = Stufe gescheitert (Fotos sammeln, SfM, Tor/Ausrichtung abgestuerzt) - Grund steht im Bericht (abbruch).
"""
import sys, os, re, json, glob, shutil, subprocess, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = "/media/oem/scan/venv-seg/bin/python"; PYC = "/media/oem/scan/venv-colmap/bin/python"
STUFEN = ["anlegen", "commons", "video", "vorpruefen", "sammeln", "sfm", "tore", "dach", "bauen", "kanten", "fototor", "fassaden", "fenster", "bauplan", "seiten", "draehte", "html", "vergleich", "druck"]
UEBERNEHMEN = ["name", "ort", "lod2", "rahmen", "rahmen_wand", "koordinate_utm", "hoehe_m", "fotos_dir", "seiten_konvention", "bildquellen"]


class _Erg:                                                                  # wie subprocess.CompletedProcess (returncode, stdout)
    def __init__(self, rc, out): self.returncode, self.stdout = rc, out


_ABSCHLUSS = [None]                                                          # Abschlussfunktion des laufenden Kettenlaufs (fuer Abbrueche aus lauf())
DATEN = "/media/oem/scan"                                                    # Datenplatte: alles Grosse liegt hier (CLAUDE.md); Test: RCPARK_DATEN
TEILLAUF = os.environ.get("RCPARK_TEILLAUF") == "1"                          # 23.11.2026: Wiederholung nach dem Nachholen (seiten_wiederholen) - kein Nachholen, kein zweites Wiederholen, keine Schlussberichte


KB_frisch = lambda p_, seit_: __import__("kette_beleg").frisch(p_, seit_)


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


def fein_paar(P, FV):
    """--fein-Argumente (Buendel + passender Bildordner) fuer fassaden_kette/tiefe_lokal. 21.11.2026 (Kettenlauf 1121o/p: 'fein 0 %', 1172 s umsonst):
    frueher dicht/sparse (ENTZERRT, PINHOLE 1200x1600) + Originalfotos (verzerrt, 3000x4000) -> Geometriefilter verwarf alles.
    Jetzt: das VERZERRTE Quellbuendel der dichten Wolke (sfm/sparse_dicht, sonst sfm/sparse/0 - dicht/sparse ist dessen Entzerrung, gleiche Posen,
    also derselbe Rahmen wie dicht/fused.ply und SFM-AUSRICHTUNG) + Originalfotos in voller Aufloesung; sonst dicht/sparse + dicht/images (nur 1600 px).
    tiefe_lokal.paar_pruefen bricht bei einem unpassenden Paar mit rc 2 ab."""
    for q in (os.path.join(P, "sfm", "sparse_dicht"), os.path.join(P, "sfm", "sparse", "0")):
        if os.path.exists(os.path.join(q, "images.bin")) and os.path.isdir(FV): return ["--fein", q, FV]
    dd = os.path.join(P, "dicht")
    if os.path.exists(os.path.join(dd, "sparse", "images.bin")) and os.path.isdir(os.path.join(dd, "images")): return ["--fein", os.path.join(dd, "sparse"), os.path.join(dd, "images")]
    return []
from speicher_muster import SPEICHER_MUSTER      # 23.11.2026: gemeinsames Muster mit der Fehlschlag-Marke von seiten_luecken (Speichermangel sperrt dort nicht mehr)


def speichermangel(rc, ausgabe, kernel_oom=False):
    """21.11.2026 (Nutzer: "immer wenn du wegen Speichermangel scheiterst, dann musst du im Lauf wiederholen"): Stufe scheiterte am Speicher (RAM oder GPU)?
    rc < 0 (vom System beendet: 9 = OOM-Killer, 6 = Abbruch nach fehlgeschlagener Anforderung), Speicher-Meldung in der Ausgabe (auch von Teilwerkzeugen) oder Kernel-OOM waehrend der Stufe."""
    if rc in (0, None): return False
    return rc in (-9, -6, 137, 134) or kernel_oom or bool(SPEICHER_MUSTER.search(ausgabe or ""))


def _kernel_oom_seit(t0):
    try:
        o = subprocess.run(["journalctl", "-k", "--since", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)), "--no-pager", "-q"], capture_output=True, text=True, timeout=20).stdout
        return bool(re.search(r"out of memory|oom-kill|page allocation failure", o, re.I))
    except Exception: return False


def _speicher_abwarten(min_mb=3000, max_s=600):
    t_ = time.time()
    while time.time() - t_ < max_s:
        try: frei = int([z.split()[1] for z in open("/proc/meminfo") if z.startswith("MemAvailable")][0]) // 1024
        except Exception: return
        if frei >= min_mb: return
        time.sleep(15)


def lauf(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
    """Stufe mit Wiederholung bei Speichermangel (RCPARK_SPEICHER_WIEDERHOL, Standard 2): erst warten, bis >= 3 GB RAM frei sind (hoechstens 10 min), dann dieselbe Stufe neu."""
    n_ = int(os.environ.get("RCPARK_SPEICHER_WIEDERHOL", "2"))
    for v_ in range(n_ + 1):
        t0_ = time.time(); rc_, out_ = _lauf_einmal(B, name, cmd, log, ok, timeout, platz)
        if rc_ in ok or v_ >= n_ or not speichermangel(rc_, out_, _kernel_oom_seit(t0_)): return rc_, out_
        if B.get("schritte"): B["schritte"][-1]["speicher_wiederholung"] = v_ + 1
        print(f"    SPEICHERMANGEL in {name} (rc {rc_}) - warte auf freien Speicher und wiederhole ({v_ + 1}/{n_})", flush=True)
        _speicher_abwarten()
    return rc_, out_


def platz_tor_rc():
    """rc von tools/platz_pruefen.py (Platztor vor jeder Stufe). 24.11.2026: Tests der Kette (test_kette_stabil, Heredoc 'Kette lauf()/Kameraregeln', test_speicher_wiederholung)
    scheiterten mit 'PLATZ ZU KNAPP', nur weil die ECHTE Root-Platte voll war (und platz_pruefen startete dabei sogar das Aufraeumen). Tests setzen RCPARK_PLATZ_TOR=test_ersetzt
    -> rc 0 ohne Plattenblick. Nur der Test des Platztors selbst (tools/test_platz_tor_ersetzt.py) laesst es weg. Nie in Kettenlaeufen setzen."""
    if os.environ.get("RCPARK_PLATZ_TOR") == "test_ersetzt": return 0
    return subprocess.run(["python3", os.path.join(ROOT, "tools", "platz_pruefen.py")], capture_output=True).returncode


def _lauf_einmal(B, name, cmd, log, ok=(0,), timeout=None, platz=()):
    """Eine Stufe starten. 16.11.2026 (Stabilisierung): Ausgabe laeuft ZEILENWEISE ins Log (vorher erst am Stufenende - eine 30-Minuten-Stufe war blind, ein Haenger nicht zu erkennen);
    Zeitlimit je Stufe (Standard RCPARK_STUFE_MAX_S = 3 h, die Prozessgruppe wird beendet) - ein Haenger auf einem Kern hielt am 16.11. die Kette stundenlang an."""
    import threading, signal
    if platz_tor_rc() != 0:      # Platztor VOR jeder Stufe (16.11.2026: Systemplatte lief mitten im Lauf unter 5 GB, die Stufe danach scheiterte halb)
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


_BAU_OFFEN = [None]


def bauen(B, name, ziel, log, zwischen=True):
    """Bau einer Kettenstufe. 21.11.2026 (Tempo, Kettenlauf 1121o: bauen_mit_fassaden/fenstern/bauplan/wolkenkoerpern je ~125 s, davon der groessere Teil Abnahme):
    Jeder dieser Bauten wird gebraucht - die naechste Stufe liest das STL (mono/fenster_ortho --stl, umriss_tor, koerper_schleife, ebenen_abweichung, kantenstufe) -,
    die ABNAHME (Pruefstand, Hoehen-Tor, Modell neben Foto, Umriss-Tor, Sichtblatt) aber nur fuer den letzten. zwischen=True -> RCPARK_NUR_BAUEN=1 (nur Generator,
    gleiches STL), die volle Abnahme holt abnahme_nachholen() auf dem ENDSTAND nach (kein Tor faellt weg). RCPARK_ZWISCHENABNAHME=1 = alter Ablauf (Abnahme nach jedem Bau)."""
    nur = zwischen and os.environ.get("RCPARK_ZWISCHENABNAHME") != "1"; alt = os.environ.get("RCPARK_NUR_BAUEN")
    if nur: os.environ["RCPARK_NUR_BAUEN"] = "1"
    try: r = lauf(B, name, ["bash", "tools/bauen_abnehmen.sh", ziel], log, ok=(0, 1))
    finally:
        if alt is None: os.environ.pop("RCPARK_NUR_BAUEN", None)
        else: os.environ["RCPARK_NUR_BAUEN"] = alt
    _BAU_OFFEN[0] = name if nur else None
    return r


def abnahme_nachholen(B, ziel, log):
    """Volle Abnahme (bauen_abnehmen.sh --nur-pruefen) auf dem aktuellen STL, wenn der letzte Bau ein Zwischenbau ohne Abnahme war (bauen)."""
    if not _BAU_OFFEN[0]: return None
    n = _BAU_OFFEN[0]; _BAU_OFFEN[0] = None
    return lauf(B, "abnahme_nach_" + n, ["bash", "tools/bauen_abnehmen.sh", ziel, "--nur-pruefen"], log, ok=(0, 1))


def notiz(B, name, ok, **k):
    B["schritte"].append(dict(stufe=name, ok=ok, **k)); __import__("json_sicher").schreiben(B["_pfad"], B); print(f"    {name}: {k}", flush=True)


def beleg(B, name, pfade, seit, inhalt=None, folge="", altstand_beiseite=False):
    """23.11.2026 AUDIT STILLE ERFOLGE (tools/kette_beleg.py, modelle/AUDIT_STILLE_ERFOLGE_2026-11-23.md): die erwarteten Ausgaben einer Stufe muessen in DIESEM Lauf
    (seit Stufenstart `seit`) geschrieben sein und ihren sachlichen Mindestinhalt haben - sonst Zeile '<name>_beleg' NICHT in Ordnung mit Grund und Folge.
    seit=None = Erzeugerstufe lief in diesem Lauf nicht (Einstieg --ab ...): nur Existenz. altstand_beiseite: Altdateien -> .veraltet_<zeit> (nicht geloescht), damit kein
    Verbraucher sie als frisch liest. Rueckgabe True = belegt."""
    import kette_beleg as KB
    f_ = KB.pruefen(pfade, seit, inhalt)
    if not f_: return True
    weg_ = KB.beiseite(pfade, seit) if altstand_beiseite else []
    notiz(B, f"{name}_beleg", False, fehler="; ".join(f_)[:400] + (f" - {folge}" if folge else ""), beiseite=[os.path.basename(w_) for w_ in weg_] or None)
    return False


def sweep_altstand(B, name, fo, i_, seit):
    """23.11.2026 AUDIT STILLE ERFOLGE (Lauf 1122t, bauplan_sweep_f01 rc 2 'nur 2 Fotos'): tools/fassade_tiefe.py endet bei zu wenigen Fotos VOR dem Schreiben - vorbauten_bauplan
    las dann vorbauten_f01.json + tiefe_f01.npz des Laufs von 12:25 (Fassadennummern koennen zwischen Laeufen wechseln). Was diese Stufe nicht neu schrieb, kommt beiseite
    (.veraltet_<zeit>, nicht geloescht); vorbauten_bauplan meldet dann ehrlich 'kein Sweep'. Die Stufe bleibt in Ordnung (rc 2/4 ist ein Urteil), der Schutz steht im Bericht."""
    import kette_beleg as KB
    weg_ = KB.beiseite([os.path.join(fo, f"vorbauten_f{i_:02d}.json"), os.path.join(fo, f"tiefe_f{i_:02d}.npz"), os.path.join(fo, f"tiefe_f{i_:02d}.jpg")], seit)
    if weg_: notiz(B, f"{name}_altstand", True, beiseite=[os.path.basename(w_) for w_ in weg_], hinweis="Sweep schrieb in diesem Lauf nichts - Altstand eines frueheren Laufs beiseite, damit vorbauten_bauplan/seiten ihn nicht als frisch lesen")
    return weg_


def verbund_hinweise(B, sp, P, FV, log):
    """22.11.2026 HINWEIS-STUFEN nach der SfM (Recherche duenne Bruecken, Methoden 6 + 2): (a) Schwachstellen-Radar tools/verbund_schwachstellen.py -> sfm/radar.json
    (Format verbund_schwachstellen/1: Gelenkbilder, duenne Schnitte; Ausloeser fuer Nachmatchen/Kopplung), (b) Lotfeld tools/teil_verformung.py -> sfm/teil_verformung.json
    (Biegung/Knick ohne Zuordnungen). Nur Meldung, kein Abbruch; RCPARK_VERBUND_HINWEIS=0 schaltet beides ab, RCPARK_LOTFELD=0 nur (b)."""
    if os.environ.get("RCPARK_VERBUND_HINWEIS", "1") == "0": return
    for name, cmd, aus in (("radar", [PYC, "-I", "tools/verbund_schwachstellen.py", "--modell", sp], os.path.join(P, "sfm", "radar.json")),
                           ("lotfeld", [PYC, "-I", "tools/teil_verformung.py", sp, FV, "--max-n", "300", "--faeden", "4"], os.path.join(P, "sfm", "teil_verformung.json"))):
        if name == "lotfeld" and os.environ.get("RCPARK_LOTFELD", "1") == "0": continue
        t_h = time.time(); rc_ = lauf(B, f"hinweis_{name}", cmd + ["--aus", aus], log, ok=(0, 2, 3, 4))[0]
        if not beleg(B, f"hinweis_{name}", [aus], t_h, folge="Hinweis eines frueheren Laufs wird nicht gemeldet"): continue
        try: notiz(B, f"hinweis_{name}_urteil", rc_ in (0, 4), hinweis=json.load(open(aus)).get("zeile", "")[:400], json=aus)
        except Exception as e_: notiz(B, f"hinweis_{name}_urteil", False, fehler=f"{aus} nicht lesbar: {e_}")


def foto_auftrag_skizze(B, wann, ZR, Z, P, W, AU, FV, log):
    """22.11.2026 FOTOAUFTRAG FRUEH UND ALS BILD (tools/foto_auftrag_skizze.py): die Kette wusste nach der SfM, welche Seite fehlt (seiten_modelle.json 'fotoluecken'),
    der Nutzer erfuhr es erst auf Nachfrage und nur als Text. Jetzt: Skizze audit/foto_auftrag.png (Grundriss, Wandbelegung, nummerierte Standpunkte mit Blick und GPS)
    nach der SfM ('frueh') und am Laufende ('ende'); Bildpfad im Bericht -> dem Nutzer sofort schicken. Nur CPU, Sekunden. Abschalten: RCPARK_FOTOAUFTRAG_SKIZZE=0."""
    if os.environ.get("RCPARK_FOTOAUFTRAG_SKIZZE", "1") == "0" or not (os.path.exists(W) or os.path.exists(AU)): return
    smj = os.path.join(P, "sfm", "seiten_modelle.json"); aus = os.path.join(Z, "audit"); os.makedirs(aus, exist_ok=True)
    try:
        t_f = time.time()
        lauf(B, f"foto_auftrag_skizze_{wann}", [PY, "-W", "ignore", "-I", "tools/foto_auftrag_skizze.py", ZR, "--wolke", W, "--ausrichtung", AU, "--fotos", FV, "--aus", aus]
             + (["--seiten-modelle", smj] if os.path.isfile(smj) else []), log, ok=(0, 2))
        if not beleg(B, f"foto_auftrag_{wann}", [os.path.join(aus, "foto_auftrag.json")], t_f, folge="Fotoauftrag eines frueheren Laufs wird dem Nutzer NICHT als aktuell gemeldet"): return
        e = json.load(open(os.path.join(aus, "foto_auftrag.json")))
        notiz(B, f"foto_auftrag_{wann}", True, bild=e.get("bild"), text=e.get("text"), luecken=[f"{l_.get('seite')}: {l_.get('satz', '')[:160]}" for l_ in e.get("luecken") or []],
              standpunkte=len(e.get("standpunkte") or []), fotos=sum(s_.get("anzahl", 0) for s_ in e.get("standpunkte") or []),
              hinweis="SOFORT DEM NUTZER SCHICKEN (Bild + Standpunktliste aus dem Text); Foto vor Ort pruefen: tools/foto_auftrag_skizze.py --pruefen <json> <foto>" if e.get("luecken") else "keine Luecke")
    except Exception as e_: print(f"Fotoauftrag-Skizze ({wann}) nicht erzeugt: {type(e_).__name__} {e_}", flush=True)


def seiten_wiederholen(B, a, ZR, Z, D, fo, sl, t_sl, log, bp, py_kette=None):
    """23.11.2026 KETTENLUECKE (Lauf 1122q): Stufe seiten holte Fotos fuer ungesehene Waende nach (327 Kameras), aber erst NACH Wandbild/Bauplan/Bau - der Lauf baute ohne sie.
    Jetzt (tools/seiten_wiederholung.py): (1) ungesehene Waende mit >= 1 BELEGTEN neuen Kamera (audit/kameras_nachtragen_tor.json dieses Laufs), (2) Wandbild nur dieser
    Waende neu in <daten>/fassade_nachgeholt, (3) Abdeckung vorher/nachher mit dem Mass von seiten_luecken; steigt sie >= MIN_GEWINN -> (4) EIN Teillauf dieser Kette
    ab RCPARK_SEITEN_WIEDERHOLUNG_AB (Standard: seiten_wiederholung.startstufe = frueheste Stufe nach fototor, deren Werkzeuge K-Dateien lesen; 23.11.: fassaden) bis seiten mit RCPARK_TEILLAUF=1 (kein Nachholen, keine zweite Wiederholung). Der Bericht B wird danach neu
    geladen (der Teillauf schreibt dieselbe Datei). Rueckgabe True = Teillauf lief (seine Stufen stehen im Bericht), sonst False (wie bisher)."""
    import seiten_wiederholung as SW
    kand, grund = SW.kandidaten(os.path.join(Z, "audit", "kameras_nachtragen_tor.json"), sl, seit=t_sl)
    if not kand: notiz(B, "seiten_wiederholung", True, wiederholt=False, grund=grund); return False
    ids = ",".join(w_["id"] for w_ in kand); fn = fo + "_nachgeholt"; gj = os.path.join(Z, "audit", "seiten_gewinn.json")
    if os.path.isdir(fn): shutil.rmtree(fn)                               # eigener Ausgabeordner dieser Probe (Stand eines frueheren Laufs gilt nicht)
    sj = os.path.join(Z, "audit", "ortho_sperre.json"); sp_alt = os.environ.get("RCPARK_ORTHO_SPERRE"); gesperrt = None
    if os.path.exists(sj): os.remove(sj)                                  # Sperre eines frueheren Laufs gilt nicht
    def probe(name_o, name_g):                                            # Wandbild der Kandidaten (mit Einzelbildern fuer wandbild_einigkeit) + Gewinn-Tor (Abdeckung UND Deckungsgleichheit, 23.11.2026)
        if os.path.isdir(fn): shutil.rmtree(fn)
        t0_ = time.time()
        if lauf(B, name_o, [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--messflaeche", "eben", "--aus", fn, "--nur", ids, "--min-flaeche", "6", "--einzeln"], log)[0] != 0: return None, None
        rc_ = lauf(B, name_g, [PY, "-I", "tools/seiten_wiederholung.py", "gewinn", sl, fn, "--aus", gj, "--alt", fo] + ([] if gesperrt else ["--sperre-aus", sj]), log, ok=(0, 3))[0]
        return rc_, (json.load(open(gj)) if frisch(gj, t0_) else None)
    t0 = time.time(); rc_g, g = probe("seiten_gewinn_ortho", "seiten_gewinn")
    if rc_g is None:
        notiz(B, "seiten_wiederholung", False, wiederholt=False, fehler=f"Wandbild der Waende {ids} mit den neuen Kameras gescheitert - nachgeholte Kameras bleiben fuer diesen Lauf ungenutzt"); return False
    if rc_g == 3 and g and g.get("sperre") and os.path.exists(sj):        # (c) uneiniges Wandbild: EINMAL ohne die uneinigsten Fotos (wandbild_einigkeit.ausschluss_vorschlag); gilt dann auch fuer den Teillauf
        gesperrt = json.load(open(sj)); os.environ["RCPARK_ORTHO_SPERRE"] = sj; g0 = g.get("waende")
        rc_g, g = probe("seiten_gewinn_ortho_gesperrt", "seiten_gewinn_gesperrt")
        if rc_g != 0 or not g or not g.get("wiederholen"):
            if sp_alt is None: os.environ.pop("RCPARK_ORTHO_SPERRE", None)
            else: os.environ["RCPARK_ORTHO_SPERRE"] = sp_alt
            notiz(B, "seiten_wiederholung", rc_g in (0, 3), wiederholt=False, kandidaten=kand, gewinn=g0, gewinn_gesperrt=(g or {}).get("waende"), sperre=gesperrt,
                  grund="Abdeckung ohne Deckungsgleichheit - Kameras ungenau; auch ohne die uneinigsten Fotos kein Gewinn"); return False
    if rc_g != 0 or not g or not g.get("wiederholen"):
        mel_ = "; ".join(f"{w_['id']}: {w_['meldung']}" for w_ in (g or {}).get("waende") or [] if w_.get("meldung"))
        notiz(B, "seiten_wiederholung", rc_g in (0, 3), wiederholt=False, kandidaten=kand, gewinn=(g or {}).get("waende"),
              grund=(mel_ or "Abdeckung der ungesehenen Waende steigt nicht messbar") if rc_g == 3 else f"seiten_wiederholung gewinn rc {rc_g}"); return False
    ab_ = os.environ.get("RCPARK_SEITEN_WIEDERHOLUNG_AB"); ab_grund = "RCPARK_SEITEN_WIEDERHOLUNG_AB" if ab_ else ""      # 23.11.2026 (1122t: Sued-Relief der Stufe fassaden lief ohne die nachgeholten Kameras):
    if not ab_: ab_, ab_grund = SW.startstufe(open(os.path.abspath(__file__)).read(), STUFEN)                               # frueheste kamera-lesende Wandstufe nach fototor, nur bei echtem Gewinn (Einigkeits-Tor)
    cmd = SW.teillauf_befehl(py_kette or sys.executable, a.quelle, a.ziel, ab_, trotz_lage="--trotz-lage" in sys.argv)
    tB = dict(schritte=[], _pfad=os.path.join(D, "seiten_wiederholung_schritt.json")); alt = os.environ.get("RCPARK_TEILLAUF"); os.environ["RCPARK_TEILLAUF"] = "1"
    try: rc_t, _ = _lauf_einmal(tB, "seiten_wiederholung_teillauf", cmd, log, ok=(0, 4), timeout=2 * float(os.environ.get("RCPARK_STUFE_MAX_S", "10800")))      # rc 4 = eine Stufe des Teillaufs rot (steht einzeln im Bericht)
    finally:
        if alt is None: os.environ.pop("RCPARK_TEILLAUF", None)
        else: os.environ["RCPARK_TEILLAUF"] = alt
        if gesperrt is not None:
            if sp_alt is None: os.environ.pop("RCPARK_ORTHO_SPERRE", None)
            else: os.environ["RCPARK_ORTHO_SPERRE"] = sp_alt
    try: neu_ = json.load(open(bp))
    except Exception as e_: neu_ = None; print(f"Bericht nach dem Teillauf nicht lesbar ({type(e_).__name__} {e_}) - Stufen des Teillaufs fehlen im Bericht", flush=True)
    if neu_ and len(neu_.get("schritte") or []) >= len(B["schritte"]): B.clear(); B.update(neu_); B["_pfad"] = bp
    B["schritte"].extend(tB["schritte"])
    try: nach_ = {w_["nr"]: w_.get("abdeckung") for w_ in json.load(open(sl)).get("waende", [])} if os.path.getmtime(sl) > t0 else {}
    except Exception: nach_ = {}
    notiz(B, "seiten_wiederholung", rc_t in (0, 4), wiederholt=True, ab=ab_, ab_grund=ab_grund, teillauf_rc=rc_t, waende=[dict(w_, nachher_ortho=next((x_["nachher"] for x_ in g["waende"] if x_["id"] == w_["id"]), None), nachher_bericht=nach_.get(w_["nr"])) for w_ in kand],
          sperre=gesperrt, hinweis="ANSEHEN: audit/seiten.jpg, audit/neben_*.jpg - die nachgeholten Waende sind jetzt im Wandbild/Bau dieses Laufs; Teillauf-Stufen im Bericht nach LAUF_START ab=" + ab_)
    return True


def main():
    if os.environ.pop("RCPARK_PLATZ_TOR", None) is not None: print("ACHTUNG: RCPARK_PLATZ_TOR (nur fuer Tests) war gesetzt - im Kettenlauf entfernt, das Platztor gilt", flush=True)
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
        try:                                                                   # 22.11.2026 VERLUSTBILANZ (tools/verlustbilanz.py): je Stufe rein/raus/verloren+Grund; stille Verluste = WARNUNG (Clip hBlkpdGf6LY ging ohne Zeile verloren)
            B.pop("verlustbilanz", None); import verlustbilanz as VB
            B["verlustbilanz"] = VB.bilanz(D, Z, B=B, n_start=n_start, seit=t_lauf, log=log, log_ab=log_ab); VB.drucken(B["verlustbilanz"], log)
            if B["verlustbilanz"]["warnungen"] and os.environ.get("RCPARK_VERLUST_ROT") == "1": notiz(B, "verlustbilanz", False, fehler="; ".join(B["verlustbilanz"]["warnungen"])[:400])
        except Exception as e: print("Verlustbilanz nicht erstellt:", type(e).__name__, e, flush=True)
        rot = [e for e in B["schritte"][n_start:] if e.get("ok") is False]      # 16.11.2026: die Kette endete IMMER mit rc 0 - auch mit abgestuerzten Stufen
        rc = rc or (4 if rot else 0)
        B["teillauf_ergebnis" if TEILLAUF else "lauf_ergebnis"] = dict(zeit=time.strftime("%Y-%m-%d %H:%M:%S"), stufen=len(B["schritte"]) - n_start, fehlgeschlagen=[e["stufe"] for e in rot], rc=rc, abbruch=abbruch, verlust_warnungen=len((B.get("verlustbilanz") or {}).get("warnungen") or [])); __import__("json_sicher").schreiben(bp, B)
        print(f"ERGEBNIS DES {'TEILLAUFS (seiten_wiederholung)' if TEILLAUF else 'LAUFS'}: {len(B['schritte']) - n_start} Stufen, " + (f"{len(rot)} NICHT in Ordnung: " + ", ".join(e["stufe"] for e in rot) if rot else "alle in Ordnung") + (" - ABGEBROCHEN" if abbruch else ""), flush=True)
        for e in rot: print(f"    {e['stufe']}: {str(e.get('fehler') or ' | '.join(e.get('ende', [])) or e.get('hinweis', ''))[:200]}", flush=True)
        print("GESAMTKETTE_TEILLAUF_ENDE" if TEILLAUF else "GESAMTKETTE_ENDE", bp, flush=True); return rc      # Teillauf: eigene Marke (Waechter/Skills suchen GESAMTKETTE_ENDE)
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
    if dran("vorpruefen") and os.path.isdir(fd):            # 22.11.2026 (schwabentor-1122): fotos_dir_quelle = alter Sammelordner, 311 von 504 'eigenen' Bildern waren Video-/Commons-/Online-Bilder ohne
        from fotos_sammeln import fremde_ordner              # Vorpruefung (Einblendungen -> config-7-Paare). Deren echte Ordner gehen als Fremdquelle in die Vorpruefung; fotos_sammeln nimmt sie nur von dort.
        fie = [d_ for d_ in fremde_ordner([fd]) if d_ not in fremd]; fremd += fie
        if fie: notiz(B, "fremd_in_eigen", True, ordner=len(fie), hinweis="Fremdbilder im eigenen Fotoordner -> Vorpruefung: " + "; ".join(fie[:30]))
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
        # 19.11.2026: Fotosatz geaendert (neue Netzfotos/Videobilder) -> SfM NEU. Vorher galt 'sfm/sparse/0 existiert' als erledigt: neu geholte Bilder kamen nie ins Modell.
        import hashlib, sqlite3
        fsj = os.path.join(P, "fotosatz.json"); namen_ = sorted(os.listdir(FV)) if os.path.isdir(FV) else []; sha_ = hashlib.sha1("\n".join(namen_).encode()).hexdigest(); neu_sfm = []
        if os.path.isdir(os.path.join(P, "sfm", "sparse", "0")):
            alt_ = json.load(open(fsj)) if os.path.isfile(fsj) else None
            if alt_ is None:                                                    # Lauf vor dem 19.11.: Bildnamen aus der SfM-Datenbank
                try:
                    c_ = sqlite3.connect("file:" + os.path.join(P, "sfm", "db.db") + "?mode=ro", uri=True); nd_ = sorted(r_[0] for r_ in c_.execute("SELECT name FROM images")); c_.close()
                    alt_ = dict(n=len(nd_), sha=hashlib.sha1("\n".join(nd_).encode()).hexdigest())
                except Exception as e_: print("HINWEIS Fotosatz des alten SfM-Laufs nicht lesbar (wird wiederverwendet):", e_, flush=True)
            if alt_ and alt_.get("sha") != sha_:
                neu_sfm = ["--neu", "sfm"]; notiz(B, "sfm_neu", True, hinweis=f"Fotosatz geaendert ({alt_.get('n')} -> {len(namen_)} Bilder): SfM und dichte Wolke werden neu gerechnet, alter Stand beiseite (pipe/*.alt_<zeit>, nicht geloescht)")
        t_s = time.time(); _pipe = [PY, "-u", "-I", "tools/pipeline_objekt.py", a.ziel, FV, P, "--stufe", a.dicht_stufe] + (["--mapper", a.mapper] if a.mapper else []); _to = float(os.environ.get("RCPARK_STUFE_MAX_S", "43200"))   # 20.11.2026: SfM mind. 6 h - das 3-h-Standardlimit brach den globalen Mapper bei 2107 Bildern ab (rc 124)
        if os.environ.get("RCPARK_LAGE_FRUEH", "1") != "0":                   # 22.11.2026 VORSTUFE 'Lage frueh' (tools/lage_frueh.py): GPS-Tor + Lageproben auf dem duennen Netz VOR der dichten Wolke
            rc_s, _abbr = __import__("lage_frueh").sfm_mit_vorstufe(B, lauf, notiz, _pipe, neu_sfm, ZR, P, FV, a.ziel, log, _to, py=PY)
            if _abbr: json.dump(dict(n=len(namen_), sha=sha_, zeit=time.strftime("%Y-%m-%d %H:%M")), open(fsj, "w")); return abschluss(3, _abbr)   # SfM steht fuer diesen Fotosatz
        else: rc_s = lauf(B, "sfm", _pipe + neu_sfm, log, platz=[P], timeout=_to)[0]
        if rc_s == 0: json.dump(dict(n=len(namen_), sha=sha_, zeit=time.strftime("%Y-%m-%d %H:%M")), open(fsj, "w"))
        B["lage"] = dict(bestanden=None, hinweis="neue SfM - Lage-Tore noch nicht gelaufen (Stufe 'tore')")
        stj = os.path.join(P, "sfm", "sift_tor.json")                           # 24.11.2026: Pflicht-Tor der Merkmalssuche (tools/sift_einstellung.py) - fehlende Bilder ROT, nie still
        if os.path.isfile(stj) and os.path.getmtime(stj) >= t_s:
            try: st_ = json.load(open(stj))
            except Exception as e_: st_ = dict(rot=True, fehlend=["?"], optionen=f"sift_tor.json unlesbar: {e_}")
            notiz(B, "sift_tor", not st_.get("rot"), bilder=st_.get("bilder"), fehlend=len(st_.get("fehlend") or []), beispiele=(st_.get("fehlend") or [])[:5],
                  nachgeholt_cpu=len(st_.get("nachgeholt_cpu") or []), log_failed=st_.get("log_failed"), optionen=st_.get("optionen"))
        mwj = os.path.join(P, "sfm", "mapper_wahl.json")                         # 19.11.2026 (Nutzer): trug der Konsens-Mapper nicht, steht der DATENMANGEL als eigene rote Zeile im Bericht (nie still die langsamere/schlechtere Methode)
        try:
            mw = json.load(open(mwj)) if os.path.isfile(mwj) and os.path.getmtime(mwj) >= t_s else {}
            if mw.get("datenmangel"): print("ACHTUNG DATENMANGEL (Mapper): " + "; ".join(mw["datenmangel"].get("ursachen", [])) + " | ABHILFE: " + mw["datenmangel"].get("abhilfe", ""), flush=True); notiz(B, "datenmangel", False, mapper=mw.get("gewaehlt"), **mw["datenmangel"])
            elif mw: notiz(B, "mapper", True, gewaehlt=mw.get("gewaehlt"), sekunden=mw.get("konsens_sek") or mw.get("global_sek"))
            # 21.11.2026: Vorstufe 'seiten' der SfM (tools/sfm_seiten_vorstufe.py) - Bildteile ohne echte Verbindung und fehlende Seiten stehen als eigene Zeile im Bericht (nie still eine Seite weglassen)
            sv_ = mw.get("seiten") or {}; se_ = sv_.get("erkennung") or {}
            if se_: notiz(B, "seiten_vorstufe", not se_.get("getrennt") and not se_.get("meldungen"), bildteile=se_.get("teile"), fremde_bilder=se_.get("fremd"), verwechselt=se_.get("verwechselt_pruefer"), masken=sv_.get("masken_weg"),
                          mapper_db=os.path.basename(se_.get("db") or ""), modelle=mw.get("modelle"), meldungen=se_.get("meldungen"),
                          hinweis=("Seiten getrennt: je Seite ein Modell + Vereinen siehe Zeile 'seiten_modelle' (tools/sfm_seiten_modelle.py)" if se_.get("getrennt") else se_.get("hinweis") or ""))
            # 21.11.2026: Seitenmodelle (tools/sfm_seiten_modelle.py) - sparse/0 ist das VEREINTE Modell oder, wenn das Vereinen abgelehnt wurde, Teil A allein. Rot, sobald ein Teil
            # nicht vereint ist oder der Weg nicht lief; die Meldungen (welcher Teil, Pruefwerte aus vereinen.json) stehen woertlich im Bericht. Das Seiten-Blick-Tor (Stufe 'tore')
            # prueft danach sparse/0 = das vereinte Modell.
            sm_ = mw.get("seiten_modelle")
            if sm_: notiz(B, "seiten_modelle", bool(sm_.get("gerechnet")) and sm_.get("art") == "vereint" and not sm_.get("nicht_vereint"), art=sm_.get("art"), teil_a=sm_.get("teil_a"), vereint=sm_.get("vereint"),
                          nicht_vereint=sm_.get("nicht_vereint"), meldungen=sm_.get("meldungen"), grund=sm_.get("grund"), bericht=sm_.get("bericht"))
            elif se_.get("getrennt"): notiz(B, "seiten_modelle", False, fehler="Seiten getrennt, aber Seitenmodelle nicht gerechnet (RCPARK_SEITEN_MODELLE=0 oder erzwungener Mapper) - sparse/0 enthaelt nur einen Teil")
            elif sv_.get("abgeschaltet"): notiz(B, "seiten_vorstufe", False, fehler="Vorstufe 'seiten' abgeschaltet (RCPARK_SEITEN=0) - keine Masken, keine Seitenerkennung, Seiten-Blick-Tor ohne Urteil")
        except Exception as e_: print("HINWEIS mapper_wahl.json nicht lesbar:", e_, flush=True)
        if rc_s != 0: return abschluss(4, f"SfM gescheitert (rc {rc_s}) - Wolke/Ausrichtung eines frueheren Laufs werden NICHT weiterverwendet")
        alt = [x_ for x_ in (W, AU) if not frisch(x_, t_s)]
        if alt: return abschluss(4, "SfM endete mit rc 0, schrieb aber NICHT neu: " + ", ".join(os.path.relpath(x_, ROOT) for x_ in alt) + f" (LoD2-Abgleich gescheitert? {P}/pipeline.log) - alte Wolke/Ausrichtung werden nicht weiterverwendet")

    if dran("sfm") or dran("tore"): foto_auftrag_skizze(B, "frueh", ZR, Z, P, W, AU, FV, log)      # 22.11.2026: Fotoluecken sofort als Bild (vor den Toren - auch ein Abbruch dort hat dann den Auftrag)
    _sb = [None]                                                           # Ergebnis des Seiten-Blick-Tors (haengt nur am SfM-Modell, nicht an der Ausrichtung -> einmal je Lauf)
    def tore(tag):
        sp = os.path.join(P, "sfm", "sparse", "0"); erg = {}
        if not os.path.isdir(sp): notiz(B, f"tor_kamera{tag}", False, fehler=f"kein SfM-Netz {sp} - Kameraabdeckung und Insel-Tor NICHT geprueft (17.11.2026: wurden still uebersprungen)")
        if not os.path.exists(AU): notiz(B, f"tor_gps{tag}", False, fehler=f"keine Ausrichtung {AU} - GPS-Tor und Kamera-Gelaende-Tor NICHT geprueft")
        if os.path.isdir(sp): erg["kamera"] = lauf(B, f"tor_kamera{tag}", [PY, "-I", "tools/kamera_abdeckung.py", sp], log, ok=(0, 2))[0]
        erg["gps"] = lauf(B, f"tor_gps{tag}", [PY, "-I", "tools/lage_gps_pruefen.py", ZR, os.path.relpath(AU, ROOT), "--fotos", FV], log)[0] if os.path.exists(AU) else None
        # 22.11.2026 LAGEPROBEN der Ausrichtung (tools/lage_proben.py, in SFM-AUSRICHTUNG transformation.lage_proben): 'keine'/'mehrdeutig' = keine Loesung besteht alle
        # urteilsfaehigen unabhaengigen Proben (Oberkante/DOM1, Kamerahoehe, Wandfit mit Nachbarn) -> Lage nicht belegt, nicht modellieren (rc 3); 'belegt' = 0; sonst kein Urteil.
        try:
            import lage_proben as _LPR                                      # 22.11.2026: Regel als Funktion (lage_proben.tor_rc) - dieselbe im Lage-Pruefstand
            erg["lage_proben"], _lpt = _LPR.tor_rc(json.load(open(AU)).get("transformation") if os.path.exists(AU) else None)
            if _lpt: notiz(B, f"tor_lage_proben{tag}", erg["lage_proben"] != 3, hinweis=_lpt)
        except Exception as e_: erg["lage_proben"] = None; print("Lageproben nicht lesbar:", e_, flush=True)
        if os.path.exists(AU): erg["kamera_gelaende"] = lauf(B, f"tor_kamera_gelaende{tag}", ["python3", "-I", "tools/kamera_gelaende.py", ZR, os.path.relpath(AU, ROOT), "--fusion", os.path.join(P, "dicht", "stereo", "fusion.cfg")], log, ok=(0, 3))[0]   # Hinweis-Tor (15.11.): Bildgruppen unter Gelaende = Geisterwaende; 24.11.: Urteil ueber die Bilder der FUSION (sonst dauernd rot nach dem Neufusionieren)
        if os.path.isdir(sp):                                              # 20.11.2026 (Martinstor FlexGlue-Nacht): Hinweis-Tore Seitenverkleben - Modell aus punktlos getrennten Stuecken? Kameras gegen Foto-GPS auf der falschen Turmseite?
            erg["zerfall"] = lauf(B, f"tor_zerfall{tag}", [PYC, "-I", "tools/modell_zerlegen.py", sp, "--min-bilder", "10"], log, ok=(0, 3))[0]
            if erg["zerfall"] == 3 and os.path.isfile(os.path.join(sp, "vereint.json")):   # 21.11.2026: vereinte Seitenmodelle haben ABSICHTLICH keine gemeinsamen Punkte - ihre Lage zueinander kommt aus seiten_vereinen und wird vom Seiten-Blick-Tor geprueft
                notiz(B, f"tor_zerfall_hinweis{tag}", True, hinweis="sparse/0 ist aus Seitenmodellen vereint (sparse/0/vereint.json, tools/sfm_seiten_modelle.py): mehrere Stuecke ohne gemeinsame Punkte sind hier erwartet, kein Zerfall des Mappers")
            erg["gps_seiten"] = lauf(B, f"tor_gps_seiten{tag}", [PYC, "-I", "tools/gps_seiten_pruefen.py", sp, "--bilder", FV], log, ok=(0, 2, 3))[0]
            if tag == "":
                # 21.11.2026 HARTES Tor gegen Seitenverklebung (Martinstor: 51 Sued-Bilder auf der Nordwand, tor_zerfall meldete 'ein Stueck', GPS-Tor ohne GPS-Fotos): Bildgruppen, die
                # die Seitenerkennung als 'verwechselt' kennt, duerfen im Modell nicht in dieselbe Richtung blicken. rc 3 = verklebt -> Modell nicht weiterverwenden (Abbruch unten).
                sj_ = os.path.join(P, "sfm", "seiten.json")
                if os.path.isfile(sj_): _sb[0] = lauf(B, "tor_seiten_blick", [PYC, "-I", "tools/seiten_blick_tor.py", sp, sj_, "--aus", os.path.join(P, "sfm", "seiten_blick.json")], log)[0]
                else: notiz(B, "tor_seiten_blick", False, fehler=f"keine {sj_} - Seiten-Blick-Tor NICHT geprueft (SfM vor dem 21.11.2026 gerechnet oder Vorstufe 'seiten' abgeschaltet, RCPARK_SEITEN=0)")
                verbund_hinweise(B, sp, P, FV, log)
                # Sperrliste fuers Messen: Kameras, deren Brennweite das Modell nicht festlegt (wandern zwischen zwei Mapper-Laeufen zu 67-100 %), vereinigt mit der Liste der
                # unstabilen Kameras des Konsens-Mappers -> sfm/sperrliste_messen.txt (die dichte Wolke nimmt sie ueber tools/dicht_bildwahl.py --ohne, siehe pipeline_objekt.py)
                uns_ = os.path.join(P, "sfm", "konsens_arbeit", "unstabil.txt"); mwj_ = os.path.join(P, "sfm", "mapper_wahl.json")
                try: kons_ = os.path.isfile(uns_) and json.load(open(mwj_)).get("gewaehlt") == "konsens"
                except Exception: kons_ = False
                lauf(B, "brennweite_schaerfe", [PYC, "-I", "tools/brennweite_schaerfe.py", sp, "--aus", os.path.join(P, "sfm", "brennweite_schaerfe.json"), "--liste", os.path.join(P, "sfm", "unbestimmt.txt"),
                                                "--sperrliste", os.path.join(P, "sfm", "sperrliste_messen.txt")] + (["--vereinen", uns_] if kons_ else []), log)
            erg["seiten_blick"] = _sb[0]
        if os.path.isdir(sp): erg["insel"] = lauf(B, f"tor_insel{tag}", [PYC, "-I", "tools/kette_insel_pruefen.py", ZR, sp], log, ok=(0, 3))[0]   # 15.11. (Schwabentor): Bildketten ohne Fremdstuetze (Videoclip) = Faecher/Geisterwolke; schreibt audit/kette_insel.json
        erg["grundriss"] = lauf(B, f"tor_grundriss{tag}", [PY, "-I", "tools/wolke_grundriss_pruefen.py", ZR, "--wolke", W], log)[0] if os.path.exists(W) else None
        # 22.11.2026 LOT-TOR Wandneigung (Kettenlauf 1122n: Modell 3,2 Grad gekippt, alle Lage-Tore gruen -> Tiefensweep 'nicht belastbar', Bilderker fehlt): gemeinsame
        # Kippung der Waende des Zielgebaeudes in der dichten Wolke, rc 3 = kippt > 2 cm/m -> Lage nicht bestanden (lage_proben.lage_bestanden, RCPARK_LOT_TOR=hinweis = nur melden).
        if os.path.exists(W):
            _rl = lauf(B, f"tor_lot{tag}", [PY, "-I", "tools/lot_wandneigung.py", ZR, "--wolke", W, "--ausrichtung", AU], log, ok=(0, 4))[0]
            erg["lot"] = __import__("lage_proben").lot_rc(_rl)
        # 22.11.2026 (Nulllauf schwabentor-1122f: Westwand ~3 m dick aus zwei per GPS vereinten Seitenteilen): je LoD2-Kante Wanddicke + Lageversatz der Seitenteile ->
        # audit/wand_dicke.json. NUR MESSUNG (kein Abbruch, Grenzen noch ANNAHME); abschalten: RCPARK_WANDDICKE=0.
        smj_ = os.path.join(P, "sfm", "seiten_modelle.json")
        if os.environ.get("RCPARK_WANDDICKE", "1") != "0" and os.path.isfile(smj_) and os.path.exists(AU):
            erg["wand_dicke"] = lauf(B, f"tor_wanddicke{tag}", [PYC, "-I", "tools/wand_dicke_tor.py", ZR, "--seiten", smj_, "--ausrichtung", AU, "--aus", os.path.join(Z, "audit", "wand_dicke.json")], log, ok=(0, 2, 3))[0]
        # 22.11.2026 REGEL "Teil nur bei belegter Lage" (tools/seiten_lage_beleg.py): weggelassene Seitenteile = FOTOLUECKE, sichtbar im Kettenergebnis (rot, kein Abbruch -
        # die Kette baut mit dem Hauptteil weiter, die Wand bleibt 'ungesehen' und geht in Fotoauftrag/seiten_luecken).
        if tag == "" and os.path.isfile(smj_):
            try: _fl = json.load(open(smj_)).get("fotoluecken") or []
            except Exception as e_: _fl = []; print("seiten_modelle.json nicht lesbar:", e_, flush=True)
            for f_ in _fl: notiz(B, f"seiten_fotoluecke_teil{f_.get('teil')}", False, fehler=f_.get("text"), grund=str(f_.get("grund"))[:400], fotos_noetig=f_.get("fotos_noetig"), azimut_grad=f_.get("azimut_grad"))
        if os.path.isdir(sp) and os.path.exists(AU):                       # 19.11.2026 (Martinstor, schiefe uebergrosse Haeuserzeile aus einem Fernclip): setzt eine Bildgruppe Punkte hoch ueber die LoD2-Hoehe? -> audit/wolke_gruppen.json
            erg["gruppen"] = lauf(B, f"tor_gruppen{tag}", [PYC, "-I", "tools/wolke_gruppen_pruefen.py", ZR, os.path.relpath(AU, ROOT), sp, "--schreiben"], log, ok=(0, 3))[0]
        return erg

    if dran("tore"):
        erg = tore("")
        if erg.get("seiten_blick") not in (0, None):                      # 21.11.2026: hartes Tor - eine andere Ausrichtung heilt ein verklebtes SfM-Modell nicht, deshalb kein Loesungs-Kreislauf
            B["lage"] = dict(tore=erg, bestanden=False, fehler="seiten_verklebt" if erg["seiten_blick"] == 3 else "tor_abgestuerzt"); __import__("json_sicher").schreiben(bp, B)
            if erg["seiten_blick"] == 3: return abschluss(3, "SEITEN-BLICK-TOR durchgefallen: aehnliche Seiten liegen im SfM-Modell aufeinander (pipe/sfm/seiten_blick.json) - Modell NICHT weiterverwenden, nicht modellieren. Abhilfe: Seiten getrennt rechnen und vereinen (tools/seiten_erkennen.py, tools/seiten_vereinen.py)")
            return abschluss(4, f"Seiten-Blick-Tor abgestuerzt (rc {erg['seiten_blick']}, Log ansehen) - KEIN Urteil ueber Seitenverklebung")
        bestanden = __import__("lage_proben").lage_bestanden           # 22.11.2026: eine Funktion fuer Kette und Lage-Pruefstand (Regel unveraendert)
        try:                                                             # 15.11.: Hoehen-Tor (DOM1-Laser gegen Modelldach) bei jedem neuen Objekt mit LoD2 in bauen_abnehmen einschalten
            _o = json.load(open(os.path.join(ROOT, ZR)))
            if _o.get("lod2", {}).get("id") and "hoehen_tor" not in _o: _o["hoehen_tor"] = True; __import__("json_sicher").schreiben(os.path.join(ROOT, ZR), _o)
        except Exception as e_: print("hoehen_tor nicht gesetzt:", e_, flush=True)
        def _gruppen_aus():                                                # Liste des Wolken-Gruppen-Tors nicht leer (leer = Ausrichtung selbst verdaechtig, dann nichts ausschliessen)
            try: return bool(json.load(open(os.path.join(Z, "audit", "wolke_gruppen.json"))).get("ausschliessen"))
            except Exception: return False
        _FVB = __import__("fusion_vorab")                                 # 24.11.2026: Ausloese-Regel als Funktion (dieselbe sagt in der Vorstufe die Neufusion voraus -> nur EINE Fusion je Lauf)
        if _FVB.noetig(erg, bestanden, _gruppen_aus):   # 15.11.: Geisterwand aus Kameras unter Gelaende -> ohne sie neu fusionieren (Minuten), Tore wiederholen; 19.11.: auch wenn das Gruppen-Tor Bilder nennt (unabhaengig vom GPS-Tor, das am Martinstor blind ist)
            rc_f, _ = lauf(B, "neu_fusionieren", [PYC, "-I", "tools/wolke_neu_fusionieren.py", ZR, P, "--stufe", a.dicht_stufe], log, ok=(0, 2), platz=[P])
            if rc_f == 0: erg = tore("_ohne_tiefe_kameras")
            if rc_f in (0, 2) and not bestanden(erg) and erg.get("grundriss") == 3:        # Haufen aus EINER Bildquelle (Geisterwand, Kameras nicht unter Gelaende) -> diese Bilder auch weg
                rc_h, _ = lauf(B, "neu_fusionieren_haufen", [PYC, "-I", "tools/wolke_neu_fusionieren.py", ZR, P, "--stufe", a.dicht_stufe, "--haufen"], log, ok=(0, 2))
                if rc_h == 0: erg = tore("_ohne_haufenquelle")
        elif _FVB.offen(P):                                                # 24.11.2026 RUECKFALL Vorab-Ausschluss: erste Fusion war gekuerzt, die Regel feuert nach der dichten Wolke aber NICHT -> Fusion mit der fusion.cfg von vorher
            rc_z, _ = lauf(B, "vorab_zurueck", [PYC, "-I", "tools/wolke_neu_fusionieren.py", ZR, P, "--stufe", a.dicht_stufe, "--vorab-zurueck"], log, ok=(0, 2), platz=[P])
            notiz(B, "fusion_vorab_rueckfall", rc_z in (0, 2), hinweis="Vorab-Ausschluss vor der ersten Fusion war nicht noetig (Tore nach der dichten Wolke loesen keine Neufusion aus) - zweite Fusion mit allen Bildern wie vor dem 24.11. (tools/fusion_vorab.py)")
            if rc_z == 0: erg = tore("_vorab_zurueck")
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
    KD = os.path.join(D, "kanten"); t_k = None                          # t_k: Start der Kantenstufe in DIESEM Lauf (None = nicht gelaufen -> Kantendateien nur auf Existenz)
    if dran("kanten"):
        if os.path.exists(AU):
            t_k = time.time()
            if lauf(B, "kanten", [PY, "-u", "-I", "tools/kantenstufe.py", ZR, "--ausrichtung", AU, "--bilder", FV, "--aus", KD] + (["--wolke", W] if os.path.exists(W) else []), log, ok=(0, 4))[0] == 4:      # 22.11.2026 KREISFALL: Suchraum = modellfreier Messkoerper (Standard der Kantenstufe), Wolke nur Lage-Veto      # 17.11.2026: rc 4 (< 6 Kameras sehen das Modell / < 2000 Kantenpunkte) stand als 'in Ordnung' im Bericht -
                notiz(B, "kanten_ergebnis", False, fehler="Kantenstufe OHNE Ergebnis (rc 4: zu wenige Kameras oder Kantenpunkte, kein Kanten-F1) - Kernmethode nicht erfuellt; Kameras/Stabilkarten pruefen (kanten_bericht.json 'fehler')")      # die Kernmethode (Fotokanten) lief leer
        else: notiz(B, "kanten", False, fehler=f"keine Ausrichtung {AU}")
    if t_k is not None:                                                  # 23.11.2026 AUDIT: kantenstufe endet bei fehlendem Suchraum (rc 4) VOR kam/kam_wahl, bei < 6 Kameras VOR dem Sweep -
        beleg(B, "kanten", [os.path.join(KD, n_) for n_ in ("kam.json", "kam_wahl.json", "sweep.npz")], t_k, altstand_beiseite=True,      # Foto-Tor, Ebenen-Bauplan, Vordach und
              folge="Altstaende beiseite; Foto-Tor, bauplan_ebenen/vordach_profil und kanten_fertig rechnen in diesem Lauf NICHT mit Kameras/Sweep eines frueheren Laufs")   # kanten_fertig lasen sonst den Stand eines frueheren Laufs
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
    t_fk = None                                                          # Start der fassaden_kette in DIESEM Lauf mit rc 0 (sonst None)
    if dran("fassaden") and os.path.exists(AU):                         # 15.11.2026: Fassaden-Kette automatisch (Netz -> Relief je LoD2-Wand -> Putz per Fotofarbe -> Steine in Loechern), danach neu bauen
        dd = os.path.join(P, "dicht"); nz = os.path.join(P, "openmvs", "mesh_modell_ausschnitt.npz")
        t_n = time.time()
        if os.path.exists(os.path.join(dd, "fused.ply")) and lauf(B, "fassaden_netz", [PY, "-I", "tools/netz_aus_dicht.py", ZR, dd], log)[0] == 0 and frisch(nz, t_n):      # frisch: ein Netzausschnitt eines frueheren Laufs gilt nicht
            t_fk = time.time()
            if lauf(B, "fassaden_kette", [PY, "-I", "tools/fassaden_kette.py", ZR, "--netz", nz, "--fotosteine"] + fein_paar(P, FV), log)[0] == 0: bauen(B, "bauen_mit_fassaden", a.ziel, log)
            else: t_fk = None                                            # gescheitert: fassaden_kette.json gilt in diesem Lauf nicht (Stufe mono unten)   # --fein: lokale Feinrechnung der Tiefe je Wand (GPU, ~11 min je Wand)
        else: notiz(B, "fassaden", False, fehler=f"kein dichter Ordner ({dd}/fused.ply) oder Netzstufe ohne neues Ergebnis ({nz})")
    fk_beleg = not dran("fassaden") or beleg(B, "fassaden_kette", [os.path.join(Z, "audit", "fassaden_kette.json")], t_fk or time.time() + 9, folge=("fassaden_kette lief in diesem Lauf nicht mit rc 0 - " if t_fk is None else "") + "Stufe mono NICHT gelaufen (sie las sonst Relief/Wandliste eines frueheren Laufs und schrieb die alte Datei mit neuem Zeitstempel zurueck)") if os.path.exists(os.path.join(Z, "audit", "fassaden_kette.json")) else False   # 23.11.2026 AUDIT
    if dran("fassaden") and fk_beleg and os.environ.get("RCPARK_OHNE_MONO") != "1":      # 17.11.2026 Stufe 'mono' (nach relief_putz/steine der Fassaden-Kette): Feinrelief aus Einzelfotos,
        fkj = os.path.join(Z, "audit", "fassaden_kette.json"); FK = json.load(open(fkj)); stl_m = os.path.join(D, "messkoerper.stl"); mono_w = []; mono_v = {}; mono_u = []
        if lauf(B, "mono_messkoerper", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--nur-messkoerper", stl_m], log)[0] != 0 and os.path.exists(stl_m): os.remove(stl_m)      # 22.11.2026 KREISFALL: Fotowahl (Sicht) gegen den modellfreien Messkoerper statt gegen das gebaute Modell      # tools/relief_aus_fotos_mono.py (Depth Anything V2 Small, Apache-2.0), Feld = Wand bis 10 m
        for w_ in FK.get("waende", []):                                   # TOR: Korrelation je Foto mit dem Scan-Bandpass >= 0,2 (schwaechere Fotos verwirft das Werkzeug; keins uebrig = rc 4 = Wand ohne Mono-Relief)
            rq_ = [os.path.join(Z, "relief", w_["name"] + e_ + ".npz") for e_ in ("_misch", "_voll")]; rq_ = [q_ for q_ in rq_ if os.path.exists(q_)]
            L_, z1m = float(w_.get("laenge", 0.0)), round(min(float(w_.get("z1", 0.0)), 10.0), 2)
            if w_.get("quader") is False and w_.get("steinzone"): z1m = round(min(z1m, float(w_["steinzone"][1])), 2)      # 24.11.2026 Quader-Tor je Zone: Putzwand mit Steinzone unten -> Mono nur in der Steinzone (Putz/Wandgemaelde korrelieren nicht mit dem Scan)
            if w_.get("aus") or w_.get("nur_foto") or not rq_ or not os.path.exists(stl_m) or L_ < 2.0 or z1m < 2.0: mono_u.append(w_.get("name")); continue
            mo = os.path.join(Z, "relief", w_["name"] + "_mono.npz")
            for e_ in (".npz", ".jpg", ".json"):
                if os.path.exists(mo[:-4] + e_): os.remove(mo[:-4] + e_)      # Ergebnis eines frueheren Laufs gilt nicht (das Werkzeug ueberschreibt nie)
            rc_ = lauf(B, "mono_" + w_["name"], [PY, "-I", "tools/relief_aus_fotos_mono.py", rq_[0], ZR, mo, "--feld", "0.1", str(round(L_ - 0.1, 2)), "0", str(z1m), "--stl", stl_m, "--min_korr", "0.2", "--gpu_mb", "3500"], log, ok=(0, 3, 4))[0]
            jm = mo[:-4] + ".json"; Jm = json.load(open(jm)) if os.path.exists(jm) else {}
            kor = [f_.get("korrelation_band_scan") for f_ in Jm.get("fotos", []) if "verworfen" not in f_]
            w_["mono"] = dict(rc=rc_, feld=[0.1, round(L_ - 0.1, 2), 0.0, z1m], korrelation=kor, fugen_f1=(Jm.get("fugenabgleich") or {}).get("feld"), datei=os.path.basename(mo) if rc_ == 0 and os.path.exists(mo) else None)
            mono_v[w_["name"]] = rc_
            if w_["mono"]["datei"]: mono_w.append(w_["name"])
        json.dump(FK, open(fkj, "w"), indent=1, ensure_ascii=False)
        ok_m, f_m = __import__("kette_beleg").bearbeitet_urteil(mono_w, mono_v, mono_u)      # 24.11.2026 AUDIT Punkt 9: 0 Waende mit Mono-Relief war "in Ordnung"
        notiz(B, "mono", ok_m, waende=mono_w, **({} if ok_m else dict(fehler=f_m + ("" if os.path.exists(stl_m) else " - kein Messkoerper (mono_messkoerper gescheitert)"))), hinweis="ANSEHEN: relief/<wand>_mono.jpg (Foto | Scan | neu); fassaden_kette.anbauen baut <wand>_mono.npz ein (seit 21.11.2026; OHNE_MONO=1 schaltet ab)")
    if dran("fenster") and os.path.exists(AU):                          # 15.11.2026: Fenster automatisch (Mehrfoto-Ortho -> OWLv2 -> Scheiben gruppieren); Probe Nordgiebel Schwabentor-Nachbarhaus: 6 von 6 sichtbaren Fenstern, 1-4 cm
        fo = os.path.join(D, "fassade"); fa = os.path.join(Z, "audit", "fenster_auto.json"); t_fen = time.time()
        if lauf(B, "fenster_ortho", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--messflaeche", "eben", "--aus", fo, "--einzeln", "--min-flaeche", "6"], log)[0] == 0:      # 22.11.2026 KREISFALL: Messorthos auf modellfreier Flaeche (LoD2 flach + Wandversatz aus Fotokanten), nie auf dem STL des vorigen Laufs (Tor 4,3/5,2 m je Lauf); Lauf von null braucht kein STL
            try: nfo = sum(len(f_.get("fotos") or {}) for f_ in json.load(open(os.path.join(fo, "fassaden.json")))["fassaden"])
            except Exception: nfo = 0
            if nfo == 0: notiz(B, "fenster_ortho_inhalt", False, fehler="KEIN Foto auf irgendeiner Fassade - Kameras/fotos_dir pruefen (rc 0 allein beweist nichts; 16.11.2026 lief die Kette so leer durch)")
            env_alt = dict(os.environ); os.environ.update(HF_HOME="/media/oem/scan/hf_cache", HF_HUB_OFFLINE="1")
            if lauf(B, "fenster_parsing", [PY, "-W", "ignore", "-I", "tools/fassade_parsing.py", "--ortho", fo, "--gpu"], log)[0] == 0 and (lauf(B, "fenster_ortho_fein", [PY, "-W", "ignore", "-I", "tools/fassade_ortho.py", ZR, "--messflaeche", "eben", "--aus", fo + "_fein", "--einzeln", "--min-flaeche", "6", "--zelle", "0.01", "--max-mpp", "0.02", "--beste", "3"], log, ok=(0, 1))[0] in (0, 1)) and (lauf(B, "fenster_fein", [PY, "-I", "tools/fassade_fein.py", fo + "_fein"], log, ok=(0, 1))[0] in (0, 1)) and lauf(B, "fenster_bauen_liste", [PY, "-I", "tools/fenster_aus_parsing.py", fo, "--aus", fa, "--fein", fo + "_fein"], log)[0] == 0:   # feines, ausgerichtetes 1-cm-Bild fuer Sprossen/Muster (Nutzer 15.11.: "immer alle Details mitnehmen"); wo kein Foto <= 2 cm/px hat, bleibt das grobe
                # 17.11.2026 (Schwabentor stand als geschlossener Klotz da): Bogenoeffnungen/Tordurchfahrten. Das Parsing fand den Torbogen (8 von 8 Stimmen), aber nur die Klasse 'fenster' ging in den Generator.
                # oeffnungen_bogen.py: Bogenkasten = Suchfenster -> Ebenen-Sweep (Durchblick belegt?) -> Formfamilie -> audit/oeffnungen_auto.json -> bauteile.oeffnungen_aus_json (Vorlage objekt_anlegen.py). Scheitert es, bleibt die Wand zu (rc != 0 nur im Bericht).
                if lauf(B, "oeffnungen_bogen", [PY, "-W", "ignore", "-I", "tools/oeffnungen_bogen.py", fo, "--objekt", ZR, "--aus", os.path.join(Z, "audit", "oeffnungen_auto.json")], log, ok=(0,))[0] == 0 and os.path.exists(gp_) and "oeffnungen_aus_json" not in open(gp_).read():
                    lauf(B, "generator_erneuern_oeffnungen", ["python3", "tools/objekt_anlegen.py", a.ziel, "--generator-erneuern"], log, ok=(0, 3))
                    if "oeffnungen_aus_json" not in open(gp_).read(): notiz(B, "generator_vorlage_oeffnungen", False, fehler=f"{os.path.basename(gp_)} ruft bauteile.oeffnungen_aus_json nicht auf - erkannte Tore/Bogenoeffnungen kommen NICHT ins Modell (Zeilen aus der Vorlage in tools/objekt_anlegen.py uebernehmen)")
                # 21.11.2026 (Schwabentor: Tor f00 gebaut, aber nur Nische 0,6 m - Gegenseite f01 hat 4 Fotos und keinen Bogenkandidaten): Durchfahrt ueber die durchgehende Laibung im
                # Torweg (dichte Wolke = Lage, keine Rueckwand) -> durchfahrt/tiefe_m in oeffnungen_auto.json (tools/durchfahrt_pruefen.py; Form bleibt aus Wandbild/Sweep).
                if os.path.exists(W) and os.path.exists(os.path.join(Z, "audit", "oeffnungen_auto.json")): lauf(B, "oeffnungen_durchfahrt", [PY, "-W", "ignore", "-I", "tools/durchfahrt_pruefen.py", os.path.join(fo, "fassaden.json"), os.path.join(Z, "audit", "oeffnungen_auto.json"), "--wolke", W], log, ok=(0, 3))
                bauen(B, "bauen_mit_fenstern", a.ziel, log)
            os.environ.clear(); os.environ.update(env_alt)
        # 23.11.2026 AUDIT STILLE ERFOLGE: scheiterte eine Stufe der Fensterkette (oder endete sie ohne zu schreiben), lasen bauplan/seiten das Wandbild und der Generator die
        # Fenster/Oeffnungen eines FRUEHEREN Laufs (anderer Rahmen, andere Fassadennummern). Ausgaben muessen aus diesem Lauf stammen, sonst beiseite (.veraltet_<zeit>) + rot.
        beleg(B, "fenster", [os.path.join(fo, "fassaden.json"), os.path.join(fo, "elemente.json"), fa, os.path.join(Z, "audit", "oeffnungen_auto.json")], t_fen, altstand_beiseite=True,
              folge="Altstand beiseite - Bauplan, Seiten und Generator verwenden in diesem Lauf KEIN Wandbild/Fenster/Tor eines frueheren Laufs")
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
        if os.path.exists(gp_) and not all(w_ in open(gp_).read() for w_ in ("rueckwaende", "laube_aus_wandbild", "vorbauten_aus_json", "uhren_aus_json", "korrekturen_aus_json", "wolkenrest_koerper", "dach_aus_profil", "umgang_aus_json", "loch_gewaende_spaet", "bogen_gewaende_spaet", "hoehen_aus_json")): lauf(B, "generator_erneuern_bauplan", ["python3", "tools/objekt_anlegen.py", a.ziel, "--generator-erneuern"], log, ok=(0, 3))
        if not all(os.path.exists(os.path.join(fo, f_)) for f_ in ("fassaden.json", "elemente.json")): notiz(B, "bauplan", False, fehler=f"{fo}/fassaden.json oder elemente.json fehlt (Stufe fenster: fassade_ortho + fassade_parsing)")
        else:
            oa_ = os.path.join(Z, "audit", "oeffnungen_aussen.json")
            # 18.11.2026: Innenwandsuche ZUERST - ihre Tiefenkarten (bauplan/tiefe/tiefe_fNN.npz, Sweep bis Gebaeudetiefe) entscheiden, ob ein Bogen offen ist (Laube; Kaufhaus: 3 von 4 Boegen fielen weg)
            erg_["innenwaende_rc"] = lauf(B, "bauplan_innenwaende", [PY, "-W", "ignore", "-I", "tools/innenwaende_finden.py", ZR, fo, "--arbeit", os.path.join(bp_, "tiefe"), "--schreiben"], log, ok=(0, 3))[0]
            t_oa = time.time()
            if os.path.isdir(ffn): lauf(B, "bauplan_oeffnungen_aussen", [PY, "-W", "ignore", "-I", "tools/oeffnungen_wandbild.py", ZR, ffn, "--grob", fo, "--aus", oa_, "--tiefe_ordner", os.path.join(bp_, "tiefe")], log)
            # 23.11.2026 AUDIT: rc wurde hier verworfen ('== 0: pass') - nach Absturz oder ohne feines Wandbild lasen rueckwand_tiefe und loch_gewaende die Aussenoeffnungen eines frueheren Laufs
            beleg(B, "bauplan_oeffnungen_aussen", [oa_], t_oa, altstand_beiseite=True, folge="Altstand beiseite - Rueckwandtiefe (dann ANNAHME) und Tueren in loch_gewaende ohne Aussenoeffnungen dieses Laufs"
                  + ("" if os.path.isdir(ffn) else f" (kein feines Wandbild {ffn})"))
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
                       and lauf(B, "bauplan_innen_oeffnungen", [PY, "-W", "ignore", "-I", "tools/oeffnungen_wandbild.py", ZR, iof_, "--grob", io_, "--nur", nur_, "--aus", oi_], log)[0] in (0, 3))      # 24.11.2026: rc 3 = Bogen ohne Tiefenurteil (rot im Bericht), die Datei ist trotzdem geschrieben
                os.environ.clear(); os.environ.update(env_alt); oz_ = json.load(open(ZJ))
                if ok_ and os.path.exists(oi_):
                    oz_["innenwand_oeffnungen"] = dict(datei=os.path.relpath(oi_, Z), ncc_min=0.2, auto="bauplan " + time.strftime("%Y-%m-%d"), quelle=f"Kettenstufe bauplan: Sicht-Modell (innenwaende_finden --sicht_stl) -> fassade_ortho {nur_} 5 cm + 1 cm einzeln -> fassade_fein --fein_ausrichten 1 -> fassade_parsing (OWLv2) -> tools/oeffnungen_wandbild.py; Bilder {io_}/elemente_*.jpg, {oi_[:-5]}.jpg")
                    erg_["innenwand_oeffnungen"] = sum(len(F_.get("oeffnungen", [])) for F_ in json.load(open(oi_)).values())
                elif IO_ and IO_.get("auto"): oz_.pop("innenwand_oeffnungen", None)
                __import__("json_sicher").schreiben(ZJ, oz_)
            elif not IW_ and IO_ and IO_.get("auto"): oz_.pop("innenwand_oeffnungen", None); __import__("json_sicher").schreiben(ZJ, oz_)
            oz_ = json.load(open(ZJ)); erg_.update(innenwaende=[(x_["name"], x_.get("versatz"), x_.get("u"), x_.get("z")) for x_ in oz_.get("innenwaende", [])], rueckwand=(oz_.get("rueckwand") or {}).get("tiefe"))
            # 20.11.2026 (Nutzer: "Wir haben hier manuell alles gebastelt ... und jetzt haben wir diese Faehigkeit verloren"): Vorbauten aus dem Ebenen-Sweep BAUEN statt nur vorschlagen.
            # Der Sweep lief bisher erst in Stufe 'seiten' (nach dem Bau) und endete als Vorschlagsliste - hier vor dem Bau, Ergebnis audit/vorbauten_auto.json -> bauteile.vorbauten_aus_json
            vb_ = {}
            for i_ in range(len(json.load(open(os.path.join(fo, "fassaden.json")))["fassaden"])):
                t_sw = time.time(); vb_[f"f{i_:02d}"] = lauf(B, f"bauplan_sweep_f{i_:02d}", [PY, "-W", "ignore", "-I", "tools/fassade_tiefe.py", ZR, fo, str(i_)], log, ok=(0, 2, 4))[0]
                sweep_altstand(B, f"bauplan_sweep_f{i_:02d}", fo, i_, t_sw)
            # 22.11.2026 (1122n, Bilderker fehlte): Wand im Kamerarahmen geneigt (Lotfehler ~2,6 Grad) -> fassade_tiefe schaetzt die geneigte Wandebene; Neigung je Fassade in den Bericht
            erg_["wand_neigung"] = {i_: json.load(open(p_))["wand_ebene"].get("neigung_grad") for i_ in vb_ for p_ in [os.path.join(fo, f"vorbauten_{i_}.json")] if os.path.exists(p_) and json.load(open(p_)).get("wand_ebene")}
            if erg_["wand_neigung"]: print(f"WARNUNG Wandebene geneigt gegen LoD2 (Grad je Fassade) {erg_['wand_neigung']} - Lot der Ausrichtung pruefen (gegenueberliegende Waende gleichsinnig = Lotfehler, gegensinnig = Anzug)", flush=True)
            t_vb = time.time(); erg_["vorbauten_rc"] = lauf(B, "bauplan_vorbauten", [PY, "-I", "tools/vorbauten_bauplan.py", ZR, fo] + (["--fein", ffn] if os.path.isdir(ffn) else []), log, ok=(0, 3))[0]
            beleg(B, "bauplan_vorbauten", [os.path.join(Z, "audit", "vorbauten_auto.json")], t_vb, altstand_beiseite=True, folge="Altstand beiseite - Generator baut KEINE Vorbauten eines frueheren Laufs (vorbauten_bauplan abgestuerzt?)")   # 24.11.2026 AUDIT
            fa_ = os.path.join(Z, "audit", "fenster_auto.json")      # 21.11.2026: Fensterliste am Sweep pruefen (Konsolenfelder als 'Fenster' verworfen, Nischen unter der Stimmenschwelle ergaenzt)
            # 21.11.2026 SCHLEIFE Schritt 1+2 (Leitbild Nutzer: Bauplaene auf mehreren Ebenen, Masse aus Kanten): dichte triangulierte Fotokanten je Wand-/Sweep-Ebene, daraus die Masse der Vorbauten
            eb_ = os.path.join(D, "ebenen"); t_eb = time.time()
            if not os.path.exists(os.path.join(KD, "kam_wahl.json")): notiz(B, "bauplan_ebenen", False, fehler=f"{KD}/kam_wahl.json fehlt (Kantenstufe ohne Kameraauswahl in diesem Lauf) - Ebenen-Bauplan, Vorbau-Masse aus Kanten und Vordachprofil NICHT gerechnet")   # 23.11.2026 AUDIT: vorher still uebersprungen
            elif lauf(B, "bauplan_ebenen", [PY, "-W", "ignore", "-I", "tools/ebenen_bauplan.py", ZR, fo, KD, eb_], log, ok=(0, 3))[0] == 0:
                erg_["ebenen_masse_rc"] = lauf(B, "bauplan_ebenen_masse", [PY, "-W", "ignore", "-I", "tools/ebenen_masse.py", ZR, eb_], log, ok=(0, 3))[0]
                # 21.11.2026 (Nutzer: Vordach im Foto geschweiftes Walmdach, Modell ebene Platte): Profil/Walm aus Foto-Silhouetten (SfM-Kameras) -> audit/vordach_profil.json -> bauteile.vordach_walm
                if os.path.exists(os.path.join(KD, "kam.json")): erg_["vordach_profil_rc"] = lauf(B, "bauplan_vordach_profil", [PY, "-W", "ignore", "-I", "tools/vordach_profil.py", ZR, KD], log, ok=(0, 3))[0]
                # 23.11.2026 (1122t: Phantom-Vorbau f03 - Ebene ohne Kantenpunkt, Sweep-Tiefen am Rand des Suchraums, Fototor trotzdem BELEGT): BELEG-TOR vor dem Bau -
                # verworfene Gruppen bekommen 'verworfen' in vorbauten_auto.json, bauteile.vorbauten_aus_json baut sie nicht (rc 2 = verworfen, kein Fehler)
                if os.path.exists(os.path.join(Z, "audit", "vorbauten_auto.json")):
                    erg_["vorbau_beleg_rc"] = lauf(B, "bauplan_vorbau_beleg", [PY, "-W", "ignore", "-I", "tools/vorbau_fototor.py", "--beleg", os.path.join(Z, "audit", "vorbauten_auto.json"), fo, os.path.join(eb_, "ebenen.json")], log, ok=(0, 2, 3))[0]
            beleg(B, "bauplan_ebenen", [os.path.join(eb_, "ebenen.json")], t_eb, altstand_beiseite=True, folge="Altstand beiseite - Oeffnungen aus Kanten und Abweichung je Ebene rechnen NICHT mit den Ebenen eines frueheren Laufs")   # 23.11.2026 AUDIT
            # 24.11.2026 (Befund 1122x f00: Koerperwand 0,32-0,40 m VOR Fotokanten und Wolke, weil der Koerper auf der LoD2-Ebene stand): KOERPERWAND AUF DIE FOTOKANTEN-EBENE
            # (tools/wandlage_fotokanten.py, Guard: Fotokanten belastbar + Wolke gleiche Seite) -> 'wandversatz' in audit/schleife_korrekturen.json -> Generator setzt die Wand
            # am Grundkoerper zurueck (bauteile.korrekturen_aus_json), Relief/Fenster/Uhr folgen. Kettenlog: je Fassade eine Zeile 'WANDLAGE fNN: alt w, neu w, Beleg, uebernommen'.
            erg_["wandlage_rc"] = lauf(B, "bauplan_wandlage", [PY, "-W", "ignore", "-I", "tools/wandlage_fotokanten.py", ZR, eb_, "--fassade", fo] + (["--wolke", W] if os.path.exists(W) else []), log, ok=(0, 3))[0]
            if os.path.exists(fa_): erg_["fenster_tor_rc"] = lauf(B, "bauplan_fenster_tiefe", [PY, "-I", "tools/fenster_tiefe_tor.py", fa_, fo], log)[0]
            if os.path.exists(fa_) and os.path.isdir(ffn): erg_["nischen_fenster_rc"] = lauf(B, "bauplan_nischen_fenster", [PY, "-I", "tools/nischen_fenster.py", fa_, fo, ffn], log, ok=(0, 3))[0]   # 21.11.2026: Fenster in Nischen = zwei Ebenen, Umriss aus Bildkanten (Schwabentor: 1 statt 2 Rundbogenfenster, Nische 0,59 statt ~2 m)
            # 24.11.2026 (1122w West: Schlitz und Luke ueber 28 m fehlten - OWLv2 ohne Kasten, feines Wandbild dort leer wegen --max-mpp 0,02): kleine dunkle Oeffnungen
            # ohne Erkennerkasten aus dem Wandbild (fein, sonst grob 5 cm) + Mehrfoto-Kanten, Formfamilie >= 3 Fotos und Mehrheit der sehenden -> Fensterliste (mit 'loch')
            if os.path.exists(fa_) and os.path.isdir(ffn): erg_["schlitze_rc"] = lauf(B, "bauplan_schlitze", [PY, "-W", "ignore", "-I", "tools/schlitze_wandbild.py", fa_, fo, ffn], log, ok=(0, 3))[0]
            # 23.11.2026 (1122o neben_detail fenster_f03/_2, oeffnung f04): Erkennerkasten = Loch + Gewaende -> Loch (dunkle Komponente) und Gewaende (Nicht-Wand-Farbe am Loch)
            # aus dem feinen Wandbild; geschlossene Tueren (oeffnungen_aussen 'tuer', flach) kommen als Eintrag dazu. Paare aus nischen_fenster bleiben unberuehrt.
            if os.path.exists(fa_) and os.path.isdir(ffn): erg_["loch_gewaende_rc"] = lauf(B, "bauplan_loch_gewaende", [PY, "-W", "ignore", "-I", "tools/loch_gewaende.py", fa_, fo, ffn, "--oeffnungen", os.path.join(Z, "audit", "oeffnungen_aussen.json"), "--oeffnungen_auto", os.path.join(Z, "audit", "oeffnungen_auto.json")], log, ok=(0, 3))[0]
            if os.path.exists(fa_) and os.path.isdir(ffn): erg_["laibung_rc"] =lauf(B, "bauplan_laibung", [PY, "-W", "ignore", "-I", "tools/laibung_aus_fotos.py", fa_, ffn, ZJ], log, ok=(0, 3))[0]   # 21.11.2026 spaet: Laibungstiefe aus der seitlich sichtbaren Laibung in >= 3 Schraegfotos (Sweep sieht den Laden nicht)
            if os.path.exists(fa_) and os.path.isdir(ffn): erg_["sohlbank_rc"] = lauf(B, "bauplan_sohlbank", [PY, "-W", "ignore", "-I", "tools/sohlbank_aus_fotos.py", fa_, ffn, ZJ], log, ok=(0, 3))[0]   # 21.11.2026 spaet: Sohlbank unter Fenster/Nische (dunkles Band, Auskragung aus Bandhoehe/Laenge gegen die Blickschraege, >= 3 Fotos; bauteile.sohlbank)
            if os.path.exists(fa_) and os.path.isdir(ffn): erg_["fenster_form_tor_rc"] = lauf(B, "bauplan_fenster_form_tor", [PY, "-I", "tools/fenster_form_tor.py", fa_, ffn], log, ok=(0, 2, 3))[0]   # 21.11.2026 spaet: FORM der gebauten Fenster/Nischen an >= 3 Einzelfotos (rc 2 = FALSCH, hand_vergleich liest audit/fenster_form_tor.json)
            if os.path.isdir(ffn): erg_["umgang_rc"] = lauf(B, "bauplan_umgang", [PY, "-I", "tools/umgang_aus_fotos.py", ZR, ffn], log, ok=(0, 3))[0]   # 21.11.2026: offener Umgang unter der Traufe aus den Einzelfotos (Wandbild endet unter dem Dachueberstand)
            if os.path.isdir(ffn): erg_["uhren_rc"] = lauf(B, "bauplan_uhren", [PY, "-I", "tools/uhren_wandbild.py", ZR, ffn, "--elemente", os.path.join(fo, "elemente.json")], log, ok=(0, 3))[0]     # 21.11.2026 Kettenluecke 9: Uhr aus Erkennerzone + Kreis im 1-cm-Wandbild
            # 24.11.2026 (Befund 1122w: Ortsteine als duenne gleich lange Streifen, Uhrzone/Kante oben leer): ORTSTEINE als eigene Stufe - Wandbild + ausgerichtete Einzelfotos,
            # Lagen/Verzahnung/Stossfugen, TOR je Kante (IoU gegen die Steinflaeche + Deckung der Ortsteinzeilen; rc 2 = Kante verworfen und nicht gebaut). Beleg audit/ortsteine_auto.json
            # + audit/ortsteine_auto.jpg (ansehen!); der Generator (fassaden_kette.anbauen -> ortsteine.ortsteine_anbauen) liest das JSON.
            if os.path.isdir(ffn) and os.environ.get("OHNE_ORTSTEINE") != "1":
                t_os = time.time(); os_j = os.path.join(Z, "audit", "ortsteine_auto.json")
                erg_["ortsteine_rc"] = lauf(B, "bauplan_ortsteine", [PY, "-W", "ignore", "-I", "tools/ortsteine.py", ZR, "--fein", ffn, "--aus", os_j, "--bild", os.path.join(Z, "audit", "ortsteine_auto.jpg")], log, ok=(0, 2, 3))[0]
                beleg(B, "bauplan_ortsteine", [os_j], t_os, altstand_beiseite=True, folge="Altstand beiseite - Generator rechnet die Ortsteine ohne Beleg-JSON selbst (ortsteine_anbauen)")
            try: erg_["vorbauten"] = [(F_["id"], g_["u0"], g_["u1"], g_["z0"], g_["z1"], g_["koerper"]["w_median"]) for F_ in json.load(open(os.path.join(Z, "audit", "vorbauten_auto.json")))["fassaden"] for g_ in F_["gruppen"]]
            except Exception as e_: erg_["vorbauten"] = f"nicht lesbar: {e_}"
            # 21.11.2026 (Schwabentor: Wolke/Sweep gaben Tor 4,86-5,37 m, Rundbogen; das Wandbild zeigt Spitzbogen, lichte Weite 4,50 = Hand 4,49): Oeffnungen aus Wolke + Kanten + FEINEM
            # WANDBILD (tools/oeffnungen_aus_kanten.py) -> gebaute Oeffnungen in audit/oeffnungen_auto.json bekommen Form/lichte Masse aus den Bildkanten (--uebernehmen; Beifang baut nichts).
            oa_ = os.path.join(Z, "audit", "oeffnungen_auto.json")
            if os.path.exists(os.path.join(eb_, "ebenen.json")) and os.path.exists(oa_):
                erg_["oeffnungen_wandbild_rc"] = lauf(B, "bauplan_oeffnungen_wandbild", [PY, "-u", "-W", "ignore", "-I", "tools/oeffnungen_aus_kanten.py", ZR, eb_, "--uebernehmen", oa_]
                                                      + (["--wolke", W] if os.path.exists(W) else []), log, ok=(0, 3))[0]
                # 23.11.2026 (1122q: Stadttor fehlte - Sweep-Form verworfen, erst die Wandbild-Stufe baut es): Durchfahrt-Pruefung NACH der Uebernahme wiederholen (prueft nur gebaute ohne Durchfahrt)
                if erg_["oeffnungen_wandbild_rc"] == 0 and os.path.exists(W) and os.path.exists(os.path.join(fo, "fassaden.json")):
                    erg_["durchfahrt_nach_wandbild_rc"] = lauf(B, "bauplan_oeffnungen_durchfahrt", [PY, "-W", "ignore", "-I", "tools/durchfahrt_pruefen.py", os.path.join(fo, "fassaden.json"), oa_, "--wolke", W], log, ok=(0, 3))[0]
            # 24.11.2026 (1122w: Torboegen f00/f01 nur glattes Loch, Foto zeigt Sandstein-Gewaende aus Bogensteinen): Gewaende-Band je gebauter Oeffnung aus dem feinen
            # Wandbild (radiale Fugen-Kohaerenz, tools/bogen_gewaende.py) -> 'gewaende_band' in oeffnungen_auto.json -> bauteile.bogen_gewaende_spaet (echte Oberflaeche)
            if os.path.exists(oa_) and os.path.isdir(ffn): erg_["bogen_gewaende_rc"] = lauf(B, "bauplan_bogen_gewaende", [PY, "-W", "ignore", "-I", "tools/bogen_gewaende.py", oa_, ffn, "--fassade", fo, "--aus", os.path.join(Z, "audit")], log, ok=(0, 3))[0]
            if os.path.exists(gp_): bauen(B, "bauen_mit_bauplan", a.ziel, log)
            # 22.11.2026 (1122n: Bilderker fehlte ohne Meldung): Foto-F1 je gebautem Vorbau (teil_fotoform) - rc 2 = NICHT BELEGT (Praezision < 0,5), rc 3 = nichts zu pruefen
            vba_ = os.path.join(Z, "audit", "vorbauten_auto.json")
            if os.path.exists(gp_) and os.path.exists(vba_) and json.load(open(vba_)).get("fassaden"):
                erg_["vorbau_fototor_rc"] = lauf(B, "bauplan_vorbau_fototor", [PY, "-W", "ignore", "-I", "tools/vorbau_fototor.py", a.ziel, os.path.join(fo, "fassaden.json")], log, ok=(0, 2, 3, 4))[0]
                if erg_["vorbau_fototor_rc"] == 4: bauen(B, "bauen_nach_vorbau_tor", a.ziel, log)      # 23.11.2026: Regel (c) hat eine Gruppe verworfen -> ohne sie neu bauen
            # 21.11.2026 (ANALYSE_SACKGASSEN: Koerper, die auf keiner Wandebene liegen - Treppenturm, Dachueberstand, Laterne - kamen im Handlauf aus der dichten Wolke): Rest der Wolke am
            # gebauten Modell -> Dach-Schichtprofil (audit/dach_profil.json, nur einmal gegen das LoD2-Dach) und KOERPER-SCHLEIFE (tools/koerper_schleife.py: Haufen benennen, Nachbarn/Hohlraeume
            # abtrennen, Kandidaten bauen, JE KANDIDAT nachmessen, annehmen/verwerfen -> audit/koerper_auto.json) -> volle Abnahme, wenn die Schleife gebaut hat.
            if os.path.exists(W) and os.path.exists(gp_):
                dp_, ks_ = (os.path.join(Z, "audit", n_) for n_ in ("dach_profil.json", "koerper_schleife.json")); dach_neu_ = False
                if not os.path.exists(dp_) and os.path.exists(os.path.join(fo, "fassaden.json")): lauf(B, "bauplan_dachprofil", [PY, "-W", "ignore", "-I", "tools/dach_profil_wolke.py", ZR, W, os.path.join(fo, "fassaden.json")], log, ok=(0, 3)); dach_neu_ = os.path.exists(dp_)
                # 21.11.2026 (Schwabentor-1120: Hoehen-Tor +1,62 m / k 0,9605 war kein Massstab - Traufe/Grundriss/Lot/Boden passten -, sondern ein zu breites Wolken-Dachprofil auf 56 Grad):
                # aeltere Profile ohne DOM1-Veto nachziehen (nur die Scheiben, kein Neumessen gegen das schon umgebaute STL), dann neu bauen.
                # Version 2 (21.11.2026, 1121q: Ueberstand 0,9 -> 0,12 m): Veto 1 interpolierte ueber die Traufkante - aeltere Vetos von 'scheiben_vorher' neu ziehen (VETO_VERSION in dach_profil_wolke.py)
                elif os.path.exists(dp_) and (json.load(open(dp_)).get("dom1_veto") or {}).get("version", 1) < 2:
                    dach_neu_ = lauf(B, "bauplan_dachprofil_veto", [PY, "-W", "ignore", "-I", "tools/dach_profil_wolke.py", ZR, W, os.path.join(fo, "fassaden.json"), "--nur_veto"], log, ok=(0, 3))[0] == 0
                # 21.11.2026 (KERNMETHODE; Schwabentor: Wolke endet 3,5 m unter dem Knauf, Laternenhals im duennen Wolkenbereich): Laterne/Spitze aus der HIMMELSKANTE der kalibrierten
                # Fotos an der Dachachse (tools/spitze_aus_umriss.py -> Block 'spitze_foto' in dach_profil.json; bauteile.dach_aus_profil baut damit ueber dem Laternenhals). Masken aus dem Cache der Stufe 'dachfoto'.
                sp_rc_ = lauf(B, "bauplan_spitze_umriss", [PY, "-u", "-W", "ignore", "-I", "tools/spitze_aus_umriss.py", ZR], log, ok=(0, 3, 4))[0] if os.path.exists(dp_) else 3; erg_["spitze_umriss_rc"] = sp_rc_
                # 22.11.2026 (Foto IMG_113231/113056: offene Laterne mit Pfosten/Krempe/Haube/Knauf, Modell runde Zwiebel): Eckenzahl + Pfosten + Zonen aus den Kanten IM INNEREN der
                # Silhouette in voller Fotoaufloesung (tools/laterne_aus_fotos.py -> Block 'laterne_foto'; bauteile.dach_aus_profil baut dann bauteile.laterne statt der Drehringe).
                la_rc_ = lauf(B, "bauplan_laterne_foto", [PY, "-u", "-W", "ignore", "-I", "tools/laterne_aus_fotos.py", ZR, "--bild", os.path.join(Z, "audit", "laterne_foto.jpg")], log, ok=(0, 3, 4))[0] if sp_rc_ == 0 else 3; erg_["laterne_foto_rc"] = la_rc_
                # 21.11.2026 (Nutzer "noch nicht gut": dicke dunkle Traufe im Foto, 2-cm-Scheibe im Modell; Ueberstand nur "aus der Wolke"): TRAUFE aus Fotokanten
                # (tools/traufe_aus_fotos.py: Kanten-Sweep waagrechter Traufkanten mit den SfM-Kameras -> Block 'traufe_foto' in dach_profil.json; bauteile.traufe_einbauen baut
                # je gemessener Seite einen Traufkasten, ungesehene Seiten bleiben Wolke/DOM1). Bild audit/traufe_foto.jpg.
                tr_rc_ = lauf(B, "bauplan_traufe_foto", [PY, "-u", "-W", "ignore", "-I", "tools/traufe_aus_fotos.py", ZR], log, ok=(0, 3, 4))[0] if os.path.exists(dp_) else 3; erg_["traufe_foto_rc"] = tr_rc_
                # 22.11.2026: Dachflaechen-Form (gerade/geschweift/gewoelbt) + Fuss des Aufsatzes aus Foto-Silhouetten (Analyse durch Synthese), ersetzt die Wolkenscheiben ueber der Traufe
                fl_rc_ = lauf(B, "bauplan_dachflaeche_foto", [PY, "-u", "-W", "ignore", "-I", "tools/dachflaeche_aus_umriss.py", ZR], log, ok=(0, 3, 4))[0] if os.path.exists(dp_) else 3; erg_["dachflaeche_foto_rc"] = fl_rc_
                t_ks = time.time(); rc_ = lauf(B, "bauplan_koerper_schleife", [PY, "-W", "ignore", "-I", "tools/koerper_schleife.py", ZR, W, "--bild", os.path.join(Z, "audit", "wolke_rest.jpg")] + (["--erst_bauen"] if dach_neu_ else []), log, ok=(0, 3))[0]
                try: k_ = json.load(open(ks_)) if rc_ in (0, 3) and beleg(B, "bauplan_koerper_schleife", [ks_], t_ks, folge="Wolkenkoerper/Abgleich eines frueheren Laufs NICHT verwendet") else {}      # 23.11.2026 AUDIT: Altstand stoesst sonst Bau/Abgleich an
                except Exception: k_ = {}
                erg_.update({n_: k_.get(n_) for n_ in ("wolke_am_modell_vorher", "wolke_am_modell_nachher")}, wolkenkoerper=dict(angenommen=[x_["id"] for x_ in k_.get("angenommen", [])], verworfen=[x_["id"] for x_ in k_.get("verworfen", [])], gemeldet=[f"{x_['id']} {x_['form']}" for x_ in k_.get("gemeldet", [])]))
                # 21.11.2026 (KERNMETHODE, Nutzer: "Form aus Fotos, Wolke nur Lage"): runde Koerper aus den FOTO-UMRISSEN nachmessen (tools/rund_aus_umriss.py, Bildpyramide,
                # Beruehrlinien je Blickrichtung gewichtet) - ersetzt Wolkenradius/-profil (Schwabentor Treppenturm: Wolke r 1,73, Foto 1,585, Handstand 1,555; Traufe 11,25 / 11,57).
                # 24.11.2026: Kranz-/Traufhoehe aus den triangulierten Fotokanten (KD/sweep.npz) bzw. der Wolken-Flaechenmitte statt Silhouette (Auskragungs-Falle L31, 1122 Rundturm)
                rr_ = lauf(B, "bauplan_rund_umriss", [PY, "-u", "-W", "ignore", "-I", "tools/rund_aus_umriss.py", ZR, "--uebernehmen"] + (["--kanten", os.path.join(KD, "sweep.npz")] if os.path.exists(os.path.join(KD, "sweep.npz")) else [])
                           + (["--wolke", W] if os.path.exists(W) else []), log, ok=(0, 3, 4))[0]
                erg_["rund_umriss_rc"] = rr_
                # 23.11.2026 (Kette 1122s: Treppentuermchen hoher Zylinder ohne Dach - Umriss-Stuetze lief bis zum Suchende 13,75, Traufe/Dach nie gefunden): Schaft und DACH
                # als Drehkoerper aus EINSEITIGEN Silhouetten gegen Himmel (tools/rund_aus_huelle.py, Bausteine tools/drehkoerper_aus_fotos.py wie die Laternenhaube)
                rh_ = lauf(B, "bauplan_rund_huelle", [PY, "-u", "-W", "ignore", "-I", "tools/rund_aus_huelle.py", ZR, "--uebernehmen", "--bild", os.path.join(Z, "audit", "rund_huelle.jpg")], log, ok=(0, 3, 4))[0] if rr_ in (0, 4) else 3
                erg_["rund_huelle_rc"] = rh_
                if k_.get("baulaeufe") or rr_ == 0 or rh_ == 0 or sp_rc_ == 0 or tr_rc_ == 0 or fl_rc_ == 0: bauen(B, "bauen_mit_wolkenkoerpern", a.ziel, log)
                if isinstance(erg_.get("wolke_am_modell_vorher"), int) and isinstance(erg_.get("wolke_am_modell_nachher"), int) and erg_["wolke_am_modell_nachher"] < erg_["wolke_am_modell_vorher"]:
                    notiz(B, "bauplan_wolkenkoerper", False, fehler=f"Wolkenkoerper/Dachprofil verschlechtern den Abgleich ({erg_['wolke_am_modell_vorher']} -> {erg_['wolke_am_modell_nachher']} Wolkenpunkte am Modell) - audit/koerper_auto.json / dach_profil.json pruefen ('angenommen': false setzt sie ausser Kraft)")
            if os.path.exists(os.path.join(eb_, "ebenen.json")): lauf(B, "bauplan_abweichung", [PY, "-W", "ignore", "-I", "tools/ebenen_abweichung.py", ZR, eb_] + (["--wolke", W] if os.path.exists(W) else []), log)      # Schritt 3: Abweichung Modell gegen Bauplan je Ebene (audit/ebenen_abweichung.json, abweichung_<ebene>.jpg)
            # 24.11.2026 (Hoehensitz-Befund 1122): HOEHEN-ANGLEICH waagerechter Bauteile - jede waagerechte Strukturlinie des GEBAUTEN Modells gegen Wolken-Linien UND
            # triangulierte Fotokanten (Kantenstufe sweep.npz); angeglichen nur, wenn beide Quellen einig sind (tools/hoehen_angleich.py -> audit/hoehen_angleich.json,
            # Generator bauteile.hoehen_aus_json als letzter Bauschritt). rc 0 = Korrektur angenommen -> Neubau; 2 = keine; 3 = keine Kantenpunkte (nur Bericht).
            if os.path.exists(os.path.join(KD, "sweep.npz")):
                rc_ha = lauf(B, "bauplan_hoehen", [PY, "-W", "ignore", "-I", "tools/hoehen_angleich.py", ZR, "--kanten", os.path.join(KD, "sweep.npz"), "--bild", os.path.join(Z, "audit", "hoehen_angleich.jpg")], log, ok=(0, 2, 3))[0]
                erg_["hoehen_angleich_rc"] = rc_ha
                if rc_ha == 0: bauen(B, "bauen_mit_hoehen", a.ziel, log)
            notiz(B, "bauplan", True, **erg_, hinweis="ANSEHEN: audit/innenwaende_auto.jpg (Tiefe je Fassade), audit/oeffnungen_innen.jpg, audit/rueckwand_auto.json; Generator-Belege 'Rueckwand' / 'Innenwand'")
    # --- Ende Stufe 'bauplan' ---
    abnahme_nachholen(B, a.ziel, log)                                    # 21.11.2026: volle Abnahme auf dem Endstand der Zwischenbauten (bauen)
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
                t_sw = time.time(); rc_sw = lauf(B, f"vorbauten_f{i_:02d}", [PY, "-W", "ignore", "-I", "tools/fassade_tiefe.py", ZR, fo, str(i_)], log, ok=(0, 2, 4))[0]
                sweep_altstand(B, f"vorbauten_f{i_:02d}", fo, i_, t_sw)
                if rc_sw == 0:
                    vj = os.path.join(fo, f"vorbauten_f{i_:02d}.json"); vb[f"f{i_:02d}"] = len(json.load(open(vj))["kandidaten"]) if os.path.exists(vj) else 0
            notiz(B, "vorbauten", True, kandidaten=vb, hinweis="Vorschlaege mit eigener Messebene (vorbauten_fNN.json, Bild tiefe_fNN.jpg ansehen); noch kein automatischer Bau")
            t_sl = time.time(); rc, out = lauf(B, "seiten_luecken", [PY, "-I", "tools/seiten_luecken.py", ZR, fo, "--sparse", sp, "--ref-db", db] + ([] if TEILLAUF else ["--download", "--holen"]), log, ok=(0, 3))   # rc 3 = Wand ohne Foto: freie Quellen laden (Commons, Hochblicke, Openverse), Kandidaten nachregistrieren; im Teillauf nur der Bericht
            sl = os.path.join(Z, "audit", "seiten_luecken.json"); S_sl = json.load(open(sl)) if frisch(sl, t_sl) else None; ung = S_sl.get("ungesehen", []) if S_sl else ["?"]
            teil = (S_sl or {}).get("teilweise") or []      # 24.11.2026 (1122x: Ostwand f02 239 m2 ohne Bilddaten, 'keine Wand ganz ungesehen' -> nichts geschah): teilweise ungesehen ueber der Schwelle speist das Nachholen/Wiederholen mit      # 17.11.2026: nach einem Absturz von seiten_luecken galt der Bericht eines frueheren Laufs (oder 'keine Luecke', wenn es keinen gab)
            if ung == ["?"]: notiz(B, "seiten_bericht", False, fehler=f"{sl} wurde nicht neu geschrieben (seiten_luecken rc {rc}) - Luecken UNBEKANNT")
            # 23.11.2026 KETTENLUECKE (Lauf 1122q: 327 nachgeholte Kameras, aber Wandbild/Bau liefen VORHER - nichts davon kam ins Modell): neue BELEGTE Kameras auf einer
            # ungesehenen Wand + messbar mehr Abdeckung -> EINMAL Wandbild/Bauplan/Bau/Tore/seiten-Bericht im selben Lauf wiederholen (tools/seiten_wiederholung.py)
            wiederholt = bool(((ung and ung != ["?"]) or teil) and not TEILLAUF and seiten_wiederholen(B, a, ZR, Z, D, fo, sl, t_sl, log, bp))      # True: der Teillauf schrieb Fotoauftrag + 'seiten' mit dem neuen Stand
            wj = os.path.join(Z, "fotowuensche.json")
            if not wiederholt: lauf(B, "foto_auftrag", [PY, "-W", "ignore", "-I", "tools/foto_auftrag.py", ZR, fo, os.path.join(D, f"fotoauftrag_{a.ziel}.html")] + (["--wunsch", wj] if os.path.exists(wj) else []) + (["--seiten-modelle", os.path.join(P, "sfm", "seiten_modelle.json")] if os.path.isfile(os.path.join(P, "sfm", "seiten_modelle.json")) else []), log)   # 16.11.2026: dem Nutzer zeigen, welche Fotos fehlen (Lageplan, Standorte, markierte Ziele)
            if not wiederholt: notiz(B, "seiten", not ung, ungesehen=ung, teilweise=teil, hinweis=("" if not teil else f"teilweise ungesehen {teil}: Nachholen je Kandidat nur einmal (seiten_nachholen/versucht_kandidaten.json); ohne Gewinn bleibt der Fotoauftrag. ") if not ung else "Nachholen brachte keine belegte Kamera / keinen messbaren Abdeckungsgewinn (Schritt 'seiten_wiederholung'), oder Teillauf-Bericht; bleibt die Wand leer: Kontaktbogen audit/seiten_luecken_kandidaten.jpg ansehen, Kamera aus Modellpunkten + tools/fassade_ein_foto.py (PIPELINE_FASSADEN.md 'Ungesehene Seite')")
        else: notiz(B, "seiten", False, fehler="kein fassaden.json (Stufe fenster) oder kein SfM-Netz/Datenbank")
    # 21.11.2026 SACKGASSEN-TOR (Nutzer: "Warum wurde das nicht bemerkt? ... die fliessen nicht in die Kette ein"): der Ebenen-Sweep schrieb vier Tage lang Vorbau-'Vorschlaege',
    # die kein Generator las, und die Stufe stand als 'in Ordnung' im Bericht. Hier je Kettenergebnis: liegt die Datei vor und hat Inhalt, MUSS der Generator (oder das von ihm
    # gerufene Werkzeug) sie verbauen - sonst 'ok: False' mit Namen. Liste der bekannten offenen Uebergaenge: modelle/KETTE_LUECKEN_2026-11-20.md.
    if os.path.exists(gp_) and (dran("bauplan") or dran("fassaden") or dran("seiten")) and not TEILLAUF:      # Teillauf: der aeussere Lauf prueft auf dem Endstand
        gtxt = open(gp_).read(); fk_txt = open(os.path.join(ROOT, "tools", "fassaden_kette.py")).read(); sg_ = []
        def hat(f_, schl_=None):
            if not os.path.exists(f_): return False
            try: j_ = json.load(open(f_)); return bool(j_.get(schl_)) if schl_ else bool(j_)
            except Exception: return os.path.getsize(f_) > 0
        if hat(os.path.join(Z, "audit", "vorbauten_auto.json"), "fassaden") and "vorbauten_aus_json" not in gtxt: sg_.append("audit/vorbauten_auto.json (Vorbauten) - Generator ruft bauteile.vorbauten_aus_json nicht")
        if glob.glob(os.path.join(Z, "relief", "*_mono.npz")) and not ("anbauen" in gtxt and "_mono.npz" in fk_txt): sg_.append("relief/*_mono.npz (Feinrelief) - fassaden_kette.anbauen baut es nicht ein")
        if hat(os.path.join(Z, "audit", "oeffnungen_auto.json")) and "oeffnungen_aus_json" not in gtxt: sg_.append("audit/oeffnungen_auto.json (Boegen/Durchfahrten) - Generator ruft oeffnungen_aus_json nicht")
        if hat(os.path.join(Z, "audit", "uhren_auto.json")) and any(v.get("uhren") for v in json.load(open(os.path.join(Z, "audit", "uhren_auto.json"))).values()) and "uhren_aus_json" not in gtxt: sg_.append("audit/uhren_auto.json (Uhren) - Generator ruft bauteile.uhren_aus_json nicht")
        if hat(os.path.join(Z, "audit", "umgang_auto.json")) and json.load(open(os.path.join(Z, "audit", "umgang_auto.json"))).get("gefunden") and "umgang_aus_json" not in gtxt: sg_.append("audit/umgang_auto.json (Umgang) - Generator ruft bauteile.umgang_aus_json nicht")
        if hat(os.path.join(Z, "audit", "fenster_auto.json")) and "fenster_aus_json" not in gtxt: sg_.append("audit/fenster_auto.json (Fenster) - Generator ruft fenster_aus_json nicht")
        fv_ = glob.glob(os.path.join(D, "fassade", "vorbauten_f*.json"))
        if any(json.load(open(f_)).get("kandidaten") for f_ in fv_) and not os.path.exists(os.path.join(Z, "audit", "vorbauten_auto.json")): sg_.append("fassade/vorbauten_fNN.json mit Kandidaten, aber keine Bauliste (tools/vorbauten_bauplan.py lief nicht)")
        if os.path.exists(os.path.join(Z, "referenz_hand.json")):
            t_hv = time.time(); lauf(B, "hand_vergleich", ["python3", "tools/hand_vergleich.py", ZR], log)
            beleg(B, "hand_vergleich", [os.path.join(Z, "audit", "hand_vergleich.json")], t_hv, altstand_beiseite=True, folge="Altstand beiseite - befundliste/Agenten-Schleife vergleichen NICHT mit dem Handstand-Vergleich eines frueheren Laufs")   # 24.11.2026 AUDIT      # 21.11.2026: Kettenergebnis gegen den frueheren Handstand (audit/hand_vergleich.json)
        notiz(B, "sackgassen", not sg_, offen=sg_, hinweis="Kettenergebnisse ohne Verbraucher im Generator; bekannte, noch nicht verbaute Uebergaenge: modelle/KETTE_LUECKEN_2026-11-20.md")
    W_ANZ = os.path.join(D, "wolke_anzeige", os.path.basename(W))                         # 24.11.2026: Anzeige-Kopie ohne Draehte/Fahnen (tools/wolke_draehte.py)
    if dran("draehte") and os.path.exists(W):
        t_dr = time.time(); wf_ = W.replace("punkte_modell_", "punkte_farben_"); os.makedirs(os.path.join(Z, "audit"), exist_ok=True); os.makedirs(os.path.dirname(W_ANZ), exist_ok=True)
        sp_ = os.path.join(P, "sfm", "sparse", "0"); si_ = os.path.join(os.path.dirname(W_ANZ), "sicht.npz")      # Freiraum-Test: SfM-Beobachtungen durchleuchten Fahnen vor der Wand
        if os.path.exists(si_): os.remove(si_)
        if os.path.isdir(sp_) and os.path.exists(AU): lauf(B, "draehte_sicht", [PYC, "-I", "tools/wolke_draehte.py", si_, "--sicht_export", sp_, AU], log, ok=(0, 5))   # 5 = anderes SfM-Modell
        lauf(B, "draehte", [PY, "-I", "tools/wolke_draehte.py", W, "--aus", os.path.dirname(W_ANZ), "--bericht", os.path.join(Z, "audit", "wolke_draehte.json"),
                            "--bild", os.path.join(Z, "audit", "wolke_draehte.jpg")] + (["--farben", wf_] if os.path.exists(wf_) else []) + (["--sicht", si_] if os.path.exists(si_) else []), log)
        beleg(B, "draehte", [os.path.join(Z, "audit", "wolke_draehte.json"), W_ANZ], t_dr, folge="html zeigt die ungefilterte Wolke (Draehte/Oberleitung sichtbar)")
    if not (os.path.exists(W_ANZ) and os.path.exists(W) and os.path.getmtime(W_ANZ) >= os.path.getmtime(W)): W_ANZ = W   # Kopie fehlt/veraltet -> Original zeigen
    if dran("html"):
        args = [PY, "-I", "tools/modell_3d_html.py", ZR, os.path.join(D, f"{a.ziel}_3d.html")]
        if os.path.exists(W_ANZ): args += ["--wolke", W_ANZ] + (["--farben", W_ANZ.replace("punkte_modell_", "punkte_farben_")] if os.path.exists(W_ANZ.replace("punkte_modell_", "punkte_farben_")) else [])
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
    abnahme_nachholen(B, a.ziel, log)
    # 22.11.2026 DETAILANSICHT JE BAUTEIL (0_DURCHBRUCH_AGENTEN_SCHLEIFE.md "Ein Nebenbild reicht nicht"): am festen Nebenbild (Steilblick 113231) wirkten Vordach und
    # Laterne flach/fehlend, das STL hatte beides. Je Bauteil (audit/*_auto.json, vordach_profil, dach_profil laterne/spitze) beste SfM-Kamera -> audit/neben_detail_<bauteil>.jpg
    # + Raster audit/neben_details.jpg. Bericht, kein Tor (rc 3 = kein Bauteil/keine Kamera). CPU-Render, kein GPU-Bedarf.
    if os.path.isdir(os.path.join(Z, "audit")) and os.path.exists(os.path.join(ROOT, json.load(open(ZJ)).get("stl") or "-")) and not TEILLAUF:
        t_nd = time.time(); rc_d, _ = lauf(B, "neben_details", [PY, "-W", "ignore", "-I", "tools/neben_details.py", ZR, "--daten", D], log, ok=(0, 3))
        try:
            if not KB_frisch(os.path.join(Z, "audit", "neben_details.json"), t_nd): raise FileNotFoundError("nicht in diesem Lauf geschrieben (Stand eines frueheren Laufs)")      # 23.11.2026 AUDIT
            nd_ = json.load(open(os.path.join(Z, "audit", "neben_details.json")))
            notiz(B, "neben_details_ergebnis", rc_d == 0, bauteile=len(nd_.get("bauteile") or []), bilder=sum(1 for b_ in nd_.get("bauteile") or [] if b_.get("bild")),
                  ohne_kamera=[b_["name"] for b_ in nd_.get("bauteile") or [] if not b_.get("bild")],
                  schwach=[b_["name"] for b_ in nd_.get("bauteile") or [] if any(v_.get("schwach") for v_ in b_.get("ansichten") or [])], hinweis="ANSEHEN: audit/neben_details.jpg - Befund je Bauteil erst an der Detailansicht bestaetigen")
        except Exception as e: notiz(B, "neben_details_ergebnis", False, fehler=f"audit/neben_details.json nicht lesbar (rc {rc_d}): {type(e).__name__} {e}"[:240])
    # 24.11.2026 MALPLAN (Nutzer 23.11.: "das Malen ist fuer mich das Kritischste", Doku/projekt/bahn-anlage.md Gestaltung/Malen): Farbzonen je Wand aus dem
    # 1-cm-Wandbild (fassade_fein, sonst fassade) -> audit/malplan.json + malplan_<wand>.jpg + malplan.md. NUR Ausgabe/Bericht, kein Tor, aendert nichts am Modell. CPU, Sekunden.
    _mp_ein = next((q_ for q_ in (os.path.join(D, "fassade_fein"), os.path.join(D, "fassade")) if glob.glob(os.path.join(q_, "ortho_f*.png"))), None)
    if _mp_ein and os.path.isdir(os.path.join(Z, "audit")) and not TEILLAUF:
        t_mp = time.time(); rc_mp, _ = lauf(B, "malplan", [PY, "-W", "ignore", "-I", "tools/malplan.py", _mp_ein, "--aus", os.path.join(Z, "audit"), "--objekt", a.ziel], log, ok=(0, 3))
        try:
            if not KB_frisch(os.path.join(Z, "audit", "malplan.json"), t_mp): raise FileNotFoundError("nicht in diesem Lauf geschrieben (Stand eines frueheren Laufs)")
            mp_ = json.load(open(os.path.join(Z, "audit", "malplan.json")))
            notiz(B, "malplan_ergebnis", rc_mp == 0, waende=len(mp_.get("waende") or []), zonen={w_["wand"]: [f"{z_['material']} {z_['hex']} {round(100 * z_['anteil'])}%" for z_ in w_["zonen"]] for w_ in mp_.get("waende") or []},
                  gebaeude={m_: f"{g_['hex']} -> {g_['mischung']['text']}" for m_, g_ in (mp_.get("gebaeude") or {}).items()}, hinweis="ANSEHEN: audit/malplan_<wand>.jpg; Anleitung audit/malplan.md (Material = Farbregel-ANNAHME)")
        except Exception as e: notiz(B, "malplan_ergebnis", False, fehler=f"audit/malplan.json nicht lesbar (rc {rc_mp}): {type(e).__name__} {e}"[:240])
    # 24.11.2026 KONVERGENZ (Nutzer: "Augenmass ist doof"): FESTER Fotosatz je Seite (audit/konvergenz_fotosatz.json, einmal gewaehlt) + feste Bauteil-Kameras
    # aus neben_details -> grobes F1 (foto_diff_batch auf das End-STL, Ausgabe <daten>/konvergenz/<lauf>) und feines F1 je Bauteil (teil_fotoform f1_fein) ->
    # Zeile audit/konvergenz.jsonl + audit/konvergenz.png; Status je Seite steigt / PLATEAU (Methode erschoepft, mit Restfehler-Ort) / kein Beleg. Bericht, kein Tor.
    if os.path.isdir(os.path.join(Z, "audit")) and not TEILLAUF:
        try:
            t_kv = time.time(); lid_ = os.environ.get("RCPARK_JOB") or time.strftime("lauf_%Y%m%d_%H%M")
            rc_kv, _ = lauf(B, "konvergenz", [PY, "-W", "ignore", "-I", "tools/konvergenz.py", ZR, "--lauf", lid_, "--daten", D], log, ok=(0, 3), timeout=3600)
            zl_ = open(os.path.join(Z, "audit", "konvergenz.jsonl")).read().splitlines()[-1] if KB_frisch(os.path.join(Z, "audit", "konvergenz.jsonl"), t_kv) else None
            if zl_ is None: raise FileNotFoundError("audit/konvergenz.jsonl nicht in diesem Lauf geschrieben")
            kv_ = json.loads(zl_)
            notiz(B, "konvergenz_ergebnis", True, lauf=lid_, seiten={e_["name"]: f"grob {e_.get('f1')} fein {e_.get('f1_fein')} -> {e_.get('status')}"
                                                                     + (f"; Wolke {e_.get('f1_wolke')} vs Modell {e_.get('f1_modell_gleich')} verlust {e_.get('verlust')} -> {e_['status_wolke']}" if e_.get("status_wolke") else "")
                                                                     for e_ in kv_["seiten"].values()},
                  hinweis="ANSEHEN: audit/konvergenz.png; PLATEAU = Methode erschoepft -> restfehler in audit/konvergenz.jsonl zeigt, wo neu ansetzen; "
                          "status_wolke: 'Modellierung verliert' = Wolke traegt mehr als das Modell (Modellstufe verbessern), 'Daten fehlen' = Fotos/SfM nachholen")
        except Exception as e: notiz(B, "konvergenz_ergebnis", True, hinweis=f"Konvergenzmessung ohne Ergebnis (kein Kettenfehler): {type(e).__name__} {e}"[:240])
    # 24.11.2026 LAUFZEIT-BERICHT (modelle/ERKENNTNISSE.md 24.11.: Doppel-Fusion 470 + 450 s, 6 volle Bauten 38 min blieben unbemerkt): Laufzeit je Stufenfamilie
    # aus gesamtkette.log ab diesem Lauf, Vorlauf = frueherer Abschnitt derselben Datei, Fusionen der SfM-Stufe aus pipe/pipeline.log -> audit/laufzeit.json. Bericht, kein Tor.
    if os.path.isdir(os.path.join(Z, "audit")) and not TEILLAUF:
        try:
            _lz = [PY, "-I", "tools/laufzeit_bericht.py", log, "--aus", os.path.join(Z, "audit", "laufzeit.json"), "--ab-zeile", str(log_ab)]
            if os.environ.get("RCPARK_JOB"): _lz += ["--unterlog", os.path.join(D, "pipe", "pipeline.log"), "--job", os.environ["RCPARK_JOB"]]
            lauf(B, "laufzeit", _lz, log, ok=(0,), timeout=300)
            _lzj = json.load(open(os.path.join(Z, "audit", "laufzeit.json")))
            notiz(B, "laufzeit_ergebnis", True, summe_min=_lzj.get("summe_min"), hinweise=(_lzj.get("hinweise") or [])[:8],
                  hinweis="DOPPELARBEIT/WIEDERHOLUNG/GEWACHSEN = Beschleunigungs-Befund fuer die Agenten-Schleife")
        except Exception as e: notiz(B, "laufzeit_ergebnis", True, hinweis=f"Laufzeit-Bericht ohne Ergebnis (kein Kettenfehler): {type(e).__name__} {e}"[:240])
    # 22.11.2026 BEFUNDLISTE (Agenten-Schleife automatisch, 0_DURCHBRUCH_AGENTEN_SCHLEIFE.md): nach allen Toren und der letzten Abnahme (neben_*.jpg sind frisch) die
    # sichtbaren Fehler maschinenlesbar -> audit/befunde.json + Ausschnitte audit/befunde/bNN.jpg (Foto | Modell). Bericht, kein Tor (ok auch mit Befunden).
    if os.path.isdir(os.path.join(Z, "audit")) and not TEILLAUF:
        t_bf = time.time(); rc_b, _ = lauf(B, "befundliste", [PY, "-W", "ignore", "-I", "tools/befundliste.py", ZR, "--daten", D, "--bericht", bp, "--ab-schritt", str(n_start), "--log", log, "--ab-zeile", str(log_ab)], log, ok=(0, 3))
        try:
            if not KB_frisch(os.path.join(Z, "audit", "befunde.json"), t_bf): raise FileNotFoundError("nicht in diesem Lauf geschrieben - die Agenten-Schleife wuerde Befunde eines frueheren Laufs abarbeiten")      # 23.11.2026 AUDIT
            bf_ = json.load(open(os.path.join(Z, "audit", "befunde.json"))); top_ = [b_ for b_ in bf_["befunde"] if b_["stufe"] == "FEHLER"][:5]
            notiz(B, "befundliste_ergebnis", True, zusammenfassung=bf_.get("zusammenfassung"), ohne_fotos=bf_.get("ohne_fotos"),
                  oben=[f"{b_['id']} {b_['art']} {(b_.get('ort') or {}).get('fassade') or ''} {(b_.get('ort') or {}).get('bauteil') or ''} -> {(b_.get('vorschlag') or {}).get('werkzeug', '')[:60]}" for b_ in top_],
                  hinweis="ANSEHEN: audit/befunde/bNN.jpg; je Befund ein Agent (Skill kette-schleife)")
        except Exception as e: notiz(B, "befundliste_ergebnis", False, fehler=f"audit/befunde.json nicht lesbar (befundliste rc {rc_b}): {type(e).__name__} {e}"[:240])
    if not TEILLAUF: foto_auftrag_skizze(B, "ende", ZR, Z, P, W, AU, FV, log)               # 22.11.2026: Fotoauftrag mit dem Stand am Laufende
    return abschluss()


if __name__ == "__main__":
    sys.exit(main())
