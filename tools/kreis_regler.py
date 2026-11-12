"""Kreis-Regler: startet selbsttaetig weitere Bauteil-Kreis-Spuren (tools/bauteil_kreis.py), solange Ressourcen frei sind
und unbelegte Bauteile uebrig sind (Nutzer 10.11.: "GPU maximal, automatisch in der Pipeline, entsprechend der Ressourcenlimits").

Aufruf (einmal, als Dienst):  tools/job_start.sh kreis_regler LOG python3 tools/kreis_regler.py <objekt> [--max 8] [--takt 60]
Startbedingung je Takt (alle muessen gelten):
  GPU-Auslastung Mittel der letzten 5 Takte < --gpu_ziel (60 %)   -> GPU nicht ausgelastet
  VRAM belegt < --vram_max (5000 MiB)    (Grenze 7000 MiB gesamt, CLAUDE.md; Agenten-Werkzeuge brauchen Spitzen bis ~2,5 GB)
  RAM verfuegbar > --ram_min (6 GB = gemessene Spitze einer Spur 5,7 GB; 10.11. zwei Spuren vom OOM-Killer beendet), Last1 < 1,5 x Kerne
  Root frei > 6 GB, Daten frei > 5,5 GB (platz_pruefen-Grenzen 5/5 GB + Puffer, Nutzer 10.11. abends; Worktrees werden nach jeder Runde entfernt)
  laufende Spuren < --max, letzter Start > --abstand s her (Spuren nicht gleichzeitig in die Messphase)
  main fuer den aktuellen HEAD nicht rot (main_status.json von bauteil_kreis.py, Start-Abnahme 12.11.)
Spuren laufen mit den Kreis-Standards (Rauschtor an, Rueckgabe aus, Messbarkeits-Filter an; 12.11.).
Regeln 2-4 (12.11.): stuendliche Zielwahl-Probe (wahl_probe.json), Freigabe gesperrter Nutzerfunde nach 1 h ohne Runde (freigabe.json), Stundenbericht (stundenbericht.txt).
Ende: 3 Spuren in Folge melden 'kein Kandidat' -> nichts mehr zu tun. Jede Entscheidung wird geloggt.
"""
import sys, os, time, subprocess, shutil, json, glob

a = sys.argv
def opt(n, d, t=str): return t(a[a.index(n) + 1]) if n in a else d
OBJ = a[1]
MAX = opt("--max", 6, int); TAKT = opt("--takt", 60, int); GPU_ZIEL = opt("--gpu_ziel", 60, float)
VRAM_MAX = opt("--vram_max", 5000, int); RAM_MIN = opt("--ram_min", 6.0, float); ABSTAND = opt("--abstand", 180, int)
RUNDEN = opt("--runden", 4, int)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); KD = "/media/oem/scan/rc-park_kreis"
sys.stdout.reconfigure(line_buffering=True)

def spuren():
    r = subprocess.run(["systemctl", "--user", "list-units", "--type=service", "--state=running", "--no-legend", "--plain"],
                       capture_output=True, text=True).stdout
    n = [l.split()[0] for l in r.splitlines() if l.strip()]
    return [x for x in n if x.startswith("rcpark-kreis") and "regler" not in x and "nach_" not in x]

def gpu():
    r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
    u, m = [float(x) for x in r.split(",")[:2]]; return u, m

def ram_gb():
    for l in open("/proc/meminfo"):
        if l.startswith("MemAvailable"): return int(l.split()[1]) / 1e6
    return 0.0

def kein_kandidat_folge():
    """Wie viele der zuletzt beendeten Spuren endeten ohne Kandidat (neueste zuerst)."""
    n = 0
    for f in sorted(glob.glob(os.path.join(KD, "kreis_a*.log")), key=os.path.getmtime, reverse=True):
        t = open(f, errors="replace").read()
        if "JOB_ENDE" not in t: continue
        if "kein Kandidat" in t and "Runde 1: Ziel" not in t: n += 1
        else: break
    return n

def tote_sperren_freigeben():
    """Sperrdatei je Bauteil enthaelt 'LAUF PID'; lebt die PID nicht mehr (OOM-Kill, Abbruch), Sperre loeschen - sonst bleibt das Teil fuer immer blockiert."""
    bd = os.path.join(KD, OBJ, "belegt")
    for f in os.listdir(bd) if os.path.isdir(bd) else []:
        try: inhalt = open(os.path.join(bd, f)).read().split()
        except OSError: continue
        if len(inhalt) >= 2 and inhalt[1].isdigit() and not os.path.exists(f"/proc/{inhalt[1]}"):
            os.remove(os.path.join(bd, f)); print(time.strftime("%H:%M:%S"), "tote Sperre freigegeben:", f, inhalt)

