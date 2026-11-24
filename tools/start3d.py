#!/usr/bin/env python3
"""start3d.py - Fragen + Start + Fortschritt fuer EIN Objekt; wird von ../0-3d-modell.sh aufgerufen (Nutzer 19.11.2026: "ein Startskript,
mach vom Martinstor in Freiburg ein 3D-Modell, fragt mich interaktiv, erst grob, nachts fein").

  0-3d-modell.sh Martinstor Freiburg [--ja] [--trocken]     neu oder wieder aufnehmen
  0-3d-modell.sh --status                                    alle Laeufe
  (intern) start3d.py --nacht <ziel>                       vom einmaligen systemd-Zeitgeber aufgerufen: wartet, bis der Kettenlauf
                                                          fertig ist, und startet die Feinstufe nur, wenn die Lage-Tore bestanden sind.
Rechnen tut tools/gesamtkette.py (alle Stufen + Tore), gestartet ueber tools/job_start.sh (systemd-Dienst rcpark-<job>, RAM-/GPU-Buchung).
Zustand je Objekt: /media/oem/scan/rc-park_daten/start3d-zustand/<kurzname>.json (welcher Lauf, welche Stufe, Feinstufe geplant?).
Die Feinstufe ist ein EINMALIGER Zeitgeber (systemd-run --on-calendar), kein wiederkehrender Plan.
"""
import sys, os, re, json, glob, time, subprocess, argparse, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATEN = "/media/oem/scan/rc-park_daten"; ZU = os.path.join(DATEN, "start3d-zustand"); LOGS = os.path.join(DATEN, "job_logs")
PY = "/media/oem/scan/venv-seg/bin/python"
JA = False


# ---------- Anzeige: Farbe, Balken, Speicher, Ablageorte (Nutzer 19.11.: "richtig geschwaetzig, viel Farbe und Grafik, Speicher, wo es auf der SSD liegt") ----------
FARBE = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
def f(t, c):
    cod = dict(rot="31", gruen="32", gelb="33", blau="34", lila="35", tuerkis="36", grau="90", fett="1")
    return f"\033[{';'.join(cod[x] for x in c.split())}m{t}\033[0m" if FARBE else str(t)


def balken(anteil, breite=28):
    anteil = max(0.0, min(1.0, anteil)); n = int(round(anteil * breite)); c = "gruen" if anteil < 0.7 else "gelb" if anteil < 0.9 else "rot"
    return f("█" * n, c) + f("░" * (breite - n), "grau") + f" {anteil * 100:5.1f} %"


def gb(b): return f"{b / 1024 ** 3:6.1f} GB" if b >= 1024 ** 3 * 0.95 else f"{b / 1024 ** 2:6.0f} MB" if b >= 1024 ** 2 else f"{b / 1024:6.0f} kB"


def ram():
    m = {l.split(":")[0]: int(l.split()[1]) * 1024 for l in open("/proc/meminfo")}; return m["MemTotal"] - m["MemAvailable"], m["MemTotal"], m.get("SwapTotal", 0) - m.get("SwapFree", 0)


def vram():
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10).stdout.split(",")
        return int(o[0]) * 1024 ** 2, int(o[1]) * 1024 ** 2, int(o[2]), int(o[3])
    except Exception: return None


def job_speicher(job):
    try:
        v = subprocess.run(["systemctl", "--user", "show", "-p", "MemoryCurrent", "--value", f"rcpark-{job}"], capture_output=True, text=True).stdout.strip()
        return int(v) if v.isdigit() else None
    except Exception: return None


def ordner_groesse(p, sek=20):
    try:
        o = subprocess.run(["du", "-sbL", p], capture_output=True, text=True, timeout=sek).stdout.split()
        return int(o[0]) if o else 0
    except Exception: return None


def kasten(titel):
    print(f("\n╔═ " + titel + " " + "═" * max(2, 70 - len(titel)), "tuerkis fett"))


