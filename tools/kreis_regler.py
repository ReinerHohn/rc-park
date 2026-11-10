"""Kreis-Regler: startet selbsttaetig weitere Bauteil-Kreis-Spuren (tools/bauteil_kreis.py), solange Ressourcen frei sind
und unbelegte Bauteile uebrig sind (Nutzer 10.11.: "GPU maximal, automatisch in der Pipeline, entsprechend der Ressourcenlimits").

Aufruf (einmal, als Dienst):  tools/job_start.sh kreis_regler LOG python3 tools/kreis_regler.py <objekt> [--max 8] [--takt 60]
Startbedingung je Takt (alle muessen gelten):
  GPU-Auslastung Mittel der letzten 5 Takte < --gpu_ziel (60 %)   -> GPU nicht ausgelastet
  VRAM belegt < --vram_max (5000 MiB)    (Grenze 7000 MiB gesamt, CLAUDE.md; Agenten-Werkzeuge brauchen Spitzen bis ~2,5 GB)
  RAM verfuegbar > --ram_min (6 GB = gemessene Spitze einer Spur 5,7 GB; 10.11. zwei Spuren vom OOM-Killer beendet), Last1 < 1,5 x Kerne
  Root frei > 6 GB, Daten frei > 5,5 GB (platz_pruefen-Grenzen 5/5 GB + Puffer, Nutzer 10.11. abends; Worktrees werden nach jeder Runde entfernt)
  laufende Spuren < --max, letzter Start > --abstand s her (Spuren nicht gleichzeitig in die Messphase)
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

hist, letzter, leer_sig = [], 0.0, None
FORM = os.path.join(KD, OBJ, "fotoform"); form_start = 0.0
def form_auffrischen():
    """Formliste je Teil (teil_fotoform, L-KR25) fuer den aktuellen main-STL: neu, wenn keine Liste zu diesem STL passt; hoechstens alle 40 min, nie doppelt."""
    global form_start
    import hashlib
    stl = os.path.join(ROOT, json.load(open(os.path.join(ROOT, "modelle", OBJ, "objekt.json")))["stl"])
    try: sha = hashlib.sha256(open(stl, "rb").read()).hexdigest()[:16]
    except OSError: return
    if os.path.exists(os.path.join(FORM, sha + "_" + __import__("re").search(r'^METRIK = "([^"]+)"', open(os.path.join(ROOT, "tools", "teil_fotoform.py")).read(), __import__("re").M).group(1) + ".json")) or time.time() - form_start < 2400: return
    if subprocess.run(["systemctl", "--user", "is-active", "--quiet", "rcpark-fotoform"]).returncode == 0: return
    if gpu()[1] > 3000: return   # 10.11. 13:3x: Auffrischung (40 min GPU) verstopfte mit Agentenpruefungen die Tore (4 fertige Runden im OOM); nur bei freier GPU
    tw = tor_wartet()
    if tw:   # Tore haben Vorrang (VRAM-Grenze allein reichte nicht: Auffrischung belegt danach selbst 2,3 GB)
        if tw != getattr(form_auffrischen, "letzt", None): print(time.strftime("%H:%M:%S"), f"Formliste veraltet, Start zurueckgestellt: {tw}", flush=True)
        form_auffrischen.letzt = tw; return
    form_auffrischen.letzt = None
    subprocess.run([os.path.join(ROOT, "tools", "job_start.sh"), "fotoform", os.path.join(KD, "fotoform.log"), "bash", "tools/fotoform_auffrischen.sh", OBJ],
                   cwd=ROOT, capture_output=True, env=dict(os.environ, JOB_GPU_MB="2500"))
    form_start = time.time(); print(time.strftime("%H:%M:%S"), f"Formliste veraltet (main-STL {sha}) -> fotoform_auffrischen gestartet", flush=True)
print(f"Kreis-Regler {OBJ}: max {MAX} Spuren, GPU-Ziel {GPU_ZIEL} %, VRAM < {VRAM_MAX} MiB, RAM > {RAM_MIN} GB, Takt {TAKT} s")
while True:
    tote_sperren_freigeben()
    try: nebenjob_anhalten(tor_wartet())
    except Exception as ex: print("nebenjob_anhalten:", ex)
    try: form_auffrischen()
    except Exception as ex: print("form_auffrischen:", ex)
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
    if time.time() - letzter < ABSTAND: grund.append("Abstand")
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