def tote_worktrees_aufraeumen(min_alter_s=1800):
    """Worktrees abgebrochener Spuren (OOM/Zeitlimit/Code-neu-Ende vor dem Entfernen) blieben liegen: 11.11. 22 x ~520 MB = 11,5 GB, Daten 8 GB frei.
    Verlustfrei wie die Spur selbst: Reststand auf den Zweig committen, dann 'worktree remove' OHNE --force (bricht bei Unklarem ab).
    Nie bei laufendem Prozess mit Laufnamen/Spur in der Kommandozeile (auch --nachpruefen), nie juenger als min_alter_s."""
    wl = subprocess.run(["git", "-C", ROOT, "worktree", "list", "--porcelain"], capture_output=True, text=True).stdout
    wts = [l[9:] for l in wl.splitlines() if l.startswith("worktree ") and l[9:].startswith(os.path.join(KD, OBJ) + "/")]
    if not wts: return
    ps = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    for w in wts:
        lauf = os.path.basename(os.path.dirname(w)); spur = lauf.split("_", 2)[-1].lstrip("0123456789")
        if not lauf[:8].isdigit() or lauf in ps or (spur and f"--spur {spur} " in ps + " "): continue
        try:
            if time.time() - os.path.getmtime(w) < min_alter_s: continue
        except OSError: continue
        if subprocess.run(["git", "-C", w, "symbolic-ref", "-q", "HEAD"], capture_output=True).returncode == 0:
            subprocess.run(["git", "-C", w, "add", "-A"], capture_output=True)
            if subprocess.run(["git", "-C", w, "diff", "--cached", "--quiet"]).returncode != 0:
                subprocess.run(["git", "-C", w, "commit", "-q", "--no-verify", "-m", f"kreis {lauf}: Reststand gesichert (Regler raeumt toten Worktree)"], capture_output=True)
        r = subprocess.run(["git", "-C", ROOT, "worktree", "remove", w], capture_output=True, text=True)
        print(time.strftime("%H:%M:%S"), "toter Worktree", "entfernt:" if r.returncode == 0 else "bleibt (" + r.stderr.strip()[:80] + "):", w)

def tor_wartet():
    """Grund-Text, wenn ein Tor (Bau/Abnahme/Messung einer Spur oder die main-Abnahme) laeuft, ansteht oder nach OOM wartet, sonst ''.
    Nutzerregel 10.11.: Tore haben Vorrang - solange eines wartet, keine Nebenjobs (Formliste usw.); 13:3x verstopften sie 4 fertige Runden."""
    import fcntl
    try:
        with open(os.path.join(KD, "gpu_tor.lock"), "a") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(lk, fcntl.LOCK_UN)
    except BlockingIOError: return "Torschritt laeuft/ansteht (gpu_tor.lock)"
    except OSError: pass
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "rcpark-abnahme_main"]).returncode == 0: return "main-Abnahme laeuft"
    for s in spuren():
        f = os.path.join(KD, s[len("rcpark-"):].replace(".service", "") + ".log")
        try: z = [l for l in open(f, errors="replace").read().splitlines()[-3:] if l.strip()]
        except OSError: continue
        if z and "OOM im Torschritt" in z[-1]: return f"{s} wartet nach OOM im Torschritt"
    return ""

def nebenjob_anhalten(grund):
    """Laufende Formliste-Auffrischung anhalten, wenn ein Tor nach OOM wartet (teil_fotoform setzt spaeter aus der .teil-Datei fort, Ergebnis gleich)."""
    if "OOM" not in grund: return
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "rcpark-fotoform"]).returncode != 0: return
    subprocess.run(["systemctl", "--user", "stop", "rcpark-fotoform"], capture_output=True)
    print(time.strftime("%H:%M:%S"), f"Formliste-Auffrischung angehalten ({grund}), setzt spaeter fort", flush=True)

