"""Kreis-Regler: startet selbsttaetig weitere Bauteil-Kreis-Spuren (tools/bauteil_kreis.py), solange Ressourcen frei sind
und unbelegte Bauteile uebrig sind (Nutzer 10.11.: "GPU maximal, automatisch in der Pipeline, entsprechend der Ressourcenlimits").

Aufruf (einmal, als Dienst):  tools/job_start.sh kreis_regler LOG python3 tools/kreis_regler.py <objekt> [--max 8] [--takt 60]
Startbedingung je Takt (alle muessen gelten):
  GPU-Auslastung Mittel der letzten 5 Takte < --gpu_ziel (60 %)   -> GPU nicht ausgelastet
  VRAM belegt < --vram_max (5000 MiB)    (Grenze 7000 MiB gesamt, CLAUDE.md; Agenten-Werkzeuge brauchen Spitzen bis ~2,5 GB)
  RAM verfuegbar > --ram_min (3 GB), Last1 < 1,5 x Kerne
  Root frei > 6 GB, Daten frei > 11 GB   (platz_pruefen-Grenzen 5/10 GB + Puffer)
  laufende Spuren < --max, letzter Start > --abstand s her (Spuren nicht gleichzeitig in die Messphase)
Ende: 3 Spuren in Folge melden 'kein Kandidat' -> nichts mehr zu tun. Jede Entscheidung wird geloggt.
"""
import sys, os, time, subprocess, shutil, json, glob

a = sys.argv
def opt(n, d, t=str): return t(a[a.index(n) + 1]) if n in a else d
OBJ = a[1]
MAX = opt("--max", 8, int); TAKT = opt("--takt", 60, int); GPU_ZIEL = opt("--gpu_ziel", 60, float)
VRAM_MAX = opt("--vram_max", 5000, int); RAM_MIN = opt("--ram_min", 3.0, float); ABSTAND = opt("--abstand", 180, int)
RUNDEN = opt("--runden", 4, int)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); KD = "/media/oem/scan/rc-park_kreis"
sys.stdout.reconfigure(line_buffering=True)

def spuren():
    r = subprocess.run(["systemctl", "--user", "list-units", "--type=service", "--state=running", "--no-legend", "rcpark-kreis_*"],
                       capture_output=True, text=True).stdout
    return [l.split()[0] for l in r.splitlines() if l.strip() and "regler" not in l and "nach_" not in l]

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

hist, letzter = [], 0.0
print(f"Kreis-Regler {OBJ}: max {MAX} Spuren, GPU-Ziel {GPU_ZIEL} %, VRAM < {VRAM_MAX} MiB, RAM > {RAM_MIN} GB, Takt {TAKT} s")
while True:
    u, m = gpu(); hist = (hist + [u])[-5:]; ug = sum(hist) / len(hist)
    sp = spuren(); r = ram_gb(); last = os.getloadavg()[0]; ker = os.cpu_count()
    rf = shutil.disk_usage("/").free / 1e9; df = shutil.disk_usage("/media/oem/scan").free / 1e9
    kk = kein_kandidat_folge()
    grund = []
    if kk >= 3: print(time.strftime("%H:%M:%S"), "3 Spuren ohne Kandidat in Folge - Regler Ende"); break
    if len(hist) < 3: grund.append("Anlauf")
    if ug >= GPU_ZIEL: grund.append(f"GPU {ug:.0f} %")
    if m >= VRAM_MAX: grund.append(f"VRAM {m:.0f} MiB")
    if r <= RAM_MIN: grund.append(f"RAM {r:.1f} GB")
    if last >= 1.5 * ker: grund.append(f"Last {last:.1f}")
    if rf <= 6 or df <= 11: grund.append(f"Platz root {rf:.1f} daten {df:.1f} GB")
    if len(sp) >= MAX: grund.append(f"{len(sp)} Spuren = max")
    if time.time() - letzter < ABSTAND: grund.append("Abstand")
    zeile = f"{time.strftime('%H:%M:%S')} Spuren {len(sp)} GPU {u:.0f}/{ug:.0f} % VRAM {m:.0f} RAM {r:.1f} Last {last:.1f} root {rf:.1f} daten {df:.1f}"
    if grund:
        print(zeile, "-> warten:", ", ".join(grund))
    else:
        name = "a" + time.strftime("%H%M%S")
        subprocess.run([os.path.join(ROOT, "tools", "job_start.sh"), f"kreis_{name}", os.path.join(KD, f"kreis_{name}.log"),
                        "python3", "tools/bauteil_kreis.py", OBJ, "--rechte", "bypassPermissions", "--runden", str(RUNDEN), "--nach_main", "--spur", name],
                       cwd=ROOT, capture_output=True)
        letzter = time.time(); print(zeile, f"-> START Spur {name}")
    time.sleep(TAKT)