def speicher_zeigen(job=None):
    kasten("Speicher und Rechner")
    u, t, sw = ram(); print(f"  RAM       {balken(u / t)}  {gb(u)} von {gb(t)}" + (f"   Auslagerung {gb(sw)}" if sw > 2 ** 28 else ""))
    v = vram()
    if v: print(f"  GPU-VRAM  {balken(v[0] / v[1])}  {gb(v[0])} von {gb(v[1])}   Last {v[2]:3d} %   {v[3]} Grad")
    du = __import__("shutil").disk_usage("/media/oem/scan"); print(f"  SSD       {balken(du.used / du.total)}  {gb(du.free)} frei von {gb(du.total)}  (/media/oem/scan)")
    if du.free < 20 * 1024 ** 3: print(f("  ACHTUNG: unter 20 GB frei - eine dichte Wolke braucht 10-40 GB", "rot fett"))
    l1, l5, _ = os.getloadavg(); print(f"  CPU-Last  {balken(l1 / os.cpu_count())}  {l1:.1f} auf {os.cpu_count()} Kernen")
    if job:
        js = job_speicher(job)
        if js: print(f"  dieser Job belegt {gb(js).strip()} RAM")


def ablage_zeigen(z, groesse=True):
    kasten("Wo alles liegt")
    orte = [("Rechendaten (SfM, Wolke, Fotos)", os.path.join(DATEN, z["ziel"])), ("Modell + Pruefbilder", os.path.join(ROOT, "modelle", z["ziel"])),
            ("Pruefbilder (audit)", os.path.join(ROOT, "modelle", z["ziel"], "audit")), ("3D-Seite", os.path.join(DATEN, z["ziel"], f"{z['ziel']}_3d.html")),
            ("Log des Laufs", z["log"]), ("Bericht", os.path.join(DATEN, z["ziel"], "gesamtkette_bericht.json"))]
    for t, p in orte:
        da = os.path.exists(p); g = ordner_groesse(p) if (groesse and da and os.path.isdir(p)) else (os.path.getsize(p) if da and os.path.isfile(p) else None)
        print(f"  {f('●', 'gruen') if da else f('○', 'grau')} {t:<32} {p}" + (f("  " + gb(g).strip(), "gelb") if g else ""))


def frage(text, vorschlag="", wahl=None):
    """Frage mit Vorschlag in [ ]; Enter = Vorschlag. wahl = erlaubte Antworten (Kleinbuchstaben)."""
    while True:
        if JA: print(f"{text} [{vorschlag}] -> {vorschlag}"); return vorschlag
        try: a = input(f"{text} [{vorschlag}] ").strip()
        except EOFError: a = ""
        a = a or vorschlag
        if not wahl or a.lower() in wahl: return a
        print(f"  bitte eines von: {', '.join(wahl)}")


def ja(text, vorschlag="j"): return frage(text + " (j/n)", vorschlag, ["j", "n", "ja", "nein"]).lower().startswith("j")