def eingang_pruefen():
    """Neue Fotoordner des Objekts (objekt.json fotos_eingang)? Dann tools/fotos_eingang.py als Dienst (JOB_GPU_MB, nie doppelt: job_start lehnt gleichen Namen ab,
    zusaetzlich Sperrdatei im Werkzeug). Trockenlauf ist billig (nur Dateilisten)."""
    cfg = json.load(open(os.path.join(ROOT, "modelle", OBJ, "objekt.json"))).get("fotos_eingang")
    if not cfg: return
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "fotos_eingang.py"), OBJ, "--trocken"], capture_output=True, text=True, cwd=ROOT, timeout=120)
    if r.returncode != 0 or " 0 mit neuen Fotos" in r.stdout or "mit neuen Fotos" not in r.stdout: return
    if os.path.exists(os.path.join(cfg["zusatz_dir"], ".eingang.lock")): return
    subprocess.run([os.path.join(ROOT, "tools", "job_start.sh"), "fotos_eingang", os.path.join(KD, "fotos_eingang.log"), sys.executable, "tools/fotos_eingang.py", OBJ],
                   cwd=ROOT, capture_output=True, env=dict(os.environ, JOB_GPU_MB=str(cfg.get("gpu_mb", 2600))))
    print(time.strftime("%H:%M:%S"), "Fotoeingang: neue Fotoordner -> fotos_eingang gestartet:", r.stdout.strip(), flush=True)

hist, letzter, leer_sig = [], 0.0, None
FORM = os.path.join(KD, OBJ, "fotoform"); form_start = 0.0
def form_auffrischen():
    """Formliste je Teil (teil_fotoform, L-KR25) fuer den aktuellen main-STL: neu, wenn keine Liste zu diesem STL passt; hoechstens alle 40 min, nie doppelt."""
    global form_start
    import hashlib
    stl = os.path.join(ROOT, json.load(open(os.path.join(ROOT, "modelle", OBJ, "objekt.json")))["stl"])
    try: sha = hashlib.sha256(open(stl, "rb").read()).hexdigest()[:16]
    except OSError: return
    if os.path.exists(os.path.join(FORM, sha + "_" + __import__("re").search(r'^METRIK = "([^"]+)"', open(os.path.join(ROOT, "tools", "teil_fotoform.py")).read(), __import__("re").M).group(1) + ".json")):
        return
    if time.time() - form_start < 2400: return
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "rcpark-fotoform"]).returncode == 0: return
    # Wartezeit seit der LETZTEN FERTIGEN Liste (Dateizeit, ueberlebt Neustart). 11.11.: STL-Zeit setzte bei jedem Merge zurueck -> bei haeufigen
    # Annahmen nie 'verhungert', 1 h 20 min ohne Liste.
    _fl = glob.glob(os.path.join(FORM, "*.json")); seit = max(max((os.path.getmtime(f) for f in _fl), default=0), form_start)
    verhungert = time.time() - seit > 3600   # 11.11.: bei 6 Spuren ist gpu_tor.lock fast immer belegt -> Liste fuer main kam 2 h nie; nach 60 min trotzdem, wenn VRAM reicht (OOM-Tor haelt sie weiter an)
    if gpu()[1] > (4500 if verhungert else 3000): return   # 10.11. 13:3x: Auffrischung (40 min GPU) verstopfte mit Agentenpruefungen die Tore (4 fertige Runden im OOM); nur bei freier GPU
    tw = tor_wartet()
    if tw and not (verhungert and "OOM" not in tw):   # Tore haben Vorrang (VRAM-Grenze allein reichte nicht: Auffrischung belegt danach selbst 2,3 GB)
        if tw != getattr(form_auffrischen, "letzt", None): print(time.strftime("%H:%M:%S"), f"Formliste veraltet, Start zurueckgestellt: {tw}", flush=True)
        form_auffrischen.letzt = tw; return
    form_auffrischen.letzt = None
    subprocess.run([os.path.join(ROOT, "tools", "job_start.sh"), "fotoform", os.path.join(KD, "fotoform.log"), "bash", "tools/fotoform_auffrischen.sh", OBJ],
                   cwd=ROOT, capture_output=True, env=dict(os.environ, JOB_GPU_MB="2500"))
    form_start = time.time()
    print(time.strftime("%H:%M:%S"), f"Formliste veraltet (main-STL {sha}) -> fotoform_auffrischen gestartet" + (f" (nach {(time.time() - seit) / 60:.0f} min Wartezeit trotz Torschritt: {tw})" if tw else ""), flush=True)
