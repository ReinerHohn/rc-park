#!/usr/bin/env python3
"""leistung_messen.py - Leistungsmessung einer Kettenstufe/eines Werkzeugs + Thread-/Parameter-Sweep + Bericht mit Engpassvermutung (22.11.2026).

Anlass: turbostat im Ausrichtungslauf (sfm_lod2_ausrichten) zeigte Busy 99,6 % auf ALLEN Threads, 3,5 GHz, 85 W, IPC nur 0,5 - bei einem
Werkzeug, dessen Rechnung grossteils einfaedig ist (least_squares, cKDTree-Bau, FFT in numpy). Verdacht (ANNAHME, bis gemessen): OpenBLAS-
/OpenMP-Threads warten aktiv (Spin) statt zu rechnen. Das Werkzeug misst so etwas systematisch, statt zu raten.

Nur Standardbibliothek (laeuft mit nacktem python3); der gemessene Befehl bringt seine eigene Umgebung mit.
  messen:  python3 -I tools/leistung_messen.py messen --name ausr --aus <ordner> [--takt 1.5] [--env K=V ...] [--perf] -- BEFEHL ...
  sweep:   python3 -I tools/leistung_messen.py sweep --name ausr --aus <ordner> --threads 1,2,4,8,14,28 [--param FEIN=20000,40000]
                  [--wait-policy passive] [--binden] [--wiederholen 2] [--warmlauf] -- BEFEHL ... {FEIN} ...
  bericht: python3 -I tools/leistung_messen.py bericht <ordner>/messung.json|sweep.json   (Markdown neu schreiben)
Threads: --threads setzt OMP/OPENBLAS/MKL/NUMEXPR/NUMBA/VECLIB_NUM_THREADS (torch-CPU folgt OMP_NUM_THREADS); {THREADS} im Befehl wird ersetzt
  (fuer Werkzeuge mit eigenem --workers). --binden legt den Befehl zusaetzlich auf die ersten N logischen CPUs (sched_setaffinity).
  --param NAME=w1,w2 ersetzt {NAME} im Befehl (Blockgroessen, --fein-punkte ...); Kreuzprodukt mit --threads.
  Rechner: i7-14700HX hybrid - logische CPUs 0-15 = 8 P-Kerne (HT), 16-27 = 12 E-Kerne; --binden N <= 16 bleibt also auf P-Kernen.
  --wait-policy wirkt nur auf OpenMP (torch/GOMP); OpenBLAS (pthreads, numpy/scipy) spinnt unabhaengig davon - dort hilft nur die
  Thread-Zahl (ANNAHME: OPENBLAS_THREAD_TIMEOUT per --env verkuerzt das Spinnen, ungeprueft).
  perf: /usr/bin/perf ist ein Ubuntu-Wrapper ohne Paket fuer 6.17; gefunden und lauffaehig ist /usr/lib/linux-tools/6.8.0-51-generic/perf
  (perf_event_paranoid 1, eigene Prozesse) - Ereignisse je Kernart cpu_core/cpu_atom, IPC je Kernart im Bericht.
Aufzeichnung alle --takt s (Standard 1,5): Prozessbaum (CPU-Zeit, RSS-Summe, Threads, IO-Bytes aus /proc), System-CPU (/proc/stat), PSI
  (/proc/pressure cpu/memory/io), Swap, Takt (scaling_cur_freq), RAPL-Energie Package/Kerne (Differenz, Ueberlauf beachtet), Temperatur
  (x86_pkg_temp), Throttle-Zaehler (thermal_throttle, Differenz), GPU (EIN dauerhafter nvidia-smi -lms, systemweit). Ende: wait4-rusage.
  perf stat (IPC, Cache-Misses) nur mit --perf und wenn ein lauffaehiges perf gefunden wird; sonst sauber uebersprungen und gemeldet.
  turbostat braucht /dev/cpu/*/msr (root) -> wird nicht benutzt, Takt kommt aus /sys.
Ausgabe: <aus>/messung.json + bericht.md (messen) bzw. <aus>/sweep.json + bericht.md + <aus>/lauf_XX/ (sweep). Befehlsausgabe -> <aus>/.../befehl.log.
WARNUNG im Bericht, wenn waehrend der Messung Fremdlast lief (System-CPU >> Prozessbaum-CPU, aktive rcpark-*-Dienste): dann gilt die Messung nicht.
Exit: 0 = gemessen (Befehl rc 0), 1 = Befehl rc != 0 (Messung trotzdem geschrieben), 2 = Aufruffehler.
Test: tools/test_leistung_messen.py (synthetische numpy-Schleife, < 10 s). Messplan: modelle/MESSPLAN_LEISTUNG.md.
"""
import argparse, glob, itertools, json, os, re, resource, shutil, statistics, subprocess, sys, threading, time

THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
TICK = os.sysconf("SC_CLK_TCK"); PAGE = os.sysconf("SC_PAGE_SIZE"); NCPU = os.cpu_count() or 1
RAPL = {"package": "/sys/class/powercap/intel-rapl:0", "kerne": "/sys/class/powercap/intel-rapl:0/intel-rapl:0:0"}


def _lies(p, default=None):
    try:
        with open(p) as f: return f.read()
    except Exception: return default


def _zahl(p):
    s = _lies(p)
    try: return int(s.strip()) if s is not None else None
    except ValueError: return None