def kurz(t):
    t = unicodedata.normalize("NFKD", t.replace("ß", "ss")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def job_aktiv(job): return subprocess.call(["systemctl", "--user", "is-active", "--quiet", f"rcpark-{job}"]) == 0


def bericht(ziel):
    p = os.path.join(DATEN, ziel, "gesamtkette_bericht.json")
    try: return json.load(open(p))
    except Exception: return None


def letzter_lauf(B):
    s = B.get("schritte", []); i = max([k for k, x in enumerate(s) if x.get("stufe") == "LAUF_START"] or [0]); return s[i:]


STUFEN = ["anlegen", "commons", "video", "vorpruefen", "sammeln", "sfm", "tore", "dach", "bauen", "kanten", "fototor", "fassaden", "fenster", "bauplan", "seiten", "draehte", "html", "vergleich", "druck"]
ERKL = dict(anlegen="Gebaeude im amtlichen 3D-Modell (LoD2) suchen, Rahmen anlegen", commons="freie Netzfotos holen (Commons, Openverse)",
            video="YouTube-Clips suchen, Bilder herausziehen", vorpruefen="Fremdbilder aussortieren (zeigt das Bild wirklich das Gebaeude?)",
            sammeln="alle Bilder zusammenlegen, Dubletten weg", sfm="Kameras berechnen (SfM) + dichte Punktwolke", tore="Lage-Pruefungen (GPS, Grundriss, Kameras)",
            dach="Dach aus Hoehenmodell vermessen", bauen="Grundmodell bauen + Abnahme", kanten="Fotokanten in 3D (Kernmethode)", fototor="Modell gegen Fotos pruefen",
            fassaden="Wandbilder entzerren, Relief", fenster="Fenster/Oeffnungen aus Wandbildern", bauplan="Bauplan je Wand", seiten="ungesehene Seiten suchen",
            draehte="Draehte/Oberleitung aus der Anzeige-Wolke nehmen", html="3D-Seite erzeugen", vergleich="Vergleich mit Referenz", druck="in Druckteile aufteilen")


def hauptstufe(name):
    return next((x for x in STUFEN if name == x or name.startswith(x + "_") or name.startswith("tor_") and x == "tore"), None)


def zeige_schritte(B, schon=0, alle=False):
    """druckt Schritte des letzten Laufs ab Nummer 'schon' (farbig); gibt die neue Anzahl zurueck."""
    s = letzter_lauf(B) if B else []
    for x in s[schon:]:
        if x.get("stufe") == "LAUF_START": continue
        ok = x.get("ok"); sym = f("✔", "gruen") if ok else f("✘", "rot fett"); sek = x.get("sekunden")
        e = x.get("ende"); txt = x.get("fehler") or (e[-1] if isinstance(e, list) and e else e) or ""
        dauer = "" if sek is None else (f"{sek // 60:d} min" if isinstance(sek, int) and sek >= 120 else f"{sek} s")
        print(f"  {sym} {f(x.get('stufe', '?'), 'fett'):<34} {f(dauer, 'grau'):>18}  {f(str(txt)[:100], 'grau' if ok else 'rot')}")
    return len(s)


def fortschritt(B):
    """welche Hauptstufe gerade dran ist -> (index, name)."""
    s = letzter_lauf(B) if B else []; i = 0
    for x in s:
        h = hauptstufe(str(x.get("stufe", "")))
        if h: i = max(i, STUFEN.index(h))
    return i


def tafel(z, B, t0):
    """ganze Anzeige neu zeichnen."""
    if FARBE: print("\033[H\033[2J", end="")
    print(f(f"  3D-MODELL: {z['name']} ({z.get('ort') or '-'})   Lauf {z['ziel']}   Stufe {z['stufe']}", "lila fett"))
    lauf = job_aktiv(z["job"]); dauer = (time.time() - t0) / 60
    print(f"  {f('● RECHNET', 'gruen fett') if lauf else f('■ STEHT', 'gelb fett')}   seit {z.get('start')}   Anzeige {dauer:.0f} min   {time.strftime('%H:%M:%S')}")
    i = fortschritt(B); bis = STUFEN.index(z.get("bis", "html")) if z.get("bis", "html") in STUFEN else len(STUFEN) - 1
    kasten("Kette")
    for k_, st in enumerate(STUFEN[:bis + 1]):
        mark = f("✔", "gruen") if k_ < i else (f("▶", "gelb fett") if k_ == i and lauf else f("·", "grau"))
        print(f"  {mark} {st:<11} {f(ERKL.get(st, ''), 'fett' if k_ == i else 'grau')}")
    print(f"  {balken(i / max(1, bis))}  Stufe {i + 1} von {bis + 1}")
    kasten("Letzte Schritte")
    s = letzter_lauf(B) if B else []; zeige_schritte({"schritte": s[-10:]} if s else None)
    try:
        zeile = [l for l in open(z["log"], errors="replace").read()[-3000:].splitlines() if l.strip()][-1]
        print(f("  Log: " + zeile[:150], "grau"))
    except Exception: pass
    speicher_zeigen(z["job"])
    print(f("\n  Strg-C trennt nur die Anzeige, der Job rechnet weiter.   Wieder ansehen: ./0-3d-modell.sh " + z["eingabe"], "grau"))


def objekte_mit_name(name):
    """vorhandene modelle/<x>/objekt.json, deren name zum gesuchten passt (erstes Wort gleich)."""
    erg = []
    for p in sorted(glob.glob(os.path.join(ROOT, "modelle", "*", "objekt.json"))):
        try: o = json.load(open(p))
        except Exception: continue
        if kurz(o.get("name", "")).split("-")[:1] == kurz(name).split("-")[:1]:
            erg.append((os.path.basename(os.path.dirname(p)), o))
    return erg


def zustand_laden(k):
    p = os.path.join(ZU, k + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def zustand_schreiben(k, z):
    os.makedirs(ZU, exist_ok=True); z["geaendert"] = time.strftime("%Y-%m-%d %H:%M"); json.dump(z, open(os.path.join(ZU, k + ".json"), "w"), indent=1, ensure_ascii=False)


def kette_befehl(z, ab="anlegen", stufe=None):
    b = [PY, "-u", "-I", "tools/gesamtkette.py", z["quelle"], "--ziel", z["ziel"], "--ab", ab, "--dicht-stufe", stufe or z["stufe"]]
    if z.get("fotos"): b += ["--fotos", z["fotos"]]
    if not z.get("video", True): b += ["--ohne-video"]
    if not z.get("netz", True): b += ["--ohne-netz"]
    return b


def starten(job, log, befehl, trocken, umgebung=None):
    voll = ["bash", "tools/job_start.sh", job, log] + befehl
    print("Start: JOB_RAM_MB=11000 " + " ".join(voll))
    if trocken: print("  (--trocken: nicht gestartet)"); return 0
    env = dict(os.environ, JOB_RAM_MB="11000", **(umgebung or {})); return subprocess.call(voll, cwd=ROOT, env=env)


def verfolgen(z):
    t0 = time.time()
    try:
        while True:
            tafel(z, bericht(z["ziel"]), t0)
            ende = os.path.exists(z["log"]) and "JOB_ENDE" in open(z["log"], errors="replace").read()[-4000:]
            if ende and not job_aktiv(z["job"]): return True
            time.sleep(30)
    except KeyboardInterrupt:
        print(f(f"\nAnzeige getrennt - der Job rechnet weiter. Wieder ansehen: ./0-3d-modell.sh {z['eingabe']}", "gelb")); return False


def abschluss_zeigen(z):
    B = bericht(z["ziel"]) or {}; le = B.get("lauf_ergebnis") or {}
    kasten("Ergebnis")
    if le.get("abbruch"): print(f("  ✘ ABGEBROCHEN: " + le["abbruch"], "rot fett"))
    elif le: print(f("  ✔ Kette durchgelaufen", "gruen fett"))
    if le.get("fehlgeschlagen"): print(f("  fehlgeschlagene Stufen: " + ", ".join(le["fehlgeschlagen"]), "rot"))
    for w in (B.get("warnungen") or [])[-6:]: print(f("  ! " + str(w.get("text", w) if isinstance(w, dict) else w)[:140], "gelb"))
    au = os.path.join(ROOT, "modelle", z["ziel"], "audit"); neben = sorted(glob.glob(os.path.join(au, "neben_*.jpg")))
    if neben: print(f"  Modell neben Foto: {len(neben)} Bilder in {au}")
    ablage_zeigen(z); speicher_zeigen()
    return not le.get("abbruch") and not le.get("fehlgeschlagen")


def druck_anbieten(z, trocken):
    """Nutzer 19.11.: am Ende Option 'in 3D-Druckteile aufteilen' (Stufe druck der Gesamtkette: tools/bausatz.sh)."""
    if not ja("In 3D-Druckteile aufteilen (Bausatz: Koerper fuer MK4S, Detailplatten fuer Bambu)?", "n"): return
    z2 = dict(z, job=f"druck-{z['kurz']}", log=os.path.join(LOGS, f"druck-{z['kurz']}.log"), bis="druck")
    rc = starten(z2["job"], z2["log"], kette_befehl(z, ab="druck") + ["--bis", "druck"], trocken)
    if rc == 0 and not trocken and verfolgen(z2):
        print(f"  Teile: {ROOT}/modelle/stl/{z['ziel']}_teile   Platten: {ROOT}/modelle/stl/{z['ziel']}_farbteile")


def nacht_planen(z, uhr, trocken):
    """einmaliger systemd-Zeitgeber, der 'start3d.py --nacht <kurz>' startet."""
    heute = time.strftime("%Y-%m-%d"); zeit = f"{heute} {uhr}:00"
    if time.strftime("%H:%M") >= uhr: zeit = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400)) + f" {uhr}:00"
    print(f("  Die Feinstufe braucht UNGEFILTERTE Tiefenkarten: die Karten der schnellen Stufe werden dafuer geloescht und neu gerechnet (Platz/Zeit, kein Datenverlust - Wolke bleibt bis zum Ende).", "gelb"))
    if not ja("Einverstanden, dass die schnellen Tiefenkarten dafuer geloescht werden?", "j"): print("  Feinstufe nicht geplant."); return
    z["fein_karten_neu"] = True
    unit = f"plan-fein-{z['kurz']}"
    b = ["systemd-run", "--user", f"--unit={unit}", f"--on-calendar={zeit}", "--timer-property=AccuracySec=1min",
         f"--working-directory={ROOT}", PY, "-I", os.path.join(ROOT, "tools", "start3d.py"), "--nacht", z["kurz"]]
    print("Plan: " + " ".join(b))
    if trocken: return
    subprocess.call(["systemctl", "--user", "stop", unit + ".timer"], stderr=subprocess.DEVNULL)
    if subprocess.call(b) == 0:
        z["fein_geplant"] = zeit; zustand_schreiben(z["kurz"], z); print(f"Feinstufe geplant fuer {zeit} (einmalig). Abbestellen: systemctl --user stop {unit}.timer")