print(f"Kreis-Regler {OBJ}: max {MAX} Spuren, GPU-Ziel {GPU_ZIEL} %, VRAM < {VRAM_MAX} MiB, RAM > {RAM_MIN} GB, Takt {TAKT} s")
_takt_nr = 0
# NIE WEGEN PLATZ STEHEN (Nutzer 11.11. 16:4x "du darfst niemals stoppen wegen zu wenig Platz"): 15:07-15:14 wartete der Regler auf Platz.
# Jetzt lagert er selbst aus (verschieben + Symlink, nie loeschen): Daten < 8 GB -> fertige Kreis-Laufordner (> 90 min unveraendert) auf
# Volume (sonst Toshiba); Root < 7,5 GB -> Git-Packs auf die Datenplatte (git_packs_auslagern.sh). Laeuft im Hintergrund, eine Instanz.
_platz_proc = None
def platz_schaffen():
    global _platz_proc
    if _platz_proc is not None and _platz_proc.poll() is None: return
    rf = shutil.disk_usage("/").free / 1e9; df = shutil.disk_usage("/media/oem/scan").free / 1e9
    cmd = None
    if df < 8:
        import glob as _g
        alt = [d for d in sorted(_g.glob(os.path.join(KD, OBJ, "2026*"))) if os.path.isdir(d) and not os.path.islink(d) and time.time() - os.path.getmtime(d) > 5400]
        ziel = "/media/oem/Volume" if os.path.ismount("/media/oem/Volume") and shutil.disk_usage("/media/oem/Volume").free / 1e9 > 20 else ""
        if alt:
            cmd = (["env"] + ([f"AUSLAGERN_MOUNT={ziel}"] if ziel else []) + ["bash", os.path.join(ROOT, "tools", "auslagern.sh")] + alt[:60])
            print(f"{time.strftime('%H:%M:%S')} PLATZ daten {df:.1f} GB -> lagere {len(alt[:60])} Laufordner aus ({ziel or 'Toshiba'})", flush=True)
    elif rf < 7.5:
        cmd = ["bash", os.path.join(ROOT, "tools", "git_packs_auslagern.sh")]
        print(f"{time.strftime('%H:%M:%S')} PLATZ root {rf:.1f} GB -> Git-Packs auf Datenplatte", flush=True)
    if cmd: _platz_proc = subprocess.Popen(cmd, cwd=ROOT, stdout=open(os.path.join(KD, "platz_schaffen.log"), "a"), stderr=subprocess.STDOUT)


# --- Regeln 2-4 (12.11., Nacht 00:30-07:45 lief ohne Erker/Baldachine: Sperrzaehler aus dem alten Tor) -----------------------------------
PROBE_ALTER = 3600; BERICHT_ALTER = 3600; FREIGABE_PAUSE = 3 * 3600
_probe_proc = None; _probe_t = 0.0; _bericht_t = 0.0; _takte = {"gesamt": 0, "leer": 0}

def _kj(): return os.path.join(KD, OBJ)

def wahl_probe_starten():
    """Regel 2: stuendlich (und beim Start) die Zielwahl-Probe laufen lassen (schreibt wahl_probe.json); Auswertung in wahl_probe_pruefen."""
    global _probe_proc, _probe_t
    if _probe_proc is not None and _probe_proc.poll() is None: return
    if time.time() - _probe_t < PROBE_ALTER: return
    _probe_t = time.time()
    _probe_proc = subprocess.Popen(["python3", "tools/bauteil_kreis.py", OBJ, "--nur_wahl"], cwd=ROOT,
                                   stdout=open(os.path.join(KD, "wahl_probe.log"), "w"), stderr=subprocess.STDOUT)

def nutzerfund_runden_letzte_stunde(teile):
    n = 0; grenze = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 3600))
    for f in glob.glob(os.path.join(_kj(), "2026*", "kreis.jsonl")):
        if time.time() - os.path.getmtime(f) > 3600: continue
        for l in open(f, errors="replace"):
            try: z = json.loads(l)
            except ValueError: continue
            if z.get("zeit", "") >= grenze and str((z.get("ziel") or {}).get("teil", "")) in teile: n += 1
    return n