# ---------------- Systemquellen (jede liefert None, wenn nicht lesbar) ----------------
def proc_tabelle():
    """{pid: (ppid, cpu_s, rss_bytes, threads, state)} fuer alle Prozesse (eine Runde /proc/*/stat)."""
    t = {}
    for d in os.listdir("/proc"):
        if not d.isdigit(): continue
        s = _lies(f"/proc/{d}/stat")
        if not s: continue
        try:
            f = s[s.rindex(")") + 2:].split()
            t[int(d)] = (int(f[1]), (int(f[11]) + int(f[12])) / TICK, int(f[21]) * PAGE, int(f[17]), f[0])
        except (ValueError, IndexError): continue
    return t


def nachfahren(tab, wurzel):
    kinder = {}
    for pid, v in tab.items(): kinder.setdefault(v[0], []).append(pid)
    out, st = [], [wurzel]
    while st:
        p = st.pop()
        if p in tab: out.append(p)
        st.extend(kinder.get(p, []))
    return out


def io_bytes(pid):
    s = _lies(f"/proc/{pid}/io")
    if not s: return None
    d = dict(l.split(": ") for l in s.strip().splitlines() if ": " in l)
    return int(d.get("read_bytes", 0)), int(d.get("write_bytes", 0))


def system_cpu():
    """(busy_ticks, gesamt_ticks, iowait_ticks) aus /proc/stat."""
    l = (_lies("/proc/stat") or "").splitlines()
    if not l: return None
    v = [int(x) for x in l[0].split()[1:]]
    idle = v[3] + (v[4] if len(v) > 4 else 0)
    return sum(v[:8]) - idle, sum(v[:8]), v[4] if len(v) > 4 else 0


def psi():
    """{cpu/memory/io: some_total_us} (Druck-Stallzeit, kumulativ)."""
    out = {}
    for k in ("cpu", "memory", "io"):
        s = _lies(f"/proc/pressure/{k}")
        m = re.search(r"some .*total=(\d+)", s or "")
        if m: out[k] = int(m.group(1))
    return out


def meminfo():
    s = _lies("/proc/meminfo") or ""; d = {}
    for l in s.splitlines():
        p = l.split()
        if len(p) >= 2: d[p[0].rstrip(":")] = int(p[1]) * 1024
    return dict(verfuegbar=d.get("MemAvailable"), swap_benutzt=(d["SwapTotal"] - d["SwapFree"]) if "SwapTotal" in d else None, gesamt=d.get("MemTotal"))


