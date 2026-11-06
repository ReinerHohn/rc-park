#!/usr/bin/env python3
"""monitor.py - EINE Ansicht: CPU je Kern wie htop, GPU wie nvtop, dazu Takt, Leistung (Watt), Temperatur.
  sudo python3 tools/monitor.py            (mit sudo: Paketleistung in Watt via RAPL; ohne sudo fehlt nur die Wattzahl der CPU)
  python3 tools/monitor.py --einmal        (ein Messblock als Text, zum Pruefen/Loggen)
  Tasten: q = Ende.  Aktualisierung 1 s (Option --intervall 0.5).
Nur lesend (/proc, /sys, nvidia-smi); aendert nichts am System.
"""
import sys, os, time, glob, subprocess, argparse

def lese(pfad, default=None):
    try:
        with open(pfad) as f: return f.read().strip()
    except Exception: return default

def cpu_zeiten():
    z = {}
    for zeile in lese("/proc/stat", "").splitlines():
        if zeile.startswith("cpu") and zeile[3:4].isdigit():
            t = zeile.split(); n = int(t[0][3:]); w = list(map(int, t[1:9]))
            idle = w[3] + w[4]; z[n] = (sum(w), idle)
    return z

def temp_cpu():
    for h in glob.glob("/sys/class/hwmon/hwmon*"):
        if lese(h + "/name") == "coretemp":
            v = lese(h + "/temp1_input")
            if v: return int(v) / 1000
    return None

RAPL = "/sys/class/powercap/intel-rapl:0"
def energie():
    e = lese(RAPL + "/energy_uj")
    return int(e) if e and e.isdigit() else None