def nacht(k):
    """vom Zeitgeber: warten bis der Kettenlauf fertig ist, Tore pruefen, dann Feinstufe (geometrischer PatchMatch-Durchgang)."""
    z = zustand_laden(k)
    if not z: print(f"kein Zustand fuer {k}"); return 2
    while job_aktiv(z["job"]): print("Kettenlauf rechnet noch - warte 10 min", flush=True); time.sleep(600)
    B = bericht(z["ziel"]) or {}; le = B.get("lauf_ergebnis") or {}
    if le.get("abbruch"):
        z["fein"] = f"NICHT gestartet: Kettenlauf abgebrochen ({le['abbruch'][:120]})"; zustand_schreiben(k, z); print(z["fein"]); return 3
    job = f"fein-{k}"; log = os.path.join(LOGS, job + ".log")
    rc = starten(job, log, kette_befehl(z, ab="sfm", stufe="fein"), False, {"RCPARK_FEIN_KARTEN_NEU": "1"} if z.get("fein_karten_neu") else None)
    z.update(fein=f"gestartet {time.strftime('%Y-%m-%d %H:%M')} (rc {rc})", fein_job=job, fein_log=log); zustand_schreiben(k, z); return rc


def status():
    kasten("Alle Laeufe")
    for p in sorted(glob.glob(os.path.join(ZU, "*.json"))):
        z = json.load(open(p)); B = bericht(z["ziel"]) or {}; le = B.get("lauf_ergebnis") or {}
        lauf = f("● rechnet", "gruen fett") if job_aktiv(z["job"]) else (f("✘ abgebrochen: " + le["abbruch"][:70], "rot") if le.get("abbruch") else f("✔ fertig", "gruen") if le else "?")
        print(f"  {f(z['eingabe'], 'fett'):<30} Lauf {z['ziel']} ({z['stufe']})  {lauf}\n      Feinstufe: {z.get('fein') or z.get('fein_geplant') or 'nicht geplant'}   Daten: {os.path.join(DATEN, z['ziel'])}")
    speicher_zeigen(); return 0