def wahl_probe_pruefen():
    """Regel 2 + 3: Probe fertig -> sind offene Nutzerfunde gesperrt UND lief in der letzten Stunde keine Runde an einem Nutzerfund-Teil, wird die
    Sperre freigegeben (freigabe.json: Runden bis jetzt zaehlen nicht mehr), hoechstens alle 3 h je Schluessel. Laut loggen, nie abbrechen."""
    global _probe_proc
    if _probe_proc is None or _probe_proc.poll() is None: return
    _probe_proc = None
    try: pj = json.load(open(os.path.join(_kj(), "wahl_probe.json")))
    except (OSError, ValueError): print(time.strftime("%H:%M:%S"), "ALARM Probe ohne wahl_probe.json (wahl_probe.log lesen)"); return
    nf = set(pj.get("nutzerfund_teile") or []); wb = set(pj.get("waehlbar") or []); gesp = pj.get("nutzerfund_gesperrt") or []
    print(time.strftime("%H:%M:%S"), f"PROBE {len(wb)} waehlbar, Nutzerfund-Teile {len(nf)} (davon waehlbar {len(nf & wb)}), gesperrt {len(gesp)}")
    if not nf or not gesp: return
    if sp_nutzerfund_aktiv(nf) or nutzerfund_runden_letzte_stunde(nf) > 0: return
    try: fr = json.load(open(os.path.join(_kj(), "freigabe.json")))
    except (OSError, ValueError): fr = {}
    jetzt = time.strftime("%Y-%m-%d %H:%M:%S"); alt = time.time() - FREIGABE_PAUSE; neu = []
    for g in gesp:
        for k in (g["schluessel"], g["teil"]):
            z0 = fr.get(k + "#frei", "")
            if z0 and time.mktime(time.strptime(z0, "%Y-%m-%d %H:%M:%S")) > alt: break
        else:
            for k in (g["schluessel"], g["teil"]): fr[k] = jetzt
            fr[g["schluessel"] + "#frei"] = jetzt; neu.append(g["teil"])
    if neu:
        json.dump(fr, open(os.path.join(_kj(), "freigabe.json"), "w"), ensure_ascii=False, indent=1)
        print(time.strftime("%H:%M:%S"), "ALARM Nutzerfunde seit 1 h ohne Runde und gesperrt -> Sperre freigegeben:", sorted(set(neu)))

def sp_nutzerfund_aktiv(teile):
    bd = os.path.join(_kj(), "belegt")
    return any(t in teile for t in (os.listdir(bd) if os.path.isdir(bd) else []))

def stundenbericht(sp):
    """Regel 4: stuendlich Runden je Teil, Annahmen, leere Runden, Anteil 'kein Kandidat' -> Log + stundenbericht.txt."""
    global _bericht_t
    if time.time() - _bericht_t < BERICHT_ALTER: return
    _bericht_t = time.time(); grenze = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 3600))
    je = {}; ang = leer = 0
    for f in glob.glob(os.path.join(_kj(), "2026*", "kreis.jsonl")):
        if time.time() - os.path.getmtime(f) > 3600: continue
        for l in open(f, errors="replace"):
            try: z = json.loads(l)
            except ValueError: continue
            if z.get("zeit", "") < grenze or not (z.get("ziel") or {}).get("teil"): continue
            t = z["ziel"]["teil"]; je[t] = je.get(t, 0) + 1; ang += bool(z.get("angenommen")); leer += bool(z.get("agent_leer"))
    kk = _takte["leer"] / max(_takte["gesamt"], 1)
    try: nf = set(json.load(open(os.path.join(_kj(), "wahl_probe.json"))).get("nutzerfund_teile") or [])
    except (OSError, ValueError): nf = set()
    nfr = sum(v for t, v in je.items() if t in nf)
    txt = (f"{time.strftime('%Y-%m-%d %H:%M')} STUNDENBERICHT Runden {sum(je.values())} (angenommen {ang}, leer {leer}), Nutzerfund-Runden {nfr}, "
           f"Takte ohne Kandidat {kk:.0%}, Spuren jetzt {len(sp)}; je Teil: " + ", ".join(f"{t} {v}" for t, v in sorted(je.items(), key=lambda x: -x[1])[:12]))
    if sum(je.values()) == 0 or (nf and nfr == 0) or kk > 0.8: txt += "  >>> ALARM: " + ("keine Runde" if not je else "keine Runde an Nutzerfunden" if nf and nfr == 0 else "ueber 80 % Takte ohne Kandidat")
    print(txt); open(os.path.join(_kj(), "stundenbericht.txt"), "a").write(txt + "\n")
    _takte["gesamt"] = _takte["leer"] = 0

