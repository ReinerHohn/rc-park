#!/usr/bin/env python3
"""gpu_buchung.py - GPU-Budget eines laufenden Jobs PHASENWEISE freigeben und wieder belegen (Nutzer 15.11.2026: "warum laeuft nur CPU?").

Ein Kettenlauf bucht in tools/job_start.sh 6000 MiB fuer die ganze Laufzeit, rechnet aber minutenlang nur auf der CPU (globaler Mapper ~7 min,
Fusion ~2 min). In diesen Phasen gibt der Job sein Budget frei (ein wartender GPU-Job darf starten) und holt es vor der naechsten GPU-Phase
wieder - dann wartet ER, bis Platz ist. Gleiche Buchungsdatei und Sperre wie job_start.sh (rc-park_daten/.gpu_buchung, flock).
Der Jobname kommt aus der Umgebung (RCPARK_JOB, RCPARK_GPU_MB - setzt job_start.sh); ohne sie tun frei()/belegen() nichts.
  import gpu_buchung as GB;  GB.frei();  ... CPU-Arbeit ...;  GB.belegen()
  python3 tools/gpu_buchung.py frei|belegen|zeigen
"""
import os, sys, time, fcntl, subprocess

BUCH = "/media/oem/scan/rc-park_daten/.gpu_buchung"; LIMIT = int(os.environ.get("JOB_GPU_LIMIT_MB", "7000"))
NAME = os.environ.get("RCPARK_JOB", ""); MB = int(os.environ.get("RCPARK_GPU_MB", "0") or 0)


def _aktiv(n): return subprocess.run(["systemctl", "--user", "is-active", "--quiet", f"rcpark-{n}"]).returncode == 0


def _lesen():
    z = []
    for l in open(BUCH).read().splitlines() if os.path.exists(BUCH) else []:
        t = l.split()
        if len(t) >= 3 and (_aktiv(t[0]) or time.time() - float(t[2]) < 120): z.append((t[0], int(t[1]), t[2]))
    return z


def _gemessen():
    try: return int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.split()[0])
    except Exception: return 0


def frei():
    if not NAME or MB <= 0: return
    with open(BUCH + ".lock", "a") as L:
        fcntl.flock(L, fcntl.LOCK_EX); z = [e for e in _lesen() if e[0] != NAME]; open(BUCH, "w").write("".join(f"{n} {m} {t}\n" for n, m, t in z))
    print(f"GPU-Buchung {NAME}: {MB} MiB freigegeben (CPU-Phase)", flush=True)


def belegen(warte_s=6 * 3600):
    if not NAME or MB <= 0: return
    t0 = time.time(); gemeldet = 0
    while True:
        with open(BUCH + ".lock", "a") as L:
            fcntl.flock(L, fcntl.LOCK_EX); z = [e for e in _lesen() if e[0] != NAME]; summe = sum(m for _, m, _ in z); basis = max(summe, _gemessen())
            if basis + MB <= LIMIT or time.time() - t0 > warte_s:
                open(BUCH, "w").write("".join(f"{n} {m} {t}\n" for n, m, t in z) + f"{NAME} {MB} {int(time.time())}\n")
                print(f"GPU-Buchung {NAME}: {MB} MiB wieder belegt (gewartet {time.time() - t0:.0f} s)", flush=True); return
        if time.time() - gemeldet > 600: print(f"GPU-Buchung {NAME}: warte auf {MB} MiB (gebucht {summe}, Grenze {LIMIT})", flush=True); gemeldet = time.time()
        time.sleep(20)


if __name__ == "__main__":
    b = sys.argv[1] if len(sys.argv) > 1 else "zeigen"
    if b == "frei": frei()
    elif b == "belegen": belegen()
    else: print(open(BUCH).read() if os.path.exists(BUCH) else "(leer)")
