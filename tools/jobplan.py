#!/usr/bin/env python3
"""jobplan.py - kleiner Job-Planer: arbeitet eine Warteschlange ab und nutzt GPU, CPU und RAM zugleich, ohne die GPU-Regel zu verletzen (Register BU).

Warum: Die GPU darf nur EINEN Job zur Zeit tragen (COLMAP-SIFT-GPU stuerzt neben LightGlue/Torch ab, CLAUDE.md), die CPU-Auswertungen haengen aber nicht an ihr.
Ohne Planer wartet der Mensch zwischen den Schritten und 27 von 28 Kernen liegen brach. Der Planer startet, sobald Abhaengigkeiten erfuellt sind:
  - GPU-Job ("gpu": true): nur wenn KEIN anderer GPU-Job laeuft - auch nicht fremd gestartet (nvidia-smi compute-apps), dazu RAM-Reserve.
  - CPU-Job: bis "max_cpu_jobs" parallel, nur wenn MemAvailable >= "ram_gb" + --ram-reserve.
  - Abhaengigkeiten: "deps" (Jobnamen, Status fertig) und "wait_files" (Dateien muessen existieren; so wartet er auf extern laufende Jobs).
  - Zustand in <queue>.state.json; nach Absturz/Neustart macht er mit 'wartend' weiter (ein halb gelaufener Job wird neu gestartet - Jobs muessen idempotent sein).
  - Je Job ein Log (<logdir>/<name>.log). Exit-Code != 0 -> 'fehler'; abhaengige Jobs werden 'blockiert', unabhaengige laufen weiter.
Queue-Datei (JSON):
  {"max_cpu_jobs": 6, "logdir": "/pfad", "jobs": [{"name": "x", "cmd": "bash-Kommando", "gpu": false, "ram_gb": 2, "deps": [], "wait_files": [], "cwd": "/pfad"}]}
  tools/jobplan.py <queue.json> [--status] [--trocken] [--ram-reserve 2.0] [--takt 20]
Nur Standardbibliothek. Der Planer aendert keine Dateien ausser Zustand und Logs; was die Jobs schreiben, verantworten die Jobs.
"""
import sys, os, json, time, subprocess, argparse

def mem_verfuegbar_gb():
    for z in open("/proc/meminfo"):
        if z.startswith("MemAvailable:"): return int(z.split()[1]) / 1048576.0
    return 0.0

def fremde_gpu_pids(eigene):
    """PIDs mit GPU-Compute-Kontext, die nicht zu unseren Jobs gehoeren (z. B. von Hand gestarteter video_dicht)."""
    try: o = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True, text=True, timeout=20).stdout
    except Exception: return []
    ps = [int(x) for x in o.split() if x.strip().isdigit()]
    return [p for p in ps if not any(_gehoert(p, e) for e in eigene)]

def _gehoert(pid, wurzel):
    """True, wenn pid der Job-Prozess oder ein Nachfahre davon ist (ueber /proc/<pid>/stat ppid)."""
    while pid > 1:
        if pid == wurzel: return True
        try: pid = int(open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[1])
        except Exception: return False
    return False

def lade_zustand(sp, jobs, anzeige=False):
    st = json.load(open(sp)) if os.path.exists(sp) else {}
    for j in jobs:
        s = st.setdefault(j["name"], {"status": "wartend"})
        if s["status"] == "laeuft" and not anzeige: s["status"] = "wartend"
    return st