def gpu():
    q = "utilization.gpu,memory.used,memory.total,power.draw,power.limit,clocks.sm,clocks.max.sm,temperature.gpu"
    try:
        a = subprocess.run(["nvidia-smi", f"--query-gpu={q}", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3).stdout.strip().split(",")
        w = [x.strip() for x in a]
        def f(s):
            try: return float(s)
            except Exception: return 0.0
        return dict(util=f(w[0]), mem=f(w[1]), memmax=f(w[2]), watt=f(w[3]), limit=f(w[4]) or 140.0, mhz=f(w[5]), mhzmax=f(w[6]), temp=f(w[7]))
    except Exception:
        return None

def gpu_prozesse():
    try:
        o = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory,name", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3).stdout.strip()
        return [z.strip() for z in o.splitlines() if z.strip()][:3]
    except Exception:
        return []

def top_prozesse(n=5):
    try:
        o = subprocess.run(["ps", "-eo", "pcpu,pid,comm", "--sort=-pcpu"], capture_output=True, text=True, timeout=3).stdout.splitlines()[1:n + 1]
        return [z.strip() for z in o]
    except Exception:
        return []

def profil():
    return lese("/sys/class/platform-profile/platform-profile-0/profile", "-")

class Messer:
    def __init__(self):
        self.z0 = cpu_zeiten(); self.e0 = energie(); self.t0 = time.time()
        self.emax = int(lese(RAPL + "/max_energy_range_uj", "0") or 0)
    def messen(self):
        z1 = cpu_zeiten(); e1 = energie(); t1 = time.time(); dt = max(t1 - self.t0, 1e-3)
        last = {}
        for n, (g1, i1) in z1.items():
            g0, i0 = self.z0.get(n, (g1, i1)); dg = g1 - g0
            last[n] = 100.0 * (1 - (i1 - i0) / dg) if dg > 0 else 0.0
        watt = None
        if e1 is not None and self.e0 is not None:
            d = e1 - self.e0
            if d < 0 and self.emax: d += self.emax
            watt = d / 1e6 / dt
        self.z0, self.e0, self.t0 = z1, e1, t1
        mhz = {}
        for n in last:
            v = lese(f"/sys/devices/system/cpu/cpu{n}/cpufreq/scaling_cur_freq")
            mhz[n] = int(v) / 1000 if v and v.isdigit() else 0
        return dict(last=last, mhz=mhz, watt=watt, temp=temp_cpu())

def balken(p, breite, voll="|"):
    n = int(round(max(0, min(100, p)) / 100 * breite))
    return voll * n + " " * (breite - n)

def text_block(m, g, breite=100):
    """Reiner Text (fuer --einmal)."""
    L = []
    n = sorted(m["last"]); gesamt = sum(m["last"].values()) / max(len(n), 1)
    mhz_mittel = sum(m["mhz"].values()) / max(len(n), 1)
    w = "-- (sudo)" if m["watt"] is None else f"{m['watt']:6.1f} W"
    t = "--" if m["temp"] is None else f"{m['temp']:.0f} C"
    L.append(f"CPU  gesamt {gesamt:5.1f} %   Paket {w}   Temp {t}   Takt-Mittel {mhz_mittel:5.0f} MHz   Profil {profil()}")
    half = (len(n) + 1) // 2; bw = max(8, breite // 2 - 24)
    for i in range(half):
        zeile = ""
        for c in (n[i], n[i + half] if i + half < len(n) else None):
            if c is None: continue
            kern = "P" if c < 16 else "E"
            zeile += f"{c:2d}{kern} [{balken(m['last'][c], bw)}] {m['last'][c]:3.0f}% {m['mhz'][c]:4.0f}  "
        L.append(zeile)
    L.append("")
    if g:
        L.append(f"GPU  Last {g['util']:3.0f} %   Leistung {g['watt']:5.1f} / {g['limit']:.0f} W   Takt {g['mhz']:4.0f} / {g['mhzmax']:.0f} MHz   Temp {g['temp']:.0f} C")
        L.append(f"     VRAM {g['mem']:5.0f} / {g['memmax']:.0f} MiB [{balken(100 * g['mem'] / max(g['memmax'], 1), bw)}]")
    else:
        L.append("GPU  (nvidia-smi nicht erreichbar)")
    return L

def curses_lauf(intervall):
    import curses
    m_ = Messer(); time.sleep(0.5)
    def haupt(scr):
        curses.curs_set(0); curses.use_default_colors(); scr.timeout(int(intervall * 1000))
        curses.init_pair(1, curses.COLOR_GREEN, -1); curses.init_pair(2, curses.COLOR_YELLOW, -1); curses.init_pair(3, curses.COLOR_RED, -1); curses.init_pair(4, curses.COLOR_CYAN, -1)
        farbe = lambda p: curses.color_pair(1 if p < 60 else 2 if p < 90 else 3)
        while True:
            m = m_.messen(); g = gpu(); h, w = scr.getmaxyx(); scr.erase()
            def put(y, x, s, a=0):
                if 0 <= y < h - 1 and 0 <= x < w - 1: scr.addstr(y, x, s[:max(0, w - 1 - x)], a)
            n = sorted(m["last"]); gesamt = sum(m["last"].values()) / max(len(n), 1); mm = sum(m["mhz"].values()) / max(len(n), 1)
            wt = "-- (mit sudo starten)" if m["watt"] is None else f"{m['watt']:.1f} W"
            put(0, 0, "CPU ", curses.A_BOLD | curses.color_pair(4))
            put(0, 4, f"gesamt {gesamt:5.1f} %   Paket {wt}   Temp {'--' if m['temp'] is None else '%.0f C' % m['temp']}   Takt-Mittel {mm:.0f} MHz   Profil {profil()}", curses.A_BOLD)
            half = (len(n) + 1) // 2; spalte = max(40, (w - 2) // 2); bw = max(8, spalte - 26)
            for i in range(half):
                for k, c in enumerate((n[i], n[i + half] if i + half < len(n) else None)):
                    if c is None: continue
                    x = k * spalte; p = m["last"][c]
                    put(2 + i, x, f"{c:2d}{'P' if c < 16 else 'E'} [")
                    put(2 + i, x + 5, "|" * int(round(p / 100 * bw)), farbe(p))
                    put(2 + i, x + 5 + bw, f"] {p:3.0f}% {m['mhz'][c]:4.0f}MHz")
            y = 3 + half
            put(y, 0, "GPU ", curses.A_BOLD | curses.color_pair(4))
            if g:
                put(y, 4, f"Last {g['util']:3.0f} %   Leistung {g['watt']:5.1f} / {g['limit']:.0f} W   Takt {g['mhz']:4.0f} / {g['mhzmax']:.0f} MHz   Temp {g['temp']:.0f} C", curses.A_BOLD)
                for j, (name, p, txt) in enumerate((("Last", g["util"], f"{g['util']:3.0f}%"),
                                                    ("Watt", 100 * g["watt"] / (g["limit"] or 140), f"{g['watt']:5.1f} W"),
                                                    ("VRAM", 100 * g["mem"] / max(g["memmax"], 1), f"{g['mem']:.0f}/{g['memmax']:.0f} MiB"))):
                    put(y + 1 + j, 0, name + " ["); put(y + 1 + j, 6, "|" * int(round(p / 100 * bw)), farbe(p)); put(y + 1 + j, 6 + bw, "] " + txt)
                gp = gpu_prozesse()
                for j, z in enumerate(gp): put(y + 4 + j, 2, "GPU-Prozess: " + z)
                y += 4 + len(gp)
            else:
                put(y, 4, "(nvidia-smi nicht erreichbar)"); y += 1
            put(y + 1, 0, "Top-Prozesse (CPU %  PID  Name):", curses.A_BOLD)
            for j, z in enumerate(top_prozesse(5)): put(y + 2 + j, 2, z)
            put(h - 1, 0, "q = beenden", curses.A_DIM)
            scr.refresh()
            if scr.getch() in (ord("q"), ord("Q"), 27): break
    curses.wrapper(haupt)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--einmal", action="store_true"); ap.add_argument("--intervall", type=float, default=1.0)
    a = ap.parse_args()
    if a.einmal:
        m_ = Messer(); time.sleep(1.0); print("\n".join(text_block(m_.messen(), gpu())))
    else:
        curses_lauf(a.intervall)