while True:
    tote_sperren_freigeben()
    try: wahl_probe_starten(); wahl_probe_pruefen()
    except Exception as ex: print("wahl_probe:", ex)
    _takt_nr += 1
    if _takt_nr % 10 == 1:
        try: tote_worktrees_aufraeumen()
        except Exception as ex: print("tote_worktrees_aufraeumen:", ex)
    try: nebenjob_anhalten(tor_wartet())
    except Exception as ex: print("nebenjob_anhalten:", ex)
    try: form_auffrischen()
    except Exception as ex: print("form_auffrischen:", ex)
    try: eingang_pruefen()
    except Exception as ex: print("eingang_pruefen:", ex)
    try: platz_schaffen()
    except Exception as ex: print("platz_schaffen:", ex)
    u, m = gpu(); hist = (hist + [u])[-5:]; ug = sum(hist) / len(hist)
    sp = spuren(); r = ram_gb(); last = os.getloadavg()[0]; ker = os.cpu_count()
    rf = shutil.disk_usage("/").free / 1e9; df = shutil.disk_usage("/media/oem/scan").free / 1e9
    kk = kein_kandidat_folge()
    grund = []
    # 10.11.: frueher 'Regler Ende' nach 3 leeren Spuren -> nach dem naechsten Merge (Sperre frei, neue Fehlkanten) startete nichts mehr.
    # Jetzt: nach einer leeren Spur erst wieder starten, wenn sich main-HEAD oder die Teilbelegung geaendert hat.
    bd = os.path.join(KD, OBJ, "belegt")
    sig = (subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
           tuple(sorted(os.listdir(bd))) if os.path.isdir(bd) else ())
    if kk >= 1:
        if leer_sig is None: leer_sig = sig
        if sig == leer_sig: grund.append("kein Kandidat seit letzter Aenderung von main/Belegung")
    else:
        leer_sig = None
    if len(hist) < 3: grund.append("Anlauf")
    if ug >= GPU_ZIEL: grund.append(f"GPU {ug:.0f} %")
    if m >= VRAM_MAX: grund.append(f"VRAM {m:.0f} MiB")
    if r <= RAM_MIN: grund.append(f"RAM {r:.1f} GB")
    if last >= 1.5 * ker: grund.append(f"Last {last:.1f}")
    if rf <= 6 or df <= 5.5:   # Nutzer 10.11. abends: Datengrenze 5 GB (+0,5 Puffer)
        grund.append(f"Platz root {rf:.1f} daten {df:.1f} GB")
    if len(sp) >= MAX: grund.append(f"{len(sp)} Spuren = max")
    # INFRA-TOR (12.11.): bauteil_kreis prueft beim Start die Abnahme auf main (main_status.json je HEAD). Ist main fuer diesen HEAD rot, keine Spur
    # starten (sie endete sofort mit 'KREIS STARTET NICHT'); neuer HEAD (Reparatur/Merge) -> naechster Start prueft neu.
    try:
        _ms = json.load(open(os.path.join(KD, OBJ, "main_status.json")))
        if _ms.get("head") == sig[0] and _ms.get("gruen") is False: grund.append(f"main rot (Abnahme {_ms.get('zeit')}, {_ms.get('log')})")
    except (OSError, ValueError): pass
    if time.time() - letzter < ABSTAND: grund.append("Abstand")
    _takte["gesamt"] += 1; _takte["leer"] += any(g_.startswith("kein Kandidat") for g_ in grund)
    try: stundenbericht(sp)
    except Exception as ex: print("stundenbericht:", ex)
    zeile = f"{time.strftime('%H:%M:%S')} Spuren {len(sp)} GPU {u:.0f}/{ug:.0f} % VRAM {m:.0f} RAM {r:.1f} Last {last:.1f} root {rf:.1f} daten {df:.1f}"
    if grund:
        print(zeile, "-> warten:", ", ".join(grund))
    else:
        name = "a" + time.strftime("%H%M%S")
        subprocess.run([os.path.join(ROOT, "tools", "job_start.sh"), f"kreis_{name}", os.path.join(KD, f"kreis_{name}.log"),
                        "python3", "tools/bauteil_kreis.py", OBJ, "--rechte", "bypassPermissions", "--runden", str(RUNDEN), "--nach_main", "--spur", name, "--max_minuten", "60"],   # Nutzer 10.11. abends: Agent hart 60 min (Annahmen brauchten Median 16 min, ab 11 Uhr 42 min ohne Ertrag)
                       cwd=ROOT, capture_output=True)
        letzter = time.time(); print(zeile, f"-> START Spur {name}")
        if kk >= 1: leer_sig = sig   # Probestart nach Aenderung: endet auch er leer, auf die naechste Aenderung warten
    time.sleep(TAKT)