def takt_mhz():
    v = [x for x in (_zahl(p) for p in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq")) if x]
    return (sum(v) / len(v) / 1000, max(v) / 1000) if v else None


def rapl_uj():
    out = {}
    for k, d in RAPL.items():
        e = _zahl(d + "/energy_uj")
        if e is not None: out[k] = (e, _zahl(d + "/max_energy_range_uj") or 2 ** 32)
    return out


def temperatur_c():
    for z in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
        if (_lies(z + "/type") or "").strip() == "x86_pkg_temp":
            t = _zahl(z + "/temp"); return t / 1000 if t else None
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if (_lies(h + "/name") or "").strip() == "coretemp":
            t = _zahl(h + "/temp1_input"); return t / 1000 if t else None
    return None


def throttle():
    c = [x for x in (_zahl(p) for p in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/thermal_throttle/core_throttle_count")) if x is not None]
    p = _zahl("/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_count")
    return dict(kern=sum(c) if c else None, package=p)


def rcpark_dienste():
    try:
        r = subprocess.run(["systemctl", "--user", "list-units", "rcpark-*", "--state=active", "--no-legend", "--plain"], capture_output=True, text=True, timeout=5)
        return [l.split()[0] for l in r.stdout.splitlines() if l.strip()]
    except Exception: return None


class GpuLeser:
    """EIN dauerhafter nvidia-smi -lms (statt je Probe ein neuer Prozess). Werte systemweit (alle GPU-Prozesse)."""
    FELDER = "power.draw,utilization.gpu,utilization.memory,memory.used,temperature.gpu,clocks.sm"

    def __init__(self, takt_s):
        self.proben = []; self.proc = None; self.fehler = None
        exe = shutil.which("nvidia-smi")
        if not exe: self.fehler = "nvidia-smi nicht gefunden"; return
        try:
            self.proc = subprocess.Popen([exe, f"--query-gpu={self.FELDER}", "--format=csv,noheader,nounits", f"-lms={int(takt_s * 1000)}"],
                                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            threading.Thread(target=self._lesen, daemon=True).start()
        except Exception as e: self.fehler = f"nvidia-smi: {e}"

    def _lesen(self):
        for l in self.proc.stdout:
            try:
                w = [float(x) if x.strip() not in ("[N/A]", "N/A") else None for x in l.split(",")]
                if len(w) == 6: self.proben.append(dict(t=time.time(), w=w[0], util=w[1], util_mem=w[2], vram_mb=w[3], temp=w[4], sm_mhz=w[5]))
            except ValueError: continue

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try: self.proc.wait(3)
            except Exception: self.proc.kill()


def perf_finden():
    """(pfad, None) fuer ein lauffaehiges perf, sonst (None, grund). Ubuntu-perf ist ein Wrapper, der ohne linux-tools-<kernel> scheitert."""
    kand = [p for p in [shutil.which("perf")] + sorted(glob.glob("/usr/lib/linux-tools/*/perf")) + sorted(glob.glob("/usr/lib/linux-tools-*/perf")) if p]
    grund = "kein perf-Programm gefunden"
    for p in kand:
        try:
            r = subprocess.run([p, "stat", "-x,", "-e", "cycles,instructions", "true"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and "instructions" in r.stderr and "<not supported>" not in r.stderr: return p, None
            grund = f"{p}: rc {r.returncode}: " + " ".join(r.stderr.split())[:160]
        except Exception as e: grund = f"{p}: {e}"
    par = (_lies("/proc/sys/kernel/perf_event_paranoid") or "?").strip()
    return None, f"{grund} (perf_event_paranoid {par})"


def perf_lesen(pfad):
    """perf stat -x, Ausgabe. Hybrid-CPU (i7-14700HX: cpu_core = P-Kerne 0-15, cpu_atom = E-Kerne 16-27): Ereignisse je Kernart + Summe."""
    out, art = {}, {}
    for l in (_lies(pfad) or "").splitlines():
        f = l.split(",")
        if len(f) >= 3 and f[0] and f[0][0].isdigit():
            try: w = float(f[0])
            except ValueError: continue
            name = f[2].split(":")[0]; mm = re.match(r"(cpu_\w+)/(.+?)/?$", name)
            if mm: art.setdefault(mm.group(1), {})[mm.group(2)] = w; name = mm.group(2)
            out[name] = out.get(name, 0.0) + w
    for k, d in art.items():
        if d.get("cycles") and d.get("instructions"): out[f"ipc_{k}"] = round(d["instructions"] / d["cycles"], 3); out[f"zyklen_anteil_{k}"] = d["cycles"]
    tz = sum(d.get("cycles", 0) for d in art.values())
    for k in art:
        if tz: out[f"zyklen_anteil_{k}"] = round(out[f"zyklen_anteil_{k}"] / tz, 3) if f"zyklen_anteil_{k}" in out else None
    if out.get("cycles") and out.get("instructions"): out["ipc"] = out["instructions"] / out["cycles"]
    if out.get("cache-references") and out.get("cache-misses") is not None: out["cache_miss_anteil"] = out["cache-misses"] / out["cache-references"]
    return out


# ---------------- eine Messung ----------------
def systemprobe():
    return dict(t=time.time(), cpu=system_cpu(), psi=psi(), mem=meminfo(), takt=takt_mhz(), rapl=rapl_uj(), temp=temperatur_c())


def _rapl_diff(a, b):
    out = {}
    for k in b:
        if k in a:
            d = b[k][0] - a[k][0]
            if d < 0: d += b[k][1]
            out[k] = d / 1e6
    return out


def messen(befehl, aus, takt=1.5, env_extra=None, perf=False, binden=None, ruhe_s=1.0, still=True):
    """Fuehrt befehl aus und zeichnet auf. Gibt das Messungs-dict zurueck (auch nach aus/messung.json)."""
    os.makedirs(aus, exist_ok=True)
    env = dict(os.environ); env.update(env_extra or {})
    hinweise = []
    perf_pfad, perf_grund, perf_out = None, None, None
    if perf:
        perf_pfad, perf_grund = perf_finden()
        if perf_pfad:
            perf_out = os.path.join(aus, "perf.csv")
            befehl = [perf_pfad, "stat", "-x,", "-o", perf_out, "-e", "cycles,instructions,cache-references,cache-misses,context-switches,cpu-migrations", "--"] + list(befehl)
        else: hinweise.append(f"perf uebersprungen: {perf_grund}")
    if not os.access("/dev/cpu/0/msr", os.R_OK): hinweise.append("turbostat/MSR nicht lesbar ohne root -> Takt aus /sys (scaling_cur_freq), kein IPC aus turbostat")
    dienste = rcpark_dienste()
    # Ruhewert vor dem Start (Fremdlast + Leerlaufleistung)
    r0 = systemprobe(); time.sleep(max(0.0, ruhe_s)); r1 = systemprobe()
    ruhe = dict(dauer_s=r1["t"] - r0["t"])
    if r0["cpu"] and r1["cpu"]: ruhe["system_cpu_kerne"] = (r1["cpu"][0] - r0["cpu"][0]) / max(1, r1["cpu"][1] - r0["cpu"][1]) * NCPU
    e = _rapl_diff(r0["rapl"], r1["rapl"])
    if e and ruhe["dauer_s"] > 0: ruhe["package_w"] = e.get("package", 0) / ruhe["dauer_s"]
    thr0 = throttle(); gpu = GpuLeser(takt); self0 = resource.getrusage(resource.RUSAGE_SELF)
    log = open(os.path.join(aus, "befehl.log"), "w")
    pre = (lambda: os.sched_setaffinity(0, set(range(min(binden, NCPU))))) if binden else None
    s0 = systemprobe(); t0 = time.time()
    p = subprocess.Popen(befehl, stdout=log if still else None, stderr=subprocess.STDOUT if still else None, env=env, preexec_fn=pre)
    proben, gesehen, io_max = [], {}, {}
    letzte = s0; ende = None
    while True:
        try:
            pid_, status, ru = os.wait4(p.pid, os.WNOHANG)
        except ChildProcessError: break
        if pid_ == p.pid: ende = (status, ru); break
        time.sleep(takt)
        tab = proc_tabelle(); baum = nachfahren(tab, p.pid)
        for q in baum:
            gesehen[q] = max(gesehen.get(q, 0.0), tab[q][1])
            io = io_bytes(q)
            if io: io_max[q] = (max(io_max.get(q, (0, 0))[0], io[0]), max(io_max.get(q, (0, 0))[1], io[1]))
        sp = systemprobe(); dt = sp["t"] - letzte["t"]
        pr = dict(t=round(sp["t"] - t0, 2), prozesse=len(baum), threads=sum(tab[q][3] for q in baum), laufend=sum(1 for q in baum if tab[q][4] == "R"),
                  rss_mb=round(sum(tab[q][2] for q in baum) / 2 ** 20, 1), cpu_s_kum=round(sum(gesehen.values()), 2),
                  takt_mhz=round(sp["takt"][0]) if sp["takt"] else None, temp_c=sp["temp"],
                  swap_mb=round(sp["mem"]["swap_benutzt"] / 2 ** 20) if sp["mem"].get("swap_benutzt") is not None else None)
        if sp["cpu"] and letzte["cpu"] and dt > 0: pr["system_cpu_kerne"] = round((sp["cpu"][0] - letzte["cpu"][0]) / max(1, sp["cpu"][1] - letzte["cpu"][1]) * NCPU, 2)
        e = _rapl_diff(letzte["rapl"], sp["rapl"])
        if e and dt > 0: pr["package_w"] = round(e.get("package", 0) / dt, 1)
        if proben and dt > 0: pr["baum_cpu_kerne"] = round((pr["cpu_s_kum"] - proben[-1]["cpu_s_kum"]) / dt, 2)
        proben.append(pr); letzte = sp
    t1 = time.time(); s1 = systemprobe(); gpu.stop(); log.close(); thr1 = throttle(); self1 = resource.getrusage(resource.RUSAGE_SELF)
    status, ru = ende if ende else (0, None)
    rc = os.waitstatus_to_exitcode(status) if ende else p.returncode
    wall = t1 - t0
    m = dict(befehl=list(befehl), env={k: v for k, v in (env_extra or {}).items()}, binden=binden, rc=rc, wall_s=round(wall, 3), ncpu=NCPU,
             beginn=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)), takt_s=takt, ruhe=ruhe, rcpark_dienste_aktiv=dienste, hinweise=hinweise)
    if ru:
        m["cpu_user_s"] = round(ru.ru_utime, 3); m["cpu_sys_s"] = round(ru.ru_stime, 3); m["cpu_s"] = round(ru.ru_utime + ru.ru_stime, 3)
        m["max_rss_einzelprozess_mb"] = round(ru.ru_maxrss / 1024, 1); m["kontextwechsel_freiwillig"] = ru.ru_nvcsw; m["kontextwechsel_erzwungen"] = ru.ru_nivcsw
        m["cpu_kerne_mittel"] = round(m["cpu_s"] / wall, 2) if wall > 0 else None
    m["rss_baum_spitze_mb"] = max((x["rss_mb"] for x in proben), default=m.get("max_rss_einzelprozess_mb"))
    if proben: m["threads_spitze"] = max(x["threads"] for x in proben); m["laufend_mittel"] = round(statistics.mean(x["laufend"] for x in proben), 2)
    if io_max: m["io_lesen_mb"] = round(sum(v[0] for v in io_max.values()) / 2 ** 20, 1); m["io_schreiben_mb"] = round(sum(v[1] for v in io_max.values()) / 2 ** 20, 1)
    if s0["cpu"] and s1["cpu"]:
        dg = max(1, s1["cpu"][1] - s0["cpu"][1])
        m["system_cpu_kerne_mittel"] = round((s1["cpu"][0] - s0["cpu"][0]) / dg * NCPU, 2); m["iowait_anteil"] = round((s1["cpu"][2] - s0["cpu"][2]) / dg, 4)
    if s0["psi"] and s1["psi"] and wall > 0: m["psi_anteil"] = {k: round((s1["psi"][k] - s0["psi"][k]) / 1e6 / wall, 4) for k in s1["psi"] if k in s0["psi"]}
    e = _rapl_diff(s0["rapl"], s1["rapl"])
    if e:
        m["energie_j"] = {k: round(v, 1) for k, v in e.items()}; m["package_w_mittel"] = round(e.get("package", 0) / wall, 1) if wall > 0 else None
        if ruhe.get("package_w") is not None: m["energie_netto_j"] = round(e.get("package", 0) - ruhe["package_w"] * wall, 1)   # ANNAHME: Ruhelast bleibt konstant
    else: hinweise.append("RAPL (/sys/class/powercap/intel-rapl:0/energy_uj) nicht lesbar -> keine Energie")
    tk = [x["takt_mhz"] for x in proben if x.get("takt_mhz")]; tp = [x["temp_c"] for x in proben if x.get("temp_c")]
    if tk: m["takt_mhz_mittel"] = round(statistics.mean(tk)); m["takt_mhz_max_cpu"] = round(max_freq_mhz() or 0)
    if tp: m["temp_c_max"] = max(tp); m["temp_c_mittel"] = round(statistics.mean(tp), 1)
    m["throttle_diff"] = {k: (thr1[k] - thr0[k]) if thr0.get(k) is not None and thr1.get(k) is not None else None for k in thr0}
    sw = [x["swap_mb"] for x in proben if x.get("swap_mb") is not None]
    if sw: m["swap_zuwachs_mb"] = max(sw) - sw[0]
    g = [x for x in gpu.proben if t0 <= x["t"] <= t1]
    if g:
        f = lambda k: [x[k] for x in g if x[k] is not None]
        m["gpu"] = dict(proben=len(g), util_mittel=round(statistics.mean(f("util")), 1) if f("util") else None, util_max=max(f("util"), default=None),
                        w_mittel=round(statistics.mean(f("w")), 1) if f("w") else None, vram_mb_max=max(f("vram_mb"), default=None),
                        vram_mb_start=g[0]["vram_mb"], energie_j=round(sum((g[i]["w"] or 0) * (g[i]["t"] - g[i - 1]["t"]) for i in range(1, len(g))), 1))
    else: m["gpu"] = dict(fehler=gpu.fehler or "keine GPU-Proben (Lauf kuerzer als ein Takt?)")
    if perf_out: m["perf"] = perf_lesen(perf_out) or dict(fehler="perf-Ausgabe leer")
    elif perf: m["perf"] = dict(uebersprungen=perf_grund)
    m["messaufwand_cpu_s"] = round((self1.ru_utime + self1.ru_stime) - (self0.ru_utime + self0.ru_stime), 3)
    m["proben"] = proben
    if rc != 0:
        try: m["log_ende"] = open(os.path.join(aus, "befehl.log"), errors="replace").read()[-1500:]
        except Exception: pass
    m["engpass"], m["vorschlaege"] = engpass(m)
    json.dump(m, open(os.path.join(aus, "messung.json"), "w"), indent=1)
    open(os.path.join(aus, "bericht.md"), "w").write(bericht_messung(m))
    return m


def max_freq_mhz():
    v = _zahl("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"); return v / 1000 if v else None


# ---------------- Engpassvermutung ----------------
def engpass(m, sweep=None):
    """[(urteil, beleg)], [vorschlag] aus den Kennzahlen. Nur Vermutungen mit Zahlen; nicht Gemessenes heisst ANNAHME."""
    u, v = [], []
    wall = m.get("wall_s") or 0; kerne = m.get("cpu_kerne_mittel"); syskerne = m.get("system_cpu_kerne_mittel")
    fremd = None
    if syskerne is not None and kerne is not None:
        fremd = syskerne - kerne - m.get("messaufwand_cpu_s", 0) / max(wall, 1e-9)
        if fremd > max(1.0, 0.25 * max(kerne, 1)):
            u.append(("FREMDLAST - Messung nicht belastbar", f"System {syskerne:.1f} Kerne, Prozessbaum {kerne:.1f} Kerne (Differenz {fremd:.1f})"))
            v.append("Messung allein wiederholen (tools/job_start.sh, kein Kettenlauf/Agentenlauf parallel)")
    rk = (m.get("ruhe") or {}).get("system_cpu_kerne")
    if rk is not None and rk > 1.5 and not any("FREMDLAST" in x[0] for x in u):   # Fremdlast vor dem Start (z. B. Kettenlauf), vom Befehl waehrend des Laufs verdraengt
        u.append(("FREMDLAST vor dem Start - Messung nicht belastbar", f"System schon in Ruhe {rk:.1f} Kerne belegt (Kettenlauf/anderer Job?)"))
        v.append("Messung allein wiederholen (tools/job_start.sh, kein Kettenlauf/Agentenlauf parallel)")
    if m.get("rcpark_dienste_aktiv"): u.append(("WARNUNG aktive rcpark-Dienste waehrend der Messung", ", ".join(m["rcpark_dienste_aktiv"])))
    g = m.get("gpu") or {}
    if g.get("util_mittel") is not None and g["util_mittel"] >= 60:
        u.append(("GPU-gebunden (vermutlich)", f"GPU-Auslastung Mittel {g['util_mittel']} % (max {g.get('util_max')}), {g.get('w_mittel')} W"))
        v.append("GPU-Teil optimieren (Blockgroessen, float32, weniger Host<->GPU-Kopien); CPU-Threads bringen hier wenig")
    elif g.get("util_mittel") is not None and g["util_mittel"] < 15 and g.get("vram_mb_max") and g.get("vram_mb_start") is not None and g["vram_mb_max"] - g["vram_mb_start"] > 200:
        u.append(("GPU belegt Speicher, rechnet aber kaum", f"VRAM +{g['vram_mb_max'] - g['vram_mb_start']:.0f} MiB, Auslastung Mittel {g['util_mittel']} %"))
        v.append("pruefen, ob die GPU-Schritte (FFT/knn) nur kurz sind und der Rest auf der CPU haengt; Host<->GPU-Kopien je Iteration zaehlen")
    pa = m.get("psi_anteil") or {}
    if pa.get("io", 0) > 0.2 or (m.get("iowait_anteil") or 0) > 0.1:
        u.append(("IO-gebunden (vermutlich)", f"PSI io {100 * pa.get('io', 0):.0f} % der Zeit, iowait {100 * (m.get('iowait_anteil') or 0):.0f} %, gelesen {m.get('io_lesen_mb')} MB"))
        v.append("Eingaben in den Seitencache/auf schnellere Platte, Zwischenergebnisse cachen, weniger oft lesen (z. B. PLY einmal als .npy)")
    if pa.get("memory", 0) > 0.05 or (m.get("swap_zuwachs_mb") or 0) > 200:
        u.append(("RAM knapp (Reclaim/Swap)", f"PSI memory {100 * pa.get('memory', 0):.0f} %, Swap +{m.get('swap_zuwachs_mb')} MB, RSS-Spitze {m.get('rss_baum_spitze_mb')} MB"))
        v.append("Spitzen-RAM senken (Blockweise, float32) oder allein laufen lassen")
    td = m.get("throttle_diff") or {}
    if (td.get("kern") or 0) > 0 or (td.get("package") or 0) > 0:
        u.append(("Thermische Drosselung", f"Throttle-Zaehler +{td.get('kern')} (Kerne) / +{td.get('package')} (Package), Temp max {m.get('temp_c_max')} C"))
        v.append("weniger Threads/Spin vermeiden senkt Leistung und Temperatur; Kuehlung pruefen")
    pf = m.get("perf") or {}
    if kerne is not None:
        if kerne < 1.3 and (g.get("util_mittel") or 0) < 60:
            u.append(("CPU einfaedig (vermutlich)", f"Prozessbaum im Mittel {kerne:.2f} Kerne von {m.get('ncpu')}"))
            v.append("Hotspot per Profil (python -m cProfile -o ... ) suchen; nur dort parallelisieren/vektorisieren; Threads fuer BLAS bringen dann nichts")
        elif kerne >= 1.3:
            beleg = f"Prozessbaum im Mittel {kerne:.1f} Kerne, Spitze {m.get('threads_spitze')} Threads"
            if pf.get("ipc") is not None:
                beleg += f", IPC {pf['ipc']:.2f}" + (f", Cache-Miss-Anteil {100 * pf['cache_miss_anteil']:.0f} %" if pf.get("cache_miss_anteil") is not None else "")
                if pf["ipc"] < 0.8 and (pf.get("cache_miss_anteil") or 0) > 0.3: u.append(("Speicher-/Latenzgebunden (perf)", beleg))
                elif pf["ipc"] < 0.8: u.append(("Viele Kerne bei niedrigem IPC ohne hohe Cache-Misses -> Spin-Warten (pause) wahrscheinlich", beleg))
                else: u.append(("CPU-gebunden mehrfaedig", beleg))
            else:
                u.append(("CPU mehrfaedig - ob Rechnung oder Spin-Warten, zeigt nur der Thread-Sweep (ANNAHME ohne perf)", beleg))
            v.append("Thread-Sweep (sweep --threads 1,2,4,8,14,28, zusaetzlich --wait-policy passive): bleibt die Wallzeit gleich, war es Spin-Warten")
    if sweep:
        b, k = sweep.get("beste"), sweep.get("kleinste_innerhalb_5")
        if b and k:
            u.append(("Sweep", f"beste Wallzeit {b['wall_s']:.1f} s bei {b['einstellung']}; kleinste Einstellung innerhalb 5 %: {k['einstellung']} ({k['wall_s']:.1f} s, {k.get('energie_j')} J)"))
            if k["einstellung"] != b["einstellung"]: v.append(f"Einstellung {k['einstellung']} fuer diese Stufe setzen (gleiche Zeit, weniger Kerne/Energie; Kerne fuer Parallelstufen frei)")
            s = sweep.get("skalierung") or []
            if len(s) >= 2 and s[-1]["beschleunigung"] < 1.3 and s[-1]["threads"] >= 4 * s[0]["threads"]:
                u.append(("Skaliert nicht mit Threads", f"{s[0]['threads']} -> {s[-1]['threads']} Threads: nur x{s[-1]['beschleunigung']:.2f}"))
    if not u: u.append(("kein klarer Engpass", "keine Kennzahl ueber der Schwelle"))
    return u, v


# ---------------- Sweep ----------------
def _ersetzen(befehl, werte):
    out = []
    for a in befehl:
        for k, w in werte.items(): a = a.replace("{" + k + "}", str(w))
        out.append(a)
    return out


def auswerten(laeufe, toleranz=0.05):
    """laeufe: [dict(einstellung, threads, wall_s, energie_j, rss_mb, rc)] -> beste, kleinste innerhalb toleranz, Skalierung (nach threads)."""
    ok = [l for l in laeufe if l.get("rc") == 0 and l.get("wall_s")]
    if not ok: return dict(beste=None, kleinste_innerhalb_5=None, skalierung=[])
    beste = min(ok, key=lambda l: l["wall_s"])
    innen = [l for l in ok if l["wall_s"] <= beste["wall_s"] * (1 + toleranz)]
    kleinste = min(innen, key=lambda l: (l.get("threads") or 0, l.get("energie_j") or 0, l["wall_s"]))
    energie = min((l for l in ok if l.get("energie_j") is not None), key=lambda l: l["energie_j"], default=None)
    skal = []
    nach_t = {}
    for l in ok:
        if l.get("threads") is not None and l.get("parameter") == beste.get("parameter"): nach_t.setdefault(l["threads"], []).append(l["wall_s"])
    if nach_t:
        t_min = min(nach_t); w_ref = statistics.median(nach_t[t_min])
        for t in sorted(nach_t):
            w = statistics.median(nach_t[t]); skal.append(dict(threads=t, wall_s=round(w, 2), beschleunigung=round(w_ref / w, 3), effizienz=round(w_ref / w / (t / t_min), 3)))
    return dict(beste=beste, kleinste_innerhalb_5=kleinste, energie_min=energie, skalierung=skal, toleranz=toleranz)


def sweep(befehl, aus, threads=None, params=None, wait_policy=None, binden=False, wiederholen=1, warmlauf=False, takt=1.5, perf=False, env_extra=None):
    os.makedirs(aus, exist_ok=True)
    params = params or {}
    for k in params:
        if not any("{" + k + "}" in a for a in befehl): raise SystemExit(f"--param {k}: Platzhalter {{{k}}} kommt im Befehl nicht vor")
    tl = threads or [None]
    kombis = [dict(zip(params, w)) for w in itertools.product(*params.values())] if params else [{}]
    laeufe, nr = [], 0
    if warmlauf:   # Seitencache/LoD2-Cache fuellen, nicht werten
        t0 = tl[-1]; env = dict(env_extra or {}); env.update({k: str(t0) for k in THREAD_VARS} if t0 else {})
        messen(_ersetzen(befehl, dict(kombis[0], THREADS=t0 or NCPU)), os.path.join(aus, "warmlauf"), takt, env, False, None, 0.5)
    for _ in range(max(1, wiederholen)):
        for t in tl:
            for pk in kombis:
                env = dict(env_extra or {})
                if t: env.update({k: str(t) for k in THREAD_VARS})
                if wait_policy: env["OMP_WAIT_POLICY"] = wait_policy.upper()
                eins = (f"threads={t}" if t else "threads=Standard") + "".join(f" {k}={w}" for k, w in pk.items()) + (f" wait={wait_policy}" if wait_policy else "") + (" gebunden" if binden and t else "")
                m = messen(_ersetzen(befehl, dict(pk, THREADS=t or NCPU)), os.path.join(aus, f"lauf_{nr:02d}"), takt, env, perf, t if (binden and t) else None, 0.5)
                laeufe.append(dict(nr=nr, einstellung=eins, threads=t if t else NCPU, parameter=pk, rc=m["rc"], wall_s=m["wall_s"], cpu_s=m.get("cpu_s"),
                                   cpu_kerne=m.get("cpu_kerne_mittel"), energie_j=(m.get("energie_j") or {}).get("package"), rss_mb=m.get("rss_baum_spitze_mb"),
                                   gpu_util=(m.get("gpu") or {}).get("util_mittel"), ipc=(m.get("perf") or {}).get("ipc"), fremdlast=any("FREMDLAST" in x[0] for x in m["engpass"])))
                print(f"  {eins}: {m['wall_s']:.1f} s, CPU {m.get('cpu_kerne_mittel')} Kerne, {laeufe[-1]['energie_j']} J, RSS {laeufe[-1]['rss_mb']} MB, rc {m['rc']}", flush=True)
                nr += 1
    # Wiederholungen: Median je Einstellung
    gr = {}
    for l in laeufe: gr.setdefault(l["einstellung"], []).append(l)
    zus = []
    for e, ls in gr.items():
        z = dict(ls[0]); z["wall_s"] = statistics.median(x["wall_s"] for x in ls); z["n"] = len(ls); z["rc"] = max(x["rc"] for x in ls)
        if all(x.get("energie_j") is not None for x in ls): z["energie_j"] = round(statistics.median(x["energie_j"] for x in ls), 1)
        z["wall_streuung_s"] = round(max(x["wall_s"] for x in ls) - min(x["wall_s"] for x in ls), 2); zus.append(z)
    erg = auswerten(zus)
    ref = json.load(open(os.path.join(aus, f"lauf_{(erg['beste'] or zus[0])['nr']:02d}", "messung.json")))
    u, v = engpass(ref, erg)
    s = dict(befehl=list(befehl), threads=threads, params=params, wait_policy=wait_policy, binden=binden, wiederholen=wiederholen, laeufe=laeufe, zusammen=zus, **erg, engpass=u, vorschlaege=v)
    json.dump(s, open(os.path.join(aus, "sweep.json"), "w"), indent=1)
    open(os.path.join(aus, "bericht.md"), "w").write(bericht_sweep(s))
    return s


# ---------------- Berichte (kurz, keine breiten Tabellen) ----------------
def _f(x, nd=1, e=""):
    return "?" if x is None else (f"{x:.{nd}f}{e}" if isinstance(x, (int, float)) else f"{x}{e}")


def bericht_messung(m):
    g = m.get("gpu") or {}; z = [f"# Leistungsmessung {m.get('beginn')}", "", f"Befehl: `{' '.join(m['befehl'])[:300]}`", ""]
    if m.get("env"): z.append(f"Umgebung: {', '.join(f'{k}={v}' for k, v in m['env'].items())}")
    z += ["## Engpassvermutung (Fehlerliste zuerst)"] + [f"- **{a}**: {b}" for a, b in m.get("engpass", [])]
    z += ["", "## Zahlen",
          f"- Wallzeit {_f(m.get('wall_s'))} s, rc {m.get('rc')}; CPU {_f(m.get('cpu_s'))} s (user {_f(m.get('cpu_user_s'))}, sys {_f(m.get('cpu_sys_s'))}) = {_f(m.get('cpu_kerne_mittel'), 2)} Kerne im Mittel von {m.get('ncpu')}",
          f"- System-CPU {_f(m.get('system_cpu_kerne_mittel'), 2)} Kerne (Ruhe vorher {_f((m.get('ruhe') or {}).get('system_cpu_kerne'), 2)}); Threads Spitze {m.get('threads_spitze')}, laufend Mittel {m.get('laufend_mittel')}",
          f"- RAM: RSS-Summe Spitze {_f(m.get('rss_baum_spitze_mb'), 0)} MB, groesster Einzelprozess {_f(m.get('max_rss_einzelprozess_mb'), 0)} MB, Swap +{m.get('swap_zuwachs_mb')} MB",
          f"- Energie Package {(m.get('energie_j') or {}).get('package')} J (netto ueber Ruhe {m.get('energie_netto_j')} J, ANNAHME Ruhelast konstant), Kerne {(m.get('energie_j') or {}).get('kerne')} J; Mittel {m.get('package_w_mittel')} W, Ruhe {_f((m.get('ruhe') or {}).get('package_w'))} W",
          f"- Takt Mittel {m.get('takt_mhz_mittel')} MHz (max {m.get('takt_mhz_max_cpu')}); Temp max {m.get('temp_c_max')} C; Throttle-Zuwachs {m.get('throttle_diff')}",
          f"- IO gelesen {m.get('io_lesen_mb')} MB, geschrieben {m.get('io_schreiben_mb')} MB; iowait {_f(100 * (m.get('iowait_anteil') or 0))} %; PSI {m.get('psi_anteil')}",
          f"- GPU: " + (f"Auslastung Mittel {g.get('util_mittel')} % (max {g.get('util_max')}), {g.get('w_mittel')} W, {g.get('energie_j')} J, VRAM {g.get('vram_mb_start')} -> max {g.get('vram_mb_max')} MiB (systemweit)" if "fehler" not in g else g["fehler"]),
          f"- perf: {m.get('perf') if m.get('perf') else 'nicht angefordert (--perf)'}",
          f"- Messaufwand des Werkzeugs: {m.get('messaufwand_cpu_s')} CPU-s"]
    z += ["", "## Vorschlaege (ANNAHME bis per Sweep/Messplan belegt)"] + [f"- {x}" for x in m.get("vorschlaege", [])]
    if m.get("hinweise"): z += ["", "## Hinweise"] + [f"- {x}" for x in m["hinweise"]]
    return "\n".join(z) + "\n"


def bericht_sweep(s):
    z = ["# Sweep-Bericht", "", f"Befehl: `{' '.join(s['befehl'])[:300]}`", "", "## Engpassvermutung (Fehlerliste zuerst)"]
    z += [f"- **{a}**: {b}" for a, b in s.get("engpass", [])]
    if any(l.get("fremdlast") for l in s["laeufe"]): z.append("- **FREMDLAST in mindestens einem Lauf** - Zahlen nicht belastbar, allein wiederholen")
    if any(l["rc"] != 0 for l in s["laeufe"]): z.append(f"- **{sum(1 for l in s['laeufe'] if l['rc'])} Laeufe mit rc != 0** (lauf_XX/befehl.log)")
    z += ["", "## Einstellungen (Median ueber Wiederholungen)"]
    for l in s["zusammen"]:
        z.append(f"- {l['einstellung']}: {l['wall_s']:.1f} s (Streuung {l.get('wall_streuung_s')} s, n {l.get('n')}), CPU {l.get('cpu_kerne')} Kerne, {l.get('energie_j')} J, RSS {l.get('rss_mb')} MB" + (f", GPU {l['gpu_util']} %" if l.get('gpu_util') is not None else "") + (f", IPC {l['ipc']:.2f}" if l.get("ipc") else "") + (" rc " + str(l["rc"]) if l["rc"] else ""))
    if s.get("skalierung"):
        z += ["", "## Skalierung (Threads -> Beschleunigung, Effizienz)"] + [f"- {x['threads']} Threads: {x['wall_s']} s, x{x['beschleunigung']}, Effizienz {x['effizienz']}" for x in s["skalierung"]]
    if s.get("beste"): z += ["", f"Beste Zeit: {s['beste']['einstellung']} ({s['beste']['wall_s']:.1f} s)", f"Kleinste Einstellung innerhalb 5 %: {s['kleinste_innerhalb_5']['einstellung']} ({s['kleinste_innerhalb_5']['wall_s']:.1f} s)"]
    if s.get("energie_min"): z.append(f"Geringste Energie: {s['energie_min']['einstellung']} ({s['energie_min']['energie_j']} J)")
    z += ["", "## Vorschlaege (ANNAHME bis im Kettenlauf bestaetigt)"] + [f"- {x}" for x in s.get("vorschlaege", [])]
    return "\n".join(z) + "\n"


def _liste(s, typ=int):
    return [typ(x) for x in s.split(",") if x.strip()] if s else None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    befehl = []
    if "--" in argv: i = argv.index("--"); befehl = argv[i + 1:]; argv = argv[:i]
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); sp = ap.add_subparsers(dest="art", required=True)
    for n in ("messen", "sweep"):
        p = sp.add_parser(n); p.add_argument("--name", default="messung"); p.add_argument("--aus", default=None)
        p.add_argument("--takt", type=float, default=1.5); p.add_argument("--env", action="append", default=[], help="K=V fuer den Befehl"); p.add_argument("--perf", action="store_true")
        p.add_argument("--laut", action="store_true", help="Befehlsausgabe ins Terminal statt befehl.log")
        if n == "sweep":
            p.add_argument("--threads", default=None, help="z. B. 1,2,4,8,14,28"); p.add_argument("--param", action="append", default=[], help="NAME=w1,w2 ersetzt {NAME}")
            p.add_argument("--wait-policy", default=None, choices=("passive", "active")); p.add_argument("--binden", action="store_true")
            p.add_argument("--wiederholen", type=int, default=1); p.add_argument("--warmlauf", action="store_true")
        else: p.add_argument("--binden", type=int, default=None, help="auf die ersten N logischen CPUs legen")
    p = sp.add_parser("bericht"); p.add_argument("json")
    a = ap.parse_args(argv)
    if a.art == "bericht":
        d = json.load(open(a.json)); md = bericht_sweep(d) if "laeufe" in d else bericht_messung(d)
        open(os.path.join(os.path.dirname(os.path.abspath(a.json)), "bericht.md"), "w").write(md); print(md); return 0
    if not befehl: print("Befehl fehlt: ... -- BEFEHL ARGS", file=sys.stderr); return 2
    basis = "/media/oem/scan/rc-park_tmp/leistung" if os.path.isdir("/media/oem/scan/rc-park_tmp") else os.path.join(os.getcwd(), "leistung")
    aus = a.aus or os.path.join(basis, f"{a.name}_{time.strftime('%Y%m%d_%H%M%S')}")
    env = dict(kv.split("=", 1) for kv in a.env)
    if a.art == "messen":
        m = messen(befehl, aus, a.takt, env, a.perf, a.binden, 1.0, not a.laut)
        print(open(os.path.join(aus, "bericht.md")).read()); print("geschrieben:", aus); return 0 if m["rc"] == 0 else 1
    params = {}
    for pv in a.param:
        k, w = pv.split("=", 1); params[k] = [x for x in w.split(",") if x]
    s = sweep(befehl, aus, _liste(a.threads), params, a.wait_policy, a.binden, a.wiederholen, a.warmlauf, a.takt, a.perf, env)
    print(open(os.path.join(aus, "bericht.md")).read()); print("geschrieben:", aus)
    return 0 if all(l["rc"] == 0 for l in s["laeufe"]) else 1


if __name__ == "__main__":
    sys.exit(main())