def speichere(sp, st): json.dump(st, open(sp + ".tmp", "w"), indent=1); os.replace(sp + ".tmp", sp)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("queue"); ap.add_argument("--status", action="store_true"); ap.add_argument("--trocken", action="store_true")
    ap.add_argument("--ram-reserve", type=float, default=2.0, help="GB RAM, die frei bleiben muessen"); ap.add_argument("--takt", type=float, default=20.0)
    a = ap.parse_args(); Q = json.load(open(a.queue)); jobs = Q["jobs"]; namen = [j["name"] for j in jobs]
    if len(set(namen)) != len(namen): sys.exit("Jobnamen nicht eindeutig")
    for j in jobs:
        for d in j.get("deps", []):
            if d not in namen: sys.exit(f"Job {j['name']}: unbekannte Abhaengigkeit {d}")
    sp = a.queue + ".state.json"; st = lade_zustand(sp, jobs, a.status); logdir = Q.get("logdir", os.path.dirname(os.path.abspath(a.queue))); os.makedirs(logdir, exist_ok=True)
    if a.status:
        for j in jobs: s = st[j["name"]]; print(f"{j['name']:28} {s['status']:10} {'GPU' if j.get('gpu') else 'CPU'}  rc={s.get('rc','-')}  {s.get('dauer_s','')}")
        return
    if a.trocken:
        for j in jobs: print(f"{j['name']:28} {'GPU' if j.get('gpu') else 'CPU'} deps={j.get('deps', [])} dateien={j.get('wait_files', [])} ram={j.get('ram_gb', 1)} GB :: {j['cmd'][:100]}")
        return
    lauf = {}                                                                                  # name -> (Popen, Startzeit)
    max_cpu = int(Q.get("max_cpu_jobs", 4)); print(f"Planer: {len(jobs)} Jobs, max {max_cpu} CPU-Jobs parallel, ein GPU-Job", flush=True)
    while True:
        for n, (p, t0) in list(lauf.items()):                                                  # beendete Jobs einsammeln
            rc = p.poll()
            if rc is not None:
                s = st[n]; s.update(status="fertig" if rc == 0 else "fehler", rc=rc, dauer_s=int(time.time() - t0), ende=time.strftime("%F %T")); del lauf[n]; speichere(sp, st)
                print(f"{time.strftime('%T')} {n}: {s['status']} (rc {rc}, {s['dauer_s']} s)", flush=True)
        for j in jobs:                                                                         # Abhaengigkeit fehlgeschlagen -> blockiert
            s = st[j["name"]]
            if s["status"] == "wartend" and any(st[d]["status"] in ("fehler", "blockiert") for d in j.get("deps", [])): s["status"] = "blockiert"; speichere(sp, st)
        offen = [j for j in jobs if st[j["name"]]["status"] == "wartend"]
        if not offen and not lauf: break
        gpu_belegt = any(next(x for x in jobs if x["name"] == n).get("gpu") for n in lauf)
        cpu_n = sum(1 for n in lauf if not next(x for x in jobs if x["name"] == n).get("gpu"))
        for j in offen:
            if any(st[d]["status"] != "fertig" for d in j.get("deps", [])): continue
            if any(not os.path.exists(f) for f in j.get("wait_files", [])): continue
            if mem_verfuegbar_gb() < j.get("ram_gb", 1.0) + a.ram_reserve: continue
            if j.get("gpu"):
                if gpu_belegt or fremde_gpu_pids([p.pid for p, _ in lauf.values()]): continue
            elif cpu_n >= max_cpu: continue
            log = open(os.path.join(logdir, j["name"] + ".log"), "w")
            p = subprocess.Popen(["bash", "-c", j["cmd"]], cwd=j.get("cwd", os.getcwd()), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            lauf[j["name"]] = (p, time.time()); st[j["name"]].update(status="laeuft", start=time.strftime("%F %T"), pid=p.pid); speichere(sp, st)
            print(f"{time.strftime('%T')} {j['name']}: gestartet ({'GPU' if j.get('gpu') else 'CPU'}, pid {p.pid})", flush=True)
            if j.get("gpu"): gpu_belegt = True
            else: cpu_n += 1
        time.sleep(a.takt)
    print("Planer fertig:", {k: v["status"] for k, v in st.items()}, flush=True)

if __name__ == "__main__":
    main()