def main():
    global JA
    ap = argparse.ArgumentParser(); ap.add_argument("worte", nargs="*"); ap.add_argument("--ja", action="store_true"); ap.add_argument("--trocken", action="store_true")
    ap.add_argument("--status", action="store_true"); ap.add_argument("--nacht", default="")
    a = ap.parse_args(); JA = a.ja
    if a.nacht: return nacht(a.nacht)
    if a.status: return status()
    worte = [w for w in a.worte if w.lower() not in ("in", "im", "am", "von")]
    if not worte: worte = frage("Welches Gebaeude, in welchem Ort? (z.B. Martinstor Freiburg)", "").split()
    if not worte: print("kein Gebaeude genannt"); return 2
    name = " ".join(worte[:-1]) if len(worte) > 1 else worte[0]; ort = worte[-1] if len(worte) > 1 else ""
    k = kurz(name); eingabe = " ".join(worte)
    print(f(f"Gebaeude: {name}   Ort: {ort or '(nicht genannt)'}", "lila fett")); speicher_zeigen()

    z = zustand_laden(k)
    if z:
        lauft = job_aktiv(z["job"])
        print(f"\nEs gibt schon einen Lauf: {z['ziel']} (Stufe {z['stufe']}, gestartet {z.get('start')}) - {'RECHNET GERADE' if lauft else 'fertig/beendet'}")
        B = bericht(z["ziel"])
        if B: zeige_schritte(B)
        w = frage("Was tun? w = weiter ansehen, f = Feinstufe heute Nacht planen, d = in Druckteile aufteilen, n = neuer Lauf, e = Ende", "w" if lauft else "f", ["w", "f", "d", "n", "e"]).lower()
        if w == "e": return 0
        if w == "d": druck_anbieten(dict(z, _jetzt=1), a.trocken) if not lauft else print("erst den laufenden Job abwarten"); return 0
        if w == "w":
            if lauft and not verfolgen(z): return 0
            ok = abschluss_zeigen(z)
            if ok and not z.get("fein_geplant") and ja("Feinstufe (mit geometrischer Pruefung) heute Nacht rechnen?"): nacht_planen(z, frage("Uhrzeit", "23:00"), a.trocken)
            if ok: druck_anbieten(z, a.trocken)
            return 0
        if w == "f":
            nacht_planen(z, frage("Uhrzeit", "23:00"), a.trocken); return 0
        if lauft: print("Der alte Lauf rechnet noch - erst abwarten oder stoppen: systemctl --user stop rcpark-" + z["job"]); return 1

    # --- neuer Lauf ---
    vorh = objekte_mit_name(name); quelle = ""; fotos = ""
    mit_lage = [(n, o) for n, o in vorh if isinstance(o.get("lod2"), dict) and o["lod2"].get("id") and "rahmen" in o]
    if mit_lage:
        best = max(mit_lage, key=lambda t: os.path.getmtime(os.path.join(ROOT, "modelle", t[0], "objekt.json")))[0]   # zuletzt bearbeitetes
        print(f"\nVorhandene Objekte mit diesem Namen und amtlicher Lage (LoD2): {', '.join(n for n, _ in mit_lage)}")
        quelle = frage("Lage/LoD2/Fotoordner uebernehmen von", best, [n for n, _ in mit_lage])
        fotos = dict(mit_lage)[quelle].get("fotos_dir_quelle") or dict(mit_lage)[quelle].get("fotos_dir", "")
    else:
        print("\nNoch kein Objekt mit diesem Namen. Die Kette sucht das Gebaeude im LoD2 per Name (Kacheln unter rc-park_daten/_geo).")
        geo = glob.glob(os.path.join(DATEN, "_geo", "**", "LoD2_*.gml"), recursive=True)
        if not any(name.split()[0].lower().encode() in open(g, "rb").read().lower() for g in geo):
            print(f"ACHTUNG: '{name.split()[0]}' steht in keiner vorhandenen LoD2-Kachel ({len(geo)} Kacheln). Fuer einen neuen Ort zuerst LoD2/DGM1/DOM1 des LGL holen.")
            if not ja("Trotzdem anlegen?", "n"): return 2
    fotos = frage("Ordner mit eigenen Fotos (leer = keine)", fotos)
    if fotos and not os.path.isdir(fotos if os.path.isabs(fotos) else os.path.join(ROOT, fotos)): print(f"  ACHTUNG: Ordner {fotos} gibt es nicht")
    netz = ja("Freie Netzfotos (Wikimedia Commons, Openverse) holen?")
    video = ja("YouTube-Clips suchen und Bilder daraus ziehen?")
    print("Stufen: grob = Vorschau (800 px, ca. 1/4 der Zeit), schnell = Standard (1600 px), fein = mit geometrischer Pruefung (deutlich laenger)")
    stufe = frage("Stufe fuer jetzt", "schnell", ["grob", "schnell", "fein"]).lower()
    fein = stufe != "fein" and ja("Danach automatisch die Feinstufe in der Nacht rechnen (nur wenn die Lage-Tore bestanden sind)?")
    uhr = frage("Uhrzeit fuer die Feinstufe", "23:00") if fein else ""

    ziel = f"{k}-{time.strftime('%m%d')}"; n = 1
    while os.path.exists(os.path.join(ROOT, "modelle", ziel)) or os.path.exists(os.path.join(DATEN, ziel)):
        n += 1; ziel = f"{k}-{time.strftime('%m%d')}-{n}"
    if not quelle:
        quelle = ziel; anl = ["python3", "-I", "tools/objekt_anlegen.py", ziel, "--name", name, "--ort", ort] + (["--fotos", fotos] if fotos else [])
        print("Anlegen: " + " ".join(anl))
        if not a.trocken and subprocess.call(anl, cwd=ROOT, stdout=subprocess.DEVNULL) != 0: print("objekt_anlegen.py fehlgeschlagen"); return 2
    job = f"kette-{ziel}"; log = os.path.join(LOGS, job + ".log")
    z = dict(eingabe=eingabe, name=name, ort=ort, kurz=k, ziel=ziel, quelle=quelle, fotos=fotos, netz=netz, video=video, stufe=stufe,
             job=job, log=log, start=time.strftime("%Y-%m-%d %H:%M"))
    print(f"\nLauf {ziel}: Quelle {quelle}, Stufe {stufe}, Netzfotos {'ja' if netz else 'nein'}, Videos {'ja' if video else 'nein'}"
          f"{', Feinstufe ' + uhr if fein else ''}\nDauer grob geschaetzt: Vorstufen ~2 h (mit Videos), SfM ~1 h, dichte Wolke 0,5-2 h.")
    if not ja("Starten?"): return 0
    rc = starten(job, log, kette_befehl(z), a.trocken)
    if a.trocken: return 0
    if rc != 0: print(f"Start fehlgeschlagen (rc {rc})"); return rc
    zustand_schreiben(k, z)
    if fein: nacht_planen(z, uhr, False)
    if verfolgen(z) and abschluss_zeigen(z): druck_anbieten(z, False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
